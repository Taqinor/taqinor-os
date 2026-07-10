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
- **Deploys — website auto, ERP manual.** The public site (`apps/web`) auto-deploys via
  **Cloudflare Workers Builds** on every push/merge to `main` — that IS the mechanism;
  NEVER ask for a Cloudflare API token (the old one is dead) and NEVER run `wrangler
  deploy`. Worker secrets (LEAD_WEBHOOK_URL, LEAD_WEBHOOK_SECRET…) are dashboard-only (a
  manual founder step). The ERP itself (Django + React on Hetzner, `api.taqinor.ma`) does
  **NOT** auto-deploy on merge — bring `main` live with `powershell -File
  scripts/deploy-prod.ps1` (SSHes with `~/.ssh/taqinor_hetzner`, `git reset --hard
  origin/main`, rebuilds compose images, runs migrations + `init_roles`, restarts nginx,
  reloads Caddy, warms the PDF engine). **Claude SHOULD run deploy-prod.ps1 when asked to
  deploy, or after a merge that must reach the ERP** — it is the canonical ERP deploy, not
  "the founder's job."
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
change), targeting **~6-10 min** on the hit path; e2e restores from the same cache (its
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
— the same migration replay WOW8 caches in CI; reuse makes each fold ~2 min).

1. **Plan the lanes once.** Run `python scripts/plan_lanes.py <planfile>` for the file-ownership
   + dependency graph. A **lane** = tasks sharing a file/migration that must run in sequence;
   independent lanes run concurrently. (Drain `docs/PLAN2.md` before `docs/PLAN.md`.)
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
3. **Orchestrator reviews each lane + runs ONE combined local test after folding.** As each lane
   returns, adversarially review its commits vs the safety rules + acceptance criteria, then — AT
   FOLD TIME, per lane — run THAT lane's new/changed test modules via
   `powershell -File scripts/test-backend.ps1 -Modules "<lane's test modules>"` (WOW11 — the
   harness's single-writer guard means only one run touches the shared `--keepdb` DB at a time, so
   parallel lanes never corrupt it). A lane whose modules are red is NOT fold-eligible: fix first.
   Then, once all file-disjoint lanes are in, run the SINGLE combined test over all new modules.
   This per-fold gate is exactly what batch-4 SKIPPED when it shipped 113 unvalidated failures; the
   combined test is the real pre-merge feedback — it has caught a real bug in most runs (missing
   import, `clean()`-vs-`save()`, name clash, hard-vs-soft-delete, a silently-swallowed effect).
   Fix, re-run only the affected module, then the single gate. NOT the GitHub CI (once at the end).
4. **Fold continuously into ONE `dev` branch + advance LOCAL `main`.** As each reviewed+tested
   task passes: fold its branch into the accumulating `dev`, tick it `[x]`, add one dated DONE LOG
   line, and **fast-forward LOCAL `main` to the `dev` tip — locally only: never push, never PR,
   never run GitHub CI between tasks.** This lets later same-app tasks inherit prior migrations;
   advancing LOCAL `main` is NOT a merge.
5. **ONE gate at the very end.** When the queue drains (or a cap is hit): refresh `docs/CODEMAP.md`
   if structure/plan changed (then `codemap_fingerprint.py --write`), integrate the latest
   `origin/main` into `dev` (sync-safe — merge it in, recompute the structure fingerprint if the
   structural surface moved, NEVER force-push), push `dev`, run the four required checks **once**
   over the whole batch, self-merge `dev` → `main` **exactly once**, then **deploy once**
   (`scripts/deploy-prod.ps1` for the ERP; the website auto-deploys via Cloudflare). When branch
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
the merge+deploy gate). Every SUBAGENT is dispatched via `Agent` `model:` / `Workflow` `agent()`
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
  built it, so a cheaper builder never lowers the merge bar. Config backstop (`.claude/settings.json`):
  `"model": "opus"` runs the orchestrator on Opus, and `env.CLAUDE_CODE_SUBAGENT_MODEL=sonnet` floors
  EVERY untagged subagent at Sonnet — a forgotten tag can never inherit Fable. Per-call `model:`
  overrides the floor (haiku down / opus-fable up). For a deliberate Fable deep-dive, `/model fable`
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
why, and the single merge + deploy.

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

### "work on the plan"
Drain `docs/PLAN2.md` (priority queue, first) then `docs/PLAN.md` using **"How a plan run works"**
above. Anything typed after the command is extra detail.
- Active files: `docs/PLAN2.md` then `docs/PLAN.md`. No lock — only ever one session at a time. Read
  them fully and verify real repo state before building.
- Process EVERY unchecked `[ ]` task; verify each isn't already built (if it is, mark
  `[x] (already present)`), then tick `[x]` + add a dated DONE LOG line as it lands.
- Lane-draining, batches sized by the RECALIBRATED MERGE FLOOR above (≈40-80 task lane-groups now
  that the gate is measured ≤45 min — not the old ≥200), each batch locally tested then one
  sync-safe self-merge, one deploy at the end of the run. The rich self-contained lanes to drain first:
  rh/flotte/qhse/contrats/ged/paie, then parametres/publicapi/kb/core/stock/sav/litiges/crm, then
  the rest. Report once with the lane plan (how many ran in parallel + what each shipped) and what
  was skipped/blocked.

### "loop work on the plan" (`/loop work on the plan`)
The SAME run model, self-paced across wakeups — NOT a merge per wakeup. Each `/loop` fire CONTINUES
the one accumulating run: keep lane-draining onto the single branch and **merge exactly once when
the lanes drain or a usage cap hits**. While the one CI runs you are NOT idle — build the next lanes
(disjoint apps) during it, deploy once after the merge. The fire that finds nothing left to build
does the final merge/deploy (or reports the queue drained). Wake-ups exist to resume a paused drain,
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
sync-safe self-merge + deploy, same stop conditions, same verify-not-already-built. Anything typed
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
Pure plan-file housekeeping. This command **NEVER builds, edits, or implements any task**, never runs
a feature/dependency/database/CI change, and makes **no code changes** of any kind. It **NEVER
changes the wording of a task, its ID, or its gating tag**; it **NEVER reorders tasks**; it **NEVER
moves a not-done task from one queue to another**; it **NEVER decides priorities**. It does exactly
one thing: it **relocates COMPLETED tasks** out of the active plan files into a single archive, leaving
every not-done task exactly where — and in the order — it already is.
- **What counts as DONE.** A task is DONE only if it is **explicitly checked complete** — a `[x]`
  checkbox or an equivalent explicit "done/shipped" mark. Anything unchecked `[ ]`, `[BLOCKED…]`,
  `[SKIP]`, gated, or ambiguous is **NOT done** and stays in its active plan file, untouched. **When
  in doubt, treat a task as NOT done and leave it where it is.**
- **Move (do not copy) into one archive.** Move every DONE task from **every active plan file**
  (`docs/PLAN.md`, `docs/PLAN2.md`, `docs/WEB_PLAN.md`, and any other `docs/PLAN*.md`) into
  **`docs/DONE.md`** (create it if missing), **grouped under a heading per source file** (e.g.
  `## Archived from PLAN.md`), **preserving each task's original text verbatim** (for a header-format
  task that is the `###` header **and** its body). After the move, that done task **no longer appears**
  in the active plan file. If a **DONE LOG / done section** already exists inside a plan file, **fold
  those entries into `docs/DONE.md` too** (under a per-file heading), so done history lives in one
  place — keep the DONE LOG **header + scaffolding** in the active file so future runs can still append.
- **Touch nothing else.** The active plan files keep **all their structure** — headers, HOW TO RUN,
  STANDING RULES, GATED/MANUAL sections, cross-cutting constraint notes, dividers, and every not-done
  task — **exactly as written**. Only completed task **lines/blocks** are removed. **Do not delete or
  reword any rule, header, prose note, or not-done task.** (Emptying a section of its done tasks is
  fine — the header stays.)
- **Reconcile — never guess.** Confirm **no task was lost or duplicated**: the count of (done tasks now
  in `docs/DONE.md`) **plus** (not-done tasks still in the active files) must equal the total task count
  **before** you started. The strongest check is line-level: every original line must end up in exactly
  one place (active file or `docs/DONE.md`), none lost, none duplicated, none altered. **If the numbers
  do not reconcile, STOP and report — do not guess.**
- **Fingerprint.** Moving done tasks out of `docs/PLAN.md` / `docs/PLAN2.md` changes the
  **plan-fingerprint surface**, so refresh §10 "Plan status" of `docs/CODEMAP.md` (paste `python
  scripts/codemap_fingerprint.py --print-plan-status` + its totals/stamp) and re-run `python
  scripts/codemap_fingerprint.py --write` **in the same commit** — this is a legitimate plan edit, not
  a code change — then confirm `python scripts/codemap_fingerprint.py --check` and `python
  scripts/check_stages.py` are green. (`docs/WEB_PLAN.md` is **not** in the plan-fingerprint surface.)
  If unsure whether re-stamping is correct, STOP and ask rather than forcing it.
- **Land it.** Commit on `dev`, get the required CI checks green (a docs-only change runs only
  `stage-names`; the heavy jobs skip), then **self-merge `dev` → `main` exactly once** (one merge
  commit, no PR, sync-safe per the STANDING RULES). If CI is red, do **not** merge — report what failed
  and stop.
- **Report** in plain language only (no diffs, no hashes): per file, **how many done tasks were
  archived** to `docs/DONE.md` and **how many not-done tasks remain**, and confirm nothing was
  reordered, reworded, re-prioritized, or built. It never reports code changes because it makes none.
