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
- [ ] N91 — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception signature, syncing when back online. (UNBLOCKED 2026-06-21 — the dev-field-exec routing was stale: the whole field-execution backend it extends is already on `main` (F9–F23, `apps/installations/models_field.py`), and worktree isolation already prevents branch collisions, so build it as a normal worktree lane. The PWA/service-worker foundation exists (`frontend/src/sw.js`). Approach: IndexedDB/localStorage outbox + idempotent sync endpoints, last-write-wins on reconnect. Coupled with F21 — same lane.) (ARCH)
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

- [ ] F21 — **Offline-tolerant field capture** covering the whole intervention flow — préparation checklist, GPS check-in, photos, serial capture, voice memos, Matériel consommé, réserves, and the signature — queuing locally on a poor connection and syncing when back online (extends the planned offline field capture to the full intervention workflow). (UNBLOCKED 2026-06-21 — same as N91: the dev-field-exec routing is stale (backend already on `main`, worktree isolation prevents collisions); build N91 + F21 in one offline-sync worktree lane.) (ARCH) (@after: N91)

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
- [ ] M4 — Formalise the three layers (foundation: authentication/roles/records/customfields/core · domain core: crm/stock/ventes/installations/sav · satellites: reporting/automation/monitoring/notifications/publicapi/audit/documents/dataimport/contact) and remove the one back-edge `ventes → audit` by moving that audit capture onto the M6 event bus. Fait = `ventes` no longer imports `apps.audit`; the layer map is written down; behaviour unchanged; tests pass. (UNBLOCKED 2026-06-21 — **RECOMMENDED APPROACH:** `ventes` already depends on `core/events.py` (for `devis_accepted`); have it EMIT a `document_pdf_generated(instance, kind)` event from the 2 PDF action sites (`apps/ventes/views/devis.py`, `views/facture.py`) and have the `audit` app SUBSCRIBE in its `apps.py ready()` and call `record(AuditLog.Action.PDF, …)`. Synchronous, behaviour-identical, no new model — reuses the existing `AuditLog.Action.PDF` enum. The old blocker's "no model-save to hook to" objection is moot: emit an explicit event, not a save signal.)
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
- [ ] FG5 — Working-hours + Moroccan public-holiday calendar feeding planning/relance. No working-hours/holiday model exists anywhere — relance/intervention/maintenance dates can land on Fridays/holidays. Add `WorkingHoursConfig` + `Holiday` (per company, seed MA public holidays) + helpers consumed by date computation. (Gate: SCHEMA + DECISION on which features skip non-working days.)
- [ ] FG6 — ICS/iCal calendar feed per user. `reporting/calendar.py` is JSON-only; no `text/calendar` anywhere. Add `GET reporting/calendar.ics?token=<per-user>` (poses/interventions/maintenance visits) + "S'abonner au calendrier" in `CalendarPage.jsx` so the agenda shows in Google/Outlook on technicians' phones. (Gate: ROUTINE; DECISION on the token scheme.)
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
- [ ] FG39 — Sales objectives & KPI targets vs actuals. No target/objective concept exists anywhere; KPIs show actuals with no goal line. Add `ObjectifCommercial`/`KpiTarget` (company, owner/metric, period, cible) + a "objectif vs réalisé" panel per commercial and company-wide attainment gauges on the dashboard. (Gate: SCHEMA + DECISION on metrics/periods.)

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
- [ ] FG49 — Account-coded accounting export (PCG/Sage layout). `exports.py` gives a journal + per-rate TVA summary but no general-ledger export with account codes (7xxx ventes / 4455 TVA / 3421 clients) for direct fiduciaire import. Add a third export format mapping buckets to configurable account codes. (Gate: ROUTINE + DECISION on default codes.)
- [ ] FG50 — Acompte transfer/refund on invoice cancel. `annuler` leaves a cancelled invoice's `Paiement` rows stuck on a dead invoice with no transfer/refund path. On cancel, offer "transférer l'acompte" to another facture of the same devis or mark refundable (negative Paiement / Avoir), with chatter. (Gate: DECISION (accounting semantics) + SCHEMA.)
- [ ] FG51 — Proof-of-delivery gate before invoicing. `BonCommande.marquer_livre` flips status + decrements stock but captures no PV/signature, and `generer-facture` never checks delivery happened. Optionally link a `documents` PV/attachment to the BC + a soft warning on the matériel tranche when no delivery proof exists. (Gate: ARCH/DECISION; route cross-app via selectors.)
- [ ] FG52 — Multi-currency quoting/invoicing. Everything is hardcoded MAD (no `devise`/`taux_change` on Devis/Facture, none in CompanyProfile, UBL hardcodes currency). Add `devise`(default MAD)+`taux_change` carried through the PDF builder + `dgi_export.py`. (Gate: SCHEMA + DECISION on currencies + legal-MAD-equivalent rules.)
- [ ] FG53 — E-payment "Payer en ligne" link. No payment gateway anywhere; ShareLink/WhatsApp/relance deliver a read-only PDF only. Add a `PaymentLink` model + a provider-interface (NoOp default, like `monitoring/providers`, no dep when unconfigured) + a public pay page + a webhook that records a `Paiement`. (Gate: DEP:<gateway SDK> + COST + AUTH — propose the NoOp scaffold now, live gateway gated.)

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
- [ ] FG70 — Auto warranty handover at RECEPTIONNE. At réception the code only writes a chatter note; it doesn't sweep the frozen `bom` into `sav.Equipement` for serial-less components, so warranty coverage depends on a tech remembering each serial. On the RECEPTIONNE transition call a `sav.services` fn to ensure one `Equipement` per BoM line (serial optional, date_pose=date_reception, idempotent) + a handover summary/PDF section. (Gate: ROUTINE; cross-app write via services.)
- [ ] FG71 — Per-chantier job-costing roll-up. The pieces exist (`labour_jours_estimes/reels`, `MaterielConsommation` variance, `prix_achat`) but nothing assembles labour + real material cost vs the devis total into a margin view. Add `chantiers/{id}/cout` (labour estimé/réel + materials BoM-vs-real + devis total → margin), **internal/admin-only** (margin ban on client docs). (Gate: DECISION confirm internal-only; else ROUTINE.)
- [x] FG72 — Multi-day chantier planning. `Installation` has single `date_pose_prevue/reelle`; a multi-day pose is counted as one day and overbooks the crew. Add `date_pose_fin_prevue`/`duree_pose_jours`, rendered as a span on the chantier calendar + factored into capacity. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG73 — Technician day route/itinerary. `MaJourneePage` lists today's interventions in date order with no geographic ordering; `haversine_km` + site GPS already exist. Add a nearest-neighbour ordering from the dépôt + a per-stop "Itinéraire" maps deep-link (and optional `interventions/ma-tournee`). (Gate: ROUTINE; DEP only if true road optimization is wanted.)  [DONE 2026-06-21]
- [x] FG74 — Cross-chantier Gantt / milestone timeline. `ChantierTimeline` is single-chantier; a PM running 10–30 concurrent chantiers has no horizontal timeline across the existing milestone dates. Add a `gantt` view (one row per chantier, bars from milestone dates) — read-only first. (Gate: ROUTINE; no new backend.)  [DONE 2026-06-21]
- [x] FG75 — Roof/drone site-survey attachment surface on the chantier. Field photos are intervention-phase only; there's no chantier-level pre-pose "Relevé de toiture / drone" gallery distinct from the day-of shot list. Add a chantier-level attachments panel (category `releve_toiture`/`drone`) reusing `records.Attachment` + the MinIO proxy. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG76 — Photo-required gate on chantier checklist steps. F8 photo-gating is intervention-only; a chantier step ("Panneaux posés") can be ticked with zero evidence. Add `photo_obligatoire` to `ChecklistEtapeModele`/`ChantierChecklistItem` and block `fait=True` until a phase photo exists (mirror the intervention logic). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [ ] FG77 — Pre-pose readiness check. Chantier status can move to EN_COURS freely with no guard on material availability or the 82-21 dossier. Add a `chantiers/{id}/readiness` selector (material shortfall via besoin-materiel, dossier status, planning date) surfaced as a banner in InstallationDetail; optionally a confirm-to-override. (Gate: ROUTINE advisory / DECISION if it should hard-block.)
- [x] FG78 — Intervention RDV confirmation + reschedule/no-show tracking. `Intervention` has dates but no client-confirmation flag, reschedule history, or no-show reason (statut state machine stays untouched — these are metadata). Add `rdv_confirme`/`rdv_confirme_le` + a reschedule count + a "Confirmer le RDV" action feeding reminders. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG79 — Auto-scaffold the standard intervention chain from chantier type. Checklist templates auto-select by type and kits by intervention type, but the expected sequence of visits (résidentiel réseau → pose/raccordement/mise en service) is created one-by-one. Add a `TypeInterventionPlan` (per type_installation, ordered intervention types) + a `creer-interventions-standard` action materializing the chain. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG80 — Outillage calibration/inspection tracking. `Outillage` tracks statut/emplacement/date_achat but no calibration/inspection dates — multimètres, earth testers, and harnais (EPI) legally need periodic checks (a safety/compliance liability). Add `date_derniere_calibration`/`intervalle_calibration_mois`/`date_prochaine_calibration` + an "à calibrer" badge + a notification event. (Gate: SCHEMA.)  [DONE 2026-06-21]

### SAV / parc / maintenance / monitoring

- [x] FG81 — Server-side ticket SLA (response/resolution clocks + breach). SLA is client-side cosmetic only; `Ticket` has no first-response timestamp, no target, no breach flag, and `SAV_TICKET_BREACHING` is never emitted. Add `Ticket.date_premiere_reponse` + per-company `sla_response_days`/`sla_resolution_days` (or a `sav_sla` JSON per priorité) + computed `sla_breach`/`sla_due_at` + a daily breach scan → notification. (Gate: SCHEMA; pairs with FG1.)  [DONE 2026-06-21]
- [x] FG82 — Maintenance-visit checklist / structured visit report. Preventive tickets + the maintenance PDF carry no inspection checklist (clean panels, torque, inverter logs, earth test) — the report is free text. Add `MaintenanceChecklistTemplate`/`Item` (per-company, seeded) + per-ticket `TicketChecklistItem`, rendered into the maintenance PDF (mirror the installations checklist pattern). (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG83 — Supplier warranty-claim (RMA) workflow. A ticket knows `sous_garantie` + equipment + supplier, but there's no claim object — so in-warranty defects sent back to the OEM (Huawei/VEICHI/panel maker) are untracked and the installer eats replacement cost. Add `WarrantyClaim` (equipement, fournisseur, ticket, statut, rma_ref, dates, resolution remplacement/avoir, internal cout_recupere) routed to the supplier via `stock.selectors`. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [x] FG84 — Per-system production history chart + expected-vs-actual + CSV. `ProductionPage` is a flat manual-entry list — no chart, trend, or expected-vs-actual surfaced, though readings + an expected ratio exist. Add `monitoring/configs/{id}/history/` (monthly aggregated + expected overlay) + a Recharts line chart + CSV export per installation. (Gate: ROUTINE; recharts already a dep.)  [DONE 2026-06-21]
- [x] FG85 — Equipment QR labels + scan-to-equipment/ticket. The QR/CODE128 engine + resolve endpoint exist only for `stock.produits`; SAV equipment has a serial but no scannable label and no `EQUIP:` token. Add `equipement_token` + an `EquipementViewSet.etiquettes` action (reuse `labels.render_labels_html`) + extend `resolve_code` to `EQUIP:<id>` (warranty clock + open tickets / open a ticket). (Gate: ROUTINE; reuses the label engine.)  [DONE 2026-06-21]
- [ ] FG86 — Public tokenized "track your SAV request" link. Quotes/invoices have public tokenized links but tickets aren't exposed publicly at all. Add `Ticket.share_token` + a read-only public endpoint returning reference/statut/last-update only (never `cout` or internal chatter) + a "Lien client" button. (Gate: SCHEMA + DECISION on what a client may see.)
- [x] FG87 — SAV knowledge base (resolution playbooks). No KB exists; ticket resolutions evaporate as free-text chatter though solar faults repeat (inverter error codes, string faults). Add `KbArticle` (per-company titre/corps/tags + optional produit/categorie) + a searchable panel on TicketsPage filtered by the ticket's equipment product. (Gate: SCHEMA.)  [DONE 2026-06-21]
- [ ] FG88 — Maintenance route/day planning for preventive visits. Visits generated from contracts spawn undated, ungrouped tickets though installation GPS exists. Add a "planifier la tournée" view listing due preventive tickets with GPS, letting a responsable bulk-assign technician+date (proximity-sorted from stored coordinates). (Gate: ROUTINE coordinate-sort; DEP/COST only for real routing.)
- [x] FG89 — Spare-parts forecasting from PieceConsommee history. `PieceConsommee` records SAV part usage + decrements stock but nothing aggregates it to forecast spares (fuses, MC4, breakers) — a stuck tech means a second truck roll. Add `insights/sav-parts-forecast/` (consumption per product over a window + suggested reorder qty), internal-only. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG90 — Chronic/repeat-failure equipment flag. A ticket links one equipment + exposes open-ticket count, but there's no detection of an item generating repeated tickets over time (a "lemon" — the strongest warranty-claim evidence, ties to FG83). Add a computed `nb_tickets_12m` to the serializer + a filter/badge + an optional repeat-offender insight. (Gate: ROUTINE.)  [DONE 2026-06-21]

### Reporting / analytics / custom fields

- [x] FG91 — SavedReport frontend (CRUD + schedule + optional dashboard pin). The `SavedReport` model + viewset + scheduled-email beat job are fully built but have **zero frontend** (and no `pinned` field) — a shipped backend feature is unusable. Add `reportingApi` methods + a "Mes rapports" UI (create/name/schedule/recipients/delete) + optional `pinned` to render a saved report as a dashboard card. (Gate: ROUTINE; SCHEMA only for the pin field.)  [DONE 2026-06-21]
- [x] FG92 — Period comparison (MoM/YoY) on dashboard & reports. Nothing computes a prior-period baseline anywhere. Add a `compare=prev|yoy` param to `dashboard/` + `reports/*` returning `{current, previous, delta_pct}` per KPI + arrows/deltas on the Stat cards. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG93 — Sales-rep leaderboard. `sales_report` has a flat per-responsable count table but no monetary leaderboard (CA signed, win rate, avg deal, kWc per rep) and it's not surfaced on the dashboard. Add `insights/sales-leaderboard/` + a "Classement commerciaux" card (responsable-visible; keep commission/buy-price admin-only). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG94 — Activate custom-field reporting. `CustomFieldDef.visible_liste` is settable but **nothing consumes it** — no list column, no `custom_data` filter, no aggregation (dead flag). Honor `visible_liste` as a column + a `?cf_<code>=` filter on Lead/Client/Produit lists + a group-by-custom-field count. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG95 — PDF export for reports (branded). Every report/insight exports xlsx only; WeasyPrint+Jinja2 are already pinned. Add `?export=pdf` on `reports/*` rendering a company-branded template (logo from CompanyProfile), never buy prices — for presentable monthly reports to stakeholders/banks. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [ ] FG96 — Configurable / per-role dashboard. `Dashboard`/`Reporting` are fully static — a technicien sees the same finance-heavy dashboard as the founder. Add a per-user/per-role widget config (enabled cards + order); minimal first cut = role-default card sets driven off `menu_tier`. (Gate: SCHEMA + DECISION on configurability scope.)
- [x] FG97 — Audit-log analytics. The Journal is a filterable feed + activity buckets but has no rollups (most-active users, action mix over time, failed-login spikes, object churn). Add `audit/analytics/` (gated on `journal_activite_voir`) + a charts panel on the Journal page. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG98 — Cohort / seasonality conversion analysis. No cohort view; solar demand is seasonal + channel-dependent. Add `insights/cohorts/` grouping leads by acquisition month (and/or canal) → eventually-signed % + avg days-to-sign per cohort (heatmap/table). (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG99 — Profitability by segment. `job_costing` is per-chantier only; there's no margin/revenue aggregation by `mode_installation`/`canal`/category. Add `insights/profitability/` (admin-only, reuses `prix_achat` internally, never client-facing) grouping revenue+margin+count by segment. (Gate: ROUTINE.)  [DONE 2026-06-21]
- [x] FG100 — Custom fields for Devis / Chantier / Ticket. `CustomFieldDef.Module` is limited to LEAD/CLIENT/PRODUIT; the operational core can't carry custom attributes ("numéro dossier ONEE", "type de nacelle"). Add INSTALLATION/DEVIS/TICKET to the choices + `custom_data` JSONField where missing + wire validation + Paramètres tabs. (Gate: SCHEMA — additive JSONField.)  [DONE 2026-06-21]
- [x] FG101 — Drill-down from report rows/charts to filtered lists. Dashboard KPI Stats are clickable but report tables/charts are dead ends (a "perte par motif" row, a funnel stage, a stock-alert row link nowhere). Make report rows/segments link to the relevant filtered list route. (Gate: ROUTINE; may add a few list-filter params.)  [DONE 2026-06-21]

### Integrations — public API / webhooks / OCR

- [ ] FG102 — Webhook delivery log + retry/replay + test ping UI. `WebhookDelivery` records every attempt and the viewset exposes the last 50, but there's no replay/retry endpoint and `ApiWebhooksSection.jsx` never shows deliveries — a failed `facture.paid` is silently lost. Add `webhooks/{id}/deliveries/{id}/replay/` + `webhooks/{id}/test/` + the delivery history/status/replay/test UI. (Gate: ROUTINE.)
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
- [ ] FG119 — **Plan d'amortissement (linéaire/dégressif)** — dotations par actif aux taux marocains, postées au grand livre (impacte l'IS). (SCHEMA)
- [ ] FG120 — **Cession / mise au rebut d'immobilisation** — plus/moins-value + écritures associées. (SCHEMA)
- [x] FG121 — **Référentiel comptes bancaires & caisses** — `CompteTresorerie` (banque/RIB/devise/solde) ; aujourd'hui un seul RIB texte. (SCHEMA)  [DONE 2026-06-21]
- [ ] FG122 — **Position de trésorerie consolidée + projection** — solde par compte/caisse + total + projection nette AR/AP/paie/impôts (vue la plus demandée). (SCHEMA)
- [ ] FG123 — **Rapprochement bancaire (relevé ↔ écritures)** — pointer ligne GL vs ligne relevé jusqu'à concordance (≠ FG42 import paiements clients). (SCHEMA)
- [ ] FG124 — **Caisse / petty cash (journal d'espèces)** — entrées/sorties + justificatifs + clôture de caisse pour les achats terrain. (SCHEMA)
- [ ] FG125 — **Virements internes entre comptes** — banque↔banque/caisse en écriture à deux jambes. (SCHEMA)
- [ ] FG126 — **Prévisionnel de trésorerie roulant 13 semaines** — lignes prévues éditables (crédits, leasing, salaires, acomptes IS) au-dessus de la projection AR/AP. (SCHEMA)
- [ ] FG127 — **Portefeuille d'effets à recevoir (chèques/traites clients)** — échéance/banque/statut (portefeuille→remis→encaissé→impayé) ; omniprésent en B2B marocain. (SCHEMA)
- [ ] FG128 — **Effets à payer fournisseurs** — chèques/traites émis + calendrier d'échéances alimentant la trésorerie. (SCHEMA)
- [ ] FG129 — **Bordereau de remise en banque (chèques/effets)** — regroupe des effets pour dépôt + écriture. (ROUTINE)
- [ ] FG130 — **Gestion des impayés / rejets d'effets** — réouverture du montant dû, frais de rejet, relance. (SCHEMA)
- [ ] FG131 — **Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur)** — contrôle avant paiement ; les montants AP sont aujourd'hui saisis à la main. (ARCH)
- [ ] FG132 — **Échéancier & relevé fournisseur (aged payables + statement)** — balance âgée fournisseurs + relevé par fournisseur (miroir de la balance clients). (ROUTINE)
- [ ] FG133 — **Campagnes de règlement fournisseurs (payment run)** — sélection des factures dues → proposition de paiement par échéance, chèques/virement, post en lot. (SCHEMA)
- [ ] FG134 — **Génération de fichier de virement bancaire** — export du lot au format de la banque depuis un payment run. (DECISION)
- [ ] FG135 — **Notes de frais & remboursements employés** — saisie avec justificatif photo, validation, remboursement ; les équipes avancent du cash en continu. (SCHEMA)
- [ ] FG136 — **Indemnités kilométriques & per-diem chantier** — barèmes km/jour calculés auto depuis la distance site (GPS/haversine déjà présents). (SCHEMA)
- [ ] FG137 — **Préparation de la déclaration TVA** — TVA collectée − déductible par régime (mensuel/trimestriel, débit/encaissement) → montant déclarable + export. (SCHEMA)
- [ ] FG138 — **Relevé de déductions détaillé (annexe TVA)** — l'annexe ligne par ligne exigée par la DGI. (ROUTINE)
- [ ] FG139 — **Retenue à la source (RAS) sur honoraires/prestations** — calcul + bordereau de versement (obligation marocaine non gérée). (SCHEMA)
- [ ] FG140 — **Aide au calcul de l'IS** — estimation depuis le CPC + échéancier des 4 acomptes provisionnels + régularisation. (DECISION)
- [ ] FG141 — **Export FEC (fichier des écritures comptables)** — export structuré et ordonné des écritures au format auditable DGI (dépend du grand livre). (SCHEMA)
- [ ] FG142 — **Trousse liasse fiscale (états de synthèse)** — bilan + CPC + balance + tableaux annexes en un paquet pour le fiduciaire/DGI. (ARCH)
- [ ] FG143 — **Déclaration des honoraires / état 9421** — déclaration annuelle des paiements aux tiers depuis les règlements fournisseurs. (ROUTINE)
- [ ] FG144 — **Calcul du timbre fiscal sur encaissements espèces** — droit de timbre auto sur les factures payées en espèces. (SCHEMA)
- [ ] FG145 — **Retenue de garantie & cautions sur marchés (RG / bonne fin)** — RG retenue sur les marchés + cautions bancaires (provisoire/définitive/restitution) avec dates de levée. (SCHEMA)
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
- [ ] FG156 — **Identité & numéros légaux employé** — CIN, CNSS, CIMR/AMO, RIB, situation familiale (données paie obligatoires). (SCHEMA)
- [ ] FG157 — **Rémunération de base (gated rôle RH)** — salaire, périodicité, historique, réservé permission `salaires_voir`. (AUTH)
- [ ] FG158 — **Contact d'urgence & coordonnées étendues** — personne à prévenir, groupe sanguin (utile chantier/accident). (SCHEMA)
- [ ] FG159 — **Coffre documents employé** — contrat/CIN/RIB/diplômes via `records.Attachment`, expiration optionnelle. (ROUTINE)
- [ ] FG160 — **Référentiels Poste & Département** — remplacent le `poste` texte libre, rattachent org-chart/grilles/habilitations. (SCHEMA)
- [ ] FG161 — **Cycle de vie & offboarding** — statut embauché/actif/sorti + motif + checklist de sortie (récup EPI/outils/badge). (SCHEMA)
- [ ] FG162 — **Soldes & droits à congés (Maroc)** — compteurs annuels, acquisition mensuelle (~1,5 j/mois + ancienneté), report. (SCHEMA)
- [ ] FG163 — **Demande & validation de congés (workflow)** — soumission employé → validation superviseur/RH, décompte jours ouvrés hors fériés/WE (utilise FG5). (SCHEMA)
- [ ] FG164 — **Typologie d'absences** — CP/maladie/sans solde/exceptionnel/AT, chacune avec règle de décompte. (SCHEMA)
- [ ] FG165 — **Calendrier d'absences d'équipe → planning** — un technicien en congé n'est pas assignable au dispatch terrain. (ROUTINE)
- [ ] FG166 — **Pointage / clock-in–out** — arrivée/départ (mobile + géoloc comme le check-in F6), calcul des heures. (SCHEMA)
- [ ] FG167 — **Feuilles de temps par chantier (timesheets)** — heures imputées à une Installation/intervention → job-costing main-d'œuvre réelle. (SCHEMA)
- [ ] FG168 — **Heures supplémentaires & calcul majoré** — détection HS + taux (25/50/100 % nuit/férié) en entrée de paie. (SCHEMA)
- [ ] FG169 — **Planning d'équipes / roster (shifts)** — affectation hebdo techniciens↔équipes/camionnettes, détection conflits congés. (SCHEMA)
- [ ] FG170 — **Registre de présence chantier journalier (émargement)** — qui était présent sur quel chantier (trace litiges/facturation). (ROUTINE)
- [ ] FG171 — **Retards & absences injustifiées** — marquage + compteur (base disciplinaire/pilotage). (ROUTINE)
- [ ] FG172 — **Matrice de compétences** — pose structure, raccordement DC/AC, MES onduleur, pompage, soudure + niveau par employé. (SCHEMA)
- [ ] FG173 — **Habilitations électriques (B1V/BR/B2V/H0…)** — par employé avec validité/organisme, exigées sur tout chantier PV. (SCHEMA)
- [ ] FG174 — **Certifications spécifiques** — travail en hauteur, harnais, CACES/nacelle, secourisme/SST, conduite + expiration. (SCHEMA)
- [ ] FG175 — **Alertes d'expiration (habilitations/certifs/docs)** — moteur d'échéances → notifications RH/superviseur X jours avant. (ROUTINE)
- [ ] FG176 — **Garde d'affectation par habilitation** — alerte/blocage doux si on assigne un technicien sans l'habilitation requise. (DECISION)
- [ ] FG177 — **Visite médicale du travail** — dernière/prochaine visite + aptitude + alerte (obligatoire pour le chantier). (SCHEMA)
- [ ] FG178 — **Catalogue & dotation EPI** — casque/harnais/gants isolants/chaussures attribués nominativement (taille, date). (SCHEMA)
- [ ] FG179 — **Suivi péremption/contrôle des EPI** — EPI à durée de vie (harnais, gants isolants) + alerte de remplacement/recontrôle. (SCHEMA)
- [ ] FG180 — **Émargement de remise EPI (signature)** — accusé signé prouvant la dotation (exigible CNSS/accident). (ROUTINE)
- [ ] FG181 — **Registre HSE & accidents du travail** — déclaration (date/lieu/blessé/gravité/arrêt/photos) + export déclaration CNSS. (SCHEMA)
- [ ] FG182 — **Presqu'accidents (near-miss)** — saisie rapide terrain pour pilotage proactif. (ROUTINE)
- [ ] FG183 — **Causeries sécurité / toolbox talks** — quart d'heure sécurité avant chantier (thème/participants/émargement). (SCHEMA)
- [ ] FG184 — **Analyse de risques chantier (plan de prévention)** — évaluation des risques par chantier avant démarrage (≠ checklist F18 par intervention). (SCHEMA)
- [ ] FG185 — **Tableau de bord HSE** — taux fréquence/gravité, EPI/habilitations/visites en alerte, incidents par chantier. (ROUTINE)
- [ ] FG186 — **Permis de travail (hauteur/électrique/consignation)** — délivrance/clôture par tâche à risque, trace la consignation avant intervention. (SCHEMA)
- [ ] FG187 — **Gestion de la formation** — sessions (interne/externe), inscriptions, présence, coût → alimente la matrice de compétences. (SCHEMA)
- [ ] FG188 — **Plan & registre de formation** — historique par employé + besoins (obligations OFPPT/CSF). (ROUTINE)
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
- [ ] FG204 — **Tableau d'attribution multi-touch** — journal de points de contact par lead (Meta→site→WhatsApp→signature), au-delà du first-touch. (SCHEMA)
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
- [ ] FG242 — **Suivi des concurrents sur deals perdus** — sur un lead Perdu, saisir le concurrent gagnant + son prix. (SCHEMA)
- [ ] FG243 — **Pipeline de renouvellement de contrats O&M** — vue des `ContratMaintenance` à reconduire (échéances/relances). (SCHEMA)
- [ ] FG244 — **Abonnements de monitoring** — offre de supervision (mensuel/annuel) liée au module monitoring (revenu récurrent). (SCHEMA)

### Vertical solaire (conception, simulation, réglementaire, O&M)

- [ ] FG245 — **Éditeur de calepinage toiture (placement panneaux)** — placer/orienter les modules (surface, retraits) pour figer un nombre réaliste de panneaux. (ARCH)
- [x] FG246 — **Calcul de chaînes (string design) & vérif ratio DC/AC** — répartir N panneaux par MPPT, contrôler Vmp/Voc à froid vs plage onduleur. (ROUTINE)
- [x] FG247 — **Appariement module–onduleur depuis le catalogue** — proposer l'onduleur compatible avec la config panneaux (mots-clés alignés `builder.py`). (ROUTINE)
- [ ] FG248 — **Pont 3D toiture web → ERP** — importer la config du builder 3D `apps/web/roof-tool-pro` (surface/pans/orientation/kWc) dans un devis/chantier. (ARCH)
- [x] FG249 — **Optimisation inclinaison/azimut** — balayer tilt/azimut autour du site (via PVGIS existant) → orientation optimale. (ROUTINE)
- [ ] FG250 — **Analyse d'ombrage & profil d'horizon** — obstacles + horizon → perte d'ombrage mensuelle (l'ombrage qualitatif du lead devient un chiffre). (DECISION)
- [ ] FG251 — **Générateur de nomenclature électrique (BOQ)** — déduit câbles DC/AC, disjoncteurs, parafoudres, coffrets, terre, structure depuis le design. (ROUTINE)
- [ ] FG252 — **Brouillon de schéma unifilaire (SVG)** — auto-générer le schéma (panneaux→strings→onduleur→comptage→ONEE) pour le dossier technique. (ROUTINE)
- [ ] FG253 — **Aide au calcul de charge structure toiture** — surcharge kg/m² vs type de toiture + alerte si dépassement. (DECISION)
- [ ] FG254 — **Bibliothèque de fiches techniques modules/onduleurs (PAN/OND)** — datasheets + paramètres normalisés (Pmax/Voc/Isc/coef temp) par produit. (SCHEMA)
- [ ] FG255 — **Dimensionnement borne de recharge VE** — borne (kW/mono-tri/sessions) couplée au PV + impact autoconsommation. (ROUTINE)
- [ ] FG256 — **Étude de stockage & dispatch batterie (backup)** — autoconsommation max vs backup heures critiques → kWh/kW utiles. (ROUTINE)
- [ ] FG257 — **Simulation bankable P50/P90 avec modèle de pertes** — production P50/P90 + ratio de performance (température/salissure/câblage/onduleur). (DECISION)
- [ ] FG258 — **Profil d'autoconsommation horaire depuis courbe de charge** — courbe 8760/profil type × production horaire → taux d'autoconso réel. (DEP:openpyxl)
- [ ] FG259 — **Économie net-metering / injection surplus (loi 13-09/MT)** — valorisation du surplus injecté par tranche horaire (réglage `surplus_injecte_compense` existant). (ROUTINE)
- [ ] FG260 — **Modélisation escalade tarifaire ONEE sur 20–25 ans** — projeter facture/économies + VAN/TRI avec taux d'escalade éditable. (ROUTINE)
- [ ] FG261 — **Optimisation puissance souscrite (C&I)** — analyser la pointe et recommander une réduction de puissance souscrite post-PV. (ROUTINE)
- [ ] FG262 — **Modélisation dégradation modules sur la durée** — courbe de dégradation appliquée à la production projetée et garantie. (ROUTINE)
- [ ] FG263 — **Modèle financier PPA / tiers-investisseur** — simuler un PPA (tarif MAD/kWh, revenus actualisés) pour les clients sans capex. (DECISION)
- [ ] FG264 — **Rendement pompage par cycle de marche** — volume d'eau journalier/mensuel selon irradiation horaire + durée de pompage (étend l'`etude_params` actuel). (ROUTINE)
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
- [ ] FG280 — **Gestion fine des alarmes/défauts onduleur** — alarmes (code/gravité/équipement) distinctes du ticket SAV + acquittement/escalade. (SCHEMA)
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

- [ ] FG291 — **Programme / Projet multi-chantiers** — `Projet` regroupant chantiers + devis + tickets d'un même client/site (ferme à 4 forages, toiture par tranches). (ARCH)
- [ ] FG292 — **Tâches & sous-tâches de projet avec dépendances** — `ProjetTache` (assigné/échéance/prédécesseur) au-delà de la checklist figée. (ARCH)
- [x] FG293 — **Jalons & phases de projet** — étude/appro/pose/MES/réception avec dates cibles/réelles. (SCHEMA)
- [ ] FG294 — **Budget projet vs réel (engagé/dépensé)** — agrège devis + BCF/factures fournisseur + main-d'œuvre vs budget, alerte de dépassement. (ARCH)
- [ ] FG295 — **P&L de projet consolidé** — résultat par `Projet` (marge tous chantiers, sous-traitance et imports inclus). (ARCH)
- [x] FG296 — **Modèles de projet (templates de chantier-type)** — patron pré-créant tâches/jalons/BoM type à la signature. (SCHEMA)
- [ ] FG297 — **Contrôle documentaire de projet (plans & révisions)** — registre versionné (schéma unifilaire, calepinage, note de calcul). (ARCH)
- [x] FG298 — **Comptes-rendus de réunion de chantier** — `ReunionChantier` (ordre du jour/présents/décisions/actions) horodaté. (SCHEMA)
- [ ] FG299 — **Plan de charge des équipes (capacité vs affecté)** — jours dispo vs affectés par technicien/équipe pour éviter la sur-réservation. (ROUTINE)
- [ ] FG300 — **Détection de conflits d'affectation** — alerte si technicien/camionnette affecté deux fois sur le même créneau. (ROUTINE)
- [ ] FG301 — **Nivellement de charge (resource levelling)** — proposition de rééquilibrage des interventions surchargées. (ROUTINE)
- [ ] FG302 — **Calendrier de disponibilité ressources** — `IndisponibiliteRessource` (congé/formation/arrêt) excluant un technicien/véhicule. (SCHEMA)
- [ ] FG303 — **Planning des camionnettes (capacité véhicule)** — affectation par véhicule sur le calendrier (cohérent avec `Intervention.camionnette`). (ROUTINE)
- [ ] FG304 — **Référentiel sous-traitants** — `SousTraitant` (métier/contact/RIB/ICE), distinct des fournisseurs matériel. (ARCH)
- [ ] FG305 — **Ordres de travaux sous-traitant** — `OrdreSousTraitance` (chantier/prestation/montant/échéance/statut). (ARCH)
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

- [ ] FG350 — **Copilote in-app (CopilotPanel)** — brancher l'agent FastAPI (SQL + actions) dans un tiroir conversationnel global ; aucune UI ne le consomme aujourd'hui. (ROUTINE)
- [ ] FG351 — **Actions en langage naturel — « crée un devis pour… »** — étendre `action_tools.py` avec des outils d'écriture gardés (Devis/Lead/Client via REST interne). (ROUTINE)
- [ ] FG352 — **RAG sur documents & manuels (DocQA)** — indexer docs/manuels dans le pgvector existant + outil de récupération ; no-op sans clé LLM. (DEP:langchain-textsplitters)
- [ ] FG353 — **Résumé automatique d'un fil (lead/chantier/ticket)** — synthèse LLM en un clic d'un fil d'activité ; no-op sans clé. (COST)
- [ ] FG354 — **Brouillon de réponse email/WhatsApp** — suggestion de réponse FR éditable depuis un fil (jamais auto-envoyée) ; no-op sans clé. (COST)
- [ ] FG355 — **OCR CIN / contrat / pièce d'identité** — nouveau schéma dans `ocr_service.py` (chemin Zhipu vision) pour accélérer l'onboarding client. (ROUTINE)
- [ ] FG356 — **OCR bon de livraison enrichi → réception stock** — apparier les lignes OCR au catalogue et pré-remplir une réception. (ROUTINE)
- [ ] FG357 — **Voice-to-text notes terrain** — transcrire les mémos audio déjà captés en notes d'activité (STT) ; no-op sans clé. (COST)
- [ ] FG358 — **Photo AI QA sur photos d'installation** — contrôle vision (panneaux alignés, étiquettes, câblage) → score/flags sur le chantier. (COST)
- [ ] FG359 — **Next-best-action recommandée** — action suggérée par lead/chantier (relancer/planifier/facturer), heuristique + IA si clé présente. (ROUTINE)
- [ ] FG360 — **Détection d'anomalies (stock/paiements/fraude)** — scan planifié signalant les outliers dans un modèle `AnomalyFlag`. (SCHEMA)
- [ ] FG361 — **Prévision de ventes / demande** — série temporelle du CA et du volume de devis par mois depuis l'historique. (DEP:statsmodels)
- [ ] FG362 — **Score de probabilité de gain (win-probability)** — probabilité par lead remplaçant l'heuristique d'étape statique de `pipeline.py`. (SCHEMA)
- [ ] FG363 — **Score de churn / risque client** — repérer les clients maintenance/SAV à risque (sans activité, contrat lapsé) pour l'outreach proactif. (SCHEMA)
- [ ] FG364 — **Prévision de réappro stock** — prédire les dates de rupture + quantités suggérées depuis l'historique de mouvements. (ROUTINE)
- [ ] FG365 — **Prédiction de retard de paiement** — scorer chaque facture ouverte pour prioriser le recouvrement. (ROUTINE)
- [ ] FG366 — **Moteur de workflow multi-étapes (BPM) + SLA/escalades** — `WorkflowDefinition/Instance/Step` pour chaînes d'approbation visuelles + minuteries SLA, au-delà des règles à déclencheur unique. (ARCH)
- [ ] FG367 — **Conditions multi-critères & branches dans les règles** — `AutomationRule` avec groupes ET/OU + plusieurs actions séquentielles. (SCHEMA)
- [ ] FG368 — **UI de gestion des tâches planifiées (jobs)** — écran Paramètres listant les jobs Celery Beat (digests/rapports/monitoring) avec statut + exécution manuelle. (ROUTINE)
- [ ] FG369 — **Bibliothèque de modèles de workflow** — workflows pré-construits (relance devis, onboarding chantier, rappel garantie) installables en un clic. (ROUTINE)
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
- [ ] PAIE3 — Valeurs légales par défaut (taux/plafonds 2026) + validation fondateur. (DECISION)
- [x] PAIE4 — `BaremeIR` : tranches + somme à déduire, versionné par date d'effet. (SCHEMA)  [DONE 2026-06-22: BaremeIR + TrancheIR (tranches + somme à déduire), versionné par date d'effet.]
- [ ] PAIE5 — Barème IR officiel + déductions charges de famille. (DECISION)
- [ ] PAIE6 — `Rubrique` paramétrable (gain/retenue/cotisation, flags imposable/CNSS/AMO/CIMR, compte). (SCHEMA)
- [ ] PAIE7 — Catalogue de rubriques standard (transport/panier/ancienneté/HS…) — seed idempotent. (ROUTINE)
- [ ] PAIE8 — `ProfilPaie` (OneToOne→DossierEmploye) : type rémunération, salaire base, affiliations, RIB. (DEP:RH-FG154)
- [ ] PAIE9 — `RubriqueEmploye` : rubriques récurrentes par employé. (SCHEMA)
- [ ] PAIE10 — `PeriodePaie` : run mensuel + statuts brouillon→calculée→validée→clôturée. (SCHEMA)
- [ ] PAIE11 — `ElementVariable` + import depuis RH (heures/HS/absences/primes). (DEP:RH-FG192)
- [ ] PAIE12 — Moteur de calcul du bulletin (`services.calculer_bulletin`). (ROUTINE)
- [ ] PAIE13 — Salaire de base multi-profils (mensuel/journalier/forfait/horaire) + proration. (ROUTINE)
- [ ] PAIE14 — Heures supplémentaires majorées (25/50/100 % jour/nuit/férié). (ROUTINE)
- [ ] PAIE15 — Prime d'ancienneté barème (5/10/15/20/25 %). (ROUTINE)
- [ ] PAIE16 — Avantages en nature & indemnités imposables vs non-imposables (plafonds). (DECISION)
- [ ] PAIE17 — `BulletinPaie` + `LigneBulletin` (snapshot immuable une fois validé). (SCHEMA)
- [ ] PAIE18 — CNSS plafonnée (part salariale & patronale). (ROUTINE)
- [ ] PAIE19 — AMO (sans plafond) salariale & patronale. (ROUTINE)
- [ ] PAIE20 — CIMR optionnelle (taux par employé adhérent). (ROUTINE)
- [ ] PAIE21 — Frais professionnels & net imposable. (ROUTINE)
- [ ] PAIE22 — Calcul IR (barème progressif + charges de famille). (DECISION)
- [ ] PAIE23 — Allocations familiales (info patronale). (ROUTINE)
- [ ] PAIE24 — Taxe de formation professionnelle (1,6 % patronal). (ROUTINE)
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
- [ ] COMPTA1 — Plan comptable CGNC paramétrable + `seed_plan_comptable` idempotent. (ARCH)
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
- [ ] PROJ3 — Machine à états du projet (propre, jamais STAGES.py). (DECISION)
- [ ] PROJ4 — Phases de projet (étude/appro/pose/MES/réception). (SCHEMA)
- [ ] PROJ5 — Tâches & sous-tâches (WBS). (ARCH)
- [ ] PROJ6 — Dépendances de tâches FS/SS/FF/SF + lag. (SCHEMA)
- [ ] PROJ7 — Jalons (+ `facturation_pct`). (SCHEMA)
- [ ] PROJ8 — Calcul du chemin critique (CPM) + marges. (ROUTINE)
- [ ] PROJ9 — Roll-up d'avancement (pondéré par charge). (ROUTINE)
- [ ] PROJ10 — API planning Gantt. (ROUTINE)
- [ ] PROJ11 — Drag-reschedule des tâches (recalcule les successeurs). (ROUTINE)
- [ ] PROJ12 — Calendrier projet (jours ouvrés/fériés). (SCHEMA)
- [ ] PROJ13 — Baseline de planning (plan vs réel). (SCHEMA)
- [ ] PROJ14 — Détection des retards (tâches/jalons à risque). (ROUTINE)
- [ ] PROJ15 — Profil ressource & équipes (RH-léger, `cout_horaire` interne). (SCHEMA)
- [ ] PROJ16 — Affectation des ressources (User/équipe/camionnette/machine). (ARCH)
- [ ] PROJ17 — Indisponibilités ressources (congé/formation/arrêt). (SCHEMA)
- [ ] PROJ18 — Plan de charge (capacité vs affecté). (ROUTINE)
- [ ] PROJ19 — Détection de conflits d'affectation. (ROUTINE)
- [ ] PROJ20 — Nivellement de charge (levelling). (ROUTINE)
- [ ] PROJ21 — Budget projet (lignes : matériel/MO/sous-traitance/divers). (SCHEMA)
- [ ] PROJ22 — Coûts engagés vs réels (factures fournisseur + MO + sous-traitance). (ROUTINE)
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
- [ ] GED5 — Navigateur arborescent FR (frontend). (ROUTINE)
- [ ] GED6 — Liaison polymorphe Document↔objet métier (étend `records.ALLOWED_TARGETS`). (SCHEMA+DECISION)
- [ ] GED7 — Migration des `records.Attachment` existants (réutilise file_key). (DECISION)
- [ ] GED8 — Coffre-fort par employé/client (ACL owner+admin). (SCHEMA+DECISION)
- [ ] GED9 — Taxonomie de tags. (SCHEMA)
- [ ] GED10 — Métadonnées typées configurables (réutilise `customfields`). (SCHEMA)
- [ ] GED11 — Recherche plein-texte Postgres (SearchVector + GIN). (SCHEMA)
- [ ] GED12 — Index OCR + recherche sémantique (pgvector, key-gated no-op). (DEP)
- [ ] GED13 — Filtres & recherche avancée (frontend). (ROUTINE)
- [ ] GED14 — Aperçu inline multi-format (proxy même-origine). (ROUTINE)
- [ ] GED15 — Versionnage + historique + restauration de version. (SCHEMA)
- [ ] GED16 — Check-out / check-in (verrouillage). (ROUTINE)
- [ ] GED17 — Cycle de vie documentaire (brouillon→revue→approuvé→archivé→obsolète). (SCHEMA+DECISION)
- [ ] GED18 — Workflow d'approbation/revue. (SCHEMA)
- [ ] GED19 — ACL par dossier/document (héritage + override). (SCHEMA+DECISION)
- [ ] GED20 — Partage par lien tokenisé (expiry/mot de passe/quota). (SCHEMA+DECISION)
- [ ] GED21 — Watermarking & contrôle de diffusion. (DEP)
- [ ] GED22 — Politiques de rétention. (SCHEMA)
- [ ] GED23 — Archivage légal à valeur probante (write-once/object-lock). (DECISION)
- [ ] GED24 — Rétention légale / legal hold. (SCHEMA)
- [ ] GED25 — Purge automatique & tâche planifiée (dry-run d'abord). (DEP+DECISION)
- [ ] GED26 — Corbeille & restauration. (SCHEMA)
- [ ] GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint, hors /proposal). (ROUTINE)
- [ ] GED28 — Génération de document → classement automatique. (ROUTINE)
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
- [ ] FLOTTE5 — Référence d'actif commune (Vehicule|Engin) pour entretien/sinistre/doc. (DECISION)
- [ ] FLOTTE6 — Référentiels listes (type véhicule/engin, énergie, catégorie permis). (SCHEMA)
- [ ] FLOTTE7 — `Conducteur` + permis (lien `authentication.User`). (SCHEMA)
- [ ] FLOTTE8 — `AffectationConducteur` (conducteur↔véhicule datée). (ROUTINE)
- [ ] FLOTTE9 — Contrôle permis valide/catégorie à l'affectation. (ROUTINE)
- [ ] FLOTTE10 — `ReservationVehicule` + détection de conflit. (ROUTINE)
- [ ] FLOTTE11 — Check-list état des lieux départ/retour (photos). (SCHEMA)
- [ ] FLOTTE12 — Carnet de carburant (`PleinCarburant`). (SCHEMA)
- [ ] FLOTTE13 — Calcul conso L/100 km (et kWh/100 km). (ROUTINE)
- [ ] FLOTTE14 — Cartes carburant & alertes anomalie (km incohérent/fraude). (ROUTINE)
- [ ] FLOTTE15 — Plans d'entretien préventif (km/date/heures). (SCHEMA)
- [ ] FLOTTE16 — Génération d'échéances d'entretien dues + alertes. (ROUTINE)
- [ ] FLOTTE17 — Ordres de réparation + atelier/garage + coûts. (SCHEMA)
- [ ] FLOTTE18 — Pneumatiques & pièces. (SCHEMA)
- [ ] FLOTTE19 — `EcheanceReglementaire` (modèle générique). (SCHEMA)
- [ ] FLOTTE20 — Vignette / TSAV (barème CV/énergie, référentiel éditable). (ROUTINE)
- [ ] FLOTTE21 — Assurance auto (police/échéance/attestation/franchise). (ROUTINE)
- [ ] FLOTTE22 — Visite technique (validité paramétrable). (ROUTINE)
- [ ] FLOTTE23 — Carte grise & autorisation de circulation (GED). (SCHEMA)
- [ ] FLOTTE24 — Moteur d'alertes d'échéances réglementaires (J-30/15/7/échu). (ROUTINE)
- [ ] FLOTTE25 — `Sinistre` (accident/constat/assurance). (SCHEMA)
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
- [ ] QHSE3 — Seed ITP solaire par type d'installation. (ROUTINE)
- [ ] QHSE4 — `PlanInspectionChantier` + `ReleveControle` (valeur/conforme/photo). (SCHEMA)
- [ ] QHSE5 — Auto-conformité des relevés mesurés (vs min/max attendu). (ROUTINE)
- [ ] QHSE6 — Points d'arrêt bloquants (hold points) gating l'avancement chantier. (DECISION)
- [ ] QHSE7 — Relevé courbe I-V par string. (SCHEMA)
- [ ] QHSE8 — Photos de contrôle (avant/pendant/après) via `records.Attachment`. (ROUTINE)
- [x] QHSE9 — `NonConformite` (NCR : gravité/origine/source/photos). (SCHEMA)  [DONE 2026-06-22: NonConformite (NCR: gravité/origine/statut/chantier loose-FK).]
- [x] QHSE10 — `ActionCorrectivePreventive` (CAPA) + cause racine. (SCHEMA)  [DONE 2026-06-22: ActionCorrectivePreventive (CAPA + cause racine, lié NCR).]
- [ ] QHSE11 — Pont réserve (`installations.Reserve`) → NCR. (ROUTINE)
- [ ] QHSE12 — Relances CAPA en retard (notifications/digest). (ROUTINE)
- [ ] QHSE13 — Vérification d'efficacité CAPA (clôture conditionnée). (ROUTINE)
- [ ] QHSE14 — Chatter QHSE (NCR/CAPA/Incident/Audit). (SCHEMA)
- [ ] QHSE15 — `GrilleAudit` + `CritereAudit` pondérés. (SCHEMA)
- [ ] QHSE16 — `Audit` + `ReponseCritere` + score (→ NCR). (SCHEMA)
- [ ] QHSE17 — Grille de notation fin de chantier (gate clôture). (DECISION)
- [ ] QHSE18 — `ProcedureQualite` versionnée (docs qualité GED). (SCHEMA)
- [ ] QHSE19 — `RetourClientQualite` (satisfaction qualité). (SCHEMA)
- [ ] QHSE20 — Tableau de bord « ISO 9001 readiness ». (ROUTINE)
- [ ] QHSE21 — `EvaluationRisque` (document unique / plan de prévention) + lignes. (SCHEMA)
- [ ] QHSE22 — Document unique requis avant pose (gate statut chantier). (DECISION)
- [ ] QHSE23 — `PermisTravail` (hauteur/élec-consignation/point chaud). (SCHEMA)
- [ ] QHSE24 — Consignation électrique (LOTO) sur permis électrique. (ROUTINE)
- [ ] QHSE25 — Alerte expiration de permis. (ROUTINE)
- [ ] QHSE26 — `InductionSecurite` (accueil sécurité site, incl. sous-traitants). (SCHEMA)
- [ ] QHSE27 — `CauserieSecurite` (toolbox talks + émargement). (SCHEMA)
- [ ] QHSE28 — `PlanUrgence` / premiers secours (contacts/secouristes/point de rassemblement). (SCHEMA)
- [ ] QHSE29 — Registre `Incident` (accident/presqu'accident/incident). (SCHEMA)
- [ ] QHSE30 — Déclaration CNSS de l'accident du travail (échéance légale). (DECISION)
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
- [ ] CONTRAT4 — Liens inter-apps (devis/lead/installation/maintenance) en string-FK. (ROUTINE)
- [ ] CONTRAT5 — Wrap de `sav.ContratMaintenance` (lecture/lien, ne casse pas). (ROUTINE)
- [ ] CONTRAT6 — Niveaux de confidentialité + droits d'accès par type. (DECISION)
- [ ] CONTRAT7 — `ModeleContrat` (bibliothèque de modèles). (SCHEMA)
- [ ] CONTRAT8 — `Clause` (bibliothèque de clauses réutilisables). (SCHEMA)
- [ ] CONTRAT9 — `ClauseContrat` (clauses résolues, ordonnées, surchargeables). (SCHEMA)
- [ ] CONTRAT10 — Génération du contrat par fusion (merge tokens). (ROUTINE)
- [ ] CONTRAT11 — Rendu PDF interne du contrat (hors `/proposal`). (ROUTINE)
- [ ] CONTRAT12 — Machine d'états du cycle de vie + transitions gardées. (ROUTINE)
- [ ] CONTRAT13 — `RegleApprobation` (par montant/type). (DECISION)
- [ ] CONTRAT14 — `EtapeApprobation` + workflow d'approbation interne. (ROUTINE)
- [ ] CONTRAT15 — Chatter/journal du contrat (audit des transitions). (ROUTINE)
- [ ] CONTRAT16 — `SignatureContrat` (point e-sign + statut signé). (DECISION)
- [ ] CONTRAT17 — Transition automatique signé→actif sur signature. (ROUTINE)
- [ ] CONTRAT18 — `VersionContrat` (versionnage immuable des rendus). (SCHEMA)
- [ ] CONTRAT19 — Dépôt en GED des versions & PDF signés. (ROUTINE)
- [ ] CONTRAT20 — Dates clés (début/fin/préavis) + tacite reconduction. (SCHEMA)
- [ ] CONTRAT21 — Calcul des échéances & contrats « à renouveler ». (ROUTINE)
- [ ] CONTRAT22 — `AlerteContrat` + rappels via notifications. (ROUTINE)
- [ ] CONTRAT23 — Renouvellement (manuel + reconduction tacite). (ROUTINE)
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
- [ ] KB3 — Recherche plein-texte + filtres par catégorie/tag. (ROUTINE)
- [ ] KB4 — Lien article ↔ produit/équipement/type d'intervention (contextuel sur SAV/chantier). (SCHEMA)
- [ ] KB5 — Procédures/SOP d'installation & dossiers ONEE/82-21 (gabarits seedés). (ROUTINE)
- [ ] KB6 — Source de contenu pour le RAG/DocQA (FG352) — indexation pgvector. (DEP)
- [ ] KB7 — Droits d'accès par rôle + suivi de lecture. (SCHEMA)

### Module Réclamations & litiges (`apps/litiges`) · LITIGE1–LITIGE6
**But :** objet formel de réclamation/litige rattaché à une Facture/Lead/Chantier/Ticket (motif, montant contesté, statut, résolution) — comble le vide entre SAV (technique) et recouvrement (financier). Survey-recommended (priorité moyenne).
- [x] LITIGE1 — App `litiges` + modèle `Reclamation` (type, gravité, source FK polymorphe, statut). (ARCH)  [DONE 2026-06-22: NEW app apps/litiges: Reclamation (type/gravité/source polymorphe loose/statut/montant_conteste).]
- [x] LITIGE2 — Workflow statut (ouverte→en_traitement→résolue/rejetée) + chatter. (SCHEMA)
- [ ] LITIGE3 — Litige financier ↔ recouvrement : suspendre les relances d'une facture en litige. (ROUTINE)
- [ ] LITIGE4 — Litige qualité ↔ QHSE : lien NCR + audit fin de chantier. (ROUTINE)
- [ ] LITIGE5 — Capture du concurrent/motif sur deal perdu (étend FG242). (SCHEMA)
- [ ] LITIGE6 — Tableau de bord litiges (ouverts/montant contesté/délai de résolution). (ROUTINE)

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
- [ ] DC17 — **`CustomUser.poste` en texte libre** → référentiel `Poste`/`Departement` (FG160), migrer/dédupliquer les chaînes existantes, canonique sur `DossierEmploye`. (SCHEMA) (@lane: apps/authentication)
- [ ] DC18 — **Sujet email hardcodé « Notification Taqinor »** (`automation/actions.py`) → store de modèles email (FG17), un store par canal (WhatsApp/email/doc). (SCHEMA)
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
