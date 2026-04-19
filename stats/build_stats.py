#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry"]
# ///
"""Aggregate games.csv + sessions.json into stats.json consumed by the Astro
static site. Players are a separate, hand-maintained source file under
../src/data/players.json — not generated here.

Usage: uv run build_stats.py  (PEP 723 inline deps — do not prepend `python`)
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from countries import is_valid as is_valid_country

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "games.csv"
SESSIONS_FILE = ROOT / "sessions.json"
WEB_ROOT = ROOT.parent
OUT_FILE = WEB_ROOT / "src" / "data" / "stats.json"
OG_SCRIPT = WEB_ROOT / "scripts" / "build-og.mjs"

STARTING_HP = 6000


def margin_bucket(final_my_hp: int, final_opp_hp: int, won: bool) -> str:
    """Classify a game margin from the winner's remaining HP.

    High remaining HP = dominant win; low = tight."""
    winner_hp = final_my_hp if won else final_opp_hp
    if winner_hp >= 4000:
        return "crush"
    if winner_hp >= 2000:
        return "clean"
    return "tight"


def score_bucket(score: int) -> int:
    """Map a 0–5000 round score to one of 5 buckets: <3500, 3500–4200, 4200–4500, 4500–4800, ≥4800."""
    if score >= 4800:
        return 4
    if score >= 4500:
        return 3
    if score >= 4200:
        return 2
    if score >= 3500:
        return 1
    return 0


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def aggregate_games(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Group CSV rows by game_id. Returns (games, rounds)."""
    by_game: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []
    for r in rows:
        gid = r["game_id"]
        if gid not in by_game:
            order.append(gid)
        by_game[gid].append(r)

    games: list[dict] = []
    rounds: list[dict] = []
    session_counters: dict[str, int] = defaultdict(int)
    for gid in order:
        game_rows = sorted(by_game[gid], key=lambda x: int(x["round_num"]))
        head = game_rows[0]
        last = game_rows[-1]

        total_rounds = int(head["total_rounds"])
        final_my_hp = int(head["final_my_hp"])
        final_opp_hp = int(head["final_opp_hp"])
        won = head["won"].strip().lower() == "true"

        my_scores = [int(r["my_score"]) for r in game_rows]

        buckets = [0, 0, 0, 0, 0]
        perfects = 0
        for s in my_scores:
            buckets[score_bucket(s)] += 1
            if s >= 5000:
                perfects += 1

        session_id = head["session"]
        session_counters[session_id] += 1

        games.append({
            "id": gid,
            "session": session_id,
            "gameNum": session_counters[session_id],
            "rounds": total_rounds,
            "won": won,
            "margin": margin_bucket(final_my_hp, final_opp_hp, won),
            "elo": int(head["my_elo_after"]),
            "eloBefore": int(head["my_elo_before"]),
            "eloDelta": int(head["elo_delta"]),
            "roundBuckets": buckets,
            "perfects": perfects,
            "finalMyHp": final_my_hp,
            "finalOppHp": final_opp_hp,
            "finalMyMult": float(last["my_mult_after"]),
            "finalOppMult": float(last["opp_mult_after"]),
        })

        for r in game_rows:
            raw = r["country"].strip().split(":", 1)[0].lower()
            # GeoGuessr uses 'uk' for the UK; emit ISO 'GB' so downstream code
            # can treat the JSON as pure ISO 3166-1 alpha-2.
            code = "GB" if raw == "uk" else raw.upper()
            rounds.append({
                "gameId": gid,
                "roundNum": int(r["round_num"]),
                "country": code,
                "myScore": int(r["my_score"]),
                "oppScore": int(r["opp_score"]),
                "winner": r["winner"],
                "damage": int(r["damage"]),
                "usedMult": float(r["used_mult"]),
            })
    return games, rounds


def parse_session_id(sid: str) -> tuple[int, int]:
    """Parse a session id like '16.5' (ISO week 16, session 5) into (week, num)."""
    w, n = sid.split(".", 1)
    return int(w), int(n)


def build_sessions(games: list[dict], sessions_meta: dict) -> list[dict]:
    """Aggregate games by session id, enrich with metadata."""
    by_session: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []
    for g in games:
        if g["session"] not in by_session:
            order.append(g["session"])
        by_session[g["session"]].append(g)

    out: list[dict] = []
    for sid in order:
        sgames = by_session[sid]
        meta = sessions_meta.get(sid, {})
        week, num = parse_session_id(sid)
        wins = sum(1 for g in sgames if g["won"])
        losses = len(sgames) - wins
        out.append({
            "id": sid,
            "week": week,
            "num": num,
            "date": meta.get("date", ""),
            "time": meta.get("time", ""),
            "eloStart": sgames[0]["eloBefore"],
            "eloEnd": sgames[-1]["elo"],
            "games": len(sgames),
            "wins": wins,
            "losses": losses,
            "vods": meta.get("vods", []),
        })
    return out


def main() -> None:
    if not CSV_FILE.exists():
        raise SystemExit(f"Missing {CSV_FILE}")

    with CSV_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    unknown = defaultdict(list)
    for r in rows:
        code = r["country"].strip().lower()
        if not is_valid_country(code):
            unknown[code].append(f"{r['game_id']} r{r['round_num']}")
    if unknown:
        print(f"⚠ {sum(len(v) for v in unknown.values())} round(s) with unknown country code:")
        for code, rounds in sorted(unknown.items()):
            print(f"  {code!r}: {len(rounds)}× ({', '.join(rounds[:3])}{'…' if len(rounds) > 3 else ''})")

    sessions_meta = load_json(SESSIONS_FILE, {})

    games, rounds = aggregate_games(rows)

    for g in games:
        g["week"], _ = parse_session_id(g["session"])

    sessions = build_sessions(games, sessions_meta)

    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "games": games,
        "rounds": rounds,
        "sessions": sessions,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE} · {len(games)} games, {len(rounds)} rounds, {len(sessions)} sessions")

    regenerate_og_image()


def regenerate_og_image() -> None:
    """Re-render public/og.png from the freshly-written stats.json.

    Soft-fails if Node or @resvg/resvg-js aren't installed — the JSON is the
    canonical artifact, the OG image is just a derived asset."""
    if not OG_SCRIPT.exists():
        return
    node = shutil.which("node")
    if not node:
        print("⚠ node not found on PATH — skipped OG image regen")
        return
    try:
        result = subprocess.run(
            [node, str(OG_SCRIPT)],
            cwd=WEB_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"⚠ OG image regen failed: {exc}")
        return
    if result.returncode != 0:
        print(f"⚠ OG image regen exited {result.returncode}")
        if result.stderr.strip():
            print(result.stderr.strip())
        return
    for line in result.stdout.strip().splitlines():
        print(line)


if __name__ == "__main__":
    main()
