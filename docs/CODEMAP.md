# CODEMAP — TAQINOR OS

Generated from commit `dev` on 2026-06-22, refreshed for the functional-domain expansion wave (5 parallel worktree lanes: apps/compta clôture de période + OD manuelles + à-nouveaux FG115–117; apps/ventes solar string-design + inverter match + tilt/azimut FG246/247/249; apps/installations jalons/modèles-de-projet/réunions FG293/296/298; **NEW app apps/flotte** Vehicule+EnginRoulant FLOTTE1/2/4; **NEW app apps/ged** Cabinet/Folder/Document/Version GED1/2/3 — all additive, company-scoped, tested), on top of the prior `dev-uiwave-20260621` world-class UI wave (34 frontend UI/UX tasks: premium DataTable, calm chrome, foundation hooks/primitives, page redesigns) (PLAN2 priority-queue run — Group Q Devis↔Toiture-3D pipeline backend (Q1–Q7: Devis.roof_layout/roof_image + layout endpoints, Lead roof_point/roof_outline/bill_kwh + per-lead token, build_devis_from_layout() service, MinIO roof-image, layout-aware quote data with byte-identical no-layout path, tokenized /proposal data endpoint + e-sign accept); Group R agentic layer — NEW APP `apps/agent` (in-code action registry + `/api/django/agent/` catalogue, AG1), FastAPI registry-driven tools with propose→confirm (`/sql-agent/confirm`, AG2) surfaced on /query, assistant confirm/result cards (AG3), domain agent actions in ventes/crm/stock/sav/installations `agent_actions.py` (AG4–AG9), Groq-Whisper assistant voice `/sql-agent/transcribe` (AG10) + voice/hands-free chat (AG11/AG12); Group S internal team chat — NEW APP `apps/chat` (Conversation/Member/Message/Attachment/Reaction/Mention, company+membership scoped, `/api/django/chat/`, S1–S9), self-hosted faster-whisper `/chat/transcribe` (NEW dep, `CHAT_TRANSCRIPTION_ENABLED`, S10) + Celery transcription pipeline (S11), full React `features/messaging` UI + `/messages` route (S12–S20); design/UI/reporting polish (F120–F123 OKLCH tokens, G124–G128 primitives, K147/N161/K148/K149/J146/P167 chart kit + dashboard + table unification); P171 DataTable→@tanstack engine swap (API-compatible, full parity). ADDITIVE migrations: ventes/0024, crm/0024, chat/0001, notifications/0007. Founder standing consent recorded in CLAUDE.md lifting the ARCH/AUTH/COST/DECISION/GALLERY/DEP gate. + 2026-06-22 greenfield-foundations run: 7 NEW apps stood up (apps/rh DossierEmploye master FG154/DC29, apps/paie ParametrePaie/BaremeIR PAIE1/2/4, apps/gestion_projet Projet/ProjetChantier PROJ1, apps/contrats Contrat CONTRAT1/2, apps/qhse NCR/CAPA QHSE1/9/10, apps/kb KbArticle KB1, apps/litiges Reclamation LITIGE1) — additive, multi-tenant, admin-gated, tested; INSTALLED_APPS+urls wired; 13 tasks ticked. BLOCKED: S21 WebSocket/Channels (needs provisioned ASGI/nginx-WS infra), I134/I138 ⌘K palette (reconcile with existing providers).) + 2026-06-22 `claude/serene-ptolemy-dj5cs0` wave-1 run: 8 parallel worktree lanes — FG122 (compta consolidated treasury position + AR/AP/payroll/TVA projection, GL-only selector + read endpoint), M4 (last `ventes → audit` back-edge removed — PDF audit capture now flows through the `core.events.document_pdf_generated` bus with an `audit` receiver; new import-linter contract pins it), FG157 (apps/rh `Remuneration` gated by the new `salaires_voir` permission), PAIE3 (apps/paie 2026 Moroccan legal payroll defaults seeded editable + `valide_par_fondateur` flag), PROJ5 (apps/gestion_projet `Tache` WBS with self-FK sub-tasks), QHSE5 (apps/qhse auto-conformity min/max on `PointControleModele`/`ReleveControle`), FG350 (frontend global `CopilotPanel` drawer reusing the FastAPI agent), GED5 (frontend `/ged` arborescent navigator over existing ged endpoints) — all additive, multi-tenant, tested; ADDITIVE migrations rh/0004, paie/0002, qhse/0004, gestion_projet/0005. + wave-2 (same run): FG123 (compta `RapprochementBancaire`/`LigneReleve`/`PointageReleve` — statement↔GL pointing, écart-zero close, no écriture), FG49 (ventes account-coded grand-livre export CGNC 3421/7111/4455, xlsx+csv, configurable codes), FG351 (apps/agent registry guarded write actions `ventes.devis.create`/`crm.client.create`/`crm.lead.create` via propose→confirm + FastAPI dynamic action_tools), FG158 (rh `DossierEmploye` emergency-contact + extended coordinates fields), PAIE5 (paie family-charge deduction params + `compute_ir` helper), GED6 (ged `DocumentLien` generic-target link via `records.ALLOWED_TARGETS` +ventes.boncommande), PROJ6 (gestion_projet `DependanceTache` FS/SS/FF/SF + lag with cycle guards), QHSE6 (qhse hold-point gating selector/endpoint) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0006, rh/0005, paie/0003, ged/0002, gestion_projet/0006 (FG49/FG351/QHSE6 need none); import-linter stays 4/4. + wave-3 (same run, 7 lanes): FG124 (compta `Caisse`/`MouvementCaisse`/`ClotureCaisse` petty-cash with optional GL posting honouring the FG115 period lock), FG50 (ventes acompte transfer/refund on facture cancel — re-point Paiement or reversing negative Paiement, chatter, no migration), FG159 (rh `DocumentEmploye` vault reusing `records.Attachment` MinIO storage + optional expiry), PAIE6 (paie `Rubrique` configurable payslip-line catalogue + idempotent seed), GED7 (ged `migrate_attachments_to_ged` command importing records.Attachment into Documents reusing file_key + DocumentLien), PROJ7 (gestion_projet `Jalon` milestones + `facturation_pct`), QHSE7 (qhse `ReleveCourbeIV` PV string I-V curve + fill factor) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0007, rh/0006, paie/0004, gestion_projet/0007, qhse/0005 (FG50/GED7 need none); import-linter stays 4/4. FG352 (RAG/pgvector, DEP:langchain-textsplitters) intentionally left [ ] for a focused run. + 2026-06-22 `claude/plan-md-completion-ysbchz` drain: 8 parallel worktree lanes off PLAN.md (compta FG125–130, ventes FG51/53/248/250/251, core FG355–359 NoOp-AI, rh FG160–165, paie PAIE7–12, ged GED8–13, gestion_projet PROJ8–13, qhse QHSE8/11–15 — 46 tasks; ADDITIVE migrations across those apps + customfields/0003; new NoOp scaffolds add no external dependency; GED12 semantic embedding OFF by default). + 2026-06-23 PLAN2 **Group U** drain (U1–U14, 10 parallel worktree lanes, one self-merge): lead-modal stays-open UX (U1), mouse-wheel + mobile-header CSS regressions (U2/U3), WhatsApp-send flips devis→envoyé via a NEW `core.events.devis_sent` event (U4), surface generated factures/BC in the devis list + BC-state warning (U5/U8), hide/badge superseded devis revisions (U7), auto-create chantier on devis acceptance via the `devis_accepted` bus (U6), stock reservation on the direct generer-facture path (U9), relance-escalation reset on full payment (U10), phantom-signé flag on post-acceptance refusal (U11, flag-only), direct nullable lead FK on Facture/BonCommande (U12), avatar same-origin proxy fix (U13), GED « Documents » write UI + `documents/televerser/` upload (U14) — additive, multi-tenant, tested; ADDITIVE migrations ventes/0027_devis_date_envoi + 0028_boncommande_lead_facture_lead. + 2026-06-24 PLAN.md batch-1 drain (8 parallel worktree lanes off the FG/module wave plan, adversarial review + local CI incl. makemigrations-check & full affected test run, one self-merge): 7 shipped — FG52 (ventes multi-currency `devise`/`taux_change` + CompanyProfile default), FG166 (rh `Pointage` clock-in/out), CONTRAT6 (contrats `confidentialite` gated on `menu_tier`), FLOTTE5 (flotte `ActifFlotte` unified asset ref), PAIE13 (paie multi-profile base-salary + proration), GED14 (ged inline `apercu` preview), PROJ14 (gestion_projet delay detection). ADDITIVE migrations ventes/0029 + parametres/0025, rh/0008, contrats/0005, flotte/0005, paie/0006. **FG131 (compta 3-way match) DEFERRED/backed-out** — the build duplicated stock's BonCommandeFournisseur/FactureFournisseur (reverse-accessor clash); needs a rebuild reusing stock procurement via selectors/services (left `[ ]`). + 2026-06-27 `claude/lucid-banzai-33af1c` PLAN.md wave-1 drain (5 parallel worktree lanes, one self-merge): PAIE14 (paie heures-sup majorées 25/50/100 %), FG167 (rh `FeuilleTemps` timesheets + labour-hours selector), CONTRAT7 (contrats `ModeleContrat` + `/instancier/`), FLOTTE7 (flotte `Conducteur` + permis), QHSE16 (qhse `Audit`/`ReponseCritere` + score → NCR) — all additive, multi-tenant, tested; ADDITIVE migrations paie/0007, rh/0009, contrats/0006, flotte/0006, qhse/0010. No new external/paid dependency, no auth change. Validated on the docker CI harness (511 affected-app tests green, makemigrations --check clean). + 2026-06-27 same run waves 2+3 (9 more file-disjoint lanes): GED15 (ged document version history + restore, `restored_from` audit), PROJ15 (gestion_projet `RessourceProfil`/`Equipe`, internal cout_horaire), FG39 (crm `ObjectifCommercial` + attainment selector, backend), FG5 (notifications `WorkingHoursConfig`/`Holiday` + calendar helpers + `seed_ma_holidays`, opt-in), FG86 (sav `Ticket.share_token` + public read-only tracking endpoint, allowlist no cout/chatter), KB5 (kb `seed_kb_templates` 5 SOP/ONEE/82-21 gabarits), FG96 (reporting `DashboardConfig` per-user/role, backend), FG102 (publicapi webhook deliveries history + replay + test, backend), FG297 (installations `DocumentProjet`/`RevisionDocument` versioned project-doc register) — all additive, multi-tenant, tested; ADDITIVE migrations ged/0008, gestion_projet/0010, crm/0028, notifications/0010, sav/0009, reporting/0003, installations/0014 (KB5/FG102 need none); import-linter stays 4/4. No new external/paid dependency, no auth change.
Structure fingerprint: 779b95c52a3391ac2f2762da89bdeeaa8ddfc76149865f8cab95949b63da909a
Plan fingerprint: 139ba50a6ad94f2ed5b6125597cad5789d30ffaae40f58c55654d0df66fed5bd

> This file is **regenerated by the build pipeline**. It is derived by reading the
> actual source (models, urls, serializers, settings, docker-compose, requirements,
> package.json, the CI workflow, frontend feature folders) — never from prose docs,
> which are known to drift. Where prose and code disagree, the code wins and the
> gap is logged in §9. Treat the commit hash above as the provenance: anything
> merged after it may not be reflected yet.

---

## Table of contents

1. [System overview](#1-system-overview)
2. [Verified stack](#2-verified-stack)
3. [Repository map](#3-repository-map)
4. [Backend, app by app](#4-backend-app-by-app)
5. [Frontend, feature by feature](#5-frontend-feature-by-feature)
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
**Django REST API** (`backend/django_core`, served by gunicorn on :8000), and a
**FastAPI AI/OCR service** (`backend/fastapi_ia`, uvicorn on :8001). The SPA calls
the Django API under the prefix `/api/django/…` and the AI service under
`/api/fastapi/…`. Django persists everything to **PostgreSQL 16 (pgvector)** and
uses **Redis** as cache plus Celery broker; a **Celery worker** (same Django image)
runs async jobs such as quote-PDF generation. Generated PDFs and uploads live in
**MinIO** (S3-compatible object storage, buckets `erp-pdf` and `erp-uploads`).
Authentication is cookie-based JWT (httpOnly refresh cookie); every API request is
scoped to the caller's `company` (the tenant). The FastAPI service shares the same
Postgres for its OCR (Zhipu) and natural-language-SQL-agent (LangChain) features,
both JWT-protected and key-gated.

```
            ┌──────────────┐
  Browser → │    nginx     │  :80 / :443  (+127.0.0.1:8090 lead webhook listener)
            └──────┬───────┘
        ┌──────────┼───────────────┬───────────────────┐
        ▼          ▼               ▼                   ▼
   frontend   django_core      fastapi_ia          (static SPA)
   (Vite SPA) gunicorn :8000   uvicorn :8001
   /api/django/*               /api/fastapi/*
        │          │               │
        │          ▼               ▼
        │     PostgreSQL 16 (pgvector)  ◄── shared DB
        │          │
        │          ├── Redis  (cache + Celery broker)
        │          ├── Celery worker (async PDFs, same Django image)
        │          └── MinIO  (erp-pdf, erp-uploads)
```

Request flow, front to back: SPA dispatches a Redux thunk → axios `GET/POST
/api/django/<app>/…` with the JWT cookie → nginx → gunicorn/Django → DRF ViewSet
(queryset filtered to `request.user.company`) → Postgres → JSON back. Quote PDFs
are the exception: the ViewSet hands off to the vendored premium engine (sync via
`/proposal`, or async via Celery) which renders with WeasyPrint and stores the file
in MinIO.

---

## 2. Verified stack

Versions below are the **pinned** values found in `requirements.txt`,
`package.json`, and `docker-compose.yml`. Items not pinned anywhere are marked
**unconfirmed**.

### Backend — Django API (`backend/django_core/requirements.txt`)
- Python **3.12** (CI runner; not pinned in repo otherwise)
- Django **5.1.4**, djangorestframework **3.15.2**, djangorestframework-simplejwt **5.3.1**, django-cors-headers **4.6.0**
- psycopg2-binary **2.9.10**, pgvector **0.3.6**
- redis **5.2.1**, django-redis **5.4.0**, celery **5.4.0**
- weasyprint **62.3**, pydyf **0.11.0**, Jinja2 **3.1.5** (PDF rendering)
- numpy **1.26.4**, matplotlib **3.9.2** (premium quote-PDF charts)
- segno **1.6.6** (scan-to-sign QR on the residential quote PDF; imported defensively)
- django-anymail[sendgrid] **10.3** (email), django-storages[s3] **1.14.4**, boto3 **1.35.99** (MinIO/S3)
- openpyxl **3.1.5** (.xlsx export), Pillow **10.4.0**, httpx **0.28.1**
- gunicorn **22.0.0** (WSGI server; 4 sync workers per compose)

### Backend — FastAPI AI service (`backend/fastapi_ia/requirements.txt`)
- fastapi **0.115.6**, uvicorn[standard] **0.34.0**, pydantic **2.10.4**, python-multipart **0.0.20**, PyJWT **2.10.1**
- sqlalchemy **2.0.36**, psycopg2-binary **2.9.10**, pgvector **0.3.6**, redis **5.2.1**
- langchain **0.3.14**, langchain-community **0.3.14**, langchain-groq **0.2.3**, langchain-openai **0.2.14**, langchain-anthropic **0.3.3**, openai **1.59.6**, sentence-transformers **>=2.0,<4.0**
- pypdf **>=4.0,<6.0**, Pillow **>=10.0,<12.0**, pymupdf **>=1.23,<2.0** (OCR utilities)
- OCR provider = **Zhipu AI / GLM vision**, key-gated by `ZHIPU_API_KEY` — called over HTTP, **not a pinned SDK** in requirements (unconfirmed which client).

### Frontend (`frontend/package.json`)
- Node **22** (CI runner)
- React **19.2.5**, react-dom **19.2.5**, react-router-dom **7.14.2**
- @reduxjs/toolkit **2.11.2**, react-redux **9.2.0**
- axios **1.15.2**, pdfjs-dist **6.0.227**, recharts **2.15.3**, @dnd-kit/core **6.3.1**
- Build/tooling: vite **8.0.9**, @vitejs/plugin-react **6.0.1**, tailwindcss **4.2.4**, @tailwindcss/vite **4.2.4**, eslint **9.39.4**, vite-plugin-pwa **1.3.0**

### Datastores & infra (`docker-compose.yml`)
- PostgreSQL **16** with pgvector — image `pgvector/pgvector:pg16`
- Redis **7.4-alpine**
- MinIO — image `minio/minio:RELEASE.2025-01-20T14-49-07Z` (CI uses `minio/minio:latest`)
- nginx (reverse proxy, custom build at `backend/nginx`)
- Django project package: **`erp_agentique`** (settings module `erp_agentique.settings.dev` in CI/compose)

---

## 3. Repository map

Vendored/generated dirs (`.venv_test`, `node_modules`, `migrations`,
`quote_engine/assets`, build output) are skipped.

```
taqinor-os/
├── STAGES.py                     Canonical pipeline stages — single source of truth (rule #2)
├── CLAUDE.md                     Founder's enforced rules (overrides assistant defaults)
├── docker-compose.yml            Local full stack (nginx, django, fastapi, celery, db, minio, redis)
├── docker-compose.prod.yml       Production compose
├── scripts/check_stages.py       CI guard: fails if any stage list diverges from STAGES.py
├── scripts/codemap_fingerprint.py CI guard: fails if this CODEMAP is stale vs the structural surface
├── .github/workflows/ci.yml      CI: changes(detector) + backend-lint, backend-tests, frontend-lint, stage-names, web-build-test, e2e + ci-gate(aggregate); per-job path filtering (infra/docs/config → stage-names only); push on main/dev only + all PRs (PR concurrency-cancel)
├── apps/web/                     Marketing website (Astro, deploys via Cloudflare) — separate autopilot scope
├── docs/                         PLAN.md, WEB_PLAN.md, this CODEMAP.md, swap maps
│
├── backend/
│   ├── django_core/              Django REST API (project: erp_agentique)
│   │   ├── authentication/         Tenant root: Company + CustomUser, JWT, registration  (NOT under apps/)
│   │   └── apps/
│   │       ├── crm/                Leads (sales funnel) + Clients + chatter + channels/tags/loss-reasons
│   │       ├── ventes/             Quotes (devis), orders (BC), invoices (factures), credit notes, payments, quote_engine
│   │       ├── stock/              Product catalogue, suppliers, movements, locations, supplier POs/returns
│   │       ├── installations/      Chantiers (installation projects), interventions, checklists, field execution
│   │       ├── sav/                After-sales: equipment registry, SAV tickets, maintenance contracts
│   │       ├── reporting/          Dashboards/KPIs/insights/audit-log (read-only; no models of its own)
│   │       ├── parametres/         Company profile + business settings + WhatsApp templates + settings audit
│   │       ├── roles/              RBAC: per-company roles + permission lists
│   │       ├── records/            Generic activities + file attachments (ContentType-based, cross-module)
│   │       ├── customfields/       Admin-defined custom fields for Lead/Client/Produit (values in custom_data)
│   │       ├── documents/          Field-execution PDFs (PV réception, bon de livraison, attestation) — no models
│   │       ├── dataimport/         Two-step CSV/XLSX import (dry-run + commit) for leads/clients/products — no models
│   │       └── contact/            Public landing-page contact form (parked by default) — no models
│   │
│   ├── fastapi_ia/               FastAPI AI service (root_path /api/fastapi)
│   │   └── app/api/endpoints/      ocr.py (Zhipu OCR), sql_agent.py (LangChain NL→SQL)
│   └── nginx/                    Reverse-proxy config
│
└── frontend/                     React/Vite SPA
    └── src/
        ├── router/                 Route table (path → page component)
        ├── pages/                  Page components grouped by area (crm, ventes, stock, sav, …)
        ├── features/               Redux slices + domain logic per area (see §5)
        ├── api/                    axios modules, one per backend area
        ├── components/             Shared UI
        ├── hooks/ store/ utils/    Cross-cutting React/Redux helpers
        └── sw.js                   PWA service worker (auto-update)
```

---

## 4. Backend, app by app

All multi-tenant models carry a `company` FK → `authentication.Company`. ViewSets
filter `get_queryset()` by `request.user.company` and force-assign `company` in
`perform_create` (never read from the request body). The literal tenant field is
**`company`** — there is no field named `tenant_id`.

API prefixes (from `erp_agentique/urls.py`, all under `/api/django/`):
`authentication` → root, `stock/`, `crm/`, `ventes/`, `parametres/`, `roles/`,
`reporting/`, `contact/`, `installations/`, `sav/`, `records/`, `imports/`
(dataimport), `custom-fields/`, `documents/`, `public/` (tokenized PDFs, no login).
JWT lives at `token/`, `token/refresh/`, `token/verify/`.

### authentication — tenant root, users, JWT  *(path: `backend/django_core/authentication`, NOT under apps/)*
Owns the tenant (`Company`), the user model, registration, and JWT issuance.
- **Company** — `nom`, `slug` (unique), `actif` (bool), `date_creation`. The tenant every other model points at.
- **CustomUser** (extends AbstractUser) — `company` FK→Company; `role` FK→roles.Role (nullable); `role_legacy` (deprecated CharField admin/responsable/normal, now kept in sync with `role`'s tier on create/update + a one-off additive data backfill); derived `menu_tier` property = the **authoritative** menu tier read from the *new* Role (Administrateur→admin, Responsable→responsable, Utilisateur/custom→normal; superuser→admin; legacy fallback only when role-less), exposed on `/auth/me/` and the JWT and used by the sidebar; `tier_for_role` + the pure `authentication/role_tiers.py` are the single source of truth; `poste`, `phone_number`, `avatar_key` (MinIO); `is_protected` (owner-account guard), `is_active`, `is_superuser`; **`supervisor`** self-FK (nullable, Feature E) driving team/subtree record-visibility. Record-visibility scoping lives in `authentication/scoping.py` (`record_scope_for`, `visible_user_ids`, `scope_queryset`) and is applied opt-in on the list+detail querysets of crm/ventes/installations/sav (only the new scoped roles narrow; admins/legacy/custom roles see all; users always keep their own records). Buy prices gated by `can_view_buy_prices` (`prix_achat_voir`).
- Endpoints (mounted at `/api/django/`): `POST /auth/register-company/` (public onboarding: new company + admin) · `POST /register/` (admin adds user to own company) · `GET /auth/me/` · `POST /auth/logout/` · `POST /auth/token/refresh/` · `GET/POST/PATCH/DELETE /users/…` + `POST /users/{id}/avatar/` (Administrateur + Responsable tier — `IsAdminOrResponsableTier`, limited tier blocked) · `GET/POST/PATCH/DELETE /companies/…` (superuser).

### crm — sales funnel + clients
Leads from creation through funnel stages, client records, Odoo-style chatter,
duplicate detection/merge, reversible archive.
- **Client** — `company` FK; `type_client` (PARTICULIER/ENTREPRISE); `nom/prenom`, `email` (optional), `telephone`, `adresse`; Moroccan IDs `cin/ice/if_fiscal/rc`; `custom_data` JSON. Unique `(company, email)` when email set.
- **Lead** — `company` FK; `client` FK→Client (nullable); `owner` FK→CustomUser; `stage` (**STAGES.py keys**: NEW/CONTACTED/QUOTE_SENT/FOLLOW_UP/SIGNED/COLD, default NEW); `perdu` (bool lost-flag) + `motif_perte`; `canal` (META_ADS/WHATSAPP_CTWA/SITE_WEB/REFERENCE/TELEPHONE/WALK_IN/AUTRE); `priorite`, `tags`, `relance_date`; `type_installation` (RESIDENTIEL/COMMERCIAL/INDUSTRIEL/AGRICOLE); energy profile (`facture_hiver/ete`, `ete_differente` bool, `regularisation_8221` bool); roof/site + pump fields; `source` (OS_NATIVE/ODOO_IMPORT_TEST/SITE_WEB); `is_archived` (bool) + `archived_by/at`; `custom_data` JSON.
- **LeadActivity** — `lead` FK; `kind` (CREATION/MODIFICATION/NOTE); field-change log (`field/old_value/new_value`) or manual `body`; `user` FK; `bulk` bool.
- **LeadTag / Canal / MotifPerte** — per-company managed lists for tags, channels, loss reasons (each has `archived` bool; Canal has `protege`).
- **WebsiteLeadPayload** — raw webhook capture from taqinor.ma; `payload` JSON, `processed` bool, `lead` FK (never loses inbound data).
- **Parrainage** (referral program, N98) — `company` FK; `parrain` FK→Client (the referrer); `filleul_lead` FK→Lead and/or `filleul_client` FK→Client (the referred) + free-text `filleul_nom`; `statut` (en_attente/converti/recompense_versee); `recompense` (Decimal, pre-filled from `parametres.CompanyProfile.referral_reward`); `notes`; `created_by`. Feature on/off via `CompanyProfile.referral_enabled`.
- Endpoints (`/api/django/crm/`): `clients/` and `leads/` ViewSets (CRUD) plus `leads/{id}/archiver|restaurer|whatsapp-devis|devis-auto|noter|merge|bulk`, `leads/{id}/duplicates`, `leads/doublons`, `leads/historique`, `leads/export-xlsx`, `clients/export-xlsx`; managed-list ViewSets `tags/`, `canaux/`, `motifs-perte/`; `parrainages/` (referrals); `assignable-users/`; `POST webhooks/website-leads/` (public, static secret).
- **management/import_odoo_leads** (N107) — `manage.py import_odoo_leads <path> --company <slug|id> [--dry-run]`: idempotent Odoo `crm.lead` importer reusing the `dataimport` parser (CSV/XLSX) + JSON; forces company server-side, reconciles on normalized email/phone + the existing `(company, external_system, external_id)` unique key (never duplicates), stage names from STAGES.py (unknown → NEW). No-op without a file. The real 619-lead extraction stays manual/gated on the actual Odoo backup (PII, never committed).

### ventes — quotes, orders, invoices, credit notes, payments, quote engine
The largest app: full quote→order→invoice→recovery lifecycle plus the vendored
premium quote-PDF engine.
- **Devis** (quote) — `company` FK; `reference` (per company+month); `client` FK→crm.Client; `lead` FK→crm.Lead (nullable, lead-primary quoting); `statut` (**brouillon/envoye/accepte/refuse/expire**); `mode_installation` (residentiel/industriel/agricole); `option_acceptee` (sans_batterie/avec_batterie); `etude_params` JSON (kWc, production, autoconso, payback, pump CV/HMT/débit…); `taux_tva`, `remise_globale`; versioning (`version`, `version_parent`, `superseded_by`, `is_active`); discount approval (`remise_approuvee`, `remise_approuvee_par`); `fichier_pdf` (MinIO key). **FG52** adds `devise` (ISO 4217, default MAD) + `taux_change` to **Devis** and **Facture** (and `parametres.CompanyProfile.devise_defaut`): on API create without an explicit devise, the company default is applied (fallback MAD); the premium PDF `fmt()` and UBL export (`dgi_export.py`/`utils/ubl.py`) emit the document currency. No base-currency conversion (currency is document-borne).
- **LigneDevis** — `devis` FK, `produit` FK→stock.Produit, `designation`, `quantite`, `prix_unitaire`, `remise`, `taux_tva` (nullable → falls back to devis rate; 10% panels / 20% other).
- **BonCommande** (client order) — `devis` OneToOne→Devis (nullable), `client` FK; `statut` (**en_attente/confirme/livre/annule**); marking `livre` decrements stock.
- **Facture** (invoice) — `devis` FK (new échéancier path) **and/or** `bon_commande` OneToOne (legacy path); `client` FK; `type_facture` (**acompte/intermediaire/solde/complete**); `statut` (**brouillon/emise/payee/en_retard/annulee**); `pourcentage`, `libelle`, frozen `montant_ht/tva/ttc`; recovery (`prochaine_relance`, `exclu_relances`); computed `montant_paye`, `avoirs_total`, `montant_du` (= TTC − paid − credits); `fichier_pdf/ubl`.
- **LigneFacture** — same shape as LigneDevis (`facture` FK).
- **Paiement** — `facture` FK; `montant`, `date_paiement`, `mode` (especes/virement/cheque/carte/prelevement/autre).
- **Avoir** (credit note) + **LigneAvoir** — `facture` FK (PROTECT), `client` FK; `statut` (emise/annulee); `motif`; frozen amounts; offsets the invoice's `montant_du`.
- **DevisActivity** — quote chatter (CREATION/MODIFICATION/NOTE), like LeadActivity.
- **FollowupLevel / RelanceLog** — recovery escalation tiers and per-invoice follow-up trace.
- **ShareLink** — public tokenized link (`token` unique, `devis`/`facture` FK, `expires_at`, 30-day) for WhatsApp PDF delivery without login.
- Endpoints (`/api/django/ventes/`): `devis/`, `devis-lignes/`, `bons-commande/`, `factures/`, `paiements/`, `avoirs/` ViewSets; key custom actions: `devis/{id}/proposal/` (**canonical quote PDF, sync**), `devis/{id}/generer-pdf/` (**async Celery**), `devis/{id}/telecharger-pdf`, `devis/{id}/accepter|reviser|approuver-remise|historique|noter`, `devis/{id}/convertir-bc`, `devis/{id}/generer-facture`; `bons-commande/{id}/confirmer|marquer-livre|annuler|creer-facture`; recovery (`relances/`, `balance-agee/`, `clients/{id}/releve(-pdf)/`, `factures/{id}/lettre-relance-pdf/`, `niveaux-relance/`); accounting (`journal-ventes/` .xlsx, `numerotation-audit/`); public `GET /api/django/public/document/{token}/` (tokenized PDF, no auth, no buy prices).
- **Toiture-3D devis web loop** (`/api/django/ventes/`): `devis/from-layout/` (build a Devis from a finalized roofPro11 layout + mint a proposal `ShareLink`), `devis/{id}/layout/` & `devis/{id}/roof-image/` (store the finalized layout + 3D snapshot); public tokenized proposal channel — `GET proposal/{token}/` (JSON quote data incl. `monthly_production`/`monthly_consumption` + `roof_image_url`), `POST proposal/{token}/accept/` (client e-signature → existing accept service), `GET proposal/{token}/pdf/` (client devis PDF). The website capture page (`/devis/mon-toit`) posts the enriched lead (exact bills, `ete_differente`, `raccordement` incl. `inconnu`, reverse-geocoded `adresse`/GPS) to the CRM webhook; **Meriem designs INSIDE the ERP** (authenticated React route `frontend` `/devis-design/:id`, same-origin cookie session — the roofPro11 builder is Vite-alias-imported from `apps/web`, no second login) and the client signs at the public `/proposition/<token>`. `GET /api/django/ventes/roof-config/` exposes the public MapTiler key same-origin (needs `PUBLIC_MAPTILER_KEY` in the ERP env).
- **quote_engine/** — premium PDF engine. `builder.py` maps an OS Devis → the generator data dict (only sell-side `prix_unitaire`; `prix_achat` excluded) and routes by market mode to one of three renderers: `residential/` (redesigned 3-page residential proposal), `agricole/` (4-page pompage-solaire proposal — cover/at-a-glance, étude+schéma+charts, équipement+prix+FDA+garanties, rentabilité solaire-vs-butane-vs-diesel+signature; modules `renderer/render/theme/cover/study/yield_page/economics_page/charts/schematic/economics/constants/sample_data`), and the legacy `generate_devis_premium.py` (one-page + industriel + fallback). `installations.py` = shared cover-hero photo library that picks the installation photo whose kWc is **nearest** the quote (agricole falls back to residential/industriel of similar power); photos in `assets/installations/<mode>-<kwc>.jpg`. `pricing.py`, `catalog.py`. Buy-price exclusion asserted by `apps/ventes/tests/test_quote_engine.py`; agricole engine by `test_agricole_quote.py`.
- **solar_design.py** (FG246/247/249) — electrical-engineering helpers: `string_design` (distributes N panels across the inverter MPPT inputs, checks string Vmp/Voc at cold temperature vs the MPPT/voltage window, reports the DC/AC ratio), `match_inverter` (picks a compatible catalogue inverter, classification keywords aligned with `builder.py`, never a price-less product), `optimize_orientation` (tilt/azimuth sweep via the existing PVGIS client). Pure + fully tested (`tests/test_solar_design.py`); not yet surfaced in an endpoint.
- **utils/references.py** — numbering = highest-used + 1 per company+month (savepoint + retry on races); never `count()+1`.
- **dgi/** (N105, silent DGI capability) — `dgi_export.py` (`build_ubl_xml`, UBL 2.1 invoice via stdlib `xml.etree`, carries seller+client ICE, per-line VAT, totals; no buy price), `dgi_validator.py` (`validate_dgi_conformity` → list of FR problem messages), `toggle.py` (`is_dgi_enabled(company)`). Armed only by `parametres.CompanyProfile.dgi_export_actif` (default **OFF**): the two facture actions `dgi-export`/`dgi-conformite` and the `dgi_export_facture` management command **404/refuse when OFF**, and the Facture model/serializer/lists are byte-identical (no field, badge, status or column added). Simpl-TVA transmission + certified e-signature remain out of scope (G14).

### stock — catalogue, suppliers, inventory, procurement
Product catalogue, multi-supplier sourcing, stock movements/locations, supplier POs
and returns.
- **Produit** — `company` FK; `nom`, `sku` (unique per company); `prix_vente` (sell HT); **`prix_achat`** (buy price — internal/generator-only, **never client-facing**); `quantite_stock` (canonical), `seuil_alerte`; `categorie`/`fournisseur` FK; commercial sheet (`marque`, `description`, `garantie`, `garantie_mois`, `garantie_production_mois`); pump specs (`pompe_cv`, `hmt_m`, `pompe_kw`, `tension_v`, `courbe_pompe` JSON); `is_archived`; `custom_data` JSON.
- **Categorie / Fournisseur / Marque** — referentials (Marque/`archived`).
- N14 (reservation-aware availability): `ProduitSerializer` exposes computed `quantite_reservee`, `quantite_disponible` (= stock − active reservations from `installations.StockReservation`) and a reservation-aware low-stock flag; the legacy `is_low_stock` and `compute_besoin_materiel` are preserved (a chantier's own reservation is not double-counted).
- **MouvementStock** — `produit` FK; `type_mouvement` (entree/sortie/transfert/ajustement); `quantite_avant/apres`; `created_by`; the audit trail for every quantity change.
- **EmplacementStock / StockEmplacement / TransfertStock** — stock locations, per-location quantities (principal derived), and transfers between them.
- **PrixFournisseur** — per-supplier `prix_achat` (internal) for cheapest-sourcing.
- **BonCommandeFournisseur** + **LigneBonCommandeFournisseur** — supplier purchase orders; `statut` (brouillon/envoye/recu/annule); receipt increments stock via MouvementStock.
- **RetourFournisseur** + **LigneRetourFournisseur** — supplier returns; `statut` (brouillon/valide/annule); validation decrements stock.
- Endpoints (`/api/django/stock/`): `produits/`, `categories/`, `fournisseurs/`, `marques/`, `mouvements/` (read-only), `bons-commande-fournisseur/`, `emplacements/`, `transferts/`, `prix-fournisseurs/`, `retours-fournisseur/`.

### installations — chantiers / field execution
Installation projects spun up once a quote is signed, through to commissioning and
closure; work orders, checklists, regulatory (law 82-21) tracking.
- **Installation** (chantier) — `company` FK; `reference`; `client` FK; `devis` FK→ventes.Devis; `bon_commande` FK→ventes.BonCommande; `lead` FK→crm.Lead; `statut` (SIGNE/MATERIEL_COMMANDE/PLANIFIE/EN_COURS/INSTALLE/RECEPTIONNE/CLOTURE + legacy values); `puissance_installee_kwc`; `type_installation`; `technicien_responsable` FK; `bom` JSON (frozen BoM from devis); `regime_8221` + `dossier_statut` (regulatory); `annule` bool + `motif_annulation`; milestone dates.
- **StockReservation** (N14) — `company` FK; `installation` FK; `produit` FK→stock.Produit; `quantite`; `consomme` bool (`unique_together (installation, produit)`). Seeded from the chantier's frozen `bom` at creation; consumed exactly once when the chantier reaches the canonical INSTALLE statut (one `MouvementStock` SORTIE per SKU, idempotent under `select_for_update()`/atomic — re-entering INSTALLE emits nothing); cancel/close releases the remaining (un-consumed) reservation. Drives the reservation-aware availability on the stock serializer (réservé vs disponible) and low-stock alerts.
- **Intervention** (sortie chantier, F3) — `installation` FK; `ticket` FK→sav.Ticket (nullable); `type_intervention` (POSE/RACCORDEMENT/MISE_EN_SERVICE/CONTROLE/DEPANNAGE); `technicien` FK; `equipe` M2M→users (default = chantier installer, set server-side); `camionnette` FK→stock.EmplacementStock (nullable); `date_prevue/realisee`; **`statut`** — its OWN ordered state machine (`a_preparer/prete/en_route/sur_site/terminee/validee` + `STATUT_ORDER`, default `a_preparer`) **completely separate from the chantier statut and the STAGES.py contract** (changing it never touches either). Réf/client/devis/ville/GPS are read-only, pulled from the chantier.
- **InterventionActivity** (F3) — per-intervention chatter (same pattern as InstallationActivity), helper `intervention_activity.py` (creation + tracked-field changes incl. statut + manual notes; user/company server-side).
- **ChecklistTemplate** (N74) — `company` FK; `nom`; `type_installation` (nullable; auto-selects the template for a chantier of that market); `ordre`; `actif`; `protege` (the per-company "Défaut" fallback that carries today's 7 steps). **ChecklistEtapeModele / ChantierChecklistItem** — template steps (now FK→ChecklistTemplate, `unique_together (company, template, cle)`) and per-chantier checklist state; `capture_serie` flags serial-number capture steps (feeds the equipment registry); `fait` bool. Auto-selection (`template_for_installation`, services.py) matches by `type_installation`, falls back to Défaut — behaviour preserved.
- **TypeIntervention / InstallationActivity** — configurable intervention types and chantier chatter.
- **JalonProjet / ModeleProjet (+ ModeleProjetJalon, ModeleProjetBomLigne) / ReunionChantier** (FG293/296/298, `models_projet.py`) — project milestones/phases (étude/appro/pose/MES/réception with `date_cible`/`date_reelle`/`atteint`), chantier-type templates (`services.instantiate_modele_projet` pre-creates standard jalons + appends BoM-type lines to the frozen `bom`, idempotent + additive), and timestamped site-meeting minutes (ordre du jour/présents/décisions/actions, author + company server-side). Endpoints `jalons-projet/`, `modeles-projet/` (+ `{id}/instancier/`), `reunions-chantier/`.
- Endpoints (`/api/django/installations/`): `chantiers/` ViewSet + `creer-depuis-devis`, `regime-suggestion`, `{id}/historique|noter|mise-en-service|annuler|reactiver`, `{id}/checklist|cocher-checklist`, `{id}/besoin-materiel|commander-besoin` (now reports a per-SKU `reserve`); `interventions/` (F3: `?statut=`/`?type_intervention=`/`?installation=` filters + `{id}/historique|noter`); `types-intervention/`; `checklist-etapes/` (filterable `?template=`); `checklist-templates/` (N74, named template CRUD, Défaut delete-protected). Frontend route `/interventions` (F4, CHANTIERS menu): list + statut kanban (drag-to-change-status, technicien reassign).

### outillage — durable field tools & kits (F1/F2)
Durable tooling (drills, ladders, meters…), tracked **strictly separate from the consumable stock catalogue** — never sellable, never consumed, never on a client-facing document.
- **Outillage** (F1) — `company` FK; `nom`; `categorie` (free text); `asset_tag`; `numero_serie`; `emplacement` FK→stock.EmplacementStock (nullable; the tool's home location among the existing dépôt/camionnette); `statut` (DISPONIBLE/EN_INTERVENTION/EN_REPARATION/PERDU); `date_achat`; `note`. Optional photo via the generic `records.Attachment` (`outillage.outillage` whitelisted in `records.ALLOWED_TARGETS`).
- **KitOutillage / KitOutillageItem** (F2) — named, reusable tooling kit templates editable in Paramètres; each an ordered list of catalogue tools (`KitOutillageItem.outil` FK→Outillage, `ordre`, `unique_together (kit, outil)`); `type_intervention` (TypeIntervention key) pre-selects a kit; `actif` toggle. Three defaults (pose structure / raccordement / mise en service) seeded on first list (idempotent), fully editable.
- Endpoints (`/api/django/outillage/`): `outils/` (read any role, write responsable/admin; filter `?statut=`/`?emplacement=`, search nom/asset_tag/numero_serie/categorie), `kits/` (seed-on-list, write admin), `kit-items/` (write admin, item company follows its kit). Frontend route `/outillage` (CHANTIERS menu) + Paramètres → « Kits d'outillage » tab.

### sav — after-sales: equipment registry, tickets, maintenance contracts
Tracks installed equipment + warranty clocks and the SAV ticket lifecycle.
- **Equipement** — `company` FK; `produit` FK→stock.Produit; `installation` FK→installations.Installation; `numero_serie`; `date_pose`; `date_fin_garantie(_production)` (computed from `date_pose` + product warranty); `statut` (EN_SERVICE/REMPLACE/HORS_SERVICE); `remplace_par_ticket` FK→Ticket.
- **Ticket** (SAV) — `company` FK; `reference`; `client` FK; `installation` FK (nullable); `equipement` FK (nullable); `type` (CORRECTIF/PREVENTIF); `statut` (NOUVEAU/PLANIFIE/EN_COURS/RESOLU/CLOTURE); `priorite`; `sous_garantie` (OUI/NON/A_DETERMINER, computed from equipment warranty if linked); `cout` (internal, never client-facing); `annule` bool + `motif_annulation`.
- **TicketActivity** — ticket chatter. **ContratMaintenance** — preventive contracts (`periodicite`, `date_debut`, `derniere_visite`, `actif`, `duree_mois`, `date_renouvellement`).
- **PieceConsommee** (N46) — parts consumed on a SAV ticket: `company` FK; `ticket` FK→Ticket; `produit` FK→stock.Produit; `quantite`; `stock_decremente` (guards double stock moves). Shown on the intervention report by designation/marque/quantité only — never buy price or margin; recording it can decrement stock via `MouvementStock`.
- Endpoints (`/api/django/sav/`): `equipements/`, `tickets/` (+ `{id}/historique|noter|annuler|reactiver|rapport-pdf`), `contrats-maintenance/`.

### reporting — dashboards, KPIs, insights, audit log  *(no models)*
Read-only aggregation across crm/ventes/installations/sav/stock, role-filtered.
- Endpoints (`/api/django/reporting/`): `dashboard/`, `search/`, `notifications/`, `calendar/` and `calendar/reschedule/` (agenda events + drag-reschedule), `pipeline/` (funnel value by STAGES, weighted forecast), `reports/sales|stock|service/` (+`?export=xlsx`), `insights/recurring-revenue|audit-log|job-costing|analytics|commissions/`, `archive/client/{id}/` and `archive/chantier/{id}/`. `job-costing` (margin via internal `prix_achat`) and `commissions` (sales commission per `CompanyProfile.commission_mode`) are admin-only.

### parametres — company profile, business settings, WhatsApp templates
- **CompanyProfile** (one per company) — identity + Moroccan legal IDs (`ice`, `identifiant_fiscal`, `rc`, `patente`, `cnss`, `rib`); branding (`logo_key`, `signature_key`, `couleur_principale`); `responsable_defaut_leads` FK (default lead owner); quote-gen knobs (`payment_terms` JSON, `quote_validity_days`, `tva_standard/panneaux`, ROI constants `onee_tarif_kwh`/`productible_kwh_kwc`/`rendement_global`, `remise_max_pct`, `discount_approval_threshold`, `agricole_pump_hours`); `default_installer` FK (default technician for new chantiers, N66; NULL = creator is responsable); sales commission (`commission_mode` off/pct_devis/par_kwc + `commission_valeur`, sensitive/admin-only, N99); referral toggle (`referral_enabled` bool + `referral_reward`, N98); silent DGI export master switch (`dgi_export_actif` bool, **default OFF**, N105 — arms the ventes `dgi/` capability, invisible while off); `doc_prefixes`/`doc_numbering` JSON.
- **MessageTemplate** — WhatsApp templates by `cle` (devis/facture/relance), `corps_fr` + `corps_darija`.
- **EmailTemplate** (FG17, in `models_email.py`) — editable e-mail templates by `cle` (devis/facture/relance/notification): `sujet` + `corps` with the same placeholder whitelist as WhatsApp (`{civilite}{nom}{reference}{lien}{n}`), `unique_together company+cle`. Helpers `EmailTemplate.get_template`/`render` (tolerant) for the future automation-email rewire (intentionally NOT wired yet). Endpoints `email-templates/` (CRUD) + `email-templates/effective/` (defaults⊕overrides) + `email-templates/bulk/` (upsert), writes audited.
- **SettingsAuditLog** — who changed which setting field.
- **StatutConfig** (N58, in `models_statuses.py`) — per-company display overlay for chantier/SAV/bon-de-commande statuses: `domaine` + canonical `cle` + `libelle` + `ordre` + `actif` (`unique_together company+domaine+cle`). Display-only — canonical keys & state machines stay in their source models; defaults read live from `Installation.STATUT_ORDER`/`Ticket.STATUT_ORDER`/`BonCommande.Statut` (`statuses_defaults.py`), so output is byte-identical until edited.
- Endpoints (`/api/django/parametres/`): `GET /`, `PUT/PATCH /update/`, `POST /upload-logo|upload-signature/`, `DELETE /delete-logo|delete-signature/`, `GET+PUT/PATCH /messages/`, `GET /audit/`; `statuts/` ViewSet (N58) + `statuts/effective/?domaine=` (full ordered effective list) + `statuts/bulk/` (upsert a domaine). Reads `GET /` and `GET /messages/` are open to any role; every write/audit endpoint (incl. `statuts/` writes) is the Administrateur + Responsable tier (`IsAdminOrResponsableTier`), limited tier blocked.

### roles — RBAC  *( `/api/django/roles/` )*
- **Role** — `company` FK; `nom` (unique per company); `permissions` JSON (validated against canonical `ALL_PERMISSIONS`); `est_systeme` bool (system roles undeletable). Linked from `CustomUser.role`.
- 2026-06-18 (Feature D): `ALL_PERMISSIONS` expanded to a module×action grid + governance codes (`*_export`, `crm/ventes/sav_reassign`, `technicien_assign`, `prix_achat_voir`, `journal_activite_voir`, scope markers `records_scope_equipe`/`records_scope_sous_arbre`). `CANONICAL_SYSTEM_ROLES` seeds **seven** roles per company — Directeur, Administrateur (=Admin), Commercial responsable, Commercial, Technicien responsable, Technicien, Viewer — plus the legacy Responsable/Utilisateur kept for existing accounts. Seeder: `init_roles` (also maps owners→Directeur, custom commercial→Commercial; N103: self-heals a drifted same-named system role to `est_systeme=True`). `role_tiers.py` now derives the tier from the authoritative permission signal first (`roles_gerer`→admin, `users_voir`→responsable) with the name mapping as fallback — so a Directeur/Administrateur whose seeded row drifted to `est_systeme=False` still resolves to the admin tier and keeps access to `/users/` and `/roles/` (N103 regression fix), without widening Commercial/Technicien/Viewer.
- Endpoints: Role ViewSet (CRUD, open to the Administrateur + Responsable tier via `IsAdminOrResponsableTier` — limited tier blocked; delete blocked if system or in-use) + `permissions-disponibles/`.

### audit — activity log (audit trail)  *( `/api/django/audit/` )*
- **AuditLog** — company-scoped (server-forced, nullable for failed login); `user` FK (null=system) + `actor_username` snapshot; `action` (create/update/delete/status/login/logout/login_failed/pdf/email/whatsapp/export/accept/refuse); `content_type` + `object_id` + `object_repr` (link-back snapshot); `detail`; `timestamp` (UTC, bucketed in Africa/Casablanca at read time).
- Capture: `apps/audit/signals.py` (post_save/post_delete + status-change via pre_save cache) on the main business models, gated by `apps/audit/middleware.py` (records only inside a request → no seed/migration noise); login/logout in `authentication/views.py`, failed login via `user_login_failed`; key actions (PDF/export/WhatsApp) via explicit `recorder.record` calls. Best-effort — never blocks the request.
- Endpoints (gated on `journal_activite_voir`, Directeur-only by default): `stats/` (hourly buckets for a day, per-day for week/month, Casablanca, filterable), `entries/` (paginated filterable list, newest first), `meta/` (filter-bar data).

### records — generic activities + attachments  *( `/api/django/records/` )*
ContentType-based, attachable to Lead/Client/Installation/Ticket.
- **ActivityType** — configurable types (Appel/Email/Relance…), `delai_defaut_jours`.
- **Activity** — generic FK target; `activity_type` FK; `due_date`; `assigned_to` FK; `done` bool + `done_at/by`; `auto_relance` bool (auto-synced from `Lead.relance_date`).
- **Attachment** — generic FK target; `file_key` (MinIO); `phase` (avant/pendant/après for field photos).
- Endpoints: `activity-types/`, `activities/` (+ `mine/`, `{id}/done/`), `attachments/` (+ `{id}/download`, `attachments-count/`).

### customfields — admin-defined custom fields  *( `/api/django/custom-fields/` )*
- **CustomFieldDef** — `module` (LEAD/CLIENT/PRODUIT), `code` (slug), `type` (TEXT/NUMBER/DATE/CHOICE/BOOLEAN), `options` JSON, `obligatoire/visible_liste/actif`. Values live in each target model's `custom_data` JSON (no schema migration).
- Endpoints: `definitions/` ViewSet.

### documents — field-execution PDFs  *(no models, `/api/django/documents/`)*
- `GET chantiers/{pk}/pv-reception|bon-livraison|dossier-remise|attestation/` — generates post-delivery PDFs for an installation.

### dataimport — CSV/XLSX import  *(no models, `/api/django/imports/`)*
- `POST dry-run/` (preview + column mapping), `POST commit/` (create-only, duplicates skipped), `GET export/{entity}/`. Targets: leads, clients, products.

### contact — public contact form  *(no models, `/api/django/contact/`)*
- `POST /` — landing-page contact form; **parked by default** (returns 404 unless `CONTACT_FORM_ENABLED=1`).

### monitoring — production supervision (N50/N51/N52)  *( `/api/django/monitoring/` )*
- Models: `MonitoringConfig` (per installed-system provider + credentials, enabled), `ProductionReading` (manual/auto yield), `UnderperformanceFlag`, per-company settings (threshold % + auto-ticket toggle, default OFF).
- Swappable provider interface (registry + `NoOpProvider` default + `FusionSolarProvider` skeleton that no-ops without credentials; no new dependency).
- `configs/` (+ `providers/`, `{id}/sync-now/`), `readings/` (list + manual entry), `settings/`. Under-performance auto-creates an idempotent SAV ticket when enabled.

### notifications — unified notification engine (N75)  *( `/api/django/notifications/` )*
- Models: `Notification` (company + recipient-scoped), `NotificationPreference` (per user×event channel toggles in_app/whatsapp/email). Service `notify()` is best-effort, respects preferences, reuses existing channels (no-op when unconfigured).
- `notifications/` (+ `unread-count/`, `{id}/read/`, `read-all/`), `preferences/`. In-app bell in the header + `/parametres/notifications`.

### automation — no-code rules engine (N72/N73)  *( `/api/django/automation/` )*
- Models: `AutomationRule` (trigger + action config), `AutomationRun` (every run logged), `AutomationApproval` (owner-tier approval step). Fires on the app's own `post_save` signals, best-effort (never breaks the originating save); opt-in.
- `rules/` (+ `{id}/toggle/`), `runs/`, `approvals/` (+ `approve/`, `reject/`). Paramètres → « Automatisations ».

### publicapi — public REST API + webhooks (N89)  *( `/api/public/` data, `/api/django/publicapi/` management )*
- Models: `ApiKey` (hashed, scoped), `Webhook`, `WebhookDelivery`. `Api-Key` auth + per-key DRF throttle; read-only company-scoped `leads/devis/factures/chantiers` (never buy prices); HMAC-SHA256-signed webhooks on lead.created / devis.accepted / chantier.completed / facture.paid (httpx, best-effort). Paramètres → « API & Webhooks ».

### agent — agentic action catalogue (Group R, AG1)  *( `/api/django/agent/` )*
- No DB model — actions are declared in code via `apps/agent/registry.py` (`AgentAction`: key/label/description/inputs-schema/endpoint/method/required_permission/risk∈internal·outward·irreversible/confirm_summary). `GET actions/` returns the per-caller, company+permission-filtered catalogue (cross-tenant leakage tested). Domain apps register their actions in `ready()` (ventes/crm/stock/sav/installations `agent_actions.py`, AG4–AG9). Execution stays the JWT-relay pattern (Django re-checks permission+company); outward/irreversible actions go through the FastAPI propose→confirm protocol.

### chat — internal team messaging « Discuss » (Group S)  *( `/api/django/chat/` )*
- Models: `Conversation` (dm/channel), `ConversationMember` (role/last_read_at/is_muted), `Message` (text/voice/system/record kinds, soft-delete, pin, reply_to), `MessageAttachment` (image/file/voice + transcript fields), `MessageReaction`, `MessageMention`, + generic shared-record link. Company **and** membership scoped everywhere (non-member 403, cross-tenant 404; company forced server-side). Endpoints: conversations (list/create/archive/read/unread/search/mute/members/leave), messages (`list?conversation=`/create/edit/delete/upload/react/pin/unpin/attachments-download/share-record via selectors). Notifications reuse `notify()` (CHAT_MESSAGE/CHAT_MENTION, mute-aware). Voice memos transcribed by a Celery task → FastAPI faster-whisper (S10/S11), flag `CHAT_TRANSCRIPTION_ENABLED`; v1 real-time is polling (WebSocket upgrade S21 is gated on provisioned infra).

### compta — Moroccan accounting (CGNC): chart, journals, ledger, statements  *( `/api/django/compta/` )*
- Double-entry bookkeeping on the CGNC plan comptable: journaux, **EcritureComptable**/**LigneEcriture** (grand livre), balance/CPC/bilan statements, lettrage. All `company`-scoped.
- **ExerciceComptable** (fiscal year) + **PeriodeComptable** (lockable month/period via `date_verrouillee`) — `services.cloturer_periode`/`rouvrir_periode` lock/unlock. Once a period is locked, `EcritureComptable`/`LigneEcriture` `save()/delete()` raise `ValidationError` (immutability), and `services.verifier_facture_modifiable` is a value-only guard ventes can call (no cross-app model import). **OD manuelles** — `services.creer_ecriture_od` posts a balanced entry with no source document, refused when the period is locked. **À-nouveaux** — `cloturer_exercice` + `reporter_a_nouveaux` carry class 1–5 balance-sheet balances into the new exercise as one balanced opening entry (idempotent via `an_reporte`). Endpoints: `periodes/{id}/cloturer|rouvrir`, `exercices/ecriture-od`, `exercices/{id}/reporter-a-nouveaux`.
- **FG118 — Immobilisation** (fixed-asset register): `company` FK, `libelle`, `categorie` (vehicule/outillage/materiel/mobilier/informatique/autre), `cout` HT, `taux_tva`, `date_acquisition`, `actif`; read-only `montant_tva`/`cout_ttc` props. Company-scoped ViewSet `immobilisations/` (category filter + search).
- **FG119 — Amortissement**: **PlanAmortissement** (OneToOne→Immobilisation; `mode` lineaire/degressif, `duree_annees`, `base_amortissable`, frozen Moroccan CGI `coefficient_degressif`) + **DotationAmortissement** (per-year `montant`/`cumul`/`valeur_nette`, `posted`, FK `ecriture`). `services.generer_plan_amortissement` (idempotent; degressive switches to straight-line-of-residual) and `services.poster_dotation` (balanced écriture debit class-6 / credit class-28 — **respects the period lock**). Actions `immobilisations/{id}/plan-amortissement`, `dotations/{id}/poster`.
- **FG120 — Cession/rebut**: **CessionImmobilisation** (`type_cession` vente/rebut, `prix_cession`, computed `valeur_nette_comptable` = cost − cumulated FG119 amortization, signed `resultat_cession` plus/moins-value, `posted` + FK `ecriture`). `services.poster_cession` posts the balanced disposal écriture (reprise amortissements + sortie class-2 + résultat 6513/7513 + 3481 on sale) — **respects the period lock** and marks the asset inactive. Actions `immobilisations/{id}/ceder`, `cessions/{id}/poster`.

### flotte — fleet: vehicles + rolling equipment (FLOTTE1, new app)  *( `/api/django/flotte/` )*
- **Vehicule** (`company` FK; immatriculation, marque, modèle, énergie diesel/essence/électrique/hybride, kilométrage, valeur, statut actif/maintenance/réformé) and **EnginRoulant** (`company` FK; type nacelle/groupe électrogène/chariot, compteur d'heures, marque, modèle, valeur, statut). Company-scoped ViewSets (company forced server-side, an injected body `company` is ignored) at `vehicules/`, `engins/` with énergie/statut/type filters + search. Uses only the `authentication.Company` string FK — no domain-app imports. **FLOTTE3** adds `Vehicule.emplacement_stock_id` (PositiveInteger, NOT a cross-app FK) referencing a `stock.EmplacementStock`; validated same-company + labelled via a function-local `apps.stock.selectors.get_emplacement_scoped` call (degrades to `#id`; never imports stock models). **FLOTTE6** adds **ReferentielFlotte** (editable per-company lookup lists: `domaine` type_vehicule/type_engin/energie/categorie_permis, `code`/`libelle`/`ordre`/`actif`, unique company+domaine+code) — additive (hardcoded choices untouched) — plus an idempotent `seed_referentiels_flotte` command. ViewSet `referentiels/` (`?domaine`/`?actif`). **FLOTTE5** adds **ActifFlotte** — a unified asset reference linking entretien/sinistre/document to EITHER a `Vehicule` OR an `EnginRoulant` via one model (exactly-one-target + same-company enforced in `clean()`/`save()`); company-scoped ViewSet `actifs/` (`?type_actif`) + selectors for cross-app reads.

### ged — document management / DMS (GED1, new app)  *( `/api/django/ged/` )*
- Governed DMS reusing `records.storage` (MinIO `file_key`). **Cabinet** + **Folder** (self-FK tree with a materialized `path` recomputed in `save()`/`services.move_folder`, sub-tree prefix rewrite + cycle refusal), **Document** (lives in a Folder) + **DocumentVersion** (`file_key`, SHA-256 `checksum` for dedupe via `services.find_duplicate`, server-set incremental `version`, `uploaded_by`). All `company`-scoped (company/created_by/uploaded_by forced server-side). Endpoints: `cabinets/`, `folders/` (+ `descendants`), `documents/`, `document-versions/`. **GED4** — move (déplacement) over HTTP: `POST folders/{id}/deplacer/` (body `{parent}`, reparent/to-root, anti-cycle + cross-cabinet refusal via `services.move_folder`) and `POST documents/{id}/deplacer/` (body `{folder}`, via `services.move_document`); destination always resolved inside the caller's company (404 cross-tenant). **GED14** — inline same-origin preview: `GET document-versions/{id}/apercu/` streams the document bytes through Django (PDF/image/text → `Content-Disposition: inline`, else attachment; `X-Content-Type-Options: nosniff`), gated as a READ action (`IsAnyRole`, like list/retrieve) so read-only roles can preview.

### rh — human resources: employee master (FG154, new app)  *( `/api/django/rh/` )*
- **DossierEmploye** (`company` FK; employee record). **FG155** adds the employment-contract layer: `type_contrat` (TextChoices CDI/CDD/ANAPEC/stage/intérim) + `contrat_date_debut`/`contrat_date_fin` (nullable dates; empty `date_fin` = open-ended/CDI). Company-scoped ViewSet (`employes/`) with `@action cdd-a-echeance/?within=N` (default 30 days) returning only same-company CDDs whose `contrat_date_fin` falls within the window. **FG156** adds the mandatory Moroccan payroll identity fields to `DossierEmploye`: `cnss`/`cimr`/`amo`, `situation_familiale` (célibataire/marié/divorcé/veuf), `nombre_enfants` (IR deductions) — all nullable (CIN/RIB already existed). **FG166** adds **Pointage** (clock-in/out: `company`+`employe` FK, `type_pointage` arrivée/départ/complet, server-set `heure_arrivee`/`heure_depart`, optional GPS, computed `duree_minutes`) with actions `pointages/pointager-arrivee` + `pointages/{id}/pointager-depart` (server timestamp; → COMPLET + duration once arrival is set). `IsResponsableOrAdmin`-gated.

### gestion_projet — project management (PROJ1, new app)  *( `/api/django/gestion-projet/` )*
- **Projet** + **ProjetChantier** (`company`-scoped). **PROJ2** adds **ProjetLien** (`company` + `projet` FK; `type_cible` devis/facture/ticket/achat, `cible_id` target PK, cached `libelle`) linking a project to other apps' documents by **string-FK only** (no real cross-app FK). Endpoints: `projet-liens/` (CRUD, `?projet=`/`?type_cible=` filters) + `projets/{id}/liens/` (enriched). `selectors.liens_enrichis` enriches devis links via a function-local `apps.ventes.selectors.devis_card` call and degrades to the stored label otherwise (cross-app boundary respected; import-linter clean). **PROJ3** adds a project-lifecycle state machine on `Projet` (`statut` brouillon→planifie→en_cours⇄en_pause→termine, annule from any non-terminal — **independent of `STAGES.py`**, rule #2) via actions `planifier`/`demarrer`/`mettre-en-pause`/`reprendre`/`terminer`/`annuler` (illegal → 400; statut read-only outside actions) + a **ProjetActivity** transition log (`historique/`). **PROJ4** adds **PhaseProjet** (project WBS: `type_phase` etude/appro/pose/mes/reception — own enum, not STAGES; prévu/réel dates, `statut`, `avancement_pct` 0-100; unique projet+type_phase) + `services.instancier_phases_standard` (5 ordered phases, idempotent). ViewSet `phases/` + action `projets/{id}/instancier-phases`. **PROJ14** adds delay detection: `selectors.retards_projet` + `GET projets/{id}/retards/` classifying unfinished tasks and unreached milestones as `en_retard` (past due) or `a_risque` (due within `seuil_jours`, default 7) with `retard_jours` (no migration).

### qhse — quality / health / safety / environment (QHSE1, new app)  *( `/api/django/qhse/` )*
- NCR/CAPA (non-conformities + corrective/preventive actions), `company`-scoped. **QHSE2** adds the ITP (inspection & test plan) templates: **PlanInspectionModele** (code/nom/actif) + **PointControleModele** (FK plan; `phase`, `type_releve` mesure/visuel/document/essai, `hold_point` bool, `ordre`). ViewSets `plans-inspection/`, `points-controle/` (company forced server-side; a point is validated to share its plan's company → 400 otherwise). **QHSE3** adds an idempotent `seed_itp_solaire` management command (per-company or `--company`) seeding 3 solar ITP templates (résidentiel réseau / autoconsommation indus-com / pompage agricole), 7 points each, hold-points on Raccordement + Mise en service. **QHSE4** adds the APPLIED instance: **PlanInspectionChantier** (FK template `PlanInspectionModele`, `chantier_id` string-FK, `statut`) + **ReleveControle** (FK point; `valeur`, `conforme` NullBoolean, `photo_key` MinIO, `releve_par`); `services.instancier_plan_chantier` materialises one relevé per template point (idempotent, backfills). ViewSets `plans-chantier/` (+ `instancier`), `releves/`. `IsResponsableOrAdmin`-gated.

### contrats — contracts (CONTRAT1, new app)  *( `/api/django/contrats/` )*
- **Contrat** (`company`-scoped). **CONTRAT3** adds **PartieContrat** (`company` + `contrat` FK `related_name='parties'`; `type_partie` client/prestataire/temoin/garant/autre, `nom`, `fonction`, `email`, `telephone`, `ordre`) — the parties/signatories of a contract. ViewSet `parties/` (CRUD, `?contrat=` filter; a party is validated same-company as its contract → 400). The "≥2 signatories" rule lives in `Contrat.valider_parties()` for finalization (not enforced at create). **CONTRAT4** adds **ContratLien** (string-FK devis/lead/installation/maintenance, like ProjetLien) with `selectors.liens_enrichis` enriching via function-local `ventes`/`crm`/`installations` selectors (sav degrades to stored label). **CONTRAT5** adds `Contrat.sav_contrat_maintenance_id` (PositiveInteger, string-id to `sav.ContratMaintenance` — additive, no sav import, validation deferred until a sav selector exists). **CONTRAT6** adds `Contrat.confidentialite` (public/interne/confidentiel, default interne) — CONFIDENTIEL contracts are visible only to Administrators, gated in `get_queryset` on the authoritative `user.menu_tier` (not the unreliable `role_legacy`/Role-FK divergence). `IsResponsableOrAdmin`-gated.

### kb — knowledge base (KB1, new app)  *( `/api/django/kb/` )*
- **KbArticle** (`company`-scoped; `statut` brouillon/publie/obsolete). **KB2** adds **KbArticleVersion** (`company` + `article` FK `related_name='versions'`; server-incremented `version` via `select_for_update` — never count()+1; `titre`/`contenu`/`auteur` snapshot). Actions `articles/{id}/publier/` (statut→publie + snapshot) and `articles/{id}/nouvelle-version/`; a version is also snapshotted on every article update. Read-only `versions/` viewset (company-scoped, `?article=` filter). **KB3** adds full-text-ish search (`?search=` over titre/corps/categorie/tags) + `?categorie=`/`?tag=`/`?statut=` filters on the article viewset, applied after company scoping (no cross-tenant leak; reuses existing fields, no migration). **KB4** adds **KbArticleLien** (string-FK produit/equipement/type_intervention, like ContratLien) with selector enrichment (produit via `stock.selectors`; others degrade) + a reverse lookup `article-liens/articles/?type_cible=&cible_id=`.

### litiges — disputes / claims (LITIGE1, new app)  *( `/api/django/litiges/` )*
- **Reclamation** (`company`-scoped; `statut` ouverte/en_traitement/resolue/rejetee). **LITIGE2** adds a server-enforced state machine (actions `prendre-en-charge`/`resoudre`/`rejeter`, illegal transitions → 400; statut read-only outside actions) plus a chatter **ReclamationActivity** (`company` + `reclamation` FK; `type` log/note, `old_value`/`new_value`/`message`/`auteur`) — auto-logs each transition and manual notes via `noter/`; timeline via `historique/`. Acting user + company always server-side.

### FastAPI AI service (`backend/fastapi_ia`, root_path `/api/fastapi`)
JWT-protected, key-gated. `GET /health`; `/ocr/*` (Zhipu bill/invoice OCR →
structured data, `ZHIPU_API_KEY`); `/sql-agent/*` (LangChain natural-language→SQL,
SELECT-only, tenant-filtered, pgvector table routing, Redis history; `GROQ_API_KEY`
or OpenAI/Anthropic via `SQL_AGENT_PROVIDER`). Group R/S additions: `/sql-agent/confirm` (run a stashed propose→confirm action by signed token), registry-driven agent tools built from the Django `/api/django/agent/actions/` catalogue with proposals surfaced on `/query`, `/sql-agent/transcribe` (Groq `whisper-large-v3` assistant voice, reuses `GROQ_API_KEY`), and `/chat/transcribe` (self-hosted `faster-whisper` for chat voice memos, behind `CHAT_TRANSCRIPTION_ENABLED`, lazy model load).

---

## 5. Frontend, feature by feature

SPA built with React 19 + Redux Toolkit + react-router 7 + Tailwind 4. `features/`
holds Redux slices and domain logic; `pages/` holds screens; `api/` holds one axios
module per backend area. The **design system** (refonte UI) lives in `design/`
(tokens + theme), `lib/` (cn + format utils), and `ui/` (primitives) — see below.

### Routes (`frontend/src/router`)
| Path | Page |
|---|---|
| `/` , `/login` | Login |
| `/landing` | Landing (marketing) |
| `/ui` | UIShowcase — design-system reference (refonte UI, public, no auth) |
| `/dashboard` | Dashboard |
| `/crm` | ClientList |
| `/crm/leads` | LeadsPage (kanban / list / calendar / charts) |
| `/activites` | MesActivitesPage |
| `/calendrier` | CalendarPage (agenda) |
| `/crm/parrainage` | ParrainagePage (referrals) |
| `/ventes/devis` | DevisList |
| `/ventes/devis/nouveau` | DevisGenerator (quote creation) |
| `/ventes/bons-commande` | VentesKanban |
| `/ventes/factures` | FactureList |
| `/ventes/avoirs` | AvoirsPage |
| `/ventes/relances` | RelancesPage |
| `/chantiers` | InstallationsPage |
| `/interventions` | InterventionsPage (field-execution list + kanban) |
| `/ma-journee` | MaJourneePage (technician day view — F22) |
| `/outillage` | OutillagePage (durable tools) |
| `/production` | ProductionPage (monitoring readings — N51) |
| `/parc` | ParcInstallePage (installed fleet) |
| `/equipements` | EquipementsPage |
| `/sav` | TicketsPage |
| `/sav/contrats` | ContratsMaintenance |
| `/stock` | StockList |
| `/stock/mouvements` | MouvementsPage |
| `/stock/bons-commande-fournisseur` | BonsCommandeFournisseur |
| `/stock/ocr-import` | OcrStockImport |
| `/ia/agent` | AgentChat |
| `/ia/ocr` | OcrUpload |
| `/reporting`, `/rapports` | Reporting / Rapports |
| `/reporting/balance-agee` | BalanceAgeePage |
| `/reporting/archive/client|chantier/:id` | Archive pages |
| `/admin/users`, `/admin/roles` | UsersManagement / RolesManagement |
| `/parametres` | ParametresEntreprise |
| `/parametres/notifications` | NotificationsPreferences (per-event channel toggles — N75) |
| `/journal` | Journal (activity log — nav item & page gated on `journal_activite_voir`) |

### Features (`frontend/src/features`)
- **auth** — session/JWT; `authSlice.js` (fetchMe, login/logout thunks).
- **crm** — leads/clients state; `crmSlice.js`, `bulk.js` (selection logic), `stages.js` (mirrors STAGES.py + CONVERSION_STAGE — CI-checked).
- **ventes** — quotes/invoices/credit notes; `ventesSlice.js`, **`solar.js`** (solar math + auto-fill for the quote generator: GHI/ONEE/ROI, panel/inverter/battery sizing, pompage HMT+débit→pump+VEICHI variateur, all TTC), `autoQuote.js`, `PdfCanvas.jsx`, `previewPdf.js`.
- **installations** — chantiers; `installationsSlice.js`, `statuses.js` (stage constants).
- **stock** — catalogue/inventory/procurement; `stockSlice.js`, `catalogue.js`, `emplacements.js`, `procurement.js`.
- **sav** — equipment + tickets; `equipementsSlice.js`, `ticketsSlice.js`, `ticketStatuses.js`.
- **reporting** — dashboards/insights; `reportingSlice.js`.
- **parametres** — settings/templates; `parametresSlice.js`.
- **ia** — AI assistant chat (registry-driven actions with propose→confirm + result cards, voice input + hands-free « Mode conversation » with a no-auto-confirm guard) + OCR; `iaSlice.js`, `voice/useVoiceChat.js`, `voice/conversationLoop.js`.
- **messaging** — internal team chat « Discuss »; `store/messagingSlice.js`, `useChatPolling.js` (visibility-aware smart polling), conversation-list/thread/composer/voice/reactions/share-record components.
- **pwa** — auto-update service worker UI; `PwaPrompts.jsx`.

### Pages (`frontend/src/pages`)
- **crm/** — ClientList, LeadForm, LeadsPage, ParrainagePage + `leads/` (ViewSwitcher, FilterBar, BulkActionBar, DoublonsPanel, SigneDialog, views/Kanban|List|Calendar|Charts).
- **ventes/** — DevisList, DevisGenerator, DevisForm, FactureList, FactureForm, AvoirsPage, RelancesPage, VentesKanban.
- **stock/** — StockList, ProduitForm, MouvementsPage, BonsCommandeFournisseur, OcrStockImport.
- **installations/** — InstallationsPage, ParcInstallePage, InstallationDetail, ChantierChecklist/Photos/Timeline.
- **sav/** — EquipementsPage, TicketsPage, ContratsMaintenance.
- **reporting/** — ArchiveClientPage, ArchiveChantierPage, BalanceAgeePage, DocumentsArchive.
- **admin/** — UsersManagement, RolesManagement. **parametres/** — ParametresEntreprise (Société tab now carries the editable RIB/Instructions de paiement/Conditions générales block; Équipe tab is the supervisor/team editor). **activities/** — MesActivitesPage. **ia/** — AgentChat (actions cards + voice/conversation mode), OcrUpload. **messaging/** — ChatPage (two-pane « Discuss »). Top-level: Dashboard (incl. "Chantiers par statut" chart), **Journal** (activity log), CalendarPage, Landing, Login, Reporting, Rapports.

### API modules (`frontend/src/api`)
`ventesApi`, `crmApi`, `stockApi`, `installationsApi`, `savApi`, `reportingApi`,
`iaApi` (→ FastAPI), `parametresApi`, `rolesApi`, `customFieldsApi`,
`documentsApi`, `recordsApi`, `messagesApi` (→ `/api/django/chat/`) — one per backend area listed in §4.

### Design system — refonte UI (`frontend/src/design`, `lib`, `ui`)
"Prettier-than-Odoo" overhaul (PLAN2 groups F+G). **Additive — existing screens
unchanged** until migrated screen-by-screen (groups J/P); custom token names, no
Tailwind default or global body font overridden, no `dark:` used elsewhere.
- **`design/`** — `tokens.css` (Tailwind 4 `@theme`: brand brass/nuit/azur/lune →
  semantic light+dark tokens + density), brand fonts (Archivo/Hanken via
  `public/fonts/brand.css`), `theme.js` + `ThemeProvider`/`ThemeToggle`
  (clair/sombre/système, défaut système).
- **`lib/`** — `cn.js` (clsx+tailwind-merge), `format.js` (MAD / fr-FR / dates /
  tél. MA — one source of truth).
- **`ui/`** — shadcn/Radix primitives: Button/IconButton/Spinner, Input/Textarea/
  Label/Number·Currency·Percent·Phone, Checkbox/Radio/Switch/Segmented/Slider,
  Select/Combobox/MultiSelect, DatePicker/DateRangePicker/TimePicker (calcul de
  dates maison, sans librairie), FileUpload/dropzone, Form system (Form/FormSection/
  FormField/FormActions + useDirtyGuard),
  Dialog/Sheet/AlertDialog/Popover/Tooltip/DropdownMenu/HoverCard/ContextMenu,
  Toaster(sonner)/Badge/StatusPill/Tag/Avatar/Card/Stat/Tabs/Accordion/Progress/
  Separator/DefinitionList, Skeleton/EmptyState/ErrorBoundary/NotFound/Offline.
  **`ui/datatable/`** — reusable `<DataTable>` engine (TanStack Table): sort/filter/
  column-management/pagination/inline-edit/bulk-bar/saved-views/URL-persistence/
  virtualization/CSV+XLSX-export/mobile-cards — engine only, demoed at `/ui`, not yet
  wired into list screens (that is Group J). Living reference at route `/ui`
  (`pages/ui/UIShowcase.jsx`, `pages/ui/DataTableDemo.jsx`). Deps (all already
  present): @radix-ui/*, @tanstack/react-table, lucide-react, sonner,
  cva/clsx/tailwind-merge.

---

## 6. Core data flow (one record, end to end)

```
crm.Lead ──(devis.lead, devis.client)──▶ ventes.Devis ──┬─(bon_commande.devis)─▶ ventes.BonCommande
   │ stage: NEW…SIGNED                  statut: accepte │                          statut: livre → stock−
   │ perdu/motif_perte                                  └─(facture.devis)────────▶ ventes.Facture
   │                                                                                type: acompte/solde/…
   │                                                          Paiement.facture ─────┤  montant_du = TTC−paid−avoirs
   │                                                          Avoir.facture ────────┘
   ▼
ventes.Devis ──(installation.devis / .lead / .bon_commande / .client)──▶ installations.Installation
                                                                          statut: SIGNE…CLOTURE, bom(JSON)
                                                                                   │
                          (equipement.installation, equipement.produit→stock.Produit, numero_serie)
                                                                                   ▼
                                                                          sav.Equipement (warranty clock)
                                                                                   │
                                  (ticket.equipement / .installation / .client)    ▼
                                                                          sav.Ticket  statut: NOUVEAU…CLOTURE
```

1. **Lead** (`crm.Lead`) — captured (native, import, or website webhook). Funnel via `stage` (STAGES.py); lost via `perdu` + `motif_perte` independent of stage.
2. **Devis** (`ventes.Devis`) — carries `lead` FK→Lead **and** `client` FK→Client; the client is resolved from the lead server-side (`apps/crm/services.resolve_client_for_lead` — reuse, else company-scoped email match, else create). `statut` walks brouillon→envoye→accepte. Accepting captures `option_acceptee` and advances the lead's `stage` to **SIGNED** (the conversion event).
3. **BonCommande** (`ventes.BonCommande`) — `devis` OneToOne→Devis; marking it `livre` decrements stock via `MouvementStock`.
4. **Facture** (`ventes.Facture`) — linked by `devis` FK (échéancier path) and/or `bon_commande` OneToOne (legacy). `type_facture` = acompte / intermediaire / solde / complete. **Paiement.facture** records payments; **Avoir.facture** records credit notes; `montant_du = total_ttc − montant_paye − avoirs_total`.
5. **Installation/Chantier** (`installations.Installation`) — created from the quote (`creer-depuis-devis`); links back via `devis`, `bon_commande`, `lead`, `client` FKs; freezes the quote's bill of materials into `bom` (JSON); `statut` SIGNE→…→CLOTURE.
6. **Equipement** (`sav.Equipement`) — registered during the chantier checklist (steps with `capture_serie`); links `installation` FK and `produit` FK→stock.Produit with `numero_serie`; warranty end dates computed from `date_pose`.
7. **SAV Ticket** (`sav.Ticket`) — links `equipement` FK (and/or `installation`, `client`); `statut` NOUVEAU→…→CLOTURE; `sous_garantie` computed from the equipment's warranty clock.

---

## 7. Hard contracts and policies

All verified against source, not prose.

- **Pipeline stages come from `STAGES.py`** (repo root) — the canonical 6 keys are
  `NEW, CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD` (French labels in the same
  file: Nouveau/Contacté/Devis envoyé/Relance/Signé/Froid). `crm.Lead.stage` uses
  these keys; the frontend mirror is `features/crm/stages.js`. CI job `stage-names`
  runs `scripts/check_stages.py` and fails on any divergence.
- **"Perdu" is a lost-flag, not a stage** — `crm.Lead.perdu` (bool) + `motif_perte`
  can be set from any stage, independent of `stage` (documented in STAGES.py lines
  8–10).
- **Entering SIGNED is the conversion event** — STAGES.py marks `CONVERSION_STAGE =
  SIGNED` and reserves the `SIGNED_QUOTE_CAPI_HOOK` sentinel for the future Meta
  CAPI "SignedQuote" emitter.
- **Buy prices never appear on client-facing PDFs** — `stock.Produit.prix_achat`
  (and `PrixFournisseur.prix_achat`, `BonCommandeFournisseur` buy lines) are
  internal/generator-only. The quote engine's `builder.py` passes only sell-side
  `prix_unitaire`; `apps/ventes/tests/test_quote_engine.py` asserts `prix_achat`
  never appears in rendered PDF HTML. `Produit.prix_achat` also powers the
  admin-only `reporting/insights/job-costing/` margin view — never a client output.
- **`/proposal` is the only client-facing quote-PDF path** — canonical endpoint
  `GET /api/django/ventes/devis/<id>/proposal/`, rendered by the vendored
  `quote_engine/generate_devis_premium.py`. `generer-pdf` (async Celery) routes
  through the same engine (toggle `USE_PREMIUM_QUOTE_ENGINE`). The legacy
  WeasyPrint quote PDF remains only as the off-switch fallback. (Invoices keep
  their own separate legacy PDF.)
- **Multi-tenant scoping** — the tenant field is **`company`** (FK →
  `authentication.Company`) on every business model; there is **no** field named
  `tenant_id`. ViewSets filter `get_queryset()` by `request.user.company` and
  force-assign `company` in `perform_create`/`perform_update` (never from the
  request body).
- **CI status checks that gate a merge** — `.github/workflows/ci.yml` defines
  **eight** jobs. It triggers on every `pull_request` and on pushes to
  **`main`/`dev`** only: feature/PR branches run once via their PR (where the
  `changes` detector diffs against the base, so config/docs-only changes skip
  the heavy jobs), and a `pull_request`-scoped `concurrency` group cancels a
  superseded PR run while pushes to `main`/`dev` always finish. A `changes`
  detector (pure-git, fails open) resolves which
  surfaces a push/PR touched and exposes `backend`/`frontend`/`web`/`code`
  outputs; the heavy/lint jobs are then **path-filtered per-job** via `if:` on
  those outputs (a skipped *job* reports "Success" to branch protection, so it
  never deadlocks — unlike a top-level `on: paths` filter, which is
  deliberately NOT used). A change that touches only CI/infra/docs/config
  (`.github/**`, `docker-compose*`, docs, `*.md`, `.gitignore`, `.claude/**`,
  top-level state) triggers **none** of the heavy jobs — only the always-on
  `stage-names` guard runs; the detector still falls open to the FULL suite when
  the diff range is unresolvable (new branch / force-push / shallow clone). The
  work jobs are: `backend-lint` (flake8) and
  `backend-tests` (Postgres+pgvector + Redis + MinIO; runs
  `python manage.py test apps authentication`) — both run when `backend/**` or
  `STAGES.py` changed; `frontend-lint` (eslint + node `--test`
  solar/catalogue/stages parity) — runs when `frontend/**` or `STAGES.py`
  changed; `web-build-test` (apps/web astro build + vitest) — runs when
  `apps/web/**` changed; `e2e` (Playwright, 16 flows) — the cross-surface net,
  runs whenever **any** application code changed (`backend/**`, `frontend/**`,
  or `STAGES.py`), skips on website-only, docs-only, and CI/infra/config-only
  changes. `stage-names`
  (`scripts/check_stages.py` **plus** `scripts/codemap_fingerprint.py --check`,
  which fails the build when this CODEMAP is stale vs the structural surface) is
  **ungated** — it is fast and is the broad drift guard, so it runs on every PR
  and on every push to `main`/`dev` (docs/plan, STAGES.py, structural). Finally `ci-gate` is an
  **always-running aggregate** (`if: always()`, `needs:` all jobs) that fails
  only when a job that actually ran failed or was cancelled — a skipped job is
  acceptable — so a single required status check can be pinned on `main` without
  deadlocking on path-filtered skips. CLAUDE.md designates the four
  lint/test/stage-name jobs as the required merge gate (0 approvals,
  merge-commit self-merge); see §9 for the `web-build-test`/branch-protection
  caveat.

---

## 8. Known discrepancies (prose vs code)

Each line is a place a prose doc says something the **code contradicts**. Code wins.

1. **App inventory is understated.** `CLAUDE.md` repo-facts lists apps
   "authentication, stock, crm, ventes, reporting, parametres, roles, contact" (8),
   and `README.md` frames the system as "five core modules + extras." The code has
   **13 apps under `apps/`** plus the top-level `authentication` package — including
   full **`installations`** (chantiers/field execution), **`sav`** (equipment +
   tickets + maintenance contracts), **`records`**, **`customfields`**,
   **`documents`**, and **`dataimport`** that the headline lists omit.
2. **`authentication` is not under `apps/`.** Prose lists it alongside the other
   apps, but it actually lives at `backend/django_core/authentication/` (top-level
   package), and the backend-tests CI command runs `test apps authentication`
   specifically because it sits outside `apps`.
3. **Quote engine swap already landed.** `README.md` says the quote-generation
   logic is "slated for replacement by an external tool." In the code the swap is
   **done**: the premium engine is vendored at `apps/ventes/quote_engine/` and
   `/proposal` is already the canonical path (matching CLAUDE.md rule #4, which is
   current; the README line is stale).
4. **CI has eight jobs, not four.** CLAUDE.md and README describe four checks
   (lint/tests/frontend-lint/stage-names). `ci.yml` actually defines eight: those
   four plus `web-build-test` (Astro build + vitest for `apps/web`), `e2e`
   (Playwright browser suite), a `changes` path-detector, and an always-on
   `ci-gate` aggregate. The four named checks are still the policy merge gate;
   whether any are branch-protection-*required* is not visible from the repo
   (see §9), but all eight jobs exist and run subject to per-job path filtering.
5. **README CI description is incomplete.** README says CI "runs flake8, eslint, the
   Django test suite, and a stage-name check" — it omits the frontend node `--test`
   parity suite and the `web-build-test` job that the workflow actually runs.
6. **"tenant_id" is not a real field.** Any reference to a `tenant_id` column is
   nominal only — the actual multi-tenant field everywhere is `company`.
7. **Reporting "no models" — confirmed, not a discrepancy.** README's claim that the
   reporting app has no models of its own is **correct** against the code (listed
   here so a reader doesn't re-flag it).

If you find no discrepancy in an area not listed above, assume none was found there
rather than that it was checked and cleared.

---

## 9. Staleness markers

Things this map could not fully verify from source — do not over-trust:

- **Which CI jobs are "required".** The eight job names come from `ci.yml`, but the
  GitHub **branch-protection** "required status checks" set is configured in
  GitHub, not in the repo, so it is not verifiable here. This map repeats CLAUDE.md's
  "first four are required" claim as policy, not as a code-verified fact. The
  `ci-gate` aggregate is built so the founder *can* later pin one always-running
  required check safely; whether they have is likewise not visible from the repo.
- **Per-app endpoint spellings.** Model names, FK targets, status/flag values, the
  root URL prefixes, the CI workflow, STAGES.py, compose, and the version pins were
  read directly. The **custom `@action` endpoint paths in §4** were collected by
  reading each app's `urls.py` via exploration agents; the high-impact ones
  (`/proposal`, `generer-pdf`, root prefixes) were double-checked, but exact
  spellings of less-critical actions should be re-confirmed against the relevant
  `urls.py` before relying on them programmatically.
- **OCR provider client.** OCR is key-gated by `ZHIPU_API_KEY` and uses Zhipu/GLM
  vision per config, but no Zhipu SDK is pinned in `fastapi_ia/requirements.txt`
  (called over HTTP) — the exact client is unconfirmed.
- **Provenance window.** Generated from `main` at commit `3267341`. Work merged
  after that commit (and any in-flight feature branches) is not reflected until this
  file is regenerated. Regeneration is wired into the plan-execution rules in
  `CLAUDE.md` (regenerate when a run changed models, endpoints, routes, or module
  structure) and is now self-enforcing: the `Structure fingerprint:` header above is
  a SHA-256 over the structural surface, recomputed by the required `stage-names` CI
  job (`scripts/codemap_fingerprint.py --check`); a structural change that does not
  refresh this map — and re-run `--write` — fails CI and cannot merge.
- **Plan-status freshness.** §10 (Plan status) is a *second* self-enforcing surface:
  the `Plan fingerprint:` header is a SHA-256 over every `docs/PLAN.md` /
  `docs/PLAN2.md` task's `(file, id, done/open/blocked)` state, recomputed by the
  same `stage-names` CI job. Ticking, adding, or removing a plan task without
  refreshing §10 (and re-running `--write`) fails CI. The Done/Open/Blocked lists
  themselves are produced verbatim by `codemap_fingerprint.py --print-plan-status`;
  the cross-check-vs-`main` notes are the agent's, refreshed in the same pass.

---

## 10. Plan status

Live build state of the execution queues — `docs/PLAN.md` (T*, N*, F*, M*, **FG*** module-gap +
functional-domain expansion audit, **PAIE*/COMPTA*/PROJ*/GED*/FLOTTE*/QHSE*/CONTRAT*/KB*/LITIGE***
new-module deep-dive backlogs, **DC*** data-connectivity / single-source-of-truth audit),
`docs/PLAN2.md` (A*–E*, F*–P* UI/UX, G*/Q*/R-AG*/S* feature groups, **U*** field-UX + document-status "connection" fixes), and `docs/ERROR_PLAN.md` (ERR* bug backlog) — read from their
BUILD QUEUE task boxes and cross-checked against `main`; completed tasks are archived verbatim in
`docs/DONE.md`. Refreshed by the `claude/lucid-banzai-33af1c` run on 2026-06-27/28 (22 PLAN.md tasks across 5 parallel worktree waves — wave 1: PAIE14/FG167/CONTRAT7/FLOTTE7/QHSE16; wave 2: GED15/PROJ15/FG39/FG5; wave 3: FG86/KB5/FG96/FG102/FG297; wave 4: LITIGE3 + COMPTA1 (already-present); wave 5: PAIE15/CONTRAT8/FLOTTE8/GED16/QHSE17/PROJ16 — all additive/multi-tenant/tested; waves 1-4 merged via #265/#266, wave 5 in flight), on top of the prior `claude/plan-md-completion-ysbchz` PLAN.md drain. This section is guarded by the
`Plan fingerprint:` header at the top of the file: the required `stage-names` CI job runs
`scripts/codemap_fingerprint.py --check`, which recomputes a SHA-256 over every task's
`(file, id, done/open/blocked)` state — so ticking, adding, or removing a plan task without
refreshing this section fails CI, exactly like the structure fingerprint guards the body. The
Done/Open/Blocked lists below are produced verbatim by `python scripts/codemap_fingerprint.py
--print-plan-status`; regenerate them and re-run `--write` whenever task states change.

**Totals: 984 tasks — 529 done · 454 open · 1 blocked.** (2026-06-29 `claude/determined-haslett-31e594` PLAN.md drain — wave 1, 8 parallel file-disjoint worktree lanes, one self-merge: compta FG132/133/134, installations FG70/71/77, ventes FG252/253/254, core FG353/354/360 (FG360 = first concrete core model AnomalyFlag), rh FG169/170/171, contrats CONTRAT10/11/12, flotte FLOTTE10/11/12, paie PAIE17/18/19 — 24 tasks open→done, all additive & revertable, multi-tenant, tested; no new external/paid dependency, no auth change; core stays a foundation layer.) (2026-06-29 `claude/crazy-goodall-89884e` PLAN.md drain — 2 parallel worktree waves (7+8 file-disjoint lanes), one self-merge: wave 1 FG131 (compta 3-way match REBUILT reusing stock procurement via selectors), FG168 (rh overtime), PAIE16 (paie benefits-in-kind), QHSE18 (qhse versioned quality procedure), CONTRAT9 (contract clauses), FLOTTE9 (driver-licence check at assignment), FG245 (ventes roof-layout editor), FG352 (ged RAG DocQA — new open-source dep langchain-text-splitters); wave 2 PROJ17 (resource unavailability), FG88 (sav preventive-tour planning), LITIGE4 (litige↔QHSE NCR link), FG6 (per-user iCal feed), DC17 (CustomUser.poste → rh.Poste référentiel, reversible data migration), DC18 (automation email-template store), N91+F21 (offline-tolerant field capture). 16 tasks moved open→done — additive (one reversible data migration), multi-tenant, tested; validated on the docker CI harness (compta 215 + automation 46 green, makemigrations --check clean, backend flake8 clean). (2026-06-24 add-to-plan: appended PLAN2 **Group QJ** (QJ1–QJ25) — best-in-world quote-journey ERP tasks: proposal open-tracking, Celery scheduler + relance cadence + auto quote-expiry, lead scoring, e-sign evidence hardening (loi 53-05), financing data, self-consumption tariff engine, commercial dashboard, + gated WhatsApp-API / CMI-deposit / auto-roof-detection. The matching website tasks WJ1–WJ24 live in docs/WEB_PLAN.md, which is NOT in the plan-fingerprint surface. Backlog additions only — nothing built or ticked; done/blocked counts unchanged.) (2026-06-22 add-to-plan: appended PLAN2 **Group U** (U1–U14) — field-UX bugs Reda is hitting + the family of document-status "connection" gaps found while investigating his WhatsApp/facture report: U1 lead-modal stays open on « Mettre à jour » + inline devis, U2 mouse-wheel scroll regression, U3 mobile header overlap, U4 WhatsApp-send flips devis → envoyé + advances funnel, U5 surface generated factures/BC in the devis list, U6 auto-create chantier on devis acceptance, U7 hide/badge superseded devis revisions, U8 reflect BC state in the devis detail, U9 stock reservation on the direct generer-facture path, U10 reset relance escalation on full payment, U11 lead-funnel sanity on post-signed refusal (DECISION), U12 direct lead FK on facture/BC, U13 user-picture upload bug, U14 GED « Documents » menu unusable (read-only nav, no create/upload). All 14 BUILT & ticked 2026-06-23 in 10 parallel worktree lanes (one self-merge) — see DONE LOG; category notes: U4 AUTH (CRM action changes a document status; new `devis_sent` event), U6 ARCH (new cross-app event reaction), U9 SCHEMA (stock side-effects on a new trigger), U12 SCHEMA (additive nullable lead FK, migration 0028), U11 DECISION (built FLAG-ONLY — founder to confirm whether the funnel should recede). ADDITIVE migrations ventes/0027_devis_date_envoi + 0028_boncommande_lead_facture_lead. Prior context below.) (2026-06-22 `claude/plan-md-completion-ysbchz` functional-domain drain — PLAN2 already drained; that run drained 8 parallel worktree lanes off PLAN.md: compta FG125–130 (trésorerie/effets), ventes FG51/FG53/FG248/FG250/FG251 (POD gate, NoOp PaymentLink, toiture-3D/ombrage/BOQ), core FG355–359 (OCR/voix/photo-QA/next-best-action — NoOp AI foundation, aucune dépendance), rh FG160–165 (postes, congés Maroc, workflow), paie PAIE7–12 (rubriques→bulletin CNSS/AMO/CIMR/IR), ged GED8–13 (coffre-fort/tags/plein-texte/sémantique), gestion_projet PROJ8–13 (CPM/Gantt/baseline), qhse QHSE8/11–15 (photos/réserve→NCR/CAPA/chatter/grilles). 46 moved open→done this run, all additive & tested. FG52 (multi-devise) left [ ] for a focused run.)
added the FG1–FG399 feature-gap + functional-domain backlog, 275 new-module deep-dive tasks across
nine modules (PAIE/COMPTA/PROJ/GED/FLOTTE/QHSE/CONTRAT/KB/LITIGE), and DC1–DC42 data-connectivity
tasks to `docs/PLAN.md`. No task was built or ticked — backlog additions only; done/blocked counts
are unchanged from the prior batch.)

> Note: only **S21** (real-time WebSocket chat) remains blocked — it waits on founder-provisioned WS
> infra (ASGI server + Redis channel layer + nginx WS proxy) and I recommend deferring it (3 s
> polling is enough). The previously-blocked tasks are unblocked: **N91/F21** (offline capture — the
> dev-field-exec routing was stale: the field-exec backend is already on `main` and worktree
> isolation prevents collisions), **M4** (do it via the M6 `core/events.py` bus — reuse
> `AuditLog.Action.PDF`), **I134/I138** (already shipped under other IDs — reconcile only), and
> **N100/N101/N102** (multi-tenant SaaS — ungated per "ungate all" but I recommend keeping them
> deferred until a 2nd paying installer; do not let a drain build them yet). See the **NEEDS YOUR
> INPUT** sections of `docs/PLAN.md` / `docs/WEB_PLAN.md` for the credential/data/taste items.

**Done (529)**

- `ERR1` — [FastAPI] NL→SQL agent has no SELECT-only enforcement in code…
- `ERR2` — [FastAPI] NL→SQL tenant isolation is defeatable four ways…
- `ERR3` — [FastAPI] The SQL agent connects as the table-owner Postgres role…
- `ERR4` — [auth] `is_responsable` returns True for ANY user that merely has a role…
- `ERR5` — [roles/auth] Responsable-tier users can self-grant any permission and escalate to…
- `ERR6` — [automation] Automation actions re-fire their own triggers with no recursion guard…
- `ERR7` — [ventes] `LigneDevisViewSet`/`LigneFactureViewSet` allow cross-tenant line injection…
- `ERR8` — [ventes] `DevisViewSet.perform_update` mass-assignment lets a devis be re-pointed at…
- `ERR9` — [sav] `ContratMaintenanceViewSet` has no `_check_tenant` and its serializer no…
- `ERR10` — [stock] The `MouvementStock` write endpoint accepts arbitrary negative/zero/overflow…
- `ERR11` — [reporting/exports] CSV/Excel formula injection in the shared `build_xlsx_response`…
- `ERR12` — [frontend] `OcrStockImport` BCF reception reads `lignes` off the create response and…
- `ERR13` — [ventes] `BonCommandeViewSet.perform_create` doesn't validate body `client`/`devis`…
- `ERR14` — [ventes] `FactureViewSet.perform_create` doesn't validate body…
- `ERR15` — [ventes] `BonCommandeViewSet.marquer_livre` does `int(ligne.quantite)`, truncating…
- `ERR16` — [ventes] The legacy BC→Facture path ignores `Devis.option_acceptee` and bills BOTH…
- `ERR17` — [quote_engine] `generate_premium_pdf` mutates ~40 module globals…
- `ERR18` — [FastAPI] JWT verification doesn't require `exp` (or `iss`/`aud`)…
- `ERR19` — [FastAPI] The raw user question is concatenated into the agent prompt that drives the…
- `ERR20` — [FastAPI] `prix_achat`/margin confidentiality is only a prompt instruction…
- `ERR21` — [auth] `UserViewSet`/`RegisterView` accept an arbitrary `role` PK with no company or…
- `ERR22` — [auth] `prod.py` omits production hardening (`erp_agentique/settings/prod.py`)…
- `ERR23` — [stock] `MouvementStockViewSet.perform_create` isn't atomic and uses…
- `ERR24` — [stock] `recevoir` and `apply_retour_fournisseur` read `quantite_stock` without…
- `ERR25` — [parametres] `CompanyProfileSerializer` uses `fields='__all__'` with `company` writable…
- `ERR26` — [frontend] The map popup injects unescaped `popupHtml` (`components/MapView.jsx:92-95`)…
- `ERR27` — [frontend] Route guards enforce authentication but not role/permission…
- `ERR28` — [frontend] The `ParametresEntreprise` `<form>` lacks `noValidate` while wrapping…
- `ERR29` — [frontend] `InstallationsPage` kanban status/reschedule writes have no rejection…
- `ERR30` — [frontend] `EquipementsPage` shows raw `JSON.stringify(err.response.data)` on save…
- `ERR31` — [frontend] `MouvementsPage.validate()` requires quantity `> 0` for all types incl
- `ERR32` — [web] `simulate.ts`/`preview-lead.ts` log full lead PII (name/phone/city/consent) via…
- `ERR33` — [ventes] `DevisViewSet.accepter` forces `ACCEPTE` with no guard on the current status…
- `ERR34` — [ventes] `FactureViewSet.creer_avoir` swallows all per-line errors and silently drops…
- `ERR35` — [ventes] `task_generate_devis_pdf` isn't idempotent under `acks_late` + retry…
- `ERR36` — [ventes] `relance_reminders` scheduling is destructive/lossy…
- `ERR37` — [quote_engine] User-controlled text (client name/address/phone/ICE; line…
- `ERR38` — [crm] `resolve_client_for_lead`'s check-then-create isn't transactional…
- `ERR39` — [crm] `Lead.gps_lat`/`gps_lng` have no range validation (`crm/models.py:181-184`): a…
- `ERR40` — [installations] `mise_en_service` sets `statut` directly and skips…
- `ERR41` — [installations] `field_capture.validate_consommation` truncates fractional…
- `ERR42` — [FastAPI] CORS `allow_credentials=True` with a default origin and `_DEBUG` defaulting…
- `ERR43` — [FastAPI] `sql_db_schema`/`sql_db_list_tables` tools and `sample_rows_in_table_info=2`…
- `ERR44` — [FastAPI] The sql_agent endpoint reads `company_id` from the JWT with no presence…
- `ERR45` — [auth] JWT auth cookies use `SameSite=Strict` with cross-origin credentialed CORS and…
- `ERR46` — [publicapi] `WebhookViewSet` allows CRUD of `target_url` and `delivery._deliver_one`…
- `ERR47` — [monitoring] `evaluate_underperformance` does read-then-create on…
- `ERR48` — [automation] `run_approved` resolves the deferred target by raw PK with no company…
- `ERR49` — [automation] SEND_EMAIL uses `send_mail(fail_silently=True)` and always returns SUCCESS…
- `ERR50` — [notifications] VERIFY whether the notification engine is actually invoked by business…
- `ERR51` — [dataimport] `commit` imports rows one-by-one with no `transaction.atomic`…
- `ERR52` — [dataimport] Product import sets `quantite_stock` directly with no `MouvementStock`…
- `ERR53` — [dataimport] Import dry-run/commit swallow all exceptions into a generic 400 and read…
- `ERR54` — [stock] `compute_besoin_materiel` truncates Decimal devis quantities via `int()`…
- `ERR55` — [parametres] `CompanyProfile` has no validation on…
- `ERR56` — [records] `resolve_target` lets `Model.DoesNotExist` (and a bad-type pk) escape as a…
- `ERR57` — [reporting] `stock_report`'s low-stock list doesn't exclude `seuil_alerte=0`…
- `ERR58` — [frontend] The `iaApi` interceptor reads `error.config` unguarded and hard-redirects to…
- `ERR59` — [frontend] Logout does `localStorage.clear()`, wiping theme, sidebar state, saved lead…
- `ERR60` — [frontend] `fetchMe.fulfilled` stores only `{username}`, dropping email/other user…
- `ERR61` — [frontend] Raw error objects are shown to users via `JSON.stringify` on `LeadsPage`…
- `ERR62` — [frontend] Swallowed fetch errors masquerade as empty data on `BalanceAgeePage`…
- `ERR63` — [frontend] `ParametresEntreprise.saveNiveaux` fires per-row PATCHes in `Promise.all`…
- `ERR64` — [frontend] `TicketsPage` bulk PATCH is non-atomic and doesn't reload on partial failure…
- `ERR65` — [frontend] `MouvementsPage` "Transferts" tab never shows its `(n)` count…
- `ERR66` — [frontend] `InterventionsPage` reassign doesn't refetch on failure and isn't optimistic…
- `ERR67` — [frontend] The voice-memo recorder leaks the mic stream on unmount…
- `ERR68` — [frontend] `Reporting` destructures the dashboard payload unconditionally after a null…
- `ERR69` — [frontend] The `Journal` data effect depends on both `filterParams` and `page` while…
- `ERR70` — [web] hreflang/x-default alternates have mismatched trailing slashes between locales…
- `ERR71` — [ventes] `Devis.total_tva` sums per-line TVA without quantize while…
- `ERR72` — [ventes] `enregistrer_paiement`'s overpayment guard reads `montant_du` outside any row…
- `ERR73` — [ventes] `recouvrement._releve_data` pulls `Facture.objects.filter(client=client)`…
- `ERR74` — [quote_engine] `/proposal` is a GET that re-renders and persists `fichier_pdf` on every…
- `ERR75` — [quote_engine] The legacy fallback PDF key is not company-scoped (`utils/pdf.py:155` vs…
- `ERR76` — [quote_engine] An unbounded `custom_acompte` can make a negative "Matériel" amount /…
- `ERR77` — [crm] `merge_leads`'s `_MERGE_FILL_FIELDS` omits several lead fields incl
- `ERR78` — [crm] bulk/whatsapp endpoints don't coerce/validate `ids` element types…
- `ERR79` — [crm] The website webhook's idempotent re-POST within `DEDUP_WINDOW` blindly `setattr`s…
- `ERR80` — [installations/sav] Three SORTIE paths drive stock negative with no floor guard…
- `ERR81` — [installations] `tool_return` is a GET that creates `ToolReturn` rows…
- `ERR82` — [outillage] No checkout step exists; a tool is only marked busy at return time inside…
- `ERR83` — [sav] `ContratMaintenance.is_due`/`renouvellement_du` default to naive `date.today()`…
- `ERR84` — [FastAPI] The generated SQL (with real table names) is returned to the client in…
- `ERR85` — [FastAPI] `create_tables()` runs unconditional `ALTER TABLE`/`CREATE INDEX` DDL on…
- `ERR86` — [FastAPI] The OCR rate-limit fails open on any Redis error…
- `ERR87` — [auth] Logout blacklists only the refresh token; the access token stays valid up to its…
- `ERR88` — [auth] `seed_demo` creates `demo_admin`/`demo_resp` with the hardcoded password…
- `ERR89` — [auth/publicapi] One-time-reveal secrets (webhook secret, API key) are returned without…
- `ERR90` — [automation] The overdue-facture check compares `echeance` against the UTC date…
- `ERR91` — [notifications] The in-app notification `body` is written unbounded while…
- `ERR92` — [auth/audit] The login audit `actor_username` comes from the client-supplied…
- `ERR93` — [stock] `StockEmplacement.unique_together` omits `company` and `quantite` allows…
- `ERR94` — [stock] The per-emplacement breakdown derives the principal location as `total −…
- `ERR95` — [stock] `ProduitSerializer` uses `fields='__all__'` with a runtime `prix_achat` pop…
- `ERR96` — [frontend] The DataTable default `getRowId` mixes a page-local index for keys with a…
- `ERR97` — [frontend] `datatable/csv.js`'s `escapeCSVCell` does RFC-4180 quoting but no…
- `ERR98` — [frontend] `ProduitForm` `prix_vente` validation accepts 0 and negatives…
- `ERR99` — [frontend] `StockList` reads `r.data.results ?? r.data` without the `?? []` fallback…
- `ERR100` — [frontend] `ProductionPage.reloadReadings` (from addReading/syncNow) fetches with no…
- `ERR101` — [frontend] `RolesManagement` reassign-on-blocked-delete requires both `users_count>0`…
- `ERR102` — [frontend] Several parametres section name inputs are uncontrolled `defaultValue` with…
- `ERR103` — [frontend] `MaJourneePage` renders the flow sheet from a stale `active` snapshot…
- `ERR104` — [frontend] `NotificationBell` optimistically marks read in `.finally()` regardless of…
- `ERR105` — [frontend] `InlineEdit` resets `draft` to `value` while not editing on save failure…
- `ERR106` — [frontend] `lib/format.js`'s `toNumber` strips a dot followed by exactly 3 digits as a…
- `ERR107` — [frontend] Per-line vs total rounding can disagree by 1 MAD on the devis screen…
- `ERR108` — [frontend] `Login`'s `BouncingBackground` captures window W/H once with no resize…
- `ERR109` — [web] The `*.workers.dev` 301 redirect applies to all methods incl
- `ERR110` — [web] The lead webhook uses a static `x-webhook-secret` with no HMAC/timestamp/nonce…
- `ERR111` — [web] The CAPI relay receives un-hashed phone/city PII…
- `ERR112` — [web] The public lead endpoint has no rate limit/CAPTCHA…
- `ERR113` — [web] `roof.ts`'s `annualSavingsBandMad` uses a flat 1.4 MAD/kWh tariff with no bill…
- `COMPTA1` — Plan comptable CGNC paramétrable + `seed_plan_comptable` idempotent
- `CONTRAT1` — App `contrats` + modèle `Contrat` socle (référence via `references.py`)
- `CONTRAT2` — Enum `type_contrat` (12 types) + lifecycle statut
- `CONTRAT3` — `PartieContrat` (parties/signataires, ≥2)
- `CONTRAT4` — Liens inter-apps (devis/lead/installation/maintenance) en string-FK
- `CONTRAT5` — Wrap de `sav.ContratMaintenance` (lecture/lien, ne casse pas)
- `CONTRAT6` — Niveaux de confidentialité + droits d'accès par type
- `CONTRAT7` — `ModeleContrat` (bibliothèque de modèles)
- `CONTRAT8` — `Clause` (bibliothèque de clauses réutilisables)
- `CONTRAT9` — `ClauseContrat` (clauses résolues, ordonnées, surchargeables)
- `CONTRAT10` — Génération du contrat par fusion (merge tokens)
- `CONTRAT11` — Rendu PDF interne du contrat (hors `/proposal`)
- `CONTRAT12` — Machine d'états du cycle de vie + transitions gardées
- `DC17` — `CustomUser.poste` en texte libre
- `DC18` — Sujet email hardcodé « Notification Taqinor »
- `DC29` — UN master employé : `DossierEmploye` OneToOne→`CustomUser`
- `F21` — Offline-tolerant field capture
- `FG1` — Activate the dead notification EventTypes via Celery-Beat sweeps
- `FG2` — Wire the automation engine's time-based triggers
- `FG3` — Automation rule template library (no-code presets)
- `FG4` — Admin-configurable notification routing rules
- `FG5` — Working-hours + Moroccan public-holiday calendar feeding planning/relance
- `FG6` — ICS/iCal calendar feed per user
- `FG7` — Generic comments + @mentions across all records
- `FG8` — Unified, role-scoped cross-record activity feed ("Fil d'activité")
- `FG9` — Shared cross-module tag taxonomy
- `FG10` — Tenant-wide document/attachment center
- `FG11` — Generalize saved filters/views to all list screens
- `FG12` — Wire the existing dark-mode/theme toggle into the app shell
- `FG13` — Surface a push-notification opt-in toggle in settings
- `FG14` — Bulk import for more entities
- `FG17` — Email template management (parity with WhatsApp templates)
- `FG27` — Lead scoring
- `FG28` — First-response SLA + "lead non contacté" alert
- `FG29` — Time-in-stage age + funnel-velocity analytics
- `FG30` — Unified communication log (calls/emails) in the chatter
- `FG31` — "File de relance du jour" consolidated queue
- `FG32` — Client segmentation (RFM / dormant / top)
- `FG33` — Bulk WhatsApp outreach
- `FG34` — Source/campaign ROI analytics
- `FG35` — "Lead express" quick capture
- `FG36` — Reusable WhatsApp message templates in CRM
- `FG37` — Lead pipeline map view
- `FG38` — Lead↔Client duplicate match at creation
- `FG39` — Sales objectives & KPI targets vs actuals
- `FG40` — Recurring maintenance-contract billing
- `FG41` — Client credit limit / encours gate
- `FG42` — Bank-statement payment import & reconciliation
- `FG43` — Invoice bulk operations
- `FG44` — Quote refusal with motif
- `FG45` — Ventes quote-to-cash finance dashboard
- `FG46` — Flexible échéancier + stored acompte
- `FG47` — Cash-flow / receivables forecast
- `FG48` — On-screen two-option quote comparison
- `FG49` — Account-coded accounting export (PCG/Sage layout)
- `FG50` — Acompte transfer/refund on invoice cancel
- `FG51` — Proof-of-delivery gate before invoicing
- `FG52` — Multi-currency quoting/invoicing
- `FG53` — E-payment "Payer en ligne" link
- `FG54` — Reorder-point auto-PO suggestions
- `FG55` — Supplier-invoice PDF (facture fournisseur)
- `FG56` — "Facturer cette réception" line-driven supplier invoice
- `FG57` — Dead-stock / rotation aging report
- `FG58` — Supplier price-list comparison UI
- `FG59` — Supplier performance scorecard
- `FG60` — Stock-movement filters + xlsx export
- `FG61` — Serial/lot capture at goods-in
- `FG62` — Per-location min/max + van replenishment
- `FG63` — Inventory-count session workflow
- `FG64` — Battery/sealant expiry tracking
- `FG65` — Demand forecasting reorder quantities
- `FG68` — Crew dispatch calendar + technician capacity for interventions
- `FG69` — Captured client signature (sign-off) on compte-rendu / PV de réception
- `FG70` — Auto warranty handover at RECEPTIONNE
- `FG71` — Per-chantier job-costing roll-up
- `FG72` — Multi-day chantier planning
- `FG73` — Technician day route/itinerary
- `FG74` — Cross-chantier Gantt / milestone timeline
- `FG75` — Roof/drone site-survey attachment surface on the chantier
- `FG76` — Photo-required gate on chantier checklist steps
- `FG77` — Pre-pose readiness check
- `FG78` — Intervention RDV confirmation + reschedule/no-show tracking
- `FG79` — Auto-scaffold the standard intervention chain from chantier type
- `FG80` — Outillage calibration/inspection tracking
- `FG81` — Server-side ticket SLA (response/resolution clocks + breach)
- `FG82` — Maintenance-visit checklist / structured visit report
- `FG83` — Supplier warranty-claim (RMA) workflow
- `FG84` — Per-system production history chart + expected-vs-actual + CSV
- `FG85` — Equipment QR labels + scan-to-equipment/ticket
- `FG86` — Public tokenized "track your SAV request" link
- `FG87` — SAV knowledge base (resolution playbooks)
- `FG88` — Maintenance route/day planning for preventive visits
- `FG89` — Spare-parts forecasting from PieceConsommee history
- `FG90` — Chronic/repeat-failure equipment flag
- `FG91` — SavedReport frontend (CRUD + schedule + optional dashboard pin)
- `FG92` — Period comparison (MoM/YoY) on dashboard & reports
- `FG93` — Sales-rep leaderboard
- `FG94` — Activate custom-field reporting
- `FG95` — PDF export for reports (branded)
- `FG96` — Configurable / per-role dashboard
- `FG97` — Audit-log analytics
- `FG98` — Cohort / seasonality conversion analysis
- `FG99` — Profitability by segment
- `FG100` — Custom fields for Devis / Chantier / Ticket
- `FG101` — Drill-down from report rows/charts to filtered lists
- `FG102` — Webhook delivery log + retry/replay + test ping UI
- `FG107` — Plan comptable CGNC
- `FG108` — Journaux + écritures (comptabilité en partie double)
- `FG109` — Auto-génération des écritures depuis factures/paiements/avoirs/factures fournisseur
- `FG110` — Grand livre
- `FG111` — Balance générale (trial balance)
- `FG112` — Lettrage & rapprochement client/fournisseur
- `FG113` — Compte de Produits et Charges (CPC / P&L marocain)
- `FG114` — Bilan comptable (format CGNC)
- `FG115` — Clôture & verrouillage de période comptable
- `FG116` — Écritures de régularisation / OD manuelles
- `FG117` — À-nouveaux / réouverture d'exercice
- `FG118` — Registre des immobilisations
- `FG119` — Plan d'amortissement (linéaire/dégressif)
- `FG120` — Cession / mise au rebut d'immobilisation
- `FG121` — Référentiel comptes bancaires & caisses
- `FG122` — Position de trésorerie consolidée + projection
- `FG123` — Rapprochement bancaire (relevé ↔ écritures)
- `FG124` — Caisse / petty cash (journal d'espèces)
- `FG125` — Virements internes entre comptes
- `FG126` — Prévisionnel de trésorerie roulant 13 semaines
- `FG127` — Portefeuille d'effets à recevoir (chèques/traites clients)
- `FG128` — Effets à payer fournisseurs
- `FG129` — Bordereau de remise en banque (chèques/effets)
- `FG130` — Gestion des impayés / rejets d'effets
- `FG131` — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur)
- `FG132` — Échéancier & relevé fournisseur (aged payables + statement)
- `FG133` — Campagnes de règlement fournisseurs (payment run)
- `FG134` — Génération de fichier de virement bancaire
- `FG154` — Module RH (app dédiée) + dossier employé
- `FG155` — Type de contrat & dates
- `FG156` — Identité & numéros légaux employé
- `FG157` — Rémunération de base (gated rôle RH)
- `FG158` — Contact d'urgence & coordonnées étendues
- `FG159` — Coffre documents employé
- `FG160` — Référentiels Poste & Département
- `FG161` — Cycle de vie & offboarding
- `FG162` — Soldes & droits à congés (Maroc)
- `FG163` — Demande & validation de congés (workflow)
- `FG164` — Typologie d'absences
- `FG165` — Calendrier d'absences d'équipe → planning
- `FG166` — Pointage / clock-in–out
- `FG167` — Feuilles de temps par chantier (timesheets)
- `FG168` — Heures supplémentaires & calcul majoré
- `FG169` — Planning d'équipes / roster (shifts)
- `FG170` — Registre de présence chantier journalier (émargement)
- `FG171` — Retards & absences injustifiées
- `FG245` — Éditeur de calepinage toiture (placement panneaux)
- `FG246` — Calcul de chaînes (string design) & vérif ratio DC/AC
- `FG247` — Appariement module–onduleur depuis le catalogue
- `FG248` — Pont 3D toiture web → ERP
- `FG249` — Optimisation inclinaison/azimut
- `FG250` — Analyse d'ombrage & profil d'horizon
- `FG251` — Générateur de nomenclature électrique (BOQ)
- `FG252` — Brouillon de schéma unifilaire (SVG)
- `FG253` — Aide au calcul de charge structure toiture
- `FG254` — Bibliothèque de fiches techniques modules/onduleurs (PAN/OND)
- `FG293` — Jalons & phases de projet
- `FG296` — Modèles de projet (templates de chantier-type)
- `FG297` — Contrôle documentaire de projet (plans & révisions)
- `FG298` — Comptes-rendus de réunion de chantier
- `FG350` — Copilote in-app (CopilotPanel)
- `FG351` — Actions en langage naturel — « crée un devis pour… »
- `FG352` — RAG sur documents & manuels (DocQA)
- `FG353` — Résumé automatique d'un fil (lead/chantier/ticket)
- `FG354` — Brouillon de réponse email/WhatsApp
- `FG355` — OCR CIN / contrat / pièce d'identité
- `FG356` — OCR bon de livraison enrichi → réception stock
- `FG357` — Voice-to-text notes terrain
- `FG358` — Photo AI QA sur photos d'installation
- `FG359` — Next-best-action recommandée
- `FG360` — Détection d'anomalies (stock/paiements/fraude)
- `FLOTTE1` — Nouvelle app `apps/flotte` (squelette multi-tenant)
- `FLOTTE2` — Modèle `Vehicule` (immat/marque/énergie/km/valeur/statut)
- `FLOTTE3` — Lien `Vehicule.emplacement_stock` ↔ `stock.EmplacementStock` (via selector)
- `FLOTTE4` — `EnginRoulant` (compteur d'heures, nacelle/groupe/chariot)
- `FLOTTE5` — Référence d'actif commune (Vehicule|Engin) pour entretien/sinistre/doc
- `FLOTTE6` — Référentiels listes (type véhicule/engin, énergie, catégorie permis)
- `FLOTTE7` — `Conducteur` + permis (lien `authentication.User`)
- `FLOTTE8` — `AffectationConducteur` (conducteur↔véhicule datée)
- `FLOTTE9` — Contrôle permis valide/catégorie à l'affectation
- `FLOTTE10` — `ReservationVehicule` + détection de conflit
- `FLOTTE11` — Check-list état des lieux départ/retour (photos)
- `FLOTTE12` — Carnet de carburant (`PleinCarburant`)
- `G5` — Supplier procurement module (a dedicated multi-session module): bons de commande…
- `GED1` — Squelette de l'app `apps/ged` (services/selectors, scoping société)
- `GED2` — Cabinet + Folder arborescent (path matérialisé)
- `GED3` — Document + DocumentVersion (file_key MinIO, checksum/dedupe)
- `GED4` — CRUD dossiers/documents + déplacement (scopé société)
- `GED5` — Navigateur arborescent FR (frontend)
- `GED6` — Liaison polymorphe Document↔objet métier (étend `records.ALLOWED_TARGETS`)
- `GED7` — Migration des `records.Attachment` existants (réutilise file_key)
- `GED8` — Coffre-fort par employé/client (ACL owner+admin)
- `GED9` — Taxonomie de tags
- `GED10` — Métadonnées typées configurables (réutilise `customfields`)
- `GED11` — Recherche plein-texte Postgres (SearchVector + GIN)
- `GED12` — Index OCR + recherche sémantique (pgvector, key-gated no-op)
- `GED13` — Filtres & recherche avancée (frontend)
- `GED14` — Aperçu inline multi-format (proxy même-origine)
- `GED15` — Versionnage + historique + restauration de version
- `GED16` — Check-out / check-in (verrouillage)
- `KB1` — App `kb` + `KbArticle` (titre/corps/catégorie/tags, company FK)
- `KB2` — Versionnage des articles + statut (brouillon/publié/obsolète)
- `KB3` — Recherche plein-texte + filtres par catégorie/tag
- `KB4` — Lien article ↔ produit/équipement/type d'intervention (contextuel sur SAV/chantier)
- `KB5` — Procédures/SOP d'installation & dossiers ONEE/82-21 (gabarits seedés)
- `LITIGE1` — App `litiges` + modèle `Reclamation` (type, gravité, source FK polymorphe, statut)
- `LITIGE2` — Workflow statut (ouverte→en_traitement→résolue/rejetée) + chatter
- `LITIGE3` — Litige financier ↔ recouvrement : suspendre les relances d'une facture en litige
- `LITIGE4` — Litige qualité ↔ QHSE : lien NCR + audit fin de chantier
- `M1` — Replace every load-time cross-app model import in the core apps with Django string FK…
- `M2` — Make `services.py` / `selectors.py` the only cross-app entry point: route cross-app…
- `M3` — Add an `import-linter` contract run in CI that forbids import cycles among the core…
- `M4` — Formalise the three layers (foundation: authentication/roles/records/customfields/core…
- `M5` — Use the empty `core/` app for shared primitives: move the tenant base mixin and the…
- `M6` — Replace the hottest direct cross-app calls with a small domain-event layer (e.g. emit…
- `M7` — Split the god-files (no behaviour change): turn the large `views.py` into a `views/`…
- `N53` — Client energy-yield report PDF (French) from ESTIMATED / MANUAL data (nameplate kWc +…
- `N76` — Daily & weekly digest notification for Reda & Meryem (jobs to plan, quotes awaiting…
- `N79` — Saved-reports & custom-views capability: save filtered/grouped views of any major…
- `N91` — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception…
- `N92` — PWA web push notifications for high-priority events from the notification engine
- `N96` — Account security: optional 2FA, visible active sessions with revoke, forced…
- `N108` — Attachment upload crashes with NoSuchBucket (HTTP 500)
- `N109` — Activate Web Push end-to-end (complete N92)
- `N110` — Admin cannot change a user's role manually (Administration → Utilisateurs → edit…
- `PAIE1` — App `paie` + permissions `paie_voir`/`paie_gerer`
- `PAIE2` — `ParametrePaie` : constantes par société versionnées (SMIG/SMAG, plafond CNSS, taux…
- `PAIE3` — Valeurs légales par défaut (taux/plafonds 2026) + validation fondateur
- `PAIE4` — `BaremeIR` : tranches + somme à déduire, versionné par date d'effet
- `PAIE5` — Barème IR officiel + déductions charges de famille
- `PAIE6` — `Rubrique` paramétrable (gain/retenue/cotisation, flags imposable/CNSS/AMO/CIMR, compte)
- `PAIE7` — Catalogue de rubriques standard (transport/panier/ancienneté/HS…) — seed idempotent
- `PAIE8` — `ProfilPaie` (OneToOne→DossierEmploye) : type rémunération, salaire base, affiliations…
- `PAIE9` — `RubriqueEmploye` : rubriques récurrentes par employé
- `PAIE10` — `PeriodePaie` : run mensuel + statuts brouillon→calculée→validée→clôturée
- `PAIE11` — `ElementVariable` + import depuis RH (heures/HS/absences/primes)
- `PAIE12` — Moteur de calcul du bulletin (`services.calculer_bulletin`)
- `PAIE13` — Salaire de base multi-profils (mensuel/journalier/forfait/horaire) + proration
- `PAIE14` — Heures supplémentaires majorées (25/50/100 % jour/nuit/férié)
- `PAIE15` — Prime d'ancienneté barème (5/10/15/20/25 %)
- `PAIE16` — Avantages en nature & indemnités imposables vs non-imposables (plafonds)
- `PAIE17` — `BulletinPaie` + `LigneBulletin` (snapshot immuable une fois validé)
- `PAIE18` — CNSS plafonnée (part salariale & patronale)
- `PAIE19` — AMO (sans plafond) salariale & patronale
- `PROJ1` — Modèle `Projet`/Programme multi-chantiers + `ProjetChantier`
- `PROJ2` — Liens projet → devis/factures/tickets/achats (string-FK via selectors)
- `PROJ3` — Machine à états du projet (propre, jamais STAGES.py)
- `PROJ4` — Phases de projet (étude/appro/pose/MES/réception)
- `PROJ5` — Tâches & sous-tâches (WBS)
- `PROJ6` — Dépendances de tâches FS/SS/FF/SF + lag
- `PROJ7` — Jalons (+ `facturation_pct`)
- `PROJ8` — Calcul du chemin critique (CPM) + marges
- `PROJ9` — Roll-up d'avancement (pondéré par charge)
- `PROJ10` — API planning Gantt
- `PROJ11` — Drag-reschedule des tâches (recalcule les successeurs)
- `PROJ12` — Calendrier projet (jours ouvrés/fériés)
- `PROJ13` — Baseline de planning (plan vs réel)
- `PROJ14` — Détection des retards (tâches/jalons à risque)
- `PROJ15` — Profil ressource & équipes (RH-léger, `cout_horaire` interne)
- `PROJ16` — Affectation des ressources (User/équipe/camionnette/machine)
- `PROJ17` — Indisponibilités ressources (congé/formation/arrêt)
- `QHSE1` — App QHSE + socle multi-tenant
- `QHSE2` — ITP : `PlanInspectionModele` + `PointControleModele` (phase/type relevé/hold-point)
- `QHSE3` — Seed ITP solaire par type d'installation
- `QHSE4` — `PlanInspectionChantier` + `ReleveControle` (valeur/conforme/photo)
- `QHSE5` — Auto-conformité des relevés mesurés (vs min/max attendu)
- `QHSE6` — Points d'arrêt bloquants (hold points) gating l'avancement chantier
- `QHSE7` — Relevé courbe I-V par string
- `QHSE8` — Photos de contrôle (avant/pendant/après) via `records.Attachment`
- `QHSE9` — `NonConformite` (NCR : gravité/origine/source/photos)
- `QHSE10` — `ActionCorrectivePreventive` (CAPA) + cause racine
- `QHSE11` — Pont réserve (`installations.Reserve`) → NCR
- `QHSE12` — Relances CAPA en retard (notifications/digest)
- `QHSE13` — Vérification d'efficacité CAPA (clôture conditionnée)
- `QHSE14` — Chatter QHSE (NCR/CAPA/Incident/Audit)
- `QHSE15` — `GrilleAudit` + `CritereAudit` pondérés
- `QHSE16` — `Audit` + `ReponseCritere` + score (→ NCR)
- `QHSE17` — Grille de notation fin de chantier (gate clôture)
- `QHSE18` — `ProcedureQualite` versionnée (docs qualité GED)
- `AG1` — Agent action-registry framework + catalogue endpoint
- `AG2` — Registry-driven agent tools + propose→confirm protocol (FastAPI)
- `AG3` — Confirmation + result cards in the assistant chat
- `AG4` — Quote (devis) agent actions
- `AG5` — Invoicing & payment agent actions
- `AG6` — CRM lead agent actions
- `AG7` — Stock agent actions
- `AG8` — SAV agent actions (migrate the existing ticket tool)
- `AG9` — Installations agent actions (migrate the chantier/visite tools)
- `AG10` — Voice transcription endpoint (Groq Whisper, reuses GROQ_API_KEY)
- `AG11` — Voice input + spoken answers in the assistant chat
- `AG12` — Hands-free conversation mode (continuous listen↔speak loop)
- `F120` — Palette de marque en OKLCH (sans régression visuelle)
- `F121` — Échelle typographique + chiffres tabulaires généralisés
- `F122` — Discipline d'élévation + anneau de focus de marque
- `F123` — Mode sombre = élévation par la clarté
- `G10` — Lead-source capture (G10 first half): (1) add nullable fields to the lead model —…
- `G124` — Tooltip thémable
- `G125` — Bouton « six états » + libellés d'icônes
- `G126` — États de chargement/erreur des sélecteurs
- `G127` — Champ de formulaire : indice + erreur ensemble
- `G128` — Tokeniser DatePicker / TimePicker / Calendar
- `H129` — Passe visuelle « tableau premium »
- `H130` — Épinglage de colonnes
- `H131` — Affordances de ligne
- `H132` — Barre d'actions groupées flottante
- `H133` — Performance perçue des tableaux
- `I134` — Palette de commandes ⌘K de premier plan (sans nouvelle dépendance)
- `I135` — Sidebar « calme »
- `I136` — Polissage de l'en-tête
- `I137` — Fil d'Ariane accessible + tronqué
- `I138` — Culture des raccourcis clavier (déjà présent)
- `J139` — CRM Clients : refonte
- `J140` — CRM Leads : tokens de couleur + vues + STAGES
- `J141` — Ventes Devis : polissage liste/détail
- `J142` — Stock : refonte
- `J143` — Installations (chantiers) : refonte
- `J144` — SAV : refonte
- `J145` — Admin Utilisateurs → DataTable
- `J146` — Reporting/Journal : tableaux HTML hérités → DataTable
- `K147` — Kit de primitives graphiques (recharts, marque)
- `K148` — Dashboard : refonte avec le kit
- `K149` — Formatage des nombres (reporting/dashboard)
- `L150` — Adoption des tokens de mouvement
- `L151` — UI optimiste + statut d'enregistrement automatique
- `L152` — Helper confirmation + toast sur mutation
- `L153` — Discipline des états de chargement
- `M154` — Repli tableau → cartes sur mobile
- `M155` — Passe tactile + zones sûres
- `M156` — Polissage de la nav basse
- `M157` — Polissage PWA iOS
- `M158` — Sheet sur mobile pour créer/éditer
- `N159` — Focus jamais masqué + anneaux visibles (WCAG 2.4.11)
- `N160` — Accessibilité du DataTable
- `N161` — Accessibilité des graphiques
- `N162` — Alternative au glisser + taille de cible (2.5.7 / 2.5.8)
- `N163` — Mouvement réduit correct + tests axe
- `O164` — Virtualiser les grandes listes
- `O165` — Découpage des routes + chargement différé
- `O166` — Largeurs de colonnes mémoïsées (60 fps)
- `P167` — Unifier sur UN seul tableau
- `P168` — Cohérence des icônes
- `P169` — Supprimer les `style={}` inline
- `P170` — Guide de style vivant (/ui)
- `P171` — Migrer le moteur `DataTable` vers `@tanstack/react-table` (déjà installé) derrière…
- `Q1` — `Devis.roof_layout` storage + endpoints
- `Q2` — Client roof-POINT capture on the Lead (pin, not drawing)
- `Q3` — `build_devis_from_layout()` service (server-side)
- `Q4` — Roof-render image storage
- `Q5` — Feed roof render + layout figures into the quote data (additive/guarded)
- `Q6` — Tokenized web-proposal data endpoint
- `Q7` — E-signature acceptance (reuse the existing stamp)
- `QJ1` — Proposal open-tracking
- `QJ2` — Instant seller notification
- `QJ3` — Scheduler infra (Celery beat)
- `QJ4` — Automated devis follow-up cadence (relance)
- `QJ5` — Auto quote-expiry + funnel hygiene
- `QJ6` — Rule-based lead scoring + hot-list sort
- `QJ7` — Auto-advance NEW→CONTACTED
- `QJ8` — Webhook dedupe beyond 60 s + secondary key
- `QJ9` — Conversion attribution + Meta CAPI wiring
- `QJ10` — Stronger e-sign legal trail (loi 53-05)
- `QJ11` — Bind the signature to the lead contact
- `QJ12` — Financing data in the quote
- `QJ13` — 82-21 self-consumption savings + tariff tables in the quote engine
- `QJ14` — Server-side proposal email send (SendGrid)
- `QJ15` — Quote variants / multi-option comparison
- `QJ16` — Reusable quote templates / presets
- `QJ17` — `from-layout` idempotency + pre-flight composition check
- `QJ18` — Commercial dashboard
- `QJ19` — Win/loss + per-source close-rate report
- `QJ20` — Self-booking site-visit scheduler
- `QJ21` — Richer layout payload fidelity
- `QJ22` — Signed-proposal artifact + prominent "signé" surfacing
- `QJ23` — [GATED: paid — WhatsApp Business API]
- `QJ24` — [GATED: paid — payment gateway]
- `QJ25` — [GATED: research — auto roof detection]
- `S1` — `apps/chat` app skeleton + core models
- `S2` — Attachment, reaction, mention & pin models
- `S3` — Serializers, viewsets, membership permissions & company scoping
- `S4` — Read-state & unread counts
- `S5` — Message search
- `S6` — Attachment & voice-memo upload
- `S7` — Reactions & pinned messages
- `S8` — Share an ERP record into a conversation
- `S9` — Notifications + per-conversation mute (reuse `notify()` + Web Push)
- `S10` — Self-hosted Whisper transcription endpoint (FastAPI)
- `S11` — Django voice-transcription pipeline
- `S12` — Chat API client + Redux slice + smart-polling hook
- `S13` — `/messages` route, nav entry, header chat icon + two-pane shell
- `S14` — Conversation list pane
- `S15` — Message thread pane
- `S16` — Composer: text, @mentions, attachments, edit/delete
- `S17` — Voice memos: record, play, transcript
- `S18` — Reactions & pinned UI
- `S19` — Share-a-record UI
- `S20` — New-DM / new-channel / manage-members modals
- `U1` — Lead modal: « Mettre à jour » keeps the window open + generate-devis stays inline
- `U2` — Regression: mouse-wheel scrolling broke across the ERP
- `U3` — Mobile: the top of the app overlaps (header stacks on itself / on content)
- `U4` — WhatsApp-send a devis flips it to « envoyé » (and advances the lead funnel)
- `U5` — Surface generated factures (and the bon-commande) in the Devis list/detail
- `U6` — Auto-create the chantier (installation) when a devis is accepted
- `U7` — Hide/badge superseded devis revisions in the list
- `U8` — Reflect the bon-commande state in the devis detail
- `U9` — Stock reservation on the direct generer-facture (échéancier) path
- `U10` — Reset the relance (dunning) escalation when a facture is fully paid
- `U11` — Lead-funnel sanity when a post-acceptance devis is later refused (DECISION)
- `U12` — Direct lead link for factures & bons-commande (efficient lead-document view)
- `U13` — Bug: uploading a user profile picture does not work
- `U14` — Bug: the new « Documents (GED) » menu does nothing usable

**Open — to build (454)**

- `COMPTA2` — Mapping document→compte par société (familles/TVA/modes de paiement → comptes)
- `COMPTA3` — Comptes auxiliaires tiers (dérivés de `crm.Client`/`stock.Fournisseur` via selectors)
- `COMPTA4` — Journaux paramétrables (VTE/ACH/BNK/CSH/OD/AN) + séquences
- `COMPTA5` — Multi-exercice & périodes comptables
- `COMPTA6` — Validation légale du plan/format CGNC (fiduciaire)
- `COMPTA7` — Écriture en partie double équilibrée (Σ débit = Σ crédit)
- `COMPTA8` — Saisie d'OD manuelle (régularisations/provisions/corrections)
- `COMPTA9` — Numérotation séquentielle des pièces (via `references.py`, jamais count()+1)
- `COMPTA10` — Pièces justificatives sur écriture
- `COMPTA11` — Extourne / contre-passation (jamais supprimer une écriture validée)
- `COMPTA12` — Auto-écriture depuis facture client (3421/71xx/4455x), réconcilie au journal-ventes
- `COMPTA13` — Auto-écriture depuis avoir
- `COMPTA14` — Auto-écriture depuis paiement client (514x/516x/caisse)
- `COMPTA15` — Auto-écriture depuis facture fournisseur (61xx/3455x/4411)
- `COMPTA16` — Auto-écriture depuis paiement fournisseur
- `COMPTA17` — Contrat de posting paie & immobilisations (signatures de service)
- `COMPTA18` — Statut-préservation & idempotence du posting (test-guarded)
- `COMPTA19` — Grand livre (détail par compte + solde courant + lettrage, export xlsx)
- `COMPTA20` — Balance générale (trial balance — distincte de la balance âgée existante)
- `COMPTA21` — Balance auxiliaire clients/fournisseurs
- `COMPTA22` — Lettrage clients/fournisseurs (manuel + auto-suggest)
- `COMPTA23` — Référentiel `CompteTresorerie` (banque/caisse/RIB/devise) lié au GL
- `COMPTA24` — Journal de caisse (petty cash) + clôture de caisse
- `COMPTA25` — Virements internes (écriture à deux jambes)
- `COMPTA26` — Import relevé bancaire & rapprochement
- `COMPTA27` — CPC (Compte de Produits et Charges)
- `COMPTA28` — Bilan (format CGNC)
- `COMPTA29` — ESG / états de synthèse + ETIC
- `COMPTA30` — Tableau de bord financier directeur (P&L/cash/DSO/DPO/marge)
- `COMPTA31` — Clôture mensuelle & verrouillage de période
- `COMPTA32` — Clôture d'exercice & génération des à-nouveaux
- `COMPTA33` — Réouverture / correction d'exercice clos (audité)
- `COMPTA34` — Préparation déclaration TVA (régime débit/encaissement)
- `COMPTA35` — Relevé de déductions détaillé (annexe TVA)
- `COMPTA36` — Export FEC (format DGI auditable)
- `COMPTA37` — Liasse fiscale & export fiduciaire (Sage/CEGID ; Odoo JSON-2 only)
- `COMPTA38` — Comptabilité analytique / centres de coût (axe chantier/agence/marché/commercial)
- `COMPTA39` — Piste d'audit comptable inaltérable (écritures hash-chaînées)
- `COMPTA40` — Séparation des tâches (saisie vs validation vs clôture)
- `CONTRAT13` — `RegleApprobation` (par montant/type)
- `CONTRAT14` — `EtapeApprobation` + workflow d'approbation interne
- `CONTRAT15` — Chatter/journal du contrat (audit des transitions)
- `CONTRAT16` — `SignatureContrat` (point e-sign + statut signé)
- `CONTRAT17` — Transition automatique signé→actif sur signature
- `CONTRAT18` — `VersionContrat` (versionnage immuable des rendus)
- `CONTRAT19` — Dépôt en GED des versions & PDF signés
- `CONTRAT20` — Dates clés (début/fin/préavis) + tacite reconduction
- `CONTRAT21` — Calcul des échéances & contrats « à renouveler »
- `CONTRAT22` — `AlerteContrat` + rappels via notifications
- `CONTRAT23` — Renouvellement (manuel + reconduction tacite)
- `CONTRAT24` — `Avenant` (amendements → nouvelle version)
- `CONTRAT25` — `Resiliation` (motif/préavis/solde)
- `CONTRAT26` — `Obligation`/`JalonContrat` (livrables & jalons)
- `CONTRAT27` — SLA & pénalités (taux SLA, valeur pénalité)
- `CONTRAT28` — Retenue de garantie (suivi de libération)
- `CONTRAT29` — Registre des cautions/garanties liées
- `CONTRAT30` — `EcheancierContrat` + `LigneEcheance`
- `CONTRAT31` — Lien facturation récurrente (via `ventes.services`)
- `CONTRAT32` — `IndexationPrix` (indexation/révision de prix)
- `CONTRAT33` — Tableau de bord contrats (actifs/à renouveler/en risque/valeur·MRR)
- `CONTRAT34` — `PieceConformite` (pièces obligatoires & attestations)
- `CONTRAT35` — Reporting valeur contractuelle & taux de renouvellement
- `DC1` — Le moteur de devis premium imprime l'identité société en dur
- `DC2` — Constantes ROI en dur dans le moteur
- `DC3` — L'étude industrielle ignore les constantes injectées
- `DC4` — `CompanyProfile.tva_panneaux` est un champ mort
- `DC5` — Tarif ONEE/productible en double
- `DC6` — TVA 10/20 hardcodée dans `solar.js`
- `DC7` — `Produit.tva` doit être la source autoritaire du taux de ligne
- `DC8` — Triplication de la classification produit + règle 10/20
- `DC9` — Tableau GHI dupliqué
- `DC10` — `LigneAvoir.produit` nullable (SET_NULL)
- `DC11` — `Devis.etude_params` sans provenance
- `DC12` — Profil site/énergie re-saisi à chaque devis
- `DC13` — Chantier sans lead : `site_adresse`/GPS non repris
- `DC14` — Parrainage : `filleul_nom` peut diverger du FK
- `DC15` — `Fournisseur` n'a ni ICE/IF/RC/RIB
- `DC16` — Montants `FactureFournisseur` saisis à la main
- `DC19` — Dates relance/maintenance non « jours ouvrés »
- `DC20` — UN référentiel `CompteTresorerie`
- `DC21` — UN plan comptable `CompteComptable` (CGNC)
- `DC22` — UNE table de mapping comptable
- `DC23` — UN référentiel de taux de TVA + un selector `tva_par_taux` unique
- `DC24` — UN référentiel d'axes analytiques
- `DC25` — UNE source devise + taux de change
- `DC26` — UN référentiel calendrier : jours ouvrés + fériés marocains
- `DC27` — UNE taxonomie de tags transversale
- `DC28` — UN résolveur `cout_achat_courant`
- `DC30` — Compta comptes auxiliaires tiers
- `DC31` — Contrats
- `DC32` — Portail client (FG228)
- `DC33` — GED
- `DC34` — Sous-traitant : pas de master fournisseur parallèle
- `DC35` — Datasheet/fiches techniques (FG254)
- `DC36` — Kit/BOM (FG66) & kitting (FG328)
- `DC37` — Serial-at-goods-in (FG61)
- `DC38` — Landed cost (FG316/FG67)
- `DC39` — Référence unique pour tout nouveau module
- `DC40` — Décision modèle `Equipe`
- `DC41` — Permis & habilitations : un seul foyer
- `DC42` — Personnes dans QHSE/Paie/Projet
- `FG15` — Broaden audit-trail coverage + a generic soft-delete/restore standard
- `FG16` — In-app onboarding / setup checklist + contextual help
- `FG18` — Settings-audit completeness
- `FG19` — Read-only org-chart / team hierarchy view
- `FG20` — Per-field / sensitive-data role permissions
- `FG21` — User invite / self-set-password onboarding
- `FG22` — Per-company password policy & account lockout
- `FG23` — Security-events view + failed-login alerting
- `FG24` — Settings config export/import between companies
- `FG25` — Configurable approval workflows beyond discount
- `FG26` — Data-retention / GDPR tooling
- `FG66` — Kit/BOM as a sellable catalogue product
- `FG67` — FIFO / landed-cost valuation option
- `FG103` — More webhook events
- `FG104` — Public API filtering, ordering & incremental sync
- `FG105` — Public API documentation page
- `FG106` — OCR → draft lead / draft devis action
- `FG135` — Notes de frais & remboursements employés
- `FG136` — Indemnités kilométriques & per-diem chantier
- `FG137` — Préparation de la déclaration TVA
- `FG138` — Relevé de déductions détaillé (annexe TVA)
- `FG139` — Retenue à la source (RAS) sur honoraires/prestations
- `FG140` — Aide au calcul de l'IS
- `FG141` — Export FEC (fichier des écritures comptables)
- `FG142` — Trousse liasse fiscale (états de synthèse)
- `FG143` — Déclaration des honoraires / état 9421
- `FG144` — Calcul du timbre fiscal sur encaissements espèces
- `FG145` — Retenue de garantie & cautions sur marchés (RG / bonne fin)
- `FG146` — Reconnaissance du revenu par avancement (% completion)
- `FG147` — Produits constatés d'avance & travaux en cours (WIP)
- `FG148` — Campagnes de versement des commissions (payout run)
- `FG149` — Budgets annuels & suivi budget-vs-réalisé
- `FG150` — Comptabilité analytique / centres de coût
- `FG151` — Tableau de bord financier directeur
- `FG152` — Provisions pour créances douteuses
- `FG153` — Inter-sociétés / consolidation multi-entités
- `FG172` — Matrice de compétences
- `FG173` — Habilitations électriques (B1V/BR/B2V/H0…)
- `FG174` — Certifications spécifiques
- `FG175` — Alertes d'expiration (habilitations/certifs/docs)
- `FG176` — Garde d'affectation par habilitation
- `FG177` — Visite médicale du travail
- `FG178` — Catalogue & dotation EPI
- `FG179` — Suivi péremption/contrôle des EPI
- `FG180` — Émargement de remise EPI (signature)
- `FG181` — Registre HSE & accidents du travail
- `FG182` — Presqu'accidents (near-miss)
- `FG183` — Causeries sécurité / toolbox talks
- `FG184` — Analyse de risques chantier (plan de prévention)
- `FG185` — Tableau de bord HSE
- `FG186` — Permis de travail (hauteur/électrique/consignation)
- `FG187` — Gestion de la formation
- `FG188` — Plan & registre de formation
- `FG189` — Recrutement (ATS-lite)
- `FG190` — Entretiens & évaluations annuelles
- `FG191` — Disciplinaire & sanctions
- `FG192` — Éléments variables de paie (export)
- `FG193` — Primes & indemnités
- `FG194` — Ordre de mission (déplacement chantier)
- `FG195` — Avances sur salaire
- `FG196` — Bulletin de paie (lecture seule)
- `FG197` — Suivi des permis de conduire & habilitation à conduire
- `FG198` — Affectation conducteur ↔ véhicule
- `FG199` — Portail self-service employé
- `FG200` — Cockpit RH (effectifs & coûts)
- `FG201` — Campagnes email & SMS
- `FG202` — Séquences de relance automatisées (drip/nurture)
- `FG203` — Récupération des devis abandonnés
- `FG204` — Tableau d'attribution multi-touch
- `FG205` — Tracking d'ouverture des ShareLink devis/facture
- `FG206` — Constructeur de formulaires / landing pages multiples
- `FG207` — Capture de leads via WhatsApp (catalogue/chatbot)
- `FG208` — Journal d'appels & click-to-call
- `FG209` — Promotions & campagnes de remise
- `FG210` — Bibliothèque de modèles de devis
- `FG211` — Configurateur d'options guidé (guided selling)
- `FG212` — Comparateur de versions de devis (UI)
- `FG213` — Routage d'approbation des configurations non-standard
- `FG214` — E-catalogue à prix publics
- `FG215` — Bibliothèque de documents de proposition
- `FG216` — Simulateur public « configurez votre kit » → lead
- `FG217` — Simulation de financement dans le devis (crédit/leasing)
- `FG218` — Offres de banques/partenaires de financement
- `FG219` — Ligne d'incitation / subvention (Tatwir/MASEN)
- `FG220` — Paiement échelonné (type Tayssir) sur facture
- `FG221` — Comparateur cash vs financement
- `FG222` — Gestion des appels d'offres (public/privé)
- `FG223` — Bordereau des prix (BOQ) d'appel d'offres
- `FG224` — Suivi des cautions & garanties de soumission
- `FG225` — Dossier de soumission (pièces administratives)
- `FG226` — Échéancier & alertes de deadline d'AO
- `FG227` — Analyse gagné/perdu des appels d'offres
- `FG228` — Portail self-service client
- `FG229` — Acceptation/e-signature de devis dans le portail
- `FG230` — Paiement en ligne des factures (portail)
- `FG231` — Téléchargement docs & dépôt factures ONEE par le client
- `FG232` — Suivi d'avancement du chantier côté client
- `FG233` — Ouverture de ticket SAV depuis le portail
- `FG234` — Portail apporteurs / sous-revendeurs
- `FG235` — Suivi des commissions partenaires
- `FG236` — Gestion des territoires / zones commerciales
- `FG237` — Annuaire & onboarding des installateurs partenaires
- `FG238` — Enquêtes NPS / satisfaction post-installation
- `FG239` — Capture d'avis/témoignages + push Google Reviews
- `FG240` — Programme de fidélité / parrainage étendu
- `FG241` — Moteur d'upsell / cross-sell
- `FG242` — Suivi des concurrents sur deals perdus
- `FG243` — Pipeline de renouvellement de contrats O&M
- `FG244` — Abonnements de monitoring
- `FG255` — Dimensionnement borne de recharge VE
- `FG256` — Étude de stockage & dispatch batterie (backup)
- `FG257` — Simulation bankable P50/P90 avec modèle de pertes
- `FG258` — Profil d'autoconsommation horaire depuis courbe de charge
- `FG259` — Économie net-metering / injection surplus (loi 13-09/MT)
- `FG260` — Modélisation escalade tarifaire ONEE sur 20–25 ans
- `FG261` — Optimisation puissance souscrite (C&I)
- `FG262` — Modélisation dégradation modules sur la durée
- `FG263` — Modèle financier PPA / tiers-investisseur
- `FG264` — Rendement pompage par cycle de marche
- `FG265` — Flux d'irradiance/météo pour simulations
- `FG266` — Comparateur de scénarios de devis
- `FG267` — Packs documentaires réglementaires par régime
- `FG268` — Checklists & échéances de soumission ONEE/raccordement
- `FG269` — Suivi de soumission & navette opérateur
- `FG270` — Éligibilité & suivi des subventions/incitations
- `FG271` — Workflow de régularisation Article 33 / déclarations 82-21
- `FG272` — Générateur de déclaration de raccordement BT/MT
- `FG273` — Calendrier réglementaire & alertes d'expiration de dossiers
- `FG274` — Protocole d'essais de mise en service IEC 62446
- `FG275` — Capture de courbe I-V par string
- `FG276` — Pack documentaire « as-built »
- `FG277` — Attestation/certificat de conformité électrique
- `FG278` — Test de performance de réception (PR initial)
- `FG279` — Analytique O&M : PR, disponibilité, soiling, dégradation
- `FG280` — Gestion fine des alarmes/défauts onduleur
- `FG281` — Tableau de bord parc/flotte multi-systèmes
- `FG282` — Suivi de garantie de production & compensation de manque
- `FG283` — Détection & suivi de pertes par salissure
- `FG284` — Suivi garantie vs courbe de dégradation fabricant
- `FG285` — Adaptateurs monitoring supplémentaires (SolarEdge/Sungrow/Solis)
- `FG286` — Reporting CO₂ évité par système & cumulé
- `FG287` — Certificats d'énergie renouvelable / attestations RE
- `FG288` — Tableau de bord environnemental client (portail)
- `FG289` — Rapport O&M périodique automatisé (PDF + email)
- `FG290` — Registre des garanties matériel & échéancier de fin par parc
- `FG291` — Programme / Projet multi-chantiers
- `FG292` — Tâches & sous-tâches de projet avec dépendances
- `FG294` — Budget projet vs réel (engagé/dépensé)
- `FG295` — P&L de projet consolidé
- `FG299` — Plan de charge des équipes (capacité vs affecté)
- `FG300` — Détection de conflits d'affectation
- `FG301` — Nivellement de charge (resource levelling)
- `FG302` — Calendrier de disponibilité ressources
- `FG303` — Planning des camionnettes (capacité véhicule)
- `FG304` — Référentiel sous-traitants
- `FG305` — Ordres de travaux sous-traitant
- `FG306` — Factures & règlements sous-traitant
- `FG307` — Attestations & assurances sous-traitant
- `FG308` — Évaluation de performance sous-traitant
- `FG309` — Retenue de garantie sur sous-traitant
- `FG310` — Demande d'achat (réquisition) → approbation
- `FG311` — RFQ multi-fournisseurs & comparatif d'offres
- `FG312` — Paliers d'approbation de BCF par seuil
- `FG313` — Contrôle budgétaire à la commande
- `FG314` — Commandes-cadres / contrats annuels (blanket orders)
- `FG315` — Suivi import / dédouanement
- `FG316` — Frais d'import & coût de revient débarqué (landed cost)
- `FG317` — Réceptionné-non-facturé (GR/IR)
- `FG318` — Contrats & accords de prix fournisseur
- `FG319` — Emplacements fins zone/allée/casier (bin locations)
- `FG320` — Rangement guidé (put-away)
- `FG321` — Bons de prélèvement (pick list) par chantier
- `FG322` — Colisage / préparation (pack)
- `FG323` — Suivi du stock par numéro de série en entrepôt
- `FG324` — Sessions de comptage tournant (cycle count ABC)
- `FG325` — Demande de transfert inter-emplacements (workflow)
- `FG326` — Réapprovisionnement multi-dépôts
- `FG327` — Stock en consignation / emballages consignés
- `FG328` — Pré-assemblage / kitting magasin
- `FG329` — Planification des livraisons (dépôt → site)
- `FG330` — Preuve de livraison (POD)
- `FG331` — Transporteurs & tarifs de transport
- `FG332` — Optimisation de tournée de livraison multi-sites
- `FG333` — Réservation à la livraison (dépôt vs site)
- `FG334` — Référentiel véhicules (flotte)
- `FG335` — Échéances réglementaires véhicule
- `FG336` — Carnet de carburant (suivi gasoil)
- `FG337` — Planning d'entretien véhicule
- `FG338` — Journal kilométrique & affectation conducteur
- `FG339` — Coût total de possession du véhicule
- `FG340` — Parc de machines & équipements propres
- `FG341` — Compteur d'heures & maintenance des machines
- `FG342` — Location de matériel (interne & externe)
- `FG343` — Plans d'inspection (ITP / plan de contrôle)
- `FG344` — Points d'arrêt (hold points)
- `FG345` — Non-conformités (NCR)
- `FG346` — Actions correctives & préventives (CAPA)
- `FG347` — Registre de conformité électrique / essais
- `FG348` — Inductions sécurité / accueil sur site
- `FG349` — Audit qualité de fin de chantier (scoring)
- `FG361` — Prévision de ventes / demande
- `FG362` — Score de probabilité de gain (win-probability)
- `FG363` — Score de churn / risque client
- `FG364` — Prévision de réappro stock
- `FG365` — Prédiction de retard de paiement
- `FG366` — Moteur de workflow multi-étapes (BPM) + SLA/escalades
- `FG367` — Conditions multi-critères & branches dans les règles
- `FG368` — UI de gestion des tâches planifiées (jobs)
- `FG369` — Bibliothèque de modèles de workflow
- `FG370` — Passerelle de paiement CMI / Payzone
- `FG371` — Passerelle SMS marocaine
- `FG372` — E-signature (Yousign/DocuSign)
- `FG373` — Email entrant IMAP → leads/tickets
- `FG374` — Sync calendrier Google/Outlook (2-way)
- `FG375` — Géocodage & cartes (Maps)
- `FG376` — Connecteur Zapier / Make
- `FG377` — Pont comptable Sage / CEGID (one-way)
- `FG378` — Connecteur Odoo Compta (JSON-2, 2-way)
- `FG379` — Open banking (flux bancaire automatique)
- `FG380` — Constructeur de tableau croisé (pivot)
- `FG381` — Constructeur de graphiques/dashboards sans-code
- `FG382` — BI embarqué — explorateur de données
- `FG383` — Extraits planifiés vers entrepôt/SFTP/S3
- `FG384` — Scan code-barres / QR (BarcodeDetector)
- `FG385` — Capture photo caméra en direct
- `FG386` — Mode terrain hors-ligne (offline queue)
- `FG387` — Application mobile native (Capacitor)
- `FG388` — Corbeille / restauration (soft-delete + undo)
- `FG389` — Édition en masse partout (bulk edit)
- `FG390` — Champs personnalisés calculés (formules)
- `FG391` — Flags de fonctionnalités / modules par tenant
- `FG392` — Thème white-label par tenant
- `FG393` — Éditeur de modèles imprimables/brandés
- `FG394` — Consentement & DSR (loi 09-08 / CNDP)
- `FG395` — Sauvegarde/restauration en libre-service
- `FG396` — Monitoring d'erreurs (Sentry)
- `FG397` — Page d'état / santé système
- `FG398` — Plans de tarif API & analytics d'usage
- `FG399` — Journal des nouveautés in-app (changelog)
- `FLOTTE13` — Calcul conso L/100 km (et kWh/100 km)
- `FLOTTE14` — Cartes carburant & alertes anomalie (km incohérent/fraude)
- `FLOTTE15` — Plans d'entretien préventif (km/date/heures)
- `FLOTTE16` — Génération d'échéances d'entretien dues + alertes
- `FLOTTE17` — Ordres de réparation + atelier/garage + coûts
- `FLOTTE18` — Pneumatiques & pièces
- `FLOTTE19` — `EcheanceReglementaire` (modèle générique)
- `FLOTTE20` — Vignette / TSAV (barème CV/énergie, référentiel éditable)
- `FLOTTE21` — Assurance auto (police/échéance/attestation/franchise)
- `FLOTTE22` — Visite technique (validité paramétrable)
- `FLOTTE23` — Carte grise & autorisation de circulation (GED)
- `FLOTTE24` — Moteur d'alertes d'échéances réglementaires (J-30/15/7/échu)
- `FLOTTE25` — `Sinistre` (accident/constat/assurance)
- `FLOTTE26` — `Infraction` / PV de circulation
- `FLOTTE27` — Point d'intégration télématique (no-op sans fournisseur)
- `FLOTTE28` — Suivi de position & trajets télématiques
- `FLOTTE29` — Journal kilométrique & trajets par chantier (via `installations.selectors`)
- `FLOTTE30` — Amortissement (lien immobilisations)
- `FLOTTE31` — Coût total de possession (TCO) par véhicule (interne)
- `FLOTTE32` — Pool de véhicules & demandes
- `FLOTTE33` — Éco-conduite & CO₂
- `FLOTTE34` — Documents véhicule (GED)
- `FLOTTE35` — Tableau de bord flotte (dispo/échéances/coûts/conso)
- `GED17` — Cycle de vie documentaire (brouillon→revue→approuvé→archivé→obsolète)
- `GED18` — Workflow d'approbation/revue
- `GED19` — ACL par dossier/document (héritage + override)
- `GED20` — Partage par lien tokenisé (expiry/mot de passe/quota)
- `GED21` — Watermarking & contrôle de diffusion
- `GED22` — Politiques de rétention
- `GED23` — Archivage légal à valeur probante (write-once/object-lock)
- `GED24` — Rétention légale / legal hold
- `GED25` — Purge automatique & tâche planifiée (dry-run d'abord)
- `GED26` — Corbeille & restauration
- `GED27` — Modèles de documents (fusion/mailing → PDF WeasyPrint, hors /proposal)
- `GED28` — Génération de document → classement automatique
- `GED29` — Filage des PDF après-vente générés (depuis `documents`)
- `GED30` — Signature électronique (point d'intégration + stub no-op)
- `GED31` — Numérisation par lot (scan-to-DMS) + OCR
- `GED32` — Import en masse (zip/CSV de métadonnées)
- `GED33` — OCR de pièces (CIN/factures/BL) → métadonnées
- `GED34` — Classification automatique (IA, no-op sans clé)
- `GED35` — Journal d'audit d'accès aux documents (lectures)
- `GED36` — Quotas de stockage par société
- `GED37` — Permissions & garde-prix sur tous les endpoints
- `GED38` — Contrats d'import + CODEMAP + tests
- `KB6` — Source de contenu pour le RAG/DocQA (FG352) — indexation pgvector
- `KB7` — Droits d'accès par rôle + suivi de lecture
- `LITIGE5` — Capture du concurrent/motif sur deal perdu (étend FG242)
- `LITIGE6` — Tableau de bord litiges (ouverts/montant contesté/délai de résolution)
- `N93` — Full Arabic & Darija localisation as a selectable interface language with RTL layout…
- `N94` — Translation-management surface in settings so interface strings can be…
- `N100` — Build out multi-tenant operation on the existing tenant_id foundation (strict…
- `N101` — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup…
- `N102` — After the modules above are built, update the master project document + PLAN + DONE log…
- `PAIE20` — CIMR optionnelle (taux par employé adhérent)
- `PAIE21` — Frais professionnels & net imposable
- `PAIE22` — Calcul IR (barème progressif + charges de famille)
- `PAIE23` — Allocations familiales (info patronale)
- `PAIE24` — Taxe de formation professionnelle (1,6 % patronal)
- `PAIE25` — Provision congés payés (consomme les soldes RH)
- `PAIE26` — Paiement & décompte des congés/absences sur le bulletin
- `PAIE27` — `CumulAnnuel` (brut/net imposable/IR/CNSS/congés)
- `PAIE28` — `Avance`/`PretSalarie` + déduction mensuelle
- `PAIE29` — Saisie-arrêt / cession sur salaire (quotité saisissable)
- `PAIE30` — `OrdreVirement` + fichier de virement banque
- `PAIE31` — Déclaration CNSS (BDS / format DAMANCOM)
- `PAIE32` — État IR 9421 + retenues à la source
- `PAIE33` — Livre de paie + journal de paie → écritures (via `compta.services`)
- `PAIE34` — PDF bulletin conforme + attestations (salaire/travail/domiciliation) via `documents`
- `PAIE35` — Coffre-fort bulletins (self-service employé, scopé à l'utilisateur)
- `PAIE36` — Clôture mensuelle + verrouillage + bulletins rectificatifs/rappels
- `PROJ18` — Plan de charge (capacité vs affecté)
- `PROJ19` — Détection de conflits d'affectation
- `PROJ20` — Nivellement de charge (levelling)
- `PROJ21` — Budget projet (lignes : matériel/MO/sous-traitance/divers)
- `PROJ22` — Coûts engagés vs réels (factures fournisseur + MO + sous-traitance)
- `PROJ23` — Alertes de dépassement budgétaire
- `PROJ24` — Suivi des temps (timesheets imputés au projet)
- `PROJ25` — Consommation matière vs BoM (via selectors)
- `PROJ26` — P&L de projet consolidé (interne/admin)
- `PROJ27` — Jalons de facturation liés à l'avancement (via `ventes.services`)
- `PROJ28` — Suivi avancement vs facturé
- `PROJ29` — EVM léger (valeur acquise) — optionnel
- `PROJ30` — Registre des risques
- `PROJ31` — Registre d'actions
- `PROJ32` — Comptes-rendus de réunion de chantier
- `PROJ33` — Documents & plans versionnés
- `PROJ34` — Commentaires & @mentions
- `PROJ35` — Templates de projet par type d'installation
- `PROJ36` — Tableau de bord portefeuille (avancement/retards/marge/charge)
- `PROJ37` — Portail d'avancement client (sans coûts/marges)
- `PROJ38` — Sous-traitance & clôture + retour d'expérience
- `QHSE19` — `RetourClientQualite` (satisfaction qualité)
- `QHSE20` — Tableau de bord « ISO 9001 readiness »
- `QHSE21` — `EvaluationRisque` (document unique / plan de prévention) + lignes
- `QHSE22` — Document unique requis avant pose (gate statut chantier)
- `QHSE23` — `PermisTravail` (hauteur/élec-consignation/point chaud)
- `QHSE24` — Consignation électrique (LOTO) sur permis électrique
- `QHSE25` — Alerte expiration de permis
- `QHSE26` — `InductionSecurite` (accueil sécurité site, incl
- `QHSE27` — `CauserieSecurite` (toolbox talks + émargement)
- `QHSE28` — `PlanUrgence` / premiers secours (contacts/secouristes/point de rassemblement)
- `QHSE29` — Registre `Incident` (accident/presqu'accident/incident)
- `QHSE30` — Déclaration CNSS de l'accident du travail (échéance légale)
- `QHSE31` — `AnalyseIncident` (arbre des causes) → CAPA
- `QHSE32` — Événement `incident_declared` sur le bus (escalade)
- `QHSE33` — `InspectionSecurite` planifiée (→ NCR)
- `QHSE34` — Statistiques TF / TG (heures travaillées depuis RH)
- `QHSE35` — Inspections/permis dans le digest + calendrier
- `QHSE36` — `Dechet` + `BordereauSuiviDechet` (BSD, loi 28-00 déchets dangereux)
- `QHSE37` — `RecyclageModule` (fin de vie des modules PV)
- `QHSE38` — `ConformiteEnvironnementale` + relances
- `QHSE39` — `BilanCarbone` interne (scopes 1/2/3)
- `QHSE40` — `IndicateurESG` + export reporting

**Blocked — awaiting founder decision (1)**

- `S21` — Real-time WebSocket upgrade (Django Channels)
