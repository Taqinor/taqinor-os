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

- Active development happens on `dev`. `main` receives merge commits via PR —
  always a merge commit, never squash, so authorship history is preserved.
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

## Plan execution (my commands)
Anything I type after a command is extra detail for that run.

When I say "work on the plan":
- If docs/PLAN.running exists, a batch is already running — stop and tell me; do not start a second.
- Otherwise pick the active file: docs/PLAN.md if it has unchecked [ ] tasks, else docs/PLAN2.md if it has any; if neither, say there's nothing to do.
- Read it fully and verify real repo state. Create docs/PLAN.running and a fresh dev branch off current main; do ALL work on dev — never touch main until the end.
- Build every unchecked [ ] task. Run independent tasks in parallel via subagents in separate worktrees (never two on the same files); do dependent or overlapping ones in sequence — decide from the code. Commit each finished task to dev, tick it [x], add one dated line to a DONE LOG.
- If a task can't be made to pass, skip it (leave it unticked, note why) and keep going.
- Database migrations a task needs are approved. New external dependencies, auth or cost changes, deleted state, or brand-new architecture are NOT — skip those and list them.
- When all buildable tasks are integrated, run the project's full CI checks (the same ones .github/workflows runs). Only if green, get dev onto main: main is protected and takes no direct pushes, so open a pull request from dev into main and merge it yourself (main requires NO approvals — never ask me to approve, never remove branch protection). This merge auto-deploys to api.taqinor.ma; never run a deploy command. If red, back out the blocking task, re-check, then open the PR for the rest; never merge a red dev.
- Delete docs/PLAN.running. Report in plain language what shipped and what was skipped. One plan file per run — don't auto-start the other.

When I say "add to plan:" followed by tasks (one per line or separated by ;):
- If docs/PLAN.running exists, append them as [ ] lines to docs/PLAN2.md (create it if missing) — never touch docs/PLAN.md while a run is in progress.
- Otherwise append them as [ ] lines to docs/PLAN.md's BUILD QUEUE.
- Land the change on main the protected way — never push to main directly: open a pull request for it and merge it yourself (main requires NO approvals; never ask me to approve, never remove branch protection). Confirm in one line which file you added to.

If I say "reset the plan lock", delete docs/PLAN.running and confirm.

## Website plan execution (apps/web) — Reda's commands
Anything Reda types after a command is extra detail for that run. This block governs the WEBSITE autopilot only (apps/web). A separate taqinor-os autopilot may run in parallel — if it shares this repo, it uses its own "os"-named commands, plan/lock files, and the dev-os branch, and never touches apps/web. The two must never share a branch, plan file, or lock file, or edit the same files. The website autopilot stays strictly inside apps/web plus its own docs/WEB_PLAN* files.

When Reda says "work on the web plan":
- If docs/WEB_PLAN.running exists, a website batch is already running — stop and say so; do not start a second.
- Pick the active file: docs/WEB_PLAN.md if it has unchecked [ ] tasks, else docs/WEB_PLAN2.md if it has any; if neither, say there's nothing to do.
- Read it fully and verify real repo state (git log, file contents, open PRs).
- Create docs/WEB_PLAN.running and a fresh dev-web branch off main; do ALL work on dev-web — never touch main until the end.
- Scope: edit ONLY apps/web/** and the docs/WEB_PLAN* files. NEVER touch OS code, the docs/PLAN-os* files, or anything outside apps/web.
- Build every unchecked [ ] task. Independent tasks in parallel via subagents in separate git worktrees (never two on the same files); dependent/overlapping ones in sequence — decide from the code. Commit each finished task to dev-web, tick it [x], add one dated line to the DONE LOG.
- If a task can't be made to pass, skip it (leave it unticked, note why) and keep going.
- Pre-approved unattended: anything website-safe a task plainly needs. NOT pre-approved (skip and list): new external dependencies, auth or cost changes, deleted state files, brand-new architecture, anything touching the form's lead data flow, anything outside apps/web.
- When all buildable tasks are integrated, run the project's full CI checks. Only if green, merge dev-web → main once via a PR you open and self-merge (no approval) — this auto-deploys the site via Cloudflare on merge; never run a deploy command. If red, back out the blocking task, re-check, merge the rest; never merge a red dev-web.
- Delete docs/WEB_PLAN.running. Report in plain language (no diffs, no commit hashes): what shipped, what was skipped, and the exact preview URLs or live changes Reda can click. One plan file per run.

When Reda says "add to web plan:" followed by tasks (one per line or separated by ;):
- Pick the target file: if docs/WEB_PLAN.running exists (a run is in progress), append the [ ] lines to docs/WEB_PLAN2.md (create if missing) — never touch docs/WEB_PLAN.md while a run is in progress; otherwise append them as [ ] lines to docs/WEB_PLAN.md's BUILD QUEUE.
- DURABILITY — this is the whole point of "queue now, fire later (another session / overnight)": a queued task only counts once it reaches the plan file on MAIN. A plain commit here lands on the ephemeral Claude Code web session branch (e.g. claude/...) and is lost when that session ends — so it must NOT stop there. Land the append on main the protected way, exactly like "add to plan" above: branch off the current main, commit only the one-line plan append, open a pull request, and self-merge it (main needs NO approval — never ask Reda to approve, never push to main directly, never remove branch protection). This durable-to-main rule applies to BOTH the WEB_PLAN.md case and the WEB_PLAN2.md case.
- Keep this PR to the docs/WEB_PLAN* files only — bundle no other change into it.
- Confirm in one line which file you appended to and that it is merged to main.

If Reda says "reset the web plan lock", delete docs/WEB_PLAN.running and confirm.
