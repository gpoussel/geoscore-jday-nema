#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry"]
# ///
"""GeoScore - enregistrement rapide de parties GeoGuessr Duels."""
from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pycountry

from countries import is_valid as is_valid_country

STARTING_HP = 6000
STARTING_MULT = 1.0
MULT_STEP = 0.5
CSV_FILE = Path(__file__).resolve().parent / "games.csv"


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


COLUMNS = [
    "session", "game_id",
    "my_elo_before", "opp_elo", "elo_delta", "my_elo_after", "won",
    "total_rounds", "final_my_hp", "final_opp_hp",
    "round_num", "country", "my_score", "opp_score",
    "winner", "damage", "used_mult",
    "my_hp_after", "opp_hp_after", "my_mult_after", "opp_mult_after",
]


@dataclass
class Round:
    country: str
    my_score: int
    opp_score: int


def compute_state(rounds: list[Round]) -> list[dict]:
    my_hp, opp_hp = STARTING_HP, STARTING_HP
    my_mult, opp_mult = STARTING_MULT, STARTING_MULT
    history: list[dict] = []
    for r in rounds:
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


def fmt_mult(m: float) -> str:
    return f"{int(m)}x" if m == int(m) else f"{m}x"


def country_label(code: str) -> str:
    """Return 'Human name (code)' for display; falls back to the code alone."""
    code = code.strip().lower()
    if code == "uk":
        return f"United Kingdom ({code})"
    if ":" in code:
        cc, sub = code.split(":", 1)
        country_obj = pycountry.countries.get(alpha_2=cc.upper())
        sub_obj = pycountry.subdivisions.get(code=f"{cc.upper()}-{sub.upper()}")
        parts = [o.name for o in (country_obj, sub_obj) if o]
        base = " / ".join(parts) if parts else code
        return f"{base} ({code})"
    obj = pycountry.countries.get(alpha_2=code.upper())
    return f"{obj.name if obj else code} ({code})"


def known_countries_from_rows(rows: list[dict]) -> set[str]:
    return {r["country"].strip().lower() for r in rows if r.get("country")}


def ask_int(prompt: str, allow_abort: bool = False) -> int | None:
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if not raw:
            print(c("  Valeur requise.", C.RED))
            continue
        if allow_abort and raw.lower() in ("q", "quit"):
            return None
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


def play_rounds(known_countries: set[str]) -> list[Round] | None:
    rounds: list[Round] = []
    while True:
        history = compute_state(rounds)
        if history:
            my_hp = history[-1]["my_hp"]
            opp_hp = history[-1]["opp_hp"]
            my_mult = history[-1]["my_mult"]
            opp_mult = history[-1]["opp_mult"]
        else:
            my_hp, opp_hp = STARTING_HP, STARTING_HP
            my_mult, opp_mult = STARTING_MULT, STARTING_MULT

        if my_hp <= 0 or opp_hp <= 0:
            return rounds

        round_num = len(rounds) + 1
        prompt = (
            f"{c(f'R{round_num}', C.BOLD, C.BCYAN)} "
            f"[{c(my_hp, hp_color(my_hp))}-{c(opp_hp, hp_color(opp_hp))}] "
            f"{c(fmt_mult(my_mult), C.YELLOW)}/{c(fmt_mult(opp_mult), C.YELLOW)}"
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
        if cmd in ("u", "undo"):
            if rounds:
                last = rounds.pop()
                print(c(f"  Annule: {last.my_score}-{last.opp_score} {last.country}", C.YELLOW))
            else:
                print(c("  (rien a annuler)", C.DIM))
            continue

        parts = raw.split()
        if len(parts) != 3:
            print(c("  Format: mon_score adv_score pays  (ex: 4850 4200 fr)", C.RED))
            continue
        try:
            my_s = int(parts[0])
            opp_s = int(parts[1])
        except ValueError:
            print(c("  Scores invalides", C.RED))
            continue
        country = parts[2].lower()
        if not is_valid_country(country):
            print(c(f"  Code pays inconnu: {country!r} (ex: fr, uk, us:fl)", C.RED))
            continue
        if country not in known_countries:
            label = country_label(country)
            try:
                confirm = input(c(f"  Premier {label}. Confirmer ? [O/n] ", C.BYELLOW)).strip().lower()
            except EOFError:
                return None
            if confirm in ("n", "no", "non"):
                print(c("  Annule, retape le round.", C.DIM))
                continue
            known_countries.add(country)

        rounds.append(Round(country=country, my_score=my_s, opp_score=opp_s))
        s = compute_state(rounds)[-1]
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
        print(
            f"  {sym_c} {dmg_c} @ {c(fmt_mult(s['used_mult']), C.YELLOW)}"
            f" -> {c(s['my_hp'], hp_color(s['my_hp']))}-{c(s['opp_hp'], hp_color(s['opp_hp']))}"
            f" {c(next_info, C.DIM)}"
        )


def play_game(session: str, game_id: str, known_countries: set[str], default_my_elo: int | None = None) -> list[dict] | None:
    print(c("\n--- Nouvelle partie ---", C.BOLD, C.BCYAN))
    if default_my_elo is not None:
        raw = ask_str(f"Mon ELO [{c(default_my_elo, C.CYAN)}] {c('(q=annuler)', C.DIM)}: ")
        if raw.lower() in ("q", "quit"):
            return None
        if not raw:
            my_elo = default_my_elo
        else:
            try:
                my_elo = int(raw)
            except ValueError:
                print(c("  Nombre invalide, annulation.", C.RED))
                return None
    else:
        my_elo = ask_int(f"Mon ELO {c('(q=annuler)', C.DIM)}: ", allow_abort=True)
        if my_elo is None:
            return None
    opp_elo = ask_int("ELO adversaire: ")
    if opp_elo is None:
        return None

    rounds = play_rounds(known_countries)
    if not rounds:
        print(c("Partie abandonnee (non sauvegardee).", C.YELLOW))
        return None

    history = compute_state(rounds)
    final_my = history[-1]["my_hp"]
    final_opp = history[-1]["opp_hp"]
    won = final_my > 0
    if won:
        verdict = c("VICTOIRE", C.BOLD, C.BGREEN)
    else:
        verdict = c("DEFAITE", C.BOLD, C.BRED)
    print(
        f"\n{c('===', C.BOLD)} {verdict} "
        f"en {c(f'{len(rounds)}R', C.BOLD)} "
        f"({c(final_my, hp_color(final_my))}-{c(final_opp, hp_color(final_opp))}) "
        f"{c('===', C.BOLD)}"
    )

    delta = ask_int("Delta ELO (ex: +25, -18): ")
    if delta is None:
        delta = 0

    rows = []
    for i, (r, s) in enumerate(zip(rounds, history), start=1):
        rows.append({
            "session": session,
            "game_id": game_id,
            "my_elo_before": my_elo,
            "opp_elo": opp_elo,
            "elo_delta": delta,
            "my_elo_after": my_elo + delta,
            "won": won,
            "total_rounds": len(rounds),
            "final_my_hp": final_my,
            "final_opp_hp": final_opp,
            "round_num": i,
            "country": r.country,
            "my_score": r.my_score,
            "opp_score": r.opp_score,
            "winner": s["winner"],
            "damage": s["damage"],
            "used_mult": s["used_mult"],
            "my_hp_after": s["my_hp"],
            "opp_hp_after": s["opp_hp"],
            "my_mult_after": s["my_mult"],
            "opp_mult_after": s["opp_mult"],
        })
    return rows


def load_rows() -> list[dict]:
    if not CSV_FILE.exists():
        return []
    with CSV_FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_all(rows: list[dict]) -> None:
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def parse_sid(sid: str) -> tuple[int, int]:
    w, n = sid.split(".", 1)
    return int(w), int(n)


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


def _renumber_game_ids(rows: list[dict]) -> None:
    """Reassign zero-padded sequential game_ids by CSV position.

    All rows sharing the same input game_id end up with the same new id.
    After this pass, sorting games by id is equivalent to sorting by CSV
    order — which is chronological since sessions are contiguous and
    ordered by (week, num).
    """
    mapping: dict[str, str] = {}
    for r in rows:
        old = r["game_id"]
        if old not in mapping:
            mapping[old] = f"{len(mapping) + 1:04d}"
    for r in rows:
        r["game_id"] = mapping[r["game_id"]]


def save_rows(new_rows: list[dict]) -> None:
    """Insert new_rows into games.csv at the right position, then renumber.

    Games within a session are always appended in order, so the insertion
    point is right after the last existing row of the target session. For
    a brand-new session, slot it before the first existing session with a
    larger (week, num) so the CSV stays chronological. Every game_id is
    then reassigned sequentially so inserting a past session shifts later
    games' ids upward and the id ordering stays in sync with date order.
    """
    sid = new_rows[0]["session"]
    existing = load_rows()
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


def main() -> None:
    enable_ansi()
    print(f"{c('GeoScore', C.BOLD, C.BCYAN)} {c('-- fichier:', C.DIM)} {c(CSV_FILE, C.CYAN)}")
    iso_week = date.today().isocalendar().week
    all_rows = load_rows()
    last_sid = all_rows[-1]["session"] if all_rows else None
    if last_sid:
        last_count, _ = session_summary(all_rows, last_sid)
        try:
            default_week, default_num = parse_sid(last_sid)
        except ValueError:
            default_week, default_num = iso_week, 1
        print(c(f"Derniere session: {last_sid} ({last_count} partie(s))", C.DIM))
    else:
        default_week, default_num = iso_week, 1

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
    session = f"{week}.{num}"

    sess_count, sess_elo = session_summary(all_rows, session)
    if sess_count:
        tag = "reprise" if session != last_sid else "en cours"
        info = f"{sess_count} partie(s) existante(s), dernier ELO: {sess_elo} — {tag}"
    else:
        info = "nouvelle session"
    print(f"Session: {c(session, C.BOLD, C.BCYAN)} {c(f'({info})', C.DIM)}")
    print(c("Commandes pendant la saisie: u=undo, q=abandonner la partie\n", C.DIM))

    total = 0
    next_elo: int | None = sess_elo
    next_id = next_game_id(all_rows)
    known = known_countries_from_rows(all_rows)
    while True:
        rows = play_game(session, game_id=f"{next_id:04d}", known_countries=known, default_my_elo=next_elo)
        if rows:
            save_rows(rows)
            total += 1
            next_elo = rows[-1]["my_elo_after"]
            next_id += 1
            print(c(f"Sauvegarde. {total} partie(s) cette session.\n", C.GREEN))
        try:
            again = input(f"{c('[Entree]', C.BCYAN)}=nouvelle partie, {c('q', C.YELLOW)}=quitter> ").strip().lower()
        except EOFError:
            break
        if again in ("n", "no", "q", "quit"):
            break
    print(c(f"\nFin. {total} partie(s) enregistree(s) dans la session '{session}'.", C.BOLD))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("\nInterrompu.", C.YELLOW))
