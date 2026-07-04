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

- **A run drains the whole plan as ONE continuous work-stealing pipeline and lands
  it as exactly ONE self-merge `dev` -> `main` at the very end** -- one merge commit,
  one CI run, one deploy, history preserved, 0 approvals, `main` always revertable
  via `git revert`. Never a merge per task, per wave, or per batch. The full model
  is **"How a plan run works"** under `## Workflow`.
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
- **Import contracts are CI-enforced (M3).** `backend/django_core/.importlinter`
  pins the decoupling already achieved and the `lint-imports` step (in the
  `backend-lint` CI job) fails on a regression: the five core domain *models*
  must stay mutually decoupled (string FKs only — the M1 win), and the `core`
  app must stay a base foundation layer (it never imports a domain-core or
  satellite app). A full no-cycles/strict-layers contract is deferred until the
  deeper service-layer decoupling lands.
- **Domain-event layer for cross-app reactions (M6).** `core/events.py` holds a
  small Django-signal event bus (foundation, depends on nothing). Apps react to
  another app's state change by subscribing in their `apps.py` `ready()` rather
  than being called directly — e.g. `ventes` emits `devis_accepted` on quote
  acceptance and `crm` subscribes (`apps/crm/receivers.py`) to advance the lead
  stage. Signals fire synchronously, so behaviour is identical to the old direct
  call.
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
- **ERP backend/frontend deploy — `scripts/deploy-prod.ps1` (NOT auto on merge).**
  Unlike the website, the ERP itself (Django + React on the Hetzner prod server,
  `api.taqinor.ma`) does **not** auto-deploy when `main` merges — a merge alone
  changes nothing the user sees in the ERP. Bring `main` live by running
  `powershell -File scripts/deploy-prod.ps1` (SSHes in with
  `~/.ssh/taqinor_hetzner`, `git reset --hard origin/main`, rebuilds the compose
  images, runs migrations + `init_roles`, restarts nginx, reloads Caddy, warms the
  PDF engine). **Claude SHOULD run this when asked to deploy, or after a merge that
  needs to reach the ERP** — it is the canonical ERP deploy and is not "the
  founder's job." (Only the public website auto-deploys, via Cloudflare; never run
  `wrangler` for that.)
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
  Never add ceremony. Never do extra or adjacent work that wasn't requested --
  don't resolve unrelated gated items, restructure neighboring files, or create
  files nobody asked for.
- **Touch only the named files.** Only edit the files explicitly named in the
  request. Asked to change two files means change exactly those two. Never create
  alternate or fallback files.
- **Several commands in one request** are all handled in the one run and land in
  the one merge to `main` -- never split across multiple merges or sessions.

### How a plan run works (applies to EVERY plan command)

A plan run drains the plan's whole BUILD QUEUE as **one continuous work-stealing
pipeline** and lands the entire run as **exactly ONE merge to `main` at the very
end**. NEVER one task at a time, NEVER a merge per wave or per batch. This is the
ONLY run model -- it OVERRIDES any older "waves", "one merge per wave", "one task
per session", or "stop after one task" wording anywhere, including in the plan
files themselves.

**THE COST MODEL (why the method below is the fast one -- internalize this).** The
single dominant cost of a run is the GitHub CI `backend-tests` gate: **~40 minutes,
serialized, per merge**. So the run's speed is set by ONE number: how many times you
pay that 40 minutes. Pay it **ONCE per run**. Merging "a batch of 5" then waiting for
its CI before starting the next 5 pays 40 min x N and is the slowest possible shape
(it is the trap -- do not do it). Two levers, always:
  (a) **Lane-draining** -- one agent drains a WHOLE app lane (8-10 tasks), so ~9
      single-task waves collapse into ~1; and
  (b) **One merge per run** -- accumulate every lane onto one branch and pay CI once.
**MERGE FLOOR (founder rule, Reda — raised 2026-06-30): never merge to `main` with
fewer than ~200 completed tasks accumulated on the branch.** Keep draining more app
lanes in parallel and folding them onto the one branch until you have ≥200 done; THEN
run the single CI + merge + deploy. Merging a small handful (5, 13, 80, …) is forbidden
-- it pays the 40-min CI for almost nothing. The ONLY time you merge with fewer than 200
is when the buildable queue is genuinely exhausted (every remaining task is
blocked/gated/deferred or in a concurrent session's dirty apps) -- then merge what you
have. To reach ≥200 you will run MANY lanes (often 8 at the concurrency cap, refilled as
they finish) across many apps in one run, AND second-round same-app lanes that first
`git merge` the integration branch to inherit the round-1 migration chain (so their
migrations chain instead of colliding); that is expected and correct, and a single run
legitimately spans many wakeups accumulating onto the one branch before the single merge.
If a mid-run merge is ever unavoidable (e.g. a same-app lane needs a prior task on
`origin/main` to chain migrations), then while that ONE CI runs you **pipeline the
next lanes on DISJOINT apps** (build during CI, never idle on it), and you reuse ONE
persistent local test DB across folds (`--keepdb`, same DB name -- a fresh full test
DB is a ~13-min rebuild; reusing it makes each fold's check ~2 min).

1. **Plan the lanes once.** At the start run `python scripts/plan_lanes.py
   <planfile>` to get the file-ownership + dependency graph. A **lane** = tasks
   that share a file/migration and must run in sequence; independent lanes run
   concurrently. (Drain `docs/PLAN2.md` before `docs/PLAN.md`.)

2. **Lane-draining is the unit of work: one agent OWNS one app and drains its
   WHOLE lane.** Dispatch up to ~8 worktree subagents (`isolation: worktree`) in
   parallel; **each agent owns one `apps/<x>` and drains that app's ENTIRE pending
   queue in sequence in one go** -- for each task: verify-not-built -> build with
   tests -> flake8 + compileall (LIGHTWEIGHT static checks ONLY) -> commit that task
   by itself -> next, building on the last (its migrations chain inside its own
   worktree). **One agent = many tasks, never one.** This is what collapses ~9
   single-task waves into ~1. Give each agent the explicit ordered list of its app's
   task IDs. A task that hits a true blocker is marked `[BLOCKED]` and SKIPPED -- the
   lane keeps going. Agents do NOT build a full test DB or spawn Postgres/their own
   containers (that thrashes the shared DB and OOM-kills it); the orchestrator runs
   the ONE real combined test after folding. Cross-app: each agent keeps ALL its code
   inside its own app, reading other apps only via their existing `selectors.py` or
   string-FKs -- so file-disjoint lanes fold with zero conflict. When a same-app lane
   tail needs a just-built prior task, that prior task must be on `origin/main` first
   (worktree agents branch from `origin/main`) -- so order is: build a lane's
   available head tasks, land them, then the tail; or split the lane across runs.

3. **Orchestrator reviews each lane + runs ONE combined local test after folding.**
   As each lane agent returns, adversarially review its commits against the safety
   rules + acceptance criteria. Fold all file-disjoint lanes onto the one accumulating
   branch, then run a SINGLE combined test in the local prod docker image over all the
   run's new test modules (reuse ONE persistent `--keepdb` test DB across folds). This
   combined test is the real pre-merge feedback -- it has caught a real bug in most
   runs (missing import, `clean()`-vs-`save()`, name clash, hard-vs-soft-delete, a
   silently-swallowed effect). Fix any failure, re-run only the affected module
   (`--keepdb` makes it seconds), then proceed to the single gate. It is NOT the
   GitHub CI, which runs only once at the very end.

4. **Fold continuously into ONE `dev` branch + advance LOCAL `main`.** As each
   reviewed+tested task passes: fold its branch into the single accumulating `dev`
   branch, tick it `[x]`, add one dated DONE LOG line, and **fast-forward LOCAL
   `main` to the `dev` tip -- locally only: never push, never open a PR, never run
   GitHub CI between tasks.** This is what lets later same-app tasks inherit prior
   migrations; advancing LOCAL `main` is NOT a merge.

5. **ONE gate at the very end.** When the queue drains (or a cap is hit): refresh
   `docs/CODEMAP.md` if structure/plan changed (then `codemap_fingerprint.py
   --write`), integrate the latest `origin/main` into `dev` (sync-safe -- merge it
   in, recompute the structure fingerprint if the structural surface moved, NEVER
   force-push), push `dev`, run the four required checks **once** over the whole
   batch, self-merge `dev` -> `main` **exactly once**, then **deploy once**
   (`scripts/deploy-prod.ps1` for the ERP; the website auto-deploys via Cloudflare).
   When branch protection requires it, ONE batch PR used purely as the CI-gated
   merge vehicle counts as that single self-merge. If the push is rejected because
   `main` advanced, repeat the sync-safe integrate -> CI -> merge -- never force.

**Engine.** Prefer a dynamic `Workflow` `pipeline()` (build -> review -> local-test
-> fold as independent stages with no barriers; concurrency auto-caps at ~8 =
native work-stealing). Fall back to manually-dispatched worktree subagents with the
SAME refill-on-completion rule. NEVER a single serial one-task-at-a-time agent, and
NEVER a merge per wave/task.

**Model selection (per task/role) — auto-pick; do NOT run everything on the session
model (founder rule, Reda).** In a plan run the ORCHESTRATOR (the main loop) keeps the
session model -- for a plan run that is Opus, and it is NEVER downgraded: that is where
the costly judgment lives (lane planning, adversarial review, real-vs-environmental
failure triage, revert/keep calls, migration-chain orchestration, the ONE combined
test, CODEMAP/fingerprint/DONE-LOG bookkeeping, and the merge+deploy gate). But each
BUILD subagent is dispatched on the CHEAPEST model that fits its lane, via the `Agent`
tool's `model:` param (or `Workflow` `agent()` `opts.model`) -- this holds EVEN WHEN the
session was started on Opus (downgrade the builders, keep orchestration on Opus):
  - **haiku** -- mechanical / low-risk lanes: DC "single-source-of-truth" wiring,
    verify-and-skip / already-present-heavy lanes, small additive CRUD, no cross-app
    writes, trivial-or-no migration.
  - **sonnet** (DEFAULT for building) -- standard feature lanes: new
    models+migrations+viewsets+tests, cross-app reads via `selectors.py`, multi-tenant
    discipline, moderate logic. This is the bulk of lanes.
  - **opus** -- high-risk lanes ONLY: the quote engine (RULE #4), `core` foundation
    under import-linter contracts, auth/permissions/security, destructive migrations,
    brand-new cross-app ARCH/event flows. ALSO escalate: any lane a cheaper agent
    returns `[BLOCKED]`/uncertain gets re-run one tier up.
  The orchestrator still adversarially reviews + locally tests EVERY lane regardless of
  which model built it, so a cheaper builder never lowers the merge bar. (If a run is
  ever started on Sonnet/Haiku the driver can't be upgraded -- orchestration judgment is
  then bounded by that model; per-task build-model choice still applies.)

**The SAME per-task rule applies to RESEARCH / AUDIT / any multi-agent workflow, not just
plan-build runs (founder rule, Reda — added 2026-07-04 after an all-Fable audit burned ~4x
the tokens it needed to).** NEVER let subagents silently inherit the session model -- ALWAYS
set the model on every `Agent` call / `Workflow` `agent()` `opts.model`, picking the cheapest
that fits the job:
  - **haiku** -- scouting: web search / WebFetch, file reads, greps, "verify-and-skip",
    mechanical extraction. Googling docs and grepping the repo needs zero frontier reasoning.
  - **sonnet** (DEFAULT for subagents) -- research synthesis, gap analysis, feature/task
    drafting, standard per-domain audit lanes. Bulk of the work.
  - **opus** -- adversarial verification, cross-domain dedupe, completeness synthesis,
    security/architecture judgment, the merge/report gate (the orchestrator itself).
  - **fable** -- RESERVED for the 1-3 passes per run where frontier reasoning materially
    changes the outcome (a final completeness critic; a decisive synthesis) AND only when Reda
    asked for a "full checkup / go deep". NEVER the default for a fleet of scouts/verifiers.
    Fable is the MOST capable AND MOST EXPENSIVE model ($10/$50 per 1M -- 2x Opus, 10x Haiku);
    treat it like a scalpel, not the house model.
  Config backstop (already set in `.claude/settings.json`): `"model": "opus"` runs the
  orchestrator on Opus, and `env.CLAUDE_CODE_SUBAGENT_MODEL=sonnet` floors EVERY untagged
  subagent at Sonnet -- so a forgotten tag can never inherit Fable again. Per-call `model:`
  still overrides the floor (haiku down / opus-fable up). To run a deliberate Fable deep-dive,
  `/model fable` at the session start -- the floor keeps the scouts cheap while the orchestrator
  + the tagged frontier passes use Fable.

**Always merge to `main` (founder standing instruction, Reda).** Every run -- local,
remote/cloud, or phone -- must land the single `dev` -> `main` self-merge; never
stop at a feature branch and never wait to be asked. The only gate is the Safety
model below.

**Always buildable (founder standing consent).** Every task category
(ROUTINE/SCHEMA/ARCH/DECISION/AUTH/COST/GALLERY/DEP) builds. Additive AND
destructive migrations are pre-approved provided they stay revertable. NOTE in the
DONE LOG any new paid/external dependency, auth change, destructive migration, or
brand-new architecture.

**Stop ONLY when:** the queue is drained; the usage/length cap is hit (re-firing
the command resumes idempotently from the first unchecked task); or a task hits a
true external blocker it cannot satisfy (a founder-provisioned
credential/secret/account, a deleted state file, or a conflict with non-negotiable
rules #1-#5) -- mark it `[BLOCKED: reason]`, move it to GATED, and KEEP GOING. A
single blocked task never halts the run.

**Safety model -- never bypass.** The four required checks (backend-lint,
backend-tests with MinIO, frontend-lint, stage-names) gate the single merge with 0
approvals, and `main` stays revertable via `git revert`. Keep branch protection
exactly as configured -- do not loosen, bypass, or add approvals.

**CODEMAP upkeep.** If the run changed backend models/endpoints, frontend
routes/features, or module structure, regenerate `docs/CODEMAP.md` from source and
run `scripts/codemap_fingerprint.py --write` (skip on docs-only runs). Whenever a
task is ticked/blocked/added/removed, refresh §10 "Plan status" + re-run `--write`
in the SAME commit. The `stage-names` CI job re-runs `--check`, so a stale map
fails CI.

**Report once**, in plain language: how many tasks shipped (and what), what was
skipped/blocked and why, and the single merge + deploy.

### "work on the plan"

Drain `docs/PLAN2.md` (priority queue, first) then `docs/PLAN.md` using **"How a
plan run works"** above. Anything typed after the command is extra detail for that
run.

- The active files are `docs/PLAN2.md` then `docs/PLAN.md`. There is no lock --
  only ever one session at a time.
- Read them fully and verify real repo state before building.
- Process EVERY unchecked `[ ]` task in the BUILD QUEUE via the work-stealing
  pipeline; verify each isn't already built first (if it is, mark
  `[x] (already present)`), then tick `[x]` + add a dated DONE LOG line as it lands.
- One run, one sync-safe self-merge to `main`, one deploy -- per "How a plan run
  works". Report once with the lane plan (how many ran in parallel and what each
  shipped) and what was skipped/blocked.
- **Default shape: lane-draining, ≥200 tasks per merge.** Dispatch one worktree agent
  per app, each draining its whole pending lane (8-10 tasks) in sequence; keep folding
  lanes onto ONE branch until **≥200 tasks are done** (drain many apps in parallel —
  the rich self-contained lanes are rh/flotte/qhse/contrats/ged/paie, then
  parametres/publicapi/kb/core/stock/sav/litiges/crm, then the rest — AND second-round
  same-app lanes that `git merge` the integration branch first to chain migrations);
  run ONE combined local docker test (persistent `--keepdb`); then ONE CI-gated merge +
  ONE deploy for the whole run. Do NOT merge per wave/batch and **do NOT merge under
  ~200 tasks** — that pays the ~40-min CI too many times (see THE COST MODEL + MERGE
  FLOOR). Merge under 200 only when the buildable queue is genuinely exhausted (every
  remaining task blocked/gated/deferred/subsumed or in a concurrent session's dirty
  apps).

### "loop work on the plan" (`/loop work on the plan`)

This is the SAME run model, self-paced across wakeups -- NOT a merge per wakeup.
Each `/loop` fire CONTINUES the one accumulating run: keep lane-draining onto the
single branch and **merge exactly once when the lanes drain or a usage cap hits**,
not every time the loop fires. While the one CI is running you are NOT idle -- you
build the next lanes (disjoint apps) during it, and deploy once after the merge.
The fire that finds nothing left to build is the one that does the final
merge/deploy (or reports the queue already drained). The schedule wake-ups exist to
resume a paused drain, never to chop the run into many small merges.

### "add to plan:" followed by tasks (one per line or separated by ;)
- Append them as `[ ]` lines to `docs/PLAN.md`'s BUILD QUEUE, then refresh §10
  "Plan status" of `docs/CODEMAP.md` and re-run
  `python scripts/codemap_fingerprint.py --write` in the same commit (adding a task
  moves the plan fingerprint, so the `stage-names` check fails otherwise), then
  commit on `dev` and self-merge to `main`. Confirm in one line.

### "work on error plan"

Identical to **"work on the plan"** and **"How a plan run works"** in every respect
-- EXCEPT it drains `docs/ERROR_PLAN.md` (the bug/error backlog). Run
`python scripts/plan_lanes.py docs/ERROR_PLAN.md` to plan the lanes. Same
work-stealing pool of up to 8, same per-task review + local test + fold, same
single sync-safe self-merge + deploy at the end, same stop conditions, same
verify-not-already-built (`[x] (already present)`). Anything typed after the
command is extra detail.

- `docs/ERROR_PLAN.md` is in the plan-fingerprint surface: ticking/adding/removing
  an `ERR*` task means refresh §10 of `docs/CODEMAP.md` + re-run
  `codemap_fingerprint.py --write` in the same commit.
- **Headless status.** At the end (or when asked) print exactly
  `PLAN_STATUS: EMPTY` if no unchecked `[ ]` task remains in `docs/ERROR_PLAN.md`,
  otherwise `PLAN_STATUS: MORE`.
- Report once, in plain language, including the lane plan.

### "work on the web plan"

Identical to **"How a plan run works"**, with three differences: it drains
`docs/WEB_PLAN.md`, it edits ONLY `apps/web/**` and the `docs/WEB_PLAN*` files
(NEVER touch anything outside `apps/web`), and the single merge **auto-deploys the
website via Cloudflare on merge -- never run a deploy command or `wrangler`**. Run
`python scripts/plan_lanes.py docs/WEB_PLAN.md` to plan the lanes. Same
work-stealing pool of up to 8, same per-task review + local build/test + fold, same
single sync-safe self-merge at the end. Anything typed after the command is extra
detail.

- The active file is `docs/WEB_PLAN.md` (no WEB_PLAN2.md, no lock).
- `docs/WEB_PLAN.md` is NOT in the plan-fingerprint surface.
- Pre-approved: anything website-safe a task plainly needs. Stop-and-ask (skip that
  ONE task, leave it `[ ]` with a one-line note, and continue): a new external
  dependency, an auth or cost change, a new Cloudflare secret, a deleted state file,
  brand-new architecture, anything touching the form's lead-data flow, or anything
  outside `apps/web`.
- Report once, in plain language, with the lane plan and the exact preview URLs /
  live changes Reda can click.

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
