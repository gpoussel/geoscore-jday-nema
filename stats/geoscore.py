#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry"]
# ///
"""GeoScore - enregistrement rapide de parties GeoGuessr Duels."""
from __future__ import annotations

import csv
import difflib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


from countries import is_valid as is_valid_country, COUNTRIES, name_of as country_name

STARTING_HP = 6000
STARTING_MULT = 1.0
MULT_STEP = 0.5
SHARED_MULT_START_ROUND = 5
GAME_MODES = ("move", "no-move")
OPP_COUNTRY_NOT_SHARED = "--"  # drapeau générique GeoGuessr
CSV_FILE = Path(__file__).resolve().parent / "games.csv"
SESSIONS_FILE = Path(__file__).resolve().parent / "sessions.json"
INDIVIDUAL_MULT_START_SESSION = "26W14.03"
INDIVIDUAL_MULT_START_FALLBACK_DATE = date(2026, 4, 1)


class C:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    CYAN = "\x1b[36m"
    BRED = "\x1b[91m"
    BGREEN = "\x1b[92m"
    BYELLOW = "\x1b[93m"
    BCYAN = "\x1b[96m"


def enable_ansi() -> None:
    if sys.platform == "win32":
        os.system("")


def hp_color(hp: int) -> str:
    if hp >= 4000:
        return C.BGREEN
    if hp >= 2000:
        return C.BYELLOW
    return C.BRED


def c(text: object, *codes: str) -> str:
    return f"{''.join(codes)}{text}{C.RESET}"


def shared_mult_for_round(round_num: int) -> float:
    if round_num < SHARED_MULT_START_ROUND:
        return STARTING_MULT
    return STARTING_MULT + (round_num - SHARED_MULT_START_ROUND + 1) * MULT_STEP


COLUMNS = [
    "session", "game_id", "mode",
    "my_elo_before", "opp_elo", "elo_delta", "my_elo_after", "won",
    "total_rounds", "final_my_hp", "final_opp_hp",
    "round_num", "country", "excluded", "my_score", "opp_score",
    "winner", "damage", "used_mult",
    "my_hp_after", "opp_hp_after", "my_mult_after", "opp_mult_after",
    "opp1_country", "opp2_country",
]


@dataclass
class Round:
    country: str
    my_score: int
    opp_score: int
    excluded: bool = False


@dataclass
class ParsedRound:
    country: str
    my_score: int
    opp_score: int
    excluded: bool = False


def compute_state(rounds: list[Round], *, shared_mult: bool = False) -> list[dict]:
    my_hp, opp_hp = STARTING_HP, STARTING_HP
    my_mult, opp_mult = STARTING_MULT, STARTING_MULT
    history: list[dict] = []
    for round_num, r in enumerate(rounds, start=1):
        if shared_mult:
            used = shared_mult_for_round(round_num)
            if r.my_score > r.opp_score:
                damage = math.floor((r.my_score - r.opp_score) * used + 0.5)
                opp_hp = max(0, opp_hp - damage)
                winner = "me"
            elif r.opp_score > r.my_score:
                damage = math.floor((r.opp_score - r.my_score) * used + 0.5)
                my_hp = max(0, my_hp - damage)
                winner = "opp"
            else:
                damage = 0
                winner = "tie"
            my_mult = shared_mult_for_round(round_num + 1)
            opp_mult = my_mult
        else:
            if r.my_score > r.opp_score:
                damage = math.floor((r.my_score - r.opp_score) * my_mult + 0.5)
                used = my_mult
                opp_hp = max(0, opp_hp - damage)
                my_mult += MULT_STEP
                winner = "me"
            elif r.opp_score > r.my_score:
                damage = math.floor((r.opp_score - r.my_score) * opp_mult + 0.5)
                used = opp_mult
                my_hp = max(0, my_hp - damage)
                opp_mult += MULT_STEP
                winner = "opp"
            else:
                damage = 0
                used = 0.0
                my_mult += MULT_STEP
                opp_mult += MULT_STEP
                winner = "tie"
        history.append({
            "winner": winner, "damage": damage, "used_mult": used,
            "my_hp": my_hp, "opp_hp": opp_hp,
            "my_mult": my_mult, "opp_mult": opp_mult,
        })
    return history


def result_from_elo_or_hp(elo_delta: int, final_my_hp: int, final_opp_hp: int) -> bool:
    """Use the observed ranked result when available, then fall back to HP."""
    if elo_delta != 0:
        return elo_delta > 0
    return final_my_hp > final_opp_hp


def fmt_mult(m: float) -> str:
    return f"{int(m)}x" if m == int(m) else f"{m}x"


def country_label(code: str) -> str:
    """Return 'Human name (code)' for display; falls back to the code alone."""
    code = code.strip().lower()
    return f"{country_name(code) or code} ({code})"


def normalize_country_code(code: str) -> str:
    code = code.strip().lower()
    if code.startswith("us:"):
        return "us"
    return code


def normalize_opp_country(raw: object) -> str:
    """'' = non renseigné, '--' = non communiqué, sinon code pays normalisé."""
    code = str(raw or "").strip().lower()
    if not code:
        return ""
    if code == OPP_COUNTRY_NOT_SHARED:
        return OPP_COUNTRY_NOT_SHARED
    return normalize_country_code(code)


def known_countries_from_rows(rows: list[dict]) -> set[str]:
    return {normalize_country_code(r["country"]) for r in rows if r.get("country")}


def csv_bool(value: object) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "y", "oui", "o")


def parse_country_marker(country: str) -> tuple[str, bool]:
    raw = country.strip().lower()
    excluded = raw.startswith("!") or raw.endswith("!")
    return raw.strip("!"), excluded


def print_round_help() -> None:
    print(c("Commandes:", C.BOLD, C.BCYAN))
    print("  fr 4850 4200     round duel")
    print("  4850 4200 fr     meme chose, pays a la fin")
    print("  fr 5000          egalite 5000-5000")
    print("  !fr 4850 4200    round exclu des stats (compte pour les HP)")
    print("  u                annuler le dernier round")
    print("  i 3 fr 5000 4200 inserer un round avant le round 3")
    print("  i end fr 5000    inserer un round a la fin")
    print("  e 3 fr 5000 4200 modifier le round 3")
    print("  d 3              supprimer le round 3")
    print("  g 3              revenir au round 3 (supprime les suivants)")
    print("  elo 1234         corriger l'ELO adversaire")
    print("  opp fr de        pays des adversaires (-- = non communiqué)")
    print("  nm               marquer la partie en no-move")
    print("  m                remettre la partie en move")
    print("  s                afficher le recapitulatif")
    print("  b                revenir a l'ELO adversaire")
    print("  q                abandonner la partie")


def print_rounds_summary(rounds: list[Round], opp_elo: int, *, shared_mult: bool = False) -> None:
    history = compute_state(rounds, shared_mult=shared_mult)
    mode = "multi commun" if shared_mult else "multi individuel"
    print(c(f"\nRecap partie - opp {opp_elo} - {mode}", C.BOLD, C.BCYAN))
    if not rounds:
        print(c("  Aucun round saisi.", C.DIM))
        return
    for i, (r, s) in enumerate(zip(rounds, history), start=1):
        if s["winner"] == "me":
            outcome = c("W", C.BGREEN, C.BOLD)
        elif s["winner"] == "opp":
            outcome = c("L", C.BRED, C.BOLD)
        else:
            outcome = c("=", C.BYELLOW, C.BOLD)
        marker = c("!", C.YELLOW, C.BOLD) if r.excluded else " "
        print(
            f"  {i:>2}. {outcome}{marker} {r.country:<6} "
            f"{r.my_score:>4}-{r.opp_score:<4} "
            f"dmg {s['damage']:>4} @ {fmt_mult(s['used_mult']):<4} "
            f"HP {s['my_hp']:>4}-{s['opp_hp']:<4} "
            f"next {fmt_mult(s['my_mult'])}/{fmt_mult(s['opp_mult'])}"
        )


def parse_round_input(raw: str) -> ParsedRound:
    parts = raw.split()
    if len(parts) not in (2, 3):
        raise ValueError("Format: 'fr 4850 4200' / '4850 4200 fr' (duel) ou 'fr 5000' / '5000 fr' (egalite)")

    try:
        if len(parts) == 2:
            try:
                my_s = int(parts[0])
                opp_s = my_s
                country = parts[1].lower()
            except ValueError:
                country = parts[0].lower()
                my_s = int(parts[1])
                opp_s = my_s
        else:
            try:
                my_s = int(parts[0])
                opp_s = int(parts[1])
                country = parts[2].lower()
            except ValueError:
                country = parts[0].lower()
                my_s = int(parts[1])
                opp_s = int(parts[2])
    except (ValueError, IndexError) as exc:
        raise ValueError("Format invalide. Scores requis (entiers).") from exc

    if not (0 <= my_s <= 5000 and 0 <= opp_s <= 5000):
        raise ValueError("Scores hors bornes (0-5000)")
    country, excluded = parse_country_marker(country)
    return ParsedRound(country=country, my_score=my_s, opp_score=opp_s, excluded=excluded)


def resolve_country(country: str) -> str | None:
    country = normalize_country_code(country)
    if is_valid_country(country):
        return country

    country_names_map = {}
    for code in COUNTRIES:
        name = country_name(code)
        if name:
            country_names_map[name.lower()] = code

    matches = difflib.get_close_matches(country, country_names_map.keys(), n=1, cutoff=0.6)
    if not matches:
        print(c(f"  Code pays inconnu et aucun match trouve pour: {country!r}", C.RED))
        return None

    matched_name = matches[0]
    matched_code = country_names_map[matched_name]
    print(c(f"  Fuzzy match: {country!r} -> {matched_name} ({matched_code})", C.CYAN))
    return matched_code


def opp_country_label(code: str) -> str:
    if not code:
        return "non renseigné"
    if code == OPP_COUNTRY_NOT_SHARED:
        return "non communiqué"
    return country_label(code)


def resolve_opp_country(raw: str) -> str | None:
    """Un jeton pays adverse: '--' ou un code/nom de pays (fuzzy match)."""
    raw = raw.strip().lower()
    if raw == OPP_COUNTRY_NOT_SHARED:
        return OPP_COUNTRY_NOT_SHARED
    return resolve_country(raw)


def parse_opp_countries(raw: str) -> tuple[str, str] | None:
    """Parse 'fr de' / 'fr --' / '--' / 'fr' en (opp1, opp2). None si invalide."""
    parts = raw.split()
    if len(parts) == 1 and parts[0] == OPP_COUNTRY_NOT_SHARED:
        return OPP_COUNTRY_NOT_SHARED, OPP_COUNTRY_NOT_SHARED
    if len(parts) not in (1, 2):
        print(c("  Format: 'fr de', 'fr --', '--' (les deux non communiqués)", C.RED))
        return None
    resolved: list[str] = []
    for part in parts:
        code = resolve_opp_country(part)
        if code is None:
            return None
        resolved.append(code)
    if len(resolved) == 1:
        print(c("  2e pays adverse laissé non renseigné.", C.DIM))
        return resolved[0], ""
    return resolved[0], resolved[1]


def confirm_new_country(country: str, known_countries: set[str]) -> bool:
    if country in known_countries:
        return True
    label = country_label(country)
    try:
        confirm = input(c(f"  Premier {label}. Confirmer ? [O/n] ", C.BYELLOW)).strip().lower()
    except EOFError:
        return False
    if confirm in ("n", "no", "non"):
        print(c("  Annule, retape le round.", C.DIM))
        return False
    known_countries.add(country)
    return True


def parse_round_index(raw: str, rounds: list[Round], *, allow_end: bool = False) -> int | None:
    if not rounds and not allow_end:
        print(c("  Aucun round saisi.", C.DIM))
        return None
    if allow_end and raw.strip().lower() in ("end", "fin", "+"):
        return len(rounds)
    try:
        idx = int(raw)
    except ValueError:
        print(c("  Numero de round invalide.", C.RED))
        return None
    max_idx = len(rounds) if not allow_end else len(rounds) + 1
    if not (1 <= idx <= max_idx):
        print(c(f"  Round hors bornes (1-{max_idx}).", C.RED))
        return None
    return idx - 1


def ask_int(prompt: str, allow_abort: bool = False, allow_undo: bool = False) -> int | str | None:
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if not raw:
            print(c("  Valeur requise.", C.RED))
            continue
        low = raw.lower()
        if allow_abort and low in ("q", "quit"):
            return None
        if allow_undo and low in ("u", "undo"):
            return "undo"
        try:
            return int(raw)
        except ValueError:
            print(c("  Nombre invalide.", C.RED))


def ask_str(prompt: str, default: str = "") -> str:
    try:
        raw = input(prompt).strip()
    except EOFError:
        return default
    return raw or default


def ask_elo_result(prompt: str, current_elo: int) -> tuple[int, int] | str | None:
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if not raw:
            print(c("  Valeur requise.", C.RED))
            continue
        low = raw.lower()
        if low in ("u", "undo"):
            return "undo"
        if low in ("r", "rounds", "edit", "rounds-edit"):
            return "rounds"
        try:
            value = int(raw)
        except ValueError:
            print(c("  Nombre invalide.", C.RED))
            continue

        if raw[0] in "+-":
            delta = value
            new_elo = current_elo + delta
        else:
            new_elo = value
            delta = new_elo - current_elo
        print(c(f"  ELO: {current_elo} -> {new_elo} ({delta:+d})", C.DIM))
        return delta, new_elo


def ask_opp_countries(default: tuple[str, str] = ("", "")) -> tuple[str, str]:
    prompt = (
        f"Pays adverses (ex: fr de, -- = non communiqué) "
        f"{c('[Entrée=non renseigné]', C.DIM)}: "
    )
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return default
        if not raw:
            return default
        parsed = parse_opp_countries(raw)
        if parsed is not None:
            return parsed


def build_game_rows(
    *,
    session: str,
    game_id: str,
    game_mode: str,
    my_elo: int,
    opp_elo: int,
    delta: int,
    new_elo: int,
    rounds: list[Round],
    history: list[dict],
    final_my: int,
    final_opp: int,
    opp1_country: str = "",
    opp2_country: str = "",
) -> list[dict]:
    won = result_from_elo_or_hp(delta, final_my, final_opp)
    rows = []
    for i, (r, s) in enumerate(zip(rounds, history), start=1):
        rows.append({
            "session": session,
            "game_id": game_id,
            "mode": game_mode,
            "my_elo_before": my_elo,
            "opp_elo": opp_elo,
            "elo_delta": delta,
            "my_elo_after": new_elo,
            "won": won,
            "total_rounds": len(rounds),
            "final_my_hp": final_my,
            "final_opp_hp": final_opp,
            "round_num": i,
            "country": r.country,
            "excluded": r.excluded,
            "my_score": r.my_score,
            "opp_score": r.opp_score,
            "winner": s["winner"],
            "damage": s["damage"],
            "used_mult": s["used_mult"],
            "my_hp_after": s["my_hp"],
            "opp_hp_after": s["opp_hp"],
            "my_mult_after": s["my_mult"],
            "opp_mult_after": s["opp_mult"],
            "opp1_country": opp1_country,
            "opp2_country": opp2_country,
        })
    return rows


def normalize_game_mode(raw: str) -> str | None:
    mode = raw.strip().lower().replace("_", "-")
    if mode in ("", "m", "move"):
        return "move"
    if mode in ("n", "nm", "no", "nomove", "no-move"):
        return "no-move"
    return None


def play_rounds(
    known_countries: set[str],
    opp_elo: int,
    rounds: list[Round] | None = None,
    *,
    shared_mult: bool = False,
    game_mode: str = "move",
    allow_finished_edit: bool = False,
    opp_countries: list[str] | None = None,
) -> tuple[list[Round], int, str] | str | None:
    if rounds is None:
        rounds = []
    current_opp_elo = opp_elo
    current_game_mode = game_mode
    while True:
        history = compute_state(rounds, shared_mult=shared_mult)
        if history:
            my_hp = history[-1]["my_hp"]
            opp_hp = history[-1]["opp_hp"]
            my_mult = history[-1]["my_mult"]
            opp_mult = history[-1]["opp_mult"]
        else:
            my_hp, opp_hp = STARTING_HP, STARTING_HP
            my_mult, opp_mult = STARTING_MULT, STARTING_MULT

        if (my_hp <= 0 or opp_hp <= 0) and rounds and not allow_finished_edit:
            return rounds, current_opp_elo, current_game_mode

        round_num = len(rounds) + 1
        round_label = "R*" if (my_hp <= 0 or opp_hp <= 0) and rounds else f"R{round_num}"
        prompt = (
            f"{c(round_label, C.BOLD, C.BCYAN)} "
            f"[{c(my_hp, hp_color(my_hp))}-{c(opp_hp, hp_color(opp_hp))}] "
            f"{c(fmt_mult(my_mult), C.YELLOW)}/{c(fmt_mult(opp_mult), C.YELLOW)} "
            f"{c(f'(opp: {current_opp_elo}, {current_game_mode})', C.DIM)} "
            f"{c('> ', C.BCYAN)}"
        )
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if not raw:
            continue
        cmd = raw.lower()
        if cmd in ("q", "abort"):
            return None
        if cmd in ("b", "back", "retour"):
            return "back"
        if allow_finished_edit and cmd in ("ok", "done", "fin", "valider"):
            return rounds, current_opp_elo, current_game_mode
        if cmd in ("h", "help", "?"):
            print_round_help()
            continue
        if cmd in ("s", "show", "recap"):
            print_rounds_summary(rounds, current_opp_elo, shared_mult=shared_mult)
            continue
        if cmd in ("nm", "no-move", "nomove"):
            current_game_mode = "no-move"
            print(c("  Mode: no-move", C.CYAN))
            continue
        if cmd in ("m", "move"):
            current_game_mode = "move"
            print(c("  Mode: move", C.CYAN))
            continue
        if cmd in ("u", "undo"):
            if rounds:
                last = rounds.pop()
                marker = " !" if last.excluded else ""
                print(c(f"  Annule: {last.my_score}-{last.opp_score} {last.country}{marker}", C.YELLOW))
            else:
                print(c("  (rien a annuler)", C.DIM))
            continue

        parts = raw.split()
        if parts and parts[0].lower() in ("i", "ins", "insert", "insert-before", "ajout"):
            if len(parts) < 4:
                print(c("  Format: i <round|end> <pays score score>", C.RED))
                continue
            idx = parse_round_index(parts[1], rounds, allow_end=True)
            if idx is None:
                continue
            try:
                parsed = parse_round_input(" ".join(parts[2:]))
            except ValueError as exc:
                print(c(f"  {exc}", C.RED))
                continue
            country = resolve_country(parsed.country)
            if country is None or not confirm_new_country(country, known_countries):
                continue
            was_end = idx == len(rounds)
            rounds.insert(idx, Round(
                country=country,
                my_score=parsed.my_score,
                opp_score=parsed.opp_score,
                excluded=parsed.excluded,
            ))
            where = "fin" if was_end else f"avant R{idx + 1}"
            marker = " !" if parsed.excluded else ""
            print(c(f"  Insere R{idx + 1} ({where}): {parsed.my_score}-{parsed.opp_score} {country}{marker}", C.CYAN))
            print_rounds_summary(rounds, current_opp_elo, shared_mult=shared_mult)
            continue

        if parts and parts[0].lower() in ("d", "del", "delete", "suppr"):
            if len(parts) != 2:
                print(c("  Format: d <round>", C.RED))
                continue
            idx = parse_round_index(parts[1], rounds)
            if idx is None:
                continue
            removed = rounds.pop(idx)
            marker = " !" if removed.excluded else ""
            print(c(f"  Supprime R{idx + 1}: {removed.my_score}-{removed.opp_score} {removed.country}{marker}", C.YELLOW))
            print_rounds_summary(rounds, current_opp_elo, shared_mult=shared_mult)
            continue

        if parts and parts[0].lower() in ("g", "go"):
            if len(parts) != 2:
                print(c("  Format: g <round>", C.RED))
                continue
            idx = parse_round_index(parts[1], rounds, allow_end=True)
            if idx is None:
                continue
            if idx < len(rounds):
                removed = len(rounds) - idx
                del rounds[idx:]
                print(c(f"  Retour a R{idx + 1}: {removed} round(s) supprime(s).", C.YELLOW))
            else:
                print(c("  Deja au prochain round.", C.DIM))
            continue

        if parts and parts[0].lower() in ("e", "edit"):
            if len(parts) < 3:
                print(c("  Format: e <round> <pays score score>", C.RED))
                continue
            idx = parse_round_index(parts[1], rounds)
            if idx is None:
                continue
            try:
                parsed = parse_round_input(" ".join(parts[2:]))
            except ValueError as exc:
                print(c(f"  {exc}", C.RED))
                continue
            country = resolve_country(parsed.country)
            if country is None or not confirm_new_country(country, known_countries):
                continue
            old = rounds[idx]
            rounds[idx] = Round(
                country=country,
                my_score=parsed.my_score,
                opp_score=parsed.opp_score,
                excluded=parsed.excluded,
            )
            old_marker = " !" if old.excluded else ""
            marker = " !" if parsed.excluded else ""
            print(c(f"  Modifie R{idx + 1}: {old.my_score}-{old.opp_score} {old.country}{old_marker} -> {parsed.my_score}-{parsed.opp_score} {country}{marker}", C.CYAN))
            print_rounds_summary(rounds, current_opp_elo, shared_mult=shared_mult)
            continue

        if len(parts) == 2 and parts[0].lower() == "elo":
            try:
                current_opp_elo = int(parts[1])
                print(c(f"  ELO adversaire corrige: {current_opp_elo}", C.CYAN))
                continue
            except ValueError:
                pass

        if parts and parts[0].lower() == "opp":
            if opp_countries is None:
                print(c("  Pays adverses non gérés ici.", C.DIM))
                continue
            if len(parts) < 2:
                print(c(f"  Pays adverses: {opp_country_label(opp_countries[0])} / {opp_country_label(opp_countries[1])}", C.CYAN))
                continue
            parsed_opp = parse_opp_countries(" ".join(parts[1:]))
            if parsed_opp is not None:
                opp_countries[0], opp_countries[1] = parsed_opp
                print(c(f"  Pays adverses: {opp_country_label(parsed_opp[0])} / {opp_country_label(parsed_opp[1])}", C.CYAN))
            continue

        try:
            parsed = parse_round_input(raw)
        except ValueError as exc:
            print(c(f"  {exc}", C.RED))
            continue

        country = resolve_country(parsed.country)
        if country is None or not confirm_new_country(country, known_countries):
            continue

        rounds.append(Round(
            country=country,
            my_score=parsed.my_score,
            opp_score=parsed.opp_score,
            excluded=parsed.excluded,
        ))
        s = compute_state(rounds, shared_mult=shared_mult)[-1]
        if s["winner"] == "me":
            sym_c = c("W", C.BOLD, C.BGREEN)
            dmg_c = c(f"+{s['damage']}", C.BGREEN)
        elif s["winner"] == "opp":
            sym_c = c("L", C.BOLD, C.BRED)
            dmg_c = c(f"-{s['damage']}", C.BRED)
        else:
            sym_c = c("=", C.BOLD, C.BYELLOW)
            dmg_c = c(f"{s['damage']}", C.BYELLOW)
        next_info = f"(next {fmt_mult(s['my_mult'])}/{fmt_mult(s['opp_mult'])})"
        label = country_label(country)
        stat_info = c(" [hors stats]", C.YELLOW) if parsed.excluded else ""
        print(
            f"  {sym_c} {dmg_c} @ {c(fmt_mult(s['used_mult']), C.YELLOW)}"
            f" -> {c(s['my_hp'], hp_color(s['my_hp']))}-{c(s['opp_hp'], hp_color(s['opp_hp']))}"
            f" {c(next_info, C.DIM)} {c(f'[{label}]', C.DIM)}{stat_info}"
        )


def play_game(
    session: str,
    game_id: str,
    known_countries: set[str],
    default_my_elo: int | None = None,
    *,
    shared_mult: bool = False,
) -> list[dict] | None:
    print(c("\n--- Nouvelle partie ---", C.BOLD, C.BCYAN))
    mode = "commun" if shared_mult else "individuel"
    print(c(f"Multiplicateur: {mode}", C.DIM))
    game_mode = "move"
    print(c("Mode: move (commande nm pour no-move)", C.DIM))
    my_elo = default_my_elo

    while True:
        # 1. Mon ELO
        if my_elo is None:
            res = ask_int(f"Mon ELO {c('(q=annuler)', C.DIM)}: ", allow_abort=True)
            if res is None: return None
            my_elo = res

        # 2. ELO adversaire
        res = ask_int(f"ELO adversaire {c('(u=retour)', C.DIM)}: ", allow_abort=True, allow_undo=True)
        if res is None: return None
        if res == "undo":
            my_elo = None
            continue
        opp_elo = res

        opp_countries = list(ask_opp_countries())

        # 3 & 4. Rounds and Delta
        rounds_list: list[Round] = []
        current_opp_elo = opp_elo
        while True:
            res_rounds = play_rounds(
                known_countries,
                current_opp_elo,
                rounds_list,
                shared_mult=shared_mult,
                game_mode=game_mode,
                opp_countries=opp_countries,
            )
            if res_rounds is None:
                print(c("Partie abandonnee (non sauvegardee).", C.YELLOW))
                return None
            if res_rounds == "back":
                print(c("Retour a l'ELO adversaire.", C.YELLOW))
                break
            rounds_list, current_opp_elo, game_mode = res_rounds

            history = compute_state(rounds_list, shared_mult=shared_mult)
            final_my = history[-1]["my_hp"]
            final_opp = history[-1]["opp_hp"]
            hp_won = final_my > final_opp
            if hp_won:
                verdict = c("VICTOIRE", C.BOLD, C.BGREEN)
            else:
                verdict = c("DEFAITE", C.BOLD, C.BRED)
            print(
                f"\n{c('===', C.BOLD)} {verdict} "
                f"en {c(f'{len(rounds_list)}R', C.BOLD)} "
                f"({c(final_my, hp_color(final_my))}-{c(final_opp, hp_color(final_opp))}) "
                f"{c('===', C.BOLD)}"
            )

            res_elo = ask_elo_result(
                f"Delta ELO ou nouvel ELO (ex: +25, -18, {my_elo + 25}) {c('(u=undo, r=rounds)', C.DIM)}: ",
                my_elo,
            )
            if res_elo == "undo":
                if rounds_list:
                    last = rounds_list.pop()
                    marker = " !" if last.excluded else ""
                    print(c(f"  Annule: {last.my_score}-{last.opp_score} {last.country}{marker}", C.YELLOW))
                    continue
                else:
                    print(c("  (rien a annuler)", C.DIM))
                    break # back to ELO adversaire prompt
            if res_elo == "rounds":
                print(c("Retour a l'edition des rounds. Commande ok pour revenir a l'ELO.", C.YELLOW))
                res_rounds = play_rounds(
                    known_countries,
                    current_opp_elo,
                    rounds_list,
                    shared_mult=shared_mult,
                    game_mode=game_mode,
                    allow_finished_edit=True,
                    opp_countries=opp_countries,
                )
                if res_rounds is None:
                    print(c("Partie abandonnee (non sauvegardee).", C.YELLOW))
                    return None
                if res_rounds == "back":
                    print(c("Retour a l'ELO adversaire.", C.YELLOW))
                    break
                rounds_list, current_opp_elo, game_mode = res_rounds
                continue
            if res_elo is None:
                print(c("Partie abandonnee (non sauvegardee).", C.YELLOW))
                return None

            delta, new_elo = res_elo
            rows = build_game_rows(
                session=session,
                game_id=game_id,
                game_mode=game_mode,
                my_elo=my_elo,
                opp_elo=current_opp_elo,
                delta=delta,
                new_elo=new_elo,
                rounds=rounds_list,
                history=history,
                final_my=final_my,
                final_opp=final_opp,
                opp1_country=opp_countries[0],
                opp2_country=opp_countries[1],
            )
            return rows


def load_rows() -> list[dict]:
    if not CSV_FILE.exists():
        return []
    with CSV_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["mode"] = normalize_game_mode(r.get("mode", "")) or "move"
        r["country"] = normalize_country_code(r.get("country", ""))
        r["excluded"] = str(csv_bool(r.get("excluded", False)))
        r["opp1_country"] = normalize_opp_country(r.get("opp1_country", ""))
        r["opp2_country"] = normalize_opp_country(r.get("opp2_country", ""))
    return rows


def load_sessions_meta() -> dict:
    if not SESSIONS_FILE.exists():
        return {}
    with SESSIONS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def write_all(rows: list[dict]) -> None:
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def regenerate_data() -> bool:
    """Rebuild frontend stats after games.csv has been durably updated."""
    try:
        from build_stats import main as build_stats_main

        build_stats_main()
    except SystemExit as exc:
        print(c(f"  Régénération des données échouée : {exc}", C.RED))
        return False
    except Exception as exc:
        print(c(f"  Régénération des données échouée : {exc}", C.RED))
        return False
    print(c("  Données régénérées.", C.GREEN))
    return True


def parse_sid(sid: str) -> tuple[int, int, int]:
    long_match = re.fullmatch(r"(\d{2})W(\d{2})\.(\d{2})", sid)
    if long_match:
        year, week, num = long_match.groups()
        return 2000 + int(year), int(week), int(num)

    legacy_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", sid)
    if legacy_match:
        week, num = legacy_match.groups()
        return 2026, int(week), int(num)

    raise ValueError(f"Invalid session id: {sid!r}")


def format_sid(year: int, week: int, num: int) -> str:
    return f"{year % 100:02d}W{week:02d}.{num:02d}"


def session_date_from_meta(session: str, sessions_meta: dict) -> date | None:
    raw = sessions_meta.get(session, {}).get("date")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def uses_shared_mult(session: str, sessions_meta: dict) -> bool:
    try:
        return parse_sid(session) < parse_sid(INDIVIDUAL_MULT_START_SESSION)
    except ValueError:
        session_date = session_date_from_meta(session, sessions_meta)
        if session_date is not None:
            return session_date < INDIVIDUAL_MULT_START_FALLBACK_DATE

        print(c(
            f"Session/date invalide pour {session}: multiplicateur individuel utilise par defaut.",
            C.YELLOW,
        ))
        return False


def next_game_id(rows: list[dict]) -> int:
    """Return (max existing numeric game_id) + 1. Ignores non-numeric ids."""
    max_id = 0
    for r in rows:
        try:
            n = int(r["game_id"])
        except (ValueError, KeyError):
            continue
        if n > max_id:
            max_id = n
    return max_id + 1


def session_summary(rows: list[dict], sid: str) -> tuple[int, int | None]:
    """Return (number of distinct games in session, last my_elo_after)."""
    games: set[str] = set()
    last_elo: int | None = None
    for r in rows:
        if r["session"] == sid:
            games.add(r["game_id"])
            try:
                last_elo = int(r["my_elo_after"])
            except (ValueError, KeyError):
                pass
    return len(games), last_elo


def previous_elo_before_session(rows: list[dict], sid: str) -> int | None:
    """Return the last known ELO before the target session starts."""
    try:
        target = parse_sid(sid)
    except ValueError:
        return None

    previous_elo: int | None = None
    previous_key: tuple[int, int, int] | None = None
    for r in rows:
        try:
            key = parse_sid(r["session"])
        except (KeyError, ValueError):
            continue
        if key >= target:
            continue
        if previous_key is None or key >= previous_key:
            try:
                previous_elo = int(r["my_elo_after"])
                previous_key = key
            except (KeyError, ValueError):
                pass
    return previous_elo


def _renumber_game_ids(rows: list[dict]) -> None:
    """Reassign zero-padded sequential game_ids by CSV position.

    Each contiguous block sharing the same game identity gets the same new id.
    After this pass, sorting games by id is equivalent to sorting by CSV
    order — which is chronological since sessions are contiguous and
    ordered by (year, week, num).
    """
    identity_fields = (
        "session", "game_id", "mode", "my_elo_before", "opp_elo",
        "elo_delta", "my_elo_after", "won", "total_rounds",
    )
    previous: tuple[str, ...] | None = None
    current = "0000"
    n = 0
    for r in rows:
        identity = tuple(r[field] for field in identity_fields)
        if identity != previous:
            n += 1
            current = f"{n:04d}"
            previous = identity
        r["game_id"] = current


def _assign_unique_pending_game_id(new_rows: list[dict], existing: list[dict]) -> None:
    existing_ids = {r.get("game_id", "") for r in existing}
    pending = "__pending_1"
    n = 1
    while pending in existing_ids:
        n += 1
        pending = f"__pending_{n}"
    for r in new_rows:
        r["game_id"] = pending


def save_rows(new_rows: list[dict]) -> None:
    """Insert new_rows into games.csv at the right position, then renumber.

    Games within a session are always appended in order, so the insertion
    point is right after the last existing row of the target session. For
    a brand-new session, slot it before the first existing session with a
    larger (year, week, num) so the CSV stays chronological. Every game_id is
    then reassigned sequentially so inserting a past session shifts later
    games' ids upward and the id ordering stays in sync with date order.
    """
    sid = new_rows[0]["session"]
    existing = load_rows()
    new_rows = [dict(r) for r in new_rows]
    _assign_unique_pending_game_id(new_rows, existing)
    if not existing:
        merged = list(new_rows)
    else:
        last_idx = -1
        for i, r in enumerate(existing):
            if r["session"] == sid:
                last_idx = i
        if last_idx >= 0:
            insert_at = last_idx + 1
        else:
            try:
                target = parse_sid(sid)
            except ValueError:
                insert_at = len(existing)
            else:
                insert_at = len(existing)
                seen: set[str] = set()
                for i, r in enumerate(existing):
                    s = r["session"]
                    if s in seen:
                        continue
                    seen.add(s)
                    try:
                        if parse_sid(s) > target:
                            insert_at = i
                            break
                    except ValueError:
                        continue
        merged = existing[:insert_at] + list(new_rows) + existing[insert_at:]
    _renumber_game_ids(merged)
    write_all(merged)


def correct_last_session_game_elo(session: str) -> int | None:
    rows = load_rows()
    last_game_id: str | None = None
    for r in rows:
        if r.get("session") == session:
            last_game_id = r.get("game_id")
    if last_game_id is None:
        print(c("  Aucune partie a corriger dans cette session.", C.DIM))
        return None

    game_rows = [
        r for r in rows
        if r.get("session") == session and r.get("game_id") == last_game_id
    ]
    if not game_rows:
        print(c("  Partie introuvable.", C.RED))
        return None

    head = game_rows[0]
    try:
        current_elo = int(head["my_elo_before"])
        old_delta = int(head["elo_delta"])
        old_elo = int(head["my_elo_after"])
        final_my = int(head["final_my_hp"])
        final_opp = int(head["final_opp_hp"])
    except (KeyError, ValueError):
        print(c("  ELO de la derniere partie illisible.", C.RED))
        return None

    print(
        c("Correction derniere partie: ", C.BOLD, C.BCYAN)
        + f"{last_game_id}, ELO {current_elo} -> {old_elo} ({old_delta:+d}), "
        + f"HP {final_my}-{final_opp}"
    )
    res = ask_elo_result("Nouveau delta ELO ou nouvel ELO: ", current_elo)
    if res is None or res in ("undo", "rounds"):
        print(c("  Correction annulee.", C.YELLOW))
        return None

    delta, new_elo = res
    won = result_from_elo_or_hp(delta, final_my, final_opp)
    for r in game_rows:
        r["elo_delta"] = delta
        r["my_elo_after"] = new_elo
        r["won"] = won
    write_all(rows)
    regenerate_data()
    print(c(f"  ELO corrige: {current_elo} -> {new_elo} ({delta:+d})", C.GREEN))
    return new_elo


def recompute_derived_columns(rows: list[dict], sessions_meta: dict) -> int:
    by_game: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in rows:
        gid = r["game_id"]
        if gid not in by_game:
            by_game[gid] = []
            order.append(gid)
        by_game[gid].append(r)

    changed = 0
    for gid in order:
        game_rows = sorted(by_game[gid], key=lambda x: int(x["round_num"]))
        session = game_rows[0]["session"]
        rounds = [
            Round(
                country=normalize_country_code(r["country"]),
                my_score=int(r["my_score"]),
                opp_score=int(r["opp_score"]),
                excluded=csv_bool(r.get("excluded", False)),
            )
            for r in game_rows
        ]
        history = compute_state(rounds, shared_mult=uses_shared_mult(session, sessions_meta))
        final_my = history[-1]["my_hp"]
        final_opp = history[-1]["opp_hp"]
        won = result_from_elo_or_hp(int(game_rows[0]["elo_delta"]), final_my, final_opp)

        for i, (r, s) in enumerate(zip(game_rows, history), start=1):
            updates = {
                "total_rounds": str(len(game_rows)),
                "final_my_hp": str(final_my),
                "final_opp_hp": str(final_opp),
                "won": str(won),
                "round_num": str(i),
                "winner": s["winner"],
                "damage": str(s["damage"]),
                "used_mult": str(s["used_mult"]),
                "my_hp_after": str(s["my_hp"]),
                "opp_hp_after": str(s["opp_hp"]),
                "my_mult_after": str(s["my_mult"]),
                "opp_mult_after": str(s["opp_mult"]),
            }
            for key, value in updates.items():
                if r.get(key) != value:
                    r[key] = value
                    changed += 1

    return changed


def main() -> None:
    enable_ansi()
    if any(arg == "--migrate-schema" for arg in sys.argv[1:]):
        rows = load_rows()
        write_all(rows)
        print(c(f"Schema CSV migre: {len(rows)} ligne(s), excluded=False par defaut.", C.GREEN))
        return

    if any(arg == "--fix-multipliers" for arg in sys.argv[1:]):
        sessions_meta = load_sessions_meta()
        rows = load_rows()
        changed = recompute_derived_columns(rows, sessions_meta)
        write_all(rows)
        print(c(f"Colonnes derivees recalculees: {changed} valeur(s) modifiee(s).", C.GREEN))
        return

    if any(arg in ("-h", "--help", "help") for arg in sys.argv[1:]):
        print(f"{c('GeoScore', C.BOLD, C.BCYAN)} - enregistrement rapide de parties GeoGuessr Duels")
        print("\nUsage:")
        print("  uv run geoscore.py")
        print("  uv run geoscore.py --migrate-schema")
        print("  uv run geoscore.py --fix-multipliers")
        print("\nSaisie des rounds:")
        print_round_help()
        return

    print(f"{c('GeoScore', C.BOLD, C.BCYAN)} {c('-- fichier:', C.DIM)} {c(CSV_FILE, C.CYAN)}")
    today_iso = date.today().isocalendar()
    iso_year = today_iso.year
    iso_week = today_iso.week
    all_rows = load_rows()
    sessions_meta = load_sessions_meta()
    last_sid = all_rows[-1]["session"] if all_rows else None

    if last_sid:
        last_count, _ = session_summary(all_rows, last_sid)
        try:
            default_year, default_week, default_num = parse_sid(last_sid)
        except ValueError:
            default_year, default_week, default_num = iso_year, iso_week, 1
        print(c(f"Derniere session: {last_sid} ({last_count} partie(s))", C.DIM))
    else:
        default_year, default_week, default_num = iso_year, iso_week, 1

    year_raw = ask_str(f"Annee ISO [{c(str(default_year)[-2:], C.CYAN)}]: ")
    try:
        year = int(year_raw) if year_raw else default_year
        if year < 100:
            year += 2000
    except ValueError:
        year = default_year
    week_raw = ask_str(f"Semaine [{c(default_week, C.CYAN)}]: ")
    try:
        week = int(week_raw) if week_raw else default_week
    except ValueError:
        week = default_week
    num_raw = ask_str(f"Session [{c(default_num, C.CYAN)}]: ")
    try:
        num = int(num_raw) if num_raw else default_num
    except ValueError:
        num = default_num
    session = format_sid(year, week, num)

    sess_count, sess_elo = session_summary(all_rows, session)
    if sess_elo is None:
        sess_elo = previous_elo_before_session(all_rows, session)

    if sess_count:
        tag = "reprise" if session != last_sid else "en cours"
        info = f"{sess_count} partie(s) existante(s), dernier ELO: {sess_elo} — {tag}"
    elif sess_elo is not None:
        info = f"nouvelle session, ELO precedent: {sess_elo}"
    else:
        info = "nouvelle session, aucun ELO precedent"
    print(f"Session: {c(session, C.BOLD, C.BCYAN)} {c(f'({info})', C.DIM)}")
    shared_mult = uses_shared_mult(session, sessions_meta)
    session_date = session_date_from_meta(session, sessions_meta)
    mode = "commun (ancien systeme)" if shared_mult else "individuel"
    date_info = f", date {session_date.isoformat()}" if session_date else ""
    print(c(f"Multiplicateur: {mode}{date_info}", C.DIM))
    print(c("Commandes pendant la saisie: h=aide, s=recap, u=undo, b=retour, q=abandonner\n", C.DIM))

    total = 0
    next_elo: int | None = sess_elo
    next_id = next_game_id(all_rows)
    known = known_countries_from_rows(all_rows)
    while True:
        rows = play_game(
            session,
            game_id=f"{next_id:04d}",
            known_countries=known,
            default_my_elo=next_elo,
            shared_mult=shared_mult,
        )
        if rows:
            save_rows(rows)
            regenerate_data()
            total += 1
            next_elo = rows[-1]["my_elo_after"]
            next_id += 1
            print(c(f"Sauvegarde. {total} partie(s) cette session.\n", C.GREEN))
        while True:
            try:
                again = input(
                    f"{c('[Entree]', C.BCYAN)}=nouvelle partie, "
                    f"{c('e', C.YELLOW)}=corriger dernier ELO, "
                    f"{c('q', C.YELLOW)}=quitter> "
                ).strip().lower()
            except EOFError:
                again = "q"
            if again in ("e", "elo", "corriger"):
                corrected_elo = correct_last_session_game_elo(session)
                if corrected_elo is not None:
                    next_elo = corrected_elo
                continue
            break
        if again in ("n", "no", "q", "quit"):
            break
    print(c(f"\nFin. {total} partie(s) enregistree(s) dans la session '{session}'.", C.BOLD))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("\nInterrompu.", C.YELLOW))
