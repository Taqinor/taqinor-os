# TAQINOR OS

Internal ERP for TAQINOR — multi-tenant, French-language UI, Moroccan market
(amounts in DH). Backend is Django + a FastAPI AI service; frontend is
React/Vite. Everything runs locally with `docker compose up` behind nginx on
port 80.

## The five core modules

| Module | Where | State |
|---|---|---|
| **CRM** | `backend/django_core/apps/crm`, `/crm` | Functional MVP — client records (name, email, phone, address), list + form. |
| **Quote Generator** | `backend/django_core/apps/ventes`, `/ventes/*` | Most complete module — quotes (devis), order confirmations (bons de commande), invoices (factures), line items, VAT, async PDF generation (WeasyPrint + Celery + MinIO), status workflows. *The quote-generation logic is slated for replacement by an external tool.* |
| **Stock Manager** | `backend/django_core/apps/stock`, `/stock` | Functional — products, categories, suppliers, stock levels, low-stock alerts, full movement history, VAT field, archiving. |
| **Bill OCR** | `backend/fastapi_ia` (service), `/ia/ocr` and `/stock/ocr-import` | Working, key-gated — scans bills/invoices/delivery notes via Zhipu AI (GLM vision models) and returns structured data; the stock-import flow turns scanned bills into stock entries. Requires `ZHIPU_API_KEY`. |
| **Unified Chatbot** | `backend/fastapi_ia` (SQL agent), `/ia/agent` | Working, key-gated — natural-language questions answered by a LangChain SQL agent (SELECT-only, tenant-filtered, pgvector table routing, Redis chat history). Requires `GROQ_API_KEY` (or OpenAI/Claude/Ollama via `SQL_AGENT_PROVIDER`). |

## Extras that are also in the codebase

These are not part of the five core modules but exist today:

- **Marketing landing page** — public page at `/` (~1,900 lines of page + CSS).
- **Public contact form** — `apps/contact`, posts from the landing page and
  emails inbound leads (SendGrid in production, console backend locally).
- **Reporting dashboard** — `apps/reporting` + `/reporting`, charts (monthly
  revenue, etc.) computed on the fly; no models of its own.
- **Supporting infrastructure** — multi-tenant authentication (cookie JWT),
  roles & permissions admin, company settings (`parametres`), Celery worker,
  nginx, MinIO object storage.

## Running locally

```bash
cp .env.example .env   # then set real secrets; see comments in the file
docker compose up --build
```

Then open http://localhost. Seed demo data with:

```bash
docker compose exec django_core python manage.py seed_demo
```

Key-gated features (everything else works without keys):
- OCR → `ZHIPU_API_KEY`
- Chatbot → `GROQ_API_KEY` (default provider)
- Outbound email (contact form delivery) → `SENDGRID_API_KEY`; locally emails
  print to the Django container logs instead.

## Tests & CI

```bash
docker compose exec django_core python manage.py test apps
```

GitHub Actions runs flake8, eslint, the Django test suite, and a pipeline
stage-name consistency check (`scripts/check_stages.py`) on every push.

## Contributing rules

See `CLAUDE.md` at the repo root — it contains the founder's enforced rules
(canonical pipeline stages, quote-PDF policy, integration and scraper rules).
Development happens on `dev`; `main` is updated by PR with merge commits
(never squash).
