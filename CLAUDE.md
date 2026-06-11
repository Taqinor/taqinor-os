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
- **Public contact form is PARKED (off by default).** The landing-page contact
  form is disabled: the `apps/contact` endpoint (`/api/django/contact/`) returns
  404 and sends no email when off, and the landing CTAs route to `/login`
  instead of opening the form. The code is intact behind two flags. To re-enable
  in one step: set `CONTACT_FORM_ENABLED=1` and `VITE_CONTACT_FORM_ENABLED=1` in
  `.env`, then `docker compose up -d --build` (the frontend flag is a build-time
  arg, so a rebuild is required). To park again: set both back to `0` and rebuild.
