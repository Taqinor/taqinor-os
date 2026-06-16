# SESSION HANDOFF — Taqinor OS (2026-06-16)

Read this first when resuming. It records the exact state at the end of the
2026-06-16 build sessions so a fresh session can continue without re-discovering.

## Where the work lives
- **Branch:** `claude/optimistic-darwin-s5mxub` — ALL work from these sessions is here.
- **NOT merged to `main`, no PR opened** (deliberate: the operator chose
  "push-to-branch, no PR" — nothing auto-deployed to api.taqinor.ma). To ship,
  the operator reviews this branch and merges it the protected way when ready.
- Commits show as "Unverified" on GitHub (no signing key in the cloud env; the
  committer email is correct). Cosmetic only — there is no merge to `main`.

## What is DONE (with tests, full local CI green)
- **`docs/PLAN.md` — T1–T17: ALL done.** (T1 devis preview & T2 PWA were verified
  already-present; T3–T17 built this session: bulk lead actions, inline editing,
  global search + notifications, settings unlock, quote expiry + pipeline dashboard,
  bulk product editing, import/export, quote revisions, custom fields, accountant
  export, reports hub, maintenance contracts, discount guard.)
- **`docs/PLAN2.md` — 30 of 102 done** (see its `[x]` marks + DONE LOG for the
  per-task detail). Delivered: N2–N13, N21–N26, N29–N31, N36, N45–N49, N55, N70.

## IMPORTANT — partial items (backend + API complete & tested, UI not yet wired)
A fresh session should finish the thin UI layer for these before calling them fully shipped:
- **N11 / N12** Supplier purchase orders (`stock.BonCommandeFournisseur`): backend +
  `stockApi` helpers exist; **no list/detail page or sidebar entry yet.**
- **N13** Besoin matériel per chantier: endpoints
  `/installations/chantiers/<id>/besoin-materiel/` and `/commander-besoin/` +
  `installationsApi` helpers exist; **no panel on the chantier detail page yet.**
- **N45 / N47** SAV intervention report PDF + maintenance report PDF, and **N48**
  "garanties qui expirent" view + warranty claims: backend + `savApi` helpers exist;
  the download buttons / dedicated views are **not surfaced in the SAV UI yet**.
- **N49** CA récurrent: works, but figures are 0 until `ContratMaintenance.montant_mensuel`
  is entered per contract (field + API exist; add an input to the contrat form).

## New backend apps / models added this session (all additive migrations)
- New apps: `apps.customfields` (T11), `apps.imports` (T9), `apps.documents` (N21–N24, no models).
- New models: stock `ProduitAuditLog`, `Marque`, `BonCommandeFournisseur` + lines;
  crm `CanalSource`; installations `ChecklistItem` + `Installation.parc_actif/date_reception`;
  sav `ContratMaintenance` (+ `date_fin/duree_mois/montant_mensuel`), `ReclamationGarantie`,
  `TicketPiece`; parametres `SettingsAuditLog` + JSON settings (roi_constants, seuil_remise,
  chantier_checklist_defaut); records `Attachment.phase`; nullable `custom_fields` /
  `import_batch` on Lead/Client/Produit; ventes Devis acceptance + revision fields, Facture
  `date_livraison/conditions_paiement`.
- Latest migration numbers: crm 0017, stock 0019, ventes 0013, installations 0006,
  parametres 0011, sav 0004, records 0003, customfields 0001, imports 0001.

## GATED — do NOT auto-build (need external deps / paid services / auth / new architecture)
Monitoring/FusionSolar (N50–52), automation engine (N72–73), email send + inbound
(N87–88), push notifications (N92), Arabic/Darija i18n (N93–94), 2FA/security (N96),
public REST API (N89), multi-tenant platform/console (N100–101), QR/barcode if it needs
a new lib (N20). Leave these unticked and flag them.

## Remaining buildable PLAN2 backlog (next waves, additive)
Inventory N14–N20 (reservation, multi-location, count/adjust, multi-supplier prices,
valuation, supplier return), Moroccan billing depth N27–N28 / N33–N35 / N37–N43,
editability/automation/notifications/dashboard/analytics N54 / N56–N69 / N71 / N74–N86,
plus N1 (richer chantier from devis: BOM copy + labour-days), N44 verify.

## How to run the full CI locally (the cloud container starts with NO services)
The next session's container is a fresh clone with Postgres/Redis/MinIO NOT running.
Recreate them before running tests:
```bash
# Postgres + Redis
service postgresql start ; redis-server --daemonize yes
sudo -u postgres psql -c "CREATE USER erp_user WITH PASSWORD 'ci_password' CREATEDB SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE erp_db OWNER erp_user;"
# S3 (Docker registry is network-blocked here, so use moto as an S3 stand-in for MinIO)
pip install "moto[s3,server]" --ignore-installed PyYAML
setsid nohup python3 -m moto.server -p 9000 >/tmp/moto.log 2>&1 </dev/null &
# Frontend + backend deps
(cd frontend && npm ci)
pip install -r backend/django_core/requirements.txt
```
Test env vars (same as `.github/workflows/ci.yml`):
```bash
export DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev DJANGO_SECRET_KEY=ci DJANGO_DEBUG=True
export DB_NAME=erp_db DB_USER=erp_user DB_PASSWORD=ci_password DB_HOST=localhost DB_PORT=5432
export REDIS_HOST=localhost REDIS_PORT=6379
export MINIO_ENDPOINT=localhost:9000 MINIO_ROOT_USER=erp_admin MINIO_ROOT_PASSWORD=erp_minio_password \
       MINIO_BUCKET_PDF=erp-pdf MINIO_BUCKET_UPLOADS=erp-uploads
```
The 5 CI jobs (must all pass before shipping):
```bash
flake8 backend --max-line-length=120 --extend-ignore=E501 --exclude=migrations   # backend-lint
python scripts/check_stages.py                                                    # stage-names
cd backend/django_core && python manage.py test apps authentication -v1 --noinput # backend-tests (needs S3+PG+Redis)
cd frontend && npm run lint                                                        # frontend-lint
cd frontend && node --test <the .test.mjs list in ci.yml line ~108>               # frontend unit tests
```
As of this handoff: backend **540 tests OK**, frontend **106 node tests OK**,
eslint 0 errors, `makemigrations --check` clean, Vite build OK.

## Plan-execution reminders (from CLAUDE.md)
- `docs/PLAN.running` is the run lock — if present, a batch is in progress.
- `work on the plan` builds the next `[ ]` items; additive migrations only; never edit
  STAGES.py semantics; never expose buy prices in client-facing output; French UI.
- This session ran with parallel worktree subagents partitioned by Django app to keep
  migrations disjoint, integrating wave-by-wave with the shared router/Sidebar/Header
  wired centrally.
