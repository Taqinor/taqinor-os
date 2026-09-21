# CODEMAP — TAQINOR OS

Generated from commit `dev-solmvp` on 2026-09-21, regenerated from source by SOLMVP51 for the **MVP solaire** perimeter (Groupe SOLMVP: 47 backend apps left the code as migration shells, 36 frontend feature folders moved to `frontend/parked/`).
Structure fingerprint: aaca5955516d8fecca32b2ec07a026d04c38df93d79bf40da58984d127b9dd0a
Plan fingerprint: 782c4188a9743a2926f0acd37b0e106ecc85d7a9ded08ef92422c1517a35fb42

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

### calepinage — Groupe CALX (lots 1 « rendre visible et opérant » et 3 « simulation sourcée », 21/09/2026 ; complète la ligne du tableau ci-dessus)  *( `/api/django/calepinage/` )*
- **Forme d'URL unique (CAL233)** : l'objet métier est servi sous `calepinages/<pk>/…` (sous-ressources en `@action` du routeur DRF, `SimpleRouter`), les réglages société sous `parametres/…`, et le moteur — un calcul SANS état — sous `moteur/calculer|pose|resultat/<job_id>/`. `tests/test_structure_urls.py` refuse toute quatrième famille.
- **Rattachement des `@action` — `views/rattachements.py` (CALX2)** : les dix sous-modules de `views/` qui posent une `@action` sur le `CalepinageViewSet` par affectation d'attribut de classe (`equipements`, `horizon`, `export_csv`, `bibliotheque`, `verrou`, `archivage`, `io_layout`, `pompage`, `simulation`, `reglementaire` — 13 actions) sont importés DEPUIS CE SEUL FICHIER ; `urls.py` l'importe une fois, AVANT `router.register` (DRF découvre les actions via `get_extra_actions()` au moment de l'enregistrement — un import posé après ne route rien). **Une action neuve s'AJOUTE en fin de `views/rattachements.py` avec son commentaire `# CALX<id>`, jamais au milieu, jamais réordonnée ; `urls.py` n'est plus rouvert par aucune tâche.**
- **Les QUATRE surfaces APPEND-ONLY du module (décision D-CALX 13)** — `frontend/src/api/calepinageApi.js`, `frontend/src/features/calepinage/atelier/onglets.js` (le rail d'onglets déclaratif), `backend/django_core/apps/calepinage/views/rattachements.py`, `backend/django_core/apps/calepinage/services/parametres_cles.py`. Elles sont déclarées dans `_APPEND_ONLY_SUFFIXES` de `scripts/plan_lanes.py` : deux tâches qui les citent ne fondent PAS leurs lanes, parce qu'une méthode, un onglet, une action ou un réglage neuf s'y **AJOUTE en fin avec un commentaire `// CALX<id>` (JS) ou `# CALX<id>` (Python)** — jamais une réécriture, jamais un tri. Mesuré sur `docs/PLAN2.md` avant CALX2 : 13 des 16 fusions de lanes du groupe CALX venaient de ces seuls fichiers (9 sur `rattachements.py`, 4 sur `calepinageApi.js`). Les règles sont purement TEXTUELLES (suffixe du chemin déclaré) : elles valent pour `onglets.js` et `parametres_cles.py` avant même leur création. `scripts/check_taches_cablage.py` admet en conséquence `features/<app>/atelier/onglets.js` comme fichier de MONTAGE d'un écran de la même feature, au même titre qu'un `module.config.jsx`.
- Corollaires de la même décision : les sorties du lot 6 vivent dans `views/documents.py` (jamais `views/sorties.py`) et le rapport d'étude dans `services/rapport/<section>.py` (jamais un `rapport_etude.py` unique). Aucun import `apps.ao` / `apps.ged` n'entre dans le module (D-CALX 2).
- **Lot 3 « Simulation de production sourcée » (CALX141-198 + 5/6/14/16/48/59/60/62/64/65/69/255/264, 21/09/2026)** : la simulation d'un calepinage est une CHAÎNE DE PERTES déclarative — `services/chaine_pertes.py` (`appliquer_chaine`, `ORDRE_ETAPES` = 24 postes dans l'ordre PVsyst, `decision_meteo`/`MeteoIndecise`, ré-indexation de la série sur l'heure LÉGALE du fuseau saisi du site, `PLAFOND_FENETRE_ANNEES = 10`) charge chaque poste PAR NOM depuis `services/etapes/<poste>.py` (`appliquer(serie, contexte) -> (serie, etape)`, fonction pure ; le contrat des six clés et les trois refus de l'ordonnanceur sont dans la docstring de `services/etapes/__init__.py` ; module absent = étape omise « non livrée », JAMAIS un défaut — D-CALX 7 : coefficient/seuil = réglage société sourcé, fiche produit, valeur PVGIS, ou omission nommant le champ). Entrées : série horaire PVGIS `services/pvgis_serie.py::ClientPvgis.serie_irradiance` (composantes + `userhorizon`, fenêtre pluriannuelle ou TMY) ou fichier météo importé (`services/meteo_fichier.py`, action `meteo-fichier/`) ; position solaire `core/calepinage/soleil.py::position_solaire` (UTC) ; ombre inter-rangées `core/calepinage/ombre_rangees.py` ; fiches produit `stock` (migration `0159_calx60_fiche_chaine_pertes`) ; réglages société À REGISTRE `services/parametres_cles.py` (sections `simulation` et `electrique_societe`, chaque valeur `{valeur, source, reference}`, migration `calepinage/0010`) — après TOUT ajout au registre, régénérer le bloc `registre` de `contract_samples/parametres_calepinage.json` (test_calx69 épingle l'égalité). Orchestration : `services/simulation.py::simuler_calepinage(calepinage, *, forcer=False)` + `construire_contexte`, action `calepinages/<pk>/simuler/` (tâche `tasks.simuler_calepinage`, nature `simulation`, `GET resultat/` la sert avec sa fraîcheur) ; résultat module par module `services/simulation_modules.py` ; incertitude P50/P90 `services/incertitude.py::bloc_incertitude` ; PR et rendement `services/performance.py::bloc_performance` ; validation croisée `services/validation.py::ecart_vs_pvcalc` ; courbe de charge `services/courbe_charge.py::construire_courbe_charge`. Dépendance `pvlib==0.15.2` (décision `docs/decisions/calx198-pvlib.md` : contre-calcul, jamais source de vérité). Golden `tests/golden_simulation/cascade_pluriannuelle_casablanca.json`. Frontend : `reglages/ReglagesSimulation.jsx`, `atelier/PanneauSeries.jsx`, `production/TapisHoraire.jsx` + `PanneauProduction.jsx`, `plan/AffectationChaines.jsx`. Règle de test (leçon du lot) : un test d'étape ISOLE son étape (`appliquer` direct ou l'entrée de cascade de son poste), jamais le total de la chaîne.

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

**Done (146)**

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
- `CALX64` — Montrer la série horaire : tapis de chaleur jour × heure et journée type par mois
- `CALX65` — Dire dans l'atelier laquelle des deux productions parle : l'estimation rapide du…
- `CALX68` — Garder un brouillon local de l'atelier et proposer sa reprise
- `CALX69` — Donner une saisie aux réglages société de simulation et d'électrique, avec provenance…
- `CALX70` — Faire servir la simulation persistée par `GET resultat/`, avec un contrôle de fraîcheur
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
- `CALX173` — Étape « ohmique AC » : la liaison onduleur-comptage, sur sa longueur saisie
- `CALX174` — Étape « transformateur » : seulement si la société en déclare un
- `CALX175` — Étape « auxiliaires » : une énergie soutirée, jour et nuit, pas un pourcentage
- `CALX176` — Étape « indisponibilité » : des fenêtres d'arrêt datées, pas un forfait annuel
- `CALX177` — Faire entrer le bifacial dans la chaîne, avec un albédo MENSUEL
- `CALX178` — Étape « vieillissement » : une production ANNÉE PAR ANNÉE, pas un pourcentage unique
- `CALX179` — Publier le ratio de performance au sens de la norme IEC 61724-1
- `CALX181` — Rendre les tableaux mensuels et par pan cohérents avec la cascade
- `CALX182` — Simuler MODULE PAR MODULE, et agréger
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
- `CALX255` — Lire la consommation du document côté serveur
- `CALX264` — Faire dépendre le COP de la pompe à chaleur de la température saisie

**Open — to build (460)**

- `AUD504` — [GATED: coût prestataire — décision fondateur] Intégration signature QUALIFIÉE DGSSI en…
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
- `CADM1` — Relecture darija par un locuteur natif
- `CADM2` — Déclaration CNDP du fichier prospects CRM + récépissé
- `CADM3` — Question à un juriste : loi 31-08, démarchage à domicile
- `CADM4` — Décision RH : travaille-t-on le soir pendant le Ramadan ?
- `CADM5` — Saisie annuelle : dates du Ramadan + 4 fêtes mobiles
- `CADM6` — Lancer le semis des 9 fériés fixes sur la société TAQINOR
- `CADM7` — Lecture SQL de production : les ~10 comptages qui manquent aux deux rondes
- `CADM8` — Relever quatre valeurs d'environnement en production
- `CADM9` — Re-vérifier neuf affirmations de marché avant tout usage client
- `ODX18` — App Facturation — étape 2 (vues/urls/recouvrement/frontend)
- `CALX44` — Brancher le rattachement d'une affaire AO à un calepinage
- `CALX63` — Compléter le dispatch batterie : écrêtage récupéré en couplage DC, stratégie « plafond…
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
- `CALX131` — Ouvrir l'atelier à une imagerie oblique ou LiDAR payante à la requête
- `CALX132` — Proposer la hauteur OSM dans le panneau Bâtiment du constructeur, sans jamais l'écrire…
- `CALX172` — Étape « écrêtage » : brancher le calcul horaire qui existe déjà et n'a jamais de série
- `CALX183` — Agréger la production par chaîne, MPPT et onduleur
- `CALX199` — Trancher l'achat d'une source météo bancable
- `CALX200` — Trancher le pas infra-horaire
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
- `CALX256` — Persister la méthode « somme d'appareils » avec la provenance de chaque appareil
- `CALX257` — Convertir les montants MAD en kWh par le barème de la société
- `CALX258` — Ouvrir les profils société au segment pompage et au type de jour
- `CALX259` — Enregistrer une courbe importée comme profil société, avec sa provenance de fichier
- `CALX260` — Décaler la courbe pendant le Ramadan sans introduire un seul chiffre neuf
- `CALX261` — Offrir les deux modes de recharge du véhicule électrique
- `CALX262` — Borner la recharge par la puissance de la borne et dire le débordement
- `CALX263` — Modéliser la climatisation en BTU avec un EER saisi
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
- `CALX339` — Figer le contrat de l'import d'un fichier PVsyst `.PAN`/`.OND` vers une fiche technique
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
- `CALX356` — Écrire le parseur de fichiers PVsyst `.PAN` et `.OND`
- `CALX357` — Téléverser un fichier `.PAN`/`.OND` depuis le formulaire produit
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
- `CALX373` — (DECISION) Trancher l'aller-retour avec un configurateur de fixation constructeur
- `CALX374` — (COST) Trancher la photogrammétrie par drone comme source de relevé
- `CALX375` — (DECISION) Trancher les intégrations partenaires de conception et de stockage
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
