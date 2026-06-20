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
- [ ] **W77 — map: touch tracing parity (double-tap finish + no dropped vertices).** Finish-on-double is
  wired only to MapLibre `dblclick` (desktop); on touch the only finish is the button, and the 240 ms
  single-click delay silently DISCARDS fast-placed corners (the `if (clickTimer) return;` guard). Add a
  `touchend` double-tap-to-finish (~300 ms) and stop dropping the queued vertex when a second tap is
  not a real dblclick. Accept: phone users can finish by double-tap and no corner is lost when tracing
  quickly. File: `roof-tool-pro11.ts`.
- [ ] **W78 — map: multi-zone view/total consistency.** A finished zone with `placedCount===0` is summed
  in the totals but skipped by `appendOtherZones` (`!a.renderPlan`), so it vanishes from the 3D
  multi-zone view — totals and 3D disagree. Capture a `renderPlan` snapshot even at 0 panels, or have
  `appendOtherZones` fall back to drawing the bare ring from `a.vertices`. Accept: every counted zone is
  visible in 3D. File: `roof-tool-pro11.ts`.
- [ ] **W79 — layout: keep the custom layout coherent after obstacle/config edits.** Editing/adding/
  deleting an obstacle (or changing a config axis) while the layout editor is open calls `recalc()`
  which nulls `layoutState` but never re-enters custom layout — the hand-placed panels silently snap to
  the optimum, the panel shows a stale count, and the `+/−` disabled-state and the note go stale. When
  `layoutMode` is on, after any recompute re-enter custom layout (re-snap occupied panels to the nearest
  valid cells of the new lattice via `nearestEmptyCell`) and re-render panel/grid/note. Accept: a custom
  layout survives an obstacle edit (re-snapped, not wiped) and all readouts stay live. File:
  `roof-tool-pro11.ts`.
- [ ] **W80 — layout: touch drag-to-move panels in 3D.** `layoutDrag` is bound only to `mousedown/move/
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
- [ ] **W88 — 3D: panel pick + highlight + per-panel delete in 3D.** Panels are one `InstancedMesh` with
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
- [ ] **W92 — map: editable trace vertices + undo-last-point.** Roof corners are immutable once placed
  (only "Effacer" restarts), unlike the fully-draggable obstacles. Generalize the obstacle-drag
  machinery to the `rp9-pts` source (drag a corner → update `vertices[i]` → `recalc`) and add an
  "Annuler le dernier point" control during tracing. Accept: a placed corner can be dragged and the last
  point undone. File: `roof-tool-pro11.ts`.
- [ ] **W93 — map: address autocomplete.** Geocode is fire-on-submit `limit=1` (one guess, no list).
  Switch to `limit=5`, render a dropdown bound to the address field, and `flyTo` only on selection
  (reuses the same MapTiler endpoint, no new key). Accept: typing shows up to 5 Morocco suggestions;
  selecting one flies there. File: `roof-tool-pro11.ts`.
- [ ] **W94 — brain: 25-year degradation band + DC:AC clip + real bifacial constants.** Savings imply
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

- [ ] **W97 — runtime/integration tests for pro-11.** Add jsdom/vitest coverage the audit found missing:
  `prefillLead` writes `lf-area`/`lf-kwc-est`/`lf-orient` correctly (incl. Est-Ouest/pitched mapping from
  W85) and the preview NEVER calls `fetch`/POSTs a lead; multi-zone totals via `+ Ajouter une zone`
  (wire the `rp9-add-area`/`rp9-areas-*` ids into the test DOM); graceful degradation (no-WebGL →
  `#rp9-fallback`, no-key → `showFallback`, `<noscript>` present); savings never exceed the bill-derived
  ceiling at the RENDERED layer; layout-edit recompute; obstacle-clearance through the mounted script.
  Accept: new tests fail before W70–W86 fixes and pass after. Files: `tests/estimatorRuntimePro10Pro11.test.ts`
  (+ new `tests/*.ts` as needed).

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
