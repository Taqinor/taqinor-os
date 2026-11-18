# Acceptation en direct de la fusion 3 — rapport de la mise au point (18/11/2026)

Rapport rendu par l'agent qui a écrit et joué `frontend/e2e/acceptation/tch2.spec.js` sur la pile n° 2 (arbre `dev-taches-f3` @ 4f5352f7ce, AVANT la fusion de la fusion 2 corrigée et AVANT les corrections de la critique). Recopié tel quel.

## Acceptance spec for Tâches merge 3 (TCH141, TCH171, TCH143)

**Result:** last full run here gave **13 passed, 5 failed**. Of the 17 steps, 12 pass on this machine. Two are red because of real product defects (P143.2, P143.3). Three are red because they need the real assistant (P143.4 to P143.6), which only the GitHub runner has.

**Branch:** `lane/f3-acceptation`, starting from `dev-taches-f3` (the `4f5352f7ce` check passed). Head is `f26a0801f5ad51474a28084962fdc998aa482bef`.

`git log --oneline dev-taches-f3..HEAD`:
- `e9bb6ec8a6` A — `frontend/e2e/acceptation/tch2.spec.js` and my helper module `frontend/e2e/taches-acceptation-f3.js`.
- `a9b4c1e34c` A, follow-up — before each Copilote step the AI service is reset to Django's clock (`E2E_IA_RELANCER`). Without this its JWT check fails (details below).
- `f26a0801f5` C, last commit, on its own — "TEMPORAIRE — workflow d'essai de l'acceptation Tâches F3 (vrai assistant)". It adds `.github/workflows/zz-scratch-acceptation-taches-f3.yml`, `.github/zz-taches-pile.sh` and `.github/zz-acceptation-commit.sh`.

So A is two commits; fold both and leave C out.

`git status --short` shows only `?? frontend/e2e/taches-acceptation.js`. That is the merge-2 helper module, copied unchanged and not committed. It has to be on `dev-taches-f3` (through the F2 merge) before the spec, or C, can run.

I removed the run records with `git clean` on `docs/audits/acceptation/TCH` and `docs/qa-explorer/captures`.

**Last command run** (from `frontend`; `jouer.sh` loads `/opt/taches-cloud/secret.env` first, because this session refuses `. file`):
`E2E_ACCEPTATION=1 E2E_BASE_URL=http://localhost:4174 E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec-f3.sh E2E_TACHES_PILE=/opt/taches-cloud/acc-f3.sh E2E_IA_URL=http://127.0.0.1:8100 E2E_IA_RELANCER="/opt/taches-cloud/ia-f3.sh demarrer /home/user/taqinor-os/.claude/worktrees/agent-a135605fe2c8fd7a2" npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch2.spec.js --workers 1 --trace off --reporter=line`

It ended **13 passed** (12 steps plus the login setup), **5 failed**, in 8.8 minutes.

## Step by step

**TCH141 — Mon iPhone: all 5 steps GREEN here**
- **P141.1** (TCH141, TCH109, TCH95): 5 steps shown as « À faire » and « 0 sur 5 ». The capture token is created on screen and shown once. « Copier mon jeton » shows « Copié. Il ne sera plus affiché… ». After reload: « Jamais utilisé · tqc_… ».
- **P141.2** (TCH141, TCH96, TCH95, TCH39): « Ajouté pour demain 10 h : appeler le fournisseur » (201; task on 25/11 at 10:00, source capture).
  - Confidential project: « Ajouté dans un projet : une tâche ».
  - Flux token on capture: 401 with « Je n'ai pas pu noter : vérifie ton raccourci dans Mon iPhone. ».
- **P141.3** (TCH141, TCH97, TCH24, TCH11, TCH109): the .ics has no note, every DESCRIPTION is empty, the confidential task appears as « SUMMARY:Tâche confidentielle », and there is no external appointment.
- **P141.4** (TCH141, TCH97, TCH24, TCH109): the tile JSON has the same keys as `tuile.json`, faites 1 / objectif 5 → « 1 sur 5 », and step 4 shows « Fait ».
- **P141.5** (TCH141, TCH132, TCH109): `mobile_home_route` = `/taches/aujourdhui`, still there after reload. The GATED section of the plan still lists the device-only gestures (Siri, Scriptable, calendar subscription, the "try on iPhone" list).

**TCH171 — Notifications and kill switch: all 6 steps GREEN here**
- **P171.1** (TCH171, TCH98, TCH20, TCH30): exactly one `taches_plan_du_jour` notification, title « Aujourd'hui ». Its body contains no task title. It is visible in the bell on the iPhone view.
- **P171.2** (TCH171, TCH98): running the sweep again sends nothing more.
- **P171.3** (TCH171, TCH98, TCH20, TCH35): a reminder set at 10:00 produces `taches_rappel` « Rappel » linking to `?tache=<id>`. Opening it from the bell shows the group « Ce rappel vient de sonner » with « Encore 10 min · Encore 1 h · Demain 9 h ».
- **P171.4** (TCH171, TCH56): `badge/` n = 3.
- **P171.5** (TCH171, TCH155, TCH160, TCH98), desktop view:
  - Réglages → Avancé, the switch, the « Couper » dialog, the toast « Messages et rappels coupés », and the banner « …coupés pour la société depuis le 24/11 à HH:MM. » all appear.
  - With it cut, neither the sweep at 08:30 nor the one at 10:00 sends anything.
  - The step switches it back on in a `finally`.
- **P171.6** (TCH171, TCH98): an account seeded with `--vide` gets nothing at 08:30, 15:00 or 18:00.

**TCH143 — Copilote**
- **P143.1** (TCH143, TCH118, TCH161, TCH117, TCH165): **GREEN.** The 4 ready requests each show their card. No call to `/sql-agent/query` was made, so no model was involved.
- **P143.2** (TCH143, TCH170, TCH161, TCH165): **RED, product defect** (ERR 1).
- **P143.3** (TCH143, TCH117): **RED, product defect** (ERR 2).
- **P143.4** (TCH143, TCH111, TCH117, TCH165), **P143.5** (TCH143, TCH111, TCH117), **P143.6** (TCH143, TCH115, TCH11): **RED, "vrai assistant requis : E2E_IA_URL + clé du dépôt".** These are to be played on the runner.
  - P143.6 checks the deterministic part first, and that part passes here: under the assistant header, `aujourdhui/`, `journee/priorites/`, `journee/point/` and `recherche/?q=dossier` never contain the confidential title.

## Defects found (rule: no oracle was changed)

**ERR 1 — P143.2 — Copilote cards unreadable on screen**
- Expected: « une raison chacune » (plan TCH143 step 2; textes.md §5.3).
- Found: in every Tâches card of the panel, titles and reasons are cut to « Co… », « App… », « procha ». At 390 px the error is: titre « 1. Mettre à jour le planning des poses » coupé à l'écran. It is the same at 1440 px.
- Evidence: `/opt/taches-cloud/captures/f3/copilote-carte-priorites-toutes-{iphone,bureau}-clair.png`, `copilote-carte-plan_propose-*`, `copilote-carte-capture_apercu-*`.
- Likely files: `frontend/src/features/taches/cartes/CartesTaches.jsx` (`LigneCarte` with no `case_`) and `frontend/src/styles/taches/coeur.css`. Probable cause: `.ligne-corps` lands in the 44 px first column of the `.tch .ligne` grid (`grid-template-columns: var(--tch-cible) 1fr auto`).

**ERR 2 — P143.3 — « Planifie ma journée » offers 1 task instead of the N proposed**
- Expected: « Adopter → « Garder ces N » » (api.md §8), with N = 3 at 08:30 per SCENARIO §3 and per the Proposé served by `aujourdhui/`.
- Found: the `plan_propose` card shows « 1 · objectif 5 » and « Garder celle-ci ».
- Evidence: `GET journee/proposition/` returns 3 lines, two of which are the "À revoir" tasks (planned for the 23rd) marked `deja_prevue: true`. The card then filters them out. Capture: `copilote-carte-plan_propose-iphone-clair.png`.
- Likely files: `backend/django_core/apps/taches/services/journee.py:520` (`deja_prevue = jour_prevu is not None`) and the `CartePlanPropose` filter in CartesTaches.jsx.
- Note: `aujourdhui/` Proposé at 08:30 is planning des poses + bureau de contrôle + rails. SCENARIO §3 says rails / fournisseur / fiche, with À revoir folded away. That part belongs to merge 2's acceptance (P137.1).

**ERR 3 — Copilote panel does not match textes.md §5.2** (outside the plan oracles; seen in the captures)
- The subtitle is « Posez une question sur vos données… » instead of « ouvert depuis {écran} ».
- The field is « Posez votre question en français… » instead of « Écris ou dicte… ».
- Without an AI key, the sentence « La conversation libre n'est pas branchée sur ce serveur… » is missing.
- The « Planifie ma journée » reply is only « Rien ne change tant que tu ne gardes pas. »; the sentence « Tu as gardé {e} essentielles… » is missing.
- Likely file: `frontend/src/features/ia/CopilotPanel.jsx`.

**ERR 4 — Missing card buttons** (textes.md §5.7)
- `capture_apercu` has no « Changer de projet ».
- `plan_projet` has neither « Changer d'étape » nor « Tout ajouter ». This answers your point (3): the `planification/apercu` problem (needs `projet.id` and `lock_version`) cannot arise because the button does not exist.
- `capture_apercu` only reads `champs.nouveau_projet`. « Range ma liste » shows « Pas de projet évident » for all 5 À trier items (capture).
- Likely file: `CartesTaches.jsx`.

**ERR 5 — Your point (2), decided from the code; the runner capture will confirm**
- Every Tâches card, including a card still awaiting validation and `plan_propose` before adoption, is wrapped in the green "result" frame (`CLASSE_RESULTAT`, `frontend/src/features/ia/cartes/CartesDuMessage.jsx`), not the amber "proposition" frame.
- After validation by finger, the card shows « Ajoutée/Modifiée · Annuler ». The message's « Action effectuée » badge never appears, because it only exists when the server performed the action.
- Source of a task validated by finger: the call goes from the browser with the cookie, so Django records `manuel` or `rapide`, never `assistant` (`views/taches.py:165`, `views/saisie.py:109` only set ASSISTANT under the header or Bearer token). Arbitrage A5 says « Les tâches créées par l'assistant portent `source='assistant'` ». **You need to decide** whether a task proposed by the assistant and validated by finger counts as "created by the assistant". P143.4 logs the observed source.

**ERR-PLAN (I did not adapt these silently; each is noted in the spec header and in Playwright annotations)**
- **(a) TCH171:** `executer(maintenant='2026-11-24T08:30')` with a string raises `AttributeError: 'str' object has no attribute 'utcoffset'` (`balayage.executer` → `timezone.localtime`). P171.1 plays the literal command, records the failure, then plays the same moment as a timezone-aware datetime for Morocco.
- **(b) TCH141:** the plan's `curl -d '{"titre":…}'` sends form-urlencoded and gets 400 « Dis-moi quoi noter. ». With `Content-Type: application/json` (what the Siri shortcut sends) it gets 201 with the expected sentence. The plan's line needs `-H "Content-Type: application/json"`.
- **(c) Reference contradiction:** textes.md §7 says a confidential project gives « Ajouté dans un projet : {titre} ». But by inheritance (A6) the task is itself confidential, and the server answers « Ajouté dans un projet : une tâche ». The step asserts the plan oracle « … dans un projet » (prefix, no project name) and notes the sentence. textes.md §7 needs a decision.

**Not settled**
- With `--rendez-vous`, the external agenda exists (`agendas-externes/`), but `aujourdhui/` served by Django under faketime returns no appointments, even though the shell reads them with `mock.patch`. P141.3 notes this (served = 0), so « aucun rendez-vous externe » is only weakly proven here. Possible cause: the cache was seeded at real time and is read at the faked time.
- Infrastructure: `pile.sh` launches Django with `DONT_FAKE_MONOTONIC=1`. With that set, Python 3.11's `time.sleep` raises EINVAL (measured: gunicorn dies). Any `time.sleep` in Django on the cloud stack would fail. My scripts no longer set it.

## What I set up on this machine
- **`/opt/taches-cloud/ia-f3.sh` (new):** `demarrer <worktree> [8100]`, `arreter`, `etat`.
  - It runs uvicorn from my worktree on 127.0.0.1:8100 under faketime, starting from Django :8001's *current* time plus 5 s (Django's start is read from its pid file's timestamp).
  - I checked by trial why this is needed: a Django JWT whose `iat` is ahead of the AI service's clock gets 401 « Token invalide ou expire ».
  - Exact variables: from `env-ia.sh`, then `DB_NAME=erp_f3 REDIS_PORT=6380 DJANGO_INTERNAL_URL=http://127.0.0.1:8001 DJANGO_DEBUG=True SQL_AGENT_PROVIDER=groq SQL_AGENT_FALLBACK_PROVIDER=groq ASSISTANT_MOTEUR=langchain CLAUDE_API_KEY= GROQ_API_KEY= OPENAI_API_KEY= HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`.
  - It is still running. Stop it with `/opt/taches-cloud/ia-f3.sh arreter`.
- The built front at :4174 cannot reach the AI service. The spec reroutes `/api/fastapi/` to `E2E_IA_URL` with the session token as Bearer, the same convention as `aic.spec.js`. No existing script was edited.
- Local trial of `zz-taches-pile.sh` on ports 8002/8102: `semer`, `horloge`, `manage` work, the Django JWT is accepted by the AI service, and the processes are stopped.
- Only my scratch files are under the scratchpad.

## Captures
64 PNG files in `/opt/taches-cloud/captures/f3/`, each at iphone/bureau × clair/sombre:
- `mon-iphone`, `mon-iphone-etape-1` to `-5`
- `reglages-notifications`, `reglages-avance-coupe`
- `cloche`, `fiche-rappel`
- `copilote-panneau`, `copilote-carte-{plan_propose,priorites,capture_apercu,point}`, `copilote-carte-priorites-toutes`

`copilote-carte-a-valider` needs the real assistant; on the runner it goes into the artifact via `E2E_TACHES_CAPTURES=/tmp/captures-f3`.

## What could not be verified
- P143.4 to P143.6 against a real model.
- The workflow itself: checked here only by `bash -n`, `yaml.safe_load` (jobs `ci-image-check` and `taches-f3`, trigger push on `dev-taches-f3`) and the local trial of `zz-taches-pile.sh`. On the runner it also assumes:
  - `apt-get install libfaketime` works in the e2e image (it runs as root);
  - `AGENT_HMAC_SECRET` is drawn at random in the job, so the assistant journal can be written; without it P143.6's journal check cannot pass.
- No rebuild of the front was needed.

The defect list above is report B. I did not write it to a file.
