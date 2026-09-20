# Module Calepinage — règles du module

> Ce fichier porte les règles DURABLES du module Calepinage (`apps/calepinage`).
> Chaque section est autonome : une tâche qui ajoute une règle ajoute SA section,
> elle ne réécrit pas celles des autres.

<!-- CAL239 -->

## Préséance entre le calepinage 3D et la variante AO 2D opposable

**Décision D9 du groupe CAL (19/09/2026), et elle ne se négocie pas ligne par ligne.**

Depuis CAL30–CAL32, une affaire d'appel d'offres porte **deux systèmes de
variantes** qui se ressemblent assez pour être confondus :

| | `ao.VarianteCalepinage` (2D) | `calepinage.CalepinageVariante` (3D) |
|---|---|---|
| Où | `apps/ao/models.py` — studio SVG AO | `apps/calepinage/models.py` — module neutre |
| Rattachement | `toiture` + `appel_offre` (FK dures) | `calepinage` (pivot du module) |
| Statut | `brouillon / calculee / publiable / perime` | statuts du module |

### La règle

1. **La variante 2D RETENUE est la source OPPOSABLE.** C'est elle — et elle
   seule — qui alimente le **bordereau des prix** (`LigneBordereau`) et la
   **fabrique documentaire** du dossier d'appel d'offres. C'est la géométrie
   relevée, cotée, contrôlée : celle qui engage l'entreprise devant l'acheteur.
2. **Le calepinage 3D est le document de TRAVAIL.** Étude, planche d'atelier,
   note de calcul, devis commercial : tout cela s'appuie légitimement sur lui.
   Il est plus riche, plus rapide à produire — et il n'est pas contradictoire.
3. **La nomenclature 3D (CAL185) ne peut JAMAIS alimenter un bordereau AO.**
   C'est le point précis que cette règle existe pour fermer : le premier agent
   qui branchera CAL185 sur le bordereau produira un dossier dont les quantités
   ne correspondent plus aux planches déposées — un motif d'écartement d'offre.
4. **Aucun modèle n'est fusionné.** Les deux tables restent distinctes, dans
   deux apps distinctes, avec deux chaînes de migrations mono-écrivain
   (contrats import-linter `ao-models-decoupled` et
   `calepinage-models-decoupled`).

### Ce qui traverse quand même la frontière

Le **contour**, et rien d'autre (D4, CAL31/CAL240/CAL241) : il voyage dans les
deux sens entre `ToitureAO.contour_local_m` (repère local métrique, ancré par
`origine_lat`/`origine_lng`) et le champ `outline` du document 3D (degrés
`[lat, lng]`). Aucune géométrie opposable — obstacles, chaînes de cotes, zones
— n'est jamais réécrite par une reprise de contour.

### Comment la règle est TENUE

`backend/django_core/apps/ao/tests/test_preseance_calepinage.py` échoue si :

* `LigneBordereau.variante` cesse de pointer `ao.VarianteCalepinage` ;
* une origine de quantité issue du module 3D apparaît dans
  `LigneBordereau.QuantiteSource` ;
* un module producteur du bordereau AO se met à lire `apps.calepinage` ;
* les deux modèles de variantes sont fusionnés.

**À citer sur l'écran d'affaire (CAL41)** : « Le bordereau est servi par la
variante 2D retenue. Le calepinage 3D est un document de travail. »
