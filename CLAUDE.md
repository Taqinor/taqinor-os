# CLAUDE.md — TAQINOR OS

The rules below come from the founder and are enforced. They override default
assistant behavior. When a rule references a system that does not exist in this
repo yet, the rule still applies to any future integration.

## Non-negotiable rules

1. **Odoo — JSON-2 API only.** All writes to Odoo go through its JSON-2 API.
   Never write to the Odoo database with SQL, under any circumstances.
   (No Odoo integration exists in this repo today; the rule binds any future one.)

2. **Pipeline stage names come from `STAGES.py` — never hardcoded.** Import the
   canonical stage names from `STAGES.py` at the repo root in backend, frontend
   build constants, scripts, and tests. Do not introduce new hardcoded stage
   lists anywhere. CI runs `scripts/check_stages.py` on every push and fails on
   divergence. `STAGES.py` now exists; the canonical 6 keys are NEW, CONTACTED,
   QUOTE_SENT, FOLLOW_UP, SIGNED, COLD (French UI labels live in the same file).
   Do NOT invent or rename stages; ask the founder.
   FUTURE INTENT: the pipeline stage is NOT wired to any table yet. It will live
   on a new CRM `Lead`/`Opportunity` model, to be built in a future session
   together with the new quote engine. Build nothing for it now. This funnel
   stage is a separate, permanent layer from the quote/invoice *document*
   statuses (rule #4) — the two never merge.

3. **Meta Ads CLI — campaigns are born paused.** Any campaign creation through
   the Meta Ads CLI must always carry `--status PAUSED`. Never create an active
   campaign programmatically. (No Meta Ads code exists in this repo today.)

4. **`/proposal` is the only path for client-facing quote PDFs.** Do not add or
   keep alternative code paths that render or deliver quote PDFs to clients.
   SWAP LANDED (2026-06-11): the founder's premium engine is vendored at
   `apps/ventes/quote_engine/` and `/proposal`
   (`GET /api/django/ventes/devis/<id>/proposal/`) is the canonical quote-PDF
   path. `generer-pdf` + the Celery task now route through it (toggle
   `USE_PREMIUM_QUOTE_ENGINE`, default on); the legacy ventes WeasyPrint quote
   PDF stays only as the off-switch fallback — do not extend it. Invoices
   (factures) keep their own legacy PDF — only the QUOTE pdf changed.
   STATUS PRESERVATION: the engine only RENDERS; it does not change statuses.
   Devis (`brouillon`, `envoye`, `accepte`, `refuse`, `expire`) and the
   downstream BonCommande/Facture chains are preserved 1:1 — a separate,
   permanent layer from the `STAGES.py` funnel (rule #2). See
   `docs/quote-engine-swap-map.md`.
   EDIT-BAN LIFTED (2026-06-20, founder): the premium engine
   (`generate_devis_premium.py`) may now be edited for fixes — the former
   "never edit the premium pages" prohibition is removed. `/proposal` stays the
   only client-facing quote-PDF path and STATUS PRESERVATION above still holds.

5. **Scraper policy.** Scrapers must never run from personal accounts. Any
   scraping with Terms-of-Service risk requires BOTH: (a) a risk file committed
   under `tos_risk/` describing target, risk, and mitigation, and (b) explicit
   manual approval from the founder before the first run.

## Repo facts

- A run lands its whole batch as a single self-merge of `dev` → `main` (one merge
  commit, history preserved, 0 approvals). At the START of the run the orchestrator
  computes the file-ownership + dependency graph from the real code and partitions
  the unchecked queue into independent **lanes** (groups that must run in sequence
  because they share a file or depend on each other; different lanes never touch
  each other's files), then fans those lanes out to **up to 8 concurrent worktree
  subagents** — each in its own isolated git worktree, so two tasks never edit the
  same files at once — running them in **waves of up to 8** when there are more
  lanes than that, with tasks inside a lane done in sequence. When the lanes finish,
  every worktree branch is folded into one `dev` branch, the four required CI checks
  run once over the whole batch and gate the single merge, and `main` stays
  revertable: if a merge breaks something, `git revert` restores the previous state.
  There is no per-agent PR and no per-task merge — exactly one merge per run.
- Backend: Django at `backend/django_core` (apps: authentication, stock, crm,
  ventes, reporting, parametres, roles, contact) + FastAPI AI service at
  `backend/fastapi_ia` (OCR via Zhipu AI, natural-language SQL agent via
  LangChain). Frontend: React/Vite at `frontend`.
- Multi-tenant: all business data is scoped by `authentication.Company`. New
  models need a `company` FK; new viewsets must filter querysets by
  `request.user.company` and force-assign `company` in `perform_create` —
  never accept it from the request body.
- **Cross-app boundary — go through `services.py`/`selectors.py`, never another
  app's `models`/`views`.** Between business-core domain apps
  (`apps/{crm,ventes,stock,installations,sav}`), all cross-app READS and WRITES
  route through the TARGET app's `selectors.py` (reads) or `services.py`
  (writes/orchestration) — or through string-FK references — never by importing
  its `models`/`views` directly. Add a thin function to the target app's
  selector/service and call it (keep lazy/function-local imports where they avoid
  cycles). Same-app imports and imports of foundation apps (roles, records,
  authentication, core, customfields, parametres, reporting, etc.) are exempt.
- Run tests: `python manage.py test apps` (inside the django_core container or
  with env vars pointing at a local Postgres).
- Full stack: `docker compose up` (nginx :80, Postgres+pgvector, Redis, MinIO,
  Celery, Django, FastAPI, frontend). Copy `.env.example` to `.env` first.
- Key-gated features (work only with API keys in `.env`): OCR (`ZHIPU_API_KEY`),
  chatbot/SQL agent (`GROQ_API_KEY` or alternative), outbound email/contact
  form delivery (`SENDGRID_API_KEY`; defaults to console backend locally).
- Deploys (apps/web): the public site auto-deploys via **Cloudflare Workers
  Builds** on every push/merge to `main` — that IS the deploy mechanism.
  NEVER ask for a Cloudflare API token (the old one is dead and deleted from
  this PC) and NEVER run `wrangler deploy` manually. Worker secrets
  (LEAD_WEBHOOK_URL, LEAD_WEBHOOK_SECRET…) are dashboard-only — changing one
  is a manual step for the founder.
- Backend production URL: `https://api.taqinor.ma` (canonical since 2026-06);
  the old `https://178-105-192-116.sslip.io` still answers (same server, same
  Caddy block). `taqinor-web.taqinor.workers.dev` 301-redirects to
  `https://taqinor.ma` (wrapper in `apps/web/worker/`, installed at build by
  the `workersDevRedirect` hook in `apps/web/astro.config.mjs`).
- **Public contact form is PARKED (off by default).** The landing-page contact
  form is disabled: the `apps/contact` endpoint (`/api/django/contact/`) returns
  404 and sends no email when off, and the landing CTAs route to `/login`
  instead of opening the form. The code is intact behind two flags. To re-enable
  in one step: set `CONTACT_FORM_ENABLED=1` and `VITE_CONTACT_FORM_ENABLED=1` in
  `.env`, then `docker compose up -d --build` (the frontend flag is a build-time
  arg, so a rebuild is required). To park again: set both back to `0` and rebuild.
- **Quote generator (2026-06).** `/ventes/devis/nouveau` is the creation screen
  (Sami's modal is edit-only), a faithful port of RedaSolar/devis-simulator
  with three market modes: Résidentiel (simulator behaviour), Industriel/
  Commercial (autoconsommation étude: taux d'autoconsommation/couverture,
  économies, payback, stored in `Devis.etude_params`), Agricole (pompage:
  pump CV/type/alim/HMT/débit inputs, array ≈1.4× pump kW, matched
  VFD/coffret, no battery/inverter). The screen is 100 % TTC and must NEVER
  snap/reject typed numbers (form `noValidate`, all inputs `step="any"` —
  guarded by a test). Solar math + auto-fill live in
  `frontend/src/features/ventes/solar.js`; keep its classification keywords
  aligned with `quote_engine/builder.py` (réseau/injection, hybride,
  batterie, panneau) — the PDF option split depends on line designations.
- **Quote PDFs.** One vendored engine
  (`apps/ventes/quote_engine/generate_devis_premium.py`) renders all formats,
  selected via the list's PDF dialog →
  `generer-pdf` body / `/proposal` query params (whitelist in
  `clean_pdf_options`): premium 'full' = 3 pages, +`include_etude` = 4 pages
  (degrades to 3 without étude data), 'onepage' = 1 page (adaptive density:
  full descriptions ≤8 lines, short 9–12, compact >12 — never overflows).
  PDFs show per-line P.U./Total HT with an explicit visible
  Sous-total HT → Remise (X %) → Total HT → TVA → Total TTC chain, a system
  summary (kWc/production/économie/prix-kWc, or pompe/débit/HMT), and rich
  product sheets from `Produit.marque/description/garantie`. Page counts are
  enforced per format in `apps/ventes/tests/test_quote_engine.py`.
- **CRM leads.** Leads are full solar records (contact incl. WhatsApp/GPS,
  pipeline incl. owner/canal/priorité/tags/relance/type_installation/
  motif_perte, energy profile incl. bills + `ete_differente` toggle +
  82-21 flag, roof & site, light survey) with an Odoo-style chatter
  (`crm.LeadActivity`: automatic old→new field logs + manual notes via
  `historique`/`noter` endpoints; acting user and company always
  server-side). Lead-primary quoting: a Devis can carry `lead` + `client`;
  client is resolved server-side from the lead
  (`apps/crm/services.resolve_client_for_lead` — reuse link, else
  company-scoped email match, else create; never duplicates).
- **Reference numbering**: NEVER count()+1. Use
  `apps/ventes/utils/references.py` (highest-used+1 per company+month,
  savepoint + retry on races) — count-based numbering collided in
  production.
- **Catalogue seeding**: `manage.py seed_catalogue` (idempotent, additive
  only; never touches existing prices/quantities) seeds the simulator
  catalogue + Pompage items and re-applies product sheets
  (marque/description/garantie only). Small-pump prices are market estimates
  flagged "à confirmer" with buy prices left at 0 for the founder.
  2026-06-12: 16 VEICHI variateurs carry the founder's REAL prices (sell
  public TTC + revendeur buy into `prix_achat`); the 6 estimated
  coffret-variateur placeholders are ARCHIVED by the seeder
  (founder-authorized exception, never deleted). 11 OSP 30-series pumps ship
  with manufacturer curves (`Produit.courbe_pompe` debit→HMT + `pompe_kw`,
  `tension_v`) and DELIBERATELY EMPTY prices: excluded from auto-fill and
  greyed "prix à renseigner" until the founder prices them.
  `Produit.prix_achat` powers a GENERATOR-ONLY margin indicator —
  it must never appear in any PDF or client-facing output.
- **Pompage sizing (2026-06-12)**: HMT + débit souhaité (m³/h) select the
  smallest curve pump that delivers enough at that HMT (interpolation in
  `solar.js debitAtHmt`); matching VEICHI variateur (smallest kW ≥ pump kW,
  tension 220/380 assortie) + one AFFICHEUR SI22 line added by default.
  m³/jour = débit@HMT × heures de pompage (editable, default 7 h), computed
  ONCE at quote creation, stored in `etude_params`, rendered identically on
  screen and the one-page PDF. Never print m³/jour for curve-less pumps —
  omit the card. Pompage compositions contain NO inverter and NO battery,
  and auto-fill never quotes a price-less product (all guarded by tests).

## Workflow

These rules govern HOW work gets done and landed.

- **Fewest steps.** Default to the fewest steps that do exactly what was asked.
  Never add ceremony. Never do extra or adjacent work that wasn't requested —
  don't go resolve unrelated gated items, don't restructure neighboring files,
  don't create files nobody asked for.
- **One run, one self-merge to main — with maximum safe parallelism.** All work
  happens in one session. At the START the run computes the file-ownership +
  dependency graph from the real code and partitions the unchecked queue into
  independent lanes, then fans them out to **up to 8 concurrent worktree subagents**
  (each in its own isolated git worktree, so two tasks never edit the same files at
  once), in **waves of up to 8** when there are more lanes than that; tasks inside a
  lane run in sequence and ownership is derived from the real code, not from guesses.
  Each subagent commits its lane's tasks to its own worktree branch the moment each
  lands. At the end every worktree branch is folded into one `dev` branch, CI runs
  once over the whole batch, and when the four required checks are green the run
  self-merges `dev` → `main` exactly once (a single merge commit, history preserved,
  0 approvals), which auto-deploys the whole batch. There is no per-agent PR, no
  per-task merge, no admin-merge bypass, and no deploy command.
- **Safety model: CI gate + revertable main.** The four required checks
  (backend-lint, backend-tests with MinIO, frontend-lint, stage-names) gate every
  merge with 0 approvals, and `main` stays revertable: if a merge breaks something,
  `git revert` restores the previous state. Keep this branch protection exactly as
  configured — do not loosen, bypass, or add approval steps to it.
- **Touch only the named files.** Only edit the files explicitly named in the
  request. Asked to change two files means change exactly those two. Never
  create alternate or fallback files.
- **Several commands in one request** are all handled in the one session and land
  in the one self-merge to `main` — never split across multiple merges or sessions.

### "work on the plan"
Anything typed after the command is extra detail for that run.
- The active file is `docs/PLAN.md`. There is no `.running` lock — there is only
  ever one session at a time.
- Read it fully and verify real repo state.
- **DRAIN THE QUEUE — one run works through ALL unchecked tasks, never just one,
  with MAXIMUM SAFE PARALLELISM.** At the START of the run, compute the
  file-ownership + dependency graph from the real code (which source files each
  unchecked `[ ]` task must write) and **partition the queue into independent lanes**
  — a lane is a group of tasks that must run in sequence because they share a file or
  depend on each other; different lanes never touch each other's files. Process EVERY
  unchecked `[ ]` task in the BUILD QUEUE. **Fan the lanes out to concurrent
  subagents, each launched with worktree isolation (`isolation: worktree`)** so no
  two ever edit the same files. Spawn them concurrently — do NOT finish one before
  starting the next — up to a ceiling of **8 worktree subagents running at once**;
  with more than 8 lanes, run them in **waves of up to 8**; with fewer, use fewer
  agents. **Tasks inside one lane run in sequence.** Each subagent builds its lane's
  tasks completely with tests and, as each lands, commits it to **its own worktree
  branch**, ticks it `[x]`, and adds one dated line to the DONE LOG — so an
  interrupted run loses nothing and re-firing resumes from the first still-unchecked
  task. CI runs once at the end over the whole batch (see below), not per task or per
  agent. This processes EVERY unchecked task; it does NOT end the run after the first.
- **Engine — default to a dynamic workflow with review; fall back to parallel
  subagents; NEVER single-serial.** The default way to run the lanes is a
  **dynamic workflow with a fan-out-and-verify shape**: one subagent per
  independent task, each in its own git worktree, **plus a separate adversarial
  review agent that checks every finished change against the standing safety
  rules and that task's acceptance criteria before the change is eligible to
  merge — nothing folds into `dev` or merges until its review passes.** When the
  workflow engine isn't available (e.g. a phone or cloud session), **fall back to
  the same lane-planned worktree subagents**, with the orchestrator itself
  reviewing each lane against the safety rules before folding it in. **Never fall
  back to a single serial, one-task-at-a-time agent** — parallel lanes with review
  are the floor, not the ceiling.
- **A run stops ONLY when one of these is true — nothing else licenses
  stopping:**
  1. **Queue drained** — no buildable unchecked `[ ]` tasks remain in the BUILD
     QUEUE.
  2. **Usage/length cap hit** — stopping here is fine; the plan is idempotent, so
     re-firing "work on the plan" resumes from the first still-unchecked task.
  3. **A task hits a genuine stop-and-ask condition** — a new external
     dependency, a schema/destructive migration, an auth or cost change, a
     deleted state file, a brand-new architectural component, or a conflict with a
     non-negotiable rule. Mark it `[BLOCKED: <reason>]`, move it to GATED, and
     CONTINUE the remaining tasks. A single blocked task must NEVER halt the whole
     run.
- **There is no "one task per session" / "stop after one task" / "merge per task"
  limit.** Any such wording anywhere — including older lines in `docs/PLAN.md`,
  `docs/PLAN2.md`, or `docs/WEB_PLAN.md` — is overridden by this rule: keep going
  until the queue is drained or a cap/limit above stops you. Do not invent a stop
  after the first task, and do not merge after each task.
- Database migrations a task needs (additive) are approved. New external
  dependencies, auth or cost changes, deleted state, or brand-new architecture
  are stop-and-ask (condition 3) — skip those and list them.
- **Refresh the code map when structure changed.** If the run added or changed any
  backend models, API endpoints, frontend routes or features, or the service/module
  structure, regenerate `docs/CODEMAP.md` from the actual source (re-derive the
  facts and update its `Generated from commit` header), then run
  `python scripts/codemap_fingerprint.py --write` so the stored
  `Structure fingerprint:` updates together with the map, then commit both on `dev`
  before the final merge. The required `stage-names` CI job re-runs that script in
  `--check` mode, so a structural change that does not refresh the map (and its
  fingerprint) fails CI and cannot merge. This is cheap and idempotent: SKIP it
  entirely on docs-only runs and on any run that touched none of those — when
  nothing structural moved, do not regenerate.
- **Refresh the plan-status section whenever task states change — in the SAME
  commit as the tick.** The moment a run ticks a task `[x]`, marks one `[BLOCKED]`,
  or adds/removes a task in `docs/PLAN.md` or `docs/PLAN2.md`, regenerate §10 "Plan
  status" of `docs/CODEMAP.md` from the plan files (paste
  `python scripts/codemap_fingerprint.py --print-plan-status` into the section and
  refresh its cross-check-vs-`main` notes + the `Generated from commit` stamp), then
  run `python scripts/codemap_fingerprint.py --write` so the stored
  `Plan fingerprint:` updates together with the section — and stage all of it in the
  **same commit** as the task tick so the tick and the status refresh land
  atomically. The required `stage-names` CI job re-runs that script in `--check`
  mode, so a tick/add/remove that does not refresh §10 (and its plan fingerprint)
  fails CI and cannot merge. Unlike the structure fingerprint, this is NOT
  skippable on docs-only runs: ticking a task IS a plan-state change. (Editing only
  a `[BLOCKED]` reason's wording, reordering the lists, or appending a DONE LOG line
  does not move the plan fingerprint, so it needs no refresh.)
- When the run stops, **fold every worktree branch into one `dev` branch**, get the
  four required CI checks green over the whole batch, then self-merge `dev` → `main`
  exactly once (a single merge commit, no per-agent PR, no per-task merge). This
  merge auto-deploys to api.taqinor.ma; never run a deploy command.
- **Sync-safe single merge — OS and web runs may run at the same time on this one
  `main`.** The two commands own different folders so their code never collides,
  but both land on the same `main` and both may touch shared files (`CLAUDE.md`,
  the plan files, `docs/CODEMAP.md`). So the single self-merge is sync-safe:
  **right before merging, fetch and integrate the latest `origin/main` into this
  run's `dev`** (merge `main` in — do **not** rebase published history, **never
  force-push**). If integrating `main` changed the code-structure surface,
  **recompute the CODEMAP structure fingerprint on the integrated tree** (the same
  fingerprint the `stage-names` check verifies) so it isn't stale on the merged
  result. **Re-run the full CI suite once on the integrated state and self-merge
  to `main` only when it is green.** If the push is rejected because `main`
  advanced again, **repeat — fetch, integrate, recompute the fingerprint if
  needed, re-run CI, push — never force, never overwrite the other run's
  commits.** A run only ever edits the shared files (`CLAUDE.md` / **its own**
  plan file / `docs/CODEMAP.md`) for **its own** command's lane, and ships that
  small change inside this **same single merge**.
- Report once, in plain language, and **include the lane plan**: how many lanes ran
  in parallel and what each shipped, plus what was skipped and why.

### "add to plan:" followed by tasks (one per line or separated by ;)
- Append them as `[ ]` lines to `docs/PLAN.md`'s BUILD QUEUE, then refresh §10
  "Plan status" of `docs/CODEMAP.md` and re-run
  `python scripts/codemap_fingerprint.py --write` in the same commit (adding a task
  moves the plan fingerprint, so the `stage-names` check fails otherwise), then
  commit on `dev` and self-merge to `main`. Confirm in one line.

### "work on error plan"
Identical to `work on the plan` in every respect — same lane partitioning, same
**up to 8 concurrent worktree subagents in waves of 8**, same
dynamic-workflow-with-adversarial-review engine (fall back to parallel worktree
subagents; never a single serial one-task-at-a-time agent), same stop conditions
(queue drained / usage cap / a genuine stop-and-ask → mark `[BLOCKED: <reason>]`,
move to GATED, and CONTINUE the rest), same verify-each-task-isn't-already-built
step (mark `[x] (already present)` when it is), same commit-tick-DONE-LOG per task
on each lane's own worktree branch, same CODEMAP refresh rules, and the same
**sync-safe single self-merge `dev` → `main`** (integrate the latest `origin/main`
first, recompute the structure fingerprint if the structural surface moved, re-run
the full CI suite once over the whole batch, never force-push) — **with EXACTLY ONE
difference: it drains `docs/ERROR_PLAN.md`** (the bug/error backlog) instead of
`docs/PLAN.md` / `docs/PLAN2.md`. Anything typed after the command is extra detail
for that run.
- **No lock — same as `work on the plan`.** There is no `.running` lock; only ever
  one session at a time, and the sync-safe single merge is what keeps `main`
  collision-free even when an OS-plan, web-plan, or error-plan run lands
  concurrently. (So there is no `reset the plan lock` to mirror.)
- **Plan-status wiring.** `docs/ERROR_PLAN.md` is registered in
  `scripts/codemap_fingerprint.py` (`PLAN_FILES`) exactly like the other plan files,
  so ticking / adding / removing an `ERR*` task moves the plan fingerprint: refresh
  §10 "Plan status" of `docs/CODEMAP.md` (paste `--print-plan-status`) and re-run
  `python scripts/codemap_fingerprint.py --write` in the SAME commit as the tick, or
  the required `stage-names` CI job fails.
- **Headless-loop status.** When asked — or at the end of a run — print exactly
  `PLAN_STATUS: EMPTY` if no unchecked `[ ]` task remains in `docs/ERROR_PLAN.md`,
  otherwise `PLAN_STATUS: MORE`, so the same headless loop that drives
  `work on the plan` can drive this command too.
- Report once, in plain language, including the lane plan.

### "work on the web plan"
The website autopilot stays strictly inside `apps/web/**` plus its own
`docs/WEB_PLAN*` files. Anything typed after the command is extra detail.
- The active file is `docs/WEB_PLAN.md`. There is no WEB_PLAN2.md and no
  `.running` lock — only ever one session at a time.
- Read it fully and verify real repo state. Scope: edit ONLY `apps/web/**` and
  the `docs/WEB_PLAN*` files. NEVER touch anything outside apps/web.
- **DRAIN THE QUEUE — one run works through ALL unchecked tasks, never just one,
  with MAXIMUM SAFE PARALLELISM.** At the START of the run, compute the
  file-ownership + dependency graph from the real code (which source files each
  unchecked `[ ]` task must write) and **partition the queue into independent lanes**
  — a lane is a group of tasks that must run in sequence because they share a file or
  depend on each other; different lanes never touch each other's files. Process EVERY
  unchecked `[ ]` task in the BUILD QUEUE. **Fan the lanes out to concurrent
  subagents, each launched with worktree isolation (`isolation: worktree`)** so no
  two ever edit the same files. Spawn them concurrently — do NOT finish one before
  starting the next — up to a ceiling of **8 worktree subagents running at once**;
  with more than 8 lanes, run them in **waves of up to 8**; with fewer, use fewer
  agents. **Tasks inside one lane run in sequence.** Each subagent builds its lane's
  tasks completely with tests and, as each lands, commits it to **its own worktree
  branch**, ticks it `[x]`, and adds one dated line to the DONE LOG — so an
  interrupted run loses nothing and re-firing resumes from the first still-unchecked
  task. CI runs once at the end over the whole batch (see below), not per task or per
  agent. This processes EVERY unchecked task; it does NOT end the run after the first.
- **Engine — default to a dynamic workflow with review; fall back to parallel
  subagents; NEVER single-serial.** The default way to run the lanes is a
  **dynamic workflow with a fan-out-and-verify shape**: one subagent per
  independent task, each in its own git worktree, **plus a separate adversarial
  review agent that checks every finished change against the standing safety
  rules and that task's acceptance criteria before the change is eligible to
  merge — nothing folds into `dev` or merges until its review passes.** When the
  workflow engine isn't available (e.g. a phone or cloud session), **fall back to
  the same lane-planned worktree subagents**, with the orchestrator itself
  reviewing each lane against the safety rules before folding it in. **Never fall
  back to a single serial, one-task-at-a-time agent** — parallel lanes with review
  are the floor, not the ceiling.
- **A run stops ONLY when one of these is true — nothing else licenses
  stopping:**
  1. **Queue drained** — no unchecked `[ ]` tasks remain in the BUILD QUEUE.
  2. **Usage/length cap hit** — stopping here is fine; the plan is idempotent, so
     re-firing "work on the web plan" resumes from the still-unchecked tasks.
  3. **A task hits a genuine stop-and-ask condition** — a new external
     dependency, an auth or cost change, a new Cloudflare secret the founder
     hasn't set, a deleted state file, or a brand-new architectural component.
     SKIP that ONE task (leave it `[ ]` with a one-line note of why) and CONTINUE
     the remaining tasks. A single stop-and-ask task must NEVER halt the whole
     run.
- **There is no "one task per session" / "stop after one task" / "merge per task"
  limit** — and this rule explicitly OVERRIDES any contrary wording in
  `docs/WEB_PLAN.md` itself (e.g. "exactly one task… and stops", "Do not start the
  next task", "One session = one task"). Keep going until the queue is drained or a
  cap/limit above stops you. Do not invent a stop after the first task, and do not
  merge after each task.
- Pre-approved: anything website-safe a task plainly needs. Stop-and-ask
  (condition 3 — skip and list): new external dependencies, auth or cost changes,
  deleted state files, brand-new architecture, anything touching the form's lead
  data flow, anything outside apps/web.
- When the run stops, **fold every worktree branch into one `dev` branch**, get CI
  green over the whole batch, then self-merge `dev` → `main` exactly once (a single
  merge commit, no per-agent PR, no per-task merge) — this auto-deploys the site via
  Cloudflare on merge; never run a deploy command.
- **Sync-safe single merge — OS and web runs may run at the same time on this one
  `main`.** The two commands own different folders so their code never collides,
  but both land on the same `main` and both may touch shared files (`CLAUDE.md`,
  the plan files, `docs/CODEMAP.md`). So the single self-merge is sync-safe:
  **right before merging, fetch and integrate the latest `origin/main` into this
  run's `dev`** (merge `main` in — do **not** rebase published history, **never
  force-push**). If integrating `main` changed the code-structure surface,
  **recompute the CODEMAP structure fingerprint on the integrated tree** (the same
  fingerprint the `stage-names` check verifies) so it isn't stale on the merged
  result. **Re-run the full CI suite once on the integrated state and self-merge
  to `main` only when it is green.** If the push is rejected because `main`
  advanced again, **repeat — fetch, integrate, recompute the fingerprint if
  needed, re-run CI, push — never force, never overwrite the other run's
  commits.** A run only ever edits the shared files (`CLAUDE.md` / **its own**
  plan file / `docs/CODEMAP.md`) for **its own** command's lane, and ships that
  small change inside this **same single merge**.
- Report in plain language (no diffs, no commit hashes), and **include the lane plan**
  (how many lanes ran in parallel and what each shipped): every task that shipped,
  what was skipped and why, and the exact preview URLs or live changes Reda can
  click.

### "add to web plan:" followed by tasks (one per line or separated by ;)
- Append them as `[ ]` lines to `docs/WEB_PLAN.md`'s BUILD QUEUE (there is no
  WEB_PLAN2.md), then commit on `dev` and self-merge to `main`. Confirm in one line
  which file you appended to.

### "clean the plans"
Pure plan-file housekeeping. This command **NEVER builds, edits, or implements any
task**, never runs a feature/dependency/database/CI change, and makes **no code
changes** of any kind. It **NEVER changes the wording of a task, its ID, or its
gating tag**; it **NEVER reorders tasks**; it **NEVER moves a not-done task from one
queue to another**; it **NEVER decides priorities**. It does exactly one thing: it
**relocates COMPLETED tasks** out of the active plan files into a single archive,
leaving every not-done task exactly where — and in the order — it already is.
- **What counts as DONE.** A task is DONE only if it is **explicitly checked
  complete** — a `[x]` checkbox or an equivalent explicit "done/shipped" mark.
  Anything unchecked `[ ]`, `[BLOCKED…]`, `[SKIP]`, gated, or ambiguous is **NOT
  done** and stays in its active plan file, untouched. **When in doubt, treat a task
  as NOT done and leave it where it is.**
- **Move (do not copy) into one archive.** Move every DONE task from **every active
  plan file** (`docs/PLAN.md`, `docs/PLAN2.md`, `docs/WEB_PLAN.md`, and any other
  `docs/PLAN*.md`) into **`docs/DONE.md`** (create it if missing), **grouped under a
  heading per source file** (e.g. `## Archived from PLAN.md`), **preserving each
  task's original text verbatim** (for a header-format task that is the `###` header
  **and** its body). After the move, that done task **no longer appears** in the
  active plan file. If a **DONE LOG / done section** already exists inside a plan
  file, **fold those entries into `docs/DONE.md` too** (under a per-file heading), so
  done history lives in one place — keep the DONE LOG **header + scaffolding** in the
  active file so future runs can still append.
- **Touch nothing else.** The active plan files keep **all their structure** —
  headers, HOW TO RUN, STANDING RULES, GATED/MANUAL sections, cross-cutting
  constraint notes, dividers, and every not-done task — **exactly as written**. Only
  completed task **lines/blocks** are removed. **Do not delete or reword any rule,
  header, prose note, or not-done task.** (Emptying a section of its done tasks is
  fine — the header stays.)
- **Reconcile — never guess.** Confirm **no task was lost or duplicated**: the count
  of (done tasks now in `docs/DONE.md`) **plus** (not-done tasks still in the active
  files) must equal the total task count **before** you started. The strongest check
  is line-level: every original line must end up in exactly one place (active file or
  `docs/DONE.md`), none lost, none duplicated, none altered. **If the numbers do not
  reconcile, STOP and report — do not guess.**
- **Fingerprint.** Moving done tasks out of `docs/PLAN.md` / `docs/PLAN2.md` changes
  the **plan-fingerprint surface**, so refresh §10 "Plan status" of
  `docs/CODEMAP.md` (paste `python scripts/codemap_fingerprint.py
  --print-plan-status` + its totals/stamp) and re-run
  `python scripts/codemap_fingerprint.py --write` **in the same commit** — this is a
  legitimate plan edit, not a code change — then confirm `python
  scripts/codemap_fingerprint.py --check` and `python scripts/check_stages.py` are
  green. (`docs/WEB_PLAN.md` is **not** in the plan-fingerprint surface.) If unsure
  whether re-stamping is correct, STOP and ask rather than forcing it.
- **Land it.** Commit on `dev`, get the required CI checks green (a docs-only change
  runs only `stage-names`; the heavy jobs skip), then **self-merge `dev` → `main`
  exactly once** (one merge commit, no PR, sync-safe per the STANDING RULES). If CI
  is red, do **not** merge — report what failed and stop.
- **Report** in plain language only (no diffs, no hashes): per file, **how many done
  tasks were archived** to `docs/DONE.md` and **how many not-done tasks remain**, and
  confirm nothing was reordered, reworded, re-prioritized, or built. It never reports
  code changes because it makes none.
