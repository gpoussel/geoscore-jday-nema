# Period selector — fenêtres glissantes

**Date** : 2026-04-25
**Statut** : design validé
**Scope** : remplacer le sélecteur de période hebdomadaire (`PeriodToggle`) par 3 fenêtres glissantes fixes, pour résoudre l'encombrement visuel quand le nombre de semaines augmente.

## Contexte

Le dashboard rend une vue par semaine + une vue "Tout" via un toggle de pilules horizontal (`src/components/PeriodToggle.astro`). Avec ~3-5 semaines actuelles ça tient ; avec 5-6 semaines historiques supplémentaires (~10 semaines au total), la barre déborde — surtout dans le `StickyHeader.astro` où l'espace est partagé avec les KPI.

L'archi reste *dual-period render* : chaque période est un `<div data-view="...">` complet pré-rendu au build, masqué via `body[data-period="..."]` + CSS global. Le changement est circonscrit à la définition des périodes ; la mécanique de bascule est conservée.

## Décisions

| Sujet | Choix |
|---|---|
| Périmètre | Encombrement visuel uniquement |
| Granularité | 3 presets fixes |
| Fenêtres | Glissantes : 7 jours / 30 jours / tout, depuis `stats.generatedAt` |
| Vue par défaut | "Dernière semaine" (7j) |
| Page vide | Fallback automatique au build : 7j → 30j → tout |
| Labels | Adaptatifs : long sur header principal, court (`7J / 30J / TOUT`) sur sticky et mobile |
| Typographie | Sans-serif partout (pas de monospace) |
| Footer | "GLOBAL" pour la clé `all`, "DERNIÈRE SEMAINE" et "DERNIER MOIS" sinon |

## Modèle de données

Aucun changement de schéma dans `src/data/stats.json`. Tout est calculé dans `src/pages/index.astro`.

```ts
type ViewKey = "7d" | "30d" | "all";

const periodSpecs: {
  key: ViewKey;
  days: number | null;
  label: string;       // toggle (header principal)
  short: string;       // toggle (sticky / mobile)
  footerLabel: string; // ligne de pied de page
}[] = [
  { key: "7d",  days: 7,    label: "DERNIÈRE SEMAINE", short: "7J",   footerLabel: "DERNIÈRE SEMAINE" },
  { key: "30d", days: 30,   label: "DERNIER MOIS",     short: "30J",  footerLabel: "DERNIER MOIS"     },
  { key: "all", days: null, label: "TOUT",             short: "TOUT", footerLabel: "GLOBAL"           },
];

const generatedAtMs = Date.parse(stats.generatedAt);

const sessionInWindow = (s, days) =>
  days === null || Date.parse(s.date) >= generatedAtMs - days * 86_400_000;

const periods = periodSpecs.map(({ key, days, label, short }) => {
  const sessions = stats.sessions.filter((s) => sessionInWindow(s, days));
  const sids = new Set(sessions.map((s) => s.id));
  const games = enrichedGames.filter((g) => sids.has(g.session));
  return { key, label, short, view: buildView(games, sessions) };
});

const activePeriod: ViewKey =
  (periods.find((p) => p.key === "7d"  && p.view.games.length > 0)?.key) ??
  (periods.find((p) => p.key === "30d" && p.view.games.length > 0)?.key) ??
  "all";
```

`buildView` est inchangé (déjà polymorphique sur `games`/`sessions`). Suppression de `weeks` et `latestWeek` dans `index.astro`.

## Composants

### `src/components/PeriodToggle.astro`

**Nouvelles props** :

```ts
interface Props {
  periods: { key: string; label: string; short: string }[];
  activeKey: string;
}
```

**Template** : un bouton par période, contenant deux spans `.long` et `.short`. Le bouton "Tout" n'est plus un cas spécial — il est une entrée du tableau comme les autres.

```astro
<button class:list={["btn", { active: p.key === activeKey }]} data-period={p.key}>
  <span class="long">{p.label}</span>
  <span class="short">{p.short}</span>
</button>
```

**CSS scoped** :

```css
.long  { display: inline; }
.short { display: none; }

@media (max-width: 640px) {
  .long  { display: none; }
  .short { display: inline; }
}
```

**Script** : conservé tel quel — bascule `data-period` sur `body`, classe `.active` sur les boutons. Aucune logique d'affichage côté client à modifier.

### `src/components/StickyHeader.astro`

**Nouvelles props** : on retire `weeks` et `activeWeek`, on remplace par `activeKey`. Le tableau `periods` est déjà passé.

```ts
interface Props {
  periods: {
    key: string;
    label: string;
    short: string;
    view: { kpis: { games; winRate; eloNet; elo; avgAcc } };
  }[];
  activeKey: string;
}
```

**CSS additionnel** (style scoped, via `:global`) — force la version courte des labels dans le sticky :

```css
.sticky-header :global(.period-bar .long)  { display: none; }
.sticky-header :global(.period-bar .short) { display: inline; }
```

### `src/pages/index.astro`

Diff conceptuel :

```astro
<!-- avant -->
<StickyHeader weeks={weeks} activeWeek={latestWeek} periods={periods} />
<PeriodToggle weeks={weeks} activeWeek={latestWeek} />

<!-- après -->
<StickyHeader periods={periods} activeKey={activePeriod} />
<PeriodToggle periods={periods} activeKey={activePeriod} />
```

`<body data-period={activePeriod}>` reste tel quel (valeurs : `"7d"`, `"30d"`, `"all"`).

`hideCss` (génération du CSS de masquage des vues inactives) reste inchangé : il itère sur `periods.map(p => p.key)`, sans hypothèse sur la nature des clés.

**Footer** (`[data-fp]`) : conservé. Affiche `${p.footerLabel} · ${p.view.games.length} PARTIES`. Le toggle utilise `label` / `short`, le footer utilise `footerLabel` — ce qui permet de garder "GLOBAL" dans le footer alors que le toggle affiche "TOUT".

## Charts

`BlockElo` fait déjà un `chart.resize()` sur clic dans `.period-bar` — mécanisme global, indépendant du nombre / de la nature des périodes. **Aucun changement nécessaire.**

`BlockPrecision` reçoit `aggregateBySession={key === "all"}`. La clé `"all"` étant conservée, le comportement est préservé.

`BlockPays`, `BlockRecords`, `BlockSessions`, `KpiRow` : indépendants du sélecteur, ils consomment juste la `view` qu'on leur passe. Aucun changement.

## Edge cases

1. **Cas nominal** (à la date de validation, 2026-04-25, dernière session 17.5 le même jour) : "7j" contient `16.5`–`17.5` (6 sessions), "30j" contient tout w15+w16+w17, "all" tout l'historique.
2. **Auto-fallback 7j → 30j** : si la dernière session date d'il y a 8+ jours, `activePeriod = "30d"`.
3. **Auto-fallback 30j → all** : si la dernière session date d'il y a 31+ jours, `activePeriod = "all"`.
4. **Resize charts** : naviguer 7d ↔ 30d ↔ all doit garder le graphe ELO net (pas de canvas écrasé).
5. **Sticky mobile** (`<640px`) : labels affichés en court.
6. **`pnpm build`** doit passer `astro check` sans warning.

Pas de test automatisé : il n'y en a pas dans le projet, on n'en introduit pas pour ce changement.

## Hors scope

- Drill-down par semaine (validé Q3 : abandonné).
- Drill-down par session (idem).
- Range de dates personnalisé.
- État vide soigné par bloc (validé Q6 : on préfère le fallback automatique au build).
- Mémorisation de la sélection en `localStorage`.
- Sync URL `?period=7d` (add-on possible plus tard).

## Notes pour l'implémentation

- Conserver l'ordre des périodes dans `periodSpecs` ; l'ordre du DOM est l'ordre d'affichage du toggle.
- `Date.parse(stats.generatedAt)` est appelé une seule fois (constante au build).
- Pas de fuseau horaire à gérer : les dates de session sont au format `YYYY-MM-DD`, comparées en UTC, écart au build acceptable.
- Vérifier au commit qu'aucun composant ne fait `key.startsWith("w")` ou un `Number(key)` sur les clés de période (un grep suffit).
