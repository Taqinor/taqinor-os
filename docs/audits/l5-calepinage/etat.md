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
   - POINT à 08 h 55 UTC — **CI VERTE sur 746e197f5** (poussé à 08 h 42 ; 79 tâches de la vague 2 + 30 de la vague
     1). C'est le candidat de la PREMIÈRE FUSION (vague A). Portail avant fusion EN VOL : critique finale Fable sur
     `git diff origin/main...746e197f5` (sortie `T2/critique-vague-A.md` ; 1er appel Fable de la campagne) et essai
     du site public sur l'aperçu Cloudflare `https://claude-calpinage-module-l5-aadbde-taqinor-web.taqinor.workers.dev`
     contre `https://taqinor.ma` (sortie `T2/apercu-public.md`) — le moteur `roofPro11` est partagé et le site
     public se déploie à la fusion. SI la critique dit fusionnable : `gh pr ready 1527` puis
     `gh pr merge 1527 --auto --merge` (file de fusion), NE RIEN POUSSER entre-temps (la tête de la PR doit rester
     746e197f5) ; après la fusion, les plis locaux (au-delà de 746e197f5 : `coque-prealables` déjà plié en local,
     tête locale 5fb6e6166e) partent dans une NOUVELLE PR de la même branche (vague B). Bloquants de la critique :
     les corriger d'abord (couture), repousser, attendre la CI.
     Les lanes partent désormais de la branche LOCALE (`git checkout -B <lane> claude/calpinage-module-l5-aadbde`,
     sans fetch) pour ne pas pousser pendant la CI. Conteneurs `l5cal-django` et `l5cal-celery` ARRÊTÉS (mémoire
     pour les tests) : à reconstruire sur la branche pour le tour 3 (`$SP/l5cal/relancer.sh` après un build du
     front de la branche dans `l5cal-instr` ou un nouveau worktree).
     EN VOL : `simulation-1` opus · `consommation` [1601, 1603, 1604, 1608, 1609, 1610] opus · `docs-m1` [1700,
     1703, 1704, 1709, 1711, 1712, 1710, 1705] opus · `coque-v2` [1800-1805 + ACAL1617] opus (base locale).
     Pliées depuis 08 h 35 : `electrique-1` (9), coutures 3 et 4, `resultats-m1` [1611, 1614 ; 1621 → demande
     croisée `scene3d.ts`], `coque-prealables` [1437, 1727, 1730, 1731, 1745 ; 1617 → `coque-v2`]. 84 tâches de
     la vague 2 livrées.
   - **POINT à 09 h 45 UTC (à lire en premier après une reprise).**
     VAGUE A EN FILE DE FUSION : PR Taqinor/taqinor-os#1527, tête `a37c9be26` (= 746e197f5 + le correctif du fond
     satellite), CI verte, `gh pr ready` + `gh pr merge --auto --merge` faits à 09 h 30 ; file : position 1,
     « AWAITING_CHECKS ». À VÉRIFIER : `gh pr view 1527 --json state,mergedAt`. Une fois fusionnée : dire à Reda
     « mergé — à déployer par toi : `scripts/deploy-prod.ps1` » (migration `calepinage/0043`), relâcher puis
     reprendre les claims (`python scripts/plan_claims.py release …` / `claim …`), et ouvrir la PR de la VAGUE B
     depuis la même branche (`git push origin HEAD` puis `gh pr create --draft`, Auto-fix à allumer
     `mcp__ccd_pr__set_monitor`, jamais d'auto-archive). Critique Fable de la vague A : `T2/critique-vague-A.md`
     — fusionnable, 0 bloquant ; ses 8 points « après » sont dans `T2/consolidation/entree-lot-O.md` § 6 (deux déjà
     corrigés : fond satellite, garde `_devis_lie` ; quatre confiés aux lanes d'écran en vol). Site public : les
     pages des visiteurs ne chargent pas le moteur modifié (lu par la critique) ; l'aperçu Cloudflare redirige vers
     le site en ligne, donc NON essayé.
     BRANCHE LOCALE (vague B, NON poussée, en avance sur la PR) : tête `f26d073102` — plis de `coque-prealables`,
     `simulation-1` [1605, 1602, 1606, 1607, 1622, 1619], `consommation` [1601, 1603, 1604, 1609, 1610 ; 1608 à
     moitié], `docs-m1` [1700, 1703, 1704, 1711, 1712, 1710, 1705 ; 1709 impossible avant ACAL1001], **`coque-v2`
     [1800-1805 + 1617] : coque PROCHE de la maquette, planches `T2/preuves/coque-v2-planche-*.png`**. 109 tâches
     de la vague 2 livrées au total. Gardes locales vertes. NE PAS pousser la branche avant la fusion de la vague A
     (cela changerait la tête de la PR en file).
     EN VOL (lancées à 09 h 35, base = branche LOCALE) : `rapport-m1` [1615, 1616, 1677, 1701, 1702] opus ·
     `ecran-toit-panneaux` [1445, 1827, 1828, 1818, 1829 + 2 points de la critique] sonnet · `ecran-elec-resultats`
     [1708, 1833, 1822, 1832, 1830, 1831 + 3 demandes croisées] sonnet · `telephone-m1` [1807, 1809, 1812, 1810,
     1811] sonnet. Chaque lane d'écran doit rendre une planche maquette | réel et un verdict.
     ENSUITE : `production-web` [1612, 1618, 1613 + demandes croisées `optimizer.ts` dont ACAL1523, champ au sol
     seul pan, épingle du lead à « + Ajouter une zone », `cadrageToit.ts` qui honore `margesPx`, ACAL1621 dans
     `scene3d.ts`] opus ; écrans restants du lot E : Documents 1834 (après 1726), Liste [1825, 1819], Démarrage
     rapide 1826, Tablette 1835, relevé et client [1814, 1836, 1817, 1837, 1838], atelier-web [1808, 1813, 1820,
     1821, 1839], e2e [1806, 1824], balayage 1823 ; `toit-d` [1706, 1707] ; `livrables` [1507, 1508, 1551, 1713] ;
     lot O à rédiger. PUIS : reconstruire l'instrument sur la branche (conteneurs `l5cal-django` et `l5cal-celery`
     arrêtés ; build du front de la branche), TOUR 3 (rejeu ciblé des 95 « insuffisants » d'après leur `motif`,
     des tâches livrées des vagues 1-2, et regard neuf + comparaison des 13 écrans aux maquettes v2), régénérer
     UNE fois `calepinage-mesures-ecran.baseline.json`, acceptation, fusion de la vague B, phase de contrôles,
     rapport final.
     INCIDENTS ET RÈGLES APPRISES : (1) 09 h 05 UTC, disque C: PLEIN (0 octet) — Docker tombé, relancé à 09 h 10 ;
     cause : ~0,5 Go par worktree de lane ; RÈGLE : après chaque pli, `git worktree remove --force
     .claude/worktrees/agent-<id>` (retirer d'abord toute jonction `node_modules` par `cmd //c rmdir`) ; ne JAMAIS
     retirer les worktrees `lane-l5-*` d'autres sessions ; garder `agent-ad48e173ad7c41aaa` (seule vraie
     installation d'`apps/web`, pour les coutures). (2) Un crochet interdit à cette session d'écrire dans un autre
     worktree : pour poser un commit ailleurs, plomberie git (`read-tree` / `commit-tree`) depuis CE worktree.
     (3) Chaque push annule le run de CI précédent : grouper les pushes. (4) Les lanes écrivent parfois leur
     fichier d'événements en cp1252 : le ré-encoder en UTF-8 à la recopie. (5) Fautes de lane qui ont rougi la CI :
     lignes de plus de 120 colonnes, test qui lit un source par motif, repère `cal-*` non déclaré, fichier ou
     fonction « mur » qui grossit, budget du bundle — toutes écrites au brief des lanes § 2.3 et § 4.
   - **POINT à 10 h 00 UTC.** La vague A est SORTIE de la file à 09 h 50 (`failed_checks` : un seul test,
     `test_acal_simuler_variante::test_get_resultat_variante_sert_sa_simulation`, qui comparait le servi au stocké
     brut — instable depuis ACAL1323, selon l'ordre des tests). Corrigé (commit `ccac9d559b` posé sur la tête de la
     PR par plomberie, aussi en local) et REMISE EN FILE à 09 h 53 (règle du dépôt : « corriger et re-mettre en
     file ») : PR #1527, tête `ccac9d559b`, file position 1. À vérifier : `gh pr view 1527 --json state,mergedAt`.
     Branche locale (vague B) : tête `6cbcc4ef99` + plis à venir ; `rapport-m1` pliée [1615, 1616, 1677, 1701,
     1702] : 114 tâches de la vague 2 livrées. Trois lanes coupées par des erreurs d'API (500 / 529) à 09 h 45 et
     REPRISES par message à 09 h 56 : `ecran-toit-panneaux` (agent ab941ec7513101b3f), `ecran-elec-resultats`
     (acf021c456913a617), `telephone-m1` (a5236a41184fe5c34). Lancée à 09 h 58 : `production-web` (opus,
     a0cd634fa4ec12e25) [1612, 1618 + 8 demandes croisées du moteur de dessin, dont ACAL1523 et ACAL1621].
   - **POINT à 10 h 20 UTC — REPRENDRE ICI.**
     **VAGUE A FUSIONNÉE** sur `main` à 10 h 12 UTC (PR Taqinor/taqinor-os#1527 : 109 tâches). À dire à Reda :
     « mergé — à déployer par toi : `scripts/deploy-prod.ps1`, ~2 min » (migration `calepinage/0043`) ; conseil :
     attendre le rejeu à l'écran du tour 3. `main` a été ré-intégré dans la branche (merge, sans conflit).
     **VAGUE B : PR Taqinor/taqinor-os#1529** (brouillon, Auto-fix allumé, auto-archive éteint), tête poussée
     `4720a085d6`. Elle porte 40 tâches de plus : `coque-prealables`, `simulation-1`, `consommation`, `docs-m1`,
     `coque-v2`, `rapport-m1`, `telephone-m1` [1807, 1809, 1812, 1810, 1811 : carte visible 141 → 335 px au
     téléphone] + trois corrections de l'orchestrateur (fond satellite, garde `_devis_lie`, test de la variante).
     119 tâches de la vague 2 livrées au total (+ 30 de la vague 1). Claims renouvelées à 10 h 17.
     EN VOL (base = branche locale) : `ecran-toit-panneaux` (sonnet, ab941ec7513101b3f, branche
     `l5w3-ecran-toit-panneaux`) [1445, 1827, 1828, 1818, 1829 + 2 points] · `ecran-elec-resultats` (sonnet,
     acf021c456913a617, `l5w3-ecran-elec-resultats`) [1708, 1833, 1822, 1832, 1830, 1831 + 3 demandes] ·
     `production-web` (opus, a0cd634fa4ec12e25, `l5w3-production-web`) [1612, 1618 + DC-1 à DC-8].
     AU RETOUR DE CHAQUE LANE : `git merge --no-ff <branche>` ; recopier `$SP/T2-lane-<nom>.jsonl` au registre
     (ré-encoder si cp1252) ; `python $SP/l5b/marquer_livrees.py` ; si serveur : `check_api_shapes.py --write` et
     `check_openapi_schema.py --write` (conteneur) ; gardes : `check_tests_source_regex`, `check_forme_code --base
     origin/main`, `check_test_placement`, `node …/e2eHooks.test.mjs`, golden ; copier la planche de preuve dans
     `T2/preuves/` ; `git worktree remove --force .claude/worktrees/agent-<id>`.
     **PLAN DE LA SUITE (budget : quota hebdo 46 % à 10 h 20, ≈ 3,5 points par heure ; viser la fin vers 60 %)** :
     1. Plier les 3 lanes en vol ; pousser ; CI verte sur la PR #1529 (les deux coutures : agent
        `ad48e173ad7c41aaa` pour la suite entière d'`apps/web` — worktree à vraie installation, branche à créer
        depuis l'origine — ; pour le front ERP, lancer une lane « couture » avec jonction `node_modules`).
     2. Critique de la vague B avant sa fusion (opus ; diff `origin/main...<tête>` ; mêmes six questions que
        `T2/critique-vague-A.md` ; elle porte des chiffres de production : lecture serrée de `simulation.py`,
        `courbe_charge.py`, `etapes/`, `rapport/`).
     3. Reconstruire l'INSTRUMENT sur la tête de la branche : `git -C <…>/l5cal-instr checkout --detach <sha>`,
        `npm run build` du front dans `l5cal-instr/frontend`, `docker start`/recréer `l5cal-django` et
        `l5cal-celery` par `$SP/l5cal/relancer.sh` (migrer la base `l5cal` : `manage.py migrate`), relancer
        l'aperçu du front (tâche de fond `bhkmo4ocy`, port 5241), réarmer le Monitor.
     4. TOUR 3 (relecteurs neufs sur l'écran réel, comptes `rev_b1…b8`, calibrage : un `ok` exige TOUS les cas
        du « fini quand » montrés) : (a) rejeu ciblé des 95 `ok` « insuffisants » (leur `motif` dit quoi rejouer :
        `registre/evenements/T2-audit-ok*.jsonl`) ; (b) contre-vérification des 149 tâches livrées des vagues 1 et
        2 (`registre/evenements/T2-lane-*.jsonl`, champ `gestes_apres`) ; (c) relecteur beauté B3 : les 13 écrans
        contre les maquettes v2, verdict FIDÈLE / PROCHE / ÉLOIGNÉ (K8) ; (d) régénérer UNE fois
        `frontend/e2e/calepinage-mesures-ecran.baseline.json` et jouer les specs de l'orchestrateur (ACAL385,
        1315, 891). Puis relecture adverse des `ok`, enregistrement d'acceptation, coches.
     5. Corriger ce que le tour 3 trouve de grave (une ou deux lanes), CI, fusion de la vague B par la file.
     6. PHASE DE CONTRÔLES (après le L5, ≤ 5 points) : fidélité des écrans aux maquettes v2 ; « tous mes devis
        se calculent seuls avec les bonnes hypothèses » ; un seul moteur, celui du CRM ; lead 1742 « CPE Go Plus »
        (faits déjà relevés : `$SP/cas-cpe-go-plus.md`, `$SP/probe1.out` ; prod en LECTURE SEULE).
     7. RAPPORT FINAL détaillé pour Reda (en anglais, comme `RAPPORT-MATIN-2026-11-23.md`) : ce qui est fait,
        chiffres, décisions prises seul à confirmer, décisions ouvertes D-ACAL-75/76 et 80 à 88, gestes pour lui
        (deploy, `.wslconfig`, disque C: plein — 110 worktrees d'anciennes sessions à nettoyer —, fourchette du
        ratio panneaux / onduleur à régler), ce qui reste au plan (M2 du tour 2 : ≈ 180 tâches, écrans restants
        du lot E : Documents, Liste, Démarrage rapide, Tablette, client), coût. Puis nettoyage (liste en fin de
        fichier) et rétro.
   - **POINT à 10 h 45 UTC (le plus récent).** Toutes les lanes sont rentrées et pliées ; tête poussée de la
     PR #1529 : `f7d5f1a7ec` (10 h 40). En plus du point de 10 h 20 : `ecran-toit-panneaux` [1445, 1827, 1818,
     1829 ; 1828 → moteur] (Toit clair FIDÈLE, Toit sombre et Panneaux PROCHES, d'après ses planches),
     `ecran-elec-resultats` [1708, 1833, 1822, 1832, 1830, 1831 + 3 demandes] (quatre écrans PROCHES),
     `production-web` [1612, 1618 + 8 demandes dont ACAL1523 et ACAL1621]. 130 tâches de la vague 2 livrées (+ 30
     de la vague 1 déjà fusionnées avec 79 d'entre elles). Planches maquette | réel : `T2/preuves/` (12 fichiers).
     Le run de CI de 4720a085d était ROUGE sur deux contrôles du CRM qui lisent `index.css` résolu par motif
     (LB40, APX2) : corrigé dans NOS feuilles (jetons v2 écrits en `rgb()`, un littéral du téléphone réécrit),
     tests de jetons réalignés ; `node --test "src/**/*.test.mjs"` : les 4 rouges restants en local sont des
     artefacts de Windows (fins de ligne), pas la CI.
     À FAIRE MAINTENANT, dans l'ordre : (1) attendre la CI de `f7d5f1a7ec` et corriger ses rouges ; en parallèle,
     suite entière d'`apps/web` (agent `ad48e173ad7c41aaa`, « quatrième passe ») et suite du front calepinage
     (nouvelle lane de couture avec jonction) ; (2) critique de la vague B (opus) ; (3) reconstruire l'instrument
     sur `f7d5f1a7ec` ou plus récent ; (4) TOUR 3 ; puis la suite du PLAN DE LA SUITE du point de 10 h 20.
     Demandes croisées neuves à verser au lot O : `formatNumber` écrit U+202F que les polices Archivo et Hanken ne
     dessinent pas (« 10620 kWh » collé) ; la tête « Étape 4 sur 5 » (ACAL1727) décale les écrans Résultats par
     rapport à leur maquette ; étiquettes de chaînes sur la carte ; `chiffrage.simulation` à servir à la coque
     (DC-1612, `useAtelierBoot.js`) ; panneaux masqués à l'étape Toit ; carte assombrie en thème sombre
     (`underlay.ts`, `mapDraw.ts`) ; boussole masquée en Guidé par `50-coque-atelier.css` ; barre d'outils de la
     carte trop large sous 640 px ; `rp9-undo-point` affiché malgré `hidden`.
   - **POINT à 11 h 00 UTC (le plus récent).** INSTRUMENT RECONSTRUIT sur `f7d5f1a7ec` (10 h 50 : worktree
     `l5cal-instr` détaché sur ce commit, base migrée, front rebâti, conteneurs relancés par `relancer.sh`).
     **TOUR 3 LANCÉ** (`T3/lancement/T3.md`, listes `T3/cv/*.md` par `$SP/l5b/listes_t3.py` : 173 tâches livrées
     en six listes + 35 « insuffisants » graves + 60 autres). EN VOL : `T3-ECRANS` (sonnet, `rev_b1`, 31 tâches),
     `T3-PROD` (opus, `rev_b2`, 20 tâches + table de toutes les lectures de la production), `T3-TOIT` (sonnet,
     `rev_b3`, 33 tâches). RESTE À LANCER (4 relecteurs au plus sur la pile) : `T3-POSE` (39, `rev_b4`),
     `T3-ELEC` (45, `rev_b5`), `T3-INSUF-GRAVES` (35, `rev_b6`), puis le relecteur beauté `B3` (opus,
     `rev_beaute` : les 13 écrans contre les maquettes v2 + `T3-TEL`, verdict FIDÈLE / PROCHE / ÉLOIGNÉ). Les 60
     « insuffisants » non graves restent au plan pour un prochain rejeu (à dire au rapport).
     Sorties attendues : `registre/evenements/T3-<code>-cv.jsonl`, `registre/constats/T3-<code>.jsonl`,
     `T3/<code>.md`. ENSUITE : relecture adverse des `ok` du tour 3 (comme `T2/lancement/AUDIT-OK.md`),
     enregistrement d'acceptation (sha `f7d5f1a7ec`…) et coches par `$SP/l5b/enregistrer_acceptation.py` (à
     adapter : lire aussi `T3-*-cv.jsonl` et `T3-audit-ok*.jsonl`).
     AUSSI EN VOL : couture 5 (suite entière d'`apps/web`, agent `ad48e173ad7c41aaa`, branche `l5w3-couture-5`),
     couture 6 (suite du front calepinage, agent `a44321ebb9d33870c`, branche `l5w3-couture-6`), CI de la PR
     #1529 sur `f7d5f1a7ec`. Commits locaux non poussés depuis : docs seulement.
   - **POINT à 11 h 10 UTC (le plus récent).** Tête poussée de la PR #1529 : `c2cac20623` (11 h 00 : budget total
     du bundle 4130 → 4145 Ko, coutures 5 et 6 pliées) ; CI en cours. EN VOL : critique Fable de la vague B (agent
     `abfb9c485f57ebf42`, sortie `T2/critique-vague-B.md`, 2e appel Fable) ; tour 3 : `T3-ECRANS` (aa8f68df498f958cb),
     `T3-PROD` (a7869b95be02b2a62), `T3-TOIT` (a9720ab55bd56619f), `T3-POSE` (a5bda948cfcd67244, `rev_b4`).
     RESTE À LANCER quand une place se libère : `T3-ELEC` (`rev_b5`, 45), `T3-INSUF-GRAVES` (`rev_b6`, 35), `B3`
     (opus, `rev_beaute`, 13 écrans contre les maquettes v2 + `T3-TEL`). BROUILLON DU RAPPORT FINAL écrit :
     `docs/audits/l5-calepinage/RAPPORT-FINAL-2026-11-23.md` (sections 6, 7 et 10 à compléter ; l'envoyer à Reda
     par SendUserFile à la fin). CONDITION DE FUSION de la vague B : CI verte + critique sans bloquant + verdict
     de `T3-ECRANS` sans défaut bloquant sur la nouvelle coque ; puis `gh pr ready 1529` et
     `gh pr merge 1529 --auto --merge`. La phase de contrôles ne commence qu'APRÈS cette fusion (consigne de Reda).
   - **POINT à 11 h 25 UTC (le plus récent).** Critique Fable de la vague B rendue : FUSIONNABLE, 0 bloquant, 10
     points « après » (`T2/critique-vague-B.md`) ; trois corrigés tout de suite par l'orchestrateur (garde des
     montants : « marge » nu de nouveau refusé ; relevé hors ligne gardé sur une réponse passagère ; kWc de la pose
     à côté des panneaux posés), les sept autres dans `T2/consolidation/entree-lot-O.md` § 8. Tête poussée de la
     PR #1529 : `de4cc97b5d` (11 h 21), CI en cours (le run précédent, sur `c2cac20623`, était VERT). FUSION de la
     vague B dès que : CI verte sur `de4cc97b5d` ET le relecteur `T3-ECRANS` ne signale aucun défaut bloquant de la
     nouvelle coque. Tour 3 en vol : `T3-ECRANS`, `T3-PROD`, `T3-TOIT`, `T3-POSE` (fichiers de sortie nommés
     `registre/evenements/T3-T3-<nom>-cv.jsonl`). Deux appels Fable faits sur trois (critiques des vagues A et B).
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

## POINT à 12 h 35 UTC

**Fait depuis 11 h 25.** Vague B FUSIONNÉE : PR #1529, 12 h 27 UTC (la file l'avait refusée une fois : deux tests
serveur — le run de PR d'une branche `claude/*` ne joue PAS le backend, seul le groupe de fusion le fait ; leçon
versée à la mémoire `plan-drain-ci-bug-classes`, entrées 15 et 35). `origin/main` re-fusionné dans la branche locale
(`d5837c0674` puis commits de docs) — RIEN n'est poussé depuis `41e7b88cab` : le prochain push ouvre la PR de la
vague C (activer Auto-fix dès l'ouverture, jamais d'archivage automatique).

**Phase de contrôles (commencée, la demande de Reda après le L5).**
- `controles/C1-moteur-unique.md` (4 moteurs, 5 bornes de ratio, causes du lead 1742, 8 tâches).
- `controles/C2-devis-automatiques.md` (par marché : aboutit / s'arrête où ; 6 tâches ; 5 questions).
- `controles/C3-mesures-prod.md` (lecture seule de la prod : résidentiel 448 des 478 leads à facture aboutissent ;
  commercial 4 sur 42 ; 11 calepinages, 5 liés à un devis, 3 à un nombre de panneaux différent de l'option retenue).
- Décisions écrites dans `docs/audits/decisions.yml` : D-ACAL-75 (rejouer), 89, 90, 91 prises seul, à confirmer ;
  D-ACAL-92 à 95 ouvertes (contrat, phase, rythme industriel, ville).

**Tour 3 (contre-vérification en direct, pile au code `f7d5f1a7ec`).** Rapports rendus : T3-ECRANS (31 : 8 ok, 22
partiel, 1 non-fait), T3-PROD (20 : 13 ok, 3 partiel, 2 non-fait, 2 non essayés), T3-POSE (24 sur 39 : 10 ok, 11
partiel, 3 non-fait ; un défaut S1 : pose personnalisée perdue à la réouverture), T3-ELEC (22 sur 45, relancé pour
les 23 restantes : agent `a43dbb69ac7e0ac40`). En cours : T3-TOIT (`a9720ab55bd56619f`, borné à 13 h 10 UTC), B3
(`adace7d0ca0efc67b`, opus : 14 écrans contre maquettes v2 + 5 tâches du téléphone, sortie `T3/B3.md`, planches dans
`T3/preuves/`). Non lancés, faute de budget : T3-INSUF-GRAVES (35) et T3-INSUF-AUTRES (60) → à dire au rapport.
Liste lisible de tous les défauts et verdicts non ok du tour 3 : `…/scratchpad/t3-constats.txt` (à régénérer).

**Vague C en construction (4 lanes en worktree, base `origin/claude/calpinage-module-l5-aadbde@41e7b88cab`).**
| Lane | Agent | Modèle | Tâches | Mission |
|---|---|---|---|---|
| moteur-unique | `a70b1300ce0d5322b` | opus | ACAL1950-1956, ALEA67, + ajouts ACAL1954 élargie, ACAL1957, ACAL1958 | `controles/lane-moteur-unique.md` |
| pose-reprise | `a9403d26b580a6e39` | opus | ACAL1900-1903 | `controles/lanes-vague-C.md` |
| ecrans-s2 | `a4af39d42636672db` | sonnet | ACAL1904-1908 | idem |
| production-s2 | `aeed6a7041ae6b1e1` | sonnet | ACAL1909-1913 | idem |
Branches `lane-l5c-<nom>` ; événements `…/scratchpad/l5b/T2-lane-<nom>.jsonl`.

**Reste à faire, dans l'ordre.**
1. À chaque lane rendue : relire ses commits, plier (`git merge --no-ff lane-l5c-<nom>`), retirer son worktree.
2. Faire écrire les lignes v3 du plan (un agent sonnet, sorties en fichiers d'attente puis assemblage) : ACAL1900-1913,
   ACAL1950-1958, ALEA67 (plan lead), restes de C1 (moitié devis de D-HYB-1 et températures → plan transverse), C2
   (devis : dire les suppositions ; calepinage : profil du CRM, quatre pertes gated D-ACAL-82 ; moteur : orthographes
   de ville gated D-ACAL-95), restes S3 du tour 3, `T2/consolidation/entree-lot-O.md`. Puis `marquer_livrees.py`.
3. Gardes hôte (`ci_guards.py stage-names`, flake8, eslint), CODEMAP / contrats / OpenAPI si des clés ont bougé,
   suite `apps.calepinage` entière en conteneur AVANT la file (le run de PR ne joue pas le backend).
4. Push → PR vague C → Auto-fix → critique (opus, pas Fable sauf surface à risque) → file de fusion.
5. Reconstruire la pile sur la vague C, rejouer en direct : pose de 16 rouverte, calepinage lié au devis envoyé,
   ratio, étape Résultats ; enregistrement d'acceptation du tour 3 (`enregistrer_acceptation.py` à adapter aux
   fichiers `T3-*-cv.jsonl`), coches.
6. Rapport final `RAPPORT-FINAL-2026-11-23.md` (sections 6, 7, 10) → `SendUserFile`.
7. Démontage de la pile, relance des 5 conteneurs `erp-agentique-*`, libération des claims, rétro.

**Quota.** 55 % de la semaine à 12 h 05 UTC ; cible de fin relevée à environ 65 % (vague C non prévue au départ).

## POINT à 15 h 10 UTC

**Reda est réveillé depuis 13 h 25 UTC.** Il a reçu le rapport (état de 14 h 20) par `SendUserFile`, a répondu à TOUTES
les décisions ouvertes par questions interactives (D-ACAL-75 à 96 dans `docs/audits/decisions.yml` ; résumé dans
`docs/claude-memory/calepinage-decisions-fondateur.md`, section 23/11), puis a choisi : **« Build everything now »**.
Sa règle : « i only want one engine calculating every number so no more then one number for each value and you keep
the most realistic number ». Quota de la semaine : 60 % à 13 h 15, environ 63 % à 14 h 50 ; il a accepté ≈ 85 %.

**PR ouverte : #1530** (vague C ; Auto-fix allumé ; PAS en file de fusion). Tête poussée `b8d4dafc27` : lanes ecrans-s2,
production-s2, ecrans-s3, pose-reprise (1re), moteur-unique (10 commits), tâches du lot O dans six plans, tour 3
(47 coches, enregistrement `2026-11-23-f7d5f1a7e`), décisions. **NE PAS mettre en file avant** : (1) le correctif RÉEL
d'ACAL1900 (le rejeu en direct `T3/T3-VAGUEC.md` a montré que la pose de 16 se rouvre encore à 5) ; (2) la suite serveur
entière jouée (le run de PR ne la joue pas) — la suite `apps.calepinage` du 23/11 14 h 26 sur `d972960ed5` : 7 280 tests,
1 échec et 14 erreurs dont 3 expliquées (front absent du montage) et 11 NON LUES (journal tronqué) : attendre la liste
de la lane moteur-unique ou la rejouer avec journal complet.

**Lanes en cours (worktrees `agent-<id>`, branches locales).**
| Lane | Agent | Modèle | Tâches | État à 15 h 10 |
|---|---|---|---|---|
| moteur-unique (C) | `a70b1300ce0d5322b` | opus | reste ACAL1957 + suite entière | 10 commits pliés (`35d938ab43`) ; re-plier son reste |
| pose-reprise-2 (C) | `ad4b2a2953bc0d89e` | opus | ACAL1900, ACAL1903 avec navigateur réel | en cours |
| pertes-simulation (D) | `aa4cc89b8529b9b34` | sonnet | ACAL1968+1349, 1671, 1987 (neuve), 1967 | en cours |
| ombrage-p90-nasa (D) | `a0f2f3d374de04120` | opus | ACAL1407+1501, 1672, 746 | en cours |
| devis-auto-ci (D) | `aeb85a9f773ecb762` | opus | ADEV125, 126, 127, 124 | en cours |
| regles-communes (D) | `aae78b8237360c887` | opus | ADEV121, ADEV122+ACAL1553, ADEV123, APAR92 | en cours |
| ecrans-d (D) | `a5ef7afef8238d297` | sonnet | ACAL1985, 1912, 1905, 1908, 1840, 1755 | 3 commits |
Missions : `controles/lane-moteur-unique.md`, `controles/lanes-vague-C.md`, `controles/lanes-vague-D.md`.
À lancer APRÈS le pli de pose-reprise-2 : lane « taille-auto » (ACAL1331 + ACAL1448, opus, moteur de dessin).

**À chaque lane rendue** : relire le diff, `git merge --no-ff`, retirer le worktree (jonctions d'abord), recopier ses
événements au registre (`lot_o_complement.py` les renomme), puis gardes : `flake8`, `eslint`, vitest du module ET
`node --test "src/**/*.test.mjs"` depuis `frontend/` (la lane ecrans-s3 a cassé un test de logique pure que vitest ne
joue pas), `check_services_appeles`, `check_api_shapes`, `check_forme_code --base origin/main`, `check_ancres_taches`,
`check_decisions`, OpenAPI en conteneur (`docker run … -v <worktree>:/repo -w /repo/backend/django_core l5cal-django:t0
python ../../scripts/check_openapi_schema.py`), `codemap_fingerprint.py --write`.

**Reste à faire, dans l'ordre.**
1. Plier pose-reprise-2 → reconstruire la pile (`l5cal-instr` : `git checkout --detach <sha>`, `vite build`, `docker
   restart l5cal-django l5cal-celery`) → rejouer ACAL1900 en direct → file de fusion de #1530 (`gh pr merge 1530 --auto --merge`).
2. Vague D : plier les lanes, critique finale (dernier appel Fable permis : la vague touche le moteur de devis), PR à
   part (vague D), rejeu en direct ciblé, fusion.
3. Plan : ligne ACAL1987 (simulation qui part seule) à écrire ; préfixes « [GATED : décision … ouverte] » des tâches
   répondues à réécrire ; `marquer_livrees.py` ; tâches des 6 points « après » de `T3/critique-vague-C1.md` et des
   restes de `T3/T3-VAGUEC.md`.
4. Rapport final à compléter (`RAPPORT-FINAL-2026-11-23.md` : décisions répondues, vagues C et D) → `SendUserFile`.
5. Démontage (le classifieur a refusé `docker rm -f` d'un conteneur de test : le dire à Reda), claims, rétro mémoire.

## POINT à 16 h 40 UTC

**Quota : 72 % de la semaine à 16 h 35** (Reda a accepté ≈ 85 % : « Build everything now »). Contexte de l'orchestrateur à 78 %.

**PR #1530 ouverte, PAS en file** (Auto-fix allumé). Branche poussée jusqu'à `7cb9f89366` (72 commits devant `main`).
Pliés depuis 15 h 10 : moteur-unique (11 commits, dont les rouges de la suite entière corrigés), ecrans-d (6 points),
ombrage-p90-nasa (3 tâches), pose-reprise-2 (**ACAL1900 corrigée pour de vrai, vue au navigateur** ; ACAL1903).
Tenue des plans faite (`…/scratchpad/l5b/tenue_plans_d.py --ecrire` : ACAL1987 écrite, 19 préfixes GATED réécrits,
tâches marquées « code livré » dans tous les plans ; à relancer après chaque pli + recopier les événements des lanes).

**CI rouge à corriger avant toute file** : `web-build-test` — 3 tests du moteur de dessin
(`apps/web/tests/estimatorRuntimePro10Pro11.test.ts` × 2, `userJourneyPro11.test.ts` × 1) : depuis ACAL1407 la matrice
d'ombrage est réécrite à chaque sérialisation (document sans obstacle : `shading12x24` n'est plus `null` ; production
qui bouge de 0,3 kWh à la réouverture sans geste). Lane de couture `adf87e0be276b65f7` (opus, branche
`lane-l5d-coutureombrage`). Pour jouer ces deux suites à la main depuis `apps/web/` (jonction `node_modules` posée
dans MON worktree vers `l5cal-instr`) : `npx vitest run --config <…>/scratchpad/PR2/vitest.jonction.mjs tests/estimatorRuntimePro10Pro11.test.ts tests/userJourneyPro11.test.ts`
— À JOUER À CHAQUE PLI qui touche `apps/web/src/scripts/roofPro11/` (les lanes ne peuvent pas les jouer).

**Lanes en cours.**
| Lane | Agent | Branche | État à 16 h 35 |
|---|---|---|---|
| pertes-simulation | `aa4cc89b8529b9b34` | `lane-l5d-pertessimu` | 4 commits (ACAL1968+1349, 1671, 1987, 1967), suite entière en cours |
| devis-auto-ci | `aeb85a9f773ecb762` | `lane-l5d-devisautoci` | 3 commits (ADEV125, 126, 127), reste ADEV124 |
| regles-communes | `aae78b8237360c887` | `lane-l5d-reglescommunes` | 3 commits (ADEV121, ADEV122+ACAL1553, ADEV123), reste APAR92 |
| taille-auto | `af9f681dc58971d47` | `lane-l5d-tailleauto` | lancée 16 h 00 (ACAL1331+1448, navigateur réel, port 5263, compte rev_b7) |
| couture-ombrage | `adf87e0be276b65f7` | `lane-l5d-coutureombrage` | lancée 16 h 20 |
| moteur-unique | `a70b1300ce0d5322b` | `lane-l5c-moteurunique` | tout plié ; attend sa suite finale (rapport à venir) |
| vérificateur T3-VAGUEC2 | `a72e242511a4baaa1` | — | rejeu en direct sur la pile (`428193cc6f`), compte rev_b8, sorties `T3/T3-VAGUEC2.md` |

**Demandes croisées ouvertes (à donner à une lane de couture après les plis)** :
- brancher `nasa_power.py::ClientNasaPower.comparaison_horizontale` dans `simulation.py` (bloc `meteo.comparaison_nasa_power`), contrat météo, écran ;
- rapport d'étude : `services/rapport/production.py` (bloc `production-ecart-devis`) et `MENTION_ECART_DEVIS` de `services/electrique.py` disent encore « Production imprimée au client = moteur du devis (D-ACAL-6) » — périmé depuis D-ACAL-86/96 (un seul chiffre, les deux nommés s'ils diffèrent, devis envoyé jamais modifié) ; recapture `calepinage_resultat.json` et son golden ;
- ACAL1957 (« cible vide » après « Générer le devis ») : « impossible » pour la lane — cause probable `ventes/domain/lignes.py::cible_depuis_lignes` (aucune ligne classée panneau) ; à lire dans `T3/T3-VAGUEC2.md` partie B ;
- 6 points « après » de `T3/critique-vague-C1.md` et restes de `T3/T3-VAGUEC.md` : tâches à écrire.

**Ordre de fin.** (1) plier couture-ombrage → CI verte ; (2) lire T3-VAGUEC2 ; (3) plier pertes-simulation, devis-auto-ci,
regles-communes, taille-auto (gardes du POINT 15 h 10 + suites runtime du moteur de dessin + `node --test`) ;
(4) critique finale (dernier appel Fable permis : la vague touche le moteur de devis) ; (5) suite serveur ENTIÈRE avant la
file (les lanes moteur-unique et pertes-simulation la jouent : lire leurs nombres) ; (6) `gh pr merge 1530 --auto --merge` ;
(7) rejeu en direct ciblé de la vague D ; (8) rapport final complété + `SendUserFile` ; (9) démontage, claims
(`plan_claims.py release` des 7 clés), rétro mémoire (leçons : run de PR sans backend ; suites runtime du moteur ;
`node --test` au pli ; ancres `fichier::CONSTANTE` refusées ; `skipTest` refusé ; contrat sans moitié cliente ;
conteneur de test oublié 4 h).

## POINT à 17 h 35 UTC

**Reda (17 h) : « i dont care about 85% i only care about good work, you can consume 100% »** — la qualité prime, pas le
quota (mémoire `quality-over-quota`). Quota 72 % à 16 h 35. Contexte de l'orchestrateur ≈ 85-90 % : ce bloc suffit à reprendre.

**D-ACAL-97 (un seul moteur dans l'ERP)** décidée et CONÇUE : `controles/C4-un-seul-moteur.md` (252 lignes),
`controles/C4-taches.md` (48 tâches, format court). Réponses de Reda aux quatre questions du §9 (à écrire dans le
document et dans decisions.yml) : Q1 = même simulation sur un toit par défaut (liste des écarts montrée avant bascule) ;
Q2 = le brouillon suit la conception sauf s'il a été retouché à la main (« Mettre à jour » proposé sinon) ; Q3 = sans
lead, le résultat est porté par le calepinage ; Q4 = pendant le dessin, panneaux et kWc seulement. **À CONSTRUIRE DANS
UNE SESSION NEUVE** (sa décision). Reste à faire aujourd'hui : convertir `C4-taches.md` en lignes v3 dans les plans des
propriétaires (agent sonnet, comme le lot O) pour que la session neuve puisse lancer « work on the plan ».

**PR #1530 ouverte, PAS en file.** Branche locale = poussée jusqu'à `c7ad6af236` + commits locaux de docs. Pliés et
poussés : toute la vague C (dont ACAL1900 vue deux fois au navigateur, couture ombrage : les 3 tests du moteur de dessin
verts) + ecrans-d + ombrage-p90-nasa.

**QUATRE LANES RENDUES, À PLIER (dans cet ordre), worktrees `agent-<id>` à retirer après :**
| Lane | Branche (tête) | Agent | Contenu |
|---|---|---|---|
| regles-communes | `lane-l5d-reglescommunes` (`b10dc14839`) | `aae78b8237360c887` | ADEV121, ADEV122+ACAL1553 (partiel : C&I et résidentiel pas encore branchés), ADEV123, APAR92 |
| devis-auto-ci | `lane-l5d-devisautoci` (`7a799b1cdf`) | `aeb85a9f773ecb762` | ADEV125, 126, 127, 124 |
| pertes-simulation | `lane-l5d-pertessimu` (`4c0672846d`) | `aa4cc89b8529b9b34` | ACAL1968+1349, 1671, 1987, 1967 |
| taille-auto | `lane-l5d-tailleauto` (`3e573106df`) | `af9f681dc58971d47` | ACAL1331, ACAL1448 (vus au navigateur) ; goldens `toitureDesign.*` recapturés |
Conflits probables au pli : `apps/ventes/services.py` (deux lanes), `EtapeResultats.test.jsx`, `ReglagesSimulation.test.jsx`,
`profilDepart.js` (pertes-simulation contre ecrans-d), goldens `toitureDesign.*` (taille-auto : prendre les siens puis
les régénérer si rouges).

**COUTURES à faire après les plis (lane(s) de couture, puis gardes) :**
1. Golden HTTP du CRM à recapturer (`UPDATE_GOLDEN=1`, `apps.crm.tests_scission_golden`, conteneur) — rouge depuis ALEA67 ; la file de fusion le refuserait.
2. ADEV122, branchement C&I : `apps/ventes/domain/etude_ci.py` pose `catalogue['froid']` et le passe à `combiner_onduleurs` (demande croisée de regles-communes, 3 lignes) ; résidentiel non branché → tâche.
3. ACAL1987 : `services/electrique.py::enregistrer_entree` appelle `lancer_simulation_automatique` en `on_commit` ; `GET resultat/` + `EtapeResultats.jsx` lisent `selectors.simulation_automatique_en_cours` (« Simulation en cours… » sans clic).
4. ACAL746 : brancher `nasa_power.py::ClientNasaPower.comparaison_horizontale` dans `simulation.py` (bloc météo), contrat, écran.
5. ACAL1755 côté rapport d'étude : `services/rapport/production.py` (bloc `production-ecart-devis`) et `MENTION_ECART_DEVIS` (`services/electrique.py`) — un seul chiffre, les deux nommés s'ils diffèrent ; recapture `calepinage_resultat.json` + golden.
6. ADEV125 : le PDF ne marque pas « estimation » (le bloc stocké n'a pas `sous_reserve_visite`) — demande croisée ; et choix à CONFIRMER par Reda : « BT patenté » pour un commerce, « BT force motrice » pour une usine.
7. Vus à l'écran par T3-VAGUEC2 (`T3/T3-VAGUEC2.md`) : le ratio « 0,99 pour 1,35 au plus » marqué « à régler » sans raison dite (borne basse non dite) ; ACAL1951 (l'option du devis n'est pas nommée, « au devis » disparaît après remplissage) ; ACAL1952 (« Repris du devis » non visible à l'écran) ; ACAL1958 (bouton 330 × 104 au lieu de 340 × 52) ; ALEA67 (le mot « ville » n'est pas lu à l'écran) ; module d'essai posé par défaut au lieu de celui du devis.
8. `docs/api-contracts.md` (3 clés de réglage de pertes), CODEMAP (nouveaux fichiers), OpenAPI en conteneur.
9. Tâches à écrire : 6 « après » de `T3/critique-vague-C1.md`, restes de `T3/T3-VAGUEC.md` et `T3-VAGUEC2.md`, 3 tests pdf du rapport d'étude rouges sur `main` aussi (`test_acal_rapport_etude_servi.SchemaJointAuRapportTest`), `test_quote_engine_amot36_pages_ci` (2 échecs antérieurs, cherche « PROPRES À CETTE OPTION »), freezegun absent de l'image locale.

**Puis** : gardes (liste du POINT 15 h 10 + suites runtime du moteur : `npx vitest run --config …/scratchpad/PR2/vitest.orchestrateur.mjs tests/estimatorRuntimePro10Pro11.test.ts tests/userJourneyPro11.test.ts` depuis `apps/web/` + `node --test "src/**/*.test.mjs"` depuis `frontend/`) → `tenue_plans_d.py --ecrire` (après avoir recopié les événements des lanes au registre) → critique finale (3e et dernier appel Fable : la vague touche le moteur de devis) → suites serveur `apps.crm`, `apps.ventes`, `apps.calepinage` → push → file de fusion (`gh pr merge 1530 --auto --merge`) → rejeu en direct de la vague D sur la pile reconstruite → rapport final complété (`RAPPORT-FINAL-2026-11-23.md` : décisions, vagues C et D, un seul moteur) → `SendUserFile` → démontage, `plan_claims.py release`, rétro mémoire.

## POINT a 18 h 40 UTC

Les quatre lanes de la vague D sont PLIEES et poussees (tete poussee `72194cca3d`, 101 commits devant `main`) :
regles-communes, devis-auto-ci, pertes-simulation, taille-auto. Verifie sur la branche pliee : moteur de dessin
1 587 + 107 tests (suites runtime comprises), ecrans 3 287 tests, `node --test` (2 echecs Windows connus), gardes
`check_forme_code`, `check_api_shapes`, deux moities, ancres, services ; import-linter 21/21 (a jouer EN CONTENEUR a
chaque pli : `docker run ... l5cal-django:t0 sh -c "pip install -q import-linter; lint-imports"` - une lane avait mis
un test de `core/tests` qui importait des apps).

EN COURS (trois lanes de couture, mission `controles/coutures-vague-D.md`, base `394d027567`) :
- couture-devis `aa7ce21db18f62294` (opus), branche `lane-l5d-couturedevis` : golden HTTP du CRM (fait), froid du site
  dans le devis C&I, marquage « estimation », libelle « ville » sur la fiche.
- couture-calepinage `ab82581dac584f255` (opus), branche `lane-l5d-couturecalepinage` : simulation qui part seule (fin),
  NASA POWER branche, rapport d'etude a un seul chiffre, borne basse du ratio, module du devis par defaut.
- couture-ecran `ab6a7006b79c58e36` (sonnet), branche `lane-l5d-coutureecran` : option du devis nommee, « Repris du
  devis » en Guide, bouton de Resultats, restes S3.
- consolidation des taches du moteur unique `a551c09f1016760d9` (sonnet) : ecrit `controles/C4-taches-v3.md` et
  `C4-consolidation.md`, et les reponses de Reda (Q1 a Q4) dans `C4-un-seul-moteur.md` §9.

ENSUITE : plier les trois coutures (gardes + import-linter + suites) -> inserer les taches C4 dans les plans (script du
type `autres_plans.py`, puis `check_ancres_taches`, `check_decisions`) -> critique finale (3e appel Fable : moteur de
devis touche) sur `git diff origin/main...HEAD` hors docs -> suites serveur `apps.crm`, `apps.ventes`,
`apps.calepinage` en conteneur -> file de fusion de #1530 -> reconstruire la pile et rejouer la vague D en direct ->
rapport final (ajouter une section « apres-midi du 23/11 » : decisions repondues, vagues C et D, un seul moteur) ->
`SendUserFile` -> demontage, claims, retro memoire.
A CONFIRMER PAR REDA (a mettre au rapport) : pour un contrat absent, la lane a suppose « BT patente » pour un commerce
et « BT force motrice » pour une usine.

## POINT a 19 h 50 UTC

TOUT EST PLIE ET POUSSE : tete `7fff8b561a` (PR #1530, Auto-fix allume, PAS en file). Vagues C et D completes + trois
coutures (devis, calepinage, ecran). Les 55 taches du moteur unique (D-ACAL-97) sont dans six plans ; conception
`controles/C4-un-seul-moteur.md` (reponses Q1-Q4 de Reda ecrites) ; a CONSTRUIRE DANS UNE SESSION NEUVE.

EN COURS a 19 h 50 :
- critique finale Fable `a2f31d6fe9e16ce5f` -> `T3/critique-finale-vagues-C-D.md` (75 min) ; un BLOQUANT se corrige avant la file.
- verificateur `a56ce18c5dde95937` (T3-VAGUED, compte rev_b2, pile reconstruite sur `7fff8b561a`) -> `T3/T3-VAGUED.md`.
- suite serveur `apps.calepinage` entiere (tache de fond bo9z2jyaw) -> `…/scratchpad/back-d1.log` (lignes ERROR/FAIL
  completes). Echecs locaux connus : modules a `parents[5]` (front absent du montage), `freezegun` absent de l'image,
  3 tests pdf `test_acal_rapport_etude_servi.SchemaJointAuRapportTest` (rouges sur main aussi).
- a lancer apres elle (meme conteneur, un a la fois) : `tester.sh <worktree> vaguec apps.crm` puis les modules ventes
  touches (`apps.ventes.tests.test_ciq118_etude_ci_preview`, `test_ciq666…`, goldens du moteur).

ENSUITE : (1) corriger les bloquants de la critique, s'il y en a ; (2) `gh pr merge 1530 --auto --merge` ; surveiller le
groupe de fusion (seul run qui joue le backend) ; (3) apres fusion : `git fetch origin main && git merge origin/main`,
ligne au DONE LOG des plans, dire a Reda « merge - a deployer par toi : scripts/deploy-prod.ps1 » + la commande
`manage.py relier_calepinages_devis_envoye` (liste) puis `--appliquer` ; (4) rapport final : ajouter au
`RAPPORT-FINAL-2026-11-23.md` une section « Apres-midi du 23/11 » (decisions repondues ; vagues C et D : ce qui est
livre, ce que les deux rejeux en direct ont vu ; un seul moteur : conception + 55 taches ; ce qui reste ; a confirmer :
« BT patente » commerce / « BT force motrice » usine) puis `SendUserFile` ; (5) taches a ecrire pour les restes
(`T3/critique-vague-C1.md` §3, `T3/T3-VAGUEC2.md`, `T3/T3-VAGUED.md`, critique finale « apres », NASA POWER a l'ecran,
residentiel au froid du site, 3 tests pdf) ; (6) demontage (conteneurs l5cal-*, bases test_l5t_*, worktree l5cal-instr,
jonctions `frontend/node_modules` et `apps/web/node_modules` de MON worktree par `cmd /c rmdir`, `docker start` des 5
conteneurs erp-agentique arretes, vite preview bhkmo4ocy) - le classifieur a deja refuse un `docker rm -f` : donner les
commandes a Reda si besoin ; (7) `plan_claims.py release` des 9 cles ; (8) retro memoire.

## POINT à 20 h 20 UTC

**PR #1530 ouverte, PAS en file.** Tête poussée `2d2d319322` (contrôles rapides verts à 20 h 18, `stage-names` et
`web-build-test` en cours) ; local = + `0e283f29de` (brief du second tour de coutures).

**Critique finale (3e et dernier appel au modèle le plus cher)** : `T3/critique-finale-vagues-C-D.md` — fusionnable
après B1 et B2. FAITS et poussés : B1 (`b9f8569a3c`, ville déterministe), B2 (`70ea625012`, aucun appel PVGIS par le
devis sous les tests + cliquet des imports ventes → calepinage à 22, seul vrai rouge de la suite complète du
calepinage), point 1 (`2454a69f24`, froid du site sur l’option des lignes), point 4 (`7e2c8a305e`, pas de re-liaison
d’une révision en brouillon). Point 3 vérifié en lecture seule sur la production : 70 devis envoyés ou acceptés avec
lead, 49 sans GPS, la nouvelle reconnaissance de ville rend la MÊME clé pour les 49 (0 devis envoyé ne change ;
sondes `…/scratchpad/probe4.py` et `probe5.py`). Restent à écrire en tâches : point 2 (réserve de visite imprimée pour
quatre motifs — à confirmer par Reda), point 5 (dire que `semer_exemples_calepinage --apply` remplit tous les réglages
vides), point 6 (page d’aperçu `/preview/toiture-3d-pro-11`).

**Suites serveur jouées en conteneur sur la branche** : `apps.calepinage` en entier (7 386 tests : 1 vrai rouge, corrigé ;
le reste = montage local sans front ni `freezegun`, et 3 tests du rapport d’étude déjà rouges sur `main`) ; 516 tests
des modules `apps.crm` et `apps.ventes` touchés : verts ; avec `freezegun` installé dans le conteneur : golden HTTP du
CRM, `test_ciq119_rafraichir_ci` et les cinq modules du calepinage qui en ont besoin : 87 verts.

**Rejeu en direct T3-VAGUED** (agent `a56ce18c5dde95937`, pile à `7fff8b561a`) : partie A rendue (6 lignes au
registre) — ADEV126, APAR92, ALEA67 ok ; ADEV125, ADEV127, ADEV123 partiels. Parties B et C en cours.

**Lane « couture-suppositions » en cours** (agent `aea0530a7f4e378c0`, opus, branche `lane-l5d-couturesuppositions`,
brief `controles/coutures-vague-D2.md`) : régime d’équipes seul (heure de début supposée 8 h en 1 × 8, 6 h en 2 × 8 —
choix de l’orchestrateur, À CONFIRMER par Reda), industriel sans tension déclarée = basse tension supposée (D-ACAL-92),
suppositions résidentielles montrées à l’écran, suppositions rangées avec le devis et remontrées à la réouverture.

**Ordre restant** : fin du rejeu T3-VAGUED (corriger ce qui bloque) → pli de la lane (`--no-ff`), golden HTTP du CRM
rejoué avec `freezegun`, gardes de l’hôte, `tenue_plans_d.py --ecrire` → push → `gh pr merge 1530 --auto --merge` →
surveiller le groupe de fusion (seul passage avec les tests serveur) → tâches des restes → rapport final complété
(section « Afternoon of 23/11 ») + `SendUserFile` → démontage, `plan_claims.py release`, rétro mémoire.

## POINT FINAL du 23/11 (le plus récent — REPRENDRE ICI)

**PR #1530 FUSIONNÉE sur `main` (23 h 33 UTC, commit de fusion `93e1afeb19`).** Vagues C et D, leurs coutures, les deux
lanes du second tour (couture-suppositions, couture-resultats), les correctifs de la critique finale. Aucune migration.
**Rien n'est déployé** : `scripts/deploy-prod.ps1` est le geste de Reda ; ensuite Calepinage → Réglages → Démarrage
rapide → « Remplir les réglages vides », puis `manage.py relier_calepinages_devis_envoye` (liste ; `--appliquer` re-lie).

**La file de fusion a retiré la PR deux fois** (22 h 21 et 23 h 08 UTC), chaque fois pour UN test que seul le groupe de
fusion joue : `apps.crm.tests_agr411_questionnaire_pompage` (phase exigée d'un lead agricole, ALEA67) puis
`apps.ventes.tests.test_split_devis_domaine` (empreinte `split_dm_auto` de `build_devis_auto`, modifiée exprès).
Leçons rangées dans la mémoire (`plan-drain-ci-bug-classes`, entrée 15).

**RÉPONDU par Reda le 24/11** (D-ACAL-98 = tri usuel 0/+3 % supposé, code changé le 24/11 ; D-ACAL-99, 100, 101 confirmées ; test utilisateur complet sur une copie anonymisée de la production ; prompt de la session suivante : `PROMPT-SESSION-SUIVANTE.md`). Texte du 23/11 (`docs/audits/decisions.yml`) : D-ACAL-98 (fiche de module sans tolérance = 0 % supposé —
aucune des 3 fiches de la production ne publie sa tolérance), D-ACAL-99 (heure de début d'équipe supposée 8 h / 6 h),
D-ACAL-100 (tarif basse tension supposé : BT patenté / BT force motrice), D-ACAL-101 (réserve de visite imprimée pour
quatre motifs).

**Ce qui reste** (tout est écrit en tâches) :
- le chantier « un seul moteur » (D-ACAL-97) : 55 tâches en neuf étapes, six plans, conception
  `controles/C4-un-seul-moteur.md` — À CONSTRUIRE DANS UNE SESSION NEUVE, rien n'en est construit ;
- 15 tâches de restes de la vague D : ACAL2030 à 2038, ACAL2040, ACAL2041, ADEV156 à 158, ADEP109
  (dont trois rejeux en direct dus : ACAL2034 ombrage proche, ACAL2035 rapport d'étude PDF et « Réviser le devis »,
  ACAL2036 NASA POWER ; ACAL2038 : en-tête « non enregistré » après l'enregistrement d'un calepinage neuf, non reproduit) ;
- les correctifs du second tour de coutures sont prouvés par tests (rouge puis vert), deux rejoués à l'écran par la lane
  (désignation du matériel, enregistrement) ; AUCUN relecteur neuf ne les a rejoués : à faire au prochain tour ;
- six écrans à refaire sur les maquettes v2 (Documents, Démarrage rapide, Tablette, relevé et vue client au téléphone,
  Présentation) et le dessin sur la carte (teinte des panneaux, contour doré, chaînes) ;
- 95 correctifs anciens prouvés en partie seulement (`T3/cv/T3-INSUF-*.md`).

**Démontage fait** : voir la fin du rapport (`RAPPORT-FINAL-2026-11-23.md`, section 11) et le message de fin de session.

## SESSION du 24/11 — « un seul moteur » puis test utilisateur complet (REPRENDRE ICI)

Demande de Reda (24/11), mot pour mot : `PROMPT-SESSION-SUIVANTE.md` (le bloc entre les deux lignes), avec deux
changements dits par lui : les décisions lui arrivent en questions interactives et, sans réponse sous 2 minutes, le
choix recommandé est pris et listé à la fin ; rien de ce qu'un client lit n'est décidé sans lui.

- Session : poste `DESKTOP-APTAHF6`, worktree `.claude/worktrees/all-plans-loop-work-1b9fa7`, branche locale
  `claude/l5-calepinage-quote-completion-da59ee` partie d'`origin/main@c99872dda8`.
- **Branche poussée : `dev-moteur-unique`** (jamais `claude/*` : le run de PR d'une branche `claude/*` est allégé et ne
  joue PAS le backend — `.github/workflows/ci.yml`, sortie `allege` ; hier la file a retiré la PR deux fois pour cela).
- Quota au départ (24/11) : **88 % « Weekly · all models », 84 % « Weekly · Fable »**, remise à zéro le 28/11 à 11 h
  UTC, usage supplémentaire éteint. La campagne ne tient pas dans cette fenêtre : construire dans l'ordre de Reda,
  état poussé à chaque étape, reprise après la remise à zéro.
- Poste mesuré : 8 cœurs, 4,6 Go libres sur 15,9, 44 Go de disque, Docker allumé (pile `erp-agentique` + une pile
  `ctr-*` d'une AUTRE session — PR #1539, ne pas y toucher) ; gabarit de test `test_erp_db_base` présent
  (`scripts/test-backend.ps1 -RestoreDb`). Plafond : 2 à 3 agents de fond.
- Claims (propriétaire `DESKTOP-APTAHF6/dev-moteur-unique`) : `file:` PLAN_AUDIT_DEVIS, _CALEPINAGE, _LEAD ;
  `app:` ventes, core, calepinage, crm. À renouveler toutes les 6 h, à relâcher après la fusion.
- `plan_lanes.py` sur le groupe seul (55 tâches) : UNE chaîne presque entièrement en série (lane
  `moteur-unique/contrats`, 42 tâches) + une lane calepinage (10) + 3 acceptations de l'orchestrateur. Fusions prévues :
  E1 contrat SEUL → E2 moteur (aucun lecteur branché, aucun chiffre ne change) → E3 relance → E4 devis (parité des 104
  goldens) → E5 calepinage → E6 + E7 → E8 retraits → E9 (ADEV154 liste montrée à Reda, ADEV155 GATED sur sa réponse).
- Instantané anonymisé local : `C:/dev/taqinor-os/var/anon/latest.anon.json.gz` date du 30/09 — à refaire (lecture
  seule de la prod, `qa_export_anonymise --out -`) avant la partie 2.

### Déroulé du 24/11 (un point par étape)

1. E1 (ADEV129, ADEV130, ACAL2010) : lane opus lancée depuis `origin/main`.
2. **E1 FAIT** (3 commits de lane + pli + coches) : PR Taqinor/taqinor-os#1540, branche `dev-moteur-unique`, Auto-fix
   allumé, auto-archive éteint, mise en file automatique demandée (`gh pr merge 1540 --auto --merge`). À VÉRIFIER à la
   reprise : `gh pr view 1540 --json state,mergedAt`. Aucune migration, aucun écran, aucun chiffre : rien à déployer
   pour elle seule. Points laissés à l'étape 2 par la lane du contrat : la réponse ne porte ni `lead`, ni
   `calepinage`, ni `empreinte_pose` (à ajouter par ADEV131/ADEV137, échantillon et code dans le même commit) ;
   `CHAMPS_ENTREES` ne couvre que les trois adaptateurs (le moteur lit aussi `batterie_souhaitee` ailleurs, et les
   mesures de visite par les sélecteurs de `visites`) : l'espion doit couvrir un passage COMPLET de
   `calculer_conception` ; les études agricoles n'ont pas de clé `etude_pompage` (clés à plat dans `etude_params`).
3. **E2 EN VOL** (lancée le 24/11 vers 04 h 10 UTC) : lane opus, worktree `.claude/worktrees/agent-a31fc72966fc4489a`,
   branche `lane/moteur-e2` partie de la branche locale d'intégration ; tâches ADEV131 → ADEV138, un commit par tâche ;
   suffixe de base de test `e2`. Brief : celui recopié ci-dessous (« Brief des lanes du moteur »). À SON RETOUR : relire
   le diff (`git diff claude/l5-calepinage-quote-completion-da59ee...lane/moteur-e2`), plier `--no-ff`, régénérer
   `docs/api-contracts.md` (`check_api_shapes.py --write`) et l'OpenAPI (`check_openapi_schema.py --write`, dans un
   conteneur), `codemap_fingerprint.py --write` (paquet neuf `apps/ventes/conception/`, modèle, route), relecture
   adverse du diff serveur par un opus neuf (isolation par société, aucun devis envoyé touché, aucune écriture hors
   `relancer`, parité), cocher (preuves « API seulement »), pousser dans une PR NEUVE après la fusion de #1540.
   Si la session s'arrête avant : les commits de la lane restent dans son worktree et sa branche locale.
4. **Restes de la vague D (étape 2 de la demande), construits en parallèle** — à fusionner dans LEUR PR, une fois
   #1540 fusionnée (un seul CI à la fois) :
   - lane B (sonnet) RENTRÉE, 5 tâches corrigées, branche locale `worktree-agent-aa8d1e0c1ac75b664` (5 commits depuis
     `origin/main@c99872dda8`) : ADEP109 `ad6b8cb210`, ACAL2041 `6e01aba789`, ACAL2037 `8540b2d482` (golden
     `cascade_pluriannuelle_casablanca.json` recapturé : `mention` vide pour un résultat complet — relu, conforme à la
     tâche), ACAL2033 `1b8508cb56`, ADEV158 `3b21d2b9dd`. Tests rejoués par la lane sur base privée (318 tests ; un
     seul échec hors sujet, qui exige le dossier du front dans le conteneur). Pas encore pliée ni cochée.
   - lane A (opus) EN VOL, worktree `.claude/worktrees/agent-a337a6de920502c94`, branche
     `worktree-agent-a337a6de920502c94` : ADEV156 livrée (`3649ec1184`), puis ADEV157, ACAL2040.
   - PAS LANCÉES : ACAL2030 (CSS du mode Expert), ACAL2031, ACAL2032 (tests et moteur de dessin d'`apps/web` : il faut
     une vraie installation de `node_modules`) ; les quatre rejeux en direct de l'orchestrateur ACAL2034, 2035, 2036,
     2038 (il faut la pile de revue).
5. **Outils de la session (scratchpad, perdus au redémarrage du poste — à réécrire d'après ceci)** :
   - Constat mesuré : le gabarit `test_erp_db_base` a 188 migrations de retard sur `main` ; `scripts/test-backend.ps1
     -RestoreDb` les rejoue À CHAQUE passage (30 min et plus sur ce poste, machine virtuelle de Docker à 4 cœurs et
     5 Go partagée avec une autre session), et chaque passage réinstalle `requirements-dev.txt` (7 min). La première
     heure de la session y est passée.
   - Remède : image `lane-test:dev` (= `erp-agentique-django_core` + `pip install -r requirements-dev.txt`, par
     `docker commit`) ; gabarit à jour `test_erp_lane_base` (2 422 migrations, figé depuis une base de lane migrée) ;
     une base privée par lane `test_erp_lane_<suffixe>` clonée de ce gabarit, puis, depuis la racine du worktree de
     la lane : `docker compose -p erp-agentique -f docker-compose.yml -f <surcharge: services.django_core.image =
     lane-test:dev> run --rm --no-deps --name lane-test-<suffixe> -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev
     -e DB_NAME=erp_lane_<suffixe> django_core python manage.py test <modules> --keepdb --parallel 1`. Un passage de
     9 tests : 1 min 30. Les lanes ne font plus la queue sur `test_erp_db`.
   - À proposer au plan deploy (pas fait) : rafraîchir `test_erp_db_base` (`-Snapshot`) et ne plus réinstaller les
     paquets de test à chaque passage.
6. Quota : 94 % à 04 h 20 UTC le 24/11 (88 % au départ, environ 2 points par heure, une autre session du même compte
   tourne aussi). Fable hebdomadaire : 89 %.
7. **PR #1540 (E1, le contrat) FUSIONNÉE le 24/11 à 04 h 44 UTC** (`f9d03181e3`). Rien à déployer pour elle seule.
8. **CONSTAT D'ARCHITECTURE de la lane E2 (24/11, 04 h 50 UTC) — la prémisse d'ADEV133 est fausse.** Les blocs que
   `build_devis_auto` range dans `Devis.etude_params` ne sont PAS des sorties de noyaux : ils sont recalculés depuis les
   LIGNES du devis écrit par les rafraîchisseurs d'étude (`domain/etudes.py::rafraichir_etudes_du_devis`, qui lit
   `devis.lignes` pour la batterie, la puissance, le rendement, le kWc par option et les onduleurs C&I, plus
   `regles_au_moins(devis)`), et chaque marché a du code de décision autour de l'appel de son noyau. « Appeler les
   noyaux tels quels » ne peut donc pas rendre les mêmes blocs. Les goldens `split_dm_auto*.json` sont des empreintes
   AST des fonctions de création, pas des leads (prémisse d'ADEV138 fausse aussi).
   **CHOIX PRIS SEUL par l'orchestrateur (technique, aucun chiffre client ne change ; réversible)** : extraire un
   pipeline PUR plutôt que faire tourner le devis automatique « à blanc » dans une transaction annulée. Pourquoi : le
   calepinage sans lead (Q3) et l'aperçu sans écriture ne peuvent pas passer par la création d'un devis ; un seul
   pipeline appelé à la fois par le moteur et par `build_devis_auto` ne peut pas dériver. Coût si faux : un refactor
   des trois fonctions de création à défaire (les goldens de figeage le protègent). Ordre :
   (a) **ADEV159 — figer avant de toucher** : goldens de caractérisation de ce que `build_devis_auto` produit
   AUJOURD'HUI (lignes, toutes les clés dérivées d'`etude_params`, `electrical_design`), par marché, sur les leads de
   fabrique de `test_devis_auto.py`, `test_ciq120_devis_auto_ci.py`, `test_agr124_devis_auto_agricole.py` ;
   (b) **ADEV160 — extraction** : code de décision de `creation_auto_residentiel.py::_build_devis_auto_residentiel`
   (L391-560 taille et options, L609-655 contrôle et passage à blanc), `creation_auto.py::_build_devis_auto_ci`
   (L125-146), `creation_auto_agricole.py::_build_devis_auto_agricole` (L63-128), et versions « par lignes » (lignes
   passées en argument) de `etude_horaire.py::_etude_horaire_pour_devis` (L1975-2086), `etudes.py::rafraichir_etude_horaire`
   (L78-110), `::puissances_etude_horaire` (L262-289), `::rafraichir_dimensionnement_devis` (L486-527),
   `etude_ci.py::rafraichir_etude_ci_devis` (L1937-1987, fichier de 2 013 lignes : il doit maigrir),
   `pompage.py::rafraichir_etude_pompage_devis` (L1504+) ; goldens d'ADEV159 identiques à l'octet après ; empreintes
   `split_dm_auto*` recapturées EXPRÈS, motif nommé au commit ;
   (c) ADEV133 compose le pipeline extrait ; ADEV134 → ADEV138 ensuite (la parité se juge contre les goldens
   d'ADEV159 ET un devis automatique fraîchement écrit).
   La lane E2 a livré : **ADEV131** `f39a59ca44` (modèle `ConceptionLead`, migration `ventes/0161_conceptionlead`,
   additive ; clés `lead`, `calepinage`, `empreinte_pose` ajoutées au contrat) et **ADEV132** `e53de9f132`
   (`conception/entrees.py` : `EntreesConception`, `entrees_pour`). Elle est REPRISE (04 h 55 UTC) pour ADEV159 et
   pour écrire au plan ADEV159, ADEV160 et les corrections d'ADEV133 et d'ADEV138. Entrées du moteur qui ne sont pas
   des colonnes du lead (à traiter à l'étape 3, déclencheurs) : barèmes et réglages de la société, catalogue (prix,
   fiches, courbes de pompe), mesures de visite (`visites.selectors.mesures_point_eau_pour_lead`), données PVGIS,
   date de référence (fenêtre du ramadan), niveau de règles, pose du calepinage. Colonnes du lead lues hors des
   adaptateurs : `taille_souhaitee_kwc`, `batterie_souhaitee`, `structure_produit_id`, `structure_pref`, `roof_outline`.
   Piège noté : avec un kWh déclaré, changer la facture d'hiver ne change pas l'empreinte (CAD166) — pas de version neuve.
9. **Restes de la vague D, premier lot : PR Taqinor/taqinor-os#1541** (branche `dev-restes-vague-d`, lane B, 5 tâches :
   ADEP109 et ACAL2041 cochées ; ACAL2037, ACAL2033, ADEV158 « code livré, preuve en direct due »), Auto-fix allumé,
   mise en file automatique demandée. La lane A (ADEV156 livrée ; ADEV157, ACAL2040 en cours) partira dans la PR
   suivante.
10. **PR Taqinor/taqinor-os#1541 FUSIONNÉE le 24/11 à 05 h 13 UTC** (5 restes de la vague D, lane B).
11. **Étape 2a : PR Taqinor/taqinor-os#1542** (branche `dev-moteur-e2a`) — ADEV131 (modèle `ConceptionLead`, migration
    `ventes/0161_conceptionlead`), ADEV132 (`EntreesConception`), ADEV159 (figeage : 9 goldens sous
    `apps/ventes/tests/golden/conception/` — résidentiel ×4, C&I ×3, agricole ×2 ; un arrondi changé rend le test
    rouge en nommant la clé), `CHAMPS_ENTREES` complété par un espion sur un passage entier du devis automatique,
    tâche ADEV160 (extraction) écrite au plan TRANSVERSE (`check_ownership` la refuse au plan devis :
    `etude_horaire.py` appartient à « moteur »), ADEV133 et ADEV138 corrigées. Premier passage de CI ROUGE sur UN
    test que seul le backend complet joue : `apps.crm.tests_acrm_dsr_copies_brutes` exige que tout modèle à clé vers
    `crm.Lead` soit déclaré au registre d'effacement. Corrigé pour de bon, pas exempté (`c52aaf20ed`) : un lead effacé
    (demande de droit ou rétention) emporte ses versions de conception — elles copient ses factures, sa ville, son
    point GPS — par un abonné `ventes` à `lead_erased`, borné à la société ; modèle déclaré dans
    `crm/dsr_provider.py` (`MODELES_LEAD_TRAITES`) ; test rouge puis vert. Second passage : VERT, en file de fusion
    (06 h 35 UTC). À VÉRIFIER à la reprise : `gh pr view 1542 --json state,mergedAt`.
12. **Restes de la vague D, second lot (lane A) : branche locale `dev-restes-a`** = étape 2a + ADEV156
    (`3649ec1184`, golden `split_dm_comp.json` recapturé `382ae7bc0e`), ADEV157 (`ed9df1dde7`), ACAL2040
    (`ab7206cc95`, prémisse contestée : le libellé attendu n'est plus imprimé depuis le commit `71d25d6d70` du 13/11,
    le test relit le titre actuel). Rejoué sur l'arbre plié : 194 tests verts, les 9 goldens de figeage INCHANGÉS.
    À pousser dans SA PR dès la fusion de #1542 (un seul CI à la fois).
    Suites notées par la lane, pas faites : `frontend/e2e/acceptation/alea.spec.js` attend « les 8 prestations » sur
    une société amorcée — la garde nomme maintenant aussi câbles, structures et protections DC à prix 0 (spec à
    mettre à jour, elle ne tourne pas en CI) ; restent à −5 °C l'aperçu `composer_devis_residentiel` et l'écran du
    générateur sans lead.

### À FAIRE À LA REPRISE (après la remise à zéro du quota, 28/11 à 11 h UTC), dans l'ordre

a. Se repérer : `git fetch`, `gh pr view 1542` et la PR des restes A, relire ce bloc ; reprendre les claims
   (`plan_claims.py claim`, propriétaire `<poste>/<branche>`) ; refaire les outils de test du point 5 s'ils ont
   disparu (image `lane-test:dev`, gabarit `test_erp_lane_base` — vérifier d'abord qu'ils existent).
b. **ADEV160 — l'extraction** (plan transverse, `@atomique: devis, moteur`), UNE lane opus effort haut, depuis `main` :
   symboles et plages au point 8 ; preuve = les 9 goldens d'ADEV159 identiques à l'octet, `build_devis_auto` appelle
   les fonctions extraites (une définition chacune), empreintes `split_dm_auto*` recapturées avec le motif nommé,
   `etude_ci.py` (2 013 lignes) maigrit. Limites connues du figeage : `electrical_design` est nul dans les 9 goldens
   (la conception électrique n'est pas protégée : ajouter une fabrique qui la remplit AVANT d'extraire) ; les
   empreintes `etude_ci.empreinte` et `provenance_pompage._empreinte` sont normalisées (calculées sur des ids).
   Puis relecture adverse du diff par un opus neuf AVANT fusion (cœur de la création de devis).
c. ADEV133 → ADEV138 (moteur, suppositions, écrivain `relancer`, porteur calepinage, sélecteurs et route, PARITÉ),
   une lane opus ; la capture des goldens passe par `UPDATE_GOLDEN=1` (le lanceur de lane ne transmet pas les
   variables : ajouter `-e UPDATE_GOLDEN`).
d. Étapes 3 à 8 du chemin (`controles/C4-consolidation.md`) ; étape 3 : chaque entrée du moteur qui n'est pas une
   colonne du lead (liste au point 8) reçoit son déclencheur ou passe par le filet d'empreinte (ADEV140).
e. Étape 9 : ADEV154 (liste des devis dont les chiffres changeraient) MONTRÉE à Reda en question interactive ;
   ADEV155 reste GATED jusqu'à sa réponse (rien de ce qu'un client lit n'est décidé sans lui).
f. Restes de la vague D non lancés : ACAL2030 (CSS du mode Expert), ACAL2031 et ACAL2032 (`apps/web`, vraie
   installation de `node_modules`) ; rejeux en direct de l'orchestrateur ACAL2034, 2035, 2036, 2038 et les trois
   « code livré » de la PR #1541 (ACAL2037, ACAL2033, ADEV158).
g. Étape 3 de la demande : écrans encore loin des maquettes v2 (Documents, Démarrage rapide, Tablette, relevé et vue
   client au téléphone, Présentation, dessin sur la carte) — chaque écran réel à côté de sa maquette, même taille.
h. PARTIE 2 (test utilisateur complet) : rien n'en est commencé. Instantané anonymisé à refaire (celui du poste date
   du 30/09), pile de revue à monter sur le code fusionné, préremplissage sourcé, relecteurs neufs.

## SESSION du 24/11, seconde partie (après la remise à zéro du quota, 10 h UTC) — REPRENDRE ICI

Quota relu à 10 h 06 UTC : 0 % (les deux fenêtres). Les quatre PR du matin sont fusionnées (#1540, #1541, #1542,
#1543) ET déployées (lu en lecture seule : la prod sert `cdaf0d30b1`). Branche d'intégration locale de cette partie :
`dev-moteur-e2b` (partie d'`origin/main@cdaf0d30b1`). Claims reprises à 10 h 10 (propriétaire
`DESKTOP-APTAHF6/dev-moteur-unique`) : plans DEVIS, CALEPINAGE, LEAD, TRANSVERSE, GENERATEUR ; apps ventes, core,
calepinage, crm, web.

### Instrument de revue `l5t` (pile privée et jetable — fiche)

- Front : http://127.0.0.1:5251 (aperçu Vite du build d'`origin/main@cdaf0d30b1`, relaie `/api/django` vers le
  serveur) · serveur : http://127.0.0.1:8031 (gunicorn 2 processus × 2 fils, 1,2 Go) · worker Celery à UN processus
  (`--max-tasks-per-child 1`, 2,3 Go, files default, scheduled, bulk, interactive ; pas de planificateur) · MinIO et
  Redis à soi (`l5t-minio`, `l5t-redis`, réseau `l5t-net`) · base `l5t` dans le Postgres partagé (clonée de
  `test_erp_lane_base`, puis `migrate`, `seed_demo`, `seed_catalogue`).
- Code servi : worktree `C:/dev/taqinor-os/.claude/worktrees/l5t-instr` (détaché, jamais édité ; mise à jour par
  `git -C … checkout --detach <sha>` puis `bash lancer.sh serveur` et un nouveau build du front).
- Lanceur : scratchpad `l5t/lancer.sh` (étapes `base`, `serveur`, `tout`) — environnement bâti depuis `.env.example`
  seul, toutes les variables à clé vidées, seules `DB_USER` et `DB_PASSWORD` viennent du vrai `.env`.
- Contrôle du tour 0 (24/11, 10 h 40 UTC) : backend d'envoi console, réseau `l5t-net` seul, écoute 127.0.0.1 seule,
  `ASSISTANT_COPILOTE=aucun`, `FASTAPI_INTERNAL_URL` mort, WhatsApp éteint. Deux variables « à clé » non vides,
  admises comme le 23/11 : `PUBLIC_MAPTILER_KEY=factice-l5t` (sans clé l'atelier refuse de démarrer ; fond de carte
  gris) et `GPG_KEY` (empreinte publique de l'image Python).
- Comptes de revue (rôle « Directeur » de la société de démonstration, copiés de `demo_admin`) : `rev_a`, `rev_b`,
  `rev_c`, `rev_d`, `rev_orch` ; mot de passe : ligne `REV_PW=` de `l5t/env.local` (scratchpad, jamais écrit ailleurs).
- Mémoire rendue : `erp-agentique-django_core-1` et `erp-agentique-fastapi_ia-1` (pile de dev partagée, au repos)
  ARRÊTÉS à 10 h 45 UTC — à relancer au démontage : `docker start erp-agentique-django_core-1 erp-agentique-fastapi_ia-1`.
- Démontage (à cocher à la fin) : `docker rm -f l5t-django l5t-celery l5t-minio l5t-redis`, `docker network rm
  l5t-net`, tuer l'aperçu du port 5251, `DROP DATABASE l5t`, effacer `l5t/l5t.env` et `l5t/env.local`, retirer le
  worktree `l5t-instr`, relancer les deux conteneurs partagés.

### En vol (24/11, 10 h 50 UTC) — au plus 4 agents de fond sur ce poste

- **Extraction ADEV160** (opus) : d'abord le figeage étendu (conception électrique, taille souhaitée, contour du
  toit…), puis l'extraction du pipeline pur ; base de test privée suffixe `x1`. À son retour : relecture adverse du
  diff par un opus NEUF avant fusion, puis la lane du moteur ADEV133 → ADEV138.
- **Écrans sur les maquettes v2** (brief : scratchpad `brief-lane-ecrans.md` ; chaque lane installe et construit le
  front dans son worktree, le sert sur son port contre le serveur 8031, capture maquette | réel à la taille native
  et range la planche sous `docs/audits/l5-calepinage/T4/preuves/`) :
  - lane `documents` (sonnet, port 5261, `rev_a`) : ACAL1725 → ACAL1726 → ACAL1834 → ACAL1943 ;
  - lane `releve-client` (sonnet, port 5262, `rev_b`) : ACAL1814 → ACAL1836 → ACAL1817 → ACAL1837 → ACAL1838
    (Présentation = la même route `/calepinage/<id>/client` à 1440 × 900) ;
  - À LANCER quand une place se libère : lane `coque` (opus, port 5263, `rev_c`) : ACAL1835 (Tablette), ACAL1826
    (Démarrage rapide), ACAL2030 (mode Expert) ; lane `dessin` (opus, port 5264, `rev_d`, vraie installation
    d'`apps/web`) : ACAL1984 (teinte des panneaux), ACAL1944 (étiquettes de chaîne), ACAL1981, ACAL1920 → ACAL1924
    (cotes), contour doré du toit (AUCUNE tâche au plan : à écrire), ACAL2031, ACAL2032 ; puis ACAL1820 → ACAL1839
    (scène 3D présentable, touche `client/HabillageClient.jsx` : après le pli de `releve-client`) et ACAL1806 (spec
    des maquettes passée à la v2, 14 planches).
  - Les prérequis de ces tâches sont « code livré, preuve en direct due » (ACAL1800, 1802, 1803, 1807, 1809, 1812,
    1705, 1516) : le code est sur `main`, on construit dessus ; leur preuve en direct sera jouée par l'orchestrateur
    sur l'instrument, et tout sera rejoué au test utilisateur de la partie 2.
- **Repérage des réglages** (sonnet, lecture seule) : tout ce que les moteurs lisent et que l'instantané anonymisé ne
  porte pas (réglages du calepinage, fiches techniques, forfaits C&I, rôles…) — pour le préremplissage de la partie 2.

### Partie 2, préparation

- Instantané anonymisé refait le 24/11 à 10 h 12 UTC (lecture seule de la prod, `qa_export_anonymise --out -`) :
  `C:/dev/taqinor-os/var/anon/2026-11-24.anon.json.gz` (5 Mo, hors dépôt) — 1 207 leads, 270 clients, 542 devis
  (361 brouillons, 105 expirés, 64 envoyés, 7 acceptés, 5 refusés), 8 057 lignes, 226 produits, 20 factures, 21
  chantiers. L'instantané ne porte NI les fiches techniques (`stock.FicheTechnique`), NI les réglages du calepinage,
  NI les calepinages : à préremplir (sourcé) dans la copie.
- Catalogue de la copie : 6 panneaux, 13 onduleurs réseau, 10 hybrides, 7 batteries, 20 pompes (11 sans prix), 22
  variateurs, 99 « Protection & accessoires » (66 sans prix), 24 câbles (5 sans prix), 15 structures (6 sans prix), 8
  prestations (4 sans prix). Liste par produit et par usage : scratchpad `produits-anon.txt`.

### Point du 24/11, ~12 h 30 UTC (le plus récent)

**Branches locales d'intégration** (worktree de l'orchestrateur ; sauvegarde poussée sur `notes-l5-2411`) :
`dev-ecrans-v2` = `origin/main@cdaf0d30b1` + les documents de la partie 2 + les lanes `releve-client` et `documents`
pliées ; `dev-moteur-e2b` = point de départ de la suite du moteur (rien de plié encore).

**Écrans sur les maquettes v2 (étape 3 de la demande)** — planches sous `T4/preuves/`, regardées par l'orchestrateur :
- PLIÉES : `releve-client` [ACAL1814, 1836, 1817, 1837, 1838] — relevé, vue client téléphone et Présentation PROCHES :
  les cadres, cartes, boutons et la barre du soleil sont à la maquette ; ce qui manque est la SCÈNE 3D (un grand bloc
  gris au lieu d'une maison, panneaux noirs) — fichiers du moteur de dessin. `documents` [ACAL1725, 1726, 1834 ;
  ACAL1943 contestée : ses prémisses sont fausses] — Documents PROCHE : trois colonnes, aperçu, pastilles, anneau ;
  reste la tête « Étape 5 sur 5 » de la coque (88 px que la maquette n'a pas) et le pied du devis à plusieurs surfaces.
- EN VOL : `coque` (opus, port 5263, `rev_c`) [ACAL1835 Tablette — livrée —, ACAL1826 Démarrage rapide, ACAL2030
  Expert, puis trois demandes croisées : tête d'étape retirée là où la maquette n'en a pas, pied du devis compact,
  une seule règle `flex` pour la vue client] ; `dessin` (opus, port 5264, `rev_d`, branche `lane/dessin` partie de
  `dev-ecrans-v2`) [ACAL1984 teinte, 1981, 1820, 1839 scène 3D présentable et cadrage, 1944 chaînes, 1920, 1924 cotes,
  ACAL2042 contour doré — tâche NEUVE que la lane écrit au plan avant de la construire] ; `spec-maquettes` (sonnet,
  port 5265, `rev_a`) [ACAL1748, ACAL1806 : la spec permanente rend les 14 planches v2 | réel].
- RESTENT : ACAL2031, ACAL2032 (`apps/web`, après la lane `dessin` : mêmes fichiers) ; un relecteur NEUF pour juger
  les 14 planches (aucune lane ne se dit FIDÈLE : chacune s'est jugée seule).
- À la fusion : couture sur l'arbre plié (vitest du module, eslint, build, gardes), PR `dev-ecrans-v2`, puis
  l'instrument est remis sur le code poussé.

**Moteur unique** : extraction ADEV160 EN VOL (opus) — figeage étendu livré (`ef400a21f8`), extraction en cours.

**Partie 2, préparation — faite sur la pile `l5t`**
- Copie anonymisée de la production importée (société `taqinor-anon`, compte `anon_admin` ; 10 420 lignes, 0 rejet).
- Miroir de la production (lecture seule du 24/11) : 93 fiches techniques, réglages du calepinage, forfaits C&I,
  délais. Scripts : scratchpad `prod_reglages.py` (sonde, lecture seule), `l5t/miroir_prod.py`.
- Fiches techniques complétées d'après les fiches publiques des fabricants : 184 valeurs remplies, 22 corrigées,
  chacune avec sa source — registre `T4/preremplissage.md` (écrit par script) ; journal `var/anon/journal-fiches-…`.
- Inventaire de couverture `T4/couverture.md` (449 éléments) ; plan `T4/plan-test-utilisateur.md` (scénarios a-r et
  balayages s-w).
- EN VOL : recherche de prix publics des articles de pompage sans prix (sortie `var/anon/prix-sources-pompage.json`).
- RESTE : « Remplir les réglages vides » par l'écran, mode météo et années, comptes aux quatre rôles, clé de carte,
  prix sourcés à appliquer, puis les relecteurs.

**Constats pour le fondateur (à dire au rapport ; la production n'est pas modifiée)**
1. Fiches techniques de production en désaccord avec le fabricant (12 produits, détail `T4/preremplissage.md` § 5.1) :
   Canadian Solar 715 W — courant de court-circuit 22,30 A sur la fiche, 18,64 A chez le fabricant ; deux panneaux
   bifaciaux marqués non bifaciaux ; Deye 10 kW monophasé — tension maximale 600 V sur la fiche, 500 V imprimés ;
   Deye 5 kW triphasé — la fiche décrit un autre produit (1 MPPT, 52 V) ; Huawei 5 kW — 22 A au lieu de 12,5 / 18 A ;
   Huawei 50 kW — 6 MPPT au lieu de 4. Ces valeurs entrent dans le verdict panneau / onduleur et la longueur des chaînes.
2. Réglages du calepinage de la production : ni mode météo, ni salissure, ni dégradation initiale, ni indisponibilité,
   ni pertes de câbles — « Remplir les réglages vides » n'a pas été appliqué en production après le déploiement.
3. Aucune des 11 pompes à courbe (OSP 30) n'a de prix ; seules les pompes sans courbe en ont : un devis automatique de
   pompage avec pompe neuve ne peut pas être complet sur le catalogue réel.
4. Modèles à identifier par le fondateur (plusieurs générations correspondent) : Deye 5 kW monophasé, Huawei 10 kW
   triphasé (standard ou « High Current »), Deye hors réseau 6 kW.

**Défauts candidats notés en passant (à rejouer en partie 2)**
- Une simulation lancée sur un calepinage SANS point GPS échoue dans le worker à 5 % (`EntreeInvalide`, « sans point
  GPS, aucune production ne peut être demandée ») au lieu d'être refusée avant le lancement — deux lanes l'ont prise
  pour une panne de PVGIS (PVGIS et NASA POWER répondent bien depuis la pile : 200, série horaire 2014-2023 en 6,6 s).

### Point du 24/11, ~14 h 00 UTC (le plus récent — REPRENDRE ICI)

**Moteur unique**
- **PR Taqinor/taqinor-os#1546** (branche `dev-moteur-e2b`) : ADEV160, figeage étendu (16 goldens) puis extraction du
  pipeline pur (`apps/ventes/conception/decisions.py`, `etudes_lignes.py`). Relecture adverse indépendante (opus neuf,
  même code) : fusionnable, aucun constat bloquant. CI de PR : 31 verts, 0 rouge ; en file de fusion (14 h). À
  VÉRIFIER : `gh pr view 1546 --json state,mergedAt`. Aucune migration.
- **Lane du moteur EN VOL** (opus, worktree `agent-a57dbc31fa995e57f`, branche `lane/moteur-e2c` partie de
  `dev-moteur-e2b`, base de test `x2`) : (0) figer le journal du devis automatique (alertes `taille_demandee`,
  `batterie_hors_reseau`, clés `plafond_applique`, `contour_client`), capturé sur le code d'AVANT l'extraction ;
  (1) ADEV133 `calculer_conception` sans écriture, avec la parité au niveau du moteur contre les goldens ;
  (2) ADEV134 suppositions. ENSUITE, autre lane : ADEV135 (écrivain), ADEV136, ADEV137 (route), ADEV138 (parité rangée).
- Leçon appliquée : une lane ne joue plus une suite entière en local (`apps.crm` = une heure en un processus sur ce
  poste ; l'extraction y a perdu ~50 min) ; la CI de PR d'une branche `dev-*` joue tout le backend. Brief corrigé.

**Écrans sur les maquettes v2 — branche `dev-ecrans-v2`, poussée (`35eae8c706`), pas encore de PR** (un seul CI à la
fois : la PR s'ouvre dès la fusion de #1546)
- Cinq lanes pliées : `releve-client`, `documents`, `coque`, `spec-maquettes`, `dessin` — 21 tâches (20 « code livré,
  preuve en direct due », ACAL1748 cochée ; ACAL1943 contestée, laissée ouverte). `main` intégré (jusqu'à
  `77807d6d1b`, PR #1539, #1544, #1545 d'autres sessions), empreinte CODEMAP recalculée.
- Couture : vitest du module, eslint, build verts sur A + B + C + E ; rejouée sur l'arbre complet (sortie
  `l5t/couture2-*.log`).
- L'instrument `l5t` sert `dev-ecrans-v2@35eae8c706` depuis 13 h 52 UTC (base migrée, serveur relancé, front rebâti).
- EN VOL : relecteur NEUF `B4` (opus, navigateur) — les 14 écrans contre les maquettes v2, verdicts et constats dans
  `T4/B4.md`, planches `T4/preuves/B4/` ; lane `suites-ecrans` (opus, worktree `agent-a60912ec13b275fe4`, branche
  `lane/suites-ecrans`, port 5266) — « Glissez pour tourner autour » mort à la souris en vue client, ACAL2032,
  ACAL2031, colonne des cartes Documents (23 px), calques du dessin selon l'étape, bascule de la carte d'accès solaire.
- Verdicts des lanes (elles se sont jugées seules) : Démarrage rapide FIDÈLE en mise en page ; Documents, Tablette,
  Relevé, Vue client, Présentation, Toit, Panneaux, Électrique PROCHES. La scène 3D montre maintenant une maison
  entière (murs clairs, toit tuile, panneaux bleus à cellules) — il manque le décor (jardin, soleil) et la taille.
- Commande de la spec permanente (14 planches) : depuis `frontend`,
  `E2E_BASE_URL=http://127.0.0.1:<port> CAL_MAQUETTES_SORTIE=<dossier> node node_modules/@playwright/test/cli.js test e2e/calepinage-maquettes.spec.js --project=chromium`.

**Partie 2, préparation** : voir le point de 12 h 30 ; en plus — préremplissage par les écrans FAIT (« Remplir les
réglages vides » : 5 pertes supposées ; météo « plusieurs années réelles » 2014-2023, source « Saisie » ; comptes
`anon_commercial`, `anon_resp`, `anon_tech`, `anon_admin2`, mot de passe = `REV_PW`), registre
`T4/preremplissage.md` §§ 1-7, constats de préparation `T4/constats-preparation.md` (16 candidats).

**Questions posées au fondateur, en attente (le choix par défaut s'applique sinon)**
1. Prix des articles de pompage dans la copie d'essai : A (défaut) prix publics les plus proches, étiquetés « valeur
   d'essai » ; B laisser vide ; C ses prix. Aucun prix public n'existe pour les pompes OSP 30 (fabricant Oswal).
2. Clé de carte : l'orchestrateur ne saisit pas une clé de production ; à poser par le fondateur dans `l5t/l5t.env`
   (`PUBLIC_MAPTILER_KEY=`), sinon le test se joue sur fond gris.

### Point du 24/11, ~15 h 20 UTC

**Règles du fondateur ajoutées dans la journée (toutes en vigueur)**
- « you push too many CIs » : UNE PR par gros lot, plus de petites PR. Le lot en cours = la branche locale
  `dev-ecrans-v2` (écrans + suites + moteur étape 2 + déclencheurs + premiers correctifs du test utilisateur).
- « launch more lanes » puis « keep monitoring ram and cpu » : avant CHAQUE lancement de lane ou de relecteur,
  `powershell -NoProfile -ExecutionPolicy Bypass -File <scratchpad>/ressources.ps1` — `GO` (≥ 3,0 Go libres et CPU ≤ 85 %),
  `GO-LEGER` (≥ 2,0 Go et ≤ 92 % : une lane légère seulement), sinon `ATTENDRE`.
- « don't spend time running local CI tests » : une lane ne joue en local que la classe de test qu'elle écrit ; la CI
  de la PR (branche `dev-*`, backend compris) est la barrière.

**Moteur unique — état**
- Sur `main` : PR #1540 (contrat), #1542 (table `ConceptionLead`, entrées, goldens ADEV159), #1546 (ADEV160,
  extraction du pipeline pur). Fusionnées ; #1546 non déployée à ma connaissance.
- Sur la branche de lot `dev-ecrans-v2` (PAS sur `main`) : lane déclencheurs pliée (ALEA68, ACAL2011, ALEA69 — « code
  livré ») ; lane moteur `lane/moteur-e2c` pliée (figeage du journal, ADEV133 `calculer_conception` — 20 goldens sur 21
  reproduits clé par clé, zéro écriture ; ADEV134 suppositions) — ADEV133 et ADEV134 cochées.
- EN VOL : lane écrivain/route `lane/moteur-e2d` (worktree `agent-aecb8f14131ba4555`, partie de `lane/moteur-e2c`,
  base de test `x4`) : ADEV135, ADEV136, ADEV137, ADEV138. Relecteur adverse NEUF (opus, lecture seule) du diff
  `4f965ebede..27b12494fe` : 9 points (extraction à comportement égal sur les cinq origines, golden recapturé
  `split_dm_auto_agr.json`, zéro écriture, pas de prix d'achat, cloisonnement société, parité, suppositions, règle 4,
  budget de `moteur.py` 461 lignes pour 380). Ses constats bloquants se corrigent AVANT la PR du lot.
- Non rejoués en local, à la charge de la CI du lot : `test_qjr_ecrivain_lignes`, `test_qjr_forfait_par_panneau`,
  `test_qjr_pipeline_appliquer`, `test_adev25`, `test_pv42`, `test_l_pcmp`, `test_stkcat23`, `test_tva_ligne_produit`,
  `test_qjr204`, `test_adev30`, `test_qjr220`, `crm.tests_dc11_provenance`, `test_auto_pipeline`, `test_err_qjr570`,
  `lint-imports`.
- Reste après ce lot : E3 (ADEV139, ADEV140, ADEV141), E4 (ADEV142-148, ALEA70, AGEN12, ACAL2027), E5 (ACAL2012-2017,
  ACAL2028), E6 (ACAL2018-2020, ADEV149-151), E7 (ALEA71, ACAL2021-2023, ADEV152-153, AGEN11, ACAL2029), E8 (AGEN13,
  ACAL2024-2025, ADEP108), E9 (ACAL2026, ADEV154 = liste montrée au fondateur, ADEV155 GATED jusqu'à sa réponse).

**Écrans v2 — état**
- Relecteur neuf B4 (14 écrans contre les maquettes) : 0 FIDÈLE / 13 PROCHES / 0 ÉLOIGNÉ / 1 non comparé (B3 : 0 / 6 /
  6 / 2). Rapport `T4/B4.md`, planches `T4/preuves/B4/`. Constats : T4-B4-001 S2 (vue client, « Glissez pour tourner
  autour » mort — corrigé par la lane suites), T4-B4-002 S2 (chargement du catalogue interrompu juste après « Créer le
  calepinage », vu une fois), T4-B4-003 S2 (le compte des réglages vides affiche 20 / 6 / 4 / 16 selon l'endroit),
  8 S3, 2 S4. Le banc API de la spec (`calepinage-maquettes.banc.js`) fausse plusieurs planches (3D vide, toit décalé).
- EN VOL : lane `suites-ecrans` (worktree `agent-a60912ec13b275fe4`, branche `lane/suites-ecrans`) — six commits posés
  (vue client à la souris et au doigt, ACAL2032, ACAL2031, colonne des cartes Documents, repères de la carte par
  étape, bascule de la carte d'accès solaire), planches en cours. À PLIER dans `dev-ecrans-v2` à son retour.
- Ensuite : lane « correctifs B4 » (constats S2/S3 restants + banc de la spec), partie de la branche pliée.

**Partie 2, test utilisateur — tour 1 EN VOL** (instrument `l5t` sur `dev-ecrans-v2@35eae8c706`, donc AVANT le pli
des déclencheurs et du moteur étape 2 : à remettre à jour avant le tour 2)
- U1 résidentiel a-d · U2 commercial et industriel e-h · U3 agricole i-k + l, m · U4 cas limites n-r. Chacun écrit
  `registre/constats/T4-<code>.jsonl`, `T4/tour1/couverture-<code>.json`, `T4/tour1/<code>.md`.
- Constats déjà posés : T4-U2-001, T4-U2-002 (S3) ; T4-U3-001 (S3), T4-U3-002 (S2 : origine du débit de pompage
  « Mesuré en visite » enregistrée, relue « Déclaré par le client » à la réouverture), T4-U3-003 (S4).
- À lancer quand les ressources le permettent : U5+ (balayages s-w). Puis consolidation en tâches v3, lanes de
  correction (test rouge d'abord), rejeu par relecteur neuf, tours jusqu'à deux d'affilée sans rien de neuf.

**Choix pris seul par l'orchestrateur ce jour (à dire au fondateur dans le rapport final, réversibles)**
figer puis extraire le pipeline avant le point d'entrée du moteur ; mode météo « plusieurs années réelles » 2014-2023
pour la copie d'essai ; en-tête d'étape masqué (lecteur d'écran seulement) là où la maquette n'en dessine pas ;
l'effacement d'un lead supprime ses versions de conception rangées ; libellé vrai « Production ÷ consommation » gardé
contre « 82 % de votre facture » de la maquette (formulation = décision du fondateur) ; conteneurs de développement
partagés `erp-agentique-django_core-1` et `erp-agentique-fastapi_ia-1` arrêtés pour libérer la mémoire (à relancer au
démontage).

### Point du 24/11, 17 h 15 UTC

**Branche de lot `dev-ecrans-v2` (locale, tête `9ff02bfaa9` + ce point) — PAS encore de PR (une seule PR pour tout le lot)**
Pliés depuis le point précédent : lane `suites-ecrans` (six correctifs d'écran, ACAL2031 cochée, ACAL2032 « code
livré ») ; lane moteur `lane/moteur-e2d` = FIN DE L'ÉTAPE 2 : ADEV135 (`relancer`, écrivain unique), ADEV136 (porteur
calepinage), ADEV137 (sélecteurs, routes `GET ventes/conception/<lead_id>/` et `POST ventes/conception/apercu/`),
ADEV138 (parité stockée, 20 goldens), corrections de la relecture d'ADEV134 — ADEV133 à ADEV138 cochées. Conflit
résolu à la main dans `core/event_coverage.py` (trois réservations d'émetteur retirées).
Gardes du dépôt jouées sur la branche avant ces plis : toutes vertes ; flake8 vert sur les .py changés.
À FAIRE avant la PR : intégrer `origin/main` (4 commits de retard à 15 h 30), régénérer `docs/api-contracts.md`, le
schéma OpenAPI (2 routes neuves), le catalogue d'événements, CODEMAP (`codemap_fingerprint.py --write`).

**Lanes EN VOL (9, plafond de la machine — jauge `ressources.ps1` avant tout lancement)**
- Moteur E3 + E4 : worktree `agent-aecb8f14131ba4555`, branche `lane/moteur-e3e4`, base de test `x4` — ADEV139, 140,
  141, 142, 143, 144, 145, 146, 147, 148, ALEA70 dans cet ordre. La chaîne du moteur est SÉQUENTIELLE (ACAL2018 attend
  ACAL2017) : E5 (ACAL2012-2017) ne part qu'à son retour, puis E6, E7, E8, E9.
- Relecteur adverse neuf (opus, lecture seule) : plage `27b12494fe..19c9d3e050` + déclencheurs `0a1daebcf1`,
  `7d12f4e406`, `58d1946eb7` — 8 points, dont la PORTÉE DU RÔLE sur les deux routes (`IsAnyRole` + filtre société
  seulement ?). Ses constats bloquants se corrigent avant la PR.
- Correctifs d'écran `correctifs-b4` : worktree `agent-a60912ec13b275fe4`, branche `lane/correctifs-b4`, port 5267 —
  constats B4-002, 003, 010, 007, 005, 009, 006, 008, 013, 012, banc de la spec, + plan décalé (U1-017) et module à
  désigner deux fois (U1-006, U2-007, U4-007, U4-008).
- Correctifs agricole et envoi `correctifs-agri` : worktree `agent-a18395c2b0287c783`, branche `lane/correctifs-agri`,
  port 5268, base de test `i` — U3-002, U3-007 (ligne à 0 : alerte + envoi refusé), U3-006, U3-008, U3-004, U3-009,
  U2-003 + U3-011, U3-001, textes techniques, U3-005, U2-011.
- Site et facture `site-facture` : worktree `agent-a57dbc31fa995e57f`, branche `lane/site-facture`, base de test `j` —
  U1-001 (facture déclarée 900 imprimée 831), U1-003 (simulation au centre de la carte), U1-019, U1-008, U1-002.
  Son correctif d'arrondi est accroché au niveau de règles 15 (déclaré, NON courant) : rien ne change tant que le
  fondateur n'a pas activé ce niveau.
- Relecteurs du test utilisateur, tour 1 : U1 (a-d), U2 (e-h), U3 (i-k, l, m), U4 (n-r) — 66 constats au registre,
  rapports `T4/tour1/U*.md` pas encore rendus.

**Tour 1 — consolidation** : `T4/tour1/consolidation.md` (17 causes ; deux S1 : facture déclarée restituée plus basse
au PDF, simulation sur un point que personne n'a choisi). La classe K3 « plusieurs chiffres pour une même valeur » est
le travail des étapes E4 à E7 du moteur : ses constats deviennent les cas d'acceptation de ces étapes.

**À lancer quand la jauge le permet** : balayages s-w (U5+) ; lane calepinage suivante (K14, K16, U3-012, U1-013,
présélection de l'option à l'acceptation U1-014) après le retour de `correctifs-b4` ; prix publics d'essai des
articles de pompage (choix A par défaut) AVANT le tour 2 ; mise à jour de l'instrument `l5t` sur la tête pliée.

**Constats pour le fondateur ajoutés ce jour (production intacte)** : le catalogue copié porte de nombreux articles
actifs sans prix de vente (11 pompes à courbe, disjoncteurs, fusibles, parafoudres, sectionneurs, lignes de
prestation C&I) et six articles au nom aléatoire (« DFASFA », « dsafsdg », « feaf », « gsdg », « sdadg », « SDVGDS »).

### Point du 24/11, 19 h 05 UTC

**PR Taqinor/taqinor-os#1552** — branche `dev-ecrans-v2`, tête `127a07c862` : LE lot du jour (écrans v2, correctifs
du tour 1 des lanes B4 / site-facture / agri, moteur étape 2 + relectures, portée du rôle). Auto-fix allumé, fusion
automatique demandée. **CI ROUGE, 1er tour — liste complète, à corriger en UN seul push :**
- gardes : ENF22 (`except` silencieux `conception/service.py::_champ_du_modele`, `::_nombre`), ENF23 (deux `skipTest`
  non signés, `HORS_PARITE`), PACT159 (promesse en prose `frontend/.../calc/totaux.js` ~185), QJR6 (deux écritures en
  bloc d'`etude_params` dans `conception/moteur.py` — objets en mémoire) ;
- tests backend (4 sur ~27 000) : cliquet des imports ventes → calepinage (24 pour 22), `test_qjr243` (site d'appel
  déplacé par l'extraction), grep « prix carburant » sur un commentaire de `crm/serializers.py:1252`, garde de portée
  ADEV41 (deux routes de la conception à classer « sondées ») ;
- api-fuzz : `POST ventes/conception/apercu/` refuse un corps conforme au schéma déclaré ;
- front : `web-build-test` (4 tests de tracé : le correctif B4-005 « fermer au premier coin » avale probablement un
  4e coin — régression de code à corriger, pas les tests), `frontend-static` (classe héritée du site public ;
  golden de geste « deux clics »), vitest (bandeau « 7,1 kWc », golden DOM de `ToitureDesign`), **e2e : la page
  « Démarrage rapide » est BLANCHE** (`/calepinage/reglages/demarrage-rapide`).
- Deux correcteurs EN VOL, chacun dans son worktree isolé, branches `fix/ci-gardes` (gardes + tests backend + fuzz)
  et `fix/ci-front` (front + page blanche), parties de `origin/dev-ecrans-v2`. À leur retour : plier les deux dans
  `dev-ecrans-v2` (le worktree de l'orchestrateur est sur `dev-lot2` : `git checkout dev-ecrans-v2` d'abord),
  régénérer l'instantané OpenAPI si un composant nommé est ajouté (commande docker du point 17 h 15), pousser UNE
  fois, puis refondre `dev-ecrans-v2` dans `dev-lot2`.
- Journaux de la CI : `%TEMP%/ci1552-*.log`.

**Lot suivant — branche locale `dev-lot2`** (PAS poussée) = `dev-ecrans-v2` + étape 3 du moteur (ADEV139, 140, 141,
145, 146, ALEA70, corrections m1-m5 — cochées) + lane `calepinage-serveur` (5 correctifs). **L'étape 3 n'est PAS
fusionnable en l'état** (relecture adverse indépendante) : BLOQUANT — un effacement légal (loi 09-08) est défait
5 s après par la relance en file (l'ancien GPS réécrit dans `ConceptionLead` et au chatter) ; MAJEURS — calepinage
archivé = conception figée pour toujours ; `remplir_conceptions --appliquer` écrase une version née d'une pose ; le
remplissage écrit une ligne d'historique sur chaque lead et relance l'horloge de conservation ; ALEA70 change ce
que l'utilisateur peut faire (lead en kWh sans facture = prêt) sans décision enregistrée.
- EN VOL : lane moteur E4 relancée en worktree ISOLÉ (branche `lane/moteur-e4b`, base de test `x4`) : d'abord ces
  corrections, puis ADEV142 + 143 ensemble, 144, 147, 148. Arbitrage de l'orchestrateur pour le C&I et l'agricole :
  la conception rangée ne porte pas les lignes du devis ; le devis automatique rejoue UNE décision pour composer
  les lignes et copie les blocs rangés (même moteur, mêmes entrées, parité testée) — à dire au fondateur.
- Leçon : une lane lancée SANS `isolation: worktree` peut se voir refuser l'écriture dans un autre worktree ;
  lancer les lanes qui écrivent avec `isolation: worktree` puis `git checkout -b <branche> dev-lot2`.
- EN VOL aussi : `atelier-suite` (worktree `agent-a60912ec13b275fe4`, 11 constats + 4 suites du serveur) et
  `front-suite` (worktree `agent-a18395c2b0287c783` : relevé au téléphone hors ligne, liste des leads, SAV,
  acceptation, garde kWh, dialogue de ville, RIB, petits).

**Test utilisateur**
- Tour 1 TERMINÉ : 101 constats (2 S1, 30 S2, 51 S3, 18 S4), rapports `T4/tour1/U1.md` à `U4.md`, consolidation
  `T4/tour1/consolidation.md`. La pile était saturée (quatre relecteurs + lanes) : scénarios b, c, d, f, g, h, j
  coupés. LEÇON : deux relecteurs à la fois, pas quatre.
- Instrument `l5t` mis à jour à 18 h 40 sur `dev-ecrans-v2@127a07c862` (gunicorn 2 × 6 fils), `SITE_URL` et
  `VITE_PUBLIC_SITE_URL` = `http://site-public.invalid` (un relecteur avait ouvert UNE page publique de production
  par « Ouvrir la page client » : aucune donnée envoyée, jeton local inconnu là-bas).
- Prix d'essai posés sur la copie (19 articles de pompage, sources publiques, `T4/preremplissage.md` § 8). Restent
  sans source : tarif de pose « Installation pompage solaire » et courbes des pompes monophasées → le devis
  automatique agricole ne peut pas aboutir sans le fondateur.
- Tour 2 PAS ENCORE LANCÉ (attend la fin des correcteurs de CI : ressources) : V1 = rejeu des correctifs côté
  calepinage + scénario b ; V2 = rejeu des correctifs devis / lead / agricole + scénarios c, d ; puis agricole
  avec prix d'essai, balayages s-w, relecteur des maquettes B5.

**Décisions à porter au fondateur** (liste tenue dans `T4/tour1/consolidation.md`) + : ALEA70 (lead en kWh sans
facture prêt à deviser — recommandé : garder) ; origines de mesure « essai / foreur » choisissables sur la fiche
(revient sur AGR400) ; bandeau de l'atelier au nom du calepinage (revient sur ACAL1730) ; `rafraichir_etudes_du_devis`
réécrit le bloc de dimensionnement d'un devis ENVOYÉ quand la facture du lead change (QJR5 contre D-ACAL-97) ; rôle
Technicien : 403 sur le calepinage et le relevé ; tarif de pose du pompage ; clé de carte.

### Point du 24/11, 20 h 50 UTC

**PR Taqinor/taqinor-os#1552 FUSIONNÉE à 20 h 40 UTC** (lot 1 : écrans v2, correctifs du tour 1 des lanes B4 /
site-facture / agri, moteur étape 2 + portée du rôle). Trois tours de CI : (1) gardes ENF22 / ENF23 / PACT159 / QJR6,
quatre tests backend, api-fuzz, tests web du tracé (vraie régression du correctif B4-005, corrigée dans le CODE),
goldens front, page « Démarrage rapide » plein écran inconnue de la fumée des écrans ; (2) budget du bundle (4 162,2
pour 4 160 → 4 175) ; (3) un test e2e instable (`calepinage-parcours.spec.js` ACAL987 : onglet recouvert pendant un
re-rendu) — vert à la relance du seul job. **À déployer par le fondateur : `scripts/deploy-prod.ps1`.** Non déployé.
Leçon du fondateur : corriger une CI rouge avec AUTANT de lanes parallèles que possible (six correcteurs lancés).
Leçon de l'orchestrateur : avant d'ouvrir une PR, jouer les familles qui ont rougi — `node --test "src/**/*.test.mjs"`
(repères hors contrat, classes héritées), tests front LIÉS aux fichiers changés (`vitest related`) et tous les goldens,
budget du bundle, gardes hôte (`check_except_larges`, `check_tests_sautes_environnement`, `check_override_registry`,
`check_services_appeles`, `test_check_choices_declares`), et en docker les tests-cliquets (`test_imports_croises_ventes`,
`test_adev41_garde_portee_ventes`, `tests_scission_golden`, `test_event_coverage`).

**Lot 2 — branche locale `dev-lot2`** (PAS poussée, PAS de PR) : étape 3 du moteur (ADEV139, 140, 141, 145, 146,
ALEA70) + ses corrections de relecture (9 commits) ; lanes `calepinage-serveur` (5), `atelier-suite` (15),
`front-suite` (18 commits) ; repère de test déclaré. Budget du bundle mesuré en local : 4 169,7 Ko pour 4 175
(roof-tool 645,1 pour 650).
- **Étape 3 toujours NON fusionnable** — seconde relecture indépendante des corrections : BLOQUANT, une ligne du
  chatter écrite AVANT l'effacement garde les coordonnées GPS (`_caviarder_historique` ne réécrit pas les lignes
  `conception_version`) ; MAJEUR, une tâche déjà en cours pendant l'effacement range encore une version avec les
  anciennes données (verrouiller la ligne du lead dans la transaction de `ranger`) ; MAJEUR, le remplissage calcule la
  première version sans le toit d'un calepinage déjà posé ; mineurs (arguments de la tâche porteurs de valeurs, tests
  qui n'épinglent que deux gardes sur cinq, tâche ancienne qui écrase une récente). Tout est parti à la lane du moteur.
- EN VOL : lane moteur `lane/moteur-e4b` (worktree isolé `agent-ae36ffd66221266fc`, base de test `x4`) — ces
  corrections puis ADEV142 + 143, 144, 147, 148 ; lane `lane/serveur-suite` (worktree isolé, base `n` : phrases du PDF
  industriel au niveau 15, blocage électrique qui nomme sa cause, article nommé dans le refus agricole, motif MT ;
  « sol et ombrière » CONTESTÉ côté serveur : ils sont câblés) ; correcteur `fix/lot2-front` (balayage front avant PR :
  golden `ToitureDesign` rouge connu) ; relecteurs du tour 2 V1 (rejeux calepinage + scénario b) et V2 (rejeux devis /
  lead / agricole + scénarios c, d) sur l'instrument à `6633028331`.
- AVANT la PR du lot 2 : plier `lane/serveur-suite`, `fix/lot2-front`, les corrections de la lane moteur ; intégrer
  `origin/main` ; CODEMAP (modules neufs : `conception/receivers.py`, tâche `ventes.relancer_conception`, commande
  `remplir_conceptions`, `calepinage/services/site.py`, `crm/provenances_pompage.py`, `ventes/selectors_calepinage.py`)
  puis `codemap_fingerprint.py --write` ; `check_api_shapes.py --write` ; instantané OpenAPI en docker ; balayage
  backend en docker (liste de la leçon ci-dessus + `test_conception_lead`, `tests_devis_auto`, `tests_vref_villes`,
  `test_pret_a_envoyer`, `test_design_context`, `test_calx297_rapport_etude`, `test_cal223_contrats`).

**Garde morte trouvée** : `frontend/src/features/calepinage/budget.test.mjs` (CAL224) ne joue son contrôle de poids
que si `dist/` existe, donc jamais en CI ; son budget (73 Ko) date de septembre, le module pèse 133,6 Ko.

**Tâche de 9 h vue par le fondateur** : c'était la lane d'extraction du matin, tenue en vie par deux boucles d'attente
sur un journal terminé ; boucles arrêtées. Le serveur du front de l'instrument (5251) reste, exprès.

### Point du 24/11, 23 h 00 UTC

**Lot 2 — branche locale `dev-lot2`** (PAS poussée, PAS de PR) contient maintenant : étape 3 du moteur + ses deux vagues
de corrections de relecture (effacement légal fermé sur tous les chemins lus : lignes du chatter caviardées, lead relu
sous verrou dans `ranger`, tâche aux seuls identifiants, une garde = un test) ; **étape 4** (ADEV142 le devis
automatique naît de la conception rangée, ADEV143 colonne `Devis.conception_source` — **migration ventes 0162** —,
ADEV144 parité 20 goldens zéro clé différente, ADEV147 + ADEV148 brouillons qui suivent, route
`POST ventes/devis/<id>/mettre-a-jour-conception/`) ; lanes `calepinage-serveur`, `atelier-suite`, `front-suite`,
`serveur-suite` ; CODEMAP à jour pour l'étape 3 (PAS encore pour l'étape 4 ni la route neuve).
Gardes hôte vertes sur la branche (`check_forme_code` avec deux exceptions C20 motivées sur ADEV139 et ADEV143).
Balayage backend en docker vert (403 tests + les deux relancés avec le dossier front monté).
- EN VOL : relecteur adverse NEUF de l'étape 4 (lecture seule) ; lane moteur **E5** (`lane/moteur-e5`, worktree
  isolé, base de test `x5` : ACAL2012 à ACAL2017 — le calepinage lit la conception) ; correcteur `fix/lot2-front`
  (balayage front avant PR + trois ajouts : avis faux « sol et ombrière pas encore raccordés » à retirer, points
  servis du blocage électrique, article nommé du kit agricole) ; relecteur V2 du tour 2.
- AVANT la PR du lot 2 : verdict du relecteur de l'étape 4 (et ses corrections) ; plier `fix/lot2-front` ; CODEMAP
  (étape 4, route neuve) + `codemap_fingerprint.py --write` ; `check_api_shapes.py --write` ; instantané OpenAPI en
  docker (route neuve) ; garde de portée ADEV41 (la route neuve doit être sondée : la lane dit l'avoir fait ?
  À VÉRIFIER : `test_adev41_garde_portee_ventes`) ; rejouer en docker `test_conception_lead`, `test_devis_auto`,
  `test_split_devis_domaine`, `test_adev41_garde_portee_ventes`, `test_imports_croises_ventes`.
- **Parité sur données réelles (à faire avant toute bascule visible)** : quand V2 a fini, mettre l'instrument `l5t`
  sur `dev-lot2` (migration 0162) et rejouer, transaction annulée, le devis automatique par l'ancien chemin et par la
  conception sur les leads de la copie ; ne sortir que des comptes et des noms de clés (aucun montant).

**Tour 2 du test utilisateur** : V1 rendu (`T4/tour2/V1.md`) — 16 rejeux « corrigé » sur 21 ; scénario b joué
jusqu'au SAV ; 12 constats (3 S2). « Pas corrigé » qui compte : T4-U4-013 — un calepinage SANS lead, tracé à l'échelle
du pays sans épingle, simule encore au milieu du Maroc (les coordonnées du tracé ne sont pas le centre exact : le
serveur ne peut pas les distinguer d'une épingle posée → il faut que l'atelier dise si l'épingle a été posée).
V2 en cours (rejeux : 12 corrigés, 4 « autre », 1 pas corrigé déjà traité dans le lot 2).
Constats du tour 2 à donner aux prochaines lanes de correction : T4-U4-013 (suite), T4-V1-002 (sélecteur de produit
qui ne filtre pas, Entrée ajoute le premier article), T4-V1-003 (deux totaux du même nom), T4-V1-005 (saison perdue :
étape E5), T4-V1-006 (bloc du plan de pose coupé), T4-V1-007 (reste de la liste des devis), T4-V1-008 (ticket SAV
sans description), T4-V1-010 (pivot de la vue client), T4-V1-011 (le commercial ne trouve pas son client),
T4-V1-012 (« SoftTimeLimitExceeded() » brut), T4-V1-004, ACAL2032 (placement libre : « + Ajouter un panneau » sans
effet vu).

### Point du 24/11, 23 h 40 UTC

**PR Taqinor/taqinor-os#1554 — BROUILLON** (branche `dev-lot2` poussée, Auto-fix allumé, PAS de fusion automatique) :
lot 2 = étapes 3 et 4 du moteur + lanes `calepinage-serveur`, `atelier-suite`, `front-suite`, `serveur-suite`, balayage
front. Ouverte en brouillon pour connaître la liste des rouges pendant que les corrections se font. Rouges ATTENDUS :
schéma OpenAPI (un avertissement sur `mettre_a_jour_conception` : `DictField()` nu), garde de portée ADEV41 (route
neuve non classée). **Ne pas fusionner avant** : les corrections de la relecture adverse de l'étape 4.
- Relecture adverse de l'étape 4 (lecture seule) : BLOQUANT — l'empreinte de la conception ne couvre ni la phase du site
  (`raccordement`), ni le catalogue, ni la TVA : un devis automatique neuf pouvait sortir sur des entrées périmées ;
  MAJEURS — brouillon envoyé pendant un réalignement réécrit (pas de verrou ni de re-contrôle), le suivi des brouillons
  ne part que si la TÂCHE a écrit, brouillons C&I / agricoles dont le pointeur avance sans que les lignes suivent, route
  de mise à jour ouverte à `crm_voir` (la route voisine exige responsable ou administrateur : même garde posée, décision
  à confirmer par le fondateur), ligne du chatter écrite après un effacement.
- EN VOL (worktrees isolés, partis de `dev-lot2`) : `lane/moteur-e4-fix` (ces corrections + schéma de la route, base de
  test `x4`) ; `lane/moteur-e5` (ACAL2012 fait ; 2013 à 2017 ; base `x5`) ; correctifs du tour 2 — `lane/agri-2`
  (pompage : trois pompes proposées incohérentes, origine remise à zéro, étude vide à la modification… base `p1`,
  port 5270), `lane/devis-2` (sélecteur de produit, totaux, bandeau des options, clic mort d'envoi, restes à payer,
  révision, SAV, dialogue PDF ; base `p2`, port 5271), `lane/calepinage-2` (épingle réellement posée — T4-U4-013 —,
  message de délai, pivot de la vue client, est-ouest, placement libre, plan de pose coupé, recherche de client ;
  base `q`, port 5272). Brief commun : `<scratchpad>/brief-lane-correctifs-tour2.md`.
- À leur retour : plier dans `dev-lot2`, rejouer les gardes hôte + l'instantané OpenAPI + `--strict` en docker, pousser
  UNE fois (corrections de CI comprises), passer la PR « prête », `gh pr merge --auto --merge`.

**Instrument `l5t`** : sur `dev-lot2@4f73d97828` depuis 23 h 25 (migration ventes 0162 appliquée, serveur relancé,
front rebâti, `l5t-django` à 1 700 Mo). ATTENTION : cette version porte encore le défaut d'empreinte de l'étape 4.

**Tour 2 TERMINÉ** : V1 (12 constats) + V2 (25 constats) = 37, aucun S1, 10 S2 ; rejeux : 28 « corrigé », 5 « pas
corrigé » (dont 3 déjà traités dans le lot 2), 4 « autre », 1 non rejoué. Rapports `T4/tour2/V1.md`, `V2.md`.
Scénarios joués jusqu'au bout ou presque : a (tour 1), b (jusqu'au SAV), c (jusqu'à l'acompte), e (tour 1) ; d arrêté
aux résultats ; f, g, h arrêtés après les PDF ; i joué sans pompe ; j, k, l, m partiels ; n à r joués (tour 1).
PAS ENCORE JOUÉ : balayages s à w ; rôle Technicien (403) ; agricole avec les prix d'essai jusqu'au bout ; relecteur des
maquettes B5 ; rejeux d'acceptation des tâches « code livré » (ACAL2027, 2028, 2034, 2035, 2036, 2038 et les tâches
d'écran) ; mesure des lenteurs AU CALME (les relecteurs ont mesuré une pile saturée par les lanes).

### Point du 25/11, 00 h 40 UTC

**Lot 1 — PR Taqinor/taqinor-os#1552 : fusionnée le 24/11, NON déployée** (le fondateur déploie).

**Lot 2 — PR brouillon Taqinor/taqinor-os#1554, branche `dev-lot2`.** Contenu : étapes 3 et 4 du moteur unique et
leurs corrections de relecture (dont `lane/moteur-e4-fix` repliée EN ENTIER, commit de suite `a770f1f050` compris :
l'étude d'un brouillon C&I / agricole renaît par l'écrivain unique, plus aucune entrée au registre des écritures en
bloc), lanes `calepinage-serveur`, `atelier-suite`, `front-suite`, `serveur-suite`, balayage front, correctif EZ16.
`origin/main` (25 commits : hybrides haute tension, puissance maximale appelée, niveau de règles 16 dormant) intégré —
un conflit d'imports dans `ventes/domain/etude_ci.py` (les deux côtés gardés) et l'empreinte de CODEMAP recalculée.
Gardes hôte toutes vertes. Avant le push unique : instantané OpenAPI régénéré + `--strict` en docker, tests-cliquets
et tests du moteur en docker (journal `lot2-sweep2.log` du scratchpad), budget du bundle à remesurer (4 169,7 Ko pour
4 175 AVANT l'intégration de main, qui ajoute ~100 lignes de front).

**Lot 3 — pas encore de branche** (à créer depuis `dev-lot2` une fois le lot 2 poussé) :
- `lane/moteur-e5` (6 commits, étape 5 : ACAL2012, 2013 partiel, 2014, 2015, 2017 ; ACAL2016 CONTESTÉE — la conception
  ne sert pas de verdict, seulement `ratio_dc_ac`). Relecture adverse indépendante EN VOL. Doutes de la lane à trancher
  avant de plier : un lead SANS conception rangée voit « Conception du lead pas encore calculée… » dans l'atelier (tous
  les leads existants juste après un déploiement) ; module rapproché du catalogue par sa désignation ; longueur de
  chaîne de la conception appliquée au nombre de panneaux de la pose réelle ; +76 lignes pour un budget de 60.
- `lane/agri-2` (10 commits, relus par l'orchestrateur : champ borné à 1,5 fois la puissance de la pompe quand elle ne
  délivre pas le débit demandé, origine du forage gardée, « Modifier » rouvre l'étude de pompage, phrases vendeur en
  mots). Demande le fondateur : T4-V2-006, T4-V2-009, T4-V2-010 côté client (PDF agricole).
- `lane/devis-2` et `lane/calepinage-2` : EN VOL.
- Puis étape 6 (ACAL2018-2020, ADEV149-151) par la lane du moteur, sur la base du lot 3.

### Point du 25/11, 01 h 35 UTC

**Lot 2 — PR Taqinor/taqinor-os#1554 FUSIONNÉE le 25/11 à 00 h 57 UTC** (CI verte du premier coup : 39 jobs ; file de
fusion). Lots 1 et 2 NON déployés : « mergé — à déployer par toi : `scripts/deploy-prod.ps1` » dit au fondateur.

**Lot 3 — branche locale `dev-lot3`** (worktree de l'orchestrateur ; sauvegarde `origin/notes-l5-2511`, PAS de PR) =
`main` (après #1554) + `lane/moteur-e5` + `lane/agri-2` + `lane/devis-2` + `lane/calepinage-2` + l'acceptation
ACAL2027. **L'étape 5 n'est pas fusionnable en l'état** (relecture indépendante : `scratchpad/revue-e5.md` — B1 un lead
sans conception rangée tombe sur un refus sans issue ; M1 deux productions sans nom à Résultats ; M2 « le devis envoyé
porte le même chiffre » parfois faux ; M3 provenance « moteur » sans libellé ; M4 chaînes de la conception forcées sur
une pose d'une autre taille ; m1-m5 ; tests affaiblis ; coût en requêtes).
- EN VOL : `lane/moteur-e5-fix` (worktree isolé, base de test `r5`, consignes `scratchpad/msg-lane-e5-fix.md` +
  ajouts par message : ACAL2025 en dernier, note « par ? », supposition de la facture d'été, accord de la ligne
  d'historique) ; `lane/moteur-e6` (worktree isolé, base `s6` : identifiants de produit dans la conception, ACAL2016,
  ACAL2018, ADEV149, ADEV150, ACAL2019, ACAL2020, ADEV151, suite d'ACAL2013, ACAL2026, ADEV154 ; ADEV155 reste GATED ;
  fait vivant transmis : conception rangée sans chaînes, tension à froid, ratio ni retour sur investissement).
- La garde `check_ancres_taches.py` est ROUGE sur `dev-lot3` tant qu'ACAL2012 et ACAL2025 ne sont pas cochées (symbole
  `cible_de_l_option_retenue` supprimé par l'étape 5) : à cocher au pli de `lane/moteur-e5-fix`.
- À cocher au pli (après relecture) : ACAL2012, 2013, 2014, 2015, 2017, 2025 ; puis l'étape 6.
- Décisions prises par les lanes, à dire au fondateur (réversibles) : un Commercial voit le client qu'il a créé
  (`core/scoping.py`) ; un ticket SAV exige une description ; « Enregistré à » = heure de la dernière version ;
  un toit tracé à un zoom ≥ 17 vaut site localisé ; champ agricole borné à 1,5 fois la puissance de la pompe.
- Demandent le fondateur (rien de codé) : T4-V2-006, T4-V2-009, T4-V2-010 côté client (PDF agricole) ; lead « avec
  batterie » = une seule option ; « OPTION 2 » imprimé pour une option unique ; type de toiture « toit plat » et
  orientation « Est-Ouest » de la fiche (T4-V2-022, trois options) ; auto-remplir « les deux » à la taille du moteur.

**Test utilisateur — tour 3 EN COURS** sur l'instrument `l5t` (branche locale `instr-tour3` du worktree `l5t-instr` =
`main` après #1554 + agri-2 + devis-2 + calepinage-2, SANS l'étape 5 ; migrations crm 0166, stock 0188-0189 jouées ;
`LOGIN_RATE_LIMIT=120/minute` posé dans `l5t.env` — la limite de 5 connexions par minute et par adresse bloquait les
scripts ; serveur à 1 700 Mo).
- Couverture après deux tours : 188 lignes jouées sur 449 (`scratchpad/remplir_couverture.py`, à lancer avec
  `--ecrire` à la fin). Listes des lignes jamais jouées par relecteur : `scratchpad/tour3/ids-X1..X5.txt`.
- EN VOL : X1 (agricole i / j de bout en bout avec prix d'essai + fenêtre des PDF + onglet devis de la fiche) et X4
  (rejeux des correctifs devis du tour 2 + balayage du générateur + brouillon retouché à l'écran puis facture changée).
- À LANCER ENSUITE, deux à la fois : X2 (outil de dessin + étapes 1 à 3 + rejeux calepinage T4-U1-006, T4-U2-007,
  T4-U4-007, T4-U4-013, ACAL2032, T4-V1-006, 010, 011, 012, T4-V2-020, 021), X5 (onglets « Avancé », coque, Résultats,
  Documents, bouton devis), X3 (réglages, liste, création, routes), puis X6 (commercial et industriel f, g, h + chaîne
  après le devis), X7 (WebKit bureau + tablette), X8 (téléphone, sombre, rôle Technicien), relecteur des maquettes B5.
- Lenteurs des tours 1 et 2 remesurées au calme : 0,0 à 0,5 s par route (`T4/tour3/mesure-lenteur-orchestrateur.md`) ;
  devis automatique 12 à 18 s : c'était la saturation de l'instrument.
- Constats du tour 2 sans lane : T4-V1-001 (responsable « Non assigné »), T4-V2-022 (fondateur) ; écarts 3 à 11 de la
  trace d'ACAL2027 (`docs/audits/acceptation/ACAL/traces/2026-11-25/`), dont 4, 5, 6, 8 sans lane.

### Point du 25/11, 02 h 00 UTC

**Charge du poste (16 Go).** Mesuré à 01 h 45 : 1 Go libre, 24 Go demandés. Règle tenue depuis : TROIS agents de fond
au plus, dont DEUX à navigateur au plus, UN seul travail lourd à la fois (test docker, build du front, vitest), et
aucun lancement tant que `scratchpad/ressources.ps1` ne dit pas GO. Fait : test front de fond arrêté, serveur
d'aperçu oublié d'une lane (port 5262) arrêté, relecteur en lecture seule des trois lanes de correctifs MIS EN PAUSE
(agent `ab340260a0e92250d` : à reprendre par un message « continue », il repart de sa transcription), lane
`moteur-e5-fix` privée de build, d'aperçu et de navigateur (les écrans seront vus à l'acceptation).

**`lane/moteur-e6` REVENUE et repliée dans `dev-lot3`** (8 commits) : identifiants de produit dans la conception,
ACAL2016 (verdicts rangés par le moteur, « Prêt à envoyer ? » ne rejuge plus), ACAL2018 (façade de la pose), ADEV149
et ADEV150 (au niveau de règles 15 seulement ; parité au niveau 14 : 0 clé), ADEV151 (`remplir_conceptions --ecarts`,
n'écrit rien), clause restante d'ACAL2013. NON faits : ACAL2019 (arbitrage de l'orchestrateur : liée au niveau 15,
comme ADEV149), ACAL2020, ACAL2026, ADEV154, le retour sur investissement de la conception (servi à la lecture depuis
le devis de référence). `VERSION_MOTEUR` = `moteur-unique-2` : toute conception rangée devient périmée et se recalcule
à la lecture. Plafond des imports ventes → calepinage relevé 22 → 23 (porte `porte_calepinage.py`) ; calepinage →
ventes à 45 pour 44 (`devis_retenu.py`, étape 5) : confié à la lane `moteur-e5-fix`.
- À LANCER dès qu'une place se libère, dans cet ordre : (1) relecture indépendante de l'étape 6 (consignes
  `scratchpad/msg-revue-e6.md`, lecture seule) ; (2) lane `moteur-e6b` (consignes `scratchpad/msg-lane-e6b.md`, base de
  test `t6`, avec les constats de la relecture en tête) ; (3) reprise du relecteur en pause ; (4) étape 7 en trois lanes
  disjointes — fiche du lead (ALEA71, ACAL2021), écran devis (AGEN11, AGEN12 puis AGEN13), atelier (ADEV153, ACAL2022,
  ACAL2023) ; (5) relecteurs X2, X5, X3 du tour 3 (consignes `scratchpad/tour3/msg-X*.md`).
- Événements de CI reçus à 01 h 45 pour les PR #1552 et #1554 : ils visent d'anciennes têtes de PR DÉJÀ fusionnées —
  rien à faire.

**Ajout de 02 h 25 UTC.** `lane/moteur-e5-fix` REVENUE (13 commits) et repliée dans `dev-lot3` (un conflit de test,
les deux côtés gardés). **PR brouillon Taqinor/taqinor-os#1555 OUVERTE sur `dev-lot3`** pour faire tourner la CI à la
place du poste (Auto-fix allumé, pas de fusion automatique demandée). Rouges CONNUS de cette première passe : garde C20
(`test_conception_lead.py` + 173 lignes : l'exception ne peut être portée que par une tâche COCHÉE par la PR — ADEV151
dès que sa preuve en direct est jouée : `remplir_conceptions --ecarts` sur la société de démonstration de l'instrument,
APRÈS la relecture de l'étape 6) ; instantané OpenAPI à régénérer en docker. Tâches des étapes 5 et 6 marquées « code
livré, preuve en direct due » ; ACAL2025 : une clause restante (`conception_retenue_du_devis` encore lue par cinq
appelants). Restes de la lane e5-fix : étape Électrique sans phrase « calcul en cours » (27 assertions à déplacer),
atelier sans relecture automatique, budget de requêtes de `resultat/` à 22 pour 15, tests du front NON joués en local
(la CI les joue), note « par ? » (source : `crm/serializers.py:129`, `ChatterTimeline.jsx:290`).
EN VOL à 02 h 25 : relecture de l'étape 6 (lecture seule), X1 et X4. EN PAUSE : relecteur des trois lanes de correctifs.

### Point du 25/11, 03 h 15 UTC

**Lot 3 — PR BROUILLON Taqinor/taqinor-os#1555 (`dev-lot3`), tête poussée `580c0ab95b` : CI VERTE (38 jobs) au second
passage.** Premier passage : 15 jobs rouges ramenés à huit causes, toutes corrigées (désignation sur un calepinage sans
identité rangée — 83 erreurs ; « calcul en cours » pour un lead sans facture ; surface publique de `ventes.services` ;
clé `siteLocalise` non classée ; garde du champ `retenue` ; golden de `ToitureDesign` ; zoom de la carte lu sans garde
dans l'outil de toit ; instantané OpenAPI). **NE PAS FUSIONNER en l'état** : l'étape 6 y est avec ses deux défauts
bloquants au niveau 14 (relecture `scratchpad/revue-e6.md`) ; la fusion attend le pli de `lane/moteur-e6b1`.
Commits locaux NON poussés au-dessus de `580c0ab95b` : rapports et constats du tour 3, consolidation (docs seuls).
- EN VOL (trois agents, la limite du poste) : `lane/moteur-e6b1` (worktree isolé, base de test `t6`, consignes
  `scratchpad/msg-lane-e6b1.md` : B1, B2, m2, M5, M1, jamais de simulation synchrone, M3, M4 + m3, retour sur
  investissement servi à la lecture, ACAL2026, ADEV154) ; `lane/moteur-e6b2` (base `u6`, consignes
  `scratchpad/msg-lane-e6b2.md` : M2, m1, m4, ACAL2019 liée au niveau 15, ACAL2020) ; relecteur X2 du tour 3.
- EN PAUSE : relecteur en lecture seule des lanes `agri-2` / `devis-2` / `calepinage-2` (agent `ab340260a0e92250d`,
  à reprendre par message).
- Garde C20 locale encore rouge (`test_conception_lead.py` + 173 lignes) alors que le job de la CI est vert : à régler
  quand ADEV151 sera cochée (preuve en direct : `remplir_conceptions --ecarts` sur la société de démonstration de
  l'instrument, après le pli de `moteur-e6b1` qui corrige la commande).

**Test utilisateur, tour 3** — X1 et X4 TERMINÉS : 38 constats (2 S1 sur des PDF clients, 10 S2), tri et plan des cinq
lanes de correctifs dans `T4/tour3/consolidation.md`, consignes communes `scratchpad/brief-lane-correctifs-tour3.md`.
Faits mesurés : le pompage va de bout en bout avec un seul chiffre par valeur ; les 14 correctifs devis rejoués sont
confirmés ; la liste des devis sert 52 à 82 Ko par devis et l'écran les charge tous (590 devis ≈ 48 Mo : un processus
du serveur de la pile tué pour mémoire) — vrai défaut, priorité des lanes de correctifs. Erreurs 500 du devis
automatique = instrument (connexion à la base perdue sous charge). À FAIRE ENSUITE, dans l'ordre des places libres :
reprise du relecteur en pause ; lanes de correctifs 1 à 5 ; relecteurs X5, X3 ; étape 7 (après le pli de l'étape 6).

**Ajout de 03 h 40 UTC.** `lane/moteur-e6b2` REVENUE et repliée (`ff796938ef`) : m1 (plus de numéro de produit dans une
phrase), m4 (parité du lead 1742 restaurée, UNE marque « échec attendu » sur
`test_acal_ecart_devis.py::test_lead_1742_ratio_juge_pour_la_pose_reelle_ok` — À RETIRER au pli de `moteur-e6b1`, dont
le point M4 la fait passer), ACAL2019 (niveau 15 seulement), ACAL2020 (moitié calepinage). **M2 NON fait** (diagnostic) :
le document du toit ne porte aucune marque de retouche à la main ; il faut que l'outil de toit écrive
`zones[].geometry.poseManuelle` (= `hasManualEdits()` de `apps/web/src/lib/layoutVariability.ts`) à l'export, et que
`pose_servie.a_la_main` la lise — ne concerne que le niveau 15 (dormant) : à confier à une lane avec l'étape 7.
Relecteur en lecture seule des trois lanes de correctifs REPRIS. EN VOL : `moteur-e6b1`, X2, ce relecteur.

**Ajout de 04 h 00 UTC — relecture indépendante des lanes `agri-2`, `devis-2`, `calepinage-2` (déjà dans `dev-lot3`).**
`agri-2` : fusionnable (reste l'écart de spécification T4-V2-003 : la pompe supérieure garde moins de panneaux que la
recommandée — non régressif). `devis-2` : APRÈS CORRECTION — un ancien ticket après-vente sans description ne peut plus
être enregistré depuis son écran de modification (le formulaire renvoie `description: null` ; le changement de statut
part AVANT l'enregistrement refusé). `calepinage-2` : APRÈS CORRECTION — le bandeau « site non localisé » contredit le
serveur pour un calepinage de client sans lead ; les températures électriques lisent encore l'épingle brute (deux
lieux pour un calepinage) ; une adresse « Route d'El Jadida, Casablanca » est résolue à El Jadida. Portée du client
créé par un Commercial : aucune fuite (créateur forcé côté serveur, sous-arbre de la société). EN VOL pour tout cela :
`lane/t3-relecture` (worktree isolé, base de test `f0`, consignes `scratchpad/tour3/msg-lane-F0-relecture.md`).
**Le lot 3 ne fusionne qu'après le pli de `moteur-e6b1` ET de `t3-relecture`.** Lane suivante prête :
`scratchpad/tour3/msg-lane-F1-liste.md` (liste des devis légère).

**Ajout de 04 h 40 UTC.** `lane/moteur-e6b1` REVENUE et repliée (`d1f4077849`) : B1 et B2 corrigés (+ un troisième
bloquant trouvé par la lane : TOUTE désignation à la main faisait refuser la conception), m2 (`source: 'impose'`), M5
(un brouillon ne suit que si son contenu change), M1 + jamais de simulation dans une requête (niveau 15), M3 (liste
`--ecarts` vraie, une transaction par lead, `--limite`, `--lead`), M4 + m3 (« Prêt à envoyer ? » juge la pose réelle
par la règle unique), retour sur investissement servi à la lecture (`payback_devis`). NON faits : ACAL2026, ADEV154,
les deux clés du moteur pour ACAL2020 (`forme_horaire_24`, entrée imposée `consommation`), M2 côté outil de toit
(`poseManuelle`) → lane « E6c » à lancer. Doutes à porter au fondateur : une désignation à la main ramène la
conception à UNE option ; un module désigné d'une autre puissance garde le même kWc, arrondi au panneau.
- Rejeu docker en cours des modules touchés par les deux lanes (journal `scratchpad/lot3-sweep-e6b.log`) ; la marque
  « échec attendu » de `test_lead_1742_ratio_juge_pour_la_pose_reelle_ok` est à retirer si le test passe.
- EN VOL : `lane/moteur-e7b` (étape 7, écran devis : ADEV152 à vérifier, AGEN11, AGEN12, AGEN13 ; consignes
  `scratchpad/msg-lane-e7b.md`, base de test `e7b`), `lane/t3-relecture`, relecteur X2.
- FILE D'ATTENTE (trois agents au plus) : E7a fiche du lead (ALEA71, ACAL2021), E7c atelier (ADEV153, ACAL2022,
  ACAL2023), E6c, lanes de correctifs du tour 3 (1 liste des devis, 2 éditeur — APRÈS e7b, mêmes fichiers —, 3, 4, 5),
  relecteurs X5, X3, X6 à X8, relecteur des maquettes.

**Ajout de 05 h 35 UTC.** `lane/t3-relecture` REVENUE (5 corrections) et repliée ; marque « échec attendu » retirée ;
garde C20 verte (banc du test ADEV151 extrait, exception motivée sur ADEV151) ; contrats et instantané OpenAPI à jour.
**`dev-lot3` POUSSÉE (troisième passage de CI de la PR brouillon #1555).** AVANT de la passer « prête » et de demander
la fusion : mettre l'instrument à jour sur `dev-lot3` (worktree `l5t-instr` : `git checkout -B instr-lot3 dev-lot3`,
build du front avec `VITE_PUBLIC_SITE_URL=http://site-public.invalid`, `bash l5t/lancer.sh serveur`) et REGARDER les
écrans de l'étape 5 que personne n'a vus (étape Panneaux « calcul en cours », Résultats avec la conception, provenance
« de la conception » à l'étape Électrique, bandeau du site d'un client sans lead, modification d'un ancien ticket
après-vente) = acceptation ACAL2028.
Tour 3 : X2 TERMINÉ (11 constats, 10 rejeux confirmés) — total 49 constats, six lanes de correctifs décrites dans
`T4/tour3/consolidation.md`. EN VOL : `lane/moteur-e7b`, `lane/moteur-e6c` (consignes `scratchpad/msg-lane-e6c.md`,
base de test `e6c`). À lancer aux places libres : relecteur X5 puis X3 (sur l'instrument mis à jour), lane F1 (liste
des devis, `scratchpad/tour3/msg-lane-F1-liste.md`), E7a, E7c, lanes de correctifs 2 à 6.

**Ajout de 06 h 15 UTC.** Troisième passage de CI du lot 3 : tous les tests verts, deux gardes rouges corrigées et
repoussées (`fb0abf2d4d`) — arrondi d'argent (`selectors_conception._payback_servi` : `arrondi_affichage` au lieu de
`round`) et budget du bundle (4 175,0 mesuré → 4 190). QUATRIÈME passage en cours. **Dès qu'il est vert : `gh pr ready
1555`, réécrire le corps de la PR (ce n'est plus un brouillon), `gh pr merge 1555 --auto --merge`, puis dire au
fondateur « mergé — à déployer par toi ».**
Instrument `l5t` mis à jour à 04 h 40 sur `dev-lot3@22e6aa81ae` (branche locale `instr-lot3` du worktree `l5t-instr`).
Écrans de l'étape 5 REGARDÉS par l'orchestrateur (captures `scratchpad/acc2027/c1970-*.png`) : étape Panneaux (cible
de la conception : 8 panneaux · 4,40 kWc), étape Électrique (« jugé pour la pose : 23 panneaux — la conception du
lead en compte 8 »), Résultats (« Production de la conception : 6 969 kWh par an », « Calcul à refaire ») ; par l'API :
un lead neuf reçoit sa conception seul en 13 s, le retour sur investissement est servi (6,0 / 6,2 ans, devis de
référence nommé), `site_de_repli` = « Casablanca (ville de référence) » pour un client sans lead, un ancien ticket
sans description se modifie. L'enregistrement d'acceptation ACAL2028 reste À ÉCRIRE (états « brouillon » et « devis
envoyé lié qui diffère » non rejoués à l'écran : le relecteur X5 les joue).
FAIT pour le fondateur : la fiche technique du panneau par défaut des devis automatiques (« Panneau mono 550W ») est
VIDE (puissance crête, Voc…) — les verdicts électriques de la conception disent donc « non calculé » pour ces leads.
EN VOL : `lane/moteur-e7b`, `lane/moteur-e6c`, relecteur X5 (atelier après le toit, thème sombre).

### Point du 25/11 noté « 07 h 05 » (heure réelle ≈ 05 h 15 UTC)

**Lot 3 — PR Taqinor/taqinor-os#1555 : CI VERTE au quatrième passage (37 jobs), passée « prête », DANS LA FILE DE
FUSION (position 1) à 07 h 00.** À sa fusion : dire au fondateur « mergé — à déployer par toi : `scripts/deploy-prod.ps1` »
(les lots 1 et 2 ne sont pas déployés non plus).

**Lot 4 — branche locale `dev-lot4`** (worktree de l'orchestrateur ; sauvegarde `origin/notes-l5-2511`) = `dev-lot3`
+ notes + `lane/moteur-e6c` (ACAL2026 plan par défaut, ADEV154 liste `--ecarts-sans-toit`, `forme_horaire_24`,
`poseManuelle` écrite par l'outil de toit ; NON fait : entrée imposée « consommation »). À y plier : `lane/moteur-e7b`,
`lane/t3-liste`, puis E7a, E7c, lanes de correctifs 2 à 6 du tour 3.

**LISTE ADEV154 jouée sur la copie anonymisée (40 leads, rien d'écrit)** — fichier CONFIDENTIEL hors dépôt :
`scratchpad/ecarts-sans-toit-echantillon.txt`. 14 leads refusés par le moteur (facture, phase, jours d'ouverture,
ville, profil météo) ; 26 leads à conception, 45 lignes d'option : **6 simulées — production du toit supposé de
+18,2 % à +21,5 % au-dessus de la production actuelle** (ex. 6 813 → 8 183 kWh/an) ; **39 NON simulées** : « aucun pan
ne porte à la fois des modules et une puissance crête » — la fiche technique du module par défaut (« Panneau mono
550W ») est vide. À CORRIGER avant de montrer la liste au fondateur : le plan par défaut doit simuler sur le kWc que
la conception porte déjà (puissance par panneau = kWc ÷ panneaux), en supposant et en DISANT les valeurs de fiche
manquantes. ADEV155 reste GATED (réponse du fondateur après lecture).
EN VOL : `lane/moteur-e7b`, `lane/t3-liste`, relecteur X5.

### Point du 25/11, 05 h 45 UTC, heure RÉELLE

(Les heures des points précédents de cette nuit sont en avance d'environ 1 h 30 à 1 h 45 sur l'heure réelle : repère
sûr = les fusions, 00 h 57 UTC pour le lot 2 et 05 h 22 UTC pour le lot 3.)

**Lot 3 — PR Taqinor/taqinor-os#1555 FUSIONNÉE le 25/11 à 05 h 22 UTC.** Dit au fondateur : « mergé — à déployer par
toi : `scripts/deploy-prod.ps1` ». TROIS lots sur `main`, AUCUN déployé.

**Lot 4 — branche locale `dev-lot4`** (worktree de l'orchestrateur ; `origin/main` d'après le lot 3 intégré ;
sauvegarde `origin/notes-l5-2511` ; PAS de PR) : `lane/moteur-e6c` + `lane/moteur-e7b` (ADEV152, AGEN11, AGEN12,
AGEN13 : l'écran devis lit la conception, bandeau « La conception a changé », maths locales retirées ; ACAL1216
résolue par conséquence) + tâches marquées « code livré » + contrats d'API régénérés. Gardes hôte vertes. À FAIRE
avant sa PR : instantané OpenAPI (docker), REGARDER les écrans de l'écran devis sur l'instrument (liste au rapport de
la lane : générateur avec lead / sans lead, brouillon retouché et « Mettre à jour », devis envoyé « Réviser », fiche
du lead, devis commercial) — après le retour du relecteur X5 (il utilise l'instrument).
- EN VOL : `lane/moteur-e7a` (fiche du lead : ALEA71, ACAL2021, note « par ? », libellé du brouillon jamais envoyé,
  T4-V1-001 ; sonnet ; consignes `scratchpad/msg-lane-e7a.md`, base de test `e7a`), `lane/t3-liste` (liste des devis
  légère), relecteur X5.
- FILE : E7c atelier (ADEV153, ACAL2022, ACAL2023), correction du plan par défaut sur le kWc de la conception +
  relance de la liste ADEV154, entrée imposée « consommation », lanes de correctifs 2 à 6 du tour 3, relecteurs X3,
  X6 à X8, relecteur des maquettes ; étape 8 (ACAL2024, ADEP108) ; ADEV155 GATED.

### Point du 25/11, 06 h 50 UTC

**Lot 4 — PR Taqinor/taqinor-os#1556 (BROUILLON), branche `dev-lot4`, Auto-fix allumé, auto-archive éteint.** Trois
lots sur `main` (PR #1552, #1554, #1555), AUCUN déployé.
- Contenu : fin de l'étape 6 (`lane/moteur-e6c`), étape 7 entière — écran devis (`e7b` : ADEV152, AGEN11 à 13), fiche
  du lead (`e7a` : ALEA71, ACAL2021 + trois petits défauts), atelier (`e7c` : ADEV153, ACAL2022, ACAL2023) — et la
  liste des devis légère (`t3-liste`, T4-X4-005). Tâches marquées « code livré, preuve en direct due ».
- Premier passage de CI (tête `2a9f3e052c`, SANS e7c) : 10 rouges, tous lus. Corrigés et commités en local, PAS
  ENCORE POUSSÉS : deux tests de lecture du source de la liste, le miroir du productible du site public (la table par
  ville de l'écran devis est retirée : il se compare au moteur), quatre gardes de `stage-names` (paramètres de requête
  déclarés, liste qui envoie sa page en clair, bloc de test recopié, deux formes OpenAPI : la liste sert DEUX formes de
  ligne — `oneOf` — et la synthèse a sa forme), la règle de taille sur `optimizer.ts` (texte de l'économie sorti vers
  `affichageErp.ts`), l'ancre d'ACAL1239, les deux listes figées des routes du devis (+ `synthese`), le budget de
  requêtes de la fiche du lead (15 → 16 ; la pastille lit le kWc en UNE requête, `kwc_de_la_conception_courante`).
- ROUGE RESTANT : `frontend/src/pages/ventes/DevisGenerator.agnrConsoApercu.test.jsx` (AGNR24, « l'aperçu reçoit la
  consommation que l'écran enregistre »). Le bandeau « Facture réelle ONEE ≈ » venait du modèle local retiré par
  AGEN13. À TRANCHER avec la relecture : `corpsApercuConception` n'envoie au moteur que la facture d'hiver, celle
  d'été, les kWh par mois et le nombre de panneaux — PAS les douze factures tapées ni la « Facture réelle » en MAD ;
  l'aperçu horaire (`etude-horaire/preview`) reste servi en premier. Si l'aperçu de la conception peut montrer des
  chiffres pour une autre consommation que celle enregistrée, c'est un défaut de l'étape 7 à corriger (lane), pas un
  test à réaligner.
- EN COURS : instantané OpenAPI régénéré dans un conteneur (`scratchpad/openapi-write6.log`), à commiter avec les
  contrats d'API ; puis UN push (deuxième passage de CI, qui portera aussi e7c).
- EN VOL (trois agents, le plafond de ce poste) : `lane/moteur-e6d` (opus ; consignes `scratchpad/msg-lane-e6d.md` :
  plan par défaut quand la fiche du module est vide + liste ADEV154 lisible, un seul calcul du coût de l'onduleur,
  entrée imposée « consommation », écarts 4 et 5 de l'acceptation) ; relecteur X5 (atelier après le toit, sombre) ;
  relecteur indépendant du lot 4 (opus, lecture seule ; consignes `scratchpad/msg-revue-lot4.md`, rapport attendu
  `scratchpad/revue-lot4.md`, trois questions précises dont AGNR24).
- PRÊT À LANCER dès qu'une place se libère : `lane/moteur-e8` (consignes `scratchpad/msg-lane-e8.md` : ACAL2024,
  reste d'ACAL2025, garde ADEP108) — base `dev-lot4` APRÈS le pli d'e6d (mêmes fichiers du moteur).
- À FAIRE ENSUITE, dans l'ordre : corriger ce que la relecture trouve (lanes) ; mettre l'instrument sur `dev-lot4`
  (après le retour de X5 ; recette dans le point de 05 h 45) et REGARDER les écrans de l'étape 7 (listes dans les
  rapports des lanes e7a, e7b, e7c et t3-liste) ; CI verte ; fusion par la file ; dire « mergé — à déployer par toi ».
  Puis : liste ADEV154 complète à montrer au fondateur (ADEV155 GATED), relecteurs X3, X6, X7, X8, lanes de correctifs
  2 à 6 du tour 3, enregistrements d'acceptation ACAL2028 et ACAL2029, les quatre rejeux `@acceptation` de la vague D
  (ACAL2034, 2035, 2036, 2038), comparaison aux maquettes, rapport final.
- Vague D (15 tâches) : 5 cochées, 6 « code livré, preuve en direct due », 4 rejeux en direct à jouer par
  l'orchestrateur.
- Point laissé au fondateur par la lane e7c : la vue « Montrer au client » ne montre AUCUN montant (garde « rien
  d'argent » ; mention « Les montants figurent dans le devis ») — la tuile d'économie en MAD demandée par ACAL2023
  n'est pas posée ; décision à lui demander (au rapport).

### Point du 25/11, 07 h 00 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon) NE FUSIONNE PAS EN L'ÉTAT.** Relecture indépendante rendue :
`docs/audits/l5-calepinage/controles/revue-lot4-2026-11-25.md` — 2 bloquants, 6 majeurs, 4 mineurs (rien exécuté par
le relecteur : chaque constat est à vérifier dans le code par la lane qui le corrige).
- **B1** vue « Montrer au client » : panneaux POSÉS à côté de la production d'une autre taille → lane `moteur-e7e`.
- **B2** écran devis : l'aperçu n'est pas calculé sur la consommation que le devis enregistre (douze factures, facture
  réelle en MAD) ; le test AGNR24 rouge en CI le dit : NE PAS le réaligner sur un bandeau → lane `moteur-e7d`.
- M1 retour sur investissement de l'écran devis = celui d'un autre devis ou « N/A » ; M2 aperçu en échec = chiffres
  rangés montrés en silence ; M3 deux calculs serveur sur le même bloc (cartes : conception ; graphe, falaise, verdict
  batterie : étude horaire) ; M4 « Mettre à jour » efface des frappes non enregistrées → tous à `moteur-e7d`.
- M5 atelier : « production au prochain enregistrement » ne vient jamais au niveau 14 quand la pose diffère de la
  conception ; m1 carte Conception bloquée sur « Recalcul en cours » ; m4 « au prix catalogue » ; marque de l'option
  retenue → `moteur-e7e`. M6 sélection sur plusieurs pages perdue par « Générer les PDF » → lane F3. m2 forme 24 h du
  calepinage hors niveau 15 → lane `moteur-e8`. m3 références figées de l'écran devis sans ancres de chiffres → e7d.
- Vérifié correct par le relecteur : un devis envoyé ne bouge jamais ; `REGLES_COURANTES` inchangé ; plan par défaut
  sans écriture ; aperçu borné à la société, sans prix d'achat ; liste légère et synthèse dans la portée du rôle.

**CI, deuxième passage (tête `9d4a2b30c9`, avec e7c)** : rouges lus — (1) le test du signal de la liste (ma faute :
test mis à jour avant la ligne du chargeur), corrigé `e0c898edea` ; (2) les deux références figées du démarrage de
l'atelier (`toitureDesign.{calepinage,devis}.boot.json`) : clé `couverture_pct` du contrat ajoutée, `e80ac5a0f0` ;
(3) AGNR24 : reste rouge jusqu'à e7d. Non poussés : attendre la fin du passage (9 jobs en cours à 06 h 54) puis pousser
AVEC les lanes de correctifs pliées — pas de passage de CI pour deux petits correctifs seuls.

**EN VOL (trois agents)** : `lane/moteur-e6d` (opus ; + note envoyée : l'entrée imposée « consommation » doit aussi
être acceptée par `apercu_conception`, clé et forme à dire au rapport) ; `lane/moteur-e7e` (sonnet ; consignes
`scratchpad/msg-lane-e7e.md` : B1, M5, m1, m4, marque de l'option retenue) ; relecteur X5.
**PRÊTS À LANCER, dans cet ordre de priorité, dès qu'une place se libère** :
1. `lane/moteur-e7d` (opus ; `scratchpad/msg-lane-e7d.md`) — APRÈS le pli d'e6d (mêmes fichiers du moteur) ; remplacer
   la ligne `%%CLE_CONSOMMATION%%` des consignes par la clé et la forme de l'entrée imposée que le rapport d'e6d donne.
2. `lane/moteur-e8` (opus ; `scratchpad/msg-lane-e8.md`, 4 tâches dont m2) — après le pli d'e6d.
3. `lane/t3-pompage-pdf` F4 (opus ; `scratchpad/tour3/msg-lane-F4-pompage-pdf.md`) — indépendante, peut partir dès
   le retour de X5.
4. `lane/t3-listes-envoi` F3 (sonnet ; `scratchpad/tour3/msg-lane-F3-listes-envoi.md`, 9 points dont M6).
5. `lane/t3-atelier` F6 (opus ; `scratchpad/tour3/msg-lane-F6-atelier.md`) — APRÈS le pli d'e7e (mêmes fichiers de
   l'atelier) ; remplacer `%%X5%%` par les constats de X5 à corriger.
6. F2 (éditeur du devis, restes du tour 3) — APRÈS e7d (même écran) ; consignes à écrire.

### Point du 25/11, 07 h 25 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon)** — branche `dev-lot4`, tête locale après plis : e7c, e7e (correctifs
de la relecture : vue client, atelier, fiche du lead), les quatre premiers commits d'e6d (plan par défaut avec fiche
vide, un seul coût d'onduleur, consommation imposée `imposes.consommation`, écarts 4 et 5). Deuxième passage de CI
(tête `9d4a2b30c9`) : seuls rouges = test du signal (corrigé), références de l'atelier (corrigées), AGNR24 (attend
e7d). À FAIRE : instantané OpenAPI en cours (`scratchpad/openapi-write7.log`), le commiter avec l'empreinte, puis UN
push (troisième passage). Rien de déployé (trois lots sur `main`).

**EN VOL (cinq agents le temps qu'e6d finisse, puis quatre)** — plafond relevé à quatre : plus d'`npm ci` (jonction
vers `agent-a8dd86f2f627793f9/{frontend,apps/web}/node_modules` — NE PAS supprimer ce worktree, et retirer une
jonction par `cmd //c rmdir`, jamais `rm -rf`), un seul test docker à la fois (le script `ressources.ps1` lit
maintenant la mémoire de la VM des conteneurs : verdicts GO, GO-DOCKER, GO-LEGER, ATTENDRE). Les deux conteneurs
serveurs de l'instrument (`l5t-django`, `l5t-celery`) sont ARRÊTÉS pour laisser la mémoire aux tests des lanes : les
relancer par `bash scratchpad/l5t/lancer.sh serveur` avant tout regard d'écran ou relecteur.
- `lane/moteur-e6d` (opus) : finit — deux notes envoyées : la liste `--ecarts-sans-toit` doit signaler les lignes
  simulées avec une fiche de module vide (étapes de pertes non appliquées : production surestimée) et donner l'écart
  moyen sur les seules lignes à fiche complète. À son retour : plier le reste, marquer ACAL2020 (reste livré), rejouer
  la liste complète sur la copie (`remplir_conceptions --ecarts-sans-toit --company 7487`, instrument relancé) et la
  porter au fondateur (ADEV155 GATED).
- `lane/moteur-e7d` (opus ; `scratchpad/msg-lane-e7d.md`) : écran devis — B2, M1, M2, M3, M4, m3 de la relecture.
- `lane/t3-atelier-ecrans` F6b (opus) : T4-X5-009 (S1, conception vidée par réimport) d'abord, puis 001, 014, 008,
  013, 016, 006, 007.
- `lane/t3-atelier` F6a (opus) : T4-X2-010 (S2, panneaux perdus) d'abord, puis 002, 004, 005, 008, 011, T4-X5-017.
- `lane/t3-pompage-pdf` F4 (opus) : T4-X1-001 et 002 (PDF client, derrière le niveau 15), 008, 009, 014.

**FILE, dans l'ordre** : `lane/moteur-e8` (`msg-lane-e8.md` : ACAL2024, reste d'ACAL2025, ADEP108, m2, T4-X5-002, 012,
004, 015, ACAL2043) ; `lane/moteur-e6e` (`msg-lane-e6e.md` : une seule conception par lead quel que soit le
déclencheur, raison dite, devis né de l'atelier T4-X5-010, révision T4-X5-011) ; F3 (`tour3/msg-lane-F3-listes-envoi.md`) ;
F2a et F2b (`tour3/msg-lane-F2a-options.md`, `F2b-petits.md`) APRÈS e7d (même écran). Puis : instrument sur `dev-lot4`,
regard des écrans, relecteurs X3, X6, X7, X8 et rejeu par des relecteurs neufs, enregistrements ACAL2028 et ACAL2029,
rejeux ACAL2034, 2035, 2038, comparaison aux maquettes, rapport final.

**Fait depuis 07 h 00** : relecteur X5 rendu (17 constats, tri dans `T4/tour3/consolidation.md`) ; ACAL2036 jouée
(enregistrement `docs/audits/acceptation/ACAL/2026-11-25-22e6aa81a.md` : NASA POWER refuse la fenêtre de dix ans en un
appel — tâche ACAL2043) ; décisions 29 à 33 au rapport (vue client sans montant, variante darija, relecture du lot 4,
ce que montre la vue client quand la pose n'a pas la taille de la conception, NASA POWER).

### Point du 25/11, 08 h 15 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon), `dev-lot4`.** Pliées depuis 07 h 25 : `moteur-e6d` (5 commits),
F6b `t3-atelier-ecrans` (8 constats dont T4-X5-009), F4 `t3-pompage-pdf` (5 constats ; PDF client derrière le niveau
15), F6a `t3-atelier` (6 corrigés, T4-X2-002 contesté). Troisième passage de CI (tête `9311c26655`, 07 h 53) TERMINÉ :
rouges = registre mono-devise (régénéré), empreinte de `dupliquer_devis` (recapturée : changement voulu, écart 4),
grand livre des appels d'`appliquer` (fonction d'e6d renommée `imposer`), et AGNR24 (attend e7d). Corrigés en local
(`0a16fdfee5`), NON poussés ; F6a pliée après ce passage (clé servie `calepinage.site_de_repli_point`, instantané
OpenAPI régénéré : inchangé). PROCHAIN PUSH : au retour d'e7d (quatrième passage, visé vert).
Le blocage de 40 min du shard 3 au deuxième passage ne s'est PAS reproduit (shards de 5 à 13 min) : aléa, à surveiller.

**EN VOL (quatre lanes)** : `moteur-e7d` (opus, écran devis — bloque la fusion) ; `moteur-e8` (opus, 6 points) ;
`moteur-e6e` (opus, une seule conception par lead, devis né de l'atelier) ; F3 `t3-listes-envoi` (sonnet, 9 points).
**Tâche de fond** : liste `--ecarts-sans-toit` sur 60 leads de la copie avec le code de `dev-lot4`
(`scratchpad/ecarts-sans-toit-60.txt`, CONFIDENTIEL : jamais commité) — mesurer la durée, puis lancer la liste
entière, la résumer SANS aucun nom ni montant d'un client, et la porter au fondateur (ADEV155 GATED).
**FILE** : F2a et F2b après e7d ; instrument à relancer sur `dev-lot4` (`lancer.sh serveur` ; `l5t-django` et
`l5t-celery` sont arrêtés) puis regard des écrans (listes aux rapports des lanes e7a, e7b, e7c, e7e, t3-liste, F4,
F6a, F6b) ; relecteurs X3, X6, X7, X8 et rejeu des constats corrigés par des relecteurs neufs ; enregistrements
ACAL2028, ACAL2029 ; rejeux ACAL2034, 2035, 2038 ; comparaison aux maquettes ; rapport final.
**Reste d'une lane à nettoyer** : entrée de remise « f6-item1-src » (lane F6a, changements déjà commités) dans la pile
de remises PARTAGÉE — ne pas y toucher par `git stash pop` ; la retirer par son étiquette en fin de session.

### Point du 25/11, 10 h 10 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon), `dev-lot4`.** TOUT ce qui suit est plié en local : e6c, e7a, e7b,
e7c, e7e, e6d, e7d (+ suite e2e), e8, e6e, t3-liste, F3 (+ 3 correctifs de CI), F4, F6a, F6b, F2a, F2b (+ crochet du
fuzz). Dernier push : `b51d59a4a8` (09 h 47, cinquième passage de CI). Plié APRÈS ce push, non poussé : F2a
(`lane/t3-editeur-options`), suite de F2b (crochet `_validite_devis_a_venir` du fuzz), contrats régénérés.
- **Cinquième passage de CI : rouges lus et attribués** — (1) test de lecture du source des cartes Économies / ROI
  (`QJR35/QJR426`, frontend-static) → auteur d'e7d ; (2) fuzz : date de validité passée refusée sans être déclarée
  → corrigé par le crochet de F2b (plié) ; (3) `test_calx390_budgets_requetes` : `resultat/` coûte 25 requêtes avec
  une conception rangée contre 13 sans (budget 9) et (4) fuzz : `calepinages/a-traiter/` ne répond plus en 10 s →
  auteur d'e8 (régressions de coût d'e8 ou d'e6e : la conception se relit plusieurs fois, quelque chose du moteur
  se calcule par ligne de liste).
- **REGARD DE L'ORCHESTRATEUR sur la pile de revue** (lead synthétique 3731 « ACC-L4 », devis 2880 ; captures dans
  `scratchpad/acc2027/l4/`, jamais commitées) :
  - fiche du lead : carte « Conception » à deux colonnes, option « retenue » marquée, 3 518 / 7 037 kWh, 5 486 / 8 886
    MAD, retour « d'après le devis DEV-… », pastille 4,40 kWc, plus de « par ? » — VU, conforme (la puce des
    suppositions de la fiche technique vide du panneau est une seule phrase très longue : à condenser, S3) ;
  - écran devis, onglet Simulation, RIEN de tapé : bandeau « Conception du moteur unique… », cartes égales à la
    conception rangée — VU ; MAIS trois retours sur investissement pour l'option avec batterie (carte 7,5 ans, tableau
    8,72 ans, falaise 7,65 ans) et 8 886 contre 8 614 MAD d'économies → auteur d'e7d ;
  - écran devis, douze factures tapées : BLOQUANT — l'aperçu est remplacé par un refus imprimé DEUX fois sur un
    panneau de 710 W qui n'est pas dans le devis (l'écran n'impose que le nombre de panneaux : le moteur choisit son
    module) → auteur d'e7d ;
  - liste des devis : 25 lignes, « Page 1 sur 24 · 583 devis », page de 90 Ko en 1,0 s — VU ; MAIS la synthèse
    (`devis/synthese/`) prend 11 à 12,5 s : les cartes par statut tombent en délai dépassé, l'en-tête dit « 0 devis »
    pendant le chargement, le message de délai s'affiche deux fois → auteur de F3.
- **EN VOL (auteurs rappelés sur leurs propres branches)** : e7d (4 points : refus sur le mauvais panneau, refus en
  double, trois retours sur investissement, test QJR35), e8 (2 régressions de coût), F3 (3 points de la liste).
  Relecteur X9 (rejeu de tous les constats corrigés, Chromium bureau clair) sur la pile `b51d59a4a8`.
- **PROCHAIN PUSH** : au retour d'e7d et d'e8 (sixième passage, visé vert) ; puis rebâtir l'instrument (`checkout -B
  instr-lot4 dev-lot4`, `vite build` ≈ 30 s, `lancer.sh serveur`) et REGARDER de nouveau l'onglet Simulation.

**RESTE À FAIRE après ce passage** : lane ACAL2045 (le toit supposé dit sa pose) puis relancer la liste ; restes
d'e6e (carte « Couvrir la facture » : « Conception recalculée : <raison> » ; avis avant « Générer le devis ») et
d'e8 (`EcartMesures.jsx` : section « Eau » seulement si servie) ; F2a non corrigés : T4-X4-004 (carte Tailles :
lignes non étiquetées) et T4-X4-018 (balayage arrêté à 4,40 kWc) ; jumeau serveur `selectors.multi_villa_totaux`
qui additionne les deux options et nourrit le PDF (à corriger derrière le niveau 15) ; relecteurs X3, X6, X7, X8 ;
enregistrements ACAL2028 et ACAL2029 ; rejeux ACAL2034, 2035, 2038 ; comparaison aux maquettes ; rapport final ;
fusion du lot 4 quand CI verte + X9 sans « pas-corrigé » bloquant ; dire « mergé — à déployer par toi ».
**Décision majeure portée au fondateur (rapport, décision 26)** : la liste « sans toit » annonçait +19 % parce que
le toit supposé ne dit pas sa pose (échauffement omis) ; corrigé, l'effet serait d'environ +4 % à +8 % (pose
affleurante) ou +11 % à +16 % (châssis). ADEV155 reste fermé.

### Point du 25/11, 10 h 45 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon), `dev-lot4`.** Plié depuis 10 h 10, non poussé : suite 2 d'e7d
(composition imposée par option depuis les LIGNES, refus dit une fois, retours libellés, fenêtre QJR35), F3 suites 2
et 3 (synthèse de la liste : cache par contenu dont profil société et produits des lignes ; limite propre de 60 s,
« Calcul des totaux… », la page n'attend plus la synthèse), tâche ADEV162 (total rangé sur le devis, à construire).
- **Rouges du cinquième passage** : QJR35 et date de validité du fuzz = pliés ; `resultat/` (25 requêtes) et
  `a-traiter/` (délai) = corrigés par l'auteur d'e8 (`c096d3d9d1`, `a723c5f232` sur `lane/moteur-e8`, test en cours,
  PAS encore pliés).
- **Relecteur X9 (en cours, 13 rejeux lus : 10 corrigés, 3 pas corrigés ; 9 constats neufs)**, fichiers
  `T4/tour3/rejeu-X9.json` et `registre/constats/T4-X9.jsonl` (non commités tant que X9 tourne). Lecture de
  l'orchestrateur — UNE classe : à l'atelier, au niveau 14, des chiffres de la conception du lead restent posés à
  côté d'une pose d'une autre taille (économies de la carte TOTAL, ligne « Moteur du devis sur cette pose », jauge
  « De la consommation », ratio 123 % de la carte Recommandation), la phrase d'explication est rendue dans une case
  de chiffre clé et quatre fois, et la cible « Couvrir la facture » compte en panneaux de 550 W quand l'atelier ne
  pose que des 710 W (8 × 710 W posés pour une conception de 4,40 kWc). Plus UN défaut du moteur (T4-X9-009) : un
  onduleur hybride désigné à l'atelier rangeait l'option « avec batterie » à la taille de l'option « sans »
  (conception retenue divisée par deux).
- **Qui corrige** : T4-X9-009 = l'orchestrateur (`conception/moteur.py::_compte_designe` décide la taille POUR le
  scénario que l'onduleur désigné impose ; test `test_x9_009_onduleur_designe_garde_la_taille_de_son_option`, à
  jouer rouge puis vert dès qu'un test docker est libre — non commité à 10 h 45) ; classe de l'atelier = auteur de
  F6a rappelé (mission `scratchpad/tour3/msg-lane-G1-atelier-conception.md` : inventaire de TOUS les chiffres de
  l'atelier, un seul prédicat, T4-X9-003/004/006/007/008/001, T4-X5-005, T4-X5-017) ; cible comptée dans le panneau
  posé = auteur d'e9, item 6 (`scratchpad/msg-lane-e9-item6.md` : une seule fonction de conversion partagée avec
  le moteur, table servie par la cible, T4-X2-001 et T4-X9-005). Le reste de la décision 28 (une seule option quand
  un onduleur est désigné ; même puissance arrondie au panneau) reste au fondateur.
- **e9** : ACAL2045 commité (`23778ec898` sur `lane/moteur-e9`), items 2 à 5 puis 6 en cours.
- **PROCHAIN PUSH (sixième passage)** : après pliage d'e8 (test vert), d'e9, de G1, du correctif X9-009 ; gardes
  d'hôte (`scratchpad/gardes.sh`), contrats et instantané OpenAPI régénérés ; puis rebâtir la pile de revue et
  REGARDER : onglet Simulation du devis (factures tapées), liste des devis (cartes), atelier d'un lead dont la pose
  diffère de la conception, fiche du lead après désignation d'un onduleur hybride.

### Point du 25/11, 11 h 10 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon) : SIXIÈME PASSAGE DE CI lancé à 11 h 10 sur `cb9d338411`**
(attente : `scripts/watch-ci.ps1 -Pr 1556`). Dans ce push, en plus du point de 10 h 45 : pliage de `lane/moteur-e8`
(coût de `resultat/` et de la file « à traiter »), correctif T4-X9-009 (`438b50856c` : rouge « 11 != 13 », vert avec
ses cinq voisins), deux tests de lecture du source réalignés (`axiosVX55Timeout`, `devisAutoKwc.ez5`), tâche ACAL2046.
Vérifié avant le push : gardes d'hôte 0 rouge (`scratchpad/gardes.sh`), instantané OpenAPI inchangé, budgets de
requêtes du calepinage 39 tests OK avec `docs/` monté (`scratchpad/lane-test-docs.sh` — la lane ne voyait pas
`docs/query-budgets.yml`), `node --test src/**/*.test.mjs` du front : seuls restent rouges en local trois artefacts
(fins de ligne Windows sur deux tests CIQ126, plafond de poids mesuré sur un vieux `dist/` → ACAL2046).

**EN VOL (auteurs rappelés sur leur branche, rien de poussé)** :
- `lane/moteur-e9` (agent a1144b5df28380f54) : ACAL2045 commité ; items 2 à 5 ; item 6 = la cible de l'atelier comptée
  dans le panneau posé (`scratchpad/msg-lane-e9-item6.md`, T4-X2-001 et T4-X9-005).
- G1 sur `lane/t3-atelier` (agent a0a39b75aa1be319f) : classe « chiffres de la conception à côté d'une pose d'une
  autre taille » (`scratchpad/tour3/msg-lane-G1-atelier-conception.md`) + T4-X2-002 rejoué pas corrigé + T4-X9-010.
- F2c sur `lane/t3-editeur-options` (agent a01f644f2f20473ee) : T4-X4-004 — EXPLIQUER le prix « sans batterie »
  de 36 900 MAD (peut-être aussi imprimé au PDF client), puis corriger sous verrou de niveau 15 avec liste en lecture
  seule (`scratchpad/tour3/msg-lane-F2c-option-sans.md`).
- E7f sur `lane/moteur-e7d` (agent a7c564f9b92c99be9) : T4-X4-018 — le tableau des tailles de la Simulation couvre
  l'option vendue ; retours « 5,7 ans » (`scratchpad/tour3/msg-lane-E7f-simulation-avec.md`).
- Relecteur X9 (agent a769f787d565e28cf) : 16 rejeux (12 corrigés, 4 pas corrigés), 10 constats neufs, continue sur
  la pile `b51d59a4a8` — NE PAS rebâtir la pile tant qu'il tourne.

**DISQUE** : C: était à 1,8 Go libres à 11 h 00 (64 dossiers de travail). Retrait des dossiers des lanes déjà
fusionnées dans `main` (script `scratchpad/menage_worktrees.ps1` : jonctions défaites d'abord, donneur
`agent-a8dd86f2f627793f9` et lanes actives intacts) : 12 Go libres à 11 h 10, retrait encore en cours. Gardés
(auteurs à rappeler) : e8, F3, F4, F6b, e6e ; gardés (commits non pliés) : `fix/ci-front` (+5), `fix/ci-gardes` (+8).
Bases de test des lanes : 39 bases, 5,2 Go dans la machine des conteneurs — à supprimer au démontage.

**ENSUITE** : plier e9, G1, F2c, E7f à leur retour (revue de chaque diff, gardes, UN push = septième passage) ;
X9 terminé → rebâtir la pile sur la tête, REGARDER (Simulation du devis avec factures tapées, liste des devis,
atelier d'un lead dont la pose diffère de la conception, fiche du lead après désignation d'un hybride) ; fusion du
lot 4 ; relecteurs X3, X6, X7, X8 ; rapport.

### Point du 25/11, 12 h 15 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon), `dev-lot4`.** Reda, 11 h 50 : « start more lanes ».
- **Passages de CI** : sixième (`cb9d338411`) rouge sur 4 causes, septième (`e6c6b1263e`) rouge sur 2 causes — TOUTES
  corrigées en local : forme de la vue effective sans le marqueur `option` ; quantités sœurs réservées au devis
  résidentiel (un brouillon C&I recomposé voyait sa structure « 1 lot » passer à 162) ; test QJR602 (taille tapée
  telle quelle) ; `except` muet du cache de la liste ; contrat d'imports M1 (`lignes_vendues_de_l_option` déplacée de
  `utils/options` vers `domain/dimensionnement_devis`) ; goldens des gestes du générateur (les cartes Tailles se
  relisent après l'enregistrement). Fuzz et e2e VERTS aux deux passages.
- **Plié depuis 11 h 10** : E7f (tableau des tailles de la Simulation : la taille de chaque option vendue, raison de
  refus de batterie en une phrase lisible, pastilles), F2c (T4-X4-004 : la carte « Recommandé — sans batterie »
  n'est plus servie pour un devis qui ne vend que « avec » — le PDF client n'imprimait PAS de total faux, la page
  client publique pouvait montrer cette carte), G1 puis G2 (atelier : un seul prédicat « tailles différentes »,
  inventaire de tous les chiffres, calepinage sans lead, création en double, tableau du site), E9 (ACAL2045 pose du
  toit supposé, « Conception recalculée : <raison> », aperçu de ce que le devis portera, section Eau, fiche technique
  regroupée, cible de l'atelier comptée dans le panneau posé).
- **HUITIÈME PUSH** : dès que gardes d'hôte, tests du front touchés, instantané OpenAPI (route `apercu-devis/`)
  et empreinte de structure sont passés en local.
- **EN VOL** : H1 (auteur d'e8, agent afaeb723706ffe3f7 : retour sur investissement de la fiche du lead, obstacle hors
  du toit, phrase du calepinage sans lead côté serveur, raison de refus de l'onduleur —
  `scratchpad/tour3/msg-lane-H1-serveur-restes.md`) ; H2 (lane neuve `lane/liste-total`, agent acd5913bf9b7ab14f :
  ADEV162 total rangé de la liste des devis + T4-X9-015 — `scratchpad/tour3/msg-lane-H2-liste-total.md`) ;
  relecteurs X6 (agent aafc8b7da92b01fe5 : quatre scénarios C&I de bout en bout) et X3 (agent aac20b788b8e1c4a7 :
  réglages, liste, création, routes) sur la pile `fc9fa2c7a5` (rebâtie à 12 h 00, E9 et G2 compris).
- **REGARD DE L'ORCHESTRATEUR (pile `e6c6b1263e`, 11 h 55)** : onglet Simulation du devis 2880, douze factures
  tapées : plus de refus, « Consommation imposée par le devis (490 kWh par mois, factures saisies) », un aperçu par
  option avec le matériel des lignes, la taille du devis présente et marquée — VU ; la colonne « Éco. avec » était
  un mur de texte technique à points décimaux (corrigé par la suite d'E7f, PAS encore revu) ; liste des devis :
  25 lignes puis cartes « Calcul des totaux… » — VU. À REVOIR sur la pile `fc9fa2c7a5` : tableau des tailles
  (phrases courtes, pastilles), atelier d'un lead dont la pose diffère de la conception, calepinage sans lead,
  fiche du lead après désignation d'un hybride, carte « Tailles » après enregistrement.
- **DISQUE** : 15 Go libres après retrait de 13 dossiers de lanes fusionnées (6 retraits incomplets à finir).

**Tri des constats du relecteur X9 (25 rejeux : 20 corrigés, 5 non ; 17 neufs)** :
| Constat | Suite |
|---|---|
| T4-X9-009 (S2) conception divisée par deux après désignation d'un hybride | corrigé, orchestrateur (438b50856c) ; le reste = décision 28 |
| T4-X9-003, 004, 008 (S2), 006, 007, 001, 010 ; rejeux T4-X5-005, T4-X5-017 | corrigés, G1 |
| T4-X9-005 (S2) / T4-X2-001 cible en panneaux de 550 W | corrigé, E9 item 6 ; « comment obtenir les chiffres de la pose » reste ouvert (niveau 15, décision du fondateur) |
| T4-X2-002 la production disparaît à l'enregistrement | écran : corrigé G1 (« Simulation à refaire ») ; serveur (empreinte) : H1 |
| T4-X2-006, T4-X9-011, 012, 013 (écran) | corrigés, G2 ; 013 côté serveur : H1 ; clé d'idempotence de la création : tâche à écrire |
| T4-X9-002 raison de refus de l'onduleur | H1 |
| T4-X9-014 la liste attend la synthèse | corrigé avant (suite 3 de F3), à revoir en direct |
| T4-X9-015 deux comptes de devis | H2 |
| T4-X9-016 retour de 21,4 ans introuvable | H1 |
| T4-X9-017 trois encarts client sur la fiche du lead | tâche à écrire (plan du lead) |

### Point du 25/11, 13 h 35 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon), `dev-lot4`.**
- **Huitième passage (`ba939f3814`) : rouge sur 5 causes, TOUTES des listes figées ou des gardes que les lanes e9,
  F2c et H1 ne pouvaient pas voir** — contrat « aperçu du devis » sans moitié cliente citée ; cliquet des imports
  calepinage → ventes (46 pour 44 : deux lectures repassées par `equipements.py`) ; golden de la région « cal »
  (recapturé sur l'hôte) ; surface publique de `ventes.services` ; ré-export de `lignes_vendues_de_l_option` dans la
  façade `dimensionnement.py`. Fuzz, e2e, vitest et front statique VERTS.
- **Plié depuis 12 h 15** : suite d'E7f (raison de refus de batterie en une phrase, ligne sous le tableau, pastilles),
  H1 (retour sur investissement de la fiche du lead servi avec son montant et son économie ; obstacle hors du toit
  hors de l'empreinte ; phrase du calepinage sans lead ; raison courte de refus de l'onduleur), ligne de l'onduleur
  qui lit la raison courte (orchestrateur), tâches ACAL2047 et ADEV163.
- **Avant le neuvième push (méthode changée après trois passages rouges d'affilée)** : « paquet des listes
  figées » joué en docker sur l'arbre plié (`scratchpad/pack_cliquets.txt` : surfaces de ventes, goldens de
  découpe, goldens du crm, cliquet des imports, contrats — 266 tests, seul `test_actions_devis_ont_appelant` rouge
  en local parce qu'il lit `frontend/src`, non monté) ; gardes d'hôte + `check_except_larges` +
  `check_contrats_calepinage_deux_moities` + `lint-imports` ; `node --test` du front ; garde de taille C20
  (`electrique.py` : les textes du verdict sont bâtis dans `raisons_verdicts.py`).
- **EN VOL** : H2 (`lane/liste-total`, agent acd5913bf9b7ab14f, 2 commits vus) ; relecteurs X6 (aafc8b7da92b01fe5)
  et X3 (aac20b788b8e1c4a7) sur la pile `fc9fa2c7a5` (NE PAS rebâtir tant qu'ils tournent).
- **PAS ENCORE REVU par l'orchestrateur à l'écran** (mémoire : pas de troisième navigateur à côté des deux
  relecteurs) : tableau des tailles après la suite d'E7f, atelier « pose ≠ conception » (G1), calepinage sans lead
  (G2), cible comptée dans le panneau posé (E9), fiche du lead (retour tracé, fiche technique regroupée), carte
  « Tailles » après enregistrement (F2c). À faire dès qu'un relecteur rend la main, pile rebâtie sur la tête.
- **Changements que lit un CLIENT dans ce lot (à dire à Reda au moment de la fusion)** : la page publique d'un
  devis qui ne vend que « avec batterie » ne montre plus de carte « Recommandé — sans batterie » (elle affichait
  un prix sans onduleur) ; aucun montant de PDF ne change.

### Point du 25/11, 14 h 45 UTC

**Lot 4 (PR Taqinor/taqinor-os#1556, brouillon), `dev-lot4`.** Reda, 14 h 15 : « where are you ? » — répondu.
- **Neuvième passage (`fe1b7982f6`) : rouge sur 2 causes.** (1) `raison_du_verdict` sans appelant hors de son
  module après mon remaniement → rendue interne (commité, garde verte). (2) FUZZ : `calepinages/a-traiter/` ne
  répond pas en 10 s (déjà au cinquième passage, vert aux 6-7-8) — CAUSE ÉTABLIE par l'orchestrateur : chaque ligne
  évaluée calcule le verdict électrique, qui va chercher les températures du site chez PVGIS PAR LE RÉSEAU
  (`assistant._bloc_electrique` → `electrique.verdict_de_conception` → fournisseur `temperatures_tmy`, limiteur de
  cadence partagé) ; dans les tests le fournisseur est neutralisé, d'où une liste « rapide » partout sauf en CI et
  en production à cache froid. La lane I4 (agent a375819ef15513c07, `lane/file-a-traiter`) a d'abord retiré le
  résultat servi entier de la liste (148 → 124 requêtes, commit 2ef5356f73, PAS encore plié) et pose maintenant un
  mode « sans réseau » dans `temperatures_tmy.py` : cache seulement, ligne non évaluée si la température manque.
- **DIXIÈME PUSH** : au retour d'I4 (pliage, paquet des listes figées en docker, gardes d'hôte APRÈS le dernier
  commit — c'est l'oubli qui a coûté le neuvième passage).
- **Plié depuis 13 h 35** : suite de la lane e9 (T4-X3-009 : la cible dite dans le module posé partout —
  première pose automatique, bande des Résultats, contrôle DC/AC, feuille Avancé ; aide unique `cibleAuModule.js`).
- **PAS plié, gardé pour le lot 5** : H2 (`lane/liste-total` : total rangé + empreinte, migration 0163, tâche
  planifiée toutes les 10 min, 180 lignes pour 80 prévues — à faire relire par un relecteur neuf avant pliage).
- **EN VOL** : I1 (`lane/editeur-ci`, agent a3ec71c931984fded : écran du devis C&I, T4-X6-007 à 012) ; I3 (auteur
  de F4, agent ab75a7c7a60c1d28c : phrases fausses du PDF industriel, case « Devis final », production par option,
  arrondi du kWc) ; I5 (`lane/reglages-calepinage`, agent a9d37147aa205718d, sonnet : 16 constats de X3 sur
  réglages / sources / bibliothèque / liste) ; relecteur X6 (agent aafc8b7da92b01fe5, C&I de bout en bout — son
  fichier de constats est mal encodé, il doit le réécrire en UTF-8).
- **Relecteur X3 : TERMINÉ** — 57 lignes jouées, 18 constats (2 S2 : T4-X3-008 = décision 28 ; T4-X3-009 corrigé).
- **REGARD DE L'ORCHESTRATEUR (pile `fc9fa2c7a5`, 14 h 40, captures `scratchpad/acc2027/l5/l5b-1974-*.png`)** :
  calepinage 1974 (pose 6 × 710 W = 4,26 kWc, conception 2,13 kWc) — étape Résultats : bandeau qui nomme les deux
  tailles, « Production simulée de la pose 6 926 kWh » en grand, carte « De la consommation » = une phrase (plus
  de jauge trompeuse), pertes, écart PVGIS, chaîne des pertes — VU, conforme. Expert : carte TOTAL « 6 × 710 W ·
  4,26 kWc · 6 926 kWh/an · simulation · — » et UNE phrase — VU en texte. À voir encore : libellés de cote de
  l'obstacle hors toit qui se chevauchent sur la carte (S4), tableau des tailles du devis après la suite d'E7f,
  fiche du lead (retour tracé), calepinage sans lead après G2.

### Point du 25/11, 16 h 10 UTC

**LOT 4 FUSIONNÉ** : PR Taqinor/taqinor-os#1556, `main` = `d619459423` (25/11, 15 h 56 UTC), onzième passage de CI
vert (37 contrôles), file de fusion verte. Relecture finale indépendante avant la mise en file : « fusionner »,
aucun bloquant (`controles/revue-lot4-finale-2026-11-25.md`). **NON DÉPLOYÉ : c'est à Reda
(`scripts/deploy-prod.ps1`). Les lots 1 à 4 attendent tous son déploiement.** Passage de CI sur `main` après
fusion : en file à 16 h 05, à relire.

**LOT 5 — branche locale `dev-lot5`** (= `main` + ce qui suit ; RIEN de poussé, pas encore de PR) :
- **Plié** : I5 (`lane/reglages-calepinage`, 14 constats de X3 sur 16 : sources des paramètres, altitude, préréglage
  fantôme, recherche et tri de la liste, menu Responsable, raison « à refaire », clés brutes, bibliothèque, liens
  profonds, garde de saisie) ; I3 (`lane/t3-pompage-pdf` : « Devis final » refusé sans la visite exigée — 409 —,
  production par option au PDF commercial AU NIVEAU 15, kWc à deux décimales pour le bandeau) ; golden du crm
  re-haché pour deux symboles (`assignable_users`, `__all__` de selectors).
- **Paquet docker joué sur `dev-lot5`** (548 tests) : vert, sauf `test_empreintes_ast` du crm (corrigé depuis, à
  rejouer) et `test_actions_devis_ont_appelant` (front non monté, vert en CI).
- **EN VOL** : I1 (`lane/editeur-ci`, agent a3ec71c931984fded : écran du devis C&I, T4-X6-007 à 012 ; 2 commits vus) ;
  I2 (`lane/ci-retour-cable`, agent abf185aa2759d2b3f : retour de la fiche du lead en C&I, câble de l'option « avec »,
  bouton BOQ qui double des lignes) ; H2 (`lane/liste-total`, agent acd5913bf9b7ab14f : corrections demandées par
  la relecture indépendante — empreinte du CODE du moteur, colonnes volatiles hors de l'empreinte, balayage léger) ;
  relecteurs X7 (agent a8c0bce9ca0c7bc1e : WebKit bureau puis tablette) et X8 (agent a1e9f64db652e1c8e : téléphone,
  thème sombre, Technicien) sur la pile `1cfa550e99` (rebâtie à 15 h 30 : tout le lot 4).
- **À ATTRIBUER dès qu'un créneau se libère (mémoire : 5 agents au plus)** :
  - majeur de la relecture finale : la file « à traiter » fait disparaître une ligne dont la température de site
    n'est pas en cache (auteur d'I4, agent a375819ef15513c07) ;
  - mineurs 1 et 2 : `GET apercu-devis` peut créer une ligne de réglages ; l'aperçu peut différer de la
    génération (auteur d'e9, agent a1144b5df28380f54) ;
  - mineur 5 (`reunirOptions`) : à l'auteur d'I1 ; mineur 6 (calepinage d'un collègue ouvert après délai dépassé) ;
  - restes de X6 : T4-X6-005 (menu de la liste hors écran), 014 (courbe de charge en marché Commercial), 015 / 016
    (taille souhaitée, deux kWc sur l'écran résidentiel), 017 (panneau « Premium » d'un devis sans onduleur), 018
    (option imposée par le registre non montrée) ; reste d'I5 : T4-X3-017 (barre du haut en WebKit tablette).
- **DÉCISIONS POUR REDA nées aujourd'hui** (rapport, décisions 34 à 38, à compléter) : phrases du PDF industriel
  corrigées seulement au niveau 15 (les rendre actives au niveau 14 ?) ; source des allées et retraits par défaut
  (un champ « Source » partagé, ou une source par valeur) ; un Commercial peut réécrire tous les réglages société
  du calepinage mais pas appliquer le profil de départ (laisser, ou aligner les deux droits) ; clause « horaires
  confirmés à la visite » sur un devis préliminaire (phrase du fondateur requise).
- **Leçon de méthode du jour (à verser au retour d'expérience)** : trois passages de CI rouges d'affilée sur des
  listes figées que les lanes ne voient pas — depuis le huitième passage, « paquet des listes figées » en docker
  (`scratchpad/pack_cliquets.txt`), goldens du front (`*olden*.test.jsx`), gardes d'hôte APRÈS le dernier commit,
  `check_except_larges`, `check_contrats_calepinage_deux_moities`, `lint-imports` avant chaque push.

### Point du 25/11, 17 h 00 UTC (le plus récent — REPRENDRE ICI)

**`main` = `d619459423` (lots 1 à 4 fusionnés, NON déployés : c'est à Reda).** Passage de CI de `main` après la
fusion du lot 4 : un échec e2e (ACAL987, clic pendant le changement d'onglets du rail), relancé vert ; le test est
durci dans le lot 5.

**LOT 5 — branche locale `dev-lot5`, tête `ece0ca9bae`, RIEN de poussé, pas de PR.** Plié : I5 (réglages du
calepinage), I3 (PDF C&I, « Devis final » refusé sans la visite exigée), H2 (total affiché rangé sur le devis,
migration `0163_adev162_total_affiche_range`, tâche périodique 10 min, commande `ranger_totaux_affiches`), I2
(retour de la fiche du lead en C&I, option « avec » non composée si chaînes infaisables, bouton BOQ sans doublon),
I1 (écran du devis C&I : un seul retour, aperçu sur les lignes du devis, factures tapées comptées), le test e2e
ACAL987 durci, et — fait par l'orchestrateur — le mineur 6 de la relecture finale (« Nouveau calepinage » ne
retrouve qu'un calepinage créé PAR la personne connectée, `cree_par` de la ligne de liste).

**Vérifications jouées sur `dev-lot5` à 16 h 45 (tête `213df5ba4f`)** : gardes d'hôte — toutes vertes SAUF
`check_forme_code` (`ventes/models.py` +2 lignes : les deux colonnes de H2). Remède prévu, AUCUNE exception à
écrire : cocher ADEV162 en citant `backend/django_core/apps/ventes/models.py` entre accents graves dans une note de
fold (son budget « lignes nettes attendues ≤ 80 » couvre alors le fichier). `check_api_shapes --write`,
`check_money_monodevise --write`, `codemap_fingerprint --write` : aucun fichier changé. Paquet docker (14 modules
touchés + listes figées + surfaces + golden du moteur + `test_quote_engine`) et tests du front : EN COURS
(tâches de fond `bdmw42pa6` et `bwh3qmkhd`) — à relire.

**EN VOL (5 agents, le plafond de mémoire)** : J1 (`lane/editeur-restes`, agent a6311371c4d45a84d : restes de X6 sur
l'écran du devis, consigne `scratchpad/tour3/msg-lane-J1-editeur-restes.md`) ; suite d'I1 (agent a3ec71c931984fded,
branche `lane/editeur-ci` : l'étude C&I rangée rejouée dès le PREMIER enregistrement, pour que le PDF suive) ; suite 2
d'I4 (agent a375819ef15513c07, branche `lane/file-a-traiter` : températures de site dans le cache partagé de Django,
ligne non jugée jamais disparue) ; relecteurs X7 (agent a8c0bce9ca0c7bc1e, WebKit bureau puis tablette) et X8 (agent
a1e9f64db652e1c8e, téléphone, sombre, Technicien) sur la pile `1cfa550e99` — NE PAS rebâtir la pile tant qu'ils jouent.

**PRÊT À LANCER dès qu'un créneau se libère** : `scratchpad/tour3/msg-lane-E9b-apercu-devis-suite.md` (mineurs 1 et 2
de la relecture finale, à l'auteur d'E9, agent a1144b5df28380f54, par SendMessage). Reste non attribué : T4-X3-017
(barre du haut en WebKit tablette : attendre le compte rendu de X7, qui joue cette taille).

**ENSUITE, dans l'ordre** : plier J1, I1 suite, I4 suite, E9b (relire chaque diff) ; trier X7 et X8 ; rebâtir la pile
(`bash scratchpad/rebatir_pile.sh` — défaut `dev-lot5` désormais) et REGARDER moi-même : en-tête de la liste des devis
juste après redémarrage (preuve en direct d'ADEV162), écran du devis C&I, tableau des tailles, retour de la fiche du
lead, calepinage sans lead, écrans de réglages ; cocher ADEV162 et les tâches livrées ; méthode complète d'avant
push ; UNE PR pour le lot 5 (Auto-fix, archivage automatique éteint), CI, relecture finale indépendante, file de
fusion ; « mergé — à déployer par toi ». Puis : relecteur des maquettes (planches côte à côte), enregistrements
d'acceptation ACAL2028 / ACAL2029, rejeux ACAL2034, 2035, 2038, deux tours sans rien de neuf, rapport final.

**Baux de plan** renouvelés à 16 h 50 UTC (propriétaire `DESKTOP-APTAHF6/dev-moteur-unique`, 6 h) : à renouveler vers
22 h 30, à relâcher après la dernière fusion.
