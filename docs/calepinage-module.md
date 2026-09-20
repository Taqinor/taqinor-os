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

<!-- CAL238 -->

## Pertes PVGIS : `loss` est une ENTRÉE d'appel, jamais un 14 % caché

**Décision CAL238 du groupe CAL.** Elle vaut pour TOUT appel PVGIS du module
(`PVcalc`, `seriescalc`, `TMY`), présent et à venir.

### Le constat

`loss` n'est pas une propriété de la donnée PVGIS : c'est un paramètre que
**l'appelant** passe dans la requête. Les 14 % que l'on voit partout ne sont
que le défaut de l'*interface web* de PVGIS. Le site public, lui, additionne
deux mondes — une « perte intégrée » et une « perte système totale », toutes
deux en constantes dans `apps/web/src/lib/systemLoss.ts` (lignes 31 et 34) —
avec un facteur de rattrapage entre les deux pour ne pas dérater deux fois.

### La règle du module

1. **Une seule addition.** Le module passe à PVGIS la **somme explicite** des
   postes de pertes du calepinage (CAL139 les possède, les source et les rend
   éditables). Comme il n'y a qu'une addition, aucun poste ne peut être compté
   deux fois — par construction, pas par vigilance.
2. **Chaque poste porte sa source** (`pvgis`, `fiche`, `societe`, `saisie`,
   `mesure`, `hypothese`, ou *aucune*). Un poste non sourcé est **publié et
   nommé** comme tel ; il ne disparaît jamais et n'est jamais « arrondi » dans
   un autre.
3. **La valeur passée est publiée** à côté du résultat
   (`production.base.loss_passee_pct` du contrat
   `contract_samples/calepinage_resultat.json`), avec le détail des postes.
4. **Aucun défaut.** Pas de poste ⇒ pas de politique ⇒ **pas d'appel PVGIS**
   ⇒ **pas de production publiée**. Le module refuse en français en nommant le
   champ ; il n'invente jamais un pourcentage « au cas où ».
5. **Aucune constante de perte du site public** (`PVGIS_BUILTIN_LOSS`,
   `SYSTEM_LOSS_TOTAL`, `PRODUCTION_DERATE`…) ne vit dans `apps/calepinage`.

### Où elle vit et comment elle est TENUE

`backend/django_core/apps/calepinage/services/pertes_politique.py` est le seul
foyer de la règle (`politique_de_pertes()` → postes publiés + la valeur `loss`
à passer, sous forme de chaîne : le total publié est cette chaîne **relue**,
les deux ne peuvent donc pas diverger).

`apps/calepinage/tests/test_politique_pertes_pvgis.py` échoue si :

* une constante de perte du site public réapparaît dans le module ;
* une perte chiffrée en dur y apparaît (balayage de surface, ciblé sur les
  littéraux *utilisés comme une perte* — pas sur le chiffre 20 en général) ;
* la politique se met à fabriquer un défaut quand aucun poste n'est fourni.

Et, côté client PVGIS (CAL135), un test lit la **chaîne de requête réellement
construite** et vérifie qu'elle porte exactement la somme publiée.
