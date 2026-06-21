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
   EVERY unchecked `[ ]` task (not `[x]`, not `[SKIP]`, not `[BLOCKED]`) of EVERY category —
   auto-gating is OFF; ignore only the NEEDS YOUR INPUT and MANUAL sections (those wait on a
   founder-provided prerequisite). **At the START, run `python scripts/plan_lanes.py docs/WEB_PLAN.md`**
   to compute the file-ownership + dependency graph from the real `apps/web` code and emit a
   **maximally-parallel wave plan** (a lane shares a file or has a dependency and runs in
   sequence; different lanes never touch each other's files; each wave takes one head per lane,
   longest lanes first), then **fan each wave's lanes out to concurrent worktree subagents**
   (`isolation: worktree`, each in its own isolated git worktree so two never edit the same files
   at once) up to the session's worktree ceiling (default 8, raised as high as the session can
   sustain via `--max-lanes`), **continuously refilled (work-stealing)** rather than rigid waves.
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
7. **Skip-and-note real blockers only, never stall.** Auto-gating is OFF: a new npm dependency or
   an architecture change is buildable — NOTE it in the DONE LOG. A task is a blocker ONLY when it
   needs something a run can't satisfy: a **paid** API/account (a cost to approve), a **new
   Cloudflare secret** the founder hasn't set, real-world data only the founder has, or a real
   **taste/promotion** decision (promoting a preview live). Then do **not** guess and do **not**
   stall: mark it `[BLOCKED: <one-line reason>]`, move it to **NEEDS YOUR INPUT**, and continue.
   A single blocked task must never halt the run.
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

**Dependencies & categories (2026-06-21 — auto-gating OFF).** A web run builds every task and is no
longer stopped by a category. A **new npm dependency** is allowed when a task plainly needs it — just
NOTE it in the DONE LOG. Still waits on you (→ NEEDS YOUR INPUT): a **paid** API/account (a cost to
approve), a **new Cloudflare secret**, real-world data only you have, and a **taste/business** call
(promotion to the live site). The site stays dependency-light by preference; PVGIS is already wired.

**Status legend:** `[ ]` to do · `[x]` done · `[SKIP]` not needed / already present ·
`[BLOCKED: reason]` waits on a founder-provided prerequisite (→ NEEDS YOUR INPUT).

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

### W70–W97 — 3D BUILDER AUDIT (canonical builder `/preview/toiture-3d-pro-11`, 2026-06-20)

These tasks come from a June 2026 six-lane audit of the canonical 3D roof builder
(`apps/web/src/pages/preview/toiture-3d-pro-11.astro` + `apps/web/src/scripts/roof-tool-pro11.ts`,
4284 lines, plus the brains `estimatorBrainV2/V6/V7/V8.ts`, `applianceConsumption.ts`,
`productionWindow.ts`, `roof.ts`, `roofPro2.ts`, `obstacles.ts`, `layoutVariability.ts`). The audit
found confirmed malfunctions, missing functions, and better-solution upgrades. **Constraints (every
task):** stay strictly inside `apps/web/**`; the **live lead form + its data flow stay byte-for-byte
unchanged** (the preview only PREFILLS the diagnostic, never posts a lead); **all preview routes stay
private** (noindex, not in nav, sitemap-excluded, unlinked); **no new npm/paid dependency** (MapLibre
ships `GeolocateControl`; PVGIS already wired); **no invented numbers** (every figure traces to PVGIS /
a confirmed constant / sound documented logic; savings never exceed avoidable bill cost; never overfill
past the bill-derived need); **inputs never reject typed numbers** (`step="any"`, no snap); **zero CLS,
reduced-motion respected, keyboard + touch + screen-reader paths**. **Verify each finding against the
live code first** (line numbers may have drifted) and mark `[x] (already present)` if already fixed.
Because nearly every task writes the one shared file `roof-tool-pro11.ts`, the tasks that touch it form
**one sequenced lane** (different lanes never co-edit a file); only self-contained pure-lib + unit-test
work (`roof.ts`, `estimatorBrainV*.ts` internals, their `tests/*.ts`) can run as separate worktree
lanes. Update the matching `apps/web/*_NOTES.md` when a task changes documented method.

**TIER 1 — MALFUNCTIONS (fix first — "correct all the malfunctions"):**

- [x] **W70 — 3D: dispose GPU resources on re-trace + on teardown.** In `roof-tool-pro11.ts`,
  `applyRoofPhoto` reassigns `roofTex` without disposing the previous texture (GPU leak on every
  re-trace at a new bbox); and the `WebGLRenderer`/`panelTex` are never disposed (leak on Astro
  client-nav away). Dispose the old `roofTex` before reassigning (guard the one still on
  `deckMaterial.map`), and add a `customLayer.onRemove` that calls `renderer.dispose()`,
  `panelTex.dispose()`, `roofTex?.dispose()`, `disposeScene()`. Accept: repeated trace/clear cycles
  do not grow GPU texture count; teardown frees the renderer. File: `roof-tool-pro11.ts`.
- [x] **W71 — 3D: hoist shared materials + static geometries out of the per-render path.** Panel/glass/
  frame/rack/ballast `Material`s and the static `BoxGeometry`/`EdgesGeometry` are re-allocated inside
  `buildZoneMeshes`/`renderScene` on every tilt-slider drag / obstacle move / layout edit, forcing
  `MeshPhysicalMaterial` shader recompiles. Cache them once in closure scope (active + `dim` variants)
  and reuse; keep `disposeScene` correct (don't dispose the shared cache, only per-zone meshes).
  Accept: no per-drag material/geometry allocation; visuals unchanged. File: `roof-tool-pro11.ts`.
- [x] **W72 — brain: one yield source for the needed-panel cap AND production.** `neededPanelsForTarget`
  (`estimatorBrainV2.ts`) sizes the "+10% coverage" cap off the committed TABLE yield at a hardcoded
  south aspect, while `solveLive`/`solveLivePitched` produce kWh from PVGIS — so the shown coverage %
  drifts from the intended 110%. Thread the winning config's PVGIS per-panel yield into the cap, and
  make `optimalSouthTiltDeg` aspect-aware (scan the winner's real aspect, not `0`). Accept: coverage %
  shown for the auto-optimum is ~110% of the bill at the PVGIS yield actually displayed. Files:
  `estimatorBrainV2.ts`, `estimatorBrainV7.ts`, `estimatorBrainV8.ts`, `roof-tool-pro11.ts` wiring +
  brain unit tests.
- [x] **W73 — brain: matrix winner must match the live-card winner.** `recomputeMatrix()` calls
  `fineGridMatrixV6(...)` with NO `yieldFn`, scoring the whole matrix on the TABLE while the reco card
  is PVGIS-scored — a transient where the badged matrix optimum and the recommendation name different
  configs. Feed `recomputeMatrix` the same PVGIS-backed `yieldFn` used by `buildMatrix`, or route only
  through `computeMatrixPvgis`. Accept: badged matrix row == reco card config once PVGIS resolves; no
  transient disagreement on the table fallback. File: `roof-tool-pro11.ts`.
- [x] **W74 — brain: explicit "no viable config" + north-facing state.** When every candidate is 0 kWh /
  0 panels (roof too small, or all-north pitched pan), `betterLive`/`betterPitched` fall through to
  "fewest panels wins" (arbitrary), and `solveLivePitched` reports `roofLimited:false` with
  `placedCount:0` for a north pan (self-contradictory). Return a flagged `noViableConfig` / expose
  `northFacing` and render an honest French "configuration non viable / pan orienté nord" instead of a
  fabricated winner. Accept: tiny-roof and north-pan cases show the honest message, not a 0-panel
  "winner". Files: `estimatorBrainV7.ts`, `estimatorBrainV8.ts`, `roof-tool-pro11.ts` + unit tests.
- [x] **W75 — map: geocoder race + debounce + abort.** The address search fires `fetch` with no
  `AbortController`, no request token, and no debounce; two quick searches (or the autorun
  `initialQuery`) race and the slower wins, flying to the wrong address. Add a `geoToken` guard +
  `AbortController` + ~300 ms debounce (mirror the existing `billTimer`). Accept: rapid searches always
  resolve to the last query. File: `roof-tool-pro11.ts`.
- [x] **W76 — map: self-intersection guard on the trace.** A bow-tie polygon yields a wrong area
  (spherical shoelace cancels) and a garbage layout; `close()` only checks `< 3` vertices. Add a pure
  `isSimplePolygon(ring)` to `roof.ts` (unit-tested) and call it from `addVertex`/`close` to reject a
  crossing edge with a clear French status. Accept: a self-crossing trace is refused with a message,
  never computed. Files: `roof.ts`, `roof-tool-pro11.ts`, `tests/roof.test.ts`.
- [x] **W77 — map: touch tracing parity (double-tap finish + no dropped vertices).** Finish-on-double is
  wired only to MapLibre `dblclick` (desktop); on touch the only finish is the button, and the 240 ms
  single-click delay silently DISCARDS fast-placed corners (the `if (clickTimer) return;` guard). Add a
  `touchend` double-tap-to-finish (~300 ms) and stop dropping the queued vertex when a second tap is
  not a real dblclick. Accept: phone users can finish by double-tap and no corner is lost when tracing
  quickly. File: `roof-tool-pro11.ts`.
- [x] **W78 — map: multi-zone view/total consistency.** A finished zone with `placedCount===0` is summed
  in the totals but skipped by `appendOtherZones` (`!a.renderPlan`), so it vanishes from the 3D
  multi-zone view — totals and 3D disagree. Capture a `renderPlan` snapshot even at 0 panels, or have
  `appendOtherZones` fall back to drawing the bare ring from `a.vertices`. Accept: every counted zone is
  visible in 3D. File: `roof-tool-pro11.ts`.
- [x] **W79 — layout: keep the custom layout coherent after obstacle/config edits.** Editing/adding/
  deleting an obstacle (or changing a config axis) while the layout editor is open calls `recalc()`
  which nulls `layoutState` but never re-enters custom layout — the hand-placed panels silently snap to
  the optimum, the panel shows a stale count, and the `+/−` disabled-state and the note go stale. When
  `layoutMode` is on, after any recompute re-enter custom layout (re-snap occupied panels to the nearest
  valid cells of the new lattice via `nearestEmptyCell`) and re-render panel/grid/note. Accept: a custom
  layout survives an obstacle edit (re-snapped, not wiped) and all readouts stay live. File:
  `roof-tool-pro11.ts`.
- [x] **W80 — layout: touch drag-to-move panels in 3D.** `layoutDrag` is bound only to `mousedown/move/
  up`; on a phone the only move path is the tactile grid. Add `touchstart/touchmove/touchend` handlers
  mirroring the mouse path, gated by `layoutMode`, with a dedicated `LAYOUT_GRAB_PX` (don't overload the
  obstacle `OBSTACLE_TAP_PX`). Accept: a panel can be dragged to a valid cell on touch. File:
  `roof-tool-pro11.ts`.
- [x] **W81 — obstacles: clamp dimensions on commit, not per keystroke.** The numeric length/width inputs
  fire `clampDim` on every `input`, rewriting "0." / a leading-zero "0.7" to 0.5 mid-keystroke and
  recalc-ing the scene. Clamp on `change`/`blur` (or skip while focused); keep the commit clamp. Accept:
  typing intermediate values no longer snaps the obstacle or fights the user. Files: `roof-tool-pro11.ts`,
  `obstacles.ts`.
- [x] **W82 — consumption: annual 12-month self-consumption integration (THE honesty fix).**
  `productionHourly()` returns the typical day of the W50-selected month and `savingsFromHourly` does
  `selfDaily × 365`, so flipping the production month toggle silently changes the headline annual
  savings (Dec understates, Jul overstates). Add `annualSelfConsumptionKwh(scaled, consCurve)` that sums
  `selfConsumptionDailyKwh(consCurve, typicalDayByMonth[m]) × daysInMonth[m]` over 12 months, and route
  annual savings + battery through it; keep the day graph month-aware for display only. Accept: annual
  savings is invariant to the month toggle and equals the 12-month integral. Files:
  `applianceConsumption.ts`, `roof-tool-pro11.ts` + tests.
- [x] **W83 — consumption: reversible sizing + correct "Recaler".** `applyConsumptionToSizing` is a
  one-way ratchet (adding an "en plus" appliance latches `neededAuto=false`, so deleting it never
  shrinks panels/battery); and "Recaler sur ma facture" rescales to bare `billDailyKwh()`, erasing
  legitimate "en plus" energy and unable to restore the appliance-composed shape. Re-derive the
  consumption-driven need each render (`max(billNeeded, consDrivenNeeded)`), fix Recaler to target
  `billDailyKwh + Σ onTop`, and add a "Réinitialiser la courbe" that clears `consHandEdited` and rebuilds
  baseline+appliances. Accept: removing an appliance shrinks the system; Recaler keeps onTop energy; the
  computed shape is restorable. File: `roof-tool-pro11.ts`.
- [x] **W84 — consumption: respect user AC/EV hours + sane battery.** AC/EV appliances are created with
  hardcoded slot windows (`13–23`, `11–15`) ignoring the entered hours, so `distributeAppliance` smears
  a "3 h" load over 10 h (wrong self-consumption shape); and battery sizing, fed a single month's
  production vs a flat-average load, flips between months / returns 0. Set the slot end-hour from the
  entered hours, and size the battery from the annual evening deficit (12-month), not one month. Accept:
  the AC/EV load lands in the right hours; battery count is stable across the month toggle. Files:
  `roof-tool-pro11.ts`, `applianceConsumption.ts` + tests.
- [x] **W85 — prefill: correct orientation handoff to the diagnostic.** `prefillLead` writes
  `lf-orient = 'sud'` unconditionally, dropping Est-Ouest (flat) and every pitched face
  (Sud-Est/Sud-Ouest/Est/Ouest). Derive the `enrichment.ORIENTATIONS` id from the winning family/azimuth
  (flat) or `facingAzimuthDeg` (pitched: 180→sud, 135→sud-est, 225→sud-ouest, 90→est, 270→ouest).
  Accept: the prefilled orientation matches the chosen config; still no lead POST from the preview.
  Files: `roof-tool-pro11.ts` + a runtime test.
- [x] **W86 — honesty + a11y: CTA label + aria-live on results.** `#rp9-cta` is labelled "Recevoir mon
  étude sur WhatsApp" with a WhatsApp icon but performs NO WhatsApp action (it only prefills and scrolls
  to the diagnostic, which is where the real WhatsApp step lives). Rename it to an honest "Continuer vers
  le diagnostic →" (drop/soften the WhatsApp framing on the preview button). Add `aria-live="polite"` to
  the recommendation `<dl>`, `#rp9-prod-headline`/`#rp9-prod-sub`, and the `#rp9-areas-window` totals so
  the headline numbers are announced to screen readers. Accept: label matches behavior; results announce.
  File: `toiture-3d-pro-11.astro`.

**TIER 2 — COMPLETIONS (needed functions — "complete it with needed function"):**

- [x] **W87 — 3D: real sun + inter-row shadow proof + time/season toggle.** The display sun is pinned at
  `azimuth − 45°` with an arbitrary elevation, so the rendered shadows bear no relation to a real time
  and never prove the anti-shading row pitch the layout is built on. Drive the sun from a real
  solar-position function of the site latitude + a user hour/season control (reuse
  `SOLAR_DECLINATION_DEG`/winter-solstice `designSunElevation` from `roofPro2.ts`); show a worst-case
  (winter noon) inter-row shadow so the spacing reads. Accept: shadows track the chosen hour and the
  rows visibly clear each other at design elevation. Files: `roof-tool-pro11.ts`, `roofPro2.ts`,
  `SOLAR_3D_PRO2_NOTES.md`.
- [x] **W88 — 3D: panel pick + highlight + per-panel delete in 3D.** Panels are one `InstancedMesh` with
  no picking; the layout editor only works via the 2D grid. Add an `instanceColor` buffer + raycast pick
  to highlight a panel on hover and toggle/remove it directly in the 3D view (desktop click + touch
  long-press), reusing the existing `layoutState`/`occupiedSet`. Accept: clicking a panel in 3D selects/
  removes it and the readouts recompute. File: `roof-tool-pro11.ts`.
- [x] **W89 — 3D: WebGL context-loss recovery.** No `webglcontextlost`/`webglcontextrestored` handler, so
  a GPU context loss (mobile background/foreground) blanks the 3D permanently. Add handlers that
  `preventDefault` the loss and rebuild the scene on restore. Accept: backgrounding/restoring the tab
  recovers the 3D. File: `roof-tool-pro11.ts`.
- [x] **W90 — 3D: pitched-roof gable massing.** The pitched deck is raised over a flat-top box with no
  gable/hip walls, reading as a tilted lid floating over a building. Build simple gable end-walls so a
  pitched roof reads as a roof. Accept: pitched mode shows a closed roof volume, not a floating plane.
  File: `roof-tool-pro11.ts`.
- [x] **W91 — map: current-location button.** No way for an on-site Moroccan user to centre on their
  roof. Add MapLibre's built-in `GeolocateControl` (no new dependency) → `flyTo` zoom 19 on geolocate.
  Accept: the control appears and centres on the device location. File: `roof-tool-pro11.ts`.
- [x] **W92 — map: editable trace vertices + undo-last-point.** Roof corners are immutable once placed
  (only "Effacer" restarts), unlike the fully-draggable obstacles. Generalize the obstacle-drag
  machinery to the `rp9-pts` source (drag a corner → update `vertices[i]` → `recalc`) and add an
  "Annuler le dernier point" control during tracing. Accept: a placed corner can be dragged and the last
  point undone. File: `roof-tool-pro11.ts`.
- [x] **W93 — map: address autocomplete.** Geocode is fire-on-submit `limit=1` (one guess, no list).
  Switch to `limit=5`, render a dropdown bound to the address field, and `flyTo` only on selection
  (reuses the same MapTiler endpoint, no new key). Accept: typing shows up to 5 Morocco suggestions;
  selecting one flies there. File: `roof-tool-pro11.ts`.
- [x] **W94 — brain: 25-year degradation band + DC:AC clip + real bifacial constants.** Savings imply
  year-1 production forever; `kwc = count × 0.72` is raw DC with no inverter clip, overstating dense
  E-W tents; the live cards hardcode a literal `× 0.05` bifacial gain instead of the `BIFACIAL_GAIN_*`
  constants. Add `ANNUAL_DEGRADATION` + `DC_AC_RATIO`/`INVERTER_KW` to `estimatorBrainV2.ts`, surface a
  Year-1 / Year-25 savings band, apply the AC clip in the kWh eval, and use the bifacial constants in
  `paintCard`. Accept: an honest 25-yr band shows; E-W kWh respects the AC cap; bifacial line uses the
  flat/tilted constants. Files: `estimatorBrainV2.ts`, `roof-tool-pro11.ts` + tests.
- [x] **W95 — consumption: seasonal profile + monthly self-consumption breakdown.** `consCurve` is one
  flat daily average while production is strongly seasonal. Add a summer/winter split
  (`ete_differente`-style toggle) and a per-month autoconsommation mini-chart driven by
  `typicalDayByMonth`. Accept: a seasonal consumption split feeds the 12-month integral and a monthly
  self-consumption chart renders. Files: `applianceConsumption.ts`, `roof-tool-pro11.ts`.
- [x] **W96 — consumption: battery payback / ROI.** `batterySizing` returns only a count — no cost, no
  payback. Add `BATTERY_KWH_USABLE` + a flagged indicative cost param and surface an indicative payback
  next to the recommended battery count (clearly "estimation, pas un devis"). Accept: a payback range
  shows, capped to honest avoided-cost. Files: `applianceConsumption.ts`, `roof-tool-pro11.ts`,
  `APPLIANCES_NOTES.md`.

**TIER 3 — TEST COVERAGE (lock the fixes in):**

- [x] **W97 — runtime/integration tests for pro-11.** Add jsdom/vitest coverage the audit found missing:
  `prefillLead` writes `lf-area`/`lf-kwc-est`/`lf-orient` correctly (incl. Est-Ouest/pitched mapping from
  W85) and the preview NEVER calls `fetch`/POSTs a lead; multi-zone totals via `+ Ajouter une zone`
  (wire the `rp9-add-area`/`rp9-areas-*` ids into the test DOM); graceful degradation (no-WebGL →
  `#rp9-fallback`, no-key → `showFallback`, `<noscript>` present); savings never exceed the bill-derived
  ceiling at the RENDERED layer; layout-edit recompute; obstacle-clearance through the mounted script.
  Accept: new tests fail before W70–W86 fixes and pass after. Files: `tests/estimatorRuntimePro10Pro11.test.ts`
  (+ new `tests/*.ts` as needed).

---

### W98–W104 — TECHNICAL SEO AUDIT & FIXES (public site, 2026-06-20)

A single-session full crawlability / indexability / structured-data pass over the **public** site.
**Constraints (every task):** stay strictly inside `apps/web/**`; **read the real source first** —
the actual `<head>`/layout components, the sitemap config in `apps/web/astro.config.mjs`, and
`robots.txt` — and fix only **genuine** gaps found in the real code (don't assume; leave good pages
alone). The **live public pages**, the **lead-capture flow** (1 000 MAD threshold, consent, WhatsApp
deeplink, webhook, CAPI), and **every tariff number** stay **byte-for-byte unchanged**. **No new npm
or API dependencies** — if a fix needs one, SKIP it and name it in the report for Reda to approve.
**Invent nothing** — omit any schema field with no real value on the site. The **private estimator
preview routes are out of scope for all of these** — they keep their `noindex` and stay unchanged;
the latest `toiture-3d-pro-*` route must NEVER enter the sitemap or nav. **Lighthouse held 97–100,
zero layout shift, reduced-motion respected.**

- [x] **W98 — Structured data (JSON-LD) across public routes.** Keep `/faq` as the **sole owner** of
  `FAQPage`. Add an **Organization/LocalBusiness** block on the homepage using the real business
  name, the phone already on the site, and the real address from the contact/footer — invent nothing,
  omit any field with no real value; set `areaServed` to the cities the site already serves; include
  `geo`/`openingHours` ONLY if real values exist on the site. Add **Service** schema on the service
  pages and a **BreadcrumbList** matching the existing nav. Leave `sameAs` OUT until real social
  profiles exist. Accept: homepage carries valid LocalBusiness JSON-LD; service pages carry Service +
  BreadcrumbList; `/faq` still the only FAQPage; no fabricated fields. Files: `apps/web/**`.
- [x] **W99 — Per-page head hygiene.** Every public route gets a **unique, descriptive `<title>` and
  meta description**, a **self-referencing canonical**, and a complete **Open Graph + Twitter Card**
  set (`og:title`, `og:description`, `og:url`, `og:type`, `og:locale = fr_MA`, `twitter:card`) with a
  **real `og:image` from an existing asset**. Fix pages missing these; leave good ones alone. Accept:
  each public route has exactly one canonical (self-referencing) and a complete OG/Twitter set with a
  real image. Files: `apps/web/**` (head/layout components).
- [x] **W100 — Sitemap completeness + exclusions.** Confirm every public page is included and that the
  private estimator preview routes and any `noindex` page are excluded. Safety line: the latest
  `toiture-3d-pro-*` route must NEVER enter the sitemap or nav. Accept: all public pages present, all
  `/preview/*` + noindex pages absent. Files: `apps/web/astro.config.mjs` (sitemap filter).
- [x] **W101 — robots.txt.** Confirm it references the sitemap, allows legitimate crawlers, and
  disallows the private estimator path as defense-in-depth alongside `noindex`. Accept: robots.txt
  cites the sitemap, allows crawlers, disallows the private estimator path. Files: `apps/web/**`
  (`robots.txt` / its generator).
- [x] **W102 — Locale.** Confirm `<html lang="fr">` site-wide. Leave `hreflang`/Arabic alone —
  parked. Accept: every public route renders `lang="fr"`. Files: `apps/web/**` (root layout).
- [x] **W103 — Images & headings.** Add descriptive `alt` text to content images missing it; confirm
  one `<h1>` per page with a sane H2/H3 order. Accept: no content image without alt; exactly one h1
  per public page; heading order is sane. Files: `apps/web/**`.
- [x] **W104 — Tests for the new SEO invariants.** Keep Vitest green and add assertions for the new
  invariants: the latest private preview route is **absent from the sitemap**, the homepage carries
  the **LocalBusiness JSON-LD**, and **each public route has exactly one canonical**. Accept: new
  assertions pass, full suite green; Lighthouse held 97–100, zero CLS, reduced-motion respected.
  Files: `apps/web/**/tests/*.ts` (+ new test files as needed).

---

### W105–W111 — 3D BUILDER: MULTI-ZONE PITCH CONNECTION, PANEL OVERHANG & CONTACT CAPTURE (founder request, 2026-06-21)

Founder report on the canonical builder (`/preview/toiture-3d-pro-11` + `apps/web/src/scripts/roof-tool-pro11.ts`
and its `roofPro11/` modules): adding a 2nd zone now works, but **two CONNECTED zones on a non-flat (pitched)
roof don't join correctly** — both pans default to the same south face (`facingAzimuthDeg = 180`) so each tilts
the same way instead of meeting at a shared ridge; the builder should **infer each pan's facing from the shared
edge automatically AND let the user correct it per zone**. Also wanted: panels that can **overhang the roof edge
by a user-specified amount** (the metal mounting rails stay on the roof, the panels cantilever out — common on
tilted roofs); and a **place in the simulator for the client to enter name / phone / address — kept at the TOP
of the page in one single flow, NOT a separate form the user must scroll down to**. Same constraints
as W70–W104: stay strictly inside `apps/web/**`; **the live lead form + its entire data flow stay byte-for-byte
unchanged** (the preview only PREFILLS the diagnostic, never posts a lead — the W85/W97 guard); **all preview
routes stay private** (noindex, not in nav, sitemap-excluded, unlinked); **no new npm/paid dependency**; **no
invented numbers** (overhang changes only geometric CAPACITY, never the bill-derived needed-panel cap; savings
never exceed avoidable bill cost); **inputs never reject typed numbers** (`step="any"`, no snap); **zero CLS,
reduced-motion respected, keyboard + touch + screen-reader paths**. **Verify each item against the live code first**
and mark `[x] (already present)` if already done. Lanes: the pure-lib tasks (W105 adjacency, W108 packing) are
self-contained worktree lanes with their own unit tests; the wiring/render/UI tasks (W106, W107, W109, W110) all
write the shared `roof-tool-pro11.ts` / `roofPro11/scene3d.ts` / the page, so they run as ONE sequenced lane.

- [x] **W105 — geometry: zone adjacency + auto facing inference (pure lib).** Today each zone keeps its own
  `facingAzimuthDeg`, but a newly-added pitched zone defaults to 180 (south), so two connected pans both tilt
  south. Add a PURE, unit-tested helper (new `apps/web/src/lib/roofAdjacency.ts`) that, given the traced rings
  (lng/lat) of the zones, finds the SHARED/closest edge between two adjacent zones and infers a coherent
  `facingAzimuthDeg` for a pitched zone relative to its neighbour: a two-pan **gable** → the pans face AWAY from
  the shared ridge (opposite azimuths, normal to the shared edge); a **continuation / mono-pente** → the same
  down-slope direction. Return `{ facingAzimuthDeg, connected: boolean, sharedEdge }` plus a confidence so the
  caller falls back to south when no edge is shared. No DOM/Three/map deps. Accept: gable + mono-pente fixtures
  infer the right opposite/equal facings; disjoint zones report `connected:false` and leave the facing to the user.
  Files: `apps/web/src/lib/roofAdjacency.ts`, `apps/web/tests/roofAdjacency.test.ts`.
- [x] **W106 — 3D: auto-apply the inferred facing on zone add + per-zone manual correction.** Wire W105 into
  `roof-tool-pro11.ts`: when a pitched zone's trace closes (or `+ Ajouter une zone` makes one adjacent to an
  existing pan), set its `facingAzimuthDeg` from the inferred value instead of the hardcoded 180 default — so
  connected pans auto-orient to meet at the ridge. Keep the existing "Face du pan" buttons (`data-facing`) + the
  fine azimuth as a **manual override that wins** and is **per-zone** (selecting a zone shows/edits ITS facing;
  the override persists in the area record via the existing `snapshotActiveAreaGeometry`/restore path), and show a
  one-line note when the facing was auto-inferred vs hand-set. Accept: adding a connected pitched pan auto-faces
  it coherently; the user can override any zone's facing and switching zones reflects the right value. Files:
  `roof-tool-pro11.ts`, `toiture-3d-pro-11.astro` (note/control wiring), `roofPro11/zones.ts` if needed.
- [x] **W107 — 3D: render connected pitched pans meeting at the shared ridge.** In `roofPro11/scene3d.ts` the
  other zones are drawn from their own `renderPlan`, each deck + gable skirt referenced to its OWN eave
  (`eaveUpSlopeCoord`), so two connected pans float as separate tilted lids ("each tilted to one side"). Use the
  W105 adjacency to reference adjacent pitched pans to a COMMON ridge line at the shared edge (matched ridge
  height, eave on the outer edges) so they read as one connected roof; flat zones and disjoint zones unchanged.
  Accept: two connected pitched zones render as a single coherent gable/slope meeting at the ridge, not two
  independent lids. Files: `roofPro11/scene3d.ts`, `roof-tool-pro11.ts` wiring.
- [x] **W108 — packing: user-specified panel overhang past the roof edge (pure lib).** Add an `overhangM` option
  to `packConfig`/`packCells` (`estimatorBrainV2.ts`) and the pitched packers (`estimatorBrainV6/V7/V8.ts` as
  wired) so a panel is retained when its footprint stays within `setbackM` of the edge OR extends at most
  `overhangM` BEYOND it (rails on-roof, panel cantilevers out) — i.e. the corner-test floor becomes `-overhangM`.
  Keep the honesty footprint bound honest: expand `usableAreaM2` by the allowed overhang ring (so the bound
  reflects the rail-supported area, never a fabricated capacity). Default `overhangM = 0` → byte-identical to
  today. Pure → unit tests. Accept: with `overhangM>0` panels may slightly exceed the ring, count rises only by
  the geometric room gained, the footprint bound still holds, and `0` is unchanged. Files: `estimatorBrainV2.ts`,
  `estimatorBrainV6/V7/V8.ts` (as wired), `roofPro2.ts` if shared, `apps/web/tests/*`.
- [x] **W109 — 3D: overhang control + render.** Add a "Débord panneaux autorisé (m)" numeric input (`step="any"`,
  default 0, beside the marge/retrait control) and thread it into the solve (flat + pitched) so panels can extend
  past the eave/rake — most useful on tilted roofs. Render the overhanging panels correctly in the 3D scene (panel
  cantilevered over the edge on its rails). Honesty: overhang changes only geometric capacity, never the
  bill-derived needed-panel cap (never overfill past the need). Accept: raising the débord lets a few more panels
  place at the edges and they render hanging over the eave; the bill cap and the savings ceiling are unchanged.
  Files: `toiture-3d-pro-11.astro`, `roof-tool-pro11.ts`, `roofPro11/scene3d.ts`, `roofPro11/optimizer.ts` /
  `roofPro11/obstaclesUi.ts` wiring as needed.
- [x] **W110 — simulator: ONE-page flow with client contact capture (Nom / Téléphone / Adresse) at the TOP.**
  Today `/preview/toiture-3d-pro-11` puts the 3D builder at the top and a SEPARATE diagnostic form
  (`DiagnosticFormEnriched`, `#simulateur`) far BELOW that the user must scroll to — and the simulator has nowhere
  to enter name/phone/address. Make the whole experience ONE top-down page: add Nom, Téléphone and Adresse inputs
  INLINE with the simulator's result/CTA block at the top, and **remove the separate diagnostic section currently
  rendered BELOW on this preview page**, consolidating everything into the single top flow (trace → result →
  name/phone/address → continue, all in one place, nothing essential below). Reuse the existing form plumbing by
  relocating/embedding `DiagnosticFormEnriched` inline near the results — its submit / WhatsApp deeplink / consent
  / webhook / CAPI stay **byte-for-byte unchanged** (do NOT edit the shared component or the live data flow) — or
  keep it prefill-only and wire the new Nom/Téléphone/Adresse into `lf-name`/`lf-phone`/`lf-city` (+ the geocoded
  `rp9-address`) via `roofPro11/prefill.ts` (which already prefills `lf-area`/`lf-orient`/`lf-kwc-est`), surfacing
  the form inline at the top. STRICT: the simulator's own prefill code still posts NO lead (the W85/W97 guard);
  the shared `DiagnosticFormEnriched.astro` component and the live lead data flow are untouched; the preview stays
  private (noindex, not in nav, sitemap-excluded, unlinked). Accept: the whole flow is one page at the top with no
  separate form below; Nom/Téléphone/Adresse are captured up top; the live form/data flow is unchanged. Files:
  `toiture-3d-pro-11.astro`, `roofPro11/prefill.ts`, `roof-tool-pro11.ts` wiring.
- [x] **W111 — tests: lock in multi-zone facing, overhang honesty & contact prefill.** Add coverage: W105 facing
  inference (gable opposite, mono-pente equal, disjoint → user); W108 overhang packing (count grows only by the
  geometric room, footprint bound holds, `overhangM=0` unchanged, savings ≤ bill ceiling); W110 contact prefill
  writes `lf-name`/`lf-phone`/`lf-city` AND the preview still never calls `fetch`/POSTs a lead (extend the existing
  no-lead-POST runtime test). Accept: new tests fail before W105–W110 and pass after; full `apps/web` vitest suite
  green. Files: `apps/web/tests/*.ts` (+ new files as needed).

---

### W112–W118 — DEVIS PIPELINE: client points at roof → Meriem designs → premium web proposal + e-sign (founder request 2026-06-21)

*Goal: turn the existing `roofPro11` builder + the premium quote into ONE loop. The
backend half (storage, Devis build, proposal/e-sign endpoints) is `docs/PLAN2.md` Group
Q (Q1–Q7); these are the `apps/web` halves. The heavy engine already exists — this is
plumbing + a beautiful client-facing surface.*

> **CRITICAL UX RULE — the client never sees the panels being placed.** The client is
> **not obliged to draw**: they just **point** at their roof (drop a pin / pick the
> building) and give their bill. **Meriem** draws the outline (if needed) and runs the
> auto-fill/optimizer, privately, so the client believes TAQINOR designed it for them.
> The client-facing capture mode must therefore instantiate NO optimizer, NO panel
> layer, NO production cards — only address search + a pin (+ optional rough trace).
> Note: exposing a `/preview/*` tool publicly is normally WG1-GATED; W112 is a NEW,
> deliberately minimal *capture* surface (no design shown), which the founder authorized.

> **UNBLOCKED 2026-06-21 (whole W112–W118 lane).** The backend dependency shipped: `docs/PLAN2.md`
> Group Q (Q1 `Devis.roof_layout` storage, Q2 client pin capture, Q3 `build_devis_from_layout`,
> Q4 render storage, Q5 quote-data feed, Q6 tokenized proposal endpoint, Q7 e-sign) is **all done
> `[x]`** on `main`. The request/response contract now exists, so these `apps/web` halves are
> buildable — wire them against the live Q1–Q7 endpoints (proxy via `apps/web/src/pages/api/`).
> The lead-data flow these touch is real now, not a phantom backend.

- [ ] W112 — **Client "où est votre toit ?" capture (public, panels HIDDEN).** A new
  minimal public route (e.g. `/devis/mon-toit`) that reuses roofPro11's MapTiler address
  search + satellite map, lets the client **drop a pin on their roof** (drawing the
  outline is OPTIONAL, not required), and enter contact + bill, then submits the
  pin (+ optional outline) + contact to the backend (Q2), creating a Lead. Add a
  **`captureOnly` flag** to `initRoofToolPro8` that boots map + geocoder + pin/trace ONLY
  and never instantiates the optimizer/scene-panels/production UI. **Done =** the client
  can pin + submit on phone & desktop; no panel/optimizer/production UI ever appears; the
  pin reaches the backend. Files: new `apps/web/src/pages/devis/mon-toit.astro`,
  `roof-tool-pro11.ts` (captureOnly branch), reuse `roofPro11/mapDraw.ts`.

- [ ] W113 — **Layout serialize + hydrate (the linchpin).** Add serialize/deserialize of
  the tool state (`AreaRecord[]`, and the lighter pin/outline) and extend
  `initRoofToolPro8` boot to **hydrate from the backend** via a token URL param
  (`?lead=<token>` for the client's pin, `?devis=<id>` for a saved layout), fetching from
  the Q1/Q2 endpoints through a small Astro API proxy. **Done =** a saved pin/outline (and
  a saved finalized layout) reload into the tool identically; round-trip vitest.
  Files: `roofPro11/prefill.ts` (load fns), `roof-tool-pro11.ts` (boot hydration),
  `apps/web/src/pages/api/roof-layout.ts` (proxy).

- [ ] W114 — **Meriem design + finalize (where the panels appear, privately).** An
  internal/gated route that boots the FULL tool **hydrated with the client's pin** (W113);
  Meriem draws the outline if the client didn't, runs the existing auto-fill/optimizer,
  edits, then a **"Valider & générer le devis"** action serializes the finalized layout +
  kWc/count/production and POSTs it to the backend (Q1) and triggers Devis creation (Q3).
  **Done =** open a client pin → draw/autofill → finalize → a Devis is created and the
  layout saved. Files: `apps/web/src/pages/internal/devis-design.astro` (or reuse the
  preview route gated), `roof-tool-pro11.ts` (finalize action), api proxy.

- [ ] W115 — **3D snapshot export.** Wire `renderer.domElement.toDataURL('image/png')`
  (`roofPro11/scene3d.ts`) to capture the finished roof-with-panels render and upload it
  to the backend (Q4) on finalize (W114). **Done =** finalizing produces + stores a clean
  PNG of the 3D roof; vitest/asserts the data-URL is produced. Files:
  `roofPro11/scene3d.ts` (snapshot fn), W114 finalize wiring.

- [ ] W116 — **Client web proposal page (the "much better UI" link we send).** A premium,
  mobile-first **public** route (e.g. `/proposition/<token>`) that fetches the quote data
  (Q6) and renders the proposal as a beautiful web page — NOT just a PDF: a hero with the
  roof render, the facture **avant → après** + couverture %, the two options, the
  equipment, the garanties, and a **sticky "Signer" CTA**. Mirrors the v2 PDF design
  language (navy/gold, DM Serif/DM Sans). **Done =** the token link renders the full
  proposal responsively on phone + desktop; Lighthouse mobile ≥ 90. Files: new
  `apps/web/src/pages/proposition/[token].astro` + components + the Q6 fetch.

- [ ] W117 — **In-page e-signature.** On the web proposal, a "Signer en ligne" flow: pick
  an option, type name + check "Bon pour accord" → POST to Q7 → success state ("Devis
  accepté ✓"), with the signed PDF offered as a download. **Done =** signing flips the
  Devis to *accepté* and shows confirmation; invalid/expired token handled. Files:
  `proposition/[token].astro` signature component, `apps/web/src/pages/api/` proxy.

- [ ] W118 — **Delivery: send the proposal link (email / WhatsApp).** On finalize (W114),
  generate the tokenized proposal URL and surface it for sending — prefilled email (reuse
  the existing SendGrid path) and a WhatsApp deep link (`wa.me` with the client's number +
  a French message + the link). **Done =** Meriem gets a one-click "Envoyer par email" and
  "Envoyer par WhatsApp"; degrades to a copyable link when `SENDGRID_API_KEY` is off.
  Files: W114 finalize UI + a small send action (reuse existing email infra).

---

### W119–W131 — SEO CONTENT EXPANSION: FAQ, EV-charging pillar, guides library & battery content (founder request 2026-06-21)

<!-- lane: apps/web -->

*Goal: make taqinor.ma the best-ranked, most useful French-language answer source for solar /
EV-charging-with-solar / battery questions in Morocco. Grounded in a June 2026 SEO research pass
(residential-solar, EV-charging-with-solar, and home-battery "People Also Ask" / high-volume
queries) plus the loi 82-21 net-billing framework that went live 9 June 2026 (≤11 kW declaration
regime, surplus export capped at ~20% of annual production, regulated low buyback ~18 c/kWh
off-peak · 21 c/kWh peak — below retail). That last fact is the honest differentiator to weave
through everything: with no true net-metering, **daytime self-consumption + storage + charging an
EV from your own midday surplus is worth more in Morocco than in net-metering markets.***

> **CONSTRAINTS — every task in this block.** Stay strictly inside `apps/web/**`. **All new
> user-facing text in French** (code/identifiers English); EN/AR mirrors are a deliberate FR-first
> follow-up — do NOT register new FR-only routes in `src/i18n/pages.ts` (so the language switcher
> correctly hides on them), and do NOT block on translating them. **Numbers come from the cited
> research doc, not from thin air.** A founder-authorized, source-cited evidence base lives at
> [`apps/web/CONTENT_SEO_NOTES.md`](../apps/web/CONTENT_SEO_NOTES.md) (loi 82-21 regimes/20 %-cap/
> 0,18–0,21 DH buyback, ONEE tranches, irradiation kWh/kWc by city, sizing, install-price ranges,
> EV economics, battery chemistry/Dyness specs, inverter backup behaviour) — each figure tagged
> PUBLISH-SAFE or LOCK-FIRST with a confidence + source. Use it as follows: (a) **STABLE** physics/
> spec figures (irradiation, optimal tilt, ~0,5 %/yr degradation, LFP cycle life/DoD/efficiency, EV
> ~15 kWh/100 km, panels-per-EV) may go in the **evergreen guides** with their source; (b)
> **VOLATILE** market/regulatory figures (MAD prices, ONEE tranches, buyback rate, fuel prices)
> belong in the **dated blog posts** (W132–W139) and are *linked* from the guides, never hardcoded
> into an undated page; (c) anything tagged **LOCK-FIRST** must be **locked by the task itself from a
> primary source** (the running agent searches the official ONEE/distributor PDF, the Bulletin
> Officiel / ANRE decision, the manufacturer datasheet, or a live price — W140 centralizes this and
> feeds the doc) — **never defer a researchable fact to the founder**; until locked it publishes as a
> labelled range (« fourchette indicative 2026 »), never as hard single-point fact; (d) **the only
> founder-owned thing is Taqinor's actual quote** — content never states the firm's internal MAD
> figure, it uses the indicative ranges + a CTA to the diagnostic/quote engine. **`<!-- PENDING(Reda)
> -->` is reserved strictly for founder-owned ASSETS the web cannot research** (real client reviews,
> team/founder photos) — **never for a number, tariff, spec, or fact**. **Never fabricate or
> over-precision a number.** **`/faq` stays the SOLE `FAQPage` JSON-LD owner** (W98 invariant): any other page
> that renders a visual FAQ MUST reuse the `Faq` component with `schema={false}`. New guide/landing
> pages carry **`Article` (or `Service`) + `BreadcrumbList`** JSON-LD and a self-referencing
> canonical, matching the existing guide pages. The **live lead form + its whole data flow** (1 000
> MAD threshold, consent, WhatsApp deeplink, webhook, CAPI) stay **byte-for-byte unchanged**; the
> **private `/preview/*` routes stay private** and untouched. **No new npm/paid dependency.**
> **Lighthouse 97–100, zero CLS, reduced-motion respected, one `<h1>` + sane H2/H3 per page,
> descriptive `alt` on any content image.** New public pages enter the sitemap automatically — verify
> they do and that `/preview/*` still does not. **Lanes:** each new page is its own file → its own
> worktree lane (W120–W128 run fully in parallel); W119 (`/faq`), W129 (guides hub), W130
> (`/batteries-stockage`) each own one existing file; W131 (tests) sequences last. **W140 (data lock/refresh) runs FIRST** — it only writes
  `CONTENT_SEO_NOTES.md` (no file conflict; can run in parallel) and its locked figures feed every
  content task below.

- [x] W140 — **Research-and-lock the open figures + refresh the volatile ones (the agent searches,
  never the founder).** Before/while the content tasks run, lock every `LOCK-FIRST` figure in
  `CONTENT_SEO_NOTES.md` from a PRIMARY source and promote it (or leave a labelled range if a primary
  source genuinely can't be reached — never a founder ask): (1) the current ONEE BT residential grid
  + bi-horaire rates from the ONEE/distributor tariff page or a recent dated source (the "+5,5 %
  Oct-2025 hike" was found UNVERIFIED — the rounded grid 0,90/1,07/1,18/1,45/1,66 DH/kWh is the
  current usable grid; confirm + date-stamp); (2) loi 82-21 penalty bands + the Article 33 window
  start-trigger from the Bulletin Officiel / decree text; (3) per-city PVGIS specific yield + optimal
  tilt from PVGIS/Global Solar Atlas (state the system-loss assumption); (4) Dyness round-trip
  efficiency for the non-PowerBrick models from the official datasheets (PowerBrick >95 %, ≥8000
  cycles, 55 °C, and H5B 7-yr-base/10-yr-on-registration are already locked); (5) **CORRECTED EV
  policy** — the "50 000/100 000 MAD prime à l'achat" is NOT a confirmed Moroccan measure (Tunisia
  cross-contamination in secondary blogs); the real, citable measures are EV **TVA exemption**,
  **vignette/TSAVA exemption** (EV + PHEV, not HEV) and **import-duty waiver** — do NOT publish the
  prime as Moroccan policy; (6) date-stamp the volatile figures (fuel ~14,3/13,6 MAD/L mid-Jun-2026,
  tariffs, prices) + a one-line refresh-cadence note so the blog posts can be re-checked. Update the
  PUBLISH-SAFE / LOCK-FIRST tags accordingly. Accept: every figure in `CONTENT_SEO_NOTES.md` is either
  locked-with-source or an explicitly labelled range, the EV-prime correction is applied, no founder
  ask anywhere. File: `apps/web/CONTENT_SEO_NOTES.md` (notes only — runs first, conflict-free).

- [x] W119 — **Expand the public FAQ (`/faq`) to ~24 questions across solar, EV-charging & battery.**
  Today `faq.astro` renders ~13 Q grounded in site facts. Add ~11 more, grouped, keeping the single
  `Faq` component / single `FAQPage` schema (it auto-aligns to the rendered array). Add the
  high-value EVERGREEN questions the research found (general-fact, publishable now, no founder number
  needed): *les panneaux fonctionnent-ils la nuit / par temps nuageux ?*, *la chaleur / l'hiver
  réduisent-ils la production ?*, *quelle orientation et quelle inclinaison ?*, *l'ombre réduit-elle
  la production ?*, *faut-il nettoyer les panneaux et à quelle fréquence ?* (Morocco dust/sand angle),
  *les panneaux perdent-ils en rendement avec le temps ?* (degradation vs the published 84,8 %/25 ans),
  *monocristallin ou polycristallin ?*, *que se passe-t-il pendant une coupure ?* (anti-îlotage vs
  hybride+batterie), **EV:** *puis-je recharger ma voiture électrique avec mes panneaux ?*, *faut-il
  une batterie pour recharger la nuit ?*, **battery:** *combien de temps dure une batterie LFP ?*
  (tie to published 10-ans Dyness warranty). Keep every answer derived from published facts or
  general physics; anything needing a price/tariff → the cited figure from `CONTENT_SEO_NOTES.md` as
  a labelled range (link the relevant blog post for the live number), never a founder ask. Accept: `/faq`
  shows ~24 grouped Q, still exactly ONE `FAQPage` block aligned to the rendered list, no fabricated
  figure, FR copy in the existing voice. Files: `apps/web/src/pages/faq.astro` (FR only; `/en/faq` +
  `/ar/faq` mirror is a flagged follow-up, not required to land).

- [x] W120 — **New EV-charging-with-solar PILLAR page `/recharge-voiture-electrique-solaire` (the
  biggest content gap).** No page covers charging an electric car from solar today. Build a
  top-level public page (same Layout/`v2` design language, `Breadcrumb`, `CtaBand`, `StickyCta` as
  the service pages) answering the cluster the research found, in clearly-titled H2 sections: *peut-on
  recharger une VE avec le solaire ?* · *combien de panneaux pour mes km quotidiens* (anchor on the
  general facts: VE ≈ 15–20 kWh/100 km, trajet quotidien typique 30–50 km ≈ 6–10 kWh/jour — a small
  daily top-up, not a 0→100 % charge; per-panel kWh under Morocco's ~5 PSH stays qualitative/PENDING)
  · *7, 11 ou 22 kW + monophasé vs triphasé* (7 kW = mono OK; 11/22 kW = triphasé) · *jour vs nuit:
  recharge directe, batterie maison, ou borne « intelligente » qui suit le surplus solaire* (the key
  honesty point: dumb full-power solar-only charging is impractical without grid/battery/throttling)
  · *carport / abri solaire* · *V2H/V2G* (framed "à venir au Maroc") · *est-ce rentable face à
  l'essence ?* (Moroccan fuel/tariff figures come from `CONTENT_SEO_NOTES.md` / the EV blog post
  W136 as labelled, sourced ranges — not a founder ask). Tie the whole page
  to the loi 82-21 self-consumption angle (export capped/cheap → charge from your own surplus). Carry
  `Service` + `BreadcrumbList` JSON-LD, a self-referencing canonical, a real `og` image (reuse an
  existing `/og/*.png`), and a visual FAQ via `Faq` with **`schema={false}`** (the EV Q in W119 own
  the schema on `/faq`). Internal-link to `/batteries-stockage`, `/équipement`, `/guides`, `/contact`.
  Surface it from `/nos-solutions` body copy and the `/guides` hub (do NOT edit the shared `Header`
  nav in this task — a nav-dropdown entry is a separate, optional follow-up so this lane stays
  single-file-plus-its-links). Accept: the page ranks-ready (unique title/description, valid
  Service+Breadcrumb JSON-LD, one canonical, one h1), no fabricated MAD/kWh, in the sitemap, FR copy.
  Files: new `apps/web/src/pages/recharge-voiture-electrique-solaire.astro` (+ contextual links from
  `nos-solutions.astro` / `guides/index.astro` handled in W129).

- [x] W121 — **Guide: « Combien de panneaux et quelle puissance (kWc) pour ma maison ? »** New guide
  page following the existing `/guides/*` pattern (Layout, Breadcrumb, `Article` JSON-LD, CtaBand,
  StickyCta). Explains the sizing METHOD from the ONEE/Lydec bill → annual kWh → kWc → panel count
  (m²/panel geometry, ~1,7–2 m²/panel are general facts), the high-Morocco-irradiation note kept
  qualitative, and routes to the diagnostic. No new price/kWh figure (method only; any Morocco
  kWh/kWc from `CONTENT_SEO_NOTES.md` §3, cited). Accept: clean Article page, single canonical, no invented number,
  internal-linked, listed by W129. File: `apps/web/src/pages/guides/combien-de-panneaux-pour-ma-maison.astro`.

- [x] W122 — **Guide: « On-grid, off-grid ou hybride : que se passe-t-il pendant une coupure ? »**
  New guide complementing the existing `onduleur-hybride-ou-reseau` guide: when each system type
  fits (grid-tied = best ROI for ONEE-connected urban homes, off-grid = remote/no-grid, hybrid =
  backup), and the safety fact that a standard grid-tied system disconnects in a blackout
  (anti-îlotage) so backup needs a hybrid + battery. `Article` JSON-LD, no invented number. Accept:
  as W121. File: `apps/web/src/pages/guides/on-grid-off-grid-ou-hybride.astro`.

- [x] W123 — **Guide: « Entretien, nettoyage et durée de vie des panneaux au Maroc ».** New guide on
  the strong local differentiator: dust/sand cleaning cadence, rain self-cleaning, heat de-rating
  (~0,3–0,5 %/°C above 25 °C — general fact), lifespan & degradation tied to the published warranty
  (84,8 % à 25 ans, ~0,5 %/an). `Article` JSON-LD. Accept: as W121. File:
  `apps/web/src/pages/guides/entretien-et-duree-de-vie-des-panneaux.astro`.

- [x] W124 — **Guide: « Orientation, inclinaison et ombrage : maximiser la production sur un toit
  marocain ».** New guide: plein sud optimal, E/O ne perd que ~10–15 %, inclinaison ≈ latitude
  (~30°), impact disproportionné de l'ombre sur une chaîne (cheminée, mur voisin, palmier) et la
  mitigation (optimiseurs/micro-onduleurs). General facts only. `Article` JSON-LD. Accept: as W121.
  File: `apps/web/src/pages/guides/orientation-inclinaison-ombrage.astro`.

- [x] W125 — **Guide: « Monocristallin ou polycristallin ? + onduleur string vs micro-onduleurs ».**
  New equipment-choice guide: mono (rendement 19–22 %, meilleur sous la chaleur, moins de surface)
  vs poly; onduleur string (moins cher, une chaîne pénalisée par l'ombre) vs micro/optimiseurs
  (suivi par panneau). General facts; tie equipment names only to what `/équipement` already
  publishes. `Article` JSON-LD. Accept: as W121. File:
  `apps/web/src/pages/guides/monocristallin-ou-polycristallin.astro`.

- [x] W126 — **Guide: « Batterie solaire : lithium LiFePO4 (LFP) vs GEL/plomb (et NMC) ».** New
  battery-chemistry guide complementing the existing `faut-il-des-batteries`: LFP wins on durée de
  vie (3 000–6 000 cycles / 10–15 ans vs 3–5 ans plomb), profondeur de décharge utile (~90 % vs
  ~50 %), rendement et tolérance à la chaleur (atout au Maroc), and LFP safety vs NMC. Anchor brand
  claims on the published Dyness LFP / 10-ans warranty only; no invented price. `Article` JSON-LD.
  Accept: as W121. File: `apps/web/src/pages/guides/batterie-lithium-ou-gel.astro`.

- [x] W127 — **Guide: « Quelle taille de batterie (kWh) pour ma maison ? Stocker ou revendre ? »**
  New battery-sizing guide: tiers (secours seul ~5–10 kWh, autoconsommation du soir ~10–20 kWh,
  quasi-autonomie 20 kWh+), usable-vs-nameplate kWh (DoD), and the Morocco economics — with export
  capped at 20 % and bought back below retail (loi 82-21, live 9 juin 2026), self-shifting a kWh to
  the evening beats exporting it; order of value = consommer en journée → stocker pour le soir →
  exporter les 20 %. Method only; client kWh from the bill stays qualitative. `Article` JSON-LD.
  Accept: as W121. File: `apps/web/src/pages/guides/quelle-taille-de-batterie.astro`.

- [x] W128 — **Guide: « Garder l'électricité pendant les coupures : EPS, onduleur hybride et
  batterie ».** New guide: backup ≠ off-grid (the key myth-buster), EPS/secours circuits on a
  Deye/Huawei hybrid, switchover behaviour, and why a standard grid-tie dies in an outage. General
  facts + published brand names only. `Article` JSON-LD. Accept: as W121. File:
  `apps/web/src/pages/guides/electricite-pendant-les-coupures.astro`.

- [x] W129 — **Update the `/guides` hub to list every new guide, grouped.** Today `guides/index.astro`
  lists 3 guides flat. Re-group into clear sections — **Solaire** (sizing W121, système/coupure W122,
  entretien W123, orientation W124, matériel W125, + the existing loi-82-21 & onduleur guides),
  **Batteries** (existing faut-il-des-batteries + chemistry W126 + sizing W127 + coupures W128),
  **Voiture électrique** (link the W120 pillar) — and add the contextual link to the W120 EV page +
  surface it from `/nos-solutions` body copy. Update the `CollectionPage` JSON-LD `hasPart` to include
  the new articles. Keep the design/voice. (Sequences AFTER W120–W128 so the links aren't dead.)
  Accept: hub lists all guides grouped, every link resolves, JSON-LD reflects the full set. Files:
  `apps/web/src/pages/guides/index.astro`, `apps/web/src/pages/nos-solutions.astro` (one contextual
  EV link). FR hub only; `/en/guides` + `/ar/guides` keep listing the 3 translated guides (correct —
  the new guides are FR-only).

- [x] W130 — **Enrich the public `/batteries-stockage` page with an SEO content + visual-FAQ block.**
  Add a question-led content section answering the top battery queries (do I need one, lifespan,
  sizing tiers, backup-during-outage, store-vs-sell Morocco angle) using the `Faq` component with
  **`schema={false}`** (so `/faq` stays the single `FAQPage` owner), plus internal links to the new
  battery guides (W126–W128) and `/garanties`. Reuse published facts only; no invented price. Live
  lead form untouched. Accept: richer page, still one canonical, no second `FAQPage`, no fabricated
  number; `/en` + `/ar` mirrors left for the FR-first follow-up. File:
  `apps/web/src/pages/batteries-stockage.astro`.

- [x] W131 — **Tests for the content-expansion invariants.** Extend the `apps/web` Vitest suite
  (build on `tests/seoInvariantsW104.test.ts`): `/faq` is still the ONLY route emitting a `FAQPage`
  (the EV page + `/batteries-stockage` render the `Faq` component with `schema={false}` → no second
  `FAQPage`); every NEW page (W120–W128) has exactly one self-referencing canonical and carries
  `Article`/`Service` + `BreadcrumbList` JSON-LD; the new public routes ARE in the sitemap and
  `/preview/*` still is NOT; a guard asserting volatile market figures render as labelled ranges
  (« indicatif » / dated) rather than bare fabricated single-point prices (best-effort). Accept: new assertions pass,
  full suite green, Lighthouse held 97–100. Files: `apps/web/tests/*.ts` (+ new files as needed).

---

### W132–W139 — DATED BLOG (Astro content collection) + data-driven cornerstone posts (founder-authorized architecture, 2026-06-21)

<!-- lane: apps/web -->

*The founder green-lit the architecture change for a real **blog** (was gated WG4). This adds a
**dated, numbers-and-market editorial layer** that is deliberately DISTINCT from the evergreen
`/guides` (concept explainers) to avoid keyword cannibalization: guides answer "comment ça marche"
forever; blog posts are **dated, chiffrés, sourced** market/regulatory/analysis pieces that signal
freshness and get refreshed. The blog is where the **VOLATILE** figures from
[`apps/web/CONTENT_SEO_NOTES.md`](../apps/web/CONTENT_SEO_NOTES.md) live (prices, tariffs, buyback,
fuel) — published as cited, dated, labelled ranges.*

> **CONSTRAINTS (whole block).** Same standing rules as W119–W131 (strictly `apps/web/**`, FR,
> live lead form untouched, previews untouched, Lighthouse 97–100, zero CLS, one h1, alt text).
> **No new npm/paid dependency:** the blog uses **core Astro content collections** (`glob` loader +
> Zod schema — already in Astro 6, no package) and a **hand-rolled `/rss.xml` endpoint** (no
> `@astrojs/rss`). Numbers trace to `CONTENT_SEO_NOTES.md` with their source + the PUBLISH-SAFE /
> LOCK-FIRST discipline (cited ranges; a LOCK-FIRST figure is locked from a primary source by the
> task / W140, else published as a labelled « fourchette indicative » — never deferred to the
> founder; `PENDING(Reda)` reserved strictly for founder-owned assets like real reviews/photos).
> **Drafts never ship:** a `draft: true` post is excluded from the
> build output, the index, the sitemap and the RSS feed. Posts are FR-only for now (not in the
> i18n registry). Cross-link blog ↔ guides ↔ service pages so intent is clear and link equity flows.
> **Lanes:** W132 builds the architecture (collection config + routes + RSS + nav) → it MUST land
> before the posts; W133–W138 are independent Markdown files (parallel once W132 exists); W139
> (tests) sequences last. (All in the `apps/web` lane → built in listed order.)

- [x] W132 — **Blog architecture (content collection + routes + RSS + nav), dependency-free.** Add a
  `blog` content collection: `apps/web/src/content.config.ts` defining `defineCollection({ loader:
  glob({ pattern: '**/*.md', base: './src/content/blog' }), schema })` with a Zod schema
  (`title`, `description`, `pubDate`, optional `updatedDate`, `tags: string[]`, `author` default
  "Taqinor", optional `ogSlug`, `draft` default false). Build `apps/web/src/pages/blog/index.astro`
  (lists published posts newest-first, drafts excluded, same `v2`/Layout design as `/guides`,
  Breadcrumb, CtaBand, StickyCta, `Blog` or `CollectionPage` JSON-LD) and
  `apps/web/src/pages/blog/[...slug].astro` (renders the Markdown via the content `render()` API
  with `BlogPosting` + `BreadcrumbList` JSON-LD, self-referencing canonical, real `og` image from an
  existing `/og/*.png` via `ogSlug` fallback, prose styling matching the guide pages, prev/next +
  related links). Add a hand-rolled `apps/web/src/pages/rss.xml.ts` endpoint emitting valid RSS 2.0
  for published posts (no `@astrojs/rss`), and a `<link rel="alternate" type="application/rss+xml">`
  in `Layout`. Add a **"Blog"** entry to the Ressources dropdown in `Header.astro` (FR nav; the
  `/blog` route auto-enters the sitemap). Ship ONE seed post (or W133) so the routes render. Accept:
  `/blog` and a post route render with valid `BlogPosting` JSON-LD + one canonical, `/rss.xml`
  validates, a `draft:true` post is absent from index/sitemap/RSS, no new dependency, Lighthouse
  held. Files: `apps/web/src/content.config.ts`, `apps/web/src/pages/blog/index.astro`,
  `apps/web/src/pages/blog/[...slug].astro`, `apps/web/src/pages/rss.xml.ts`,
  `apps/web/src/layouts/Layout.astro` (RSS link), `apps/web/src/components/Header.astro` (nav),
  `apps/web/src/content/blog/` (seed).

- [x] W133 — **Post: « Combien coûte une installation solaire au Maroc en 2026 ? » (cost pillar).**
  Markdown post using `CONTENT_SEO_NOTES.md` §5: turnkey **fourchettes indicatives** by size
  (3 kWc ~28–42 k, 5 kWc ~45–65 k, 10 kWc ~85–120 k MAD) and **~10 000–14 000 DH/kWc** turnkey —
  explicitly debunk the "4 700 DH/kWc" anchor as kit-only; equipment ranges, roof surcharges, the
  battery add-on (+22–60 k), and the **TVA nuance** (panneaux nus exonérés sans déduction vs pose
  clé-en-main à 20 % avec déduction; onduleurs droits de douane 17,5 %→2,5 %). Every figure labelled
  « indicatif 2026 » with its source; Taqinor's real quote → CTA to the diagnostic, not a hard price.
  Cross-link the sizing guide (W121) + ROI post (W134). Accept: dated post renders with cited ranges,
  no false precision, `BlogPosting` schema. File: `apps/web/src/content/blog/prix-installation-solaire-maroc-2026.md`.

- [x] W134 — **Post: « Rentabilité et retour sur investissement du solaire par ville marocaine ».**
  Uses `CONTENT_SEO_NOTES.md` §3+§2: the **kWh/kWc/yr by city** table (Casablanca 1 500–1 600,
  Marrakech ~1 779, Ouarzazate ~1 850–1 950, etc., cited PVGIS/Solargis), the **"sélective" tranche
  mechanism** (above 150 kWh/mo you pay the high marginal rate on everything — what solar removes),
  and the **5–7 yr payback** consensus. Use the locked ONEE grid from `CONTENT_SEO_NOTES.md` §2
  (date-stamped); if a fresher rate is needed the task locks it from the ONEE/distributor tariff
  source (W140), else publishes the date-stamped range. Cross-link the cost pillar (W133) + loi
  82-21 post (W135). Accept: cited
  city/yield table + payback, freshness-flagged tariffs. File:
  `apps/web/src/content/blog/rentabilite-solaire-par-ville-maroc.md`.

- [x] W135 — **Post: « Loi 82-21 : ce qui change depuis le 9 juin 2026 (autoproduction, plafond
  20 %, rachat 0,18–0,21 DH) ».** Regulatory deep-dive from `CONTENT_SEO_NOTES.md` §1: the three
  regimes + thresholds (≤11 kW déclaration / 11 kW–5 MW accord / >5 MW autorisation), the **9 June
  2026** entry into force, the **20 % surplus cap**, the **net-billing (not net-metering)** fact and
  the **0,18–0,21 DH buyback ≪ retail** consequence (self-consumption is where the value is). Penalties
  + Article 33 18-month window included, locked from the Bulletin Officiel / decree text by W140
  (or stated qualitatively if a primary article reference can't be reached — never a founder ask). Complements the existing `/guides/loi-82-21-expliquee` (this one is dated + numeric).
  Accept: accurate cited regulatory post with the honest self-consumption conclusion. File:
  `apps/web/src/content/blog/loi-82-21-autoproduction-2026.md`.

- [x] W136 — **Post: « Recharger sa voiture électrique au solaire : combien ça coûte vraiment au
  Maroc ? »** Economics piece from `CONTENT_SEO_NOTES.md` §6: the **cost-per-100 km** comparison —
  petrol ~93 MAD vs EV-on-grid ~23 MAD (¼) vs EV-on-solar ~0–13 MAD — **with the assumptions stated
  inline** (petrol 6,5 L/100 km, essence 14,27 MAD/L mid-Jun-2026, EV 15 kWh/100 km +10 %, grid
  ~1,40 DH/kWh marginal), the **panels-per-EV (~2–4 × 550 W)** rule, and **7 kW monophasé vs 11/22 kW
  triphasé**. Fuel price date-stamped + flagged biweekly. This is the dated companion to the W120 EV
  service page (link both ways). Accept: cited, assumption-transparent EV-vs-petrol economics. File:
  `apps/web/src/content/blog/recharger-voiture-electrique-solaire-cout-maroc.md`.

- [x] W137 — **Post: « Batterie solaire : stocker ou revendre ? L'économie de l'autoconsommation au
  Maroc ».** From `CONTENT_SEO_NOTES.md` §1+§7: with export capped at 20 % and bought back at
  0,18–0,21 DH while you buy at 0,90–1,66 DH, a **stored-and-self-used kWh beats an exported one**;
  the **order of value** (consommer en journée → stocker le soir → exporter les 20 %), generic LFP
  **~3 000–4 000 DH/kWh** (LOCK-FIRST; the 12 400 DH/kWh outlier explicitly excluded), battery
  payback +1–3 yr. Cross-link battery sizing guide (W127) + Dyness post (W138). Accept: the Morocco
  store-vs-sell economics, honestly framed, cited ranges. File:
  `apps/web/src/content/blog/batterie-stocker-ou-revendre-maroc.md`.

- [x] W138 — **Post: « Quelle batterie LFP choisir : la gamme Dyness, et Deye vs Huawei pour le
  secours ».** Product/spec deep-dive from `CONTENT_SEO_NOTES.md` §7: the **Dyness LFP lineup** (B4850
  2,4 kWh, PowerDepot H5B 5,12 kWh w/ built-in heating, Tower T7/T10/T14, PowerBrick 14,34 kWh — LFP,
  ≥6 000 cycles, 10-yr/70 % warranty) and the **backup differentiator** — **Deye SG-series near-seamless
  ~4–10 ms UPS, no extra box, 48 V LFP, 6 TOU windows** vs **Huawei SUN2000 + Backup Box (<3 s
  changeover, three-phase M0 = no backup)** — plus the LFP lifespan/heat facts (10–15 yr, +10 °C ≈
  halves life, never charge <0 °C). Lock the spec conflicts (efficiency %, H5B 7-vs-10-yr) from the
  official Dyness datasheets via W140; publish what's locked, omit what isn't — no founder ask.
  Complements the chemistry guide (W126). Accept: accurate cited product/backup post. File:
  `apps/web/src/content/blog/batterie-lfp-dyness-deye-huawei.md`.

- [x] W139 — **Tests for the blog.** Add `apps/web` Vitest coverage: the blog collection schema parses
  the seed posts; `/rss.xml` emits valid RSS 2.0 (well-formed XML, item count = published posts);
  a `draft:true` fixture post is **excluded** from the index, the sitemap and RSS; each post route has
  exactly one self-referencing canonical and carries `BlogPosting` + `BreadcrumbList` JSON-LD and NO
  second `FAQPage`; `/blog` is present in the sitemap and `/preview/*` still absent. Accept: new
  assertions pass, full suite green, Lighthouse held. Files: `apps/web/tests/*.ts` (+ new files).

### W141–W145 — FICHES TECHNIQUES LIBRARY (host product datasheets on taqinor.ma; founder request 2026-06-21)

*Goal: the equipment in every quote (panels, inverters, batteries, smart meter,
dongle…) gets a real **fiche technique** that lives on taqinor.ma — so the
quote PDF/web proposal can link `taqinor.ma/produits/<slug>` and the client
downloads the datasheet from OUR site, not a manufacturer's. The quote engine
already links to `taqinor.ma/produits`; these tasks build that destination.*

> **Source datasheets (official manufacturer PDFs — host a copy + cite the
> source on each page).** Catalogue products map to these public datasheets:
> - **Panneau Canadian Solar 710W** (TOPBiHiKu7, CS7N-685…715TB-AG) →
>   `https://static.csisolar.com/wp-content/uploads/2022/12/12090125/CS-Datasheet-TOPBiHiKu7-TOPCon_CS7N-TB-AG_v1.62C3_EN.pdf`
> - **Panneau Jinko 710W** (Tiger Neo 66HL5-BDV 710–735W) → hub
>   `https://www.jinkosolar.com/en/site/tigerneo` (datasheet via ENF
>   `https://www.enfsolar.com/pv/panel-datasheet/crystalline/68315`)
> - **Onduleurs réseau Huawei 5/10/12kW** (SUN2000-3-10KTL-M1/M0) →
>   `https://solar.huawei.com/-/media/Solar/attachment/pdf/apac/datasheet/SUN2000-5-10KTL-M0-M1.pdf`
> - **Onduleur réseau Huawei 100kW** (SUN2000-100KTL) →
>   `https://solar.huawei.com/-/media/Solar/attachment/pdf/in/datasheet/SUN2000-100KTL-INM0.pdf`
> - **Onduleurs hybrides Deye 5–12kW** (SUN-5/6/8/10/12K-SG04LP3-EU) →
>   `https://www.deyeinverter.com/deyeinverter/2024/10/21/datasheet_sun-5-12k-sg04lp3_241021_en.pdf`
> - **Batterie Dyness** (DL5.0C / DL5.0C PRO, LFP 5,12 kWh) →
>   `https://www.dyness.com/Public/Uploads/uploadfile/files/20241023/DynessDL5.0CdatasheetEN.pdf`
>   (the catalogue label "Deyness" is the **Dyness** brand — page Équipement confirms it)
> - **Smart Meter Huawei** (DTSU666-H Smart Power Sensor) →
>   `https://solar.huawei.com/~/media/Solar/attachment/pdf/es/datasheet/SmartPowerSensor.pdf`
> - **Wifi Dongle Huawei** (Smart Dongle-WLAN-FE, SDongleA-05, region MEA) →
>   `https://solar.huawei.com/-/media/Solar/attachment/pdf/mea/datasheet/SmartDongle-WLAN-FE.pdf`
> - Structures acier/alu, Socles, Tableau AC/DC, Accessoires, Installation,
>   Transport, Suivi = **TAQINOR's own** components/prestations — no manufacturer
>   datasheet; author a short in-house spec card (founder supplies copy) or omit.
> Quote-engine slugs (must match these pages so the PDF links resolve):
> `canadian-solar-710`, `jinko-710`, `onduleur-huawei-reseau`,
> `onduleur-deye-hybride`, `batterie-dyness`, `smart-meter-huawei`,
> `wifi-dongle-huawei`.

- [x] W141 — **Host the datasheet PDFs on taqinor.ma.** *(2026-06-21: `fiches.ts`
  manifest shipped (7 products, Dyness corrected) + `ficheDownloadHref` uses the
  self-hosted `/fiches/<slug>.pdf` when present, else the official source — so the
  download always works today. Actually fetching + self-hosting the PDF binaries
  is split out into **W146** (a normal build task — NOT a founder chore), because a
  bare programmatic GET hit HTTP 403 on at least one manufacturer; W146 fetches
  them with a real browser UA / mirror and flips the `pdf` fields.)* Download each official PDF
  above into `apps/web/public/fiches/<slug>.pdf` (one per slug; panels/inverters/
  battery/meter/dongle) so they are served from `taqinor.ma/fiches/<slug>.pdf` —
  no hotlinking a manufacturer URL at runtime. Keep a small
  `apps/web/src/data/fiches.ts` manifest (slug → {nom, marque, modèle, catégorie,
  pdf path, source URL, key specs}) as the single source of truth. **Done =** each
  PDF is reachable under `/fiches/<slug>.pdf`; the manifest lists every catalogue
  product with a datasheet; vitest asserts every manifest `pdf` file exists.
  Files: `apps/web/public/fiches/*.pdf`, `apps/web/src/data/fiches.ts`.

- [x] W142 — **Fiches library hub `/produits`.** A premium, mobile-first public page
  listing every product from the W141 manifest grouped by catégorie (Panneaux,
  Onduleurs réseau, Onduleurs hybrides, Batteries, Accessoires), each card showing
  marque/modèle + key specs + a "Fiche technique (PDF) ›" download and a link to its
  detail page (W143). Brand-filterable. Mirrors the site's navy/gold + DM Serif/DM
  Sans language. This IS the destination the quote engine already links to
  (`taqinor.ma/produits`). **Done =** `/produits` renders the full grid responsively
  (Lighthouse mobile ≥ 90); each card downloads the right PDF. Files: new
  `apps/web/src/pages/produits/index.astro` + a card component, reads `fiches.ts`.

- [x] W143 — **Per-product fiche pages `/produits/<slug>`.** A detail route generated
  from the W141 manifest (`getStaticPaths`) for each slug: hero (marque/modèle/
  catégorie), a clean key-spec table, the embedded/downloadable datasheet, the
  TAQINOR garanties for that family, and a "Demander un devis" CTA. Add JSON-LD
  `Product` structured data (keep `/faq` the sole FAQPage owner — see W98). **Done =**
  every slug renders with specs + PDF + valid Product JSON-LD; included in the
  sitemap; vitest covers one panel + one inverter slug. Files: new
  `apps/web/src/pages/produits/[slug].astro`, reuse SEO head partial.

- [x] W144 — **Wire the funnel: link fiches from the web proposal (W116) + nav.** *(2026-06-21: nav (Ressources dropdown) + footer now expose `/produits`, and the **devis PDF** already deep-links each equipment line to `/produits/<slug>`. The web-proposal row-linking part waits on W116, which is not built yet.)* On
  the client web proposal (W116), make each equipment line link to its
  `/produits/<slug>` page (match by the same slug map above; unmatched lines stay
  plain text). Add "Produits / Fiches techniques" to the site nav + footer so the
  library is discoverable. **Done =** proposal equipment rows deep-link to the right
  fiche; nav/footer expose `/produits`; vitest asserts the slug map resolves the
  catalogue's panel/inverter/battery names. Files: `proposition/[token].astro`
  (W116), nav/footer components, shared slug map in `fiches.ts`.

- [x] W145 — **Sitemap + SEO for the library.** Ensure `/produits` and every
  `/produits/<slug>` are in the sitemap (W100), have unique titles/descriptions
  (W99), and that the PDFs are crawlable but not duplicated as canonical pages.
  **Done =** sitemap includes the library; per-page head is unique; Vitest SEO
  invariants (W104) extended to cover `/produits`. Files: sitemap config,
  `produits/*` heads, SEO tests.

- [x] W146 — **Self-host the actual datasheet PDFs on taqinor.ma (no manufacturer
  hotlink).** For every fiche in `src/lib/fiches.ts`, fetch the official PDF from
  its `datasheet` URL and save it under `apps/web/public/fiches/<slug>.pdf`, then
  set the manifest `pdf` field to `/fiches/<slug>.pdf` so `ficheDownloadHref`
  serves the file from OUR domain (the source URL stays the automatic fallback, so
  the link is never dead). Some manufacturer URLs return **HTTP 403 to a bare
  programmatic GET** (seen on Canadian Solar from the build env): fetch with a
  normal browser `User-Agent`/`Referer`, or pull the same datasheet from the
  manufacturer's product page / official mirror — **research it, do not leave it as
  a founder chore**; only the genuinely unreachable ones stay on the source-URL
  fallback with a one-line note. Keep file sizes sane (these are ~1–3 MB each).
  **Done =** every reachable fiche serves a self-hosted `/fiches/<slug>.pdf`;
  `fiches.test.ts` asserts that any non-null `pdf` path exists on disk under
  `apps/web/public`. Files: `apps/web/public/fiches/*.pdf`,
  `apps/web/src/lib/fiches.ts`, `apps/web/tests/fiches.test.ts`.

- [x] W147 — **Embed the datasheet inline on each `/produits/<slug>` page.** Beyond
  the download button, render the self-hosted PDF inline (a lazy `<object>`/
  `<iframe>` preview with a graceful "Télécharger la fiche (PDF)" fallback for
  mobile/no-PDF-viewer), so the fiche is truly *integrated* in the page, not just
  linked out. Respect reduced-motion and keep CLS at zero (reserve the box). Skip
  the embed (download-only) when a fiche has no self-hosted `pdf` yet (W146). **Done
  =** a slug with a hosted PDF shows an inline preview on desktop + a clean download
  fallback on mobile; Lighthouse stays ≥ 95; Vitest covers the embed-vs-fallback
  branch. Files: `apps/web/src/pages/produits/[slug].astro`, `tests/fiches.test.ts`.

### W148–W221 — WEBSITE BEAUTY & POLISH AUDIT (founder request 2026-06-21)

*Goal: lift the public site from "tasteful and quiet" to "expensive and gripping"
on both phone and desktop, without touching the lead-mechanics flow (form fields,
1 000 MAD threshold, consent, WhatsApp deeplink, webhook, CAPI stay byte-identical).
Sourced from a 9-lane parallel design audit (hero, design-system, mobile/RTL, nav
chrome, imagery, forms, content, motion, perf/a11y). Every task is presentational,
reduced-motion-safe, and revertable. **Two tasks are asset-blocked** (founder must
supply a photo / official brand SVGs) — flagged inline; build the rest.*

**— Structural / highest-impact —**

- [x] W148 — **Restore the dark→light "salle blanche" diagnostic climax.** The page
  now runs one flat navy tone top-to-bottom; the lit final act was removed, so the
  scroll never "arrives." Bring back an illuminated diagnostic act (or a dramatically
  brighter glass-lifted card on a luminous gradient) and wire up the unused
  `.seam-lumiere`. Files: `apps/web/src/components/DiagnosticForm.astro`,
  `apps/web/src/styles/global.css`.
- [x] W149 — **Make the hero CTA own the first 3 seconds.** Shorten "Recevez votre
  étude sur WhatsApp", give the button a persistent golden halo (the `.glow` resting
  state barely glows today) and a larger size/weight so it's unmistakably the focal
  point. Files: `apps/web/src/pages/index.astro`, `apps/web/src/styles/global.css`.
- [x] W150 — **Scroll-reactive header.** It carries the same heavy `bg-nuit/90` slab
  over the cinematic hero as mid-page, with zero scroll JS. Start transparent/borderless
  over the hero → solid + backdrop-blur + condensed height + logo step-down past ~80px
  (reuse the rAF pattern in `StickyCta.astro`). Files: `apps/web/src/components/Header.astro`.
- [x] W151 — **Active-page indicator in the desktop nav.** No `aria-current`/active state
  exists; every link looks identical. Compute the current section from `rootPath` and
  render a brass underline / text on the active item. Files: `apps/web/src/components/Header.astro`.
- [x] W152 — **Footer redesign.** It's a flat link grid on bare `bg-nuit` with a 1px top
  border — the weakest element on the site. Add a brand block + phone/WhatsApp CTA buttons,
  a golden hairline/seam top edge, and real column hierarchy. Files: `apps/web/src/components/Footer.astro`.
- [x] W153 — **Ship the founder portrait.** *(Shipped 2026-06-21: founder supplied the photo
  (`DSC_0612.JPG`, Nikon 6016×4000) inside a zip; generated 4:5 face-framed AVIF+WebP derivatives
  at 640/480 into `public/photos/fondateur-portrait-*`, set `FOUNDER_PHOTO='fondateur-portrait'`,
  and recorded provenance as a `PHOTOS` entry in `process-photos.mjs`. The doctor-engineer trust
  section now renders the real portrait + "Reda Kasri" caption instead of the text fallback.)*
  Files: `apps/web/src/components/FounderPortrait.astro`, `apps/web/scripts/process-photos.mjs`,
  `apps/web/public/photos/fondateur-portrait-*`.

**— Homepage & hero —**

- [x] W154 — **Richer art-directed hero scrim** (layered radial vignette + text-side
  darkening) so the golden headline always reads over busy photos. Files: `apps/web/src/pages/index.astro`.
- [x] W155 — **Portrait-crop hero `<source>` for phones.** One 16:9 landscape is center-punched
  on tall screens; add `media="(orientation: portrait)"` with a vertical crop. Files:
  `apps/web/src/pages/index.astro`, `apps/web/src/pages/realisations/[slug].astro`, `apps/web/src/components/Picture.astro`.
- [x] W156 — **Consistent monumental `.fig .lum` trust-band figures** (the four-up row mixes
  one golden `text-4xl` with three plain white `text-xl`). Files: `apps/web/src/pages/index.astro`.
- [x] W157 — **Lift `.cine-card`** from near-invisible (`bg-white/0.04`) with faint glass
  blur, a top-edge highlight, and a warm brass hover. Files: `apps/web/src/styles/global.css`.
- [x] W158 — **Refine section seams** — replace stacked hard `border-y border-white/10`
  hairlines with occasional gradient/glow transitions. Files: `apps/web/src/pages/index.astro`,
  `apps/web/src/styles/global.css`.
- [x] W159 — **Vary the repeated eyebrow treatment** (`tech-label + rule-brass` used ~9×
  down the homepage → wallpaper). Files: `apps/web/src/pages/index.astro`.
- [x] W160 — **Refine the Article 33 ribbon** so it reads as a premium announcement, not an
  admin bar above the hero. Files: `apps/web/src/components/Article33Ribbon.astro`.
- [x] W161 — **Add a hero scroll affordance** (subtle animated chevron / peeking next-section
  edge). Files: `apps/web/src/pages/index.astro`.
- [x] W162 — **Warm the austere "L'argument en chiffres" stat column** (faint brass backing /
  baseline glow). Files: `apps/web/src/pages/index.astro`.

**— Navigation chrome —**

- [x] W163 — **Rotate dropdown chevrons on open + polish dropdown panels** (rounded, layered
  shadow, brass top accent). Files: `apps/web/src/components/Header.astro`.
- [x] W164 — **Upgrade the mobile menu** into an animated panel: replace the emoji 📞 with the
  existing phone SVG, move the language switcher inside it, and add
  `max-h-[calc(100svh-3.5rem)] overflow-y-auto overscroll-contain`. Files: `apps/web/src/components/Header.astro`.
- [x] W165 — **Refine the StickyCta pill** (the green WhatsApp button breaks the brass/night
  palette; add the glow) and add `env(safe-area-inset-bottom)` padding so notched iPhones don't
  bury it. Files: `apps/web/src/components/StickyCta.astro`.
- [x] W166 — **Chevron + RTL-safe breadcrumb separators** (literal `/` doesn't flip for Arabic).
  Files: `apps/web/src/components/Breadcrumb.astro`.
- [x] W167 — **LanguageSwitcher discoverability + ≥44px tap target** (currently `text-xs`, ~24px).
  Files: `apps/web/src/components/LanguageSwitcher.astro`.
- [x] W168 — **Logo sun-mark glow + elevate the ZelligeDivider motif** (currently ~18px, nearly
  invisible). *(Asset available 2026-06-21: official TAQINOR logo pack — main/inverted/monochrome
  SVGs — at `apps/web/public/brand/`; use it instead of the hand-coded inline mark if it reads
  better.)* Files: `apps/web/src/components/Logo.astro`, `apps/web/src/components/ZelligeDivider.astro`,
  `apps/web/public/brand/`.

**— Design system & consistency —**

- [x] W169 — **Extend the modular scale to body + figure sizes as tokens** (`.fig-xl/lg/md`,
  `.v2-body`); 519 ad-hoc `text-*` uses across 40 pages drive drift. Files: `apps/web/src/styles/global.css` + sweep.
- [x] W170 — **Bring `produits/*` + legal pages onto the `v2-page-title` scale + `V2Enhance`
  engine** (they bypass it and feel like a different site). Files: `apps/web/src/pages/produits/index.astro`,
  `apps/web/src/pages/produits/[slug].astro`, `politique-de-confidentialite.astro`, `mentions-legales.astro`.
- [x] W171 — **Extract a `PhotoCaption` scrim component** (duplicated ~30× verbatim with drifting
  padding). Files: new `apps/web/src/components/PhotoCaption.astro` + gallery pages.
- [x] W172 — **Tokenize the hero scrim gradient** (mid-stop hand-tuned per page: `/35`, `/45`,
  `/55`…). Files: `apps/web/src/styles/global.css` + heroes.
- [x] W173 — **Section vertical-rhythm scale utilities** (`.section`/`.section-lg`/`.section-tight`);
  121 magic `py-*` values across 40 files. Files: `apps/web/src/styles/global.css` + sweep.
- [x] W174 — **Extract the outline-pill link button + the premium drop-shadow into utilities.**
  Files: `apps/web/src/styles/global.css` + contextual-link rows site-wide.
- [x] W175 — **Resolve the azur-vs-brass light-eyebrow inconsistency + componentize the
  "salle blanche" palette-swap with its seam.** Files: `apps/web/src/styles/global.css`, light-section pages.
- [x] W176 — **Align off-scale section headings** (`DiagnosticForm`, `Faq`, `CtaBand`) to
  `v2-section-title`. Files: those components.
- [x] W177 — **Add a design-tokens doc + optional lint** guarding arbitrary `text-[…]`/`shadow-[…]`
  figure values. Files: `apps/web/STYLE.md` (or new doc), `apps/web/tests/`.

**— Imagery & media —**

- [x] W178 — **Lightbox / zoom on gallery + case-study photos** (detail shots are never viewable
  full-size today). Files: `apps/web/src/pages/realisations/index.astro`, `apps/web/src/pages/realisations/[slug].astro`.
- [x] W179 — **Standardize one hover-zoom token** across all clickable photo cards (inconsistent
  `1.02`/`1.04`/none). Files: `apps/web/src/components/VideoChantier.astro` + gallery pages.
- [x] W180 — **Fix mixed aspect-ratio crop vs declared `ratio`** (silent crop + slightly wrong
  anti-CLS height). Files: `apps/web/src/pages/index.astro`, `apps/web/src/pages/realisations/[slug].astro`.
- [x] W181 — **Add `object-position` focal-point control to `Picture.astro`** (everything is
  center-cropped). Files: `apps/web/src/components/Picture.astro`, `apps/web/src/lib/realisations.ts`.
- [x] W182 — **Style the chantier `<video>`** (default browser chrome clashes with navy/brass;
  add poster + explicit dims + a save-data/mobile encode). Files: `apps/web/src/components/VideoChantier.astro`.
- [x] W183 — **Optical-size-normalize + monochrome the brand-logo row** (per-brand height
  multipliers + grayscale→color hover). Files: `apps/web/src/lib/brands.ts`, `apps/web/src/components/BrandStrip.astro`.
- [x] W184 — **Before/during/after diptych or slider on case pages** (source material already
  exists). Files: `apps/web/src/pages/realisations/[slug].astro`, `apps/web/src/lib/realisations.ts`.
- [x] W185 — **Per-realisation OG card** (each case reuses a generic OG today). Files:
  `apps/web/src/pages/realisations/[slug].astro`.
- [x] W186 — **Optional duotone/grade pass on non-hero photos** so the imagery matches the
  "Cinéma du chantier" claim (keep the hero ungraded for LCP). Files: `apps/web/scripts/` or scoped
  `apps/web/src/styles/v3-photo-motion.css`.
- [BLOCKED: founder must drop 6 official brand SVGs or widen the network egress allowlist] W187 — **Source real brand-logo SVGs** (Canadian Solar, Huawei, Deye, Jinko, JA Solar,
  Dyness, Nexans) to replace the text word-mark fallback. These are THIRD-PARTY *manufacturer*
  logos for the partner trust-strip — distinct from Taqinor's own mark (W168). *(BLOCKED 2026-06-21:
  net-sourcing attempted but this environment's network egress is ALLOWLISTED — only npm-type hosts
  are reachable; commons.wikimedia.org and the open web return `403 Host not in allowlist`. Of the 7,
  only Huawei exists in a reachable npm logo set (`simple-icons`); the 6 solar brands are in none.
  To finish, EITHER the founder drops the 6 remaining official monochrome SVGs (Canadian Solar,
  JA Solar, Jinko, Deye, Dyness, Nexans) in a zip — best, from each brand kit — OR widens the
  environment's network egress allowlist to include the logo source hosts, then a run can fetch them.)*
  Files: `apps/web/public/brands/`, `apps/web/src/lib/brands.ts`.

**— Forms & interactive widgets (visual-only; lead mechanics untouched) —**

- [x] W188 — **16px inputs (kill iOS zoom-on-focus) + ~44px tap targets + sized consent
  checkboxes** (the live `DiagnosticForm` lags the roof tool, which already fixed this). Files:
  `apps/web/src/components/DiagnosticForm.astro`, `DiagnosticFormEnriched.astro`, `RegimeSelector.astro`.
- [x] W189 — **Polish the multi-step progress bar** (`bg-azur-100` reads as "complete" on navy;
  4px thin). Files: `apps/web/src/components/DiagnosticForm.astro`.
- [x] W190 — **Elevate the "your estimate" result card** into a premium payoff (framing, glow
  seam, value-vs-label hierarchy). Files: `apps/web/src/components/DiagnosticForm.astro`.
- [x] W191 — **Submitting spinner + `aria-busy` + fade-in results** (today it's a silent text
  swap and the result pops). Files: `DiagnosticForm.astro`, `DiagnosticFormEnriched.astro`, `RegimeSelector.astro`,
  `apps/web/src/styles/global.css` (one `@keyframes spin`).
- [x] W192 — **Estimator chips as a true segmented control + branded range sliders** (active
  state nearly invisible on dark). Files: `apps/web/src/pages/preview/toiture-3d-pro-11.astro`.
- [x] W193 — **WhatsAppMock realism** (delivered/read ticks, "en ligne" dot, bubble polish).
  Files: `apps/web/src/components/WhatsAppMock.astro`.
- [x] W194 — **Strengthen error/validation styling + placeholder contrast + focus-ring presence.**
  Files: `DiagnosticForm.astro`, `DiagnosticFormEnriched.astro`, `RegimeSelector.astro`.

**— Content & reading experience —**

- [x] W195 — **Shared `.prose` article style for guides + blog + a body-vs-lead type rank**
  (guides set whole bodies at lead size; blog reinvents prose separately). Files: new shared style,
  `apps/web/src/pages/blog/[...slug].astro`, `apps/web/src/pages/guides/*.astro`.
- [x] W196 — **Constrain long-form measure to ~65–70ch** (bodies sit in `max-w-3xl`). Files: guides/blog.
- [x] W197 — **Reading-time + auto table-of-contents on long articles.** Files: guides/blog.
- [x] W198 — **Cover image + hover lift on guide/blog index cards; cover + figure pattern on
  articles.** Files: `apps/web/src/pages/guides/index.astro`, `apps/web/src/pages/blog/index.astro`, content schema.
- [x] W199 — **Reusable callout / pull-quote / key-figure prose component** so the "numbers are
  the protagonist" identity carries into prose. Files: new component + guides/blog.
- [x] W200 — **Branded list markers + table styling + mobile reflow; shared `RelatedLinks`
  component** for the duplicated internal-link chip rows. Files: shared prose style + new component + content pages.
- [x] W201 — **Standardize 2–3 sanctioned hero archetypes** so segment/service/city/guide heroes
  stop drifting. Files: `installation-solaire-[city].astro` + a short design note.

**— Motion & micro-interactions —**

- [x] W202 — **Fix the anchor scroll offset under the sticky header** (`#simulateur` lands hidden);
  add `scroll-padding-top`. Files: `apps/web/src/styles/global.css`.
- [x] W203 — **Card-level hover (lift/border) on content + product cards** (many clickable cards
  have no hover at all). Files: `apps/web/src/styles/global.css` (`.cine-card`) + card wrappers.
- [x] W204 — **Hover arrow nudge on gallery/CTA links** (`group-hover:translate-x-1`). Files:
  `apps/web/src/pages/index.astro`, `nos-solutions.astro`, `realisations/index.astro`.
- [x] W205 — **Lead with a count-up on the first above-the-fold figure** (the protagonist number
  is static text). Files: `apps/web/src/pages/index.astro`.
- [x] W206 — **Extract a `cine-in` stagger token** (literal `animation-delay:120/240/360ms`
  repeated across ~40 hero blocks). Files: `apps/web/src/styles/global.css` + heroes.
- [x] W207 — **Wire up or remove the orphaned `.reveal`/`.emerge` CSS scroll-timeline reveals**
  (defined, zero usages). Files: `apps/web/src/styles/global.css`, `v3-photo-motion.css`.
- [x] W208 — **Optional slow shimmer on `.seam-lumiere` + subtle brand-logo/testimonial-card hover.**
  Files: `apps/web/src/styles/global.css`, `v2.css`, `BrandStrip.astro`, `Testimonials.astro`.

**— Shared interaction primitives —**

- [x] W209 — **Global `focus-visible` brass ring on all interactive elements** (CTAs/nav/card
  links have none; some set `focus:outline-none`). Files: `apps/web/src/styles/global.css` + chrome.
- [x] W210 — **Propagate the signature `.glow` to every primary CTA** (header, CtaBand, StickyCta
  are flat `transition-colors`). Files: `Header.astro`, `CtaBand.astro`, `StickyCta.astro`.

**— Mobile & responsive —**

- [x] W211 — **Verify no 320px horizontal overflow from wide `whitespace-nowrap` figures**
  (`43,48 kWc`, `60–90 %`). Files: `index.astro`, `installation-solaire-[city].astro`, `realisations/[slug].astro` (+ mirrors).
- [x] W212 — **Add a middle breakpoint to the 3-col équipement comparison grid** (cramped in the
  md→lg band). Files: `apps/web/src/pages/équipement.astro` (+ `en/`/`ar/` twins).

**— RTL / Arabic —**

- [x] W213 — **Mirror the ~90 directional `→` arrows across `ar/*`** (direction-aware glyph or
  SVG flipped via `rtl:-scale-x-100`). Files: `apps/web/src/pages/ar/**`.
- [x] W214 — **Add a global `[dir="rtl"]` stylesheet** (accent rails, timeline dots, blockquote
  borders, spec-row alignment), flip the asymmetric two-column hero grids, and guard `tech-label`
  letter-spacing/uppercase off for Arabic. Files: `apps/web/src/styles/global.css`, `apps/web/src/pages/ar/**`.

**— Performance / rendering / accessibility finish —**

- [x] W215 — **Preload the hero headline font (`archivo-latin.woff2`) + add `size-adjust`
  metric-matched fallbacks** to kill the FOUT flash and font-swap CLS on the LCP `<h1>`. Files:
  `apps/web/src/layouts/Layout.astro`, `apps/web/src/styles/global.css`.
- [x] W216 — **Skip-to-content link + `id` on `<main>`.** Files: `apps/web/src/layouts/Layout.astro`.
- [x] W217 — **Set `color-scheme: dark` globally** (fixes light-mode native `<select>` menus on
  the dark canvas + scrollbar/autofill) + a `::selection` brass color. Files: `apps/web/src/styles/global.css`.
- [x] W218 — **Complete the favicon/app-icon set** + `site.webmanifest` + `theme-color`.
  *(Shipped 2026-06-21: real brand lockup wired as `apple-touch-icon.png` (256px) + `icon-512.png`
  from the official logo pack; added `site.webmanifest` (name/theme `#070b1d`/bg + 256+512 icons) and
  the `apple-touch-icon`/`manifest` head links; `theme-color` already present; kept the lightweight
  square sun `favicon.svg` for the 16–32px browser tab because the wordmark is illegible at that size.
  Deliberate deviations from the original spec: apple-touch is 256 not 180, no `.ico` (SVG-first), and
  icons are `purpose:"any"` not maskable — the wordmark lockup has no maskable safe-zone. Refine later
  if a dedicated icon-only mark is produced.)* Files: `apps/web/public/apple-touch-icon.png`,
  `apps/web/public/icon-512.png`, `apps/web/public/site.webmanifest`, `apps/web/src/layouts/Layout.astro`.
- [x] W219 — **Complete the Twitter/X card** (`twitter:title/description/image`) + `og:image:alt/type`.
  Files: `apps/web/src/layouts/Layout.astro`.
- [x] W220 — **Reserve count-up width to prevent micro-CLS** during the number animation. Files:
  `apps/web/src/styles/v2.css`, `apps/web/src/lib/countup.ts`.
- [x] W221 — **Add `prefers-contrast: more` / `forced-colors` handling** for the faint "lune"
  inks and brass glow. Files: `apps/web/src/styles/global.css`.

---

## NEEDS YOUR INPUT — ungated; each waits on something only you can give (with my recommendation)

**Auto-gating is OFF (2026-06-21).** A web run no longer skips a task for being a new dep, an
architecture change, or a taste call — it builds and NOTES it. What remains here genuinely needs
**you**: a real-world data drop, a Cloudflare dashboard secret, or a taste/business call.

- **WG1 — Promote a `/preview/*` tool to the live public site.** A taste + business decision (which
  tool, when, how it links into the funnel). **MY RECOMMENDATION: promote `toiture-3d-pro-11`** — the
  most-refined 3D roof-trace tool and the strongest top-of-funnel hook ("trace your roof → see your
  potential → get a quote"). It needs two manual founder steps first: set **`PUBLIC_MAPTILER_KEY`** in
  the Cloudflare dashboard (else tiles 404 in prod) and **approve a privacy line** for home-location
  data. Then a web run wires it in and flips off `noindex` for that one page. Promote one polished
  tool, not the whole lab. Effort M.
- **WG2 — Délégataire exact tariff grids** (Lydec/Casablanca, Redal/Rabat, Amendis/Tanger). The régie
  barème half is RESOLVED (W11). **MY RECOMMENDATION: KEEP GATED — pure data gate, do NOT guess.**
  Wrong tariffs would make the public ROI estimator lie in the three biggest urban markets. **Provide
  one recent bill per city** (a photo) and it becomes a small transcription task (S) into the W11
  model. Until then the ONEE/régie fallback is the honest default.
- **WG3 — A new paid API or npm dependency** beyond PVGIS / what `apps/web` ships. No longer a blanket
  gate: a web run MAY add a needed dependency and NOTE it in the DONE LOG. Only a **paid** API/account
  (a cost you must approve) or a **new Cloudflare secret** still waits on you. **MY RECOMMENDATION:
  keep the site dependency-light; approve paid APIs case by case.**
- **W187 — 6 manufacturer logo SVGs** (Canadian Solar, JA Solar, Jinko, Deye, Dyness, Nexans). Blocked
  by network egress (only npm is reachable; the open web returns 403), not by a decision. **MY
  RECOMMENDATION: drop a zip of the 6 official monochrome SVGs** (from each brand's media kit — correct
  colours + license-clean, better than random web logos). Wiring them into `public/brands/` +
  `brands.ts` is then trivial (S). The text word-mark fallback is fine meanwhile — low urgency.

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
- 2026-06-21 — W218: shipped the favicon/app-icon set from the founder's official TAQINOR logo
  pack (staged under `apps/web/public/brand/`) — real brand lockup as apple-touch (256px) +
  icon-512, a `site.webmanifest` (name/theme `#070b1d`/bg + 256/512 icons), and the apple-touch +
  manifest head links; kept the lightweight square sun `favicon.svg` for the tiny browser tab.
- 2026-06-21 — W153: shipped the founder portrait. Founder zipped the photo (`DSC_0612.JPG`); used a
  one-off `sharp` pass to generate 4:5 face-framed AVIF+WebP derivatives (640/480) into
  `public/photos/fondateur-portrait-*`, wired `FOUNDER_PHOTO='fondateur-portrait'`, and logged
  provenance in `process-photos.mjs`. The accueil "Le fondateur" section now shows the real face.
- 2026-06-21 — W187 still BLOCKED: tried to source the manufacturer logos from the web, but the
  environment's network egress is allowlisted (only npm reachable; the open web returns 403). Only
  Huawei is obtainable (npm `simple-icons`); the 6 solar brands are in no reachable set. Needs the
  founder's 6 official SVGs (zip) or a widened egress allowlist. NOTE: no new external/paid dep added.
- 2026-06-20 — W75: pro-11 address `geocode` now takes a module-scoped `geoToken` (ignores stale
  responses) + an `AbortController` (aborts the previous request) and the search-form submit is
  debounced ~300 ms (mirroring the bill debounce) — rapid Enter presses resolve only to the last
  query, no stray flyTo.
- 2026-06-20 — W70: pro-11 now disposes the orphaned `roofTex` before reassigning it on re-trace
  (guarded so it never frees the texture still on `deckMaterial.map`), and a new `customLayer.onRemove`
  frees the `WebGLRenderer`, `panelTex`, `roofTex`, and the scene (`disposeScene`) on teardown —
  repeated trace/clear cycles no longer leak textures and client-nav frees the renderer.
- 2026-06-20 — W76: added pure `isSimplePolygon(ring)` to `roof.ts` (proper segment-intersection
  test, ring treated closed) + unit tests (convex/concave-simple true, bow-tie false); wired into
  pro-11 `addVertex` (rejects a crossing point) and `close()` (refuses a self-intersecting ring)
  with clear French status — a bow-tie trace is now refused, never computed.- 2026-06-20 — REFACTOR (founder-requested foundation): split the 4284-line monolith
  `src/scripts/roof-tool-pro11.ts` into a 1876-line orchestration entry + 16 focused modules under
  `src/scripts/roofPro11/` (constants, dom, panelTexture, types, context [shared `ctx` state bridge],
  graphs, prefill, zones, consumption, prodWindow, matrix, layoutEditor, obstaclesUi, mapDraw, scene3d,
  optimizer). Behavior byte-identical (2262 tests + typecheck + build green at every commit); the page
  still imports `initRoofToolPro8`. The Three.js/MapLibre isolation guards now allow the whole
  `src/scripts/roofPro11/**` prefix. This makes every W71–W97 fix localized to one module so the lanes
  finally run in parallel.
- 2026-06-20 — W71: hoisted the shared panel/glass/frame/rack/ballast materials + static geometries out of the per-render path in `scene3d.ts` (cached active+dim variants), killing per-drag MeshPhysicalMaterial shader recompiles; disposeScene frees only per-zone meshes, the cache frees on teardown.
- 2026-06-20 — W72: the needed-panel cap now uses the SAME PVGIS yield as production (optional `perPanelYieldOverride` on `neededPanelsForTarget`, aspect-aware `optimalSouthTiltDeg`); coverage % for the auto-optimum no longer drifts from the displayed yield.
- 2026-06-20 — W73: `recomputeMatrix` is fed the same PVGIS-backed `yieldFn` as the live solve, so the badged matrix optimum and the recommendation card agree once PVGIS resolves (table-fallback internally consistent).
- 2026-06-20 — W74: V7/V8 expose a `noViableConfig`/`northFacing` flag and the optimizer renders an honest French "configuration non viable / pan orienté nord" instead of a fabricated 0-panel winner.
- 2026-06-20 — W77: touch tracing parity — double-tap (touchend ~300 ms) finishes the trace, and a pending single-tap vertex is flushed before the next tap so fast tracing never drops a corner; desktop click/dblclick unchanged.
- 2026-06-20 — W78: a counted zone with 0 placed panels is now drawn as a bare ring in the 3D multi-zone view (no longer skipped), so totals and the 3D view always agree.
- 2026-06-20 — W79: with the layout editor open, any recompute re-enters custom layout — occupied panels are re-snapped to the nearest valid cells of the new lattice and the readouts stay live (no silent wipe to the optimum).
- 2026-06-20 — W80: panels can be dragged to a valid cell on touch in the 3D view (touchstart/move/end mirror of the mouse path, single-finger, dedicated `LAYOUT_GRAB_PX`).
- 2026-06-20 — W81: obstacle length/width inputs clamp on `change`/`blur` (commit) instead of every keystroke, so typing "0." / "0,7" no longer snaps to 0,5 mid-keystroke; commit-time `clampDim` preserved.
- 2026-06-20 — W82: annual self-consumption/savings/battery integrate over the 12 real monthly typical-day profiles (bill-capped), so flipping the production month toggle no longer changes annual savings.
- 2026-06-20 — W83: sizing is reversible (re-derives `max(billNeeded, consNeeded)` each render so removing an appliance shrinks the system); "Recaler" preserves "en plus" energy and a new "Réinitialiser la courbe" restores the computed shape.
- 2026-06-20 — W84: AC/EV appliance slots use the entered hours (`slotEndHour`) instead of hardcoded windows, and battery sizing uses the 12-month evening deficit so the count is stable across the month toggle.
- 2026-06-20 — W85: the diagnostic prefill derives `lf-orient` from the winning config (flat family / pitched facing azimuth → nearest ORIENTATIONS id), no longer hardcoded 'sud'; preview still never posts a lead.
- 2026-06-20 — W86: the preview CTA is honestly labelled "Continuer vers le diagnostic →" (no fake WhatsApp action), and the recommendation/production/zone-total readouts gained `aria-live="polite"`.
- 2026-06-20 — W87: the 3D sun is driven by a real solar position (`sunDirection(lat, day, hour)`) with a time-of-day/season control; the default winter-noon view proves the spaced rows clear at the design elevation.
- 2026-06-20 — W88: panels are pickable in 3D (instanceColor + raycast) — hover highlights, click/long-press removes that specific panel via the lattice and recomputes the figures (layout mode only).
- 2026-06-20 — W89: WebGL context-loss/restore handlers rebuild the renderer on the fresh context so backgrounding a mobile tab no longer permanently blanks the 3D.
- 2026-06-20 — W90: pitched roofs get triangular gable end-walls so they read as a closed volume instead of a tilted lid floating over a flat box; flat mode unchanged.
- 2026-06-20 — W91: added MapLibre's native GeolocateControl (no new dep) — "ma position" recenters to zoom 19.
- 2026-06-20 — W92: trace corners are editable (drag a vertex → re-solve, mouse + touch) and an "Annuler le dernier point" control pops the last vertex during tracing.
- 2026-06-20 — W93: address search is an autocomplete combobox (up to 5 Morocco suggestions, keyboard-navigable, flies only on selection); the W75 race-guard is preserved.
- 2026-06-20 — W94: honest brain numbers — a 25-year degradation band (0,5 %/yr), a DC:AC inverter clip that only lowers over-dense E-W arrays (south unchanged), and bifacial gain from the BIFACIAL_GAIN_* constants instead of a magic 5 %.
- 2026-06-20 — W95: a summer/winter consumption split feeds the 12-month integral and a per-month autoconsommation mini-chart (zero-CLS) renders.
- 2026-06-20 — W96: an indicative battery payback range shows next to the recommended count (labelled "estimation indicative, pas un devis", capped to honest avoided cost; hidden when there's no honest saving).
- 2026-06-20 — W97: added runtime/integration coverage (prefill-via-CTA + no-lead-POST, multi-zone totals, graceful degradation, rendered savings ≤ bill ceiling, layout-edit recompute, obstacle clearance) plus an end-to-end "parcours utilisateur complet" test driving the whole session; full suite 69 files / 2397 tests green.
- 2026-06-21 — W98: structured data verified already-present — homepage carries valid LocalBusiness
  JSON-LD via Layout (real NAP, areaServed = the 5 service cities, no fabricated geo/openingHours/sameAs);
  service pages carry Service + BreadcrumbList; /faq stays the sole FAQPage owner (financement left
  breadcrumb-only on purpose — it disclaims being a lender, so a Service entry would be invented).
- 2026-06-21 — W99: per-page head hygiene verified already-present — unique titles/descriptions, a
  self-referencing canonical, and a full OG/Twitter set (real /og/*.png) are centralised in Layout.astro;
  every ogSlug maps to a real asset.
- 2026-06-21 — W100: sitemap completeness verified already-present — the astro.config.mjs filter excludes
  /preview/ (and the work-page patterns); every public page is included and toiture-3d-pro-* never enters
  the sitemap or nav.
- 2026-06-21 — W101: robots.txt now adds `Disallow: /preview/` (defense-in-depth alongside noindex) while
  keeping `User-agent: *`, `Allow: /`, and the Sitemap line — the only genuine SEO gap found.
- 2026-06-21 — W102: locale verified already-present — LOCALE_BCP47.fr === 'fr' → `<html lang="fr">`
  site-wide; hreflang/Arabic left parked.
- 2026-06-21 — W103: images & headings verified already-present — Picture.astro makes alt a required prop,
  exactly one h1 per public page, only decorative hero posters carry alt="" (correct); no changes needed.
- 2026-06-21 — W104: added tests/seoInvariantsW104.test.ts — asserts /preview/toiture-3d-pro-11 is excluded
  by the sitemap filter, the homepage carries LocalBusiness JSON-LD, and Layout has exactly one
  self-referencing canonical.
- 2026-06-21 — W105: new pure src/lib/roofAdjacency.ts (zero deps) infers a coherent facingAzimuthDeg for a
  newly-traced pitched zone from the shared edge with a neighbour (gable → opposite/normal-to-ridge,
  mono-pente → copies the neighbour, disjoint → connected:false + south fallback) + 21 unit tests.
- 2026-06-21 — W106: a pitched zone closing adjacent to an existing pan now auto-infers its facing via
  roofAdjacency (inferZoneFacingAmong) instead of defaulting to 180; the "Face du pan" buttons + fine
  azimuth stay a per-zone manual override that wins (persisted as facingManual in the area record), with a
  note showing auto-inferred vs hand-set.
- 2026-06-21 — W107: connected pitched pans now meet at a common ridge in 3D — a pure computeRidgeLifts
  groups adjacent pans (union-find on the shared edge) and lifts each pan so the shared ridge edges coincide
  at the group's ridge height (eaves stay on the building); isolated/flat zones byte-identical (lift 0).
- 2026-06-21 — W108: optional overhangM on both packers (packConfig/packCells in estimatorBrainV2,
  packFlushPlane/packFlushCells in estimatorBrainV3) — a panel may cantilever up to overhangM past the edge
  (rails on-roof) via a signed boundary distance; lattice phase preserved so overhangM=0 is byte-identical;
  honesty bound widened by the Minkowski overhang ring (new pure roof.geodesicPerimeterM) + unit tests.
- 2026-06-21 — W109: a "Débord panneaux autorisé (m)" input (step="any", default 0) threads overhangM
  through the whole solve (V7 solveLive, V6 matrix, V8 solveLivePitched → packConfig/packFlushPlane, added
  to every pack cache key) and the 3D render; overhang grows only geometric capacity — the bill-derived cap
  and savings ceiling are unchanged (placedCount = min(need, fit)).
- 2026-06-21 — W110: the pro-11 preview is now one top-down flow — the shared DiagnosticFormEnriched was
  relocated up under the result/CTA block and the separate lower section removed; prefillLead also writes
  lf-name/lf-phone/lf-city (city falls back to the geocoded address, never overwriting a typed value). The
  shared component and the live lead/webhook/CAPI flow are byte-for-byte unchanged; the preview still posts
  NO lead.
- 2026-06-21 — W111: added tests/multiZoneFacingW106.test.ts, tests/overhangSolveW109.test.ts,
  tests/contactPrefillW110.test.ts and extended the pro-11 runtime test (contact prefill + re-asserted
  no-lead-POST guard); full apps/web suite 76 files / 2480 tests green.

- 2026-06-21 — W140: targeted research pass locked the residual figures in CONTENT_SEO_NOTES.md (201–300 kWh tranche ≈1,18 DH, BT VAT resolved as TTC-stable, distributors confirmed = ONEE grid proxy, live wallbox ~12–25k / battery ~2,7–3,8k DH/kWh ranges), date-stamped the volatile figures (fuel/tariffs) 2026-06-21, EV-prime correction kept intact — no founder ask.
- 2026-06-21 — W119: /faq expanded to 24 grouped questions (solar night/clouds, heat/winter, orientation, shade, cleaning, degradation, mono/poly, outage, EV charging ×2, LFP lifespan) — still exactly one FAQPage aligned to the rendered list, no fabricated figure.
- 2026-06-21 — W120: new EV-charging-with-solar pillar page /recharge-voiture-electrique-solaire (Service+BreadcrumbList JSON-LD, one canonical, Faq schema=false, EV economics as labelled ranges, no EV-prime), tied to the loi 82-21 self-consumption angle.
- 2026-06-21 — W121–W128: eight new evergreen guides (sizing, on/off-grid/hybride, orientation/ombrage, entretien/durée de vie, mono/poly+onduleurs, batterie LFP vs GEL/NMC, taille de batterie, électricité pendant les coupures) — all method/general-fact, Article JSON-LD, one canonical, FR voice mirroring the existing guide template.
- 2026-06-21 — W129: /guides hub regrouped into Solaire / Batteries / Voiture électrique with all new guides + the EV pillar, CollectionPage hasPart updated; one contextual EV link added to /nos-solutions.
- 2026-06-21 — W130: /batteries-stockage enriched with a question-led visual-FAQ block (Faq schema=false → no 2nd FAQPage) + links to the new battery guides and /garanties; lead form untouched.
- 2026-06-21 — W132: dependency-free blog shipped — core Astro content collection (glob+Zod), /blog index + /blog/[slug] (BlogPosting+BreadcrumbList, one canonical), hand-rolled /rss.xml (RSS 2.0, drafts excluded), RSS <link> in Layout, Blog entry in the Ressources nav, one seed post.
- 2026-06-21 — W133–W138: six dated, cited blog posts (coût 2026, rentabilité par ville, loi 82-21, recharge VE coût, batterie stocker-ou-revendre, gamme Dyness/Deye vs Huawei) — every figure a labelled/dated « fourchette indicative » sourced from CONTENT_SEO_NOTES.md.
- 2026-06-21 — W131: content-expansion invariant tests (single FAQPage, one canonical per new page, Article/Service+Breadcrumb JSON-LD, new routes in sitemap / preview excluded, volatile figures labelled).
- 2026-06-21 — W139: blog invariant tests (collection schema, frontmatter validity, RSS 2.0 + draft exclusion via a draft fixture, BlogPosting+BreadcrumbList, one canonical, /blog in sitemap) — verified the draft fixture is absent from build/sitemap/RSS.
- 2026-06-21 — W146: self-hosted all 7 datasheet PDFs under /fiches/<slug>.pdf (browser-UA fetch; Jinko datasheet located + recompressed to 1,3 MB), manifest pdf fields flipped, fiches.test.ts asserts every hosted PDF exists on disk.
- 2026-06-21 — W147: /produits/<slug> now embeds the self-hosted datasheet inline (lazy iframe on desktop, clean download fallback on mobile, height reserved → zero CLS), guarded by fiche.pdf; fiches.test.ts covers the embed-vs-fallback branch.
- 2026-06-21 — W112–W118 BLOCKED: the devis-pipeline web halves depend on unbuilt backend endpoints (PLAN2 Group Q1–Q7); skipped per STANDING RULES and listed in GATED-style note above.
- 2026-06-21 — W152: Footer redesign — brand block (logo + tagline) + phone & WhatsApp CTA buttons (real NAP/WHATSAPP_LEADS constants, no invented number), brass gradient hairline top seam, clearer column hierarchy; reduced-motion safe.
- 2026-06-21 — W160: Article 33 ribbon refined to a premium announcement — translucent brass badge with ring, small solar icon, subtle azur-tinted background, brass top hairline; message/link/i18n unchanged.
- 2026-06-21 — W166: Breadcrumb separator switched from literal "/" to an aria-hidden inline chevron SVG that flips under [dir="rtl"] for Arabic.
- 2026-06-21 — W167: LanguageSwitcher given a globe icon, ≥44px tap targets, per-locale aria-labels; links/behaviour unchanged.
- 2026-06-21 — W168: Logo sun-mark gains a static brass glow (+ reduced-motion-gated pulse); ZelligeDivider motif enlarged 18→28px with raised opacity/stroke and longer flanking rules.
- 2026-06-21 — W170: produits/index, produits/[slug], politique-de-confidentialite, mentions-legales brought onto the v2-page-title scale + V2Enhance engine (matching nos-solutions pattern); W147 datasheet embed preserved, lead form untouched.
- 2026-06-21 — W157+W203: .cine-card lifted (stronger glass, top-edge highlight, brass hover lift) + .cine-card-link modifier; reduced-motion gated.
- 2026-06-21 — W206: .cine-in-1..4 + .cine-in-d stagger utilities (replacing inline animation-delay magic numbers); delays reset to 0 under reduced-motion.
- 2026-06-21 — W173: .section / .section-lg / .section-tight vertical-rhythm utilities (clamp-based).
- 2026-06-21 — W174: .btn-pill outline-pill link button + .shadow-premium drop-shadow utilities.
- 2026-06-21 — W169: figure size tokens .fig-xl/.fig-lg/.fig-md (fluid clamp on .fig) + .v2-body body rank.
- 2026-06-21 — W172: .hero-scrim layered radial+linear scrim utility + --hero-scrim-strength custom property.
- 2026-06-21 — W175: .eyebrow-light canonical light-section eyebrow (single accent), composes with .tech-label.
- 2026-06-21 — W192: estimator chips → true segmented control (clear brass active state + focus-visible) and branded .rp9-range sliders; math/values/prefill untouched, step="any" kept.
- 2026-06-21 — W193: WhatsAppMock realism — online dot, read double-ticks, bubble tails + WhatsApp radii, date separator; decorative only.
- 2026-06-21 — W212: équipement comparison grid given a middle breakpoint (1 col <lg, 2 cols ≥lg) across fr/en/ar twins; content unchanged.
- 2026-06-21 — W171: extracted PhotoCaption.astro scrim component; replaced duplicated inline caption scrims on realisations pages.
- 2026-06-21 — W178: accessible dependency-free lightbox (ESC/arrows/focus-trap/aria) on realisations index gallery + case-study photos.
- 2026-06-21 — W179: standardized hover-zoom to 1.04 across VideoChantier poster + realisations photo cards; reduced-motion gated.
- 2026-06-21 — W181: Picture.astro gains optional position/objectPosition prop (default unchanged); realisations data carries optional objectPosition + phase fields.
- 2026-06-21 — W182: VideoChantier styled (brass frame + glow, poster, explicit dims, preload=none, reserved aspect-ratio → zero CLS).
- 2026-06-21 — W183: brand-logo row optical-size normalization (per-brand heightMultiplier) + grayscale→colour hover; brands.test.ts updated.
- 2026-06-21 — W184: before/during/after phased "chantier en phases" section on realisations/[slug] (phase field in data; graceful when absent).
- 2026-06-21 — W185 NOT DONE (deferred): needs Layout.astro to accept a per-page og:image prop — handled in the CORE Layout slice.
- 2026-06-21 — W195: new src/styles/prose.css shared article style (.prose + .prose-lead body-vs-lead rank, h2/h3 scroll-margin) applied to guides + blog; global.css untouched.
- 2026-06-21 — W196: long-form measure constrained to max-w-[68ch] (~65–70ch) across all 11 guides + blog.
- 2026-06-21 — W197: src/lib/readingTime.ts (reading-time + auto-TOC from headings); blog article shows reading-time badge + TOC (≥3 headings) with sticky-header anchor offset.
- 2026-06-21 — W198: optional cover field in content schema; graceful cover figure on blog articles; hover lift on guides/blog index cards (reduced-motion gated).
- 2026-06-21 — W199: reusable Callout / PullQuote / KeyFigure prose components (accessible), wired into a guide as example.
- 2026-06-21 — W200: RelatedLinks component replacing duplicated internal-link chip rows across 11 guides + blog; branded list/table styling + mobile reflow in prose.css; 73 new tests (proseW195to200).
- 2026-06-21 — W202: html scroll-padding-top (clamp 4–5.5rem) so sticky-header anchors land below the header.
- 2026-06-21 — W209: global :focus-visible brass ring on a/button/[role=button]/inputs/select/textarea/summary (overridable).
- 2026-06-21 — W217: color-scheme: dark globally (native controls/scrollbars) + brass ::selection.
- 2026-06-21 — W221: prefers-contrast: more remaps faint inks + kills .lum glow; forced-colors neutralizes decorative shadows and defers to system colors.
- 2026-06-21 — W207: removed dead .reveal/.emerge scroll-timeline CSS (zero usages confirmed by grep), left a note.
- 2026-06-21 — W177: STYLE.md §7 design-system tokens/utilities doc + tests/styleTokens.test.ts (39 assertions guarding token/utility presence; +dead-class-stays-removed).
- 2026-06-21 — W150: scroll-reactive header (transparent over hero → solid+blur+condensed+logo step-down past 80px via rAF), zero CLS (sticky, chrome-only), reduced-motion safe.
- 2026-06-21 — W151: active desktop-nav indicator (brass underline + aria-current) computed from rootPath, incl. dropdown sub-pages.
- 2026-06-21 — W163: dropdown chevrons rotate on open; panels polished (rounded, layered shadow, brass top accent).
- 2026-06-21 — W164: mobile menu animated grid-rows panel, emoji 📞 → inline phone SVG, LanguageSwitcher moved inside, scrollable (max-h/overscroll-contain).
- 2026-06-21 — W165: StickyCta pill restyled to brass/night + .glow + env(safe-area-inset-bottom); WhatsApp deeplink byte-identical.
- 2026-06-21 — W210: signature .glow propagated to header/mobile/CtaBand/StickyCta primary CTAs; all hrefs unchanged.
- 2026-06-21 — W176: DiagnosticForm/Faq/CtaBand section headings aligned to v2-section-title.
- 2026-06-21 — W188: form inputs ≥16px (no iOS zoom) + ~44px tap targets + larger consent checkbox hit-area; field names/required untouched.
- 2026-06-21 — W189: multi-step progress bar — 8px brass fill on subtle track, role=progressbar + aria-valuenow.
- 2026-06-21 — W190: estimate result card elevated (cine-card+glow, brass seam, .fig/.fig-lg/.lum value vs .tech-label); computed numbers + deeplink unchanged.
- 2026-06-21 — W191: submitting spinner + aria-busy + reduced-motion-safe result fade-in; shared @keyframes spin/.spinner in global.css; submit/fetch/threshold logic unchanged.
- 2026-06-21 — W194: stronger error/validation styling (aria-invalid highlight), higher placeholder contrast, visible focus rings; validation logic unchanged.
- 2026-06-21 — W148: restored the dark→light "salle blanche" climax — .seam-lumiere + .diag-lumiere lifted card around the diagnostic; form mechanics untouched.
- 2026-06-21 — W149: hero CTA shortened to "Estimer mon installation →" with a stronger .glow-hero halo + larger size; href unchanged.
- 2026-06-21 — W154: hero scrim switched to the canonical layered .hero-scrim.
- 2026-06-21 — W156: trust-band four-up figures unified to monumental .fig .fig-lg .lum + .tech-label labels.
- 2026-06-21 — W158: hard border hairlines replaced with .seam-soft gradient transitions on homepage seams.
- 2026-06-21 — W159: varied the repeated eyebrow treatment (section-index prefixes / plain label variants).
- 2026-06-21 — W161: hero scroll-affordance chevron (bounce gated to no-preference, static under reduced-motion).
- 2026-06-21 — W162: warmed the "L'argument en chiffres" stat column with a faint brass radial backing.
- 2026-06-21 — W205: first above-the-fold figure now count-ups (existing countup.ts, width locked → zero CLS, final value instantly under reduced-motion).
- 2026-06-21 — W216: "Aller au contenu" skip link (focus-revealed, brass) + id="main" on <main>; position:fixed → zero CLS.
- 2026-06-21 — W219: completed Twitter card (title/description/image) + og:image:type/og:image:alt; values reuse existing meta, nothing invented.
- 2026-06-21 — W185: Layout gains optional ogImage/ogImageAlt props; realisations/[slug] passes each case's real hero webp + French alt as its per-case OG/Twitter image.
- 2026-06-21 — W215: preload archivo-latin.woff2 for the LCP <h1> + metric-matched Archivo/Hanken size-adjust fallbacks to cut font-swap CLS.
- 2026-06-21 — W220: count-up width reserved (tabular-nums + min-width + exported reserveWidth() lock) to prevent micro-CLS.
- 2026-06-21 — W155: portrait-orientation hero source/crop for tall phones (Picture portraitPosition prop; homepage + realisation heroes); existing callers unchanged.
- 2026-06-21 — W180: corrected mismatched declared aspect-ratios vs actual crops (homepage feature + realisations/city cards) for accurate anti-CLS height.
- 2026-06-21 — W204: reduced-motion-safe hover arrow nudge on gallery/CTA "→" links (index, nos-solutions, realisations index).
- 2026-06-21 — W211: removed whitespace-nowrap from wide figures (kWc/%/years) on homepage + city + realisation pages (+ en/ar twins) → no 320px overflow.
- 2026-06-21 — W201: documented 3 sanctioned hero archetypes (top-of-file note) and kept installation-solaire-[city] on archetype B.
- 2026-06-21 — W208: reduced-motion-gated slow shimmer on .seam-lumiere (RTL-aware) + subtle brand-logo lift and testimonial-card hover.
- 2026-06-21 — W186: subtle .photo-grade duotone utility in v3-photo-motion.css for non-hero photos (hero/LCP excluded; opt-in, documented).
- 2026-06-21 — W214: comprehensive [dir="rtl"] block in global.css (tech-label tracking off, logical-property border/padding flips, rule-brass reorder, blockquote, grids, shimmer direction) + one scoped ar timeline fix.
- 2026-06-21 — W213: RTL-mirrored 88 directional → arrows across 22 ar/* pages (Tailwind rtl:-scale-x-100 wrapper); non-directional/comment arrows left alone; text/hrefs unchanged.
- 2026-06-21 — W187 BLOCKED: 6 of 7 third-party manufacturer brand SVGs unobtainable (network egress allowlist blocks the open web; only Huawei in a reachable npm set). Needs founder to drop the 6 official monochrome SVGs or widen the allowlist. Moved to GATED.
