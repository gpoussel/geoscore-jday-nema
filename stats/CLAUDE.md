# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Pipeline

`games.csv` + `sessions.json` → `build_stats.py` → `../src/data/stats.json` → Astro static site (`..`).

The Astro site consumes `stats.json` at build time only — it never reads the CSV directly. Any schema change in `build_stats.py`'s output must be mirrored in `../src/types.ts`.

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

Sessions are identified by `<iso_week>.<num>` (ISO 8601 week of year), e.g. `16.5` = ISO week 16, session 5. This string is the key in `sessions.json` and the value of the `session` column in `games.csv`. `build_stats.py:parse_session_id` splits it into `week` and `num`. `geoscore.py` defaults the week prompt to today's ISO week, or to the previous session's week if any; never invent another format.

`sessions.json` stores **only metadata** (`duoRank`, `date`, `time`, `vods`) — never game data. Players are in `../src/data/players.json` (hand-maintained, not generated).

## Data gotchas

- **ELO chain integrity**: per session, `my_elo_after` of game N must equal `my_elo_before` of game N+1. Breaks in the chain are typos in the CSV. When fixing, verify against the `elo_delta` (which is usually correct because it comes directly from the game UI).
- **Country normalization**: CSV may contain `us:fl`, `us:nh`, etc. `build_stats.py` strips anything after `:` so all US rounds aggregate as `US` in the JSON. The CSV also keeps GeoGuessr's `uk`; `build_stats.py` rewrites it to ISO `GB` when emitting the JSON, so downstream code sees pure ISO 3166-1 alpha-2.
- **Country validation** (`countries.py`): ISO 3166-1 alpha-2 countries + `uk` alias (GeoGuessr quirk — they use `uk`, not the ISO `gb`) + ISO 3166-2:US state codes. `build_stats.py` prints a warning for unknown codes; `geoscore.py` rejects unknown codes at input time.
- **`game.week`** in the JSON output is derived from the session id, not stored separately in the CSV.
- **Starting HP / mult step** (`6000` / `0.5`) are defined in `geoscore.py`; `build_stats.py` uses `STARTING_HP` only for margin bucketing.
- **`margin_bucket`** classifies by the winner's remaining HP: `crush` ≥ 4000, `clean` ≥ 2000, else `tight`. **`score_bucket`** maps round score (0–5000) to 5 buckets.

## CLI behavior (geoscore.py)

Defaults to continuing the last session (same `week`, same `num`) and uses the last `my_elo_after` **of the chosen session** as the default for `my_elo_before` — so pressing Enter through the prompts appends to the ongoing session.

Picking a past `week.num` resumes that session: new games get inserted in `games.csv` right after the last existing row of the target session, and the default ELO is that session's last `my_elo_after`. Within a session, games are always added as the next one (N+1), never in the middle. A brand-new `week.num` is slotted chronologically (before the first existing session with a larger `(week, num)`). `save_rows` always rewrites the whole file, which is negligible at this size.
