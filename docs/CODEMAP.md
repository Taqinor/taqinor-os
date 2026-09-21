# CODEMAP — TAQINOR OS

Generated from commit `dev-solmvp` on 2026-09-21, regenerated from source by SOLMVP51 for the **MVP solaire** perimeter (Groupe SOLMVP: 47 backend apps left the code as migration shells, 36 frontend feature folders moved to `frontend/parked/`).
Structure fingerprint: 60d026d4dc7bc762e9163950e9751bdba4160264a474a533e0615c6d4b47ce5b
Plan fingerprint: 4944f801d28ea92a0fd213b0c68add71d5f3e6bcc7f25030c237e67fb9be86d7

> This file is **regenerated from the actual source** (models, urls, settings, app
> manifests, docker-compose, requirements, package.json, the CI workflow, the frontend
> router and feature folders) — never from prose docs, which are known to drift. Where
> prose and code disagree, the code wins and the gap is logged in §8. Two SHA-256
> fingerprints above are recomputed by the required `stage-names` CI job, so a
> structural or plan change that does not refresh this map fails the build.
>
> **Keep it LEAN.** This is a read-once INDEX whose job is to tell an agent *which app
> and which file* owns a subject, so it can jump there with one targeted `Grep` instead
> of sweeping the repo. It is not a knowledge dump: per-app detail belongs in the app's
> own docstrings, and per-subject detail in `docs/*.md`.

---

## Table of contents

1. [System overview](#1-system-overview)
2. [Verified stack](#2-verified-stack)
3. [Repository map](#3-repository-map)
4. [Backend, app by app](#4-backend-app-by-app)
5. [Frontend](#5-frontend)
6. [Core data flow (one record, end to end)](#6-core-data-flow-one-record-end-to-end)
7. [Hard contracts and policies](#7-hard-contracts-and-policies)
8. [Known discrepancies (prose vs code)](#8-known-discrepancies-prose-vs-code)
9. [Staleness markers](#9-staleness-markers)
10. [Plan status](#10-plan-status)

---

## 1. System overview

TAQINOR OS is a multi-tenant ERP for a Moroccan solar installer. A browser loads a
**React/Vite single-page app** (`frontend/`). All traffic enters through **nginx**
(ports 80/443), which reverse-proxies three upstreams: the SPA static bundle, the
**Django REST API** (`backend/django_core`, gunicorn on :8000) and a **FastAPI AI/OCR
service** (`backend/fastapi_ia`, uvicorn on :8001). The SPA calls Django under
`/api/django/…` (and the identical `/api/v1/…` alias) and the AI service under
`/api/fastapi/…`. Django persists to **PostgreSQL 16 (pgvector)** and uses **Redis** as
cache plus Celery broker; a **Celery worker** (same Django image) runs async jobs such
as quote-PDF generation. Generated PDFs and uploads live in **MinIO** (buckets
`erp-pdf`, `erp-uploads`). Auth is cookie-based JWT (httpOnly refresh cookie); every API
request is scoped to the caller's `company` (the tenant). The FastAPI service shares the
same Postgres for OCR (Zhipu) and the natural-language-SQL agent (LangChain), both
JWT-protected and key-gated.

**MVP solaire (founder decision, 20-21/09/2026 — Groupe SOLMVP).** What is sold is a
single product, the solar MVP: CRM, Visites, Calepinage, Ventes (+Facturation), Stock
(+Achats), Chantiers (core + GPS), Après-vente (+Monitoring, Outillage, Documents), GED,
Portail client, Publicité, Analyse, Paramètres, Administration, plus the invisible
foundation — so **47 apps left the code physically** ("fully out": no toggle, no edition
mechanism, which SOLMVP3 deleted) and became *migration shells* whose tables and data are
untouched. Each one comes back by a written, tested recipe
(`docs/parked-modules.md` §5); the machine-readable label list lives once, in
`backend/django_core/core/parked.py`.

```
            +---------------+
  Browser ->|     nginx     |  :80 / :443  (+127.0.0.1:8090 lead webhook listener)
            +-------+-------+
                    |
        +-----------+-----------+-----------------+
        v           v                             v
   frontend    django_core                   fastapi_ia
   (Vite SPA)  gunicorn :8000                uvicorn :8001
               /api/django/*  /api/v1/*      /api/fastapi/*
                    |                             |
                    +------> PostgreSQL 16 (pgvector) <-- shared DB
                    |
                    +------> Redis          (cache + Celery broker)
                    +------> Celery worker  (async PDFs, same Django image)
                    +------> MinIO          (erp-pdf, erp-uploads)
```

Request flow, front to back: the SPA dispatches a Redux thunk or a `useResource` fetch ->
axios `GET/POST /api/django/<app>/…` with the JWT cookie -> nginx -> gunicorn/Django ->
DRF ViewSet (queryset filtered to `request.user.company`) -> Postgres -> JSON back. Quote
PDFs are the exception: the ViewSet hands off to the vendored premium engine (sync via
`/proposal`, async via Celery), which renders with WeasyPrint and stores the file in MinIO.

---

## 2. Verified stack

Versions are the **pinned** values in `requirements.txt`, `package.json` and
`docker-compose.yml`. Items not pinned anywhere are marked **unconfirmed**.

### Backend — Django API (`backend/django_core/requirements.txt`)
- Python **3.11** in the prod image and in CI (`python:3.11.x` Dockerfiles; the
  `stage-names`/lint jobs pin 3.11 so a 3.11-only SyntaxError cannot slip through)
- Django **5.1.15**, djangorestframework **3.15.2**, djangorestframework-simplejwt **5.5.1**, django-cors-headers **4.6.0**
- psycopg2-binary **2.9.10**, pgvector **0.3.6**
- redis **5.2.1**, django-redis **5.4.0**, celery **5.4.0**
- weasyprint **62.3**, pydyf **0.11.0**, Jinja2 **3.1.6** (PDF rendering)
- numpy **1.26.4**, matplotlib **3.9.2** (premium quote-PDF charts)
- segno **1.6.6** (scan-to-sign QR on the residential quote PDF; imported defensively)
- django-anymail[sendgrid] **10.3**, django-storages[s3] **1.14.4**, boto3 **1.35.99** (MinIO/S3)
- openpyxl **3.1.5**, Pillow **12.3.0**, httpx **0.28.1**, drf-spectacular (OpenAPI 3)
- gunicorn **22.0.0** (4 sync workers per compose)

### Backend — FastAPI AI service (`backend/fastapi_ia/requirements.txt`)
- fastapi **0.115.6**, uvicorn[standard] **0.34.0**, pydantic **2.10.4**, python-multipart **0.0.31**, PyJWT **2.13.0**
- sqlalchemy **2.0.36**, psycopg2-binary **2.9.10**, pgvector **0.3.6**, redis **5.2.1**
- langchain **0.3.30**, langchain-community **0.3.27**, langchain-groq **0.2.3**, langchain-openai **0.2.14**, langchain-anthropic **0.3.3**, openai **1.59.6**, sentence-transformers **>=2.0,<4.0**
- pypdf **>=4.0,<6.0**, Pillow **>=10.0,<12.0**, pymupdf **>=1.23,<2.0** (OCR utilities)
- OCR provider = **Zhipu AI / GLM vision**, key-gated by `ZHIPU_API_KEY`, called over HTTP — **no pinned SDK** (exact client **unconfirmed**).

### Frontend (`frontend/package.json`)
- Node **22** (CI runner)
- React **19.2.5**, react-dom **19.2.5**, react-router-dom **7.18.2**
- @reduxjs/toolkit **2.11.2**, react-redux **9.2.0**
- axios **1.18.0**, pdfjs-dist **6.2.108**, recharts **2.15.3**, @dnd-kit/core **6.3.1**
- Build/tooling: vite **8.0.16**, @vitejs/plugin-react **6.0.1**, tailwindcss **4.2.4**, @tailwindcss/vite **4.2.4**, eslint **9.39.4**, vite-plugin-pwa **1.3.0**

### Datastores & infra (`docker-compose.yml`)
- PostgreSQL **16** with pgvector — `pgvector/pgvector:pg16`
- Redis **7.4-alpine**
- MinIO — `minio/minio:RELEASE.2025-01-20T14-49-07Z` (CI uses `minio/minio:latest`)
- nginx (reverse proxy, custom build at `backend/nginx`)
- Django project package **`erp_agentique`** (settings module `erp_agentique.settings.dev` in CI/compose)

---

## 3. Repository map

Vendored/generated dirs are skipped (`.venv_test`, `node_modules`, `migrations`,
`quote_engine/assets`, build output). **`backend/parked/` and `frontend/parked/` are
excluded from every build, lint, test and CI guard** — they are source archives, not code.

```
taqinor-os/
+- STAGES.py                      Canonical pipeline stages — single source of truth (rule #2)
+- CLAUDE.md                      Founder's enforced rules (overrides assistant defaults)
+- docker-compose.yml             Local full stack (nginx, django, fastapi, celery, db, minio, redis)
+- docker-compose.prod.yml        Production compose
+- .github/workflows/ci.yml       16 jobs: changes(detector) + lint/test/e2e/rls + ci-gate aggregate (see §7)
+- scripts/                       Host-run CI guards (46 check_*.py) + plan tooling. Notable:
|    check_stages.py                  stage lists vs STAGES.py
|    codemap_fingerprint.py           this map's structure + plan fingerprints
|    check_platform.py                ARC52 platform-kernel guards (10 DB-free source scans)
|    check_api_contract.py            every frontend call resolves to a real backend route
|    check_parked_apps.py             SOLMVP guard: nothing may reference a parked label (SOLMVP53)
|    parquer_app.py / parquer_miroir.py  shell an app / refresh backend/parked from the archive
|    plan_lanes.py, plan_progress.py, split_plan.py   plan-run machinery
+- apps/web/                      Marketing website (Astro, Cloudflare Workers) — separate scope
+- docs/                          PLAN*.md, this CODEMAP.md, parked-modules.md, module-playbook.md,
|                                 quote-engine-swap-map.md, BUILD_ORDER.yml, done_task.md
|
+- backend/
|  +- django_core/                Django REST API (project: erp_agentique)
|  |  +- core/                    Foundation layer, NOT under apps/ — TenantModel/SoftDeleteModel,
|  |  |                           CompanyScopedModelViewSet, numbering, pdf.render_pdf, events bus,
|  |  |                           platform registry + coverage matrix, documents kit, BPM workflow,
|  |  |                           parked.py (the 47-label registry), calepinage + electrique pure engines
|  |  +- app_template/            Scaffold source for `manage.py startapp_erp`
|  |  +- authentication/          Tenant root: Company + CustomUser, JWT, registration (NOT under apps/)
|  |  +- apps/                    39 kept apps — see §4
|  +- parked/                     SOLMVP37 source mirror of the 47 shelled apps (pre-shell code, no
|  |                              migrations); refreshed from the archive tag by parquer_miroir.py
|  +- fastapi_ia/                 FastAPI AI service (root_path /api/fastapi)
|  |  +- app/api/endpoints/       ocr.py (Zhipu OCR), sql_agent.py (LangChain NL->SQL)
|  +- nginx/                      Reverse-proxy config
|
+- frontend/                      React/Vite SPA
|  +- src/router/                 Route table + moduleRoutes.jsx module registry + moduleGating
|  +- src/pages/                  22 page folders (see §5)
|  +- src/features/               27 feature folders: Redux slices, domain logic, module.config.jsx
|  +- src/api/                    39 axios clients; resource.js shared CRUD factory
|  +- src/components/ hooks/ store/ utils/   layout, offline, sav + cross-cutting helpers
|  +- src/design/ lib/ ui/        Design system (tokens/theme, format utils, primitives, DataTable)
|  +- src/i18n/                   fr/en/ar, RTL, hijri display
|  +- e2e/                        Playwright flows
+- frontend/parked/               SOLMVP40 archive of the shelled frontend modules: 36 folders under
                                  features/, 15 under pages/, 38 api/*.js, 1 components/ — moved with `git mv`
```

### Modules sortis du MVP (coquilles de migrations)

**47 apps** left the product on 20-21/09/2026. Each keeps ONLY `__init__.py`, `apps.py`
(`parked = True`), its `migrations/` verbatim plus one final state-only
`SeparateDatabaseAndState(database_operations=[])`, and a `models.py` with **no Django
model** (a verbatim *talon* of functions/enums when a frozen migration references one).
They **stay in `INSTALLED_APPS`** — that is what keeps the kept apps' migration graph
valid, so never a squash — and expose no url, no Celery task, no test, no screen. **No
table and no `django_migrations` row is ever dropped.**

`agriculture ai_governance ao assurances btp_chantier chat compta contacts contrats
conversation_ai cpq credit dataquality datarooms douane ecommerce_connect education
einvoice esg extensions fiscal flotte fpa frais gestion_projet grc hospitality immobilier
innovation juridique kb litiges marketing migration mlops mrp paie pos promotions qhse rh
sante scm territoires transport veille_ao voip`

`ged` and `statuspage` were candidates and **stayed** (GED is a sold module; `core` reads
statuspage's SLA/uptime models). Full story, families, PHASE 2 return order and the
**proven restore recipe**: **`docs/parked-modules.md`**. Authoring/parking a module:
`docs/module-playbook.md`. Machine-readable registry (the only copy of the labels):
`backend/django_core/core/parked.py`.

---

## 4. Backend, app by app

39 apps under `backend/django_core/apps/` plus two top-level packages (`core`,
`authentication`). Every app is served at `/api/django/<prefix>/` **and** at the identical
`/api/v1/<prefix>/` alias (`_APP_URLS` is mounted twice in `erp_agentique/urls.py`); public
tokenized channels sit outside that list under `/api/django/public/…` and `/api/public/…`.
Model counts are the real class count across `models*.py`/`models/`.

| App | Prefix | Models | Role |
|---|---|---|---|
| `authentication` | `/` | 2 (+CustomUser) | **Tenant root**: `Company`, `CustomUser`, `UserSession`; JWT, registration, per-user locale/calendar. NOT under `apps/`. |
| `crm` | `crm/` | 43 | Leads (funnel via STAGES.py), Clients, chatter (`LeadActivity`), canaux/tags/motifs de perte, `SiteProfile`, salle de vente, forecast, parrainage, playbooks, équipes. |
| `visites` | `visites/` | 2 | Visites techniques terrain (`VisiteTerrain`, `VisiteMedia`) — autonomous app; the field rep has no CRM access. |
| `calepinage` | `calepinage/` | 10 | Roof design studio: `Calepinage` + variantes/versions, `ReleveTerrain`, `PhotoSite`, `PoseReelle`, `DossierReglementaire`. Holds the villa engine + kit catalogue + roof-marker helper repatriated from `ao`. |
| `ventes` | `ventes/` | 48 | Devis (statuts brouillon/envoye/accepte/refuse/expire), BonCommande, `RoofLayout`, `ShareLink`, listes de prix, mandats/remises, `quote_engine/` (rule #4). |
| `facturation` | `facturation/` | 7 | Factures, `Paiement`, `Avoir`, `FollowupLevel`, `RelanceLog` — state-only split out of `ventes` (ODX17); legacy `/ventes/factures…` paths still served. |
| `stock` | `stock/` | 71 | Catalogue (`Produit`, `Marque`, `Categorie`, kits, `courbe_pompe`), `Fournisseur`, `MouvementStock`, emplacements/lots/inventaires, portail fournisseur. |
| `achats` | `achats/` | 10 | Supplier POs/receptions/invoices/payments/returns, `PrixFournisseur` — state-only split out of `stock` (ODX19). |
| `installations` | `installations/` | 115 | Chantiers **core + GPS**: `Installation`, planning, interventions, checklists, field documents, demandes d'achat, `DossierImport`, kitting, livraisons. |
| `outillage` | `outillage/` | 3 | Durable tools and loans (`Outillage`, `KitOutillage`). |
| `sav` | `sav/` | 32 | Equipment registry (`Equipement`, warranty clock), tickets + SLA, `ContratMaintenance`, worksheets, `Probleme`, `KbArticle`, `AlarmeOnduleur`. |
| `monitoring` | `monitoring/` | 9 | Production supervision: `ProductionReading`, `UnderperformanceFlag`, `SlaDisponibilite`, `CertificatCarbone`. Swappable provider, no-op by default. |
| `documents` | `documents/` | 0 | Field-execution PDFs (PV de réception, bon de livraison, attestation) — no models. |
| `ged` | `ged/` | 43 | Document management: `Cabinet`/`Folder`/`Document`/`DocumentVersion`, ACL, retention/legal hold, signature requests, public deposits, `Coffre`. |
| `portail` | `portail/` | 8 | Client self-service: quotes/invoices/deliveries, e-signature acceptance, online payment, site timeline. **Never financial detail beyond its own scope** (NTPRT14). GED links kept (SOLMVP16b). |
| `adsengine` | `adsengine/` | 47 | Meta Ads engine: mirrors, propose->approve->apply, creative library, experiments, guardrails, `AssumptionNode` tree. **`installable: True`** (SOLMVP17 — the toggle now gates its API). Campaign creation is always PAUSED (rule #3). |
| `reporting` | `reporting/` | 11 | Dashboards/KPIs/insights, federated KPI hub, `Classeur`, `RapportDefinition`, `KpiAlerte`, global search (`search.py`) — the app owns no business data. |
| `semantic` | `semantic/` | 2 | Named, governed metrics (`MetricDefinition` + versions) — BI semantic layer consumed via `core.data_explorer`. |
| `parametres` | `parametres/` | 18 | `CompanyProfile`, business settings, WhatsApp/email templates, `TauxTVA`/`ConditionPaiement`/`UniteMesure` referentials, `Realisation`, tax-ID validators, output-language resolver. |
| `roles` | `roles/` | 1 | Per-company `Role` + permission lists (RBAC). |
| `identity` | `identity/` | 7 | SSO/SCIM, network & session policies, trusted devices, break-glass (NTSEC). |
| `accessreview` | `accessreview/` | 3 | Access-review campaigns, attestation, SoD rules. |
| `audit` | `audit/` | 1 | `AuditLog` activity trail. |
| `records` | `records/` | 7 | Generic chatter: `Activity`, `Comment`, `Follower`, `Tag`, `Attachment` (ContentType-based) + `platform_guards.py` (the pure guard logic `scripts/check_platform.py` reuses). |
| `customfields` | `custom-fields/` | 4 | Admin-defined fields and custom objects, registry fed by the platform manifests. |
| `dataimport` | `imports/` | 4 | Two-step CSV/XLSX import (dry-run + commit), registry-driven targets, `ExternalRef`. |
| `tiers` | `tiers/` | 1 | Unified party directory (`res.partner` equivalent), bridged additively from crm/stock. **Foundation layer** under an import-linter contract. |
| `entites` | `entites/` | 1 | Intra-tenant org tree (`Entite`: holding/filiale/agence) with anti-cycle guard. |
| `adminops` | `adminops/` | 12 | Health score, sandbox, config packages, adoption, `PlanLicence`/`FactureLicence`, impersonation, signup requests, product announcements. |
| `notifications` | `notifications/` | 16 | Unified notification engine: `Notification`, preferences, routing rules, WhatsApp templates/logs, push, `MessageAccueil`, working hours. |
| `automation` | `automation/` | 13 | No-code rules + approvals: `AutomationRule`/`Run`/`Step`, `ApprovalRequest`/`Decision`/`Delegation`, incoming webhooks. |
| `agent` | `agent/` | 1 | Agentic action catalogue (declared in code, `AgentActionLog` only) — metadata; the endpoint re-checks permissions. |
| `publicapi` | `publicapi/` | 13 | Public REST API: `ApiKey`, scopes, signed `Webhook` + deliveries, bulk jobs, OAuth clients, EDI partner, sandbox tenants. |
| `uxviews` | `uxviews/` | 4 | Server-side saved views, favourites, recent screens, UX prefs (NTUX). |
| `trash` | `trash/` | 1 | Cross-app 30-day recycle bin (`ElementSupprime`) + per-model restorer registry. |
| `offlinesync` | `offlinesync/` | 1 | Single offline write outbox (`OfflineOperation`), one `operations/batch/` sync point. |
| `onboarding` | `onboarding/` | 4 | « Premiers pas » checklist + product tours, auto-completed via `core.events`. |
| `statuspage` | `statuspage/` | 6 | Public status page: components, incidents, 90-day uptime buckets, subscribers. `core` reads its models for SLA/uptime. |
| `contact` | `contact/` | 0 | Public landing contact form — **PARKED by flag** (`CONTACT_FORM_ENABLED=0` -> 404, no email). No models. |
| `core` | `core/` | ~53 | **Foundation, NOT under apps/**: abstract bases (`TenantModel`, `SoftDeleteModel`), `CompanyScopedModelViewSet`, numbering, `pdf.render_pdf`, `events.py` signal bus, platform registry + `platform_coverage.py` drift matrix, `documents` kit, workflow/BPM engine, `parked.py`, pure `calepinage`/`electrique` engines, jobs, quotas, DSR/PII registries. |

**What each SOLMVP lane changed in a kept app** (verified against
`git log origin/main..HEAD -- backend/django_core/apps/<x>`):

- **crm** (SOLMVP10, SOLMVP41) — calls to compta/dataquality/grc/marketing/territoires
  removed; the `partenaires` / `soumissions-lead-partenaire` / `commissions-partenaire`
  routes and the Partenaires screen are gone (the ViewSets were compta-backed), along with
  the marketing-maturity badge, the marketing-touch link resolution and the cpq negotiated-
  price tab. The `Partenaire`/`CommissionPartenaire` **models stay** (tables untouched);
  `parrainage` is a different feature and is untouched.
- **ventes** (SOLMVP11, SOLMVP41) — hooks into compta/cpq/credit/contrats/ao/marketing/
  litiges/grc/ecommerce_connect removed (incl. the discount-approval banner and the
  "vérifier faisabilité atelier" MRP action). **Rule #4 intact**: `/proposal` is still the
  only client quote-PDF path, page counts, the Devis/BC/Facture status chain and
  `utils/references.py` numbering are unchanged; `prix_achat` still never leaves the
  generator.
- **stock** (SOLMVP12, SOLMVP41) — 4 FKs removed by `RemoveField` (`flotte.ActifFlotte`,
  `flotte.Vehicule`, `qhse.NonConformite`, `rh.Departement`); accounting valuation of
  movements, van-sales ("Mon stock camionnette"), showroom/immobilisation and the reception
  scan are gone. `seed_catalogue` stays idempotent.
- **installations** (SOLMVP13) — chantiers keep **core + GPS**. Removed screens AND
  endpoints: sous-traitance (ordres/factures/attestations/évaluations/retenues de
  garantie), prix négociés (write screen), documents-projet, suivi-projet
  (jalons/modèles/réunions), consultations fournisseurs (RFQ), astreintes (+ the
  indisponibilités and recurring-intervention CRUD). Their **models and tables remain**
  (PHASE 2), and internal users of `JalonProjet` / the recurrence engine still work. Also
  detached from qhse/rh/compta; the Gantt (gestion_projet) is gone and the signature pad
  was rehoused.
- **sav** (SOLMVP14, SOLMVP41) — `RemoveField` of `rh.Competence`; contract billing
  (contrats), pos/rh/kb/litiges/grc calls and the "create a KB article" closing step
  removed. Its own `ContratMaintenance` and `KbArticle` stay.
- **calepinage** (SOLMVP15/15b) — nothing of the studio was lost: the engine (io +
  stateless service), the plan analyser (DXF + vector PDF), the pose-kit catalogue, the
  roof-marker helper and the library moved **in** from `ao`; PDF packs now go through
  `records`, then back to GED after SOLMVP16b. No `apps.ao` string remains.
- **portail** (SOLMVP16, SOLMVP16b) — compta/kb/marketing removed; the `ged.Document` FK
  `RemoveField` was **cancelled** by SOLMVP16b (GED stays), so the GED links are back. The
  compta shim is relogged, site progress + photos + quotes intact.
- **adsengine** (SOLMVP17) — compta/qhse calls removed; `installable: True` so the module
  toggle finally gates its API (404 when off). Rule #3 (PAUSED) untouched.
- **reporting** (SOLMVP18) — KPIs, reports and approval sources of shelled modules
  removed; `kpi-federes` only cites kept apps; the Contrats approval source went, GED
  stayed.
- **notifications** (SOLMVP19) — event catalogue, templates and `module_gating` trimmed to
  kept apps; the GED wiring was restored by SOLMVP16b.
- **records / customfields / dataimport** (SOLMVP20) — import targets and the custom-field
  registry limited to kept models; the "GED Document" target came back with SOLMVP16b.
- **audit / tiers / monitoring / parametres / roles** (SOLMVP21) — parametres lost the
  Douane, Point de vente, marketing sending-domain, esg/hospitality/mrp/customobjects
  tabs and the monitoring subscriptions screen; `tiers`' `res.partner` bridge is limited to
  crm/stock.
- **automation / publicapi / agent** (SOLMVP22) — `/api/public/` no longer exposes
  btp/scm resources (OpenAPI snapshot regenerated); agentic actions of shelled modules left
  the AG1 registry.
- **core** (SOLMVP23) — references to shelled apps removed from `events.py`,
  `event_catalog.py`, `tasks.py`, `models.py`, `ai/services.py` and the platform/quota/DSR/
  PII/RLS surfaces; the 4 pure engines that only served shelled apps (demand forecast,
  safety stock, attrition risk, pricing paliers, clv) are gone. `statuspage` stays because
  `core` reads its models. `core` remains a base layer (import-linter).
- **authentication** (SOLMVP30b) — `CustomUser.poste_ref` (rh) removed.

### FastAPI AI service (`backend/fastapi_ia`, root_path `/api/fastapi`)

`ocr.py` (Zhipu/GLM vision invoice + document OCR, key-gated by `ZHIPU_API_KEY`) and
`sql_agent.py` (LangChain natural-language -> SQL with a propose/confirm step, key-gated by
`GROQ_API_KEY` or an alternative). Both JWT-protected, both no-op without their key.

---

## 5. Frontend

React 19 + Redux Toolkit + react-router 7 + Tailwind 4. `features/` holds Redux slices,
domain logic and the per-module `module.config.jsx`; `pages/` holds screens; `api/` holds
one axios client per backend area. The design system lives in `design/` (tokens + theme),
`lib/` (cn + format utils) and `ui/` (primitives + the DataTable engine).

### Coquille par app — the ODY paradigm (founder, 2026-08-01)

The ERP opens on ITS apps: you enter an app, you leave it to pick another. Everything goes
through `frontend/src/lib/apps/` — **never a second app registry**:

| Module | Role |
|---|---|
| `useInstalledApps.js` | **The single source** for the app list: `moduleConfigs` registry ∩ the company's active modules (ODX6) ∩ role/permission (ARC47). Consumed by the home menu, the launcher, pins, the Applications screen. |
| `ActiveAppContext.jsx` | Derives the ACTIVE app from the route (a pure function of `pathname`, so deep-link/F5/back render the same shell). Exposes `useActiveApp`, `useAppVisibility`, `crossAppNavigate`. |
| `appPrefs.js` / `appSearch.js` / `appIcon.js` / `appTransition.js` | Favourites, order, per-app resume, type-ahead search, icon resolution, enter/exit transition. |
| `useAppBadges.js` | Live grid badges — ONE aggregated call on the existing federated endpoint `GET /reporting/reports/kpi-federes/`, never a local re-aggregation. |

In immersion, `Sidebar`/`Header`/`BottomTabBar` render only the active app. The build flag
`VITE_APPS_SHELL` (default ON) is an emergency kill-switch; removing it is task ODY33,
gated on founder validation in production.

### Routes

Core routes are declared in `router/index.jsx`; every module's routes come from its
`features/<x>/module.config.jsx`, glob-imported by `router/moduleRoutes.jsx` (no edit to
`router/index.jsx` per module). Parked modules took their routes with them.

**Core (`router/index.jsx`)** — public: `/`, `/landing`, `/login`, `/register`, `/ui`,
`/403`, `*`; public tokenized: `/rdv/:token`, `/salle-vente/:token`,
`/ged/signature|signataire|depot/:token`, `/e/:token`, `/suivi/:token`,
`/intervention/:token`, `/intervention-rapport/:token`; portals: `/portail/client`
(+`/devis`, `/factures`, `/livraisons`, `/chantiers`, `/mot-de-passe`),
`/portail/fournisseur` (+`/commandes`), `/portail/partenaire` (+`/affaires`,
`/commissions`); authenticated shell: `/apps` (HomeMenu — the front door),
`/app-non-activee`, `/dashboard`, `/dashboards-tv`, `/onboarding/demarrage`,
`/aide/lexique`, `/annonces`, `/ged`, `/ia/agent`, `/ia/actions`, `/ia/ocr`,
`/ventes/devis/:id/3d`, `/ventes/devis/:id/design`, `/devis-design/:id`.

**Per module (`features/<x>/module.config.jsx`)**

| Module | Routes |
|---|---|
| `crm` | `/crm/cockpit`, `/crm`, `/crm/leads`, `/crm/leads/:id`, `/activites`, `/calendrier`, `/carte`, `/crm/parrainage`, `/crm/profils-site`, `/crm/payloads-site-web`, `/crm/forecast`, `/crm/concurrents-perte`, `/crm/defis`, `/crm/relances`, `/crm/visiteurs` |
| `visites` | `/visites`, `/visites/toutes`, `/visites/planifier`, `/visites/revue`, `/visites/:id`, `/visites/:id/calage` |
| `calepinage` | `/calepinage`, `/calepinage/nouveau`, `/calepinage/bibliotheque`, `/calepinage/sources`, `/calepinage/:id` + 16 sub-tabs (variantes, fiches, pompage, plan, photos, pente, terrain, ombriere, schema, production, pertes, horizon, course-soleil, dossiers, affectation) |
| `ventes` | `/ventes/cockpit`, `/ventes/devis`, `/ventes/devis/action-requise`, `/ventes/devis/nouveau`, `/ventes/conception-3d`, `/ventes/bons-commande`, `/ventes/factures`, `/ventes/avoirs`, `/ventes/relances`, `/ventes/paiements`, `/ventes/paiements/import-releve`, `/ventes/listes-prix`, `/ventes/dossiers-reglementaires`, `/ventes/mandats-paiement`, `/ventes/remises-encaissement` |
| `stock` | `/stock`, `/stock/mouvements`, `/stock/categories`, `/stock/fournisseurs` (+`/:id/360`), `/stock/bons-commande-fournisseur`, `/stock/modeles-bcf`, `/stock/receptions-fournisseur`, `/stock/factures-fournisseur`, `/stock/retours-fournisseur`, `/stock/paiements-fournisseur`, `/stock/ocr-import`, `/stock/lots-entrepot`, `/stock/inventaires-annuels`, `/stock/revalorisations`, `/stock/conditionnements`, `/stock/entrepot` |
| `installations` | `/chantiers`, `/chantiers/demandes-achat`, `/chantiers/approvisionnement`, `/chantiers/import`, `/interventions`, `/planification`, `/planification/suivi-gps`, `/ma-journee`, `/parc`, `/atelier`, `/atelier/kits`, `/production` (+`/parc`, `/analytique`, `/garanties`, `/co2`, `/nettoyages`, `/rapports`, `/portail-client`), `/outillage` |
| `sav` | `/sav/cockpit`, `/sav`, `/equipements`, `/sav/contrats`, `/sav/warranty-claims`, `/sav/parametres`, `/sav/sla-rapport`, `/sav/alarmes`, `/sav/action-requise`, `/sav/kb`, `/sav/problemes` |
| `ged` | `/ged/numeriser`, `/ged/checklist`, `/ged/approbation`, `/ged/retention`, `/ged/tags`, `/ged/corbeille`, `/ged/coffres`, `/ged/regles-dossier`, `/ged/regles-acl`, `/ged/routages`, `/ged/planifications` |
| `reporting` | `/reporting`, `/rapports`, `/reporting/balance-agee`, `/reporting/commercial`, `/reporting/quote-to-cash`, `/reporting/cohortes`, `/reporting/dashboards` (+`/partage`), `/reporting/rapport-builder`, `/reporting/archive/client|chantier/:id`, `/approbations`, `/reporting/classeurs` (+`/:id`), `/reporting/sav-sla`, `/reporting/field-service`, `/reporting/scorecard-technicien`, `/reporting/pilotage-chantiers` |
| `adsengine` | `/publicite` + 25 screens (tableau-de-bord, cockpit, ad/:id, approbations, campagnes, creatifs, commentaires, instagram, experimentations, plan-de-vol, backlog, regles, simulation, reporting, brief, journal, connexion, arbre, table-des-faits, comparateur, consentements, kit-marque, veille, import-chantier, tests-terrain) |
| `parametres` | `/parametres` + 24 tabs/screens (export, notifications, alertes-kpi, vues, playbooks, achats(+cloture), gammes, tiers-doublons, ia, objets-personnalises, pieces-jointes, plans-commission, corbeille, ux, sauvegardes, export-reversibilite, limites-usage, etat-dependances, sla, maintenance, messages-accueil, historique-statut), `/objets/:code`, `/journal` |
| `admin` | `/admin/users`, `/admin/roles`, `/admin/tenants`, `/admin/securite-identite`, `/admin/gouvernance-acces`, `/admin/impersonation` (+`/demander`), `/admin/demo/nouveau` |
| `adminops` | `/admin/sante`, `/admin/sandbox`, `/admin/config-packages`, `/admin/adoption`, `/admin/diagnostic`, `/admin/licences`, `/admin/reglages-admin` |
| `entites` | `/parametres/entites`, `/admin/groupe` |
| `offlinesync` | `/mobile/commercial`, `/mobile/cockpit`, `/mobile/equipe-terrain`, `/mobile/equipe-commerciale`, `/synchro/conflits` |
| `portail` | `/portail/administration` |
| `core` | `/donnees/explorateur` |
| `tiers` | `/tiers` |
| `ia` | `/ia` |

### Features (`frontend/src/features`) — 27 folders

- **auth** — session/JWT (`authSlice.js`).
- **crm** — leads/clients state; `crmSlice.js`, `bulk.js`, `stages.js` (mirrors STAGES.py, CI-checked); **`workspace/`** = the lead cockpit (`LeadWorkspace.jsx` over the pure autosave engine `draftCore.js` via `useLeadDraft.js`, with `IdentityRail`/`SectionsPane`/`ContextRail`, `TimelineTab`, `DevisTab`, `ArbreHistorique.jsx`, `StageControl`); `traceToit.js` (pure: `Lead.roof_outline` -> SVG polygon + area, via `features/calepinage`'s roof-marker helper), `leadPrefetch.js`, `rotting.js`.
- **ventes** — quotes/invoices/credit notes; `ventesSlice.js`, **`solar.js`** (solar math + auto-fill: GHI/ONEE/ROI, panel/inverter/battery sizing, pompage HMT+débit -> pump + VEICHI variateur, all TTC), `autoQuote.js`, `PdfCanvas.jsx`, `previewPdf.js`.
- **calepinage** — the roof-design studio (module.config-registered): library, sources, variantes, plan/pente/terrain/ombrière/schéma/production tabs, `repere.js` roof-marker helper (repatriated from `ao` by SOLMVP15).
- **visites** — field technical visits (module.config-registered).
- **installations** — chantiers; `installationsSlice.js`, `statuses.js`, offline field capture.
- **stock** — catalogue/inventory/procurement; `stockSlice.js`, `catalogue.js`, `emplacements.js`, `procurement.js`.
- **sav** — equipment + tickets; `equipementsSlice.js`, `ticketsSlice.js`, `ticketStatuses.js`.
- **ged** — document management console (module.config-registered).
- **reporting** — dashboards/insights; `reportingSlice.js`.
- **parametres** — settings/templates; `parametresSlice.js` + module.config tabs.
- **adsengine** — the « Publicité » console (module.config-registered, no slice: `hooks.js`/`adsengineApi.js`), 25 screens under `/publicite`, `TenantBrand.jsx` (white-label clean), DOM hooks `ae-*`.
- **portail** — client-portal administration + the client-facing portal screens.
- **admin / adminops / entites / audit / uxviews / tiers / notifications / onboarding / core** — administration, audit log, saved views, party directory, notification prefs, « Premiers pas », the « Données » explorer.
- **ia** — AI assistant chat (registry-driven actions with propose->confirm + result cards, voice input, hands-free mode) + OCR; `iaSlice.js`, `voice/`.
- **offlinesync** — mobile-first role homes under `/mobile/*` + `readCache.js`, `AFaireAujourdhui.jsx`.
- **pwa** — auto-update service worker UI, `appLock.js` + `AppLockGate.jsx`.
- **kanban / queue** — shared libraries **deliberately kept** (consumed by CRM and notifications), not modules.
- **`frontend/parked/`** — the 37 shelled modules' features/pages/api/components, moved by `git mv`, excluded from ESLint, Vitest, Docker and the repo check scripts. See its `README.md`.

### Pages (`frontend/src/pages`) — 22 folders

`crm/` (ClientList, LeadsPage, ParrainagePage + `leads/`), `ventes/` (DevisList,
DevisGenerator, DevisForm, FactureList, FactureForm, AvoirsPage, RelancesPage,
BonCommandeList), `stock/`, `installations/`, `interventions/`, `outillage/`, `sav/`,
`monitoring/`, `ged/`, `reporting/`, `approbations/`, `activities/`, `admin/`,
`parametres/`, `preferences/`, `onboarding/`, `aide/`, `tiers/`, `visites/`, `ia/`,
`home/`, `ui/`. Top-level: `Dashboard.jsx`, `Journal.jsx`, `CalendarPage.jsx`,
`CartePage.jsx`, `Landing.jsx`, `Login.jsx`, `RegisterCompany.jsx`, `Reporting.jsx`,
`Rapports.jsx`.

### Module architecture and design system

A "coquille" module registers itself by dropping `features/<module>/module.config.jsx`
(nav + routes + role gate); `router/moduleRoutes.jsx` glob-imports every one.
`api/resource.js` gives `makeResourceFactory(client, basePath)` (the shared
`{list,get,create,update,remove}` CRUD factory) + `unwrapList()`; `hooks/useResource.js`
centralises the loading/error/refetch/stale-response cycle; `ui/module/ListShell` +
`RecordShell` give list and detail/form chrome with no duplicated markup;
`scripts/scaffold-module.mjs` generates the three files for a brand-new module. Role gating
goes through `useHasRole`/`useHasPermission` — no screen reads `state.auth` directly.
`design/tokens.css` defines the brand + semantic light/dark tokens and density;
`design/tenantTheme.js` applies a per-company white-label theme as CSS variables;
`ui/datatable/` is the reusable TanStack-Table engine (sort/filter/column management/
pagination/inline edit/bulk bar/saved views/URL persistence/virtualization/CSV+XLSX export/
mobile cards), demoed at `/ui`. i18n (`i18n/`, `LOCALES` fr/en/ar) is a light zero-dependency
framework with RTL via Radix `DirectionProvider`, a lazily injected Arabic font, per-user
interface language, document output language (`apps/parametres/i18n_resolver.py`) and an
additive hijri display built on `Intl`.

---

## 6. Core data flow (one record, end to end)

```
crm.Lead --(devis.lead, devis.client)--> ventes.Devis --(bon_commande.devis)--> ventes.BonCommande
   | stage: NEW...SIGNED                 statut: accepte |                      statut: livre -> stock-
   | perdu / motif_perte                                 +--(facture.devis)--> facturation.Facture
   |                                                                             type: acompte/solde/...
   |                                              Paiement.facture --+  montant_du = TTC - paid - avoirs
   |                                              Avoir.facture -----+
   v
ventes.Devis --(installation.devis / .lead / .bon_commande / .client)--> installations.Installation
                                                        statut: SIGNE...CLOTURE, bom (JSON)
                                                                         |
          (equipement.installation, equipement.produit -> stock.Produit, numero_serie)
                                                                         v
                                                                sav.Equipement (warranty clock)
                                                                         |
                    (ticket.equipement / .installation / .client)        v
                                                                sav.Ticket  statut: NOUVEAU...CLOTURE
```

1. **Lead** (`crm.Lead`) — captured natively, by import, or by the website webhook. Funnel via `stage` (STAGES.py); lost via `perdu` + `motif_perte`, independent of stage.
2. **Devis** (`ventes.Devis`) — carries `lead` FK **and** `client` FK; the client is resolved from the lead server-side (`apps/crm/services.resolve_client_for_lead` — reuse, else company-scoped email match, else create). `statut` walks brouillon -> envoye -> accepte. Accepting captures `option_acceptee` and advances the lead's `stage` to **SIGNED** (the conversion event, emitted on `core.events` as `devis_accepted`, to which `apps/crm/receivers.py` subscribes).
3. **BonCommande** (`ventes.BonCommande`) — `devis` OneToOne; marking it `livre` decrements stock via `MouvementStock`.
4. **Facture** (`facturation.Facture`) — linked by `devis` FK (échéancier path) and/or `bon_commande` OneToOne (legacy). `type_facture` = acompte / intermediaire / solde / complete. `Paiement.facture` records payments, `Avoir.facture` credit notes; `montant_du = total_ttc - montant_paye - avoirs_total`.
5. **Installation/Chantier** (`installations.Installation`) — created from the quote (`creer-depuis-devis`); links back via `devis`/`bon_commande`/`lead`/`client`; freezes the quote's bill of materials into `bom` (JSON); `statut` SIGNE -> … -> CLOTURE.
6. **Equipement** (`sav.Equipement`) — registered during the chantier checklist (steps with `capture_serie`); links `installation` and `produit` -> `stock.Produit` with `numero_serie`; warranty end dates computed from `date_pose`.
7. **SAV Ticket** (`sav.Ticket`) — links `equipement` (and/or `installation`, `client`); `statut` NOUVEAU -> … -> CLOTURE; `sous_garantie` computed from the equipment's warranty clock.

---

## 7. Hard contracts and policies

All verified against source, not prose.

- **Pipeline stages come from `STAGES.py`** (repo root) — the canonical 6 keys are `NEW, CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD` (French labels in the same file: Nouveau/Contacté/Devis envoyé/Relance/Signé/Froid). `crm.Lead.stage` uses these keys; the frontend mirror is `features/crm/stages.js`. CI job `stage-names` runs `scripts/check_stages.py` and fails on any divergence.
- **"Perdu" is a lost-flag, not a stage** — `crm.Lead.perdu` (bool) + `motif_perte` can be set from any stage, independent of `stage`.
- **Entering SIGNED is the conversion event** — STAGES.py marks `CONVERSION_STAGE = SIGNED` and reserves the `SIGNED_QUOTE_CAPI_HOOK` sentinel for the future Meta CAPI "SignedQuote" emitter.
- **Buy prices never appear on client-facing PDFs** — `stock.Produit.prix_achat` (and `PrixFournisseur.prix_achat`, supplier-PO buy lines) are internal/generator-only. `quote_engine/builder.py` passes only sell-side `prix_unitaire`; `apps/ventes/tests/test_quote_engine_formats.py` asserts `prix_achat` never appears in rendered PDF HTML. Same regime for `Devis.prix_par_kwc`.
- **`/proposal` is the only client-facing quote-PDF path** — canonical endpoint `GET /api/django/ventes/devis/<id>/proposal/`, rendered by the vendored `quote_engine/generate_devis_premium.py`. `generer-pdf` (async Celery) routes through the same engine (toggle `USE_PREMIUM_QUOTE_ENGINE`). The legacy WeasyPrint quote PDF remains only as the off-switch fallback; invoices keep their own separate legacy PDF. See `docs/quote-engine-swap-map.md`.
- **Multi-tenant scoping** — the tenant field is **`company`** (FK -> `authentication.Company`) on every business model; there is **no** field named `tenant_id`. ViewSets filter `get_queryset()` by `request.user.company` and force-assign `company` in `perform_create`/`perform_update`, never from the request body.
- **Cross-app boundary** — between business-core domain apps, reads go through the target app's `selectors.py` and writes/orchestration through its `services.py` (or string FKs); never an import of its `models`/`views`. Cross-app reactions go through the synchronous `core/events.py` signal bus, subscribed in each app's `apps.py` `ready()`. **CI-enforced** by `backend/django_core/.importlinter` + the `lint-imports` step in `backend-lint-fast` (16 contracts, 0 broken).
- **Migration-shell contract (SOLMVP, 20-21/09/2026)** — a parked app (`core.parked.APPS_PARQUEES`, the single copy of the 47 labels) keeps ONLY `__init__.py`, `apps.py` (`parked = True` + `'parked': True` in its manifest), `migrations/` verbatim plus ONE final `SeparateDatabaseAndState(state_operations=[DeleteModel…], database_operations=[])`, and a `models.py` declaring **no Django model** (a verbatim *talon* of module-level functions, enums and namespace classes is allowed, and is required whenever a frozen migration imports a symbol from that file — an empty `models.py` would make the migration unimportable and break the whole graph, visible only in a FRESH process). It **stays in `INSTALLED_APPS`** (that is what keeps the kept apps' graph valid — never a squash) and exposes no url, Celery task/beat entry, test, screen, `contract_samples/` or e2e spec. **No table and no `django_migrations` row is ever touched**; the 5 kept->parked FK links left as `RemoveField` (revertable: only the link column goes). The only authorised tool is `manage.py parquer_app <label>` (`--dry-run`, `--check`), which verifies in a fresh subprocess that the migration graph still loads before deleting anything; the host wrapper `python scripts/parquer_app.py --verifier-tout` asserts all 47 still satisfy the contract (it does, at this commit). The **permanent** CI guard is **`scripts/check_parked_apps.py`** in the `stage-names` job — it fails if any import, FK, url include or beat entry targets a parked label outside `*/migrations/*`; it is delivered by **SOLMVP53** in this same batch and is the guard a future session must keep green. Restoring a module: the proven recipe in `docs/parked-modules.md` §5, plus `docs/module-playbook.md`.
- **Reference numbering** — never `count()+1` (it collided in production when quotes were deleted). `core.numbering.next_reference` / `apps/ventes/utils/references.py` compute highest-used+1 per company+month under a savepoint with retry; `scripts/check_platform.py` (ARC6) blocks any new `count() + 1`.
- **Platform guards** — `scripts/check_platform.py` runs 10 DB-free source scans against frozen baselines that can only SHRINK (`apps/records/platform_baselines/`): no new bespoke `*Activity` chatter (ARC8), no wild `FileField`/`ImageField` (ARC26), no direct `weasyprint` import outside the allowlist (ARC11), no `count()+1` numbering (ARC6), no hand-rolled `company` FK model and no `ModelViewSet` outside `CompanyScopedModelViewSet` (SCA4), no flat storage key and no bare `store_attachment()` (SCA42/AUD311), no hardcoded `taqinor` brand string in a user-facing surface (SCA29), no hand-rolled « document métier » outside `core.documents.DocumentMetier` (SCA37 — Devis/Facture/BonCommande/Avoir are a permanent code-named exclusion under rule #4). `core/platform_coverage.py` (ARC41) additionally cross-checks the ARC28 manifests and fails on a NEW inter-surface drift, with `BASELINE_DRIFT` holding the 11 assumed ones — an entry that is no longer a real drift must be removed, which `core/tests/test_platform_coverage.py` enforces.
- **CI** — `.github/workflows/ci.yml` defines **16 jobs**, triggered on every `pull_request` and on pushes to `main`/`dev` only (a `pull_request`-scoped `concurrency` group cancels a superseded PR run). A pure-git `changes` detector (fails OPEN to the full suite when the diff range is unresolvable) exposes `backend`/`frontend`/`web`/`code` outputs, and the heavy jobs are path-filtered **per job** via `if:` (a skipped *job* reports Success to branch protection, so it never deadlocks — a top-level `on: paths` filter is deliberately NOT used). **Four of the 16 job names are AGGREGATES of sharded/split lanes, not the work itself** — that indirection exists so one stable name can be pinned in branch protection while the lanes underneath are re-sharded freely, and each aggregate explicitly fails when a lane failed OR was cancelled (a `skipped` lane is acceptable): `backend-lint` = `backend-lint-fast` (compileall-3.11 + flake8 + `lint-imports` + **26** `check_*.py`) + `backend-openapi`; `backend-tests` = `backend-tests-shard` (Postgres+pgvector + Redis + MinIO); `frontend-lint` = `frontend-static` (eslint + hex/bundle-budget guards) + `frontend-vitest-shard`; `e2e` = `e2e-shard` (Playwright). The rest are real jobs: `changes`, `ci-image-check`, `stage-names`, `web-build-test`, `rls-tests`, and the always-running `ci-gate` aggregate (`if: always()`, `needs:` all) which fails only when a job that actually RAN failed or was cancelled. `stage-names` is **ungated** — it is the fast broad drift guard and runs on every push/PR, chaining **20** `check_*.py` (`check_stages`, `check_modules`, `check_api_contract`, `check_api_shapes`, `check_ecrans_atteignables`, `check_invariants`, `check_build_order`, …) plus `codemap_fingerprint.py --check`, and `check_parked_apps.py` as the 21st once SOLMVP53 lands. CLAUDE.md designates `backend-lint`, `backend-tests`, `frontend-lint` and `stage-names` as the required merge gate (0 approvals, merge-commit self-merge); see §9 for the branch-protection caveat.
- **Key-gated features** — OCR (`ZHIPU_API_KEY`), chatbot/SQL agent (`GROQ_API_KEY` or alternative), outbound email (`SENDGRID_API_KEY`; console backend locally). Absent key = the feature no-ops, never a 500.

---

## 8. Known discrepancies (prose vs code)

Each line is a place a prose doc says something the **code contradicts**. Code wins.

1. **App inventory.** `CLAUDE.md`'s repo-facts lists "authentication, stock, crm, ventes, reporting, parametres, roles, contact" and `README.md` frames the system as "five core modules + extras". The code has **39 apps under `apps/`** plus the top-level `authentication` and `core` packages — including `installations`, `sav`, `ged`, `portail`, `adsengine`, `calepinage`, `visites`, `achats`, `facturation`, `records`, `customfields`, `documents`, `dataimport`, which the headline lists omit. 47 further apps exist only as migration shells (§3).
2. **`authentication` and `core` are not under `apps/`.** They live at `backend/django_core/{authentication,core}/`, which is why the backend-tests command runs `test apps authentication` specifically.
3. **Quote engine swap already landed.** `README.md` says the quote-generation logic is "slated for replacement by an external tool". In the code the swap is **done**: the premium engine is vendored at `apps/ventes/quote_engine/` and `/proposal` is the canonical path (CLAUDE.md rule #4 is current; the README line is stale).
4. **CI has 16 jobs, not four.** CLAUDE.md and README describe four checks. The four named ones are still the policy merge gate, but the workflow defines 16 (§7) subject to per-job path filtering.
5. **README CI description is incomplete** — it omits the frontend node `--test` parity suite, `web-build-test`, the e2e and RLS suites, and the 46 `check_*.py` guards.
6. **"tenant_id" is not a real field** — the multi-tenant field everywhere is `company`.
7. **The edition/toggle mechanism no longer exists.** Prose that mentions `TAQINOR_EDITION`/`VITE_EDITION`, `settings/editions.py`, `frontend/src/lib/editions.js`, `verifier_edition`, `preflight_edition`, `check_editions_decouplage.py`, `check_dist_edition.mjs` or the `taqinor-edition-parking` Vite plugin is describing code SOLMVP3 deleted. One product is sold; out-of-scope modules leave as migration shells (§3, §7). The runtime `ModuleToggle` (per company) is a different, still-live mechanism.
8. **"49 apps sortent" is the plan's original count; 47 is the truth.** `ged` stayed (founder decision 21/09) and `statuspage` stayed (`core` reads its models). `docs/PLAN.md`'s Groupe SOLMVP preamble still says 49 — it is the historical decision text, not an inventory; `core/parked.py` is authoritative.
9. **Reporting owns no business data — confirmed, not a discrepancy** (listed so a reader does not re-flag it).

If you find no discrepancy in an area not listed above, assume none was found there rather than that it was checked and cleared.

---

## 9. Staleness markers

Things this map could not fully verify from source — do not over-trust:

- **Which CI jobs are "required".** The 16 job names come from `ci.yml`, but the GitHub **branch-protection** "required status checks" set is configured in GitHub, not in the repo, so it is not verifiable here. This map repeats CLAUDE.md's "the four lint/test/stage-name jobs are required" as POLICY, not as a code-verified fact — though the fact that `backend-lint`/`backend-tests`/`frontend-lint`/`e2e` are `if: always()` aggregates over sharded lanes is strong evidence those four names ARE the pinned ones. The `ci-gate` aggregate exists so one always-running required check can be pinned safely.
- **`scripts/check_parked_apps.py` is not on disk at this commit.** It is SOLMVP53's deliverable in the same batch; §3 and §7 describe it as the permanent guard because that is the contract, not because this map verified the file. `parquer_app.py --verifier-tout` (47 conformant shells) and `check_api_contract.py` (1917 calls, 0 orphans) WERE run at this commit.
- **Per-app endpoint spellings.** Model names, URL prefixes, the app manifests, the CI workflow, STAGES.py, compose and the version pins were read directly from source. §4 lists each app's prefix and models but **not** its custom `@action` paths — read the app's `urls.py` before relying on an action path programmatically. `scripts/check_api_contract.py` is the live proof that every frontend call resolves (currently 1917 calls, 0 orphans).
- **Model counts** are the count of classes inheriting a `*Model` base across `models*.py`/`models/`, computed by the same AST rule as `core.parked.modeles_declares`. They include abstract bases in `core` and intermediate/line models elsewhere — a headcount, not an API surface.
- **OCR provider client.** OCR is key-gated by `ZHIPU_API_KEY` and uses Zhipu/GLM vision per config, but no Zhipu SDK is pinned in `fastapi_ia/requirements.txt` (it is called over HTTP) — the exact client is unconfirmed.
- **Provenance window.** Generated on the `dev-solmvp` integration branch (SOLMVP51). Work merged after that is not reflected until this file is regenerated — which is self-enforcing: the `Structure fingerprint:` header is a SHA-256 over the structural surface (every `models.py`/`urls.py` under `backend/` excluding `parked/`, `STAGES.py`, both requirements files, `package.json`, `ci.yml`, everything under `frontend/src/router`, plus the file PATHS under `frontend/src/features` and `frontend/src/pages`), recomputed by the required `stage-names` job. A structural change that does not refresh this map — and re-run `--write` — fails CI and cannot merge.
- **Plan-status freshness.** §10 is a second self-enforcing surface: the `Plan fingerprint:` header is a SHA-256 over every `docs/PLAN.md` / `docs/PLAN2.md` / `docs/ERROR_PLAN.md` task's `(file, id, done/open/blocked)` state, recomputed by the same job. Ticking, adding or removing a plan task without refreshing §10 (and re-running `--write`) fails CI. The lists below are produced verbatim by `codemap_fingerprint.py --print-plan-status`. The `docs/plans/PLAN_*` domain files, `docs/new_tasks_plan.md`, `docs/WEB_PLAN.md` and `docs/backlog/*` are deliberately OUTSIDE this surface.

---

## 10. Plan status

**Done (0)**

- _(none)_

**Open — to build (61)**

- `AUD504` — [GATED: coût prestataire — décision fondateur] Intégration signature QUALIFIÉE DGSSI en…
- `ODX18` — App Facturation — étape 2 (vues/urls/recouvrement/frontend)
- `SOLMVP1` — Archive + registre unique
- `SOLMVP2` — Outil `scripts/parquer_app.py` + `manage.py parquer_app <label>`
- `SOLMVP3` — Fin du mécanisme d'édition (un seul produit)
- `SOLMVP10` — Détacher crm
- `SOLMVP11` — Détacher ventes + facturation
- `SOLMVP12` — Détacher stock + achats
- `SOLMVP13` — Détacher installations + Chantiers « cœur + GPS » (décision 4)
- `SOLMVP14` — Détacher sav
- `SOLMVP15` — Détacher calepinage d'AO sans rien perdre du studio
- `SOLMVP16` — Détacher portail (Portail client = MVP, décision 1)
- `SOLMVP17` — Détacher adsengine + Publicité vendable (décision 5)
- `SOLMVP18` — Détacher reporting
- `SOLMVP19` — Détacher notifications
- `SOLMVP20` — Détacher records + customfields + dataimport
- `SOLMVP21` — Détacher audit + tiers + monitoring + parametres + roles
- `SOLMVP22` — Détacher automation + publicapi + agent
- `SOLMVP23` — Détacher `core/` (fondation sous contrats import-linter)
- `SOLMVP30` — Coquiller Finance
- `SOLMVP31` — Coquiller RH
- `SOLMVP32` — Coquiller Commercial avancé
- `SOLMVP33` — Coquiller Opérations & services
- `SOLMVP34` — Coquiller Supply & retail
- `SOLMVP35` — Coquiller Technique
- `SOLMVP36` — Coquiller les 7 verticaux
- `SOLMVP40` — Frontend : suppression des modules sortis
- `SOLMVP41` — Frontend : recâblage des fichiers gardés (inventaire du 20/09)
- `SOLMVP42` — e2e + gardes
- `SOLMVP50` — Plans : la mémoire de la Phase 2
- `SOLMVP51` — CODEMAP + gardes de plateforme
- `SOLMVP52` — Semis et démo
- `SOLMVP53` — Gate final + garde CI permanente
- `CRX42` — [OPS — action fondateur] Vérification .env prod (30 min)
- `CRXB1` — [GATED: mot fondateur « lance CRXB »] Contrat d'abord (PACT10)
- `CRXB2` — [GATED] Scission models.py [VAGUE EXCLUSIVE]
- `CRXB3` — [GATED] Fin de `__all__`
- `CRXB4` — [GATED] UN round-robin
- `CRXB5` — [GATED] Façade chatter partout
- `CRXB6` — [GATED] Frontière sortante contractée
- `CRXB7` — [GATED] Registres LeadsPage/ListView + tests de rendu
- `CRXB8` — [GATED] LeadViewSet dégonflé
- `ODY33` — Retrait du legacy : à la fin, UN seul shell dans le code
- `PUB107` — [GATED: décision WhatsApp Cloud API (même porte qu'ADSENG34)] Boîte de réception…
- `PUB108` — [GATED: décision WhatsApp Cloud API] Réponse instantanée + qualification WhatsApp Flows
- `PUB109` — [GATED: décision WhatsApp Cloud API] Relances drip marketing WhatsApp
- `PUB110` — [GATED: clé LLM + revue anti-hallucination (même porte que le commentaire LLM des…
- `PUB111` — [GATED: budget fondateur — dépendance payante] Tier vidéo AI-UGC (Arcads/Creatify-style)
- `PUB112` — [GATED: décision fondateur — touche le cœur décisionnel] Bandit « toujours actif » au…
- `PUB114` — [GATED: numéro dédié + coût télécom] Suivi d'appels par annonce + rappel SMS d'appel…
- `PUB132` — [GATED: budget fondateur fal.ai ~50-150 MAD/mois] Adaptateur images fal.ai dans la…
- `PUB133` — [GATED: budget fondateur json2video/Bannerbear ~200-500 MAD/mois] Pont template-vidéo
- `QJR113` — [GATED: chantier séparé post-programme — décision fondateur D10 du 29/08] Moteur…
- `QXG1` — [GATED: founder account]
- `QXG2` — [GATED: founder account]
- `QXG3` — [GATED: founder data]
- `QXG4` — [GATED: founder content]
- `QXG5` — [GATED: founder ops check, 10 minutes]
- `QXG6` — [GATED: vérifs fondateur avant hard-coding]
- `VTAG1` — [GATED: décision fondateur]
- `VTG1` — [GATED: décision fondateur coût/infra]

**Blocked — awaiting founder decision (4)**

- `QC2` — [GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style…
- `S21` — Real-time WebSocket upgrade (Django Channels)
- `VX203` — Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane…
- `VX252` — [BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
