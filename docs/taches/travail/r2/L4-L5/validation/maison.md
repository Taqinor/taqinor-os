# R3 — lentille « maison » : le projet go-deep L4 / L5 tient-il dans CETTE maison, sur CE poste ?

Vérificateur neuf, lecture seule (20/11/2026). `origin/main` lu = 81899193d. Preuves = commandes de cette session.
Verdict : **pas prêt à merger** — 3 bloquants (crochet, format des tâches dans les plans d'audit, sécurité de
l'instrument non garantie) et 12 importants. Le reste (régime sur `origin/main`, merge par la file, Auto-fix, arrêt au
merge, pas de `scripts/`, pas de Docker « pour voir », réemploi des verdicts de `vérifie` et des oracles de qa-explorer)
est cohérent avec la maison.

## 1. Crochet — testé (Git Bash, enveloppe JSON réaliste par `json.dumps`, 29 phrases, ancien et nouveau)
Commande extraite de `crochet.md` l. 31 par `json.loads` (identique au bloc shell l. 25 : vérifié). Code de sortie 0 et
JSON valide partout.

| Entrée | Projet | Actuel | Attendu |
|---|---|---|---|
| `go L3 on this` | L3 | aucun | L3 |
| message réel de Reda (« … make it an L4 or l5 … build an L4 and L5 … l4 and l5 is much more powerfull … go L3 on this ») | **L3** | aucun | L3 ✔ |
| `go L3 on this` + rapport collé contenant « we should go deeper, and maybe do an L5 next time » | **L5** | L1 | L3 ✘ |
| rapport collé « il faut go deeper sur la lane 3 ; un L5 serait excessif » | aucun | L1 | aucun ✔ |
| rapport collé « Recommandation : go L5 sur le module stock » | **L5** | aucun | aucun ✘ |
| `ACHT22 est rouge` · `CAL51 reste gate ?` · `la tache L4-12 est bloquee` · `go L4-12 again` | aucun ×4 | aucun | aucun ✔ |
| `niveau 4 sur le stock` · `va tres profond sur les devis` | aucun ×2 | aucun | aucun (choix assumé) |
| `fais un L4 sur le module stock` · `ok⏎go L4 on stock` · `go l5` · `go L 4` | L4 · L4 · L5 · L4 | aucun | ✔ |
| prompt vide | aucun | aucun | ✔ |
| `il a ecrit "go L4" dans son message⏎et puis rien` (guillemets + retour) | **L4** | aucun | aucun ✘ (atténué par la consigne « ignore le cité ») |
| `start L5 now, the lane L4 is done` | **L5** | aucun | aucun ✘ — les lanes s'appellent L1-L8 ici (`grep "Lane L[0-9]"` : 15 occurrences dans r2/) |
| `run L4 again, it failed on flake8` | **L4** | aucun | aucun ✘ (lane) |
| `launch L3 and L4 in parallel` | L3 | aucun | aucun ✘ (faible coût) |
| `don't go L5, go L3` | **L5** | aucun | L3 ✘ |
| `should we go L5 on this? no - go L3` | **L5** | aucun | L3 ✘ |
| `go L3 then do L4 later if needed` | **L4** | aucun | L3 ✘ |
| `go L4 or L5? what would it cost` | L4 | aucun | une proposition, pas un départ |
| `run l2 cache flush` · `go level 3 of the building` | L2 · L3 | aucun | aucun (faux positifs bas coût, déjà assumés) |
| `go deeper on lane 3` · `Go Very Deep` · `ultra deep audit please` | aucun · L2 · L3 | L1 · L2 · L3 | ✔ |

**BLOQUANT C1 — un niveau supérieur cité n'importe où l'emporte sur le niveau demandé**, et `run/start/launch` heurtent
les noms de lanes. L'ordre L5→L4 fait qu'une négation ou un collage déclenche L5 avec le texte « Reda named level L5 ».
Correction (prototype testé dans cette session : `"don't go L5, go L3"` → niveaux nommés [5 3], `start L5 now` → aucun,
message réel → [3]) : (a) verbes réduits à `go|do|lance|fais` ; (b) relever TOUS les niveaux nommés
(`grep -ioE "$v"` + `sed` vers le chiffre) ; (c) un seul niveau distinct → texte actuel ; ≥ 2 distincts → texte neutre
« [go-deep] plusieurs niveaux cités (Lx, Ly) : prends celui que Reda demande en ses propres mots ; jamais L4/L5 sur ce
seul signal — au plus L3, et propose L4/L5 avec leur coût ». Ajouter les cas ci-dessus à la table de `crochet.md`.

## 2. Plans des propriétaires — la CI refuserait les tâches d'une ligne
**BLOQUANT C2.** SKILL étape 2 et `consolidation.md` § 1 : « Corrections become one-line tasks of the owner's plan
(`@lane @files @model @after`) ». Or le propriétaire est presque toujours un `docs/plans/PLAN_AUDIT_<MOT>.md`
(`docs/ownership.yml` : 17 fichiers PLAN_AUDIT, seuls taches / web / yanbow / platform ont un plan non-audit), et
`scripts/check_taches_cablage.py` FORME 5 « clauses-absentes » est **BLOQUANTE** sur toute tâche ouverte d'un
`PLAN_AUDIT_*.md` sans les 14 libellés v3 (docstring l. 58-67) ; elle tourne dans `stage-names`
(`scripts/ci_guards.py` l. 371), comme `check_ancres_taches.py` (l. 567, ancres v3 de PLAN_AUDIT). Lu, non exécuté.
Le run du 19-20/11 y a échappé parce que `PLAN_TACHES.md` n'est pas un plan d'audit. Correction (SKILL étape 2 +
consolidation § 1) : « Dans un `PLAN_AUDIT_*.md`, une correction est une tâche v3 (METHODE §C.2, 14 clauses, `@model`
obligatoire) ; multi-propriétaires → `PLAN_AUDIT_TRANSVERSE.md` (`@atomique`) ; avant de pousser,
`check_ownership.py`, `check_ancres_taches.py`, `check_taches_cablage.py` (METHODE §C.4.5). Une ligne courte n'est
permise que dans un plan non-audit. » Coût à dire dans la ligne de coût (≈ 2 400 caractères par tâche v3).

## 3. Sécurité de l'instrument — prescrite, jamais rendue impossible
**BLOQUANT C3.** `instrument-de-revue.md` énonce de bonnes règles mais rien ne les applique (pas de script, renvoyé à
une tâche future) ; or le script réel `r2/lancer-django.sh` les violait :
- `--env-file 'C:\dev\taqinor-os\.env'` : le vrai `.env` passé tel quel — il porte `CLAUDE_API_KEY` (106 car.),
  `GROQ_API_KEY` (56 car.), `WEBSITE_LEAD_WEBHOOK_SECRET` (longueurs relevées, valeurs non lues). Le mail n'était sûr
  que par hasard (`EMAIL_BACKEND` console et `SENDGRID_API_KEY` vide dans ce `.env`, rien de forcé).
- `-p 8010:8000` : publié sur toutes les interfaces (règle 1 « 127.0.0.1 uniquement » non tenue), avec `DEBUG=True`,
  `ALLOWED_HOSTS='*'`, `LOGIN_RATE_LIMIT=1000/minute`.
- `--network erp-agentique_default` sans forcer `MINIO_ENDPOINT` (défaut `minio:9000` = MinIO de l'autre pile, base.py
  l. 1684) ni `FASTAPI_INTERNAL_URL` (défaut `http://fastapi_ia:8001`, `apps/crm/intake_photo.py` l. 53 = le FastAPI
  de la pile principale, qui a les vraies clés IA) ; `ASSISTANT_COPILOTE` vaut `admins` par défaut (base.py l. 1532).
- Celery : broker sur le Redis à soi, aucun worker → effets asynchrones absents (à dire aux relecteurs).
Correction : ajouter au gabarit § 1 un bloc OBLIGATOIRE et une vérification qui ARRÊTE le tour 0 si elle échoue :
`-p 127.0.0.1:<port>:8000` ; env construit depuis `.env.example` seul + `-e` forcés : `EMAIL_BACKEND=django.core.mail.
backends.console.EmailBackend`, `SENDGRID_API_KEY= BREVO_API_KEY= CLAUDE_API_KEY= GROQ_API_KEY= OPENAI_API_KEY=
ZHIPU_API_KEY= VEILLE_IA_CLE_API= WHATSAPP_ENABLED=0 WHATSAPP_ACCESS_TOKEN= WHATSAPP_CLOUD_ACCESS_TOKEN=
SAV_WHATSAPP_APP_SECRET= META_LEAD_ADS_ACCESS_TOKEN= META_AD_LIBRARY_ENABLED=0 META_AD_LIBRARY_ACCESS_TOKEN=
WEBSITE_LEAD_WEBHOOK_SECRET= VAPID_AUTOGENERATE=0 ASSISTANT_COPILOTE=<valeur « éteint » du réglage>
FASTAPI_INTERNAL_URL=http://127.0.0.1:9`, MinIO à soi ou bucket `<run>-*` ; puis
`docker exec <run>-django env | grep -E 'KEY|TOKEN|SECRET'` ne doit montrer que `DJANGO_SECRET_KEY`/`FASTAPI_SECRET_KEY`
de développement, et `docker port <run>-django` que `127.0.0.1`. Port libre vérifié avant (8010 a déjà servi à une
autre session, mémoire 26-27/10 chantier). Tant que le script n'existe pas, ce bloc EST le lanceur.

## 4. Cohérence avec CLAUDE.md et la mémoire (importants)
- **I1 Merge par tour contre le plafond.** SKILL Tensions 2 « an L4 round is one WOW23 wave … no PR outlives a round ».
  Le tour 1 mesuré = 102 corrections (RETRO l. 47) > « never carry more than ~100 unmerged tasks » et > « A wave = ~80
  tasks ». Texte : « Un tour dont les corrections dépassent ~80 tâches se découpe en vagues (`plan_lanes.py --wave-size
  80`), chacune mergée dès sa CI verte ; jamais une seconde vague sur une rouge. »
- **I2 WOW23 TEST ECONOMICS.** `brief-lane.md` § 2.3 « les tests sans base de ton module » = un sous-ensemble local
  (interdit : seule exception « the ONE test you're actively fixing ») ; « `makemigrations --check` » exige Django
  installé ou Docker, que § 6 interdit. Texte : « flake8 + py_compile + eslint sur tes fichiers + le test que tu répares,
  seul ; makemigrations : la CI ».
- **I3 Preuve visuelle avant push.** `brief-lane.md` § 4 : chaque lane construit SON front et rejoue Playwright sur du
  code NON poussé = un gate local avant push (ci-avant-docker : « jamais comme gate avant de pousser ») et un build +
  Chromium par lane sur 4 cœurs. Texte : la capture « après » se prend sur l'instrument APRÈS pli et poussée, par la
  lane de couture ou le relecteur de contre-vérification ; la lane écrit les gestes à rejouer.
- **I4 Statut « 3-bis » auto-attribué.** SKILL Tensions 1 et le gabarit donnent à l'instrument « le statut de
  l'exception 3-bis », alors que `notes` § 7.5 ne touche `CLAUDE.md` « que si Reda l'accepte ». 3-bis vise l'acceptation
  jouée par l'orchestrateur, pas une flotte. La base existe déjà : mémoire `ci-avant-docker` « ce que la CI ne sait pas
  faire … se joue APRÈS le push, en parallèle de la CI ». Texte : citer CETTE exception, pas 3-bis ; sinon appliquer § 5.2.
- **I5 Acceptation.** Une tâche v3 cochée à « Preuve en direct » d'un groupe d'audit doit être couverte par
  `docs/audits/acceptation/<G>/<date>-<sha9>.md` + `.results.json` (`check_acceptation.py`, stage-names l. 345) ; la
  skill n'en dit rien. Ajouter à l'étape 10 : « avant la poussée d'une vague qui coche de telles tâches, l'orchestrateur
  joue et commite l'enregistrement (CLAUDE.md 3-bis) ; les verdicts des relecteurs n'en tiennent pas lieu ».
- **I6 Claims.** Bail de 6 h (`plan_claims.py` `TTL_HOURS = 6`), un tour dure des heures, une PR a vécu ≈ 2 jours : la
  skill ne dit jamais `renew`. Ajouter « renew à chaque point de contrôle ; claim aussi sur chaque plan d'un autre
  propriétaire qui reçoit des tâches (dont PLAN_AUDIT_TRANSVERSE) ; release après le merge (D-CLAIMS-MERGE) ».
- **I7 Décisions de produit.** `contrat-de-sortie.md` § 3 garde les réponses de Reda dans un fichier de run sur une
  branche de notes. Une décision fondateur va dans `docs/audits/decisions.yml` (METHODE §B.6) ou `docs/claude-memory/`
  (CLAUDE.md « Shared Claude memory »). Ajouter : « réponse obtenue → recopiée là dans la PR du tour ».
- **I8 L5 « vraie vie ».** « activation by flag » + « 5 days of real use » supposent un deploy et un réglage prod :
  gestes de Reda (Deploys : « Claude STOPS AT THE MERGE » ; auto-deploy arrêté le 17/11, mémoire poste). Et
  « qa-explorer `dataset: anon` chargé par sa commande » = `docker compose cp/exec` sur la pile principale (qa-explorer
  l. 118-120), que l'instrument interdit ; ses captures sont confidentielles (« never committed ») alors que le registre
  vit sur une branche poussée. Texte : « deploy et drapeau = Reda ; lecture prod en lecture seule (prod-read-access) ;
  jeu anonymisé chargé par Reda ou par la commande de qa-explorer sur SA pile, captures au scratchpad seulement, aucun
  montant au registre ».
- **I9 Campagne et Fable.** « Several commands … never split across merges or sessions » (Workflow) contre L5 « across
  sessions » ; « harness revalidation » n'est aucun des trois cas Fable permis (a)(b)(c). Ajouter à notes § 5 : « a
  go-deep L5 named by Reda is a multi-session campaign; its state file is the resume point » et rattacher la
  revalidation à (c) ou la retirer du budget Fable.

## 5. Double emploi
- **I10 Gravité.** Le registre invente A / B / C ; la maison a déjà S1-S4 + P0-P3 (METHODE §C.1) et Critical / High /
  Medium / Low (qa-explorer STEP 5 = error-autopilot B). Une 3e échelle casse la fusion vers les plans. Fusion : garder
  S1-S4 dans `registre.md` (A = S1-S2, B = S3, C = S4) ; P0-P3 posé par l'orchestrateur.
- Réemplois réels, vérifiés : verdicts fermés de `vérifie` (ok / partiel / non-fait / faux / régression / déjà-présent
  = METHODE l. 254-255) ; oracles 1-10 et règles 1-12 de qa-explorer (STEP 2 l. 236, STEP 3 l. 315) cités, non
  copiés ; `plan_lanes.py` ; specs `frontend/e2e/acceptation/`. Écart mineur : l'échantillon de contre-vérification
  « A + 25 % » omet « min 8, max 48, graine = SHA » de METHODE §C.4.2 (optionnel : le reprendre).
- Registre JSONL ≠ `unites.yml` ; contrat de sortie ≠ critères d'acceptation des tâches (QJR5) : complémentaires.

## 6. Faisabilité sur ce poste (mesurée)
- **I11 Poste.** Disque : `df` = 97 %, 15 Go libres, 218 dossiers sous `.claude/worktrees` ; L4 ≈ 40 agents de
  correction × ≈ 1 Go. Mémoire `machine_laptop_capacite` (11/11) : « plafonner chaque session à 3 sous-agents » ;
  « 8 lanes = machine pleine » sans pile. Or L4 suppose 4-6 relecteurs simultanés, chacun avec un Chromium, contre un
  `runserver` mono-processus que le gabarit dit déjà ralenti à 4 captures. Tâches planifiées du poste : `TAQINOR
  nightly QA` à 23:00 (`nightly-qa.ps1` : `docker compose up -d --build` + flotte qa-explorer sur le même Postgres) et
  `TaqinorDevClean` à 03:00 UTC (supprime les worktrees sans activité git depuis 7 jours — l'instrument d'une campagne
  L5 en pause y passerait). Texte pour « Box » : « au plus 3 agents simultanés avec l'instrument monté (relecteurs par
  lots de 3) ; au tour 0, espace libre ≥ (lanes × 1 Go + 10 Go) sinon moins de lanes ; aucun tour pendant la fenêtre
  de la QA de nuit ; worktree de l'instrument touché au moins tous les 7 jours ou recréé à la reprise ».
- **I12 Quota.** L'outil existe dans l'application de bureau : `mcp__ccd_session_mgmt__get_usage` a rendu ici
  « Weekly · all models 82 % » et « Weekly · Fable 70 % » (remise dans 5 j 17 h). Hors application (`claude -p`, cloud)
  rien ne l'établit, et « dernière valeur connue + points dépensés » n'est pas mesurable sans lui. Avec u = 82, la
  formule donne k = floor(3/25) = 0 : aucun L4 ne peut partir cette semaine. Texte : « (vérifié 20/11 : l'outil donne le
  % hebdomadaire et celui de Fable) ; illisible → k = 0, tour 0 seulement, sauf chiffre donné par Reda dans le chat ;
  passe Fable seulement si la fenêtre Fable < 90 % ».
- Base gabarit `test_erp_db_base` : ajouter « si le gabarit est occupé, attendre ou réutiliser un clone ; jamais
  `pg_terminate_backend` (mémoire docker_local_testdb, 24/08) ».

## 7. La PR (notes § 7)
- Gardes qui lisent `.claude/` ou `CLAUDE.md` sur `origin/main` : seule `check_audit_dossier.py` lit un SKILL
  (`.claude/skills/audit/SKILL.md`) ; `test_nightly_qa_scripts.py` lit `problemes-prod/SKILL.md` ; aucune ne lit
  `go-deep` ni `settings.json` (grep exécuté). Les autres citent CLAUDE.md en commentaire.
- CI : `ci.yml` l. 288-290 — `.claude/**`, `docs`, `*.md` ne lancent pas les jobs lourds ; `stage-names` tourne
  toujours (empreintes CODEMAP : skills et mémoire hors surface). PR docs / config confirmée rapide.
- Fichiers frères d'une skill : aucune skill du dépôt n'en a (`git ls-tree origin/main .claude/skills` : 7 SKILL.md
  seuls) ; précédent établi sur le poste : plugin superpowers 5.1.0 (`skills/brainstorming/visual-companion.md`, etc.).
- Liste suffisante une fois corrigé ; entrée `docs/claude-memory/` + index : oui (« Shared Claude memory ») ; CODEMAP : rien.

## Optionnels
- Relecteurs opus : qa-explorer explore en sonnet ; CLAUDE.md « cheapest tier that fits » — opus pour la
  contre-vérification (vérification adverse), sonnet pour le regard neuf, à mesurer.
- Formule de quota : 10 points pour toute la semaine de Reda, serré ; elle ignore le jour de la semaine.
