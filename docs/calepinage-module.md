# Module Calepinage — règles du module

> Ce fichier porte les règles DURABLES du module Calepinage (`apps/calepinage`).
> Chaque section est autonome : une tâche qui ajoute une règle ajoute SA section,
> elle ne réécrit pas celles des autres.

<!-- CAL239 -->

## Appels d'offres : module parqué

Le module d'appels d'offres est parqué (voir `docs/parked-modules.md`) : le calepinage 3D n'a plus de pendant AO 2D ni de règle de préséance à tenir. Le contour reste le seul objet géométrique de portée commune ; aucun autre module ne lit `apps.calepinage` pour produire un bordereau.

<!-- CAL238 -->

## Pertes PVGIS : `loss` est une ENTRÉE d'appel, jamais un 14 % caché

**Décision CAL238 du groupe CAL.** Elle vaut pour TOUT appel PVGIS du module
(`PVcalc`, `seriescalc`, `TMY`), présent et à venir.

### Le constat

`loss` n'est pas une propriété de la donnée PVGIS : c'est un paramètre que
**l'appelant** passe dans la requête. Les 14 % que l'on voit partout ne sont
que le défaut de l'*interface web* de PVGIS. Le site public, lui, additionne
deux mondes — une « perte intégrée » et une « perte système totale », toutes
deux en constantes dans `apps/web/src/lib/systemLoss.ts` (`SYSTEM_LOSS_TOTAL` et `PVGIS_BUILTIN_LOSS`) —
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
