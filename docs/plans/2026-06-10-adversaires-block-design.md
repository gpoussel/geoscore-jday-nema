# Bloc « Adversaires » — design

Date : 2026-06-10

## Objectif

Afficher la nationalité des adversaires (désormais saisie dans `games.csv` via
`opp1_country` / `opp2_country`) et **vérifier / debunker le mythe** « on tombe
dans le pays de l'adversaire » — particulièrement ressenti en Allemagne.

## Le verdict (données période `all`, ~491 parties avec adversaires connus)

- **Global** : 2,5 % des rounds tombent dans un pays adverse, contre **2,9 %
  attendu** par hasard → ratio **×0,87**. On tombe même légèrement *moins* que le
  hasard. **Mythe faux.**
- **Allemagne** : 2,2 % avec adversaire allemand vs 2,3 % sans → **×0,95**. Aucun
  effet.
- **L'illusion** : la carte est mondiale, l'Allemagne ne pèse que ~2,3 % des
  rounds, mais le duo affronte **37 % d'Allemands**. Sur ~1 770 rounds face à des
  Allemands, ça fait ~39 coïncidences « on retombe chez eux ! » en absolu —
  mémorables, mais au taux normal. Biais de fréquence amplifié par le nombre
  d'Allemands affrontés.

## Constat secondaire : avantage à domicile (réel, lui)

Distinct du mythe de localisation. Quand on tombe **chez** l'adversaire, il joue
mieux :

| Terrain | n | multi nous | multi adv. | cumul ± |
|---|---|---|---|---|
| DE (vs All.) | 39 | 2,24 | **2,44** | **−9 489** |
| US (vs Amér.) | 26 | 2,52 | **2,62** | −7 489 |
| FR (chez nous) | 10 | **2,45** | 2,35 | **+2 546** |

Le multiplicateur de l'équipe à domicile est ~le même partout (adv. en DE 2,44 ≈
nous en FR 2,45). Home advantage symétrique.

## Métriques (calculées par période dans `buildView`)

Pool = parties de la période dont **au moins un** pays adverse est connu (≠ `""`,
≠ `--`).

1. **Qui affronte-t-on ?** part de chaque pays parmi les slots adverses.
2. **Tombe-t-on chez eux ?** par pays X : `P(round=X | adv. de X)` vs
   `P(round=X | adv. pas de X)`, + global observé/attendu/ratio. L'attendu se
   calcule sur la fréquence empirique des pays dans les rounds du pool :
   `attendu_round = 1 − Π(1 − f(c))` pour c dans les pays adverses du jeu.
3. **Sur leurs terres** (rounds `round=X & adv. de X`, seuil `n ≥ 8`) :
   - **multi domicile** = moyenne du multi de l'équipe à domicile (`oppMult` pour
     un pays adverse, `myMult` pour la France repère).
   - **cumul ±** = `Σ(myScore − oppScore)`, signé, **sans multiplicateur**.
   - Ligne repère **FR** = notre multi + notre cumul sur les rounds `round=FR` de
     la période (on est toujours « à domicile » en France).

## UI — `src/components/BlockAdversaires.astro`

Inséré après `BlockPays` dans la boucle des périodes de `index.astro`. Réutilise
`BlockHead`, `Card`, `CardHead`, `Flag`, `HelpTooltip`, style `tf-list`. Pas de
hero « FAUX » : les chiffres suffisent à trancher. Empty-state si pool vide.

1. **Rangée 2 colonnes**
   - Carte « Qui affronte-t-on ? » : liste `tf-list` (drapeau · nom · `×slots` ·
     part %).
   - Carte « Tombe-t-on vraiment chez eux ? » : en-tête compacte avec le global
     (obs % vs att % · ratio), puis par pays obs % vs att % + indicateur ≈/▲/▼.
2. **Carte « Sur leurs terres »** (pleine largeur) : drapeau · pays · `×n` ·
   multi domicile · cumul ± coloré ; ligne repère FR distincte.

## Plomberie

- `stats/build_stats.py` :
  - chaque game → `opp1`, `opp2` (ISO normalisé `uk`→`GB`, `""`/`--` → `null`).
  - chaque round → `myMult` (`my_mult_after`), `oppMult` (`opp_mult_after`).
  - **Pas de changement de schéma CSV** → pas de redémarrage du serveur
    d'enregistrement.
- `src/types.ts` : `RawGame.opp1/opp2: string | null`, `Round.myMult/oppMult:
  number`, nouveau type `OpponentStats`.
- `src/pages/index.astro` : `buildView` calcule `opponents: OpponentStats` et le
  passe au bloc.

## Hors périmètre (YAGNI)

- Perf globale par pays adverse (taux de victoire) — écarté.
- Distinction `--` (non communiqué) vs non renseigné dans l'agrégat.
- État par joueur (le duo est traité comme une entité).
