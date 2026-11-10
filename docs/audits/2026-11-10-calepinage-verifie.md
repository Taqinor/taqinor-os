# Vérifie ACAL — contre-visite des correctifs de l'unité D3 « calepinage », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 01/11 (`docs/audits/2026-11-01-calepinage-verifie.md`) avait trouvé 4 écarts
S1-S2 et déposé 11 tâches d'écart (ACAL366-376) ; 8 ont été construites et cochées depuis, sans jamais être relues. Le script de
registre ne redemande pas de contre-visite après des écarts corrigés : celle-ci est lancée à la main. Rien n'a été construit ni
déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** D3 `calepinage`, groupe ACAL, 367 tâches cochées sur 368.
- **Échantillon.** Les 8 tâches d'écart cochées : ACAL368, 370, 371, 372, 373, 374, 375, 376. Les 3 autres (ACAL366, 367, 369)
  ne sont pas cochées : listées en §6, non vérifiées.
- **Pile locale.** Aucune ; verdicts par lecture des commits et du code sur `origin/main`, par les gardes et leurs tests
  Python purs lancés sur l'hôte. **Production lue en lecture seule** (comptages) pour l'essai à blanc dû par ACAL375.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire) et essai à blanc de l'orchestrateur

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **8** | ACAL368, 370, 371, 372, 373, 374, 375, 376 |
| partiel / non-fait / faux / régression | **0** | — |

ACAL375 avait été rendue « partielle » par le vérificateur : le code est juste, mais l'essai à blanc en production demandé par
sa preuve n'avait jamais été joué. L'orchestrateur l'a joué le 10/11 (lecture seule) : la migration du marqueur est appliquée ;
8 calepinages, **aucun fichier météo déposé, aucun retrait journalisé, aucun fichier revenu**. Rien à soumettre au fondateur ;
la tâche est tenue.

Écarts S1-S2 du 01/11 : **3 fermés sur 4**. Fermés : la resynchronisation d'un devis qui traite d'abord les modèles désignés
(ACAL374, le S1), le fichier météo retiré qui ne revient plus après la purge de la corbeille (ACAL375), le fournisseur du
fichier météo nommé à la place de PVGIS (ACAL376). Le quatrième (ACAL366, les zones de toiture relues à l'ouverture) a son
code sur `main`, mais la tâche reste bloquée sur sa preuve en direct : elle n'est pas cochée et n'a pas été vérifiée.

## 2. Tests nommés

Tous présents et comportementaux (vraies requêtes HTTP, état relu). Lancés sur l'hôte, verts : les deux gardes du calepinage et
leurs tests (5 et 9 tests). Les tests Django n'ont pas été rejoués ici (CI d'abord).

## 3. Sondes

Les sept sondes de la contre-visite du 01/11 demandent Django : lues, non rejouées (une tentative sur l'hôte a échoué à
l'import). Les enregistrements d'acceptation du 03/11 (`docs/audits/acceptation/ACAL/`) donnent les étapes des tâches ACAL374,
375 et 376 passées.

## 4. Écarts retenus

Aucun sur les tâches cochées.

## 5. Optionnel (non déposé)

- ACAL376 : l'export CSV imprime le code brut de la source au lieu de son libellé.
- ACAL370 : le message d'erreur de la garde ne cite pas le nom réellement appelé.
- ACAL372 : le comptage avant / après de la règle de cohérence sur l'instantané anonymisé, laissé à l'orchestrateur, n'a pas
  d'enregistrement.
- ACAL373 : la raison de lecture seule dit « multi-villa » pour toute autre exclusion (par exemple un devis inactif).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 8 tâches d'écart cochées ; lecture du code, des commits, des tests et des enregistrements d'acceptation ;
  essai à blanc en production.
- **Non couvert, tâches encore ouvertes.** ACAL366 et ACAL367 : code présent, bloquées sur leurs preuves en direct (dont une
  clé de fond de carte). ACAL369 : marquée « attend ACAL368 », or ACAL368 est cochée et relue ici — ce blocage est périmé, la
  tâche est constructible.
- **Non couvert, reste.** Les 359 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; les tests du
  navigateur d'ACAL366 ; aucun rejeu navigateur.
- **Statut.** Aucun écart sur les tâches cochées, mais un écart S2 du 01/11 reste ouvert (ACAL366, non cochée) : le marqueur
  en garde 1 et ACAL reste « construit » jusqu'à ce que cette tâche soit cochée puis relue.

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ACAL | pct: 99 | ecarts_s1_s2: 1 -->
