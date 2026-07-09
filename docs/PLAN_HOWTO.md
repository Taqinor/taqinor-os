# Taqinor OS — Plan run HOW-TO, STANDING RULES & ALREADY-LIVE

> Hoisted out of `docs/PLAN.md` (WOW17) so the plan file leads with its BUILD
> QUEUE. Read this once per session before draining the queue. The five
> non-negotiable rules (#1–#5) live in `CLAUDE.md`.

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

