# CODEMAP — TAQINOR OS

Generated from commit `dev-qah1-20260928` on 2026-09-28, regenerated from source by SOLMVP51 for the **MVP solaire** perimeter (Groupe SOLMVP: 47 backend apps left the code as migration shells, 36 frontend feature folders moved to `frontend/parked/`).
Structure fingerprint: c4f5508da3846cbf2224bfa0a341e3be18d0e7b44dad231738ba2eb3a54a67b2
Plan fingerprint: 46284c39f438628eab0aebad3e7c116570ecc932a2ba1503cdb1cab115cc095f



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
|    setup-nightly-qa.ps1 / nightly-qa.ps1   QAH11 « setup nightly QA » : tâche Windows 23:00 → skill qa-explorer
|    nightly_alert_gate.py            CAD177 : alerte si release-verify rougit/saute 2 nuits
+- .claude/skills/                error-autopilot (constats statiques) + qa-explorer (QAH1 : flotte « testeur
|                                 humain » Playwright/DevTools MCP, oracles durs → ERR-QAH-* ; docs/qa-explorer.md)
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
| `ventes` | `ventes/` | 49 | Devis (statuts brouillon/envoye/accepte/refuse/expire), BonCommande, `ShareLink`, listes de prix, mandats/remises, `quote_engine/` (rule #4). `coherence/` = auditeur d'invariants nocturne en lecture seule (`ViolationCoherence`, `manage.py audit_coherence`, beat `ventes.audit_coherence_nuit` 04:15). |
| `facturation` | `facturation/` | 7 | Factures, `Paiement`, `Avoir`, `FollowupLevel`, `RelanceLog` — state-only split out of `ventes` (ODX17); legacy `/ventes/factures…` paths still served. |
| `stock` | `stock/` | 71 | Catalogue (`Produit`, `Marque`, `Categorie`, kits, `courbe_pompe`), `Fournisseur`, `MouvementStock`, emplacements/lots/inventaires, portail fournisseur. |
| `achats` | `achats/` | 10 | Supplier POs/receptions/invoices/payments/returns, `PrixFournisseur` — state-only split out of `stock` (ODX19). |
| `installations` | `installations/` | 115 | Chantiers **core + GPS**: `Installation`, planning, interventions, checklists, field documents, demandes d'achat, `DossierImport`, kitting, livraisons, `RecettePompage` (recette pompage, `/recettes-pompage/`, AGR). |
| `outillage` | `outillage/` | 3 | Durable tools and loans (`Outillage`, `KitOutillage`). |
| `sav` | `sav/` | 32 | Equipment registry (`Equipement`, warranty clock), tickets + SLA, `ContratMaintenance`, worksheets, `Probleme`, `KbArticle`, `AlarmeOnduleur`. |
| `monitoring` | `monitoring/` | 9 | Production supervision: `ProductionReading`, `UnderperformanceFlag`, `SlaDisponibilite`, `CertificatCarbone`. Swappable provider, no-op by default. |
| `documents` | `documents/` | 0 | Field-execution PDFs (PV de réception, bon de livraison, attestation) — no models. |
| `ged` | `ged/` | 43 | Document management: `Cabinet`/`Folder`/`Document`/`DocumentVersion`, ACL, retention/legal hold, signature requests, public deposits, `Coffre`. |
| `portail` | `portail/` | 8 | Client self-service: quotes/invoices/deliveries, e-signature acceptance, online payment, site timeline. **Never financial detail beyond its own scope** (NTPRT14). GED links kept (SOLMVP16b). |
| `adsengine` | `adsengine/` | 52 | Meta Ads engine: mirrors, propose->approve->apply, creative library, experiments, guardrails, `AssumptionNode` tree, PLAN_VEILLE Ad Library seller discovery (`VeilleDecouverte`/`VeilleRequete`/`VeilleAnnonceur`/`VeillePubVue`/`VeilleVerdict`, `veille/{couverture,decouvertes,annonceurs}/`). **`installable: True`** (SOLMVP17 — the toggle now gates its API). Campaign creation is always PAUSED (rule #3). |
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
| `publicapi` | `publicapi/` | 13 | Public REST API: `ApiKey`, scopes (catalogue in `portees.py`, SPL307), signed `Webhook` + deliveries, bulk jobs, OAuth clients, EDI partner, sandbox tenants. |
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

### crm / parametres / ventes — Groupe CAD (cadence de suivi client, 21/09/2026)

- **Groupe CAD — cadence de suivi client, vague 1 (21/09/2026, 106/184 tâches ; vague 2 = 68 tâches dépendant des racines CAD22/35/75/83/87/88/93/149, CADM1-9 manuelles)** : modules neufs `apps/crm/cadence_temps.py` (naissance/report des touches, un appel et un message par jour, WhatsApp seul, fixe), `cadence_absence.py` + `PeriodeAbsence` (absences déclarées), `cadence_reveil_saison.py` (réveil saisonnier), `mesure_cadence.py` (KPI touche × heure × jour × canal, `GET crm/leads/mesure-cadence/`), `signaux.py` (comportement/fraîcheur du score), `panneau_appel.py` (`GET crm/leads/<id>/panneau-appel/`, contrat `panneau_appel.json`), `srm_regions.py` (12 SRM), `signup_hooks.py` (crm + notifications : fêtes mobiles, dossiers 82-21/FDA), `dsr_provider.py` (politique d'anonymisation) ; champs du script d'appel vagues 1+2 avec leur question en `help_text` (migrations crm 0104-0109), `RelanceEtape.outcome`, `Lead.date_creation_origine` ; `apps/parametres` : `models_messages.py` (darija 27/27, `{marque}`, porte de sortie, mentions loi 31-08), `models_relance.py` (`samedi_ok`, créneaux par type, cadence « deuxième affaire », Ramadan 09-15), `models_company.py` (lien Google, paliers d'escalade), `models_realisations.py` (lien vidéo) — migrations parametres 0097-0102 ; `apps/ventes` : signature au domicile (migration 0118), `courbes_journalieres.py`/`etude_horaire.py` (correctifs de courbe, recharge nocturne, VE), `quote_engine/pricing.py::_resolve_tranches` (tout distributeur nommé) ; frontend `pages/parametres/CadenceRelanceEditor.jsx` (ajout/suppression de barreau, samedi/dimanche, onglet Générique, erreurs sous le champ, `lib/feriesMaroc.js`), `components/ChatterTimeline.jsx` (6 issues), `relances/RelanceEtapeRow.jsx`, e2e mobile/tablet (`/crm/cockpit`, `/crm/relances`). **Vague 2 (24/09/2026, 69 tâches)** : réponses par table unique (`suite_touche.py`, contrat `suites`), panneau d'appel guidé (`PanneauScriptAppel.jsx`, `appelGuidance.js`, `panneau_appel.py` + fenetre_du_jour Ramadan), signaux→touche (`poser_touche_signal`), locataire (`GET/POST leads/<id>/locataire/`), civilité en donnée (migration 0113), langues (bascule `?langue=`, `POST langue/`, repli publié), cadences échues (`GET relance-etapes/cadences-echues/`), pièce reçue, heure promise, contacts secondaires (0111), périodicité facture (0112), file Action requise ouverte au rôle qui relance (ventes selectors + module.config), engagement re-branché sur `devis_ouverts_ratio_client`.

- **PARAM-CADENCE + chaîne commerciale (décision fondateur 25/09/2026)** : la chaîne après l'appel et autour de la visite passe dans Paramètres — cadences `apres_contact` (« Après l'appel (avant devis) », 6 barreaux) et `visite` (« Visite technique », 4 barreaux) de `parametres.CadenceRelanceEtape`, clé stable `CadenceRelanceEtape.cle` (lecture seule, unique par société+cadence, migration parametres 0109) et `RelanceEtape.cle` (migration crm 0114) ; `apps/crm/cadence_config.py` (`etape_configuree` avec repli sur les défauts, `est_etape`/`cle_de`/`q_etape` — reconnaissance par clé, `cles_actives`) lu par tout le moteur (`services.py`, `suite_touche.py`) ; `RelanceEtapeSerializer` + `cle`, `visite_prevue_le`, `visite_id`, `visite_retour_disponible` ; `GET crm/relance-etapes/chaine-commerciale/` (`selectors.chaine_commerciale`, contrat `chaine_commerciale.json`, devis en lot par `ventes.selectors.leads_ayant_recu_un_devis`).

- **CAD176/CAD178 (28/09/2026)** : la touche e-mail générique J+10 porte la clé `relance_email_j10` (gabarit ✎, migration parametres 0110) et le contrat `relance_etape_v2` sert `lead_email` (masqué comme le téléphone) ; `crm.GesteRelanceAppareil` (migration crm 0115, compteur journalier société × geste Fait/Reporter/Appeler/WhatsApp × famille d'appareil, aucun User-Agent brut stocké) alimenté par `fait`/`reporter`/`whatsapp` et la nouvelle action `POST crm/relance-etapes/<id>/appel-compose/`, servi en `gestes_par_appareil` par `mesure_cadence` (troisième tableau de `RelancesSuiviPage`).
- **COCKPIT-CONTRÔLE (30/09/2026)** : bloc « Contrôle du suivi » du cockpit CRM — `apps/crm/controle_suivi.py` (lecture pure, requêtes indépendantes du volume) servi par `GET crm/relance-etapes/controle/?jours=7|14|30&owner=` (contrat `contract_samples/controle_suivi.json` : retard en JOURS OUVRÉS, congés déclarés, étapes reportées) ; traces `RelanceEtape.due_initial_at`/`nb_reports` (migration crm 0116, règle unique `services.deplacer_echeance_etape`) ; la liste `relance-etapes/?scope=` sert le bloc `file` (`selectors.file_du_cockpit`, tâches ouvertes dans « maintenant ») ; « Sauter » refusé sur une tâche ; écran `pages/crm/ControleSuiviPanel.jsx` + `controleSuiviTexte.js` (repliable, même ordre pour tous les rôles), file « À faire aujourd'hui » (`RelancesDuJourWidget.jsx`) ; garde « scénario vécu » `apps/crm/tests_cockpit_scenario.py` contre l'oracle indépendant `apps/crm/cockpit_oracle_outils.py`.
- **QAH (28/09/2026) — tester « comme un humain »** : `tests/test_tenant_sweep.py` + `testkit/tenant_sweep.py` (balayage IDOR/BOLA de ~390 viewsets, cliquets `EXCLUSIONS`/`FUITES_CONNUES`, opt-in `ci_shard.TOP_LEVEL_MODULES`) ; invariants Hypothesis `apps/ventes/tests/test_invariants_{money,documents}.py` ; différentiel `solar.js` ↔ serveur `apps/ventes/tests/test_solar_differential.py` + corpus figé `fixtures/solar_corpus*.json` (`frontend/scripts/solar_corpus.mjs`).

### calepinage — Groupe CALX (lots 1 « rendre visible et opérant », 3 « simulation sourcée » et 4 « électrique pro », 21/09/2026 ; complète la ligne du tableau ci-dessus)  *( `/api/django/calepinage/` )*
- **Forme d'URL unique (CAL233)** : l'objet métier est servi sous `calepinages/<pk>/…` (sous-ressources en `@action` du routeur DRF, `SimpleRouter`), les réglages société sous `parametres/…`, et le moteur — un calcul SANS état — sous `moteur/calculer|pose|resultat/<job_id>/`. `tests/test_structure_urls.py` refuse toute quatrième famille.
- **Rattachement des `@action` — `views/rattachements.py` (CALX2)** : les dix sous-modules de `views/` qui posent une `@action` sur le `CalepinageViewSet` par affectation d'attribut de classe (`equipements`, `horizon`, `export_csv`, `bibliotheque`, `verrou`, `archivage`, `io_layout`, `pompage`, `simulation`, `reglementaire` — 13 actions) sont importés DEPUIS CE SEUL FICHIER ; `urls.py` l'importe une fois, AVANT `router.register` (DRF découvre les actions via `get_extra_actions()` au moment de l'enregistrement — un import posé après ne route rien). **Une action neuve s'AJOUTE en fin de `views/rattachements.py` avec son commentaire `# CALX<id>`, jamais au milieu, jamais réordonnée ; `urls.py` n'est plus rouvert par aucune tâche.**
- **Atelier découpé (SPL194/213-216, 05/10/2026)** — `pages/ventes/ToitureDesign.jsx` délègue à `features/calepinage/atelier/` : `contexteAtelier.js` (12 mappeurs purs lead/devis → builder), `useAtelierBoot.js` (effet de boot lead/devis/calepinage), `useAtelierVues.js` + `OutilsVue.jsx` (plan 2D, export HD, calques, plein écran), `BuilderDom.jsx` (DOM `rp9-*` du builder) ; golden des trois modes : `features/calepinage/__golden__/` (`VITE_UPDATE_GOLDEN=1` pour régénérer). Goldens fiche technique stock (SPL110-112) : `apps/stock/golden/` (`GOLDEN_CAPTURE=1`).
- **Audit ACAL vague B (05/10/2026)** — `services/layout.py` : deux empreintes (`empreinte_document` + `CLES_VOLATILES` pour versions/journal ; `layout_hash` = empreinte IMPRIMÉE `CLES_IMPRIMEES`, migration `calepinage/0018` + commande `acal_empreintes_dry_run`) ; `lier_devis` seul écrivain de `Calepinage.devis` (`0017` unicité) ; `Calepinage.systeme_fixation` (`0019`, `POST fixation/`) ; `services/resultat.py::modifier_resultat` seul écrivain de `resultat` ; `GET entree-electrique/` ; `creation.ouvrir_ou_creer_pour_lead` = la porte unique de création sur lead (verrou) ; `selectors.calepinages_visibles` = prédicat d'accès unique ; `services/rangees.py` (rangée orientée), `services/garde_montants.py`, `services/valeurs.py` ; proxy Django des fichiers du site (`photos/<id>/fichier/`, `plan-importe/fichier/`, `roof-image/fichier/`) ; atelier web `roofPro11/hydratation.ts` (une hydratation pour les deux boots). Tests des contrats posés avant leur moitié serveur : `tests/_m0_en_attente.py` (clé → tâche qui la sert).
- **Les QUATRE surfaces APPEND-ONLY du module (décision D-CALX 13)** — `frontend/src/api/calepinageApi.js`, `frontend/src/features/calepinage/atelier/onglets.js` (le rail d'onglets déclaratif), `backend/django_core/apps/calepinage/views/rattachements.py`, `backend/django_core/apps/calepinage/services/parametres_cles.py`. Elles sont déclarées dans `_APPEND_ONLY_SUFFIXES` de `scripts/plan_lanes.py` : deux tâches qui les citent ne fondent PAS leurs lanes, parce qu'une méthode, un onglet, une action ou un réglage neuf s'y **AJOUTE en fin avec un commentaire `// CALX<id>` (JS) ou `# CALX<id>` (Python)** — jamais une réécriture, jamais un tri. Mesuré sur `docs/PLAN2.md` avant CALX2 : 13 des 16 fusions de lanes du groupe CALX venaient de ces seuls fichiers (9 sur `rattachements.py`, 4 sur `calepinageApi.js`). Les règles sont purement TEXTUELLES (suffixe du chemin déclaré) : elles valent pour `onglets.js` et `parametres_cles.py` avant même leur création. `scripts/check_taches_cablage.py` admet en conséquence `features/<app>/atelier/onglets.js` comme fichier de MONTAGE d'un écran de la même feature, au même titre qu'un `module.config.jsx`.
- Corollaires de la même décision : les sorties du lot 6 vivent dans `views/documents.py` (jamais `views/sorties.py`) et le rapport d'étude dans `services/rapport/<section>.py` (jamais un `rapport_etude.py` unique). Aucun import `apps.ao` / `apps.ged` n'entre dans le module (D-CALX 2).
- **Lot 3 « Simulation de production sourcée » (CALX141-198 + 5/6/14/16/48/59/60/62/64/65/69/255/264, 21/09/2026)** : la simulation d'un calepinage est une CHAÎNE DE PERTES déclarative — `services/chaine_pertes.py` (`appliquer_chaine`, `ORDRE_ETAPES` = 24 postes dans l'ordre PVsyst, `decision_meteo`/`MeteoIndecise`, ré-indexation de la série sur l'heure LÉGALE du fuseau saisi du site, `PLAFOND_FENETRE_ANNEES = 10`) charge chaque poste PAR NOM depuis `services/etapes/<poste>.py` (`appliquer(serie, contexte) -> (serie, etape)`, fonction pure ; le contrat des six clés et les trois refus de l'ordonnanceur sont dans la docstring de `services/etapes/__init__.py` ; module absent = étape omise « non livrée », JAMAIS un défaut — D-CALX 7 : coefficient/seuil = réglage société sourcé, fiche produit, valeur PVGIS, ou omission nommant le champ). Entrées : série horaire PVGIS `services/pvgis_serie.py::ClientPvgis.serie_irradiance` (composantes + `userhorizon`, fenêtre pluriannuelle ou TMY) ou fichier météo importé (`services/meteo_fichier.py`, action `meteo-fichier/`) ; position solaire `core/calepinage/soleil.py::position_solaire` (UTC) ; ombre inter-rangées `core/calepinage/ombre_rangees.py` ; fiches produit `stock` (migration `0159_calx60_fiche_chaine_pertes`) ; réglages société À REGISTRE `services/parametres_cles.py` (sections `simulation` et `electrique_societe`, chaque valeur `{valeur, source, reference}`, migration `calepinage/0010`) — après TOUT ajout au registre, régénérer le bloc `registre` de `contract_samples/parametres_calepinage.json` (test_calx69 épingle l'égalité). Orchestration : `services/simulation.py::simuler_calepinage(calepinage, *, forcer=False)` + `construire_contexte`, action `calepinages/<pk>/simuler/` (tâche `tasks.simuler_calepinage`, nature `simulation`, `GET resultat/` la sert avec sa fraîcheur) ; résultat module par module `services/simulation_modules.py` ; incertitude P50/P90 `services/incertitude.py::bloc_incertitude` ; PR et rendement `services/performance.py::bloc_performance` ; validation croisée `services/validation.py::ecart_vs_pvcalc` ; courbe de charge `services/courbe_charge.py::construire_courbe_charge`. Dépendance `pvlib==0.15.2` (décision `docs/decisions/calx198-pvlib.md` : contre-calcul, jamais source de vérité). Golden `tests/golden_simulation/cascade_pluriannuelle_casablanca.json`. Frontend : `reglages/ReglagesSimulation.jsx`, `atelier/PanneauSeries.jsx`, `production/TapisHoraire.jsx` + `PanneauProduction.jsx`, `plan/AffectationChaines.jsx`. Règle de test (leçon du lot) : un test d'étape ISOLE son étape (`appliquer` direct ou l'entrée de cascade de son poste), jamais le total de la chaîne.
- **Lot 4 « Électrique pro » (CALX201-250 + 172/183, 21/09/2026)** : la TOPOLOGIE électrique entre dans le document et le résultat — contrats `roof_layout_v2.schema.json::electrical` (`equipements[]` 8 types fermés, `cheminements[]` avec `origine` plan/saisie/mixte), échantillons `electrique_equipements.json`, `electrique_cheminements.json`, `calepinage_troncons.json` (+ `verdicts[]`), `calepinage_sld.json`, `calepinage_raccordement.json`. Noyau pur `core/electrique/` : `VerdictElectrique {code, nature, statut, libelle, borne, valeur, source, temperature_*}` (CALX215/214, `bloquants`/`alertes` en DÉRIVENT ; `passer_outre` = dérogation écrite dans le fil par `services/electrique.py`), `ChoixLongueur` motivé (216), bornes onduleur `s_max_kva`/`dc_max_kwc` + paliers DC/AC en RÉGLAGES (213, `bornes_dc_ac`), branches AC micro-onduleurs (`calibrer_branches_ac`/`dimensionner_branches_ac`/`dimensionner_cables(branches_ac=)`, 210), `blocs_du_schema(branches_onduleur=)` « typique de N » (238), API publique du schéma `GEOMETRIE`/`places_du_schema`/`bloc_svg`/`rendre_schema(blocs=, bandeau=)`, nomenclature à références catalogue + coffrets réellement posés + métré par section (246/230/227), structure SOURCÉE ou omise (247, `regle_bom_structure`). Services : `polystring.py` (206/207), `micro_onduleurs.py` (209), `troncons.py` (224-226 : longueur réelle avec origine, section/chute par tronçon lues sur la NORME, chute cumulée verdictée une fois par côté, métré), `coffrets.py` (230-232), `raccordement.py` (241-243 + `bloc_raccordement` contrat CALX205), `terre.py` continuité (245), `agregation_electrique.py` (183), `sld.py`/`sld_export.py` (233-237 : édition persistée dans `resultat['sld_edition']`, gabarit par pays — `pays=ma` sans norme = gabarit neutre, DXF `ezdxf` reproductible), `etapes/ecretage.py` (172), `cables.py::course_de_chaine` (218), `electrique.py::verdict_publiable` (248 : publiable ⇔ zéro bloquant ET zéro conclusion sans source, exposé par la clé `publication` de `evaluer-electrique`). Routes : `troncons/` (GET), `raccordement/` (GET|POST), `schema-unifilaire/` (GET|POST), `schema-unifilaire.dxf/` (GET) — toutes greffées par affectation de classe (`rattachements.py`, la garde `check_api_contract` les voit). 3D (`apps/web/src/scripts/roofPro11/electrique3d.ts`, 219-223) : couche d'organes et de cheminements persistée par `serializeLayout` (`electrical`), calque « Électrique » piloté depuis `ToitureDesign.jsx` — réservé au lot 2 : attacher `electrique.groupe` à `sceneRoot` (`scene3d.ts`), Ctrl+Z/Y (`layoutEditor.ts`). Onglets React `features/calepinage/electrique/` : Équipements (222), Cheminement & câbles (229), Raccordement (244), Verdict électrique (249) ; `Rail.jsx` relaie `builderApi` à chaque onglet. Gardes : `scripts/check_seuils_electriques.py` (250 : aucun littéral numérique non trivial sans commentaire de provenance dans `core/electrique/` + services électriques ; base `seuils_electriques_exceptions.txt` ne peut que rétrécir, motifs manuscrits, tests épinglés par NOM de constante) ; `check_services_appeles` : une fonction publique de service sans appelant hors module = rouge (les assembleurs appelés dans leur propre module sont privés).

- **Lot 2 « site, toit & atelier 3D » (21/09/2026, 53/54 tâches — CALX130 e2e ouverte)** : contrat `roof_layout_v2` étendu (retraits par arête, `modules[]`/`moduleId`, `numerotation`, `buildings[]`, obstacles `forme`/`contour`/`rayonM`, allées `usage`/`axe`/`largeurM`, `underlay`, `poseSurfaces` façade + `appuis`, `optimisation`, `scene`) ; backend `views/modules_disponibles.py` (`GET calepinages/<pk>/modules-disponibles/`), `views/plan_importe.py` (`GET …/plan-importe/`), `services/modules_stock.py`, `gabarits.py`/`traduction.py` (CALX405), `degagements.py` (allées par pays), `zones_reglementaires.py` (gabarits d'obstacle sans genre), `apps/crm/roof_detect.py` (bloc `batiment` OSM), `apps/ventes/selectors.py::_reglages_atelier` (mode devis) ; apps/web `roofPro11/` : `snap`, `mapDraw` (grille, fond, calage), `underlay`, `clavier`, `mesureUi`, `edges`/`edgesUi`, `layoutEditor`, `shadingUi` (seuil, info-bulle), `batiment`, `numerotation`, `moduleSelect`, `panStats` (totaux site), `poseSurfaces` (sol/ombrière/façade), `obstaclesUi` (polygone/cercle/allées), `optimizer` (cible, seuil, module, retraits par arête → `solveLive*`), `soleilPlay`, `calageFondUi`, `teinteAllees`, `optimisationDocument`, `fondDocument`, `infoBulleOmbrage` ; frontend `atelier/OngletCoupeRangees.jsx`, `CourseSoleil.jsx`, `ToitureDesign.jsx` (reglagesAtelier, modulesDisponibles, batiment OSM, fond photo/plan, panId).
- **Lots 5 « Consommation, tarifs & finance » + 6 « Livrables & rapports » (23/09/2026, 76 tâches + CALX130 ; restent CALX327/329 + CALX96)** : consommation — contrat `roof_layout_v2::consumption` (courbe24/saisons/appareils, sérialisé/réhydraté par `prefill.ts`), `services/consommation.py` (`publier_kwh` via `apps/parametres/tariff.py::kwh_depuis_facture` — inversion dichotomique du barème, D5 ; `courbe_appareils` normalisée sur le total saisi ; `appliquer_ramadan` relit `apps.ventes.ramadan`, courbe en horloge ORDINAIRE), `charges.py` (VE `immediat|pv_optimise` + `puissance_borne_kw`, `courbe_climatisation` BTU/EER saisis, `cle_tarifaire`), profils société `pompage` + `jour_type` (migration `0011`), `profil_depuis_import` avec provenance ; batterie — `simuler_groupes` multi-groupes AC/DC, SOC cible, pointe avant/après, réserve par appareils secourus, rendement OBLIGATOIRE, capacités candidates SANS prix (stock `avec_prix=False`), `hors_reseau.py` seuils saisis, CALX63 (écrêtage récupéré DC, plafond d'injection justifié, stratégie TOU sur `tou_pour` société — jamais `DEFAULT_HOUR_TRANCHES` en repli) câblé dans `simulation.py` (`tou_heures`, capacité batterie/année sur `production.projection`) ; tarifs société — `models_tariff.py` TOU par saison/compensation typée/structures hors-Maroc/taxes séparées/indexation SAISIE/amortissement-fiscalité (migrations parametres **0103→0108** — 0097-0102 étaient tenues par la vague CAD), défauts financiers non sourcés SUPPRIMÉS (`DEFAULT_TRANCHE_TARIFFS`, `DEFAULT_PPA_TARIFF`, escalade 6 % → 0 % avec avertissement), audit de version branché sur `CHAMPS_LOT5`, écran `pages/parametres/TarificationSection.jsx` + `serializers_tariff.py::validate` ; économie (D5, `apps/ventes`) — contrat `ventes_economie.json`, `economie.py` (flux/VAN/TRI/retours, LCOE, prêts, P90, comparaison ; LECTURE STRICTE : tout taux manquant ⇒ indicateurs `None` motivés), route `GET devis/<pk>/economie/` (action greffée), onglet atelier `PanneauEconomie.jsx` (lecture seule, omissions visibles) ; documents — hub `services/rapport/` (une section par fichier : site, système+annexes fiches PDF, pertes+SVG serveur, production/PR/P50-P90, électrique+SLD, nomenclature SANS prix, preuve, annexe hypothèses, sommaire/pages), gabarit société + libellés FR/EN, sections choisies par société (migration `0012`, réglage `documents` servi par `parametres/`), `views/documents.py` (rapport-etude.pdf, diagramme-pertes.svg, documents/, apercu-document/, image-document POST — genres fermés `ombrage|sankey|plan3d`, validation octets magiques —, rapport-ombrage.pdf, plan-cablage.pdf|.dxf, export-projet.json, manuel-proprietaire.pdf, document-asbuilt.pdf, presentation-compacte.pdf, dossier-fin-chantier POST), inventaire à manques NOMMÉS + versions (`records.Attachment`) + journal, exports avec bloc de provenance UNIFIÉ (XLSX/DXF/JSON), packs (plans, rapport, câblage, fin de chantier), panneau `PanneauDocuments.jsx` (9 cartes, liens `ou_saisir` seulement vers de VRAIS onglets), e2e `calepinage-parcours.spec.js` (7 gestes lot 2, ancre `#rp9-areas-window` réparée) ; base `services_appeles_allow` élargie de 69 fonctions M4 (consommateurs planifiés lots 7-8, `--autoriser-croissance` de clôture, visible en revue).
- **Lots 7 « Workflow, données & intégrations » + 8 « Qualité, perf, gardes & docs » (24/09/2026, 56 tâches ; CALX339/356/357 [BLOCKED : fichiers .PAN/.OND fondateur])** : contrats posés SEULS d'abord (PACT10 — comparaison 1-5 calepinages, étiquettes, différentiel de versions, approbation, bom-fixation, reprise de visite, écarts de pose, zones vent/neige société : CALX331-337/340) puis leurs moitiés : comparaison + classeur (`comparer/`, `ComparaisonProjets.jsx`), étiquettes + filtre de liste, différentiel champ par champ + onglet `atelier/DiffVersions.jsx`, chaîne d'approbation (rôle `calepinage_approuver`, réglage société « approbation avant variante retenue », onglet), modèles & jeux de réglages à la création, fixation (catalogue systèmes, nomenclature + feuille tableur + porte, onglet, zones vent/neige par site → lestage), reprise de visite technique (porte `releve_pour_calepinage` côté visites, mesures+photos avec provenance, onglet `atelier/RepriseVisite.jsx`), pose réelle (porte, écarts → version, onglet `atelier/PoseReelle.jsx`), champs de fiche saisissables au formulaire produit, intégrations (webhook `calepinage.simule` signé, GET public `calepinages/<id>/resultat/`, export/import projet JSON + onglet `atelier/Projet.jsx` — le verdict est REJOUÉ, jamais lu du fichier), responsable d'un calepinage + visibilité par rôle (CALX406). Lot 8 : 6 gardes CI neuves inscrites dans `ci_guards.py` (`check_calepinage_actions_consommees`, `check_onglets_calepinage_testes`, `check_calepinage_provenance_constantes`, `check_contrats_calepinage_deux_moities`, garde des clés `calepinageApi.js` appelées, `check_frontiere_calepinage` à base mesurée), e2e parcours étendu + chaque onglet du rail s'ouvre, budgets (requêtes liste/détail/résultat, temps de simulation 1/4/12 pans + linéarité zéro réseau, poids du module recalé, perf atelier 10 000 modules `apps/web/roofPro11/perf.test.ts`), déterminisme de la simulation (même entrée = même empreinte), rail ARIA clavier, télémétrie des onglets ouverts, docs (`moteur-calepinage.md`, guide utilisateur, lexique métier + aide du rail), repères DOM `cal-*` gelés en contrat (`e2eHooks.test.mjs` + `E2E_HOOKS.md`). Les agrégats calepinage restent hors `docs/api-contracts.md` (CALX399 : formes statiquement indéterminables, principe anti-faux-positif). `check_stages.py` : exclusion `(?<!LE)STAGE` (« lestage »/« délestage » ≠ étape du funnel).
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
DevisGenerator, FactureList, FactureForm, AvoirsPage, RelancesPage,
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
- **CI** — `.github/workflows/ci.yml` defines **15 jobs**, triggered on every `pull_request` and on pushes to `main`/`dev` only (a `pull_request`-scoped `concurrency` group cancels a superseded PR run). A pure-git `changes` detector (fails OPEN to the full suite when the diff range is unresolvable) exposes `backend`/`frontend`/`web`/`code` outputs, and the heavy jobs are path-filtered **per job** via `if:` (a skipped *job* reports Success to branch protection, so it never deadlocks — a top-level `on: paths` filter is deliberately NOT used). **Four of the 15 job names are AGGREGATES of sharded/split lanes, not the work itself** — that indirection exists so one stable name can be pinned in branch protection while the lanes underneath are re-sharded freely, and each aggregate explicitly fails when a lane failed OR was cancelled (a `skipped` lane is acceptable): `backend-lint` = `backend-lint-fast` (one parallel runner step, `scripts/ci_guards.py backend-lint-fast`: compileall-3.11 + flake8 + `lint-imports` + the gated `check_*.py`, **44** commands in `ci_guards.GARDES`) + `backend-openapi` (schema check + `makemigrations --check`); `backend-tests` = `backend-tests-shard` (**8** duration-balanced lanes from `scripts/ci_shard.py`, Postgres 16 in the job container + Redis + MinIO; lane 0 also runs the opt-in RLS seal suite, formerly the `rls-tests` job); `frontend-lint` = `frontend-static` (eslint + node:test in parallel, hex/bundle-budget guards) + `frontend-vitest-shard` (4 lanes, no coverage); `e2e` = `e2e-shard` (Playwright, smoke specs on 3 workers). The rest are real jobs: `changes`, `ci-image-check`, `stage-names`, `web-build-test`, and the always-running `ci-gate` aggregate (`if: always()`, `needs:` the LANES, not the aggregates — one runner hop less on the critical path) which fails only when a job that actually RAN failed or was cancelled. `stage-names` is **ungated** — it is the fast broad drift guard and runs on every push/PR: one parallel runner step (`scripts/ci_guards.py stage-names`, **44** commands: `check_stages`, `check_modules`, `check_parked_apps`, `check_api_contract`, `check_api_shapes`, `check_ecrans_atteignables`, `check_services_appeles`, `check_invariants`, `check_build_order`, `codemap_fingerprint.py --check`, the shard-split completeness tests, …). **The guard LIST lives in `scripts/ci_guards.py` only** (SOLMVP54, 21/09/2026): `scripts/ci_fast_gate_steps.py` expands the runner step so `preflight.ps1` still sees one entry per guard, and `scripts/tests/test_ci_guards.py` refuses a guard left as a serial ci.yml step. CLAUDE.md designates `backend-lint`, `backend-tests`, `frontend-lint` and `stage-names` as the required merge gate (0 approvals, merge-commit self-merge); see §9 for the branch-protection caveat.
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

**Done (853)**

- `ERR115` — [installations]
- `ERR116` — [installations]
- `ERR117` — [chantiers]
- `ERR118` — [ci]
- `ERR119` — [ci]
- `ERR120` — [ventes]
- `ERR121` — [e2e]
- `ERR122` — [DÉGATÉ 29/09/2026 — décision fondateur (question interactive) : bump majeur autorisé…
- `ERR123` — [DÉGATÉ 29/09/2026 — décision fondateur (question interactive) : bump majeur autorisé…
- `ERR124` — [installations]
- `AGR1` — Contrat d'abord : forme pompage du Lead, règle « devis auto prêt » agricole et drapeaux…
- `AGR2` — Contrat d'abord : aperçu serveur du pompage + clés `etude_params` pompage v2
- `AGR3` — Contrat d'abord : le bloc `economie_pompage` (économie agricole déclarée), ses saisies…
- `AGR4` — Contrat d'abord : la charge utile publique d'un devis agricole (`synthese_agricole`…
- `AGR5` — Contrat d'abord : la visite « relevé du point d'eau » (gabarit agricole)
- `AGR6` — Contrat d'abord : recette de mise en service pompage (mesures, comparaison au devis…
- `AGR7` — Contrat d'abord : le produit pompe / variateur structuré
- `AGR100` — Produit pompe/variateur : champs structurés et vocabulaire de rôles pompage (fin du…
- `AGR101` — Fiche technique typée « pompe » et « variateur de pompage » (valeurs constructeur…
- `AGR102` — Courbe de pompe refusée si elle n'est pas physiquement lisible
- `AGR103` — Une seule lecture serveur du catalogue pompage : `stock.selectors.produits_pompage`
- `AGR104` — Articles des options du kit pompage (prix à renseigner) + rôles des articles existants
- `AGR105` — Fiche produit : saisir les champs pompage, la fiche variateur et une courbe vérifiée…
- `AGR106` — Catalogue : filtre « pompage à compléter » et indicateur « kit pompage chiffrable »
- `AGR107` — Réglages société du pompage, sans valeur par défaut
- `AGR108` — Écran Paramètres : saisir les réglages pompage avec leur source à côté
- `AGR109` — Un seul moteur pompage en Python : noyau pur `core/pompage` partagé par ventes et…
- `AGR110` — Table unique des hypothèses de pompage, chacune avec sa source
- `AGR111` — HMT calculée par composantes (niveau dynamique + dénivelé + pertes Hazen-Williams +…
- `AGR112` — Besoin FAO-56 corrigé dans le noyau : profil Kc mensuel de l'olivier, cultures sans…
- `AGR114` — Production d'eau mois par mois, heure par heure : irradiation PVGIS du site + lois de…
- `AGR115` — Champ PV dimensionné sur l'énergie du mois critique, chaînes vérifiées contre la…
- `AGR116` — Débit de conception tiré du besoin retenu (déclaré d'abord), plafonné par le forage et…
- `AGR117` — Pompe neuve : choisie sur le débit de conception, jamais une ligne pompe absente ni une…
- `AGR118` — Pompe existante conservée (D-AGR-7) : variateur et champ dimensionnés sur la PLAQUE…
- `AGR119` — Kit « minimum + options nommées » (D-AGR-8) composé par le noyau
- `AGR120` — Trois tailles tirées du catalogue + hectares irrigables
- `AGR133` — Cas de référence externes en tests de non-régression (AMEE, SPIS, Water Mission…
- `AGR200` — Contrat d'abord : base légale TVA par ligne, date prévue d'une tranche, attestation…
- `AGR201` — Moteur `economie_pompage` (1/5) : la dépense ACTUELLE vient des chiffres déclarés…
- `AGR202` — Moteur `economie_pompage` (2/5) : charges solaires, remplacements au prix réel des…
- `AGR203` — Moteur `economie_pompage` (3/5) : coût du m³ actuel et solaire, sensibilité au prix du…
- `AGR204` — Moteur `economie_pompage` (4/5) : garde de cohérence des litres ou bouteilles déclarés…
- `AGR205` — Moteur `economie_pompage` (5/5) : vue INTERNE (VAN avec taux saisi, scénario butane non…
- `AGR207` — Réglages société : barème des charges solaires de pompage et règle FDA datée (pour le…
- `AGR208` — Requalifier les réglages « bonbonne » morts en REPÈRES énergie datés et sourcés : une…
- `AGR209` — Paramètres › Devis : éditer les repères énergie datés et sourcés ; retirer le…
- `AGR210` — Paramètres › Tarification & ROI : saisir le barème des charges solaires de pompage et…
- `AGR300` — Garde serveur : aucune « Économie / an » ni « Rentabilisé en » résidentiels ne sort sur…
- `AGR301` — `_mode_kpis` agricole : retirer le bassin « ×2 » et le drapeau FDA, servir les heures…
- `AGR302` — Une-page agricole : chiffres à la française, libellés traduits, m³/jour marqué «…
- `AGR303` — Retirer les options PDF agricoles mortes et la surcharge de l'énergie actuelle par un…
- `AGR304` — `synthese_agricole(data)` : UNE fonction serveur pure qui dit l'eau, la pompe, les…
- `AGR305` — Garanties par composant dérivées des lignes du devis pompage (pompe, variateur…
- `AGR309` — Schéma forage → pompe → variateur → panneaux → bassin → irrigation, et courbe de la…
- `AGR400` — Colonnes pompage du Lead, chacune avec sa question d'appel
- `AGR401` — Scinder `pompe_cv` : la pompe ACTUELLE n'est plus jamais la pompe du devis (backend)
- `AGR402` — Promouvoir les réponses agricoles du site, du sac vers les colonnes (webhook + reprise…
- `AGR403` — « Devis auto prêt » agricole sans le CV, et drapeau « visite du point d'eau avant devis…
- `AGR404` — `entrees_pompage` : UNE lecture lead → entrées du dimensionnement, avec leur provenance…
- `AGR408` — CAD123 × D-AGR-4 : la visite de relevé du point d'eau AVANT le devis n'est plus traitée…
- `AGR409` — Score d'un lead agricole : complétude du pompage et dépense déclarée à la place de la…
- `AGR410` — Formulaire Meta agricole : réponses de pompage vers les colonnes, facture jamais…
- `AGR411` — Lien « questionnaire client » : une section pompage, et plus jamais piscine/clim/toit…
- `AGR412` — Visite technique : gabarit « relevé du point d'eau » qui REMPLACE la checklist toiture…
- `AGR413` — À la validation, les mesures du point d'eau remontent au lead (la mesure remplace la…
- `AGR414` — Message « visite de relevé du point d'eau » avec sa liste de préparation (FR + darija)
- `AGR500` — Contrat d'abord : la touche de relance dit le segment du lead
- `AGR501` — Contrat d'abord : l'état du dossier de subvention, champ interne
- `AGR502` — Contrat d'abord : la mesure de la cadence découpée par segment
- `AGR503` — Contrat d'abord : le cockpit « Contrôle du suivi » filtrable par segment
- `AGR504` — Contrat d'abord : « envoyer le résumé à un associé »
- `AGR505` — Contrat d'abord : une réalisation porte son segment
- `AGR506` — Contrat d'abord : la carte des références proches
- `AGR507` — Contrat d'abord : la tâche du playbook sait quel texte proposer
- `AGR510` — Textes FR pompage : plus de facture, de toit, de promesse d'économie ni de « chez vous…
- `AGR511` — Variantes darija pompage de TOUTES les clés agricoles (D-AGR-11)
- `AGR512` — Le réveil saisonnier « factures d'été » exclut l'agricole
- `AGR513` — Réalisation : colonne `segment` et preuve filtrée dans les deux sens
- `AGR522` — Champ interne `dossier_subvention` + rappel « 3 mois après l'approbation préalable »
- `AGR523` — Validité du devis : un dossier de subvention en instruction reçoit la validité du…
- `AGR525` — Playbook FDA réservé à la pompe au butane + seeding idempotent sur les sociétés…
- `AGR600` — Contrat d'abord : relevés de compteur heures / m³ et facturation à l'usage en m³ (SAV)
- `AGR601` — Contrat d'abord : relevés de la pompe saisis par le client sur le portail
- `AGR602` — Chantier pompage (1/2) : régime « déclaration hors réseau » (loi 82-21, art
- `AGR605` — Chantier pompage : checklist et plan d'interventions semés (idempotents), sans «…
- `AGR606` — Réglage société « écart de recette pompage toléré (%) », sans défaut
- `AGR607` — Paramètres : saisir l'écart de recette pompage toléré
- `AGR608` — Modèle et endpoints de la recette pompage (fiche structurée, scopée société…
- `AGR610` — Gate « mise en service » et pack de remise d'un chantier agricole jugés sur la recette…
- `AGR615` — Relevé m³ et facturation à l'usage en m³ : jamais des kWh étiquetés m³
- `AGR619` — Checklist d'entretien « Pompage solaire » semée (idempotente), sans intervalle ni…
- `AGR620` — Catalogue : SKU pompage à « prix à renseigner » — installation pompage, contrat…
- `AGR621` — Étiquette SAV du coffret : téléphone de la société et référence du chantier
- `AGR622` — Garanties pompe/variateur au SAV : une seule source (fiche produit), la garantie légale…
- `AGR623` — Fiche produit : saisir le profil saisonnier de réappro (saison d'irrigation), aucun…
- `AGR625` — Chantier pompage (2/2, l'« AGR602b » de la critique) : gate 82-21 consultatif, étape…
- `CAD1` — [TEST ROUGE D'ABORD] « Intéressé » après devis ne doit plus redémarrer le plan à la…
- `CAD2` — Les trois étapes de VISITE posent la question du suivi de proposition
- `CAD3` — « À rappeler le… » sur une étape de filet la transforme en « Décider la suite — perdu…
- `CAD4` — « Client joint » et « Intéressé » sont deux mots pour le même effet moteur
- `CAD5` — Réponse « Ne plus me contacter » sur toutes les cadences
- `CAD6` — Réponse « Plus tard — pas maintenant » (la plus fréquente du résidentiel), avec le…
- `CAD7` — Réponse « Question de prix — veut négocier »
- `CAD8` — Réponse « Demande un devis modifié » — le libellé existe déjà mais n'est atteignable…
- `CAD9` — Réponse « Décision à plusieurs (famille / propriétaire) », qui pose l'étiquette au…
- `CAD10` — Motif de refus FACULTATIF dans le panneau « Refus », au seul moment où la raison est…
- `CAD11` — Raccourci « Numéro invalide / a bloqué » sur la touche, et `est_junk` visible
- `CAD12` — « Le client accepte » : l'issue la plus importante oblige à quitter l'écran de relance
- `CAD13` — La précision « Répondeur » / « Occupé » est effacée dès que Meryem tape une note
- `CAD14` — L'issue « Visite acceptée » n'a aucun libellé dans l'historique — ni dans le journal…
- `CAD15` — Le journal d'appel de la fiche arrête des cadences sans rien annoncer
- `CAD16` — Sur le DERNIER réveil (J60), « Pas de réponse » promet un réveil suivant qui n'existe…
- `CAD17` — Cause commune : les phrases « suite » sont écrites PAR CADENCE, le comportement dépend…
- `CAD18` — Le lead qui répond au message d'identité AVANT l'appel J0+3 min ne reçoit jamais…
- `CAD19` — Un lead du week-end voit trois jours de protocole s'écraser sur le lundi
- `CAD20` — La règle « jamais plus d'un appel ET un message par jour » est écrite en français et…
- `CAD21` — L'heure imposée d'une touche est effacée dès qu'elle est repoussée d'un jour
- `CAD22` — Une touche naît déjà en retard, et le tableau de bord compte une faute
- `CAD23` — [TRANCHÉ 21/09/2026 — le dimanche le PLUS PROCHE de J+5.]
- `CAD24` — L'« Heure cible » des touches dominicales est un réglage qui s'enregistre sans effet…
- `CAD25` — [TRANCHÉ 21/09/2026 — créneaux par type — messages 09:30, appels 17:30-18:30.]
- `CAD26` — « Rappelez-moi dans trois semaines » translate tout le plan de trois semaines, clôture…
- `CAD27` — Une date de report dans le passé est acceptée et tire tout le plan en arrière
- `CAD28` — La reprise après visite part de la date PRÉVUE, jamais du retour réellement saisi
- `CAD29` — Le champ « délai en minutes » annonce une limite 0-1439 que rien n'applique côté…
- `CAD30` — La justesse du fuseau pendant le Ramadan dépend de la base tzdata de l'image de…
- `CAD31` — La promesse « 5 minutes » ne surveille AUCUN lead publicitaire, et punit Meryem le…
- `CAD32` — « WhatsApp uniquement » est saisi par le client et jamais lu par la cadence
- `CAD33` — [TRANCHÉ 21/09/2026 — lead « WhatsApp uniquement » → dimanche en WhatsApp.]
- `CAD34` — Un lead arrivé par téléphone, sans WhatsApp, n'a aucune cadence
- `CAD35` — Aucune suspension globale quand Meryem est absente
- `CAD36` — La docstring des cadences contredit le gabarit qu'elle décrit
- `CAD37` — La branche Ramadan est MORTE par défaut : les appels sonnent de 09 h à 20 h en plein…
- `CAD38` — La fenêtre de Ramadan par défaut (10 h-14 h) est deux heures plus étroite que la…
- `CAD39` — [TRANCHÉ 21/09/2026 — Ramadan : fenêtre commune 09 h-15 h, pas de soirée.]
- `CAD40` — Les fêtes mobiles (Aïd al-Fitr, Aïd al-Adha, Mawlid, 1er Moharram) ne sont dans aucun…
- `CAD41` — La touche du dimanche court-circuite les fériés ET le Ramadan
- `CAD42` — Un férié non récurrent bloque la même date TOUTES les années — et cocher « Récurrent »…
- `CAD43` — Le samedi est totalement fermé, alors que le dimanche est ouvert par exception
- `CAD44` — [TRANCHÉ 21/09/2026 — agir en avance : Appeler/WhatsApp/Reporter ouverts, « Fait »…
- `CAD45` — Traiter par écrit une touche « appel » impose quand même de répondre « Joint / Non…
- `CAD46` — « Reporter au » et « À rappeler le… » déplacent TOUT le plan, et aucun écran ne le dit
- `CAD47` — « Sauter » n'explique pas ce qu'il fait : Meryem peut croire qu'elle éteint la cadence
- `CAD48` — Le champ « Relance le » de la fiche ment sur ce qu'il fait
- `CAD49` — L'action en masse « définir la relance » écrit une date que le moteur écrase
- `CAD50` — « Annuler » et « Arrêter » n'existent que sur la fiche du lead
- `CAD51` — « Relancer la cadence » peut TUER une cadence en cours, en silence et sans motif
- `CAD52` — [TRANCHÉ 21/09/2026 — pas de variante de rythme — mesurer d'abord.]
- `CAD53` — [TRANCHÉ 21/09/2026 — l'éditeur ouvre l'ajout/suppression de barreau et la case…
- `CAD54` — Réattribuer un lead à un autre commercial : personne ne sait ce que deviennent ses…
- `CAD55` — « Relancer la cadence — Après devis » depuis la fiche crée des touches SANS devis
- `CAD56` — Un devis corrigé et renvoyé ne redate rien : le client reçoit « je classe ? » deux…
- `CAD57` — [TRANCHÉ 21/09/2026 — validité J+30 pour un dossier financé, J+14 sinon.]
- `CAD58` — [TRANCHÉ 21/09/2026 — retirer le canal visite de la générique : J+35 devient un appel.]
- `CAD59` — Le message J9 et le PDF ne calculent pas la validité de la même façon
- `CAD60` — Les deux messages de l'appel du fondateur n'ont aucun bouton — et personne ne sait…
- `CAD61` — [TRANCHÉ 21/09/2026 — document reçu = geste « pièce reçue » ; facture envoyée = trace…
- `CAD62` — Zéro darija sur toute la marche après-devis : le repli en français est silencieux
- `CAD63` — Changer la langue au moment utile coûte trois écrans
- `CAD64` — Le repli de langue est invisible : darija, anglais et arabe classique partent en…
- `CAD65` — « Bonjour M
- `CAD66` — Le message J7 promet un classement « dans trois jours » que le moteur tient à J14
- `CAD67` — Le script « répondeur » part deux fois en 20 heures, et deux appels n'ont aucun script
- `CAD68` — L'écran de réglage des réveils montre des gabarits que le moteur n'enverra pas
- `CAD69` — Les crochets `[ ]` partent tels quels dans WhatsApp, sans aucun avertissement
- `CAD70` — Sans catalogue Réalisations, le message J4 se réduit à une phrase orpheline
- `CAD71` — `avis_google` enverrait au client le lien de SON DEVIS à la place du lien d'avis
- `CAD72` — `parrainage` promet un lien qui n'existe pas — et ce n'est même pas ce texte qui part
- `CAD73` — Le premier réveil dit au client « il y a quelques mois » alors qu'il part six semaines…
- `CAD74` — `reveil_b` (« la saison des factures d'été ») est écrit, validé, et n'est envoyé par…
- `CAD75` — Le réveil n'est pas déclenché par le temps mais par un CLIC : un dossier abandonné n'en…
- `CAD76` — Écrire noir sur blanc que la rentrée scolaire n'est PAS une fenêtre de réveil
- `CAD77` — La recette marketing « Réveil base froide » trace des exécutions sans jamais rien…
- `CAD78` — Les scripts d'appel écrits par le fondateur ne sont JAMAIS affichés
- `CAD79` — Le « vocal » part en texte écrit
- `CAD80` — « Appeler » fait QUITTER l'application, et la note en cours est perdue
- `CAD81` — La langue du lead n'est jamais affichée avant de décrocher
- `CAD82` — Le bouton « Appeler » se désactive en silence, et la préférence du client n'atteint pas…
- `CAD83` — La file du jour trie par heure ; la priorité et le score affichés ne servent à rien
- `CAD84` — La question « message ouvert ? » présume le canal suggéré
- `CAD85` — Les écrans quotidiens de la cadence ne sont couverts par aucun test mobile
- `CAD86` — Quatre écrans de la cadence n'ont été ouverts par personne pendant l'audit
- `CAD87` — Rien ne mesure ce qui prouverait que la cadence marche
- `CAD88` — Le KPI de premier contact neutralise le week-end : un lead qui a attendu 60 heures…
- `CAD89` — Écrire la méthode de comparaison, pour qu'aucun futur run ne recalibre la cadence sur…
- `CAD90` — Le registre de consentement ne couvre que les leads du formulaire du site
- `CAD91` — L'opposition (« ne plus contacter ») n'est jamais tracée au registre
- `CAD92` — Une durée de conservation est déclarée et n'est appliquée nulle part
- `CAD93` — Deux leads du même foyer reçoivent deux cadences parallèles
- `CAD94` — [TRANCHÉ 21/09/2026 — rien sur le score avant la mesure de CAD87.]
- `CAD95` — Joindre une courte vidéo à la preuve chantier J4
- `CAD96` — Trois graphies de la marque dans la même conversation WhatsApp
- `CAD97` — Sur la cadence générique, « Fait — passer à la suite » annonce « demain » à tort
- `CAD98` — Les trois « Appel de suivi » du suivi après-devis n'ont aucun script
- `CAD99` — Afficher la liste des cadences échues (moitié écran de CAD75)
- `CAD100` — Afficher les KPI touche × heure × jour × canal (moitié écran de CAD87)
- `CAD101` — Le client envoie sa facture ou son adresse sur WhatsApp : aucun geste pour…
- `CAD102` — Après l'appel du filet resté sans réponse, l'ERP réclame un devis pour un client jamais…
- `CAD103` — Un lead créé déjà « Contacté » n'entre dans aucun protocole, et rien ne le dit
- `CAD104` — Un lead NEUF créé dans Odoo est refusé en silence par la cadence, et servi par l'écran…
- `CAD105` — [TRANCHÉ 21/09/2026 — la sync Odoo démarre la cadence des leads neufs.]
- `CAD106` — La fusion de deux fiches ne déplace PAS les relances : le doublon fusionné sort du…
- `CAD107` — Un lead perdu qui revient : trois chemins, trois résultats, et le plus courant ne…
- `CAD108` — [TRANCHÉ 21/09/2026 — l'étage 3 exclut le miroir Odoo, comme l'étage 2.]
- `CAD109` — Le script d'appel ne dit ni que l'appel est commercial, ni d'où viennent les données
- `CAD110` — Aucun message ne dit au client comment faire cesser les relances
- `CAD111` — Le message qui propose la visite part sans laisser aucune trace, et son lien wa.me…
- `CAD112` — Deux onglets portent le même nom et montrent deux choses différentes
- `CAD113` — Dans l'éditeur de cadence, une erreur serveur s'affiche en toast générique
- `CAD114` — Le canal « Visite » est proposé à la configuration et ne déclenche rien
- `CAD115` — La file qui lit les signaux est fermée à la personne qui relance
- `CAD116` — Le rappel de 08:30 ne donne qu'un nombre — et il part aussi chez qui ne peut pas le…
- `CAD117` — « X leads sans cadence » n'existe nulle part : le refus se lit fiche par fiche
- `CAD118` — On mesure si les touches sont cochées, jamais si elles joignent quelqu'un
- `CAD119` — La vraie date de création Odoo finit dans une note, pas dans un champ
- `CAD120` — Les notifications ne connaissent aucune fenêtre horaire, et la garde est éteinte par…
- `CAD121` — [TRANCHÉ 21/09/2026 — case WhatsApp du formulaire décochée par défaut.]
- `CAD122` — [TRANCHÉ 21/09/2026 — formalisme 31-08 quand le bon de commande se signe chez le…
- `CAD123` — [TRANCHÉ 21/09/2026 — avertir, sans bloquer, une visite sans devis envoyé.]
- `CAD124` — [TRANCHÉ 21/09/2026 — pas d'axe segment dans le gabarit de cadence.]
- `CAD125` — Le dossier 82-21 et le dossier FDA sont captés et ne déclenchent aucune parole
- `CAD126` — Les textes sont 100 % résidentiels : « sur votre toit » part à un pompage au bord d'un…
- `CAD127` — « Vous venez de remplir notre formulaire » est faux pour la moitié des origines
- `CAD128` — Un ancien client SIGNÉ qui redemande un devis est refusé comme « doublon »
- `CAD129` — Le client clique « rappelez-moi » : sa demande n'entre pas dans la file
- `CAD130` — Le client rouvre sa proposition trois fois dans la soirée : la cadence ne bouge pas…
- `CAD131` — « Rappelé en moins de 5 minutes » se valide en SAUTANT la première touche
- `CAD132` — Le filet « lead chaud non contacté » ne peut pas se déclencher sur un lead Meta, et…
- `CAD133` — Le score ne regarde que ce que le client a DIT, jamais ce qu'il FAIT
- `CAD134` — La même phrase du client vaut 8 points depuis le site et 0 depuis Meta
- `CAD135` — « Le client relit la page du prix » : le code dit lui-même qu'il faut appeler, et…
- `CAD136` — Questionnaire rempli, photo de facture reçue : silence complet
- `CAD137` — « Rouvert 3 fois » se déclenche sur une seule visite
- `CAD138` — Le panier « relance d'engagement » ne se vide jamais et masque les devis qui expirent
- `CAD139` — Du code mort laisse croire que l'ouverture d'un devis fait avancer le funnel
- `CAD140` — Le « score d'engagement client » a abandonné le seul signal comportemental qu'il devait…
- `CAD141` — Le rafraîchissement nocturne des scores balaie les dossiers clos
- `CAD142` — Le Journal du plan de relance ne mentionne jamais les visites, que la Frise affiche…
- `CAD143` — L'éditeur n'a pas d'onglet pour la cadence « Générique », pourtant encore active sur de…
- `CAD144` — Un achat de coopérative ou un comité industriel n'a qu'UN seul contact dans le CRM
- `CAD145` — Le type d'installation est stocké à deux endroits
- `CAD146` — Un prospect de la diaspora reçoit ses touches à l'heure de Casablanca
- `CAD147` — T0 — Le contrat du panneau d'appel, livré SEUL et en premier (PACT10)
- `CAD148` — T1 — L'endpoint « questions à poser sur cet appel »
- `CAD149` — T2 — Migration « vague 1 » : les champs qui manquent, et les SIX endroits à tenir
- `CAD150` — T3 — Les champs captés par le site sont figés en lecture seule, même quand ils sont…
- `CAD151` — T4 — `appelGuidance.js` : le contenu du script, sur le patron de `visiteGuidance.js`
- `CAD152` — T5 — `PanneauScriptAppel.jsx` : le script sous les yeux pendant l'appel
- `CAD153` — T9 — Les tests qui figent le script guidé
- `CAD154` — Vague 2 des champs, à ouvrir seulement après la vague 1
- `CAD155` — Pendant le Ramadan, l'appel du soir n'existe pas — aucun script ne le dit
- `CAD156` — « Je vous rappelle jeudi à 18 h » : l'heure promise n'a aucun champ
- `CAD157` — Dire à l'écran ce qui n'est PAS compté
- `CAD158` — « Votre facture, c'est pour un mois ou pour deux ? » — la périodicité n'est nulle part
- `CAD159` — [TRANCHÉ 21/09/2026 — champs du site TOUJOURS éditables, jamais reposés.]
- `CAD160` — [TRANCHÉ 21/09/2026 — vague 1 confirmée telle quelle.]
- `CAD161` — [TRANCHÉ 21/09/2026 — panneau résidentiel d'abord, agricole/industriel en seconde…
- `CAD162` — [TRANCHÉ 21/09/2026 — ordre de l'appel 1 : facture, été, occupation, toit, objectif.]
- `CAD163` — [TRANCHÉ 21/09/2026 — 82-21 : rien de spontané, une phrase factuelle sans tarif si le…
- `CAD164` — [TRANCHÉ 21/09/2026 — locataire : demander le propriétaire, sinon « Perdu — Locataire…
- `CAD165` — T6 — Quatre correctifs du moteur horaire, tous visibles sur le chiffre client
- `CAD166` — T7 — Le pro qui donne ses kWh sur le site reste « incomplet » dans l'ERP
- `CAD167` — T8 — La liste des distributeurs devient les SRM régionales, et « autre » cesse de…
- `CAD168` — Deux lignes fixes de la facture ne sont jamais dites, et elles creusent l'écart entre…
- `CAD169` — [TRANCHÉ 21/09/2026 — VE prévue : comptée des deux côtés, devis étiqueté.]
- `CAD170` — [TRANCHÉ 21/09/2026 — recharge nocturne : dimensionner la batterie pour la couvrir.]
- `CAD171` — [TRANCHÉ 21/09/2026 — créneau déclaré sans chargeur : étaler sur tout le créneau.]
- `CAD172` — [TRANCHÉ 21/09/2026 — occupation non posée : présence supposée + bandeau sur la…
- `CAD173` — [TRANCHÉ 21/09/2026 — lot des 13 réglages du calcul et du contenu.]
- `CAD174` — La moitié écran de la migration : un champ qui n'est pas déclaré à la fiche est…
- `CAD175` — Seconde livraison du panneau d'appel : agricole (pompage) et industriel
- `CAD176` — La touche e-mail rend un texte vide et l'adresse du client n'atteint jamais la file
- `CAD178` — Aucune mesure mobile des gestes de relance
- `CIQ1` — Contrat d'abord : forme pro du Lead, règle « devis auto prêt » pro, drapeau…
- `CIQ2` — Contrat d'abord : aperçu serveur C&I `POST /ventes/etude-ci/preview/` + clés…
- `CIQ3` — Contrat d'abord : le bloc `economie_ci` (économies C&I serveur), ses saisies, ses…
- `CIQ4` — Contrat d'abord : la charge utile publique d'un devis commercial ou industriel…
- `CIQ5` — Contrat d'abord : la visite technique C&I (gabarit `ci`, non relevé, déclaré/constaté…
- `CIQ6` — Contrat d'abord : la recette C&I (IEC 62446-1), les réserves et la réception provisoire…
- `CIQ7` — Contrat d'abord : le produit C&I structuré (rôles C&I, type de pose, fiches limiteur /…
- `CIQ8` — Contrat d'abord : le client « entreprise » créé ou rattaché depuis un lead pro, sans…
- `CIQ9` — Contrat d'abord : l'acceptation d'un devis par une entreprise (raison sociale…
- `CIQ10` — Contrat d'abord : relance B2B — `{societe}`, raison de l'attente d'un accord, canal…
- `CIQ11` — Contrat d'abord : le tarif DÉCLARÉ de la facture du client, la grille officielle…
- `CIQ12` — Contrat d'abord : le dossier 82-21 — régime suggéré sourcé, pièces par étape, statut…
- `CIQ200` — Contrat d'abord : échéancier C&I à N jalons, retenue de garantie, pénalités et caution…
- `CIQ400` — Contrat d'abord : questionnaire client pro, relève « Affiner » du site et clés pro du…
- `CIQ669` — Contrat d'abord : le contrat O&M C&I (prestations nommées, délai d'intervention en…
- `QAH1` — Skill `qa-explorer` : flotte d'agents « testeur humain » qui explore l'ERP démo module…
- `QAH2` — Invariants Hypothesis sur la chaîne d'argent et la chaîne d'états des documents ventes
- `QAH3` — Test différentiel `solar.js` ↔ `quote_engine/builder.py` sur un corpus figé
- `QAH4` — Balayage d'isolation multi-tenant sur TOUTES les routes du routeur (IDOR/BOLA)
- `QAH5` — Mutation nightly : passer à mutmut 3, étendre la portée aux filtres tenant et à la…
- `QAH6` — Schemathesis dans `release-verify` à partir du schéma drf-spectacular
- `QAH7` — Marcheur aléatoire gremlins.js sur chaque écran (matrice e2e complète)
- `QAH8` — Sentry armé pour le pilote : SDK React installé, session replay masqué, tag société des…
- `QAH9` — Brief de bug bash pour 1-2 testeurs humains francophones (chartes par rôle, gabarit de…
- `QAH11` — Commande « setup nightly QA » : script idempotent `scripts/setup-nightly-qa.ps1` +…
- `QAH12` — étendre `seed_demo` pour les deux angles morts du qa-explorer du 28/09 : un compte…
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
- `SOLMVP54` — CI sous 2 minutes (demande fondateur 21/09, APRÈS le merge SOLMVP)
- `CALX1` — Poser le rail d'onglets de l'atelier et y faire entrer les 13 panneaux invisibles
- `CALX2` — Rendre append-only les surfaces partagées du module et sortir `urls.py` du chemin de…
- `CALX3` — Faire exposer par le constructeur 3D l'entrée moteur, l'application d'un plan et les…
- `CALX4` — Figer le contrat de la simulation avant ses deux moitiés
- `CALX5` — Construire le service d'orchestration de la simulation et sa porte HTTP, sur la chaîne…
- `CALX6` — Persister la série horaire et rendre l'export horaire réellement téléchargeable
- `CALX7` — Lever le masquage qui empêche l'export tableur CSV d'être enregistré
- `CALX8` — Remettre au panneau de l'atelier l'API du constructeur, et non la référence qui la…
- `CALX14` — Rendre visibles la batterie et le hors-réseau que la chaîne calcule
- `CALX16` — Brancher la chaîne électrique la plus faible en ombrage sur le verdict
- `CALX17` — Brancher la masse installée et la feuille de lestage sur un panneau
- `CALX18` — Ouvrir l'éditeur des postes de pertes
- `CALX19` — Ouvrir l'inventaire des sorties et y brancher la planche cotée
- `CALX20` — Brancher les trois plans (pose, toiture, masse) sur le panneau Documents
- `CALX21` — Brancher la note de calcul et son verdict de preuve
- `CALX22` — Brancher l'export DXF et l'export XLSX
- `CALX23` — Brancher l'export tableur CSV, une fois son enregistrement réparé
- `CALX24` — Brancher la composition du pack technique
- `CALX25` — Ouvrir le relevé terrain (chaînes de cotes) sur un panneau
- `CALX26` — Brancher l'archivage et la restauration depuis la corbeille
- `CALX27` — Brancher le déverrouillage d'une conception figée
- `CALX28` — Brancher l'export et l'import du document de conception
- `CALX29` — Brancher la suggestion de pente LiDAR, France seulement
- `CALX30` — Brancher les profils types de consommation de la société
- `CALX31` — Ouvrir le fil d'activité du calepinage
- `CALX32` — Brancher les colonnes de tri déjà servies par la liste
- `CALX33` — Permettre de renommer un calepinage après sa création
- `CALX35` — Exposer la duplication de calepinage qui existe déjà dans le service
- `CALX36` — Ouvrir l'historique des versions et la restauration
- `CALX37` — Permettre de créer et de dupliquer une variante
- `CALX38` — Permettre de téléverser une photo de site
- `CALX39` — Ouvrir une porte HTTP pour l'import d'un plan DXF/PDF/image
- `CALX40` — Ouvrir la génération d'un dossier réglementaire
- `CALX41` — Faire enregistrer les champs à compléter d'un dossier
- `CALX42` — Brancher le marquage « modèle » et la création depuis un modèle
- `CALX43` — Ouvrir l'édition des préréglages et des favoris de la société
- `CALX45` — Figer le contrat du calepinage publié avec un devis
- `CALX46` — Publier le calepinage d'un devis et rendre le bloc de retour vivant
- `CALX47` — Ouvrir le module calepinage depuis la fiche d'un lead
- `CALX48` — Rendre le refus « production non calculée » actionnable
- `CALX49` — Brancher la priorité de remplissage déjà écrite
- `CALX50` — Dessiner le champ au sol au lieu de n'en donner que le compte
- `CALX51` — Dessiner l'ombrière à sa hauteur libre saisie
- `CALX52` — Afficher, ou faire saisir, la hauteur de toit supposée du diagramme solaire
- `CALX53` — Signaler les coefficients de température non sourcés jusque dans le verdict
- `CALX54` — N'offrir que les calques réellement présents dans la scène
- `CALX55` — Poser le retour vers l'atelier depuis chaque lien profond
- `CALX56` — Fermer le trou de la garde d'atteignabilité sur les chemins paramétrés
- `CALX57` — Poser la garde « service sans appelant » et l'e2e du parcours complet
- `CALX58` — Publier TOF et TSRF par pan, à côté de l'accès solaire
- `CALX59` — Aligner la série météo (UTC) sur l'heure locale du site avant tout croisement avec une…
- `CALX60` — Ajouter à la fiche technique, en UNE migration, tout ce que la chaîne de pertes et…
- `CALX61` — Brancher enfin le fournisseur de températures TMY que la chaîne électrique attend
- `CALX62` — Accepter un fichier météo horaire déposé par la société, à la place de PVGIS, pour un…
- `CALX63` — Compléter le dispatch batterie : écrêtage récupéré en couplage DC, stratégie « plafond…
- `CALX64` — Montrer la série horaire : tapis de chaleur jour × heure et journée type par mois
- `CALX65` — Dire dans l'atelier laquelle des deux productions parle : l'estimation rapide du…
- `CALX68` — Garder un brouillon local de l'atelier et proposer sa reprise
- `CALX69` — Donner une saisie aux réglages société de simulation et d'électrique, avec provenance…
- `CALX70` — Faire servir la simulation persistée par `GET resultat/`, avec un contrôle de fraîcheur
- `CALX72` — Saisir dans l'écran Tarification les réglages ajoutés par le lot 5
- `CALX81` — Porter au contrat le type d'arête corrigé à la main et le retrait PAR arête
- `CALX82` — Porter au contrat un catalogue de MODULES dans le document et le module retenu par pan
- `CALX83` — Porter au contrat la numérotation persistante des modules et des rangées
- `CALX84` — Porter au contrat les bâtiments : hauteur et nombre d'étages SAISIS, avec provenance
- `CALX85` — Porter au contrat les obstacles non rectangulaires (polygone, cercle)
- `CALX86` — Porter au contrat le calque de fond calé (plan importé ou photo) et son échelle à deux…
- `CALX87` — Porter au contrat la surface de pose « façade » et les poteaux d'ombrière
- `CALX88` — Porter au contrat les choix d'optimisation et le soleil de scène
- `CALX89` — Magnétiser le tracé à 90° et 45° et offrir un mode orthogonal
- `CALX90` — Saisir au clavier la longueur et l'angle du segment en cours de tracé
- `CALX91` — Insérer et supprimer un sommet sur une arête d'un contour fermé
- `CALX92` — Aimanter le tracé aux sommets et aux arêtes des pans déjà tracés
- `CALX93` — Déduire noue et arêtier en comparant les pans voisins
- `CALX94` — Corriger à la main le type d'une arête depuis l'atelier
- `CALX95` — Appliquer un retrait propre à chaque arête physique du contour
- `CALX96` — Ajouter les formes de toit en L et en T à la bibliothèque de préréts
- `CALX97` — Saisir les cotes exactes d'un pan et le faire pivoter d'un bloc
- `CALX98` — Dupliquer un pan avec ses obstacles et ses réglages
- `CALX99` — Prendre l'azimut d'un pan depuis une arête cliquée
- `CALX100` — Saisir la hauteur et le nombre d'étages du bâtiment, et extruder la 3D à cette hauteur
- `CALX101` — Rendre les murs et les acrotères comme des volumes 3D distincts
- `CALX102` — Modéliser une lucarne comme un volume qui perce le pan, pas comme une boîte posée
- `CALX103` — Tracer un obstacle polygonal au clic
- `CALX104` — Tracer un obstacle circulaire et réutiliser des gabarits d'obstacle de la société
- `CALX105` — Poser un arbre ou un bâtiment voisin au clic et le déplacer au glissé
- `CALX106` — Remonter la hauteur et le nombre de niveaux OSM du bâtiment, avec leur provenance…
- `CALX107` — Afficher un plan importé ou une photo calée comme calque de fond de l'atelier
- `CALX108` — Caler le fond de plan à l'échelle par deux points et une distance réelle saisie
- `CALX109` — Choisir le module depuis le stock et calepiner avec ses vraies cotes
- `CALX110` — Poser plusieurs modèles de module dans un même système
- `CALX111` — Numéroter les modules de façon stable et l'afficher en 3D comme en plan
- `CALX112` — Dupliquer une sélection de panneaux et la coller au pas saisi
- `CALX113` — Rendre la symétrie d'une sélection de panneaux par rapport à un axe
- `CALX114` — Choisir la cible de l'optimisation au lieu de la figer sur l'énergie
- `CALX115` — Écarter d'emblée les emplacements sous un seuil d'accès solaire saisi
- `CALX116` — Sélectionner des panneaux au lasso, en plus du rectangle
- `CALX117` — Afficher une grille métrique de repère au pas saisi
- `CALX118` — Montrer la course du soleil du site dans l'atelier
- `CALX119` — Choisir une date libre pour le soleil de la scène et la retenir
- `CALX120` — Animer la course de l'ombre sur une journée et sur l'année
- `CALX121` — Dessiner la coupe transversale d'une rangée sur l'autre
- `CALX122` — Lire la fréquence d'ombrage de chaque module sur l'année
- `CALX123` — Tracer et éditer un champ au sol sur la carte de l'atelier
- `CALX124` — Éditer une ombrière dans l'atelier, poteaux compris
- `CALX125` — Poser des modules en façade sur un mur du bâtiment
- `CALX126` — Totaliser le site par bâtiment et par surface de pose dans l'atelier
- `CALX128` — Rendre les gestes de l'atelier utilisables au clavier et annoncés
- `CALX129` — Basculer la vue 3D d'édition en plein écran
- `CALX130` — Prouver le parcours de conception enrichi de bout en bout
- `CALX132` — Proposer la hauteur OSM dans le panneau Bâtiment du constructeur, sans jamais l'écrire…
- `CALX141` — Déclarer le contrat de la cascade de pertes séquentielle, sous une clé neuve
- `CALX142` — Déclarer le contrat de la série horaire persistée
- `CALX143` — Déclarer le contrat de l'énoncé de source météo
- `CALX144` — Déclarer le contrat d'incertitude et de quantiles
- `CALX145` — Ouvrir deux sections société — « simulation » et « electrique_societe » — au registre…
- `CALX146` — Donner au noyau une position solaire HORAIRE (le dépôt n'en a qu'une, au solstice)
- `CALX147` — Écrire l'ordonnanceur de la chaîne de pertes
- `CALX148` — Déclarer l'ordre de la chaîne une fois, avec ses règles d'exclusivité et ses étapes…
- `CALX149` — Faire primer le poste CALCULÉ sur le poste saisi, et refuser le double comptage
- `CALX150` — Demander à PVGIS l'irradiance NUE et non sa propre production
- `CALX151` — Passer NOTRE horizon à PVGIS, et dire lequel fait foi
- `CALX152` — Séparer direct, diffus et réfléchi — sans quoi ni IAM ni ombrage ne se calculent
- `CALX153` — Laisser choisir entre année météo type et fenêtre pluriannuelle, et en tirer les…
- `CALX154` — Publier le bloc `meteo` dans le résultat
- `CALX155` — Une requête météo par PLAN, jamais par module
- `CALX156` — Étape « horizon » : masquer le direct heure par heure sous la ligne d'horizon
- `CALX157` — Étape « ombrage proche » : appliquer la matrice 12×24 HEURE PAR HEURE
- `CALX158` — Étape « accès module » : lire `solarAccess` par module au lieu d'un facteur de toit
- `CALX159` — Étape « inter-rangées » : l'auto-ombrage horaire depuis la géométrie 3D
- `CALX160` — Étape « IAM » : Fresnel par défaut (physique, sourcé), ASHRAE ou Martin-Ruiz sur choix…
- `CALX161` — Étape « salissure » : douze valeurs mensuelles, pas une moyenne
- `CALX162` — Étape « niveau d'irradiance » : le faible éclairement, depuis la courbe de la fiche
- `CALX163` — Étape « thermique » : Faiman avec des coefficients PAR TYPE DE POSE, NOCT en repli…
- `CALX164` — Donner enfin le vent au modèle thermique
- `CALX165` — Étape « qualité module » : la tolérance de la fiche, ou rien
- `CALX166` — Étape « LID » : selon la technologie de cellule, et seulement si la société la chiffre
- `CALX167` — Étape « mismatch fabricant » : la dispersion des modules, saisie et sourcée
- `CALX168` — Étape « mismatch d'ombrage » : l'effondrement I-V d'une chaîne dont un module est…
- `CALX169` — Étape « ohmique DC » : la chute réelle des câbles, plus jamais saisie en double
- `CALX170` — Étape « onduleur » : la courbe η(P), sinon le rendement européen, sinon rien
- `CALX171` — Étape « fenêtre MPPT » : les heures où la tension sort de la plage
- `CALX172` — Étape « écrêtage » : brancher le calcul horaire qui existe déjà et n'a jamais de série
- `CALX173` — Étape « ohmique AC » : la liaison onduleur-comptage, sur sa longueur saisie
- `CALX174` — Étape « transformateur » : seulement si la société en déclare un
- `CALX175` — Étape « auxiliaires » : une énergie soutirée, jour et nuit, pas un pourcentage
- `CALX176` — Étape « indisponibilité » : des fenêtres d'arrêt datées, pas un forfait annuel
- `CALX177` — Faire entrer le bifacial dans la chaîne, avec un albédo MENSUEL
- `CALX178` — Étape « vieillissement » : une production ANNÉE PAR ANNÉE, pas un pourcentage unique
- `CALX179` — Publier le ratio de performance au sens de la norme IEC 61724-1
- `CALX181` — Rendre les tableaux mensuels et par pan cohérents avec la cascade
- `CALX182` — Simuler MODULE PAR MODULE, et agréger
- `CALX183` — Agréger la production par chaîne, MPPT et onduleur
- `CALX184` — Mesurer σ, ou refuser — supprimer le repli 6 % non sourcé
- `CALX185` — Composer l'incertitude en quadrature, comme une étude bancable
- `CALX186` — Ajouter P95 aux quantiles publiés
- `CALX188` — Faire tourner le dispatch batterie sur la série AC réelle
- `CALX189` — Construire la courbe de charge horaire, VE et PAC compris
- `CALX190` — Publier l'autoconsommation et le plafond d'injection sur la vraie série
- `CALX191` — Chiffrer le défaut d'alimentation hors réseau sur la série réelle
- `CALX192` — Dire la vérité sur la résolution : PVGIS est horaire
- `CALX193` — Persister la série horaire que l'export attend depuis toujours
- `CALX195` — Bâtir le harnais de validation contre PVGIS lui-même
- `CALX196` — Figer un golden pluriannuel de la cascade et des quantiles
- `CALX197` — Un seul calcul d'ombrage pour un même toit
- `CALX198` — Adopter `pvlib` (tranché par Reda le 21/09/2026) pour le modèle à une diode, la…
- `CALX201` — Déclarer le contrat `electrical.equipements[]` du document v2
- `CALX202` — Déclarer le contrat `electrical.cheminements[]` du document v2
- `CALX203` — Déclarer le contrat des tronçons de câble calculés
- `CALX204` — Déclarer le contrat du schéma unifilaire éditable
- `CALX205` — Déclarer le contrat du raccordement réseau
- `CALX206` — Autoriser plusieurs orientations sur UNE entrée MPPT (jamais dans une chaîne)
- `CALX207` — Calculer l'écart de puissance d'un groupe polystring et le verdicter sur un seuil…
- `CALX209` — Dimensionner une branche AC de micro-onduleurs
- `CALX210` — Calibrer la protection et le câble d'une branche AC de micro-onduleurs
- `CALX211` — Fermer la longueur de chaîne à optimiseurs quand la fiche publie enfin la sortie…
- `CALX212` — Compter et placer les optimiseurs module par module
- `CALX213` — Contrôler enfin les deux bornes d'onduleur publiées mais jamais lues
- `CALX214` — Publier, contrôle par contrôle, LA température qui a servi
- `CALX215` — Nommer les deux natures de dépassement : plage INTERDITE et plage BLOQUANTE
- `CALX216` — Dire POURQUOI cette longueur de chaîne a été retenue
- `CALX217` — Rejouer l'incident DEV-202608-0016 sur les trois régimes de chaînage
- `CALX218` — Choisir le motif de parcours d'une chaîne et en tirer sa longueur de câble
- `CALX219` — Créer `electrique3d.ts` et y poser les marqueurs d'équipement
- `CALX220` — Poser, déplacer et retirer un équipement au clic, et le persister
- `CALX221` — Ajouter le calque « Électrique » au panneau de calques
- `CALX222` — Donner à l'atelier son onglet « Équipements électriques »
- `CALX223` — Tracer un cheminement de câble par points de passage dans l'atelier
- `CALX224` — Mesurer la longueur RÉELLE de chaque tronçon
- `CALX225` — Dimensionner la section et la chute PAR tronçon
- `CALX226` — Cumuler la chute de tension bout en bout et la verdicter une seule fois
- `CALX227` — Produire le métré de câble par tronçon et par section
- `CALX228` — Servir les tronçons en HTTP et les joindre au résultat électrique
- `CALX229` — Donner à l'atelier son onglet « Cheminement & câbles »
- `CALX230` — Dimensionner un coffret de jonction DC par son nombre d'entrées
- `CALX231` — Dimensionner le coffret de regroupement quand plusieurs coffrets remontent
- `CALX232` — Dimensionner le coffret AC par ses départs
- `CALX233` — Persister les libellés et les repères édités du schéma unifilaire
- `CALX234` — Persister les positions de blocs et les passer jusqu'au dessin
- `CALX235` — Exporter le schéma unifilaire en DXF
- `CALX236` — Exporter le schéma unifilaire en PNG depuis le navigateur
- `CALX237` — Choisir un gabarit de schéma par pays, sans supposer une norme au Maroc
- `CALX238` — Replier les circuits d'onduleurs identiques en un seul « typique de N »
- `CALX241` — Calculer l'élévation de tension au point de raccordement contre une limite SAISIE
- `CALX242` — Vérifier la puissance de raccordement et le régime mono/tri
- `CALX243` — Équilibrer les phases quand plusieurs onduleurs monophasés se branchent sur un réseau…
- `CALX244` — Servir le raccordement en HTTP et lui donner son onglet
- `CALX245` — Étendre la check-list de terre à la continuité mesurée de l'existant
- `CALX246` — Rattacher chaque ligne de nomenclature électrique à une référence du catalogue
- `CALX247` — Retirer les quantités de structure non sourcées de la nomenclature électrique
- `CALX248` — Prononcer un verdict électrique publiable unique, entrée par entrée sourcée
- `CALX249` — Donner à l'atelier son onglet « Verdict électrique »
- `CALX250` — Garder en CI qu'aucun seuil électrique n'entre sans source
- `CALX251` — Déclarer `consumption` dans le contrat `roof_layout` v2
- `CALX253` — Sérialiser la consommation de l'atelier dans le document
- `CALX254` — Ré-hydrater la consommation au rechargement de l'atelier
- `CALX255` — Lire la consommation du document côté serveur
- `CALX256` — Persister la méthode « somme d'appareils » avec la provenance de chaque appareil
- `CALX257` — Convertir les montants MAD en kWh par le barème de la société
- `CALX258` — Ouvrir les profils société au segment pompage et au type de jour
- `CALX259` — Enregistrer une courbe importée comme profil société, avec sa provenance de fichier
- `CALX260` — Décaler la courbe pendant le Ramadan sans introduire un seul chiffre neuf
- `CALX261` — Offrir les deux modes de recharge du véhicule électrique
- `CALX262` — Borner la recharge par la puissance de la borne et dire le débordement
- `CALX263` — Modéliser la climatisation en BTU avec un EER saisi
- `CALX264` — Faire dépendre le COP de la pompe à chaleur de la température saisie
- `CALX265` — Rattacher une clé tarifaire à chaque charge déclarée
- `CALX267` — Simuler plusieurs groupes de batteries, chacun avec son couplage
- `CALX268` — Ajouter la commande horaire à SOC cible par groupe
- `CALX269` — Publier la pointe avant et après effacement
- `CALX270` — Déduire la réserve de secours des appareils réellement secourus
- `CALX271` — Proposer des capacités candidates depuis la motivation du client, sans aucun prix
- `CALX272` — Rendre saisissables les seuils de protection de la batterie hors-réseau
- `CALX274` — Faire saisir les tranches horaires et leurs tarifs par la société, avec source et date
- `CALX275` — Découper les tranches horaires par saison
- `CALX276` — Typer le mécanisme de compensation du surplus
- `CALX277` — Admettre une grille tarifaire à prix unique ou à deux postes horaires pour les sociétés…
- `CALX278` — Séparer les taxes des prix dans la grille société
- `CALX279` — Faire saisir l'indexation annuelle et trancher la contradiction interne
- `CALX280` — Poser le contrat du bloc économie servi par `apps/ventes`
- `CALX281` — Construire le flux de trésorerie, la VAN, le TRI et le retour actualisé dans…
- `CALX282` — Calculer le coût actualisé du kWh (LCOE)
- `CALX283` — Modéliser les prêts : annuité, échéances constantes, différé
- `CALX284` — Ajouter l'amortissement et la fiscalité en paramètres société
- `CALX285` — Faire passer le P90 dans le flux de trésorerie
- `CALX286` — Remplacer les défauts financiers non sourcés par une omission motivée, et le prouver
- `CALX287` — Exiger un tarif PPA saisi
- `CALX288` — Servir le bloc économie en lecture seule depuis `apps/ventes`
- `CALX289` — Monter un onglet « Économie » en lecture seule dans l'atelier
- `CALX290` — Comparer deux scénarios sur le MÊME flux
- `CALX291` — Publier le contrat de l'inventaire « Documents »
- `CALX292` — Publier le contrat des sections du rapport d'étude
- `CALX293` — Publier le contrat de l'export JSON projet + résultats
- `CALX294` — Donner aux documents du module un gabarit société (en-tête, pied, logo, couleurs)
- `CALX295` — Imprimer une page de garde avec l'identité société et projet
- `CALX296` — Servir les documents techniques en français et en anglais
- `CALX297` — Bâtir le rapport d'étude PDF et son endpoint
- `CALX298` — Écrire la section Site et source météo du rapport
- `CALX299` — Écrire la section Système, l'annexe des fiches et JOINDRE les fiches PDF constructeur
- `CALX300` — Écrire la section Chaîne de pertes SÉQUENTIELLE (table)
- `CALX301` — Écrire la section Production mensuelle, PR et P50/P90
- `CALX302` — Écrire la section Ombrage et recevoir sa carte de chaleur produite par le navigateur
- `CALX303` — Écrire la section Électrique du rapport, schéma unifilaire inclus
- `CALX304` — Écrire la section Nomenclature SANS prix du rapport
- `CALX305` — Écrire la section Régime de preuve et empreinte du rapport
- `CALX306` — Donner au rapport un sommaire, une pagination et un test de pages
- `CALX307` — Laisser la société choisir les sections incluses dans ses rapports
- `CALX308` — Rendre le diagramme de pertes en SVG côté serveur
- `CALX309` — Rendre enfin le plan de toiture et le plan de masse dans le dossier technique
- `CALX310` — Produire le plan de câblage des chaînes, en PDF et en DXF
- `CALX312` — Exporter le projet et ses résultats en JSON versionné
- `CALX313` — Laisser choisir les colonnes et le pas de temps de l'export horaire
- `CALX314` — Poser la provenance sur TOUS les exports, pas seulement le CSV
- `CALX315` — Produire une présentation compacte INTERNE de deux pages, sans aucun montant
- `CALX316` — Produire le manuel du propriétaire depuis un gabarit société
- `CALX317` — Produire un rapport d'ombrage autonome
- `CALX318` — Imprimer le document as-built (prévu, posé, écarts, photos)
- `CALX319` — Assembler le dossier de fin de chantier du calepinage
- `CALX320` — Étendre le panneau Documents : versions, données manquantes nommées, images jointes
- `CALX321` — Nommer, donnée par donnée, ce qui manque à chaque document
- `CALX322` — Versionner les documents produits
- `CALX323` — Servir un aperçu HTML avant le PDF
- `CALX324` — Journaliser l'émission d'un document dans le fil du calepinage
- `CALX325` — Dire sur la pièce qu'elle vient d'une conception verrouillée ou archivée
- `CALX326` — Faire entrer le rapport d'étude et le plan de câblage dans le dossier technique
- `CALX327` — Interdire tout mot de montant dans le TEXTE EXTRAIT de chaque document du module
- `CALX328` — Verrouiller le nombre de pages attendu de chaque document
- `CALX329` — Poser une garde CI : un document déclaré a un rendu
- `CALX330` — Imprimer l'annexe « hypothèses, sources et omissions » du rapport
- `CALX331` — Figer le contrat de la comparaison de plusieurs calepinages
- `CALX332` — Figer le contrat des étiquettes libres d'un calepinage
- `CALX333` — Figer le contrat du différentiel entre deux versions
- `CALX334` — Figer le contrat de l'approbation d'un calepinage
- `CALX335` — Figer le contrat du catalogue de fixation et de sa nomenclature
- `CALX336` — Figer le contrat de la reprise d'une visite technique dans un calepinage
- `CALX337` — Figer le contrat des écarts de pose réelle
- `CALX340` — Étendre le contrat des réglages avec les zones de vent et de neige société
- `CALX341` — Construire la comparaison de jusqu'à 5 calepinages et son export tableur
- `CALX342` — Servir la comparaison de calepinages sur sa propre route de liste
- `CALX343` — Poser les étiquettes libres et leur filtre de liste
- `CALX344` — Afficher et filtrer les étiquettes dans la liste et la fiche
- `CALX345` — Calculer le différentiel champ par champ entre deux versions
- `CALX346` — Monter le différentiel de versions en onglet de l'atelier
- `CALX347` — Créer le rôle relecteur et la décision d'approbation
- `CALX348` — Exiger l'approbation avant de retenir une variante, en réglage société
- `CALX349` — Monter la décision d'approbation en onglet de l'atelier
- `CALX351` — Démarrer un calepinage depuis un modèle et un jeu de réglages société
- `CALX352` — Proposer modèle et jeu de réglages au moment de la création
- `CALX355` — Rendre les nouveaux champs de fiche saisissables dans le formulaire produit
- `CALX358` — Créer le catalogue de systèmes de fixation dans le module
- `CALX359` — Calculer la nomenclature de fixation d'un calepinage et l'exporter
- `CALX360` — Monter la fixation en onglet de l'atelier
- `CALX361` — Saisir les zones de vent et de neige par site et servir la feuille de lestage
- `CALX362` — Monter le lestage en onglet de l'atelier
- `CALX363` — Ouvrir la porte visite technique → calepinage côté `apps.visites`
- `CALX364` — Reprendre les mesures et les photos d'une visite dans le calepinage, avec leur…
- `CALX365` — Monter la reprise de visite en onglet de l'atelier
- `CALX366` — Ouvrir la porte de la pose réelle et transformer les écarts en version
- `CALX367` — Monter la pose réelle en onglet de l'atelier
- `CALX368` — Publier l'évènement « calepinage simulé » et son webhook
- `CALX369` — Servir le résultat de simulation d'un calepinage en lecture publique
- `CALX370` — Exporter et réimporter un projet de calepinage complet en JSON
- `CALX371` — Monter l'export et l'import de projet en onglet de l'atelier
- `CALX372` — Garder la frontière du module contre les couplages interdits, depuis une base mesurée
- `CALX381` — Garder qu'aucune `@action` du module ne reste sans consommateur
- `CALX382` — Garder qu'aucune clé de `calepinageApi.js` ne reste jamais appelée
- `CALX383` — Garder qu'un onglet du rail arrive avec son test
- `CALX384` — Étendre au paquet `services/` la discipline de provenance des constantes
- `CALX385` — Garder qu'un échantillon de contrat a bien ses DEUX moitiés
- `CALX386` — Traverser le parcours calepinage COMPLET en e2e, et le faire tourner par PR
- `CALX387` — Prouver que chaque onglet du rail s'ouvre, en e2e
- `CALX388` — Porter le budget de performance de l'atelier à 10 000 modules
- `CALX389` — Déclarer et garder le temps de la chaîne de simulation
- `CALX390` — Donner au module ses budgets de requêtes SQL
- `CALX391` — Affirmer le déterminisme de la simulation, entrée pour entrée
- `CALX392` — Rendre le rail d'onglets utilisable au clavier
- `CALX393` — Écrire la chaîne de simulation dans `docs/moteur-calepinage.md`
- `CALX394` — Réécrire la section « Calepinage » du guide utilisateur sur le parcours réel
- `CALX395` — Faire entrer le module dans la CODEMAP
- `CALX396` — Mettre les mots du métier solaire dans le lexique
- `CALX397` — Savoir quels onglets sont réellement ouverts
- `CALX398` — Re-mesurer le budget de poids du module après le lot
- `CALX399` — Figer la forme des agrégats du module dans `docs/api-contracts.md`
- `CALX400` — Geler les repères DOM `cal-*` en contrat
- `CALX401` — Porter au contrat l'allée de circulation tracée et sa largeur
- `CALX402` — Faire saisir par la société la largeur d'allée de circulation de chaque pays où elle…
- `CALX403` — Tracer une allée de circulation dans l'atelier et en retirer la surface posable
- `CALX404` — Refuser un rendement aller-retour de batterie supposé parfait
- `CALX405` — Poser un châssis incliné sous un seuil de pente saisi par la société
- `CALX406` — Nommer le responsable d'un calepinage et n'ouvrir à chacun que les siens
- `QJR500` — Contrat d'abord : un devis dit s'il est modifiable et révisable ; la ligne devis du…
- `QJR501` — Contrat d'abord : la proposition publique dit qu'elle est remplacée et porte le texte…
- `QJR502` — Contrat d'abord : aperçu WhatsApp multi-devis du lead, sans aucun effet
- `QJR503` — Contrat d'abord : verrou optimiste d'édition
- `QJR504` — Contrat d'abord : enregistrer une édition en UNE transaction (replace-lines + en-tête +…
- `QJR505` — Contrat d'abord : dérive lead → devis, « reprendre » ou « garder »
- `QJR506` — Contrat d'abord : ville effective, écart de la fiche client, champs de provenance du…
- `QJR507` — Contrat d'abord : le registre D12 marque les chemins que le moteur ne lit pas
- `QJR508` — Contrat d'abord : modèle de devis complet
- `QJR509` — Contrat d'abord : la règle « devis automatique prêt » servie structurée
- `QJR510` — Contrat d'abord : bloc ECRAN de l'étude industrielle/commerciale avec kWc de base et…
- `QJR511` — Contrat d'abord : dry-run de composition par lead au lieu d'une ville libre
- `QJR512` — Contrat d'abord : questionnaire public — colonnes écrites et pré-remplissage vu
- `QJR513` — Contrat d'abord : historique de configuration d'un devis (versions, différences…
- `QJR514` — Contrat d'abord : la liste « mes devis » du portail client dit quand le document a été…
- `QJR515` — Enregistrer l'Édition complète ne rétrograde jamais un devis envoyé en brouillon
- `QJR516` — Un seul prédicat de modifiabilité par geste, servi au front, et le verrou d'un devis…
- `QJR517` — L'écrivain unique remplacer_lignes persiste groupe_index / groupe_label : le mode «…
- `QJR518` — Une correction après envoi est tracée à UN seul point d'appel : instantané de l'état vu…
- `QJR519` — Un email de devis en échec ne marque plus le devis envoyé
- `QJR520` — Une version remplacée ne peut plus être signée, relancée, expirée ni listée au portail
- `QJR521` — « Réviser » passe par un service de domaine verrouillé : une seule V+1, jamais de…
- `QJR522` — Le PDF n'imprime plus une planche de calepinage périmée après une correction
- `QJR523` — Un seul couple de mappeurs lignes serveur ⇄ écran (lignesEcran.js), role_devis compris
- `QJR524` — Rouvrir un devis restaure l'option recommandée enregistrée : un ré-enregistrement sans…
- `QJR525` — L'Édition complète ouverte depuis la fiche lead ne ré-applique plus le lead sur le…
- `QJR526` — La réouverture re-dérive des lignes le wattage panneau, la structure, le hors-réseau et…
- `QJR527` — L'Édition complète charge les réglages société et relit le prix cible du devis
- `QJR528` — La part diurne d'un devis industriel est persistée (etude_params.part_diurne_pct) et…
- `QJR529` — La remise par ligne stockée fait l'aller-retour, compte dans les totaux de l'écran et…
- `QJR530` — Rouvrir un devis multi-villas restaure le mode « villas » et ses groupes
- `QJR531` — « Copier le lien de la proposition » depuis la liste marque le devis envoyé, comme…
- `QJR532` — Un devis envoyé s'ouvre et se corrige sur place dans l'Édition complète et depuis la…
- `QJR533` — « Réviser » depuis la liste dit ce qui se passe et ouvre la V2 en Édition complète
- `QJR534` — Cockpit lead : chaque carte devis propose « Modifier » (brouillon/envoyé) ou « Réviser…
- `QJR535` — Cockpit lead : une version remplacée est signalée « Remplacé par … » et ne peut plus…
- `QJR536` — Le lien public d'une version remplacée s'affiche « remplacée », sans signature, et mène…
- `QJR537` — La bande publique « Autres versions de ce devis » ne montre plus les brouillons
- `QJR538` — WhatsApp multi-devis de la fiche lead : l'aperçu n'écrit plus rien, seul « Ouvrir…
- `QJR539` — Garde de remise T17 appliquée à tous les vrais envois AVANT tout effet de bord et à la…
- `QJR540` — Bascule : les blocs livrés du modal mort DevisForm montent dans l'Édition complète, et…
- `QJR541` — Statut et champs de cycle de vie du devis en lecture seule au PATCH/POST : plus de…
- `QJR542` — La projection « étude du marché → clés etude_params légales » vit dans UNE fonction…
- `QJR543` — Le « Devis automatique » agricole / industriel / commercial se crée en UN appel…
- `QJR544` — Enregistrer une édition (en-tête + lignes + choix d'écran + échéancier) = UNE…
- `QJR545` — Verrou optimiste serveur : 409 si le devis ou ses lignes ont bougé depuis l'ouverture…
- `QJR546` — Appliquer un modèle de devis remplace les lignes À L'ÉCRAN dans les deux modes ; POST…
- `QJR547` — Un modèle enregistré reprend exactement le devis à l'écran, sans copier l'étude du…
- `QJR548` — Appliquer une taille d'offre recharge l'écran depuis le devis recomposé ; le bouton dit…
- `QJR549` — Édition complète : le générateur envoie le jeton de fraîcheur, le ré-arme après chaque…
- `QJR550` — Historique de configuration : UN instantané par geste d'enregistrement, avec son…
- `QJR551` — Historique : lignes appariées par une identité stable, instantané complet (lignes…
- `QJR552` — Historique d'un envoyé : la capture « avant correction » posée par QJR518 est…
- `QJR553` — L'historique de configuration est visible dans l'Édition complète (versions +…
- `QJR554` — Enregistrer en Édition complète remet à jour le cache kWc et la marge interne (mode…
- `QJR555` — Une seule définition du « prix négocié » : prix_manuel protège une ligne du recalage…
- `QJR556` — La resynchro calepinage lit le scénario du layout par son propriétaire unique et ne…
- `QJR557` — Sur un devis envoyé, le calepinage 3D et « appliquer une taille d'offre » se corrigent…
- `QJR558` — Une révision garde le travail manuel : conception toiture 3D, registre D12, tailles…
- `QJR559` — Accepter la V2 d'un devis signé réutilise son chantier et son contrat d'entretien, sans…
- `QJR560` — V2 d'un devis signé acceptée : BC et factures de la V1 restent valables et passent à la…
- `QJR561` — Le suivi après-devis passe sur la révision envoyée au lieu de rester accroché à la…
- `QJR562` — La création d'une gamme sœur est atomique : jamais de brouillon orphelin sans lignes
- `QJR563` — La création atomique applique la même devise par défaut de la société que POST /devis/…
- `QJR564` — Poser ou régénérer une surcharge relance les études stockées du devis
- `QJR565` — Le portail client dit « Document mis à jour le … » sur un devis corrigé après envoi
- `QJR566` — Cockpit lead : « lu le … » ne ment plus après une correction
- `QJR567` — Le total du rail, le prix/kWc, la marge et l'étude C&I excluent les lignes optionnelles…
- `QJR568` — Prix/kWc, prix cible et étude C&I utilisent le kWc réellement facturé par les lignes …
- `QJR569` — Une quantité tapée pose le verrou quantiteManuelle, visible et réversible sur la ligne
- `QJR570` — Recomposer FUSIONNE : prix tapés et lignes ajoutées à la main conservés d'office, seuls…
- `QJR571` — Le registre DIT quels chemins le moteur ne lit pas (non_lu) : la réponse, l'écran et la…
- `QJR572` — Scénario, option recommandée et nombre de panneaux de l'écran suivent le registre : une…
- `QJR573` — Aucune surcharge acceptée n'est ignorée : chaque chemin D12 non lu est câblé ou retiré…
- `QJR574` — Le panneau brut « Surcharges (registre) » est réservé aux administrateurs (D-QJR5-8)
- `QJR575` — Devis C&I : l'Édition complète recalcule avec les MÊMES paramètres que « Devis…
- `QJR576` — Une seule conversion panneaux ↔ kWc (kwcPourPanneaux + PANEL_W_DEFAUT) et un seul…
- `QJR577` — Résidentiel : serveur injoignable → erreur + « Réessayer » ; la composition JS de repli…
- `QJR578` — Le schéma d'étude porte etude_kwc_base : le kWc pour lequel l'écran a calculé l'étude…
- `QJR579` — Le générateur enregistre, avec l'étude industrielle/commerciale, le kWc pour lequel il…
- `QJR580` — En Édition complète, le lead et le client du devis sont en lecture seule (« changer de…
- `QJR581` — Ouvrir un devis sans rien changer ne crée plus de « brouillon non enregistré » ; un…
- `QJR582` — En industriel/commercial, la facture réelle « recommandée » alimente l'étude et la…
- `QJR583` — Corriger la ville d'un lead efface sa ville de rattachement périmée (et le chatter le…
- `QJR584` — Corriger le téléphone d'un lead fait suivre son WhatsApp quand il n'en était qu'une…
- `QJR585` — Un seul résolveur « quel lead lit ce devis » : crm.selectors.lead_du_devis(devis)
- `QJR586` — Une seule « ville de calcul » : crm.selectors.ville_effective(lead) alimente moteur…
- `QJR587` — L'estampille de provenance couvre les valeurs du lead qui pilotent le devis (taille…
- `QJR588` — La dérive lead → devis se résout : « reprendre les valeurs du lead » ou « garder celles…
- `QJR589` — Une bannière de dérive à deux boutons dans l'Édition complète ET dans la fenêtre devis…
- `QJR590` — Corriger le nom, le téléphone, l'e-mail ou l'adresse d'un lead met à jour la fiche…
- `QJR591` — Le PDF garde la ville sur laquelle le devis a été chiffré et l'affiche « X, près de Y »
- `QJR592` — Le questionnaire ne redemande plus au client pro la consommation mensuelle déjà saisie…
- `QJR593` — La structure choisie à la création d'un lead (structure_produit) est enregistrée…
- `QJR594` — À l'entrée d'un lead (site, questionnaire), l'e-mail invalide est écarté et le…
- `QJR595` — La puissance souscrite (kVA) et la surface de toiture données par un client pro sur le…
- `QJR596` — Le questionnaire public ne promet plus que les colonnes que la page sait poser (les…
- `QJR597` — Une réponse du questionnaire restée au pré-remplissage n'écrase plus une valeur…
- `QJR598` — Un seul repère toit du lead : le GPS corrigé prime sur l'épingle du site partout ; hors…
- `QJR599` — Le cockpit lead propose toujours « Nouveau devis (édition complète) », même quand le…
- `QJR600` — CRM : la règle « devis automatique prêt » est SERVIE structurée (champ + libellé +…
- `QJR601` — CRM (écran) : la section Énergie et les puces « manquant » lisent la règle servie
- `QJR602` — Une taille EXPLICITE est respectée telle quelle partout — plus d'arrondi au palier de 5…
- `QJR603` — Lead pro « kWh seulement » : le devis automatique se dimensionne depuis ces kWh…
- `QJR604` — Le barème transport par ville est appliqué DANS l'étape composer du pipeline pour…
- `QJR605` — Cartes Éco / Recommandé / Max, échelle de paliers batterie et balayage de tailles…
- `QJR606` — recommander_taille reçoit partout les mêmes entrées du devis (gamme et phase dans…
- `QJR607` — Le scénario stocké et option_avec_servable dérivent de utils/options.familles_servables…
- `QJR608` — Deux wattages de repli NOMMÉS, un propriétaire chacun (layout 550 / catalogue 710), et…
- `QJR609` — Garde PDF « cet optimum décrit votre devis » : capacité UTILE contre UTILE, comme la…
- `QJR610` — Le moteur PDF lit l'option recommandée par domain.scenario.recommended_option_effective…
- `QJR611` — Production journalière par saison : une seule boucle, etude_horaire délègue
- `QJR612` — CAD170 réellement appliqué : la batterie retenue couvre la recharge VE nocturne, sur…
- `QJR613` — Un seul formateur monétaire au centime ROUND_HALF_UP dans le moteur : _fmt2 déménage…
- `QJR614` — Les PDF premium résidentiel / commercial / industriel impriment les montants au…
- `QJR615` — La page équipements du PDF commercial imprime P.U
- `QJR616` — Le prix d'une option proposée imprimé au client est le supplément CANONIQUE qu'elle…
- `QJR617` — L'intercalage sections / notes ↔ lignes produit devient UNE fonction pure…
- `QJR618` — Le PDF premium résidentiel (format par défaut) imprime les intertitres de section, les…
- `QJR619` — Le PDF commercial premium et la page 2 du format legacy complet impriment sections…
- `QJR620` — Le PDF industriel premium passe à 4 pages : couverture, équipements + chaîne de totaux…
- `QJR621` — Un devis commercial demandé « avec l'étude » sort en 4 pages avec la page d'étude
- `QJR622` — La correspondance « échéancier du devis → acompte / matériel / solde » vit dans…
- `QJR623` — Le PDF imprime l'échéancier RÉEL du devis et les cases du Devis final au centime —…
- `QJR624` — L'échéancier est éditable dans l'Édition complète ; l'« acompte personnalisé » du…
- `QJR625` — Les PDF industriel / commercial n'impriment plus un taux d'autoconsommation, une…
- `QJR626` — La mention TVA du PDF décrit les taux RÉELLEMENT portés par les lignes
- `QJR627` — Le champ « Notes » du générateur est un texte CLIENT, imprimé sur le PDF et la…
- `QJR628` — Le PDF dit quand un devis a été corrigé après envoi et quel devis une révision remplace
- `QJR629` — Moteur PDF : retirer le script démo embarqué (données personnelles du fondateur…
- `QJR630` — Moteur PDF : supprimer la chaîne de financement morte à taux bancaires inventés
- `QJR631` — [WEB] Un lead du site n'est plus perdu sur une panne passagère du CRM : forwardLead…
- `QJR632` — [WEB] La page questionnaire demande la consommation mensuelle (kWh) ; une garde de…
- `QJR633` — [WEB] La page questionnaire renvoie le pré-remplissage qu'elle a affiché (prefill_vu)…
- `QJR634` — [WEB] Page /proposition : retirer backendFinancing, loanMonthlyPayment et…
- `QJR635` — Un seul constructeur de lien WhatsApp, qui normalise le numéro (06… → 2126…)
- `QJR636` — Choix du devis à calepiner : un filtre serveur ?concevable=1 lu dans la table de…
- `QJR637` — Générateur : le bloc étude réseau (conso, injection 82-21, BT/MT, bloc MT) extrait en…
- `QJR638` — Cockpit lead : enumOptions et le collage de carte de visite ont chacun une seule…
- `QJR639` — Un devis accepté ne peut plus être supprimé définitivement (sa signature électronique…
- `QJR640` — Retirer de ventesApi les 7 méthodes sans aucun appelant
- `QJR641` — Le sélecteur « Type d'installation » disparaît : le Marché est la seule source, et le…
- `QJR642` — Écran : un seul noyau de totaux et de remise (remise.js) pour le générateur et la…
- `QJR643` — Calculateur (écran) : supprimer le hook useComposition mort et les exports sans…
- `QJR644` — Aperçu étude horaire : une seule temporisation de 500 ms
- `QJR645` — Façade ventes/services.py : retirer les alias PRIVÉS sans importeur de production et…
- `QJR646` — Retirer deux fonctions backend sans appelant : crm.log_whatsapp_message_on_lead et…
- `QJR647` — Supprimer le troisième stockage de géométrie de toit ventes.RoofLayout…
- `QJR648` — POST /devis/{id}/lots/ : une entrée invalide répond 400 et ne laisse jamais de lot…
- `QJR649` — DevisViewSet.get_permissions réduit à sa vraie table, avec une matrice (action, rôle)…
- `QJR650` — Vues ventes : supprimer _resolve_accepted_option (mort) et les imports `# noqa: F401`…
- `QJR651` — Moteur premium : un seul harnais de rendu industriel / commercial et un seul _kwc_str
- `QJR652` — Téléchargements du panneau devis du lead et du RDV .ics : le helper partagé (chemin iOS…
- `QJR653` — Aperçu PDF du panneau devis du lead : le même moteur d'aperçu que PdfPreviewSheet, sans…
- `QJR654` — Libellés de statut devis : une seule table dans features/ventes/devisStatuts.js…
- `QJR655` — Portée société des vues ventes : une seule règle company_qs dans core, les 8 copies de…
- `QJR656` — Bannière « valeurs du lead modifiées » : libellés courts dans fieldLabels.js, et un…
- `QJR657` — Le « Type de toiture (site) » fabriqué (« autre » pour tout visiteur résidentiel) n'est…
- `QJR658` — Édition complète : un module pur etatDevis.js (devis ⇄ état d'écran) avec un vrai test…
- `QJR659` — [DÉCIDÉ fondateur 01/10/2026 : oui, partager le PDF vaut envoi (feuille résolue)] La…
- `QJR660` — [DÉCIDÉ fondateur 01/10/2026 : cadence d'origine gardée ; paire « répondez oui / non »…
- `QJR661` — [DÉCIDÉ fondateur 01/10/2026 : archivage seul ; seul un brouillon se supprime]…
- `QJR662` — [DÉCIDÉ fondateur 01/10/2026 : oui, repli en lecture seule sur le kWh déclaré…
- `QJR663` — [DÉCIDÉ fondateur 01/10/2026 : oui, KV avec expiration (liaison LEADS_DLQ à créer au…
- `QJR664` — [DÉCIDÉ fondateur 01/10/2026 : montrer le graphe en FR, EN et AR] [WEB] Le graphe « Une…
- `QJR665` — [DÉCIDÉ fondateur 01/10/2026 : même barème national que le balayage] Étude C&I …
- `QJR666` — [DÉCIDÉ fondateur 01/10/2026 : pages ajoutées au gabarit premium résidentiel] Les choix…
- `QJR667` — [DÉCIDÉ fondateur 01/10/2026 : construire les écrans (contrat d'abord)] Endpoints devis…
- `QJR668` — [DÉCIDÉ fondateur 01/10/2026 : brancher : gel à l'envoi, re-gel à chaque correction…
- `QJR669` — [DÉCIDÉ fondateur 01/10/2026 : suit le devis corrigé et envoyé] Sémantique de…
- `QJR670` — Le PDF public d'un devis ACCEPTÉ sert l'exemplaire SIGNÉ figé, plus un re-rendu en…

**Open — to build (419)**

- `AGR121` — Aperçu serveur `POST /ventes/etude-pompage/preview/` : un orchestrateur ventes, le…
- `AGR122` — Clés `etude_params` pompage v2 déclarées au schéma, propriétaire `moteur_pompage`
- `AGR123` — Rafraîchisseur d'étude pompage : l'étude suit la pompe FACTURÉE, à chaque écriture de…
- `AGR124` — Devis automatique agricole par le serveur (bouton « Devis automatique »)
- `AGR125` — Calepinage : même calcul de production et de HMT que le devis (fin du second volume)
- `AGR126` — Écran : le devis automatique agricole appelle le serveur et montre ses alertes
- `AGR127` — Hook d'aperçu pompage (debouncé, annulable, jamais périmé)
- `AGR128` — Générateur agricole : saisir le besoin, le point d'eau, la HMT détaillée et le cas de…
- `AGR129` — Générateur agricole : le résultat serveur en direct — pompe, chaînes, 12 mois…
- `AGR130` — Générateur agricole : Auto-remplir, enregistrer et rouvrir passent par le serveur …
- `AGR131` — Supprimer le jumeau JS du besoin en eau (`agronomy.js`)
- `AGR132` — Supprimer le moteur pompage JS de `solar.js` et ses axes de parité
- `AGR134` — Marge indicative : dire quand elle est partielle
- `AGR135` — [GATED: founder data] Nom et diamètre réels des pompes OSP 30
- `AGR136` — Guide Meryem « Devis pompage en 10 gestes » dans la GED, régénéré par script
- `AGR206` — Brancher le moteur : lecture du devis, deux endpoints, clé d'étude déclarée, lecture…
- `AGR212` — Générateur, panneau agricole : saisir la consommation DÉCLARÉE, le prix payé daté, les…
- `AGR213` — Générateur : carte « Économie déclarée » en direct, servie par le serveur (le JS ne…
- `AGR214` — Générateur : volet INTERNE de la carte économie (VAN, scénario butane non subventionné…
- `AGR216` — Capacité TVA : un taux de 0 % saisi reste 0 % à l'écran (aujourd'hui il redevient 20 %)
- `AGR217` — Capacité TVA : chaque ligne exonérée porte sa base légale, la note multi-taux {0, 10…
- `AGR218` — Générateur : saisir la base légale d'une ligne à 0 % et cocher l'attestation d'usage…
- `AGR219` — Échéancier agricole : 30/60/10 conservé, date de solde « après récolte » saisissable
- `AGR220` — Générateur : saisir la date de solde « après récolte » dans la carte Échéancier
- `AGR222` — Aller-retour EN DIRECT du parcours économie agricole (pile locale, Playwright)
- `AGR223` — Réviser V2, dupliquer, variante, renouveler : un devis agricole recopie ses ENTRÉES…
- `AGR306` — Textes réglementaires du devis agricole : la règle de l'aide FDA (sans montant) et les…
- `AGR307` — Bloc « argent » du devis agricole : il lit le bloc `economie_pompage` (AGR3) tel quel…
- `AGR308` — `proposal_data` sert `synthese_agricole` — la même fonction que le PDF, prouvée par un…
- `AGR310` — Renderer agricole de 3 pages dans `quote_engine/agricole/` (P1 eau et argent, P2…
- `AGR311` — Clôture de la page 3 agricole alignée sur le canon v6 : « Bon pour accord », options du…
- `AGR312` — Brancher le renderer agricole au registre et retirer la dégradation « full → une page »…
- `AGR313` — Le une-page agricole (version courte) lit `synthese_agricole` : mêmes chiffres que le 3…
- `AGR314` — Document agricole de 3 pages en arabe et en anglais : libellés tirés du catalogue…
- `AGR315` — Dialogue PDF : le format complet d'un devis agricole annonce le vrai document (3 pages…
- `AGR316` — Écran du générateur : le texte « aucune promesse de chiffre dans le PDF » est remplacé…
- `AGR317` — Garde de vocabulaire du devis agricole : jamais « eau gratuite », « à vie », « illimité…
- `AGR318` — Clôture de vague : aller-retour EN DIRECT d'un devis agricole (création → PDF 3 pages →…
- `AGR319` — Annexe « Note de calcul du kit de pompage » (pièce du dossier FDA) rendue par le…
- `AGR405` — Drapeau d'incohérence segment lead ↔ devis (D-AGR-9, jamais de changement automatique)
- `AGR406` — Segment SUGGÉRÉ depuis la page d'arrivée et les mots-clés, jamais écrit
- `AGR407` — Panneau d'appel agricole côté serveur : cinq étapes qui collectent ce qui dimensionne…
- `AGR415` — Fiche CRM : section Pompage complète, avec la question de l'appel sous chaque champ
- `AGR416` — Fiche d'un lead agricole : sections résidentielles repliées, et plus d'« économie » non…
- `AGR417` — Bandeaux de la fiche : incohérence de segment (D-AGR-9) et segment suggéré, changement…
- `AGR418` — Script d'appel agricole réécrit : énergie actuelle → source et niveau d'eau → besoin →…
- `AGR419` — Dialogue « Envoyer un questionnaire » : sections selon le segment, avec la section…
- `AGR420` — Générateur : pré-remplir le pompage depuis `entrees_pompage` du lead, sans recopier la…
- `AGR421` — Générateur : bandeau « devis agricole sur un lead non agricole », changement de type à…
- `AGR422` — Écrans de visite : saisie et revue du gabarit « relevé du point d'eau »
- `AGR423` — Aller-retour EN DIRECT du lead agricole : site → fiche → appel → visite du point d'eau…
- `AGR424` — Retirer l'alias déprécié `pompe_cv` du sérialiseur Lead/SiteProfile (fin de la scission…
- `AGR514` — J4 « preuve » omise quand aucune réalisation éligible n'existe (D-AGR-10)
- `AGR515` — Paramètres → Réalisations : choisir le segment d'une réalisation
- `AGR516` — Références de pompage proches : sélecteur + action du lead
- `AGR517` — Fiche lead agricole : la carte « Références de pompage proches »
- `AGR520` — Nouvelle réponse « En attente d'un accord (DPA / banque) » : date de rappel…
- `AGR521` — Motifs de perte « Subvention non obtenue » et « Eau insuffisante / forage »
- `AGR524` — Fiche lead : saisir l'état du dossier de subvention
- `AGR526` — API : la tâche du playbook propose son texte, et `message-visite` rend `dossier_fda`
- `AGR527` — Fiche lead : bouton « Proposer le texte » sur la tâche « dossier FDA »
- `AGR530` — D-AGR-4 côté cadence : suite par défaut = « Planifier la visite — relevé du point d'eau…
- `AGR531` — Le sérialiseur de touche sert `lead_segment`
- `AGR532` — Panneau « Proposer la visite » : consignes agricoles À CÔTÉ des textes du fondateur
- `AGR533` — Table du parcours : libellés agricoles « Décision à plusieurs — associés / coopérative…
- `AGR534` — Action « envoyer le résumé à un associé » (manuelle, avec l'accord du client)
- `AGR535` — Fiche lead : bouton « Envoyer le résumé à un associé » + étiquette suggérée
- `AGR536` — Fiche argumentaire interne : objections agricoles, sans aucun chiffre au téléphone
- `AGR540` — Mesure par segment (lecture seule) + commande de comptage CADM7 par segment
- `AGR541` — Écran Relances → mesures : le tableau « Par segment »
- `AGR542` — Cockpit « Contrôle du suivi » : filtre `segment`, appliqué aussi par l'oracle
- `AGR543` — Cockpit : sélecteur « Segment »
- `AGR545` — Aller-retour EN DIRECT du suivi d'un lead agricole (clôture de la vague, leçon QJR5)
- `AGR603` — Jumeau ventes du régime hors réseau : dossiers réglementaires et régularisation art
- `AGR604` — Écran chantier : régime hors réseau, raccordement au réseau, avertissement consultatif…
- `AGR609` — Recette pompage : comparaison mesurée au débit promis du devis, écart en % et…
- `AGR611` — PV de réception et dossier de remise pompage : mesures de la recette, cadre IEC 62253…
- `AGR612` — Portail client : la recette pompage de SON chantier (lecture seule)
- `AGR613` — Fiche chantier : saisir la recette pompage (au lieu de la fiche IEC) avec l'écart au…
- `AGR614` — Portail client « Chantiers » : afficher l'essai de mise en service de la pompe
- `AGR616` — Fiche équipement SAV : relevé en m³ et moyenne par jour
- `AGR617` — Monitoring pompage phase 1 sans dépendance payante : le client saisit heures et index…
- `AGR618` — Portail client « Chantiers » : formulaire « Relevés de ma pompe »
- `AGR624` — Aller-retour EN DIRECT du parcours chantier pompage (pile locale, Playwright)
- `AGRM1` — QXG3 étendu : prix des 11 OSP, courbes des pompes réellement vendues, une famille…
- `AGRM2` — kW de plaque et prix d'achat des 8 pompes génériques
- `AGRM3` — Fiches VEICHI : série exacte, plages de tension, fiches SI22
- `AGRM4` — Fiche constructeur OSP 30 : diamètre réel et source des courbes
- `AGRM5` — Prix des options du kit et des protections
- `AGRM6` — Réglages société du pompage
- `AGRM7` — Décider la variante hybride réseau / groupe
- `AGRM8` — Avis ÉCRIT du fiscaliste : TVA d'un kit de pompage solaire agricole
- `AGRM9` — Décision de prix après l'avis fiscal
- `AGRM10` — Saisir le barème des charges solaires de pompage
- `AGRM11` — Sourcer les repères énergie et les tenir à jour
- `AGRM12` — Règle FDA : récupérer l'édition 2026 du Guide FDA et mettre à jour la règle datée
- `AGRM13` — DPA / ORMVA : confirmer par écrit le processus FDA et l'approbation préalable
- `AGRM14` — Lire le décret 2.25.100 (loi 82-21) : déclaration hors réseau et régularisation art
- `AGRM15` — Collecter des montants terrain réels
- `AGRM16` — Conditions de financement écrites
- `AGRM17` — Décider la délégation de créance FDA
- `AGRM18` — Droits de douane 2026 sur modules, pompes et variateurs
- `AGRM19` — Clause « travaux après approbation FDA » dans le bon de commande agricole
- `AGRM20` — Juriste : la loi 31-08 (rétractation) s'applique-t-elle à un achat de pompage pour…
- `AGRM21` — E-mail de contact canonique (.ma ou .com) et fiche société
- `AGRM22` — Garanties ÉCRITES des fournisseurs de pompage et garantie de pose
- `AGRM23` — Relecture native de la darija et de l'arabe pompage (après livraison, sans bloquer…
- `AGRM24` — Engagement de mesure à la réception
- `AGRM25` — Seuil d'écart de recette pompage
- `AGRM26` — Échéancier agricole 30/60/10 : garder et mesurer
- `AGRM27` — Facteur CO₂ du réseau (autres marchés) : source datée ou masquage
- `AGRM28` — Qui porte la déclaration 82-21 d'une installation hors réseau ?
- `AGRM29` — Mémoire Claude : retirer un défaut obsolète du PDF agricole
- `AGRM30` — Confirmer (ou non) « dossier FDA accompagné par nos soins »
- `AGRM31` — Créer le formulaire Meta agricole FORM-AGRI-1 (campagne PAUSED)
- `AGRM32` — Requalifier à la main les leads pompage mal typés
- `AGRM33` — Qui relève le niveau et le débit en visite, avec quel matériel
- `AGRM34` — Mesure par segment en production : maintenant, puis fin mars 2027
- `AGRM35` — Valider les nouveaux textes FR (✎)
- `AGRM36` — Saisir la première réalisation de pompage réelle
- `AGRM37` — Motif de refus de devis obligatoire ?
- `AGRM38` — Part de commission liée à l'absence de ticket SAV à J+90
- `AGRM39` — Prix et barèmes des SKU pompage semés « prix à renseigner »
- `AGRM40` — Saison d'irrigation pour le stock
- `AGRM41` — Engagement SAV affichable
- `AGRM42` — Assurance vol des panneaux
- `AGRM43` — Consignes de remise au fermier (FR + darija)
- `AUD504` — [GATED: coût prestataire — décision fondateur] Intégration signature QUALIFIÉE DGSSI en…
- `CAD177` — (30/09 : nocturne encore rouge — backend-full sur 3 tests PDF ventes réels ; e2e…
- `CADM1` — Relecture darija par un locuteur natif
- `CADM2` — Déclaration CNDP du fichier prospects CRM + récépissé
- `CADM3` — Question à un juriste : loi 31-08, démarchage à domicile
- `CADM4` — Décision RH : travaille-t-on le soir pendant le Ramadan ?
- `CADM5` — Saisie annuelle : dates du Ramadan + 4 fêtes mobiles
- `CADM6` — Lancer le semis des 9 fériés fixes sur la société TAQINOR
- `CADM7` — Lecture SQL de production : les ~10 comptages qui manquent aux deux rondes
- `CADM8` — Relever quatre valeurs d'environnement en production
- `CADM9` — Re-vérifier neuf affirmations de marché avant tout usage client
- `CIQ101` — Produit C&I : `role_ci`, `type_pose`, délai d'appro et fiches limiteur / logger /…
- `CIQ102` — Une seule lecture serveur du catalogue C&I : `stock.selectors.produits_ci`
- `CIQ103` — Articles C&I « prix à renseigner » + rôle C&I des articles existants
- `CIQ104` — Fiche produit : saisir le rôle C&I, le type de pose et les fiches limiteur / logger /…
- `CIQ105` — Réglages société C&I sans défaut : forfaits de prestations C&I et bande interne de…
- `CIQ106` — Paramètres › Devis : saisir les forfaits de prestations C&I et la bande prix/kWc…
- `CIQ107` — Profils de charge de repli : archétypes SOURCÉS seulement (BDEW, NREL ComStock)…
- `CIQ108` — Courbe de charge DÉCLARÉE en jours types (12 mois × types de jour × 24 h) : calendrier…
- `CIQ109` — Production horaire du site par la MÊME chaîne PVGIS que le résidentiel (fin du GHI ×…
- `CIQ110` — Autoconsommation HEURE PAR HEURE et régime d'injection selon la tension (aucun taux…
- `CIQ111` — Combinaison d'onduleurs au coût minimal sous contraintes de fiche (fin du plafond de…
- `CIQ112` — Calepinage : mode de pose « bac acier » lu par la règle de pose (un bac acier peu pentu…
- `CIQ113` — Contenance estimée d'une surface DÉCLARÉE par le vrai moteur de calepinage (aucune…
- `CIQ114` — Charge de toiture : la capacité admissible est DÉCLARÉE (propriétaire, bureau de…
- `CIQ115` — Composition C&I serveur (BOQ) : chaînes, protections et câbles dimensionnés, structure…
- `CIQ116` — Taille C&I = la plus grande dont chaque tranche de 5 kWc se rembourse encore en ≤…
- `CIQ117` — Clés `etude_params` C&I v2 déclarées au schéma, propriétaire `moteur_ci` ; le…
- `CIQ118` — Aperçu serveur `POST /ventes/etude-ci/preview/` : un orchestrateur ventes, le noyau…
- `CIQ119` — Rafraîchisseur d'étude C&I : l'étude suit les LIGNES facturées, à chaque écriture de…
- `CIQ120` — Devis automatique commercial/industriel par le serveur (bouton « Devis automatique »)
- `CIQ121` — Étude bancable d'un devis C&I : courbe de charge du moteur C&I, aucune économie de…
- `CIQ122` — Cas de référence C&I en tests de non-régression (comportement, pas parité)
- `CIQ123` — Gros volumes : prix de vente par palier de quantité (saisi) et disponibilité « sur…
- `CIQ124` — Hook d'aperçu C&I (debouncé, annulable, jamais périmé)
- `CIQ125` — Générateur C&I : UN bloc « profil déclaré » (consommation, calendrier, toit…
- `CIQ126` — Générateur C&I : Auto-remplir, enregistrer et rouvrir passent par le serveur ; le…
- `CIQ127` — Devis automatique C&I depuis la fiche lead : un seul appel serveur ; la branche C&I de…
- `CIQ128` — Supprimer le moteur C&I JS de `solar.js` (aucun second moteur)
- `CIQ129` — Retirer du schéma les clés ÉCRAN C&I v1 et les réponses de catégorie plates (D-CIQ-21 …
- `CIQ130` — Commercial : les réponses de catégorie deviennent des éléments d'HORAIRE déclarés…
- `CIQ131` — Générateur commercial : catégorie, réponses et heures transmises au moteur ; archétype…
- `CIQ132` — Industriel MT : la courbe de charge se construit depuis les registres de la facture…
- `CIQ133` — Industriel et grands sites : une courbe de charge MESURÉE (export du compteur, journal…
- `CIQ134` — Industriel MT : alerte INTERNE de facteur de puissance après PV (jamais un chiffre…
- `CIQ135` — Générateur industriel : équipes, registres MT, puissance souscrite, réactif déclaré et…
- `CIQ136` — Calepinage C&I : contraintes de site saisies PAR PROJET (assureur, sécurité incendie)…
- `CIQ137` — Calepinage C&I : découpage automatique du champ en îlots bornés avec allées coupe-feu…
- `CIQ138` — Atelier de calepinage : saisir les contraintes de site du projet (assureur…
- `CIQ139` — Barèmes électriques étendus aux puissances C&I : sections de câble au-delà de 25 mm² et…
- `CIQ141` — L'orchestrateur C&I lit le relevé de visite VALIDÉ : longueurs DC/AC, zones de toiture…
- `CIQ201` — Constantes 82-21 SOURCÉES (D-CIQ-4) : tarif d'excédent ANRE 04/26 brut HT, plafond…
- `CIQ202` — Grille officielle ONEE sourcée dans UN module de fondation…
- `CIQ203` — `ventes/tarif_ci.py` : le tarif du client résolu — facture déclarée d'abord, grille…
- `CIQ204` — Moteur `economie_ci` (1/6) : économies = facture d'énergie AVANT − APRÈS, heure par…
- `CIQ205` — Moteur `economie_ci` (2/6) : base HT si la TVA est récupérable, TTC sinon, les deux…
- `CIQ206` — Moteur `economie_ci` (3/6) : UN flux 25 ans par `economie.flux_de_tresorerie`, jalons…
- `CIQ207` — Moteur `economie_ci` (4/6) : revente 82-21 du surplus HORAIRE, MT/HT seulement, au…
- `CIQ208` — Moteur `economie_ci` (5/6) : financement construit UNIQUEMENT depuis l'offre ÉCRITE…
- `CIQ209` — Moteur `economie_ci` (6/6) : vue INTERNE de comparaison face à une offre CSE/PPA…
- `CIQ210` — Brancher `economie_ci` : aperçu et lecture serveur, et le moteur de devis sert CE bloc…
- `CIQ211` — Réglages société C&I, sans valeur par défaut : scénarios de sensibilité saisis par Reda…
- `CIQ212` — Échéancier C&I à N jalons (D-CIQ-13) : commercial 40/50/10, industriel 30/40/20/10…
- `CIQ213` — Variante « règlement par l'organisme financeur à la réception signée » : un payeur…
- `CIQ214` — Retenue de garantie SEULEMENT à la demande du client, libérée à la réception définitive…
- `CIQ215` — Facture de tranche : la TVA ventilée par taux (base 10 % / TVA 10 % / base 20 % / TVA…
- `CIQ216` — Référence de commande du client portée par le devis, héritée par la facture de BC et…
- `CIQ217` — Facture d'un client entreprise : raison sociale, ICE, IF et RC imprimés, et émission…
- `CIQ218` — Conditions générales C&I par mode (commercial, industriel) : texte de la société relu…
- `CIQ219` — Réviser V2, dupliquer, variante, variante-gamme, renouveler : un devis C&I recopie ses…
- `CIQ220` — [GATED: critères écrits de l'opérateur SR500 — manuel] Indicateur INTERNE de…
- `CIQ221` — [GATED: phrase et accord écrits de l'opérateur SR500 — manuel] Phrase client SR500 dans…
- `CIQ222` — Générateur C&I : saisir le tarif de SA facture (MT : 3 postes, prime fixe, puissance…
- `CIQ223` — Générateur C&I : la carte « Économies » est servie par le serveur (`economie_ci`), sans…
- `CIQ224` — Générateur C&I, volet INTERNE : saisir l'offre écrite de financement et l'offre CSE…
- `CIQ225` — Échéancier à N jalons à l'écran : Paramètres → Devis par mode, et carte Échéancier du…
- `CIQ226` — Générateur et facture : retenue de garantie, pénalités et caution déclarées, échéancier…
- `CIQ227` — Paramètres → Tarification & ROI : saisir les scénarios de sensibilité C&I avec leur…
- `CIQ228` — Supprimer le jumeau JS de la valorisation C&I (prix plats, tarif MT moyen, injection…
- `CIQ229` — Inversion facture → kWh et facture simulée de la classe « force motrice » (atelier…
- `CIQ231` — Sensibilités industrielles calculées sur les SEULES valeurs saisies par Reda (D-CIQ-10…
- `CIQ233` — Vue INTERNE après impôt d'un industriel, seulement sur le taux d'IS et l'amortissement…
- `CIQ300` — Garde serveur : plus aucune économie résidentielle, BT ou JS sur la proposition en…
- `CIQ301` — Garde PDF : les gabarits commercial et industriel ne reprennent plus jamais le chiffre…
- `CIQ302` — Devis C&I à deux options : l'offre réseau seule est l'offre principale ; la batterie…
- `CIQ303` — `synthese_ci(data)` (1/2) : UNE fonction serveur pure qui dit le système, l'énergie, la…
- `CIQ304` — `synthese_ci(data)` (2/2) : le bloc argent recopie `economie_ci` tel quel — base HT ou…
- `CIQ305` — Mentions et hypothèses C&I : une table unique, sourcée et trilingue, servie au PDF et à…
- `CIQ306` — `proposal_data` sert `synthese_ci` — la même fonction que le PDF, prouvée par un test…
- `CIQ307` — Les gabarits commercial et industriel lisent `synthese_ci` : une seule source pour la…
- `CIQ308` — Proposition C&I : les blocs du moteur horaire RÉSIDENTIEL (courbe du jour, jours types…
- `CIQ309` — Bloc client entreprise sur les PDF C&I : raison sociale, ICE, RC, IF, interlocuteur et…
- `CIQ310` — Bande légale du vendeur (RC, ICE, capital) sur la dernière page des PDF C&I, par UNE…
- `CIQ311` — Bloc « Conditions » des PDF C&I : CGV gelées à l'envoi, mention TVA et « Bon pour…
- `CIQ313` — Paramètres › Documents : saisir les CGV commerciales et industrielles à côté des CGV…
- `CIQ314` — O&M, suivi de production et garanties : le document ne promet que ce que le devis porte
- `CIQ315` — Chiffres phares en HT pour une entreprise qui récupère la TVA, TTC sinon ; la chaîne HT…
- `CIQ316` — Options proposées en HT, avec leur taux de TVA, comme le reste du tableau
- `CIQ317` — Page équipements C&I : une longue nomenclature n'est jamais coupée en silence
- `CIQ318` — Bloc « Offre de financement » facultatif, construit seulement depuis l'offre écrite…
- `CIQ319` — Acceptation entreprise côté serveur : raison sociale, qualité du signataire et ICE…
- `CIQ320` — « Bon pour accord — pour la société » avec une case « Cachet » sur les PDF C&I, remplie…
- `CIQ321` — Portail client : l'acceptation d'un devis C&I demande aussi la raison sociale, la…
- `CIQ322` — Portail client : le formulaire de signature d'un devis C&I demande la raison sociale…
- `CIQ323` — Acceptation saisie dans l'ERP (devis papier signé) : l'action `accepter` enregistre…
- `CIQ324` — Dialogues d'acceptation de l'ERP : trois champs facultatifs pour un C&I (raison…
- `CIQ325` — Dialogue PDF : un devis commercial annonce 3 pages, un industriel 4 pages, et aucune…
- `CIQ327` — Aucune annexe de rétractation « signé à domicile » (loi 31-08) sur un devis commercial…
- `CIQ330` — Contenu par catégorie commerciale : UNE table trilingue (réponses du questionnaire →…
- `CIQ331` — PDF commercial : 3 pages complétées du retour sur investissement, de la production…
- `CIQ332` — Commercial : « Inclure l'étude » ne renvoie plus au moteur legacy ; le document reste…
- `CIQ333` — PDF commercial en arabe et en anglais : libellés structurels par `i18n_labels`, mise en…
- `CIQ334` — Clôture de la vague commerciale : aller-retour EN DIRECT d'un devis commercial…
- `CIQ340` — Industriel : le document est TOUJOURS le premium 4 pages, étude intégrée — plus de…
- `CIQ341` — Couverture industrielle : une synthèse de direction à transmettre, une baseline…
- `CIQ342` — Page finance industrielle (1/2) : 25 ans, jalons 5/10/15/20/25, TRI avec son horizon et…
- `CIQ343` — Page finance industrielle (2/2) : coût du kWh solaire face au tarif du client, VAN sur…
- `CIQ344` — Page 4 industrielle : 4 jalons de paiement, une phrase de décarbonation conditionnelle…
- `CIQ345` — PDF industriel de 4 pages en arabe et en anglais
- `CIQ346` — Clôture de la vague industrielle : aller-retour EN DIRECT d'un devis industriel MT…
- `CIQ401` — Colonnes pro du Lead, chacune avec sa question d'appel
- `CIQ402` — Client « entreprise » : siège, personne à l'attention de, TVA récupérable, et…
- `CIQ403` — Résolution lead → Client entreprise : raison sociale, ICE d'abord, conflit visible…
- `CIQ404` — « Devis auto prêt » pro : facture en MAD acceptée pour un BT, kWh exigés en MT, et…
- `CIQ405` — `entrees_ci` : UNE lecture lead → entrées du moteur C&I, avec leur provenance, sans…
- `CIQ406` — Promouvoir les réponses pro du site, du sac vers les colonnes (webhook + reprise de…
- `CIQ407` — Formulaire Meta « pour mon entreprise » : une tranche ouverte n'est jamais un montant…
- `CIQ408` — Reprise des leads Meta dont « plus de 4 000 DH » a été écrit 4 000 dans facture_hiver
- `CIQ409` — Segment pro SUGGÉRÉ (jamais écrit) et drapeau d'incohérence lead ↔ devis C&I
- `CIQ410` — Panneau d'appel pro côté serveur : les 5 étapes de D-CIQ-7, chaque champ avec sa…
- `CIQ411` — CAD123 × D-CIQ-5 : pour un site pro, la visite AVANT le devis final n'est plus une «…
- `CIQ412` — Lien « questionnaire client » d'un lead pro : sections réseau, activité, site, société…
- `CIQ413` — Relève « Affiner » : le site obtient le lien du questionnaire pro de SA soumission, et…
- `CIQ414` — Score d'un lead pro : complétude pro et facture déclarée (y compris la tranche Meta)…
- `CIQ415` — Réglage « responsable des leads commerciaux et industriels », vide par défaut…
- `CIQ416` — Routage et notification d'un lead pro : le responsable désigné reçoit le lead, et la…
- `CIQ417` — Paramètres → Leads : choisir le responsable des leads commerciaux et industriels
- `CIQ418` — Fiche CRM d'un lead pro : section « Professionnel » complète (question sous chaque…
- `CIQ419` — Bandeaux de la fiche : lead pro à confirmer, et devis C&I sur un lead d'un autre type —…
- `CIQ420` — Script d'appel pro réécrit en 5 étapes (D-CIQ-7), avec la proposition de visite quand…
- `CIQ421` — Dialogue « Envoyer un questionnaire » : sections pro selon le segment
- `CIQ422` — Fiche client : saisir l'identité d'une entreprise (siège, à l'attention de, TVA…
- `CIQ423` — Générateur : bandeau « devis C&I sur un lead d'un autre type » et rappel « ICE manquant…
- `CIQ424` — Aller-retour EN DIRECT du lead pro : webhook du site → fiche → appel en 5 étapes →…
- `CIQ425` — [GATED: échantillon réel de facture MT anonymisée fourni par Reda] OCR de la facture MT…
- `CIQ426` — Générateur : la tension du lead se lit dans la colonne promue (CIQ406), plus dans le…
- `CIQ427` — Panneau d'appel pro : le numéro direct de celui qui décide quand la fiche n'a qu'un…
- `CIQ428` — Indicateur INTERNE « audit énergétique obligatoire probable » (loi 47-09, décret…
- `CIQ500` — Placeholder `{societe}` : un message B2B peut nommer l'entreprise, sans jamais laisser…
- `CIQ501` — Textes B2B FR (base partagée commercial + industriel) : plus de 3D promise, de « une…
- `CIQ502` — Forme e-mail validée (objet + corps) des touches après devis et réveil, pour les…
- `CIQ503` — Accusé « en attente d'un accord » et résumé pour la direction : deux textes prêts, sans…
- `CIQ504` — Variantes darija B2B des clés réécrites (base partagée), relecture native à faire
- `CIQ505` — Numéro fixe : une touche née WhatsApp devient un E-MAIL quand une adresse existe, sinon…
- `CIQ506` — Rendu e-mail d'une touche : objet et lien `mailto:` construits par le serveur
- `CIQ507` — Touche e-mail : afficher l'objet, ouvrir la messagerie, rappeler de joindre le PDF
- `CIQ508` — « En attente d'un accord » rendu B2B : raison typée obligatoire, étiquette par raison…
- `CIQ509` — Écran de suivi : choisir la raison de l'attente, libellés pros
- `CIQ510` — Validité d'un dossier pro : réglage « financé » sur financement déclaré ou attente d'un…
- `CIQ511` — Le lien public de la proposition vit au moins jusqu'à la validité du devis
- `CIQ512` — Attente plus longue que la validité : une étape datée « validité à renouveler », jamais…
- `CIQ513` — « Qui décide : avec un associé / la direction » pose enfin l'étiquette « Décision à…
- `CIQ514` — Motifs de perte B2B, ajoutés sans migration
- `CIQ515` — Preuve J4 d'un lead pro : une réalisation commerciale/industrielle de taille proche…
- `CIQ516` — Panneau « Proposer la visite » : consignes pros À CÔTÉ des textes du fondateur
- `CIQ517` — Playbook 82-21 : seulement pour un site MT, un lead `regularisation_8221` ou un client…
- `CIQ518` — Mesure par segment : ce que le C&I ajoute (raisons d'attente, touches converties…
- `CIQ519` — Écran Relances → mesures : les colonnes C&I du tableau « Par segment »
- `CIQ520` — Textes : structure « base B2B partagée + surcharges commerciales », vide aujourd'hui
- `CIQ521` — Aller-retour EN DIRECT du suivi d'un lead commercial (clôture de la vague, leçon QJR5)
- `CIQ523` — Beat nocturne QJ5 : un lead qui porte une étiquette « En attente d'un accord » ou une…
- `CIQ600` — Visite technique : gabarit `ci` (socle commun + BT) pour un lead commercial ou…
- `CIQ601` — Visite : « non relevé + motif » au lieu d'un chiffre inventé
- `CIQ602` — Visite C&I : zones de toiture répétables avec structure, étanchéité, accès et drapeau…
- `CIQ603` — Un seul vocabulaire de type de toiture entre le lead et la visite
- `CIQ604` — Visite validée : date et auteur du feu vert enregistrés
- `CIQ605` — Qualification de fin de visite : même vocabulaire « décideur » que le lead
- `CIQ606` — Relevé C&I : déclaré / constaté / écart, sans seconde saisie
- `CIQ607` — À la validation, le relevé C&I remonte au lead : la mesure remplace la déclaration…
- `CIQ609` — Écrans de visite : gabarit `ci` (zones, « non relevé », écarts déclaré/constaté) et…
- `CIQ610` — Chantier : niveau de tension et puissance souscrite, recopiés du lead à la création
- `CIQ611` — Checklist de chantier C&I semée (socle commun + BT), choisie par type ET par niveau de…
- `CIQ612` — Un seul calcul du régime 82-21, sourcé, dans le noyau `core` (chantier, dossier, devis…
- `CIQ613` — Chantier : régime suggéré par le noyau sourcé, libellés sans seuil, « à qualifier » au…
- `CIQ614` — Paramètres : les seuils 82-21 sont ceux des textes, la société ne saisit qu'une…
- `CIQ615` — Déclaration de raccordement : supprimer le « MT si triphasé et ≥ 50 kWc » inventé
- `CIQ616` — Pièces du dossier 82-21 tirées du décret, par étape et avec leur source ; «…
- `CIQ617` — Un SEUL état du dossier 82-21 : le chantier lit le dossier réglementaire et n'en garde…
- `CIQ618` — Un chantier C&I ouvre seul son dossier 82-21 ; un régime inconnu crée « Qualifier le…
- `CIQ619` — Dossier 82-21 : étude du distributeur, capacité réservée, convention et exploitation…
- `CIQ620` — Équipements figés au dépôt : un changement de modèle ou de puissance après dépôt…
- `CIQ621` — Site pro : pas de pose avant l'accord et la convention (loi 82-21 art
- `CIQ622` — Réglages société C&I, tous SANS défaut : tolérance de recette, échantillonnage I-V…
- `CIQ623` — Sécurité chantier minimale dans `installations` : documents HSE et garde `exige_hse`…
- `CIQ624` — Consignes de sécurité C&I (hauteur, levage, toiture fragile, coactivité, habilitation…
- `CIQ625` — Recette : le résultat est CALCULÉ par le serveur, un essai raté ne laisse plus passer «…
- `CIQ626` — Recette C&I : irradiance, énergie, PR « à titre d'information », thermographie, terre…
- `CIQ627` — Recette : la promesse de production du devis est FIGÉE dans la fiche, et comparée…
- `CIQ628` — Réserves de réception : une liste au niveau du chantier (bloquante ou non, échéance…
- `CIQ629` — Réception provisoire puis définitive : la définitive n'est prononcée qu'une fois toutes…
- `CIQ630` — Site pro : recette passée avant « Réceptionné » et visite technique validée avant le…
- `CIQ631` — PV de réception C&I : signataire nommé avec sa fonction et sa société, co-signature…
- `CIQ632` — Pack de remise C&I : as-built réel (déposé APRÈS la pose), pièces C&I, certificat…
- `CIQ633` — Numéros de série : saisie atomique sans erreur 500, import en lot avec la chaîne, gate…
- `CIQ634` — Garanties de pose et d'étanchéité du chantier : durées saisies, sans défaut, dans la…
- `CIQ635` — Portail client : la recette et les réserves de SON chantier (lecture seule)
- `CIQ636` — Fiche chantier : saisir la recette C&I (résultat calculé, sections par niveau, promesse…
- `CIQ637` — Fiche chantier : niveau de tension, régime sans seuil, section 82-21 lue dans le…
- `CIQ638` — Écran Dossiers réglementaires : régime et pièces sourcés, étude, capacité, convention…
- `CIQ639` — Paramètres : seuils 82-21 sourcés (surcharge facultative) et réglages C&I sans défaut
- `CIQ640` — Contrat O&M C&I : créé depuis la ligne O&M du devis, avec ses prestations nommées et un…
- `CIQ641` — Checklist d'entretien « Site professionnel » semée (idempotente), sans intervalle ni…
- `CIQ642` — SAV : une panne qui met un site pro à l'arrêt crée l'action « notifier le distributeur…
- `CIQ643` — Monitoring : plus d'attendu « 1 500 kWh/kWc » inventé ; sans référence, aucune alerte…
- `CIQ644` — SLA de disponibilité : plus de 98 % pré-rempli, l'indicateur s'appelle « indice de…
- `CIQ645` — Suivi de production des sites pros, phase 1 sans dépendance payante : import CSV des…
- `CIQ646` — Garantie de production : aucun rapport client tant que la société n'a pas validé…
- `CIQ648` — Écran Contrats de maintenance : prestations O&M, fréquences et prix « à renseigner »…
- `CIQ649` — Portail client « Chantiers » : afficher la recette et les réserves de son chantier pro
- `CIQ650` — Aller-retour EN DIRECT du parcours site professionnel BT : visite → lead → chantier →…
- `CIQ651` — Visite d'un commerce, d'un hôtel ou d'une clinique : horaires, circuits critiques…
- `CIQ652` — Besoin de continuité déclaré à la visite → note « orienter vers une étude de secours »…
- `CIQ653` — Écran de visite : saisir la catégorie « site commerce »
- `CIQ654` — Recette côté ventes (FG274/FG275/FG278) : plus de tolérance I-V 8 % ni de seuil PR 0,75…
- `CIQ660` — Visite d'un site MT : poste, TGBT, comptage et registres, cos φ, groupe, charges…
- `CIQ661` — Écran de visite : saisir le supplément MT
- `CIQ662` — Checklist de chantier MT semée (supplément au socle C&I)
- `CIQ663` — Recette MT : essais de limitation d'injection et de découplage exigés quand l'étude du…
- `CIQ664` — Schéma unifilaire : un étage MT (transformateur, cellule, protection de découplage…
- `CIQ665` — Aller-retour EN DIRECT du parcours site MT : visite avec supplément MT → chantier MT →…
- `CIQM1` — Juriste, une seule consultation : loi 31-08 face à l'acheteur professionnel (étend…
- `CIQM2` — Avis ÉCRIT du fiscaliste et de l'expert-comptable étendu au C&I (même consultation…
- `CIQM3` — SR500 : devenir installateur participant et obtenir les critères écrits
- `CIQM4` — Distributeur (SRM), ONEE et ANRE : position écrite sur l'excédent injecté en MT, les…
- `CIQM5` — Lire une facture MT 2026 et une facture BT professionnelle réelles (anonymisées)
- `CIQM6` — Valider le parcours « organisme financeur » avec un bailleur, et vérifier le statut des…
- `CIQM7` — Fiche d'orientation interne des financements verts (vendeur seulement)
- `CIQM8` — Modifier le formulaire Meta « pour mon entreprise » : question d'activité et tranches…
- `CIQM9` — Fournir une première référence C&I réelle (photos et accord écrit du client)
- `CIQM10` — Fournir les pièces « service achats » : police RC Pro, ICE de TAQINOR, attestations
- `CIQM11` — Mesure en lecture seule des leads pro avant de toucher au seuil, au score ou à la…
- `CIQM12` — QXG6(b) : trois offres réelles 100 / 250 / 500 kWc
- `CIQM13` — Prix de vente et d'achat des articles C&I « prix à renseigner » et fiches techniques…
- `CIQM14` — Forfaits de prestations C&I avec leur source, et prix de l'option O&M nommée
- `CIQM15` — Saisir les réglages C&I (tolérances de recette, délais, sécurité) et les scénarios de…
- `CIQM16` — Assureur et juriste : valider la clause de garantie de production avant de l'activer
- `CIQM17` — Conseiller HSE : obligations de sécurité des travaux en toiture et modèles de documents
- `CIQM18` — Bureau de contrôle : règles de charge des toitures, fibrociment, exigences d'assureur
- `CIQM19` — Décision : premier connecteur de supervision (nouvelle dépendance externe)
- `CIQM20` — Licences de réutilisation des profils BDEW et NREL ComStock
- `CIQM21` — Relevé en lecture seule des onduleurs réseau éligibles en production (verrou PVOND)
- `CIQM22` — Relectures natives darija / arabe / anglais des textes C&I (étend CADM1, modèle AGRM23)
- `CIQM23` — Valider les textes B2B marqués ✎ de la cadence
- `CIQM24` — Script d'appel `objection_loi_8221` : valider une réponse qui réserve la revente du…
- `CIQM25` — Écrire les surcharges commerciales après les premières mesures
- `ODX18` — App Facturation — étape 2 (vues/urls/recouvrement/frontend)
- `QAH10` — [GATED: secret `ANTHROPIC_API_KEY` GitHub + URL de staging/démo joignable — fondateur]…
- `CALX44` — Brancher le rattachement d'une affaire AO à un calepinage
- `CALX131` — Ouvrir l'atelier à une imagerie oblique ou LiDAR payante à la requête
- `CALX199` — Trancher l'achat d'une source météo bancable
- `CALX200` — Trancher le pas infra-horaire
- `CALX373` — (DECISION) Trancher l'aller-retour avec un configurateur de fixation constructeur
- `CALX374` — (COST) Trancher la photogrammétrie par drone comme source de relevé
- `CALX375` — (DECISION) Trancher les intégrations partenaires de conception et de stockage
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

**Blocked — awaiting founder decision (8)**

- `AGR113` — ET0 et pluie efficace par région tirées de FAO CLIMWAT (ou de la DMN), sinon étiquetées…
- `CALX339` — Figer le contrat de l'import d'un fichier PVsyst `.PAN`/`.OND` vers une fiche technique
- `CALX356` — Écrire le parseur de fichiers PVsyst `.PAN` et `.OND`
- `CALX357` — Téléverser un fichier `.PAN`/`.OND` depuis le formulaire produit
- `QC2` — [GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style…
- `S21` — Real-time WebSocket upgrade (Django Channels)
- `VX203` — Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane…
- `VX252` — [BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
