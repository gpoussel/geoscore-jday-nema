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
    for row in game_rows:
        winner = row["winner"]
        if winner == "me":
            outcome = c("W", C.BGREEN, C.BOLD)
        elif winner == "opp":
            outcome = c("L", C.BRED, C.BOLD)
        else:
            outcome = c("=", C.BYELLOW, C.BOLD)
        label = country_label(row["country"])
        print(f"  {int(row['round_num']):>2}. {outcome}  {label:<28} {row['my_score']:>4}-{row['opp_score']:<4}  [{row['my_hp_after']:>4}-{row['opp_hp_after']}]")
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

    # Liste à plat des parties à traiter, figée au lancement: 'u' ne ramène que
    # vers des parties initialement en attente (la dernière partie traitée).
    pending = [
        (sid, position, len(games), game_rows)
        for sid, games in sessions
        for position, game_rows in enumerate(games, start=1)
        if needs_backfill(game_rows)
    ]
    if not pending:
        print(c("Rien à rattraper: tous les pays adverses sont renseignés.", C.GREEN))
        return
    print(f"{c('Backfill pays adverses', C.BOLD, C.BCYAN)} — {len(pending)} partie(s) à renseigner")
    print(c("Saisie: 'fr de', '--' = non communiqué, s/Entrée = passer, u = revenir en arrière, q = quitter\n", C.DIM))

    changed = False
    shown_session: str | None = None
    i = 0
    try:
        while 0 <= i < len(pending):
            sid, position, total, game_rows = pending[i]
            if sid != shown_session:
                print_session_header(sid, sessions_meta, total)
                shown_session = sid
            print_game(game_rows, position, total)
            try:
                raw = input(
                    f"Pays adverses {c('(fr de, --=non communiqué, s/Entrée=passer, u=retour, q=quitter)', C.DIM)}: "
                ).strip()
            except EOFError:
                raw = "q"
            low = raw.lower()
            if low in ("q", "quit"):
                break
            if low in ("u", "undo", "b", "back"):
                if i == 0:
                    print(c("  Déjà à la première partie.", C.YELLOW))
                else:
                    i -= 1
                    shown_session = None  # ré-affiche l'en-tête de la session ciblée
                continue
            if not raw or low in ("s", "skip"):
                # Passer: efface une valeur déjà saisie (remet en non renseignée).
                if not needs_backfill(game_rows):
                    for row in game_rows:
                        row["opp1_country"], row["opp2_country"] = "", ""
                    save_countries(game_rows[0]["game_id"], "", "")
                    changed = True
                    print(c("  Effacé (non renseignée).", C.YELLOW))
                i += 1
                continue
            parsed = geoscore.parse_opp_countries(raw)
            if parsed is None:
                continue
            for row in game_rows:
                row["opp1_country"], row["opp2_country"] = parsed
            save_countries(game_rows[0]["game_id"], *parsed)
            changed = True
            print(c(f"  Sauvegardé: {opp_country_label(parsed[0])} / {opp_country_label(parsed[1])}", C.GREEN))
            i += 1
    except KeyboardInterrupt:
        print(c("\nInterrompu.", C.YELLOW))

    if changed:
        geoscore.regenerate_data()
    done = sum(1 for _, _, _, game_rows in pending if not needs_backfill(game_rows))
    remaining = len(pending) - done
    print(c(f"\nFin. {done} renseignée(s), {remaining} restante(s).", C.BOLD))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("\nInterrompu.", C.YELLOW))
