# Pays des adversaires — design

Date : 2026-06-09. Validé en brainstorming.

## Objectif

Enregistrer le pays (drapeau) des deux adversaires de chaque partie de Team Duels,
pour de futures statistiques. Périmètre actuel : **saisie uniquement** — aucune
visualisation côté site, `build_stats.py` inchangé.

## Modèle de données (games.csv)

Deux nouvelles colonnes en fin de schéma : `opp1_country`, `opp2_country`.
Donnée de **niveau partie**, répétée sur chaque ligne de round (comme `opp_elo`).

| Valeur CSV | Sens |
|---|---|
| *(vide)* | **Non renseignée** — pas encore saisie |
| `--` | **Non communiquée** — drapeau générique GeoGuessr |
| `fr`, `de`, `uk`… | Code pays (ISO 3166-1 alpha-2 minuscule + alias `uk`) |

- `COLUMNS` étendu dans `geoscore.py` ; `load_rows()` normalise les valeurs
  manquantes en `""` — les lignes existantes restent lisibles sans migration.
- `uv run geoscore.py --migrate-schema` matérialise les colonnes sur tout le fichier.
- Validation : vide, `--`, ou code pays valide (liste complète `countries.py`,
  fuzzy match via `resolve_country`). Pas d'ordre garanti entre opp1/opp2.
- Pas de confirmation « premier pays » pour les pays adverses (garde-fou réservé
  aux rounds).
- `build_stats.py` : aucun changement (le `DictReader` ignore les colonnes en plus).
- `stats/CLAUDE.md` : documenter le schéma et la sémantique `--` vs vide.

## Saisie nouvelle partie

### geoscore.py

Après le prompt « ELO adversaire », un prompt unique :

```
Pays adverses (ex: fr de, -- = non communiqué) [Entrée=non renseigné]:
```

- Entrée vide → les deux non renseignés (saisie rapide préservée).
- `fr de` → deux codes validés (fuzzy match inclus).
- `fr --`, `-- --` acceptés ; `--` seul = les deux non communiqués.
- Un seul code (`fr`) → `opp1=fr`, `opp2` non renseigné, rappel discret.
- Commande **`opp fr de`** pendant la saisie des rounds pour corriger après coup
  (même esprit que `elo 1234`), documentée dans l'aide `h`.
- Transit : `play_game` → `build_game_rows` (deux nouveaux paramètres) → CSV.

### geoscore_server.py

- Section « Partie » : deux champs « Pays adv. 1 / Pays adv. 2 » avec la même
  `datalist` que les rounds + un bouton « Non communiqué » par champ (remplit `--`).
- Champs vides → non renseigné.
- Payload `/api/save` : `opp1Country` / `opp2Country`, validés côté serveur
  (même règle), passés à `build_game_rows`. `resetGame` les vide.

## Outil de rattrapage : stats/backfill_opponents.py

Script dédié (PEP 723, importe les helpers de `geoscore.py`).
Lancement : `uv run backfill_opponents.py` (option `--session 26W24.03`).

Parcourt les sessions dans l'ordre chronologique du CSV, ne s'arrête que sur les
parties où au moins un des deux pays est vide :

```
=== Session 25W52.01 — 2025-12-26 — 4 parties ===
  VOD jday (youtube): https://www.youtube.com/watch?v=…

--- Partie 0001 (1/4) — opp 462 — VICTOIRE 6000-0 en 6R ---
   1. W  Iceland (is)   4832-4551
   ...
Pays adverses (fr de, --=non communiqué, s=passer, q=quitter):
```

- Le récap des rounds (pays + scores, W/L/= colorés) sert de repère pour
  naviguer dans la VOD de partie en partie.
- `s` → passe (reste non renseignée), `q` → quitte proprement.
- Saisie identique à geoscore.py (`fr de`, `--`, fuzzy match).
- **Sauvegarde après chaque partie** (`write_all`) → interruption sans perte ;
  relancer reprend où on en était (seules les parties incomplètes sont proposées).
- Partie partiellement renseignée (`opp1` sans `opp2`) : proposée avec la valeur
  existante pré-affichée.
- À la fin (ou sur `q`) : `regenerate_data()` une seule fois + récapitulatif
  (renseignées / passées / restantes).
