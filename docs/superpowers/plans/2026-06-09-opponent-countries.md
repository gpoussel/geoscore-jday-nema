# Opponent Countries Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Record the two opponent flags (countries) per Team Duels game — entry on new games (CLI + mobile server) and a CLI backfill tool driven by VOD navigation.

**Architecture:** Two game-level CSV columns (`opp1_country`, `opp2_country`) with three states: `""` = non renseignée, `--` = non communiquée (generic GeoGuessr flag), or a country code. Parsing/validation helpers live in `stats/geoscore.py` and are reused by `stats/geoscore_server.py` and the new `stats/backfill_opponents.py`. `build_stats.py` is untouched (no stats yet).

**Tech Stack:** Python 3.10+ via `uv run` (PEP 723 inline deps, `pycountry`), stdlib `http.server` for the mobile recorder. No test suite in this repo — each task ends with a scripted smoke check instead.

**Spec:** `docs/superpowers/specs/2026-06-09-opponent-countries-design.md`

**Conventions:** all commands run from `stats/` unless noted. Commit data changes (`games.csv`, `stats.json`, `og.png`) separately from code changes.

---

### Task 0: Commit pending data changes

The working tree already has uncommitted data (`stats/games.csv`, `src/data/stats.json`, `public/og.png`, `pnpm-workspace.yaml`). The schema migration in Task 1 rewrites `games.csv`, so snapshot the pending data first.

**Step 1: Inspect what is pending**

Run (repo root): `git status --short` and `git diff --stat stats/games.csv`

Expected: modifications limited to session-data updates (new rows / regenerated outputs). If anything else shows up, stop and ask the user.

**Step 2: Commit data + the stray workspace file**

```bash
git add stats/games.csv src/data/stats.json public/og.png pnpm-workspace.yaml
git commit -m "Add pending session data and pnpm workspace file"
```

---

### Task 1: CSV schema + parsing helpers in geoscore.py

**Files:**
- Modify: `stats/geoscore.py`

**Step 1: Extend the schema**

In `COLUMNS` (around line 72), append the two game-level columns at the end:

```python
COLUMNS = [
    "session", "game_id", "mode",
    "my_elo_before", "opp_elo", "elo_delta", "my_elo_after", "won",
    "total_rounds", "final_my_hp", "final_opp_hp",
    "round_num", "country", "excluded", "my_score", "opp_score",
    "winner", "damage", "used_mult",
    "my_hp_after", "opp_hp_after", "my_mult_after", "opp_mult_after",
    "opp1_country", "opp2_country",
]
```

Next to the other constants (after `GAME_MODES`), add:

```python
OPP_COUNTRY_NOT_SHARED = "--"  # drapeau générique GeoGuessr
```

**Step 2: Normalization on load**

Add a helper near `normalize_country_code` and call it from `load_rows` so legacy rows (missing columns) read back as `""`:

```python
def normalize_opp_country(raw: object) -> str:
    """'' = non renseigné, '--' = non communiqué, sinon code pays normalisé."""
    code = str(raw or "").strip().lower()
    if not code:
        return ""
    if code == OPP_COUNTRY_NOT_SHARED:
        return OPP_COUNTRY_NOT_SHARED
    return normalize_country_code(code)
```

In `load_rows`, inside the `for r in rows:` loop:

```python
        r["opp1_country"] = normalize_opp_country(r.get("opp1_country", ""))
        r["opp2_country"] = normalize_opp_country(r.get("opp2_country", ""))
```

**Step 3: Parsing + display helpers**

Below `resolve_country`, add:

```python
def opp_country_label(code: str) -> str:
    if not code:
        return "non renseigné"
    if code == OPP_COUNTRY_NOT_SHARED:
        return "non communiqué"
    return country_label(code)


def resolve_opp_country(raw: str) -> str | None:
    """Un jeton pays adverse: '--' ou un code/nom de pays (fuzzy match)."""
    raw = raw.strip().lower()
    if raw == OPP_COUNTRY_NOT_SHARED:
        return OPP_COUNTRY_NOT_SHARED
    return resolve_country(raw)


def parse_opp_countries(raw: str) -> tuple[str, str] | None:
    """Parse 'fr de' / 'fr --' / '--' / 'fr' en (opp1, opp2). None si invalide."""
    parts = raw.split()
    if len(parts) == 1 and parts[0] == OPP_COUNTRY_NOT_SHARED:
        return OPP_COUNTRY_NOT_SHARED, OPP_COUNTRY_NOT_SHARED
    if len(parts) not in (1, 2):
        print(c("  Format: 'fr de', 'fr --', '--' (les deux non communiqués)", C.RED))
        return None
    resolved: list[str] = []
    for part in parts:
        code = resolve_opp_country(part)
        if code is None:
            return None
        resolved.append(code)
    if len(resolved) == 1:
        print(c("  2e pays adverse laissé non renseigné.", C.DIM))
        return resolved[0], ""
    return resolved[0], resolved[1]
```

Note: no `confirm_new_country` here — that guard is for round typos; opponent flags can be any country.

**Step 4: build_game_rows carries the values**

Add keyword params `opp1_country: str = ""` and `opp2_country: str = ""` to `build_game_rows`, and the two keys to the row dict:

```python
            "opp1_country": opp1_country,
            "opp2_country": opp2_country,
```

**Step 5: Smoke check**

```bash
cd stats
uv run --with pycountry python -c "import geoscore as g; print(g.parse_opp_countries('fr de'), g.parse_opp_countries('--'), g.parse_opp_countries('fr --'), g.normalize_opp_country(''), g.opp_country_label('--'))"
```

Expected: `('fr', 'de') ('--', '--') ('fr', '--')  non communiqué`

Also check fuzzy + rejection:

```bash
uv run --with pycountry python -c "import geoscore as g; print(g.parse_opp_countries('germany')); print(g.parse_opp_countries('zz 123'))"
```

Expected: fuzzy match message then `('de', '')`; unknown-country message then `None`.

**Step 6: Migrate the CSV and verify round-trip**

```bash
uv run geoscore.py --migrate-schema
git diff --stat stats/games.csv
head -2 ../stats/games.csv
```

Expected: header ends with `,opp1_country,opp2_country`; every data row gains `,,`. Run `uv run build_stats.py` — must complete without new warnings (DictReader ignores the extra columns).

**Step 7: Commit (code, then data)**

```bash
git add stats/geoscore.py
git commit -m "Add opponent country columns and parsing helpers"
git add stats/games.csv
git commit -m "Migrate games.csv schema with opponent country columns"
```

---

### Task 2: Entry flow in geoscore.py (new games)

**Files:**
- Modify: `stats/geoscore.py`

**Step 1: Prompt helper**

Near `ask_elo_result`, add:

```python
def ask_opp_countries(default: tuple[str, str] = ("", "")) -> tuple[str, str]:
    prompt = (
        f"Pays adverses (ex: fr de, -- = non communiqué) "
        f"{c('[Entrée=non renseigné]', C.DIM)}: "
    )
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return default
        if not raw:
            return default
        parsed = parse_opp_countries(raw)
        if parsed is not None:
            return parsed
```

**Step 2: Wire into play_game**

In `play_game`, right after `opp_elo = res` (step "2. ELO adversaire"):

```python
        opp_countries = list(ask_opp_countries())
```

Pass `opp_countries` to **both** `play_rounds` calls (`opp_countries=opp_countries`), and extend the `build_game_rows` call:

```python
                opp1_country=opp_countries[0],
                opp2_country=opp_countries[1],
```

**Step 3: `opp` command during round entry**

Add parameter `opp_countries: list[str] | None = None` to `play_rounds`. In the command-dispatch section (next to the `elo` command, before the final `parse_round_input`):

```python
        if parts and parts[0].lower() == "opp":
            if opp_countries is None:
                print(c("  Pays adverses non gérés ici.", C.DIM))
                continue
            if len(parts) < 2:
                print(c(f"  Pays adverses: {opp_country_label(opp_countries[0])} / {opp_country_label(opp_countries[1])}", C.CYAN))
                continue
            parsed_opp = parse_opp_countries(" ".join(parts[1:]))
            if parsed_opp is not None:
                opp_countries[0], opp_countries[1] = parsed_opp
                print(c(f"  Pays adverses: {opp_country_label(parsed_opp[0])} / {opp_country_label(parsed_opp[1])}", C.CYAN))
            continue
```

(`opp` alone shows current values; `opp fr de` sets them. No ISO code collides with `opp`.)

**Step 4: Help text**

In `print_round_help`, after the `elo 1234` line:

```python
    print("  opp fr de        pays des adversaires (-- = non communiqué)")
```

**Step 5: Smoke check (scripted end-to-end on a temp copy)**

From `stats/`, on a throwaway copy so the real CSV stays clean:

```powershell
Copy-Item games.csv games.csv.bak
@'
26
24
99
1000
500
fr de
de 5000 1000
fr 5000 1000
au 5000 1000
+10
q
'@ | uv run geoscore.py
```

Expected: prompt « Pays adverses » appears after the opponent ELO; game saves. Then:

```powershell
Select-String -Path games.csv -Pattern "26W24.99" | Select-Object -First 1
```

Expected: rows end with `,fr,de`. Restore: `Move-Item games.csv.bak games.csv -Force` then `uv run build_stats.py` (restore stats.json/og.png too: `git checkout -- ../src/data/stats.json ../public/og.png`).

Also test the `opp` command path: same script but with empty line for countries and `opp -- --` before the first round; verify the saved rows end with `,--,--`.

**Step 6: Commit**

```bash
git add stats/geoscore.py
git commit -m "Ask for opponent countries when recording a game"
```

---

### Task 3: Mobile server support (geoscore_server.py)

**Files:**
- Modify: `stats/geoscore_server.py`

**Step 1: Server-side validation helper**

Near `parse_elo_result`:

```python
def parse_opp_country_field(value: object, name: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw == geoscore.OPP_COUNTRY_NOT_SHARED:
        return geoscore.OPP_COUNTRY_NOT_SHARED
    code = geoscore.normalize_country_code(raw)
    if not is_valid_country(code):
        resolved = geoscore.resolve_country(code)
        if resolved is None:
            raise ApiError(f"Pays adverse inconnu : {name} = {raw}")
        code = resolved
    return code
```

**Step 2: Wire into save_game**

In `save_game`, before `rows = geoscore.build_game_rows(...)`:

```python
    opp1_country = parse_opp_country_field(payload.get("opp1Country"), "adv. 1")
    opp2_country = parse_opp_country_field(payload.get("opp2Country"), "adv. 2")
```

and add `opp1_country=opp1_country, opp2_country=opp2_country` to the `build_game_rows` call.

**Step 3: HTML — two fields + « non communiqué » buttons**

In the « Partie » section, after the `elo-grid` div (before the move/no-move `.seg`):

```html
      <div class="grid elo-grid" style="margin-top:10px">
        <label>Pays adv. 1 <input id="opp1Country" list="countries" autocomplete="off" autocapitalize="none" placeholder="fr ou --"></label>
        <label>Pays adv. 2 <input id="opp2Country" list="countries" autocomplete="off" autocapitalize="none" placeholder="de ou --"></label>
      </div>
      <div class="seg">
        <button id="opp1Unknown" type="button">Adv. 1 non communiqué</button>
        <button id="opp2Unknown" type="button">Adv. 2 non communiqué</button>
      </div>
```

Note: the shared `<datalist id="countries">` is declared later in the Rounds section — datalist references work regardless of document order.

**Step 4: JS wiring**

In `gamePayload()`:

```javascript
    opp1Country: $("opp1Country").value.trim(),
    opp2Country: $("opp2Country").value.trim(),
```

Button handlers (next to `modeMove`/`modeNoMove`):

```javascript
$("opp1Unknown").onclick = () => { $("opp1Country").value = "--"; };
$("opp2Unknown").onclick = () => { $("opp2Country").value = "--"; };
```

In `resetGame`, alongside `$("oppElo").value = "";`:

```javascript
  $("opp1Country").value = "";
  $("opp2Country").value = "";
```

**Step 5: Smoke check via the API (no browser needed)**

```powershell
# terminal 1 (or background): uv run geoscore_server.py --host 127.0.0.1
Copy-Item games.csv games.csv.bak
$body = @{ year="26"; week="24"; num="98"; myElo="1000"; oppElo="500"; mode="move"; eloResult="+10";
  opp1Country="fr"; opp2Country="--";
  rounds=@(@{country="fr"; myScore=5000; oppScore=0}, @{country="de"; myScore=5000; oppScore=0}) } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/save -Method Post -Body $body -ContentType "application/json"
Select-String -Path games.csv -Pattern "26W24.98" | Select-Object -First 1
```

Expected: `ok: True`; rows end with `,fr,--`. Also POST with `opp1Country="zzz"` → HTTP 400 « Pays adverse inconnu ». Restore `games.csv.bak`, regenerate, restore stats.json/og.png, stop the server.

**Step 6: Commit**

```bash
git add stats/geoscore_server.py
git commit -m "Add opponent country fields to the mobile recorder"
```

---

### Task 4: Backfill tool (stats/backfill_opponents.py)

**Files:**
- Create: `stats/backfill_opponents.py`

**Step 1: Write the script**

```python
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
        print(f"  {int(row['round_num']):>2}. {outcome}  {label:<28} {row['my_score']:>4}-{row['opp_score']:<4}")
    current = (head["opp1_country"], head["opp2_country"])
    if any(current):
        print(c(f"  Actuel: {opp_country_label(current[0])} / {opp_country_label(current[1])}", C.YELLOW))


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
    print(c("Saisie: 'fr de', '--' = non communiqué, s = passer, q = quitter\n", C.DIM))

    filled = 0
    skipped = 0
    changed = False
    quitting = False
    for sid, games in sessions:
        pending = [g for g in games if needs_backfill(g)]
        if not pending or quitting:
            continue
        print_session_header(sid, sessions_meta, len(games))
        for game_rows in games:
            if not needs_backfill(game_rows):
                continue
            position = games.index(game_rows) + 1
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
                geoscore.write_all(rows)
                changed = True
                filled += 1
                print(c(f"  Sauvegardé: {opp_country_label(parsed[0])} / {opp_country_label(parsed[1])}", C.GREEN))
                break
            if quitting:
                break
        if quitting:
            break

    if changed:
        geoscore.regenerate_data()
    remaining = total_pending - filled - skipped
    print(c(f"\nFin. {filled} renseignée(s), {skipped} passée(s), {remaining} restante(s).", C.BOLD))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("\nInterrompu.", C.YELLOW))
```

**Step 2: Smoke check on a temp copy**

```powershell
Copy-Item games.csv games.csv.bak
@'
fr de
s
q
'@ | uv run backfill_opponents.py --session 25W52.01
Select-String -Path games.csv -Pattern "25W52.01" | Select-Object -First 1
```

Expected: session header with the YouTube VOD, game 0001 rounds listed (Iceland, Kenya, Singapore…), first game saved with `,fr,de`, second skipped, exit on `q` with recap `1 renseignée(s), 1 passée(s), …` and « Données régénérées ». Re-run the same command: game 0001 is no longer proposed (resume works). Restore `games.csv.bak`, `uv run build_stats.py`, `git checkout -- ../src/data/stats.json ../public/og.png`.

**Step 3: Commit**

```bash
git add stats/backfill_opponents.py
git commit -m "Add CLI backfill tool for opponent countries"
```

---

### Task 5: Documentation

**Files:**
- Modify: `stats/CLAUDE.md`

**Step 1: Document schema + tools**

- In « Commands », add: `uv run backfill_opponents.py  # rattrapage des pays adverses sur les anciennes parties (navigation VOD)`.
- In « Data gotchas », add a bullet: `opp1_country` / `opp2_country` are game-level columns repeated on each round row; `""` = non renseignée (not yet entered), `--` = non communiquée (generic GeoGuessr flag), otherwise a lowercase country code (`uk` alias kept). Ignored by `build_stats.py` for now.
- In « CLI behavior (geoscore.py) », mention: prompt after the opponent-ELO prompt (Entrée = skip), and the `opp fr de` round-entry command.

**Step 2: Commit**

```bash
git add stats/CLAUDE.md
git commit -m "Document opponent country columns and backfill tool"
```

---

### Task 6: Final verification

**Step 1:** `git status --short` → only expected artifacts; `stats/games.csv` matches the committed migrated state (no stray test games: `Select-String -Path stats/games.csv -Pattern "26W24.9"` → no results).

**Step 2:** From `stats/`: `uv run build_stats.py` → completes, no new warnings. From repo root: `pnpm build` → 0 errors/warnings (site untouched, sanity only).

**Step 3:** Commit any regenerated data separately if `stats.json` changed.
