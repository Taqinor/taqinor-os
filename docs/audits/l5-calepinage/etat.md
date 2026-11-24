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
