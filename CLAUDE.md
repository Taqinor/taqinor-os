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

5. **Scraper policy.** Scrapers must never run from personal accounts. Any
   scraping with Terms-of-Service risk requires BOTH: (a) a risk file committed
   under `tos_risk/` describing target, risk, and mitigation, and (b) explicit
   manual approval from the founder before the first run.

## Repo facts

- All work lands as a single direct push to `main` (`git push origin main`) —
  no feature branches, no pull requests, no worktrees. `main` is revertable:
  if a push breaks something, `git revert` restores the previous state.
- Backend: Django at `backend/django_core` (apps: authentication, stock, crm,
  ventes, reporting, parametres, roles, contact) + FastAPI AI service at
  `backend/fastapi_ia` (OCR via Zhipu AI, natural-language SQL agent via
  LangChain). Frontend: React/Vite at `frontend`.
- Multi-tenant: all business data is scoped by `authentication.Company`. New
  models need a `company` FK; new viewsets must filter querysets by
  `request.user.company` and force-assign `company` in `perform_create` —
  never accept it from the request body.
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
  (`apps/ventes/quote_engine/generate_devis_premium.py`, never edit the
  premium pages) renders all formats, selected via the list's PDF dialog →
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

These rules govern HOW work gets done and landed. They replace the old
branch / pull-request / merge ceremony entirely.

- **Fewest steps.** Default to the fewest steps that do exactly what was asked.
  Never add ceremony. Never do extra or adjacent work that wasn't requested —
  don't go resolve unrelated gated items, don't restructure neighboring files,
  don't create files nobody asked for.
- **One session, one direct push to main.** All work happens in one session and
  lands as a single direct push to `main`: run any relevant tests, then
  `git push origin main`. No feature branches, no pull requests, no self-merge,
  no admin-merge, no auto-merge, no worktrees — ever.
- **Safety model: main is revertable.** If a push breaks something, `git revert`
  restores the previous state. Do not add branch-protection gates, PR review, or
  approval steps. Revert is the only safety net, by the operator's explicit
  choice.
- **Touch only the named files.** Only edit the files explicitly named in the
  request. Asked to change two files means change exactly those two. Never
  create alternate or fallback files.
- **Several commands in one request** are all handled in the one session and the
  one push to main — never split across multiple pushes or PRs.

### "work on the plan"
Anything typed after the command is extra detail for that run.
- The active file is `docs/PLAN.md`. There is no `.running` lock — there is only
  ever one session at a time.
- Read it fully and verify real repo state.
- **DRAIN THE QUEUE — one run works through ALL unchecked tasks, never just
  one.** Process EVERY unchecked `[ ]` task in the BUILD QUEUE, in order, one
  after another, in the SAME session. For each task: build it completely with
  tests, get CI green, land it (commit the finished task, tick it `[x]`, add one
  dated line to the DONE LOG) — then **IMMEDIATELY CONTINUE to the next unchecked
  `[ ]` task**. Keep looping until a stop condition below is hit. This per-task
  build-and-checkoff is the existing correct mechanic and is repeated for every
  task; it does NOT end the run after the first task.
- **A run stops ONLY when one of these is true — nothing else licenses
  stopping:**
  1. **Queue drained** — no unchecked `[ ]` tasks remain in the BUILD QUEUE.
  2. **Usage/length cap hit** — stopping here is fine; the plan is idempotent, so
     re-firing "work on the plan" resumes from the still-unchecked tasks.
  3. **A task hits a genuine stop-and-ask condition** — a new external
     dependency, a schema/destructive migration, an auth or cost change, a
     deleted state file, or a brand-new architectural component. SKIP that ONE
     task (leave it `[ ]` with a one-line note of why) and CONTINUE the remaining
     tasks. A single stop-and-ask task must NEVER halt the whole run.
- **There is no "one task per session" / "stop after one task" limit.** Any such
  wording anywhere — including older lines in `docs/PLAN.md` or `docs/WEB_PLAN.md`
  — is overridden by this rule: keep going until the queue is drained or a
  cap/limit above stops you. Do not invent a stop after the first task.
- Database migrations a task needs (additive) are approved. New external
  dependencies, auth or cost changes, deleted state, or brand-new architecture
  are stop-and-ask (condition 3) — skip those and list them.
- When the run stops, run any relevant tests, then `git push origin main`. This
  push auto-deploys to api.taqinor.ma; never run a deploy command.
- Report in plain language: every task that shipped, and what was skipped and
  why.

### "add to plan:" followed by tasks (one per line or separated by ;)
- Append them as `[ ]` lines to `docs/PLAN.md`'s BUILD QUEUE (there is no
  PLAN2.md), then `git push origin main`. Confirm in one line.

### "work on the web plan"
The website autopilot stays strictly inside `apps/web/**` plus its own
`docs/WEB_PLAN*` files. Anything typed after the command is extra detail.
- The active file is `docs/WEB_PLAN.md`. There is no WEB_PLAN2.md and no
  `.running` lock — only ever one session at a time.
- Read it fully and verify real repo state. Scope: edit ONLY `apps/web/**` and
  the `docs/WEB_PLAN*` files. NEVER touch anything outside apps/web.
- **DRAIN THE QUEUE — one run works through ALL unchecked tasks, never just
  one.** Process EVERY unchecked `[ ]` task in the BUILD QUEUE, in order, one
  after another, in the SAME session. For each task: build it completely with
  tests, get CI green, land it (commit the finished task, tick it `[x]`, add one
  dated line to the DONE LOG) — then **IMMEDIATELY CONTINUE to the next unchecked
  `[ ]` task**. Keep looping until a stop condition below is hit. This per-task
  build-and-checkoff is the existing correct mechanic and is repeated for every
  task; it does NOT end the run after the first task.
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
- **There is no "one task per session" / "stop after one task" limit** — and this
  rule explicitly OVERRIDES any contrary wording in `docs/WEB_PLAN.md` itself
  (e.g. "exactly one task… and stops", "Do not start the next task", "One session
  = one task"). Keep going until the queue is drained or a cap/limit above stops
  you. Do not invent a stop after the first task.
- Pre-approved: anything website-safe a task plainly needs. Stop-and-ask
  (condition 3 — skip and list): new external dependencies, auth or cost changes,
  deleted state files, brand-new architecture, anything touching the form's lead
  data flow, anything outside apps/web.
- When the run stops, run any relevant tests, then `git push origin main` — this
  auto-deploys the site via Cloudflare on push; never run a deploy command.
- Report in plain language (no diffs, no commit hashes): every task that shipped,
  what was skipped and why, and the exact preview URLs or live changes Reda can
  click.

### "add to web plan:" followed by tasks (one per line or separated by ;)
- Append them as `[ ]` lines to `docs/WEB_PLAN.md`'s BUILD QUEUE (there is no
  WEB_PLAN2.md), then `git push origin main`. Confirm in one line which file you
  appended to.
