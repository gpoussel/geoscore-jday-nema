# Map distribution extraction & multi-map support

## Context

Today, the map's theoretical country distribution lives at `stats/distribution.json` and is folded into the generated `src/data/stats.json` by `build_stats.py:67-87` (under a top-level `distribution` key). This commingles map-static metadata with player-dependent aggregates.

It also models a single map: schema is `{ map, source, counts, totalCount }`. GeoGuessr Duels rotates featured maps over time; the duo will eventually play under multiple maps, and we want each session to be measured against the distribution that was active at the time.

## Goals

1. Move the distribution out of the generated `stats.json`, into a hand-maintained `src/data/distributions.json` (plural), aligned with how `players.json` is treated.
2. Support multiple distributions, each tagged with a date range, so the right map applies to a given session.
3. In week views (single map), keep the existing "Carte · *<map>*" credit pill and the per-country deviation calculation unchanged.
4. In the "all" view, show every map ever used (one credit pill each, no per-week annotation), and compute deviation against a rounds-weighted expected share.

## Non-goals

- Validating non-overlap or gap-freeness of distribution date ranges. The data is small and hand-maintained; mistakes are easy to spot.
- Fixing the pre-existing ISO-week-without-year conflation in `index.astro:95` (`enrichedGames.map(g => g.week)`).
- Migrating older sessions to a real start date if unknown. The single existing entry gets a `from` set to the date of the duo's first session on that map.

## Schema

`src/data/distributions.json`:

```json
{
  "distributions": [
    {
      "map": "A Modified Moving World",
      "source": "https://amovingworld.com/#/distribution",
      "from": "<ISO date of first duo session on this map>",
      "counts": { "US": 8189, "BR": 5003, "...": 0 }
    }
  ]
}
```

- Each entry: `{ map: string, source: string, from?: string, to?: string, counts: Record<string, number> }`.
- `from` / `to` are ISO dates (`YYYY-MM-DD`).
- Constraint (not enforced; convention only): at least one of `from` / `to` is present per entry. `from` absent = "from the beginning of recorded sessions". `to` absent = "currently active".
- `totalCount` is no longer stored — recomputed in TS where needed.

## Type changes (`src/types.ts`)

```ts
export type Distribution = {
  map: string;
  source: string;
  from?: string;
  to?: string;
  counts: Record<string, number>;
};

export type DistributionsFile = { distributions: Distribution[] };
```

`Stats.distribution` is removed. `Stats` now contains only `generatedAt`, `games`, `rounds`, `sessions`.

## Pipeline changes (`stats/build_stats.py`)

- Delete `DISTRIBUTION_FILE`, `load_distribution`.
- Remove `distribution` from the emitted `payload`.
- The file `stats/distribution.json` is moved to `src/data/distributions.json`, with its content wrapped as `{ "distributions": [ {...existing fields, plus from } ] }`.

## Astro wiring (`src/pages/index.astro`)

### One-time setup (frontmatter)

```ts
import distributionsData from "../data/distributions.json";
const { distributions } = distributionsData as DistributionsFile;

// per-distribution total count
const distTotals = new Map<Distribution, number>(
  distributions.map(d => [d, Object.values(d.counts).reduce((s, n) => s + n, 0)])
);

const distFor = (date: string): Distribution | undefined =>
  distributions.find(d => (!d.from || date >= d.from) && (!d.to || date <= d.to));

// session id → distribution (build-time lookup)
const distBySession = new Map<string, Distribution>();
for (const s of stats.sessions) {
  const d = distFor(s.date);
  if (!d) throw new Error(`No distribution covers session ${s.id} (date ${s.date})`);
  distBySession.set(s.id, d);
}

// game id → session id (built once)
const sessionByGame = new Map<string, string>(
  stats.games.map(g => [g.id, g.session])
);
```

Failing the build when a session has no covering distribution makes the data error loud at the right time. Acceptable because the file is hand-maintained and small.

### `buildView`: weighted expected share

Replace the current `distCounts` / `distTotal` constants with:

```ts
const roundsPerDist = new Map<Distribution, number>();
for (const r of rounds) {
  const sid = sessionByGame.get(r.gameId)!;
  const d = distBySession.get(sid)!;
  roundsPerDist.set(d, (roundsPerDist.get(d) ?? 0) + 1);
}

const expectedShare: Record<string, number> = {};
const N = rounds.length;
if (N > 0) {
  for (const [d, n] of roundsPerDist) {
    const T = distTotals.get(d)!;
    if (T <= 0) continue;
    const w = n / N;
    for (const [code, c] of Object.entries(d.counts)) {
      expectedShare[code] = (expectedShare[code] ?? 0) + (w * c) / T;
    }
  }
}
```

Then compute per-country `observedShare = a.seen / N` and `deviation` exactly as today.

### `View` shape & prop wiring

`View` gets a new field `distributions: Distribution[]` — the list of distributions active in the view, in chronological order (by `from ?? to`). Built from `[...roundsPerDist.keys()]`.

Render:

```astro
<BlockPays countryStats={v.countryStats} distributions={v.distributions} />
```

(Old prop `distribution` removed.)

### Convergence with current behavior

In a week view with a single distribution `D` covering all rounds:

- `roundsPerDist = Map<D, N>`
- For each country `k`: `expectedShare[k] = (N/N) * (D.counts[k] / D.totalCount) = D.counts[k] / D.totalCount`

This is byte-for-byte identical to the current single-map formula. Therefore the per-week visual output is unchanged for the existing dataset.

## `BlockPays.astro`

Prop signature changes:

```ts
interface Props { countryStats: Record<string, CountryStat>; distributions: Distribution[]; }
const { countryStats, distributions } = Astro.props;
```

The credit-pill block (`BlockPays.astro:177-190`) now iterates:

```astro
{distributions.length > 0 && (
  <div class="map-credits" data-metric="occurrence">
    <span class="mc-label">{distributions.length > 1 ? "Cartes" : "Carte"}</span>
    {distributions.map(d => (
      <a class="map-credit" href={d.source} target="_blank" rel="noopener noreferrer"
         title="Distribution de la carte utilisée">
        <span class="mc-name">{d.map}</span>
        <span class="mc-ext" aria-hidden="true">↗</span>
      </a>
    ))}
  </div>
)}
```

The `mc-label` "Carte" / "Cartes" wrapper moves outside the individual link so a single label fronts the row. CSS for `.map-credit` is preserved; a small `.map-credits` wrapper provides flex layout for the label + N pills.

`tf-dev` tooltip text remains "Écart vs. distribution attendue sur la carte" — accurate enough for both single- and multi-map cases.

## Behavior summary

| Period view | Active distributions | Credit pill | Deviation |
|---|---|---|---|
| Single week (today, only one map exists) | 1 | Single pill, label "Carte" — same look as today | Same formula as today |
| "All" (today, only one map exists) | 1 | Single pill, label "Carte" — same look as today | Same formula as today (weighted form converges) |
| Single week (after rotation) | 1 | Single pill, the active map | Single-map formula |
| "All" (after rotation) | 2+ | One pill per map, label "Cartes" | Rounds-weighted average across maps |

## Files touched

- New: `src/data/distributions.json`, `docs/superpowers/specs/2026-04-25-distribution-extraction-design.md`
- Deleted: `stats/distribution.json`
- Modified: `src/types.ts`, `src/pages/index.astro`, `src/components/BlockPays.astro`, `stats/build_stats.py`, `stats/CLAUDE.md` (mention of distribution.json), regen of `src/data/stats.json` after pipeline change

## Validation

- `pnpm run build` (= `astro check && astro build`) stays at 0 errors / 0 warnings.
- Visual regression on the current dataset (single-map era): per-country deviation, credit pill, and country list ordering identical to before. The `stats.json` regen step in this branch should produce a file with no `distribution` key, but otherwise byte-identical to the current output (modulo `generatedAt`).
