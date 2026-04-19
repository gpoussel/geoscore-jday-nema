#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry"]
# ///
"""GeoScore - enregistrement rapide de parties GeoGuessr Duels."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from countries import is_valid as is_valid_country

STARTING_HP = 6000
STARTING_MULT = 1.0
MULT_STEP = 0.5
CSV_FILE = Path(__file__).resolve().parent / "games.csv"

COLUMNS = [
    "session", "game_id", "game_started_at",
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
            print("  Valeur requise.")
            continue
        if allow_abort and raw.lower() in ("q", "quit"):
            return None
        try:
            return int(raw)
        except ValueError:
            print("  Nombre invalide.")


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
            f"R{round_num} [{my_hp}-{opp_hp}] "
            f"{fmt_mult(my_mult)}/{fmt_mult(opp_mult)}> "
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
                print(f"  Annule: {last.my_score}-{last.opp_score} {last.country}")
            else:
                print("  (rien a annuler)")
            continue

        parts = raw.split()
        if len(parts) != 3:
            print("  Format: mon_score adv_score pays  (ex: 4850 4200 fr)")
            continue
        try:
            my_s = int(parts[0])
            opp_s = int(parts[1])
        except ValueError:
            print("  Scores invalides")
            continue
        country = parts[2].lower()
        if not is_valid_country(country):
            print(f"  Code pays inconnu: {country!r} (ex: fr, uk, us:fl)")
            continue

        rounds.append(Round(country=country, my_score=my_s, opp_score=opp_s))
        s = compute_state(rounds)[-1]
        sym = {"me": "W", "opp": "L", "tie": "="}[s["winner"]]
        sign = "+" if s["winner"] == "me" else ("-" if s["winner"] == "opp" else "")
        print(
            f"  {sym} {sign}{s['damage']} @ {fmt_mult(s['used_mult'])}"
            f" -> {s['my_hp']}-{s['opp_hp']}"
            f" (next {fmt_mult(s['my_mult'])}/{fmt_mult(s['opp_mult'])})"
        )


def play_game(session: str, default_my_elo: int | None = None) -> list[dict] | None:
    print("\n--- Nouvelle partie ---")
    if default_my_elo is not None:
        raw = ask_str(f"Mon ELO [{default_my_elo}] (q=annuler): ")
        if raw.lower() in ("q", "quit"):
            return None
        if not raw:
            my_elo = default_my_elo
        else:
            try:
                my_elo = int(raw)
            except ValueError:
                print("  Nombre invalide, annulation.")
                return None
    else:
        my_elo = ask_int("Mon ELO (q=annuler): ", allow_abort=True)
        if my_elo is None:
            return None
    opp_elo = ask_int("ELO adversaire: ")
    if opp_elo is None:
        return None

    game_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    started_at = datetime.now().isoformat(timespec="seconds")

    rounds = play_rounds()
    if not rounds:
        print("Partie abandonnee (non sauvegardee).")
        return None

    history = compute_state(rounds)
    final_my = history[-1]["my_hp"]
    final_opp = history[-1]["opp_hp"]
    won = final_my > 0
    print(
        f"\n=== {'VICTOIRE' if won else 'DEFAITE'} "
        f"en {len(rounds)}R ({final_my}-{final_opp}) ==="
    )

    delta = ask_int("Delta ELO (ex: +25, -18): ")
    if delta is None:
        delta = 0

    rows = []
    for i, (r, s) in enumerate(zip(rounds, history), start=1):
        rows.append({
            "session": session,
            "game_id": game_id,
            "game_started_at": started_at,
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
    print(f"GeoScore -- fichier: {CSV_FILE}")
    iso_week = date.today().isocalendar().week
    prev, n_games, prev_elo = last_session()
    if prev:
        try:
            w_str, n_str = prev.split(".", 1)
            default_week, default_num = int(w_str), int(n_str)
        except ValueError:
            default_week, default_num = iso_week, 1
        print(f"Derniere session: {prev} ({n_games} partie(s))")
    else:
        default_week, default_num = iso_week, 1

    week_raw = ask_str(f"Semaine [{default_week}]: ")
    try:
        week = int(week_raw) if week_raw else default_week
    except ValueError:
        week = default_week
    num_raw = ask_str(f"Session [{default_num}]: ")
    try:
        num = int(num_raw) if num_raw else default_num
    except ValueError:
        num = default_num
    session = f"{week}.{num}"
    print(f"Session: {session}")
    print("Commandes pendant la saisie: u=undo, q=abandonner la partie\n")

    total = 0
    next_elo: int | None = prev_elo if session == prev else None
    while True:
        rows = play_game(session, default_my_elo=next_elo)
        if rows:
            append_rows(rows)
            total += 1
            next_elo = rows[-1]["my_elo_after"]
            print(f"Sauvegarde. {total} partie(s) cette session.\n")
        try:
            again = input("[Entree]=nouvelle partie, q=quitter> ").strip().lower()
        except EOFError:
            break
        if again in ("n", "no", "q", "quit"):
            break
    print(f"\nFin. {total} partie(s) enregistree(s) dans la session '{session}'.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu.")
