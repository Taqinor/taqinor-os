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
   gated/blocked — following PLAN2.md's own rules, which are the same as this file's — then
   drain this file's **BUILD QUEUE** the same way. Process EVERY unchecked `[ ]` task (not
   `[x]`, not `[SKIP]`, not `[BLOCKED]`); ignore the GATED and MANUAL sections entirely.
   **At the START, compute the file-ownership + dependency graph from the real code** (which
   source files each `[ ]` task must write) and **partition the queue into independent lanes**
   — a lane is a group that must run in sequence because it shares a file or has a dependency;
   different lanes never touch each other's files. **Fan the lanes out to up to 8 concurrent
   worktree subagents** (`isolation: worktree`, each in its own isolated git worktree so two
   never edit the same files at once); with more than 8 lanes, run them in **waves of up to 8**;
   with fewer, use fewer agents. **Tasks inside one lane run in sequence.** Each subagent
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
6. **Skip-and-note blockers, never stall.** If a task hits a blocker (a destructive migration,
   a paid/external dependency that isn't pre-approved, an auth or cost change, a brand-new
   architectural component, a conflict with a non-negotiable rule, or a real decision): do
   **not** guess and do **not** stall. Mark it `[BLOCKED: <one-line reason>]`, move it to the
   GATED section, and continue with the remaining tasks. A single blocked task must never halt
   the run.
7. **STOP only when** the queue is drained (no buildable `[ ]` task remains in `docs/PLAN2.md`
   then this file), a usage/length cap pauses the run (fine — the plan is idempotent;
   re-firing resumes from the first still-unchecked task), or every remaining task is blocked.
   Then **report once**, in plain language only — no diffs, no commit hashes: every task that
   shipped, what was skipped and why, and exactly what Reda must click/type (with menu paths).

**Then the REFINEMENT QUEUE (run order).** Once the existing BUILD QUEUE is drained — **T1–T17
first**, then the N/F tasks — work the **REFINEMENT QUEUE — existing-feature polish (audit
2026-06-18)** section (below, after the BUILD QUEUE and before GATED) top-down: build the
**ROUTINE** tasks unattended exactly like a queue task, and **skip + flag** every gated task
(`SCHEMA` / `DEP` / `DECISION` / `GALLERY`) — same skip-and-report behaviour as a GATED item today.
Those gated refinements are mirrored into the GATED section so an unattended run never auto-builds
them. The refinement tasks use the format `[ ] [<MODULE>] [L<lens#>] [<GATE>] …` (not the `T#/N#`
ids), so they are deliberately outside the plan-status fingerprint — ticking one does not require a
CODEMAP §10 refresh.

**Run from anywhere — web or phone.** Because `main` auto-deploys itself, a task can be run
from Claude Code on the web or from the phone with no PC involved. **One-line starter** to
paste into a fresh cloud session:

> Read `docs/PLAN.md` top to bottom. Work through EVERY `[ ]` task — **first** `docs/PLAN2.md` (if it exists), **then** this file's BUILD QUEUE. First partition the unchecked tasks into independent lanes by the real files each writes, then build the lanes in parallel with **up to 8 concurrent worktree subagents** (each in its own git worktree, waves of 8 if there are more lanes), coupled tasks in sequence inside a lane (default: run this as a dynamic workflow with a separate adversarial review agent that must pass each change before it's merge-eligible; fall back to plain parallel worktree subagents — never a single serial one-task-at-a-time agent). For each task: verify it isn't already built, build it with tests, commit it to its worktree branch, tick it `[x]`, add a dated DONE LOG line, then continue to the next. Skip-and-note any blocker (`[BLOCKED: reason]` → GATED) and keep going. At the very end, fold every worktree branch into one `dev`, integrate the latest `origin/main` first (merge it in, never force-push) and recompute the CODEMAP structure fingerprint if that changed the structural surface, get the four required CI checks green over the whole batch (with MinIO) and self-merge `dev` → `main` exactly once (this auto-deploys — do not run any deploy command; no per-agent PR, no per-task merge). Report once, in plain language, including the lane plan. Do not stop after one task and do not merge per task.

---

## STANDING RULES (every task obeys these)

- **One run = the whole queue, not one task, fanned across up to 8 lanes.** At the start, partition the unchecked queue into independent **lanes** (grouped by the real files each task writes) and give each lane its own subagent in its own git worktree — **up to 8 worktree subagents at once, in waves of 8** when there are more lanes — so each subagent's context stays small and focused and two lanes never edit the same files at once; tasks that depend on or overlap each other run in sequence inside one lane. Never stop after a single task. The orchestrator folds every worktree branch into one `dev`, CI runs **once** over the whole batch, and the run self-merges `dev` → `main` **exactly once** — no per-agent PR, no per-task merge. (Human-review PRs are still not wanted — the run self-merges its own green work.)
- **Engine = workflow-with-review by default; parallel subagents as fallback; never single-serial.** Run the lanes as a **dynamic workflow with a fan-out-and-verify shape** — one worktree subagent per independent task **plus a separate adversarial review agent** that checks every finished change against these STANDING RULES and the task's acceptance criteria; nothing folds into `dev` or merges until its review passes. When no workflow engine is available (e.g. a phone or cloud session), **fall back to the same lane-planned worktree subagents** with the orchestrator reviewing each lane against these rules before folding it in. **Never drop to a single serial, one-task-at-a-time agent** — parallel lanes with review are the floor.
- **Sync-safe single merge.** Right before the one self-merge, **fetch and integrate the latest `origin/main` into `dev`** (merge it in — never rebase published history, never force-push); if that changed the code-structure surface, **recompute the CODEMAP structure fingerprint on the integrated tree** (the fingerprint the `stage-names` check verifies); **re-run CI once on the integrated state and merge only when green**; if the push is rejected because `main` advanced, **repeat (fetch, integrate, recompute if needed, re-run CI, push) — never force**. A run edits the shared files (`CLAUDE.md` / its own plan file / `docs/CODEMAP.md`) only for its own command and ships that change inside this same merge — so a concurrent OS run and web-plan run never fight over those files.
- **Verify against real code first. Never trust prior reports.** (Round 1 reported a preview
  fix that was never real, because that session's CI was silently broken.)
- **Additive only.** New tables / nullable columns / new defaults. **Never** a destructive
  migration (no dropping columns/tables, no deleting rows). If one is needed → `[BLOCKED]`.
- **Do not touch the DEBUG setting.** It is ON by Reda's explicit decision for the trial.
- **Do not redesign the PDFs.** Keep the existing WeasyPrint engine and the `PDF_ENGINE=legacy`
  fallback. (A full document redesign is a GATED item — see below.)
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

**Pre-approved dependencies (do NOT treat as blockers):** `openpyxl` (real .xlsx) and
`vite-plugin-pwa` (build-time dev dependency for the PWA). Anything else new → `[BLOCKED]`.

**Status legend:** `[ ]` to do · `[x]` done · `[SKIP]` not needed / already present ·
`[BLOCKED: reason]` needs a decision (moved to GATED).

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

### PRE-APPROVED FOR AUTONOMOUS BUILD (added 2026-06-18)

For the **specific ungated tasks below ONLY** — N14, N26, N59, N60, N64, N65, N67, N85,
N87, N88, G9, N103, N104, N105, N106, N107, and the additive-column / UI / comptable-export /
Odoo-importer refinement tasks flipped to `[ROUTINE]` in the REFINEMENT QUEUE — the following are
**already authorized**, and a future session must **NOT pause** on them despite the general rule to
stop-and-ask before a new dependency / schema / cost change:

- the **Leaflet** map library (N85 + the Parc « Carte » refinement);
- **Celery Beat** as the scheduler (G9);
- the **Brevo** email integration (N87/N88, SDK or SMTP, key from settings/env, no-op without key);
- the **specific additive columns** listed (Client `created_by` + `date_modification`; a
  `type_equipement` tag on `stock.Categorie`; per-company serial uniqueness on `Equipement`;
  ICE-inclusive client export);
- the **ONEE grid seed values** (the residential TTC scale + the cheaper force-motrice/agricole
  class in N64);
- the **stock-reserve-then-decrement rule** (N14 + the folded-in G6);
- the **silent DGI export/validator** capability (N105, master toggle default OFF);
- **converting the devis PDF literals to settings** (the rule-#4 literal→setting wiring of N26 /
  N59 / N60 / N67 — minimal premium-engine wiring with byte-identical defaults, visual layout
  unchanged).

The general stop-and-ask / pause rule **still applies to everything NOT on this list.**

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
- [BLOCKED: ROUTED to the dev-field-exec branch — the offline-sync architecture is APPROVED, but build it ONLY on dev-field-exec; it must NOT be built in a main "work on the plan" run (branch-collision risk on main). Coupled with F21.] N91 — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception signature, syncing when back online.
- [x] N92 — PWA web push notifications for high-priority events from the notification engine. (UNGATED 2026-06-20 — pywebpush dependency approved; in the build run generate the VAPID keypair — public key to the frontend, private key to the backend env. Opt-in per device subscription.) [DONE 2026-06-20: `notifications.PushSubscription` (company+user forced server-side), subscribe/unsubscribe/vapid-public-key endpoints, best-effort web-push channel in `notify()` (drops dead subs on 404/410), `sw.js` push+notificationclick handlers, per-device opt-in toggle in NotificationsPreferences. VAPID keys default EMPTY → total NO-OP until Reda sets them. `pywebpush` left as an OPTIONAL install (its `http-ece` sdist won't build on modern setuptools, so it's `pip install`-to-enable rather than a base requirement — keeps CI install green; the dispatch path imports it lazily). 8 tests.]
### Localisation / audit / security / data
- [ ] N93 — Full Arabic & Darija localisation as a selectable interface language with RTL layout support across the app, French default, English in code; client-facing document language selectable per client (facture/devis in French or Arabic). (UNGATED 2026-06-20 — i18n framework approved. SEQUENCING NOTE (do NOT prioritize): this touches every component, so run it as the FINAL step of the UI/UX overhaul, AFTER the component restyle, to avoid re-translating restyled components — pull forward only on Reda's explicit instruction.)
- [ ] N94 — Translation-management surface in settings so interface strings can be reviewed/adjusted per language without a code change. (UNGATED 2026-06-20 — depends on the N93 i18n framework; SAME sequencing note — final step of the UI/UX overhaul, not prioritized.)
- [x] N96 — Account security: optional 2FA, visible active sessions with revoke, forced credential-rotation flow; production DEBUG setting left unchanged. (UNGATED 2026-06-20 — auth change approved (this closes G8); pyotp dependency approved. Build 2FA as OPT-IN per user so it can NEVER lock existing users out.) [DONE 2026-06-20: the **2FA** half (opt-in TOTP on `CustomUser`, default OFF → no lockout, setup/enable/disable/status endpoints, login requires `otp` only when enabled, settings tab + login code step, `pyotp==2.10.0`, 11 tests) shipped earlier; THIS run completed the rest — additive `UserSession` (company+user forced, refresh-token jti, UA/IP/last-seen), `GET /auth/sessions/` + `POST /auth/sessions/<id>/revoke/` (blacklists the refresh token via the already-installed `token_blacklist` + marks the row revoked; current device flagged), forced rotation via additive `must_change_password` (default **False** → nobody locked out) + nullable `password_changed_at` surfaced in `/auth/me/`, `POST /auth/change-password/`, and the "Sessions actives" + "Mot de passe" sub-sections in the Sécurité-du-compte tab. Migration 0012, 11 new tests (95 auth tests total green). Closes G8's 2FA half.]
### Growth / multi-tenant platform
- [BLOCKED: full multi-tenant SaaS platform + per-tenant billing (cost) + new architecture. REVIEWED 2026-06-20 — Reda chose to KEEP this deferred post-V1.] N100 — Build out multi-tenant operation on the existing tenant_id foundation (strict per-tenant isolation verification, tenant onboarding flow, per-tenant branding/white-label of client-facing documents, configurable per-plan feature limits, tenant-level billing).
- [BLOCKED: tenant administration console + self-serve signup (auth change) + new architecture. REVIEWED 2026-06-20 — Reda chose to KEEP this deferred post-V1.] N101 — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup for design-partner installers.
- [BLOCKED: depends on N100/N101 (final platform doc/update). REVIEWED 2026-06-20 — kept deferred post-V1 together with N100/N101.] N102 — After the modules above are built, update the master project document + PLAN + DONE log in plain language to reflect the new post-sale, procurement/inventory, Moroccan billing/compliance, full-editability, and platform additions, noting which shipped and which were skipped.

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

- [BLOCKED: ROUTED to the dev-field-exec branch — same offline-sync architecture as N91; APPROVED but build it ONLY on dev-field-exec, never in a main "work on the plan" run (branch-collision risk on main).] F21 — **Offline-tolerant field capture** covering the whole intervention flow — préparation checklist, GPS check-in, photos, serial capture, voice memos, Matériel consommé, réserves, and the signature — queuing locally on a poor connection and syncing when back online (extends the planned offline field capture to the full intervention workflow).

---

## BUILD QUEUE — M1–M7 (modularity / decoupling — added 2026-06-20)

Architecture hardening for the modular monolith. The backend is already split into clean
per-domain Django apps, but the five business-core apps (`crm`, `ventes`, `stock`,
`installations`, `sav`) are woven together by **circular, load-time model imports**
(confirmed cycles: crm⇄ventes, stock⇄ventes, installations⇄ventes, installations⇄stock),
so none can be tested or extracted on its own. These tasks decouple that core **without
changing behaviour or schema** (additive / refactor only; every STANDING RULE applies).
Build order top-down — M1 and M2 unlock the rest. Gate notes are inline; an unattended run
must skip-and-flag the tasks marked `[GATE: …]` per the stop-and-ask STANDING RULE.

- [x] M1 — Replace every load-time cross-app model import in the core apps with Django string FK references so no `models.py` imports a sibling app at import time. Fait = no top-level `from apps.<other>.models import …` remains in crm/ventes/stock/installations/sav `models.py`; every cross-app FK/M2M uses the `"app.Model"` string form; `python manage.py makemigrations --check` reports no new migration and the suite passes. (Safe refactor — no schema change.) [DONE 2026-06-20: `ventes/models.py` was the ONLY core-app models.py with load-time sibling imports — its 5 `Client` FKs and 3 `Produit` FKs now use `'crm.Client'` / `'stock.Produit'`, the two top-level imports removed (breaks the crm⇄ventes / stock⇄ventes import cycles). The other four already used the string form. `manage.py check` passes; `makemigrations --check` = No changes detected.]
- [x] M2 — Make `services.py` / `selectors.py` the only cross-app entry point: route cross-app reads/writes through an app's service/selector functions instead of importing its `models`/`views` directly, and write the rule into CLAUDE.md repo-facts. Fait = remaining cross-app call sites import another app's `services`/`selectors` (or use string FKs), never its `models`/`views`; behaviour unchanged; tests pass. (Generalises the existing `ventes → crm.services` lazy-import pattern.) [DONE 2026-06-20: new `selectors.py` in crm/ventes/stock/installations (read helpers + lock helper + lead reassignment); new services `stock.record_stock_movement`/`mouvement_type_*`, `sav.create_equipement_from_serial`/`create_corrective_ticket`; ~25 cross-app call sites across crm/ventes/stock/installations/sav rerouted through services/selectors; same-app and foundation-app imports left as-is; the cross-app boundary rule added to CLAUDE.md repo-facts. 900/903 tests green (the 3 reds are MinIO-unreachable storage tests that pass in CI).]
- [x] M3 — Add an `import-linter` contract run in CI that forbids import cycles among the core apps and pins the layer order (foundation → domain core → satellites). Fait = a `lint-imports` step runs in CI and fails on a new cycle or an upward import; the contract is committed. (UNGATED 2026-06-20 by the founder — `import-linter` dev dependency approved.) [DONE 2026-06-20: `backend/django_core/.importlinter` (3 contracts — core domain models stay mutually decoupled = the M1 string-FK win, incl. the M7-split installations model modules; `core` stays a base foundation layer that imports no domain/satellite app), `import-linter==2.11` pinned in requirements.txt, a `lint-imports` step added to the `backend-lint` CI job; `lint-imports` = 3 kept / 0 broken locally. Scope note: a full no-cycles/strict-layers contract among the five core apps does NOT pass yet (they still call each other at the service layer) — that is deferred until the deeper decoupling lands; documented in the contract file + CLAUDE.md.]
- [BLOCKED: the load-time back-edge it targets does NOT exist on main — `ventes` imports `apps.audit` only LAZILY (function-local, in `views.py`), so there is no import-time cycle to remove. The two remaining calls record explicit ACTION audits ("PDF devis généré") with no corresponding model-save to hook a signal to; moving them to signals would change/lose audit semantics. Needs founder sign-off on the audit-event model before any change. Moved to GATED.] M4 — Formalise the three layers (foundation: authentication/roles/records/customfields/core · domain core: crm/stock/ventes/installations/sav · satellites: reporting/automation/monitoring/notifications/publicapi/audit/documents/dataimport/contact) and remove the one back-edge `ventes → audit` by moving that audit capture onto signals. Fait = `ventes` no longer imports `apps.audit`; the layer map is written down; behaviour unchanged; tests pass. (The signal move builds independently; enforcement rides on M3's contract.)
- [x] M5 — Use the empty `core/` app for shared primitives: move the tenant base mixin and the `authentication/scoping.py` company-scoping helpers into `core` so apps depend down on `core` instead of sideways. Fait = the shared helpers live under `core/`, re-exported for back-compat, callers updated; no schema change; tests pass. (Touches authentication/scoping — additive, build carefully.) [DONE 2026-06-20: `core/mixins.py` (`TenantMixin`) + `core/scoping.py` (the full scoping implementation) now hold the real code; `authentication/mixins.py` and `authentication/scoping.py` are thin re-export shims so every existing `from authentication.scoping import …` / `…mixins import TenantMixin` keeps working unchanged — no caller edits needed. `makemigrations --check` clean (no schema change); `manage.py check` passes.]
- [x] M6 — Replace the hottest direct cross-app calls with a small domain-event layer (e.g. emit `DevisAccepted` that `installations` subscribes to) instead of `installations` importing `ventes`. Fait = at least the accept→chantier and accept→stage seams run through events/signals, no direct call removed without an equivalent subscriber, tests pass. (UNGATED 2026-06-20 by the founder — new event-bus component approved.) [DONE 2026-06-20: `core/events.py` holds a Django-signal event bus (foundation, depends on nothing); `ventes.accepter()` now EMITS `devis_accepted` instead of calling `crm.services` directly, and `crm` subscribes (`apps/crm/receivers.py`, wired in `CrmConfig.ready`) to advance the lead stage — signals fire synchronously so behaviour is identical (the accept→stage seam now runs through the event). DELIBERATE SCOPE on accept→chantier: NOT auto-wired — `create_installation_from_devis` triggers N14 stock RESERVATIONS, so auto-creating a chantier on every acceptance would silently reserve inventory company-wide (a behaviour/inventory change, not a refactor). The event infra is in place for `installations` to subscribe if/when the founder wants that behaviour; flagged in the run report.]
- [x] M7 — Split the god-files (no behaviour change): turn the large `views.py` into a `views/` package (one module per resource) and split the big `models.py` into `models_*.py` mirroring `parametres`, for `installations` (views 1879 / models 1056 LOC), `ventes` (views 1259) and `stock` (views 1063). Fait = each split app keeps identical importable symbols (re-exported from its package `__init__`), endpoints and migrations unchanged, suite passes. (Pure reorg — cuts merge conflicts across parallel lanes.) [DONE 2026-06-20: `installations/views.py`→`views/` (7 modules), `ventes/views.py`→`views/` (8), `stock/views.py`→`views/` (13), each package `__init__` re-exporting every public name (urls.py untouched); `installations/models.py`→`models_chantier/_field/_installation/_intervention.py` with `models.py` re-exporting all 23 classes. Verified byte-identical (reconstructed each original from the pieces — zero code-line diffs); `makemigrations --check` = no changes; suite green.]

The two heavy options I recommended **deferring** (microservice extraction; per-app pip
packaging) are recorded under GATED below — not for an unattended run.

---

## BUILD QUEUE — module feature-gap audit 2026-06-21 (FG1–FG106)

A whole-system feature-gap review run as **8 parallel module lanes** (CRM · Ventes/facturation ·
Stock/procurement · Installations/field-exec/outillage · SAV/parc/maintenance/monitoring ·
Reporting/analytics/custom-fields · Paramètres/RBAC/auth/notifications/automation ·
Integrations + transversal). Every task below was **verified ABSENT against the real `main` code**
(the audit cited the proving file for each) — none re-propose anything already shipped, queued
(N93/N94 i18n), or GATED (G2 WhatsApp Cloud, G3 redesign, G7 e-sign, G8 SSO, G11 chatbot key,
G12 M365, G14 DGI portal, N100–N102 SaaS platform, N91/F21 offline capture, Meta CAPI send).

**These obey every STANDING RULE** (multi-tenant `company` FK forced server-side, additive-only,
French UI, `STAGES.py` contract untouched, buy prices/margins never client-facing, cross-app via
`services.py`/`selectors.py`, premium `/proposal` engine off-limits for restyle). **Gate legend
(inline per task):** `ROUTINE` = autonomous · `SCHEMA` = additive migration (pre-approved per
STANDING RULES, safe for an unattended run) · `DEP:<lib>` / `COST` / `AUTH` / `ARCH` / `DECISION`
/ `GALLERY` = **stop-and-ask** — an unattended run SKIPS these and flags them (mirror to GATED on
build). Build order is by value within each module; priority across modules is Reda's call.
**Note (merge):** because these are new `FG*` task IDs, the first run that ticks any of them must
refresh CODEMAP §10 + re-run `codemap_fingerprint.py --write` in the same commit (standard
add-to-plan rule) — this audit branch only edits `docs/PLAN.md`.

### Transversal — notifications, automation, scheduling & collaboration

- [ ] FG1 — Activate the dead notification EventTypes via Celery-Beat sweeps. `CHANTIER_DUE`, `WARRANTY_EXPIRING`, `MAINTENANCE_DUE`, `SAV_TICKET_BREACHING` are declared in `notifications/models.py` but **never emitted** (no producers); `digests.py` counts maintenances/SAV-open only. Add idempotent daily beat tasks (the `celery_beat` process already exists) that sweep expiring warranties (~90 d), due maintenance/renewals, relances due / stale leads, breaching tickets, and chantier milestone transitions → `notify()` to owner/responsable. (Gate: ROUTINE; reuses the existing engine + beat infra.)
- [ ] FG2 — Wire the automation engine's time-based triggers. `automation/models.py` declares `WARRANTY_EXPIRING`/`MAINTENANCE_DUE`/`FACTURE_OVERDUE` and the UI offers them, but `automation/signals.py` only wires `post_save` (`_equipement_saved` is an explicit no-op). Add a beat task that calls `engine.evaluate(TriggerType.X, instance, company)` per match so configurable rules actually fire. (Gate: ROUTINE; engine + beat already exist.)
- [ ] FG3 — Automation rule template library (no-code presets). `AutomatisationsSection.jsx` forces the founder to hand-type raw `trigger_config`/`action_config` JSON. Add an `AUTOMATION_TEMPLATES` constant + `GET automation/templates/` + a "Créer depuis un modèle" pre-fill (e.g. WhatsApp link on devis accepté, assign new lead to default responsable). (Gate: ROUTINE.)
- [ ] FG4 — Admin-configurable notification routing rules. `NotificationPreference` is per-user opt-in only; recipient selection (digests, alerts) is hardcoded (`_is_manager`). Add `NotificationRoutingRule` (company, event_type, target role/user) + an admin editor; `notify()` resolves recipients through it. Defaults must reproduce today's behaviour. (Gate: SCHEMA.)
- [ ] FG5 — Working-hours + Moroccan public-holiday calendar feeding planning/relance. No working-hours/holiday model exists anywhere — relance/intervention/maintenance dates can land on Fridays/holidays. Add `WorkingHoursConfig` + `Holiday` (per company, seed MA public holidays) + helpers consumed by date computation. (Gate: SCHEMA + DECISION on which features skip non-working days.)
- [ ] FG6 — ICS/iCal calendar feed per user. `reporting/calendar.py` is JSON-only; no `text/calendar` anywhere. Add `GET reporting/calendar.ics?token=<per-user>` (poses/interventions/maintenance visits) + "S'abonner au calendrier" in `CalendarPage.jsx` so the agenda shows in Google/Outlook on technicians' phones. (Gate: ROUTINE; DECISION on the token scheme.)
- [ ] FG7 — Generic comments + @mentions across all records. Each app has a bespoke chatter and there is **no @mention** anywhere. Add a generic `records.Comment` (ContentType target, like `Attachment`) with `@username` parsing → `notifications.notify()`, rendered in a shared chatter component reused on Lead/Devis/Facture/Chantier/Ticket. (Gate: SCHEMA.)
- [ ] FG8 — Unified, role-scoped cross-record activity feed ("Fil d'activité"). The only cross-record history is the Directeur-gated audit Journal. Add a read endpoint surfacing recent `records.Activity` + per-app chatter scoped via `authentication/scoping.py`, rendered as a dashboard widget. (Gate: ROUTINE; no new model.)
- [ ] FG9 — Shared cross-module tag taxonomy. Tags live only on `Lead` (free-text + `LeadTag`). Add a generic `records.Tag` + `TaggedItem` (ContentType) with a company-scoped vocabulary, surfaced as a chip-input on any record; keep CRM's existing free-text intact. (Gate: SCHEMA.)
- [ ] FG10 — Tenant-wide document/attachment center. `records.Attachment` is only listable per-record (`?model=&id=`). Add `GET records/attachments/all/` (company-scoped, filter by mime/phase/content_type/date, paginated) + a "Documents" page reusing the existing same-origin download relay. (Gate: ROUTINE.)
- [ ] FG11 — Generalize saved filters/views to all list screens. Saved views exist only in `LeadsPage.jsx` (localStorage). Extract a shared `useSavedViews(key)` hook and adopt it on ClientList/DevisList/FactureList/StockList/TicketsPage. (Gate: ROUTINE.)
- [ ] FG12 — Wire the existing dark-mode/theme toggle into the app shell. `design/ThemeToggle` is rendered only on `/ui` (UIShowcase); add it to `components/layout/Header.jsx` and confirm `ThemeProvider` wraps the authenticated app. (Gate: ROUTINE — distinct from the Group J restyle.)
- [ ] FG13 — Surface a push-notification opt-in toggle in settings. Web-push is fully built backend (`PushSubscription`) + helper (`pushSubscribe.js`) but headless. Add an "Activer les notifications push" switch in `/parametres/notifications` showing subscription state. (Gate: ROUTINE.)
- [ ] FG14 — Bulk import for more entities. `dataimport` covers only leads/clients/products though export covers 17 types. Add `equipements`, `fournisseurs` (and optionally `devis`) to `FIELD_MAPS` + commit branches (create-only/dedup/atomic) reusing the existing import modal. (Gate: ROUTINE.)
- [ ] FG15 — Broaden audit-trail coverage + a generic soft-delete/restore standard. `audit/signals.py TRACKED_MODELS` misses money/security writes (BonCommande, Paiement, supplier procurement, StockReservation, ContratMaintenance, `publicapi.ApiKey`/`Webhook` issue/revoke); only Lead/Produit have archive/restore. Add the missing tracked pairs (ROUTINE) and phase in a shared archive/restore mixin for Devis/Facture/Chantier/Ticket/Client (SCHEMA+DECISION). (Gate: ROUTINE for audit; SCHEMA for soft-delete.)
- [ ] FG16 — In-app onboarding / setup checklist + contextual help. No tour/guided help exists. Add a dependency-free spotlight/coachmark sequence keyed on a localStorage "seen" flag + a Paramètres "setup checklist" (company profile, first product, first user). (Gate: ROUTINE; DECISION on scope/copy.)

### Paramètres / RBAC / auth & security

- [ ] FG17 — Email template management (parity with WhatsApp templates). Only WhatsApp templates are modelled; the automation email action falls back to a hardcoded "Notification Taqinor" subject. Add editable `sujet`+`corps` per `cle` (extend `MessageTemplate` or add `EmailTemplate`) with `{civilite}{nom}{reference}{lien}` placeholders + editor in `EmailSection.jsx`. (Gate: SCHEMA.)
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

- [ ] FG27 — Lead scoring. No lead-quality score exists (only manual `priorite`; `_completeness` is merge-only). Add `scoring.py compute_score(lead)` from existing fields (bill amount, canal, type_installation, recency, completeness) exposed read-only on the serializer + a kanban badge + a FilterBar sort. (Gate: ROUTINE; SCHEMA only if persisted.)
- [ ] FG28 — First-response SLA + "lead non contacté" alert. No first-response clock; nothing flags an untouched NEW/site_web lead. Add nullable `first_contacted_at` (set on first transition/note) + a beat sweep (configurable `lead_sla_hours`) → red kanban badge + a "Non contactés > Xh" filter (pairs with FG1). (Gate: SCHEMA.)
- [ ] FG29 — Time-in-stage age + funnel-velocity analytics. `LeadActivity` logs stage-change timestamps but nothing computes stage dwell time; cards show no age and there's no per-stage velocity chart. Derive `stage_since` on the serializer (age pill on cards) + an avg-days-per-stage + stalled-leads view in reporting (`pipeline.py`/`insights`). (Gate: ROUTINE.)
- [ ] FG30 — Unified communication log (calls/emails) in the chatter. Chatter logs only auto field-changes + free notes; no typed "appel passé (résultat)" or email send/receive entry (only the WhatsApp link-builder). Add a typed-interaction action (reuse `records.Activity` Appel/Email types or a `Kind.APPEL` + optional `outcome`) + quick-log buttons. (Gate: ROUTINE; SCHEMA if adding `outcome`/`Kind`.)
- [ ] FG31 — "File de relance du jour" consolidated queue. `relance_date` + client-side filters exist but there's no cross-lead overdue-relance work queue. Add `leads/relances/?scope=overdue|today|week` (visibility-scoped) + a "Relances" panel/badge on LeadsPage. (Gate: ROUTINE.)
- [ ] FG32 — Client segmentation (RFM / dormant / top). `ClientList` segments only by `type_client`. Add computed segment filters (top clients, sans devis >12 mois, à recontacter) driven by the existing serializer totals + derived last-devis/facture dates. (Gate: ROUTINE.)
- [ ] FG33 — Bulk WhatsApp outreach. `apply_bulk_action` has no batched WhatsApp; sending is per-lead. Add a `prepare_whatsapp` bulk op returning an ordered `{phone, wa_url}` click-through queue (reuse `build_wa_url`; no auto-send). (Gate: ROUTINE.)
- [ ] FG34 — Source/campaign ROI analytics. `fbclid`/`utm_*` first-touch is captured on `Lead` but never analyzed; ChartsView shows per-canal counts only. Add a per-canal/per-campaign aggregation (lead count, signed count, win-rate, signed value) — turns wasted attribution data into ad-spend guidance. (Gate: ROUTINE.)
- [ ] FG35 — "Lead express" quick capture. The only creation path is the heavy multi-section `LeadForm`. Add a ⚡ minimal modal (nom/téléphone/canal=walk_in/owner=me) posting to the existing create endpoint with inline duplicate pre-check — for walk-ins/salons/mobile. (Gate: ROUTINE.)
- [ ] FG36 — Reusable WhatsApp message templates in CRM. Only the devis-link message is hardcoded (FR/Darija); no reusable premier-contact/relance/fête templates. Add `crm.MessageTemplate` (company, nom, langue, corps with `{prenom}/{ville}/{lien}`, archived) + CRUD + a picker in the lead WhatsApp action. (Gate: SCHEMA.)
- [ ] FG37 — Lead pipeline map view. `gps_lat/lng` are captured but the 4 views are kanban/liste/calendrier/graphique — no map. Add a 5th `CarteView` plotting filtered leads by GPS, coloured by stage, click→lead, to batch site visits by region. (Gate: DEP:leaflet — verify if a map lib already ships for `reporting/geo`; if yes → ROUTINE.)
- [ ] FG38 — Lead↔Client duplicate match at creation. Duplicate detection scans only across Leads; a returning customer comes in as a fresh lead. Extend `check-duplicates` (or add `leads/{id}/client-match/`) to scan `Client` by normalized phone/email → a "Déjà client X (N devis/chantiers)" banner in LeadForm. (Gate: ROUTINE.)
- [ ] FG39 — Sales objectives & KPI targets vs actuals. No target/objective concept exists anywhere; KPIs show actuals with no goal line. Add `ObjectifCommercial`/`KpiTarget` (company, owner/metric, period, cible) + a "objectif vs réalisé" panel per commercial and company-wide attainment gauges on the dashboard. (Gate: SCHEMA + DECISION on metrics/periods.)

### Ventes / facturation

- [ ] FG40 — Recurring maintenance-contract billing. `ContratMaintenance.prix`/`periodicite` exist and preventive tickets are materialized, but **no Facture is ever produced** from a contract — recurring O&M revenue leaks. Add a beat job + manual `contrats-maintenance/{id}/facturer` that creates a `Facture` via a new `ventes.services.creer_facture_contrat` (cross-app from sav via services) + a `derniere_facturation`/`facturation_active` field; optionally a covered-equipment M2M. (Gate: SCHEMA.)
- [ ] FG41 — Client credit limit / encours gate. `Client` has no `plafond_credit`; nothing warns when a new quote/invoice pushes a client past their outstanding balance. Add `plafond_credit` + a soft warning banner on DevisGenerator/FactureForm and on accepter/émettre (warn, never hard-block). (Gate: SCHEMA.)
- [ ] FG42 — Bank-statement payment import & reconciliation. `Paiement` is created one-at-a-time; no statement import, reference-matching, or "à rapprocher" queue. Add a `paiements/import-releve` flow (reuse the dataimport dry-run+commit + openpyxl) matching by reference/montant, reusing the existing over-payment guard. (Gate: ROUTINE.)
- [ ] FG43 — Invoice bulk operations. `FactureViewSet` has no bulk action — émission/relance/PDF/email are per-row (DevisList already batch-PDFs). Add `factures/bulk` (emettre/relancer/envoyer-email/generer-pdf, company-scoped, per-id results) + a select-all bar in FactureList. (Gate: ROUTINE.)
- [ ] FG44 — Quote refusal with motif. There's `accepter` but no symmetric `refuser` — a quote goes refuse/expire via raw PATCH capturing no reason (`Devis` has no `motif_refus`, unlike `Lead.motif_perte`). Add a `devis/{id}/refuser` action (date + motif + chatter + optional lead `perdu` sync via the event bus). (Gate: SCHEMA.)
- [ ] FG45 — Ventes quote-to-cash finance dashboard. No ventes dashboard ties the document chain together. Add a read-only aggregation (devis envoyés→acceptés→facturés→encaissés conversion, quote-to-cash cycle, DSO, encaissé-vs-facturé, per-commercial pipeline value) + a `/ventes` dashboard tab. (Gate: ROUTINE.)
- [ ] FG46 — Flexible échéancier + stored acompte. `utils/echeancier.py` hardcodes exactly 3 tranches (acompte/materiel/solde) in fixed order/percent, and a custom acompte is a render-only PDF flag never stored — so the proposal's deposit and the generated invoice can disagree. Add an optional per-devis `echeancier` JSON (ordered `{libelle,type,pct_or_montant}`) + persist `acompte_montant/pct`, degrading to today's 3-tranche default when empty. (Gate: SCHEMA.)
- [ ] FG47 — Cash-flow / receivables forecast. Aged balance exists but there's no forward projection. Add `insights/cash-flow/` bucketing outstanding `Facture.montant_du` by `date_echeance` into upcoming weeks/months, optionally netting `FactureFournisseur` payables (admin-only) for a true cash view. (Gate: ROUTINE.)
- [ ] FG48 — On-screen two-option quote comparison. The engine computes both options (sans/avec batterie) with ROI, but DevisList shows only option 1; the salesperson can't present A vs B interactively. Surface `totaux_sans/avec` + ROI per option from the serializer in a DevisGenerator/detail comparison card. (Gate: ROUTINE; data already computed.)
- [ ] FG49 — Account-coded accounting export (PCG/Sage layout). `exports.py` gives a journal + per-rate TVA summary but no general-ledger export with account codes (7xxx ventes / 4455 TVA / 3421 clients) for direct fiduciaire import. Add a third export format mapping buckets to configurable account codes. (Gate: ROUTINE + DECISION on default codes.)
- [ ] FG50 — Acompte transfer/refund on invoice cancel. `annuler` leaves a cancelled invoice's `Paiement` rows stuck on a dead invoice with no transfer/refund path. On cancel, offer "transférer l'acompte" to another facture of the same devis or mark refundable (negative Paiement / Avoir), with chatter. (Gate: DECISION (accounting semantics) + SCHEMA.)
- [ ] FG51 — Proof-of-delivery gate before invoicing. `BonCommande.marquer_livre` flips status + decrements stock but captures no PV/signature, and `generer-facture` never checks delivery happened. Optionally link a `documents` PV/attachment to the BC + a soft warning on the matériel tranche when no delivery proof exists. (Gate: ARCH/DECISION; route cross-app via selectors.)
- [ ] FG52 — Multi-currency quoting/invoicing. Everything is hardcoded MAD (no `devise`/`taux_change` on Devis/Facture, none in CompanyProfile, UBL hardcodes currency). Add `devise`(default MAD)+`taux_change` carried through the PDF builder + `dgi_export.py`. (Gate: SCHEMA + DECISION on currencies + legal-MAD-equivalent rules.)
- [ ] FG53 — E-payment "Payer en ligne" link. No payment gateway anywhere; ShareLink/WhatsApp/relance deliver a read-only PDF only. Add a `PaymentLink` model + a provider-interface (NoOp default, like `monitoring/providers`, no dep when unconfigured) + a public pay page + a webhook that records a `Paiement`. (Gate: DEP:<gateway SDK> + COST + AUTH — propose the NoOp scaffold now, live gateway gated.)

### Stock & procurement

- [ ] FG54 — Reorder-point auto-PO suggestions. The only reorder signal is a passive low-stock flag; the one auto-PO path is chantier-driven, never inventory-driven. Add `produits/a-reapprovisionner/` (disponible ≤ seuil, grouped by cheapest supplier) + `generer-bcf-reappro/` reusing `create_with_reference('BCF')`; optional `quantite_reappro_cible`. (Gate: SCHEMA for the optional field; endpoints ROUTINE.)
- [ ] FG55 — Supplier-invoice PDF (facture fournisseur). BCF has an internal PDF but `FactureFournisseur` has none (explicit G5 future). Add `factures-fournisseur/{id}/pdf/` via the existing WeasyPrint helper + a download button. (Gate: ROUTINE.)
- [ ] FG56 — "Facturer cette réception" line-driven supplier invoice. `FactureFournisseur` amounts are typed by hand; `LigneFactureFournisseur` exists but no flow populates it from a reception (explicit G5 future). Add `receptions-fournisseur/{id}/facturer/` building lines + HT/TVA/TTC from the reception + a "Facturer" button. (Gate: ROUTINE.)
- [ ] FG57 — Dead-stock / rotation aging report. `stock_report` has no "no movement since N days" analysis though `MouvementStock.date` is a full audit trail. Add `produits/rotation/?jours=180` (last-movement date + tied-up value via `average_cost`, buckets), admin-only. (Gate: ROUTINE.)
- [ ] FG58 — Supplier price-list comparison UI. `PrixFournisseur` is modelled + exposed but there's no comparison screen — the buyer can't see "A 1,200 vs B 1,150, last bought 3 mo ago". Add a "Comparer fournisseurs" panel on the product/BCF screen (admin/buyer-only). (Gate: ROUTINE.)
- [ ] FG59 — Supplier performance scorecard. All raw data exists (BCF date vs reception date = lead time; quantite_recue vs quantite = fill rate; returns = defect rate) but nothing aggregates it. Add `fournisseurs/{id}/performance/` (avg lead time, fill rate, return rate, spend), admin-only. (Gate: ROUTINE.)
- [ ] FG60 — Stock-movement filters + xlsx export. `MouvementStockViewSet` supports only search/ordering and has no export (valuation does). Add `?type_mouvement/?produit/?date_min/?date_max` filters + `mouvements/export-xlsx/` reusing `build_xlsx_response` for month-end reconciliation. (Gate: ROUTINE.)
- [ ] FG61 — Serial/lot capture at goods-in. Serials live only on `sav.Equipement` (captured at install); the stock layer has none, so a received inverter serial can't be reconciled to the installed one for warranty/RMA. Add `LigneReceptionFournisseur.numeros_serie` (JSON) captured at reception + a reconcile selector. (Gate: SCHEMA.)
- [ ] FG62 — Per-location min/max + van replenishment. `seuil_alerte` is a single global threshold; multi-location carries quantity only, so a camionnette can't be flagged low. Add `StockEmplacement.seuil_min/max` + a "réapprovisionner cet emplacement" suggestion proposing transfers from the principal. (Gate: SCHEMA.)
- [ ] FG63 — Inventory-count session workflow. `apply_inventory_count` posts adjustments immediately/irreversibly in one shot — no draft, partial save, or large-variance review for a real stock-take. Add `InventaireSession`+`LigneInventaire` (draft) with a `valider` action emitting the AJUSTEMENT movements + an écart report. (Gate: SCHEMA.)
- [ ] FG64 — Battery/sealant expiry tracking. No expiry fields anywhere; lithium batteries and sealants have shelf-life/expiry and installing one out-of-date voids warranty. Add optional `LigneReceptionFournisseur.date_peremption`/lot + an "expiring soon" report (lighter subset of FG61). (Gate: SCHEMA.)
- [ ] FG65 — Demand forecasting reorder quantities. `seuil_alerte`/reorder qty are static; `MouvementStock` SORTIE history is never used. Add a selector computing avg monthly consumption per SKU → suggested reorder qty feeding FG54. (Gate: ROUTINE; depends on FG54.)
- [ ] FG66 — Kit/BOM as a sellable catalogue product. No kit/nomenclature concept in stock (KitOutillage is durable tools only); standard configs ("Kit pompage 3CV", "Kit résidentiel 5kWc") must be quoted line-by-line each time. Add a `Produit.composition`/`KitProduit` that explodes into component SKUs at devis-line insertion (accurate reservation for the bundle). (Gate: DECISION — touches the quote engine + SCHEMA.)
- [ ] FG67 — FIFO / landed-cost valuation option. Valuation is weighted-average only; no FIFO and no landed-cost (freight/customs), so imported-inverter true cost is understated. Add `LigneBonCommandeFournisseur.frais_annexes` folded into average_cost + an optional FIFO toggle (`CompanyProfile.stock_valuation_method`), internal only. (Gate: SCHEMA + DECISION on accounting method.)

### Installations / field execution / outillage

- [ ] FG68 — Crew dispatch calendar + technician capacity for interventions. `InterventionsPage` has only liste+kanban (chantiers have a calendar, interventions don't), so a PM can't see who's over/under-booked on a day or drag a visit between techs. Add a `calendrier` view keyed on `date_prevue` (columns per technicien) + an `interventions/?date_from&date_to` range filter, reusing the chantier drag-reschedule pattern. (Gate: ROUTINE.)
- [ ] FG69 — Captured client signature (sign-off) on compte-rendu / PV de réception. The compte-rendu template renders an **empty** signature box; no signature is captured anywhere. Add `Intervention.signature_client` (vector strokes like `PhotoAnnotation.drawing`, or a PNG attachment + `signataire_nom`/`signe_le`) + `interventions/{id}/signer-client` + a signature-pad panel, embedded in the PDF; same for the Installation PV. (Gate: SCHEMA.)
- [ ] FG70 — Auto warranty handover at RECEPTIONNE. At réception the code only writes a chatter note; it doesn't sweep the frozen `bom` into `sav.Equipement` for serial-less components, so warranty coverage depends on a tech remembering each serial. On the RECEPTIONNE transition call a `sav.services` fn to ensure one `Equipement` per BoM line (serial optional, date_pose=date_reception, idempotent) + a handover summary/PDF section. (Gate: ROUTINE; cross-app write via services.)
- [ ] FG71 — Per-chantier job-costing roll-up. The pieces exist (`labour_jours_estimes/reels`, `MaterielConsommation` variance, `prix_achat`) but nothing assembles labour + real material cost vs the devis total into a margin view. Add `chantiers/{id}/cout` (labour estimé/réel + materials BoM-vs-real + devis total → margin), **internal/admin-only** (margin ban on client docs). (Gate: DECISION confirm internal-only; else ROUTINE.)
- [ ] FG72 — Multi-day chantier planning. `Installation` has single `date_pose_prevue/reelle`; a multi-day pose is counted as one day and overbooks the crew. Add `date_pose_fin_prevue`/`duree_pose_jours`, rendered as a span on the chantier calendar + factored into capacity. (Gate: SCHEMA.)
- [ ] FG73 — Technician day route/itinerary. `MaJourneePage` lists today's interventions in date order with no geographic ordering; `haversine_km` + site GPS already exist. Add a nearest-neighbour ordering from the dépôt + a per-stop "Itinéraire" maps deep-link (and optional `interventions/ma-tournee`). (Gate: ROUTINE; DEP only if true road optimization is wanted.)
- [ ] FG74 — Cross-chantier Gantt / milestone timeline. `ChantierTimeline` is single-chantier; a PM running 10–30 concurrent chantiers has no horizontal timeline across the existing milestone dates. Add a `gantt` view (one row per chantier, bars from milestone dates) — read-only first. (Gate: ROUTINE; no new backend.)
- [ ] FG75 — Roof/drone site-survey attachment surface on the chantier. Field photos are intervention-phase only; there's no chantier-level pre-pose "Relevé de toiture / drone" gallery distinct from the day-of shot list. Add a chantier-level attachments panel (category `releve_toiture`/`drone`) reusing `records.Attachment` + the MinIO proxy. (Gate: ROUTINE.)
- [ ] FG76 — Photo-required gate on chantier checklist steps. F8 photo-gating is intervention-only; a chantier step ("Panneaux posés") can be ticked with zero evidence. Add `photo_obligatoire` to `ChecklistEtapeModele`/`ChantierChecklistItem` and block `fait=True` until a phase photo exists (mirror the intervention logic). (Gate: SCHEMA.)
- [ ] FG77 — Pre-pose readiness check. Chantier status can move to EN_COURS freely with no guard on material availability or the 82-21 dossier. Add a `chantiers/{id}/readiness` selector (material shortfall via besoin-materiel, dossier status, planning date) surfaced as a banner in InstallationDetail; optionally a confirm-to-override. (Gate: ROUTINE advisory / DECISION if it should hard-block.)
- [ ] FG78 — Intervention RDV confirmation + reschedule/no-show tracking. `Intervention` has dates but no client-confirmation flag, reschedule history, or no-show reason (statut state machine stays untouched — these are metadata). Add `rdv_confirme`/`rdv_confirme_le` + a reschedule count + a "Confirmer le RDV" action feeding reminders. (Gate: SCHEMA.)
- [ ] FG79 — Auto-scaffold the standard intervention chain from chantier type. Checklist templates auto-select by type and kits by intervention type, but the expected sequence of visits (résidentiel réseau → pose/raccordement/mise en service) is created one-by-one. Add a `TypeInterventionPlan` (per type_installation, ordered intervention types) + a `creer-interventions-standard` action materializing the chain. (Gate: SCHEMA.)
- [ ] FG80 — Outillage calibration/inspection tracking. `Outillage` tracks statut/emplacement/date_achat but no calibration/inspection dates — multimètres, earth testers, and harnais (EPI) legally need periodic checks (a safety/compliance liability). Add `date_derniere_calibration`/`intervalle_calibration_mois`/`date_prochaine_calibration` + an "à calibrer" badge + a notification event. (Gate: SCHEMA.)

### SAV / parc / maintenance / monitoring

- [ ] FG81 — Server-side ticket SLA (response/resolution clocks + breach). SLA is client-side cosmetic only; `Ticket` has no first-response timestamp, no target, no breach flag, and `SAV_TICKET_BREACHING` is never emitted. Add `Ticket.date_premiere_reponse` + per-company `sla_response_days`/`sla_resolution_days` (or a `sav_sla` JSON per priorité) + computed `sla_breach`/`sla_due_at` + a daily breach scan → notification. (Gate: SCHEMA; pairs with FG1.)
- [ ] FG82 — Maintenance-visit checklist / structured visit report. Preventive tickets + the maintenance PDF carry no inspection checklist (clean panels, torque, inverter logs, earth test) — the report is free text. Add `MaintenanceChecklistTemplate`/`Item` (per-company, seeded) + per-ticket `TicketChecklistItem`, rendered into the maintenance PDF (mirror the installations checklist pattern). (Gate: SCHEMA.)
- [ ] FG83 — Supplier warranty-claim (RMA) workflow. A ticket knows `sous_garantie` + equipment + supplier, but there's no claim object — so in-warranty defects sent back to the OEM (Huawei/VEICHI/panel maker) are untracked and the installer eats replacement cost. Add `WarrantyClaim` (equipement, fournisseur, ticket, statut, rma_ref, dates, resolution remplacement/avoir, internal cout_recupere) routed to the supplier via `stock.selectors`. (Gate: SCHEMA.)
- [ ] FG84 — Per-system production history chart + expected-vs-actual + CSV. `ProductionPage` is a flat manual-entry list — no chart, trend, or expected-vs-actual surfaced, though readings + an expected ratio exist. Add `monitoring/configs/{id}/history/` (monthly aggregated + expected overlay) + a Recharts line chart + CSV export per installation. (Gate: ROUTINE; recharts already a dep.)
- [ ] FG85 — Equipment QR labels + scan-to-equipment/ticket. The QR/CODE128 engine + resolve endpoint exist only for `stock.produits`; SAV equipment has a serial but no scannable label and no `EQUIP:` token. Add `equipement_token` + an `EquipementViewSet.etiquettes` action (reuse `labels.render_labels_html`) + extend `resolve_code` to `EQUIP:<id>` (warranty clock + open tickets / open a ticket). (Gate: ROUTINE; reuses the label engine.)
- [ ] FG86 — Public tokenized "track your SAV request" link. Quotes/invoices have public tokenized links but tickets aren't exposed publicly at all. Add `Ticket.share_token` + a read-only public endpoint returning reference/statut/last-update only (never `cout` or internal chatter) + a "Lien client" button. (Gate: SCHEMA + DECISION on what a client may see.)
- [ ] FG87 — SAV knowledge base (resolution playbooks). No KB exists; ticket resolutions evaporate as free-text chatter though solar faults repeat (inverter error codes, string faults). Add `KbArticle` (per-company titre/corps/tags + optional produit/categorie) + a searchable panel on TicketsPage filtered by the ticket's equipment product. (Gate: SCHEMA.)
- [ ] FG88 — Maintenance route/day planning for preventive visits. Visits generated from contracts spawn undated, ungrouped tickets though installation GPS exists. Add a "planifier la tournée" view listing due preventive tickets with GPS, letting a responsable bulk-assign technician+date (proximity-sorted from stored coordinates). (Gate: ROUTINE coordinate-sort; DEP/COST only for real routing.)
- [ ] FG89 — Spare-parts forecasting from PieceConsommee history. `PieceConsommee` records SAV part usage + decrements stock but nothing aggregates it to forecast spares (fuses, MC4, breakers) — a stuck tech means a second truck roll. Add `insights/sav-parts-forecast/` (consumption per product over a window + suggested reorder qty), internal-only. (Gate: ROUTINE.)
- [ ] FG90 — Chronic/repeat-failure equipment flag. A ticket links one equipment + exposes open-ticket count, but there's no detection of an item generating repeated tickets over time (a "lemon" — the strongest warranty-claim evidence, ties to FG83). Add a computed `nb_tickets_12m` to the serializer + a filter/badge + an optional repeat-offender insight. (Gate: ROUTINE.)

### Reporting / analytics / custom fields

- [ ] FG91 — SavedReport frontend (CRUD + schedule + optional dashboard pin). The `SavedReport` model + viewset + scheduled-email beat job are fully built but have **zero frontend** (and no `pinned` field) — a shipped backend feature is unusable. Add `reportingApi` methods + a "Mes rapports" UI (create/name/schedule/recipients/delete) + optional `pinned` to render a saved report as a dashboard card. (Gate: ROUTINE; SCHEMA only for the pin field.)
- [ ] FG92 — Period comparison (MoM/YoY) on dashboard & reports. Nothing computes a prior-period baseline anywhere. Add a `compare=prev|yoy` param to `dashboard/` + `reports/*` returning `{current, previous, delta_pct}` per KPI + arrows/deltas on the Stat cards. (Gate: ROUTINE.)
- [ ] FG93 — Sales-rep leaderboard. `sales_report` has a flat per-responsable count table but no monetary leaderboard (CA signed, win rate, avg deal, kWc per rep) and it's not surfaced on the dashboard. Add `insights/sales-leaderboard/` + a "Classement commerciaux" card (responsable-visible; keep commission/buy-price admin-only). (Gate: ROUTINE.)
- [ ] FG94 — Activate custom-field reporting. `CustomFieldDef.visible_liste` is settable but **nothing consumes it** — no list column, no `custom_data` filter, no aggregation (dead flag). Honor `visible_liste` as a column + a `?cf_<code>=` filter on Lead/Client/Produit lists + a group-by-custom-field count. (Gate: ROUTINE.)
- [ ] FG95 — PDF export for reports (branded). Every report/insight exports xlsx only; WeasyPrint+Jinja2 are already pinned. Add `?export=pdf` on `reports/*` rendering a company-branded template (logo from CompanyProfile), never buy prices — for presentable monthly reports to stakeholders/banks. (Gate: ROUTINE.)
- [ ] FG96 — Configurable / per-role dashboard. `Dashboard`/`Reporting` are fully static — a technicien sees the same finance-heavy dashboard as the founder. Add a per-user/per-role widget config (enabled cards + order); minimal first cut = role-default card sets driven off `menu_tier`. (Gate: SCHEMA + DECISION on configurability scope.)
- [ ] FG97 — Audit-log analytics. The Journal is a filterable feed + activity buckets but has no rollups (most-active users, action mix over time, failed-login spikes, object churn). Add `audit/analytics/` (gated on `journal_activite_voir`) + a charts panel on the Journal page. (Gate: ROUTINE.)
- [ ] FG98 — Cohort / seasonality conversion analysis. No cohort view; solar demand is seasonal + channel-dependent. Add `insights/cohorts/` grouping leads by acquisition month (and/or canal) → eventually-signed % + avg days-to-sign per cohort (heatmap/table). (Gate: ROUTINE.)
- [ ] FG99 — Profitability by segment. `job_costing` is per-chantier only; there's no margin/revenue aggregation by `mode_installation`/`canal`/category. Add `insights/profitability/` (admin-only, reuses `prix_achat` internally, never client-facing) grouping revenue+margin+count by segment. (Gate: ROUTINE.)
- [ ] FG100 — Custom fields for Devis / Chantier / Ticket. `CustomFieldDef.Module` is limited to LEAD/CLIENT/PRODUIT; the operational core can't carry custom attributes ("numéro dossier ONEE", "type de nacelle"). Add INSTALLATION/DEVIS/TICKET to the choices + `custom_data` JSONField where missing + wire validation + Paramètres tabs. (Gate: SCHEMA — additive JSONField.)
- [ ] FG101 — Drill-down from report rows/charts to filtered lists. Dashboard KPI Stats are clickable but report tables/charts are dead ends (a "perte par motif" row, a funnel stage, a stock-alert row link nowhere). Make report rows/segments link to the relevant filtered list route. (Gate: ROUTINE; may add a few list-filter params.)

### Integrations — public API / webhooks / OCR

- [ ] FG102 — Webhook delivery log + retry/replay + test ping UI. `WebhookDelivery` records every attempt and the viewset exposes the last 50, but there's no replay/retry endpoint and `ApiWebhooksSection.jsx` never shows deliveries — a failed `facture.paid` is silently lost. Add `webhooks/{id}/deliveries/{id}/replay/` + `webhooks/{id}/test/` + the delivery history/status/replay/test UI. (Gate: ROUTINE.)
- [ ] FG103 — More webhook events. Only 4 terminal events exist (lead.created/devis.accepted/chantier.completed/facture.paid). Add codes + emitters for devis.sent, lead.lost/stage_changed, facture.created, intervention.completed, ticket.created/resolved, paiement.recorded (reuse the existing transition-diff pattern; the Paramètres checkbox list auto-updates). (Gate: ROUTINE.)
- [ ] FG104 — Public API filtering, ordering & incremental sync. The public viewsets have no filter_backends and no `?updated_since=`, so a consumer must full-scan the company list every poll. Add DjangoFilterBackend+OrderingFilter + a whitelist of filter fields + `?updated_since=` against `date_modification` (add it to `PublicChantierSerializer`). (Gate: DEP:django-filter, or hand-rolled query-param filtering = ROUTINE.)
- [ ] FG105 — Public API documentation page. No OpenAPI/Swagger anywhere; the API & Webhooks screen issues keys but documents no endpoints/scopes/`Api-Key` header/`X-Taqinor-Signature` HMAC recipe. Add a static FR reference page (endpoints, auth, scopes, events, HMAC-verify snippet) linked from the settings screen. (Gate: ROUTINE static doc; DEP:drf-spectacular only if auto-generated.)
- [ ] FG106 — OCR → draft lead / draft devis action. OCR extracts structured supplier-quote/bill data but its only sink is the OCR table (+ the existing OCR→stock flow). Add a "Créer un lead / brouillon de devis depuis ce document" action on `OcrUpload.jsx` posting parsed fields to the existing CRM/ventes create endpoints. (Gate: ROUTINE.)

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

## GATED — needs Reda's decision before building (agent does NOT auto-build)

The agent must **not** start these. They cost money, change auth, add a new module/architecture, or
need Reda's taste. Reda decides; then I write a focused task and move it into the BUILD QUEUE.

- **G1 — Real email sending** (devis/facture/relance by email). **UNGATED 2026-06-18 → BUILD QUEUE
  (N87/N88, Brevo).** Provider chosen = **Brevo** (SDK or SMTP), key from settings/env, no-op
  without a key; pre-approved (see the PRE-APPROVED block). No longer a blocker.
- **G2 — WhatsApp Business Cloud API** (true auto-send + PDF *attached*, message templates). STILL
  GATED — unblocks when Reda provides: Meta Business **verification** + a WhatsApp Cloud API **access
  token**, the **phone-number ID**, and an **approved template name**. Cost + Meta Business setup (Month-2 roadmap).
- **G3 — Full document visual redesign** (devis/facture/bon de commande). **Still GATED** — the
  full visual redesign **needs your gallery approval** (taste) and is a deliberate non-goal for an
  unattended run; `PDF_ENGINE=legacy` stays as the fallback. **PARTIAL UNGATE 2026-06-18 → BUILD
  QUEUE (N106):** only the two additive deliverables in the EXISTING premium visual language — the
  three escalating-tone relance letters and the one-page after-sale handover/warranty sheet — were
  ungated; the redesign itself stays here. STILL GATED 2026-06-20 — the full devis/facture/BC redesign needs a deliberate design pass with **gallery review**; the premium devis engine (`generate_devis_premium.py`) stays off-limits.
- **G5 — Supplier procurement module** (bons de commande fournisseur, goods-in/receiving, supplier
  invoices / accounts payable). **UNGATED 2026-06-20 → BUILD QUEUE (G5, under « Procurement & inventory »).** Approved as a dedicated multi-session module.
- **G6 — Stock auto-decrement on installation** (a chantier consumes its equipment from stock).
  **UNGATED 2026-06-18 → folded into BUILD QUEUE N14.** The exact rule is now confirmed and
  pre-approved: **reserve on chantier create → decrement on « Installé » → release on
  cancel/close** (see the PRE-APPROVED block). No longer a blocker.
- **G7 — Quote e-signature.** STILL GATED — pending Reda's choice of a **paid external e-signature provider**. LOW PRIORITY: lightweight in-OS quote acceptance already exists, so this only adds certified third-party signing.
- **G8 — 2FA / SSO.** **2FA UNGATED 2026-06-20 → BUILD QUEUE (N96)** — auth change approved, pyotp approved, built OPT-IN per user (never locks out existing users). SSO stays gated (separate provider / architecture).
- **G9 — Automation engine / scheduler.** **UNGATED 2026-06-18 → BUILD QUEUE (G9).** Decision made:
  **Celery Beat (in-app)**, two scheduled jobs in Africa/Casablanca time — scheduled relance
  reminders + a daily facture-overdue check (overdue = échéance passed & not fully paid → « En
  retard »; default échéance = issue + 30 days). Pre-approved (see the PRE-APPROVED block). The
  broader no-code automation engine (N72/N73) and n8n workflows stay separate.
- **G10 — CAPI service** (Meta Conversions API, sends `SignedQuote` on Signé, EMQ ≥ 7.0). **First half
  — lead-source capture (fbclid + UTM on the lead model and the apps/web form) — UNGATED 2026-06-20 →
  queued as the TOP item of `docs/PLAN2.md`.** The **second half (the CAPI SEND itself) STAYS GATED**,
  pending Reda's **Meta pixel access token**; only the CAPI send remains once the capture ships.
- **G11 — Chatbot → Reda's Claude API key.** STILL GATED — unblocks when Reda provides a **Claude API key** and **approves the per-use cost**. Small but a cost change.
- **G12 — MCP server + Microsoft 365** (Entra ID, Outlook, OneDrive, Teams). STILL GATED — unblocks when Reda provides **M365 / Entra access**. Roadmap.
- **G13 — Import of the 619 real Odoo leads.** The idempotent importer is **already built**; STILL
  GATED — unblocks on a **fresh Odoo backup file**. The backup holds PII → must **never be committed**
  (gitignored, never in chat/GitHub).
- **G14 — DGI e-invoicing readiness (Morocco).** Mandatory ~**Jan 2027** for businesses with CA >
  500k DH — likely Taqinor's wave. **PARTIAL UNGATE 2026-06-18 → BUILD QUEUE (N105):** only the
  **silent, backend-only local capability** was ungated — on-demand **UBL 2.1 / CII** XML export
  (recipient ICE on every line) + a conformity validator, both behind a master toggle that defaults
  OFF and is completely invisible while off. **STILL GATED here** (blocked on the unpublished DGI
  implementing decree — no API spec exists yet, not a decision of Reda's): the **Simpl-TVA portal
  transmission** and the **certified e-signature** (a PDF is explicitly NOT compliant; clearance
  needs the live DGI platform). Start those when the specs publish. CONFIRMED 2026-06-20 — the silent local UBL/XML export already shipped (N105); only the DGI portal transmission + certified e-signature wait on the unpublished DGI implementing decree.
- **G15 — Arabic / Darija UI** (full interface localization, not just message templates). **UNGATED
  2026-06-20 → BUILD QUEUE (N93/N94)** — i18n framework approved. SEQUENCING: run as the FINAL step of
  the UI/UX overhaul (after the component restyle); not prioritized — pull forward only on Reda's
  explicit instruction.
- **G16 — Heavy modularity options (deferred, NOT recommended now).** The two heaviest
  decoupling moves from the 2026-06-20 modularity review, recorded for completeness and held
  here so no unattended run starts them: (a) extracting a bounded context into its own
  deployable service (like `fastapi_ia`), and (b) turning each Django app into a versioned,
  pip-installable package. Both are large, risky migrations against a shared Postgres and the
  single `company` tenant threaded through every model, with low payoff for a single-installer
  ERP. Defer until a module genuinely needs independent scaling/deploy; the M1–M7 in-monolith
  decoupling delivers the modularity benefit first.

### From the 2026-06-18 refinement audit — gated copies (do NOT auto-build)

Mirror of every non-ROUTINE task in the REFINEMENT QUEUE above, kept here so an unattended run
never auto-builds them. Each still lives in its module section above; build only after Reda's call.

**SCHEMA — needs an additive DB migration (still gated)**
_(none — the three SCHEMA refinements (client ICE export, client `created_by`/`date_modification`,
`type_equipement` tag on `stock.Categorie`) were UNGATED 2026-06-18 to `[ROUTINE]` in their module
sections; additive migrations are pre-approved — see the PRE-APPROVED block.)_

**DEP — needs a dependency beyond openpyxl / vite-plugin-pwa**
_(none — the Parc « Carte » Leaflet refinement was UNGATED 2026-06-18 to `[ROUTINE]`; Leaflet is
pre-approved — see the PRE-APPROVED block + N85.)_

**DECISION — needs Reda's product call**
_(none remaining — 2026-06-20: L17 « Langue préférée » UNGATED to `[ROUTINE]`; L7 « En retard » matérialisé RESOLVED + DONE — already shipped via the G9 daily job (`check_overdue_factures` flips the stored `statut` → `en_retard`), see docs/DONE.md.)_
_(UNGATED 2026-06-18 to `[ROUTINE]` in their module sections — see the PRE-APPROVED block:
saved named views (local, no email); comptable export; per-company `Equipement` serial uniqueness;
Stock-category management UI; Fournisseurs management screen; Retours list; public ShareLink
noindex + per-token throttle.)_

**GALLERY — changes a client-facing PDF/visual (needs gallery approval)**
_(none remaining — 2026-06-20: L13 (escalating-tone relance letter) and L4 (in-app after-sale PDF preview) both UNGATED to `[ROUTINE]` in their module sections on Reda's explicit approval; the premium devis engine stays off-limits.)_

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
