# Road to Champion — JDay × Néma Duo Stats

Static dashboard tracking the [JDay](https://www.twitch.tv/misterjday) × [Néma](https://www.twitch.tv/nema) GeoGuessr Duels duo on their climb toward the Champion rank. Games are recorded round-by-round from the streams, aggregated into a JSON payload by a small Python pipeline, and rendered by an Astro site with ELO evolution, precision breakdowns, a country map, session replays, and record books.

## Repo layout

```
.
├── stats/                     Python pipeline (recorder + aggregator)
│   ├── geoscore.py            interactive CLI to append rounds to games.csv
│   ├── build_stats.py         games.csv + sessions.json → src/data/stats.json
│   ├── countries.py           ISO 3166-1 alpha-2 validation
│   ├── games.csv              one row per round (source of truth for games)
│   └── sessions.json          session metadata (date, time, VODs)
└── src/                       Astro 6 static site
    ├── components/            blocks (BlockElo, BlockPrecision, BlockPays, …)
    │   └── ui/                reusable primitives (Kpi, Card, Flag, …)
    ├── data/
    │   ├── stats.json         generated — don't edit by hand
    │   ├── players.json       hand-maintained player identity (names, socials) + weekly duo ranks
    │   └── world.ts           simplified country overrides
    ├── lib/country.ts         country-name helpers (i18n-iso-countries + fr)
    ├── pages/index.astro      single-page dashboard
    ├── styles/global.css      design tokens + page chrome only
    └── types.ts               shared types (RawGame vs Game, Stats, etc.)
```

## Data flow

```
stats/games.csv  ─┐
                  ├─► stats/build_stats.py ──► src/data/stats.json ──► Astro build
stats/sessions.json ┘                                                         │
                                                                              ▼
                                                                          dist/
```

- `games.csv` holds one row per round.
- `sessions.json` is the only session-level metadata (date, time, VOD links).
- `src/data/players.json` is the source of truth for player identity and `duoRanks`, keyed by ISO `weekKey` (`YYYY-Www`). The latest played week drives the rank shown at the top of the page, and each session's week rank selects the matching map distribution.
- Per-game precision (`myAcc`, `advAcc`) is **computed in the web layer** as `score / 50` (linear mapping of 0–5000 pts to 0–100%). The JSON does not carry them.

## Commands

Regenerate `stats.json`:

```bash
cd stats
uv run build_stats.py     # PEP 723 inline deps — no `python` prefix
uv run geoscore.py        # interactive recorder (appends to games.csv)
```

Run / build the site:

```bash
pnpm install
pnpm run dev              # http://localhost:4321
pnpm run build            # astro check + astro build — the only correctness gate
pnpm run preview
```

There is no test suite. `astro check` (run as part of `build`) must stay at 0 errors.

## Architecture notes

- Fully static Astro, no React, no client framework. Chart.js is loaded as a vanilla lib through an Astro `<script>` tag (bundled, tree-shaken).
- Period toggle (current week ↔ global) is a **build-time dual render**: both views are emitted into the HTML and `PeriodToggle.astro` flips a `body.period-*` class — no hydration, no runtime state.
- World map uses `d3-geo` + `topojson-client` + `world-atlas` (all compile-time only, so the shipped JS stays tiny). Pan/zoom is a short inline script on the SVG.
- Colors are OKLCH with three hues: purple (`285`) base, teal (`172`) wins, orange (`50`) losses. All interpolation goes through `color-mix(in oklch, …)`.
- Precision is linear: per round, `score / 50` (0–5000 pts → 0–100%).

## Tech stack

Astro 6 · TypeScript · Chart.js 4 · d3-geo · topojson-client · world-atlas · flag-icons · i18n-iso-countries · Python 3.10+ with PEP 723 inline deps (`pycountry`) · `uv` for Python execution · `pnpm` for Node.

## License

Released under the [MIT License](LICENSE).
