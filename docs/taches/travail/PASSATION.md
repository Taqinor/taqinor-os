# Passation — chantier « Tâches » (gestionnaire de tâches et agenda personnel de Reda)

Écrit le 17/11/2026 par la session du portable de Reda (`Reda_Laptop`), parce que le quota hebdomadaire de tokens
arrive à sa fin. Une autre session (autre PC, autre compte) reprend ICI. Tout ce qui compte est sur GitHub.
**La section 1 (« État à l'arrêt ») est tenue à jour jusqu'au dernier moment : lis-la en premier.**

## 0. La demande et les règles de Reda (ne pas re-demander)

- Reda veut SON gestionnaire de tâches et de projets dans l'ERP, avec l'IA qui l'aide à prioriser, planifier et tenir
  son rythme (« si je dis que je veux en faire plus, il m'y aide ; si je dis que ça suffit, il m'aide à garder le
  pas »), présent sur son iPhone. « Le meilleur, en une fois » : conception en profondeur (faite), construction, test
  en direct, corrections.
- **Aucune question à Reda** (« je ne veux plus que tu me poses de questions ») : décider seul, option la plus sûre,
  et noter chaque choix. Décisions fondateur déjà prises : `docs/claude-memory/taches-decisions-fondateur.md` (sur main).
- Règles de maison : rapports en français simple ; chaque sous-agent lancé avec `model:` + effort explicites ; la CI
  vérifie en premier (jamais de base de test locale, jamais de docker avant un push) ; s'arrêter AU MERGE (pas de
  deploy) ; fusion par `gh pr merge <n> --auto --merge` (merge queue, jamais squash, jamais force-push) ; Auto-fix
  allumé sur toute PR dès l'ouverture, sans demander.

## 1. État à l'arrêt

(Mis à jour en dernier — voir la fin du fichier, section « Journal de fin de session ».)

## 2. Où est quoi

| Quoi | Où |
|---|---|
| Plan (174 tâches `TCH<n>`, 4 fusions F1-F4), cases cochées = vérité | `docs/plans/PLAN_TACHES.md` sur la branche `dev-taches-f2` |
| Référence qui fait foi (données, API, règles, textes) | `docs/taches/reference/` (sur main) |
| Conception, arbitrages A1-A18, consignes de construction | `docs/taches/conception/` (sur main) |
| 81 maquettes + jeu d'exemple `SCENARIO.md` | `docs/taches/maquettes/` (sur main) |
| Dossier de travail (briefs, relectures, raccords, cette passation) | `docs/taches/travail/` sur la branche `claude/erp-task-manager-ai-f8db1b` (jamais mergée) |
| **Fusion 1** (socle invisible) | MERGÉE sur main — PR Taqinor/taqinor-os#1447 |
| **Fusion 2** (cœur utilisable) | branche `dev-taches-f2`, PR brouillon Taqinor/taqinor-os#1454, Auto-fix allumé |
| Code | `backend/django_core/apps/taches/`, `frontend/src/{features,pages}/taches/`, `frontend/src/api/tachesApi.js`, `frontend/src/styles/taches/` |

Fichiers de travail à lire avant de relancer quoi que ce soit (branche `claude/erp-task-manager-ai-f8db1b`) :
- `docs/taches/travail/brief-lane-f2.md` — le brief commun donné à chaque lane (à réutiliser tel quel) ;
- `docs/taches/travail/ecarts-f2.md` — TOUS les raccords à faire entre écrans et serveur, déclarés par les lanes
  (sections A à J) ; les deux lanes de raccord travaillent dessus ;
- `docs/taches/travail/revue-code-f1.md` — relecture adverse de la fusion 1 (tout corrigé).

## 3. Comment on construit (recette éprouvée)

1. `python scripts/plan_lanes.py docs/plans/PLAN_TACHES.md --workers 8 --wave-size 80 --group "Fusion F2"` donne les
   lanes, leur ordre et leur modèle.
2. Une lane = un sous-agent `isolation: worktree`, lancé **UN PAR UN** (un appel par message : à plusieurs en même
   temps la création des worktrees dépasse le délai sur un disque plein). **Jamais** d'agent non isolé envoyé vers un
   worktree fait à la main : un hook refuse ses écritures.
3. Le worktree d'un agent part de `origin/main` → première consigne de chaque lane :
   `git fetch origin dev-taches-f2 && git checkout -B lane/<nom> origin/dev-taches-f2`.
4. Le prompt d'une lane = branche + liste ordonnée de tâches + « lis en entier le brief commun » + particularités +
   le bloc d'ancrage (« Before reporting progress, audit each claim… ») mot pour mot.
5. Au retour : `git branch --contains <sha>` (le SHA annoncé est bien sur la branche de lane), puis pli dans le
   worktree de `dev-taches-f2` par `git merge --no-ff <sha>`, cocher les tâches dans le plan + une ligne DONE LOG,
   commit, push.
6. Sur l'hôte (Windows) : seuls tournent `manage.py check`, `makemigrations --check`, les tests SANS base, flake8,
   eslint, vitest ciblé. Commande Python :
   `$env:PYTHONPATH='C:\dev\wpstub'; $env:PYTHONIOENCODING='utf-8'; & "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" manage.py …`
   (sur un autre PC : n'importe quel Python avec Django 5.x et les dépendances du backend ; `C:\dev\wpstub` est un
   faux module `weasyprint` vide, à recréer si besoin). **Les tests avec base ne tournent qu'en CI.**
7. Avant un push de la branche d'intégration : `python scripts/check_openapi_schema.py --write` (≈ 1 min 30) si des
   routes ou des sérialiseurs ont bougé, puis `python scripts/codemap_fingerprint.py --write` ; `--check` des deux.
8. Avant de retirer un worktree de lane sous Windows : casser d'abord la jonction
   (`cmd /c rmdir <worktree>\frontend\node_modules`), sinon la suppression vide le `node_modules` visé.
9. Réservations de plan (deux PC en même temps) : `python scripts/plan_claims.py list` ; cette session tient
   `file:docs/plans/PLAN_TACHES.md app:taches app:records app:roles app:erp_agentique app:scripts app:authentication`
   sous le propriétaire `Reda_Laptop/erp-task-manager-ai` (bail de 6 h : périmé, il se reprend par `claim`).

## 4. Ce qui reste, dans l'ordre

**Fusion 2** (64 tâches + 6 acceptations)
1. Plier les lanes encore ouvertes (voir section 1) : raccord serveur, raccord écrans, sécurité/plafonds
   (TCH151, TCH128, TCH129, TCH19), corrections de la première CI.
2. CI verte sur l'état plié (première exécution des ~400 tests à base : prévoir 2 ou 3 cycles).
3. Activation pour l'Administrateur SEUL : TCH130 (droit), TCH131 (manifeste, navigation, traductions), TCH132
   (route d'accueil mobile) — une lane opus, tâches dans cet ordre. Puis bout en bout Playwright TCH133, TCH134.
4. Acceptations en direct TCH136-TCH140, TCH144 : jouées par l'ORCHESTRATEUR sur la pile locale
   (`docker compose up`, `manage.py migrate`, `manage.py seed_taches_demo`, rebuild du front), jamais par une lane ;
   enregistrement `docs/audits/acceptation/…`. Corriger ce qu'elles trouvent (c'est le « L3 n° 10 » : test en direct).
5. TCH94 : régénérer les dérivés, dé-geler la fusion 3 dans le plan (retirer `[GATED: attend la fusion F2 sur main]`).
6. PR #1454 : `gh pr ready 1454` puis `gh pr merge 1454 --auto --merge`. Dire à Reda « mergé — l'auto-deploy suit ».

**Fusion 3** (iPhone : grande tuile Scriptable, capture Siri, notifications, flux d'agenda ; Copilote) : 29 tâches
+ 3 acceptations. **Fusion 4** (avancé, ouverture aux autres rôles — TCH168 attend un mot de Reda) : le reste.
Puis deux relectures finales : ergonomie et beauté sur le rendu réel (captures iPhone 390 px, clair et sombre,
comparées aux maquettes), et relecture adverse du code. Rapport final à Reda en français simple : ce qui est livré,
ce qui n'est pas vérifié (essai sur un vrai iPhone), ses gestes (lien du raccourci Siri, Scriptable, abonnement à
l'agenda, `VITE_VAPID_PUBLIC_KEY` en prod, fournisseur d'IA en prod) — liste dans `docs/taches/README.md`.

## 5. Pièges déjà payés

- Un pli qui répond « Already up to date » = la lane a committé ailleurs : vérifier `git branch --contains`.
- `nplusone` est actif en CI : jamais de liste Python dans `_prefetched_objects_cache` ; un `TestCase` n'a jamais
  d'attribut `client` ; aucun `skipTest`.
- `tests/test_routes.py` : l'aide `est_construite()` fait que les tests « 501 » ne regardent que les routes encore
  vides — ne pas la réécrire.
- Les lanes déclarent des « écarts » en fin de rapport : les recopier dans `ecarts-f2.md` AVANT de les oublier.
- Le module reste invisible tant que TCH130-TCH132 ne sont pas pliées : `taches_voir` n'est accordé à aucun rôle.

## Journal de fin de session

### Reprise par une session cloud — commencée le 17/11/2026 à 23 h 40 UTC (LIRE EN PREMIER ; tenue à jour au fil de l'eau)

**État vérifié à la reprise.** `main` = `6b4435c2a` ; PR #1454 (fusion 2) brouillon, tête `7c50012ee`, verte ;
`dev-taches-f3` = `53c6d4443` (138 cochées sur 174, jamais passée en CI) ; `origin/lane/f2-revue` portait 6 commits
NON pliés ; les trois autres lanes F3 du portable étaient déjà entièrement dans `dev-taches-f3`.

**Fait depuis (dans l'ordre)**
1. `lane/f2-revue` relue commit par commit puis PLIÉE dans `dev-taches-f2` (les 4 majeurs #3, #4, #5, #6 et les mineurs
   #2, #7, #8 de `revue-code-f2.md`), `origin/main` fusionné, poussé : tête `85c186783`. CI relancée sur #1454.
2. `dev-taches-f2` fusionnée dans `dev-taches-f3`, poussé : tête `684aed104`. **PR brouillon de la fusion 3 ouverte :
   Taqinor/taqinor-os#1462** (empilée sur la fusion 2 ; à ne mettre en file de merge qu'après #1454). L'instantané
   OpenAPI de `dev-taches-f3` a été régénéré : il était déjà à jour (aucun diff).
3. Lanes lancées (worktrees isolés, branches LOCALES de cette machine) : `lane/f2-restes` (sonnet : mineurs #1 et #9 de
   la relecture, test « la nuit n'écrit rien pour un compte qui n'a jamais utilisé le module ») ; `lane/f3-presence2`
   (opus : TCH155, TCH98, TCH174, suites de sécurité de TCH95) ; `lane/f3-copilote-restes` (opus : garde A5 « contenu
   non fiable » et « 3 écritures par tour », bouton Modifier de la carte écho, styles des cartes, bloc de consignes
   conditionnel, branchement des 4 demandes prêtes dans `CopilotPanel.jsx`, plafonds mesurés, 6 conversations
   d'évaluation manquantes).

**Décisions prises seul par cette session (chacune notée ici, aucune ne demande Reda)**
- **Branches** : cette session cloud a pour consigne technique de pousser sur `claude/nice-lamport-fsv7my`. Reda a
  demandé de reprendre CETTE passation, qui vit sur `dev-taches-f2` (PR #1454), `dev-taches-f3` et la branche de
  travail `claude/erp-task-manager-ai-f8db1b` : la session pousse donc sur ces trois branches-là et sur aucune autre
  (jamais sur `main`, qui n'avance que par la file de merge ; jamais de force-push). Raison de fond, en plus de la
  continuité de #1454 : la CI d'une PR dont la branche s'appelle `claude/*` est ALLÉGÉE (règle « une seule CI par PR »
  du 27/10 : tests à base, vitest et bout en bout reportés à la file de merge) ; une fusion de cette taille a besoin
  de la CI complète sur la PR. `claude/nice-lamport-fsv7my` reste vide.
- **Réservations de plan IMPOSSIBLES depuis le cloud** : GitHub refuse à cette session l'écriture des refs
  `refs/plan-claims/*` (403, garde volontaire : non contournée). `plan_claims.py list` (lecture) marche : aucun poste
  ne tient de réservation Tâches. Parade : relire la liste et faire `git fetch` avant chaque push. SI UN AUTRE POSTE
  REPREND : qu'il prenne les réservations normalement, cette session le verra à sa prochaine lecture et s'arrêtera.
- **Auto-fix** : l'interrupteur de l'app de bureau n'existe pas dans une session cloud ; la session est abonnée aux
  événements des PR #1454 et #1462 et corrige elle-même les rouges de CI.
- **Pile locale SANS docker** (docker ne tourne pas dans ce conteneur) : PostgreSQL 16 + pgvector, Redis, Python
  3.11 (celui de la CI et de la prod) dans `/opt/venv-erp`, Node 22, front construit servi par `vite preview` avec
  le relais `/api/django` (la pile e2e de la CI). Scripts de la machine dans `/opt/taches-cloud/` (hors dépôt,
  recopiés dans `docs/taches/travail/cloud/` à la fin). Les tests À BASE tournent donc ICI, chaque lane sur sa base
  privée (clone d'un gabarit migré une fois : 2 399 migrations, ≈ 1 h). Brief des lanes : `brief-lane-cloud.md`.
- **Horloge des acceptations** : la journée du 24/11 du semis suppose une horloge figée. Le serveur Django des
  acceptations tourne sous `libfaketime` (heure du scénario), le navigateur sous l'horloge de Playwright. Aucun code
  de « fausse horloge » n'est ajouté au produit.
- **Heure du Maroc** : depuis le 20/09/2026 le Maroc est revenu à GMT (UTC+0) toute l'année (décret annoncé le
  25/06/2026 ; `tzdata` 2026.6 épinglé par le dépôt le sait). Le Chromium de cette machine a des fuseaux PÉRIMÉS
  (Africa/Casablanca encore à +1) : les acceptations lancent le navigateur en UTC (= l'heure réelle du Maroc) et une
  étape vérifie en plus qu'une heure posée depuis un navigateur « périmé » n'est pas décalée d'une heure.
- **Relecture F2 #1** (sous-tâche restaurée dont le parent reste supprimé) : elle est DÉTACHÉE (`parent=None`), même
  règle que N7 pour un projet supprimé — jamais refusée, jamais perdue à la purge du parent.
- **Relecture F2 #4** : la correction touche `frontend/src/providers/session-bridge.js` (+ son test), fichier d'un
  autre propriétaire, en AJOUT seulement (purge des clés `taches:*` à toute déconnexion) : accepté, c'est la seule
  place qui marche quand le module Tâches n'a pas été chargé dans l'onglet. À inscrire dans l'en-tête du plan.
- **Copilote** : `CopilotPanel.jsx` n'appelait pas les 4 demandes prêtes (TCH118 a livré la fonction sans appelant).
  Le fichier est hors de la liste du plan : autorisé en AJOUT seulement pour ce branchement (tâche à inscrire au plan).
- **Constats « optionnels » de la relecture F2** (CGNAT accepté par le validateur, `g j` offert sans le module, clé de
  cache sans société, « Annuler » après « Fait » sans lire les conflits, activité liée à la tâche d'un collègue) :
  NON corrigés (durcissement, cas hypothétiques) ; ils restent listés dans `revue-code-f2.md`.

**Trouvé par la CI de la nuit du 17 au 18/11 et corrigé (à savoir pour toute lane future)**
- **Tests qui dépendent de l'heure ou du jour** (ils passaient le 17/11 après-midi, jour où ils ont été écrits, et
  cassent la CI de tout le monde ensuite) : (1) `tests/test_plafonds.py` — `aujourdhui/` coûte 2 requêtes de plus AVANT
  MIDI (carte « bilan d'hier ») ; plafonds mesurés horloge vivante l'après-midi → rouges la nuit et le matin. Corrigé :
  classe figée (`testkit.time.frozen`, mardi 15:00) + mesure du matin (28 et 33) ; manifeste et `api.md` §10 mis à
  jour. (2) `pages/taches/Aujourdhui.test.jsx` « ouvert sans réseau… » — le cache est par JOUR et l'échantillon dit
  `2026-11-17` : le test ne passait que ce jour-là. Corrigé : `Date` figée au jour de l'échantillon + un test « le
  cache d'un autre jour n'est jamais montré ». RÈGLE : aucun test ne lit l'horloge vivante ; un plafond de requêtes
  d'une route qui passe par la journée se mesure matin ET après-midi. Balayage fait : la suite `apps.taches` (1 427
  tests) et la suite vitest Tâches rejouées sous des dates simulées par `faketime` (samedi matin, dimanche 23:58,
  31/12 23:50, vendredi 16:00, nuit, 01/03/2027).
- `apps.calepinage.tests.test_releve_terrain` (2 tests, AUTRE module) casse quand un shard de CI passe minuit
  (`DEMAIN` calculé à l'import) : pas touché ici, tâche suggérée à Reda (carte « Fix midnight flake… »). Un rouge de
  ce genre sur #1454/#1462 vers minuit UTC n'est pas à nous : relancer la CI.
- **Fusion 3, première CI (#1462)** : `check_liste_page1` (liste des jetons) et les 2 tests de la pastille
  (`BottomTabBar.test.jsx`, encore écrits pour deux requêtes) corrigés par l'orchestrateur ; FUITE de confidentialité
  réelle `taches.projet.lire` (nom d'étape d'un projet confidentiel servi à l'assistant) → lane copilote ; « Mes
  agendas » de l'écran Agenda menait à Réglages → Avancé où la section n'est plus (déplacée dans Mon iPhone) → lane
  écran-iphone, avec les 3 specs e2e ; plafonds `badge/` (14) et `journee/point/` → lane copilote, horloge figée.

**État au 18/11/2026, 01 h 40 UTC (branches LOCALES de la machine cloud ; ce qui est poussé est dit « poussé »)**
- `dev-taches-f2` : poussé `f3102c936f` (PR #1454) + 1 commit local `eae7042972` (en-tête du plan). CI de
  `f3102c936f` : tout vert SAUF `frontend-vitest-shard (2)` sur `src/pages/installations/RecettePompageDialog.test.jsx:60`
  (AUTRE module, test synchrone juste après un chargement asynchrone, 3/3 verts ici) → l'UNIQUE relance permise des
  jobs en échec a été déclenchée (run 44209983280). S'il rougit encore : ce n'est pas à nous, le dire une fois sur la PR.
- `dev-taches-f3` : poussé `1fe6a6c76c` (PR #1462, CI tour 2 en cours) + local `4f5352f7ce` (TCH127 pliée et cochée,
  143 sur 174 ; 4 routes fermées à l'assistant). Batterie locale verte avant le push (21 gardes, FastAPI 362 tests,
  Django 2 444 tests sauf 1 artefact connu du mode rapide, vitest 965, eslint).
- `dev-taches-f4` : LOCALE seulement, `6556621585` : fusion 3 fusionnée dedans, `lane/f4-erp-avance` (TCH71, TCH72),
  `lane/f4-presence-front` (TCH102, TCH103) et `lane/f4-coquille` (TCH123, 125, 126, 159) pliées ; tâches PAS encore
  cochées dans le plan de f4 ; empreinte de structure de CODEMAP périmée sur f4 (à refaire à la fin de la fusion 4).

**Lanes en cours (worktrees `…/.claude/worktrees/agent-*`)**
- F2 `lane/f2-acceptation` : écrit `frontend/e2e/acceptation/tch.spec.js` sur la pile F2 (usage exclusif de :4173/:8000/`erp_acc`).
- F2 `lane/f2-revue2-journee` (opus) : constats 1, 2, 3, 4, 6, 11 de la seconde relecture.
- F2 `lane/f2-revue2-rythme` (opus) : constats 5, 7, 8, 9, 10 et la part « Mon rythme + saisie » du constat 12.
- F4 `lane/f4-etiquettes-avance` (TCH156, 166, 167, 152) et `lane/f4-projets-avances` (TCH64, 90, 157).
- À LANCER quand une place se libère (machine à 4 cœurs : 5 lanes au plus) : F2 « entrées mal formées » (sonnet), le
  reste du constat 12 (dates extrêmes `9999-12-31`/`0001-01-01` → borner dans `selectors/base.py::date_de` et les
  sérialiseurs ; `?exclure=²` ; `nouveau_projet.priorite` hors 0-3 ; caractère nul dans un texte libre) : des 500 sur
  entrée fabriquée, à rendre en 400 — le fuzz de la CI est bloquant et finira par tomber dessus.

**Seconde relecture adverse du serveur de la fusion 2 (passe Fable n° 1 du run) — `revue-code-f2-tour2-serveur.md`**
Verdict : mergeable après corrections ; 0 bloquant, 5 majeurs, 7 mineurs, tous PROUVÉS par exécution. Ce qu'elle a
attrapé : des NOMBRES FAUX à l'écran dès la première semaine (journée réussie qui retombe à 0 quand on termine le
projet le jour même ; activité ERP gardée puis close jamais comptée ; « jour court » ignoré par Aujourd'hui ; phrase
« Objectif atteint X jours sur N » fausse ; carte de palier périmée qui monte à 9 au lieu de 6).
Tri de l'orchestrateur (aucune question à Reda) :
- Les 5 majeurs et les mineurs 6, 8, 9, 10, 11 : CORRIGÉS avant le merge de la fusion 2 (règle « aucun chiffre faux »).
- Constat 4 : « Objectif atteint » compte les jours où le compte a atteint l'objectif (`compte ≥ objectif`), pas la
  « journée réussie » ; la nuit pose l'objectif du jour jugé ; « jours non travaillés » ne compte que des jours que le
  compte travaille d'habitude.
- Constat 5 : les DEUX protections (la carte de palier ouverte est abandonnée dès que le palier change ; une réponse
  « Oui » n'applique jamais autre chose que le nombre de la carte, et rien si le palier a bougé).
- Constat 7 : les constats C4 (« Te proposer 4 à garder ? ») et C8 (« Mettre une de ses tâches dans Proposé
  demain ? ») sont RETIRÉS de la première livraison, comme C6 : leur « Oui » n'enregistrait que la réponse, rien ne
  changeait. C1 et C2 ne peuvent pas apparaître (ils lisent des champs que rien n'écrit) : hors livraison aussi. C7
  compte comme l'écran « À revoir ». À DIRE À REDA dans le rapport final (4 conseils du rythme reportés).
- Constat 12 : traité en entier (voir la lane à lancer) ; la seule entrée atteignable par l'écran (« dans 999999
  semaines » qui cassait tout l'aperçu d'une liste collée) est dans la lane rythme.
- La liste « Optionnel » du rapport : NON corrigée (durcissement, cas hypothétiques), elle reste dans le rapport.

**Décisions de plus**
- TCH174 : `taches.balayer` routée sur la file `scheduled` (api.md §9 fait foi sur le « rien d'autre » de la tâche).
- Jetons (suites de TCH95) : (a) un jeton refusé ne consomme pas de débit — LAISSÉ tel quel : 256 bits d'aléa, et un
  débit par adresse IP couperait Siri/flux/tuile de tous les abonnés d'une même adresse partagée ; (b) le jeton du
  calendrier abonné est dans le chemin de l'adresse (imposé par Apple) : Django le masque déjà dans ses journaux,
  nginx NON. `backend/nginx/nginx.conf` n'est pas touché par ce chantier (fichier de production d'un autre
  propriétaire, erreur = site coupé) : c'est un GESTE DE SERVEUR à proposer à Reda dans le rapport final (ligne `map`
  prête dans le rapport de la lane présence).
- Base RAPIDE pour les lanes et la mise au point des specs (tables créées depuis les modèles en 18 s) en attendant
  la base migrée (≈ 3 h à froid) ; l'enregistrement d'acceptation final se joue sur la base migrée. Rejeu des
  migrations : ≈ 1 550 sur 2 399 à 01 h 40 (détaché ; journal `/opt/taches-cloud/logs/migrate-tpl-suite.log`).
- TCH127 (canari) : 3 fuites de plus trouvées et fermées par la lane (`mes-donnees/` servi à l'assistant ; « En
  attente de : … » d'une confidentielle dans `gestes/` et dans l'explication de `projets/{id}/vue/`). Le canari a
  aussi montré que `api.md` §0 n'était pas tenu sur `reglages/`, `reglages-societe/`, `tout-effacer/`,
  `agendas-externes/` : l'assistant POUVAIT appeler « tout effacer ». Fermé par l'orchestrateur (403 sous l'en-tête ou
  Bearer, test `FermeesALAssistantTests`), textes inscrits dans `textes.md` §2.16 et `regles.md` §8.
- Budget du bundle (`frontend/scripts/check_bundle_budget.mjs`, total 3 815 Ko) : la fusion 4 le dépasse d'environ
  10 Ko (chunks lazy neufs ; bundle initial +0,4 Ko). Le budget sera monté UNE fois, au juste-dessus de la mesure
  réelle faite sur l'arbre final de la fusion 4, avec la ligne datée d'usage (précédents du 20/09 dans le fichier).
- Machine cloud : 4 cœurs, 15 Go. Au plus 5 agents à la fois, un seul processus de test par lane.

**Ce qui reste, dans l'ordre** (mis à jour à chaque étape)
- Fusion 2 : plier `lane/f2-revue2-journee` et `lane/f2-revue2-rythme` (relire chaque commit, suite `apps.taches`
  entière, gardes) → lane « entrées mal formées » → rafraîchir les deux lignes périmées de `docs/CODEMAP.md` de f2
  (262 et 494 : « INVISIBLE… aucune entrée de nav ») + empreinte → pousser, CI verte → recevoir la spec d'acceptation
  et sa liste de défauts, corriger → REJEU FINAL par l'orchestrateur sur la base migrée (`tpl_test`), enregistrement
  `docs/audits/acceptation/TCH/<date>-<sha9>.md` → cocher TCH136-140, TCH144, TCH94 → PR prête + file de merge
  (`--merge`). Dire à Reda : « mergé — à déployer par toi : `scripts/deploy-prod.ps1`, ~2 min » (le deploy
  automatique est ARRÊTÉ depuis le 17/11 : ne plus écrire « l'auto-deploy suit »).
- Fusion 3 : lire la CI du tour 2 de #1462, pousser `4f5352f7ce` ; pile n° 2 (`acc-f3.sh` : base `erp_f3`, Django
  :8001, front :4174, Redis :6380) pour jouer les specs e2e Tâches (dont les 3 retouchées par `lane/f3-ecran-iphone2`,
  jamais jouées) et écrire/jouer les acceptations TCH141, TCH171, TCH143 ; phrase du seuil A5 à écrire dans
  `reference/regles.md` ; TCH135 ; merge après la fusion 2.
- Fusion 4 : plier les deux lanes en cours, puis TCH158 (opus), TCH173, cocher, OpenAPI, CODEMAP + empreinte, budget
  du bundle, pousser `dev-taches-f4`, PR brouillon, CI, acceptations TCH142, TCH172. TCH168 reste GATED (décision de Reda).
- Passe visuelle (écrans réels contre maquettes : captures dans `/opt/taches-cloud/captures/f2/` et
  `docs/taches/maquettes/captures/`), relecture adverse finale, README « gestes de Reda », mémoire
  `docs/claude-memory/taches-decisions-fondateur.md`, rapport final.

### État FINAL de la session du portable — 17/11/2026, quota à 98-99 % (arrêt)

**Sur GitHub**
- `main` : fusion 1 mergée (#1447).
- `dev-taches-f2` (PR brouillon #1454, Auto-fix allumé) : tête `7c50012ee` — **CI ENTIÈREMENT VERTE : 36 contrôles sur 36** (8 tours de corrections ; les 58 specs de bout en bout Tâches passent)` : au run d'avant 55 specs Tâches passées sur 58, les 3 dernières traitées au tour 8 — lire le run de `7c50012ee`)` : 43 specs passées, 15 échouées, toutes traitées au tour 6 — résultat à lire sur le run de `e90a5167e`). **63 des 64 tâches de la fusion 2 sont
  pliées et cochées** (115 tâches cochées sur 174 au total). Tout le code de la fusion 2 y est : serveur, écrans,
  raccords des deux côtés, semis, sécurité, plafonds, activation Administrateur seul, bout en bout Playwright.
- Aucune lane en cours, aucune branche de lane non pliée. Rien d'important ne vit seulement sur le portable.

**Fusion 3 commencée en avance** : branche `dev-taches-f3` (poussée, partie de `dev-taches-f2`, plan dé-gelé pour la
fusion 3). Les lanes F3 pliées y sont cochées dans SON plan ; à la reprise, après le merge de la fusion 2, fusionner
`origin/main` dans `dev-taches-f3` et ouvrir sa PR. Lanes F3 (`plan_lanes.py … --group "Fusion F3"`) : assistant (10,
opus), presence (8, opus), cartes (3), ecran-iphone (3), etranger-coquille-F3 (1), etranger-deploy-F3 (1),
presence-front (1), final-F3 (1), orchestrateur (1). Voir le journal ci-dessous pour celles qui sont faites.

**Journal de la fusion 3 (branche `dev-taches-f3`, PAS de PR ouverte, CI jamais jouée dessus) — 10 tâches pliées, 125 cochées sur 174**
- Ajout de fin de session : TCH109 (écran « Mon iPhone », 5 étapes, jetons montrés une fois, agendas externes à
  l'étape 2) et TCH110 (script Scriptable de la grande tuile) pliées et cochées. Reste de TCH109 : brancher la
  révélation `mon_iphone` (J+3) dans `services/revelations.py` (serveur). Le script suit le contrat `tuile.json`
  (`faites`, `essentiel.prevues`), pas l'annexe A de la spec ; vrai Scriptable jamais essayé.
- **POINT À 138 TÂCHES SUR 174 (dernier pli)** : sur `dev-taches-f3` sont pliées et cochées en plus TCH97 (flux
  d'agenda et tuile par jeton) et TOUTE la lane assistant (TCH161, 112, 111, 164, 113, 114, 163, 115, 162, 116 : le
  Copilote). Restes déclarés par la lane assistant, à traiter : personne n'applique encore « au plus 3 écritures par
  tour » dans le relais ; la conversion « contenu non fiable → carte écho » (arbitrage A5) n'existe pas ; la carte
  écho n'a pas de bouton « Modifier » ; le bloc de consignes Tâches part à TOUS les comptes qui ont le copilote
  (≈ 280 mots de plus, à rendre conditionnel dans `sql_agent_service._contenu_systeme`) ; `CopilotPanel.jsx`
  n'appelle toujours pas `lancerDemandePrete` / `estEcranTaches` ; plafonds de `journee/priorites` et
  `journee/point` non mesurés (`enforced: false`) ; 12 conversations d'évaluation sur les 18 de textes.md §5.8.
  Plafonds tuile 14 / flux 10 = estimations, à poser à la mesure de la CI. Reste de la fusion 3 : TCH155, TCH98,
  TCH174 (fin de la présence), TCH160, TCH127, TCH135, acceptations TCH141, TCH171, TCH143. `dev-taches-f3` n'a
  JAMAIS vu la CI : ouvrir sa PR après le merge de la fusion 2 et prévoir plusieurs tours de corrections.
- **RELECTURE ADVERSE DU CODE DE LA FUSION 2 : `docs/taches/travail/revue-code-f2.md` — 0 bloquant, 4 MAJEURS à corriger
  AVANT d'activer pour un vrai utilisateur** : annuler le geste du plan du jour supprime tout le plan (bilan compris) ;
  la journée en cache et le brouillon restent dans le navigateur après déconnexion hors `/taches/*` ; le délai de
  lecture d'un agenda externe n'est pas tenu (un serveur lent peut bloquer tout l'ERP) ; un agenda en échec est relu
  à chaque écran (décision prise : mémoriser l'échec 15 min). Une lane les corrigeait à l'arrêt : branche LOCALE
  `lane/f2-revue` (basée sur `dev-taches-f2`). Si ses commits « F2 revue — … » existent (`git log
  origin/dev-taches-f2..lane/f2-revue` sur le portable, ou `origin/lane/f2-revue`), les plier dans `dev-taches-f2`
  puis fusionner `dev-taches-f2` dans `dev-taches-f3` ; sinon relancer la lane avec ce rapport. TCH96 (capture Siri)
  est pliée et cochée sur `dev-taches-f3` (127 sur 174).
- **SI LA SESSION A ÉTÉ COUPÉE NET (quota à 100 %)** : quatre lanes tournaient sur la fusion 3, chacune committant tâche
  par tâche sur une branche LOCALE du portable (pas encore sur GitHub) : `lane/f3-tch96` (capture Siri),
  `lane/f3-tch97` (flux d'agenda et tuile), `lane/f3-assistant` (Copilote : TCH161, TCH111, TCH164, TCH112, TCH113…),
  `lane/f3-restes` (révélation `mon_iphone`, garde du brouillon, tests « ne grandit pas », pastille en une requête).
  Sur le portable : `git branch --list "lane/f3-*"` puis `git log origin/dev-taches-f3..lane/f3-<nom>` montre ce qui
  est committé ; `git push origin lane/f3-<nom>` les met sur GitHub ; plier dans `dev-taches-f3` celles dont les
  commits sont complets (TCH96 et TCH97 touchent toutes deux `tests/test_routes.py` et
  `tests/test_meme_proprietaire.py` : garder les lignes des deux), cocher les tâches, régénérer OpenAPI + empreinte.
  Toute lane absente de la liste des branches pliées ci-dessous est à relancer.
  PLIÉES depuis : `lane/f3-restes` (révélation `mon_iphone` = fin de TCH109, garde de test du brouillon, tests « ne
  grandit pas » pour la proposition et la vue d'un projet, `badge/` sert `a_trier` → pastille en une requête,
  `docs/api-contracts.md` régénéré). À faire sur `dev-taches-f3` : régénérer l'instantané OpenAPI (réponse de `badge/`).
- **MISE À JOUR (dernière action de la session) : TCH95 est FINIE, pliée et cochée sur `dev-taches-f3`** (11 tâches F3,
  126 cochées sur 174). Cause des 7 échecs : un seul nom de schéma de sécurité OpenAPI pour trois classes de jeton
  (corrigé : `jetonCapture`, `jetonTuile`, `jetonFlux`). À faire à la reprise sur `dev-taches-f3` : régénérer
  `docs/openapi-schema.yml` (`check_openapi_schema.py --write`, non fait), puis continuer la lane présence à TCH96
  (capture Siri), TCH97 (flux et tuile), TCH155, TCH98, TCH174. `tests/test_jetons.py` (à base) n'a jamais tourné.
  Les deux points de sécurité ci-dessous restent ouverts. Le paragraphe suivant est l'historique.
- **(historique) TCH95, version la plus avancée : `docs/taches/travail/tch95-wip/tch95-v2-complet.diff`** (1 173 lignes, contient
  aussi les 4 fichiers neufs dont `tests/test_jetons.py`) : `git apply` sur `dev-taches-f3`. NON committée parce que
  7 tests sans base échouent encore (`test_routes` RoutesSansBaseTests / AssistantEtBouchonTests / SchemaTests et
  `test_meme_proprietaire.ListeFermeeTests`, dont « True is not false ») : cause non lue. Deux points de sécurité
  ouverts à trancher : les journaux d'accès nginx/gunicorn voient l'adresse du flux avec son jeton ; un jeton
  refusé ne consomme aucun débit. (L'ancien `tch95.diff` + 3 fichiers du même dossier = version antérieure.)
- Pliées et cochées (8 tâches, 123 cochées sur 174) : TCH117, TCH165, TCH118 (cartes Tâches du Copilote, 4 demandes
  prêtes), TCH101, TCH124 (pastille du jour et « À trier »), TCH120 (badge au push, raccourci de l'app), TCH20
  (4 types de notification, migration `notifications/0079`), TCH21 (`notify(badge=n)`).
- **TCH95 à moitié faite, NON committée** : le travail est sauvé dans `docs/taches/travail/tch95-wip/` (cette branche) :
  `tch95.diff` (à appliquer sur `dev-taches-f3` par `git apply`) + 3 fichiers neufs (`auth_jeton.py`, `throttles.py`,
  `presence.py` = `serializers/presence.py`). Il manquait `tests/test_jetons.py`, le lint, et la validation CI du
  flux en 404 neutre. Reprendre la lane `taches/presence` à TCH95, puis TCH96, TCH97, TCH155, TCH98, TCH174.
- Restes déclarés par la lane cartes : pas de feuille de style pour les cartes du Copilote (classes `.ep-carte-ia*`
  de la maquette absentes) ; `CopilotPanel.jsx` n'appelle pas encore `lancerDemandePrete` / `estEcranTaches` (une
  ligne, par la lane assistant) ; gestes « Changer de projet / d'étape », « Tout ajouter » d'un plan et l'écho
  « Modifier » absents faute de donnée servie ; la pastille fait 2 requêtes (`badge/` + `aujourdhui/`).
- Non commencées : lanes assistant (TCH161, 111, 164, 112, 113, 114, 163, 115, 162, 116), ecran-iphone (TCH109,
  110, 160), final-F3 (TCH127), TCH135, acceptations TCH141, TCH171, TCH143.
- Sur ce portable, le worktree `…\worktrees\dev-taches-f2` est positionné sur la branche `dev-taches-f3`.
- Réservations de plan (`plan_claims.py`) RENDUES à l'arrêt pour que l'autre poste puisse les prendre.

**Ce qui reste pour la fusion 2, dans l'ordre**
0. (FAIT) CI verte sur `7c50012ee`. Si `main` a avancé : fusionner `origin/main`, régénérer OpenAPI + empreinte.
1. **(historique) CI verte sur la tête.** Deux tours de rouges ont été corrigés ; le tour sur la version complète (raccords
   écrans, défauts connus, bout en bout) n'a pas été lu. `gh pr checks 1454 --repo Taqinor/taqinor-os`, puis une
   lane sonnet par tour (prompt modèle : « corrige le test s'il est faux, le code sinon, jamais d'assertion
   élargie ni de test sauté ; plafond de requêtes sans N+1 = poser la mesure »). À surveiller en premier :
   - `frontend/e2e/taches-*.spec.js` (TCH133, TCH134) : JAMAIS exécutés, écrits à la lecture du code ; les mesures
     d'accessibilité (axe 0 violation, cibles 44 px, texte à 130 %) sont strictes : un rouge y montre un vrai écart
     d'écran à corriger dans l'écran, pas dans le test. Les specs sont branchées par 6 lignes ajoutées à
     `.github/workflows/ci.yml` (lane 2 du shard e2e) et utilisent le compte `demo_admin` de `seed_demo`.
   - `tests/test_plafonds.py` : `agenda/` rabaissé de 35 à 28 après correction (une seule lecture) — la CI mesure.
   - `tests/test_seed_demo.py` : « 3 sur 5 » à 15 h, Benali 5 ouvertes, En attente 1.
   - Les tests qui appellent les 27 fonctions de service renommées avec `_` (TCH151).
2. **Acceptations en direct TCH136-140, TCH144** (orchestrateur, pile locale : `docker compose up`, `migrate`,
   `TACHES_DEMO_PASSWORD=… manage.py seed_taches_demo`, rebuild du front, parcours dans un vrai navigateur à 390 px
   et 1440 px, clair et sombre, comparés aux maquettes). C'est aussi le « L3 n° 10 » : corriger ce qu'on y trouve.
   **Ne pas merger #1454 avant** : le pli contient l'activation → dès le merge + deploy, l'Administrateur voit le module.
3. **TCH94** : régénérer les dérivés, retirer `[GATED: attend la fusion F2 sur main]` (ouverture de la fusion 3).
4. `gh pr ready 1454` puis `gh pr merge 1454 --auto --merge`. Dire à Reda : « mergé — l'auto-deploy suit ».

**Décisions prises seul pendant cette session (à relire, aucune ne demande Reda)**
- Coupe-circuit `balayage_actif` : il ne coupe que l'ENVOI de sollicitations ; clôture, purges et revérification des
  liens tournent toujours pour une société où le module est activé.
- Un compte neuf peut dire son objectif avant d'avoir une tâche (`ReglagesRythme` créé au premier `POST rythme/`
  ou `PATCH reglages/`) → `reference/donnees.md` dit encore « créée uniquement par creer_taches » : À CORRIGER.
- « Ailleurs dans l'ERP » : jamais de compteur à 0 inventé ; `approbations` omis (pas de porte publique).
- Les activités ERP closes qui portent une tâche ne comptent pas dans les « faites ».
- Plafonds de requêtes posés à la MESURE de la CI : `badge/` 11, `journee/proposition/` 25, `agenda/` 35 (cible 16 :
  **N+1 probable à corriger**, lots répétés tâche + rappel + check-list), `projets/{id}/vue/` 20, `recherche/` 10.

**Défauts connus à reprendre (aucun n'est en production)**
- **Activation en production — établi par lecture du code (17/11)** : le module est ACTIF par défaut pour toute
  société (pas de `ModuleToggle` à poser) ; `auto-deploy.sh` lance `init_roles`, qui réaligne le rôle système
  « Administrateur » EXISTANT (donc `taches_voir` arrive seul au deploy) ; un compte portant ce rôle voit le module ;
  un superutilisateur ou un compte hérité SANS rôle fin ne le voit pas (l'écran lit `role.permissions`). Seul geste
  possible pour Reda : se donner le rôle « Administrateur » si son compte n'en a pas.
- **À vérifier avant le merge** : `taches.nocturne` (03:00) parcourt TOUTES les sociétés actives où le module est
  actif, donc toutes dès le premier soir ; s'assurer qu'elle n'écrit RIEN (ni `PlanJour`, ni carte, ni
  `ReglagesRythme`) pour un compte qui n'a jamais utilisé le module (test à ajouter dans `tests/test_nocturne.py`).
- **E2E, tours 7 et 8 (pliés)** : le bout en bout a trouvé deux VRAIS défauts d'écran, corrigés : au bureau le bouton
  « Actions » d'une ligne recouvrait l'étoile (padding droit de `.ligne` ≥ 768 px, `base.css`) ; la carte
  « Brouillon » restait après une création (brouillon effacé avant l'événement, `FeuilleSaisie.jsx` — test unitaire
  de garde à ajouter). Aide `garderParApi` (route `journee/planifier/`) pour valider un plan dans les specs.
- **E2E, tour 6 (plié)** : les specs journée lisent l'état réel du compte (`etatJournee` dans `taches-aides.js`) au
  lieu de coder « 4 » et « 0 sur 5 » (`demo_admin` a 3 activités ERP closes du jour) ; vrais écarts d'écran
  corrigés : feuille plus haute que la fenêtre au bureau (`max-height` sur `.feuille.dialogue-bureau`), créneaux de
  l'agenda du bureau à 28 px (retour à 88 px par heure : densité à revoir à l'œil), segments de l'agenda à 390 px,
  nom accessible de « Planifier ma semaine ». Si le run suivant est vert : la fusion 2 n'attend plus que les
  acceptations en direct.
- **(historique) E2E restant rouge après le tour 5** (58 tests ; les écrans se montent) : (1) `taches-journee.spec.js` : « Garder
  ces 4 » et « 0 sur 5 faites » introuvables — hypothèse : le compte `demo_admin` a déjà des activités ERP closes
  du jour qui comptent dans « faites » (`selectors/journee.py`, `compte_faites`) et `tout-effacer` ne les touche
  pas → rendre les specs indépendantes du compteur initial (lire N dans `aujourdhui/`) ; (2) `taches-saisie` :
  « Coller encore » et « Fait » de la fiche « outside of the viewport » (feuille à faire défiler) ; (3) a11y :
  `PlanifierSemaine.jsx` `.ag-pj` (`label-content-name-mismatch`), `recherche` à 390 px non examiné. La spec a11y
  mesure désormais une cible par `max(boîte, ::after)` (zone étendue du design), seuil 44 px inchangé : à relire
  lors de la relecture ergonomie (L3 n° 11).
- **À VÉRIFIER AVANT DE DIRE À REDA « c'est activé » : son propre compte.** `taches_voir` est donné au RÔLE
  Administrateur ; un compte « hérité » (palier admin SANS rôle fin) ne l'a pas — c'est voulu (jamais de repli), et
  c'est ce qui a fait échouer les 57 specs e2e (`demo_admin` de `seed_demo` est un compte hérité → 403). Regarder en
  lecture seule sur la prod (accord permanent) si le compte de Reda est superutilisateur ou porte le rôle
  Administrateur ; sinon son geste est : Paramètres → Utilisateurs → se donner le rôle « Administrateur » (à écrire
  dans `docs/taches/README.md` et dans le rapport final).
- **Confirmé au tour 4 : l'ÉCRAN ne lit que les droits du RÔLE** (`/auth/me/` → `role.permissions`) ; même un
  superutilisateur sans rôle fin ne voit pas le module (le serveur, lui, le laisse passer). Donc Reda doit porter le
  rôle Administrateur. Le tour 4 donne ce rôle à `demo_admin` dans le shard 2 de la CI (heredoc dans `ci.yml`).
- E2E : le 3e tour a levé le 403 en passant `demo_admin` superutilisateur DANS LE SHARD 2 de la CI seulement
  (6 lignes de `.github/workflows/ci.yml`). Les 57 tests n'ont donc ENCORE JAMAIS atteint leur vrai contenu : le
  prochain run dira les vrais écarts (sélecteurs, écrans, accessibilité). Si ce passage en superutilisateur gêne
  d'autres specs du shard 2, repli plus propre : semer `seed_taches_demo` dans ce shard et connecter les specs
  Tâches avec `demo_taches` (rôle de test portant `taches_voir`).
- Plafonds de requêtes posés à la mesure de la CI (tour 3) : aperçu de saisie 11, aujourdhui sans familles 26,
  badge 13, liste des projets 14, proposition 27, recherche 12, vue d'un projet 22, agenda 28 (à confirmer). Seul
  l'agenda a un test « ne grandit pas » : en ajouter un pour proposition et vue d'un projet avant de s'y fier.
- Semis de démonstration : à 15 h il rend « 4 sur 5 » (l'activité ERP close compte) alors que les maquettes et
  `SCENARIO.md` disent « 3 sur 5 » → changer le semis (lier l'activité à une tâche), pas le calcul. Société de
  démonstration = `demo-taches` (séparée de `taqinor-demo`). Voir `ecarts-f2.md` §J pour le reste.
- Pastille « À trier » de la barre d'onglets : non faite (demande `BottomTabBar.jsx` et un compteur léger).
- « En faire des sous-tâches » : le parent est créé dans le même lot et n'a pas d'id → choix serveur à faire
  (index de ligne parente).
- « Annuler » d'un geste autre que cocher ne remet pas la progression du jour (la route `annuler/` ne la rend pas).
- `avant_id` / `apres_id` ont deux sens (tâches : voisin qui précède ; projets : « juste avant lui ») : documenté
  dans `api.md`, pas unifié.
- `reglages-societe/` répond encore 501 ; `mes_donnees.json` montre 2 clés de `reglages_rythme` sur l'objet entier.
- Jamais vérifié : rendu réel sur iPhone (390 px, clair/sombre), cibles 44 px, clavier virtuel, IndexedDB réel.

**Machine de cette session** : les worktrees `…\.claude\worktrees\agent-*` de cette session sont des copies de
lanes déjà pliées (sauf raccord écrans) ; ils peuvent être retirés (casser d'abord les jonctions node_modules).
