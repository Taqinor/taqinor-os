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

### W67 — English + Arabic versions of the public site (i18n, FR default) — [x]
**Do:** Add Astro's built-in i18n (FR default + EN + AR) — FAITHFUL translations of the EXISTING true
copy (translate, never re-invent a claim; keep loi-82-21 wording and every figure exact), a language
switcher in header + footer, correct `hreflang` + per-locale canonicals + sitemap entries, and **full
RTL** for Arabic (`dir="rtl"`, mirrored layout). No new dependency (Astro i18n is native). The lead form
and its entire data flow stay byte-for-byte unchanged in every locale.
**Done when:** every public page resolves under /en/ and /ar/ with accurate translations, the switcher
works, hreflang + sitemap are correct, Arabic renders RTL without layout breakage, Lighthouse held, the
lead form is unchanged. (Large task — the autopilot may lane/stage it across pages.)
**Decisions (Reda, 2026-06-18):** WHOLE SITE in one build (not staged); the diagnostic lead form's
visible LABELS are translated per language while its payload, endpoint, 1 000 MAD threshold, consent,
WhatsApp deeplink + CAPI stay byte-for-byte identical. Pre-publication translation review waived —
build to a high bar and ship; keep loi-82-21 wording and every figure exact in EN + AR. Executed in
verified non-breaking increments (FR stays byte-identical, suite stays green): foundation first
(config + dictionary + utils + LanguageSwitcher + Layout hreflang/RTL), then page-by-page.

---

### W68 — Task 4 : mode VARIABILITÉ de consommation (« Affiner ma consommation ») — [x]
**Do:** On the SAME current latest private preview route, **in place** (this builds on the
consumption/savings engine and the Année/Mois/Jour graph from the earlier tasks — **read that
engine first and reuse it; do NOT duplicate it**): add a consumption **VARIABILITY** mode the
client can enter to refine the hourly curve, opened from a clear control (**"Affiner ma
consommation"**). It has two ways in, **both feeding the SAME self-consumption + savings + sizing
engine** so the graph, savings, recommended system size and battery sizing all recompute live.
- **(A) Hand-edit:** the 24 hourly values are directly editable both by **dragging bars** AND by
  **numeric entry** (numeric entry is required so it works on a phone and with reduced-motion),
  with a live daily total in kWh and in the site's DH/MAD notation; a choice to **"Recaler sur ma
  facture"** (rescale the edited curve so its daily total matches the bill-derived daily kWh) or
  keep it as a free override.
- **(B) Appliance calculator:** the client adds appliances; each contributes its energy across a
  time-of-day window that reshapes the hourly curve, and each (or the calculator globally) carries
  a choice — **"Sur ma facture actuelle"** (ADD on top of the bill baseline, for an appliance not
  yet reflected in the bill, e.g. a newly bought AC or EV — this **raises** the daily total and
  therefore the recommended system and battery sizing) versus **"Déjà compris dans ma facture"**
  (use the appliance ONLY to reshape the existing hourly distribution while **holding the bill's
  daily total fixed**).
- **Curated appliance list**, each with a documented typical power and a default daily usage and
  time window, **ALL client-editable**, recorded with their sources in a new **`APPLIANCES_NOTES.md`**
  (typical published ranges from standard appliance-wattage references; the client's own nameplate
  always overrides, so nothing is asserted as a fact): **Climatisation** — entered by BTU (presets
  9 000 / 12 000 / 18 000 / 24 000 BTU, each also labelled in chevaux since Moroccan units are sold
  in CV, ≈9 000 BTU = 1 CV, plus a custom field) divided by EER to get watts (default EER ≈ 9 for a
  non-inverter and ≈ 12 for an inverter, both editable; electrical watts = BTU/h ÷ EER), default
  window afternoon-to-evening; **Recharge voiture électrique** — charger power presets
  2,3 / 3,7 / 7,4 / 11 / 22 kW (7,4 kW the common single-phase home wallbox; or custom) times hours
  charged per day, OR an alternative "kilomètres par jour × consommation (~17 kWh/100 km, éditable)",
  with a selectable charging window (nuit / midi solaire / soir) and a visible note that charging in
  the solar window sharply raises self-consumption; **Chauffe-eau électrique (cumulus)** —
  ~1 500–3 000 W, ~2–3 h/jour, morning/evening or off-peak window, with a note that many Moroccan
  homes use a gas (butane) water heater so this is optional; **Pompe de piscine** — ~750–2 000 W,
  4–8 h/jour, midday window; **Four électrique** — ~2 000–2 500 W, ~1 h/jour evening;
  **Plaque/cuisinière électrique ou induction** — ~1 500–3 000 W at meal times (note gas is common);
  **Lave-linge** — ~500 W moyen (~1 kWh/cycle), ~0,5–1 cycle/jour; **Lave-vaisselle** —
  ~1 200–2 400 W (~1–1,5 kWh/cycle) evening; **Sèche-linge** — ~1 800–3 000 W (~2–3 kWh/cycle);
  **Réfrigérateur/congélateur** — ~100–400 W running 24 h as a flat baseload (~1–2 kWh/jour);
  **Chauffage électrique/radiateur** — ~500–2 400 W, winter mornings/evenings; **Pompe à eau/forage**
  — ~750–1 500 W intermittent (villas/rural); **Fer à repasser** — ~1 000–1 800 W; **Micro-ondes** —
  ~600–1 200 W; **Pompe à chaleur (chauffage/refroidissement)** — configurable; **Téléviseur +
  électronique** and **Éclairage LED** — small aggregate baseload; plus a free **"Autre appareil"**
  row (nom + puissance W + heures + créneau).
- All appliance energy still flows through the **existing self-consumption model** (surplus valued
  at zero, savings via the existing billMAD cap — **introduce no new tariff number**), and "on top"
  appliances increase the production/battery sizing target through the existing **size-to-need +
  6 kWh/day-per-battery** logic. **Reduced-motion respected, zero layout shift, mobile-first.**
**Tests:** watts = BTU/h ÷ EER and kWh = W × h ÷ 1000; an appliance's energy distributes across its
window and the hourly sums are correct; "Sur ma facture actuelle" raises the daily total while "Déjà
compris" holds it fixed (reshape only); "Recaler sur ma facture" rescales the hand-edited curve to
the bill total; self-consumption and savings recompute from the modified curve and never exceed the
cap; the curve still sums to the intended daily total. **One self-merged PR.**

### W69 — Task 5 : mode VARIABILITÉ de disposition (« Personnaliser la disposition ») — [x]
**Do:** On the SAME route **in place**: add a layout **VARIABILITY** mode so that **AFTER the
auto-layout finishes**, the client can enter a **"Personnaliser la disposition"** mode and move
panels on the roof realistically, on the existing 3D (flat tilted racks or pitched flush) —
mirroring how professional solar tools (Aurora, HelioScope, OpenSolar, RatedPower, SolarEdge
Designer) do it: drag-and-drop with snap-to-grid, roof keep-outs and setbacks, no overlap, and
automatic recompute. Implement it on the array's own **valid placement LATTICE**: the optimizer's
layout already defines the legal cells (row/column positions that encode the correct winter-solstice
row pitch on a flat roof, and the dense coplanar tiling on a pitched roof), so make movement **SNAP
to that lattice** — the client selects one or more panels (tap to select individual panels, or enter
a count to move a group) and drags; the drag raycasts onto the roof plane and snaps the selection to
the nearest valid EMPTY cells, so **every reachable position is physically valid BY CONSTRUCTION**
(every panel corner inside the traced polygon and inside the edge/ridge/eave setback, no overlap with
other panels or obstacle keep-outs, coplanar with the roof plane on pitched, row pitch preserved on
flat). Invalid targets (off the roof, into the setback, onto an obstacle, onto an occupied cell) are
rejected — snap back or to the nearest valid empty cell, with a hover highlight (**valid = green,
invalid = red**) — so the client can never produce an impossible arrangement, which is exactly what
"real moving" means here. Allow **ADD** a panel (tap an empty valid cell) and **REMOVE** a panel
(select + delete); on any change to the count, recompute nombre de panneaux / kWc / kWh-an /
économies through the **EXISTING PVGIS-by-count path** — moving panels within the same plane leaves
per-panel yield unchanged because tilt/azimuth/GPS are unchanged (**never invent a different yield**),
only the count changes production and savings; the client may go below the recommended count
(production and savings drop honestly) and the tool flags when the layout no longer covers the need.
A **"Réinitialiser la disposition optimale"** control restores the optimizer's layout. The footprint
bound and the needed-panel cap still hold throughout. **Three.js mechanics:** pointer + raycaster
onto the roof plane with snap-to-lattice and a validity check on hover, commit on release; provide a
**tap-to-select-then-tap-target-cell fallback** plus **+/- add/remove controls** so it works on touch
and under reduced-motion without fine dragging. Because the build agent cannot render the 3D, anchor
correctness to code-checkable logic and tests, with the final visual check on the phone.
**Tests:** a snapped move lands only on valid empty cells; off-polygon, setback-violating,
obstacle-overlapping and occupied-cell targets are all rejected; add/remove updates the count and
recomputes production/savings via the existing PVGIS-by-count path with per-panel yield unchanged
when only position changes; reset restores the optimizer layout; the footprint bound and needed-panel
cap still hold. **One self-merged PR.**

**ACROSS W68–W69 (founder's cross-cutting constraints):** every figure traces to **PVGIS, the
existing billMAD, the documented-and-editable appliance typicals** (recorded with sources in
`APPLIANCES_NOTES.md`, always overridable by the client), **the operator battery constants, or sound
physics — no invented numbers and no new tariff figure**; savings never exceed the avoidable energy
cost or the bill; surplus valued at zero; the **needed-panel cap and footprint bound always hold**.
**No new dependencies** (Three.js, PVGIS, MapLibre, Mapbox already in the stack; graphs and controls
are inline SVG/HTML). **Touch only `apps/web`.** All work stays on the **CURRENT latest private
preview route IN PLACE** (noindex, not in nav, excluded from sitemap, unlinked), the
**immediately-prior route left byte-for-byte intact as the baseline**. The **live public site and the
live lead form and its entire data flow** (1 000 MAD threshold, consent, WhatsApp deeplink, webhook,
CAPI) stay **byte-for-byte unchanged**. **Each task is its own self-merged PR to protected main** (the
accepted path — do not flag it). Full Vitest suite green, **Lighthouse held 97–100**, reduced-motion
respected, zero layout shift. **Plain-language report only** (no diffs or hashes): the preview URL;
for Task 4 the variability mode (hand-edit, the appliance calculator and its sourced editable
defaults, and the on-top-vs-already-in-the-bill choice) and how it drives the graph/savings/sizing;
for Task 5 the panel-move mode (drag-snap to valid cells, add/remove, recompute, reset) and
confirmation it can't create an invalid layout; confirmation the live site and lead flow are
untouched; the map env var the route reads; and the one thing to check on the phone — open Affiner ma
consommation, add an AC by BTU and an EV charger and watch the curve and savings move; then enter
Personnaliser la disposition, drag a few panels and try to drop one off the roof (it should refuse),
add and remove one and watch kWc and savings update.

---

---

**ACROSS W2–W10 (founder's cross-cutting constraints):** no invented facts — every figure traces
to what's already published on the site or confirmed repo data; **no new dependencies**; the **live
lead form and its data flow untouched**; these tasks **land in the run's single end-of-batch self-merge — no per-task PR** per the protected-main
convention; **Lighthouse held on every page**; and a plain-language report listing the new public
URLs to click. NOTE: these are **public, indexed** pages (a deliberate exception to the preview-lab
"build everything private / noindex" standing rule for this batch — the founder asked for live
public pages), but the **live lead form and its data flow must stay byte-for-byte unchanged**.

---

---

---

---

**ACROSS W13–W19 (founder's cross-cutting constraints):** no invented facts — every figure traces
to what is already published, confirmed repo data, or public meteo data; **no new dependencies**;
the **live lead form and its entire data flow** (1 000 MAD threshold, consent, WhatsApp deeplink,
webhook, CAPI) **untouched**; the **estimator preview routes stay private** (noindex, not in nav,
excluded from sitemap, unlinked); these tasks **land in the run's single end-of-batch self-merge — no per-task PR** per the protected-main
convention; **Lighthouse held on every page**. Plain-language report listing **every new and
changed public URL to click**, plus confirmation the **live lead flow is untouched**. NOTE: like
W2–W10 these are **public, indexed** pages (the deliberate exception to the preview-lab
"build everything private / noindex" standing rule).

---

---

**ACROSS W20–W21 (founder's cross-cutting constraints):** every figure traces to **PVGIS, confirmed
tariff/physics, or sound logic** — **no invented numbers**, savings never exceed the avoidable energy
cost, impossible panel counts stay blocked by the **footprint bound**; the **needed-panel cap** is
always respected; **no new dependencies** (PVGIS, MapLibre, Mapbox, Three.js are already in the
stack); these tasks **land in the run's single end-of-batch self-merge to protected main — no per-task PR** (the accepted path — don't flag
it); **touch only `apps/web`**; **every new route stays private** (noindex, not in nav, excluded from
sitemap, unlinked); the **live public site and the live lead form and its entire data flow** (1 000
MAD threshold, consent, WhatsApp deeplink, webhook, CAPI) stay **byte-for-byte unchanged**;
**reduced-motion respected and zero layout shift**. **Tests:** full Vitest suite green with **added
tests** for the optimizer picking the true maximum over the sweep, the **PVGIS azimuth-sign
mapping**, **graceful PVGIS fallback**, the **flat-vs-pitched branch**, and **pitched-roof layout
using no inter-row gap while flat-roof spacing is unchanged**; **Lighthouse held**. **Plain-language
report only** (no diffs or hashes): the new preview URLs to click, what changed for flat roofs
(fine-grid optimizer via PVGIS at the exact GPS, true optimum shown as its own row when it isn't a
standard config) and for pitched roofs (the roof-type-first step and the flush coplanar layout),
confirmation the live site and lead flow are untouched, and the one thing to confirm on the phone —
that the pitched-roof 3D shows panels lying flat on the slope and correctly aligned.

---

---

---

**ACROSS W23–W33 (founder's cross-cutting constraints):** this is an **information-architecture and
content pass on the EXISTING site** — **do NOT rebuild pages that already exist** (réalisations,
garanties, pourquoi-taqinor, marocains-du-monde, guides, faq, the 5 city pages, and the segment pages
all already exist — **read the repo and surface/restructure them, never recreate them**). **No invented
facts anywhere:** pompage has no Taqinor installations so **no fabricated pompage projects or figures**;
financing **names no bank partner, quotes no rate, and claims no residential tax exemption**; every
other figure **traces to what is already published or confirmed repo data**. **No new dependencies.
Touch only `apps/web`.** The **live lead form and its entire data flow** (1 000 MAD threshold, consent,
WhatsApp deeplink, webhook, CAPI) stay **byte-for-byte unchanged**. The **private estimator preview
routes stay private** (noindex, not in nav, excluded from sitemap, unlinked). These tasks **land in the
run's single end-of-batch self-merge to protected main** (the accepted path — don't flag it).
**Lighthouse held on every page (97–100), reduced-motion respected, zero layout shift.** **Plain-language
report only** (no diffs or hashes): the new nav and footer exactly as a visitor now sees them,
confirmation the homepage matches the sub-pages, the full list of pages now reachable from the menu,
confirmation the Loi 82-21 explainer is **still live and indexed but out of the top nav** (and where it
is now linked), the **URLs of the new Pompage / Batteries / Maintenance / Financement / Nos solutions
pages**, confirmation the live lead form is untouched, and **the one thing Reda does by hand** (purge
the `/` cache once in Cloudflare).

---

---

---

**ACROSS W34–W35 (founder's cross-cutting constraints):** every figure traces to **PVGIS, confirmed
tariff/physics, or sound logic — no invented numbers**; savings never exceed the avoidable energy cost;
impossible panel counts stay blocked by the **footprint bound** (Σ panel footprints ≤ usable area); the
**needed-panel cap is always respected**. **No new dependencies** (PVGIS, MapLibre, Mapbox, Three.js are
already in the stack). **Touch only `apps/web`.** Every new route stays **private** (noindex, not in nav,
excluded from the sitemap, unlinked) and every prior preview route is left **byte-for-byte intact** as a
baseline. The **live public site and the live lead form and its entire data flow** (1 000 MAD threshold,
consent, WhatsApp deeplink, webhook, CAPI) stay **byte-for-byte unchanged**. The whole W34–W35 batch
lands in the run's **single self-merge to protected main** (the accepted path — don't flag it). **Reduced-motion respected, zero
layout shift, Lighthouse held.** Because the build agent cannot render the map (the map keys live in
Cloudflare), **anchor every claim to code-checkable logic and tests** rather than to how it looks.

**Tests — full Vitest suite green with added tests for:** the flat optimizer returning the true maximum
over the full sweep; locking an axis holds it while only the still-AUTO axes re-optimize; locks accumulate
across successive picks and Réinitialiser clearing all of them; the per-group recommended value equalling
the freed-axis optimum given the other current locks; the PVGIS azimuth-sign mapping (S=0 / E=−90 / W=+90 /
N=180); generation = placed × kWc × PVGIS yield with placed = min(needed, fits) and the cap never exceeded;
graceful PVGIS fallback; and for the pitched route that there is no tilt axis, orientation is fixed to
alignée toit, only the free axes re-optimize, production uses mountingplace="building", and the flush
coplanar layout is unchanged (every panel normal = the roof-plane normal, every panel corner inside the
traced polygon). **Lighthouse held.**

**Plain-language report only** (no diffs or hashes): the **two new preview URLs** to open; what changed for
the FLAT optimizer (it now re-solves the optimum live on every option change, locks accumulate,
Réinitialiser resets, generation maximized within the cap from PVGIS at the exact GPS, recommended value
shown in every group); what the PITCHED optimizer does (the same, minus the tilt axis and with orientation
fixed to alignée toit); confirmation the live public site and the lead flow are untouched; **which map env
var each new route reads** (`PUBLIC_MAPBOX_TOKEN` / `PUBLIC_MAPTILER_KEY`); and the one thing to check on
the phone — trace a roof, change one option and watch every other option re-optimize live to the
highest-generation combination, then change a second and watch the rest re-optimize holding both.

---

---

**ACROSS W36–W45 (founder's cross-cutting constraints):** this is a **copy-and-craft elevation of
the EXISTING site** — read the repo and rewrite what's there, never recreate a page that already
exists, and never reintroduce removed content (fake testimonials, project-count framing). **No
invented facts anywhere:** every figure traces to what's already published or confirmed repo data;
pompage has no Taqinor installs; financing names no partner, quotes no rate, claims no residential
exemption. **No new dependencies. Touch only `apps/web`.** The **live lead form and its entire data
flow** (1 000 MAD threshold, consent, WhatsApp deeplink, webhook, CAPI) stay **byte-for-byte
unchanged**. The **private estimator preview routes stay private** (noindex, not in nav, excluded
from sitemap, unlinked) — do not promote or alter them. **The whole W36–W45 batch lands in the run's
single self-merge to protected main** (the accepted path — don't flag it). **Lighthouse held 97–100 on every page,
reduced-motion respected, zero layout shift.** Plain-language report only (no diffs or hashes): for
each task, the pages changed and what a visitor now reads differently, confirmation the homepage
matches the sub-pages, confirmation the live lead flow is untouched, and any one thing left for Reda.

---

---

---

---

---

---

**ACROSS W46–W50 (founder's cross-cutting constraints):** every figure traces to **PVGIS, confirmed
tariff/physics, or sound logic — no invented numbers**; savings never exceed the avoidable energy
cost; impossible panel counts stay blocked by the footprint bound; the **needed-panel cap is always
respected**. **No new dependencies** (PVGIS, MapLibre, Mapbox, Three.js are already in the stack;
graphs are inline SVG). **Touch only `apps/web`.** All work stays on the **CURRENT latest private
preview route IN PLACE** (noindex, not in nav, excluded from sitemap, unlinked), the
**immediately-prior route left byte-for-byte intact as the baseline** — do NOT spawn a new route per
task and do NOT promote anything to public. The **live public site and the live lead form and its
entire data flow** (1 000 MAD threshold, consent, WhatsApp deeplink, webhook, CAPI) stay
**byte-for-byte unchanged**. **Each task is its own self-merged PR to protected main** (the accepted
path — don't flag it). Full Vitest suite green, **Lighthouse held 97–100**, reduced-motion respected,
zero layout shift. **Plain-language report only** (no diffs or hashes): the preview URL to open; for
each task what changed (the optimizer now re-solves after every lock down to the last one and what the
stop-after-two cause actually was; the pitched roof now offers "alignée toit" as the flush default and
drops the impossible orientations; both engines hardened with the new test count and the categories
covered; the production window with its Année/Mois/Jour views, typical-vs-specific day, and how
panel-count/layout/GPS drive it); confirmation the live site and the lead flow are untouched; which
map env var the route reads; and the one thing to check on the phone — lock options past the third and
watch each one re-optimize, switch a roof to pitched and confirm alignée toit is the flush default,
then open the production window, cycle months and days, and confirm a typical day versus a picked
date.

---

---

**ACROSS W51–W61 (founder's cross-cutting constraints):** **no invented facts, reviews, testimonials,
dashboard imagery or founder bio anywhere** — every figure traces to what is **already published**;
the **five installations stay exactly five, just uncounted**. **No new dependencies. Touch only
`apps/web`.** The **live lead form and its entire data flow stay byte-for-byte unchanged in
behaviour** (the form change is **visual restyle only**). The **private estimator preview routes stay
private** (noindex, not in nav, excluded from the sitemap, unlinked) — **do not touch them**. **Each
task is its own self-merged PR to protected main** (the accepted path — don't flag it). **Lighthouse
held 97–100 on every page, prefers-reduced-motion respected, zero layout shift.** **Plain-language
report only** (no diffs or hashes): for each task, **what a visitor now sees differently**;
**confirmation the form still advances all 3 steps with the deeplink intact**; **confirmation
`/sitemap.xml` returns 200**; and **confirmation the five installs are all still shown with no count**.

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
- 2026-06-18 — W62 shipped: `Testimonials.astro` + `testimonials.ts` (ships EMPTY, renders nothing
  until real avis added) on accueil/résidentiel/professionnel, Review/AggregateRating JSON-LD only on
  real data, `TESTIMONIALS_NOTES.md` with a one-tap WhatsApp review-request message. No fabricated avis.
- 2026-06-18 — W63 shipped: homepage guarantee band « 25 ans de performance garantie · production
  mesurée, pas promise — monitoring Deye Cloud » (facts from /garanties + monitoring; no new number).
- 2026-06-18 — W64 shipped: `FounderPortrait.astro` — photo-ready founder block, text-only fallback
  identical to today until Reda's portrait file lands under `public/photos/` (FOUNDER_PHOTO=null).
- 2026-06-18 — W65 shipped: `BrandStrip.astro` + `brands.ts` — 7 founder-confirmed tier-1 brands
  (+ Jinko, Huawei, Nexans), official logos when a file exists else styled word-marks; /équipement intro
  updated to name them (no invented model/spec). Logo files pending under `public/brands/`.
- 2026-06-18 — W66 shipped: « réponse sous 48 h ouvrées » on /contact (corrected from 24 h); SEO/a11y/
  hygiene guards (seo-pages, hygiene-w61, picture, photos-assets) green + clean production build.
- 2026-06-18 — Verified: full Vitest suite 1364/1364 green, `astro build` clean, `tsc` check clean.
- 2026-06-19 — W68 shipped: « Affiner ma consommation » on `/preview/toiture-3d-pro-11` — hand-edit the
  24 hourly bars (drag + required numeric grid + « Recaler sur ma facture ») AND a curated, fully-editable
  appliance calculator (climatisation BTU÷EER with CV labels, EV by kW×h or km/jour, cumulus, piscine, four,
  plaque, lave-linge/-vaisselle, sèche-linge, frigo, chauffage, pompe, fer, micro-ondes, PAC, TV, LED, +
  « Autre appareil ») with « Sur ma facture actuelle » (adds on top → raises size + battery) vs « Déjà compris »
  (reshape only). Feeds the existing self-consumption/savings (`billMAD`, surplus=0) + size-to-need +
  6 kWh/day-per-battery engine. Defaults + sources in `apps/web/APPLIANCES_NOTES.md`. New lib
  `applianceConsumption.ts` + 25 unit tests.
- 2026-06-19 — W69 shipped: « Personnaliser la disposition » on `/preview/toiture-3d-pro-11` — after the
  auto-layout, move/add/remove panels on the optimizer's valid placement lattice (snap to nearest valid empty
  cell; off-roof/setback/obstacle/occupied targets refused; green/red hover; drag + tap-to-select + +/− touch
  fallback; « Réinitialiser la disposition optimale »). Count changes recompute kWc/kWh-an/économies via the
  existing PVGIS-by-count path (per-panel yield unchanged when only position moves); footprint bound +
  needed-panel cap always hold. New lib `layoutVariability.ts` + 19 unit tests. Route stays private; pro-10
  byte-identical; live site + lead form untouched.
- 2026-06-19 — W67 PARTIAL: i18n foundation finished (registry `src/i18n/pages.ts`, LanguageSwitcher wired
  into Header+Footer, Layout-driven hreflang/canonical/sitemap, locale-aware shared chrome) + EN (`/en/`) and
  AR (`/ar/`, full RTL) for 12 pages: contact, nos-solutions, faq, garanties, financement, pourquoi-taqinor,
  à-propos, pompage-solaire, batteries-stockage, maintenance-monitoring, mentions-legales,
  politique-de-confidentialite. FR copy + every figure byte-identical; lead-form payload/endpoint/threshold/
  deeplink invariant across locales (asserted by a test). Remaining ~13 pages (home, résidentiel, professionnel,
  marocains-du-monde, équipement, regularization-article-33, loi-82-21, the 5 city pages, realisations/*,
  guides/*) need their shared figure-bearing components made locale-aware first — left FR-only and unswitched
  (FR unchanged), a clean next increment. W67 stays unticked.
- 2026-06-19 — Verified over the folded batch: full Vitest suite 1657/1657 green, `astro build` clean,
  `tsc` check clean, sitemap has the EN/AR pages with 0 `/preview/` leaks.
- 2026-06-19 — W67 COMPLETE: the remaining ~13 pages now ship in EN (`/en/`) + AR (`/ar/`, full RTL),
  built by 6 parallel worktree lanes. (1) Foundation lane made the 6 figure-bearing shared components
  locale-aware via inline `{fr,en,ar}` objects — GarantiesTeaser, BrandStrip, FounderPortrait,
  VideoChantier, WhatsAppMock, Testimonials — with FR rendered output byte-identical (links localized via
  `localizeNavHref`; figures/brands/Deye Cloud kept literal). (2) Home (`/en/`, `/ar/`), (3) résidentiel/
  professionnel/marocains-du-monde, (4) équipement/regularization-article-33/the 4 guides, (5) loi-82-21 +
  locale-aware `RegimeSelector`/`regime.ts` (additive `regimesFor(locale)`), (6) the 5 city pages + the
  réalisations hub + the 5 case studies, with locale-aware `cityContent.ts`/`caseStudies.ts`
  (`realisations.ts` untouched — translated `resume`/alts live in `caseStudies.ts`). Central registry
  `src/i18n/pages.ts` now lists all paths (dynamic city/case-study paths derived from CITIES/REALISATIONS),
  with `TRANSLATED_PATHS` exported and `tests/i18n.test.ts` extended to assert every registered path has its
  EN + AR source (incl. dynamic templates) and that nav links localize (no dead links). Lead form payload/
  endpoint/threshold/deeplink invariant across locales; every figure/law-number/legal-line/brand kept exact
  in Latin digits; no fabricated content. Folded batch verified: full Vitest suite **2245/2245 green**,
  `tsc` clean, sitemap = 34 EN + 34 AR public URLs, **0 `/preview/` leaks**. FR pages byte-for-byte unchanged.