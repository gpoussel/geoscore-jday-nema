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
from datetime import date, datetime
from pathlib import Path

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


def play_rounds() -> list[Round] | None:
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


def play_game(session: str, default_my_elo: int | None = None) -> list[dict] | None:
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

    game_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    rounds = play_rounds()
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


def last_session() -> tuple[str | None, int, int | None]:
    """Retourne (nom_derniere_session, nb_parties, dernier_my_elo_after) ou (None, 0, None)."""
    if not CSV_FILE.exists():
        return None, 0, None
    with CSV_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None, 0, None
    name = rows[-1]["session"]
    games = {r["game_id"] for r in rows if r["session"] == name}
    try:
        last_elo = int(rows[-1]["my_elo_after"])
    except (ValueError, KeyError):
        last_elo = None
    return name, len(games), last_elo


def append_rows(rows: list[dict]) -> None:
    exists = CSV_FILE.exists()
    with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            w.writeheader()
        w.writerows(rows)


def main() -> None:
    enable_ansi()
    print(f"{c('GeoScore', C.BOLD, C.BCYAN)} {c('-- fichier:', C.DIM)} {c(CSV_FILE, C.CYAN)}")
    iso_week = date.today().isocalendar().week
    prev, n_games, prev_elo = last_session()
    if prev:
        try:
            w_str, n_str = prev.split(".", 1)
            default_week, default_num = int(w_str), int(n_str)
        except ValueError:
            default_week, default_num = iso_week, 1
        print(c(f"Derniere session: {prev} ({n_games} partie(s))", C.DIM))
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
    print(f"Session: {c(session, C.BOLD, C.BCYAN)}")
    print(c("Commandes pendant la saisie: u=undo, q=abandonner la partie\n", C.DIM))

    total = 0
    next_elo: int | None = prev_elo if session == prev else None
    while True:
        rows = play_game(session, default_my_elo=next_elo)
        if rows:
            append_rows(rows)
            total += 1
            next_elo = rows[-1]["my_elo_after"]
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
