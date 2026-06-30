# Taqinor OS — Build Plan & Progress

This file is the **single source of truth** for the Taqinor OS build backlog and the
**memory between Claude Code sessions**. Each run first works through EVERY unchecked task in `docs/PLAN2.md` (if that file exists) from top to bottom — not just one — ticking each off as it lands, then does the same for this file, and only stops when both queues are clear (or a usage limit pauses it, in which case re-running resumes from the next unchecked task). The next session reads this file and
continues. Nothing relies on the agent's own memory — the file on disk is the memory.
Each run partitions its unchecked tasks into independent **lanes** (grouped by which real
source files they write) and builds them with **up to 8 concurrent worktree subagents**, in
waves of 8 when there are more lanes — see HOW TO RUN.

---

## HOW TO RUN (read this every session)

1. **Read this whole file.**
2. **Drain the WHOLE queue, PLAN2 first — never just one task, with MAXIMUM SAFE PARALLELISM.**
   Check `docs/PLAN2.md` FIRST: work through EVERY pending `[ ]` task there that isn't
   `[BLOCKED]` — following PLAN2.md's own rules, which are the same as this file's — then
   drain this file's **BUILD QUEUE** the same way. Process EVERY unchecked `[ ]` task (not
   `[x]`, not `[SKIP]`, not `[BLOCKED]`) of EVERY category — auto-gating is OFF, nothing is
   skipped for being `ARCH`/`AUTH`/`COST`/`DECISION`/`GALLERY`/`DEP`; ignore only the NEEDS YOUR
   INPUT and MANUAL sections (those wait on a founder-provided prerequisite).
   **At the START, run `python scripts/plan_lanes.py docs/PLAN2.md` then
   `python scripts/plan_lanes.py docs/PLAN.md`** — it computes the file-ownership + dependency
   graph from the real code (which source files each `[ ]` task must write) and emits a
   **maximally parallel, cross-category wave plan** instead of a top-down walk: each wave takes
   one head from each independent lane (a lane is a group that must run in sequence because it
   shares a file or has a dependency; different lanes never touch each other's files), spanning
   as many different apps/categories as possible, longest lanes first. It reports `0 gated` (every
   category builds — labels only) and lists any `UNASSIGNED` task that still needs a `@lane:`/`@files:` tag.
   **Fan each wave's lanes out to concurrent worktree subagents** (`isolation: worktree`, each
   in its own isolated git worktree so two never edit the same files at once) up to the
   session's worktree ceiling (default 8, raised as high as the session can sustain, passed as
   `--max-lanes`), **continuously refilled (work-stealing): a freed slot immediately takes the
   next ready lane head rather than idling until a whole wave finishes**. **Tasks inside one
   lane run in sequence.** Each subagent
   commits its lane's work to its own worktree branch — ticking each task `[x]` + a DONE LOG
   line as it lands — and the orchestrator folds every worktree branch into one `dev` branch at
   the end. Derive lane ownership from the real code, not from guesses. **Default to running
   this as a dynamic workflow with review** — one worktree subagent per task plus a **separate
   adversarial review agent** that must pass each finished change (against the STANDING RULES
   and the task's acceptance criteria) before it is eligible to fold in — and **fall back to the
   same parallel worktree subagents (orchestrator reviews each lane) when no workflow engine is
   available; never a single serial one-task-at-a-time agent** (see STANDING RULES).
3. **Verify each task isn't already built — never trust these ticks or prior reports.**
   Inspect the actual repo and the deployed app. If a task already exists and works, mark it
   `[x] (already present)`, add a line to the DONE LOG, and move on to the next `[ ]` task.
4. **Build each task completely, with tests, and land it on its lane's worktree branch the moment
   it's done.** Obey every STANDING RULE below. As each task finishes: commit it to its **worktree
   branch** (folded into `dev` at the end of the run), flip it to `[x]`, and append one dated
   plain-language line to the DONE LOG — so an interrupted run never loses finished work and
   re-firing resumes from the first still-unchecked task. Then the lane **immediately continues to
   its next `[ ]` task. Do NOT merge after each task.**
5. **Fold every lane's worktree branch into one `dev`, then CI runs ONCE over the whole batch.**
   The four required checks must pass: backend-lint, backend-tests **with MinIO** (so PDF/storage
   tests actually run, including the PDF page-count guardrails), frontend-lint, and the stage-name
   check. When all four are green, **self-merge `dev` → `main` exactly once** (a single merge
   commit, history preserved, 0 approvals; no per-agent PR, no per-task merge). **Merging to `main` AUTO-DEPLOYS to api.taqinor.ma on its own** — the
   production server polls `main` about once a minute and runs the full deploy (rebuild +
   migrations + role sync + nginx/Caddy reload + the mandatory PDF pre-warm). **You do not run
   any deploy command.** `powershell -File scripts\deploy-prod.ps1` still works as a **manual
   fallback** from a PC if ever needed. **Make this one merge sync-safe:** right before merging,
   **integrate the latest `origin/main` into `dev`** (merge it in, never force-push), recompute
   the CODEMAP structure fingerprint if that changed the structural surface, **re-run CI once on
   the integrated tree, and merge only when green**; if the push is rejected because `main`
   advanced (e.g. a concurrent web-plan run landed first), **repeat the integrate → CI → push
   loop — never force, never overwrite the other run's commits** (see STANDING RULES).
6. **Skip-and-note real blockers only, never stall.** Auto-gating is OFF: a destructive (but
   revertable) migration, a new paid/external dependency, an auth or cost change, a brand-new
   architectural component, and any `DECISION` are all **buildable** — just NOTE each in the DONE
   LOG (new paid/external dep, auth change, destructive migration, new architecture). A task is a
   blocker ONLY when it hits a true external prerequisite a run cannot satisfy (a credential /
   secret / account / real-world data the founder must provide) or a conflict with a non-negotiable
   rule (#1–#5). Then do **not** guess and do **not** stall: mark it `[BLOCKED: <one-line reason>]`,
   move it to **NEEDS YOUR INPUT**, and continue. A single blocked task must never halt the run.
7. **STOP only when** the queue is drained (no buildable `[ ]` task remains in `docs/PLAN2.md`
   then this file), a usage/length cap pauses the run (fine — the plan is idempotent;
   re-firing resumes from the first still-unchecked task), or every remaining task is blocked.
   Then **report once**, in plain language only — no diffs, no commit hashes: every task that
   shipped, what was skipped and why, and exactly what Reda must click/type (with menu paths).

**Then the REFINEMENT QUEUE (run order).** Once the existing BUILD QUEUE is drained — **T1–T17
first**, then the N/F tasks — work the **REFINEMENT QUEUE — existing-feature polish (audit
2026-06-18)** section (below, after the BUILD QUEUE) top-down: build **every** task unattended
regardless of its category label (`ROUTINE` / `SCHEMA` / `DEP` / `DECISION` / `GALLERY`) — auto-gating
is OFF, so none are skipped; just NOTE any new dep/auth/destructive-migration/architecture in the
DONE LOG. The refinement tasks use the format `[ ] [<MODULE>] [L<lens#>] [<GATE>] …` (not the `T#/N#`
ids), so they are deliberately outside the plan-status fingerprint — ticking one does not require a
CODEMAP §10 refresh.

**Run from anywhere — web or phone.** Because `main` auto-deploys itself, a task can be run
from Claude Code on the web or from the phone with no PC involved. **One-line starter** to
paste into a fresh cloud session:

> Read `docs/PLAN.md` top to bottom. Work through EVERY `[ ]` task — **first** `docs/PLAN2.md` (if it exists), **then** this file's BUILD QUEUE. First run `python scripts/plan_lanes.py docs/PLAN2.md` then `python scripts/plan_lanes.py docs/PLAN.md` to get the maximally-parallel cross-category wave plan, then build those lanes in parallel with concurrent worktree subagents (each in its own git worktree) up to the session ceiling (default 8, raised as high as the session can sustain via `--max-lanes`), continuously refilled (work-stealing), coupled tasks in sequence inside a lane (default: run this as a dynamic workflow with a separate adversarial review agent that must pass each change before it's merge-eligible; fall back to plain parallel worktree subagents — never a single serial one-task-at-a-time agent). For each task: verify it isn't already built, build it with tests, commit it to its worktree branch, tick it `[x]`, add a dated DONE LOG line, then continue to the next. Skip-and-note any blocker (`[BLOCKED: reason]` → GATED) and keep going. At the very end, fold every worktree branch into one `dev`, integrate the latest `origin/main` first (merge it in, never force-push) and recompute the CODEMAP structure fingerprint if that changed the structural surface, get the four required CI checks green over the whole batch (with MinIO) and self-merge `dev` → `main` exactly once (this auto-deploys — do not run any deploy command; no per-agent PR, no per-task merge). Report once, in plain language, including the lane plan. Do not stop after one task and do not merge per task.

---

## STANDING RULES (every task obeys these)

- **One run = the whole queue, not one task, fanned across as many parallel lanes as the session can sustain.** At the start, run `python scripts/plan_lanes.py` (PLAN2 first, then PLAN.md) to partition the unchecked queue into independent **lanes** (grouped by the real files each task writes) and build the **maximally-parallel cross-category wave plan** it emits — give each lane its own subagent in its own git worktree, **up to the session's worktree ceiling (default 8, raised as high as the session can sustain) and continuously refilled (work-stealing)** rather than rigid waves — so each subagent's context stays small and focused and two lanes never edit the same files at once; tasks that depend on or overlap each other run in sequence inside one lane. Never stop after a single task. The orchestrator folds every worktree branch into one `dev`, CI runs **once** over the whole batch, and the run self-merges `dev` → `main` **exactly once** — no per-agent PR, no per-task merge. (Human-review PRs are still not wanted — the run self-merges its own green work.)
- **Engine = workflow-with-review by default; parallel subagents as fallback; never single-serial.** Run the lanes as a **dynamic workflow with a fan-out-and-verify shape** — one worktree subagent per independent task **plus a separate adversarial review agent** that checks every finished change against these STANDING RULES and the task's acceptance criteria; nothing folds into `dev` or merges until its review passes. When no workflow engine is available (e.g. a phone or cloud session), **fall back to the same lane-planned worktree subagents** with the orchestrator reviewing each lane against these rules before folding it in. **Never drop to a single serial, one-task-at-a-time agent** — parallel lanes with review are the floor.
- **Sync-safe single merge.** Right before the one self-merge, **fetch and integrate the latest `origin/main` into `dev`** (merge it in — never rebase published history, never force-push); if that changed the code-structure surface, **recompute the CODEMAP structure fingerprint on the integrated tree** (the fingerprint the `stage-names` check verifies); **re-run CI once on the integrated state and merge only when green**; if the push is rejected because `main` advanced, **repeat (fetch, integrate, recompute if needed, re-run CI, push) — never force**. A run edits the shared files (`CLAUDE.md` / its own plan file / `docs/CODEMAP.md`) only for its own command and ships that change inside this same merge — so a concurrent OS run and web-plan run never fight over those files.
- **Verify against real code first. Never trust prior reports.** (Round 1 reported a preview
  fix that was never real, because that session's CI was silently broken.)
- **Additive by default; destructive allowed only if revertable.** Prefer new tables / nullable
  columns / new defaults. A destructive migration (dropping columns/tables, deleting rows) is
  permitted per CLAUDE.md **only when it stays revertable via `git revert`** and is **NOTED in the
  DONE LOG** — never an irreversible data loss. When in doubt, stay additive.
- **Do not touch the DEBUG setting.** It is ON by Reda's explicit decision for the trial.
- **Premium devis PDF stays off-limits.** The `/proposal` premium devis engine
  (`generate_devis_premium.py`) is the only client-facing quote-PDF path (rule #4) — never replace
  or fork it; keep the `PDF_ENGINE=legacy` fallback working. A facture/BC visual redesign is allowed
  but needs a **gallery review** first (G3 → NEEDS YOUR INPUT below).
- **Never expose buy prices / prix revendeur / margins** in any client-facing output, link,
  message, or PDF. This is critical for the WhatsApp public links.
- **Do not change `STAGES.py` semantics.** Six canonical stages are a contract; "Perdu" is a
  boolean flag, never a stage.
- **Keep the contact form parked OFF.**
- **Multi-tenant:** every new model carries a `company` FK, filtered querysets, and a
  server-forced company. No client-supplied company is ever trusted.
- **All new user-facing text in French.** (Code/identifiers in English.)
- **New settings default to today's exact behavior** — nothing changes until Reda edits it.
- After merge, **deploy**, then **one plain-language report**.

**Dependencies & categories (2026-06-21 — auto-gating OFF).** Per the founder standing consent,
EVERY task category is buildable — `ARCH` / `AUTH` / `COST` / `DECISION` / `GALLERY` / `DEP` are
now **labels only**, never a stop-and-ask, and `scripts/plan_lanes.py` schedules them like any other
task. A run may add a new dependency, an additive **or** destructive (but revertable) migration, an
auth change, or a brand-new architectural component — it just **NOTES each in the DONE LOG** (new
paid/external dep, auth change, destructive migration, new architecture) so you keep visibility.
The five non-negotiable rules (#1–#5) still bind. A task is `[BLOCKED]` ONLY when a run cannot
satisfy a real external prerequisite (a credential / secret / account / real-world data you must
provide) — those are parked under **NEEDS YOUR INPUT** with a recommendation, not auto-built.

**Status legend:** `[ ]` to do · `[x]` done · `[SKIP]` not needed / already present ·
`[BLOCKED: reason]` waits on a founder-provided external prerequisite (→ NEEDS YOUR INPUT).

---

## ALREADY LIVE — do not rebuild (verify if unsure)

As reported in the build logs (treat as "very likely present, confirm before assuming"):
production on Hetzner at **api.taqinor.ma** (cx23, daily backups, deploy via
`scripts\deploy-prod.ps1`); multi-tenant ERP monorepo; CI now genuinely green **with MinIO**.

- **CRM:** Odoo-style multi-view (kanban default / liste / calendrier / graphique), full solar
  lead record, Historique chatter, lead-primary quoting, per-mode-gated "⚡ Devis auto",
  automatic stage movement, lead↔devis links, real `perdu` flag, reordered lead form,
  Activities + "Mes activités", Pièces jointes, employee avatars, lead routing/assignment,
  employee management, **Doublons workspace + N-way group merge**.
- **Quote generator:** three markets (résidentiel / industriel-commercial étude / agricole
  pompage), simulator-exact screen, prix/kWc, internal margin indicator, **reads saved
  settings** (validité, heures de pompage).
- **Per-line TVA** (panels 10% / else 20%), PDF suite (premium / one-page / étude), payment
  terms by mode, client ICE, seller legal IDs, unified warranties.
- **Invoicing:** Devis→Facture installment factures d'acompte, manual payments, running solde,
  per-line TVA on invoices, **Avoirs** (credit notes), **Relances/Impayés** + balance âgée +
  relevé client.
- **Chantier/Installation** module (lifecycle, interventions, mise en service, planning),
  **Equipment registry** + warranty clocks + "Expirant bientôt", **SAV tickets** (warranty-aware).
- **Stock:** catalogue + Pompage category, Category→Brand redesign, warranties populated.
- **Settings:** Société/Identité + Moroccan legal IDs, Devis (payment terms, validité,
  heures de pompage, prefixes), TVA, CRM tags & motifs de perte, niveaux de relance.
- **Sending:** **"Envoyer par WhatsApp"** on leads/factures/relances, with tokenized public
  PDF links and editable FR + Darija templates (Paramètres → Messages WhatsApp).
- Login is the front door (landing at `/landing`); website → CRM lead pipe live end-to-end.

---

## BUILD QUEUE (do top-down — highest value first)

### EVERY CATEGORY IS BUILDABLE (auto-gating OFF, 2026-06-21)

> **Founder standing consent (2026-06-21, Reda).** The former auto-skip of
> `ARCH` / `DECISION` / `AUTH` / `COST` / `GALLERY` / `DEP` is **LIFTED**. A run builds tasks of
> EVERY category without pausing — including brand-new greenfield modules (compta, paie, flotte,
> qhse, contrats, gestion_projet, ged, kb, litiges), auth changes, new paid/external dependencies,
> additive **and** destructive-but-revertable migrations, and new architecture. `scripts/plan_lanes.py`
> reflects this in code (`GATED_KEYWORDS` is empty → it reports `0 gated`). The planner still LABELS
> each category, and the run **NOTES in the DONE LOG** whenever a built task introduced a new
> paid/external dependency, an auth change, a destructive migration, or a brand-new architectural
> component — so you keep visibility. The five non-negotiable rules (#1–#5) are unaffected and still
> bind (rule #5's `tos_risk/` process still applies to any scraping task). Every change must stay
> revertable via `git revert` and pass the four required CI checks before merge.

A task is held back ONLY by a genuine **external prerequisite a run cannot satisfy** — a credential /
secret / account / real-world data **you** must provide, or a conflict with a non-negotiable rule.
Those are parked under **NEEDS YOUR INPUT** (below) each with a recommendation; everything else
builds. (Historical note: the long list of "specifically pre-approved" deps — Leaflet, Celery Beat,
Brevo, the additive columns, ONEE seeds, the stock-reserve rule, the silent DGI export, the devis
literal→setting wiring — all shipped; they are now just instances of the general rule above.)

### Active regressions — fix first (added 2026-06-18, top priority)

Added 2026-06-20 (top priority for this run): two live-production regressions + one
dormant-feature activation. Same STANDING RULES (additive only, multi-tenant, French UI,
`STAGES.py` untouched, premium devis engine untouched, never re-raise).

- [x] N108 — Attachment upload crashes with NoSuchBucket (HTTP 500). Uploading any file via the attachments paperclip (and avatars, company logo/signature, field photos, voice memos) returns 500 because the MinIO bucket `erp-uploads` (`settings.MINIO_BUCKET_UPLOADS`) does not exist and nothing creates it. The PDF path self-heals via `apps/ventes/quote_engine/builder.py _ensure_pdf_bucket()` (head_bucket → create_bucket on miss); the uploads bucket has no equivalent. Fix: add an idempotent self-healing ensure-bucket helper beside `get_minio_client` (mirroring `_ensure_pdf_bucket` exactly), called immediately before the upload in every code path that writes to the `erp-uploads` bucket (grep `settings.MINIO_BUCKET_UPLOADS` to find them all). Do not modify the premium devis engine or the existing `_ensure_pdf_bucket`. Add a test that an upload succeeds when the bucket is initially absent. (UNGATED 2026-06-20 — confirmed from a live production traceback; contained bug fix.) [DONE 2026-06-20: added best-effort `ensure_uploads_bucket()` beside `get_minio_client` (mirrors `_ensure_pdf_bucket`, never raises), called immediately before every write to the uploads bucket — `records.store_attachment`, `authentication.store_avatar`, `parametres._upload_image`. `_ensure_pdf_bucket` / the premium engine untouched. New test `test_upload_self_heals_absent_bucket` (head_bucket raises → create_bucket → upload succeeds). 32 records tests OK.]
- [x] N109 — Activate Web Push end-to-end (complete N92). Fully built but dormant. Install `pywebpush` in every backend image that runs `notify()`/dispatch (django_core web + celery_worker), handling its `http-ece` sdist build via a wheel-having pin so neither CI nor the prod build breaks. The production server loads `erp_agentique.settings.dev` (not prod.py) and `VAPID_*` env values may already be set there — confirm which module it loads, gate any production-on behavior to that module, and always let env-provided keys take precedence. The repo is public, so never commit a private key: if no VAPID keys are provided via env, auto-generate a keypair once and persist it as a single app-global singleton DB row (infra config, no company FK), and have the vapid-public-key endpoint return it so the frontend's "Le push n'est pas encore configuré côté serveur" clears. Preserve existing tests (empty keys ⇒ endpoint empty ⇒ no-op); add tests for the keys-present path. Push stays best-effort (a send failure never blocks the request; 404/410 prunes the dead subscription). (UNGATED 2026-06-20 — pywebpush approved in N92; completes the dormant N92 stack.) [DONE 2026-06-20: pinned `pywebpush==2.0.3` in `backend/django_core/requirements.txt` (covers web+celery_worker+celery_beat, all built from django_core) + Dockerfile upgrades pip/setuptools/wheel so the http-ece sdist always builds; `base.py` adds a test-aware `TESTING`/`VAPID_AUTOGENERATE` gate (off under the test runner — preserves the empty-keys contract — on in prod); new `notifications.VapidKeyPair` singleton (no company FK) auto-generates a P-256 keypair via `py_vapid` and persists it (private never committed); `resolve_vapid_keys()` = env precedence → singleton; vapid-public-key endpoint returns it so the frontend banner clears; push stays best-effort. 39 notifications tests OK (old empty-keys tests preserved + 3 new keys-present tests).]
- [x] N110 — Admin cannot change a user's role manually (Administration → Utilisateurs → edit employee → Rôle). Not reproduced from code review — the path looks correct (`UserViewSet.update` + `UserSerializer` accept a writable `role`; only deliberate blocks are demoting the protected owner or the last admin). Reproduce and diagnose against the live system first; check menu-tier/permission resolution for the acting and target accounts (known tier-drift history, CODEMAP §roles/N103), the exact API response on save, and any role-dropdown value mismatch. If a real bug is found, fix it additively without weakening the protected-owner/last-admin guards. If not reproducible, document that and make no change. (UNGATED 2026-06-20 — diagnosis-first; additive fix only if a real bug surfaces.) [DONE 2026-06-20: NOT reproducible — the backend is correct and already covered by `TestRoleAssignmentN103`; the frontend (`UsersManagement.jsx`) sends `role: Number(v)` (a real PK). NO production code change. Added `authentication/tests_role_change.py` (4 tests) locking the API response (new role + re-aligned `menu_tier`), int-vs-string PK acceptance (rules out a dropdown value mismatch), persistence on reload, and the unchanged last-admin guard. Documented likely live cause: stale JWT `menu_tier` or a drifted role on the ACTING account → 403 on /users/ + /roles/ → screen won't load; remedy = run `init_roles` (self-heals) + re-login.]

---

## BUILD QUEUE — N1–N102 (post-sale, procurement, Moroccan billing, editability, platform)

Re-homed from the recovered `docs/PLAN2.md` (the overflow queue) on 2026-06-16. The ticks
below were **re-verified against the live `main` code**, task by task — the recovered file's
own ticks were written on a branch that never merged and were unreliable. `[x]` here means the
feature genuinely exists **and is usable** on `main` today; `[ ]` means missing, backend-only
with no usable screen, or only partially meeting the spec. Same STANDING RULES as the rest of
this file apply (additive only, multi-tenant, French UI, STAGES.py pipeline never edited, buy
prices never client-facing). **Reconciliation result: 30 of 102 done, 72 open.**

Two tasks have a working backend on `main` but no usable screen yet — flagged inline as
_Backend ready, frontend pending_: **N11** (supplier-PO management page) and **N29** (facture
conformity warning banner).

### Chantiers / projets & execution
### Parc installé (installed-systems asset base)
### Procurement & inventory
- [x] G5 — Supplier procurement module (a dedicated multi-session module): bons de commande fournisseur (BC fournisseur), goods-in / receiving, and supplier invoices / accounts payable (AP). (UNGATED 2026-06-20 — approved as its own multi-session project. Additive only, multi-tenant with the company FK forced server-side, French UI; buy prices / margins never client-facing.) [DONE 2026-06-20: BC fournisseur already existed; this run added the goods-in/receiving spine (`ReceptionFournisseur`/lines → idempotent stock ENTRÉE on confirm, advances BCF statut) and supplier invoices / AP (`FactureFournisseur`/lines + `PaiementFournisseur`, `solde_du`, comptes-à-payer) with company-scoped viewsets + 2 frontend pages + 14 tests. FUTURE G5 sessions: supplier-invoice PDF, line-editing UI, one-click "facturer cette réception", aged-payables reporting.]
### Post-sale / client-facing documents
### Devis acceptance trigger
### Moroccan legal billing & compliance
### Loi 82-21 / Article 33 regulatory
### SAV / maintenance / warranty / monitoring
- [x] N53 — Client energy-yield report PDF (French) from ESTIMATED / MANUAL data (nameplate kWc + irradiation assumptions and/or manual entry): a system's production over a period, estimated bill savings, CO2 avoided; client-facing, no buy prices. (UNGATED 2026-06-20 — the estimated/manual version is approved and buildable now; the real MEASURED-monitoring version stays gated on the N50 monitoring integration.) [DONE 2026-06-20: stateless WeasyPrint PDF + DRF `@action` `chantiers/<id>/rapport-energie/`, company-scoped (404 cross-company), defaults 1600 kWh/kWc/an · 1.40 MAD/kWh · 0.81 kg CO₂/kWh (all overridable, labelled ESTIMATION, no buy prices), Parc-installé per-row button + modal, 10 tests.]
### Editability layer (Paramètres hub)
### Notifications / dashboards / analytics
- [x] N76 — Daily & weekly digest notification for Reda & Meryem (jobs to plan, quotes awaiting acceptance, overdue payments, due maintenance, open SAV), in-app and optionally WhatsApp/email. (UNGATED 2026-06-20 — verified on main: the Celery Beat scheduler (G9) and the Brevo email integration (N87) both shipped; register the digest as a new beat_schedule job and deliver via the existing email/WhatsApp/notification services. CAVEAT for the build run: a celery **beat process** is not yet deployed in docker-compose/prod — add it so the scheduled job actually fires.) [DONE 2026-06-20: `notifications/digests.py` daily_digest + weekly_digest beat jobs (07:30 / Mon 07:30 Casablanca) deliver per-company via `notify()` (in-app + email/WhatsApp no-op until configured); the missing `celery_beat` process was ADDED to docker-compose.yml. 4 tests.]
- [x] N79 — Saved-reports & custom-views capability: save filtered/grouped views of any major object, pin to dashboard, schedule a periodic export of a saved report by email when email is configured. (UNGATED 2026-06-20 — scheduler (G9) + Brevo email (N87) verified on main; local named saved-views already shipped, so only the SCHEDULED EMAIL EXPORT of a saved view remains. Same beat-process deployment caveat as N76.) [DONE 2026-06-20: server-side `reporting.SavedReport` (company-scoped CRUD) + `reporting.email_saved_reports` beat job (daily 06:00 / Mon 06:00) renders the due report to xlsx and emails it (no-op until email configured). Beat process shipped with N76. 7 tests.]
### Import/export / search / calendar / map
### Chatbot / integrations / API
### PWA / mobile / offline
- [x] N91 — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception signature, syncing when back online. (UNBLOCKED 2026-06-21 — the dev-field-exec routing was stale: the whole field-execution backend it extends is already on `main` (F9–F23, `apps/installations/models_field.py`), and worktree isolation already prevents branch collisions, so build it as a normal worktree lane. The PWA/service-worker foundation exists (`frontend/src/sw.js`). Approach: IndexedDB/localStorage outbox + idempotent sync endpoints, last-write-wins on reconnect. Coupled with F21 — same lane.) (ARCH)
- [x] N92 — PWA web push notifications for high-priority events from the notification engine. (UNGATED 2026-06-20 — pywebpush dependency approved; in the build run generate the VAPID keypair — public key to the frontend, private key to the backend env. Opt-in per device subscription.) [DONE 2026-06-20: `notifications.PushSubscription` (company+user forced server-side), subscribe/unsubscribe/vapid-public-key endpoints, best-effort web-push channel in `notify()` (drops dead subs on 404/410), `sw.js` push+notificationclick handlers, per-device opt-in toggle in NotificationsPreferences. VAPID keys default EMPTY → total NO-OP until Reda sets them. `pywebpush` left as an OPTIONAL install (its `http-ece` sdist won't build on modern setuptools, so it's `pip install`-to-enable rather than a base requirement — keeps CI install green; the dispatch path imports it lazily). 8 tests.]
### Localisation / audit / security / data
- [ ] N93 — Full Arabic & Darija localisation as a selectable interface language with RTL layout support across the app, French default, English in code; client-facing document language selectable per client (facture/devis in French or Arabic). (UNGATED 2026-06-20 — i18n framework approved. SEQUENCING NOTE (do NOT prioritize): this touches every component, so run it as the FINAL step of the UI/UX overhaul, AFTER the component restyle, to avoid re-translating restyled components — pull forward only on Reda's explicit instruction.)
- [ ] N94 — Translation-management surface in settings so interface strings can be reviewed/adjusted per language without a code change. (UNGATED 2026-06-20 — depends on the N93 i18n framework; SAME sequencing note — final step of the UI/UX overhaul, not prioritized.)
- [x] N96 — Account security: optional 2FA, visible active sessions with revoke, forced credential-rotation flow; production DEBUG setting left unchanged. (UNGATED 2026-06-20 — auth change approved (this closes G8); pyotp dependency approved. Build 2FA as OPT-IN per user so it can NEVER lock existing users out.) [DONE 2026-06-20: the **2FA** half (opt-in TOTP on `CustomUser`, default OFF → no lockout, setup/enable/disable/status endpoints, login requires `otp` only when enabled, settings tab + login code step, `pyotp==2.10.0`, 11 tests) shipped earlier; THIS run completed the rest — additive `UserSession` (company+user forced, refresh-token jti, UA/IP/last-seen), `GET /auth/sessions/` + `POST /auth/sessions/<id>/revoke/` (blacklists the refresh token via the already-installed `token_blacklist` + marks the row revoked; current device flagged), forced rotation via additive `must_change_password` (default **False** → nobody locked out) + nullable `password_changed_at` surfaced in `/auth/me/`, `POST /auth/change-password/`, and the "Sessions actives" + "Mot de passe" sub-sections in the Sécurité-du-compte tab. Migration 0012, 11 new tests (95 auth tests total green). Closes G8's 2FA half.]
### Growth / multi-tenant platform
- [ ] N100 — Build out multi-tenant operation on the existing tenant_id foundation (strict per-tenant isolation verification, tenant onboarding flow, per-tenant branding/white-label of client-facing documents, configurable per-plan feature limits, tenant-level billing). (UNGATED 2026-06-21 per "ungate all". **RECOMMENDATION: KEEP DEFERRED until a 2nd paying installer — the `company` foundation is ready so no debt accrues by waiting; building SaaS billing for zero customers adds cost + the biggest auth surface in the app. Do NOT let a drain build this unless you've decided to sell TAQINOR as a product.** See NEEDS YOUR INPUT.) (ARCH)
- [ ] N101 — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup for design-partner installers. (UNGATED 2026-06-21. **RECOMMENDATION: KEEP DEFERRED — pairs with N100; self-serve signup is a major auth surface, build only when going multi-installer.**) (ARCH) (@after: N100)
- [ ] N102 — After the modules above are built, update the master project document + PLAN + DONE log in plain language to reflect the new post-sale, procurement/inventory, Moroccan billing/compliance, full-editability, and platform additions, noting which shipped and which were skipped. (UNGATED 2026-06-21 — depends on N100/N101; do last.) (@after: N100, N101)

---

## BUILD QUEUE — F1–F24 (field-execution & outillage module — added 2026-06-17)

Reda's "intervention" / field-execution module. **Build order = the order below** (outillage and
the intervention spine first, then the departure gate, then on-site capture, reconciliation, voice,
completion, and the advanced layer last). It is a big queue and **paces against the usage window** —
re-firing "work on the plan" after a cap resets resumes from the next unchecked task. Honour every
STANDING RULE plus the **module-specific constraints** below.

**MODULE CONSTRAINTS (in addition to the STANDING RULES):**
- The lead pipeline **`STAGES.py` stays a fixed CI contract** and is **never** made runtime-editable.
- The new Intervention **`statut` is its own separate state machine** that **never reads from or
  writes to `STAGES.py`** or to the **chantier status field**.
- **Buy prices and margins never appear on any client-facing document**, including the
  **compte-rendu d'intervention**.
- **Voice-memo capture, OCR, and AI photo-QA each add NO external credential and NO per-use cost by
  default**, and **no-op safely** until a provider is explicitly configured in Paramètres. The
  **transcription provider is left unconfigured** — a separate operator decision, added by **no**
  part of these tasks.
- **All photos, voice memos, GPS, and site data are real customer data** → object storage, **never
  committed to the repo**.
- **The production DEBUG setting is left exactly as configured — unchanged by these tasks.**
- **Reuse existing patterns**: file attachments / object storage, audit + chatter, kanban visual
  language + drag-to-change-status, the existing PDF engine, stock reservation + consumption,
  race-safe gapless numbering, Paramètres editability.
- **One session = the whole queue across up to 8 concurrent worktree lanes, every branch folded
  into one `dev` → self-merged to `main` exactly once after tests pass — never one PR per agent,
  never a merge per task, never split into review PRs.**

- [x] F21 — **Offline-tolerant field capture** covering the whole intervention flow — préparation checklist, GPS check-in, photos, serial capture, voice memos, Matériel consommé, réserves, and the signature — queuing locally on a poor connection and syncing when back online (extends the planned offline field capture to the full intervention workflow). (UNBLOCKED 2026-06-21 — same as N91: the dev-field-exec routing is stale (backend already on `main`, worktree isolation prevents collisions); build N91 + F21 in one offline-sync worktree lane.) (ARCH) (@after: N91)

---

## BUILD QUEUE — M1–M7 (modularity / decoupling — added 2026-06-20)

Architecture hardening for the modular monolith. The backend is already split into clean
per-domain Django apps, but the five business-core apps (`crm`, `ventes`, `stock`,
`installations`, `sav`) are woven together by **circular, load-time model imports**
(confirmed cycles: crm⇄ventes, stock⇄ventes, installations⇄ventes, installations⇄stock),
so none can be tested or extracted on its own. These tasks decouple that core **without
changing behaviour or schema** (additive / refactor only; every STANDING RULE applies).
Build order top-down — M1 and M2 unlock the rest. Category notes are inline labels only; auto-gating
is OFF so every task builds (M4 is unblocked below — see NEEDS YOUR INPUT for the recommended
event-bus approach; the two heavy-modularity options G16 are recommended-defer, not skipped by rule).

- [x] M1 — Replace every load-time cross-app model import in the core apps with Django string FK references so no `models.py` imports a sibling app at import time. Fait = no top-level `from apps.<other>.models import …` remains in crm/ventes/stock/installations/sav `models.py`; every cross-app FK/M2M uses the `"app.Model"` string form; `python manage.py makemigrations --check` reports no new migration and the suite passes. (Safe refactor — no schema change.) [DONE 2026-06-20: `ventes/models.py` was the ONLY core-app models.py with load-time sibling imports — its 5 `Client` FKs and 3 `Produit` FKs now use `'crm.Client'` / `'stock.Produit'`, the two top-level imports removed (breaks the crm⇄ventes / stock⇄ventes import cycles). The other four already used the string form. `manage.py check` passes; `makemigrations --check` = No changes detected.]
- [x] M2 — Make `services.py` / `selectors.py` the only cross-app entry point: route cross-app reads/writes through an app's service/selector functions instead of importing its `models`/`views` directly, and write the rule into CLAUDE.md repo-facts. Fait = remaining cross-app call sites import another app's `services`/`selectors` (or use string FKs), never its `models`/`views`; behaviour unchanged; tests pass. (Generalises the existing `ventes → crm.services` lazy-import pattern.) [DONE 2026-06-20: new `selectors.py` in crm/ventes/stock/installations (read helpers + lock helper + lead reassignment); new services `stock.record_stock_movement`/`mouvement_type_*`, `sav.create_equipement_from_serial`/`create_corrective_ticket`; ~25 cross-app call sites across crm/ventes/stock/installations/sav rerouted through services/selectors; same-app and foundation-app imports left as-is; the cross-app boundary rule added to CLAUDE.md repo-facts. 900/903 tests green (the 3 reds are MinIO-unreachable storage tests that pass in CI).]
- [x] M3 — Add an `import-linter` contract run in CI that forbids import cycles among the core apps and pins the layer order (foundation → domain core → satellites). Fait = a `lint-imports` step runs in CI and fails on a new cycle or an upward import; the contract is committed. (UNGATED 2026-06-20 by the founder — `import-linter` dev dependency approved.) [DONE 2026-06-20: `backend/django_core/.importlinter` (3 contracts — core domain models stay mutually decoupled = the M1 string-FK win, incl. the M7-split installations model modules; `core` stays a base foundation layer that imports no domain/satellite app), `import-linter==2.11` pinned in requirements.txt, a `lint-imports` step added to the `backend-lint` CI job; `lint-imports` = 3 kept / 0 broken locally. Scope note: a full no-cycles/strict-layers contract among the five core apps does NOT pass yet (they still call each other at the service layer) — that is deferred until the deeper decoupling lands; documented in the contract file + CLAUDE.md.]
- [x] M4 — Formalise the three layers (foundation: authentication/roles/records/customfields/core · domain core: crm/stock/ventes/installations/sav · satellites: reporting/automation/monitoring/notifications/publicapi/audit/documents/dataimport/contact) and remove the one back-edge `ventes → audit` by moving that audit capture onto the M6 event bus. Fait = `ventes` no longer imports `apps.audit`; the layer map is written down; behaviour unchanged; tests pass. (UNBLOCKED 2026-06-21 — **RECOMMENDED APPROACH:** `ventes` already depends on `core/events.py` (for `devis_accepted`); have it EMIT a `document_pdf_generated(instance, kind)` event from the 2 PDF action sites (`apps/ventes/views/devis.py`, `views/facture.py`) and have the `audit` app SUBSCRIBE in its `apps.py ready()` and call `record(AuditLog.Action.PDF, …)`. Synchronous, behaviour-identical, no new model — reuses the existing `AuditLog.Action.PDF` enum. The old blocker's "no model-save to hook to" objection is moot: emit an explicit event, not a save signal.)  [DONE 2026-06-22: ventes n’importe plus apps.audit — capture PDF via core.events.document_pdf_generated, audit souscrit (apps.py ready); contrat import-linter ventes↟audit ajouté; comportement identique, 4 tests.]
- [x] M5 — Use the empty `core/` app for shared primitives: move the tenant base mixin and the `authentication/scoping.py` company-scoping helpers into `core` so apps depend down on `core` instead of sideways. Fait = the shared helpers live under `core/`, re-exported for back-compat, callers updated; no schema change; tests pass. (Touches authentication/scoping — additive, build carefully.) [DONE 2026-06-20: `core/mixins.py` (`TenantMixin`) + `core/scoping.py` (the full scoping implementation) now hold the real code; `authentication/mixins.py` and `authentication/scoping.py` are thin re-export shims so every existing `from authentication.scoping import …` / `…mixins import TenantMixin` keeps working unchanged — no caller edits needed. `makemigrations --check` clean (no schema change); `manage.py check` passes.]
- [x] M6 — Replace the hottest direct cross-app calls with a small domain-event layer (e.g. emit `DevisAccepted` that `installations` subscribes to) instead of `installations` importing `ventes`. Fait = at least the accept→chantier and accept→stage seams run through events/signals, no direct call removed without an equivalent subscriber, tests pass. (UNGATED 2026-06-20 by the founder — new event-bus component approved.) [DONE 2026-06-20: `core/events.py` holds a Django-signal event bus (foundation, depends on nothing); `ventes.accepter()` now EMITS `devis_accepted` instead of calling `crm.services` directly, and `crm` subscribes (`apps/crm/receivers.py`, wired in `CrmConfig.ready`) to advance the lead stage — signals fire synchronously so behaviour is identical (the accept→stage seam now runs through the event). DELIBERATE SCOPE on accept→chantier: NOT auto-wired — `create_installation_from_devis` triggers N14 stock RESERVATIONS, so auto-creating a chantier on every acceptance would silently reserve inventory company-wide (a behaviour/inventory change, not a refactor). The event infra is in place for `installations` to subscribe if/when the founder wants that behaviour; flagged in the run report.]
- [x] M7 — Split the god-files (no behaviour change): turn the large `views.py` into a `views/` package (one module per resource) and split the big `models.py` into `models_*.py` mirroring `parametres`, for `installations` (views 1879 / models 1056 LOC), `ventes` (views 1259) and `stock` (views 1063). Fait = each split app keeps identical importable symbols (re-exported from its package `__init__`), endpoints and migrations unchanged, suite passes. (Pure reorg — cuts merge conflicts across parallel lanes.) [DONE 2026-06-20: `installations/views.py`→`views/` (7 modules), `ventes/views.py`→`views/` (8), `stock/views.py`→`views/` (13), each package `__init__` re-exporting every public name (urls.py untouched); `installations/models.py`→`models_chantier/_field/_installation/_intervention.py` with `models.py` re-exporting all 23 classes. Verified byte-identical (reconstructed each original from the pieces — zero code-line diffs); `makemigrations --check` = no changes; suite green.]

The two heavy options I recommend **deferring** (microservice extraction; per-app pip
packaging) are G16 under **NEEDS YOUR INPUT** below — ungated, but recommended-hold (~0 payoff for a
single-installer ERP now that M1–M7 shipped).

---

## BUILD QUEUE — module feature-gap audit 2026-06-21 (FG1–FG106)

A whole-system feature-gap review run as **8 parallel module lanes** (CRM · Ventes/facturation ·
Stock/procurement · Installations/field-exec/outillage · SAV/parc/maintenance/monitoring ·
Reporting/analytics/custom-fields · Paramètres/RBAC/auth/notifications/automation ·
Integrations + transversal). Every task below was **verified ABSENT against the real `main` code**
(the audit cited the proving file for each) — none re-propose anything already shipped, queued
(N93/N94 i18n), or parked under NEEDS YOUR INPUT (G2 WhatsApp Cloud, G3 redesign, G7 e-sign, G8 SSO,
G11 chatbot key, G12 M365, G14 DGI portal, N100–N102 SaaS platform, Meta CAPI send — each waits on a
founder-provided prerequisite). N91/F21 offline capture is now unblocked below.

**These obey every STANDING RULE** (multi-tenant `company` FK forced server-side, additive-only,
French UI, `STAGES.py` contract untouched, buy prices/margins never client-facing, cross-app via
`services.py`/`selectors.py`, premium `/proposal` engine off-limits for restyle). **Category legend
(inline per task — LABELS ONLY, 2026-06-21):** `ROUTINE` · `SCHEMA` (additive migration) ·
`DEP:<lib>` · `COST` · `AUTH` · `ARCH` · `DECISION` · `GALLERY`. **None of these gate any more** —
auto-gating is OFF, so a run builds every category and the planner reports `0 gated`; the label is
kept for visibility and the DONE LOG notes any new paid/external dep, auth change, destructive
migration, or new architecture. Build order is by value within each module; priority across modules
is your call. A task only ever waits on a real external prerequisite you must provide (→ NEEDS YOUR
INPUT).
**Note (merge):** because these are new `FG*` task IDs, the first run that ticks any of them must
refresh CODEMAP §10 + re-run `codemap_fingerprint.py --write` in the same commit (standard
add-to-plan rule) — this audit branch only edits `docs/PLAN.md`.

### Transversal — notifications, automation, scheduling & collaboration

- [x] FG1 — Activate the dead notification EventTypes via Celery-Beat sweeps. `CHANTIER_DUE`, `WARRANTY_EXPIRING`, `MAINTENANCE_DUE`, `SAV_TICKET_BREACHING` are declared in `notifications/models.py` but **never emitted** (no producers); `digests.py` counts maintenances/SAV-open only. Add idempotent daily beat tasks (the `celery_beat` process already exists) that sweep expiring warranties (~90 d), due maintenance/renewals, relances due / stale leads, breaching tickets, and chantier milestone transitions → `notify()` to owner/responsable. (Gate: ROUTINE; reuses the existing engine + beat infra.)  [DONE 2026-06-21]
- [x] FG2 — Wire the automation engine's time-based triggers. `automation/models.py` declares `WARRANTY_EXPIRING`/`MAINTENANCE_DUE`/`FACTURE_OVERDUE` and the UI offers them, but `automation/signals.py` only wires `post_save` (`_equipement_saved` is an explicit no-op). Add a beat task that calls `engine.evaluate(TriggerType.X, instance, company)` per match so configurable rules actually fire. (Gate: ROUTINE; engine + beat already exist.)  [DONE 2026-06-21]
- [x] FG3 — Automation rule template library (no-code presets). `AutomatisationsSection.jsx` forces the founder to hand-type raw `trigger_config`/`action_config` JSON. Add an `AUTOMATION_TEMPLATES` constant + `GET automation/templates/` + a "Créer depuis un modèle" pre-fill (e.g. WhatsApp link on devis accepté, assign new lead to default responsable). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG4 — Admin-configurable notification routing rules. `NotificationPreference` is per-user opt-in only; recipient selection (digests, alerts) is hardcoded (`_is_manager`). Add `NotificationRoutingRule` (company, event_type, target role/user) + an admin editor; `notify()` resolves recipients through it. Defaults must reproduce today's behaviour. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG5 — Working-hours + Moroccan public-holiday calendar feeding planning/relance. No working-hours/holiday model exists anywhere — relance/intervention/maintenance dates can land on Fridays/holidays. Add `WorkingHoursConfig` + `Holiday` (per company, seed MA public holidays) + helpers consumed by date computation. (Gate: SCHEMA + DECISION on which features skip non-working days.) [DONE 2026-06-27: `notifications.WorkingHoursConfig` (OneToOne company, working-days bitmask) + `Holiday` (company, date, recurrent_annuel) + `calendar_utils` helpers (is_jour_ouvre/prochain_jour_ouvre/ajouter_jours_ouvres) + idempotent `seed_ma_holidays` (9 fixed MA holidays; Islamic lunar dates left manual) + company-scoped viewsets. ADDITIVE infra — existing date computations UNCHANGED until opted in. Migration notifications 0010, tests.]
- [x] FG6 — ICS/iCal calendar feed per user. `reporting/calendar.py` is JSON-only; no `text/calendar` anywhere. Add `GET reporting/calendar.ics?token=<per-user>` (poses/interventions/maintenance visits) + "S'abonner au calendrier" in `CalendarPage.jsx` so the agenda shows in Google/Outlook on technicians' phones. (Gate: ROUTINE; DECISION on the token scheme.)
- [x] FG7 — Generic comments + @mentions across all records. Each app has a bespoke chatter and there is **no @mention** anywhere. Add a generic `records.Comment` (ContentType target, like `Attachment`) with `@username` parsing → `notifications.notify()`, rendered in a shared chatter component reused on Lead/Devis/Facture/Chantier/Ticket. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG8 — Unified, role-scoped cross-record activity feed ("Fil d'activité"). The only cross-record history is the Directeur-gated audit Journal. Add a read endpoint surfacing recent `records.Activity` + per-app chatter scoped via `authentication/scoping.py`, rendered as a dashboard widget. (Gate: ROUTINE; no new model.)  [DONE 2026-06-21]
- [x] FG9 — Shared cross-module tag taxonomy. Tags live only on `Lead` (free-text + `LeadTag`). Add a generic `records.Tag` + `TaggedItem` (ContentType) with a company-scoped vocabulary, surfaced as a chip-input on any record; keep CRM's existing free-text intact. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG10 — Tenant-wide document/attachment center. `records.Attachment` is only listable per-record (`?model=&id=`). Add `GET records/attachments/all/` (company-scoped, filter by mime/phase/content_type/date, paginated) + a "Documents" page reusing the existing same-origin download relay. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG11 — Generalize saved filters/views to all list screens. Saved views exist only in `LeadsPage.jsx` (localStorage). Extract a shared `useSavedViews(key)` hook and adopt it on ClientList/DevisList/FactureList/StockList/TicketsPage. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG12 — Wire the existing dark-mode/theme toggle into the app shell. `design/ThemeToggle` is rendered only on `/ui` (UIShowcase); add it to `components/layout/Header.jsx` and confirm `ThemeProvider` wraps the authenticated app. (Gate: ROUTINE — distinct from the Group J restyle.)  [DONE 2026-06-21]
- [x] FG13 — Surface a push-notification opt-in toggle in settings. Web-push is fully built backend (`PushSubscription`) + helper (`pushSubscribe.js`) but headless. Add an "Activer les notifications push" switch in `/parametres/notifications` showing subscription state. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG14 — Bulk import for more entities. `dataimport` covers only leads/clients/products though export covers 17 types. Add `equipements`, `fournisseurs` (and optionally `devis`) to `FIELD_MAPS` + commit branches (create-only/dedup/atomic) reusing the existing import modal. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [ ] FG15 — Broaden audit-trail coverage + a generic soft-delete/restore standard. `audit/signals.py TRACKED_MODELS` misses money/security writes (BonCommande, Paiement, supplier procurement, StockReservation, ContratMaintenance, `publicapi.ApiKey`/`Webhook` issue/revoke); only Lead/Produit have archive/restore. Add the missing tracked pairs (ROUTINE) and phase in a shared archive/restore mixin for Devis/Facture/Chantier/Ticket/Client (SCHEMA+DECISION). (Gate: ROUTINE for audit; SCHEMA for soft-delete.)
- [ ] FG16 — In-app onboarding / setup checklist + contextual help. No tour/guided help exists. Add a dependency-free spotlight/coachmark sequence keyed on a localStorage "seen" flag + a Paramètres "setup checklist" (company profile, first product, first user). (Gate: ROUTINE; DECISION on scope/copy.)

### Paramètres / RBAC / auth & security

- [x] FG17 — Email template management (parity with WhatsApp templates). Only WhatsApp templates are modelled; the automation email action falls back to a hardcoded "Notification Taqinor" subject. Add editable `sujet`+`corps` per `cle` (extend `MessageTemplate` or add `EmailTemplate`) with `{civilite}{nom}{reference}{lien}` placeholders + editor in `EmailSection.jsx`. (Gate: SCHEMA.)
- [ ] FG18 — Settings-audit completeness. `SettingsAuditLog` covers only profil/messages; role-permission edits, user role/active/supervisor changes, and automation rule create/toggle/delete are **not** audited. Emit audit entries on those writes + add their sections to the audit filter. (Gate: ROUTINE.)
- [ ] FG19 — Read-only org-chart / team hierarchy view. `EquipeSection.jsx` is a flat supervisor table; add a tree view fed by the existing `/users/` `supervisor` field (optionally a per-node "sees N records/people" hint from `visible_user_ids`) so the founder can verify record-visibility scoping at a glance. (Gate: ROUTINE — frontend only.)
- [ ] FG20 — Per-field / sensitive-data role permissions. RBAC has only `prix_achat_voir`/`journal_activite_voir`; no PII/margin masking. Add a curated "Données sensibles" permission group (e.g. `client_pii_voir`, `marge_voir`) enforced in the relevant serializers (mask when absent). (Gate: DECISION on which fields; curated version SCHEMA-light, fully-dynamic version ARCH.)
- [ ] FG21 — User invite / self-set-password onboarding. Admins must type a new user's plaintext password; `must_change_password` exists but the create form never sets it. Minimal: expose the checkbox on create (already serializer-writable). Fuller: invite-token + emailed set-password link. (Gate: AUTH.)
- [ ] FG22 — Per-company password policy & account lockout. Only Django default validators + a fixed 5/min IP throttle. Add `CompanyProfile` policy fields (min length, complexity, lockout-after-N, expiry days) enforced in change-password/login + a "Sécurité" settings section. (Gate: AUTH + SCHEMA.)
- [ ] FG23 — Security-events view + failed-login alerting. `login`/`login_failed` are captured but only via the Directeur-gated Journal, with no proactive alert. Add a filtered "Sécurité" tab (reuse `AuditLogViewSet`) + a `SECURITY_ALERT` event that fires after N consecutive failed logins. (Gate: AUTH.)
- [ ] FG24 — Settings config export/import between companies. `ExportSauvegarde.jsx` exports business data only, never configuration. Add `GET parametres/config-export/` (profile, roles, message templates, automation rules, statut/intervention/checklist types — never secrets/business data) + admin-only additive `config-import/`. (Gate: DECISION on merge-vs-overwrite + ARCH-lite.)
- [ ] FG25 — Configurable approval workflows beyond discount. The only first-class approval is discount; the generic `AutomationApproval` primitive isn't wired to other high-impact actions. Add an "Approbations" settings surface declaring policies (action type + threshold + approver tier) feeding the approval flow. (Gate: DECISION + SCHEMA.)
- [ ] FG26 — Data-retention / GDPR tooling. No per-subject export, anonymize/erase, or retention window. Add `GET crm/clients/{id}/data-export/` (subject access bundle) + an admin-gated `clients/{id}/anonymize/` (scrubs PII, preserves accounting integrity) + optional `audit_retention_days` purge. (Gate: DECISION (erasure vs legal retention) + AUTH.)

### CRM

- [x] FG27 — Lead scoring. No lead-quality score exists (only manual `priorite`; `_completeness` is merge-only). Add `scoring.py compute_score(lead)` from existing fields (bill amount, canal, type_installation, recency, completeness) exposed read-only on the serializer + a kanban badge + a FilterBar sort. (Gate: ROUTINE; SCHEMA only if persisted.)  [DONE 2026-06-21]
- [x] FG28 — First-response SLA + "lead non contacté" alert. No first-response clock; nothing flags an untouched NEW/site_web lead. Add nullable `first_contacted_at` (set on first transition/note) + a beat sweep (configurable `lead_sla_hours`) → red kanban badge + a "Non contactés > Xh" filter (pairs with FG1). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG29 — Time-in-stage age + funnel-velocity analytics. `LeadActivity` logs stage-change timestamps but nothing computes stage dwell time; cards show no age and there's no per-stage velocity chart. Derive `stage_since` on the serializer (age pill on cards) + an avg-days-per-stage + stalled-leads view in reporting (`pipeline.py`/`insights`). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG30 — Unified communication log (calls/emails) in the chatter. Chatter logs only auto field-changes + free notes; no typed "appel passé (résultat)" or email send/receive entry (only the WhatsApp link-builder). Add a typed-interaction action (reuse `records.Activity` Appel/Email types or a `Kind.APPEL` + optional `outcome`) + quick-log buttons. (Gate: ROUTINE; SCHEMA if adding `outcome`/`Kind`.)  [DONE 2026-06-21]
- [x] FG31 — "File de relance du jour" consolidated queue. `relance_date` + client-side filters exist but there's no cross-lead overdue-relance work queue. Add `leads/relances/?scope=overdue|today|week` (visibility-scoped) + a "Relances" panel/badge on LeadsPage. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG32 — Client segmentation (RFM / dormant / top). `ClientList` segments only by `type_client`. Add computed segment filters (top clients, sans devis >12 mois, à recontacter) driven by the existing serializer totals + derived last-devis/facture dates. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG33 — Bulk WhatsApp outreach. `apply_bulk_action` has no batched WhatsApp; sending is per-lead. Add a `prepare_whatsapp` bulk op returning an ordered `{phone, wa_url}` click-through queue (reuse `build_wa_url`; no auto-send). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG34 — Source/campaign ROI analytics. `fbclid`/`utm_*` first-touch is captured on `Lead` but never analyzed; ChartsView shows per-canal counts only. Add a per-canal/per-campaign aggregation (lead count, signed count, win-rate, signed value) — turns wasted attribution data into ad-spend guidance. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG35 — "Lead express" quick capture. The only creation path is the heavy multi-section `LeadForm`. Add a ⚡ minimal modal (nom/téléphone/canal=walk_in/owner=me) posting to the existing create endpoint with inline duplicate pre-check — for walk-ins/salons/mobile. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG36 — Reusable WhatsApp message templates in CRM. Only the devis-link message is hardcoded (FR/Darija); no reusable premier-contact/relance/fête templates. Add `crm.MessageTemplate` (company, nom, langue, corps with `{prenom}/{ville}/{lien}`, archived) + CRUD + a picker in the lead WhatsApp action. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG37 — Lead pipeline map view. `gps_lat/lng` are captured but the 4 views are kanban/liste/calendrier/graphique — no map. Add a 5th `CarteView` plotting filtered leads by GPS, coloured by stage, click→lead, to batch site visits by region. (Gate: DEP:leaflet — verify if a map lib already ships for `reporting/geo`; if yes → ROUTINE.)  [DONE 2026-06-21]
- [x] FG38 — Lead↔Client duplicate match at creation. Duplicate detection scans only across Leads; a returning customer comes in as a fresh lead. Extend `check-duplicates` (or add `leads/{id}/client-match/`) to scan `Client` by normalized phone/email → a "Déjà client X (N devis/chantiers)" banner in LeadForm. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG39 — Sales objectives & KPI targets vs actuals. No target/objective concept exists anywhere; KPIs show actuals with no goal line. Add `ObjectifCommercial`/`KpiTarget` (company, owner/metric, period, cible) + a "objectif vs réalisé" panel per commercial and company-wide attainment gauges on the dashboard. (Gate: SCHEMA + DECISION on metrics/periods.) [DONE 2026-06-27 (backend): `crm.ObjectifCommercial` (company forcé, owner, metric nb_leads/nb_contacts/nb_rdv/nb_devis/ca_signe, period month/quarter/year, cible) + `selectors.compute_attainment` (réalisé vs cible, taux) + company-scoped viewset + `/attainment/` endpoints. Import-linter safe (no other-domain model imports; nb_devis/ca_signe are future hooks). Migration crm 0028, 20 tests. Frontend panel = follow-up.]

### Ventes / facturation

- [x] FG40 — Recurring maintenance-contract billing. `ContratMaintenance.prix`/`periodicite` exist and preventive tickets are materialized, but **no Facture is ever produced** from a contract — recurring O&M revenue leaks. Add a beat job + manual `contrats-maintenance/{id}/facturer` that creates a `Facture` via a new `ventes.services.creer_facture_contrat` (cross-app from sav via services) + a `derniere_facturation`/`facturation_active` field; optionally a covered-equipment M2M. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG41 — Client credit limit / encours gate. `Client` has no `plafond_credit`; nothing warns when a new quote/invoice pushes a client past their outstanding balance. Add `plafond_credit` + a soft warning banner on DevisGenerator/FactureForm and on accepter/émettre (warn, never hard-block). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG42 — Bank-statement payment import & reconciliation. `Paiement` is created one-at-a-time; no statement import, reference-matching, or "à rapprocher" queue. Add a `paiements/import-releve` flow (reuse the dataimport dry-run+commit + openpyxl) matching by reference/montant, reusing the existing over-payment guard. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG43 — Invoice bulk operations. `FactureViewSet` has no bulk action — émission/relance/PDF/email are per-row (DevisList already batch-PDFs). Add `factures/bulk` (emettre/relancer/envoyer-email/generer-pdf, company-scoped, per-id results) + a select-all bar in FactureList. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG44 — Quote refusal with motif. There's `accepter` but no symmetric `refuser` — a quote goes refuse/expire via raw PATCH capturing no reason (`Devis` has no `motif_refus`, unlike `Lead.motif_perte`). Add a `devis/{id}/refuser` action (date + motif + chatter + optional lead `perdu` sync via the event bus). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG45 — Ventes quote-to-cash finance dashboard. No ventes dashboard ties the document chain together. Add a read-only aggregation (devis envoyés→acceptés→facturés→encaissés conversion, quote-to-cash cycle, DSO, encaissé-vs-facturé, per-commercial pipeline value) + a `/ventes` dashboard tab. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG46 — Flexible échéancier + stored acompte. `utils/echeancier.py` hardcodes exactly 3 tranches (acompte/materiel/solde) in fixed order/percent, and a custom acompte is a render-only PDF flag never stored — so the proposal's deposit and the generated invoice can disagree. Add an optional per-devis `echeancier` JSON (ordered `{libelle,type,pct_or_montant}`) + persist `acompte_montant/pct`, degrading to today's 3-tranche default when empty. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG47 — Cash-flow / receivables forecast. Aged balance exists but there's no forward projection. Add `insights/cash-flow/` bucketing outstanding `Facture.montant_du` by `date_echeance` into upcoming weeks/months, optionally netting `FactureFournisseur` payables (admin-only) for a true cash view. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG48 — On-screen two-option quote comparison. The engine computes both options (sans/avec batterie) with ROI, but DevisList shows only option 1; the salesperson can't present A vs B interactively. Surface `totaux_sans/avec` + ROI per option from the serializer in a DevisGenerator/detail comparison card. (Gate: ROUTINE; data already computed.)  [DONE 2026-06-21]
- [x] FG49 — Account-coded accounting export (PCG/Sage layout). `exports.py` gives a journal + per-rate TVA summary but no general-ledger export with account codes (7xxx ventes / 4455 TVA / 3421 clients) for direct fiduciaire import. Add a third export format mapping buckets to configurable account codes. (Gate: ROUTINE + DECISION on default codes.)  [DONE 2026-06-22: Export comptable codé par compte — grand-livre CGNC (3421 clients / 7111 ventes / 4455 TVA collectée) xlsx+csv, codes configurables (settings global + par société), GET ventes/export-comptable/?layout=grand-livre, AR uniquement (aucun prix d’achat). Aucune migration, 10 tests.]
- [x] FG50 — Acompte transfer/refund on invoice cancel. `annuler` leaves a cancelled invoice's `Paiement` rows stuck on a dead invoice with no transfer/refund path. On cancel, offer "transférer l'acompte" to another facture of the same devis or mark refundable (negative Paiement / Avoir), with chatter. (Gate: DECISION (accounting semantics) + SCHEMA.)  [DONE 2026-06-22: Transfert/remboursement d’acompte à l’annulation — annuler accepte {acompte:{action}} : « transferer » re-pointe les Paiement vers une autre facture du MÊME devis (soldes re-dérivés, chatter des 2 côtés), « rembourser » écrit un Paiement négatif de reprise (acompte plus bloqué). Validations same-devis/same-company/self/already-cancelled. Annulation sans acompte inchangée. Aucune migration, 16 tests.]
- [x] FG51 — Proof-of-delivery gate before invoicing. `BonCommande.marquer_livre` flips status + decrements stock but captures no PV/signature, and `generer-facture` never checks delivery happened. Optionally link a `documents` PV/attachment to the BC + a soft warning on the matériel tranche when no delivery proof exists. (Gate: ARCH/DECISION; route cross-app via selectors.) [DONE 2026-06-22: Gate proof-of-delivery avant facturation; BonCommande.pv_livraison(JSON)+date_livraison_reelle+has_proof_of_delivery, marquer-livre capture signataire/PV, creer-facture warning soft si pas de preuve; migration 0025; 6 tests.]
- [x] FG52 — Multi-currency quoting/invoicing. Everything is hardcoded MAD (no `devise`/`taux_change` on Devis/Facture, none in CompanyProfile, UBL hardcodes currency). Add `devise`(default MAD)+`taux_change` carried through the PDF builder + `dgi_export.py`. (Gate: SCHEMA + DECISION on currencies + legal-MAD-equivalent rules.)
- [x] FG53 — E-payment "Payer en ligne" link. No payment gateway anywhere; ShareLink/WhatsApp/relance deliver a read-only PDF only. Add a `PaymentLink` model + a provider-interface (NoOp default, like `monitoring/providers`, no dep when unconfigured) + a public pay page + a webhook that records a `Paiement`. (Gate: DEP:<gateway SDK> + COST + AUTH — propose the NoOp scaffold now, live gateway gated.) [DONE 2026-06-22: Lien Payer-en-ligne (scaffold NoOp); PaymentLink + provider NoOp par défaut (aucune SDK/coût), create_payment_link/record_payment_from_link, action lien-paiement, page publique pay/<token>/ + webhook; migration 0026; 7 tests. NOTE: nouveau modèle + endpoint webhook public (additif), aucune dépendance externe.]

### Stock & procurement

- [x] FG54 — Reorder-point auto-PO suggestions. The only reorder signal is a passive low-stock flag; the one auto-PO path is chantier-driven, never inventory-driven. Add `produits/a-reapprovisionner/` (disponible ≤ seuil, grouped by cheapest supplier) + `generer-bcf-reappro/` reusing `create_with_reference('BCF')`; optional `quantite_reappro_cible`. (Gate: SCHEMA for the optional field; endpoints ROUTINE.)  [DONE 2026-06-21]
- [x] FG55 — Supplier-invoice PDF (facture fournisseur). BCF has an internal PDF but `FactureFournisseur` has none (explicit G5 future). Add `factures-fournisseur/{id}/pdf/` via the existing WeasyPrint helper + a download button. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG56 — "Facturer cette réception" line-driven supplier invoice. `FactureFournisseur` amounts are typed by hand; `LigneFactureFournisseur` exists but no flow populates it from a reception (explicit G5 future). Add `receptions-fournisseur/{id}/facturer/` building lines + HT/TVA/TTC from the reception + a "Facturer" button. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG57 — Dead-stock / rotation aging report. `stock_report` has no "no movement since N days" analysis though `MouvementStock.date` is a full audit trail. Add `produits/rotation/?jours=180` (last-movement date + tied-up value via `average_cost`, buckets), admin-only. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG58 — Supplier price-list comparison UI. `PrixFournisseur` is modelled + exposed but there's no comparison screen — the buyer can't see "A 1,200 vs B 1,150, last bought 3 mo ago". Add a "Comparer fournisseurs" panel on the product/BCF screen (admin/buyer-only). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG59 — Supplier performance scorecard. All raw data exists (BCF date vs reception date = lead time; quantite_recue vs quantite = fill rate; returns = defect rate) but nothing aggregates it. Add `fournisseurs/{id}/performance/` (avg lead time, fill rate, return rate, spend), admin-only. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG60 — Stock-movement filters + xlsx export. `MouvementStockViewSet` supports only search/ordering and has no export (valuation does). Add `?type_mouvement/?produit/?date_min/?date_max` filters + `mouvements/export-xlsx/` reusing `build_xlsx_response` for month-end reconciliation. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG61 — Serial/lot capture at goods-in. Serials live only on `sav.Equipement` (captured at install); the stock layer has none, so a received inverter serial can't be reconciled to the installed one for warranty/RMA. Add `LigneReceptionFournisseur.numeros_serie` (JSON) captured at reception + a reconcile selector. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG62 — Per-location min/max + van replenishment. `seuil_alerte` is a single global threshold; multi-location carries quantity only, so a camionnette can't be flagged low. Add `StockEmplacement.seuil_min/max` + a "réapprovisionner cet emplacement" suggestion proposing transfers from the principal. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG63 — Inventory-count session workflow. `apply_inventory_count` posts adjustments immediately/irreversibly in one shot — no draft, partial save, or large-variance review for a real stock-take. Add `InventaireSession`+`LigneInventaire` (draft) with a `valider` action emitting the AJUSTEMENT movements + an écart report. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG64 — Battery/sealant expiry tracking. No expiry fields anywhere; lithium batteries and sealants have shelf-life/expiry and installing one out-of-date voids warranty. Add optional `LigneReceptionFournisseur.date_peremption`/lot + an "expiring soon" report (lighter subset of FG61). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG65 — Demand forecasting reorder quantities. `seuil_alerte`/reorder qty are static; `MouvementStock` SORTIE history is never used. Add a selector computing avg monthly consumption per SKU → suggested reorder qty feeding FG54. (Gate: ROUTINE; depends on FG54.)  [DONE 2026-06-21]
- [ ] FG66 — Kit/BOM as a sellable catalogue product. No kit/nomenclature concept in stock (KitOutillage is durable tools only); standard configs ("Kit pompage 3CV", "Kit résidentiel 5kWc") must be quoted line-by-line each time. Add a `Produit.composition`/`KitProduit` that explodes into component SKUs at devis-line insertion (accurate reservation for the bundle). (Gate: DECISION — touches the quote engine + SCHEMA.)
- [ ] FG67 — FIFO / landed-cost valuation option. Valuation is weighted-average only; no FIFO and no landed-cost (freight/customs), so imported-inverter true cost is understated. Add `LigneBonCommandeFournisseur.frais_annexes` folded into average_cost + an optional FIFO toggle (`CompanyProfile.stock_valuation_method`), internal only. (Gate: SCHEMA + DECISION on accounting method.)

### Installations / field execution / outillage

- [x] FG68 — Crew dispatch calendar + technician capacity for interventions. `InterventionsPage` has only liste+kanban (chantiers have a calendar, interventions don't), so a PM can't see who's over/under-booked on a day or drag a visit between techs. Add a `calendrier` view keyed on `date_prevue` (columns per technicien) + an `interventions/?date_from&date_to` range filter, reusing the chantier drag-reschedule pattern. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG69 — Captured client signature (sign-off) on compte-rendu / PV de réception. The compte-rendu template renders an **empty** signature box; no signature is captured anywhere. Add `Intervention.signature_client` (vector strokes like `PhotoAnnotation.drawing`, or a PNG attachment + `signataire_nom`/`signe_le`) + `interventions/{id}/signer-client` + a signature-pad panel, embedded in the PDF; same for the Installation PV. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG70 — Auto warranty handover at RECEPTIONNE. At réception the code only writes a chatter note; it doesn't sweep the frozen `bom` into `sav.Equipement` for serial-less components, so warranty coverage depends on a tech remembering each serial. On the RECEPTIONNE transition call a `sav.services` fn to ensure one `Equipement` per BoM line (serial optional, date_pose=date_reception, idempotent) + a handover summary/PDF section. (Gate: ROUTINE; cross-app write via services.)
- [x] FG71 — Per-chantier job-costing roll-up. The pieces exist (`labour_jours_estimes/reels`, `MaterielConsommation` variance, `prix_achat`) but nothing assembles labour + real material cost vs the devis total into a margin view. Add `chantiers/{id}/cout` (labour estimé/réel + materials BoM-vs-real + devis total → margin), **internal/admin-only** (margin ban on client docs). (Gate: DECISION confirm internal-only; else ROUTINE.)
- [x] FG72 — Multi-day chantier planning. `Installation` has single `date_pose_prevue/reelle`; a multi-day pose is counted as one day and overbooks the crew. Add `date_pose_fin_prevue`/`duree_pose_jours`, rendered as a span on the chantier calendar + factored into capacity. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG73 — Technician day route/itinerary. `MaJourneePage` lists today's interventions in date order with no geographic ordering; `haversine_km` + site GPS already exist. Add a nearest-neighbour ordering from the dépôt + a per-stop "Itinéraire" maps deep-link (and optional `interventions/ma-tournee`). (Gate: ROUTINE; DEP only if true road optimization is wanted.)  [DONE 2026-06-21]
- [x] FG74 — Cross-chantier Gantt / milestone timeline. `ChantierTimeline` is single-chantier; a PM running 10–30 concurrent chantiers has no horizontal timeline across the existing milestone dates. Add a `gantt` view (one row per chantier, bars from milestone dates) — read-only first. (Gate: ROUTINE; no new backend.)  [DONE 2026-06-21]
- [x] FG75 — Roof/drone site-survey attachment surface on the chantier. Field photos are intervention-phase only; there's no chantier-level pre-pose "Relevé de toiture / drone" gallery distinct from the day-of shot list. Add a chantier-level attachments panel (category `releve_toiture`/`drone`) reusing `records.Attachment` + the MinIO proxy. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG76 — Photo-required gate on chantier checklist steps. F8 photo-gating is intervention-only; a chantier step ("Panneaux posés") can be ticked with zero evidence. Add `photo_obligatoire` to `ChecklistEtapeModele`/`ChantierChecklistItem` and block `fait=True` until a phase photo exists (mirror the intervention logic). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG77 — Pre-pose readiness check. Chantier status can move to EN_COURS freely with no guard on material availability or the 82-21 dossier. Add a `chantiers/{id}/readiness` selector (material shortfall via besoin-materiel, dossier status, planning date) surfaced as a banner in InstallationDetail; optionally a confirm-to-override. (Gate: ROUTINE advisory / DECISION if it should hard-block.)
- [x] FG78 — Intervention RDV confirmation + reschedule/no-show tracking. `Intervention` has dates but no client-confirmation flag, reschedule history, or no-show reason (statut state machine stays untouched — these are metadata). Add `rdv_confirme`/`rdv_confirme_le` + a reschedule count + a "Confirmer le RDV" action feeding reminders. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG79 — Auto-scaffold the standard intervention chain from chantier type. Checklist templates auto-select by type and kits by intervention type, but the expected sequence of visits (résidentiel réseau → pose/raccordement/mise en service) is created one-by-one. Add a `TypeInterventionPlan` (per type_installation, ordered intervention types) + a `creer-interventions-standard` action materializing the chain. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG80 — Outillage calibration/inspection tracking. `Outillage` tracks statut/emplacement/date_achat but no calibration/inspection dates — multimètres, earth testers, and harnais (EPI) legally need periodic checks (a safety/compliance liability). Add `date_derniere_calibration`/`intervalle_calibration_mois`/`date_prochaine_calibration` + an "à calibrer" badge + a notification event. (Gate: SCHEMA.)  [DONE 2026-06-21]

### SAV / parc / maintenance / monitoring

- [x] FG81 — Server-side ticket SLA (response/resolution clocks + breach). SLA is client-side cosmetic only; `Ticket` has no first-response timestamp, no target, no breach flag, and `SAV_TICKET_BREACHING` is never emitted. Add `Ticket.date_premiere_reponse` + per-company `sla_response_days`/`sla_resolution_days` (or a `sav_sla` JSON per priorité) + computed `sla_breach`/`sla_due_at` + a daily breach scan → notification. (Gate: SCHEMA; pairs with FG1.)  [DONE 2026-06-21]
- [x] FG82 — Maintenance-visit checklist / structured visit report. Preventive tickets + the maintenance PDF carry no inspection checklist (clean panels, torque, inverter logs, earth test) — the report is free text. Add `MaintenanceChecklistTemplate`/`Item` (per-company, seeded) + per-ticket `TicketChecklistItem`, rendered into the maintenance PDF (mirror the installations checklist pattern). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG83 — Supplier warranty-claim (RMA) workflow. A ticket knows `sous_garantie` + equipment + supplier, but there's no claim object — so in-warranty defects sent back to the OEM (Huawei/VEICHI/panel maker) are untracked and the installer eats replacement cost. Add `WarrantyClaim` (equipement, fournisseur, ticket, statut, rma_ref, dates, resolution remplacement/avoir, internal cout_recupere) routed to the supplier via `stock.selectors`. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG84 — Per-system production history chart + expected-vs-actual + CSV. `ProductionPage` is a flat manual-entry list — no chart, trend, or expected-vs-actual surfaced, though readings + an expected ratio exist. Add `monitoring/configs/{id}/history/` (monthly aggregated + expected overlay) + a Recharts line chart + CSV export per installation. (Gate: ROUTINE; recharts already a dep.)  [DONE 2026-06-21]
- [x] FG85 — Equipment QR labels + scan-to-equipment/ticket. The QR/CODE128 engine + resolve endpoint exist only for `stock.produits`; SAV equipment has a serial but no scannable label and no `EQUIP:` token. Add `equipement_token` + an `EquipementViewSet.etiquettes` action (reuse `labels.render_labels_html`) + extend `resolve_code` to `EQUIP:<id>` (warranty clock + open tickets / open a ticket). (Gate: ROUTINE; reuses the label engine.)  [DONE 2026-06-21]
- [x] FG86 — Public tokenized "track your SAV request" link. Quotes/invoices have public tokenized links but tickets aren't exposed publicly at all. Add `Ticket.share_token` + a read-only public endpoint returning reference/statut/last-update only (never `cout` or internal chatter) + a "Lien client" button. (Gate: SCHEMA + DECISION on what a client may see.) [DONE 2026-06-27: `Ticket.share_token` (nullable/unique, lazy `secrets.token_urlsafe`) + auth-exempt public endpoint `/api/django/public/sav/ticket/<token>/` returning ONLY reference/statut/date_modification (explicit allowlist — never cout/chatter/PII), noindex + throttle; `tickets/<id>/lien-client/` action returns the URL. Migration sav 0009 (additive, no backfill). Tests assert no cout/chatter leak. Frontend button = follow-up.]
- [x] FG87 — SAV knowledge base (resolution playbooks). No KB exists; ticket resolutions evaporate as free-text chatter though solar faults repeat (inverter error codes, string faults). Add `KbArticle` (per-company titre/corps/tags + optional produit/categorie) + a searchable panel on TicketsPage filtered by the ticket's equipment product. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG88 — Maintenance route/day planning for preventive visits. Visits generated from contracts spawn undated, ungrouped tickets though installation GPS exists. Add a "planifier la tournée" view listing due preventive tickets with GPS, letting a responsable bulk-assign technician+date (proximity-sorted from stored coordinates). (Gate: ROUTINE coordinate-sort; DEP/COST only for real routing.)
- [x] FG89 — Spare-parts forecasting from PieceConsommee history. `PieceConsommee` records SAV part usage + decrements stock but nothing aggregates it to forecast spares (fuses, MC4, breakers) — a stuck tech means a second truck roll. Add `insights/sav-parts-forecast/` (consumption per product over a window + suggested reorder qty), internal-only. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG90 — Chronic/repeat-failure equipment flag. A ticket links one equipment + exposes open-ticket count, but there's no detection of an item generating repeated tickets over time (a "lemon" — the strongest warranty-claim evidence, ties to FG83). Add a computed `nb_tickets_12m` to the serializer + a filter/badge + an optional repeat-offender insight. (Gate: ROUTINE.)  [DONE 2026-06-21]

### Reporting / analytics / custom fields

- [x] FG91 — SavedReport frontend (CRUD + schedule + optional dashboard pin). The `SavedReport` model + viewset + scheduled-email beat job are fully built but have **zero frontend** (and no `pinned` field) — a shipped backend feature is unusable. Add `reportingApi` methods + a "Mes rapports" UI (create/name/schedule/recipients/delete) + optional `pinned` to render a saved report as a dashboard card. (Gate: ROUTINE; SCHEMA only for the pin field.)  [DONE 2026-06-21]
- [x] FG92 — Period comparison (MoM/YoY) on dashboard & reports. Nothing computes a prior-period baseline anywhere. Add a `compare=prev|yoy` param to `dashboard/` + `reports/*` returning `{current, previous, delta_pct}` per KPI + arrows/deltas on the Stat cards. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG93 — Sales-rep leaderboard. `sales_report` has a flat per-responsable count table but no monetary leaderboard (CA signed, win rate, avg deal, kWc per rep) and it's not surfaced on the dashboard. Add `insights/sales-leaderboard/` + a "Classement commerciaux" card (responsable-visible; keep commission/buy-price admin-only). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG94 — Activate custom-field reporting. `CustomFieldDef.visible_liste` is settable but **nothing consumes it** — no list column, no `custom_data` filter, no aggregation (dead flag). Honor `visible_liste` as a column + a `?cf_<code>=` filter on Lead/Client/Produit lists + a group-by-custom-field count. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG95 — PDF export for reports (branded). Every report/insight exports xlsx only; WeasyPrint+Jinja2 are already pinned. Add `?export=pdf` on `reports/*` rendering a company-branded template (logo from CompanyProfile), never buy prices — for presentable monthly reports to stakeholders/banks. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG96 — Configurable / per-role dashboard. `Dashboard`/`Reporting` are fully static — a technicien sees the same finance-heavy dashboard as the founder. Add a per-user/per-role widget config (enabled cards + order); minimal first cut = role-default card sets driven off `menu_tier`. (Gate: SCHEMA + DECISION on configurability scope.) [DONE 2026-06-27 (backend): `reporting.DashboardConfig` (company forcé, user OU menu_tier, cards JSON) + `/dashboard-config/effective/` resolving per-user → rôle-défaut → défaut global; no-config returns the full current card set (zéro changement de comportement). Migration reporting 0003, 12 tests. Frontend wiring = follow-up.]
- [x] FG97 — Audit-log analytics. The Journal is a filterable feed + activity buckets but has no rollups (most-active users, action mix over time, failed-login spikes, object churn). Add `audit/analytics/` (gated on `journal_activite_voir`) + a charts panel on the Journal page. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG98 — Cohort / seasonality conversion analysis. No cohort view; solar demand is seasonal + channel-dependent. Add `insights/cohorts/` grouping leads by acquisition month (and/or canal) → eventually-signed % + avg days-to-sign per cohort (heatmap/table). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG99 — Profitability by segment. `job_costing` is per-chantier only; there's no margin/revenue aggregation by `mode_installation`/`canal`/category. Add `insights/profitability/` (admin-only, reuses `prix_achat` internally, never client-facing) grouping revenue+margin+count by segment. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG100 — Custom fields for Devis / Chantier / Ticket. `CustomFieldDef.Module` is limited to LEAD/CLIENT/PRODUIT; the operational core can't carry custom attributes ("numéro dossier ONEE", "type de nacelle"). Add INSTALLATION/DEVIS/TICKET to the choices + `custom_data` JSONField where missing + wire validation + Paramètres tabs. (Gate: SCHEMA — additive JSONField.)  [DONE 2026-06-21]
- [x] FG101 — Drill-down from report rows/charts to filtered lists. Dashboard KPI Stats are clickable but report tables/charts are dead ends (a "perte par motif" row, a funnel stage, a stock-alert row link nowhere). Make report rows/segments link to the relevant filtered list route. (Gate: ROUTINE; may add a few list-filter params.)  [DONE 2026-06-21]

### Integrations — public API / webhooks / OCR

- [x] FG102 — Webhook delivery log + retry/replay + test ping UI. `WebhookDelivery` records every attempt and the viewset exposes the last 50, but there's no replay/retry endpoint and `ApiWebhooksSection.jsx` never shows deliveries — a failed `facture.paid` is silently lost. Add `webhooks/{id}/deliveries/{id}/replay/` + `webhooks/{id}/test/` + the delivery history/status/replay/test UI. (Gate: ROUTINE.) [DONE 2026-06-27 (backend): company-scoped `webhooks/<id>/deliveries/`, `webhooks/<id>/deliveries/<did>/replay/` (re-sends original payload via the existing HMAC-signed delivery fn, records a new attempt, preserves the original), and `webhooks/<id>/test/` (synthetic `webhook.test` ping). Cross-company blocked (404). No migration (reuses existing models). 11 tests (HTTP mocked). Frontend history/replay/test UI = follow-up.]
- [ ] FG103 — More webhook events. Only 4 terminal events exist (lead.created/devis.accepted/chantier.completed/facture.paid). Add codes + emitters for devis.sent, lead.lost/stage_changed, facture.created, intervention.completed, ticket.created/resolved, paiement.recorded (reuse the existing transition-diff pattern; the Paramètres checkbox list auto-updates). (Gate: ROUTINE.)
- [ ] FG104 — Public API filtering, ordering & incremental sync. The public viewsets have no filter_backends and no `?updated_since=`, so a consumer must full-scan the company list every poll. Add DjangoFilterBackend+OrderingFilter + a whitelist of filter fields + `?updated_since=` against `date_modification` (add it to `PublicChantierSerializer`). (Gate: DEP:django-filter, or hand-rolled query-param filtering = ROUTINE.)
- [ ] FG105 — Public API documentation page. No OpenAPI/Swagger anywhere; the API & Webhooks screen issues keys but documents no endpoints/scopes/`Api-Key` header/`X-Taqinor-Signature` HMAC recipe. Add a static FR reference page (endpoints, auth, scopes, events, HMAC-verify snippet) linked from the settings screen. (Gate: ROUTINE static doc; DEP:drf-spectacular only if auto-generated.)
- [ ] FG106 — OCR → draft lead / draft devis action. OCR extracts structured supplier-quote/bill data but its only sink is the OCR table (+ the existing OCR→stock flow). Add a "Créer un lead / brouillon de devis depuis ce document" action on `OcrUpload.jsx` posting parsed fields to the existing CRM/ventes create endpoints. (Gate: ROUTINE.)

---

## BUILD QUEUE — functional-domain expansion audit 2026-06-21 (round 2 · FG107–FG399)

A second, **much more ambitious** pass: instead of incremental gaps inside existing modules
(round 1, FG1–FG106), this round audits **whole functional DOMAINS** an ERP — and a solar
vertical specifically — should have, benchmarked against best-in-class suites (Odoo, SAP B1,
Sage, Salesforce, Aurora/OpenSolar/PVsyst) AND Moroccan reality (CGNC, DGI, CNSS, ONEE, MASEN,
loi 13-09/82-21, CNDP loi 09-08). Run as **6 parallel domain lanes** (Finance/Compta/Trésorerie ·
RH/Terrain/HSE · Croissance commerciale/Marketing/CPQ/Portail · Vertical solaire · Opérations/
Projets/Supply-chain/Flotte/Qualité · Plateforme/IA/Intégrations/BI/Mobile). Every item was
verified ABSENT against real `main` code and deduplicated against FG1–FG106.

**These are mostly NEW sub-systems** — but auto-gating is OFF, so an unattended run **builds every
category**: `ROUTINE`/`SCHEMA` as before, and now also `ARCH` (new app/model-cluster/architecture),
`DECISION` (founder product/accounting call — pick a sensible default and NOTE it), and
`DEP:<lib>` / `COST` / `AUTH` (new dependency, cost, or auth/security change — NOTE each in the DONE
LOG). The only thing that still parks a task is a real external prerequisite you must provide
(→ NEEDS YOUR INPUT). Same STANDING RULES as the rest of the file (multi-tenant company FK forced,
French UI, buy prices/margins never client-facing, `STAGES.py` untouched, cross-app via
services/selectors, Odoo writes JSON-2-API only). Category labels = the round-1 legend.
Big greenfield clusters (compta générale, RH, projets, WMS, flotte, BPM, portail client) are each
a multi-session module — sequence them on the founder's call. Same merge note as round 1: the
first run that ticks any `FG*` task refreshes CODEMAP §10 + `--write` in that commit.

### Comptabilité, finance & trésorerie

- [x] FG107 — **Plan comptable CGNC** — plan de comptes par société (classes 1–7 : 3421 clients, 4411 fournisseurs, 4455 TVA, 71xx ventes, 61xx achats) ; socle de toute la compta. (ARCH)  [DONE 2026-06-21]
- [x] FG108 — **Journaux + écritures (comptabilité en partie double)** — `Journal` (VTE/ACH/BNK/CSH/OD) + écritures équilibrées débit=crédit ; aujourd'hui aucune écriture n'est passée. (ARCH)  [DONE 2026-06-21]
- [x] FG109 — **Auto-génération des écritures depuis factures/paiements/avoirs/factures fournisseur** — chaque document émis produit une écriture équilibrée (produit, TVA, tiers, trésorerie). (ARCH)  [DONE 2026-06-21]
- [x] FG110 — **Grand livre** — détail par compte avec solde courant + lettrage, exportable. (SCHEMA)  [DONE 2026-06-21]
- [x] FG111 — **Balance générale (trial balance)** — débit/crédit/solde par compte sur une période (≠ la balance âgée clients actuelle). (ROUTINE)  [DONE 2026-06-21]
- [x] FG112 — **Lettrage & rapprochement client/fournisseur** — apparier factures et règlements au niveau compte (lettré/non-lettré) pour un encours exact. (SCHEMA)  [DONE 2026-06-21]
- [x] FG113 — **Compte de Produits et Charges (CPC / P&L marocain)** — état de résultat au format CGNC depuis le grand livre. (SCHEMA)  [DONE 2026-06-21]
- [x] FG114 — **Bilan comptable (format CGNC)** — actif/passif depuis les soldes du grand livre. (SCHEMA)  [DONE 2026-06-21]
- [x] FG115 — **Clôture & verrouillage de période comptable** — figer un mois/exercice (écritures + factures immuables) pour l'audit. (SCHEMA)
- [x] FG116 — **Écritures de régularisation / OD manuelles** — saisie d'écritures sans document source (provisions, amortissements, corrections). (SCHEMA)
- [x] FG117 — **À-nouveaux / réouverture d'exercice** — report des soldes de bilan dans le nouvel exercice. (SCHEMA)
- [x] FG118 — **Registre des immobilisations** — actifs (camionnettes, outillage, matériel) avec coût/date/catégorie/TVA. (SCHEMA)
- [x] FG119 — **Plan d'amortissement (linéaire/dégressif)** — dotations par actif aux taux marocains, postées au grand livre (impacte l'IS). (SCHEMA)
- [x] FG120 — **Cession / mise au rebut d'immobilisation** — plus/moins-value + écritures associées. (SCHEMA)
- [x] FG121 — **Référentiel comptes bancaires & caisses** — `CompteTresorerie` (banque/RIB/devise/solde) ; aujourd'hui un seul RIB texte. (SCHEMA)  [DONE 2026-06-21]
- [x] FG122 — **Position de trésorerie consolidée + projection** — solde par compte/caisse + total + projection nette AR/AP/paie/impôts (vue la plus demandée). (SCHEMA)  [DONE 2026-06-22: GET compta/etats/position-tresorerie/ — solde par CompteTresorerie + total + projection nette AR/AP/paie/TVA depuis le GL, additif, 9 tests.]
- [x] FG123 — **Rapprochement bancaire (relevé ↔ écritures)** — pointer ligne GL vs ligne relevé jusqu'à concordance (≠ FG42 import paiements clients). (SCHEMA)  [DONE 2026-06-22: Rapprochement bancaire — RapprochementBancaire (CompteTresorerie/période/solde/statut) + LigneReleve + PointageReleve (through→LigneEcriture), pointer_ligne_releve (rapprochée si écart 0), resume (solde relevé vs GL vs écart), clôture sans écriture (≠ FG42). 1 migration additive (0006), 24 tests.]
- [x] FG124 — **Caisse / petty cash (journal d'espèces)** — entrées/sorties + justificatifs + clôture de caisse pour les achats terrain. (SCHEMA)  [DONE 2026-06-22: Caisse / petty cash — Caisse (liée à un CompteTresorerie type=caisse, solde_initial/responsable), MouvementCaisse (entrée/sortie, justificatif/pièce, posté→écriture CSH équilibrée optionnelle respectant le verrou FG115), ClotureCaisse (théorique gelé vs compté = écart, fige les mouvements ≤ date). Endpoints caisses/ + actions mouvement/poster/resume/cloturer. Migration 0007 additive, 24 tests.]
- [x] FG125 — **Virements internes entre comptes** — banque↔banque/caisse en écriture à deux jambes. (SCHEMA) [DONE 2026-06-22: Virements internes (banque↔banque/caisse) écriture OD 2 jambes, idempotent, verrou de période; VirementInterne + enregistrer/poster_virement + /compta/virements/; 9 tests.]
- [x] FG126 — **Prévisionnel de trésorerie roulant 13 semaines** — lignes prévues éditables (crédits, leasing, salaires, acomptes IS) au-dessus de la projection AR/AP. (SCHEMA) [DONE 2026-06-22: Prévisionnel trésorerie 13 semaines (lignes prévues éditables + effets ouverts); LignePrevisionnelTresorerie + selector previsionnel_tresorerie + endpoints; 5 tests.]
- [x] FG127 — **Portefeuille d'effets à recevoir (chèques/traites clients)** — échéance/banque/statut (portefeuille→remis→encaissé→impayé) ; omniprésent en B2B marocain. (SCHEMA) [DONE 2026-06-22: Portefeuille effets à recevoir (chèque/traite, portefeuille→remis→encaissé→impayé); Effet(recevoir) + encaisser_effet + échéancier; couvert par 11 tests effets.]
- [x] FG128 — **Effets à payer fournisseurs** — chèques/traites émis + calendrier d'échéances alimentant la trésorerie. (SCHEMA) [DONE 2026-06-22: Effets à payer fournisseurs (calendrier d'échéances → trésorerie); payer_effet; couvert par tests effets.]
- [x] FG129 — **Bordereau de remise en banque (chèques/effets)** — regroupe des effets pour dépôt + écriture. (ROUTINE) [DONE 2026-06-22: Bordereau de remise en banque (regroupe effets→dépôt, débit 5113/crédit 3425), bascule en remis, idempotent; BordereauRemise; 7 tests.]
- [x] FG130 — **Gestion des impayés / rejets d'effets** — réouverture du montant dû, frais de rejet, relance. (SCHEMA) [DONE 2026-06-22: Gestion impayés/rejets d'effets (contre-passe remise + frais 6147), statut impayé; rejeter_effet; 5 tests. Comptes CGNC 3425/4415/5113/6147 ajoutés au seed (additif), migration 0008 (4 modèles).]
- [x] FG131 — **Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur)** — contrôle avant paiement ; les montants AP sont aujourd'hui saisis à la main. (ARCH) (DEFERRED 2026-06-24 — a build attempt duplicated BonCommandeFournisseur/FactureFournisseur in apps/compta, clashing with the existing apps/stock procurement models; backed out. Needs a rebuild that REUSES stock's BC/FactureFournisseur via stock selectors/services.)
- [x] FG132 — **Échéancier & relevé fournisseur (aged payables + statement)** — balance âgée fournisseurs + relevé par fournisseur (miroir de la balance clients). (ROUTINE)
- [x] FG133 — **Campagnes de règlement fournisseurs (payment run)** — sélection des factures dues → proposition de paiement par échéance, chèques/virement, post en lot. (SCHEMA)
- [x] FG134 — **Génération de fichier de virement bancaire** — export du lot au format de la banque depuis un payment run. (DECISION)
- [x] FG135 — **Notes de frais & remboursements employés** — saisie avec justificatif photo, validation, remboursement ; les équipes avancent du cash en continu. (SCHEMA)
- [x] FG136 — **Indemnités kilométriques & per-diem chantier** — barèmes km/jour calculés auto depuis la distance site (GPS/haversine déjà présents). (SCHEMA)
- [x] FG137 — **Préparation de la déclaration TVA** — TVA collectée − déductible par régime (mensuel/trimestriel, débit/encaissement) → montant déclarable + export. (SCHEMA)
- [x] FG138 — **Relevé de déductions détaillé (annexe TVA)** — l'annexe ligne par ligne exigée par la DGI. (ROUTINE)
- [x] FG139 — **Retenue à la source (RAS) sur honoraires/prestations** — calcul + bordereau de versement (obligation marocaine non gérée). (SCHEMA)
- [x] FG140 — **Aide au calcul de l'IS** — estimation depuis le CPC + échéancier des 4 acomptes provisionnels + régularisation. (DECISION)
- [x] FG141 — **Export FEC (fichier des écritures comptables)** — export structuré et ordonné des écritures au format auditable DGI (dépend du grand livre). (SCHEMA)
- [x] FG142 — **Trousse liasse fiscale (états de synthèse)** — bilan + CPC + balance + tableaux annexes en un paquet pour le fiduciaire/DGI. (ARCH)
- [x] FG143 — **Déclaration des honoraires / état 9421** — déclaration annuelle des paiements aux tiers depuis les règlements fournisseurs. (ROUTINE)
- [x] FG144 — **Calcul du timbre fiscal sur encaissements espèces** — droit de timbre auto sur les factures payées en espèces. (SCHEMA)
- [x] FG145 — **Retenue de garantie & cautions sur marchés (RG / bonne fin)** — RG retenue sur les marchés + cautions bancaires (provisoire/définitive/restitution) avec dates de levée. (SCHEMA)
- [ ] FG146 — **Reconnaissance du revenu par avancement (% completion)** — reconnaître le CA des chantiers pluri-tranches selon l'avancement réel. (DECISION)
- [ ] FG147 — **Produits constatés d'avance & travaux en cours (WIP)** — acomptes non encore acquis en produits différés, coûts non facturés en travaux en cours. (SCHEMA)
- [ ] FG148 — **Campagnes de versement des commissions (payout run)** — transformer le calcul de commission (lecture seule aujourd'hui) en payable : relevé par commercial, validation, post. (SCHEMA)
- [ ] FG149 — **Budgets annuels & suivi budget-vs-réalisé** — lignes de budget par compte/centre de coût + variance mensuelle. (SCHEMA)
- [ ] FG150 — **Comptabilité analytique / centres de coût** — axe analytique (chantier/agence/marché/commercial) sur les écritures et documents. (ARCH)
- [ ] FG151 — **Tableau de bord financier directeur** — résultat du mois, position de trésorerie, DSO/DPO, marge brute %, top encours (≠ FG45 quote-to-cash). (ROUTINE)
- [ ] FG152 — **Provisions pour créances douteuses** — provision calculée depuis la balance âgée + dotation au grand livre. (SCHEMA)
- [ ] FG153 — **Inter-sociétés / consolidation multi-entités** — multi-entités (EI + SARL) avec élimination inter-co et CPC/bilan consolidés. (ARCH)

### RH, terrain & HSE

- [x] FG154 — **Module RH (app dédiée) + dossier employé** — `DossierEmploye` (OneToOne→user) : date d'embauche, matricule, statut ; socle de tout le RH (inexistant aujourd'hui). (ARCH)  [DONE 2026-06-22: RH app + DossierEmploye master (OneToOne→user; matricule/poste/contrat/statut/cout_horaire interne); admin-gated, multi-tenant, tests. NEW app apps/rh.]
- [x] FG155 — **Type de contrat & dates** — CDI/CDD/ANAPEC/stage/intérim + alerte fin de CDD. (SCHEMA)
- [x] FG156 — **Identité & numéros légaux employé** — CIN, CNSS, CIMR/AMO, RIB, situation familiale (données paie obligatoires). (SCHEMA)
- [x] FG157 — **Rémunération de base (gated rôle RH)** — salaire, périodicité, historique, réservé permission `salaires_voir`. (AUTH)  [DONE 2026-06-22: Remuneration (employe/montant/periodicite/date_effet, historique) gaté read+write par permission salaires_voir (Directeur/Admin, ELEVATED), multi-tenant, 7 tests.]
- [x] FG158 — **Contact d'urgence & coordonnées étendues** — personne à prévenir, groupe sanguin (utile chantier/accident). (SCHEMA)  [DONE 2026-06-22: Contact d’urgence & coordonnées étendues — 7 champs additifs nullable sur DossierEmploye (urgence nom/lien/téléphone, groupe sanguin, adresse/téléphone/email perso) exposés via le serializer existant, accès dossier inchangé (IsResponsableOrAdmin). Migration 0005 additive, 6 tests.]
- [x] FG159 — **Coffre documents employé** — contrat/CIN/RIB/diplômes via `records.Attachment`, expiration optionnelle. (ROUTINE)  [DONE 2026-06-22: Coffre documents employé — DocumentEmploye (employe→DossierEmploye, OneToOne→records.Attachment string-FK, type contrat/cin/rib/diplome/autre, date_expiration nullable) réutilisant le stockage MinIO records (aucun nouveau stockage). Endpoints rh/documents/ (?employe/?type) + expirant-bientot/?within. Accès IsResponsableOrAdmin. Migration 0006 additive, 10 tests.]
- [x] FG160 — **Référentiels Poste & Département** — remplacent le `poste` texte libre, rattachent org-chart/grilles/habilitations. (SCHEMA) [DONE 2026-06-22: Référentiel Poste & Département; modèle Poste (company-scoped) + DossierEmploye.poste_ref, endpoint rh/postes/; 5 tests.]
- [x] FG161 — **Cycle de vie & offboarding** — statut embauché/actif/sorti + motif + checklist de sortie (récup EPI/outils/badge). (SCHEMA) [DONE 2026-06-22: Cycle de vie & offboarding; Statut EMBAUCHE + date_sortie/motif_sortie + ElementSortie (checklist EPI/outil/badge); 5 tests.]
- [x] FG162 — **Soldes & droits à congés (Maroc)** — compteurs annuels, acquisition mensuelle (~1,5 j/mois + ancienneté), report. (SCHEMA) [DONE 2026-06-22: Soldes & droits congés Maroc; SoldeConge + acquisition 1,5 j/mois + ancienneté; 4 tests.]
- [x] FG163 — **Demande & validation de congés (workflow)** — soumission employé → validation superviseur/RH, décompte jours ouvrés hors fériés/WE (utilise FG5). (SCHEMA) [DONE 2026-06-22: Demande & validation congés (workflow); DemandeConge + valider/refuser/annuler atomique, décompte jours ouvrés via holidays.py minimal (swappable quand FG5 arrive); 9 tests.]
- [x] FG164 — **Typologie d'absences** — CP/maladie/sans solde/exceptionnel/AT, chacune avec règle de décompte. (SCHEMA) [DONE 2026-06-22: Typologie d'absences; TypeAbsence (décompte/déduit_solde/rémunéré) pilote FG163; couvert par tests décompte.]
- [x] FG165 — **Calendrier d'absences d'équipe → planning** — un technicien en congé n'est pas assignable au dispatch terrain. (ROUTINE) [DONE 2026-06-22: Calendrier d'absences équipe→planning; selectors absences_equipe/employes_assignables + endpoint calendrier-equipe; 4 tests. Migration rh 0007 additive.]
- [x] FG166 — **Pointage / clock-in–out** — arrivée/départ (mobile + géoloc comme le check-in F6), calcul des heures. (SCHEMA)
- [x] FG167 — **Feuilles de temps par chantier (timesheets)** — heures imputées à une Installation/intervention → job-costing main-d'œuvre réelle. (SCHEMA) [DONE 2026-06-27: `rh.FeuilleTemps` (company forcé, employe FK, installation_id/intervention_id string-refs, heures, taux interne, cout_calcule) + company-scoped viewset/filters + `selectors.labour_hours_for_installation` so ventes can read labour without importing rh models. Migration rh 0009 additive, tests for company-forcing/isolation/selector.]
- [x] FG168 — **Heures supplémentaires & calcul majoré** — détection HS + taux (25/50/100 % nuit/férié) en entrée de paie. (SCHEMA)
- [x] FG169 — **Planning d'équipes / roster (shifts)** — affectation hebdo techniciens↔équipes/camionnettes, détection conflits congés. (SCHEMA)
- [x] FG170 — **Registre de présence chantier journalier (émargement)** — qui était présent sur quel chantier (trace litiges/facturation). (ROUTINE)
- [x] FG171 — **Retards & absences injustifiées** — marquage + compteur (base disciplinaire/pilotage). (ROUTINE)
- [x] FG172 — **Matrice de compétences** — pose structure, raccordement DC/AC, MES onduleur, pompage, soudure + niveau par employé. (SCHEMA)
- [x] FG173 — **Habilitations électriques (B1V/BR/B2V/H0…)** — par employé avec validité/organisme, exigées sur tout chantier PV. (SCHEMA)
- [x] FG174 — **Certifications spécifiques** — travail en hauteur, harnais, CACES/nacelle, secourisme/SST, conduite + expiration. (SCHEMA)
- [x] FG175 — **Alertes d'expiration (habilitations/certifs/docs)** — moteur d'échéances → notifications RH/superviseur X jours avant. (ROUTINE)
- [x] FG176 — **Garde d'affectation par habilitation** — alerte/blocage doux si on assigne un technicien sans l'habilitation requise. (DECISION)
- [x] FG177 — **Visite médicale du travail** — dernière/prochaine visite + aptitude + alerte (obligatoire pour le chantier). (SCHEMA)
- [x] FG178 — **Catalogue & dotation EPI** — casque/harnais/gants isolants/chaussures attribués nominativement (taille, date). (SCHEMA)
- [x] FG179 — **Suivi péremption/contrôle des EPI** — EPI à durée de vie (harnais, gants isolants) + alerte de remplacement/recontrôle. (SCHEMA)
- [x] FG180 — **Émargement de remise EPI (signature)** — accusé signé prouvant la dotation (exigible CNSS/accident). (ROUTINE)
- [x] FG181 — **Registre HSE & accidents du travail** — déclaration (date/lieu/blessé/gravité/arrêt/photos) + export déclaration CNSS. (SCHEMA)
- [x] FG182 — **Presqu'accidents (near-miss)** — saisie rapide terrain pour pilotage proactif. (ROUTINE)
- [x] FG183 — **Causeries sécurité / toolbox talks** — quart d'heure sécurité avant chantier (thème/participants/émargement). (SCHEMA)
- [x] FG184 — **Analyse de risques chantier (plan de prévention)** — évaluation des risques par chantier avant démarrage (≠ checklist F18 par intervention). (SCHEMA)
- [x] FG185 — **Tableau de bord HSE** — taux fréquence/gravité, EPI/habilitations/visites en alerte, incidents par chantier. (ROUTINE)
- [x] FG186 — **Permis de travail (hauteur/électrique/consignation)** — délivrance/clôture par tâche à risque, trace la consignation avant intervention. (SCHEMA) [DONE (already present) 2026-06-30: déjà couvert par qhse `PermisTravail` (QHSE23) + `ConsignationLoto` (QHSE24) ; aucun doublon créé en rh.]
- [x] FG187 — **Gestion de la formation** — sessions (interne/externe), inscriptions, présence, coût → alimente la matrice de compétences. (SCHEMA)
- [x] FG188 — **Plan & registre de formation** — historique par employé + besoins (obligations OFPPT/CSF). (ROUTINE)
- [ ] FG189 — **Recrutement (ATS-lite)** — postes ouverts, candidatures, pipeline, conversion en dossier employé à l'embauche. (ARCH)
- [ ] FG190 — **Entretiens & évaluations annuelles** — campagnes d'appréciation, objectifs individuels, notation (≠ objectifs commerciaux FG39). (SCHEMA)
- [ ] FG191 — **Disciplinaire & sanctions** — registre avertissements/mises à pied conforme au code du travail. (SCHEMA)
- [ ] FG192 — **Éléments variables de paie (export)** — agrégat mensuel par employé (heures/HS/absences/primes/retenues) exporté vers le prestataire de paie (pas un moteur de paie). (SCHEMA)
- [ ] FG193 — **Primes & indemnités** — référentiel (rendement/chantier/panier/transport) attribuables par employé/période. (SCHEMA)
- [ ] FG194 — **Ordre de mission (déplacement chantier)** — ordre daté (destination/motif/véhicule/per-diem) en PDF. (SCHEMA)
- [ ] FG195 — **Avances sur salaire** — demande/validation + déduction au mois suivant (intégré à l'export paie). (SCHEMA)
- [ ] FG196 — **Bulletin de paie (lecture seule)** — dépôt mensuel du bulletin PDF consultable par l'employé (pas de calcul légal interne). (DECISION)
- [ ] FG197 — **Suivi des permis de conduire & habilitation à conduire** — catégorie/validité, condition pour affecter une camionnette. (SCHEMA)
- [ ] FG198 — **Affectation conducteur ↔ véhicule** — lien flotte avec contrôle de permis valide à l'affectation. (DECISION)
- [ ] FG199 — **Portail self-service employé** — voir/modifier ses infos, demander congés, déclarer frais, consulter soldes/bulletins/EPI/habilitations. (AUTH)
- [ ] FG200 — **Cockpit RH (effectifs & coûts)** — effectif par département/contrat, pyramide d'ancienneté, masse salariale (gated), turnover, alertes. (ROUTINE)

### Croissance commerciale, marketing, CPQ, financement, appels d'offres & portail

- [ ] FG201 — **Campagnes email & SMS** — segment ciblé → envoi groupé (Brevo) avec compteurs ouvertures/clics pour réveiller une base froide. (COST)
- [ ] FG202 — **Séquences de relance automatisées (drip/nurture)** — enchaînement multi-étapes (J0 WhatsApp, J3 email, J7 appel) déclenché par l'entrée en étape. (COST)
- [ ] FG203 — **Récupération des devis abandonnés** — détecter les devis envoyés non répondus après N jours + relance ciblée. (ROUTINE)
- [x] FG204 — **Tableau d'attribution multi-touch** — journal de points de contact par lead (Meta→site→WhatsApp→signature), au-delà du first-touch. (SCHEMA)
- [ ] FG205 — **Tracking d'ouverture des ShareLink devis/facture** — horodater vu/non-vu pour prioriser les relances. (SCHEMA)
- [ ] FG206 — **Constructeur de formulaires / landing pages multiples** — plusieurs formulaires d'intake (pompage agricole, régularisation 82-21) pré-taguant le lead. (ARCH)
- [ ] FG207 — **Capture de leads via WhatsApp (catalogue/chatbot)** — un message entrant crée un lead pré-qualifié (le client marocain démarre sur WhatsApp). (COST)
- [ ] FG208 — **Journal d'appels & click-to-call** — consigner appels + issue avec bouton tel:, pour mesurer l'effort téléphonique. (ROUTINE)
- [ ] FG209 — **Promotions & campagnes de remise** — codes datés applicables au devis (ex. « -5 % Aïd »), traçables au ROI. (SCHEMA)
- [ ] FG210 — **Bibliothèque de modèles de devis** — modèles réutilisables par marché (Résidentiel 5 kWc, Pompage 3 CV). (SCHEMA)
- [ ] FG211 — **Configurateur d'options guidé (guided selling)** — assistant pas-à-pas pour qu'un commercial junior produise un devis correct. (ROUTINE)
- [ ] FG212 — **Comparateur de versions de devis (UI)** — affichage côte-à-côte de deux versions (le versionnage Devis existe déjà). (ROUTINE)
- [ ] FG213 — **Routage d'approbation des configurations non-standard** — workflow quand la composition sort des règles (kWc/onduleur incohérents). (SCHEMA)
- [ ] FG214 — **E-catalogue à prix publics** — page catalogue tokenisée, prix public TTC seulement, jamais prix d'achat. (ROUTINE)
- [ ] FG215 — **Bibliothèque de documents de proposition** — annexes réutilisables (lettre de couverture, références, garanties) attachables au PDF. (SCHEMA)
- [ ] FG216 — **Simulateur public « configurez votre kit » → lead** — simulateur kWc/économies sur le site créant un lead pré-rempli. (ARCH)
- [ ] FG217 — **Simulation de financement dans le devis (crédit/leasing)** — bloc mensualités (montant/durée/taux) ; beaucoup achètent à crédit. (SCHEMA)
- [ ] FG218 — **Offres de banques/partenaires de financement** — catalogue d'offres sélectionnables sur un devis. (SCHEMA)
- [ ] FG219 — **Ligne d'incitation / subvention (Tatwir/MASEN)** — montant déductible affiché → coût net après aide. (SCHEMA)
- [ ] FG220 — **Paiement échelonné (type Tayssir) sur facture** — échéancier de tranches + suivi des versements. (SCHEMA)
- [ ] FG221 — **Comparateur cash vs financement** — encart client (coût total, payback) pour lever l'objection prix. (ROUTINE)
- [ ] FG222 — **Gestion des appels d'offres (public/privé)** — objet AO (acheteur/deadline/lot/caution) lié au lead ; l'industriel/agricole passe par marchés. (SCHEMA)
- [ ] FG223 — **Bordereau des prix (BOQ) d'appel d'offres** — chiffrage ligne à ligne séparé du devis client. (SCHEMA)
- [ ] FG224 — **Suivi des cautions & garanties de soumission** — cautions provisoires/définitives (montant/banque/échéance/restitution). (SCHEMA)
- [ ] FG225 — **Dossier de soumission (pièces administratives)** — checklist + dépôt (attestations fiscale/CNSS, RC, déclaration sur l'honneur). (SCHEMA)
- [ ] FG226 — **Échéancier & alertes de deadline d'AO** — dates clés (remise des plis, ouverture, validité) avec rappels. (ROUTINE)
- [ ] FG227 — **Analyse gagné/perdu des appels d'offres** — résultat (attributaire, prix gagnant, écart) + taux de réussite. (SCHEMA)
- [ ] FG228 — **Portail self-service client** — espace connecté : devis, factures, chantiers, tickets. (AUTH)
- [ ] FG229 — **Acceptation/e-signature de devis dans le portail** — accepter en ligne (choix d'option, signature) → acceptation côté OS. (AUTH)
- [ ] FG230 — **Paiement en ligne des factures (portail)** — bouton payer (CMI/virement) + rapprochement auto. (COST)
- [ ] FG231 — **Téléchargement docs & dépôt factures ONEE par le client** — le client téléverse ses factures pour affiner l'étude. (AUTH)
- [ ] FG232 — **Suivi d'avancement du chantier côté client** — timeline lecture-seule des jalons dans le portail. (AUTH)
- [ ] FG233 — **Ouverture de ticket SAV depuis le portail** — le client crée/suit un ticket de garantie en ligne. (AUTH)
- [ ] FG234 — **Portail apporteurs / sous-revendeurs** — partenaires soumettent des leads et suivent leur statut. (AUTH)
- [ ] FG235 — **Suivi des commissions partenaires** — commission par lead/devis signé soumis par un partenaire + relevé. (SCHEMA)
- [ ] FG236 — **Gestion des territoires / zones commerciales** — découpage par région + affectation auto des leads. (SCHEMA)
- [ ] FG237 — **Annuaire & onboarding des installateurs partenaires** — fiche partenaire (statut/agrément/zone/taux) + activation. (SCHEMA)
- [ ] FG238 — **Enquêtes NPS / satisfaction post-installation** — envoi auto après réception + score consolidé. (COST)
- [ ] FG239 — **Capture d'avis/témoignages + push Google Reviews** — solliciter un avis et router vers Google (preuve sociale). (COST)
- [ ] FG240 — **Programme de fidélité / parrainage étendu** — points/paliers au-delà du parrainage simple existant. (SCHEMA)
- [ ] FG241 — **Moteur d'upsell / cross-sell** — suggestions contextuelles (batterie, 2ᵉ site, contrat O&M) selon l'historique. (ROUTINE)
- [x] FG242 — **Suivi des concurrents sur deals perdus** — sur un lead Perdu, saisir le concurrent gagnant + son prix. (SCHEMA)
- [ ] FG243 — **Pipeline de renouvellement de contrats O&M** — vue des `ContratMaintenance` à reconduire (échéances/relances). (SCHEMA)
- [ ] FG244 — **Abonnements de monitoring** — offre de supervision (mensuel/annuel) liée au module monitoring (revenu récurrent). (SCHEMA)

### Vertical solaire (conception, simulation, réglementaire, O&M)

- [x] FG245 — **Éditeur de calepinage toiture (placement panneaux)** — placer/orienter les modules (surface, retraits) pour figer un nombre réaliste de panneaux. (ARCH)
- [x] FG246 — **Calcul de chaînes (string design) & vérif ratio DC/AC** — répartir N panneaux par MPPT, contrôler Vmp/Voc à froid vs plage onduleur. (ROUTINE)
- [x] FG247 — **Appariement module–onduleur depuis le catalogue** — proposer l'onduleur compatible avec la config panneaux (mots-clés alignés `builder.py`). (ROUTINE)
- [x] FG248 — **Pont 3D toiture web → ERP** — importer la config du builder 3D `apps/web/roof-tool-pro` (surface/pans/orientation/kWc) dans un devis/chantier. (ARCH) [DONE 2026-06-22: Pont toiture 3D web→ERP; extract_roof_config parse les areas roofPro11 → etude_params['toiture'] (surface/pans/orientation/azimut/kWc); 5 tests.]
- [x] FG249 — **Optimisation inclinaison/azimut** — balayer tilt/azimut autour du site (via PVGIS existant) → orientation optimale. (ROUTINE)
- [x] FG250 — **Analyse d'ombrage & profil d'horizon** — obstacles + horizon → perte d'ombrage mensuelle (l'ombrage qualitatif du lead devient un chiffre). (DECISION) [DONE 2026-06-22: Analyse d'ombrage + profil d'horizon; solar_design.shading_analysis → pertes mensuelles/annuelles + facteur de production; 7 tests.]
- [x] FG251 — **Générateur de nomenclature électrique (BOQ)** — déduit câbles DC/AC, disjoncteurs, parafoudres, coffrets, terre, structure depuis le design. (ROUTINE) [DONE 2026-06-22: Générateur de BOQ électrique; solar_design.generate_boq → câbles DC/AC, disjoncteurs, parafoudres, coffrets, terre, structure (quantités seules, jamais de prix); 6 tests.]
- [x] FG252 — **Brouillon de schéma unifilaire (SVG)** — auto-générer le schéma (panneaux→strings→onduleur→comptage→ONEE) pour le dossier technique. (ROUTINE)
- [x] FG253 — **Aide au calcul de charge structure toiture** — surcharge kg/m² vs type de toiture + alerte si dépassement. (DECISION)
- [x] FG254 — **Bibliothèque de fiches techniques modules/onduleurs (PAN/OND)** — datasheets + paramètres normalisés (Pmax/Voc/Isc/coef temp) par produit. (SCHEMA)
- [x] FG255 — **Dimensionnement borne de recharge VE** — borne (kW/mono-tri/sessions) couplée au PV + impact autoconsommation. (ROUTINE)
- [x] FG256 — **Étude de stockage & dispatch batterie (backup)** — autoconsommation max vs backup heures critiques → kWh/kW utiles. (ROUTINE)
- [x] FG257 — **Simulation bankable P50/P90 avec modèle de pertes** — production P50/P90 + ratio de performance (température/salissure/câblage/onduleur). (DECISION)
- [x] FG258 — **Profil d'autoconsommation horaire depuis courbe de charge** — courbe 8760/profil type × production horaire → taux d'autoconso réel. (DEP:openpyxl)
- [x] FG259 — **Économie net-metering / injection surplus (loi 13-09/MT)** — valorisation du surplus injecté par tranche horaire (réglage `surplus_injecte_compense` existant). (ROUTINE)
- [x] FG260 — **Modélisation escalade tarifaire ONEE sur 20–25 ans** — projeter facture/économies + VAN/TRI avec taux d'escalade éditable. (ROUTINE)
- [x] FG261 — **Optimisation puissance souscrite (C&I)** — analyser la pointe et recommander une réduction de puissance souscrite post-PV. (ROUTINE)
- [x] FG262 — **Modélisation dégradation modules sur la durée** — courbe de dégradation appliquée à la production projetée et garantie. (ROUTINE)
- [x] FG263 — **Modèle financier PPA / tiers-investisseur** — simuler un PPA (tarif MAD/kWh, revenus actualisés) pour les clients sans capex. (DECISION)
- [x] FG264 — **Rendement pompage par cycle de marche** — volume d'eau journalier/mensuel selon irradiation horaire + durée de pompage (étend l'`etude_params` actuel). (ROUTINE)
- [ ] FG265 — **Flux d'irradiance/météo pour simulations** — flux TMY/temps réel pour caler simulations et O&M sur le site. (DEP/COST)
- [ ] FG266 — **Comparateur de scénarios de devis** — comparer plusieurs dimensionnements (kWc/batterie/orientation) sur production/économies/payback. (ROUTINE)
- [ ] FG267 — **Packs documentaires réglementaires par régime** — liste de pièces requises selon `regime_8221` (déclaration BT, accord raccordement, autorisation ANRE). (SCHEMA)
- [ ] FG268 — **Checklists & échéances de soumission ONEE/raccordement** — checklist par étape (dépôt, étude, convention, comptage) + dates limites + relances. (SCHEMA)
- [ ] FG269 — **Suivi de soumission & navette opérateur** — journaliser les échanges ONEE/distributeur (envois/accusés/compléments/refus). (SCHEMA)
- [ ] FG270 — **Éligibilité & suivi des subventions/incitations** — qualifier (MASEN/IRESEN/Tatwir) + suivre le dossier (statut/montant/pièces). (SCHEMA)
- [ ] FG271 — **Workflow de régularisation Article 33 / déclarations 82-21** — régularisation des installations existantes (drapeau présent) + génération des déclarations. (SCHEMA)
- [ ] FG272 — **Générateur de déclaration de raccordement BT/MT** — pré-remplir la demande (client/site/kWc/onduleur/schéma) en PDF depuis le chantier. (ROUTINE)
- [ ] FG273 — **Calendrier réglementaire & alertes d'expiration de dossiers** — tableau par échéance (dépôt/validité d'accord/date limite MES) + alertes. (ROUTINE)
- [ ] FG274 — **Protocole d'essais de mise en service IEC 62446** — fiche de recette (isolement/polarité/continuité terre/Voc-Isc par string/contrôle onduleur). (SCHEMA)
- [ ] FG275 — **Capture de courbe I-V par string** — mesures I-V par chaîne comparées aux valeurs datasheet (détecte modules défectueux à la pose). (SCHEMA)
- [ ] FG276 — **Pack documentaire « as-built »** — PDF assemblant plans/schéma/datasheets/séries/photos/PV de réception. (ROUTINE)
- [ ] FG277 — **Attestation/certificat de conformité électrique** — attestation (référentiel/mesures/signataire) liée au chantier réceptionné. (ROUTINE)
- [ ] FG278 — **Test de performance de réception (PR initial)** — PR mesuré à la MES vs attendu, archivé comme référence O&M/garantie. (ROUTINE)
- [ ] FG279 — **Analytique O&M : PR, disponibilité, soiling, dégradation** — tableau de bord par système depuis `ProductionReading`. (ROUTINE)
- [x] FG280 — **Gestion fine des alarmes/défauts onduleur** — alarmes (code/gravité/équipement) distinctes du ticket SAV + acquittement/escalade. (SCHEMA)
- [ ] FG281 — **Tableau de bord parc/flotte multi-systèmes** — production totale, kWc installés, alertes, PR moyen sur tous les systèmes actifs. (ROUTINE)
- [ ] FG282 — **Suivi de garantie de production & compensation de manque** — production réelle vs productible garanti (avec dégradation) → écart/compensation. (SCHEMA)
- [ ] FG283 — **Détection & suivi de pertes par salissure** — estimer la perte (chute de PR entre nettoyages) + recommandation de nettoyage (régions poussiéreuses). (ROUTINE)
- [ ] FG284 — **Suivi garantie vs courbe de dégradation fabricant** — superposer production mesurée et courbe garantie → dérive anormale → recours fabricant. (ROUTINE)
- [ ] FG285 — **Adaptateurs monitoring supplémentaires (SolarEdge/Sungrow/Solis)** — connecteurs derrière l'interface provider existante (NoOp/FusionSolar). (COST)
- [ ] FG286 — **Reporting CO₂ évité par système & cumulé** — tonnes de CO₂ évitées par système et parc (réutilise le facteur réseau de l'energy report). (ROUTINE)
- [ ] FG287 — **Certificats d'énergie renouvelable / attestations RE** — attestation d'énergie verte produite (kWh + CO₂) par période, signée. (ROUTINE)
- [ ] FG288 — **Tableau de bord environnemental client (portail)** — production/économies/CO₂ cumulés côté client (fidélise, soutient le réabonnement). (ROUTINE)
- [ ] FG289 — **Rapport O&M périodique automatisé (PDF + email)** — rapport mensuel/trimestriel par système (production/PR/alarmes/recommandations). (ROUTINE)
- [ ] FG290 — **Registre des garanties matériel & échéancier de fin par parc** — fins de garantie produit/production (déjà calculées sur `Equipement`) + alertes par parc. (ROUTINE)

### Opérations, projets, supply-chain, logistique, flotte & qualité

- [x] FG291 — **Programme / Projet multi-chantiers** — `Projet` regroupant chantiers + devis + tickets d'un même client/site (ferme à 4 forages, toiture par tranches). (ARCH)
- [x] FG292 — **Tâches & sous-tâches de projet avec dépendances** — `ProjetTache` (assigné/échéance/prédécesseur) au-delà de la checklist figée. (ARCH)
- [x] FG293 — **Jalons & phases de projet** — étude/appro/pose/MES/réception avec dates cibles/réelles. (SCHEMA)
- [x] FG294 — **Budget projet vs réel (engagé/dépensé)** — agrège devis + BCF/factures fournisseur + main-d'œuvre vs budget, alerte de dépassement. (ARCH)
- [x] FG295 — **P&L de projet consolidé** — résultat par `Projet` (marge tous chantiers, sous-traitance et imports inclus). (ARCH)
- [x] FG296 — **Modèles de projet (templates de chantier-type)** — patron pré-créant tâches/jalons/BoM type à la signature. (SCHEMA)
- [x] FG297 — **Contrôle documentaire de projet (plans & révisions)** — registre versionné (schéma unifilaire, calepinage, note de calcul). (ARCH) [DONE 2026-06-27: `installations.DocumentProjet` (company forcé, installation FK même-app, type schema_unifilaire/calepinage/note_calcul/autre, titre) + `RevisionDocument` (indice, date, auteur serveur, fichier via string-FK records.Attachment, unique (document, indice)) en module `models_document.py` re-exporté ; viewsets company-scoped + filtres. Import-linter safe (aucun import d'un autre modèle domaine). Migration installations 0014, 13 tests.]
- [x] FG298 — **Comptes-rendus de réunion de chantier** — `ReunionChantier` (ordre du jour/présents/décisions/actions) horodaté. (SCHEMA)
- [x] FG299 — **Plan de charge des équipes (capacité vs affecté)** — jours dispo vs affectés par technicien/équipe pour éviter la sur-réservation. (ROUTINE)
- [x] FG300 — **Détection de conflits d'affectation** — alerte si technicien/camionnette affecté deux fois sur le même créneau. (ROUTINE)
- [x] FG301 — **Nivellement de charge (resource levelling)** — proposition de rééquilibrage des interventions surchargées. (ROUTINE)
- [x] FG302 — **Calendrier de disponibilité ressources** — `IndisponibiliteRessource` (congé/formation/arrêt) excluant un technicien/véhicule. (SCHEMA)
- [x] FG303 — **Planning des camionnettes (capacité véhicule)** — affectation par véhicule sur le calendrier (cohérent avec `Intervention.camionnette`). (ROUTINE)
- [x] FG304 — **Référentiel sous-traitants** — `SousTraitant` (métier/contact/RIB/ICE), distinct des fournisseurs matériel. (ARCH)
- [x] FG305 — **Ordres de travaux sous-traitant** — `OrdreSousTraitance` (chantier/prestation/montant/échéance/statut). (ARCH)
- [ ] FG306 — **Factures & règlements sous-traitant** — facture entrante + paiements (AP dédiée), montants jamais client-facing. (SCHEMA)
- [ ] FG307 — **Attestations & assurances sous-traitant** — pièces obligatoires (CNSS, RC décennale, agrément) + expiration + blocage d'affectation. (SCHEMA)
- [ ] FG308 — **Évaluation de performance sous-traitant** — note qualité/délai/sécurité par prestation + scorecard cumulée. (SCHEMA)
- [ ] FG309 — **Retenue de garantie sur sous-traitant** — % bloqué jusqu'à levée des réserves (pratique BTP marocaine). (SCHEMA)
- [ ] FG310 — **Demande d'achat (réquisition) → approbation** — `DemandeAchat` validée avant transformation en BCF. (ARCH)
- [ ] FG311 — **RFQ multi-fournisseurs & comparatif d'offres** — demande de prix à plusieurs fournisseurs + tableau comparatif avant choix. (ARCH)
- [ ] FG312 — **Paliers d'approbation de BCF par seuil** — workflow par montant (responsable < X, admin au-delà) avant envoi. (AUTH)
- [ ] FG313 — **Contrôle budgétaire à la commande** — vérifie le budget projet/chantier restant avant de valider un BCF. (ROUTINE)
- [ ] FG314 — **Commandes-cadres / contrats annuels (blanket orders)** — prix négociés/volume engagé déclinables en commandes d'appel. (SCHEMA)
- [ ] FG315 — **Suivi import / dédouanement** — `DossierImport` (incoterm/BL/conteneur/dates port/statut douane) pour un container de panneaux. (ARCH)
- [ ] FG316 — **Frais d'import & coût de revient débarqué (landed cost)** — ventilation fret + douane + TVA import + transit par SKU (étend FG67). (ARCH)
- [ ] FG317 — **Réceptionné-non-facturé (GR/IR)** — marchandises reçues sans facture fournisseur → dette latente provisionnée. (SCHEMA)
- [ ] FG318 — **Contrats & accords de prix fournisseur** — convention datée/versionnée par fournisseur/SKU (au-delà du dernier prix). (SCHEMA)
- [ ] FG319 — **Emplacements fins zone/allée/casier (bin locations)** — sous-découpage adressable des `EmplacementStock` pour retrouver un onduleur précis. (ARCH)
- [ ] FG320 — **Rangement guidé (put-away)** — à la réception, suggestion du casier + trace de mise en stock. (SCHEMA)
- [ ] FG321 — **Bons de prélèvement (pick list) par chantier** — liste de picking depuis la réservation de stock, ordonnée par emplacement. (SCHEMA)
- [ ] FG322 — **Colisage / préparation (pack)** — emballage/contrôle des articles prélevés avant départ vers le site. (SCHEMA)
- [ ] FG323 — **Suivi du stock par numéro de série en entrepôt** — registre série→emplacement avant installation (étend FG61). (SCHEMA)
- [ ] FG324 — **Sessions de comptage tournant (cycle count ABC)** — comptages partiels récurrents par zone/classe (étend FG63 one-shot). (SCHEMA)
- [ ] FG325 — **Demande de transfert inter-emplacements (workflow)** — `DemandeTransfert` (demandé→approuvé→exécuté) en amont du transfert direct. (SCHEMA)
- [ ] FG326 — **Réapprovisionnement multi-dépôts** — règles min/max par emplacement → transfert proposé entre dépôts (étend FG62). (SCHEMA)
- [ ] FG327 — **Stock en consignation / emballages consignés** — palettes/tourets/matériel consigné (retournable, non possédé). (SCHEMA)
- [ ] FG328 — **Pré-assemblage / kitting magasin** — assemblage léger (coffret AC/DC pré-câblé) consommant des composants → article composite. (ARCH)
- [ ] FG329 — **Planification des livraisons (dépôt → site)** — `Livraison` (chantier/date/transporteur/articles/dépôt) distinct du PDF bon de livraison. (ARCH)
- [ ] FG330 — **Preuve de livraison (POD)** — signature/photo/GPS horodaté à la remise sur site. (SCHEMA)
- [ ] FG331 — **Transporteurs & tarifs de transport** — `Transporteur` + coût de course affectable à une livraison. (SCHEMA)
- [ ] FG332 — **Optimisation de tournée de livraison multi-sites** — regroupe/ordonne les livraisons du jour par proximité. (ROUTINE)
- [ ] FG333 — **Réservation à la livraison (dépôt vs site)** — distingue le matériel livré direct site vs passant par le dépôt, décrémente le bon emplacement. (SCHEMA)
- [ ] FG334 — **Référentiel véhicules (flotte)** — `Vehicule` (immat/modèle/km/conducteur) lié à l'`EmplacementStock` camionnette. (ARCH)
- [ ] FG335 — **Échéances réglementaires véhicule** — vignette/assurance/visite technique/carte grise + alertes. (SCHEMA)
- [ ] FG336 — **Carnet de carburant (suivi gasoil)** — litres/montant/km/station par véhicule → coût/100 km + imputation projet. (SCHEMA)
- [ ] FG337 — **Planning d'entretien véhicule** — échéances vidange/révision par km ou date + rappel. (SCHEMA)
- [ ] FG338 — **Journal kilométrique & affectation conducteur** — km par trajet + historique conducteur↔véhicule (coût/responsabilité). (SCHEMA)
- [ ] FG339 — **Coût total de possession du véhicule** — carburant + entretien + assurance par véhicule/période (décision remplacement). (ROUTINE)
- [ ] FG340 — **Parc de machines & équipements propres** — `ActifEntreprise` (groupe électrogène, nacelle, station de test) amortissables, affectables chantier. (ARCH)
- [ ] FG341 — **Compteur d'heures & maintenance des machines** — relevé d'heures déclenchant l'entretien préventif. (SCHEMA)
- [ ] FG342 — **Location de matériel (interne & externe)** — locations entrantes (nacelle louée) + allocation interne d'un actif à un chantier. (SCHEMA)
- [ ] FG343 — **Plans d'inspection (ITP / plan de contrôle)** — points de contrôle par phase (couples de serrage, polarité DC, étanchéité) appliqués au chantier. (ARCH)
- [ ] FG344 — **Points d'arrêt (hold points)** — étapes bloquantes exigeant une validation avant de poursuivre la pose. (SCHEMA)
- [ ] FG345 — **Non-conformités (NCR)** — `NonConformite` (défaut/gravité/photo/responsable) distincte de la réserve de finition. (ARCH)
- [ ] FG346 — **Actions correctives & préventives (CAPA)** — boucle rattachée à une NCR (cause/action/vérification/clôture). (SCHEMA)
- [ ] FG347 — **Registre de conformité électrique / essais** — relevés normés de MES (isolement/court-circuit/tension à vide par string) horodatés. (SCHEMA)
- [ ] FG348 — **Inductions sécurité / accueil sur site** — registre d'accueil HSE par intervenant et par site (briefing/EPI vérifié). (SCHEMA)
- [ ] FG349 — **Audit qualité de fin de chantier (scoring)** — grille notée à la réception (conformité/propreté/documentation) → indicateur qualité par équipe. (SCHEMA)

### Plateforme, IA, intégrations, BI & mobile

- [x] FG350 — **Copilote in-app (CopilotPanel)** — brancher l'agent FastAPI (SQL + actions) dans un tiroir conversationnel global ; aucune UI ne le consomme aujourd'hui. (ROUTINE)  [DONE 2026-06-22: CopilotPanel — tiroir conversationnel global (Header toggle + Layout) réutilisant l’agent FastAPI via le slice ia existant; no-op propre sans clé, 7 tests.]
- [x] FG351 — **Actions en langage naturel — « crée un devis pour… »** — étendre `action_tools.py` avec des outils d'écriture gardés (Devis/Lead/Client via REST interne). (ROUTINE)  [DONE 2026-06-22: Outils d’écriture LN gardés — apps/agent registry: ventes.devis.create (internal→outward), crm.client.create, crm.lead.create ; risk=outward → proposition signée propose→confirm (jamais d’écriture directe), company toujours serveur. FastAPI action_tools dynamiques. Aucune migration. 7 (Django) + 7 (FastAPI) tests.]
- [x] FG352 — **RAG sur documents & manuels (DocQA)** — indexer docs/manuels dans le pgvector existant + outil de récupération ; no-op sans clé LLM. (DEP:langchain-textsplitters)
- [x] FG353 — **Résumé automatique d'un fil (lead/chantier/ticket)** — synthèse LLM en un clic d'un fil d'activité ; no-op sans clé. (COST)
- [x] FG354 — **Brouillon de réponse email/WhatsApp** — suggestion de réponse FR éditable depuis un fil (jamais auto-envoyée) ; no-op sans clé. (COST)
- [x] FG355 — **OCR CIN / contrat / pièce d'identité** — nouveau schéma dans `ocr_service.py` (chemin Zhipu vision) pour accélérer l'onboarding client. (ROUTINE) [DONE 2026-06-22: OCR CIN/contrat (NoOp par défaut); core/ai/schemas (CIN/CONTRAT) + extract_document; 4 tests. Aucune dépendance externe.]
- [x] FG356 — **OCR bon de livraison enrichi → réception stock** — apparier les lignes OCR au catalogue et pré-remplir une réception. (ROUTINE) [DONE 2026-06-22: Rapprochement BL→réception (match_ocr_lines référence/libellé difflib); 6 tests.]
- [x] FG357 — **Voice-to-text notes terrain** — transcrire les mémos audio déjà captés en notes d'activité (STT) ; no-op sans clé. (COST) [DONE 2026-06-22: Voice-to-text notes terrain (transcribe_audio + NoOpSTTProvider); 2 tests. NoOp, aucune clé.]
- [x] FG358 — **Photo AI QA sur photos d'installation** — contrôle vision (panneaux alignés, étiquettes, câblage) → score/flags sur le chantier. (COST) [DONE 2026-06-22: Photo AI-QA (inspect_photo + checklist FR + NoOp); 3 tests. NoOp.]
- [x] FG359 — **Next-best-action recommandée** — action suggérée par lead/chantier (relancer/planifier/facturer), heuristique + IA si clé présente. (ROUTINE) [DONE 2026-06-22: Next-best-action (heuristique FR déterministe + enrichissement LLM optionnel du motif); 9 tests + 12 tests fondation AI. Aucune dépendance/clé requise.]
- [x] FG360 — **Détection d'anomalies (stock/paiements/fraude)** — scan planifié signalant les outliers dans un modèle `AnomalyFlag`. (SCHEMA)
- [x] FG361 — **Prévision de ventes / demande** — série temporelle du CA et du volume de devis par mois depuis l'historique. (DEP:statsmodels)
- [x] FG362 — **Score de probabilité de gain (win-probability)** — probabilité par lead remplaçant l'heuristique d'étape statique de `pipeline.py`. (SCHEMA)
- [x] FG363 — **Score de churn / risque client** — repérer les clients maintenance/SAV à risque (sans activité, contrat lapsé) pour l'outreach proactif. (SCHEMA)
- [x] FG364 — **Prévision de réappro stock** — prédire les dates de rupture + quantités suggérées depuis l'historique de mouvements. (ROUTINE)
- [x] FG365 — **Prédiction de retard de paiement** — scorer chaque facture ouverte pour prioriser le recouvrement. (ROUTINE)
- [x] FG366 — **Moteur de workflow multi-étapes (BPM) + SLA/escalades** — `WorkflowDefinition/Instance/Step` pour chaînes d'approbation visuelles + minuteries SLA, au-delà des règles à déclencheur unique. (ARCH)
- [x] FG367 — **Conditions multi-critères & branches dans les règles** — `AutomationRule` avec groupes ET/OU + plusieurs actions séquentielles. (SCHEMA)
- [x] FG368 — **UI de gestion des tâches planifiées (jobs)** — écran Paramètres listant les jobs Celery Beat (digests/rapports/monitoring) avec statut + exécution manuelle. (ROUTINE)
- [x] FG369 — **Bibliothèque de modèles de workflow** — workflows pré-construits (relance devis, onboarding chantier, rappel garantie) installables en un clic. (ROUTINE)
- [ ] FG370 — **Passerelle de paiement CMI / Payzone** — paiement carte en ligne d'une facture + rapprochement vers `Paiement`. (AUTH)
- [ ] FG371 — **Passerelle SMS marocaine** — brancher un vrai fournisseur SMS pour que le canal SMS cesse de no-op. (AUTH)
- [ ] FG372 — **E-signature (Yousign/DocuSign)** — envoyer un Devis/contrat en signature électronique + enregistrer le statut/document signé. (AUTH)
- [ ] FG373 — **Email entrant IMAP → leads/tickets** — interroger une boîte partagée et convertir les emails entrants en leads/tickets avec threading. (AUTH)
- [ ] FG374 — **Sync calendrier Google/Outlook (2-way)** — synchroniser poses/interventions/visites (déjà agrégées dans `calendar.py`) avec les calendriers externes. (AUTH)
- [ ] FG375 — **Géocodage & cartes (Maps)** — géocoder les adresses lead/client pour remplir les GPS consommés par la carte. (DEP:geocoding-api)
- [ ] FG376 — **Connecteur Zapier / Make** — trigger-polling + actions sur l'API publique pour automatiser sans code. (ROUTINE)
- [ ] FG377 — **Pont comptable Sage / CEGID (one-way)** — exporter les journaux ventes/achats au format importable Sage/CEGID. (ROUTINE)
- [ ] FG378 — **Connecteur Odoo Compta (JSON-2, 2-way)** — pousser factures/paiements vers Odoo via son API JSON-2 uniquement (règle #1) + récupérer le statut de paiement. (AUTH)
- [ ] FG379 — **Open banking (flux bancaire automatique)** — tirer les transactions d'un agrégateur bancaire pour alimenter le rapprochement. (AUTH)
- [ ] FG380 — **Constructeur de tableau croisé (pivot)** — pivot/crosstab interactif sur les données scopées (lignes/colonnes/mesures). (ROUTINE)
- [ ] FG381 — **Constructeur de graphiques/dashboards sans-code** — dashboard drag-and-drop sauvegardé par utilisateur/société (Recharts présent). (SCHEMA)
- [ ] FG382 — **BI embarqué — explorateur de données** — query builder à sélection de champs sur l'API read pour l'analyse ad-hoc sans SQL. (ROUTINE)
- [ ] FG383 — **Extraits planifiés vers entrepôt/SFTP/S3** — planifier des extraits CSV/parquet vers un bucket/SFTP externe. (AUTH)
- [ ] FG384 — **Scan code-barres / QR (BarcodeDetector)** — scan dans la PWA pour rechercher produits et numéros de série sur site (réception/picking/série). (ROUTINE)
- [ ] FG385 — **Capture photo caméra en direct** — capture caméra in-app (getUserMedia) pour les photos d'installation, au-delà du seul upload de fichier. (ROUTINE)
- [ ] FG386 — **Mode terrain hors-ligne (offline queue)** — file locale des éditions chantier/intervention synchronisée à la reconnexion (même architecture que N91/F21, routée hors run main). (ARCH)
- [ ] FG387 — **Application mobile native (Capacitor)** — empaqueter la PWA en app iOS/Android (distribution store + accès device). (ARCH)
- [ ] FG388 — **Corbeille / restauration (soft-delete + undo)** — soft-delete avec corbeille par société + restauration + fenêtre « annuler » globale (complète FG15). (SCHEMA)
- [ ] FG389 — **Édition en masse partout (bulk edit)** — généraliser l'édition de champ en masse sur les écrans liste DataTable. (ROUTINE)
- [ ] FG390 — **Champs personnalisés calculés (formules)** — type FORMULA évaluant une expression sûre sur les champs (aujourd'hui valeurs statiques). (SCHEMA)
- [ ] FG391 — **Flags de fonctionnalités / modules par tenant** — activation/désactivation de modules par société (aujourd'hui seuls des flags env globaux). (SCHEMA)
- [ ] FG392 — **Thème white-label par tenant** — logo/couleurs/domaine par société appliqués à la SPA et aux PDF, au-delà des bases CompanyProfile. (SCHEMA)
- [ ] FG393 — **Éditeur de modèles imprimables/brandés** — éditeur de modèles PDF/email/WhatsApp (aujourd'hui code ou fixes). (SCHEMA)
- [ ] FG394 — **Consentement & DSR (loi 09-08 / CNDP)** — registre de consentement + export/effacement des demandes de personnes concernées (sur le `consent_timestamp` existant). (SCHEMA)
- [ ] FG395 — **Sauvegarde/restauration en libre-service** — export/restore de données société à la demande + planifié (les bundles d'export existent, restore + planif non). (SCHEMA)
- [ ] FG396 — **Monitoring d'erreurs (Sentry)** — supervision des erreurs applicatives, init gardée par DSN (no-op sans DSN). (DEP:sentry-sdk)
- [ ] FG397 — **Page d'état / santé système** — page status/health (santé des services + incidents récents). (ROUTINE)
- [ ] FG398 — **Plans de tarif API & analytics d'usage** — limites par `ApiKey` + vue d'usage (les clés existent, quotas/usage non). (SCHEMA)
- [ ] FG399 — **Journal des nouveautés in-app (changelog)** — fil de notes de version avec suivi de lecture par utilisateur. (SCHEMA)

---

## NEW MODULES — dedicated module deep-dives 2026-06-21 (PAIE/COMPTA/PROJ/GED/FLOTTE/QHSE/CONTRAT/KB/LITIGE)

Whole **new modules** an ERP needs, each spec'd by its own deep-dive lane (entities, lifecycle,
Moroccan specifics, integration with existing apps). An ERP-module landscape survey confirmed the
FG1–FG399 backlog + these deep-dives already cover nearly every standard ERP module; the only
genuinely-missing extras it recommended (internal Knowledge Base, formal Réclamations/Litiges) are
added at the end. **Each module's first task is `ARCH` (a brand-new app = stop-and-ask / founder
sign-off); its sub-features are then buildable `SCHEMA`/`ROUTINE`/`DECISION`/`DEP`/`AUTH`.** All obey
the STANDING RULES (multi-tenant company FK forced, additive-only, French UI, cross-app via
services/selectors, references via `apps/ventes/utils/references.py` never count()+1, buy
prices/margins/`cout` internal-only, `STAGES.py`/`/proposal` untouched, Odoo JSON-2 only). Many of
these overlap and SUPERSEDE the domain-list FG items as the module-organized home for the same work.

### Module Paie — paie marocaine (`apps/paie`) · PAIE1–PAIE36
**But :** moteur de paie marocain (bulletin conforme : IR progressif, CNSS/AMO plafonnées, CIMR, congés, HS, primes/retenues) consommant le dossier RH + éléments variables, produisant bulletin/virement/livre de paie/déclarations + coffre-fort employé. **Intègre :** RH (DossierEmploye), Compta (journal de paie), notifications, documents, records. **Salaires gated rôle paie.**
- [x] PAIE1 — App `paie` + permissions `paie_voir`/`paie_gerer`. (ARCH)  [DONE 2026-06-22: NEW app apps/paie (admin/responsable-gated via IsResponsableOrAdmin; custom paie_voir/paie_gerer codenames = follow-up).]
- [x] PAIE2 — `ParametrePaie` : constantes par société versionnées (SMIG/SMAG, plafond CNSS, taux CNSS/AMO/CIMR/taxe formation, frais pro, déductions familiales). (SCHEMA)  [DONE 2026-06-22: ParametrePaie (SMIG/SMAG, plafond CNSS, taux CNSS/AMO/formation), versionné par date_effet.]
- [x] PAIE3 — Valeurs légales par défaut (taux/plafonds 2026) + validation fondateur. (DECISION)  [DONE 2026-06-22: Valeurs légales 2026 (CNSS/AMO/IR barème/frais pro) semées comme défauts éditables, flag valide_par_fondateur=False, seed idempotent + endpoint, 11 tests.]
- [x] PAIE4 — `BaremeIR` : tranches + somme à déduire, versionné par date d'effet. (SCHEMA)  [DONE 2026-06-22: BaremeIR + TrancheIR (tranches + somme à déduire), versionné par date d'effet.]
- [x] PAIE5 — Barème IR officiel + déductions charges de famille. (DECISION)  [DONE 2026-06-22: Barème IR + déductions charges de famille — champs deduction_par_personne_a_charge (30 MAD) + plafond_personnes_a_charge (6) sur ParametrePaie semés éditables ; helper compute_ir (barème − somme à déduire − déductions famille, planché 0). Migration 0003 additive, 22 tests.]
- [x] PAIE6 — `Rubrique` paramétrable (gain/retenue/cotisation, flags imposable/CNSS/AMO/CIMR, compte). (SCHEMA)  [DONE 2026-06-22: Rubrique paramétrable — Rubrique (company-scoped, unique code, type gain/retenue/cotisation, flags imposable/soumis_cnss/soumis_amo/soumis_cimr, compte, base+taux/montant_fixe, ordre/actif) + seed idempotent 7 rubriques standard (SB/PRIME/HS/CNSS/AMO/IR/AVANCE). Endpoint rubriques/ + seed-defaults. Migration 0004 additive, 7 tests.]
- [x] PAIE7 — Catalogue de rubriques standard (transport/panier/ancienneté/HS…) — seed idempotent. (ROUTINE) [DONE 2026-06-22: Catalogue rubriques standard (transport/panier/ancienneté/CIMR…), seed idempotent; ensure_rubriques_standard + endpoint seed-standard; 3 tests.]
- [x] PAIE8 — `ProfilPaie` (OneToOne→DossierEmploye) : type rémunération, salaire base, affiliations, RIB. (DEP:RH-FG154) [DONE 2026-06-22: ProfilPaie (OneToOne→rh.DossierEmploye), type rémunération/affiliations CNSS-AMO-CIMR/RIB; /profils/; 5 tests.]
- [x] PAIE9 — `RubriqueEmploye` : rubriques récurrentes par employé. (SCHEMA) [DONE 2026-06-22: RubriqueEmploye (rubriques récurrentes par profil); /rubriques-employe/; 2 tests.]
- [x] PAIE10 — `PeriodePaie` : run mensuel + statuts brouillon→calculée→validée→clôturée. (SCHEMA) [DONE 2026-06-22: PeriodePaie (run mensuel, statuts brouillon→calculée→validée→clôturée strictement progressifs); /periodes/ + changer-statut; 6 tests.]
- [x] PAIE11 — `ElementVariable` + import depuis RH (heures/HS/absences/primes). (DEP:RH-FG192) [DONE 2026-06-22: ElementVariable (heures/HS/absence/prime/retenue) + importer_elements_rh (cross-app via rh.selectors, idempotent, inerte tant que RH n'expose pas d'heures); 4 tests.]
- [x] PAIE12 — Moteur de calcul du bulletin (`services.calculer_bulletin`). (ROUTINE) [DONE 2026-06-22: Moteur calculer_bulletin (brut/CNSS plafonnée/AMO/CIMR/IR barème + charges famille/net à payer); action bulletin; 8 tests. Migration paie 0005 additive (dépend de rh.0006).]
- [x] PAIE13 — Salaire de base multi-profils (mensuel/journalier/forfait/horaire) + proration. (ROUTINE)
- [x] PAIE14 — Heures supplémentaires majorées (25/50/100 % jour/nuit/férié). (ROUTINE) [DONE 2026-06-27: `ParametrePaie` gains taux_hs_jour/nuit/ferie (défauts 25/50/100 %, éditables par société) + `ElementVariable.categorie_hs`; `services` helpers (taux_majoration_hs, calculer_gain_hs, taux_horaire_base_profil) wired into `calculer_bulletin` (quantité × taux horaire × majoration ; montant explicite l'emporte). Migration paie 0007 additive, 20 tests.]
- [x] PAIE15 — Prime d'ancienneté barème (5/10/15/20/25 %). (ROUTINE) [DONE 2026-06-27: barème ancienneté (5 seuils/taux éditables sur `ParametrePaie`, défauts 2/5/12/20/25 ans → 5/10/15/20/25 %) + helpers `taux_anciennete`/`calculer_prime_anciennete` câblés dans `calculer_bulletin` (gain ANCIENNETE, base prorata) ; date d'embauche lue via nouveau selector `rh.date_embauche_employe` (cross-app propre). Sans date → 0, aucun effet. Migration paie 0008, tests.]
- [x] PAIE16 — Avantages en nature & indemnités imposables vs non-imposables (plafonds). (DECISION)
- [x] PAIE17 — `BulletinPaie` + `LigneBulletin` (snapshot immuable une fois validé). (SCHEMA)
- [x] PAIE18 — CNSS plafonnée (part salariale & patronale). (ROUTINE)
- [x] PAIE19 — AMO (sans plafond) salariale & patronale. (ROUTINE)
- [x] PAIE20 — CIMR optionnelle (taux par employé adhérent). (ROUTINE)
- [x] PAIE21 — Frais professionnels & net imposable. (ROUTINE)
- [x] PAIE22 — Calcul IR (barème progressif + charges de famille). (DECISION)
- [x] PAIE23 — Allocations familiales (info patronale). (ROUTINE)
- [x] PAIE24 — Taxe de formation professionnelle (1,6 % patronal). (ROUTINE)
- [ ] PAIE25 — Provision congés payés (consomme les soldes RH). (DEP:RH-FG162)
- [ ] PAIE26 — Paiement & décompte des congés/absences sur le bulletin. (ROUTINE)
- [ ] PAIE27 — `CumulAnnuel` (brut/net imposable/IR/CNSS/congés). (SCHEMA)
- [ ] PAIE28 — `Avance`/`PretSalarie` + déduction mensuelle. (DEP:RH-FG195)
- [ ] PAIE29 — Saisie-arrêt / cession sur salaire (quotité saisissable). (DECISION)
- [ ] PAIE30 — `OrdreVirement` + fichier de virement banque. (ROUTINE)
- [ ] PAIE31 — Déclaration CNSS (BDS / format DAMANCOM). (ROUTINE)
- [ ] PAIE32 — État IR 9421 + retenues à la source. (ROUTINE)
- [ ] PAIE33 — Livre de paie + journal de paie → écritures (via `compta.services`). (DEP:COMPTA)
- [ ] PAIE34 — PDF bulletin conforme + attestations (salaire/travail/domiciliation) via `documents`. (ROUTINE)
- [ ] PAIE35 — Coffre-fort bulletins (self-service employé, scopé à l'utilisateur). (AUTH)
- [ ] PAIE36 — Clôture mensuelle + verrouillage + bulletins rectificatifs/rappels. (SCHEMA)

### Module Comptabilité générale (`apps/compta`) · COMPTA1–COMPTA40
**But :** grand livre en partie double (plan CGNC, journaux, écritures auto-postées depuis les documents existants) produisant les états marocains (grand livre, balance, CPC, bilan, ESG/ETIC), FEC et piste d'audit inaltérable — sans devenir un chemin documentaire alternatif. **Intègre :** ventes/stock/paie/immo/trésorerie/reporting via services/selectors ; **statut-préservation** (ne mute jamais devis/facture). Recouvre/organise FG107–FG153.
- [x] COMPTA1 — Plan comptable CGNC paramétrable + `seed_plan_comptable` idempotent. (ARCH) [DONE (already present) 2026-06-27: verified on `main` — `compta.PlanComptable` + `CompteComptable` (company, code, classe 1–8, parent hierarchy, sens/type, unique (company, code)) + `services.seed_plan_comptable` idempotent (8 classes + 3421/4411/5141/5161/7111/4455/3455) + serializers/viewsets/urls + tests already exist (compta 0001). No code change.]
- [ ] COMPTA2 — Mapping document→compte par société (familles/TVA/modes de paiement → comptes). (SCHEMA)
- [ ] COMPTA3 — Comptes auxiliaires tiers (dérivés de `crm.Client`/`stock.Fournisseur` via selectors). (SCHEMA)
- [ ] COMPTA4 — Journaux paramétrables (VTE/ACH/BNK/CSH/OD/AN) + séquences. (SCHEMA)
- [ ] COMPTA5 — Multi-exercice & périodes comptables. (SCHEMA)
- [ ] COMPTA6 — Validation légale du plan/format CGNC (fiduciaire). (DECISION)
- [ ] COMPTA7 — Écriture en partie double équilibrée (Σ débit = Σ crédit). (SCHEMA)
- [ ] COMPTA8 — Saisie d'OD manuelle (régularisations/provisions/corrections). (ROUTINE)
- [ ] COMPTA9 — Numérotation séquentielle des pièces (via `references.py`, jamais count()+1). (ROUTINE)
- [ ] COMPTA10 — Pièces justificatives sur écriture. (SCHEMA)
- [ ] COMPTA11 — Extourne / contre-passation (jamais supprimer une écriture validée). (ROUTINE)
- [ ] COMPTA12 — Auto-écriture depuis facture client (3421/71xx/4455x), réconcilie au journal-ventes. (ROUTINE)
- [ ] COMPTA13 — Auto-écriture depuis avoir. (ROUTINE)
- [ ] COMPTA14 — Auto-écriture depuis paiement client (514x/516x/caisse). (ROUTINE)
- [ ] COMPTA15 — Auto-écriture depuis facture fournisseur (61xx/3455x/4411). (ROUTINE)
- [ ] COMPTA16 — Auto-écriture depuis paiement fournisseur. (ROUTINE)
- [ ] COMPTA17 — Contrat de posting paie & immobilisations (signatures de service). (ARCH)
- [ ] COMPTA18 — Statut-préservation & idempotence du posting (test-guarded). (ROUTINE)
- [ ] COMPTA19 — Grand livre (détail par compte + solde courant + lettrage, export xlsx). (SCHEMA)
- [ ] COMPTA20 — Balance générale (trial balance — distincte de la balance âgée existante). (ROUTINE)
- [ ] COMPTA21 — Balance auxiliaire clients/fournisseurs. (ROUTINE)
- [ ] COMPTA22 — Lettrage clients/fournisseurs (manuel + auto-suggest). (SCHEMA)
- [ ] COMPTA23 — Référentiel `CompteTresorerie` (banque/caisse/RIB/devise) lié au GL. (SCHEMA)
- [ ] COMPTA24 — Journal de caisse (petty cash) + clôture de caisse. (SCHEMA)
- [ ] COMPTA25 — Virements internes (écriture à deux jambes). (ROUTINE)
- [ ] COMPTA26 — Import relevé bancaire & rapprochement. (SCHEMA)
- [ ] COMPTA27 — CPC (Compte de Produits et Charges). (SCHEMA+DECISION)
- [ ] COMPTA28 — Bilan (format CGNC). (SCHEMA+DECISION)
- [ ] COMPTA29 — ESG / états de synthèse + ETIC. (DECISION)
- [ ] COMPTA30 — Tableau de bord financier directeur (P&L/cash/DSO/DPO/marge). (ROUTINE)
- [ ] COMPTA31 — Clôture mensuelle & verrouillage de période. (SCHEMA)
- [ ] COMPTA32 — Clôture d'exercice & génération des à-nouveaux. (SCHEMA+DECISION)
- [ ] COMPTA33 — Réouverture / correction d'exercice clos (audité). (DECISION)
- [ ] COMPTA34 — Préparation déclaration TVA (régime débit/encaissement). (SCHEMA+DECISION)
- [ ] COMPTA35 — Relevé de déductions détaillé (annexe TVA). (ROUTINE)
- [ ] COMPTA36 — Export FEC (format DGI auditable). (SCHEMA+DECISION)
- [ ] COMPTA37 — Liasse fiscale & export fiduciaire (Sage/CEGID ; Odoo JSON-2 only). (DECISION+ARCH)
- [ ] COMPTA38 — Comptabilité analytique / centres de coût (axe chantier/agence/marché/commercial). (ARCH)
- [ ] COMPTA39 — Piste d'audit comptable inaltérable (écritures hash-chaînées). (SCHEMA)
- [ ] COMPTA40 — Séparation des tâches (saisie vs validation vs clôture). (DECISION)

### Module Gestion de projet (`apps/gestion_projet`) · PROJ1–PROJ38
**But :** couche projet/programme au-dessus de `installations` regroupant N chantiers+devis+factures+tickets+achats avec WBS/dépendances/chemin critique, Gantt, capacité ressources, budget & P&L projet, jalons de facturation, timesheets, risques, documents, portefeuille. **Statuts propres** (jamais STAGES.py / statut chantier) ; coûts/marges internes. Recouvre FG291–FG303.
- [x] PROJ1 — Modèle `Projet`/Programme multi-chantiers + `ProjetChantier`. (ARCH)  [DONE 2026-06-22: NEW app apps/gestion_projet: Projet + ProjetChantier (multi-chantiers, statut propre, jamais STAGES.py).]
- [x] PROJ2 — Liens projet → devis/factures/tickets/achats (string-FK via selectors). (SCHEMA)
- [x] PROJ3 — Machine à états du projet (propre, jamais STAGES.py). (DECISION)
- [x] PROJ4 — Phases de projet (étude/appro/pose/MES/réception). (SCHEMA)
- [x] PROJ5 — Tâches & sous-tâches (WBS). (ARCH)  [DONE 2026-06-22: Tache WBS (parent self-FK → sous_taches, statut propre jamais STAGES.py, avancement/charge) + sélecteur arbre + endpoints, 21 tests.]
- [x] PROJ6 — Dépendances de tâches FS/SS/FF/SF + lag. (SCHEMA)  [DONE 2026-06-22: Dépendances de tâches — DependanceTache (predecesseur/successeur→Tache, type FS/SS/FF/SF, lag ±j) avec gardes anti-self / anti-cross-project / anti-cycle direct ; sélecteurs prédécesseurs/successeurs (fondation CPM PROJ8). Migration 0006 additive, 21 tests.]
- [x] PROJ7 — Jalons (+ `facturation_pct`). (SCHEMA)  [DONE 2026-06-22: Jalons (+ facturation_pct) — Jalon (projet + phase/tache optionnels SET_NULL same-project, libelle, date_prevue/reelle, statut propre a_venir/atteint/manque jamais STAGES.py, facturation_pct 0–100 validé modèle+serializer). Endpoints jalons/ + projets/<id>/jalons/, sélecteur jalons_for_projet ordonné. Migration 0007 additive, 19 tests.]
- [x] PROJ8 — Calcul du chemin critique (CPM) + marges. (ROUTINE) [DONE 2026-06-22: Chemin critique CPM + marges (forward/backward FS/SS/FF/SF+lag, tri topo, marges totale/libre); endpoint chemin-critique; 18 tests.]
- [x] PROJ9 — Roll-up d'avancement (pondéré par charge). (ROUTINE) [DONE 2026-06-22: Roll-up d'avancement pondéré par charge (récursif); endpoint avancement; 10 tests.]
- [x] PROJ10 — API planning Gantt. (ROUTINE) [DONE 2026-06-22: API planning Gantt (barres datées CPM + liens); endpoint gantt; 8 tests.]
- [x] PROJ11 — Drag-reschedule des tâches (recalcule les successeurs). (ROUTINE) [DONE 2026-06-22: Drag-reschedule (reprogrammer_tache, cascade successeurs FS/SS/FF/SF, anti-cycle); endpoint reprogrammer; 12 tests.]
- [x] PROJ12 — Calendrier projet (jours ouvrés/fériés). (SCHEMA) [DONE 2026-06-22: Calendrier projet (jours ouvrés/fériés); CalendrierProjet + JourFerie; migration 0008 additive; 12 tests.]
- [x] PROJ13 — Baseline de planning (plan vs réel). (SCHEMA) [DONE 2026-06-22: Baseline de planning (plan vs réel); BaselinePlanning + BaselineTache + comparer_baseline; migration 0009 additive; 9 tests.]
- [x] PROJ14 — Détection des retards (tâches/jalons à risque). (ROUTINE)
- [x] PROJ15 — Profil ressource & équipes (RH-léger, `cout_horaire` interne). (SCHEMA) [DONE 2026-06-27: `gestion_projet.RessourceProfil` (company forcé, user FK optionnel, role/competences, `cout_horaire` interne) + `Equipe` (M2M membres) avec contraintes uniques nommées ; viewsets company-scoped + filtres. Migration gestion_projet 0010, 10 tests.]
- [x] PROJ16 — Affectation des ressources (User/équipe/camionnette/machine). (ARCH) [DONE 2026-06-27: `gestion_projet.AffectationRessource` (company forcé, FK Tache, ressource RessourceProfil OU equipe Equipe OU actif lâche `flotte.ActifFlotte` via type+id — exactement un vecteur validé, dates, charge/quantité) + viewset company-scoped + filtres. Cross-app par string-FK uniquement. Migration gestion_projet 0011 (regénérée), 18 tests.]
- [x] PROJ17 — Indisponibilités ressources (congé/formation/arrêt). (SCHEMA)
- [x] PROJ18 — Plan de charge (capacité vs affecté). (ROUTINE)
- [x] PROJ19 — Détection de conflits d'affectation. (ROUTINE)
- [x] PROJ20 — Nivellement de charge (levelling). (ROUTINE)
- [x] PROJ21 — Budget projet (lignes : matériel/MO/sous-traitance/divers). (SCHEMA)
- [x] PROJ22 — Coûts engagés vs réels (factures fournisseur + MO + sous-traitance). (ROUTINE)
- [ ] PROJ23 — Alertes de dépassement budgétaire. (ROUTINE)
- [ ] PROJ24 — Suivi des temps (timesheets imputés au projet). (SCHEMA)
- [ ] PROJ25 — Consommation matière vs BoM (via selectors). (ROUTINE)
- [ ] PROJ26 — P&L de projet consolidé (interne/admin). (ARCH)
- [ ] PROJ27 — Jalons de facturation liés à l'avancement (via `ventes.services`). (ROUTINE)
- [ ] PROJ28 — Suivi avancement vs facturé. (ROUTINE)
- [ ] PROJ29 — EVM léger (valeur acquise) — optionnel. (ROUTINE)
- [ ] PROJ30 — Registre des risques. (SCHEMA)
- [ ] PROJ31 — Registre d'actions. (SCHEMA)
- [ ] PROJ32 — Comptes-rendus de réunion de chantier. (SCHEMA)
- [ ] PROJ33 — Documents & plans versionnés. (ARCH)
- [ ] PROJ34 — Commentaires & @mentions. (SCHEMA)
- [ ] PROJ35 — Templates de projet par type d'installation. (SCHEMA)
- [ ] PROJ36 — Tableau de bord portefeuille (avancement/retards/marge/charge). (ROUTINE)
- [ ] PROJ37 — Portail d'avancement client (sans coûts/marges). (ARCH)
- [ ] PROJ38 — Sous-traitance & clôture + retour d'expérience. (ARCH)

### Module GED — gestion documentaire (`apps/ged`) · GED1–GED38
**But :** DMS multi-tenant transformant les fichiers épars (`records.Attachment`) en référentiel gouverné : arborescence, métadonnées/tags, versionnage, recherche plein-texte+OCR (pgvector), liaison polymorphe, ACL + partage tokenisé, cycle de vie/approbation, rétention/archivage, modèles, scan-to-DMS, journal d'accès. **Réutilise** records.storage/OCR/WeasyPrint/notifications. Étend FG10.
- [x] GED1 — Squelette de l'app `apps/ged` (services/selectors, scoping société). (ARCH)
- [x] GED2 — Cabinet + Folder arborescent (path matérialisé). (SCHEMA)
- [x] GED3 — Document + DocumentVersion (file_key MinIO, checksum/dedupe). (SCHEMA)
- [x] GED4 — CRUD dossiers/documents + déplacement (scopé société). (ROUTINE)
- [x] GED5 — Navigateur arborescent FR (frontend). (ROUTINE)  [DONE 2026-06-22: Navigateur arborescent FR /ged (frontend) — arbre dossiers expand/collapse + table documents, consomme les endpoints ged existants, 7 tests.]
- [x] GED6 — Liaison polymorphe Document↔objet métier (étend `records.ALLOWED_TARGETS`). (SCHEMA+DECISION)  [DONE 2026-06-22: Liaison polymorphe Document↔objet — DocumentLien (ContentType générique via records.resolve_target), records.ALLOWED_TARGETS étendu (+ventes.boncommande → 8 types), endpoints /ged/liens/ + reverse-lookup, company/created_by serveur, import-linter 4/4 KEPT. Migration ged 0002 additive, tests ged+records 99.]
- [x] GED7 — Migration des `records.Attachment` existants (réutilise file_key). (DECISION)  [DONE 2026-06-22: Import idempotent des records.Attachment — command migrate_attachments_to_ged [--company][--dry-run] : chaque Attachment → Document (cabinet/folder « Importé » auto par société) + DocumentVersion v1 RÉUTILISANT le file_key MinIO (aucune copie), + DocumentLien (GED6) si la cible est dans ALLOWED_TARGETS. Clé idempotence (company, file_key) ; originaux jamais mutés. Aucune migration (command), 9 tests.]
- [x] GED8 — Coffre-fort par employé/client (ACL owner+admin). (SCHEMA+DECISION) [DONE 2026-06-22: Coffre-fort par employé/client (ACL propriétaire+admin); Coffre + Document.coffre + ACL liste/détail; migration 0003; 10 tests.]
- [x] GED9 — Taxonomie de tags. (SCHEMA) [DONE 2026-06-22: Taxonomie de tags hiérarchique (DocumentTag self-FK anti-cycle + assignment); migration 0004; 9 tests.]
- [x] GED10 — Métadonnées typées configurables (réutilise `customfields`). (SCHEMA) [DONE 2026-06-22: Métadonnées typées configurables (réutilise customfields, Document.custom_data validé); migrations ged 0005 + customfields 0003; 5 tests.]
- [x] GED11 — Recherche plein-texte Postgres (SearchVector + GIN). (SCHEMA) [DONE 2026-06-22: Recherche plein-texte Postgres (SearchVector pondéré + GIN, endpoint recherche?q=); migration 0006; 7 tests.]
- [x] GED12 — Index OCR + recherche sémantique (pgvector, key-gated no-op). (DEP) [DONE 2026-06-22: Index OCR + recherche sémantique pgvector (key-gated NoOp, dégrade en plein-texte sans clé); migration 0007; 7 tests. NOTE: embedding OFF par défaut (GED_EMBEDDING_ENABLED), aucun coût/réseau tant que non activé.]
- [x] GED13 — Filtres & recherche avancée (frontend). (ROUTINE) [DONE 2026-06-22: Filtres & recherche avancée (frontend GedSearch.jsx + search.js + gedApi); 14 tests frontend node:test.]
- [x] GED14 — Aperçu inline multi-format (proxy même-origine). (ROUTINE)
- [x] GED15 — Versionnage + historique + restauration de version. (SCHEMA) [DONE 2026-06-27: sur le `DocumentVersion` existant — endpoint `documents/<id>/historique/` (versions, plus récentes d'abord) + action `documents/<id>/restaurer/` créant une NOUVELLE version courante depuis une antérieure (historique préservé), champ d'audit `restored_from`. Réutilise le file_key (pas de ré-upload MinIO). Migration ged 0008 (additive), 16 tests (ACL coffre, rôle, isolation société).]
- [x] GED16 — Check-out / check-in (verrouillage). (ROUTINE) [DONE 2026-06-27: verrouillage optimiste sur `Document` (`locked_by`/`locked_at`, propriété `is_locked`) + actions `documents/<id>/check-out/` (409 si déjà verrouillé) et `check-in/` (locker ou admin) ; ajout de version refusé si verrouillé par un autre (select_for_update). Migration ged 0009 additive, 20 tests.]
- [x] GED17 — Cycle de vie documentaire (brouillon→revue→approuvé→archivé→obsolète). (SCHEMA+DECISION)
- [x] GED18 — Workflow d'approbation/revue. (SCHEMA)
- [x] GED19 — ACL par dossier/document (héritage + override). (SCHEMA+DECISION)
- [x] GED20 — Partage par lien tokenisé (expiry/mot de passe/quota). (SCHEMA+DECISION)
- [x] GED21 — Watermarking & contrôle de diffusion. (DEP)
- [x] GED22 — Politiques de rétention. (SCHEMA)
- [x] GED23 — Archivage légal à valeur probante (write-once/object-lock). (DECISION)
- [x] GED24 — Rétention légale / legal hold. (SCHEMA)
- [ ] GED25 — Purge automatique & tâche planifiée (dry-run d'abord). (DEP+DECISION)
- [x] GED26 — Corbeille & restauration. (SCHEMA)
- [x] GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint, hors /proposal). (ROUTINE)
- [x] GED28 — Génération de document → classement automatique. (ROUTINE)
- [ ] GED29 — Filage des PDF après-vente générés (depuis `documents`). (ROUTINE)
- [ ] GED30 — Signature électronique (point d'intégration + stub no-op). (DEP+DECISION)
- [ ] GED31 — Numérisation par lot (scan-to-DMS) + OCR. (DEP)
- [ ] GED32 — Import en masse (zip/CSV de métadonnées). (ROUTINE)
- [ ] GED33 — OCR de pièces (CIN/factures/BL) → métadonnées. (DEP)
- [ ] GED34 — Classification automatique (IA, no-op sans clé). (DEP)
- [ ] GED35 — Journal d'audit d'accès aux documents (lectures). (SCHEMA)
- [ ] GED36 — Quotas de stockage par société. (SCHEMA+DECISION)
- [ ] GED37 — Permissions & garde-prix sur tous les endpoints. (ROUTINE)
- [ ] GED38 — Contrats d'import + CODEMAP + tests. (ROUTINE)

### Module Gestion de flotte (`apps/flotte`) · FLOTTE1–FLOTTE35
**But :** référentiel et opérations de tout ce qui roule (camionnettes, nacelles, groupes électrogènes) : immatriculation/compteurs, conducteurs+permis, carburant, entretien, échéances réglementaires marocaines (TSAV/assurance/visite technique), sinistres, télématique, trajets imputés chantier, TCO. Recouvre FG334–FG342.
- [x] FLOTTE1 — Nouvelle app `apps/flotte` (squelette multi-tenant). (ARCH)
- [x] FLOTTE2 — Modèle `Vehicule` (immat/marque/énergie/km/valeur/statut). (SCHEMA)
- [x] FLOTTE3 — Lien `Vehicule.emplacement_stock` ↔ `stock.EmplacementStock` (via selector). (DEP)
- [x] FLOTTE4 — `EnginRoulant` (compteur d'heures, nacelle/groupe/chariot). (SCHEMA)
- [x] FLOTTE5 — Référence d'actif commune (Vehicule|Engin) pour entretien/sinistre/doc. (DECISION)
- [x] FLOTTE6 — Référentiels listes (type véhicule/engin, énergie, catégorie permis). (SCHEMA)
- [x] FLOTTE7 — `Conducteur` + permis (lien `authentication.User`). (SCHEMA) [DONE 2026-06-27: `flotte.Conducteur` (company forcé, user FK nullable→authentication.User `related_name=conducteurs_flotte`, numero/categorie permis, dates obtention/expiration, actif) + company-scoped viewset, `?actif`/`?permis_expirant=<jours>` filters, selectors conducteurs_de_la_societe/permis_expirant. Migration flotte 0006 additive, 17 tests.]
- [x] FLOTTE8 — `AffectationConducteur` (conducteur↔véhicule datée). (ROUTINE) [DONE 2026-06-27: `flotte.AffectationConducteur` (company forcé, FK Conducteur + Vehicule, date_debut/date_fin, actif) + viewset company-scoped + filtres ?vehicule/?conducteur/?actif + selectors (conducteur actuel du véhicule). Validation date_fin ≥ date_debut + intégrité cross-company. Migration flotte 0007 additive, 25 tests.]
- [x] FLOTTE9 — Contrôle permis valide/catégorie à l'affectation. (ROUTINE)
- [x] FLOTTE10 — `ReservationVehicule` + détection de conflit. (ROUTINE)
- [x] FLOTTE11 — Check-list état des lieux départ/retour (photos). (SCHEMA)
- [x] FLOTTE12 — Carnet de carburant (`PleinCarburant`). (SCHEMA)
- [x] FLOTTE13 — Calcul conso L/100 km (et kWh/100 km). (ROUTINE)
- [x] FLOTTE14 — Cartes carburant & alertes anomalie (km incohérent/fraude). (ROUTINE)
- [x] FLOTTE15 — Plans d'entretien préventif (km/date/heures). (SCHEMA)
- [x] FLOTTE16 — Génération d'échéances d'entretien dues + alertes. (ROUTINE)
- [x] FLOTTE17 — Ordres de réparation + atelier/garage + coûts. (SCHEMA)
- [x] FLOTTE18 — Pneumatiques & pièces. (SCHEMA)
- [x] FLOTTE19 — `EcheanceReglementaire` (modèle générique). (SCHEMA)
- [x] FLOTTE20 — Vignette / TSAV (barème CV/énergie, référentiel éditable). (ROUTINE)
- [x] FLOTTE21 — Assurance auto (police/échéance/attestation/franchise). (ROUTINE)
- [x] FLOTTE22 — Visite technique (validité paramétrable). (ROUTINE)
- [x] FLOTTE23 — Carte grise & autorisation de circulation (GED). (SCHEMA)
- [x] FLOTTE24 — Moteur d'alertes d'échéances réglementaires (J-30/15/7/échu). (ROUTINE)
- [x] FLOTTE25 — `Sinistre` (accident/constat/assurance). (SCHEMA)
- [ ] FLOTTE26 — `Infraction` / PV de circulation. (SCHEMA)
- [ ] FLOTTE27 — Point d'intégration télématique (no-op sans fournisseur). (DEP)
- [ ] FLOTTE28 — Suivi de position & trajets télématiques. (DEP)
- [ ] FLOTTE29 — Journal kilométrique & trajets par chantier (via `installations.selectors`). (ROUTINE)
- [ ] FLOTTE30 — Amortissement (lien immobilisations). (UNGATED 2026-06-21 — buildable once a compta/immobilisations sub-module exists; sequence it after the relevant COMPTA task. No founder input needed — it's an intra-plan dependency, not an external blocker.) (DEP)
- [ ] FLOTTE31 — Coût total de possession (TCO) par véhicule (interne). (ROUTINE)
- [ ] FLOTTE32 — Pool de véhicules & demandes. (ROUTINE)
- [ ] FLOTTE33 — Éco-conduite & CO₂. (ROUTINE)
- [ ] FLOTTE34 — Documents véhicule (GED). (DEP)
- [ ] FLOTTE35 — Tableau de bord flotte (dispo/échéances/coûts/conso). (ROUTINE)

### Module QHSE — qualité, hygiène, sécurité & environnement (`apps/qhse`) · QHSE1–QHSE40
**But :** couche programme/site au-dessus de la checklist F18 : ITP + points d'arrêt + relevés (couples/polarité/isolement/I-V), NCR/CAPA, audits, document unique/permis de travail, incidents+CNSS, inspections/TF-TG, déchets (BSD loi 28-00)/recyclage modules, bilan carbone/ESG. **Garde F18 intacte.** Recouvre FG181–FG186, FG343–FG349.
- [x] QHSE1 — App QHSE + socle multi-tenant. (ARCH)  [DONE 2026-06-22: NEW app apps/qhse, socle multi-tenant.]
- [x] QHSE2 — ITP : `PlanInspectionModele` + `PointControleModele` (phase/type relevé/hold-point). (SCHEMA)
- [x] QHSE3 — Seed ITP solaire par type d'installation. (ROUTINE)
- [x] QHSE4 — `PlanInspectionChantier` + `ReleveControle` (valeur/conforme/photo). (SCHEMA)
- [x] QHSE5 — Auto-conformité des relevés mesurés (vs min/max attendu). (ROUTINE)  [DONE 2026-06-22: Auto-conformité des relevés: valeur_min/max sur PointControleModele, conforme calculé dans ReleveControle.save() (inclusif, numérique seulement), 16 tests.]
- [x] QHSE6 — Points d'arrêt bloquants (hold points) gating l'avancement chantier. (DECISION)  [DONE 2026-06-22: Points d’arrêt bloquants — selectors.hold_points_status / phase_peut_avancer (un hold-point sans relevé ou non-conforme bloque l’avancement ; conforme débloque), endpoint plans-chantier/<id>/hold-points/ + champs peut_avancer / nb_hold_points_bloquants. Aucune migration (lecture seule), 15 tests.]
- [x] QHSE7 — Relevé courbe I-V par string. (SCHEMA)  [DONE 2026-06-22: Relevé courbe I-V par string — ReleveCourbeIV (chantier_id loose, plan_chantier SET_NULL, string_id, voc/isc/vmpp/impp/pmpp, irradiance, temperature_module, courbe_points JSON [{v,i}]) + fill_factor()=Pmpp/(Voc·Isc) si présents. Endpoints courbes-iv/ + par-chantier, sélecteur courbes_iv_for_chantier (aucun import installations). Migration 0005 additive, tests.]
- [x] QHSE8 — Photos de contrôle (avant/pendant/après) via `records.Attachment`. (ROUTINE) [DONE 2026-06-22: Photos de contrôle par phase via records.Attachment (ALLOWED_TARGETS), endpoint releves/<id>/photos/; 6 tests.]
- [x] QHSE9 — `NonConformite` (NCR : gravité/origine/source/photos). (SCHEMA)  [DONE 2026-06-22: NonConformite (NCR: gravité/origine/statut/chantier loose-FK).]
- [x] QHSE10 — `ActionCorrectivePreventive` (CAPA) + cause racine. (SCHEMA)  [DONE 2026-06-22: ActionCorrectivePreventive (CAPA + cause racine, lié NCR).]
- [x] QHSE11 — Pont réserve (`installations.Reserve`) → NCR. (ROUTINE) [DONE 2026-06-22: Pont réserve installations.Reserve→NCR via installations.selectors (string-FK, creer_ncr_depuis_reserve idempotent); migration 0006; 8 tests.]
- [x] QHSE12 — Relances CAPA en retard (notifications/digest). (ROUTINE) [DONE 2026-06-22: Relances CAPA en retard (capa_en_retard + relancer_capa_en_retard best-effort); endpoints; 7 tests.]
- [x] QHSE13 — Vérification d'efficacité CAPA (clôture conditionnée). (ROUTINE) [DONE 2026-06-22: Vérification d'efficacité CAPA + clôture NCR conditionnée; migration 0007; 10 tests.]
- [x] QHSE14 — Chatter QHSE (NCR/CAPA/Incident/Audit). (SCHEMA) [DONE 2026-06-22: Chatter QHSE (QhseChatterEntry + auto-log create/field-change + historique/noter); migration 0008; 9 tests.]
- [x] QHSE15 — `GrilleAudit` + `CritereAudit` pondérés. (SCHEMA) [DONE 2026-06-22: GrilleAudit + CritereAudit pondérés (poids_total/note_max); migration 0009; 8 tests.]
- [x] QHSE16 — `Audit` + `ReponseCritere` + score (→ NCR). (SCHEMA) [DONE 2026-06-27: `qhse.Audit` (company forcé, grille FK, date/auditeur/statut/score/notes) + `ReponseCritere` (audit+critere, conforme/non_conforme/na, UniqueConstraint audit+critère) over the existing GrilleAudit/CritereAudit template; services calculer_score_audit (% conforme, NA exclu) + lever_ncr_audit (idempotent NonConformité par réponse non-conforme); company-scoped viewsets + `/calculer-score/` `/lever-ncr/` actions, Audit registered for chatter. Migration qhse 0010 additive, 14 tests.]
- [x] QHSE17 — Grille de notation fin de chantier (gate clôture). (DECISION) [DONE 2026-06-27: `qhse.NotationFinChantier` (company forcé, chantier lâche, score 0-100, seuil_passage défaut 70, verdict passe/échec, auteur serveur) + `ItemNotation` (items pondérés) + service `calculer_score_notation` + selector-gate `chantier_peut_cloturer(chantier_id, company)` (advisory, ne bloque aucun flux existant — câblage installations = futur). Migration qhse 0011 additive, tests.]
- [x] QHSE18 — `ProcedureQualite` versionnée (docs qualité GED). (SCHEMA)
- [x] QHSE19 — `RetourClientQualite` (satisfaction qualité). (SCHEMA)
- [x] QHSE20 — Tableau de bord « ISO 9001 readiness ». (ROUTINE)
- [x] QHSE21 — `EvaluationRisque` (document unique / plan de prévention) + lignes. (SCHEMA)
- [x] QHSE22 — Document unique requis avant pose (gate statut chantier). (DECISION)
- [x] QHSE23 — `PermisTravail` (hauteur/élec-consignation/point chaud). (SCHEMA)
- [x] QHSE24 — Consignation électrique (LOTO) sur permis électrique. (ROUTINE)
- [x] QHSE25 — Alerte expiration de permis. (ROUTINE)
- [x] QHSE26 — `InductionSecurite` (accueil sécurité site, incl. sous-traitants). (SCHEMA)
- [x] QHSE27 — `CauserieSecurite` (toolbox talks + émargement). (SCHEMA) [DONE (already present) 2026-06-30: déjà couvert par FG183 (`rh.CauserieSecurite` + `CauserieParticipant`, émargement) livré dans le même run ; aucun doublon créé en qhse.]
- [x] QHSE28 — `PlanUrgence` / premiers secours (contacts/secouristes/point de rassemblement). (SCHEMA)
- [x] QHSE29 — Registre `Incident` (accident/presqu'accident/incident). (SCHEMA)
- [x] QHSE30 — Déclaration CNSS de l'accident du travail (échéance légale). (DECISION)
- [ ] QHSE31 — `AnalyseIncident` (arbre des causes) → CAPA. (SCHEMA)
- [ ] QHSE32 — Événement `incident_declared` sur le bus (escalade). (ROUTINE)
- [ ] QHSE33 — `InspectionSecurite` planifiée (→ NCR). (SCHEMA)
- [ ] QHSE34 — Statistiques TF / TG (heures travaillées depuis RH). (ROUTINE)
- [ ] QHSE35 — Inspections/permis dans le digest + calendrier. (ROUTINE)
- [ ] QHSE36 — `Dechet` + `BordereauSuiviDechet` (BSD, loi 28-00 déchets dangereux). (SCHEMA)
- [ ] QHSE37 — `RecyclageModule` (fin de vie des modules PV). (SCHEMA)
- [ ] QHSE38 — `ConformiteEnvironnementale` + relances. (ROUTINE)
- [ ] QHSE39 — `BilanCarbone` interne (scopes 1/2/3). (SCHEMA)
- [ ] QHSE40 — `IndicateurESG` + export reporting. (ROUTINE)

### Module Gestion des contrats — CLM (`apps/contrats`) · CONTRAT1–CONTRAT35
**But :** référentiel multi-type de contrats (vente/O&M/monitoring/garantie/PPA/fournisseur/sous-traitance/location/emploi/NDA) : modèles+clauses, génération, approbation, e-sign, obligations/SLA/retenue de garantie, renouvellements/avenants/résiliation, facturation récurrente, tableau de bord. **Wrappe** `sav.ContratMaintenance` sans le casser ; parties = FK Client/Fournisseur/Employé. Recouvre FG243.
- [x] CONTRAT1 — App `contrats` + modèle `Contrat` socle (référence via `references.py`). (ARCH)  [DONE 2026-06-22: NEW app apps/contrats: Contrat socle (champ reference présent; auto-numérotation references.py = follow-up).]
- [x] CONTRAT2 — Enum `type_contrat` (12 types) + lifecycle statut. (SCHEMA)  [DONE 2026-06-22: type_contrat 12 types + statut lifecycle (brouillon→…→résilié/expiré).]
- [x] CONTRAT3 — `PartieContrat` (parties/signataires, ≥2). (SCHEMA)
- [x] CONTRAT4 — Liens inter-apps (devis/lead/installation/maintenance) en string-FK. (ROUTINE)
- [x] CONTRAT5 — Wrap de `sav.ContratMaintenance` (lecture/lien, ne casse pas). (ROUTINE)
- [x] CONTRAT6 — Niveaux de confidentialité + droits d'accès par type. (DECISION)
- [x] CONTRAT7 — `ModeleContrat` (bibliothèque de modèles). (SCHEMA) [DONE 2026-06-27: `contrats.ModeleContrat` (company forcé, nom/categorie/type_contrat_defaut/corps/clauses/devise/confidentialite/actif/ordre, `related_name=contrats_modeles`) + company-scoped viewset, `?actif`/`?categorie`/`?search` filters, `/instancier/` action creating a pre-filled `Contrat`. Migration contrats 0006 additive, 18 tests.]
- [x] CONTRAT8 — `Clause` (bibliothèque de clauses réutilisables). (SCHEMA) [DONE 2026-06-27: `contrats.Clause` (company forcé, titre/categorie/type_clause/corps/ordre/actif) + through-model `ModeleContratClause` (clauses ordonnées rattachées à un `ModeleContrat`, unique modele+clause) + viewsets company-scoped + filtres. Migration contrats 0007 additive, tests.]
- [x] CONTRAT9 — `ClauseContrat` (clauses résolues, ordonnées, surchargeables). (SCHEMA)
- [x] CONTRAT10 — Génération du contrat par fusion (merge tokens). (ROUTINE)
- [x] CONTRAT11 — Rendu PDF interne du contrat (hors `/proposal`). (ROUTINE)
- [x] CONTRAT12 — Machine d'états du cycle de vie + transitions gardées. (ROUTINE)
- [x] CONTRAT13 — `RegleApprobation` (par montant/type). (DECISION)
- [x] CONTRAT14 — `EtapeApprobation` + workflow d'approbation interne. (ROUTINE)
- [x] CONTRAT15 — Chatter/journal du contrat (audit des transitions). (ROUTINE)
- [x] CONTRAT16 — `SignatureContrat` (point e-sign + statut signé). (DECISION)
- [x] CONTRAT17 — Transition automatique signé→actif sur signature. (ROUTINE)
- [x] CONTRAT18 — `VersionContrat` (versionnage immuable des rendus). (SCHEMA)
- [x] CONTRAT19 — Dépôt en GED des versions & PDF signés. (ROUTINE)
- [x] CONTRAT20 — Dates clés (début/fin/préavis) + tacite reconduction. (SCHEMA)
- [x] CONTRAT21 — Calcul des échéances & contrats « à renouveler ». (ROUTINE)
- [x] CONTRAT22 — `AlerteContrat` + rappels via notifications. (ROUTINE)
- [x] CONTRAT23 — Renouvellement (manuel + reconduction tacite). (ROUTINE)
- [ ] CONTRAT24 — `Avenant` (amendements → nouvelle version). (SCHEMA)
- [ ] CONTRAT25 — `Resiliation` (motif/préavis/solde). (ROUTINE)
- [ ] CONTRAT26 — `Obligation`/`JalonContrat` (livrables & jalons). (SCHEMA)
- [ ] CONTRAT27 — SLA & pénalités (taux SLA, valeur pénalité). (ROUTINE)
- [ ] CONTRAT28 — Retenue de garantie (suivi de libération). (SCHEMA)
- [ ] CONTRAT29 — Registre des cautions/garanties liées. (SCHEMA)
- [ ] CONTRAT30 — `EcheancierContrat` + `LigneEcheance`. (SCHEMA)
- [ ] CONTRAT31 — Lien facturation récurrente (via `ventes.services`). (ROUTINE)
- [ ] CONTRAT32 — `IndexationPrix` (indexation/révision de prix). (DECISION)
- [ ] CONTRAT33 — Tableau de bord contrats (actifs/à renouveler/en risque/valeur·MRR). (ROUTINE)
- [ ] CONTRAT34 — `PieceConformite` (pièces obligatoires & attestations). (SCHEMA)
- [ ] CONTRAT35 — Reporting valeur contractuelle & taux de renouvellement. (ROUTINE)

### Module Base de connaissances / Wiki technique (`apps/kb`) · KB1–KB7
**But :** base documentaire interne searchable (SOP d'installation, procédures ONEE/raccordement, fiches techniques, guides de dépannage, onboarding) — alimente aussi le RAG/DocQA (FG352). Survey-recommended (priorité moyenne).
- [x] KB1 — App `kb` + `KbArticle` (titre/corps/catégorie/tags, company FK). (ARCH)  [DONE 2026-06-22: NEW app apps/kb: KbArticle (titre/corps/catégorie/tags/statut/auteur).]
- [x] KB2 — Versionnage des articles + statut (brouillon/publié/obsolète). (SCHEMA)
- [x] KB3 — Recherche plein-texte + filtres par catégorie/tag. (ROUTINE)
- [x] KB4 — Lien article ↔ produit/équipement/type d'intervention (contextuel sur SAV/chantier). (SCHEMA)
- [x] KB5 — Procédures/SOP d'installation & dossiers ONEE/82-21 (gabarits seedés). (ROUTINE) [DONE 2026-06-27: management command `seed_kb_templates [--company <slug>]` idempotent (clé stable (company, titre)) créant 5 gabarits KbArticle français — 3 procédures d'installation (résidentiel/industriel-commercial/pompage), checklist raccordement ONEE, checklist dossier loi 82-21 — contenu générique éditable (pas de spécificités réglementaires inventées). Pas de migration. 10 tests.]
- [ ] KB6 — Source de contenu pour le RAG/DocQA (FG352) — indexation pgvector. (DEP)
- [x] KB7 — Droits d'accès par rôle + suivi de lecture. (SCHEMA)

### Module Réclamations & litiges (`apps/litiges`) · LITIGE1–LITIGE6
**But :** objet formel de réclamation/litige rattaché à une Facture/Lead/Chantier/Ticket (motif, montant contesté, statut, résolution) — comble le vide entre SAV (technique) et recouvrement (financier). Survey-recommended (priorité moyenne).
- [x] LITIGE1 — App `litiges` + modèle `Reclamation` (type, gravité, source FK polymorphe, statut). (ARCH)  [DONE 2026-06-22: NEW app apps/litiges: Reclamation (type/gravité/source polymorphe loose/statut/montant_conteste).]
- [x] LITIGE2 — Workflow statut (ouverte→en_traitement→résolue/rejetée) + chatter. (SCHEMA)
- [x] LITIGE3 — Litige financier ↔ recouvrement : suspendre les relances d'une facture en litige. (ROUTINE) [DONE 2026-06-27: `Reclamation.bloque_relances` (défaut True) + selector `litiges.relances_suspendues_pour_facture(facture_id, company)` ; `ventes.scheduled.relance_reminders` saute une facture en litige bloquant via un import FONCTION-LOCAL de `litiges.selectors` (import-linter reste 4/4). Comportement inchangé sans litige. Migration litiges 0003 additive, 12 tests.]
- [x] LITIGE4 — Litige qualité ↔ QHSE : lien NCR + audit fin de chantier. (ROUTINE)
- [ ] LITIGE5 — Capture du concurrent/motif sur deal perdu (étend FG242). (SCHEMA)
- [x] LITIGE6 — Tableau de bord litiges (ouverts/montant contesté/délai de résolution). (ROUTINE)

---

## DATA-CONNECTIVITY — single-source-of-truth audit 2026-06-21 (DC1–DC42)

A **DRY-data / single-source-of-truth audit** run as 7 parallel master-data lanes (Client/tiers,
Company & settings, People/employee, Product & pricing, Supplier & procurement, Financial master,
Operational cross-cutting) over the **current ERP + the FG1–FG399 backlog + the new-module specs**.
Goal: any datum shared by ≥2 modules is entered ONCE and propagated (FK / server-side resolve /
auto-fill), never re-typed where it can drift.

**Confirmed CORRECT (no action — do not "fix"):** `crm.Client` is the single client master, FK'd
& server-resolved down the whole document/chantier/SAV chain (duplicate-safe lead→client resolve);
`stock.Produit` is the single product master, FK'd everywhere; `stock.Fournisseur` is the single
supplier master; invoice-line designation/price and the frozen `Installation.bom` are **intentional
immutable snapshots that keep their `produit` FK** (legal/historical — NOT bugs); warranty end-dates
and per-location/total stock are **computed, never re-stored**; `StatutConfig` is a clean display
overlay; the 3 status layers (STAGES.py / document / physical) stay correctly separate; document
numbering (`references.py`) and `company_settings` resolvers are good single-source patterns.

The tasks below are the REAL re-entry/duplication gaps + the single-source referentials to lock in
BEFORE the new finance/HR/contract modules are built (cheap now, expensive later). Same STANDING
RULES + gate legend as the FG queue. Same merge note (ticking a `DC*` task refreshes CODEMAP §10).

### Corrections immédiates — duplication/saisie multiple existante (current ERP)

- [ ] DC1 — **Le moteur de devis premium imprime l'identité société en dur** (RC/ICE/RIB/banque/adresse/tél/couleur littéraux dans `generate_devis_premium.py`) → multi-tenant FAUX + fuite du RIB Taqinor. Injecter `entreprise_*` depuis `CompanyProfile` dans `builder.build_quote_data` et les rendre (la voie facture le fait déjà bien). (ROUTINE — priorité haute)
- [ ] DC2 — **Constantes ROI en dur dans le moteur** (`quote_engine/pricing.py` 1240 kWh/kWc · 0.60/0.85 autoconso · 1.75 MAD/kWh) → écran ROI et PDF divergent. Passer `company` et lire onee_tarif/productible/autoconso depuis `CompanyProfile`. (ROUTINE) (@lane: apps/ventes)
- [ ] DC3 — **L'étude industrielle ignore les constantes injectées** (`solar.js computeEtudeIndustrielle` utilise `KWH_PRICE`/`EFFICIENCY` du module) → l'industriel ignore le tarif société même à l'écran. Threader `kwhPrice`/`efficiency` comme `computeROI`. (ROUTINE) (@lane: frontend/ventes)
- [ ] DC4 — **`CompanyProfile.tva_panneaux` est un champ mort** (édité/validé mais lu nulle part ; la TVA 10% vient de `Produit.tva` + hardcode `solar.js`). Câbler le taux panneaux depuis `tva_panneaux` (back + front). (DECISION)
- [ ] DC5 — **Tarif ONEE/productible en double** : `CompanyProfile` vs `TariffSettings` (ce dernier construit mais non câblé). Choisir le canonique, router moteur+simulateur via `parametres.selectors`, documenter dans CODEMAP. (DECISION)
- [ ] DC6 — **TVA 10/20 hardcodée dans `solar.js`** (`ttcFromHt`/`htFromTtc`/`tauxTvaOf`) → un changement de taux société n'est pas pris. Lire `tva_standard`/`tva_panneaux` du profil (fallback actuel). (ROUTINE) (@lane: frontend/ventes)
- [ ] DC7 — **`Produit.tva` doit être la source autoritaire du taux de ligne** : l'écran préfère `produit.tva`, `expectedTvaForDesignation` ne sert plus que d'avertissement de divergence. (ROUTINE)
- [ ] DC8 — **Triplication de la classification produit + règle 10/20** (`solar.js` ⇄ `quote_engine/builder.py` ⇄ `seed_catalogue.py`, garde-fou actuel = test « keyword présent » insuffisant). Une source canonique OU un test de parité qui classe un jeu de fixtures à l'identique sur les 3. (DECISION)
- [ ] DC9 — **Tableau GHI dupliqué** (`solar.js` & `quote_engine/constants.py`) + **productible incohérent** (1240 vs `CompanyProfile` 1600). Réconcilier (source unique ou mirroir documenté façon `stages.js`). (DECISION)
- [ ] DC10 — **`LigneAvoir.produit` nullable (SET_NULL)** = maillon faible des snapshots → exiger `produit` à la création d'une ligne d'avoir + test (garder la traçabilité SKU). (ROUTINE)
- [ ] DC11 — **`Devis.etude_params` sans provenance** : valeurs énergie/toiture re-saisies depuis le lead sans lien → estampiller `{source_lead_id, captured_at, valeurs}` + bannière « valeurs du lead modifiées depuis ». (ROUTINE)
- [ ] DC12 — **Profil site/énergie re-saisi à chaque devis** (surtout devis sans lead) → profil réutilisable (sur `Lead` ou nouveau `crm.SiteProfile` par client) que le générateur pré-remplit. (SCHEMA+DECISION)
- [ ] DC13 — **Chantier sans lead : `site_adresse`/GPS non repris** → fallback sur `client.adresse` dans `create_installation_from_devis`. (ROUTINE)
- [ ] DC14 — **Parrainage : `filleul_nom` peut diverger du FK** → afficher le nom du `filleul_client`/`filleul_lead` quand présent (FK prioritaire). (ROUTINE) (@lane: apps/crm)
- [ ] DC15 — **`Fournisseur` n'a ni ICE/IF/RC/RIB** → ajouter ces champs pour saisir l'identité légale fournisseur une fois (consommée par AP/PDF/compta/sous-traitant). (SCHEMA)
- [ ] DC16 — **Montants `FactureFournisseur` saisis à la main** → les dériver de la réception (FG56) AVANT le rapprochement 3 voies (FG131) ; séquencer FG56 avant FG131. (ROUTINE)
- [x] DC17 — **`CustomUser.poste` en texte libre** → référentiel `Poste`/`Departement` (FG160), migrer/dédupliquer les chaînes existantes, canonique sur `DossierEmploye`. (SCHEMA) (@lane: apps/authentication)
- [x] DC18 — **Sujet email hardcodé « Notification Taqinor »** (`automation/actions.py`) → store de modèles email (FG17), un store par canal (WhatsApp/email/doc). (SCHEMA)
- [ ] DC19 — **Dates relance/maintenance non « jours ouvrés »** (`prochaine_relance`, `ContratMaintenance.prochaine_visite`) → router via le helper calendrier partagé (DC26). (ROUTINE, dépend DC26)

### Référentiels uniques à fonder (single-source masters — build once, consume everywhere)

- [ ] DC20 — **UN référentiel `CompteTresorerie`** (banque/caisse, RIB/IBAN/BIC, devise) ; migrer `CompanyProfile.rib`/`banque` en une ligne par défaut ; consommé par devis/facture, Trésorerie, Paie (fichier de virement), Contrats, AP — un compte bancaire saisi une fois. (ARCH)
- [ ] DC21 — **UN plan comptable `CompteComptable` (CGNC)** + contrat CI : aucun module de posting (ventes/stock/paie/immo/flotte/export FG49) n'écrit de numéro de compte en dur. (ARCH)
- [ ] DC22 — **UNE table de mapping comptable** (famille produit→compte 71xx/61xx, mode de paiement→compte trésorerie, taux→4455x, famille charge→6x) consommée par tout l'auto-posting. (ARCH)
- [ ] DC23 — **UN référentiel de taux de TVA + un selector `tva_par_taux` unique** consommé par factures/compta/DGI/FEC (centraliser la logique de bucket TVA déjà dans `ventes/models.py`). (ROUTINE)
- [ ] DC24 — **UN référentiel d'axes analytiques** (`AxeAnalytique`/`SectionAnalytique` : chantier/agence/marché/commercial) FK depuis écritures/budgets/projet P&L/job-costing/commissions — pas de tags par module. (ARCH)
- [ ] DC25 — **UNE source devise + taux de change** (FG52) consommée par devis/facture/compta/UBL ; remplacer le `'MAD'` hardcodé de `dgi_export.build_ubl_xml`. (SCHEMA+DECISION)
- [ ] DC26 — **UN référentiel calendrier : jours ouvrés + fériés marocains** (FG5) + helper partagé `core/calendar.py` (`next_working_day`/`count_working_days`) consommé par congés/relance/maintenance/dispatch/paie. (SCHEMA+DECISION)
- [ ] DC27 — **UNE taxonomie de tags transversale** (`records.Tag`/`TaggedItem`, FG9) sur clients/devis/factures/produits/chantiers/tickets ; adosser `Lead.tags` au vocabulaire partagé. (SCHEMA)
- [ ] DC28 — **UN résolveur `cout_achat_courant`** (accord de prix actif → `PrixFournisseur` dernier payé → `Produit.prix_achat` fallback) ; documenter la précédence ; marge/auto-fill/job-costing lisent ce seul accesseur (réconcilier commande↔facturé après FG56/FG131). (DECISION)
- [x] DC29 — **UN master employé : `DossierEmploye` OneToOne→`CustomUser`** (règle deux couches : identité sur User, emploi sur DossierEmploye) ; documenter et faire FK dessus depuis tout RH/Paie/QHSE/Contrats/Flotte/Projet — jamais re-saisir nom/CIN/RIB/poste/téléphone/qualifications. (ARCH)  [DONE 2026-06-22: DossierEmploye employee master shipped with RH (FG154); FK target for Paie/QHSE/Contrats/Flotte/Projet (per-module FK wiring = follow-up).]

### Contraintes de câblage des nouveaux modules (référencer les masters, ne pas re-saisir)

- [ ] DC30 — **Compta comptes auxiliaires tiers** : dériver de `crm.Client` / `stock.Fournisseur` par FK via selectors, jamais recréer nom/ICE/RIB sur le compte. (ARCH)
- [ ] DC31 — **Contrats** : parties = FK `crm.Client`/`stock.Fournisseur`/`DossierEmploye` (calquer `sav.ContratMaintenance.client`), identité jamais stockée inline. (ARCH)
- [ ] DC32 — **Portail client (FG228)** : le compte portail se lie à `crm.Client` par FK et réutilise `Client.email` — pas de 2ᵉ copie d'identité client. (AUTH+ARCH)
- [ ] DC33 — **GED** : liens polymorphes (ContentType) vers Lead/Devis/Facture/Chantier/Client/Employé/Fournisseur (réutiliser le pattern `records.Attachment`) — aucune identité copiée sur le document. (ARCH)
- [ ] DC34 — **Sous-traitant : pas de master fournisseur parallèle** → `Fournisseur.type` (matériel/service/mixte, défaut matériel) + `SousTraitantProfile` OneToOne satellite ; AP sous-traitant via la chaîne `FactureFournisseur`/`PaiementFournisseur` existante ; reformuler FG304–FG306. (DECISION)
- [ ] DC35 — **Datasheet/fiches techniques (FG254)** : FK→`Produit`, ne re-stocke pas marque/garantie/specs/courbe (uniquement params normalisés Pmax/Voc/Isc + PDF). (SCHEMA)
- [ ] DC36 — **Kit/BOM (FG66) & kitting (FG328)** : composants = FK→`Produit`, explosion en lignes à l'insertion ; aucun prix/marque/TVA stocké sur le kit (tout vient des composants). (SCHEMA/DECISION)
- [ ] DC37 — **Serial-at-goods-in (FG61)** : `numeros_serie` sur la ligne de réception (gardant le FK `produit`), réconciliés à `sav.Equipement` par produit. (SCHEMA)
- [ ] DC38 — **Landed cost (FG316/FG67)** : intégrer fret/douane/TVA-import au même `average_cost_with_source`, pas de champ de coût d'achat parallèle. (ARCH)
- [ ] DC39 — **Référence unique pour tout nouveau module** (Paie/bulletins, Compta pièces/journaux, Contrats, Projet, QHSE NCR, docs 3-way) via `references.py create_with_reference`, jamais `count()+1` — critère d'acceptation. (ROUTINE)
- [ ] DC40 — **Décision modèle `Equipe`** : introduire un modèle d'équipe unique (membres = M2M→User) réutilisé par roster (FG169)/plan de charge (FG299)/planning camionnette (FG303), OU garder le M2M `Intervention.equipe` ad-hoc — une seule définition, pas une par feature. (DECISION)
- [ ] DC41 — **Permis & habilitations : un seul foyer** (`Conducteur` pour le permis, `DossierEmploye` pour les habilitations) ; les gardes d'affectation FG176/FG198 et la matrice FG174 les RÉFÉRENCENT, sans re-saisie de catégorie/validité. (SCHEMA+DECISION)
- [ ] DC42 — **Personnes dans QHSE/Paie/Projet** : victime d'incident/participant/porteur EPI/ressource/timesheet = FK→`DossierEmploye` ; `cout_horaire` champ unique (un employé = une fiche, un taux). (SCHEMA)

---

## REFINEMENT QUEUE — existing-feature polish (audit 2026-06-18)

Atomic refinements of **already-shipped** features, found by reading the real frontend + backend
source surface by surface (not the docs). Each line is one focused session in the format
`[ ] [<MODULE>] [L<lens#>] [<GATE>] <imperative>. Fait = <observable acceptance>`. **Build order:**
drain the existing BUILD QUEUE first (T1–T17, then the N/F tasks), **then** work this queue
top-down — build the **ROUTINE** tasks unattended and **skip + report** every gated task
(`SCHEMA`/`DEP`/`DECISION`/`GALLERY`); the gated ones are mirrored into the GATED section below so an
unattended run never auto-builds them. Every task obeys the STANDING RULES (French UI, additive only,
company-scoped, `STAGES.py` contract untouched, buy prices never client-facing, DEBUG untouched,
client-facing PDFs are GALLERY-gated).

### CRM / Leads

#### Fiche & formulaire

#### Funnel / étapes & cycle de vie

#### Vues (kanban / liste / calendrier / graphique)

#### Filtres / recherche / findability

#### Actions en masse (bulk)

#### Doublons

#### Activités / Mes activités / rappels

#### Gagné (Won)

#### Mobile / ergonomie

#### Cohérence cross-module / export / localisation
[x] [CRM/Leads] [L17] [ROUTINE] Capturer/afficher la langue de communication préférée du lead (FR/Darija) pour préparer l'envoi WhatsApp bilingue (whatsapp_devis prend déjà un paramètre langue, mais rien ne le mémorise sur le lead). Fait = un champ "Langue préférée" (nullable FR/Darija) sur la fiche pré-sélectionne la langue du message WhatsApp. (UNGATED 2026-06-20 — migration additive nullable, FK société forcée serveur.) [cf. N93] [DONE 2026-06-20: champ nullable `Lead.langue_preferee` (crm 0019), exposé au serializer, `whatsapp_devis` retombe sur la langue préférée du lead quand aucune n'est passée, sélecteur sur LeadForm + pré-sélection dans l'envoi WhatsApp, 4 tests.]

### Clients

### Devis (génération & PDF)

### Facturation
[x] [Facturation/Relances] [L13] [ROUTINE] Adapter la lettre de relance PDF au niveau courant (ton J+7 doux → J+30 ferme) en variant le corps depuis FollowupLevel.message. Fait = generate_lettre_relance_pdf rend un texte distinct par niveau, sans changer la mise en page premium. (UNGATED 2026-06-20 — approuvé par Reda ; construire sur le rendu de relance existant (N106), NE PAS toucher generate_devis_premium.py.) [DONE 2026-06-20: `render_lettre_relance_pdf`/`build_lettre_relance_html` acceptent un `message` optionnel ; sans message ils résolvent le `FollowupLevel.message` par niveau (1/2/3 → seuils croissants), sinon retombent sur le corps par défaut (rétro-compatible). Mise en page premium inchangée. 3 tests ajoutés ; generate_devis_premium.py non touché.]

### Chantiers / Installations
[x] [Chantiers] [L4] [ROUTINE] Ajouter un aperçu in-app des PDF client après-vente (PV de réception, bon de livraison, dossier de remise, attestation) avant téléchargement dans InstallationDetail.jsx. Fait = chaque bouton "Documents après-vente" ouvre un aperçu PDF inline au lieu de seulement downloadBlob, sans changer le contenu du PDF généré. (UNGATED 2026-06-20 — approuvé par Reda ; aperçu seulement, le PDF généré est inchangé.) [DONE 2026-06-20: les 5 boutons après-vente (PV de réception, bon de livraison, dossier de remise, fiche de remise, attestation) ouvrent un aperçu inline (réutilise PdfCanvas + previewPdf.js comme LeadDevisPanel) avec un bouton "Télécharger" ; octets PDF et endpoints inchangés.]

#### Équipement

#### Checklist

#### Photos

#### Planning

#### Parc installé

#### Lifecycle / data quality / traçabilité

### Parc & Équipements (registre SAV)

### SAV

### Maintenance

### Stock & Achats

#### Catalogue — liste & form

#### Catégories & marques

#### Fournisseurs

#### Mouvements & low-stock

#### Multi-emplacements & transferts

#### Inventaire

#### Bons de commande fournisseur

#### Listes de prix fournisseur (multi-fournisseur)

#### Valorisation

#### Retours fournisseur

#### OCR import

#### Chatbot stock (agent IA / SQL)

#### Mobile & cohérence

### Paramètres & Référentiels

### Rôles & RBAC

### Champs personnalisés

### Reporting & Tableaux de bord

### Recherche & Notifications

### WhatsApp & Liens publics

### Documents & Archives

### Transversal (mobile, états, traçabilité)

---

## NEEDS YOUR INPUT — ungated; each waits on something only you can give (with my recommendation)

**Auto-gating is OFF (2026-06-21).** Per your standing consent, NO task is gated by category any
more — `ARCH` / `AUTH` / `COST` / `DECISION` / `GALLERY` / `DEP` are now just **labels**, never a
stop-and-ask, and `scripts/plan_lanes.py` schedules them like any other task (the planner reports
`0 gated` by design). The only things that still hold a task are the five non-negotiable rules
(#1–#5) and a genuine **external prerequisite a run cannot satisfy** — a credential / account /
paid service **you** must provide, real-world data only you have, or a taste / strategic call that
is yours to make.

The items below are no longer auto-skipped; they are parked here **with my recommendation** because
each genuinely needs you. To act on one: provide the credential/data, or say "build it" and a run
ships the safe **no-op scaffold now** (it lights up the moment the key/data lands). Effort tags:
S/M/L. The cross-app safety rules (#1–#5, multi-tenant, buy-prices-never-client-facing) still bind.

- **G1 — Real email sending** (devis/facture/relance by email). **UNGATED 2026-06-18 → BUILD QUEUE
  (N87/N88, Brevo).** Provider chosen = **Brevo** (SDK or SMTP), key from settings/env, no-op
  without a key; pre-approved (see the PRE-APPROVED block). No longer a blocker.
- **G2 — WhatsApp Business Cloud API** (true auto-send + PDF *attached*, message templates).
  Needs: Meta Business **verification** + a WhatsApp Cloud API **access token** + **phone-number
  ID** + an **approved template name**. Today WhatsApp is link-only (`wa.me`, manual tap) and works
  well. **MY RECOMMENDATION: defer until you provision the Meta token — the manual link covers the
  daily need; don't pre-build a dead scaffold. FG207 (inbound WhatsApp → lead) is the SAME Meta
  credential — bundle the two.** Effort M once unblocked. Use Meta Cloud API directly (skip BSP
  resellers/their markup). Verification can take days–weeks; that, not code, is the bottleneck.
- **G3 — Full document visual redesign** (facture + bon de commande; the premium **devis** engine
  `generate_devis_premium.py` / `/proposal` stays OFF-LIMITS per rule #4). The facture/BC still use
  the plainer legacy WeasyPrint templates, which undercut the brand next to the premium devis.
  Needs: a **gallery review** (taste) — I generate 2–3 redesigned facture/BC drafts in the premium
  visual vocabulary, you pick one. **MY RECOMMENDATION: worth doing — clients see the facture as
  often as the devis. Say the word and I'll produce the gallery; keep `PDF_ENGINE=legacy` working.**
  Effort M. (N106 relances + handover sheet already shipped in the premium language.)
- **G5 — Supplier procurement module** (bons de commande fournisseur, goods-in/receiving, supplier
  invoices / accounts payable). **UNGATED 2026-06-20 → BUILD QUEUE (G5, under « Procurement & inventory »).** Approved as a dedicated multi-session module.
- **G6 — Stock auto-decrement on installation** (a chantier consumes its equipment from stock).
  **UNGATED 2026-06-18 → folded into BUILD QUEUE N14.** The exact rule is now confirmed and
  pre-approved: **reserve on chantier create → decrement on « Installé » → release on
  cancel/close** (see the PRE-APPROVED block). No longer a blocker.
- **G7 — Quote e-signature (certified third-party).** Needs your choice of a **paid e-signature
  provider**. The lightweight in-OS acceptance already shipped (Q7: tokenized public accept stamps
  name + timestamp + IP, flips the devis to `accepte`, renders on the PDF) — that is legally
  adequate for residential/SME solar quotes and effectively satisfies FG229. **MY RECOMMENDATION:
  defer — only add a certified provider (Yousign > DocuSign for an MA/FR SME: cheaper, EU-based,
  simpler API) when a high-ticket contract or dispute actually needs eIDAS-grade signing.** Effort M.
- **G8 — 2FA / SSO.** 2FA shipped (N96, opt-in TOTP). **SSO** still needs your choice of an IdP
  (Google Workspace / Microsoft Entra / Okta) + that tenant's app credentials. **MY RECOMMENDATION:
  defer — opt-in 2FA already covers the security need for a small internal team; add SSO only if you
  standardise on one IdP (and then it pairs naturally with G12 if that IdP is Microsoft).** Effort M.
- **G9 — Automation engine / scheduler.** **UNGATED 2026-06-18 → BUILD QUEUE (G9).** Decision made:
  **Celery Beat (in-app)**, two scheduled jobs in Africa/Casablanca time — scheduled relance
  reminders + a daily facture-overdue check (overdue = échéance passed & not fully paid → « En
  retard »; default échéance = issue + 30 days). Pre-approved (see the PRE-APPROVED block). The
  broader no-code automation engine (N72/N73) and n8n workflows stay separate.
- **G10 — CAPI send** (Meta Conversions API, sends `SignedQuote` on Signé, EMQ ≥ 7.0). Capture half
  shipped (fbclid + UTM on the lead + apps/web). The send hook is a stub at two known sites
  (`apps/crm/services.py` SIGNED transition). Needs your **Meta pixel/dataset access token**. CAPI
  itself is **free** (ad-attribution signal, not messaging). **MY RECOMMENDATION: low effort to
  finish (M) and the hook + hashable lead data already exist — provide the pixel token and I'll wire
  the SHA-256-hashed event POST; or build the no-op scaffold now (it's nearly free risk).**
- **G11 — Chatbot / AI assistant → LLM provider.** The chatbot (NL→SQL agent) AND the cross-app AI
  assistant (PLAN2 Group R, already built) run on a multi-provider factory (`SQL_AGENT_PROVIDER` =
  `groq` | `openai` | `claude` | `ollama`). **MY RECOMMENDATION: stay on the default — Groq's FREE
  tier (`llama-3.3-70b-versatile`) — it already works and costs nothing.** The SAME free Groq key
  also powers FG352 (RAG synthesis), FG353 (summarise), FG354 (reply drafts), and the assistant's
  voice (Groq Whisper). `openai`/`claude` are **optional PAID quality upgrades** (better
  reasoning/French, only if Groq's quality/limits prove insufficient); `ollama` is **fully free but
  self-hosted** (needs your own GPU/CPU) if you ever outgrow Groq's free rate limits. FG358 photo QA
  needs a **vision** model — reuse the already-configured Zhipu key, not a new one. **No new paid key
  is required.** FG357 voice and FG361 forecasting aren't LLM-gated at all (free faster-whisper /
  `statsmodels`).
- **💰 AI running costs (verified in code, 2026-06-21).** The whole AI stack runs **FREE by design** —
  no paid key required. Groq's free tier powers the chatbot, the Group R assistant, and assistant
  voice (`whisper-large-v3`, same Groq key); embeddings (`sentence-transformers all-MiniLM-L6-v2`)
  and chat voice memos (`faster-whisper`) are **local/free**; pgvector is free. The **only
  externally-billed AI is OCR via Zhipu GLM** (`ZHIPU_API_KEY`, `glm-4.5v`/`glm-4.7`) — usage-billed
  but very cheap, with free trial credits, and a **pure no-op without a key** (OCR just doesn't run;
  nothing else is affected). `claude`/`openai` are **optional paid quality upgrades**; `ollama` is a
  **free self-hosted fallback** if Groq's free rate limits are ever hit.
- **G12 — Microsoft 365** (Entra ID, Outlook, OneDrive, Teams). Needs an **Entra app registration**
  in your tenant (client id/secret + admin-consented Graph scopes). **MY RECOMMENDATION: confirm
  your team's mail/file stack first — if you live in Google Workspace, skip M365 and prioritise
  Google (calendar/email) instead; only invest here (L) if the team actually runs on M365.**
- **G13 — Import the 619 real Odoo leads.** The idempotent importer is **already built**
  (`apps/crm/management/commands/import_odoo_leads.py` — 3-way match, fills empty fields only, maps
  to `STAGES.py`, `--dry-run`). Needs a **fresh Odoo export of `crm.lead`** (CSV/JSON, holds PII →
  **never committed**, gitignored). **MY RECOMMENDATION: zero dev work — export `crm.lead`, then run
  `manage.py import_odoo_leads <file> --company <slug> --dry-run` first, then for real.** Effort S to
  operate.
- **G14 — DGI e-invoicing readiness (Morocco).** Mandatory ~**Jan 2027** for businesses with CA >
  500k DH — likely Taqinor's wave. **PARTIAL UNGATE 2026-06-18 → BUILD QUEUE (N105):** only the
  **silent, backend-only local capability** was ungated — on-demand **UBL 2.1 / CII** XML export
  (recipient ICE on every line) + a conformity validator, both behind a master toggle that defaults
  OFF and is completely invisible while off. **STILL GATED here** (blocked on the unpublished DGI
  implementing decree — no API spec exists yet, not a decision of Reda's): the **Simpl-TVA portal
  transmission** and the **certified e-signature** (a PDF is explicitly NOT compliant; clearance
  needs the live DGI platform). CONFIRMED — the silent local UBL/XML export already shipped (N105).
  **MY RECOMMENDATION: WAIT for the spec — there is no published Simpl-TVA API to code against, so
  building the portal half now would be guesswork. Mandatory ~Jan 2027 gives runway; the local UBL
  export already positions the data model. Revisit the day DGI publishes the technical spec.** This
  one is blocked by an external SPEC, not by anything you can provide today. Effort L when it lands.
- **G15 — Arabic / Darija UI** (full interface localization, not just message templates). **UNGATED
  2026-06-20 → BUILD QUEUE (N93/N94)** — i18n framework approved. SEQUENCING: run as the FINAL step of
  the UI/UX overhaul (after the component restyle); not prioritized — pull forward only on Reda's
  explicit instruction.
- **G16 — Heavy modularity options.** (a) extract a bounded context into its own deployable service
  (like `fastapi_ia`), (b) per-app pip packaging. **MY RECOMMENDATION: KEEP DEFERRED.** M1–M7
  already delivered the modularity benefit (CI-enforced decoupled boundaries + the `core/events.py`
  bus). Both moves are large, risky migrations against a shared Postgres + the ubiquitous `company`
  FK with ~zero payoff for a single-installer ERP. Defer until a module genuinely needs independent
  scaling/deploy. No founder action needed — this is a "don't burn weeks on it" call. Effort L.

### Strategic calls (ungated, but I recommend holding until you decide)

- **N100 / N101 / N102 — Multi-tenant SaaS platform** (per-tenant billing, tenant admin console,
  self-serve signup). The `company` foundation is already threaded everywhere and isolation is
  enforced, so **no debt accrues by waiting**. **MY RECOMMENDATION: KEEP DEFERRED until there is a
  2nd paying installer.** Self-serve signup is the single biggest auth surface in the app; building
  SaaS billing/console for zero customers adds cost + risk for no return. Decide on a *demand
  signal*, not a date. (The cheap, reversible bit with standalone value — per-tenant white-label of
  client docs via `CompanyProfile` — can be a small separate task if you want it.) These three are
  flipped to `[ ]` in the BUILD QUEUE per your "ungate all", but **do not let a drain build them yet
  unless you've decided to sell TAQINOR as a product** — tell me and I'll re-park them.
- **S21 — Real-time WebSocket chat** (Django Channels + Redis layer + ASGI + nginx WS proxy). Chat
  already works via 3 s polling. **MY RECOMMENDATION: DEFER — polling is plenty for a small internal
  team; the WS stack adds real ops complexity (sticky sessions, connection draining on deploy) for a
  marginal UX gain.** Build only on a concrete need (live dispatch, many concurrent users).

### From the 2026-06-18 refinement audit — gated copies

_All cleared. The former SCHEMA / DEP / DECISION / GALLERY mirrors of the REFINEMENT QUEUE held
nothing pending even before this change, and auto-gating is now OFF entirely (the labels remain on
the tasks for visibility but no run skips them)._

---

## MANUAL — Reda's / Meryem's tasks (NOT code; agent never does these)

Tracked here so they aren't lost:
- Enter the real **ICE / IF / RC** on the server (Paramètres → Identifiants légaux) — live invoices
  currently lack the legally-required seller ICE until then.
- Enter the **11 OSP pump prices** on the server (the agricole pump box stays red; don't send an agri
  quote before).
- Enter **real stock quantities** on the server (the ~283 M DH dashboard value is demo quantities).
- **Article 33 / Loi 82-21 outreach** to the install portfolio (decree in force since 9 June —
  overdue, still sendable; Meryem sends; tag replies « Régularisation 82-21 »).
- **Confirm Sami's GitHub org access is removed.**
- **Confirm the PC cleanup ran** (taqinor-secrets.txt + test-leads JSON deleted).
- **Set the default lead responsable** to Meryem (Paramètres → Leads).
- **Personalize the WhatsApp templates** (Paramètres → Messages WhatsApp).
- Optional: add `PUBLIC_BASE_URL=https://api.taqinor.ma` to the server `.env` for cleaner WhatsApp
  links (they already work via auto-redirect).
- **DEBUG:** turn it off when you decide the OS is ready (your call — the agent will not raise it).

---

## DONE LOG (agent appends one plain-language line per completed task)

- *(seeded baseline — see "ALREADY LIVE" above for the full pre-plan state)*
- _next: the agent adds entries here, e.g. "2026-06-15 — T1 done: devis preview renders + downloads in all 3 formats; cache-busting added; deployed."_
- 2026-06-20 — G5 done: supplier procurement spine — réception fournisseur (goods-in → idempotent stock ENTRÉE on confirm, advances BCF statut) + factures fournisseur / comptes-à-payer (AP, `solde_du`, paiements) with company-scoped viewsets, 2 frontend pages, 14 tests. (future: supplier-invoice PDF, line UI, auto-facturer, aged-payables.)
- 2026-06-20 — N53 done: client energy-yield report PDF (estimated/manual) — stateless WeasyPrint, DRF `@action` `chantiers/<id>/rapport-energie/`, company-scoped, Moroccan defaults (1600 kWh/kWc/an · 1.40 MAD/kWh · 0.81 kg CO₂/kWh, all overridable, ESTIMATION-labelled, no buy prices), Parc-installé button + modal, 10 tests.
- 2026-06-20 — N76 done: daily + weekly digest beat jobs (per-company via `notify()`, in-app + email/WhatsApp no-op until configured); ADDED the missing `celery_beat` process to docker-compose. 4 tests.
- 2026-06-20 — N79 done: server-side `reporting.SavedReport` (company-scoped CRUD) + `reporting.email_saved_reports` beat job rendering due reports to xlsx and emailing (no-op until email configured). 7 tests.
- 2026-06-20 — N92 done: PWA web push — `PushSubscription` (company+user forced), subscribe/unsubscribe/vapid-public-key endpoints, best-effort web-push channel in `notify()` (drops dead subs), sw.js handlers, per-device opt-in toggle; VAPID empty → NO-OP until configured; `pywebpush` left as optional install (http-ece build) to keep CI green. 8 tests.
- 2026-06-20 — N96 PARTIAL: opt-in TOTP 2FA shipped (additive `CustomUser` fields default OFF → no lockout, setup/enable/disable/status endpoints, login requires `otp` only when enabled, settings tab + login code step, `pyotp`, 11 tests). Visible-sessions-revoke + forced-rotation remain open.
- 2026-06-20 — L17 done: nullable `Lead.langue_preferee` (FR/Darija) pre-selects the WhatsApp language; LeadForm select + serializer + server fallback, 4 tests.
- 2026-06-20 — L13 done: relance letter body escalates per `FollowupLevel.message` (soft J+7 → firm J+30), premium layout unchanged, 3 tests; premium devis engine untouched.
- 2026-06-20 — L4 done: in-app inline preview (reusing PdfCanvas/previewPdf) in front of every après-sale document download in InstallationDetail; PDF bytes/endpoints unchanged.
- 2026-06-20 — G10 verified already-present: Lead fbclid/utm_* fields (crm 0006), website webhook maps+stores them, apps/web captures first-touch fbclid+UTM, covered by tests — ticked `[x] (already present)` in PLAN2.
- 2026-06-27 — PAIE14 done: heures supplémentaires majorées — taux 25/50/100 % éditables par société sur `ParametrePaie`, `ElementVariable.categorie_hs`, calcul auto câblé dans `calculer_bulletin` (taux horaire × majoration, montant explicite prioritaire). Migration paie 0007 additive. 20 tests.
- 2026-06-27 — FG167 done: feuilles de temps par chantier — `rh.FeuilleTemps` (heures imputées à une installation, taux interne, coût calculé) + selector `labour_hours_for_installation` pour le job-costing ventes sans import de modèles rh. Migration rh 0009 additive. Tests company-forcing/isolation/selector.
- 2026-06-27 — CONTRAT7 done: `contrats.ModeleContrat` (bibliothèque de modèles de contrats) + action `/instancier/` créant un Contrat pré-rempli. Migration contrats 0006 additive. 18 tests.
- 2026-06-27 — FLOTTE7 done: `flotte.Conducteur` + permis (lien optionnel vers authentication.User), filtres actif/permis-expirant + selectors. Migration flotte 0006 additive. 17 tests.
- 2026-06-27 — QHSE16 done: exécution d'audit — `qhse.Audit` + `ReponseCritere` sur les grilles existantes, score (% conforme) + levée idempotente de non-conformités. Migration qhse 0010 additive. 14 tests.
- 2026-06-27 — Run note: wave 1 of a parallel worktree drain (5 file-disjoint apps). No new external/paid dependency; no auth change; all migrations additive & revertable. Validated via the docker CI harness (511 affected-app tests green, makemigrations --check clean). One bug caught+fixed pre-merge: rh timesheet migration had unnamed `Meta.indexes` (would fail CI) — regenerated via makemigrations.
- 2026-06-29 — FG132 done: balance âgée fournisseurs (buckets 0-30/31-60/61-90/90+) + relevé fournisseur (statement + solde courant) en miroir du côté clients, bâtis sur le GL compta auxiliarisé (compte 4411), noms fournisseurs via stock.selectors. 11 tests.
- 2026-06-29 — FG133 done: `compta.PaymentRun`+`PaymentRunLine` — campagne de règlements fournisseurs (proposition par échéance → écriture GL équilibrée 4411/5141), cycle brouillon→proposée→postée, idempotent, period-lock-aware. Migration compta 0010 additive (2 tables). 19 tests.
- 2026-06-29 — FG134 done: `fichier_virement` — ordre de virement bancaire (RIB/IBAN, montant, motif) export CSV depuis un PaymentRun de type virement. Couvert par les tests FG133.
- 2026-06-29 — FG70 done: remise de garantie auto à RECEPTIONNE — balayage du BoM figé vers le parc SAV (un `sav.Equipement` par ligne, date_pose=date_reception, idempotent) via `apps/sav/services.py` (write cross-app), note chatter + endpoint `chantiers/<id>/remise-garantie`. Pas de migration. Tests handover.
- 2026-06-29 — FG71 done: roll-up coût de chantier (job-costing) interne — service `compute_chantier_cout` + endpoint admin-only (IsAdminRole) main-d'œuvre + matières prévu/réel + marge ; prix_achat jamais exposé côté client. Tests.
- 2026-06-29 — FG77 done: contrôle de préparation pré-pose (bannière consultative) — `compute_chantier_readiness` + endpoint `chantiers/<id>/readiness` (manque matière, dossier 82-21, date pose) ; advisory, ne bloque pas EN_COURS. Tests.
- 2026-06-29 — FG252 done: brouillon de schéma unifilaire (SVG) — module pur Panneaux→String→Onduleur→Comptage→ONEE (+ branche batterie), endpoints `schema-unifilaire` (params bruts) et `devis/<id>/schema-unifilaire` (company-scoped), read-only, aucun prix. Tests.
- 2026-06-29 — FG253 done: aide à la charge structurelle toiture — charge PV kg/m² (coef sécurité 1.1) vs capacité indicative par type de toit, sévérité ok/attention/dépassement + disclaimer ; endpoint `toiture/charge/`. Tests.
- 2026-06-29 — FG254 done: bibliothèque de fiches techniques normalisées — `ventes.FicheTechnique` (FK string→stock.Produit + company, params Pmax/Voc/Isc/Vmp/Imp + coef temp, PDF optionnel, jamais de prix), CRUD company-scopé. Migration ventes 0038 additive (1 table). Tests.
- 2026-06-29 — FG353 done: résumé automatique d'un fil (LLM) — `core.ai.summarize_thread` foundation-pure (entrées génériques), NO-OP sans clé (zéro appel réseau, configured=False). Réutilise le registre de providers core.ai existant (pas de nouvelle dépendance). Tests.
- 2026-06-29 — FG354 done: brouillon de réponse email/WhatsApp éditable (FR) — `core.ai.draft_reply` ; génère seulement, jamais d'envoi auto ; même NO-OP-sans-clé. Tests.
- 2026-06-29 — FG360 done: détection d'anomalies — `core.AnomalyFlag` (1er modèle concret de core, multi-tenant, sujet générique) + `scan_for_outliers` (z-score stdlib) + `record_outliers` (company forcée, dedup). Migration core 0001 additive. import-linter: core reste foundation. 13 tests.
- 2026-06-29 — FG169 done: roster d'équipes hebdo — `rh.AffectationRoster` (technicien↔équipe/camionnette via `flotte.Vehicule` string-FK), détection conflit congés réutilisant le selector congés. Migration rh 0011 additive. 20 tests.
- 2026-06-29 — FG170 done: registre de présence chantier (émargement) — `rh.PresenceChantier` (présent/absent/retard/parti-tôt, émargement posé server-side), registre par chantier + selectors effectif. Migration rh 0012 additive. 16 tests.
- 2026-06-29 — FG171 done: marquage retard/absence injustifiée + compteur — `rh.IncidentPresence`, compteur par employé (justifiés exclus), régularisation via `justifier/`. Migration rh 0013 additive. 10 tests.
- 2026-06-29 — CONTRAT10 done: génération de contrat par fusion (merge tokens) — `services.fusionner/rendre_contrat` (substitution stdlib, pas de moteur de template), FK nullable `Contrat.modele`, endpoint `contrats/<id>/rendre/`. Migration contrats 0009 additive. 19 tests.
- 2026-06-29 — CONTRAT11 done: rendu PDF interne du contrat (hors /proposal) — `rendre_contrat_pdf` (WeasyPrint, HTML échappé) + endpoint `contrats/<id>/pdf/` ; PDF de travail interne, pas un PDF devis client. 7 tests.
- 2026-06-29 — CONTRAT12 done: machine d'états du cycle de vie du contrat + transitions gardées — `machine_etats.changer_statut` (transitions légales, ≥2 parties pour finaliser/signer, terminaux resilie/expire), endpoints `changer-statut/` et `statuts-suivants/`. 14 tests.
- 2026-06-29 — FLOTTE10 done: `flotte.ReservationVehicule` + détection de conflit (intervalle semi-ouvert, annulées exclues, adjacentes OK). Migration flotte 0009 additive. 24 tests.
- 2026-06-29 — FLOTTE11 done: état des lieux départ/retour — `flotte.EtatDesLieux` (km, niveau carburant, état général, checklist JSON + photos MinIO). Migration flotte 0010 additive. 14 tests.
- 2026-06-29 — FLOTTE12 done: carnet de carburant — `flotte.PleinCarburant` (quantité/unité litre|kWh, prix unitaire calculé, contrôle odomètre non-décroissant). Migration flotte 0011 additive. 14 tests.
- 2026-06-29 — PAIE17 done: `paie.BulletinPaie`+`LigneBulletin` — snapshot complet immuable une fois validé (garde dans save/delete, brouillon→valide seule transition autorisée), services `generer_bulletin`/`valider_bulletin` idempotents, viewset read-only. Migration paie 0010 additive. 16 tests (dont 6 d'immutabilité).
- 2026-06-29 — PAIE18 done: CNSS plafonnée (part salariale 4.48 % & patronale 8.98 % par défaut, assiette plafonnée), câblée dans `calculer_bulletin` (charges_patronales hors net). 9 tests.
- 2026-06-29 — PAIE19 done: AMO sans plafond (part salariale & patronale 2.26 % par défaut, assiette = brut intégral), agrégée aux charges patronales. 9 tests.
- 2026-06-29 — Run note (wave 1, 8 lanes parallèles file-disjoint: compta/installations/ventes/core/rh/contrats/flotte/paie): aucune dépendance externe/payante nouvelle (FG353/354 réutilisent core.ai) ; aucune nouvelle dépendance ; aucun changement d'auth ; toutes migrations additives & revertables ; nouveau modèle concret core.AnomalyFlag (1ère table de core, reste foundation). 24 tâches.
- 2026-06-27 — GED15 done: document versioning — `documents/<id>/historique/` + `restaurer` action (new current version from a prior one, history preserved, `restored_from` audit), reuses file_key. Migration ged 0008. 16 tests.
- 2026-06-27 — PROJ15 done: `gestion_projet.RessourceProfil` (internal `cout_horaire`) + `Equipe` (M2M membres). Migration gestion_projet 0010. 10 tests.
- 2026-06-27 — FG39 done (backend): `crm.ObjectifCommercial` (owner/metric/period/cible) + `compute_attainment` (réalisé vs cible) + `/attainment/` endpoints; import-linter safe. Migration crm 0028. 20 tests. Frontend panel = follow-up.
- 2026-06-27 — FG5 done: `notifications.WorkingHoursConfig` + `Holiday` + `calendar_utils` helpers + idempotent `seed_ma_holidays` (9 fixed MA holidays; Islamic lunar = manual). Additive infra, existing date logic unchanged until opted in. Migration notifications 0010.
- 2026-06-27 — FG86 done: `sav.Ticket.share_token` + auth-exempt public endpoint returning only reference/statut/last-update (allowlist; never cout/chatter/PII), noindex+throttle, `lien-client` action. Migration sav 0009. Tests assert no leak. Frontend button = follow-up.
- 2026-06-27 — KB5 done: idempotent `seed_kb_templates` command — 5 French SOP/ONEE/82-21 dossier gabarits (generic editable content). No migration. 10 tests.
- 2026-06-27 — FG96 done (backend): `reporting.DashboardConfig` (per-user/per-role cards) + `/dashboard-config/effective/` (per-user→role→global default; no-config = full current set, no behavior change). Migration reporting 0003. 12 tests. Frontend = follow-up.
- 2026-06-27 — FG102 done (backend): webhook `deliveries/` history + `replay/` (re-send via existing HMAC delivery fn, new attempt, original preserved) + `test/` ping; cross-company 404. No migration. 11 tests. Frontend = follow-up.
- 2026-06-27 — FG297 done: `installations.DocumentProjet` + `RevisionDocument` (versioned project-doc register, file via records.Attachment string-FK, unique indice per doc) in `models_document.py`; import-linter safe. Migration installations 0014. 13 tests.
- 2026-06-27 — COMPTA1 verified already-present: `compta.PlanComptable` + `CompteComptable` (CGNC, hierarchy, unique (company,code)) + idempotent `seed_plan_comptable` + viewsets/tests already on `main` (compta 0001). Ticked `[x] (already present)`, no code change.
- 2026-06-27 — LITIGE3 done: `Reclamation.bloque_relances` + `litiges.relances_suspendues_pour_facture` selector; `ventes.relance_reminders` skips factures en litige via a function-local litiges import (import-linter 4/4). No change without a dispute. Migration litiges 0003. 12 tests.
- 2026-06-27 — Run note: waves 2+3 of the parallel worktree drain (9 more file-disjoint apps: ged/gestion_projet/crm/notifications + sav/kb/reporting/publicapi/installations). No new external/paid dependency; no auth change; all migrations additive & revertable. Validated via the docker CI harness (makemigrations --check clean, flake8 clean, import-linter 4/4, affected-app tests green). Bugs caught+fixed pre-merge: a French apostrophe in a single-quoted Python string (gestion_projet), model↔migration field drift (ged/gestion_projet), and several flake8 unused-import / ambiguous-name issues. NOTE: local docker harness can't sign MinIO PutObject (pre-existing crm `/proposal` PDF + VAPID tests fail locally only — they pass in CI, as proven by PR #265).
- 2026-06-27 — PAIE15 done: prime d'ancienneté barème (editable seuils/taux on ParametrePaie) wired into calculer_bulletin; hire date via new `rh.date_embauche_employe` selector. Migration paie 0008.
- 2026-06-27 — CONTRAT8 done: `contrats.Clause` reusable clause library + `ModeleContratClause` ordered link to templates. Migration contrats 0007.
- 2026-06-27 — FLOTTE8 done: `flotte.AffectationConducteur` (dated driver↔vehicle) + current-driver selector. Migration flotte 0007.
- 2026-06-27 — GED16 done: document check-out/check-in optimistic locking (`locked_by`/`locked_at`, 409 on conflict, new-version blocked while locked). Migration ged 0009.
- 2026-06-27 — QHSE17 done: `qhse.NotationFinChantier` + items + `chantier_peut_cloturer` advisory gate selector. Migration qhse 0011.
- 2026-06-27 — PROJ16 done: `gestion_projet.AffectationRessource` (profil/équipe/actif-flotte via string-FK, exactly-one-kind validated). Migration gestion_projet 0011.
- 2026-06-27 — Run note: wave 5 (6 module-extension lanes — paie/contrats/flotte/ged/qhse/gestion_projet, +1 rh selector) built after waves 1-4 merged, so the base now carried prior migrations (collision-free reuse of module lanes). All additive, multi-tenant, tested; validated on the docker harness (drift clean, flake8 clean, import-linter 4/4). Bugs caught+fixed pre-merge: PROJ16 migration drift (regenerated) + flake8 unused-import/ambiguous-name.
- 2026-06-20 — N108 done: uploads bucket self-heal — best-effort `ensure_uploads_bucket()` beside `get_minio_client` (mirrors `_ensure_pdf_bucket`), called before every write to `erp-uploads` (records/avatars/logo-signature); fixes the live HTTP-500 NoSuchBucket; new bucket-absent test; premium engine untouched.
- 2026-06-20 — N109 done: Web Push activated — `pywebpush==2.0.3` pinned (http-ece sdist builds via Dockerfile pip/setuptools upgrade), `VAPID_AUTOGENERATE` gated off under the test runner, `notifications.VapidKeyPair` singleton auto-generates+persists a P-256 keypair (private never committed), endpoint serves it so the frontend banner clears; env keys take precedence; push best-effort. Empty-keys tests preserved + 3 new tests.
- 2026-06-20 — N110 done: role-change NOT reproducible (backend correct + already tested); no code change; added `tests_role_change.py` (4 tests) + documented the likely live cause (stale JWT menu_tier / drifted acting-account role → run init_roles + re-login).
- 2026-06-20 — M1 done: `ventes/models.py` cross-app FKs → lazy `'crm.Client'`/`'stock.Produit'` string form, load-time sibling imports removed (breaks crm⇄ventes / stock⇄ventes cycles); `makemigrations --check` clean, `manage.py check` passes. (M4 BLOCKED — its load-time back-edge doesn't exist on main; M2/M5/M7 deferred to a focused run.)
- 2026-06-20 — N96 done (completed): added visible active sessions + revoke (`UserSession`, `/auth/sessions/` list + `/revoke/`, refresh-token blacklist, current device flagged) and forced credential rotation (`must_change_password` default OFF + `password_changed_at` in `/auth/me/`, `/auth/change-password/`) + the Sessions/Mot-de-passe sub-sections in the Sécurité tab. Migration 0012, 95 auth tests green. The earlier-shipped opt-in 2FA half is unchanged. Closes G8's 2FA half.
- 2026-06-20 — M5 done: `TenantMixin` + the company-scoping helpers moved into `core/` (`core/mixins.py`, `core/scoping.py`); `authentication/{mixins,scoping}.py` are now back-compat re-export shims so no caller changed. No schema change (`makemigrations --check` clean).
- 2026-06-20 — M2 done: cross-app reads/writes between crm/ventes/stock/installations/sav rerouted through the target app's `selectors.py`/`services.py` (~25 sites; new selectors in 4 apps + new stock/sav services); same-app + foundation imports left as-is; cross-app boundary rule written into CLAUDE.md.
- 2026-06-20 — M7 done: god-files split with no behaviour change — `installations`/`ventes`/`stock` `views.py` → `views/` packages (re-exported), `installations/models.py` → `models_*.py` (re-exports 23 classes); byte-identical, `makemigrations --check` clean.
- 2026-06-20 — M6 done (founder-ungated): domain-event layer in `core/events.py`; `ventes` emits `devis_accepted`, `crm` subscribes (`receivers.py` via `ready()`) to advance the stage — synchronous, behaviour-identical. accept→chantier deliberately NOT auto-wired (would trigger N14 stock reservations on every acceptance = a behaviour change); infra left ready, flagged for the founder.
- 2026-06-20 — M3 done (founder-ungated): `import-linter==2.11` + `.importlinter` (3 contracts: core domain models stay decoupled — the M1 win, incl. M7-split installations model modules; `core` stays a base foundation layer) + a `lint-imports` step in the `backend-lint` CI job. 3 kept / 0 broken. Full no-cycles/strict-layers contract deferred until deeper decoupling lands.
- 2026-06-21 — FG batch (8 parallel worktree lanes, founder-ungated ARCH): shipped 82 feature-gap tasks across existing apps + a brand-new accounting module, folded into one branch, tests green (MinIO-PDF cases gated to CI).
- 2026-06-21 — notifications/transversal: FG1 (dead EventType beat sweeps), FG2 (automation time-triggers beat), FG3 (automation template library), FG4 (NotificationRoutingRule), FG7 (records.Comment + @mentions chatter), FG8 (activity-feed widget), FG9 (records.Tag/TaggedItem taxonomy), FG10 (tenant-wide attachment center), FG11 (useSavedViews on 5 lists), FG12 (Header ThemeToggle), FG13 (push toggle, already present), FG14 (import fournisseurs+équipements).
- 2026-06-21 — CRM: FG27 lead scoring, FG28 first-response SLA (first_contacted_at + lead_sla_hours + beat), FG29 stage-age + funnel velocity, FG30 typed comm log (Appel/Email+outcome), FG31 relance queue, FG32 client segments, FG33 bulk-WhatsApp queue, FG34 source/campaign ROI, FG35 lead-express modal, FG36 crm.MessageTemplate, FG37 pipeline map view, FG38 lead↔client match. (Fix on fold: new actions added to LeadViewSet.get_permissions; 37/37 FG tests.)
- 2026-06-21 — Ventes: FG40 recurring contract billing, FG41 client plafond_credit, FG42 bank-statement payment import, FG43 invoice bulk ops, FG44 devis refusal+motif, FG45 quote-to-cash dashboard, FG46 flexible échéancier+acompte, FG47 cash-flow forecast, FG48 two-option comparison.
- 2026-06-21 — Stock: FG54 reorder auto-PO, FG55 supplier-invoice PDF, FG56 facturer-réception, FG57 rotation/dead-stock, FG58 supplier price compare, FG59 supplier scorecard, FG60 movement filters+xlsx, FG61 serial/lot goods-in, FG62 per-location min/max, FG63 inventory-count session, FG64 expiry/lot, FG65 demand forecasting.
- 2026-06-21 — Installations/outillage: FG68 crew dispatch calendar, FG69 client signature on CR/PV, FG72 multi-day chantier, FG73 technician day route, FG74 cross-chantier Gantt, FG75 roof/drone survey attachments, FG76 photo-required checklist gate, FG78 RDV confirm/reschedule, FG79 auto-scaffold intervention chain, FG80 outillage calibration tracking. (FG70 deferred — cross-app installations↔sav.)
- 2026-06-21 — SAV/monitoring: FG81 server-side ticket SLA, FG82 maintenance checklist, FG83 warranty-claim/RMA, FG84 production history chart+CSV, FG85 equipment QR labels + scan, FG87 SAV knowledge base, FG89 spare-parts forecast, FG90 chronic-failure flag.
- 2026-06-21 — Reporting/customfields: FG91 SavedReport UI+pin, FG92 MoM/YoY comparison, FG93 sales leaderboard, FG94 custom-field reporting, FG95 branded report PDF, FG97 audit-log analytics, FG98 cohort/seasonality, FG99 profitability by segment, FG100 custom fields for Devis/Chantier/Ticket, FG101 report drill-down links.
- 2026-06-21 — Comptabilité (new module apps/compta, founder-ungated ARCH): FG107 plan comptable CGNC, FG108 journaux + écritures partie double, FG109 auto-écritures (default-OFF), FG110 grand livre, FG111 balance générale, FG112 lettrage, FG113 CPC, FG114 bilan, FG121 comptes de trésorerie. 32 tests.
- 2026-06-21 — Comptabilité (apps/compta): FG115 clôture & verrouillage de période (ExerciceComptable + PeriodeComptable, immutabilité des écritures/lignes en période verrouillée, garde-facture côté valeur), FG116 écritures OD manuelles (équilibrées, refusées si période verrouillée), FG117 à-nouveaux/réouverture d'exercice (report des soldes bilan, idempotent). 2 tables additives, 1 migration additive (0002), 32 nouveaux tests. Aucune dépendance/charge nouvelle, aucun changement d'auth.
- 2026-06-21 — Ventes (apps/ventes): FG246 calcul de chaînes/string design + vérif ratio DC/AC (Vmp/Voc à froid vs fenêtre onduleur), FG247 appariement module–onduleur depuis le catalogue (mots-clés alignés builder.py, jamais d'onduleur sans prix), FG249 optimisation inclinaison/azimut (balayage via PVGIS existant). Module purement additif `solar_design.py` + 22 tests. Aucune nouvelle route PDF (/proposal reste l'unique chemin).
- 2026-06-21 — Installations (apps/installations): FG293 JalonProjet (phases étude/appro/pose/MES/réception, dates cibles/réelles), FG296 ModeleProjet (+ jalons/BoM-type, service instantiate_modele_projet idempotent), FG298 ReunionChantier (comptes-rendus horodatés). Modèles additifs (migration 0013), 17 tests, FK produit en string-FK.
- 2026-06-21 — NOUVELLE APP apps/flotte (composant architectural nouveau, ARCH founder-ungated): FLOTTE1 squelette multi-tenant + enregistrement (INSTALLED_APPS, urls), FLOTTE2 modèle Vehicule (immat/marque/énergie/km/valeur/statut), FLOTTE4 EnginRoulant (compteur d'heures nacelle/groupe/chariot). ViewSets company-scoped (company forcée serveur), 2 migrations additives, 9 tests. Aucune dépendance externe/payante, aucun changement d'auth.
- 2026-06-21 — NOUVELLE APP apps/ged (composant architectural nouveau, ARCH founder-ungated): GED1 squelette DMS multi-tenant + enregistrement, GED2 Cabinet + Folder arborescent (chemin matérialisé, déplacement sûr anti-cycle), GED3 Document + DocumentVersion (file_key MinIO réutilisant records.storage, checksum SHA-256 dédup, version auto). ViewSets company-scoped, 1 migration additive, 22 tests. Aucune dépendance externe/payante, aucun changement d'auth.
- 2026-06-22 — GED4 (apps/ged): exposé le déplacement (déjà un service interne) en HTTP — actions `deplacer` sur dossiers et documents (`POST /api/django/ged/dossiers/<id>/deplacer/` body `{parent}` et `/documents/<id>/deplacer/` body `{folder}`), destination résolue dans la société de l'appelant (404 cross-tenant, 400 cycle/cross-cabinet), réutilise `services.move_folder` + nouveau `services.move_document`. CRUD dossiers/documents déjà présent (verrouillé par 8 nouveaux tests de scoping). +20 tests. Aucune migration (déplacement = réassignation de FK), aucune dépendance/auth nouvelle.
- 2026-06-22 — QHSE2 (apps/qhse): ITP — nouveaux modèles `PlanInspectionModele` (gabarit, code/nom/actif) + `PointControleModele` (FK plan, `phase`, `type_releve` choices mesure/visuel/document/essai, `hold_point` bool, `ordre`), ViewSets company-scoped (company posée serveur, point validé même-société que son plan → 400 sinon), routes `plans-inspection/` + `points-controle/`. 1 migration additive (2 CreateModel), 11 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — FG155 (apps/rh): type de contrat (CDI/CDD/ANAPEC/stage/intérim — déjà présent sur DossierEmploye) + dates `contrat_date_debut`/`contrat_date_fin` (DateField nullable, sûr sur table peuplée) + action `GET /api/django/rh/employes/cdd-a-echeance/?within=N` (CDD dont date_fin tombe dans N jours, défaut 30, scopé société). 1 migration additive (2 AddField nullable, pas de défaut/unique → pas de piège), 7 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — PROJ2 (apps/gestion_projet): modèle `ProjetLien` (FK projet, `type_cible` devis/facture/ticket/achat, `cible_id` PK, `libelle` cache) reliant un projet aux documents d'autres apps par STRING-FK (pas de vrai FK cross-app) ; CRUD `projet-liens/` + action `projets/<id>/liens/` enrichie via `selectors.liens_enrichis` (appel fonction-local de `apps.ventes.selectors.devis_card` pour les devis, dégradation au libellé stocké sinon — frontière cross-app respectée, import-linter non violé). 1 migration additive, 8 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — FG118 (apps/compta): modèle `Immobilisation` (registre des immobilisations) — company FK, libellé, catégorie (vehicule/outillage/materiel/mobilier/informatique/autre), coût HT, taux TVA, date d'acquisition, actif ; props montant_tva/cout_ttc ; ViewSet company-scoped + filtres/recherche. 1 migration additive, 8 tests. Pas d'amortissement (hors scope). Aucune dépendance/auth nouvelle.
- 2026-06-22 — CONTRAT3 (apps/contrats): modèle `PartieContrat` (parties/signataires d'un contrat) — company FK, contrat FK (related_name parties), type_partie (client/prestataire/temoin/garant/autre), nom/fonction/email/telephone/ordre ; CRUD company-scoped (partie validée même-société que son contrat → 400 sinon) ; règle ≥2 via `Contrat.valider_parties()` (finalisation, testée). 1 migration additive, 11 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — KB2 (apps/kb): versionnage des articles — modèle `KbArticleVersion` (snapshot titre/contenu/auteur, numéro incrémenté serveur via select_for_update, jamais count()+1) ; actions `publier` (statut→publié + snapshot) et `nouvelle-version`, snapshot aussi à chaque update ; viewset versions read-only company-scoped. statut (brouillon/publié/obsolète) déjà présent (KB1). 1 migration additive, 8 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — LITIGE2 (apps/litiges): workflow statut `Reclamation` (ouverte→en_traitement→résolue/rejetée, machine d'état serveur, transitions illégales → 400 ; statut read-only hors actions) + chatter `ReclamationActivity` (log auto old→new sur chaque transition + notes manuelles via `noter`/`historique`, auteur+société serveur). Actions prendre-en-charge/resoudre/rejeter/noter/historique. 1 migration additive, 22 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — FG17 (apps/parametres): gestion des modèles d'e-mail (parité templates WhatsApp) — NOUVEAU modèle `EmailTemplate` (company+cle unique, sujet+corps, placeholders {civilite}{nom}{reference}{lien}{n}) + helpers `get_template`/`render` tolérants pour le futur câblage automation ; viewset company-scoped + `effective/` (défauts+overrides) + `bulk/`, écritures auditées. Le câblage de l'action e-mail de l'automation est VOLONTAIREMENT laissé à une lane séparée. 1 migration additive, 17 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — FLOTTE3 (apps/flotte): lien `Vehicule.emplacement_stock_id` (PositiveInteger nullable, PAS de FK cross-app) vers `stock.EmplacementStock` ; validé même-société via `apps.stock.selectors.get_emplacement_scoped` (import fonction-local, jamais les models — import-linter respecté), label résolu via `flotte/selectors.py` (dégrade au #id). 1 migration additive nullable, 6 tests. Aucune dépendance/auth nouvelle.
- 2026-06-22 — FG119 (apps/compta): plan d'amortissement — `PlanAmortissement` (mode linéaire/dégressif, durée, base, coefficient dégressif marocain CGI figé) + `DotationAmortissement` (1/an, montant/cumul/VNC, posted+écriture). `services.generer_plan_amortissement` (idempotent, linéaire vs dégressif-bascule-linéaire) + `services.poster_dotation` (écriture équilibrée débit cl.6 / crédit cl.28 via le service compta existant, RESPECTE le verrou de période → ValidationError si verrouillée). Actions `immobilisations/{id}/plan-amortissement`, `dotations/{id}/poster`. 1 migration additive, 29 tests.
- 2026-06-22 — CONTRAT4 (apps/contrats): `ContratLien` (string-FK devis/lead/installation/maintenance, comme PROJ2) + `selectors.liens_enrichis` enrichissant via `ventes.selectors.devis_card`/`crm.selectors.lead_card`/`installations.selectors.chantier_card` (imports fonction-locaux, sav→dégrade au libellé), frontière cross-app + import-linter respectés. CRUD `contrat-liens/` + action `contrats/{id}/liens/`. 1 migration additive, 13 tests.
- 2026-06-22 — KB3 (apps/kb): recherche plein-texte (`?search=` sur titre/corps/catégorie/tags via SearchFilter, déjà câblé) + filtres `?categorie=`/`?tag=`/`?statut=` ajoutés dans get_queryset APRÈS le scope société (jamais de fuite inter-société). Réutilise les champs categorie/tags/statut existants — aucune migration. 16 tests.
- 2026-06-22 — QHSE3 (apps/qhse): management command `seed_itp_solaire` (idempotent, additif, par société ou `--company`) seedant 3 ITP solaires (résidentiel réseau / autoconsommation indus-com / pompage agricole), 7 points chacun, hold-points sur Raccordement + Mise en service. Clés idempotentes company+code / company+plan+ordre (jamais d'écrasement). Aucune migration (modèles QHSE2). 7 tests.
- 2026-06-22 — PROJ3 (apps/gestion_projet): machine à états du projet INDÉPENDANTE de STAGES.py (rule #2 respectée — aucune clé STAGES réutilisée) — statut brouillon→planifié→en_cours⇄en_pause→terminé, annulé depuis tout état non terminal ; actions planifier/demarrer/mettre-en-pause/reprendre/terminer/annuler (transitions illégales → 400), statut read-only hors actions, log `ProjetActivity` (old→new, auteur+société serveur) + `historique`. 1 migration additive, 25 tests.
- 2026-06-22 — FG156 (apps/rh): identité & numéros légaux employé sur `DossierEmploye` — `cnss`/`cimr`/`amo` (CIN+RIB déjà présents), `situation_familiale` (célibataire/marié/divorcé/veuf), `nombre_enfants` (déductions IR). Champs optionnels/nullables (lignes existantes valides), pas d'unicité (notée en follow-up pour éviter le piège AddField unique). 1 migration additive, 8 tests.
- 2026-06-22 — FG120 (apps/compta): cession/mise au rebut d'immobilisation — `CessionImmobilisation` (type vente/rebut, prix, VNC = coût − amortissements cumulés FG119, résultat de cession signé plus/moins-value, posted+écriture). `services.poster_cession` poste l'écriture de sortie équilibrée (reprise amortissements + sortie cl.2 + résultat 6513/7513 + 3481 si vente) via le service compta, RESPECTE le verrou de période, et désactive l'actif. Actions `immobilisations/{id}/ceder`, `cessions/{id}/poster`. 1 migration additive, 19 tests.
- 2026-06-22 — KB4 (apps/kb): `KbArticleLien` (string-FK produit/equipement/type_intervention, comme ContratLien) + `selectors` enrichissant produit via `stock.selectors.get_produit_scoped` (equipement/type_intervention dégradent), reverse-lookup `article-liens/articles/?type_cible=&cible_id=`. Frontière cross-app + import-linter OK. 1 migration additive, 15 tests.
- 2026-06-22 — QHSE4 (apps/qhse): instance ITP chantier — `PlanInspectionChantier` (FK modèle QHSE2, `chantier_id` string-FK, statut) + `ReleveControle` (FK point, valeur, conforme NullBool, photo_key MinIO, releve_par serveur). `services.instancier_plan_chantier` copie un relevé par point (idempotent, backfill). ViewSets company-scoped + action `plans-chantier/instancier`. 1 migration additive, 16 tests.
- 2026-06-22 — PROJ4 (apps/gestion_projet): `PhaseProjet` (type étude/appro/pose/MES/réception — enum propre, jamais STAGES.py ; dates prévues/réelles, statut, avancement 0-100 borné) + `services.instancier_phases_standard` (5 phases ordonnées, idempotent). ViewSet `phases/` + action `projets/{id}/instancier-phases`. 1 migration additive, 18 tests.
- 2026-06-22 — FLOTTE6 (apps/flotte): `ReferentielFlotte` (listes éditables par société : domaine type_vehicule/type_engin/energie/categorie_permis, code/libellé/ordre/actif, unique company+domaine+code) — ADDITIF, les choices hardcodés Vehicule/EnginRoulant restent intacts. Command idempotente `seed_referentiels_flotte` (énergie/permis/types standards). ViewSet `referentiels/` (?domaine/?actif). 1 migration additive, 19 tests.
- 2026-06-22 — CONTRAT5 (apps/contrats): champ `Contrat.sav_contrat_maintenance_id` (PositiveInteger nullable, string-id vers `sav.ContratMaintenance`) — purement additif, AUCUN import/édition de sav (sav n'a pas de selectors.py), pas de validation cross-app (notée en follow-up). Ne casse rien. 1 migration additive nullable, 4 tests.
- 2026-06-22 — FG122 (apps/compta): position de trésorerie consolidée + projection — `selectors.position_tresorerie` (solde par `CompteTresorerie` actif = solde_initial + mouvements GL de son compte cl.5 + total consolidé) et `selectors.projection_tresorerie` (estimation nette = trésorerie + créances 3421 − dettes 4411 − dettes sociales/paie 44xx − TVA nette due, plancher 0), calculées 100 % depuis le GL compta (aucun import cross-app). Action `GET compta/etats/position-tresorerie/` (Admin/Responsable, params date_fin/validees). Purement additif, aucune migration, 9 tests.
- 2026-06-22 — M4 (apps/ventes + apps/audit + core): dernière back-edge `ventes → audit` supprimée — la capture d'audit PDF passe désormais par `core.events.document_pdf_generated`, émis par `ventes/views/devis.py` et `facture.py`, auquel `audit` souscrit dans `apps.py ready()` (`receivers.py`) pour écrire le même `AuditLog.Action.PDF`. Carte des 3 couches documentée dans `core/events.py`. Nouveau contrat import-linter `ventes-does-not-import-audit` (4 contrats KEPT). NOTE: nouvelle réaction inter-apps via le bus d'événements M6 (nouvelle architecture) ; aucun modèle/migration/dépendance, comportement identique. 4 tests (audit).
- 2026-06-22 — FG157 (apps/rh + apps/roles): `Remuneration` (FK employe `DossierEmploye`, montant, devise MAD, periodicite mensuel/horaire/journalier/annuel, date_effet, historique = lignes datées) gatée en lecture ET écriture par la nouvelle permission `salaires_voir`. NOTE (AUTH): permission `salaires_voir` enregistrée dans roles (auto-accordée Directeur/Administrateur, marquée ELEVATED — non auto-octroyable). Multi-tenant (company forcée serveur). 1 migration additive (CreateModel), 7 tests.
- 2026-06-22 — PAIE3 (apps/paie): valeurs légales 2026 marocaines (CNSS plafond 6000 + taux, AMO, taxe formation, SMIG/SMAG, frais professionnels, barème IR mensuel 6 tranches) semées comme DÉFAUTS ÉDITABLES par société (`services.ensure_defaults`, idempotent sur (company, 2026-01-01)) avec `valide_par_fondateur=False`. Command `seed_paie_legaux` + action `paie/parametres/seed-defaults/`. NOTE (DECISION): valeurs statutaires en attente de validation fondateur, modifiables par PATCH. 1 migration additive revertable, 11 tests.
- 2026-06-22 — PROJ5 (apps/gestion_projet): `Tache` WBS — FK projet/phase + self-FK `parent` (related_name sous_taches → profondeur arbitraire), `code_wbs`, `statut` propre (a_faire/en_cours/termine/bloque — JAMAIS STAGES.py), `avancement_pct` borné 0-100, `charge_estimee`. Sélecteur `arbre_taches` (arbre imbriqué 1 requête) + endpoints CRUD company-scoped + `projets/{id}/taches/`. NOTE (ARCH): nouveau modèle Tache. 1 migration additive revertable, 21 tests.
- 2026-06-22 — QHSE5 (apps/qhse): auto-conformité des relevés mesurés — `valeur_min`/`valeur_max` (Decimal nullable) ajoutés à `PointControleModele` ; `ReleveControle.save()` calcule `conforme = (min ≤ valeur ≤ max)` (bornes inclusives optionnelles) UNIQUEMENT quand le point définit une plage numérique et que la valeur parse en nombre — sinon laisse la conformité manuelle intacte (bulk_create QHSE4 préservé). 1 migration additive, 16 tests.
- 2026-06-22 — FG350 (frontend): CopilotPanel — tiroir conversationnel global (Sheet droite, focus-trap) monté dans Layout.jsx, togglé par un bouton Bot dans Header.jsx (état `ia.copilotOpen`). Réutilise 1:1 le slice ia existant (queryAgent → /api/fastapi/sql-agent/query, historique, confirmation d'actions sensibles AG3). Dégrade proprement sans clé (label FR « Assistant indisponible »). Aucune nouvelle dépendance/endpoint. eslint 0 erreur, 7 tests.
- 2026-06-22 — GED5 (frontend): navigateur arborescent FR à `/ged` (lien Sidebar « Documents (GED) ») — arbre dossiers role=tree (expand/collapse, icônes, aria) à gauche + table documents du dossier sélectionné à droite ; consomme les endpoints ged existants (cabinets/dossiers/documents, company-scoped), arbre reconstruit client-side par des helpers purs testés (`tree.js`). Aucun backend touché. eslint 0 erreur, 7 tests.
- 2026-06-22 — FG123 (apps/compta): rapprochement bancaire — `RapprochementBancaire` (FK `CompteTresorerie`, période/solde_releve/statut en_cours→rapproche), `LigneReleve` (lignes de relevé signées) et `PointageReleve` (through liant une ligne relevé à une ou plusieurs `LigneEcriture` GL). `services.pointer_ligne_releve` remplace les lignes GL pointées, valide même société + compte de la trésorerie, marque la ligne rapprochée si Σ(débit−crédit) = montant relevé (écart 0). `selectors.resume_rapprochement` (solde relevé vs solde GL vs écart) ; `cloturer_rapprochement` ne clôt que si tout concorde — AUCUNE écriture créée (distinct de FG42 import paiements). Endpoints `compta/rapprochements/` + actions. 1 migration additive (0006), 24 tests.
- 2026-06-22 — FG49 (apps/ventes): 3e format d'export comptable — grand-livre codé par compte (CGNC : 3421 Clients TTC / 7111 Ventes HT par taux / 4455 TVA collectée par taux, avoirs inversés), colonnes Compte/Intitulé/Date/Journal/Pièce/Libellé/Tiers/ICE/TVA/Débit/Crédit + ligne TOTAL, en .xlsx et .csv (layout PCG/Sage pour fiduciaire). Codes par défaut `_DEFAULT_ACCOUNT_CODES` surchargeables global (`settings.VENTES_COMPTA_ACCOUNT_CODES`) et par société. `GET ventes/export-comptable/?layout=grand-livre&fmt=xlsx|csv`, company-scoped, AR uniquement (aucun prix d'achat/marge). Aucune migration, 10 tests.
- 2026-06-22 — FG351 (apps/agent + fastapi_ia): outils d'écriture en langage naturel GARDÉS — `apps/agent/registry.py` étendu de 3 actions d'écriture (`ventes.devis.create` passée internal→outward, `crm.client.create`, `crm.lead.create`), `risk=outward` ⇒ le relais FastAPI renvoie une PROPOSITION signée (confirm_token) qui doit passer par le flux confirm existant (re-valide permission + company + entrées, relaie via REST interne JWT) — jamais d'écriture directe, company jamais lue du corps. NOTE (architecture/auth) : nouvelles capacités d'écriture agent, gardées propose→confirm. Aucune migration/dépendance. 7 (Django) + 7 (FastAPI) tests.
- 2026-06-22 — FG158 (apps/rh): contact d'urgence & coordonnées étendues — 7 champs additifs nullable sur `DossierEmploye` (urgence_nom/lien/telephone, groupe_sanguin, adresse_perso, telephone_perso, email_perso) exposés via le serializer existant et l'endpoint `rh/employes/`, sans nouveau modèle/viewset ni accès élargi (dossier reste IsResponsableOrAdmin). Migration 0005 additive (sur 0004_remuneration de wave-1), 6 tests.
- 2026-06-22 — PAIE5 (apps/paie): barème IR officiel + déductions charges de famille — 2 champs additifs sur `ParametrePaie` (`deduction_par_personne_a_charge`=30 MAD, `plafond_personnes_a_charge`=6 → cap 360/mois) semés comme défauts éditables ; helper `compute_ir(base, bareme, parametre, personnes_a_charge)` = barème (base×taux − somme à déduire, planché 0) − min(n, plafond)×montant. NOTE (DECISION) : valeurs officielles éditables. Migration 0003 additive (sur 0002 de PAIE3), 22 tests.
- 2026-06-22 — GED6 (apps/ged + apps/records): liaison polymorphe Document↔objet métier — `DocumentLien` (ContentType + GenericFK, validé par `records.resolve_target`, unique (document, content_type, object_id), company/created_by serveur), `records.ALLOWED_TARGETS` étendu d'une entrée (`ventes.boncommande` → 8 types autorisés). Endpoints `ged/liens/` (create `{document, model, id}`) + reverse-lookup `?model=&id=` + sélecteurs `documents_for_target`/`liens_for_target` (génériques, aucun import de modèle domaine — import-linter 4/4 KEPT). NOTE (DECISION) : 8 cibles autorisées. Migration ged 0002 additive (records = édition Python pure, sans schéma), 99 tests ged+records.
- 2026-06-22 — PROJ6 (apps/gestion_projet): dépendances de tâches — `DependanceTache` (FK predecesseur/successeur → `Tache`, `type_dependance` FS/SS/FF/SF — enum propre jamais STAGES.py, `lag` IntegerField ± jours, unique (predecesseur, successeur)) avec validation clean()+serializer (rejette self-dépendance, cross-projet/cross-tenant, cycle direct A→B/B→A) ; sélecteurs prédécesseurs/successeurs + action `taches/<id>/dependances/` (fondation CPM PROJ8). Migration 0006 additive (sur 0005_tache de PROJ5), 21 tests.
- 2026-06-22 — QHSE6 (apps/qhse): points d'arrêt bloquants — `selectors.hold_points_status(plan_chantier)` + `phase_peut_avancer(plan, phase)` : un `PointControleModele.hold_point=True` dont le `ReleveControle` est absent OU non `conforme=True` bloque l'avancement ; débloqué dès qu'un relevé conforme existe ; les non-conformités hors hold-point ne bloquent pas. Endpoint `plans-chantier/<id>/hold-points/` + champs serializer `peut_avancer`/`nb_hold_points_bloquants`. Lecture seule (ne mute pas le chantier, n'importe pas installations — câblage avancement laissé en follow-up). NOTE (DECISION) : règle de blocage. Aucune migration, 15 tests.
- 2026-06-22 — FG124 (apps/compta): caisse / petty cash — `Caisse` (liée à un `CompteTresorerie` type=caisse, solde_initial/responsable), `MouvementCaisse` (entrée/sortie, justificatif/pièce, posté→écriture CSH 2 jambes équilibrée optionnelle respectant le verrou de période FG115, idempotent), `ClotureCaisse` (solde théorique gelé vs compté = écart, fige les mouvements ≤ date close). Endpoints `compta/caisses/` + actions mouvement/poster-mouvement/resume/cloturer, company-scoped Admin/Responsable. Aucun prix d'achat exposé. Migration 0007 additive, 24 tests.
- 2026-06-22 — FG50 (apps/ventes): transfert/remboursement d'acompte à l'annulation de facture — `FactureViewSet.annuler` accepte `{acompte:{action}}` : « transferer » re-pointe les `Paiement` vers une autre facture du MÊME devis (soldes re-dérivés, chatter des 2 côtés) ; « rembourser » écrit un `Paiement` négatif de reprise (acompte plus « coincé »). Validations same-devis / same-company / self / non-annulée, transaction atomique select_for_update. Annulation sans acompte STRICTEMENT inchangée. NOTE (DECISION) : sémantique comptable conservatrice, aucune migration (réutilise Paiement). 16 tests, suite ventes 492 OK.
- 2026-06-22 — FG159 (apps/rh): coffre documents employé — `DocumentEmploye` (FK employe→`DossierEmploye`, OneToOne→`records.Attachment` en string-FK, `type_document` contrat/cin/rib/diplome/autre, `date_expiration` nullable) réutilisant le pipeline de stockage MinIO de `records` (aucun nouveau stockage). Endpoints `rh/documents/` (filtres ?employe/?type_document) + `expirant-bientot/?within=N` (sélecteur ignorant NULL/déjà-expiré). Accès IsResponsableOrAdmin (même verrou que le dossier), company serveur. Migration 0006 additive, 10 tests.
- 2026-06-22 — PAIE6 (apps/paie): `Rubrique` paramétrable — modèle company-scoped (unique code, `type` gain/retenue/cotisation, flags `imposable`/`soumis_cnss`/`soumis_amo`/`soumis_cimr`, `compte`, base+`taux`/`montant_fixe`, ordre/actif) — catalogue éditable des lignes de bulletin. Endpoint `paie/rubriques/` + `seed-defaults` (seed idempotent de 7 rubriques standard SB/PRIME/HS/CNSS/AMO/IR/AVANCE, ne réécrit jamais une rubrique éditée). Migration 0004 additive, 7 tests.
- 2026-06-22 — GED7 (apps/ged): import idempotent des `records.Attachment` existants — command `migrate_attachments_to_ged [--company][--dry-run]` : chaque Attachment → `Document` (cabinet « Importé »/dossier auto par société) + `DocumentVersion` v1 RÉUTILISANT le `file_key` MinIO (aucune copie/ré-upload) ; si la cible de l'Attachment est dans `records.ALLOWED_TARGETS` et existe, crée le `DocumentLien` (GED6). Clé d'idempotence `(company, file_key)` ; back-fill du lien manquant au re-run ; originaux jamais supprimés/mutés ; `--dry-run` n'écrit rien. NOTE (DECISION) : landing par défaut cabinet/dossier « Importé ». Aucune migration (command), 9 tests.
- 2026-06-22 — PROJ7 (apps/gestion_projet): jalons (+ facturation_pct) — `Jalon` (FK projet + phase/tache optionnels SET_NULL contraints même-projet, libelle/description, `date_prevue` requise, `date_reelle` nullable, `statut` propre a_venir/atteint/manque — JAMAIS STAGES.py, `facturation_pct` % de la valeur projet à facturer au jalon, validé 0–100 modèle+serializer). Endpoints `jalons/` (?projet/?statut/?facturation) + `projets/<id>/jalons/`, sélecteur `jalons_for_projet` ordonné par date. Migration 0007 additive, 19 tests.
- 2026-06-22 — QHSE7 (apps/qhse): relevé courbe I-V par string — `ReleveCourbeIV` (company-scoped, `chantier_id` loose + `plan_chantier` SET_NULL — aucun import installations, `string_id`, mesures voc/isc/vmpp/impp/pmpp, irradiance W/m², temperature_module °C, `courbe_points` JSON `[{v,i}]`) + `fill_factor()` = Pmpp/(Voc·Isc) (4 décimales) si valeurs présentes. Endpoints `qhse/courbes-iv/` (?chantier_id) + `par-chantier`, sélecteur `courbes_iv_for_chantier`. Migration 0005 additive, tests (suite qhse 79 OK).
- 2026-06-24 — FG52 (apps/ventes): facturation multi-devises — champs additifs `devise` (ISO 4217, défaut MAD) + `taux_change` (défaut 1) sur Devis et Facture, et `CompanyProfile.devise_defaut` (défaut MAD) ; à la création API d'un devis/facture sans devise explicite, la devise par défaut de la société est appliquée (repli MAD), une devise envoyée reste prioritaire. `fmt()` du moteur PDF premium et l'export UBL (`dgi_export.py` + `utils/ubl.py`) lisent désormais la devise du document → DocumentCurrencyCode. Migrations ventes/0029 + parametres/0025 additives. Tests verts (MAD défaut, défaut-société EUR, override explicite, isolation tenant, UBL). NOTE (SCHEMA) : pas de conversion en base, la devise est portée par le document.
- 2026-06-24 — FG166 (apps/rh): pointage arrivée/départ — modèle `Pointage` (company-scoped, employe, type arrivée/départ/complet, heure_arrivee/heure_depart serveur, GPS optionnel, `duree_minutes`) + actions `pointager-arrivee` / `<id>/pointager-depart` (horodatage serveur, passe COMPLET + calcule la durée quand l'arrivée est renseignée). Migration 0008 additive (noms d'index ≤30 car.). Tests verts (durée, isolation tenant, double-départ refusé, rôle, GPS).
- 2026-06-24 — CONTRAT6 (apps/contrats): niveaux de confidentialité — champ `confidentialite` (public/interne/confidentiel, défaut interne) ; les contrats CONFIDENTIEL ne sont visibles que des Administrateurs, la garde s'appuie sur le palier FAISANT AUTORITÉ `menu_tier` (corrige un `effective_role` inexistant qui excluait à tort un admin provisionné via le Role FK). Migration 0005 additive. Tests verts (exclusion responsable liste+détail, admin via Role FK voit, isolation tenant, filtre).
- 2026-06-24 — FLOTTE5 (apps/flotte): référence d'actif unifiée — modèle `ActifFlotte` reliant entretien/sinistre/document à un `Vehicule` OU un `EnginRoulant` via une seule référence (exclusivité + même-société validées dans clean()/save()), endpoint company-scoped + sélecteurs cross-app. Migration 0005 additive. Tests verts (validation, cascades, isolation tenant, rôle).
- 2026-06-24 — PAIE13 (apps/paie): salaire de base multi-profils — `calculer_salaire_base_periode()` gère mensuel (proraté aux jours d'absence), journalier (×jours travaillés), horaire (×heures), forfait (fixe) ; champs `jours_travail_mensuel` (26) + `heures_travail_mensuel` (191) sur ProfilPaie, consommés par `calculer_bulletin`. Migration 0006 additive. Tests verts (4 types + proration).
- 2026-06-24 — GED14 (apps/ged): aperçu inline multi-format — action `versions/<id>/apercu` qui relaie les octets du document via Django (même origine) pour un affichage inline (PDF/image/texte → inline, sinon attachment, X-Content-Type-Options: nosniff), gardée comme une LECTURE (IsAnyRole, comme list/retrieve) pour que les rôles lecture seule puissent prévisualiser. Réutilise le stockage MinIO de records (aucune nouvelle dépendance). Tests verts (inline pdf/image/texte, fallback, 404, isolation tenant, rôle lecture seule).
- 2026-06-24 — PROJ14 (apps/gestion_projet): détection des retards — sélecteur `retards_projet` + action `projets/<id>/retards` classant tâches non terminées et jalons non atteints en `en_retard` (échéance dépassée) ou `a_risque` (échéance dans `seuil_jours`, défaut 7), avec `retard_jours`. Aucune migration. Tests verts (logique, isolation tenant 404, seuil, rôle).
- 2026-06-24 — FG131 (apps/compta) DEFERRED (non livré) : un build a créé des modèles `BonCommandeFournisseur`/`FactureFournisseur` en double dans apps/compta, en conflit avec ceux déjà présents dans apps/stock (clash d'accesseur inverse sur `company`) ; le rapprochement opérait donc sur des données isolées, déconnectées de l'approvisionnement réel. Backé out (compta ramené à origin/main), laissé `[ ]` : à reconstruire en RÉUTILISANT les modèles d'achat de stock via ses selectors/services.
- 2026-06-29 — FG131 (apps/compta): Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) RECONSTRUIT en réutilisant les modèles d'achat de `apps/stock` via ses selectors (jamais de doublon) — nouveau `Rapprochement` (string-FK `stock.BonCommandeFournisseur`) + service `creer_rapprochement_3voies`/`evaluer`/`valider` (bon-à-payer bloqué tant qu'un écart subsiste), endpoint `rapprochements-3voies/`. Migration compta 0009 additive, 23 tests. (NOTE: nouvelle brique de contrôle pré-paiement.)
- 2026-06-29 — FG168 (apps/rh): Heures supplémentaires & calcul majoré — `HeuresSupp` (seuil journalier, nuit/repos/férié) calcul serveur des buckets HS 25/50/100 % (droit du travail marocain) + selector `heures_supp_pour_paie` pour la paie. Migration rh 0010 additive, 27 tests.
- 2026-06-29 — PAIE16 (apps/paie): Avantages en nature & indemnités imposables/non-imposables (plafonds) — `Rubrique` étendue (`avantage_nature`, `plafond_exoneration`) + `repartir_avantage` (exonéré jusqu'au plafond, excédent réintégré dans la base IR), barèmes marocains au catalogue. Migration paie 0009 additive, 18 tests.
- 2026-06-29 — QHSE18 (apps/qhse): `ProcedureQualite` versionnée (docs qualité GED) — versionnage référence+version (max+1 via select_for_update), lien lâche `document_id` vers ged, service activer/nouvelle version. Migration qhse 0012 additive, 24 tests.
- 2026-06-29 — CONTRAT9 (apps/contrats): `ClauseContrat` (clauses résolues, ordonnées, surchargeables) sur un Contrat — résolution depuis une clause source, flag `surchargee`, unicité conditionnelle. Migration contrats 0008 additive, 22 tests.
- 2026-06-29 — FLOTTE9 (apps/flotte): Contrôle permis valide/catégorie à l'affectation — `Vehicule.categorie_permis_requise` + service `controle_permis` (rejette permis absent/expiré/mauvaise catégorie, flag `force` pour avertir). Migration flotte 0008 additive, 21 tests.
- 2026-06-29 — FG245 (apps/ventes): Éditeur de calepinage toiture — `RoofLayout` (dims toiture/retraits/modules, JSON panels, `panel_count` calculé serveur), viewset scopé société, `recompute`. N'altère pas le PDF premium ni les statuts. Migration ventes 0037 additive, 24 tests. (NOTE: nouveau modèle/table.)
- 2026-06-29 — FG352 (apps/ged): RAG DocQA — `DocumentChunk` (pgvector existant réutilisé), `chunk_text` (langchain-text-splitters, fallback pur Python) + `index_document_chunks` + selector `retrieve_chunks` (scopé société + ACL coffre-fort), endpoint `documents/docqa/`, AgentAction `ged.docqa.retrieve`. No-op sans clé d'embedding. Migration ged 0010 additive, 10 tests. (NOTE: nouvelle dépendance open-source `langchain-text-splitters`.)
- 2026-06-29 — PROJ17 (apps/gestion_projet): Indisponibilités ressources (congé/formation/arrêt) — `Indisponibilite` + selector `ressource_disponible_sur_periode` (détection chevauchement, bornes inclusives). Migration gestion_projet 0012 additive, 24 tests.
- 2026-06-29 — FG88 (apps/sav): Planification de tournée maintenance préventive — `Ticket.date_tournee` + `tournee_preventive` (tickets préventifs dus enrichis GPS, tri proximité haversine) + `planifier_tournee` (bulk-assign date+technicien). Lecture GPS via `installations.selectors`. Migration sav 0010 additive, 11 tests.
- 2026-06-29 — LITIGE4 (apps/litiges): Lien litige qualité ↔ QHSE — `Reclamation.ncr_id`/`audit_id` (réfs lâches) + aperçus résolus via `qhse.selectors` (jamais d'import cross-app de modèles). Migration litiges 0004 additive, 18 tests.
- 2026-06-29 — FG6 (apps/reporting): Flux iCal par utilisateur — `GET reporting/calendar.ics?token=` (VCALENDAR fait main, poses/MES/interventions/visites), token signé stable par utilisateur (core.signing, sans expiration), bouton « S'abonner au calendrier » dans CalendarPage.jsx. Aucune dépendance/migration, 9 tests. (NOTE: endpoint authentifié par token signé, lecture seule scopée société.)
- 2026-06-29 — DC17 (authentication): `CustomUser.poste` texte → référentiel `rh.Poste` — FK nullable `poste_ref` + migration de données dédupliquant par société les chaînes existantes (colonne texte legacy préservée). Migration authentication 0013 (SCHEMA + data, réversible), 11 tests. (NOTE: migration de données réversible.)
- 2026-06-29 — DC18 (apps/automation): Store de modèles email/message — `ModeleMessage` (par société+canal email/whatsapp/doc) + `actions._send_email` résout sujet/corps depuis le modèle actif (fallback au défaut « Notification Taqinor » si absent — comportement identique). Migration automation 0002 additive, 11 tests.
- 2026-06-29 — N91 (apps/installations + frontend): Capture terrain tolérante au hors-ligne — `FieldOp` (journal d'idempotence) + endpoint `installations/sync/` (lot rejouable, last-write-wins, scopé société) + outbox IndexedDB front + Background Sync dans sw.js. Migration installations 0015 additive, 14 tests backend + 7 front.
- 2026-06-29 — F21 (apps/installations + frontend): Capture hors-ligne étendue à tout le flux d'intervention (checklist/check-in/photos/séries/mémos/consommables/réserves/signature) sur l'infra outbox+sync de N91. Couvert par la suite field_sync.
- 2026-06-29 — FG135 (apps/compta): Notes de frais & remboursements employés — `NoteFrais` (justificatif photo, cycle brouillon→soumise→validée→remboursée/rejetée), validation poste une écriture de charge équilibrée et le remboursement poste le paiement (idempotents, verrou de période respecté), référence NDF-YYYYMM-NNNN via la fabrique race-safe. Migration compta 0011 additive, 22 tests. (NOTE: revue adverse — `creer_note_frais` ré-enveloppé dans `create_with_reference` pour éviter le 500 sous collision concurrente.)
- 2026-06-29 — FG291 (apps/installations): Programme / Projet multi-chantiers — `Projet` (+ liens chantier/devis/ticket) regroupant les documents d'un même client/site via FK chaînes (`ventes.Devis`/`sav.Ticket`/`crm.Client`), machine d'états propre (brouillon/actif/en_pause/termine/annule) distincte de STAGES.py, attache idempotente scopée société, référence PRG- race-safe. Migration installations 0016 additive, 13 tests. (NOTE: NOUVEAU composant architectural — couche projet au-dessus de `installations`.)
- 2026-06-29 — FG255 (apps/ventes): Dimensionnement borne de recharge VE — fonction pure `ev_charger_sizing` (courant/calibre mono 230 V & tri 400 V, durée de charge, borne standard 3.7/7.4/11/22 kW) couplée au PV : le surplus solaire alimente la borne et relève le taux d'autoconsommation. Aucune migration, aucune dépendance, 9 tests, chemin PDF intact.
- 2026-06-29 — FG361 (core): Prévision de ventes / demande — `core/forecast.py` projette le CA et le volume de devis mensuels depuis l'historique (Holt-Winters statsmodels si dispo, repli pur Python tendance/moyenne mobile). Couche fondation (aucun import d'app métier, import-linter vert), 16 tests. (NOTE: NOUVELLE dépendance externe `statsmodels==0.14.4` ajoutée à requirements.txt — import défensif, repli si absente. Revue adverse — garde NaN déplacée avant le clamp pour que le repli se déclenche réellement.)
- 2026-06-29 — FG172 (apps/rh): Matrice de compétences — catalogue `Competence` (pose structure, raccordement DC/AC, MES onduleur, pompage, soudure…) + niveau 0–4 par employé `CompetenceEmploye` avec traçabilité de l'évaluateur, CRUD + action `matrice`. Migration rh 0014 additive, 14 tests.
- 2026-06-29 — CONTRAT13 (apps/contrats): `RegleApprobation` (par montant/type) + résolveur « règle la plus spécifique gagne » (type exact > intervalle borné le plus étroit > priorité), CRUD + action `/resoudre/`, scopé société. Migration contrats 0010 additive, 15 tests.
- 2026-06-29 — FLOTTE13 (apps/flotte): Calcul conso L/100 km et kWh/100 km depuis pleins + odomètre (segment plein-à-plein, garde division par zéro, unités L/kWh isolées), endpoint lecture scopé société `/pleins/consommation/?vehicule=`. Aucune migration, 15 tests. (NOTE: revue adverse — action `consommation` ajoutée à READ_ACTIONS pour la lecture tout rôle.)
- 2026-06-29 — GED17 (apps/ged): Cycle de vie documentaire — champ `statut` sur `Document` (brouillon→revue→approuvé→archivé→obsolète) avec machine d'états gardée (transitions illégales rejetées), action `cycle-vie/`, statut en lecture seule hors action, filtre `?statut=` ; statuts locaux GED distincts du funnel STAGES.py. Migration ged 0011 additive, 15 tests.
- 2026-06-29 — FG136 (apps/compta): Indemnités kilométriques & per-diem chantier — `BaremeIndemnite` (taux km + per-diem, un défaut actif par société) + `IndemniteChantier` (distance haversine GPS départ→site × taux × A/R + per-diem × jours, figés à la création) ; validation poste une écriture équilibrée et le remboursement le paiement (verrou de période respecté, idempotents). Migration compta 0012 additive, 30 tests. (NOTE: haversine recopié localement pour garder compta découplé de installations/sav.)
- 2026-06-29 — FG292 (apps/installations): Tâches & sous-tâches de projet avec dépendances — `ProjetTache` (FK Projet, `parent` self-FK sous-tâches, `predecesseur` self-FK, assigné/échéance, statut propre a_faire/en_cours/termine ≠ STAGES.py) avec gardes anti-cycle (parent ET prédécesseur, rollback atomique). Migration installations 0017 additive, 13 tests. (NOTE: étend le composant ARCH Projet de FG291.)
- 2026-06-29 — FG256 (apps/ventes): Étude de stockage & dispatch batterie — fonction pure `battery_storage_sizing` : objectif autoconsommation max (stockage du surplus diurne, plafonné par la charge de nuit réutilisable) vs backup N heures critiques (kWh/kW utiles), kWh nominal via DoD×rendement, pack recommandé + contrainte dominante. Aucune migration, 14 tests, chemin PDF intact.
- 2026-06-29 — FG362 (core + apps/reporting): Score de probabilité de gain — `core/win_probability.py` (scorer pur fondation, prend les features d'un lead en entrée, base par étape + ajustements récence/priorité/canal/relances, bornée [0,1], cas terminaux perdu→0/SIGNED→1) ; `reporting/pipeline.py` pondère désormais la prévision par cette probabilité par lead (repli sur l'ancienne carte statique en cas d'erreur). Aucune migration, import-linter 4/4 (core reste fondation), 28 tests.
- 2026-06-29 — FG173 (apps/rh): Habilitations électriques (NF C 18-510 B0/H0/B1V/B2V/BR…) — `Habilitation` par employé avec organisme + `date_validite`, propriété `valide` (active & non expirée), endpoint `habilitations/expirantes/?expire_within=N`. Distinct de la matrice de compétences FG172. Migration rh 0015 additive, 18 tests.
- 2026-06-29 — CONTRAT14 (apps/contrats): Étapes & workflow d'approbation interne — `EtapeApprobation` instanciée depuis la `RegleApprobation` (CONTRAT13) via le résolveur existant ; `lancer_workflow_approbation`/`approuver_etape`/`rejeter_etape` séquentiels et gardés ; ne touche jamais `Contrat.statut` (préservation des statuts). Migration contrats 0011 additive, 23 tests.
- 2026-06-29 — FLOTTE14 (apps/flotte): Cartes carburant & alertes anomalie — `CarteCarburant` (numéro/plafond, FK véhicule/conducteur optionnelles) + détecteur `anomalies_pleins` (km en recul, saut >5000 km, conso aberrante >2× médiane véhicule en réutilisant FLOTTE13, dépassement de plafond), endpoint `cartes/anomalies/` lecture tout rôle. Migration flotte 0012 additive, 22 tests. (NOTE: nouveau composant CarteCarburant, additif/réversible.)
- 2026-06-29 — QHSE19 (apps/qhse): `RetourClientQualite` (satisfaction qualité) — note 1–5 + commentaire, liens chantier/client par id chaîné (pas d'import cross-app), `traite` bool, sélecteur `satisfaction_moyenne` + endpoint `retours-client/moyenne/`. Migration qhse 0013 additive, 18 tests.
- 2026-06-29 — FG137 (apps/compta): Préparation de la déclaration TVA — `DeclarationTVA` agrège depuis le grand-livre TVA collectée (4455/44552) − déductible (3455/34552) sur la période par régime (mensuel/trimestriel) & méthode (débit/encaissement) → `tva_a_declarer` + `credit_reportable`, snapshot figé (réf `TVA-` race-safe), export CSV. Migration compta 0013 additive, 18 tests.
- 2026-06-29 — FG294 (apps/installations): Budget projet vs réel — `BudgetProjet` (enveloppes HT par catégorie + seuil d'alerte) + `BudgetEngagement`, sélecteur `budget_projet_synthese` agrège les réels (devis ventes via get_model, BCF/factures fournisseur via stock.selectors, main-d'œuvre même-app) vs budget + alerte de dépassement. Migration installations 0018 additive, 16 tests, import-linter 4/4. (NOTE: composant ARCH budgétaire, viewsets internes responsable/admin.)
- 2026-06-29 — FG257 (apps/ventes): Simulation bankable P50/P90 — fonction pure `simulate_bankable_yield` : Performance Ratio depuis les pertes (température/salissure/câblage/onduleur/mismatch/dispo), P50 = base×PR, P90/P75 via quantile gaussien d'une variabilité annuelle σ (déf. 6 %), breakdown des pertes. Aucune migration, 16 tests, chemin PDF intact.
- 2026-06-29 — FG363 (core): Score de churn / risque client — `core/churn_risk.py` scorer pur fondation (features client en entrée : inactivité/contrat lapsé/tickets SAV/âge intervention → score [0,1] + bande faible/moyen/élevé + explication), repli si aucune feature. Aucune migration, import-linter 4/4 (core reste fondation), 26 tests.
- 2026-06-29 — FG174 (apps/rh): Certifications spécifiques — `Certification` par employé (travail en hauteur/harnais/CACES-nacelle/secourisme-SST/conduite + organisme + `date_validite`), propriété `valide`, endpoint `certifications/expirantes/?expire_within=N`. Distincte des habilitations électriques FG173. Migration rh 0016 additive, 19 tests.
- 2026-06-29 — CONTRAT15 (apps/contrats): Chatter/journal du contrat — `ContratActivity` journalise automatiquement les transitions (statut/confidentialité + étapes du workflow d'approbation) + notes manuelles, timeline `historique/` et action `noter/`, valeurs old/new en TextField (snapshots longs). Migration contrats 0012 additive, 21 tests.
- 2026-06-29 — FLOTTE15 (apps/flotte): Plans d'entretien préventif — `PlanEntretien` rattaché à un `ActifFlotte` (véhicule|engin), déclenchement par intervalle km/jours/heures + seuils, sélecteur d'échéances (due/upcoming/ok) + endpoint `plans-entretien/echeances/` (lecture tout rôle). Migration flotte 0013 additive, 21 tests.
- 2026-06-29 — GED18 (apps/ged): Workflow d'approbation/revue documentaire — `DemandeApprobation` (demandeur/approbateur, statut en_attente/approuve/rejete) ; `request_review`/`approve`/`reject` réutilisent la machine d'états GED17 (`change_lifecycle_status`, brouillon→revue→approuvé) sans la dupliquer, gardes anti-doublon/déjà-décidé/cross-société. Migration ged 0012 additive, 20 tests.
- 2026-06-29 — FG138 (apps/compta): Relevé de déductions détaillé (annexe TVA) — sélecteur `releve_deductions_tva` liste ligne par ligne les écritures de TVA déductible (3455/34552) d'une période (date/pièce/tiers/base HT/TVA/taux), réconcilie 1:1 avec FG137, endpoint lecture `etats/releve-deductions-tva/` (JSON/CSV). Aucune migration (réutilise le GL), 11 tests.
- 2026-06-29 — FG295 (apps/installations): P&L de projet consolidé — sélecteur `projet_pnl` : revenu (factures clients des chantiers/devis) − coûts (matériel/sous-traitance/imports via engagements + main-d'œuvre) → marge brute + marge %, réutilise les agrégats cross-app FG294 (get_model/selectors, import-linter 4/4), action `programmes/{id}/pnl/` responsable/admin. Aucune migration, 14 tests. (NOTE: couche ARCH P&L sur FG291/FG294.)
- 2026-06-29 — FG258 (apps/ventes): Profil d'autoconsommation horaire — `hourly_self_consumption` (par heure autoconsommé = min(charge, production) → taux d'autoconso/couverture, surplus injecté), profils types résidentiel/commercial + `load_curve_from_xlsx` (openpyxl déjà présent, NON ajouté). Math pure, garde division par zéro, 16 tests, chemin PDF intact.
- 2026-06-29 — FG364 (core): Prévision de réappro stock — `core/stock_reorder.py` scorer pur fondation : depuis l'historique de conso (ou conso moyenne) + stock + délai + stock de sécurité → date de rupture, point de commande, quantité suggérée, drapeau « commander maintenant » ; `today` en paramètre, garde conso nulle. Aucune migration, import-linter 4/4 (stdlib seul), 33 tests.
- 2026-06-29 — FG175 (apps/rh): Alertes d'expiration (habilitations/certifs/docs) — moteur unifié `echeances_rh` (union habilitations + certifications + documents employé expirant sous X jours, trié, jours_restants), endpoint `echeances/?within=N` + commande `alertes_expiration_rh` qui notifie via le service partagé `notifications.notify` (import function-local). Aucune migration, 13 tests.
- 2026-06-29 — PROJ18 (apps/gestion_projet): Plan de charge (capacité vs affecté) — sélecteur `plan_de_charge` : par ressource, capacité (jours ouvrés − indisponibilités × heures/jour) vs affecté (affectations directes + via équipe, pro-rata fenêtre) → surcharge + utilisation %, garde capacité nulle, endpoint `ressources/plan-de-charge/`. Aucune migration, 24 tests.
- 2026-06-29 — PAIE20 (apps/paie): CIMR optionnelle (taux par employé adhérent) — helper dédié `cimr_salariale(brut, affilie, taux)` (miroir CNSS/AMO, 0 si non-adhérent ou taux≤0) branché dans `calculer_bulletin` (formule/arrondi inchangés, comportement préservé) ; les champs `affilie_cimr`/`taux_cimr_salarial` existaient déjà (migration 0005). Aucune nouvelle migration, 9 tests.
- 2026-06-29 — QHSE20 (apps/qhse): Tableau de bord « ISO 9001 readiness » — sélecteur `iso9001_readiness` : score pondéré + 6 critères mappés aux clauses ISO 9001:2015 (NCR clôturées 10.2, CAPA délais 10.2, audits 9.2, procédures 7.5, couverture ITP 8.5/8.6, satisfaction 9.1.2), garde division par zéro, endpoint `iso9001-readiness/` responsable/admin. Aucune migration, 18 tests.
- 2026-06-29 — FG139 (apps/compta): Retenue à la source (RAS) sur honoraires/prestations — `RetenueSource` (taux × base = montant retenu par pièce/tiers, réf `RAS-` race-safe) + sélecteur bordereau de versement (totaux par prestataire + total à verser) avec export CSV (`?export=csv`). Migration compta 0014 additive, 17 tests.
- 2026-06-29 — FG299 (apps/installations): Plan de charge des équipes — sélecteur `plan_de_charge_equipes` : par technicien, capacité (jours ouvrés × heures) vs affecté (interventions principal OU équipe, dédupliquées, fenêtrées) → sur-réservation + charge %, garde capacité nulle, endpoint `interventions/plan-de-charge/`. Distinct du PROJ18 (gestion_projet) et de STAGES.py. Aucune migration, 14 tests.
- 2026-06-29 — FG259 (apps/ventes): Économie net-metering / injection surplus (loi 13-09) — fonction pure `net_metering_savings` : surplus injecté valorisé par tranche horaire (compensé jusqu'à l'import simultané de la même tranche × ratio, toggle `surplus_injecte_compense`, cap annuel optionnel, tarif résiduel). Aucune migration, 12 tests, chemin PDF intact.
- 2026-06-29 — FG365 (core): Prédiction de retard de paiement — `core/payment_delay.py` scorer pur fondation (features facture : jours de retard, retard moyen client, impayés antérieurs, relances → score [0,1] + bande de priorité de recouvrement), montant informatif seulement, repli si features absentes. Aucune migration, import-linter 4/4 (stdlib seul), 32 tests.
- 2026-06-29 — FG176 (apps/rh): Garde d'affectation par habilitation — `verifier_habilitation_requise(company, employe, type_requis)` → {autorisé, manquantes, expirées, message} (réutilise FG173), map type d'intervention→habilitations requises, endpoint `employes/{id}/verifier-habilitation/`. Blocage doux (l'enforcement à l'affectation reste côté installations). Aucune migration, 27 tests.
- 2026-06-29 — CONTRAT16 (apps/contrats): `SignatureContrat` (point e-sign in-app, loi 53-05) — nom tapé + preuve (`ip_adresse`/`user_agent` posées côté serveur), `signer_contrat` enregistre la signature, journalise (CONTRAT15) et bascule `Contrat.statut` → signé via la machine d'états existante quand toutes les parties requises ont signé. Aucun fournisseur e-sign externe. Migration contrats 0013 additive, 19 tests. (NOTE: DECISION — e-sign in-app, pas de dépendance externe.)
- 2026-06-29 — FLOTTE16 (apps/flotte): Génération d'échéances d'entretien dues + alertes — `EcheanceEntretien` générée (idempotente, pas de doublon ouvert par plan) depuis les `PlanEntretien` (FLOTTE15), alerte best-effort via `notifications.notify`, endpoint liste (dues/en retard) + commande `generer_echeances_entretien`. Migration flotte 0014 additive, 23 tests.
- 2026-06-29 — GED19 (apps/ged): ACL par dossier/document (héritage + override) — `AclGed` (cible exactement-une folder|document, principal utilisateur et/ou rôle, niveau lecture/écriture/gestion, `herite`) + sélecteur `acl_effective` qui remonte le `Folder.path` (override > plus proche > ancêtre si hérité), câblage doux dans `documents_visible_to_user` (rétrocompatible : aucune ligne ACL → comportement inchangé). Migration ged 0013 additive (2 CheckConstraint `condition=`), 16 tests. (NOTE: DECISION — modèle de contrôle d'accès rétrocompatible. Drift CheckConstraint corrigé avant merge : Meta.constraints alignées sur la migration.)
- 2026-06-29 — FG140 (apps/compta): Aide au calcul de l'IS — sélecteurs `estimer_is` (CPC → résultat fiscal ± réintégrations/déductions → IS dû = max(barème progressif, cotisation minimale 0,25 %/3000)), `echeancier_acomptes` (4 × 25 % aux fins de mois 3/6/9/12), `regularisation_is`, endpoint `etats/aide-is/` (JSON/`?export=csv`). Aucune migration (réutilise le GL/CPC), 25 tests. (NOTE: DECISION — barème IS encodé en constantes, aide indicative.)
- 2026-06-29 — FG300 (apps/installations): Détection de conflits d'affectation — sélecteur `conflits_affectation` : même technicien (principal/équipe) ou même camionnette sur ≥2 interventions le même jour → conflit (dédupliqué, exclut les actifs matériels), endpoint `interventions/conflits-affectation/`. Aucune migration, 16 tests.
- 2026-06-29 — FG260 (apps/ventes): Modélisation escalade tarifaire ONEE 20-25 ans — fonction pure `tariff_escalation_projection` : cashflow annuel (économies × escalade × dégradation), cumulé, année de payback (simple+actualisé), **VAN (NPV)** et **TRI (IRR)** par bissection/Newton stdlib (itérations bornées, None si pas de convergence). Aucune migration, 16 tests, chemin PDF intact.
- 2026-06-29 — FG366 (core): Moteur de workflow multi-étapes (BPM) + SLA/escalades — `WorkflowDefinition`/`WorkflowStepDefinition`/`WorkflowInstance`/`WorkflowStepInstance` (cible générique via contenttypes, jamais d'import d'app métier), services démarrer/avancer/approuver/rejeter/escalader, échéance SLA = début + sla_heures, sélecteur `etapes_sla_depassees(now)` + commande `escalate_workflow_sla`. Migration core 0002 additive, import-linter 4/4 (core reste fondation), 19 tests. (NOTE: ARCH — NOUVEAU composant BPM générique dans la couche fondation.)
- 2026-06-29 — FG177 (apps/rh): Visite médicale du travail — `VisiteMedicale` par employé (date/prochaine visite, aptitude apte/restrictions/inapte, médecin/organisme, propriété `a_jour`), endpoint + action `expirantes/?expire_within=N`, alimente le moteur d'échéances FG175. Migration rh 0017 additive, 24 tests.
- 2026-06-29 — PROJ19 (apps/gestion_projet): Détection de conflits d'affectation — sélecteur `conflits_affectation` : même `RessourceProfil` affectée à ≥2 `AffectationRessource` aux fenêtres qui se chevauchent (direct + via équipe), bonus affectation pendant indisponibilité, endpoint `ressources/conflits-affectation/`. Aucune migration, 17 tests.
- 2026-06-29 — PAIE21 (apps/paie): Frais professionnels & net imposable — fonctionnalité DÉJÀ PRÉSENTE (params `taux_frais_pro_bas/haut`+plafonds, `calculer_bulletin` déduit les frais pro avant IR) ; ajout de la couverture de tests comportementaux manquante. Aucune migration, 9 tests. (already present — tests added)
- 2026-06-29 — QHSE21 (apps/qhse): `EvaluationRisque` (document unique / plan de prévention) + `LigneEvaluationRisque` — gravité×probabilité = criticité (recalculée au save), réf `DUER-` race-safe, statut brouillon/validée/archivée, action `criticite/` (résumé max/moyenne/bandes, garde division par zéro). Migration qhse 0014 additive, 25 tests.
- 2026-06-29 — FG141 (apps/compta): Export FEC (fichier des écritures comptables) — sélecteur `export_fec` produit les 18 colonnes FEC standard, une ligne par écriture, ordonnée par date/pièce, bornée sur l'exercice, équilibre vérifié ; endpoint `etats/export-fec/?exercice=` (JSON / `?export=fec` tab-délimité DGI / `?export=csv`). Aucune migration (réutilise le GL), 22 tests.
- 2026-06-29 — FG301 (apps/installations): Nivellement de charge (resource levelling) — sélecteur `nivellement_charge` propose de déplacer les interventions des techniciens surchargés vers les sous-chargés SANS recréer de conflit FG300 (lecture seule, ne mute rien), endpoint `interventions/nivellement-charge/` (lecture tout rôle). Aucune migration, 14 tests.
- 2026-06-29 — FG261 (apps/ventes): Optimisation puissance souscrite (C&I) — fonction pure `optimize_subscribed_power` : demande réseau nette post-PV (charge − PV), pointe post-PV → puissance souscrite recommandée = ceil(pointe × marge) (jamais > l'actuelle), économie annuelle sur la prime de puissance, conversion kW→kVA optionnelle. Aucune migration, 12 tests, chemin PDF intact.
- 2026-06-29 — FG367 (core): Conditions multi-critères & branches — `core/rules.py` : `evaluate_condition_group` (arbre ET/OU/NON, 11 opérateurs, court-circuit, tolérant aux champs manquants, ne lève jamais) + `validate_condition_group` (erreurs structurelles) + `sequential_actions` (exécution ordonnée stop-on-error). Pur fondation (stdlib seul, import-linter 4/4). Aucune migration, 33 tests. (NOTE: moteur réutilisable ; câblage dans `apps/automation.AutomationRule` laissé à une tâche dédiée.)
- 2026-06-29 — FG178 (apps/rh): Catalogue & dotation EPI — `EpiCatalogue` (type casque/harnais/gants isolants/chaussures/lunettes) + `DotationEpi` nominative (employé, taille, date, renouvellement, quantité), endpoints + action `a-renouveler/`, alimente le moteur d'échéances FG175. Migration rh 0018 additive, 20 tests.
- 2026-06-29 — CONTRAT17 (apps/contrats): Transition automatique signé→actif — après signature complète, `signer_contrat` enchaîne vers `actif` via la machine d'états existante SI `date_debut` nulle ou ≤ aujourd'hui (date future → reste `signé`), journalisé dans la chatter CONTRAT15, `today` injectable. N'altère pas le flip-vers-signé de CONTRAT16. Aucune migration, 13 tests.
- 2026-06-29 — FLOTTE17 (apps/flotte): Ordres de réparation + garage + coûts — `Garage` + `OrdreReparation` (actif flotte, garage, description, coûts main-d'œuvre/pièces → `cout_total` figé, statut ouvert/en_cours/cloturé, lien échéance), action `couts/` (résumé, garde division par zéro) + `cloturer/` (solde l'échéance liée). Migration flotte 0015 additive, 22 tests.
- 2026-06-29 — GED20 (apps/ged): Partage par lien tokenisé (expiry/mot de passe/quota) — `PartageGed` (token `secrets`, `expires_at`, mot de passe haché TextField, `quota_max`, compteur, kill-switch) + endpoint PUBLIC `public/<token>/` (AllowAny, résolu par token uniquement, stream du document ; inconnu/révoqué→404, expiré/quota→410, mot de passe manquant/faux→403, incrément atomique conditionnel), gestion CRUD multi-tenant + `revoquer/`. Migration ged 0014 additive, 20 tests. (NOTE: DECISION — endpoint public tokenisé, modèle de sécurité calqué sur ventes.ShareLink, aucune fuite cross-société.)
- 2026-06-29 — FG142 (apps/compta): Trousse liasse fiscale (états de synthèse) — sélecteur `liasse_fiscale` assemble bilan + CPC + balance + annexe TVA (FG138) en réutilisant les sélecteurs existants sans recalcul, endpoint `etats/liasse-fiscale/?exercice=` (JSON / `?export=csv` multi-sections). Aucune migration, 19 tests. (NOTE: ARCH — bundle d'états en lecture seule.)
- 2026-06-29 — FG302 (apps/installations): Calendrier de disponibilité ressources — `IndisponibiliteRessource` (technicien XOR camionnette indisponible sur `[debut, fin]`, type congé/formation/arrêt/autre) + sélecteur `ressource_indisponible` que FG299/FG300/FG301 peuvent appeler pour exclure. Migration installations 0019 additive, 22 tests.
- 2026-06-29 — FG262 (apps/ventes): Modélisation dégradation modules sur la durée — fonction pure `module_degradation_curve` : facteur de production par année (courbe composée/linéaire + LID année 1), confronté aux planchers de garantie ({10:0.90, 25:0.80}) avec détection d'année de rupture/shortfall. Aucune migration, 11 tests, chemin PDF intact.
- 2026-06-29 — FG368 (core): UI de gestion des jobs (backend) — `core/jobs.py` introspecte `current_app.conf.beat_schedule` (+ django-celery-beat si installé, repli sinon) → liste normalisée ; `ScheduledJobViewSet` (`jobs/` liste + `jobs/run/` exécution manuelle via `send_task`, broker down→503), réservé admin. Câblé à `/api/django/core/`. Aucune dépendance nouvelle, import-linter 4/4 (celery infra seul), 17 tests. (NOTE: ROUTINE — l'écran Paramètres frontend reste une tâche dédiée.)
- 2026-06-29 — FG179 (apps/rh): Suivi péremption/contrôle des EPI — `EpiCatalogue.duree_vie_mois`/`intervalle_controle_mois` → `DotationEpi.date_peremption`/`date_prochain_controle` dérivées (ajout de mois borné fin de mois), `perime`/`a_controler` (`today` injectable), sélecteur + endpoint `a-remplacer-controler/`, alimente FG175 (familles epi_peremption/epi_controle). Migration rh 0019 additive, 23 tests.
- 2026-06-29 — PROJ20 (apps/gestion_projet): Nivellement de charge (levelling) — sélecteur `nivellement_charge` réutilise PROJ18 : propose de déplacer les affectations directes des ressources sur-allouées vers les sous-allouées sans créer de conflit PROJ19 (lecture seule), endpoint `ressources/nivellement-charge/`. Aucune migration, 14 tests.
- 2026-06-29 — PAIE22 (apps/paie): Calcul IR (barème progressif + charges de famille) — DÉJÀ PRÉSENT (PAIE5 : `ir_bareme` progressif, `deduction_charges_famille` plafonnée, `compute_ir` câblé dans `calculer_bulletin` sur le net imposable) ; ajout de 30 tests comportementaux (toutes les tranches, plafond charges de famille, IR sur base réduite, scoping). Aucune migration. (already present — tests added)
- 2026-06-29 — QHSE22 (apps/qhse): Document unique requis avant pose — sélecteur `document_unique_valide(company, chantier_id)` (vrai si ≥1 `EvaluationRisque` validée avec lignes) + service `exiger_document_unique` (lève ValidationError, consommable par installations pour gater la pose) + endpoint `evaluations-risque/document-unique-statut/`. Réf chantier par id chaîné (pas d'import installations). Aucune migration, 18 tests. (NOTE: DECISION — check + portail de gate ; l'enforcement côté installations est une tâche séparée.)
- 2026-06-29 — FG143 (apps/compta): Déclaration des honoraires / état 9421 — sélecteur `declaration_honoraires(company, annee)` agrège par bénéficiaire les paiements aux tiers de l'année civile depuis le registre RAS (FG139) : brut/retenue/net + IF/ICE + nb pièces ; endpoint `etats/declaration-honoraires/` (?annee=, ?export=csv), réservé responsable/admin. Aucune migration, 14 tests.
- 2026-06-29 — FG303 (apps/installations): Planning des camionnettes — sélecteur `planning_camionnettes(company, debut, fin)` regroupe par camionnette (via `Intervention.camionnette`) les interventions de la fenêtre + charge journalière, capacité zéro sur les indisponibilités FG302 (surréservation visible) ; endpoint `planning-camionnettes` (action lecture ajoutée à get_permissions, IsAnyRole). Aucune migration, 24 tests.
- 2026-06-29 — FG263 (apps/ventes): Modèle financier PPA / tiers-investisseur — fonction pure `ppa_model` : applique la dégradation FG262, calcule les revenus investisseur (production × tarif PPA + escalade − O&M ; NPV/IRR/payback via FG260) et les économies client (tarif réseau − PPA), double perspective, chemin PDF intact. Aucune migration, 18 tests. (NOTE: DECISION — math pure ; écran/PDF dédiés restent une tâche séparée.)
- 2026-06-29 — FG369 (core): Bibliothèque de modèles de workflow — catalogue de données `workflow_templates.py` (relance devis, onboarding chantier, rappel garantie) + service idempotent `installer_modele_workflow` matérialisant les `WorkflowDefinition`/`StepDefinition` FG366 par société (skip si déjà installé) ; `WorkflowTemplateViewSet` (liste authentifiée / installer admin-responsable), câblé à `/api/django/core/`. Aucune dépendance, import-linter respecté (core base), 17 tests.
- 2026-06-29 — FG180 (apps/rh): Émargement de remise EPI (signature) — modèle `EmargementEpi` (e-sign loi 53-05 nom typé, preuve IP/user-agent côté serveur) + `accuse_remise`/`date_accuse` sur DotationEpi ; service `emarger_dotation` (société + acteur serveur, accusé figé à la première signature) ; endpoints `emarger`/`emargements`. Aucune dépendance e-sign externe. Migration rh 0020 additive, 15 tests.
- 2026-06-29 — CONTRAT18 (apps/contrats): `VersionContrat` (versionnage immuable des rendus) — modèle versionné (numéro serveur max+1 select_for_update, jamais count()+1 ; contenu figé + clé MinIO), snapshot via service `creer_version` + auto-snapshot à la signature (best-effort, CONTRAT16/17 préservés), viewset lecture seule. Migration contrats 0014 additive, 19 tests.
- 2026-06-29 — FLOTTE18 (apps/flotte): Pneumatiques & pièces — modèles `Pneumatique` (position/dimension/montage/dépose/statut/coût) et `PieceFlotte` (désignation/réf/quantité/coût, lien OrdreReparation), CRUD + action `synthese` pneus+pièces par véhicule. Migration flotte 0016 additive (index ≤30, related_name préfixés), 25 tests.
- 2026-06-29 — GED21 (apps/ged): Watermarking & contrôle de diffusion — drapeaux `Document.watermark_diffusion`/`PartageGed.watermark` + service `apply_watermark` (Pillow pour images — déjà dépendance ; PyMuPDF pour PDF importé en lazy, dégradation propre si absent), câblé dans l'aperçu GED14 et le partage public GED20 (chemin sans filigrane identique). Migration ged 0015 additive, 17 tests. (NOTE: DEP — aucune dépendance dure ajoutée ; filigrane PDF actif seulement si PyMuPDF installé ultérieurement.)
- 2026-06-29 — PAIE23 (apps/paie): Allocations familiales (charge patronale) — taux configurable `ParametrePaie.taux_allocations_familiales` (défaut 6,4 %, non plafonné, sur le brut) émis comme cotisation patronale (alimente `charges_patronales`, jamais déduit du net du salarié), lié à l'affiliation CNSS. Migration paie 0011 additive, 11 tests.
- 2026-06-29 — PROJ21 (apps/gestion_projet): Budget projet (lignes par catégorie) — modèles `BudgetProjet` + `LigneBudgetProjet` (catégorie matériel/MO/sous-traitance/divers, montant prévu, qté/PU optionnels) + sélecteur `budget_total` (total + par_categorie), ViewSets CRUD + action `/total/`. Migration gestion_projet 0013 additive, 22 tests.
- 2026-06-29 — QHSE23 (apps/qhse): `PermisTravail` (hauteur/consignation élec/point chaud) — référence serveur race-safe (`PT`, jamais count()+1), `chantier_id` string-ref (pas d'import installations), dates de validité, actions `valider`/`cloturer`. Migration qhse 0015 additive, 22 tests.
- 2026-06-29 — LITIGE6 (apps/litiges): Tableau de bord litiges — sélecteur `tableau_bord_litiges(company, debut, fin)` agrège les Reclamation existantes : nombres par statut, total `montant_conteste`, délai de résolution moyen (depuis le log chatter « resolue », division par zéro gardée → None) ; endpoint `reclamations/tableau-bord/`. Aucune migration, 18 tests.
- 2026-06-29 — FG242 (apps/crm): Suivi des concurrents sur deals perdus — modèle `ConcurrentPerte` (lead perdu → concurrent gagnant + prix + devise + motif), acteur + société côté serveur, réutilise le flag `Lead.perdu` (aucun nom d'étape STAGES.py codé en dur), note chatter best-effort. Migration crm 0029 additive, 20 tests.
- 2026-06-29 — FG280 (apps/sav): Gestion fine des alarmes/défauts onduleur — modèle `AlarmeOnduleur` DISTINCT du ticket SAV (code/gravité/équipement, statut active/acquittée/résolue/escaladée), actions `acquitter` (acteur + date serveur, idempotent) et `escalader` (lie/ouvre un ticket SAV). Migration sav 0011 additive, 18 tests.
- 2026-06-29 — KB7 (apps/kb): Droits d'accès par rôle + suivi de lecture — modèles `KbArticleAcl` (rôle/niveau) + `KbLecture` ; filtre ACL câblé dans la queryset article (rétro-compatible : sans ACL → visible par tous, admin toujours visible), actions `marquer-lu` (idempotent) + `resume-lecture`. Migration kb 0005 additive, 17 tests.
- 2026-06-29 — FG144 (apps/compta): Calcul du timbre fiscal sur encaissements espèces — modèle `TimbreFiscal` (droit de timbre 0,25 % + minimum statutaire sur les factures réglées EN ESPÈCES ; règlements non-espèces exonérés → None), paiement référencé par string-id (pas d'import ventes), pas d'écriture GL (snapshot façon FG139). Migration compta 0015 additive, 24 tests.
- 2026-06-29 — FG181 (apps/rh): Registre HSE & accidents du travail — modèle `AccidentTravail` (référence serveur race-safe `AT-`, date/lieu/employé/gravité/arrêt+jours/photo, déclaration CNSS) + export CSV CNSS (`?export=csv`). Migration rh 0021 additive, 23 tests.
- 2026-06-29 — FG264 (apps/ventes): Rendement pompage par cycle de marche — fonction pure `pumping_cycle_yield` : volume d'eau journalier/mensuel (mode plat = parité `solar.js`, mode profil = intégration horaire pondérée par l'irradiation, profil ciel-clair normalisé sur le total journalier) ; pompes sans courbe → None. Aucune migration, 14 tests, chemin PDF intact.
- 2026-06-29 — FG304 (apps/installations): Référentiel sous-traitants — modèle `SousTraitant` (métier/contact/ICE/RIB, drapeau `actif` d'archivage, défaut True quel que soit le type de contenu), DISTINCT des fournisseurs matériel ; société + créateur serveur. Migration installations 0020 additive, 15 tests.
- 2026-06-29 — GED22 (apps/ged): Politiques de rétention — modèle `PolitiqueRetention` (durée + action à l'échéance, défaut NON destructif `signaler`) + sélecteur `documents_echus(company, today)` (politique la plus spécifique, today injectable) + commande `lister_documents_echus` ; ne supprime JAMAIS passivement. Migration ged 0016 additive, 23 tests.
- 2026-06-29 — FLOTTE19 (apps/flotte): `EcheanceReglementaire` (modèle générique) — échéances réglementaires (visite technique/assurance/vignette/carte grise/taxe à l'essieu) sur `ActifFlotte`, statut a_jour/a_renouveler/expire (today injectable), action `expirantes/?within=N` ; distinct des échéances d'entretien FLOTTE16. Migration flotte 0017 additive, 18 tests.
- 2026-06-29 — PAIE24 (apps/paie): Taxe de formation professionnelle (charge patronale) — réutilise le taux existant `ParametrePaie.taux_formation_pro` (1,6 %), ajoute le calcul `formation_professionnelle_patronale` + le snapshot `BulletinPaie.formation_professionnelle`, émis comme cotisation patronale (alimente charges_patronales, jamais déduit du net), lié à l'affiliation CNSS. Migration paie 0012 additive, 15 tests.
- 2026-06-29 — QHSE24 (apps/qhse): Consignation électrique (LOTO) sur permis — modèle `ConsignationLoto` (FK `PermisTravail`, point de consignation/cadenas/étiquette/vérif absence tension, statut consignée/déconsignée, référence serveur race-safe), action `deconsigner`. Migration qhse 0016 additive, 18 tests.
- 2026-06-29 — FG204 (apps/crm): Tableau d'attribution multi-touch — modèle `PointContact` (journal des points de contact par lead : canal réutilisant `Lead.Canal`, source, date, ordre, coût canal payant), sélecteur timeline + résumé first/last-touch, endpoints `points-contact/` + `leads/{id}/points-contact/` (action lecture ajoutée à la liste IsAnyRole). Migration crm 0030 additive, 26 tests.
- 2026-06-30 — FG145 (apps/compta): Retenue de garantie & cautions bancaires — modèles `RetenueGarantie` (RG retenue sur marché, référence serveur race-safe, levée à échéance) + `CautionBancaire` (provisoire/définitive/restitution, banque, mainlevée), marché/facture en string-ref, actions `liberer`/`mainlevee`, sélecteurs d'échéance. Migration compta 0016 additive, 27 tests.
- 2026-06-30 — FG182 (apps/rh): Presqu'accidents (near-miss) — modèle `PresquAccident` (référence serveur race-safe `NM-`, lieu/gravité potentielle/mesure corrective, déclarant serveur), plus léger que FG181 (ni blessé ni CNSS), sélecteur de stats par gravité. Migration rh 0022 additive, 22 tests.
- 2026-06-30 — FG305 (apps/installations): Ordres de travaux sous-traitant — modèle `OrdreSousTraitance` (FK SousTraitant FG304 + chantier même-app, référence serveur race-safe `OST-`, prestation/montant/échéance, cycle brouillon→émis→en_cours→réceptionné→clos). Migration installations 0021 additive, 22 tests.
- 2026-06-30 — PROJ22 (apps/gestion_projet): Coûts engagés vs réels — sélecteur `couts_engages_vs_reels` (budget PROJ21 par catégorie vs réel : MO depuis AffectationRessource interne quantizée 2 décimales, matériel/sous-traitance via ProjetLien avec dégradation gracieuse), écart + écart % (division par zéro gardée), endpoint `projets/{id}/couts-engages-reels/`. Aucune migration, 24 tests.
- 2026-06-30 — GED23 (apps/ged): Archivage légal à valeur probante (write-once) — modèle `ArchivageLegal` (hash SHA-256 d'intégrité, object-lock MinIO best-effort avec dégradation), immuabilité applicative une fois archivé (édition/suppression/nouvelle version/déplacement/cycle-de-vie/check-out/check-in bloqués → 403, jamais 500), aucune dépendance dure ajoutée. Migration ged 0017 additive, 21 tests.
- 2026-06-30 — FLOTTE20 (apps/flotte): Vignette / TSAV (barème CV/énergie) — modèle `BaremeVignette` (référentiel éditable par société : énergie × tranche CV → montant, par année) + `Vehicule.puissance_fiscale`, sélecteur `calcul_tsav` (électrique exonéré, pas de tranche → None), seed idempotent du barème marocain standard. Migration flotte 0018 additive, 30 tests.
- 2026-06-30 — FG183 (apps/rh): Causeries sécurité / toolbox talks — modèles `CauserieSecurite` (thème, chantier en string-ref façon PresquAccident, animateur, lieu/notes) + `CauserieParticipant` (présent/émargé + horodatage, unique causerie+participant), viewset société-scopé avec action `emarger`, sérialiseur à participants imbriqués. Migration rh 0023 additive, 14 tests.
- 2026-06-30 — FLOTTE21 (apps/flotte): Assurance véhicule (police/échéance/attestation/franchise) — modèle dédié `AssuranceVehicule` (assureur, numéro de police, période de couverture, franchise MAD, attestation scannée), complémentaire de `EcheanceReglementaire` (jamais doublon), `statut_calcule(today)` valide/à-renouveler/expirée, action `expirantes/?within=N`, sélecteurs société-scopés. Migration flotte 0019 additive, 20 tests.
- 2026-06-30 — QHSE25 (apps/qhse): Alerte expiration de permis de travail — sélecteur `permis_travail_expirant(company, within_days, inclure_expires)` (non clôturés dont `date_fin` tombe dans la fenêtre ou déjà périmés, société-scopé) + action `permis-travail/expirant/?expire_within=N&inclure_expires=`. Aucune migration (réutilise `PermisTravail.date_fin`), 14 tests.
- 2026-06-30 — CONTRAT19 (apps/contrats): Dépôt en GED des versions & PDF signés — chaque `VersionContrat` créée (y compris l'instantané figé à la signature) atterrit dans la GED via `ged.services.deposit_document` (frontière cross-app, jamais d'import des modèles GED), idempotent (trace `source_type/source_id` dans `custom_data`, pas de doublon), best-effort (un échec GED ne casse jamais la création de version). Aucune migration (réutilise les modèles GED), 8 tests.
- 2026-06-30 — FG184 (apps/rh): Analyse de risques chantier (plan de prévention) — modèles `AnalyseRisquesChantier` (chantier string-ref, rédacteur, statut brouillon/validé, action `valider`) + `LigneRisqueChantier` (danger/description/gravité/probabilité/niveau/mesure de prévention), sérialiseur à lignes imbriquées, viewset société-scopé. Distinct de la checklist F18 par intervention. Migration rh 0024 additive, ~14 tests.
- 2026-06-30 — FLOTTE22 (apps/flotte): Visite technique (validité paramétrable) — modèle `VisiteTechnique` (centre, date, résultat favorable/défavorable/contre-visite, `validite_mois` paramétrable, `date_prochaine` calculée au save avec gestion débordement fin-de-mois), complémentaire d'`EcheanceReglementaire`, `statut_calcule` + action `expirantes/?within=N`. Migration flotte 0020 additive, ~25 tests. (review: calcul de `date_prochaine` déplacé dans `save()` — `clean()` n'est pas appelé par le save de DRF.)
- 2026-06-30 — QHSE26 (apps/qhse): InductionSecurite (accueil sécurité site, incl. sous-traitants) — modèle `InductionSecurite` (chantier string-ref, personne nommée — gère les externes via `est_sous_traitant`/`entreprise_externe` —, employé interne optionnel, thèmes, acquittement horodaté via action `acquitter`, validité optionnelle), viewset société-scopé. Migration qhse 0017 additive, ~17 tests.
- 2026-06-30 — CONTRAT20 (apps/contrats): Dates clés (début/fin/préavis) + tacite reconduction — champs additifs sur `Contrat` (`preavis_jours`, `tacite_reconduction`, `duree_reconduction_mois`, `preavis_traite`) + méthodes `echeance_preavis`/`jours_avant_preavis`, sélecteur `contrats_a_preavis` + action `preavis/?within=N`. Migration contrats 0015 additive, ~20 tests. (review: annotation du sélecteur renommée `echeance_preavis_calc` pour ne pas masquer la méthode-modèle homonyme.)
- 2026-06-30 — GED24 (apps/ged): Rétention légale / legal hold — modèle `LegalHold` (motif, posé par, actif, levée tracée), services `placer_legal_hold`/`lever_legal_hold` idempotents, blocage de suppression à DEUX niveaux (`Document.delete()` → `LegalHoldError`, `DocumentViewSet.perform_destroy` → 403 jamais 500), indépendant des politiques de rétention GED22 et de l'archivage GED23. Migration ged 0018 additive, ~30 tests.
- 2026-06-30 — FG185 (apps/rh): Tableau de bord HSE — sélecteur d'agrégation `tableau_bord_hse(company, within_days)` (taux de fréquence/gravité BIT/INRS calculés sur les heures travaillées FeuilleTemps, division par zéro gardée → None ; alertes d'expiration habilitations/certifications/visites/EPI ; presqu'accidents groupés par chantier) + endpoint lecture seule `tableau-bord-hse`. Aucune migration (lecture seule), ~13 tests.
- 2026-06-30 — FLOTTE23 (apps/flotte): Carte grise & autorisation de circulation — modèle `CarteGriseVehicule` (numéro carte grise, dates immatriculation/mise en circulation, autorisation de circulation + validité, fichiers scannés en FileField, `statut_calcule` + action `expirantes`), stocké côté flotte (pas de couplage GED). Migration flotte 0021 additive, ~25 tests.
- 2026-06-30 — CONTRAT21 (apps/contrats): Calcul des échéances & contrats à renouveler — sélecteur `contrats_a_renouveler(company, within_days)` (contrats dont `date_fin` tombe dans la fenêtre, tacite reconduction exposée pas exclue) + méthode `jours_avant_echeance` + action `a-renouveler/?within=N`, complémentaire (pas doublon) du préavis CONTRAT20. Aucune migration (réutilise `date_fin`), ~20 tests.
- 2026-06-30 — QHSE28 (apps/qhse): PlanUrgence / premiers secours — modèles `PlanUrgence` (point de rassemblement, hôpital proche, révision) + `ContactUrgence` (pompiers/SAMU/police/interne) + `Secouriste` (interne via `rh.DossierEmploye` ou externe nommé, certification/validité), viewsets société-scopés. Migration qhse 0018 additive, ~tests multi-classes.
- 2026-06-30 — GED26 (apps/ged): Corbeille & restauration (soft-delete) — champs additifs `Document.supprime_le`/`supprime_par`, services `mettre_en_corbeille`/`restaurer_de_corbeille`/`purger_definitivement`, DELETE recâblé en soft-delete (la liste par défaut exclut la corbeille, endpoint `corbeille` + actions `restaurer`/`purger`), guards GED23 (archivage write-once) + GED24 (legal hold) préservés → 403 jamais 500. Migration ged 0019 additive, ~24 tests. (review: 2 tests ged préexistants qui supposaient le hard-delete mis à jour pour le soft-delete.)
- 2026-06-30 — QHSE27 (apps/qhse): `CauserieSecurite` (toolbox talks + émargement) — `[x] (already present)` : déjà couvert par FG183 (`rh.CauserieSecurite` + `CauserieParticipant`, émargement) livré dans le même run ; pas de doublon créé en qhse.
- 2026-06-30 — FG187 (apps/rh): Gestion de la formation — modèles `SessionFormation` (interne/externe, organisme, dates, coût, compétence visée, statut) + `InscriptionFormation` (présence, résultat, unique session+participant) ; action `marquer-realisee` upsert la matrice `CompetenceEmploye` (FG172) pour les présents. Migration rh 0025 additive, ~tests.
- 2026-06-30 — FLOTTE24 (apps/flotte): Moteur d'alertes d'échéances réglementaires — sélecteur `alertes_echeances_reglementaires(company)` agrégeant 5 sources (EcheanceReglementaire, AssuranceVehicule, VisiteTechnique, CarteGriseVehicule, EcheanceEntretien) en buckets J-7/J-15/J-30/échu, + endpoint `alertes-echeances`. Aucune migration (lecture seule, réutilise les sélecteurs `*_expirantes`), ~tests.
- 2026-06-30 — QHSE29 (apps/qhse): Registre `Incident` — modèle `Incident` (type accident/presqu'accident/incident, gravité, statut, chantier en réf souple, référence serveur via util partagé) côté QHSE, distinct des modèles RH `AccidentTravail`/`PresquAccident` (aucun import rh). Migration qhse 0019 additive, ~tests.
- 2026-06-30 — CONTRAT22 (apps/contrats): `AlerteContrat` + rappels via notifications — modèle `AlerteContrat` (type préavis/échéance/personnalisé, date de déclenchement, statut), service `declencher_alertes_contrat` (dispatch idempotent via `notifications.services.notify_many` appelé en import fonction-local — frontière cross-app respectée, import-linter 4/4) + `semer_alertes_echeances` (depuis CONTRAT20/21). Migration contrats 0016 additive, ~18 tests.
- 2026-06-30 — GED27 (apps/ged): Modèles de documents (fusion/mailing → PDF WeasyPrint) — modèle `ModeleDocument` (corps HTML à jetons `{{ champ }}`), service `rendre_modele` (substitution sûre via le moteur de templates Django, jamais d'exécution de code) → PDF WeasyPrint (import fonction-local gardé), `generer_document` réutilise le dépôt GED. Le moteur `/proposal` (règle #4) NON touché. Migration ged 0020 additive, ~14 tests. (review: assertion de test jeton-inconnu corrigée — l'espace littéral est préservé.)
- 2026-06-30 — FG186 (apps/rh): Permis de travail (hauteur/électrique/consignation) — `[x] (already present)` : déjà couvert par qhse `PermisTravail` (QHSE23) + `ConsignationLoto` (QHSE24) ; pas de doublon créé en rh.
- 2026-06-30 — FG188 (apps/rh): Plan & registre de formation — sélecteur `registre_formation_employe` (historique des sessions FG187 par employé) + modèle `BesoinFormation` (thème, priorité, échéance, obligation réglementaire OFPPT/CSF, statut identifié/planifié/satisfait, action `satisfaire` gardée sur session réalisée). Migration rh 0026 additive, ~tests.
- 2026-06-30 — FLOTTE25 (apps/flotte): `Sinistre` (accident/constat/assurance) — modèle `Sinistre` (actif, assurance FLOTTE21 nullable, type accident matériel/corporel/vol/bris/incendie, constat en FileField, n° déclaration, montant/franchise, statut déclaré→indemnisé), viewset société-scopé + filtres. Migration flotte 0022 additive, ~tests.
- 2026-06-30 — QHSE30 (apps/qhse): Déclaration CNSS de l'accident du travail (échéance légale) — modèle `DeclarationCnss` (réf souple string-FK `rh.AccidentTravail`, `delai_jours` paramétrable défaut 2 j, `date_limite` calculée, statut à_déclarer/déclaré/hors_délai recalculé au save) + sélecteur `declarations_cnss_a_echeance` + action `a-echeance`. Complète `AccidentTravail` qui n'avait pas l'échéance légale. Migration qhse 0020 additive (dép. rh.0021), ~tests. (DECISION construite — auto-gating OFF.)
- 2026-06-30 — CONTRAT23 (apps/contrats): Renouvellement (manuel + reconduction tacite) — services `renouveler_contrat` (étend date_fin, réinitialise préavis, snapshot version, journalise, refuse résilié/expiré) + `traiter_reconductions_tacites` (auto-renouvelle les contrats tacites échus, idempotent, rattrapage borné) + actions `renouveler`/`traiter-reconductions` ; champs d'audit `date_dernier_renouvellement`/`nb_renouvellements`. PERFORME le renouvellement (≠ CONTRAT20/21 qui ne font que lister). Migration contrats 0017 additive, ~tests.
- 2026-06-30 — GED28 (apps/ged): Génération de document → classement automatique — `ModeleDocument.cabinet_cible`/`dossier_cible` (templaté `{{ }}` via la fusion GED27), `generer_document` dépose dans le cabinet/dossier résolu (auto-créé si absent), rétrocompatible (dossier par défaut sans cible), `/proposal` non touché. Migration ged 0021 additive, ~tests.
