#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry"]
# ///
"""Local mobile-friendly web recorder for GeoScore.

Run from stats/ with:
  uv run geoscore_server.py

The server is for local data entry only. It writes stats/games.csv through the
same helpers as geoscore.py, then regenerates src/data/stats.json and og.png.
"""
from __future__ import annotations

import argparse
import json
import socket
import threading
from dataclasses import asdict
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pycountry

import geoscore
from countries import COUNTRIES, is_valid as is_valid_country

ROOT = Path(__file__).resolve().parent
WRITE_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


class NewCountryError(ApiError):
    def __init__(self, country: str):
        super().__init__(
            f"Premier {country_label(country)}. Confirme avant d'enregistrer.",
            HTTPStatus.CONFLICT,
        )
        self.country = country


def country_label(code: str) -> str:
    code = geoscore.normalize_country_code(code)
    if code == "uk":
        return "United Kingdom (uk)"
    obj = pycountry.countries.get(alpha_2=code.upper())
    return f"{obj.name if obj else code} ({code})"


def country_options() -> list[dict[str, str]]:
    out = []
    for code in sorted(COUNTRIES):
        out.append({"code": code, "label": country_label(code)})
    return out


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise ApiError("Content-Length invalide") from exc
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError("JSON invalide") from exc
    if not isinstance(payload, dict):
        raise ApiError("Payload JSON invalide")
    return payload


def int_field(payload: dict, name: str, *, required: bool = True) -> int | None:
    value = payload.get(name)
    if value in (None, ""):
        if required:
            raise ApiError(f"Champ requis: {name}")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(f"Champ numérique invalide : {name}") from exc


def session_from_payload(payload: dict) -> str:
    explicit = str(payload.get("session") or "").strip()
    if explicit:
        try:
            geoscore.parse_sid(explicit)
        except ValueError as exc:
            raise ApiError(f"Session invalide : {explicit}") from exc
        return explicit
    year = int_field(payload, "year")
    week = int_field(payload, "week")
    num = int_field(payload, "num")
    if year is None or week is None or num is None:
        raise ApiError("Session incomplète")
    if year < 100:
        year += 2000
    return geoscore.format_sid(year, week, num)


def session_context(session: str | None = None) -> dict:
    rows = geoscore.load_rows()
    sessions_meta = geoscore.load_sessions_meta()
    today_iso = date.today().isocalendar()
    iso_year = today_iso.year
    iso_week = today_iso.week
    last_sid = rows[-1]["session"] if rows else None

    if session is None:
        if last_sid:
            try:
                year, week, num = geoscore.parse_sid(last_sid)
            except ValueError:
                year, week, num = iso_year, iso_week, 1
            session = geoscore.format_sid(year, week, num)
        else:
            year, week, num = iso_year, iso_week, 1
            session = geoscore.format_sid(iso_year, iso_week, 1)
    else:
        year, week, num = geoscore.parse_sid(session)

    count, session_elo = geoscore.session_summary(rows, session)
    if session_elo is None:
        session_elo = geoscore.previous_elo_before_session(rows, session)
    shared_mult = geoscore.uses_shared_mult(session, sessions_meta)
    session_date = geoscore.session_date_from_meta(session, sessions_meta)
    known = geoscore.known_countries_from_rows(rows)

    return {
        "session": session,
        "year": year,
        "week": week,
        "num": num,
        "sessionGameCount": count,
        "defaultMyElo": session_elo,
        "nextGameId": f"{geoscore.next_game_id(rows):04d}",
        "lastSession": last_sid,
        "sharedMult": shared_mult,
        "multLabel": "commun" if shared_mult else "individuel",
        "sessionDate": session_date.isoformat() if session_date else None,
        "knownCountries": sorted(known),
        "countries": country_options(),
        "lastGame": last_game_summary(rows, session),
    }


def last_game_summary(rows: list[dict], session: str) -> dict | None:
    last_gid = None
    for row in rows:
        if row.get("session") == session:
            last_gid = row.get("game_id")
    if last_gid is None:
        return None
    game_rows = [r for r in rows if r.get("session") == session and r.get("game_id") == last_gid]
    if not game_rows:
        return None
    head = game_rows[0]
    return {
        "gameId": last_gid,
        "myEloBefore": int(head["my_elo_before"]),
        "myEloAfter": int(head["my_elo_after"]),
        "eloDelta": int(head["elo_delta"]),
        "oppElo": int(head["opp_elo"]),
        "won": geoscore.csv_bool(head["won"]),
        "rounds": len(game_rows),
        "finalMyHp": int(head["final_my_hp"]),
        "finalOppHp": int(head["final_opp_hp"]),
    }


def parse_rounds(payload: dict, *, allow_new_countries: bool) -> list[geoscore.Round]:
    raw_rounds = payload.get("rounds")
    if not isinstance(raw_rounds, list):
        raise ApiError("Liste de rounds requise")
    known = geoscore.known_countries_from_rows(geoscore.load_rows())
    confirmed = {
        geoscore.normalize_country_code(str(c))
        for c in payload.get("confirmedNewCountries", [])
        if str(c).strip()
    }
    rounds: list[geoscore.Round] = []
    for idx, item in enumerate(raw_rounds, start=1):
        if not isinstance(item, dict):
            raise ApiError(f"Round {idx} : objet invalide")
        country = geoscore.normalize_country_code(str(item.get("country") or ""))
        if country.startswith("!") or country.endswith("!"):
            country, excluded = geoscore.parse_country_marker(country)
        else:
            excluded = bool(item.get("excluded", False))
        if not is_valid_country(country):
            resolved = geoscore.resolve_country(country)
            if resolved is None:
                raise ApiError(f"Round {idx} : pays inconnu : {country}")
            country = resolved
        if country not in known and country not in confirmed:
            if allow_new_countries:
                confirmed.add(country)
            else:
                raise NewCountryError(country)
        my_score = int_field(item, "myScore")
        opp_score = int_field(item, "oppScore")
        if my_score is None or opp_score is None:
            raise ApiError(f"Round {idx} : scores requis")
        if not (0 <= my_score <= 5000 and 0 <= opp_score <= 5000):
            raise ApiError(f"Round {idx} : scores hors bornes (0-5000)")
        rounds.append(geoscore.Round(country, my_score, opp_score, excluded))
    if not rounds:
        raise ApiError("Ajoute au moins un round")
    return rounds


def game_preview(payload: dict, *, allow_new_countries: bool = True) -> dict:
    session = session_from_payload(payload)
    my_elo = int_field(payload, "myElo")
    opp_elo = int_field(payload, "oppElo")
    if my_elo is None or opp_elo is None:
        raise ApiError("ELO requis")
    mode = geoscore.normalize_game_mode(str(payload.get("mode") or "move"))
    if mode is None:
        raise ApiError("Mode invalide")
    rounds = parse_rounds(payload, allow_new_countries=allow_new_countries)
    shared_mult = geoscore.uses_shared_mult(session, geoscore.load_sessions_meta())
    history = geoscore.compute_state(rounds, shared_mult=shared_mult)
    final = history[-1]
    return {
        "session": session,
        "mode": mode,
        "sharedMult": shared_mult,
        "rounds": [
            {
                **asdict(round_),
                "state": state,
                "label": country_label(round_.country),
            }
            for round_, state in zip(rounds, history)
        ],
        "finalMyHp": final["my_hp"],
        "finalOppHp": final["opp_hp"],
        "finished": final["my_hp"] <= 0 or final["opp_hp"] <= 0,
        "hpWon": final["my_hp"] > final["opp_hp"],
    }


def parse_elo_result(raw: object, current_elo: int) -> tuple[int, int]:
    text = str(raw or "").strip()
    if not text:
        raise ApiError("Delta ELO ou nouvel ELO requis")
    try:
        value = int(text)
    except ValueError as exc:
        raise ApiError("ELO invalide") from exc
    if text[0] in "+-":
        return value, current_elo + value
    return value - current_elo, value


def save_game(payload: dict) -> dict:
    preview = game_preview(payload, allow_new_countries=False)
    if not preview["finished"]:
        raise ApiError("La partie n'est pas terminée")
    session = preview["session"]
    my_elo = int_field(payload, "myElo")
    opp_elo = int_field(payload, "oppElo")
    if my_elo is None or opp_elo is None:
        raise ApiError("ELO requis")
    delta, new_elo = parse_elo_result(payload.get("eloResult"), my_elo)
    rounds = parse_rounds(payload, allow_new_countries=False)
    history = geoscore.compute_state(
        rounds,
        shared_mult=geoscore.uses_shared_mult(session, geoscore.load_sessions_meta()),
    )
    rows = geoscore.build_game_rows(
        session=session,
        game_id=f"{geoscore.next_game_id(geoscore.load_rows()):04d}",
        game_mode=preview["mode"],
        my_elo=my_elo,
        opp_elo=opp_elo,
        delta=delta,
        new_elo=new_elo,
        rounds=rounds,
        history=history,
        final_my=history[-1]["my_hp"],
        final_opp=history[-1]["opp_hp"],
    )
    with WRITE_LOCK:
        geoscore.save_rows(rows)
        regenerated = geoscore.regenerate_data()
    ctx = session_context(session)
    return {
        "ok": True,
        "regenerated": regenerated,
        "saved": {
            "session": session,
            "rounds": len(rows),
            "eloDelta": delta,
            "myEloAfter": new_elo,
        },
        "context": ctx,
    }


def correct_last_elo(payload: dict) -> dict:
    session = session_from_payload(payload)
    rows = geoscore.load_rows()
    last_gid = None
    for row in rows:
        if row.get("session") == session:
            last_gid = row.get("game_id")
    if last_gid is None:
        raise ApiError("Aucune partie à corriger dans cette session")
    game_rows = [r for r in rows if r.get("session") == session and r.get("game_id") == last_gid]
    head = game_rows[0]
    current_elo = int(head["my_elo_before"])
    final_my = int(head["final_my_hp"])
    final_opp = int(head["final_opp_hp"])
    delta, new_elo = parse_elo_result(payload.get("eloResult"), current_elo)
    won = geoscore.result_from_elo_or_hp(delta, final_my, final_opp)
    with WRITE_LOCK:
        for row in game_rows:
            row["elo_delta"] = delta
            row["my_elo_after"] = new_elo
            row["won"] = won
        geoscore.write_all(rows)
        regenerated = geoscore.regenerate_data()
    return {
        "ok": True,
        "regenerated": regenerated,
        "corrected": {"gameId": last_gid, "eloDelta": delta, "myEloAfter": new_elo},
        "context": session_context(session),
    }


HTML = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>GeoScore - saisie locale</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111316;
      --panel: #1b2026;
      --line: #303842;
      --text: #f4f6f8;
      --muted: #9ba7b4;
      --accent: #34d1bf;
      --win: #43d17a;
      --loss: #ff6b5f;
      --warn: #f2bd4b;
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
      font-size: 16px;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 10;
      background: rgba(17, 19, 22, .94);
      border-bottom: 1px solid var(--line);
      padding: max(12px, env(safe-area-inset-top)) 14px 10px;
      backdrop-filter: blur(12px);
    }
    h1 { margin: 0 0 3px; font-size: 20px; line-height: 1.1; }
    .sub { color: var(--muted); font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }
    main { max-width: 820px; margin: 0 auto; padding: 8px 12px 104px; }
    section {
      border-bottom: 1px solid var(--line);
      padding: 14px 0 16px;
    }
    h2 { margin: 0 0 10px; font-size: 12px; text-transform: uppercase; color: var(--muted); letter-spacing: .08em; }
    .grid { display: grid; gap: 10px; }
    .session-grid { grid-template-columns: 1fr 1fr 1fr; }
    .elo-grid, .correction-grid { grid-template-columns: 1fr; }
    .round-entry { grid-template-columns: 1fr 1fr; }
    .round-entry label:first-child { grid-column: 1 / -1; }
    label { display: grid; gap: 6px; font-size: 12px; color: var(--muted); min-width: 0; }
    input, select, button {
      width: 100%;
      min-height: 52px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      font: inherit;
      font-size: 16px;
      padding: 12px;
    }
    input { font-variant-numeric: tabular-nums; }
    input:focus { outline: 2px solid color-mix(in srgb, var(--accent), transparent 55%); }
    button {
      font-weight: 750;
      touch-action: manipulation;
      line-height: 1.1;
    }
    button.primary { background: var(--accent); color: #071311; border-color: transparent; }
    button.danger { border-color: color-mix(in srgb, var(--loss), transparent 30%); color: var(--loss); }
    button.ghost { background: transparent; }
    button:disabled { opacity: .45; }
    .seg { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
    .seg button.active { background: #e8eef2; color: #111316; border-color: transparent; }
    .sign-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; }
    .sign-row button.active { background: #e8eef2; color: #111316; border-color: transparent; }
    .row-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
    .rounds { display: grid; gap: 8px; margin-top: 12px; }
    .round {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr) 76px;
      gap: 10px;
      align-items: center;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 10px;
      text-align: left;
    }
    .round.selected { border-color: var(--accent); }
    .pill { display: inline-flex; align-items: center; justify-content: center; min-width: 28px; min-height: 28px; border-radius: 999px; background: #2a313a; font-weight: 800; }
    .round-main { min-width: 0; }
    .round-main strong { display: block; font-size: 15px; line-height: 1.25; overflow-wrap: anywhere; }
    .round-main span { display: block; color: var(--muted); font-size: 12px; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .state { font-variant-numeric: tabular-nums; font-size: 13px; color: var(--muted); text-align: right; line-height: 1.25; }
    .summary {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 12px;
    }
    .kpi { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px; min-width: 0; }
    .kpi:last-child { grid-column: 1 / -1; }
    .kpi span { display: block; color: var(--muted); font-size: 11px; }
    .kpi strong { display: block; margin-top: 4px; font-size: 18px; line-height: 1.15; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .status { min-height: 20px; margin-top: 10px; color: var(--muted); font-size: 13px; line-height: 1.35; }
    .status.ok { color: var(--win); }
    .status.err { color: var(--loss); }
    .status.warn { color: var(--warn); }
    .sticky-save {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(17, 19, 22, .95);
      border-top: 1px solid var(--line);
      padding: 10px 12px max(10px, env(safe-area-inset-bottom));
      box-shadow: 0 -10px 28px rgba(0,0,0,.28);
      z-index: 20;
    }
    .sticky-save > div { max-width: 820px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .sticky-save button { min-height: 54px; }
    @media (min-width: 480px) {
      .summary { grid-template-columns: repeat(3, 1fr); }
      .kpi:last-child { grid-column: auto; }
      .row-actions { grid-template-columns: repeat(4, 1fr); }
    }
    @media (min-width: 700px) {
      main { padding-inline: 18px; }
      section { padding-block: 18px; }
      .elo-grid, .correction-grid { grid-template-columns: 1fr 1fr; }
      .round-entry { grid-template-columns: 2fr 1fr 1fr; }
      .round-entry label:first-child { grid-column: auto; }
      .wide { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>GeoScore</h1>
    <div class="sub" id="topline">Saisie locale</div>
  </header>
  <main>
    <section>
      <h2>Session</h2>
      <div class="grid session-grid">
        <label>Annee ISO <input id="year" inputmode="numeric"></label>
        <label>Semaine <input id="week" inputmode="numeric"></label>
        <label>Session <input id="num" inputmode="numeric"></label>
      </div>
      <div class="status" id="sessionInfo"></div>
    </section>

    <section>
      <h2>Partie</h2>
      <div class="grid elo-grid">
        <label>Mon ELO <input id="myElo" inputmode="numeric"></label>
        <label>ELO adversaire <input id="oppElo" inputmode="numeric"></label>
      </div>
      <div class="seg">
        <button id="modeMove" type="button" class="active">Move</button>
        <button id="modeNoMove" type="button">No-move</button>
      </div>
    </section>

    <section>
      <h2>Rounds</h2>
      <div class="grid round-entry">
        <label>Pays <input id="country" list="countries" autocomplete="off" autocapitalize="none" placeholder="fr"></label>
        <label>Nous <input id="myScore" inputmode="numeric" placeholder="5000"></label>
        <label>Adv. <input id="oppScore" inputmode="numeric" placeholder="5000"></label>
      </div>
      <datalist id="countries"></datalist>
      <label style="display:flex;align-items:center;gap:8px;margin-top:10px">
        <input id="excluded" type="checkbox" style="min-height:0;width:20px;height:20px"> Hors stats
      </label>
      <div class="row-actions">
        <button id="addRound" type="button" class="primary">Ajouter</button>
        <button id="updateRound" type="button">Modifier</button>
        <button id="undoRound" type="button">Undo</button>
        <button id="deleteRound" type="button" class="danger">Suppr.</button>
      </div>
      <div class="rounds" id="rounds"></div>
      <div class="summary">
        <div class="kpi"><span>HP</span><strong id="hp">6000-6000</strong></div>
        <div class="kpi"><span>Issue HP</span><strong id="verdict">-</strong></div>
        <div class="kpi"><span>Rounds</span><strong id="roundCount">0</strong></div>
      </div>
      <div class="status" id="roundStatus"></div>
    </section>

    <section>
      <h2>ELO final</h2>
      <div class="sign-row">
        <button id="eloGain" type="button" class="active">Gain</button>
        <button id="eloLoss" type="button">Perte</button>
      </div>
      <label>Delta ELO <input id="eloResult" inputmode="numeric" pattern="[0-9]*" placeholder="12"></label>
      <div class="status" id="saveStatus"></div>
    </section>

    <section>
      <h2>Correction dernière partie</h2>
      <div class="status" id="lastGame">Aucune partie chargée.</div>
      <div class="sign-row">
        <button id="correctGain" type="button" class="active">Gain</button>
        <button id="correctLoss" type="button">Perte</button>
      </div>
      <div class="grid correction-grid">
        <label>Delta ELO corrigé <input id="correctElo" inputmode="numeric" pattern="[0-9]*" placeholder="18"></label>
        <button id="correctLast" type="button">Corriger</button>
      </div>
      <div class="status" id="correctStatus"></div>
    </section>
  </main>

  <div class="sticky-save">
    <div>
      <button id="resetGame" type="button" class="ghost">Nouvelle saisie</button>
      <button id="saveGame" type="button" class="primary">Enregistrer</button>
    </div>
  </div>

<script>
const $ = (id) => document.getElementById(id);
const state = { rounds: [], selected: -1, mode: "move", eloSign: "+", correctSign: "+", context: null, preview: null, confirmedNewCountries: [] };

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.data = data;
    throw err;
  }
  return data;
}

function sessionPayload() {
  return { year: $("year").value, week: $("week").value, num: $("num").value };
}

function gamePayload() {
  return {
    ...sessionPayload(),
    myElo: $("myElo").value,
    oppElo: $("oppElo").value,
    mode: state.mode,
    rounds: state.rounds,
    eloResult: signedValue("eloResult", state.eloSign),
    confirmedNewCountries: state.confirmedNewCountries,
  };
}

function signedValue(inputId, sign) {
  const raw = $(inputId).value.trim();
  if (!raw) return "";
  if (raw.startsWith("+") || raw.startsWith("-")) return raw;
  return `${sign}${raw}`;
}

function setStatus(id, text, kind = "") {
  const el = $(id);
  el.textContent = text || "";
  el.className = `status ${kind}`.trim();
}

function setEloSign(sign) {
  state.eloSign = sign;
  $("eloGain").classList.toggle("active", sign === "+");
  $("eloLoss").classList.toggle("active", sign === "-");
}

function setCorrectSign(sign) {
  state.correctSign = sign;
  $("correctGain").classList.toggle("active", sign === "+");
  $("correctLoss").classList.toggle("active", sign === "-");
}

function applyContext(ctx, keepGame = false) {
  state.context = ctx;
  $("year").value = String(ctx.year).slice(-2);
  $("week").value = ctx.week;
  $("num").value = ctx.num;
  if (!keepGame && ctx.defaultMyElo != null) $("myElo").value = ctx.defaultMyElo;
  $("topline").textContent = `${ctx.session} · multi ${ctx.multLabel} · prochain id ${ctx.nextGameId}`;
  const gameText = ctx.sessionGameCount ? `${ctx.sessionGameCount} partie(s), dernier ELO ${ctx.defaultMyElo}` : `Nouvelle session, ELO précédent ${ctx.defaultMyElo ?? "-"}`;
  setStatus("sessionInfo", `${gameText}${ctx.sessionDate ? " · " + ctx.sessionDate : ""}`);
  const datalist = $("countries");
  datalist.innerHTML = "";
  for (const c of ctx.countries) {
    const opt = document.createElement("option");
    opt.value = c.code;
    opt.label = c.label;
    datalist.appendChild(opt);
  }
  renderLastGame(ctx.lastGame);
}

function renderLastGame(game) {
  if (!game) {
    $("lastGame").textContent = "Aucune partie dans cette session.";
    return;
  }
  $("lastGame").textContent = `${game.gameId} · ${game.myEloBefore} -> ${game.myEloAfter} (${game.eloDelta >= 0 ? "+" : ""}${game.eloDelta}) · ${game.finalMyHp}-${game.finalOppHp} · ${game.rounds}R`;
}

function clearRoundForm() {
  $("country").value = "";
  $("myScore").value = "";
  $("oppScore").value = "";
  $("excluded").checked = false;
}

function focusCountry() {
  $("country").focus({ preventScroll: true });
}

function focusFinalElo() {
  $("eloResult").focus({ preventScroll: true });
}

function readRoundForm() {
  const country = $("country").value.trim().toLowerCase();
  const myScore = Number($("myScore").value);
  const oppScore = Number($("oppScore").value || $("myScore").value);
  if (!country) throw new Error("Pays requis");
  if (!Number.isInteger(myScore) || !Number.isInteger(oppScore)) throw new Error("Scores requis");
  if (myScore < 0 || myScore > 5000 || oppScore < 0 || oppScore > 5000) throw new Error("Scores hors bornes");
  return { country, myScore, oppScore, excluded: $("excluded").checked };
}

function selectRound(index) {
  state.selected = index;
  const r = state.rounds[index];
  if (r) {
    $("country").value = r.country;
    $("myScore").value = r.myScore;
    $("oppScore").value = r.oppScore;
    $("excluded").checked = !!r.excluded;
  }
  renderRounds();
}

function renderRounds() {
  const wrap = $("rounds");
  wrap.innerHTML = "";
  state.rounds.forEach((r, index) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `round ${index === state.selected ? "selected" : ""}`;
    item.onclick = () => selectRound(index);
    const previewRound = state.preview?.rounds?.[index];
    const st = previewRound?.state;
    const outcome = st ? (st.winner === "me" ? "W" : st.winner === "opp" ? "L" : "=") : "-";
    item.innerHTML = `
      <span class="pill">${index + 1}</span>
      <span class="round-main"><strong>${r.country}${r.excluded ? " !" : ""} · ${r.myScore}-${r.oppScore}</strong><span>${previewRound?.label || ""}</span></span>
      <span class="state">${outcome}<br>${st ? `${st.my_hp}-${st.opp_hp}` : ""}</span>`;
    wrap.appendChild(item);
  });
  $("roundCount").textContent = state.rounds.length;
  $("updateRound").disabled = state.selected < 0;
  $("deleteRound").disabled = state.selected < 0;
}

async function refreshContext(keepGame = true) {
  const q = new URLSearchParams(sessionPayload()).toString();
  const ctx = await api(`/api/context?${q}`);
  applyContext(ctx, keepGame);
}

async function refreshPreview() {
  renderRounds();
  if (!state.rounds.length || !$("myElo").value || !$("oppElo").value) {
    $("hp").textContent = "6000-6000";
    $("verdict").textContent = "-";
    setStatus("roundStatus", "");
    return;
  }
  try {
    state.preview = await api("/api/preview", { method: "POST", body: JSON.stringify(gamePayload()) });
    $("hp").textContent = `${state.preview.finalMyHp}-${state.preview.finalOppHp}`;
    $("verdict").textContent = state.preview.finished ? (state.preview.hpWon ? "Victoire" : "Defaite") : "En cours";
    if (state.preview.finished) {
      setEloSign(state.preview.hpWon ? "+" : "-");
      focusFinalElo();
    }
    setStatus("roundStatus", state.preview.finished ? "Partie terminée, saisis le delta ELO puis enregistre." : "Partie en cours.");
  } catch (err) {
    setStatus("roundStatus", err.message, "err");
  }
  renderRounds();
}

function resetGame(keepElo = true) {
  const nextElo = keepElo ? $("myElo").value : state.context?.defaultMyElo;
  state.rounds = [];
  state.selected = -1;
  state.preview = null;
  state.confirmedNewCountries = [];
  $("oppElo").value = "";
  $("eloResult").value = "";
  if (nextElo != null) $("myElo").value = nextElo;
  clearRoundForm();
  refreshPreview();
}

$("modeMove").onclick = () => {
  state.mode = "move";
  $("modeMove").classList.add("active");
  $("modeNoMove").classList.remove("active");
};
$("modeNoMove").onclick = () => {
  state.mode = "no-move";
  $("modeNoMove").classList.add("active");
  $("modeMove").classList.remove("active");
};
$("eloGain").onclick = () => {
  setEloSign("+");
};
$("eloLoss").onclick = () => {
  setEloSign("-");
};
$("correctGain").onclick = () => {
  setCorrectSign("+");
};
$("correctLoss").onclick = () => {
  setCorrectSign("-");
};
$("addRound").onclick = async () => {
  try {
    state.rounds.push(readRoundForm());
    state.selected = state.rounds.length - 1;
    clearRoundForm();
    await refreshPreview();
    if (!state.preview?.finished) focusCountry();
  } catch (err) { setStatus("roundStatus", err.message, "err"); }
};
$("updateRound").onclick = async () => {
  try {
    if (state.selected < 0) return;
    state.rounds[state.selected] = readRoundForm();
    clearRoundForm();
    await refreshPreview();
    if (!state.preview?.finished) focusCountry();
  } catch (err) { setStatus("roundStatus", err.message, "err"); }
};
$("undoRound").onclick = async () => {
  state.rounds.pop();
  state.selected = -1;
  await refreshPreview();
};
$("deleteRound").onclick = async () => {
  if (state.selected >= 0) state.rounds.splice(state.selected, 1);
  state.selected = -1;
  clearRoundForm();
  await refreshPreview();
};
$("saveGame").onclick = async () => {
  setStatus("saveStatus", "Enregistrement...", "warn");
  try {
    const data = await api("/api/save", { method: "POST", body: JSON.stringify(gamePayload()) });
    applyContext(data.context, true);
    $("myElo").value = data.saved.myEloAfter;
    resetGame(true);
    focusCountry();
    setStatus("saveStatus", `Sauvegarde OK · ${data.saved.session} · ELO ${data.saved.myEloAfter}`, "ok");
  } catch (err) {
    if (err.data?.country) {
      if (confirm(`${err.message}\n\nConfirmer ce pays et enregistrer ?`)) {
        state.confirmedNewCountries.push(err.data.country);
        $("saveGame").click();
        return;
      }
    }
    setStatus("saveStatus", err.message, "err");
  }
};
$("resetGame").onclick = () => resetGame();
$("correctLast").onclick = async () => {
  setStatus("correctStatus", "Correction...", "warn");
  try {
    const data = await api("/api/correct-last-elo", {
      method: "POST",
      body: JSON.stringify({ ...sessionPayload(), eloResult: signedValue("correctElo", state.correctSign) }),
    });
    applyContext(data.context, true);
    $("myElo").value = data.corrected.myEloAfter;
    $("correctElo").value = "";
    setStatus("correctStatus", `Correction OK · ELO ${data.corrected.myEloAfter}`, "ok");
  } catch (err) {
    setStatus("correctStatus", err.message, "err");
  }
};
for (const id of ["year", "week", "num"]) $(id).addEventListener("change", () => refreshContext(true).catch(err => setStatus("sessionInfo", err.message, "err")));
for (const id of ["myElo", "oppElo"]) $(id).addEventListener("change", refreshPreview);

(async function init() {
  try {
    const ctx = await api("/api/context");
    applyContext(ctx);
    renderRounds();
  } catch (err) {
    setStatus("sessionInfo", err.message, "err");
  }
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "GeoScoreLocal/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_html(self) -> None:
        raw = HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_html()
                return
            if parsed.path == "/api/context":
                qs = parse_qs(parsed.query)
                session = None
                if qs:
                    payload = {k: v[0] for k, v in qs.items() if v}
                    if any(payload.get(k) for k in ("session", "year", "week", "num")):
                        session = session_from_payload(payload)
                self.send_json(session_context(session))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ApiError as exc:
            self.send_json({"error": str(exc)}, exc.status)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = parse_json_body(self)
            if parsed.path == "/api/preview":
                self.send_json(game_preview(payload))
                return
            if parsed.path == "/api/save":
                self.send_json(save_game(payload))
                return
            if parsed.path == "/api/correct-last-elo":
                self.send_json(correct_last_elo(payload))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except NewCountryError as exc:
            self.send_json({"error": str(exc), "country": exc.country}, exc.status)
        except ApiError as exc:
            self.send_json({"error": str(exc)}, exc.status)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def local_interface_ips() -> list[str]:
    """Return IPv4 addresses that another device on the LAN can try."""
    ips: set[str] = set()
    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except OSError:
        pass

    try:
        _, _, host_ips = socket.gethostbyname_ex(hostname)
        for ip in host_ips:
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except OSError:
        pass

    # On some networks hostname resolution misses the active Wi-Fi/Ethernet IP.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except OSError:
        pass

    return sorted(ips)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur local de saisie GeoScore")
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'écoute (défaut : 0.0.0.0, toutes les interfaces)")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute (défaut : 8765)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"GeoScore local: http://127.0.0.1:{args.port}/", flush=True)
    if args.host in ("0.0.0.0", "::"):
        ips = local_interface_ips()
        if ips:
            print("Adresses accessibles depuis le même réseau :", flush=True)
            for ip in ips:
                print(f"  http://{ip}:{args.port}/", flush=True)
        else:
            print("Aucune adresse réseau non-loopback détectée.", flush=True)
    else:
        print(f"Adresse d'écoute demandée : http://{args.host}:{args.port}/", flush=True)
    print("Ctrl+C pour arrêter.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
