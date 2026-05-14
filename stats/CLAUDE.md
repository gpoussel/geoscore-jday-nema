# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Pipeline

`games.csv` + `sessions.json` → `build_stats.py` → `../src/data/stats.json` → Astro static site (`..`).

The Astro site consumes `stats.json` at build time only — it never reads the CSV directly. Any schema change in `build_stats.py`'s output must be mirrored in `../src/types.ts`.

Map distributions live in `../src/data/distributions.json` (hand-maintained, keyed by date range — not generated here).

## Commands

```bash
uv run geoscore.py       # interactive CLI to record a new GeoGuessr Duels game (appends to games.csv)
uv run build_stats.py    # rebuild ../src/data/stats.json from CSV + sessions.json
```

Both scripts declare `pycountry` via PEP 723 inline metadata. Invoke them with `uv run <script.py>` (no `python` prefix) so uv picks up the script-local deps.

Web (from the repo root `..`, uses pnpm):

```bash
pnpm dev       # astro dev server
pnpm build     # astro check (type-check) + astro build
pnpm preview
```

After editing `games.csv` / `sessions.json` by hand, rerun `build_stats.py` — the web site will not pick up changes otherwise.

## Session identifiers

Sessions are identified by `<yy>W<iso_week>.<num>` (ISO 8601 year + week), e.g. `26W16.05` = ISO year 2026, week 16, session 5. This string is the key in `sessions.json` and the value of the `session` column in `games.csv`. `build_stats.py:parse_session_id` splits it into `year`, `week`, and `num`, and emits `weekKey` as `YYYY-Www` for frontend week grouping. `geoscore.py` defaults the ISO year/week prompt to today's ISO year/week, or to the previous session's values if any. Do not add new data using the old `<iso_week>.<num>` format.

`sessions.json` stores **only metadata** (`date`, `time`, `vods`) — never game data. The duo's rank history lives in `../src/data/players.json` (alongside the two player entries, under `duoRanks`, keyed by ISO `weekKey`). Only weeks with at least one VOD or recorded game should be listed. Players and ranks are hand-maintained, not generated.

## Data gotchas

- **ELO chain integrity**: per session, `my_elo_after` of game N must equal `my_elo_before` of game N+1. Breaks in the chain are typos in the CSV. When fixing, verify against the `elo_delta` (which is usually correct because it comes directly from the game UI).
- **Country normalization**: CSV stores only country-level codes. US state-level entries are intentionally not kept because that signal is too unreliable; legacy `us:<state>` rows are normalized to `us`. The CSV also keeps GeoGuessr's `uk`; `build_stats.py` rewrites it to ISO `GB` when emitting the JSON, so downstream code sees pure ISO 3166-1 alpha-2.
- **Country validation** (`countries.py`): ISO 3166-1 alpha-2 countries + `uk` alias (GeoGuessr quirk — they use `uk`, not the ISO `gb`). `build_stats.py` prints a warning for unknown codes; `geoscore.py` rejects unknown codes at input time.
- **`game.year` / `game.week` / `game.weekKey`** in the JSON output are derived from the session id, not stored separately in the CSV.
- **Starting HP / mult step** (`6000` / `0.5`) are defined in `geoscore.py`; `build_stats.py` uses `STARTING_HP` only for margin bucketing.
- **`margin_bucket`** classifies by the winner's remaining HP: `crush` ≥ 4000, `clean` ≥ 2000, else `tight`. **`score_bucket`** maps round score (0–5000) to 5 buckets.

## CLI behavior (geoscore.py)

Defaults to continuing the last session (same `year`, `week`, same `num`) and uses the last `my_elo_after` **of the chosen session** as the default for `my_elo_before` — so pressing Enter through the prompts appends to the ongoing session.

For a brand-new past session, the default `my_elo_before` is the last known `my_elo_after` from the latest session chronologically before the chosen session. If no earlier game exists, there is no default and the CLI asks for the ELO explicitly.

Picking a past `yyWweek.num` resumes that session: new games get inserted in `games.csv` right after the last existing row of the target session, and the default ELO is that session's last `my_elo_after`. Within a session, games are always added as the next one (N+1), never in the middle. A brand-new session is slotted chronologically (before the first existing session with a larger `(year, week, num)`). `save_rows` always rewrites the whole file, which is negligible at this size.

After each insert, `save_rows` renumbers every `game_id` sequentially by CSV position (zero-padded 4 digits, e.g. `0042`). That keeps the invariant **`game_id` ordering ≡ chronological ordering**, so inserting into a past session shifts the ids of all later games upward.

During round entry, `h` prints inline help. Useful navigation commands are `s` for a recap, `u` to undo the last round, `b` to return to the opponent ELO prompt, `e <round> ...` to edit a previous round, `d <round>` to delete a round, and `g <round>` to truncate the game back to that round.

At the final ELO prompt, a signed value (`+25`, `-18`) is treated as an ELO delta, while an unsigned value (`1248`) is treated as the new absolute ELO. The CSV still stores both `elo_delta` and `my_elo_after`.

`games.csv` has a `mode` column (`move` by default, or `no-move`). New games are recorded as `move` unless the `nm` command is entered during round input; `m` switches back to `move`. The field is currently ignored by `build_stats.py`.

Sessions dated before `2026-04-17` use the old shared-multiplier Duel rules: R1-R4 stay at `1x`, R5 is `1.5x`, then the multiplier increases by `0.5x` each round. Later sessions use the current per-team multiplier rules. The CSV schema stays unchanged: under the old rules, `my_mult_after` and `opp_mult_after` are written with the same shared value. Use `uv run geoscore.py --fix-multipliers` after changing this logic to recompute derived CSV columns (`damage`, HP, winner, multiplier fields) from the recorded scores without touching ELO values.
