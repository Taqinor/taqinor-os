# Format de semis de l'arbre d'hypothèses (ASG5)

**Le contrat du point de contact IA « au début » (dd-assumption-engine §4).** Au
jour 0, Claude + le fondateur sèment l'arbre via UN fichier YAML. Après l'import,
le moteur tourne sans IA (§7). Ce document EST le contrat : `apps/adsengine/
seeding.py` lit ce format, le valide (refus avec raisons FR) et l'importe de façon
idempotente (double import = même état).

## Structure

```yaml
version: 1                         # obligatoire — doit valoir 1
nodes:                             # liste NON vide
  - key: hook_facture             # identité LOCALE au fichier (voir plus bas)
    classe: creatif               # creatif | angle | audience_structure
    enonce_fr: "Le hook « facture » convertit mieux que « économies »."
    enjeux_s: 0.7                  # S — enjeux ∈ [0, 1]
    pertinence_r: 0.8             # R — pertinence-décision ∈ [0, 1]
    tags_saison: [ramadan]         # optionnel — posteriors séparés par saison
    parent: null                   # optionnel — key d'un autre nœud
    invalidation_links: []         # optionnel — liste de keys
    prior:                         # optionnel — pseudo-comptes de démarrage
      alpha0: 3
      beta0: 2
    demi_vie_semaines: 8           # optionnel — override (déf. = demi-vie classe)
    statut: assumed                # optionnel — assumed|testing|validated|stale|retired

  - key: hook_facture_video
    classe: creatif
    enonce_fr: "Le hook « facture » gagne SURTOUT en format vidéo."
    enjeux_s: 0.4
    pertinence_r: 0.6
    parent: hook_facture           # ce nœud est un enfant de hook_facture
    invalidation_links: [hook_facture]
```

## Champs

| Champ | Obligatoire | Règle |
|---|---|---|
| `version` | oui | doit valoir `1` |
| `nodes` | oui | liste non vide |
| `key` | oui | chaîne UNIQUE dans le fichier — sert aux références `parent`/`invalidation_links` |
| `classe` | oui | `creatif` \| `angle` \| `audience_structure` |
| `enonce_fr` | oui | texte non vide — **c'est l'identité idempotente** (voir ci-dessous) |
| `enjeux_s` | oui | nombre ∈ [0, 1] |
| `pertinence_r` | oui | nombre ∈ [0, 1] |
| `tags_saison` | non | liste (ex. `[ramadan, ete]`) — un nœud saisonnier n'est jamais oublié par l'horloge hebdo (§3.2) |
| `parent` | non | `key` d'un autre nœud (pas soi-même) |
| `invalidation_links` | non | liste de `key` (arêtes orientées du DAG, §3.5) |
| `prior.alpha0` / `prior.beta0` | non | pseudo-comptes > 0 (démarrage à froid §3.4 ; déf. 1/1 = prior uniforme) |
| `demi_vie_semaines` | non | entier > 0 — override de la demi-vie de classe (§8.1) |
| `statut` | non | un des statuts du modèle (déf. `assumed`) |

## Identité idempotente

Le modèle `AssumptionNode` **ne porte pas** de champ `key` : `key` est LOCAL au
fichier (références internes). L'identité idempotente en base est
**`(company, classe, enonce_fr)`**. Conséquences :

- Réimporter le même énoncé le **retrouve et le met à jour en place** — jamais un
  doublon (double import = même état).
- Le **posterior appris** (`alpha`/`beta`) et le **statut** (cycle de vie) ne sont
  **PAS écrasés** à la réimport : seules les propriétés définitionnelles
  (S/R/tags/prior/demi-vie) sont rafraîchies. On ne rembobine jamais un
  apprentissage en re-semant.
- Un énoncé **réécrit** est une hypothèse **neuve** (nouvel identifiant) — c'est
  voulu : une hypothèse reformulée est une autre croyance.

## Validation

`seeding.validate(seed)` collecte **toutes** les raisons FR d'un coup (jamais un
échec à la fois) et lève `SeedValidationError(reasons_fr)` si le semis est
invalide : version inattendue, `nodes` vide, `key` manquante/dupliquée, classe ou
statut illégal, énoncé vide, S/R hors [0, 1], `tags_saison` non-liste, prior ≤ 0,
demi-vie non entière/≤ 0, `parent`/`invalidation_links` pointant une `key`
inconnue, auto-parent.

## Préflight (ADSENG38 étendu)

`seeding.preflight(company)` vérifie que l'arbre semé est **exploitable** avant
l'autonomie :

- `tree_testable` — l'arbre porte ≥ `SEED_MIN_TESTABLE_NODES` (2) nœuds testables
  (non retirés, S > 0 et R > 0) ;
- `backlog_compatible` — au moins une hypothèse de classe **créatif** testable
  existe (sinon le backlog créatif n'a aucune hypothèse à alimenter).

Renvoie `{'ready': bool, 'checks': [...], 'missing_fr': [...]}`.

## Import

```python
from apps.adsengine import seeding
result = seeding.import_seed(company, yaml_text)   # valide puis importe
# {'created': n, 'updated': m, 'nodes': {key: pk, ...}}
```

L'import est transactionnel (tout ou rien) et se fait en deux passes : upsert des
nœuds, puis câblage des relations `parent` + `invalidation_links`.
