# Calepinage L5 — état du chantier (à lire EN PREMIER pour reprendre, sur ce poste ou un autre)

Dernière écriture : 23/11/2026 par la session « Calpinage module L5 completion » (poste `DESKTOP-APTAHF6`) ·
branche `claude/calpinage-module-l5-aadbde`.
**Prochaine action unique** : voir la dernière ligne du § « Déroulé ».
Ce fichier vit POUSSÉ. Les états antérieurs : `docs/audits/2026-11-20-calepinage-l5.md` (tour 0 du 20/11),
`docs/audits/2026-11-21-calepinage-l5-vague2.md` (vague 2), `T1/` (tour 1 de relecteurs),
`docs/claude-memory/calepinage-decisions-fondateur.md` (recette du 22/11 et fidélité aux maquettes).

## Demande et cadre

- Demande de Reda (22/11/2026 au soir), mot pour mot : dans `contrat-de-sortie.md`. Consignes : « i am going to sleep,
  i want you to choose for me, and give me detailled report tomorrow » puis « forget about cpge go plus for now — only
  do the l5 — the l5 should take you more then 12 hours… and then the checks, and among the checks comes this lead ».
- Ordre imposé : (1) le L5 complet ; (2) les contrôles — maquettes, fonctions, « tous mes devis se calculent seuls
  avec les bonnes hypothèses », un seul moteur (celui du CRM), le lead 1742 ; (3) le rapport détaillé.
- Niveau L5 · régime MIXTE lu sur `origin/main@bfb859c90` · contrat : `contrat-de-sortie.md` (K1-K17) · registre :
  `registre/`.
- Coût annoncé : k = 3 tours × c = 21 points + réserve finale 10 ; quota au départ 3 % (« Weekly · all models », lu par
  `get_usage` le 22/11) ; L5 : coût non mesuré.
- Poste mesuré au tour 0 : 8 cœurs, 15,9 Go de mémoire (8,6 libres avant Docker), 27 Go de disque libre, 82 worktrees,
  Docker Desktop éteint au départ (démarré par cette session : 6 conteneurs de la pile `erp-agentique` sont revenus
  seuls, sans worker ni planificateur) → 2 relecteurs à navigateur à la fois, 3 agents de fond au plus.

## Inventaire du tour 0 (lu sur `origin/main@bfb859c90`)

- Plan `docs/plans/PLAN_AUDIT_CALEPINAGE.md` : 894 tâches ACAL — 436 cochées, **388 « code livré, preuve en direct
  due »** (25 S1, 120 S2, 210 S3, 9 S4, 24 sans gravité ; dues à ACAL1031 : 336, à ACAL1327 : 29, à ACAL490 : 22),
  51 ouvertes (dont 5 tâches d'acceptation), 19 retenues par une décision ouverte.
- CI (run 45077305806 de `main`, vert) : le backend et vitest lisent le module ; en PR, seules 2 specs e2e du
  calepinage tournent (`calepinage-parcours`, `calepinage-onglets`) ; 8 specs ne tournent que la nuit ; les 10 specs
  `e2e/acceptation/acal*.spec.js` ne tournent jamais en CI ; api-fuzz, a11y, visuel et perf de PR ne lisent aucun écran
  du calepinage. Nocturne du 22/11 (45014638342) ROUGE sur : `calepinage-perf` (ACAL440, 2 tests),
  `calepinage-horizon-telephone` (ACAL521), « monkey » calepinage, `test_calx389_budget_simulation` (4 échecs),
  `test_calx328_pages_documents` (rapport d'étude 19 pages, plafond 14). → Lane 0.
- Défaut d'hygiène trouvé : 13 fichiers `.whl` (80 Mo, paquets Python pour Windows) commités dans
  `backend/django_core/apps/calepinage/` par ACAL454 ; rien ne les lit ; ils entrent dans l'image Django à chaque
  deploy. → Lane 0.
- Classes ouvertes du tour 1 (`T1/classes/`) : K-ACTION-ENFOUIE, K-DEFAUT-CHOIX, K-DOC-GEOMETRIE, K-GESTE,
  K-GRANDEUR-UNIQUE, K-IMPASSE, K-JARGON, K-RETOUR-FAUX, K-SAISIE-PERDUE, K-STYLE.

## Instrument de revue (pile privée `l5cal`)

Fiche : `T2/instrument.md`. Écarts au gabarit, voulus : image à soi `l5cal-django:t0` construite depuis
`origin/main` (l'image partagée avait pvlib 0.15.2 au lieu de 0.16.1), un MinIO à soi et un worker Celery à soi sans
planificateur (l'étape Résultats et l'étape Documents en dépendent). Les scripts (lanceur, base, comptes, captures)
vivent dans le scratchpad de la session, pas sur `main`.

## Quota et contexte aux points de contrôle (ajout seulement)

| Point | Date | Quota hebdo | Contexte orchestrateur | Claims renouvelées | Décision |
|---|---|---|---|---|---|
| départ | 22/11 23 h | 3 % | 21 % | prises (`file:docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `app:calepinage`) | tour 0 |
| tour 0 fini, tour 2 lancé | 23/11 00 h UTC | 6 % | 67 % | renouvelées | état écrit et poussé ; économie de contexte : l'orchestrateur ne lit plus que des messages courts |
| tour 2 à mi-chemin | 23/11 02 h 25 UTC | 17 % | 85 % | à renouveler avant 05 h UTC | état écrit et poussé avant la compaction du contexte |
| tour 2 aux trois quarts | 23/11 06 h 00 UTC | 30 % (≈ 3,7 points par heure) | 21 % (après compaction) | renouvelées à 05 h 55 UTC | consolidation par lots, en sonnet sauf les lots C et E ; viser moins de 65 % à la fin du L5 |

## Où sont les choses

- Notes : `docs/audits/l5-calepinage/` — `contrat-de-sortie.md`, `etat.md`, `T2/` (recherches R1-R2, listes de
  contre-vérification `T2/cv/`, rapports des relecteurs), `registre/`, `maquettes/` (v1), `maquettes-v2/`.
- Code : branche d'intégration `claude/calpinage-module-l5-aadbde` ; worktree de l'instrument
  `.claude/worktrees/l5cal-instr` (ne jamais l'éditer ; mise à jour par `git merge --ff-only`).
- Claims : `file:docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `app:calepinage`, propriétaire
  `DESKTOP-APTAHF6/claude/calpinage-module-l5-aadbde` (bail 6 h, à renouveler à chaque point ; relâcher après le merge).

## Choix pris seul (aucune question — réversibles, jamais des décisions de Reda)

| # | Choix | Règle appliquée | Coût si faux |
|---|---|---|---|
| 1 | Docker Desktop démarré sur ce poste pour monter l'instrument | prérequis manquant à installer plutôt qu'à signaler | aucun (arrêt en fin de session) |
| 2 | Les deux lanes de diagnostic du lead 1742 arrêtées dès la précision de Reda ; le cas est rangé dans la phase de contrôles | consigne de Reda | à relancer à la phase de contrôles |
| 3 | Contre-vérification du tour 2 : les 388 corrections livrées, réparties sur 11 relecteurs, S1-S2 d'abord ; passage à « S1-S2 + 25 % du reste » dès que `non-fait + partiel` ≤ 10 % | `L4.md` « Cost and stop » | des corrections S3 non rejouées, dites au rapport |
| 4 | Contrôle de l'instrument : deux variables « à clé » non vides admises — `GPG_KEY` (empreinte PUBLIQUE de la clé de publication de Python 3.11, posée par l'image de base, vérifiée égale à celle de `python:3.11.11-slim-bookworm`) et `PUBLIC_MAPTILER_KEY=factice-l5cal` (sans clé l'atelier refuse de démarrer ; la vraie est limitée au domaine du site) | lecture du gabarit : aucune clé RÉELLE | aucun |
| 5 | Conteneurs inutilisés de la pile partagée `erp-agentique` arrêtés (`fastapi_ia`, `django_core`, `minio`, `redis`, `redis_cache`) pour rendre 1,7 Go ; la base, elle, reste en marche | poste à 2,7 Go libres avec deux relecteurs ; personne ne s'en servait (Docker était éteint) | `docker start` des cinq à la fin (ligne du nettoyage) |
| 6 | Lane 0 : les deux tests rouges du nocturne ont été remis au vert en RELEVANT leur borne au nombre mesuré, avec la liste des tâches qui l'expliquent écrite dans le test (3 lectures météo de plus par simulation : ACAL706, ACAL744 ×2 ; rapport d'étude à 19 pages : six sections nées depuis) | consigne de lane : jamais un plafond élargi sans nommer ce qui le consomme | si l'une des trois lectures est jugée superflue : une tâche pour la retirer |
| 7 | Maquettes v2 : même ossature que la v1 (rien ne se déplace), finition refaite — carte plein cadre, pièces flottantes, bleu nuit pour l'actif, or pour la seule action suivante, chiffres dessinés (`maquettes-v2/LANGAGE.md`) | « much prettier » sans jeter les trois tours de fidélité du 22/11 | une passe de style à défaire |

## Déroulé (un point par étape, avec ses chiffres)

1. Tour 0 (22-23/11) : état relu, claims prises, poste mesuré, CI de `main` lue (ci-dessus), recherches R1 (beauté,
   simplicité) et R2 (fonctions : 15 fonctions utiles absentes du plan, `T2/R2-fonctions.md` § B) rendues, listes de
   contre-vérification générées (`T2/cv/`, 388 corrections sur 11 relecteurs). Instrument `l5cal` monté et contrôlé
   (« instrument sûr » avec les deux exceptions du choix n° 4) : base clonée du gabarit de test `test_erp_l5w` + `migrate`
   + `seed_demo` + `seed_catalogue`, serveur gunicorn à 3 processus (127.0.0.1:8021), worker Celery à 2 processus sans
   planificateur, MinIO et Redis à soi, front construit servi sur 127.0.0.1:5241, 14 comptes de revue. PR #1527 ouverte
   en brouillon, Auto-fix allumé.
2. Lane 0 (pliée, d7bc604cc) : 13 fichiers `.whl` retirés du dépôt et ignorés ; `test_calx389_budget_simulation` et
   `test_calx328_pages_documents` verts (rejoués localement : 17 tests, 6 échecs avant, 0 après). Restent du nocturne :
   `calepinage-perf`, `calepinage-horizon-telephone`, « monkey » — à rejouer sur l'instrument au repos.
3. Maquettes v2 : langage écrit, `Main` (Toit) et `Resultats` écrites par l'orchestrateur et publiées sur le canevas
   https://claude.ai/artifact/BJ5TrpZU3QvwHE3fWAteH5 ; lot A (six écrans) confié à une lane de design.
4. Tour 2 de relecteurs : EN COURS (etat au 23/11 02 h 25 UTC). `non-fait + partiel` ~ 40 % > 10 % : TOUTES les
   corrections sont rejouees. Listes longues coupees en deux : moitie « a » = relecteur opus (liste + classes +
   regard neuf), moitie « b » = verificateur sonnet (liste seule). Lancement : `T2/lancement/<code>.md` (message de
   deux lignes : « lis ta fiche et execute-la » + le bloc d'ancrage). RENTRES (rapport `T2/<code>.md`, verdicts
   `registre/evenements/T2-<code>-cv.jsonl`, constats `registre/constats/T2-<code>.jsonl`) :
   - `S2-PARCOURS` 29/54 jouees : ok 18, partiel 8, non-fait 3 ; 26 constats (8 S2) ; K6 NON tenu.
   - `F2-RESU` 31/54 : ok 17, partiel 13 (dont la S1 ACAL1304), non-fait 1 ; 26 constats (7 S2) ; meme production
     lue 4 362 / 4 542 / 5 131 / 5 173 kWh selon l'ecran.
   - `S2-PARCOURS-b` 11/25 (arrete par la panne) : ok 9, partiel 1, non-fait 1 ; 10 a REDONNER (ACAL874, 875,
     877-880, 883-885, 888).
   - `F2-GESTES` (liste -a) 18/18 : ok 11, partiel 6, non essaye 1 ; 16 constats (1 S1 : champ au sol compte deux
     fois, 106 modules ; 3 S2).
   - `F2-TOIT-a` 21/21 : ok 11, partiel 10 ; 18 constats (9 S2). `F2-GESTES-b` 17 : ok 9, partiel 6, non-fait 1.
   - `F2-DOCS-a` 17 : ok 8, partiel 5, non essaye 4 ; 2 S1 (rapport d'etude : un plafond imprime comme P50 ; deux
     productions pour un meme client). `F2-RESU-b` 23 : ok 11, partiel 7, non-fait 1, non essaye 4.
   - `F2-POSE-a` 18 : ok 9, partiel 7 ; 1 S1 (pose enregistree de 60 panneaux rouverte a 5, puis ecrite a 5).
   - `F2-TOIT-b` 20 : ok 12, partiel 5, non-fait 2, REGRESSION 1 (ACAL510 : un calepinage a « Pan existant » ne se
     rouvre plus). `F2-DOCS-b` 19 : ok 11, partiel 6, non essaye 2.
   - `F2-ELEC-a` 19 : ok 6, partiel 7, non essaye 6 (redonnees a `F2-ELEC-b`). `F2-SIMU-a` 22 : ok 10, partiel 9,
     non-fait 1 ; 1 S1 (le P50 de tete compte des panneaux raccordes a rien).
   - `F2-POSE-b` 17 : ok 7, partiel 9, non-fait 1 (ACAL547) ; 11 constats. `F2-ELEC-b` 25 (dont ACAL632-636, 1188) :
     ok 19, partiel 5, non essaye 1 (ACAL895). `T2` (telephone, tablette) 16 : ok 10, partiel 5, non essaye 1
     (ACAL385, une spec e2e : a jouer par l'orchestrateur) ; 12 constats dont 6 S2 (au telephone on pose sans voir
     le toit ; « Releve de visite » et « Montrer au client » enfouis ; releve hors ligne jamais renvoye).
   BILAN au 23/11 06 h UTC (script `$SP/l5b/bilan_cv.py`) : 312 corrections avec verdict — ok 188, partiel 112,
   non-fait 11, regression 1 ; 76 sans verdict (en vol ou a lancer).
   EN VOL (23/11 06 h 05 UTC) : `F2-CONSO` (opus), `F2-SIMU-b` (`rev_b7`), `RATT-1` (`rev_b8`, 15 taches : les
   preuves perdues de `S2-PARCOURS-b` + ACAL856, 959), `RATT-2` (`rev_b5`, 15 taches : restes des autres listes,
   avec une exception pour `docker exec l5cal-django python manage.py …`) ; lancement : `T2/lancement/RATT.md`.
   RESTE A LANCER : `B2` EN DERNIER (opus, 15 taches + comparaison des 13 ecrans aux maquettes v1 et v2).
   A JOUER PAR L'ORCHESTRATEUR : ACAL385 (spec e2e), ACAL1194 et ACAL490 (taches d'acceptation).
   CONSOLIDATION PAR LOTS (section ajoutee a `T2/brief-consolidation.md`) : lots A (toit, gestes ; ids 1400-1499)
   et B (pose, electrique ; 1500-1599) EN VOL en sonnet effort haut ; C (production ; 1600-1699, opus) apres
   `F2-SIMU-b` et `F2-CONSO` ; D (documents, parcours, liste ; 1700-1799) apres `RATT-1/2` ; E (ecrans, maquettes v2,
   telephone, fonctions ; 1800-1899, opus) apres `B2`. Chaque lot ecrit `T2/consolidation/lot-<X>-taches.md` ;
   l'orchestrateur ASSEMBLE dans le plan (nouveau groupe), lance les gardes, puis `plan_lanes.py`.
   Plafond : 4 agents de fond (3 relecteurs + 1 lane) ; machine virtuelle de Docker a 5 Go (voir point 8).
5. Construction, vague 1 (37 taches ouvertes du plan ; brief `T2/brief-lanes.md` ; base = branche d'integration) :
   - PLIEES et poussees : lane 0 (2 tests du nocturne, wheels retires) ; lane `liste` (ACAL1308, 1309 contestee,
     1310, 1322, 1333-1339, 1342, 1343 ; migration calepinage 0043 ; schema OpenAPI regenere ; empreinte CODEMAP et
     reference on_delete rafraichies ; reperes de test `cal-vignette-toit`, `cal-signal` declares) ; lane `carte`
     (ACAL1273, 1328, 1329 ; ACAL746 IMPOSSIBLE : pas de page officielle de conditions d'usage NASA POWER).
   - PLIEES aussi : lanes `production` (ACAL1274, 1249 ; 1321 contestee), `brouillon` (ACAL1246, 1248, 1275, 1345),
     `toit` (ACAL1341, 1323, 1247 ; demande croisee : valeur `plat` a ajouter a `pitchSource.mode` du contrat du
     document de toiture), `finitions` (ACAL1280, 1340, 1344, 1267 ; 1348 contestee ; 1349 IMPOSSIBLE sans valeurs
     inventees : salissure, degradation initiale, indisponibilite, pertes de cables).
   - RESTE de la vague 1 : la lane `e2e` + `telephone` [ACAL1272, 1346, 1347, 1353], qui a besoin de la pile.
   - TENUE DU PLAN faite le 23/11 (script `$SP/l5b/marquer_vague1.py`) : 28 tâches livrées + 3 « déjà présent »
     marquées `[BLOCKED: code livré le 2026-11-23 … preuve en direct due à ACAL1254 / ACAL1327, tour 3 du L5]` ;
     ACAL746 et ACAL1349 passées GATED sur D-ACAL-81 et D-ACAL-82 ; D-ACAL-80 (température de froid) ouverte.
5-bis. RELECTURE ADVERSE DES `ok` (23/11, `T2/lancement/AUDIT-OK.md`, sorties `registre/evenements/T2-audit-ok*.jsonl`) :
   un `ok` de relecteur ne coche RIEN. Échantillon 37 : 17 confirmés, 16 insuffisants, 4 contredits. Lots A 35 :
   22 / 13 / 0 ; B 32 : 23 / 9 / 0 ; D 52 : 26 / 24 / 2. RESTE : lot C (ok de F2-SIMU-a/b, F2-RESU, F2-RESU-b,
   F2-CONSO, quand ces relecteurs sont rentrés — `python $SP/l5b/listes_audit_ok.py "" C`) et un lot D2 (RATT-1, B2 :
   `… "-2" D`). ENSUITE : `confirme` → enregistrement d'acceptation par l'orchestrateur + coche ; `insuffisant` →
   rejeu ciblé au tour 3 (le motif dit quoi rejouer) ; `contredit` → tâche de reprise (lot O, ids 1900-1949).
5-ter. CONSTRUCTION, vague 2 (groupe du 23/11 du plan ; assemblage `$SP/l5b/assembler.py --ecrire`, idempotent ;
   lanes : `$SP/l5b/lanes-v2.txt`). `plan_lanes.py` range 57 tâches dans UNE lane `etape-toit` (fichiers partagés du
   moteur de dessin) : découpe à la main en sous-lanes disjointes par fichier SOURCE, 3 à 4 agents à la fois (mémoire
   libre du poste : 2,5 Go), chaque agent part de la tête de la branche d'intégration :
   - PLIÉES et poussées (23/11, 06 h 45 → 07 h 40 UTC), 29 tâches corrigées : `contrats-m0` [1400, 1401] ·
     `balayage` [1404 (la régression), 1504, 1505, 1525, 1526, 1533] · `carte-a` [1405, 1406, 1409, 1421 ; 1407
     IMPOSSIBLE sans décision → GATED D-ACAL-83 (l'ombre proche est mesurée au seul centre du pan : d'où « −72 % ») ;
     1501 contestée, même cause, GATED] · `contrats-suite` [1402, 1500, 1413, 1414, 1417, 1440, 1419] · `editeur-1`
     [1403, 1520, 1521] · `zones` [1415, 1418, 1420, 1430, 1431, 1513, 1510]. Goldens de démarrage régénérés.
   - CI ROUGE à 77c8c0128 (07 h 20 UTC), trois causes : (1) deux lignes de plus de 120 colonnes — corrigé (6d3d95a44a) ;
     (2) `check_forme_code` (gros fichier `optimizer.ts` : +18 lignes) — vert depuis que les tâches sont marquées
     livrées au plan (le budget vient de leur clause « Code net ») ; (3) `apps/web/tests/estimatorPreviewPro11.test.ts`
     (2 cas qui lisent le source par motif) — lane `couture-1` EN VOL (vraie installation d'`apps/web`, suite
     entière). NE RIEN PLIER de plus sur `roofPro11` avant le retour de `couture-1`.
   - PLIÉES ensuite (07 h 45 → 08 h 06 UTC) : `scene` [1412 (S1 champ au sol compté deux fois), 1408, 1503, 1515,
     1516 ; 1523 impossible dans sa lane → `optimizer.ts::renderLiveWinner`] · `react` [1502, 1410, 1411, 1514, 1517,
     1428, 1429, 1424, 1435, 1438, 1427, 1519] · `carte-b` [1416, 1422, 1423, 1433, 1432, 1436, 1441, 1442 + deux
     demandes croisées honorées] · `couture-1` (suite `apps/web` verte sur sa base : 9 742 cas). 53 tâches de la
     vague 2 corrigées et marquées livrées. TOUR 2 CLOS : 381 corrections avec verdict (ok 239, partiel 130,
     non-fait 11, régression 1) ; relecture adverse de tous les ok : 132 confirmés (cochés), 95 insuffisants, 12
     contredits. Fidélité aux maquettes v2 (relecteur B2) : 0 fidèle, 3 proches, 8 éloignés, 2 non comparés.
   - EN VOL (23/11 08 h 10 UTC) : `electrique-1` [1506, 1538, 1539, 1540, 1512, 1545, 1546, 1537, 1542] opus ·
     `simulation-1` [1605, 1602, 1606, 1607, 1622, 1619] opus · `editeur-2` [1522, 1524, 1527, 1528, 1529, 1530,
     1443 + demande croisée historique] sonnet · `electrique-2` [1509, 1535, 1536, 1541, 1543, 1544, 1547, 1549,
     1550] sonnet · couture, 2e passe (branche `l5w2-couture-2`, agent ad48e173ad7c41aaa repris, garde son
     `node_modules`) · consolidation LOT E (opus). CI en cours sur cf6c37e195 : NE PAS pousser avant son verdict
     (chaque push annule le run précédent).
   - POINT à 08 h 35 UTC : pliées en plus `electrique-2` [1509, 1535, 1536, 1541, 1543, 1544, 1547, 1549, 1550],
     `editeur-2` [1522, 1524, 1527, 1528, 1529, 1530, 1443 + historique du pan actif], coutures 1 et 2 ; 68 tâches
     de la vague 2 livrées. LOT E assemblé (42 tâches, ACAL1800-1841 ; D-ACAL-88 ouverte) : le plan porte 284 tâches
     du tour 2, gardes vertes. Budget du bundle `roof-tool` 635 → 650 Ko (636,0 mesurés). CI ROUGE à 626926e930 sur
     DEUX gardes connues : (a) `check_tests_source_regex` — trois cas de `langageVisuel.test.mjs` (ACAL1519, 1524,
     1443) lisent un source par motif : `couture-3` (agent a528a75d09c030a66, branche `l5w2-couture-3`) les réécrit
     et joue la suite du front ERP ; (b) `check_forme_code` — `apps/web/tests/estimatorRuntimePro10Pro11.test.ts`
     +3 lignes : `couture-4` (agent ad48e173ad7c41aaa, branche `l5w2-couture-4`, vraie installation d'`apps/web`).
     EN VOL aussi : `electrique-1`, `simulation-1`, `resultats-m1` [1611, 1621, 1614] sonnet, `coque-prealables`
     [1437, 1617, 1727, 1730, 1731, 1745] sonnet. ENSUITE, sur la tête pliée de `coque-prealables` : `coque-v2`
     [1800, 1801, 1802, 1803, 1804, 1805] opus, UNE lane, puis les écrans du lot E en parallèle (ordre :
     `T2/consolidation/lot-E.md` § 7) et le téléphone M1 [1807-1812].
   - BUDGET (08 h 10 UTC) : quota hebdo 39 % (≈ 4 points par heure, ≈ 0,3 point par agent) ; contexte de
     l'orchestrateur 58 %. Règle : construire jusqu'à ≈ 56 %, puis tour 3 léger, fusion, phase de contrôles (≤ 5
     points), rapport. PRIORITÉ de ce qui reste à construire : (1) les M1 de tous les lots ; (2) la coque v2 puis
     les écrans (lot E) ; (3) les M2 restent au plan.
   - À LANCER ensuite (M1 d'abord) : `consommation` [1601, 1603, 1604, 1608, 1609, 1610] opus ; `rapport-m1`
     [1615, 1616, 1677, 1701, 1702] opus ; `resultats-m1` [1611, 1614, 1621, 1613] sonnet/opus ; `production-web`
     [1612, 1618] opus ; `docs-m1` [1700, 1703, 1704, 1709, 1705, 1710, 1711, 1712] (après `electrique-1`) ;
     `toit-d` [1706, 1707] opus ; `livrables` [1507, 1508, 1551, 1713] ; `terrain` [1511, 1425] ; `optimiseur-2`
     (demandes croisées de `entree-lot-O.md` § 3 sur `optimizer.ts`, dont ACAL1523) opus ; puis la chaîne de coque
     du lot E et ses écrans. M2 restants : `petites` [1444, 1447, 1446, 1534, 1434, 1439, 1548, 1518, 1531], [1445],
     `coque-e2e` [1272, 1346, 1347, 1353, 1426, 1437] (pile reconstruite sur la branche) ; [1532] derrière 1501.
   - LOT D assemblé (59 tâches, ACAL1700-1758 ; D-ACAL-86 et 87 ouvertes). Le plan porte 242 tâches du tour 2.
     Demandes croisées encore ouvertes : `optimizer.ts` (kWc de la carte passé à `peindreBande`, `majChiffrage`
     après « Enregistrer ») ; contrat `orientation_nord` aux motifs de pan vide ; `prodWindow.ts` et
     `roof-tool-pro11.ts` multiplient encore par 720 W.
   - LOT C assemblé (78 tâches, ACAL1600-1677 ; classes `K-ANNEE-MOYENNE`, table des 17 lectures de la production
     dans `T2/classes/complement-C.md`) ; lanes à découper d'après `T2/consolidation/lot-C.md` § 8 : simulation
     (serveur), consommation (serveur), rapport, résultats (front), atelier-web, petites. LOT D EN VOL (sonnet).
     LOT E après `B2` (EN VOL). LOT O (orchestrateur, ids 1900-1949) à écrire : reprises d'ACAL987 et ACAL444
     (`ok` contredits hors lots), demandes croisées ci-dessus, tâches pour d'autres plans listées par le lot C
     (worker Celery → plan deploy ; fiche produit → plan stock).
   - ACCEPTATION : `docs/audits/acceptation/ACAL/2026-11-23-bfb859c90.md` — 127 tâches cochées (ok confirmés par
     la relecture adverse : 127 confirmés, 94 insuffisants à rejouer au tour 3, 12 contredits devenus des reprises).
     Scripts : `$SP/l5b/confirmes.py`, `enregistrer_acceptation.py`, `marquer_livrees.py` (à relancer après chaque
     assemblage), `assembler.py --ecrire`, `decisions_t2.py` (D-ACAL-80 à 85 ouvertes).
   - A LANCER ensuite, une a la fois : `atelier-brouillon` [ACAL1246, 1248, 1275, 1345] sonnet · `e2e` + `telephone`
     [ACAL1272, 1346, 1347, 1353] sonnet (a besoin de la pile : le dire dans son message) · `atelier-carte` + `coque`
     + `pompage` [ACAL1340, 1280, 1267] sonnet · `atelier-coque` + `exemples` + `reglages` [ACAL1348, 1349, 1344]
     sonnet · `atelier-toit` + `langage-ecran` + `simulation` [ACAL1341, 1323, 1247] opus.
   - Pli d'une lane : `git diff --stat <integration>...<branche>` ; `git merge --no-ff` ; si le serveur a change :
     `makemigrations --check` et `check_openapi_schema.py --write` dans un conteneur `l5cal-django:t0` (env
     `l5cal/test-lane0.env`, monte le worktree en `/repo`) ; `python scripts/codemap_fingerprint.py --write` ; pousser.
     Rouges CI deja vus et corriges sur cette vague : fonction de service publique sans appelant (la rendre privee),
     empreinte CODEMAP, reference `docs/on-delete-financial-audit.md`, repere `data-testid="cal-*"` non declare dans
     `frontend/src/features/calepinage/E2E_HOOKS.md` + `e2eHooks.test.mjs`.
   - Neuf taches REFUSEES par le planificateur tant que leurs prerequis ne sont pas coches (ACAL450, 982, 984,
     1193, 1002, 1003, 1010, 1286, 1293) : elles attendent l'acceptation (K16).
6. Maquettes v2 : écrites et publiées par l'orchestrateur — `Main` (Toit), `Resultats`, `Liste`, `Presentation`
   (écran NEUF : « Montrer au client » en grand format, sans prix) ; lot A en cours par une lane de design
   (`Panneaux`, `Electrique`, `Schema`, `ToitSombre`, `ResultatsIncomplet`, `Documents` — elle écrit dans le
   scratchpad `maquettes-v2/project/`, l'orchestrateur regarde le rendu, publie sur le canevas et recopie dans
   `maquettes-v2/`) ; lot B fait de même. LES 14 MAQUETTES v2 SONT ÉCRITES, publiées sur le canevas et rangées dans `maquettes-v2/`.
7. Mesures du poste avec 4 agents : 3,3 Go libres, 43 % de processeur — 4 agents de fond tiennent (2 relecteurs à
   navigateur + 2 lanes sans navigateur) ; ne pas dépasser.
8. PANNE de l'instrument le 23/11 de ~00 h 55 a ~01 h 28 UTC : la machine virtuelle de Docker (5 Go, 3 Go d'echange,
   `.wslconfig` de Reda, non modifie) etait pleine, echange compris ; `docker` ne repondait plus. Remede applique :
   Docker Desktop redemarre (`wsl --shutdown`), instrument remonte par `l5cal/relancer.sh` avec des plafonds —
   serveur gunicorn 2 processus x 2 fils, recyclage a 250 requetes, 1,1 Go ; worker Celery 1 processus, recycle
   toutes les 4 taches, 1,3 Go ; conteneur de test d'une lane 0,9 Go. Base, comptes et donnees intacts. Un
   surveillant (outil Monitor, a rearmer toutes les 30 min) previent si l'API est muette trois fois de suite.
   `S2-PARCOURS-b` s'est arrete a 11 sur 25 a cause de la panne : ses 10 non joues (ACAL874, 875, 877-880, 883-885,
   888) sont a redonner a un verificateur.

**Prochaines actions, dans l'ordre** :
a. à chaque retour de relecteur → lancer le suivant de la liste ; à chaque retour de lane → relire son diff
   (`git diff claude/calpinage-module-l5-aadbde...<branche>`), plier `--no-ff`, pousser, lancer la lane suivante ;
b. au retour de la lane de design → regarder les six rendus, publier, recopier, lui confier le lot B ;
c. entre deux lots de relecteurs, pile au repos : rejouer la base e2e du calepinage sur l'instrument
   (`E2E_BASE_URL=http://127.0.0.1:5241`, specs `calepinage-*.spec.js`, dont perf, horizon téléphone, « monkey » : K17) ;
d. tous les relecteurs rentrés → consolidation (un agent opus, `gabarits/consolidation.md`) : verdicts, classes,
   tâches v3 au plan du propriétaire, lanes ; y joindre les fonctions retenues de `T2/R2-fonctions.md` § B ;
e. tests premiers, lanes de correction, pli, couture, CI, merge par la file ; enregistrements d'acceptation de
   l'orchestrateur pour les tâches au verdict `ok` (K16) ; puis tour 3 ; puis la finale ; puis la phase de contrôles.

## Phase de contrôles (APRÈS le L5 — ne pas commencer avant)

- Maquettes : chaque écran contre sa maquette v2, relecteur neuf.
- Fonctions : parcours critiques rejoués 3 fois.
- « Tous mes devis se calculent seuls, avec les bonnes hypothèses » et « un seul moteur, celui du CRM » : mesure sur
  des fiches réelles, en lecture seule.
- Lead 1742 : relu en prod (lecture seule) le 22/11 — son calepinage est resté attaché à un brouillon antérieur au
  devis envoyé, il porte le nombre de panneaux de l'option avec batterie alors que le devis recommande l'option sans,
  il juge l'onduleur hybride avec la borne 1,35 que la décision D-HYB-1 a remplacée par la fiche constructeur, deux
  calculs de chaînes ne s'accordent pas, et sa production n'est pas simulée alors que le devis porte la sienne. Causes
  à établir dans le code à ce moment-là, pas avant.

## À dire à Reda dans le rapport final

Tenu à jour au fil de l'eau dans `T2/pour-reda.md`.

## Nettoyage à la fin (cocher chaque ligne)

- [ ] dernière vague mergée par la file ; [ ] claims relâchées ; [ ] instrument démonté (conteneurs `l5cal-*`, réseau
      `l5cal-net`, serveur du front, `DROP DATABASE l5cal`, fichier d'environnement effacé, image `l5cal-django:t0`)
- [ ] worktree `l5cal-instr` et worktrees de lanes retirés ; Docker Desktop arrêté s'il n'était pas en marche
- [ ] rétro bornée
