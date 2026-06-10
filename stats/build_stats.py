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
import re
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


def csv_bool(value: object) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "y", "oui", "o")


def norm_country(raw: str) -> str | None:
    """Normalize a CSV country code to ISO 3166-1 alpha-2 (upper-case).

    GeoGuessr's 'uk' alias becomes 'GB'. Empty ('' = non renseignée) and '--'
    ('non communiquée', generic flag) both collapse to None — i.e. no country."""
    code = raw.strip().lower()
    if not code or code == "--":
        return None
    return "GB" if code == "uk" else code.upper()


def validate_game_id_sequence(rows: list[dict]) -> None:
    """Fail fast when game_id blocks are not strictly sequential in CSV order."""
    previous_gid: str | None = None
    seen: dict[str, int] = {}
    expected = 1
    errors: list[str] = []

    for line_no, row in enumerate(rows, start=2):
        gid = row.get("game_id", "")
        if gid == previous_gid:
            continue

        if gid in seen:
            errors.append(
                f"line {line_no}: game_id {gid!r} reappears after first block at line {seen[gid]}"
            )

        try:
            int(gid)
        except ValueError:
            errors.append(f"line {line_no}: game_id {gid!r} is not numeric")
        else:
            wanted = f"{expected:04d}"
            if gid != wanted:
                errors.append(f"line {line_no}: expected game_id {wanted}, got {gid!r}")
            expected += 1

        seen.setdefault(gid, line_no)
        previous_gid = gid

    if errors:
        details = "\n  - ".join(errors[:20])
        extra = "" if len(errors) <= 20 else f"\n  - ... {len(errors) - 20} more"
        raise SystemExit(
            "Inconsistent game_id numbering in stats/games.csv:\n"
            f"  - {details}{extra}\n"
            "Run geoscore.py's renumbering flow or fix the CSV before rebuilding stats."
        )


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

        stat_rows = [r for r in game_rows if not csv_bool(r.get("excluded", False))]
        my_scores = [int(r["my_score"]) for r in stat_rows]

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
            "opp1": norm_country(head.get("opp1_country", "")),
            "opp2": norm_country(head.get("opp2_country", "")),
        })

        for r in stat_rows:
            raw = r["country"].strip().lower()
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
                "myMult": float(r["my_mult_after"]),
                "oppMult": float(r["opp_mult_after"]),
            })
    return games, rounds


def parse_session_id(sid: str) -> tuple[int, int, int]:
    """Parse '26W16.05' into (ISO year, week, session num).

    Legacy ids like '16.5' are still accepted and treated as 2026 data.
    """
    long_match = re.fullmatch(r"(\d{2})W(\d{2})\.(\d{2})", sid)
    if long_match:
        year, week, num = long_match.groups()
        return 2000 + int(year), int(week), int(num)

    legacy_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", sid)
    if legacy_match:
        week, num = legacy_match.groups()
        return 2026, int(week), int(num)

    raise ValueError(f"Invalid session id: {sid!r}")


def build_sessions(games: list[dict], sessions_meta: dict) -> list[dict]:
    """Aggregate games by session id, enrich with metadata."""
    by_session: dict[str, list[dict]] = defaultdict(list)
    played_order: list[str] = []
    for g in games:
        if g["session"] not in by_session:
            played_order.append(g["session"])
        by_session[g["session"]].append(g)

    # Combine played sessions and metadata-only sessions
    all_sids = set(played_order) | set(sessions_meta.keys())
    
    # Sort all session IDs chronologically
    def sid_key(sid: str):
        year, week, num = parse_session_id(sid)
        return year, week, num

    sorted_sids = sorted(list(all_sids), key=sid_key)

    out: list[dict] = []
    for sid in sorted_sids:
        sgames = by_session.get(sid, [])
        meta = sessions_meta.get(sid, {})
        year, week, num = parse_session_id(sid)
        week_key = f"{year}-W{week:02d}"
        
        if sgames:
            wins = sum(1 for g in sgames if g["won"])
            losses = len(sgames) - wins
            out.append({
                "id": sid,
                "year": year,
                "week": week,
                "weekKey": week_key,
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
        else:
            # "En chantier" session
            out.append({
                "id": sid,
                "year": year,
                "week": week,
                "weekKey": week_key,
                "num": num,
                "date": meta.get("date", ""),
                "time": meta.get("time", ""),
                "eloStart": 0,
                "eloEnd": 0,
                "games": 0,
                "wins": 0,
                "losses": 0,
                "vods": meta.get("vods", []),
            })
    return out


def main() -> None:
    if not CSV_FILE.exists():
        raise SystemExit(f"Missing {CSV_FILE}")

    with CSV_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    validate_game_id_sequence(rows)

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

    excluded_count = sum(1 for r in rows if csv_bool(r.get("excluded", False)))
    games, rounds = aggregate_games(rows)

    for g in games:
        year, week, _ = parse_session_id(g["session"])
        g["year"] = year
        g["week"] = week
        g["weekKey"] = f"{year}-W{week:02d}"

    sessions = build_sessions(games, sessions_meta)

    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "games": games,
        "rounds": rounds,
        "sessions": sessions,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    excluded_msg = f", {excluded_count} excluded" if excluded_count else ""
    print(f"Wrote {OUT_FILE} · {len(games)} games, {len(rounds)} rounds{excluded_msg}, {len(sessions)} sessions")

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
