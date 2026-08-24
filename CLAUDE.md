# CLAUDE.md — TAQINOR OS

The rules below come from the founder and are enforced. They override default
assistant behavior. When a rule references a system that does not exist in this
repo yet, the rule still applies to any future integration.

## Non-negotiable rules

1. **Odoo — JSON-2 API only.** All writes to Odoo go through its JSON-2 API. Never
   write to the Odoo database with SQL, under any circumstances. (No Odoo
   integration exists in this repo today; the rule binds any future one.)

2. **Pipeline stage names come from `STAGES.py` — never hardcoded.** Import the 6
   canonical keys (NEW, CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD; French UI
   labels in the same file) from `STAGES.py` at the repo root in backend, frontend
   build constants, scripts, and tests — never a hardcoded stage list. CI
   (`scripts/check_stages.py`) fails on divergence. Do NOT invent or rename stages;
   ask the founder. FUTURE INTENT: the funnel stage is NOT wired to any table yet —
   it will live on a new CRM `Lead`/`Opportunity` model built in a future session
   with the new quote engine; build nothing for it now. It is a separate, permanent
   layer from the quote/invoice *document* statuses (rule #4) — the two never merge.

3. **Meta Ads CLI — campaigns are born paused.** Any campaign creation through the
   Meta Ads CLI must always carry `--status PAUSED`. Never create an active campaign
   programmatically. (No Meta Ads code exists in this repo today.)

4. **`/proposal` is the only path for client-facing quote PDFs.** The vendored
   premium engine at `apps/ventes/quote_engine/` renders them, exposed at `/proposal`
   (`GET /api/django/ventes/devis/<id>/proposal/`); `generer-pdf` + the Celery task
   route through it (toggle `USE_PREMIUM_QUOTE_ENGINE`, default on). Do not add or
   keep any alternative client quote-PDF path; the legacy ventes WeasyPrint quote PDF
   exists ONLY as the off-switch fallback — never extend it. `generate_devis_premium.py`
   may be edited for fixes. The engine only RENDERS — it never changes statuses: the
   Devis (`brouillon`/`envoye`/`accepte`/`refuse`/`expire`) and downstream
   BonCommande/Facture chains are preserved 1:1, a separate permanent layer from the
   STAGES.py funnel (rule #2). Invoices (factures) keep their own separate legacy PDF —
   only the QUOTE PDF changed. See `docs/quote-engine-swap-map.md`.

5. **Scraper policy.** Scrapers must never run from personal accounts. Any scraping
   with Terms-of-Service risk requires BOTH: (a) a risk file committed under
   `tos_risk/` describing target, risk, and mitigation, and (b) explicit manual
   approval from the founder before the first run.

## Repo facts

- Backend: Django at `backend/django_core` (apps: authentication, stock, crm, ventes,
  reporting, parametres, roles, contact) + FastAPI AI service at `backend/fastapi_ia`
  (OCR via Zhipu AI, natural-language SQL agent via LangChain). Frontend: React/Vite
  at `frontend`. Run backend tests locally via the canonical harness
  `powershell -File scripts/test-backend.ps1 [-Modules "apps authentication core"]`
  (docker `--keepdb --parallel`, single-writer guard so parallel lanes never
  corrupt the shared `test_erp_db`; see WOW9). Full stack:
  `docker compose up` (nginx :80, Postgres+pgvector, Redis, MinIO, Celery, Django,
  FastAPI, frontend) — copy `.env.example` to `.env` first.
- **Multi-tenant.** All business data is scoped by `authentication.Company`. New
  models need a `company` FK; new viewsets must filter querysets by
  `request.user.company` and force-assign `company` in `perform_create` — never
  accept it from the request body.
- **Cross-app boundary — go through `services.py`/`selectors.py`.** Between
  business-core domain apps (`apps/{crm,ventes,stock,installations,sav}`), all
  cross-app READS/WRITES route through the TARGET app's `selectors.py` (reads) or
  `services.py` (writes/orchestration) — or string-FK references — never by importing
  its `models`/`views`. Add a thin function to the target's selector/service and call
  it (keep lazy/function-local imports where they avoid cycles). Same-app imports and
  foundation-app imports (roles, records, authentication, core, customfields,
  parametres, reporting, etc.) are exempt. **CI-enforced (M3):**
  `backend/django_core/.importlinter` + the `lint-imports` step (in `backend-lint`)
  fail on regression — the five core domain *models* stay mutually decoupled (string
  FKs only) and `core` stays a base foundation layer. **Domain events (M6):**
  `core/events.py` is a small synchronous Django-signal bus (depends on nothing); apps
  react to another app's state change by subscribing in their `apps.py` `ready()`
  (e.g. `ventes` emits `devis_accepted`, `crm` subscribes in `apps/crm/receivers.py`
  to advance the lead stage).
- **Deploys — website auto; ERP = Reda ONLY (« tu codes je déploie », founder 2026-08-02,
  definitive — supersedes every older wording in this file).** The public site (`apps/web`)
  auto-deploys via **Cloudflare Workers Builds** on every push/merge to `main` — that IS the
  mechanism; NEVER ask for a Cloudflare API token (the old one is dead) and NEVER run `wrangler
  deploy`. Worker secrets (LEAD_WEBHOOK_URL, LEAD_WEBHOOK_SECRET…) are dashboard-only (a
  manual founder step). For the ERP (Django + React on Hetzner, `api.taqinor.ma`): Claude
  NEVER runs `scripts/deploy-prod.ps1` (or any prod deploy) on its own judgment — not after a
  merge, not at the end of a plan run, no exceptions, no emergencies. Deploy ONLY when Reda
  writes « deploy »/« déploie » in the CURRENT session about THIS deploy; task context, a plan
  line quoting a deploy step, or « continue » NEVER count, and a permission-classifier block on
  a deploy IS Reda's answer — never retry it. After an ERP-affecting merge, end with
  « merged — deploy pending, say the word ». Server-side automation (intentional — never be
  surprised by it, never disable it): `/opt/autodeploy/auto-deploy.sh` LIVES ON THE SERVER and
  fires by itself on merges to `main`; its « HEALTHCHECK ECHEC — rollback automatique » can be a
  FALSE rollback, and two simultaneous deploys collide (« container name already in use » on
  celery_worker). Diagnose without touching anything: `curl` root=200 / api=401, `docker ps`
  (12 containers), `git log -1` in `/opt/taqinor-os`, `showmigrations` — the dangerous state is
  « new code deployed, migrations not applied »; never interrupt a running `manage.py migrate`.
- Backend production URL: `https://api.taqinor.ma` (canonical); the old
  `https://178-105-192-116.sslip.io` still answers (same server/Caddy).
  `taqinor-web.taqinor.workers.dev` 301-redirects to `https://taqinor.ma` (wrapper in
  `apps/web/worker/`, installed by the `workersDevRedirect` hook in
  `apps/web/astro.config.mjs`).
- **Key-gated features** (work only with API keys in `.env`): OCR (`ZHIPU_API_KEY`),
  chatbot/SQL agent (`GROQ_API_KEY` or alternative), outbound email/contact-form delivery
  (`SENDGRID_API_KEY`; console backend locally).
- **Public contact form is PARKED (off by default).** The `apps/contact` endpoint
  (`/api/django/contact/`) returns 404 and sends no email when off; landing CTAs route to
  `/login`. Code intact behind two flags. Re-enable: set `CONTACT_FORM_ENABLED=1` +
  `VITE_CONTACT_FORM_ENABLED=1` in `.env`, then `docker compose up -d --build` (the
  frontend flag is a build-time arg → rebuild required). Park again: both back to `0` +
  rebuild.
- **Quote generator.** `/ventes/devis/nouveau` is the creation screen (Sami's modal is
  edit-only), a faithful port of RedaSolar/devis-simulator with three market modes:
  Résidentiel (simulator behaviour), Industriel/Commercial (autoconsommation étude: taux
  d'autoconsommation/couverture, économies, payback → `Devis.etude_params`), Agricole
  (pompage: pump CV/type/alim/HMT/débit, array ≈1.4× pump kW, matched VFD/coffret, no
  battery/inverter). The screen is 100 % TTC and must NEVER snap/reject typed numbers
  (form `noValidate`, all inputs `step="any"` — guarded by a test). Solar math + auto-fill
  live in `frontend/src/features/ventes/solar.js`; keep its classification keywords aligned
  with `quote_engine/builder.py` (réseau/injection, hybride, batterie, panneau) — the PDF
  option split depends on line designations.
- **Quote PDFs.** The one vendored engine
  (`apps/ventes/quote_engine/generate_devis_premium.py`) renders all formats, selected via
  the list's PDF dialog → `generer-pdf` body / `/proposal` query params (whitelist in
  `clean_pdf_options`): premium 'full' = 3 pages, +`include_etude` = 4 (degrades to 3
  without étude data), 'onepage' = 1 (adaptive density, never overflows). PDFs show
  per-line P.U./Total HT with a visible Sous-total HT → Remise → Total HT → TVA → Total TTC
  chain, a system summary (kWc/production/économie/prix-kWc, or pompe/débit/HMT), and product
  sheets from `Produit.marque/description/garantie`. Page counts enforced in
  `apps/ventes/tests/test_quote_engine.py`. `Produit.prix_achat` powers a GENERATOR-ONLY
  margin indicator — it must NEVER appear in any PDF or client-facing output.
- **CRM leads.** Full solar records (contact incl. WhatsApp/GPS; pipeline incl.
  owner/canal/priorité/tags/relance/type_installation/motif_perte; energy profile incl.
  bills + `ete_differente` + 82-21 flag; roof & site; light survey) with an Odoo-style
  chatter (`crm.LeadActivity`: automatic old→new field logs + manual notes via
  `historique`/`noter`; acting user + company always server-side). Lead-primary quoting: a
  Devis can carry `lead` + `client`; client resolved server-side from the lead
  (`apps/crm/services.resolve_client_for_lead` — reuse link, else company-scoped email match,
  else create; never duplicates).
- **Reference numbering.** NEVER count()+1 (it collided in production — deleted quotes shrink
  the count). Use `apps/ventes/utils/references.py` (highest-used+1 per company+month,
  savepoint + retry on races).
- **Catalogue seeding.** `manage.py seed_catalogue` (idempotent, additive-only; never touches
  existing prices/quantities) seeds the simulator catalogue + Pompage items and re-applies
  product sheets (marque/description/garantie only). 16 VEICHI variateurs carry the founder's
  REAL prices (public TTC + revendeur buy in `prix_achat`); 6 estimated coffret placeholders
  are ARCHIVED by the seeder (founder-authorized, never deleted). 11 OSP 30-series pumps ship
  with manufacturer curves (`Produit.courbe_pompe` debit→HMT + `pompe_kw`, `tension_v`) and
  DELIBERATELY EMPTY prices — excluded from auto-fill, greyed "prix à renseigner" until the
  founder prices them. Small-pump prices are market estimates flagged "à confirmer" (buy
  prices 0).
- **Pompage sizing.** HMT + débit souhaité (m³/h) select the smallest curve pump that delivers
  enough at that HMT (`solar.js debitAtHmt`); matched VEICHI variateur (smallest kW ≥ pump kW,
  tension 220/380 assortie) + one AFFICHEUR SI22 by default. m³/jour = débit@HMT × heures
  (editable, default 7 h), computed ONCE at creation, stored in `etude_params`, rendered
  identically on screen and the one-page PDF. Never print m³/jour for curve-less pumps (omit
  the card). Pompage compositions contain NO inverter and NO battery; auto-fill never quotes a
  price-less product (all guarded by tests).

## Workflow

These rules govern HOW work gets done and landed.

- **Fewest steps.** Default to the fewest steps that do exactly what was asked. Never add
  ceremony; never do extra or adjacent work (don't resolve unrelated gated items, restructure
  neighboring files, or create files nobody asked for).
- **Touch only the named files.** Asked to change two files → change exactly those two. Never
  create alternate or fallback files.
- **Several commands in one request** are all handled in the one run and land in the one merge
  to `main` — never split across merges or sessions.

### How a plan run works (applies to EVERY plan command)

A plan run drains the plan's whole BUILD QUEUE as **one continuous work-stealing pipeline** and
lands it as **exactly ONE merge to `main` at the very end** — one merge commit, one CI run, one
deploy, history preserved, 0 approvals, `main` always revertable via `git revert`. NEVER one
task at a time, NEVER a merge per wave or per batch. This is the ONLY run model — it OVERRIDES
any older "waves"/"one merge per wave"/"one task per session"/"stop after one task" wording
anywhere, including in the plan files.

**THE COST MODEL (measured 2026-07-09 — internalize the NEW numbers).** The dominant cost of a
run is the GitHub CI `backend-tests` gate. Its measured arc: **2h15** (serial + coverage, pre-WOW)
→ **45.5 min** (WOW1 `--parallel 4`) → **41 min** (WOW6 4× shard — small gain because the
~850-migration test-DB build was **97% of each shard**; the tests themselves ran in 62s) →
**WOW8** cache-restores that pre-migrated DB (key = migrations hash, rebuilt once per migration
change), targeting **~6-10 min** on the hit path; **WOW8-INCR** (2026-07-11) adds a `restore-keys`
fallback so the exact-key MISS that EVERY migration-adding plan build hits restores the newest
prior dump and applies ONLY the new migrations (delta, a few min) instead of the ~40-min cold
replay — the CI twin of the local harness's `-RestoreDb`; e2e restores from the same cache (its
migrate+seed was 94% of its 32 min — the specs run in 36s). Docs-only merges skip the heavy jobs
entirely and cost **~2 min** (measured) — the floor below NEVER applies to them.
**MERGE FLOOR (founder rule — CONDITION FIRED 2026-07-09).** The old ~200-task floor was the
correct adaptation to the 2h15 gate, but the 5-day evidence shows what it cost: giant PRs sat open
a median 3.16h/mean ~10h (one 202-task PR abandoned outright; #329 open 39h through 4 red cycles),
and 11 red heavy-gate cycles burned ~20-40h of CI wall-clock. The gate is now MEASURED ≤45 min on
two full runs (#335 45.5 min, #342 41 min), so the WOW22 recalibration is ACTIVE. THE FLOOR NOW:
land ONE drained lane-GROUP (≈40-80 tasks) or one full work-day of folded lanes, whichever comes
first; never carry more than ~100 unmerged tasks; once the WOW8 hit-path is confirmed ≤15 min,
a single full app lane (8-15 tasks) is a legitimate merge. **If a batch's CI is red, FIX it within
that batch before building the next on top — NEVER stack a second unvalidated batch on a red one**
(batch-4, merged unvalidated, cost 13 CI-red bugs and 4 red cycles). KEEP unchanged: lane-draining
as the unit of work, one sync-safe self-merge per batch, 0 approvals, `main` always revertable via
`git revert`, and the local combined docker test BEFORE every merge (it has caught ~96 real bugs
pre-merge, 67 in one run — it is the cheap gate; CI is the expensive confirmation). Second-round
same-app lanes still `git merge` the integration branch to inherit the round-1 migration chain.
While ONE batch's CI runs, pipeline the next lanes on DISJOINT apps (never idle on it) and reuse
ONE persistent `--keepdb` test DB across folds (a fresh full test DB build is ~35-38 min measured
— the same migration replay WOW8 caches in CI). **WOW8-local brings that cache to the harness:**
seed the DB once, `test-backend.ps1 -Snapshot` freezes it as a Postgres TEMPLATE, and every later
gate uses `-RestoreDb` (TEMPLATE clone ~seconds + `--keepdb` for only the new migrations) instead
of a cold rebuild — a real ARC+SCA run burned ~3.5 h purely on local test-DB churn without it.

**WOW23 — PIPELINED 80-TASK WAVES (founder, 2026-07-11 — supersedes the sizing/testing specifics
above where they conflict; the mechanics are CODED into `plan_lanes.py`, read them off its output).**
- **A wave = ~80 tasks = 8 file-disjoint lanes of ~5-15 tasks each = ONE merge.** Never a merge per
  agent-round: a "wave of agents" is not a merge unit (a run once shipped 5 PRs for 20 tasks — the
  exact ceremony this forbids). `plan_lanes.py --workers 8 --wave-size 80` emits the whole thing:
  lanes FORCED file-disjoint (lanes sharing a substantive declared `Files:` are auto-unioned;
  append-only surfaces like index.css exempt), LPT time-balanced so the 8 agents finish together,
  and a SEQUENCE of mutually-disjoint waves.
- **Pipeline the waves:** while wave K runs its single CI, wave K+1 is being BUILT (disjointness
  guarantees no collision). Don't wait for a whole wave: an agent that finishes early immediately
  work-steals the heaviest not-yet-started lane of wave K+1. **Disjointness outranks the
  PLAN2→PLAN→NT file order** — pool the plan files (`plan_lanes.py f1 f2 f3`) and pick disjoint
  work over strict order.
- **TEST ECONOMICS (supersedes "local combined docker test before every merge"):** a local gate is
  worth running ONLY if its FULL relevant set is faster than the CI job that catches the same
  thing. With CI at ~6-10 min: the ONLY routine local gate is `eslint` on changed files (seconds —
  catches what no-node_modules worktree agents can't see). NO local vitest subsets (false-green:
  you still pay the CI round), NO local docker test-DB gate (contended, OOM-prone, slower than CI).
  Exceptions: the ONE test you're actively fixing; `vite build` (~8 s) after any MANUAL conflict
  resolution. Local docker remains a debugging tool for reproducing a specific red, never a gate.
- **Merge the INSTANT CI is green** (a green run sat on for an hour went BEHIND main → integrate +
  full CI again + a woken flaky test). During an active CI wait, check every ~5 min. Skip
  preflight.ps1 on the cache-hit path (it doubles wall-clock for nothing).
- **At every merge, report:** tasks done this batch (one line each: what it was for) + remaining
  open counts per plan file.
- **Agent hygiene:** commit-per-task (a process crash killed 7 live agents; only COMMITTED work
  survived — ~16 tasks recovered), push the accumulating batch branch to origin as backup after
  each fold, kill stale 6-8h+ agent processes at run START (never mid-run, never broadly), and on
  a heavy fold conflict DROP & REQUEUE the task on the merged base — never hand-merge 100+-line
  collisions (both build-breakers of the 2026-07-11 batch were manual resolutions).
- **CONTRAT D'ABORD (PACT10, incident du 03/08/2026 — l'écran AO Tableau de bord, 0 clé sur 6
  concordante).** Toute fonctionnalité à deux moitiés livre son **contrat d'abord, SEUL, sur `main`**
  (`apps/<x>/contract_samples/*.json`) : sans fichier partagé, deux lanes file-disjointes inventent
  mécaniquement deux contrats — appliqué par `check_api_shapes.py`, ne le défaites pas en « simplifiant ».
- **`@after` SUR LA MOITIÉ BACKEND (PACT11, même incident).** Une tâche frontend qui consomme les
  données d'une tâche backend du même run **doit** porter `@after` sur ELLE (AOF172 déclarait `@after`
  sur la liste AOF170, jamais sur AOF166 qui produit ses données → départ en parallèle, écran mort) —
  refusé par `plan_lanes.py`, en français ; ajouter la dépendance, jamais `--force-wave`.

1. **Plan the lanes once.** Run `python scripts/plan_lanes.py <planfile>` for the file-ownership
   + dependency graph. A **lane** = tasks sharing a file/migration that must run in sequence;
   independent lanes run concurrently. (Drain `docs/PLAN2.md` before `docs/PLAN.md`.)
   **Build-order gate (SCA6).** `plan_lanes.py` automatically consults `docs/BUILD_ORDER.yml`
   (SCA1, the machine-readable wave DAG) before emitting a lane: noyau ARC → NTPLT+NTSEC →
   reste du Tier-1 (NTAPI/NTOBS/NTGRC/NTADM/NTMAR) → floods features/verticaux is a RUN RULE,
   not a suggestion — a task whose prerequisite group is under its `BUILD_ORDER.yml` threshold
   is refused with a French reason (see the "Refusé — ordre de vague" section of the plan-lanes
   output) instead of silently scheduled out of order. This is a pure machinery gate: no
   BUILD_ORDER.yml (or a prefix absent from it / listed `unmapped_ok`) means gating is a no-op,
   byte-identical to pre-SCA3 behaviour — never a reason to skip running `plan_lanes.py` first.
   `--force-wave` bypasses the gate entirely and is **reserved for the founder** (every use is
   logged to stderr) — an agent hitting a refused lane fixes the real prerequisite gap or moves
   to a different lane, it does not reach for `--force-wave` on its own judgment.
2. **Lane-draining is the unit of work: one agent OWNS one app and drains its WHOLE lane.**
   Dispatch up to ~8 worktree subagents (`isolation: worktree`) in parallel; each owns one
   `apps/<x>` and drains its ENTIRE pending queue in sequence — per task: verify-not-built →
   build with tests → flake8 + compileall (LIGHTWEIGHT static checks ONLY) → commit that task
   alone → next, building on the last (migrations chain inside its own worktree). **One agent =
   many tasks, never one.** Give each the explicit ordered task-ID list. A true blocker → mark
   `[BLOCKED]` and SKIP; the lane keeps going. Agents do NOT build a full test DB or spawn
   Postgres/containers (thrashes the shared DB, OOM-kills it) — the orchestrator runs the ONE
   combined test after folding. Each agent keeps ALL its code inside its own app, reading others
   only via their `selectors.py` or string-FKs, so file-disjoint lanes fold with zero conflict.
   When a same-app lane tail needs a just-built prior task, that prior must be on `origin/main`
   first (worktree agents branch from `origin/main`) — so build a lane's available head tasks,
   land them, then the tail; or split the lane across runs.
3. **Orchestrator reviews each lane + runs the combined local test — CACHED, not rebuilt (WOW8-local,
   2026-07-10).** As each lane returns, adversarially review its commits vs the safety rules +
   acceptance criteria, then — AT FOLD TIME, per lane — run THAT lane's new/changed test modules via
   `powershell -File scripts/test-backend.ps1 -RestoreDb -Modules "<lane's test modules>"` (WOW11 —
   the harness's single-writer guard means only one run touches the shared `--keepdb` DB at a time,
   so parallel lanes never corrupt it). A lane whose modules are red is NOT fold-eligible: fix first.
   Then, once all file-disjoint lanes are in, run the SINGLE combined test over all new modules.
   **THE COST DISCIPLINE — a real ARC+SCA run's whole lost afternoon (~3.5 h) was LOCAL test-DB
   churn, not CI (it never reached CI): the test DB is CACHED locally exactly like WOW8 caches it in
   CI.** Seed it once, then `test-backend.ps1 -Snapshot` freezes the migrated DB as a Postgres
   TEMPLATE (`test_erp_db_base`); every gate after uses `-RestoreDb` — a TEMPLATE clone (~seconds) +
   `--keepdb` applying only the NEW migrations. **NEVER `-RebuildDb`** (the ~35-min cold "heures"
   rebuild) except once to seed; a migration collision or stale `--keepdb` DB is recovered with
   `-RestoreDb`, not a rebuild. Run the FULL combined gate ONCE per merge-batch, **not once per fold**
   (that run did ~6 gates = ~6 rebuilds — the whole afternoon); never fold while a gate runs (the
   harness live-mounts the worktree → code shifts under the tests) and cap concurrent heavy lanes at
   2-3 (more OOM-kills the gate → forces a rebuild). This per-fold gate is exactly what batch-4
   SKIPPED when it shipped 113 unvalidated failures; the combined test is the real pre-merge feedback
   — it has caught a real bug in most runs (missing import, `clean()`-vs-`save()`, name clash,
   hard-vs-soft-delete, a silently-swallowed effect). Fix, re-run only the affected module, then the
   single gate. NOT the GitHub CI (once at the end).
4. **Fold continuously into ONE `dev` branch + advance LOCAL `main`.** As each reviewed+tested
   task passes: fold its branch into the accumulating `dev`, tick it `[x]`, add one dated DONE LOG
   line, and **fast-forward LOCAL `main` to the `dev` tip — locally only: never push, never PR,
   never run GitHub CI between tasks.** This lets later same-app tasks inherit prior migrations;
   advancing LOCAL `main` is NOT a merge.
5. **ONE gate at the very end.** When the queue drains (or a cap is hit): refresh `docs/CODEMAP.md`
   if structure/plan changed (then `codemap_fingerprint.py --write`), integrate the latest
   `origin/main` into `dev` (sync-safe — merge it in, recompute the structure fingerprint if the
   structural surface moved, NEVER force-push). **Then decide whether to run `powershell -File
   scripts/preflight.ps1` BEFORE pushing — WOW (2026-07-11): gate it on the CI path, do NOT run it
   reflexively.** Preflight runs EVERY fast gate (backend-lint's compileall-3.11 / flake8 / lint-imports,
   the model↔migration drift check, and all 10 `stage-names` sub-checks) locally in the prod 3.11 image
   in one pass (~7 min) and reports ALL failures at once — a run that skipped it once burned FOUR CI
   round-trips discovering stage-names reds one at a time. Its ONLY value is catching a fast-gate red
   BEFORE a SLOW CI cycle, so gate it on the WOW8-INCR cache path: **run full preflight when the push
   will be a cold cache-MISS (new/changed migrations → ~40-min CI) or touches a high-risk fast-gate
   surface (migrations, imports, stage-names/CODEMAP).** But on the cache-HIT path the CI gate is now
   ~6-7 min (measured 2026-07-11) — a ~7-min preflight in front of a ~7-min CI just DOUBLES the
   wall-clock for zero saving, so there SKIP full preflight and run only the cheap host-only checks on
   the changed files (`flake8` + `py_compile`), letting the fast CI be the gate. Fix everything red,
   THEN push `dev` and run the four required checks **once** over the whole batch. To WAIT on that CI, use `powershell -File scripts/watch-ci.ps1` (or
   `-Pr <n>`) — it wraps `gh run watch --exit-status` and prints a per-job PASS/FAIL summary, so no
   session re-invents a waiter/monitor or hand-rolls a `2>&1 | tail` status check that masks the exit
   code. Self-merge `dev` → `main` **exactly once**. Deploy is NOT part of the run: the website
   auto-deploys via Cloudflare, and the ERP deploy belongs to Reda alone (Deploys rule above —
   end with « merged — deploy pending, say the word »; the server's `auto-deploy.sh` may bring
   `main` live by itself). When branch
   protection requires it, ONE batch PR used purely as the CI-gated merge vehicle counts as that
   single self-merge. If the push is rejected because `main` advanced, repeat the sync-safe
   integrate → CI → merge — never force.

**Engine.** Prefer a dynamic `Workflow` `pipeline()` (build → review → local-test → fold as
independent stages with no barriers; concurrency auto-caps at ~8 = native work-stealing). Fall
back to manually-dispatched worktree subagents with the SAME refill-on-completion rule. NEVER a
single serial one-task-at-a-time agent.

**Model selection (per task/role) — auto-pick the cheapest model that fits; NEVER let subagents
inherit the session model (founder rule).** This applies to plan-build runs AND research/audit/any
multi-agent workflow (an all-Fable audit once burned ~4× the tokens it needed). The ORCHESTRATOR
(main loop) keeps the session model (Opus for a plan run, never downgraded — that is where the
costly judgment lives: lane planning, adversarial review, real-vs-environmental triage, revert/keep
calls, migration-chain orchestration, the combined test, CODEMAP/fingerprint/DONE-LOG bookkeeping,
the merge gate). Every SUBAGENT is dispatched via `Agent` `model:` / `Workflow` `agent()`
`opts.model` on the cheapest tier that fits:
  - **haiku** — scouting/mechanical: greps, file reads, web search/WebFetch, verify-and-skip, DC
    single-source wiring, small additive CRUD, trivial-or-no migration. Zero frontier reasoning.
  - **sonnet** (DEFAULT) — standard feature lanes (models+migrations+viewsets+tests, cross-app
    reads via `selectors.py`, moderate logic) and standard research synthesis / per-domain audit
    lanes. The bulk of the work.
  - **opus** — high-risk lanes ONLY (the quote engine RULE #4, `core` under import-linter
    contracts, auth/permissions/security, destructive migrations, brand-new cross-app ARCH/event
    flows) AND judgment work (adversarial verification, cross-domain dedupe, completeness
    synthesis, the merge/report gate). Escalate any lane a cheaper agent returns
    `[BLOCKED]`/uncertain one tier up.
  - **fable** — the 1-3 passes per run where frontier reasoning materially changes the outcome.
    **AUTO-AUTHORIZED (2026-07-10, founder) when a pass is objectively WORTH IT — no longer only
    on request.** Worth it means one of exactly these (each backed by a real catch in this repo's
    history: the QW7 live data-corruption bug, two ARC security catches, the VX false-premise
    fixes were ALL single Fable critic passes): (a) ONE final adversarial/completeness critic
    over a large or high-risk batch BEFORE its single merge (≥~40 folded tasks, or any batch
    touching rule-#4/auth/architecture); (b) adjudicating a contradiction two Opus passes could
    not resolve, or a lane that failed twice at the opus tier; (c) ONE decisive synthesis whose
    verdict shapes many downstream tasks. HARD LIMITS: cap 1-3 Fable calls per run; NEVER for
    build lanes, scouts, or verifier fleets; each Fable call gets a one-line DONE-LOG note
    (what it was for + what it caught) so the founder sees whether it earned its cost. Fable is
    the MOST capable AND MOST EXPENSIVE model ($10/$50 per 1M — 2× Opus, 10× Haiku); a scalpel,
    not the house model. A small batch (<~40 routine tasks, no high-risk surface) does NOT get
    a Fable pass — Opus review is enough there.
  The orchestrator still adversarially reviews + locally tests EVERY lane regardless of which model
  built it, so a cheaper builder never lowers the merge bar. Config (`.claude/settings.json`):
  `"model": "opus"` runs the orchestrator on Opus. **`CLAUDE_CODE_SUBAGENT_MODEL` must stay UNSET
  (removed 2026-08-24, audit-verified against the official sub-agents docs):** that env var has
  HIGHEST precedence and silently overrides per-call `model:` AND agent frontmatter — so the old
  `=sonnet` « floor » was in fact forcing haiku scouts, opus judgment lanes and any subagent Fable
  pass ALL onto Sonnet. The real protections against inheritance are: (a) NEVER dispatch an
  untagged subagent (this rule), (b) read each lane's `model=` off `plan_lanes.py`, (c) in a
  `/model fable` session EVERY subagent call carries an explicit `model:` — inheritance at $10/$50
  is the 2026-07-04 ~4× incident. **Effort is the second dial (official levels low→max):** set it
  per role — `low` for haiku scouts, `medium` for routine sonnet lanes (official: Sonnet 5 at
  medium ≈ Sonnet 4.6 at high), `high` for opus judgment/verifiers and Fable passes. NEVER switch
  `/model` or `/effort` MID-session: both are prompt-cache keys — one switch re-bills the whole
  transcript uncached; run a Fable critique as a fresh subagent/session instead (also the
  documented higher-quality pattern). For a deliberate Fable deep-dive, `/model fable`
  at session start. **AUTOMATIC ROUTING (2026-07-10): `python scripts/plan_lanes.py <planfile>`
  prints the model tier per task AND per lane** (a lane's model = its highest-risk task; an explicit
  `@model:haiku|sonnet|opus` tag on a task line overrides the classifier) — a plan run reads each
  lane's `model=` off the lane plan and passes it to the Agent call; no judgment call needed for
  the routine tiers. `fable` is deliberately not routable — it stays a session-level scalpel.
  **EVERY-PROMPT RULE (2026-07-10, founder): this routing applies to ALL of Reda's prompts, not
  only plan runs.** On ANY substantive request — bug fix, audit, research, a facture, an
  investigation — the session model acts as the ORCHESTRATOR ONLY: it thinks, decomposes, reviews
  and reports, and DELEGATES the heavy mechanical volume (bulk edits, sweeps, log-reading, broad
  greps, transcript/file mining, standard build work) to subagents tagged per the tiers above
  (haiku scout / sonnet worker / opus judgment). Answer directly WITHOUT delegation only when the
  work is genuinely small (a question, a one-file fix, pure judgment) — spawning an agent for a
  two-minute task wastes more than it saves. The session model itself is never downgraded; the
  savings come from where the VOLUME runs, and the orchestrator's adversarial review keeps the
  quality bar identical regardless of which tier produced the work.

**Fleet quality & economics (founder-adopted 2026-08-24; each rule audit-verified against
official docs).**
- **Size by independent surfaces, never by emphasis.** A fact-check = 1 agent. A breadth audit =
  one lane per genuinely independent surface (378 numbers over 9 surfaces = ~9-12 lanes — never
  161 agents at 2,3 numbers each). Go past ~10 lanes only when the material genuinely exceeds one
  context window. When Reda escalates (« best in EVERY aspect »), answer with a DEEPER pass per
  lane (more rounds, higher effort, adversarial re-reads) — never more lanes.
- **Grounding block — include VERBATIM in every dispatched agent/lane prompt:** « Before reporting
  progress, audit each claim against a tool result from this session. Only report work you can
  point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say
  so with the output. » Every done-claim cites its commit SHA + the gate command it ran; the
  orchestrator then SPOT-checks git state instead of sweeping every lane.
- **Reviewer calibration.** Critics/verifiers flag ONLY correctness or spec (plan-task-text)
  findings; style, defensive hardening and hypothetical cases are reported separately as OPTIONAL.
  EXCEPTION: checked-facts / zero-invented-number findings are ALWAYS correctness, never optional.
  TRIAGE findings (classify → decide) before dispatching any corrector — never « fix all N »
  blindly (the 47-findings-all-fixed episode and PR #547's over-broad guard both came from that).
- **Read-only fleets never get worktrees.** Audit/verifier fleets run as same-directory fan-outs
  (Workflow): the prompt cache is scoped per directory, so homogeneous siblings read the first
  agent's cached prefix at ~10% of the input rate; worktrees are ONLY for lanes that edit files.
  Structure big audits as ONE workflow (on a stop in the same session, completed agents replay
  from cache). Resume a subagent only to DEEPEN its own lane; adversarial round-2 is always a
  FRESH agent (fresh context is the point).
- `ENABLE_PROMPT_CACHING_1H=1` stays set in `.claude/settings.json` env: on usage credits the
  prompt-cache TTL silently drops 1 h → 5 min (official) — exactly the overnight/credit-cap
  windows where long runs live.

**Go-deep levels.** « go deep » / « go very deep » / « go extremely deep » each map to a calibrated
investigation depth — full doctrine in the **`go-deep` skill** (`.claude/skills/go-deep/`), injected
by the prompt hook on those phrases. On any substantive audit/investigation request WITHOUT an
explicit level, auto-pick the level per that skill's criteria and announce the choice in one line
(Reda's named level always overrides).

**Token discipline — read the MAP before grepping the territory (founder rule).** `docs/CODEMAP.md`
is the curated, always-current map (§3 repository map + §4 app-by-app: every app's
models/endpoints/routes) — a "read-once" index so an agent spends a few thousand tokens reading ONE
map instead of grepping hundreds of files (the biggest free token lever after model selection). On
any task that needs to LOCATE code: (1) consult CODEMAP §3/§4 FIRST for the owning app + file; (2)
jump there with a TARGETED `Grep`/`Glob` or a line-ranged `Read` — never a repo-wide grep or a
blanket whole-file read; (3) delegate broad exploration / log-reading / verbose output to a subagent
that returns a SHORT CONCLUSION (only its summary enters the orchestrator's context). Keep CODEMAP
LEAN (§4 is an index, not a knowledge dump). Optional accelerator: the **Serena code-index MCP**
(`.mcp.json`) gives symbol-level `find_symbol`/`find_referencing_symbols` retrieval — approve it in
`/mcp` when you want it; everything above degrades gracefully to CODEMAP + targeted Grep without it.
No tool grants free cross-session memory: every session starts fresh, so savings always come from
loading LESS.

**Autonomy & stop conditions (founder standing consent).** Every run — local, remote/cloud, or
phone — must land the single `dev` → `main` self-merge; never stop at a feature branch, never wait
to be asked. Every task category (ROUTINE/SCHEMA/ARCH/DECISION/AUTH/COST/GALLERY/DEP) builds; additive
AND destructive migrations are pre-approved provided they stay revertable — NOTE in the DONE LOG any
new paid/external dependency, auth change, destructive migration, or brand-new architecture. **Stop
ONLY when:** the queue is drained; the usage/length cap is hit (re-firing resumes idempotently from
the first unchecked task); or a task hits a true external blocker it cannot satisfy (a
founder-provisioned credential/secret/account, a deleted state file, or a conflict with rules #1-#5)
— mark it `[BLOCKED: reason]`, move it to GATED, KEEP GOING. A single blocked task never halts the run.

**Safety model — never bypass.** The four required checks (backend-lint, backend-tests with MinIO,
frontend-lint, stage-names) gate the single merge with 0 approvals, and `main` stays revertable via
`git revert`. Keep branch protection exactly as configured — do not loosen, bypass, or add approvals.

**CODEMAP upkeep.** If the run changed backend models/endpoints, frontend routes/features, or module
structure, regenerate `docs/CODEMAP.md` from source and run `scripts/codemap_fingerprint.py --write`
(skip on docs-only runs). Whenever a task is ticked/blocked/added/removed, refresh §10 "Plan status"
+ re-run `--write` in the SAME commit. The `stage-names` CI job re-runs `--check`, so a stale map
fails CI.

**Report once**, in plain language: how many tasks shipped (and what), what was skipped/blocked and
why, and the single merge (deploy pending Reda's word).

**RETRO — every plan run learns from itself (MANDATORY, ≤5 min, BOUNDED so memory improves
instead of bloating).** After the report, run a short self-retrospective over what THIS run got
wrong and fixed, and bank it in the ONE right place:
1. **New CI/test bug class** a subagent shipped → ONE numbered 2-4-line entry in the memory file
   `plan_drain_ci_bug_classes` (the proven pattern: that catalog grew 8→19 entries across runs and
   each entry saved later runs a red cycle). **Dedupe first**: if the class exists, sharpen the
   existing entry — never add a near-duplicate.
2. **Routing misjudgment** (a sonnet lane returned `[BLOCKED]` and opus fixed it, or an opus lane
   proved trivially mechanical) → fix it in CODE, not notes: add `@model:` tags to the similar
   remaining plan tasks or refine `scripts/plan_lanes.py`'s classifier regexes in the same run.
   The router IS the memory for routing lessons.
3. **New infra/concurrency hazard** → the matching memory file (`local_ci_via_docker` for
   docker/test-harness, `worktree_drain_mechanics` for worktree/git, `plan_run_addenda` for
   run-economics), 1-3 lines, evidence-counted where possible.
4. **ANTI-BLOAT RULES (absolute):** only bank a lesson that would CHANGE a future run's behavior —
   run history belongs in the DONE LOG, never in memory; update-in-place beats appending; NEVER
   create a new memory file for a lesson that fits an existing one; if a touched file exceeds its
   budget (gotcha files ~40 lines, mechanics files ~180, the bug catalog ~4 lines/entry), fold its
   weakest/stalest entries into `done_history_archive` IN THE SAME edit — memory must come out of
   every run at the same size or smaller, just sharper. A run with nothing genuinely new banks
   NOTHING (most runs — that is success, not failure).

### "work on the plan <domain>" — PARALLEL domain sessions (founder, 2026-07-10)
The 2,084-task NT backlog is SPLIT into 7 domain files under `docs/plans/` — **PLAN_CRM_VENTES,
PLAN_FINANCE, PLAN_SUPPLY, PLAN_SERVICE, PLAN_RH_PAIE, PLAN_DOCS_JURIDIQUE, PLAN_VERTICALS**
(`scripts/split_plan.py` did the move; `docs/new_tasks_plan.md` keeps the PLATFORM tier,
single-session). Each file opens with an **APP-OWNERSHIP CONTRACT** — the guarantee that parallel
sessions never conflict, exactly like the web/ERP split. A domain run is identical to **"How a
plan run works"** EXCEPT:
- It drains ONLY its own file and touches ONLY the apps/dirs its contract owns; anything outside →
  `[BLOCKED: hors périmètre]` + keep going (it returns to the platform run). Foreign apps are read
  via `selectors.py`/string-FK only — NEVER their models/migrations (this keeps every app's
  migration chain single-writer). **COMPOSITION GUARD: a task that depends on a platform/NT
  primitive not yet on `main` (chatter, numbering, job queue, registry…) → `[BLOCKED: attend
  <ID>]` — NEVER hand-roll a local substitute for a platform primitive** (the #1 measured debt
  source: 13 hand-rolled chatters). Cross-queue ORDER is enforced by machinery, not memory:
  `BUILD_ORDER.yml` + `plan_lanes.py` refuse any task whose prerequisite group is under its
  completion threshold, so sessions can be started in ANY order and still compose — the planner
  simply won't hand out work whose foundations are missing.
- Local tests use `DB_NAME=erp_<domain>` (never the shared test DB); at most 2-3 sessions run
  heavy local docker on this box concurrently — further sessions run in the cloud and lean on the
  ~6-min CI gate instead.
- It merges its own `dev-<domain>` branch to `main` independently (update-branch → ~6-min CI →
  auto-merge). If `docs/CODEMAP.md` conflicts at update time (two sessions both moved the
  STRUCTURE fingerprint), take the merged tree and re-run `codemap_fingerprint.py --write` —
  30 seconds, mechanical. Shared frontend files (router/nav/api): append-only additions; a
  conflict there = keep BOTH sides' additions.
- Domain files are NOT in the plan-fingerprint surface (like WEB_PLAN.md): tick `[x]` + DONE LOG
  inside the domain file itself; never touch CODEMAP §10 for them.
- **ONE session per domain file** (the per-file version of the old single-session rule). Any set
  of DIFFERENT domains runs in parallel. The classic platform run (below) also joins, but
  CRM_VENTES should be idle while it drains PLAN2's QX/VX (they touch ventes/crm/frontend-shell).
- **Respect `docs/BUILD_ORDER.yml` (SCA3):** `plan_lanes.py <domain file>` says what is buildable
  NOW vs wave-gated behind platform prerequisites; `--force-wave` is the founder-consigned
  override when Reda wants a domain to start early. No session deploys — the ERP deploy belongs
  to Reda alone (Deploys rule above).

### "work on the plan"
Drain in STANDING PRIORITY ORDER (founder, 2026-07-10): **1) `docs/PLAN2.md` → 2) `docs/PLAN.md`
→ 3) `docs/new_tasks_plan.md` (the NT platform tier)** using **"How a plan run works"** above.
Anything typed after the command is extra detail. This is the PLATFORM/cross-cutting run
(ARC, SCA, ODX, YAPIC, VX shell, QX journey, then the NT platform groups — the work that touches
many apps and therefore stays single-session).
- **The priority order is STANDING and re-checked at every lane refill:** when a higher-priority
  file gains new `[ ]` tasks mid-run (an "add to plan:" landed, a task got unblocked), the next
  free lane pulls from the highest-priority non-empty queue FIRST — new PLAN2/PLAN tasks always
  jump ahead of the NT tier, today and after any future additions. A run only descends to
  `new_tasks_plan.md` when PLAN2 + PLAN.md hold zero buildable `[ ]` tasks (blocked/gated ones
  don't hold it back).
- NT-tier bookkeeping follows its file's own rules (NOT in the plan-fingerprint surface: tick +
  DONE LOG in-file, never CODEMAP §10; respect `BUILD_ORDER.yml` wave-gating within it; the NT
  header's built-digest regeneration step applies). The `docs/plans/PLAN_*` domain files are NEVER
  part of this run — they belong to their own parallel `work on the plan <domain>` sessions.
- One session at a time ON THESE THREE FILES (domain sessions on `docs/plans/*` run in parallel
  with it, per the section above). Read them fully and verify real repo state before building.
- Process EVERY unchecked `[ ]` task; verify each isn't already built (if it is, mark
  `[x] (already present)`), then tick `[x]` + add a dated DONE LOG line as it lands.
- Lane-draining, batches sized by the RECALIBRATED MERGE FLOOR above (≈40-80 task lane-groups now
  that the gate is measured ≤45 min — not the old ≥200), each batch locally tested then one
  sync-safe self-merge (deploy = Reda's word only). The rich self-contained lanes to drain first:
  rh/flotte/qhse/contrats/ged/paie, then parametres/publicapi/kb/core/stock/sav/litiges/crm, then
  the rest. Report once with the lane plan (how many ran in parallel + what each shipped) and what
  was skipped/blocked.

### "loop work on the plan" (`/loop work on the plan`)
The SAME run model, self-paced across wakeups — NOT a merge per wakeup. Each `/loop` fire CONTINUES
the one accumulating run: keep lane-draining onto the single branch and **merge exactly once when
the lanes drain or a usage cap hits**. While the one CI runs you are NOT idle — build the next lanes
(disjoint apps) during it. The fire that finds nothing left to build does the final merge (or
reports the queue drained; deploy stays Reda's — Deploys rule). Wake-ups exist to resume a paused drain,
never to chop the run into many small merges.

### "add to plan:" followed by tasks (one per line or separated by ;)
Append them as `[ ]` lines to `docs/PLAN.md`'s BUILD QUEUE, then refresh §10 "Plan status" of
`docs/CODEMAP.md` and re-run `python scripts/codemap_fingerprint.py --write` in the same commit
(adding a task moves the plan fingerprint, so `stage-names` fails otherwise), then commit on `dev`
and self-merge to `main`. Confirm in one line.

### "work on error plan"
Identical to **"work on the plan"** / **"How a plan run works"** in every respect — EXCEPT it drains
`docs/ERROR_PLAN.md` (the bug/error backlog); plan lanes with `python scripts/plan_lanes.py
docs/ERROR_PLAN.md`. Same pool of up to 8, same per-task review + local test + fold, same single
sync-safe self-merge (deploy = Reda), same stop conditions, same verify-not-already-built. Anything typed
after is extra detail.
- `docs/ERROR_PLAN.md` IS in the plan-fingerprint surface: ticking/adding/removing an `ERR*` task
  means refresh §10 of `docs/CODEMAP.md` + re-run `codemap_fingerprint.py --write` in the same commit.
- **Headless status.** At the end (or when asked) print exactly `PLAN_STATUS: EMPTY` if no unchecked
  `[ ]` task remains in `docs/ERROR_PLAN.md`, else `PLAN_STATUS: MORE`.
- Report once, in plain language, including the lane plan.

### "work on the web plan"
Identical to **"How a plan run works"**, with three differences: it drains `docs/WEB_PLAN.md`, it
edits ONLY `apps/web/**` and the `docs/WEB_PLAN*` files (NEVER touch anything outside `apps/web`),
and the single merge **auto-deploys the website via Cloudflare — never run a deploy command or
`wrangler`**. Plan lanes with `python scripts/plan_lanes.py docs/WEB_PLAN.md`. Same pool of up to 8,
same per-task review + local build/test + fold, same single sync-safe self-merge. Anything typed
after is extra detail.
- Active file: `docs/WEB_PLAN.md` (no WEB_PLAN2.md, no lock). It is NOT in the plan-fingerprint
  surface.
- Pre-approved: anything website-safe a task plainly needs. Stop-and-ask (skip that ONE task, leave
  it `[ ]` with a one-line note, continue): a new external dependency, an auth or cost change, a new
  Cloudflare secret, a deleted state file, brand-new architecture, anything touching the form's
  lead-data flow, or anything outside `apps/web`.
- Report once, with the lane plan and the exact preview URLs / live changes Reda can click.

### "add to web plan:" followed by tasks (one per line or separated by ;)
Append them as `[ ]` lines to `docs/WEB_PLAN.md`'s BUILD QUEUE (there is no WEB_PLAN2.md), then commit
on `dev` and self-merge to `main`. Confirm in one line which file you appended to.

### "clean the plans"
Structural plan-file housekeeping (founder rewrite 2026-08-04). This command **NEVER builds, edits,
or implements any task** and makes **no code changes** of any kind. For **PENDING work** the old
guarantees still hold absolutely: it **never rewords a pending task, its ID, or its gating tag**,
**never reorders pending tasks**, **never moves a pending task between queues**, **never decides
priorities**. What changed: it now **restructures** the active files — done tasks leave **with their
emptied menus**, stale scaffolding is condensed out, and the archive is a **condensed story**, not a
verbatim ledger.
- **Scope.** ALL active plan files: `docs/PLAN.md`, `docs/PLAN2.md`, `docs/WEB_PLAN.md`,
  `docs/ERROR_PLAN.md`, `docs/WEB_ERROR_PLAN.md`, `docs/new_tasks_plan.md`,
  `docs/FRONTEND_GAP_PLAN.md`, every `docs/plans/PLAN_*.md` domain file, and any other
  `docs/PLAN*.md` (not `PLAN_HOWTO.md`).
- **What counts as DONE.** Only explicitly checked complete — `[x]` or an equivalent explicit
  "done/shipped" mark. Anything `[ ]`, `[BLOCKED…]`, `[SKIP]`, gated, or ambiguous is NOT done and
  stays, byte-identical. **When in doubt, treat as NOT done and leave it.**
- **Archive condensed into ONE file: `docs/done_task.md`** (create if missing). Done tasks are
  REMOVED from the active file and SUMMARIZED there — per source file, per group/menu: the group
  title, a 1-3 line story (what shipped, when, PR # when noted), then **one short line per task ID**
  (ID + a clause saying what it was) for small/heterogeneous groups — large homogeneous groups
  compress to **explicit ID ranges** (e.g. `FG1–FG106 — module feature-gap audit, all shipped`) with
  a theme summary. Long bodies, acceptance criteria, and evidence paragraphs are
  dropped — `git` history keeps every verbatim word; `done_task.md` keeps just enough to understand
  the story and MUST stay small (target well under ~1,000 lines total; tighten summaries rather than
  grow it). In-file **DONE LOG entries** fold in the same condensed way (keep one empty `## DONE LOG`
  header per active file so future runs can append). The legacy verbatim `docs/DONE.md` is folded in
  condensed too, then **deleted** — its full text stays in git history.
- **Clean the menus.** A group/menu header whose tasks are ALL archived is removed with them (its
  story lives in `done_task.md`). Prose/preamble that refers ONLY to archived work condenses out.
  KEEP: every header that still owns at least one pending task; HOW TO RUN / STANDING RULES /
  ALREADY LIVE / NE PAS FAIRE / GATED sections and every rule, constraint, or note a future run
  needs; all pending tasks in their original order. When unsure whether prose is still load-bearing,
  keep it.
- **Wave-gate ledger (the machinery must never notice the archive).** `docs/done_task.md` opens
  with a machine-readable `plan-progress-ledger` block (`PREFIX=N` lines) counting the archived
  `[x]` tasks per id-prefix from the files `scripts/plan_progress.py` scans; `plan_progress.py`
  folds it back into the default surface, so archiving NEVER lowers a group's `BUILD_ORDER.yml`
  completion (an absent prefix would read 0.0% and re-gate every downstream wave). Every clean run
  recomputes the ledger by diffing the pre-clean files (git HEAD) with
  `plan_progress.count_file` and MUST prove per-prefix done/total/pct equivalence before landing.
- **Model routing (per the model-selection rules).** The ORCHESTRATOR (session model) rewrites
  nothing by hand at scale: it dispatches **one subagent per plan file** (file-disjoint, parallel,
  `sonnet` — condensation is synthesis work; `haiku` only for pure counting/inventory scouting),
  then itself does the judgment: adversarial review of each cleaned file, reconciliation, fingerprint,
  the single merge. Subagents never inherit the session model.
- **Reconcile — mechanical, never guessed.** Before dispatch, snapshot every pending-task line
  (`[ ]`/`[BLOCKED…]`/gated) per file. After: (a) the pending-line set per file is **byte-identical**
  to the snapshot; (b) zero `[x]` tasks remain in active files; (c) every archived task ID is
  covered in `docs/done_task.md` — individually or by an explicit ID range. Any mismatch → STOP and
  report — do not guess.
- **Fingerprint.** `docs/PLAN.md` / `docs/PLAN2.md` / `docs/ERROR_PLAN.md` are in the
  plan-fingerprint surface: refresh §10 "Plan status" of `docs/CODEMAP.md` (paste
  `python scripts/codemap_fingerprint.py --print-plan-status` — `PYTHONIOENCODING=utf-8` on Windows)
  and re-run `python scripts/codemap_fingerprint.py --write` **in the same commit**, then confirm
  `--check` and `python scripts/check_stages.py` green. (`WEB_PLAN.md`, `new_tasks_plan.md`, and the
  `docs/plans/*` domain files are NOT in the surface.)
- **Land it.** Commit on `dev`, get the required CI checks green (docs-only → only the fast gates
  run), then **one sync-safe self-merge to `main`** (merge commit, never squash). If CI is red, do
  not merge — report and stop. No deploy (docs-only; Reda deploys).
- **Report** in plain language: per file, how many done tasks were archived and how many pending
  remain; the size of `done_task.md`; confirm no pending task was reworded, reordered,
  re-prioritized, or built.
