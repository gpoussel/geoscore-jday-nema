# Period selector — fenêtres glissantes — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le toggle hebdomadaire (1 pilule par semaine + "Tout") par 3 presets fixes (`Dernière semaine` / `Dernier mois` / `Tout`) calculés en fenêtres glissantes 7j / 30j depuis `stats.generatedAt`, avec fallback automatique au build si la fenêtre par défaut est vide, et labels adaptatifs (long sur header principal, court `7J`/`30J`/`TOUT` sur sticky et mobile).

**Architecture:** L'archi *dual-period render* est conservée. Chaque période est toujours pré-rendue comme un `<div data-view>` complet, masquée via CSS sur `body[data-period]`. Le seul changement est la **définition** des périodes (3 fenêtres temporelles au lieu de N semaines), pas la mécanique de bascule. Trois fichiers touchés : `src/pages/index.astro` (data layer + wiring), `src/components/PeriodToggle.astro` (template + props + CSS adaptatif), `src/components/StickyHeader.astro` (props + override CSS pour forcer la version courte).

**Tech Stack:** Astro 6 statique, TypeScript, CSS scoped + `:global`. Pas de framework client. Pas de framework de test (le projet n'en a pas). `pnpm build` (qui inclut `astro check`) est l'unique gate de correctness ; vérification fonctionnelle = `pnpm dev` + navigateur.

**Spec source:** `docs/superpowers/specs/2026-04-25-period-selector-rolling-windows-design.md`

---

## File structure

| Fichier | Rôle | Action |
|---|---|---|
| `src/pages/index.astro` | Data layer (calcul des 3 vues, choix du défaut), wiring vers les composants, footer | Modifier (lignes 140–159 : data layer ; lignes 218 / 222 : wiring ; lignes 239–241 : footer) |
| `src/components/PeriodToggle.astro` | Toggle visuel (boutons, script de bascule, CSS adaptatif) | Réécriture quasi-totale (template + props + CSS) ; le script de bascule reste identique |
| `src/components/StickyHeader.astro` | Wrapper sticky qui contient un `PeriodToggle` + bundle KPI | Modifier les props (retirer `weeks`/`activeWeek`, ajouter `activeKey`) ; ajouter une règle `:global` pour forcer la version courte des labels dedans |

Tous les autres composants (`KpiRow`, `BlockElo`, `BlockPrecision`, `BlockPays`, `BlockRecords`, `BlockSessions`, `Banner`, `TeamCard`) restent **inchangés**.

`src/types.ts` contient un type `Period = "current" | "all"` jamais utilisé ailleurs — laissé tel quel (hors scope).

---

## Task 1: Refactor du sélecteur de période

Toutes les modifications nécessaires en un seul commit. Justification : les props de `PeriodToggle` et `StickyHeader` changent, donc tout état intermédiaire casse `astro check`. On modifie les 3 fichiers ensemble, on vérifie le build une seule fois à la fin.

**Files:**
- Modify: `src/components/PeriodToggle.astro` (réécriture complète, voir Step 1)
- Modify: `src/components/StickyHeader.astro` (props + CSS — voir Step 2)
- Modify: `src/pages/index.astro` (data layer + wiring + footer — voir Step 3)

---

- [ ] **Step 1 : Réécrire `src/components/PeriodToggle.astro`**

Remplace **tout le contenu** du fichier par :

```astro
---
interface Props {
  periods: { key: string; label: string; short: string }[];
  activeKey: string;
}
const { periods, activeKey } = Astro.props;
---

<div class="period-bar">
  <span class="label">Période</span>
  <div class="toggle">
    {periods.map((p) => (
      <button
        class:list={["btn", { active: p.key === activeKey }]}
        data-period={p.key}
      >
        <span class="long">{p.label}</span>
        <span class="short">{p.short}</span>
      </button>
    ))}
  </div>
</div>

<script>
  const buttons = document.querySelectorAll<HTMLButtonElement>(".period-bar .btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.dataset.period!;
      document.body.dataset.period = p;
      buttons.forEach((b) => b.classList.toggle("active", b.dataset.period === p));
    });
  });
</script>

<style>
  .period-bar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    margin-top: var(--gap);
  }
  .label {
    font-family: var(--sans);
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-2);
  }
  .toggle {
    display: flex;
    gap: 4px;
    padding: 3px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 99px;
  }
  .btn {
    background: transparent;
    border: none;
    color: var(--fg-2);
    padding: 6px 14px;
    font-family: var(--sans);
    font-size: 13px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 99px;
    transition: all 0.15s;
  }
  .btn:hover { color: var(--fg-0); }
  .btn.active {
    background: var(--fg-0);
    color: var(--bg-0);
  }

  .long  { display: inline; }
  .short { display: none; }

  @media (max-width: 980px) {
    .period-bar { justify-content: flex-start; }
  }

  @media (max-width: 640px) {
    .long  { display: none; }
    .short { display: inline; }
  }
</style>
```

Notes :
- Le **script de bascule** est identique au comportement actuel — c'est lui qui pilote `BlockElo`'s resize (l'écouteur Chart.js est branché sur la même classe `.period-bar .btn`).
- Le bouton "Tout" ancien (hardcodé en dehors du `.map`) disparaît : il est désormais une entrée du tableau `periods` comme les deux autres.
- Tout le CSS d'origine est conservé ; on **ajoute** uniquement la paire de règles `.long` / `.short` et la media-query 640px pour la version courte.

---

- [ ] **Step 2 : Modifier `src/components/StickyHeader.astro`**

Remplace les lignes 1–13 (frontmatter) par :

```astro
---
import PeriodToggle from "./PeriodToggle.astro";

interface Props {
  periods: {
    key: string;
    label: string;
    short: string;
    view: { kpis: { games: number; winRate: number; eloNet: number; elo: number; avgAcc: number } };
  }[];
  activeKey: string;
}
const { periods, activeKey } = Astro.props;
---
```

Remplace la ligne 18 (le `<PeriodToggle>` à l'intérieur du sticky) :

```astro
    <PeriodToggle periods={periods} activeKey={activeKey} />
```

Dans le `<style>`, ajoute cette règle juste après le bloc `.sticky-header :global(.period-bar .label) { display: none; }` (autour de la ligne 94) :

```css
  .sticky-header :global(.period-bar .long)  { display: none; }
  .sticky-header :global(.period-bar .short) { display: inline; }
```

Cette règle force la version courte des labels **dans le sticky header**, indépendamment du breakpoint mobile (qui s'applique de toute façon en plus). Résultat : sticky desktop = court ; sticky mobile = court ; header principal desktop = long ; header principal mobile = court (via la media-query du PeriodToggle).

Le reste du fichier (`.sticky-kpis`, `.kpi-bundle`, etc.) reste inchangé. Le rendu des KPI bundles continue d'utiliser `data-view={key}` qui est déjà piloté par le CSS global de `index.astro`.

---

- [ ] **Step 3 : Modifier `src/pages/index.astro`**

**3a.** Remplace les lignes 140–159 (de `const weeks = ...` jusqu'à `const activePeriod = ...`) par :

```ts
type ViewKey = "7d" | "30d" | "all";

const periodSpecs: {
  key: ViewKey;
  days: number | null;
  label: string;
  short: string;
  footerLabel: string;
}[] = [
  { key: "7d",  days: 7,    label: "DERNIÈRE SEMAINE", short: "7J",   footerLabel: "DERNIÈRE SEMAINE" },
  { key: "30d", days: 30,   label: "DERNIER MOIS",     short: "30J",  footerLabel: "DERNIER MOIS"     },
  { key: "all", days: null, label: "TOUT",             short: "TOUT", footerLabel: "GLOBAL"           },
];

const generatedAtMs = Date.parse(stats.generatedAt);

const sessionInWindow = (s: Stats["sessions"][number], days: number | null): boolean =>
  days === null || Date.parse(s.date) >= generatedAtMs - days * 86_400_000;

const periods = periodSpecs.map(({ key, days, label, short, footerLabel }) => {
  const sessions = stats.sessions.filter((s) => sessionInWindow(s, days));
  const sids = new Set(sessions.map((s) => s.id));
  const games = enrichedGames.filter((g) => sids.has(g.session));
  return { key, label, short, footerLabel, view: buildView(games, sessions) };
});

const activePeriod: ViewKey =
  (periods.find((p) => p.key === "7d"  && p.view.games.length > 0)?.key) ??
  (periods.find((p) => p.key === "30d" && p.view.games.length > 0)?.key) ??
  "all";
```

Notes :
- `weeks` et `latestWeek` disparaissent — plus utilisés.
- L'ancien `type ViewKey = string;` annotation devient un type union strict `"7d" | "30d" | "all"` — plus de conversion de string libre.
- `buildView` reste tel quel.
- Si tu vois un avertissement TS sur le typage de `periodSpecs`, tu peux extraire le type local de `Stats["sessions"][number]` au sommet du bloc.

**3b.** Remplace la ligne 218 :

```astro
    <StickyHeader periods={periods} activeKey={activePeriod} />
```

Et la ligne 222 :

```astro
        <PeriodToggle periods={periods} activeKey={activePeriod} />
```

**3c.** Remplace les lignes 239–241 (le footer `[data-footer-period]`) :

```astro
        <span data-footer-period>
          {periods.map(({ key, footerLabel, view: v }) => (
            <span data-fp={key}>{footerLabel} · {v.games.length} PARTIES</span>
          ))}
        </span>
```

(Seul changement : `label` → `footerLabel`, qui vaut "GLOBAL" pour la clé `all` et reprend le `label` pour les deux autres.)

`hideCss` (lignes 161–167) **n'est pas touché** : il itère déjà sur `periods.map(p => p.key)` sans hypothèse sur la nature des clés.

`<body data-period={activePeriod}>` (ligne 216) **n'est pas touché** non plus : la valeur change (`"7d"` au lieu de `"w17"`) mais la mécanique est identique.

---

- [ ] **Step 4 : Vérifier le build**

Run :
```bash
pnpm build
```

Expected :
- Sortie inclut `0 errors, 0 warnings, 0 hints`.
- `dist/index.html` est généré.

Si `astro check` râle, lis l'erreur et corrige avant d'avancer. Erreurs probables et leur cause :
- "Property 'weeks' does not exist on type ..." → un appelant n'a pas été migré (vérifier que les deux occurrences `<PeriodToggle>` et `<StickyHeader>` ont bien été remplacées).
- "Cannot find name 'latestWeek'" → un usage résiduel ; grep `latestWeek` dans `src/`.
- "Type 'string' is not assignable to type 'ViewKey'" → quelque chose passe une string au lieu d'une clé du union ; vérifier que `periodSpecs` n'a pas été retouché.

---

- [ ] **Step 5 : Vérification manuelle dans le navigateur**

Run :
```bash
pnpm dev
```

Ouvre http://localhost:4321 et vérifie chaque point :

1. **Cas nominal (date du build = 2026-04-25)** : au chargement, `body[data-period="7d"]` est sélectionné, le toggle affiche "DERNIÈRE SEMAINE" actif. Les KPI doivent montrer ~6 sessions (16.5 + tout w17).
2. **Toggle desktop, header principal** : labels longs lisibles ("DERNIÈRE SEMAINE", "DERNIER MOIS", "TOUT").
3. **Sticky header desktop** : scroll vers le bas pour faire apparaître le sticky → labels en version courte ("7J", "30J", "TOUT") même sur grand écran.
4. **Resize mobile** (DevTools, largeur < 640px) : header principal aussi en version courte. Aucune coupure ni débordement.
5. **Switch entre périodes** : clique 7J → 30J → TOUT → 7J. Le graphe ELO doit rester net (test du `chart.resize()` automatique). KPI, donut, world map se mettent à jour correctement.
6. **Footer** : la ligne du milieu affiche "DERNIÈRE SEMAINE · X PARTIES", "DERNIER MOIS · X PARTIES", ou "GLOBAL · X PARTIES" selon la sélection.
7. **Console** : pas d'erreur JS, pas de warning Astro/Vite.

Si tu peux le tester (optionnel), simule un fallback en éditant temporairement `src/data/stats.json` pour mettre `generatedAt` à une date 10 jours après la dernière session — recharger doit landing sur "DERNIER MOIS" actif. **N'oublie pas de revert ce changement avant de commit.**

---

- [ ] **Step 6 : Commit**

```bash
git add src/components/PeriodToggle.astro src/components/StickyHeader.astro src/pages/index.astro
git commit -m "Replace weekly toggle with rolling-window period selector

Three fixed presets (Dernière semaine / Dernier mois / Tout) computed
as 7d / 30d rolling windows from generatedAt. Default lands on 7d
with auto-fallback to 30d → all when the window is empty. Labels are
adaptive: long on the main header, short (7J/30J/TOUT) on the sticky
header and below 640px.

Spec: docs/superpowers/specs/2026-04-25-period-selector-rolling-windows-design.md"
```

(Pas de push — préférence utilisateur.)

---

## Hors scope (rappel pour éviter le scope creep pendant l'exécution)

- Pas de drill-down par semaine ou par session.
- Pas de range de dates personnalisé.
- Pas d'état vide soigné par bloc (le fallback build-time s'en occupe).
- Pas de mémorisation `localStorage` ni de sync URL `?period=`.
- Pas de modification de `src/types.ts`, `src/data/*.json`, ou des autres composants block.
