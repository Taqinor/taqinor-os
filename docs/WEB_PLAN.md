# Taqinor WEB — Build Plan & Progress (site public + previews `apps/web`)

This file is the **single source of truth** for the public website (`apps/web`, the
**Astro** marketing site) and its **private preview lab** (`/preview/*`), and the
**memory between Claude Code sessions** for that work. It is the web-side twin of
[`docs/PLAN.md`](PLAN.md) — which stays **OS-only** (the React OS app + Django/FastAPI
backend) and explicitly excludes `apps/web`. Anything touching the Astro site or a
`/preview/*` route is planned here, not there.

A run drains the **whole** BUILD QUEUE — every unchecked task, never just one — by partitioning
the unchecked tasks into independent **lanes** (grouped by the real `apps/web` files each writes)
and building them with **up to 8 concurrent worktree subagents** (waves of 8 if there are more
lanes), ticking each off *in this file* and committing it to its worktree branch as it lands,
then folding every branch into one `dev` and self-merging `dev` → `main` exactly once at the end
and letting that merge deploy itself. The next session reads this file and continues. Nothing
relies on the agent's own memory — the file on disk is the memory.

---

## HOW TO RUN (read this every session)

1. **Read this whole file.**
2. **Drain the WHOLE BUILD QUEUE — never just one task, with MAXIMUM SAFE PARALLELISM.** Process
   EVERY unchecked `[ ]` task (not `[x]`, not `[SKIP]`, not `[BLOCKED]`); ignore the GATED and
   MANUAL sections entirely. **At the START, compute the file-ownership + dependency graph from
   the real `apps/web` code and partition the queue into independent lanes** (a lane shares a
   file or has a dependency and runs in sequence; different lanes never touch each other's
   files), then **fan the lanes out to up to 8 concurrent worktree subagents** (`isolation:
   worktree`, each in its own isolated git worktree so two never edit the same files at once),
   in **waves of up to 8** when there are more lanes, with fewer agents when there are fewer.
   Each subagent commits its lane to its own worktree branch as each task lands; the orchestrator
   folds every branch into one `dev` at the end. Scope stays strictly inside `apps/web/**` and
   the `docs/WEB_PLAN*` files. **Default to running this as a dynamic workflow with review** —
   one worktree subagent per task plus a **separate adversarial review agent** that must pass
   each finished change (against the STANDING RULES and the task's acceptance criteria) before it
   is eligible to fold in — and **fall back to the same parallel worktree subagents (orchestrator
   reviews each lane) when no workflow engine is available; never a single serial
   one-task-at-a-time agent** (see STANDING RULES).
3. **Verify each task isn't already built — never trust these ticks or prior reports.** Inspect
   the actual route and the deployed preview. If a task already exists and works, mark it
   `[x] (already present)`, add a line to the DONE LOG, and move on to the next `[ ]` task.
4. **Build each task completely, with tests, and land it to `dev` the moment it's done.** Obey
   every STANDING RULE below. As each task finishes: commit it to `dev`, flip it to `[x]`, and
   append one dated plain-language line to the DONE LOG — so an interrupted run never loses
   finished work and re-firing resumes from the first still-unchecked task. Then **immediately
   continue to the next `[ ]` task. Do NOT merge after each task.**
5. **Fold every lane's worktree branch into one `dev`, then CI runs ONCE over the whole batch**
   (lint, the `apps/web` vitest suite, the preview/privacy guards, plus the four required checks).
   When green, **self-merge `dev` → `main` exactly once** (a single merge commit, history
   preserved, 0 approvals; no per-agent PR, no per-task merge). **Make this one merge sync-safe:**
   right before merging, **integrate the latest `origin/main` into `dev`** (merge it in, never
   force-push), recompute the CODEMAP structure fingerprint if that changed the structural
   surface, **re-run CI once on the integrated tree, and merge only when green**; if the push is
   rejected because `main` advanced (e.g. a concurrent OS-plan run landed first), **repeat the
   integrate → CI → push loop — never force, never overwrite the other run's commits** (see
   STANDING RULES).
6. **Deploy is automatic.** The public site **auto-deploys via Cloudflare Workers Builds
   on every push/merge to `main`** — that IS the deploy. **You never run `wrangler deploy`,
   and you never ask for a Cloudflare API token** (the old one is dead and deleted). Worker
   secrets and Cloudflare dashboard variables (e.g. `PUBLIC_MAPTILER_KEY`,
   `LEAD_WEBHOOK_URL`, `LEAD_WEBHOOK_SECRET`) are **dashboard-only** — changing one is a
   manual step for the founder; list it under MANUAL, never block on it silently.
7. **Skip-and-note blockers, never stall.** If a task hits a blocker (a paid/external
   dependency that isn't pre-approved, a new Cloudflare secret the founder hasn't set, anything
   touching the public site or the lead form, or a real taste/promotion decision): do **not**
   guess and do **not** stall. Mark it `[BLOCKED: <one-line reason>]`, move it to GATED, and
   continue with the remaining tasks. A single blocked task must never halt the run.
8. **STOP only when** the BUILD QUEUE is drained, a usage/length cap pauses the run (fine — the
   plan is idempotent; re-firing resumes from the first still-unchecked task), or every
   remaining task is blocked. Then **report once**, in plain language only — no diffs, no commit
   hashes: every task that shipped, what was skipped and why, the exact private preview URLs to
   open, and what (if anything) the founder must set in the Cloudflare dashboard.

**Run from anywhere — web or phone.** Because `main` auto-deploys itself through Cloudflare,
a task can be run from Claude Code on the web or the phone with no PC involved.

---

## STANDING RULES (every web task obeys these)

- **One run = the whole BUILD QUEUE across up to 8 concurrent worktree lanes, one self-merge at
  the end.** Partition the queue into independent lanes and run **up to 8 worktree subagents at
  once** (each in its own git worktree, waves of 8 if there are more lanes); the orchestrator
  folds every branch into one `dev` and the run self-merges `dev` → `main` exactly once when CI
  is green — no per-agent PR, no per-task merge. Multiple sessions or multiple merges are not
  wanted.
- **Engine = workflow-with-review by default; parallel subagents as fallback; never
  single-serial.** Run the lanes as a **dynamic workflow with a fan-out-and-verify
  shape** — one worktree subagent per independent task **plus a separate adversarial
  review agent** that checks every finished change against these STANDING RULES and the
  task's acceptance criteria; nothing folds into `dev` or merges until its review passes.
  When no workflow engine is available (e.g. a phone or cloud session), **fall back to the
  same lane-planned worktree subagents** with the orchestrator reviewing each lane against
  these rules before folding it in. **Never drop to a single serial, one-task-at-a-time
  agent** — parallel lanes with review are the floor.
- **Sync-safe single merge.** Right before the one self-merge, **fetch and integrate the
  latest `origin/main` into `dev`** (merge it in — never rebase published history, never
  force-push); if that changed the code-structure surface, **recompute the CODEMAP structure
  fingerprint on the integrated tree** (the fingerprint the `stage-names` check verifies);
  **re-run CI once on the integrated state and merge only when green**; if the push is
  rejected because `main` advanced, **repeat (fetch, integrate, recompute if needed, re-run
  CI, push) — never force**. A run edits the shared files (`CLAUDE.md` / its own plan file /
  `docs/CODEMAP.md`) only for its own command and ships that change inside this same merge —
  so a concurrent OS run and web-plan run never fight over those files.
- **Verify against real code first. Never trust prior reports.** Inspect the actual route
  and the deployed preview before assuming anything is present or correct.
- **The live public site and the lead form stay unchanged.** Preview work must never alter
  what a real visitor sees or how the website → CRM lead pipe behaves. If a change would
  touch a public page or the lead form, that's out of scope → `[BLOCKED]` or a separate task.
- **Build everything private.** Each preview route is `noindex`, **not in nav**, **excluded
  from the sitemap** (the `filter` on `/preview/` in `apps/web/astro.config.mjs`), and
  **unlinked** from any public page. New previews inherit the same guards.
- **No invented numbers.** Every figure on a preview traces to PVGIS, to a confirmed
  tariff/physics constant, or to sound documented logic. Savings never exceed the avoidable
  energy cost. Impossible panel counts are blocked by the hard footprint bound
  (Σ panel ground-footprints ≤ usable roof area). When a number can't be computed honestly,
  show a clear French "estimation indisponible", never a fabricated value.
- **Respect the needed-panel cap.** Never overfill a roomy roof — surplus generation is
  uncompensated in Morocco (no clear BT net-billing). Size to the bill-derived need, not to
  the maximum the roof could hold.
- **PVGIS is the irradiance source and is already in the stack** (server route
  `/api/roof-yield`, committed table `src/lib/yieldTable.ts`). Using it more is **not** a new
  dependency. The browser never calls PVGIS directly. Cache per location, query only the
  configs that matter, reuse across toggles, and **degrade gracefully** (live → committed
  table → "indisponible") if PVGIS is unreachable.
- **Method, not client data, is committed.** Rationale/assumptions belong in the
  `apps/web/*_NOTES.md` / `*_RATIONALE.md` files (e.g.
  [`ESTIMATOR_BRAIN_NOTES.md`](../apps/web/ESTIMATOR_BRAIN_NOTES.md)). Nothing on a preview is
  a quote — always an indicative range.
- **All new user-facing text in French.** Code/identifiers in English.
- **Promotion to the live site is the founder's call** — never auto-promote a preview.

**Pre-approved (do NOT treat as blockers):** PVGIS (already wired). Anything else new (a paid
API, a new npm dep beyond what `apps/web` already ships) → `[BLOCKED]`.

**Status legend:** `[ ]` to do · `[x]` done · `[SKIP]` not needed / already present ·
`[BLOCKED: reason]` needs a decision (moved to GATED).

---

## ALREADY LIVE — do not rebuild (verify if unsure)

The Astro site is on Cloudflare Workers; `taqinor-web.taqinor.workers.dev` 301-redirects to
`https://taqinor.ma`. Private preview lab under `/preview/*` (all `noindex`, sitemap-excluded,
unlinked):

- **`/preview/toiture`** — trace-your-roof tool (PR #65). Needs `PUBLIC_MAPTILER_KEY` set in
  Cloudflare (founder dashboard task).
- **`/preview/toiture-3d-pro`**, **`-pro-2`** — earlier 3D roof tools (panel model, obstacle
  boxes + on-box size labels were introduced across these sessions).
- **`/preview/toiture-3d-pro-5`** — **estimator brain v2 — orientation layer** (W1,
  2026-06-17). Adds a real roof-aligned **azimuth** (rows follow the roof's true edges on a
  rotated roof, with honest off-south PVGIS yield per config), a **margin/setback toggle**
  (keep vs full-roof, with a computed keep/remove recommendation), **"Recommandé" badges**
  genuinely computed per option group (orientation, portrait/paysage, tilt, azimuth, margin)
  that stay correct whatever the user selects, **multi-obstacle** size labels on the 2D map
  **and** the 3D box, and **per-config live PVGIS** (cached per location, reused across
  toggles, graceful fallback to the committed table). Built as a clone of **pro-4** and
  composing on its `estimatorBrainV2.ts` engine — **pro-4 and pro-3 left as untouched
  baselines**. Engine extensions are additive and **gated behind an opt-in
  (`recommend(..., { enableRoofAligned: true })`)** so pro-4's behaviour is byte-identical
  (proven across 7 roof cases + a regression test).
- **`/preview/toiture-3d-pro-4`** — **estimator brain v2 — tilt layer** (overnight autopilot,
  PR #107). Separate engine `estimatorBrainV2.ts`: a fine tilt-sweep that drives the
  recommendation toward a flatter angle on roof-limited roofs (more total energy, never over
  the needed-panel cap), independent option toggles, and engine tightening. pro-5 builds on it.
- **`/preview/toiture-3d-pro-3`** — the **bill-driven estimator brain** (PR #77, live). The
  brain (`src/lib/estimatorBrain.ts`) ranks Sud / Est-Ouest, sizes to the bill, paves real
  panel rectangles with a solstice row-spacing rule, prices economies off a selective ONEE
  grid, and reads PVGIS via the committed yield table. Multiple-obstacle handling lives in
  `src/lib/obstacles.ts`. Method documented in
  [`ESTIMATOR_BRAIN_NOTES.md`](../apps/web/ESTIMATOR_BRAIN_NOTES.md).
  > The `1,4 MAD/kWh` legacy site figure and the brain's selective grid are FLAGGED to confirm
  > against a real Lydec/ONEE bill before any harmonization.

---

## BUILD QUEUE (do top-down — highest value first)

**ACROSS W62–W66 (world-class audit — founder's cross-cutting constraints):** these tasks come from
a June 2026 audit of the live site against best-in-class residential-solar sites (1KOMMA5°, Otovo,
Aira, Enpal). **No invented facts anywhere** — every figure on the site traces to already-published
Taqinor data or confirmed repo data; where a world-class pattern needs an asset the site does not yet
have (client reviews, founder/team photos, brand logos), **build the empty section/scaffold and leave
it flagged `pending real content from Reda` — never fabricate the content**. **No new dependencies.
Touch only `apps/web`.** The **live lead form and its entire data flow** (1 000 MAD threshold,
consent, WhatsApp deeplink, webhook, CAPI) stay **byte-for-byte unchanged**. The **private estimator
preview routes stay private** (noindex, not in nav, excluded from sitemap, unlinked) — do not surface
or alter them. These tasks **land in the run's single end-of-batch self-merge to protected main** (the
accepted path — don't flag it). **Lighthouse held 97–100 on every page, reduced-motion respected, zero
layout shift.**

> **W62–W66 archived to `docs/DONE.md` (shipped 2026-06-18).** See the DONE LOG below for the one-line
> outcomes; full task text lives under "## Archived from WEB_PLAN.md" in `docs/DONE.md`.

---

## GATED — needs the founder's decision before building (agent does NOT auto-build)

- **WG1 — Promote a preview to the live site.** Moving any `/preview/*` tool onto the public
  website is a **taste + business decision** — never an unattended run. The founder decides
  which preview, when, and how it links into the public funnel.
- **WG2 — Harmonize the tariff model. — [RESOLVED 2026-06-17 → see W11 in BUILD QUEUE]** The
  founder supplied the verified June 2026 régie barème, so this is now an active build task
  (W11), not gated. Délégataire (Lydec/Redal/Amendis) exact grids still await a real bill per
  city — those numbers remain gated until then.
- **WG3 — Any new paid API or npm dependency** beyond PVGIS / what `apps/web` already ships.

---

## MANUAL — founder's dashboard tasks (NOT code; agent never does these)

- Set **`PUBLIC_MAPTILER_KEY`** in the Cloudflare dashboard so the map-based previews load
  tiles in production.
- Add the **privacy line** to the trace-your-roof preview if/when it is considered for
  promotion (location data handling).
- Any **Cloudflare Worker secret** rotation (`LEAD_WEBHOOK_URL`, `LEAD_WEBHOOK_SECRET`, …) —
  dashboard-only.

---

## DONE LOG (agent appends one plain-language line per completed task)

- *(seeded baseline — see "ALREADY LIVE" above for the full pre-plan state of the site +
  preview lab)*