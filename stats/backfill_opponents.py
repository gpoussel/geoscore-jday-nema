#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry"]
# ///
"""Rattrapage des pays adverses sur les anciennes parties, VOD par VOD.

Parcourt les sessions dans l'ordre du CSV et ne s'arrête que sur les parties
dont au moins un des deux pays adverses est non renseigné. Le récap des rounds
(pays + scores) sert de repère pour naviguer dans la VOD de partie en partie.
"""
from __future__ import annotations

import argparse

import geoscore
from geoscore import C, c, country_label, opp_country_label


def games_by_session(rows: list[dict]) -> list[tuple[str, list[list[dict]]]]:
    """Group rows into games, grouped by session, preserving CSV order."""
    sessions: list[tuple[str, list[list[dict]]]] = []
    current_key: tuple[str, str] | None = None
    for row in rows:
        key = (row["session"], row["game_id"])
        if not sessions or sessions[-1][0] != row["session"]:
            sessions.append((row["session"], []))
            current_key = None
        if key != current_key:
            sessions[-1][1].append([])
            current_key = key
        sessions[-1][1][-1].append(row)
    return sessions


def needs_backfill(game_rows: list[dict]) -> bool:
    head = game_rows[0]
    return not head["opp1_country"] or not head["opp2_country"]


def print_session_header(sid: str, meta: dict, game_count: int) -> None:
    info = meta.get(sid, {})
    date_str = info.get("date") or "date inconnue"
    print(c(f"\n=== Session {sid} — {date_str} — {game_count} partie(s) ===", C.BOLD, C.BCYAN))
    vods = info.get("vods") or []
    if not vods:
        print(c("  (aucune VOD)", C.DIM))
    for vod in vods:
        print(f"  VOD {vod.get('player', '?')} ({vod.get('platform', '?')}): {c(vod.get('url', ''), C.CYAN)}")


def print_game(game_rows: list[dict], position: int, total: int) -> None:
    head = game_rows[0]
    won = geoscore.csv_bool(head["won"])
    verdict = c("VICTOIRE", C.BOLD, C.BGREEN) if won else c("DEFAITE", C.BOLD, C.BRED)
    print(
        f"\n--- Partie {head['game_id']} ({position}/{total}) — opp {head['opp_elo']} — "
        f"{verdict} {head['final_my_hp']}-{head['final_opp_hp']} en {head['total_rounds']}R ---"
    )
    my_total = 0
    opp_total = 0
    for row in game_rows:
        winner = row["winner"]
        if winner == "me":
            outcome = c("W", C.BGREEN, C.BOLD)
        elif winner == "opp":
            outcome = c("L", C.BRED, C.BOLD)
        else:
            outcome = c("=", C.BYELLOW, C.BOLD)
        label = country_label(row["country"])
        my_total += int(row["my_score"])
        opp_total += int(row["opp_score"])
        print(f"  {int(row['round_num']):>2}. {outcome}  {label:<28} {row['my_score']:>4}-{row['opp_score']:<4}  [{my_total:>5}-{opp_total}]")
    current = (head["opp1_country"], head["opp2_country"])
    if any(current):
        print(c(f"  Actuel: {opp_country_label(current[0])} / {opp_country_label(current[1])}", C.YELLOW))


def save_countries(game_id: str, opp1: str, opp2: str) -> None:
    """Recharge le CSV avant d'écrire: un enregistrement concurrent ne doit pas être écrasé."""
    fresh = geoscore.load_rows()
    for row in fresh:
        if row["game_id"] == game_id:
            row["opp1_country"], row["opp2_country"] = opp1, opp2
    geoscore.write_all(fresh)


def main() -> None:
    geoscore.enable_ansi()
    parser = argparse.ArgumentParser(description="Rattrapage des pays adverses")
    parser.add_argument("--session", help="Limiter à une session (ex: 26W24.03)")
    args = parser.parse_args()

    rows = geoscore.load_rows()
    sessions_meta = geoscore.load_sessions_meta()
    sessions = games_by_session(rows)
    if args.session:
        sessions = [s for s in sessions if s[0] == args.session]
        if not sessions:
            print(c(f"Session inconnue: {args.session}", C.RED))
            return

    total_pending = sum(1 for _, games in sessions for g in games if needs_backfill(g))
    if not total_pending:
        print(c("Rien à rattraper: tous les pays adverses sont renseignés.", C.GREEN))
        return
    print(f"{c('Backfill pays adverses', C.BOLD, C.BCYAN)} — {total_pending} partie(s) à renseigner")
    print(c("Saisie: 'fr de', '--' = non communiqué, s/Entrée = passer, q = quitter\n", C.DIM))

    filled = 0
    skipped = 0
    changed = False
    quitting = False
    try:
        for sid, games in sessions:
            if not any(needs_backfill(g) for g in games):
                continue
            print_session_header(sid, sessions_meta, len(games))
            for position, game_rows in enumerate(games, start=1):
                if not needs_backfill(game_rows):
                    continue
                print_game(game_rows, position, len(games))
                while True:
                    try:
                        raw = input(
                            f"Pays adverses {c('(fr de, --=non communiqué, s/Entrée=passer, q=quitter)', C.DIM)}: "
                        ).strip()
                    except EOFError:
                        raw = "q"
                    low = raw.lower()
                    if low in ("q", "quit"):
                        quitting = True
                        break
                    if not raw or low in ("s", "skip"):
                        skipped += 1
                        break
                    parsed = geoscore.parse_opp_countries(raw)
                    if parsed is None:
                        continue
                    for row in game_rows:
                        row["opp1_country"], row["opp2_country"] = parsed
                    save_countries(game_rows[0]["game_id"], *parsed)
                    changed = True
                    filled += 1
                    print(c(f"  Sauvegardé: {opp_country_label(parsed[0])} / {opp_country_label(parsed[1])}", C.GREEN))
                    break
                if quitting:
                    break
            if quitting:
                break
    except KeyboardInterrupt:
        quitting = True
        print(c("\nInterrompu.", C.YELLOW))

    if changed:
        geoscore.regenerate_data()
    remaining = total_pending - filled - skipped
    print(c(f"\nFin. {filled} renseignée(s), {skipped} passée(s), {remaining} restante(s).", C.BOLD))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("\nInterrompu.", C.YELLOW))
