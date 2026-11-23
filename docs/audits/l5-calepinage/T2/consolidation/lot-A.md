# Lot A (toit et gestes de dessin) — consolidation du tour 2 · 23/11/2026

« Before reporting progress, audit each claim against a tool result from this session. » Relecteurs : F2-TOIT-a, F2-TOIT-b,
F2-GESTES, F2-GESTES-b. Code lu sur la branche (`ba8ca4707`), pas sur `bfb859c90` ; événements `registre/evenements/T2-consolidation-A.jsonl`.

## 1. Comptes
- **Verdicts lus** : 76 lignes (74 corrections ; ACAL950 et ACAL968 ont une 2e ligne qui remplace la 1re) — ok 44 · partiel 28 · non-fait 3
  (ACAL1291, ACAL508, ACAL384) · régression 1 (ACAL510) · faux 0 · déjà-présent 0. Dernier mot par correction : ok 43 · partiel 27.
- **Constats vus** 45 (S1 1, S2 13, S3 25, S4 6) → retenus avec tâche 36 (S1 1, S2 12, S3 23 : GESTES-005 abaissé S2→S3), retenus optionnels 6 (S4),
  a-reproduire 2 (optionnels : GESTES-b-001, -003), doublon 1 (GESTES-002 = commit 6dd9d51955, ACAL1275), écartés artefact 0 (le produit CALX109 ne
  motive aucun écart : il est dit dans GESTES-005 et -015). Causes : lue 28, probable 13, à reproduire 4.
- **Tâches** : ACAL1400 à ACAL1449 (50) : M0 3 (1400-1402) · M1 19 (1403-1421) · M2 26 (1422-1447) · GATED 1 (1448) · Acceptation 1 (1449).
  Modèles : opus 8 · sonnet 42. « Reproduire puis corriger » (cause probable) : 1404, 1407, 1408 ; 1417 et 1425 : le test peut réfuter la cause.
- **Reprises** : ACAL1032→1403 ; 492→1435 ; 504→1405 ; 500, 501, 502→1406 ; 1290→1428+1445 ; 495→1432 ; 527→1411 ; 509→1405+1443 ; 520→1430 ;
  511→1431 ; 533, 1291→1409 ; 508→1421 ; 510→1404 ; 913→1415 ; 968→1413+1414 ; 922→1417 ; 918→1425 ; 946→1424 ; 956→1422 ; 972→1423 ;
  981→1420 ; 994→1418 ; 1006→1419 ; 1028→1427 ; 384→1426. Même cause, même symbole : 500/501/502 (une tâche), 1291/533 (une tâche).
## 2. Classes et écartés
- Neuves : `K-HYDRATATION` (8 endroits, 7 lignes de matrice) et `K-ETAT-PARTAGE` (6 endroits) ; complément de `K-GESTE`, `K-DEFAUT-CHOIX`,
  `K-RETOUR-FAUX`, `K-GRANDEUR-UNIQUE`, `K-SAISIE-PERDUE`, `K-STYLE`, `K-JARGON`, `K-DOC-GEOMETRIE`, `K-IMPASSE` : `T2/classes/complement-A.md`.
- Écartés ou reclassés : GESTES-002 doublon (corrigé, `6dd9d51955`) ; GESTES-005 : déclencheur = produit CALX109 de la pile, texte du 409 gardé (ACAL1440) ;
  ACAL506 reste « 4 appels de géocodage à la saisie de coordonnées » = sondes voulues d'ACAL507, pas un défaut ; fond de carte absent : ACAL508
  (vrai jeton Mapbox) et ACAL507 (vrai 403) restent à rejouer ; ACAL987 : 409 `plan-importe` d'un document d'exemple au plan de fond détaché = artefact du jeu de test.
- Hors périmètre, sans tâche : composition du devis (GESTES-005 : la composition ne suit pas le module du pan) ; `POST simuler` 409 (lot C).
## 3. Choix de produit tranchés (règle écrite ; jamais une décision de Reda)
| # | Choix | Retenu | Coût si faux | Réversible par |
|---|---|---|---|---|
| 1 | Adresse en Guidé (TOIT-a-007) | champ visible tant qu'aucun toit n'est tracé (ACAL1410) | un contrôle de plus au premier écran (plafond 36 de la spec) | CSS |
| 2 | Contour de champ au sol enregistré (GESTES-004, S1) | le pan de tracé disparaît, Annuler le rétablit (ACAL1412) | un pan voulu perdu : Annuler | tâche |
| 3 | Bouton « Générer le devis » de la barre (GESTES-003) | génère quand son bloc est à l'écran (ACAL1437) | un devis créé un clic plus tôt (garde de taille 409 gardée) | tâche |
| 4 | Nom des pans (TOIT-b-002) | « Zone » partout, pas « Pan » (ACAL1430) | libellé | lexique |
| 5 | « Module de départ, à confirmer » (GESTES-007) | drapeau `moduleChoisi` écrit au document (ACAL1401, 1415) | une clé inutile | schéma |
| 6 | Reprise de visite sur plusieurs pans (TOIT-a-015) | dire « comparaison à faire à la main » (ACAL1411) | aucun | tâche |
Le choix 2 corrige un double comptage (justesse), il ne tranche aucun chiffre client : M1, pas GATED. **Décisions ouvertes à écrire** (listées, `decisions.yml` non touché) : aucune nouvelle ; un COMPLÉMENT à D-ACAL-76 (ACAL1448) : « l'étape Panneaux se marque-t-elle
  faite avant tout choix ? » avec le constat TOIT-a-001 ; la pose qui se rouvre à 5 reste D-ACAL-75 (ACAL1330, rien construit avant la réponse).
## 4. Preuves à rejouer (tour 3 — un `partiel` sans défaut vu n'est pas une tâche)
ACAL916 (deux modèles de panneau : la pile n'a pas de second module composable) · ACAL515 (le pivot lui-même ; l'état « site sans panneau posé » n'est pas atteignable
à la main : « Couvrir la facture » descend à 3) · ACAL466 hors ligne · ACAL956 thème sombre et tablette · ACAL962 pays réglé · ACAL1028 « fiches complétées → vrai schéma »
· ACAL377 vraie clé · ACAL949 Alt + molette sur fond calé · ACAL499 recul effectif de 1,8 m sur des modules · ACAL513 phrase d'échelle pendant la frappe · ACAL764
« non calculé » · ACAL478 spec et base non lancées · ACAL987 spec e2e non lancée.

## 5. Optionnels (S4 ou hors-contrat, sans tâche)
TOIT-b-007 « 1 heures » · GESTES-010 carte qui recouvre la bulle · GESTES-011 bouton « Terminer le tracé » grisé resté · GESTES-016 légende « Prêt à envoyer ? »
qui se tasse · GESTES-b-001 tracé fantôme après refus d'allée (à reproduire) · GESTES-b-002 bandeau « Conception rapide » doublé, bouton 36 px · GESTES-b-003
`simuler` 409 sur plan vide (lot C) · GESTES-b-004 surface 30 m² puis 61 m² pendant le tracé · ACAL1032 refus d'un pas nul dit dans la barre d'état · ACAL513, ACAL531,
ACAL536, ACAL537 réserves · ACAL504 panneau Bâtiment absent du Guidé · ACAL478 « 36 contrôles au premier écran » = plafond, pas un résultat simple.

## 6. Tâche → fichiers (disjonction : tout le lot partage `roof-tool-pro11.ts`, `zones.ts`, `obstaclesUi.ts`, `shadingUi.ts` et `EtapeToit.jsx` : 1 lane ou chaîne `@after`)
- Schéma / contrat : 1400, 1401 `contract_samples/roof_layout_v2.schema.json` ; 1402 `contract_samples/calepinage_detail.json` (+ `tests/test_api_detail.py`).
- `roofPro11` (atelier-web) : 1403 `layoutEditor.ts` · 1404 `optimizer.ts` · 1405 `mapDraw.ts`, `roof-tool-pro11.ts`, `shadingUi.ts` · 1406 `obstaclesUi.ts`, `roof-tool-pro11.ts` ·
  1407 `shadingUi.ts`, `environment.ts` · 1408 `scene3d.ts` · 1409 `roof-tool-pro11.ts` · 1412 `poseSurfaces.ts` · 1415 `zones.ts`, `prefill.ts` · 1416 `roof-tool-pro11.ts` ·
  1418 `zones.ts`, `affichageErp.ts` · 1420 `zones.ts` · 1422 `roof-tool-pro11.ts`, `toitParCotes.ts` · 1423 `roof-tool-pro11.ts` · 1430 `zones.ts`, `panVerrouille.ts` ·
  1431 `zones.ts`, `panStats.ts` · 1432 `obstaclesUi.ts` · 1433 `types.ts` · 1436 `shadingUi.ts`.
- Front ERP : 1410 `50-coque-atelier.css` · 1411 `RepriseVisite.jsx` · 1414 et 1413 `BoutonDevis.jsx` / serveur · 1421 `useAtelierBoot.js`, `mapDraw.ts` · 1424 `Approbation.jsx` ·
  1425 `ModeTerrain.jsx` · 1427 `CroquisSchemaGrise.jsx` · 1428, 1429, 1445 `EtapeToit.jsx`/`.helpers.js`/`51-etape-toit.css` · 1434 `calepinageApi.js` (+ `ReglagesGabaritsObstacle.jsx`) ·
  1435 `RaccourcisAtelier.jsx`, `AtelierPanneaux.jsx` · 1437 `CoqueAtelier.jsx` · 1438 `modeExpert.js` · 1439 `calepinageApi.js` · 1441, 1442 `51-etape-toit.css` (+ `obstaclesUi.ts` pour 1441) ·
  1443 `roofbuilder.css`, `PlanImporteCalage.jsx` · 1444 `SunDiagram.jsx` · 1446 `PanneauDetectionToit.jsx` · 1447 `CourseSoleil.jsx` · 1426 `frontend/e2e/calepinage-visuel.spec.js` (fichier NEUF).
- Serveur : 1413 `serializers.py`, `views/calepinages.py` · 1417, 1440 `services/devis.py` · 1419 `services/creation.py`.
- Recoupe possible avec d'autres lots : `calepinageApi.js`, `51-etape-toit.css`, `EtapeToit.jsx`, `roof-tool-pro11.ts`. `plan_lanes.py` (copie du plan + lot) : 0 refus neuf, lot rangé dans la lane `atelier-coque` unie à 71 tâches.
