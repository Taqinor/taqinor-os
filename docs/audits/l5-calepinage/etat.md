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
   EN VOL (23/11 05 h 10 UTC) : `F2-POSE-b`, `F2-CONSO`, `F2-ELEC-b`, `T2`.
   RESTE A LANCER : `F2-SIMU-b` (compte `rev_b7`), puis un verificateur de RATTRAPAGE (compte `rev_b8`) pour les
   preuves non jouees — les 10 de `S2-PARCOURS-b` (ACAL874, 875, 877-880, 883-885, 888), ACAL833, ACAL767, ACAL738,
   ACAL703, ACAL712 et toute simulation restee bloquee avant 04 h 40 —, puis `B2` EN DERNIER.
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
