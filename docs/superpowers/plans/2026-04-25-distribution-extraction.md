# Map distribution extraction & multi-map support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move map country distribution out of generated `stats.json` into a hand-maintained `src/data/distributions.json` that supports multiple maps with date ranges, with a rounds-weighted expected share in the global view.

**Architecture:** Replace the single inlined `Stats.distribution` with a sibling data file imported directly by Astro (mirroring the `players.json` pattern). Each session is matched to a distribution by date at build time; `buildView` aggregates the active distributions and weights expected shares by rounds played under each.

**Tech Stack:** Astro 6 (static, no React), TypeScript, JSON data imports, Python pipeline (`build_stats.py` via `uv`). No test suite — `pnpm run build` (= `astro check && astro build`) is the only correctness gate. Visual smoke via `pnpm run dev` is required for UI changes.

**Spec:** `docs/superpowers/specs/2026-04-25-distribution-extraction-design.md`

---

## File structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/data/distributions.json` | Hand-maintained list of map distributions with date ranges |
| Modify | `src/types.ts` | Add `Distribution` + `DistributionsFile`, remove `Stats.distribution` |
| Modify | `src/pages/index.astro` | Build `distBySession` map; weighted expected share in `buildView`; new `View.distributions` field; pass it to `BlockPays` |
| Modify | `src/components/BlockPays.astro` | Accept `distributions: Distribution[]`; render one `map-credit` pill per entry; rework label placement and CSS |
| Modify | `stats/build_stats.py` | Drop `DISTRIBUTION_FILE`, `load_distribution`, and the `distribution` key in the emitted payload |
| Regenerate | `src/data/stats.json` | Re-run pipeline so the file no longer carries `distribution` |
| Delete | `stats/distribution.json` | Source of truth moved into `src/data/` |
| Modify | `stats/CLAUDE.md` | Remove the `distribution.json` references |

---

## Task 1: Create `src/data/distributions.json`

**Files:**
- Create: `src/data/distributions.json`

The earliest session date in `stats/sessions.json` is `2026-04-07` — that becomes the `from` date of the only existing entry. Content is otherwise identical to `stats/distribution.json`.

- [ ] **Step 1: Create the file**

Create `D:/dev-oss/geoscore/web/src/data/distributions.json`:

```json
{
  "distributions": [
    {
      "map": "A Modified Moving World",
      "source": "https://amovingworld.com/#/distribution",
      "from": "2026-04-07",
      "counts": {
        "US": 8189, "BR": 5003, "RU": 3900, "MX": 3750, "CA": 3450,
        "ID": 3400, "IN": 3350, "AU": 3100, "JP": 2836, "ZA": 2678,
        "PH": 2651, "AR": 2300, "ES": 2273, "TR": 2150, "FR": 2100,
        "DE": 2100, "VN": 2000, "TH": 1995, "IT": 1850, "CO": 1800,
        "GB": 1793, "PE": 1650, "CL": 1620, "MY": 1473, "SE": 1420,
        "NZ": 1347, "KE": 1325, "NO": 1306, "BD": 1250, "PL": 1200,
        "RO": 1200, "NG": 937, "FI": 850, "GR": 850, "EC": 850,
        "BG": 840, "CZ": 800, "PT": 783, "AT": 753, "HU": 720,
        "TW": 674, "SK": 650, "UA": 608, "NL": 600, "SN": 600,
        "DK": 600, "BE": 526, "BO": 525, "IE": 507, "KR": 500,
        "HR": 450, "CR": 439, "CH": 439, "BA": 420, "GT": 400,
        "PA": 400, "EE": 400, "KZ": 397, "LK": 385, "IS": 385,
        "LT": 382, "LV": 381, "PY": 300, "UY": 300, "SI": 300,
        "GH": 286, "NA": 255, "RS": 250, "NP": 225, "AE": 215,
        "KH": 205, "OM": 200, "IL": 200, "BW": 190, "MN": 180,
        "AL": 180, "RW": 175, "SZ": 150, "ME": 150, "KG": 150,
        "TN": 140, "CY": 125, "LS": 125, "BT": 120, "HK": 110,
        "PS": 100, "QA": 100, "JO": 90, "SG": 80, "LU": 75,
        "MK": 72, "PR": 50, "RE": 46, "DO": 35, "UG": 33,
        "LA": 30, "AD": 30, "GL": 27, "MT": 20, "CW": 20,
        "FO": 20, "SM": 20, "BM": 19, "GU": 15, "LI": 15,
        "MP": 11, "LB": 10, "AS": 6, "GI": 5, "CX": 5,
        "CN": 4, "ST": 3, "PK": 3, "AX": 2, "EG": 2,
        "BY": 2, "MC": 2, "MG": 2, "PM": 2, "TZ": 1,
        "ML": 1, "VU": 1
      }
    }
  ]
}
```

The `counts` values come verbatim from `stats/distribution.json:4-127`. Keep the formatting clean (multiple entries per line is fine — the file is hand-maintained, readability wins over diff-friendliness).

- [ ] **Step 2: Verify the build still passes**

Run: `pnpm run build`
Expected: `0 errors, 0 warnings`. The file is not yet imported by anything, so this just confirms no JSON parse error.

- [ ] **Step 3: Commit**

```bash
git add src/data/distributions.json
git commit -m "Add hand-maintained distributions.json (single map, 2026-04-07 onward)"
```

---

## Task 2: Add `Distribution` and `DistributionsFile` types

**Files:**
- Modify: `src/types.ts:71-84`

This task is additive — the existing `Distribution` type already exists with a different shape. We update it (no `totalCount`, add `from`/`to`), add `DistributionsFile`, and remove `Stats.distribution`. Astro consumers still reference `stats.distribution` at this point, so the build will fail until Task 3 lands.

We split this awkwardness by keeping the build green via a two-step approach: first add the new shapes alongside the old, then in Task 3 cut over consumers and remove the old field.

- [ ] **Step 1: Update `src/types.ts`**

Replace the `Distribution` block (lines 71-76) and the `Stats` block (lines 78-84) with:

```ts
export type Distribution = {
  map: string;
  source: string;
  from?: string;
  to?: string;
  counts: Record<string, number>;
};

export type DistributionsFile = { distributions: Distribution[] };

export type Stats = {
  generatedAt: string;
  games: RawGame[];
  rounds: Round[];
  sessions: Session[];
  distribution: Distribution & { totalCount: number };
};
```

The `Stats.distribution` field is kept temporarily (with the legacy `totalCount` property folded back in via intersection) so existing consumers in `index.astro` continue to type-check. It will be removed in Task 3.

- [ ] **Step 2: Run the build**

Run: `pnpm run build`
Expected: `0 errors, 0 warnings`. The `as Stats` cast in `index.astro:18` still works because `stats.json` has not been regenerated yet — it still has `distribution` with `totalCount`. The new fields `from?` / `to?` are optional, so existing consumer code is unaffected.

- [ ] **Step 3: Commit**

```bash
git add src/types.ts
git commit -m "Add Distribution from/to fields and DistributionsFile shape"
```

---

## Task 3: Wire Astro to `distributions.json` and remove `Stats.distribution`

**Files:**
- Modify: `src/types.ts` (final shape)
- Modify: `src/pages/index.astro` (import distributions, build lookups, weighted expected, prop)
- Modify: `src/components/BlockPays.astro` (prop signature, JSX, CSS)

This is the cutover. `index.astro` and `BlockPays.astro` change signatures together; `Stats.distribution` is removed in the same commit so the type system enforces the cutover.

- [ ] **Step 1: Drop `Stats.distribution`**

Edit `src/types.ts`. Replace the temporary `Stats` block from Task 2 with:

```ts
export type Stats = {
  generatedAt: string;
  games: RawGame[];
  rounds: Round[];
  sessions: Session[];
};
```

- [ ] **Step 2: Update `src/pages/index.astro` imports and pre-computed lookups**

Edit the import block (current lines 1-19) to:

```astro
---
import "../styles/global.css";
import statsData from "../data/stats.json";
import playersData from "../data/players.json";
import distributionsData from "../data/distributions.json";
import bannerData from "../data/banner.json";
import type {
  CountryStat, Distribution, DistributionsFile, Game, PlayersFile, Round, Stats,
} from "../types";
import TeamCard from "../components/TeamCard.astro";
import PeriodToggle from "../components/PeriodToggle.astro";
import StickyHeader from "../components/StickyHeader.astro";
import Banner from "../components/Banner.astro";
import KpiRow from "../components/KpiRow.astro";
import BlockElo from "../components/BlockElo.astro";
import BlockPrecision from "../components/BlockPrecision.astro";
import BlockPays from "../components/BlockPays.astro";
import BlockRecords from "../components/BlockRecords.astro";
import BlockSessions from "../components/BlockSessions.astro";

const stats = statsData as Stats;
const { duoRank, players } = playersData as PlayersFile;
const { distributions } = distributionsData as DistributionsFile;
```

Then, immediately after `const enrichedGames = …` (current line 31), insert the pre-computed distribution lookups:

```ts
const distTotals = new Map<Distribution, number>(
  distributions.map((d) => [d, Object.values(d.counts).reduce((s, n) => s + n, 0)]),
);

const distFor = (date: string): Distribution | undefined =>
  distributions.find((d) => (!d.from || date >= d.from) && (!d.to || date <= d.to));

const distBySession = new Map<string, Distribution>();
for (const s of stats.sessions) {
  const d = distFor(s.date);
  if (!d) throw new Error(`No distribution covers session ${s.id} (date ${s.date})`);
  distBySession.set(s.id, d);
}

const sessionByGame = new Map<string, string>(
  stats.games.map((g) => [g.id, g.session]),
);
```

- [ ] **Step 3: Update `View` type and `buildView`**

In `src/pages/index.astro`, replace the existing `View` type (current lines 33-39) with:

```ts
type View = {
  games: Game[];
  rounds: Round[];
  sessions: Stats["sessions"];
  countryStats: Record<string, CountryStat>;
  distributions: Distribution[];
  kpis: { games: number; winRate: number; eloNet: number; elo: number; avgAcc: number };
};
```

Replace the entire `buildView` function (current lines 46-93) with:

```ts
const buildView = (games: Game[], sessions: Stats["sessions"]): View => {
  const gids = new Set(games.map((g) => g.id));
  const rounds = stats.rounds.filter((r) => gids.has(r.gameId));

  const agg: Record<string, { seen: number; mySum: number; advSum: number; balSum: number }> = {};
  const roundsPerDist = new Map<Distribution, number>();
  for (const r of rounds) {
    const k = r.country;
    if (!agg[k]) agg[k] = { seen: 0, mySum: 0, advSum: 0, balSum: 0 };
    agg[k].seen++;
    agg[k].mySum += precision(r.myScore);
    agg[k].advSum += precision(r.oppScore);
    agg[k].balSum += r.myScore - r.oppScore;

    const sid = sessionByGame.get(r.gameId)!;
    const d = distBySession.get(sid)!;
    roundsPerDist.set(d, (roundsPerDist.get(d) ?? 0) + 1);
  }

  const totalRounds = rounds.length;
  const expectedShare: Record<string, number> = {};
  if (totalRounds > 0) {
    for (const [d, n] of roundsPerDist) {
      const T = distTotals.get(d)!;
      if (T <= 0) continue;
      const w = n / totalRounds;
      for (const [code, c] of Object.entries(d.counts)) {
        expectedShare[code] = (expectedShare[code] ?? 0) + (w * c) / T;
      }
    }
  }

  const countryStats: Record<string, CountryStat> = {};
  for (const k in agg) {
    const a = agg[k];
    const acc = a.mySum / a.seen;
    const advAcc = a.advSum / a.seen;
    const score = a.balSum / a.seen;
    const exp = expectedShare[k] ?? 0;
    const observedShare = totalRounds > 0 ? a.seen / totalRounds : 0;
    const deviation = exp > 0 ? ((observedShare - exp) / exp) * 100 : null;
    countryStats[k] = {
      seen: a.seen, acc, advAcc, gap: acc - advAcc, score,
      expectedShare: exp, deviation,
    };
  }

  const wins = games.filter((g) => g.won).length;
  const eloNet = games.reduce((s, g) => s + g.eloDelta, 0);
  const avgAcc = games.length ? games.reduce((s, g) => s + g.myAcc, 0) / games.length : 0;

  const viewDistributions = [...roundsPerDist.keys()].sort((a, b) => {
    const ka = a.from ?? a.to ?? "";
    const kb = b.from ?? b.to ?? "";
    return ka.localeCompare(kb);
  });

  return {
    games,
    rounds,
    sessions,
    countryStats,
    distributions: viewDistributions,
    kpis: {
      games: games.length,
      winRate: Math.round((wins / Math.max(1, games.length)) * 100),
      eloNet,
      elo: latestElo(games),
      avgAcc,
    },
  };
};
```

- [ ] **Step 4: Update the `BlockPays` JSX prop**

In `src/pages/index.astro`, change the line currently reading:

```astro
<BlockPays countryStats={v.countryStats} distribution={stats.distribution} />
```

to:

```astro
<BlockPays countryStats={v.countryStats} distributions={v.distributions} />
```

- [ ] **Step 5: Update `BlockPays.astro` prop signature and import**

Edit `src/components/BlockPays.astro`. Change the import line currently reading:

```ts
import type { CountryStat, Distribution } from "../types";
```

(unchanged — the type is already imported).

Change the `Props` interface (current line 35) and the destructuring (current line 36) from:

```ts
interface Props { countryStats: Record<string, CountryStat>; distribution: Distribution; }
const { countryStats, distribution } = Astro.props;
```

to:

```ts
interface Props { countryStats: Record<string, CountryStat>; distributions: Distribution[]; }
const { countryStats, distributions } = Astro.props;
```

- [ ] **Step 6: Update the credit block in `BlockPays.astro`**

Replace the conditional block currently at `BlockPays.astro:177-190` (the single `{distribution?.source && ( … )}` link) with:

```astro
{distributions.length > 0 && (
  <div class="map-credits" data-metric="occurrence">
    <span class="mc-label">{distributions.length > 1 ? "Cartes" : "Carte"}</span>
    {distributions.map((d) => (
      <a
        class="map-credit"
        href={d.source}
        target="_blank"
        rel="noopener noreferrer"
        title="Distribution de la carte utilisée"
      >
        <span class="mc-name">{d.map}</span>
        <span class="mc-ext" aria-hidden="true">↗</span>
      </a>
    ))}
  </div>
)}
```

- [ ] **Step 7: Update `BlockPays.astro` styles**

In the `<style>` block (scoped, currently around `BlockPays.astro:561-586`), replace the `.map-credit` block and its descendants with the wrapper-aware version:

```css
  .map-credits {
    display: inline-flex; align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    align-self: center;
    margin-left: auto;
  }
  .map-credits .mc-label {
    font-family: var(--sans); font-size: 10px;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--fg-2);
  }

  .map-credit {
    display: inline-flex; align-items: center; gap: 8px;
    text-decoration: none;
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: 99px;
    transition: border-color 0.15s, color 0.15s;
  }
  .map-credit:hover { border-color: var(--border-hi); }
  .map-credit .mc-name {
    font-family: var(--serif); font-style: italic;
    font-size: 14px; color: var(--fg-0);
  }
  .map-credit .mc-ext {
    font-family: var(--sans); font-size: 11px;
    color: var(--fg-2);
  }
  .map-credit:hover .mc-name { color: var(--fg-0); }
  .map-credit:hover .mc-ext { color: var(--fg-0); }
```

The differences vs. the previous CSS:

- `align-self: center` and `margin-left: auto` move from `.map-credit` to the new `.map-credits` wrapper (so the row of pills gets pushed right inside `.tf-title`, instead of each pill individually).
- The old `.map-credit .mc-label` selector becomes `.map-credits .mc-label` (the label is now a sibling of the pills, not a child).
- `flex-wrap: wrap` keeps multi-pill rows from overflowing on narrow viewports.

- [ ] **Step 8: Run the build**

Run: `pnpm run build`
Expected: `0 errors, 0 warnings`.

If TypeScript complains that `stats.distribution` is referenced anywhere else in the project, grep for it (`rg "stats\.distribution"` from the project root) and remove the references — there should be none after this task.

- [ ] **Step 9: Visual smoke test**

Run: `pnpm run dev` (background) and open http://localhost:4321 in the browser.

Verify in **week view** (e.g., latest week button):
- "Carte" pill appears at the top-right of the "Top 40" / occurrence section, with text "*A Modified Moving World*" and the external-link arrow.
- Click the pill → opens `https://amovingworld.com/#/distribution` in a new tab.
- Switch metric to "Occurrence" — the deviation column (e.g. "▲+12%") shows for countries with non-zero expected.

Verify in **"all" / global view**:
- Same single pill (we still only have one map). Label is "Carte", not "Cartes".
- Deviation values look reasonable (similar to before — single map → identical formula).

Stop the dev server.

- [ ] **Step 10: Commit**

```bash
git add src/types.ts src/pages/index.astro src/components/BlockPays.astro
git commit -m "Switch Astro to distributions.json with rounds-weighted expected share"
```

---

## Task 4: Drop distribution from the Python pipeline & regen `stats.json`

**Files:**
- Modify: `stats/build_stats.py:24-87, 199-236`
- Regenerate: `src/data/stats.json`

Per project convention (`web/CLAUDE.md`: "Keep `stats.json` regeneration commits separate from code changes"), this task produces **two** commits — first the Python source change, then the regenerated JSON.

- [ ] **Step 1: Edit `stats/build_stats.py`**

Remove the `DISTRIBUTION_FILE` constant. Edit lines 24-30 (the constants block) from:

```python
ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "games.csv"
SESSIONS_FILE = ROOT / "sessions.json"
DISTRIBUTION_FILE = ROOT / "distribution.json"
WEB_ROOT = ROOT.parent
OUT_FILE = WEB_ROOT / "src" / "data" / "stats.json"
OG_SCRIPT = WEB_ROOT / "scripts" / "build-og.mjs"
```

to:

```python
ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "games.csv"
SESSIONS_FILE = ROOT / "sessions.json"
WEB_ROOT = ROOT.parent
OUT_FILE = WEB_ROOT / "src" / "data" / "stats.json"
OG_SCRIPT = WEB_ROOT / "scripts" / "build-og.mjs"
```

- [ ] **Step 2: Remove the `load_distribution` function**

Delete lines 67-87 in `stats/build_stats.py` (the entire `load_distribution` function and the blank line preceding it). The `from countries import is_valid as is_valid_country` import on line 22 stays — it's still used in `main()` for the unknown-country warning at lines 207-214.

- [ ] **Step 3: Drop the distribution call and key from `main()`**

In `stats/build_stats.py:main()`, remove the line that reads:

```python
    distribution = load_distribution(DISTRIBUTION_FILE)
```

And remove the `"distribution": distribution,` entry from the `payload` dict so it becomes:

```python
    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "games": games,
        "rounds": rounds,
        "sessions": sessions,
    }
```

- [ ] **Step 4: Run the build to confirm Python source compiles**

Run: `pnpm run build`
Expected: `0 errors, 0 warnings`. (The Python change does not affect this build directly — it only matters once we regen `stats.json` — but we run the gate as a sanity check.)

- [ ] **Step 5: Commit the Python change (without regen)**

```bash
git add stats/build_stats.py
git commit -m "Drop distribution loading from build_stats.py"
```

- [ ] **Step 6: Regenerate `stats.json`**

Run from `D:/dev-oss/geoscore/web/stats`:

```bash
uv run build_stats.py
```

Expected output: `Wrote …/src/data/stats.json · N games, M rounds, K sessions`. The OG image regen may follow (it's optional and warns if Node isn't available — non-blocking).

Verify the regenerated `src/data/stats.json` no longer has a top-level `"distribution"` key. Grep:

`rg '"distribution"' src/data/stats.json` should return no matches.

- [ ] **Step 7: Run the build with the regenerated stats**

Run: `pnpm run build`
Expected: `0 errors, 0 warnings`.

- [ ] **Step 8: Commit the regenerated stats**

```bash
git add src/data/stats.json
git commit -m "Regen stats without distribution field"
```

---

## Task 5: Cleanup — delete obsolete source file & update pipeline docs

**Files:**
- Delete: `stats/distribution.json`
- Modify: `stats/CLAUDE.md`

- [ ] **Step 1: Delete the obsolete source**

```bash
git rm stats/distribution.json
```

- [ ] **Step 2: Update `stats/CLAUDE.md`**

The current pipeline doc mentions distribution flow only via the general pipeline statement. Open `stats/CLAUDE.md` and:

- Confirm the current "Pipeline" section reads:
  > `games.csv` + `sessions.json` → `build_stats.py` → `../src/data/stats.json` → Astro static site (`..`).

  It does not mention `distribution.json` explicitly, so no edit is needed here.
- Append a one-line note at the end of the "Pipeline" section to disambiguate:

  > Map distributions live in `../src/data/distributions.json` (hand-maintained, keyed by date range — not generated here).

This makes future readers aware that the map distribution is *not* part of this pipeline.

- [ ] **Step 3: Run the build**

Run: `pnpm run build`
Expected: `0 errors, 0 warnings`.

- [ ] **Step 4: Final visual smoke test**

Run: `pnpm run dev` and reload http://localhost:4321 in the browser. Spot-check the same items from Task 3 Step 9 — week view and "all" view both render the credit pill, deviation column populates in occurrence mode. Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add stats/distribution.json stats/CLAUDE.md
git commit -m "Remove obsolete stats/distribution.json; note new home in CLAUDE.md"
```

---

## Final verification

After all tasks:

```bash
pnpm run build           # green
rg '"distribution"' src/data/stats.json   # no matches
rg 'stats\.distribution' src/                # no matches in source
ls src/data/distributions.json            # exists
ls stats/distribution.json                # absent
git log --oneline -10                     # 6 commits added by this plan
```

Expected commit list (most recent first):

```
Remove obsolete stats/distribution.json; note new home in CLAUDE.md
Regen stats without distribution field
Drop distribution loading from build_stats.py
Switch Astro to distributions.json with rounds-weighted expected share
Add Distribution from/to fields and DistributionsFile shape
Add hand-maintained distributions.json (single map, 2026-04-07 onward)
```

The branch is up to date locally; per the user's standing preference (`MEMORY.md`), do **not** push — the user pushes manually to control Pages deploys.
