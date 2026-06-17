# Taqinor WEB — Build Plan & Progress (site public + previews `apps/web`)

This file is the **single source of truth** for the public website (`apps/web`, the
**Astro** marketing site) and its **private preview lab** (`/preview/*`), and the
**memory between Claude Code sessions** for that work. It is the web-side twin of
[`docs/PLAN.md`](PLAN.md) — which stays **OS-only** (the React OS app + Django/FastAPI
backend) and explicitly excludes `apps/web`. Anything touching the Astro site or a
`/preview/*` route is planned here, not there.

Each session does **exactly one task**, ticks it off *in this file*, commits, lets the
push deploy itself, and stops. The next session reads this file and continues. Nothing
relies on the agent's own memory — the file on disk is the memory.

---

## HOW TO RUN (read this every session)

1. **Read this whole file.**
2. In **BUILD QUEUE** below, find the **first task marked `[ ]`** (not `[x]`, not
   `[SKIP]`, not `[BLOCKED]`). Ignore the GATED and MANUAL sections entirely.
3. **Verify it isn't already built.** Inspect the actual repo and the deployed preview.
   If the task already exists and works, mark it `[x] (already present)`, add a line to
   the DONE LOG, commit this file, and move on to the next `[ ]` task — repeat this verify
   step.
4. **Build only that one task, completely, with tests.** Obey every STANDING RULE below.
5. **CI must pass** (lint, the `apps/web` vitest suite, the preview/privacy guards). When
   green: self-merge `dev` → `main` (merge commit, history preserved).
6. **Deploy is automatic.** The public site **auto-deploys via Cloudflare Workers Builds
   on every push/merge to `main`** — that IS the deploy. **You never run `wrangler deploy`,
   and you never ask for a Cloudflare API token** (the old one is dead and deleted). Worker
   secrets and Cloudflare dashboard variables (e.g. `PUBLIC_MAPTILER_KEY`,
   `LEAD_WEBHOOK_URL`, `LEAD_WEBHOOK_SECRET`) are **dashboard-only** — changing one is a
   manual step for the founder; list it under MANUAL, never block on it silently.
7. **Update this file on `main`:** flip the task to `[x]`, append one plain-language line
   (with today's date) to the DONE LOG, and commit.
8. **STOP and report** in plain language only — no diffs, no commit hashes: which task, what
   changed, the exact private preview URL to open, and what (if anything) the founder must
   set in the Cloudflare dashboard. **Do not start the next task.** One task per session.
9. **If a task hits a blocker** (it would need a paid/external dependency that isn't
   pre-approved, a new Cloudflare secret the founder hasn't set, or a real taste/promotion
   decision): do **not** guess and do **not** stall. Mark it `[BLOCKED: <one-line reason>]`,
   move it to GATED, pick the **next** `[ ]` task instead, and note the block in your report.

**Run from anywhere — web or phone.** Because `main` auto-deploys itself through Cloudflare,
a task can be run from Claude Code on the web or the phone with no PC involved.

---

## STANDING RULES (every web task obeys these)

- **One session = one task, one self-merged PR.** Many subagents inside the session are
  fine; multiple sessions or multiple PRs are not.
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

### W1 — Estimator-brain v2: real azimuth, per-config PVGIS, recommended badges, multi-obstacle, margin toggle — [x]

Build this as the **next brain session** on a **new private preview route cloned from the
latest existing preview** — **`toiture-3d-pro-3` today, or `toiture-3d-pro-4` if the
already-queued overnight brain session has shipped** — named as the next
`/preview/toiture-3d-pro-N`, **leaving the prior route untouched as the baseline**.

These improvements **extend and must compose cleanly with the already-queued brain work**
(tilt optimization, independent options, engine tightening). **If that queued work has not
run yet, build it in the same session** so the two compose rather than collide. First read the
latest brain (`estimatorBrain.ts`) and obstacle (`obstacles.ts`) code and **extend only what
is missing — do not rebuild** parts that already exist.

**Do:**

1. **Real roof-aligned array orientation — an actual azimuth variable**, not just snap-to-
   true-south or true-east-west. When a roof sits a few degrees off south, let the layout
   **follow the roof's real edges** so it can fit more panels, and **compute the off-south
   production precisely** (per-panel yield drops as azimuth moves off the optimum). Compare
   configurations on **total kWh and how well they match the needed power** — **not on panel
   count**.
   - **Sweep azimuth toward roof-aligned only when** the standard south, low-tilt, or
     east-west configs **cannot meet the need** on a roof-limited roof, **or when** doing so
     **raises total roof energy**.
   - **Keep true south** when the roof already meets the need at south **within the
     needed-panel cap**.

2. **Use PVGIS irradiance for the roof's actual GPS position** to compute production for
   **each candidate layout (orientation, azimuth, tilt)** and compare them on **real
   per-config irradiance**, not a generic factor — this is what makes the off-south numbers
   honest. Keep PVGIS querying **fast** (cache per location, query only the configs that
   matter, reuse results across toggles) and **degrade gracefully** if PVGIS is unreachable.
   PVGIS is already in the stack — **not a new dependency**.

3. **"Recommandé" badge on the recommended choice in every option group** — orientation,
   layout (portrait / paysage), tilt, azimuth, and the margin toggle below — **genuinely
   calculated** and **staying correct regardless of what the user has currently selected**.
   Even when the user picks a non-recommended option, the brain still computes and **displays
   which option is recommended in each group**, so the user can see they chose one option but
   another is recommended.

4. **Support more than one rooftop obstacle at once**, each showing its **real size
   (length × width) clearly on both the 2D map and the 3D box**. First check what already
   exists (obstacle boxes and on-box size labels were added in earlier sessions) and **extend
   only what is missing instead of rebuilding**, with **panel count, kWc, kWh/an, % of bill,
   and the savings band all updating** as obstacles are added, moved, or resized.

5. **Add a toggle for the roof-edge margin/setback** — keep the margin, or remove it to use
   the **full roof to the edge** — and **compute its recommended setting**:
   - **Recommend KEEPING the margin** whenever the need is **already met with the margin in
     place** (the needed panel count fits, or the needed power is reached).
   - **Recommend REMOVING the margin** to reclaim space **only when the need is NOT met with
     the margin on** (drop the setback to fit more panels and get closer to the target).

**Keep every standing estimator rule throughout** (see STANDING RULES): respect the
needed-panel cap (never overfill a roomy roof — surplus is uncompensated in Morocco); no
invented numbers (every figure traces to PVGIS, confirmed tariff/physics, or sound logic;
savings never exceed avoidable energy cost; impossible counts blocked by the footprint
bound); build private (noindex, not in nav, excluded from the sitemap, unlinked); one
self-merged PR; the **live public site and lead form unchanged**.

**Acceptance:** open the new `/preview/toiture-3d-pro-N` → trace a slightly-off-south roof and
see the array follow the real edges with more panels and an honest per-config PVGIS yield; every
option group shows a calculated "Recommandé" badge that stays correct after the user picks a
different option; two-plus obstacles render with their L×W on both the 2D map and 3D boxes and
all the head numbers update on add/move/resize; the margin toggle works and its recommended
setting flips KEEP↔REMOVE on whether the need is met with the margin on. The prior preview route
is byte-for-byte untouched as the baseline.

---

## GATED — needs the founder's decision before building (agent does NOT auto-build)

- **WG1 — Promote a preview to the live site.** Moving any `/preview/*` tool onto the public
  website is a **taste + business decision** — never an unattended run. The founder decides
  which preview, when, and how it links into the public funnel.
- **WG2 — Harmonize the tariff model.** The brain's selective ONEE grid vs. the legacy site
  `1,4 MAD/kWh` must be reconciled **against a real Lydec/ONEE bill** before either changes.
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
- 2026-06-17 — W1 done: new private `/preview/toiture-3d-pro-5`, built as a clone of the
  overnight autopilot's pro-4 and composing on its `estimatorBrainV2.ts` engine (pro-4 and
  pro-3 left as untouched baselines). Adds real roof-aligned azimuth (rows follow the roof's
  true edges on a rotated roof; off-south yield from real per-config PVGIS, never a flat
  factor), a margin/setback toggle with a computed keep-vs-remove recommendation, "Recommandé"
  badges genuinely calculated for every option group (correct even when the user picks another
  option), multi-obstacle size labels on the 2D map and the 3D box, and per-config live PVGIS
  cached per location with graceful fallback. Engine additions are additive and gated behind an
  opt-in (`enableRoofAligned`) so pro-4 stays byte-identical — proven across 7 roof cases plus a
  regression test. 494 web tests green; site build clean; pro-5 is noindex + sitemap-excluded;
  public site + lead form unchanged. Auto-deployed via Cloudflare on merge to main._
- 2026-06-17 — Plan consolidation: this `WEB_PLAN.md` is now the single canonical web/preview
  plan. The autopilot's thin `docs/PLAN-web.md` / `PLAN-web2.md` (an autopilot shakedown that
  added then removed a homepage marker on 2026-06-16) were folded here and removed; the website
  autopilot commands in `CLAUDE.md` now point at `WEB_PLAN.md` / `WEB_PLAN2.md` / `WEB_PLAN.running`.
