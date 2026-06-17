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

### W2 — Five public city landing pages (Casablanca, Rabat, Marrakech, Tanger, Agadir) — [x]

Build five **public**, indexed city landing pages — "Installation solaire à Casablanca / à
Rabat / à Marrakech / à Tanger / à Agadir" — following the existing **"Cinéma du chantier"**
design and tokens. Each page: a city-specific intro, the **local sunshine-hours figure** (public
meteo data — already a defensible site claim, no new invented numbers), the service framing, and
**where a real Taqinor installation exists in or near that city** (Casablanca, El Jadida,
Nouaceur references already on the site) feature it with its **real kWc/production** and link to
its case-study page (see W3). Add **LocalBusiness + areaServed** structured data per page. Use
ONLY facts already published on the site or public meteo data. Each page is **in the sitemap**,
**linked from the footer and from the relevant segment pages**, and **cross-linked to the
diagnostic and to the matching case study**.

### W3 — Five public case-study pages (one per real installation) — [x]

Build five **public**, indexed case-study pages, one per real installation already shown on the
site — **réf. 468 El Jadida 17,04 kWc**, **réf. 400 Casablanca 11,36 kWc**, **réf. 236 El Jadida
5,68 kWc**, **réf. 134 Casablanca 5,68 kWc**, **réf. NC-10/25 Nouaceur 3,72 kWc** — built
entirely from facts already published (kWc, measured production, equipment, city, date) — invent
nothing. Each page: the context, the **roof/sizing logic in plain language**, the **equipment
posed**, and the **measured result from Deye Cloud**, using the existing real photos. Indexed, in
the sitemap, **linked from the homepage evidence gallery, the fiches chantier, the relevant city
page, and résidentiel/professionnel**. Add appropriate structured data (**Article or
CreativeWork**).

### W4 — Public "Pourquoi Taqinor" page — [x]

Build a **public**, indexed "Pourquoi Taqinor" page that consolidates the differentiators already
expressed across the site — engineering-led sizing (l'étude d'abord), real measured monitoring via
Deye Cloud, full **loi 82-21** conformity handled end to end, tier-1 equipment only, evidence over
promises. Introduce **no new claims or figures**; only restate and structure what the site already
says. In the sitemap, **linked from the homepage and segment pages**.

### W5 — Dedicated public /faq page — [x]

Build a dedicated **public**, indexed `/faq` page expanding the current homepage FAQ, covering
ONLY topics whose answers are already established on the site or in confirmed repo data: pricing
logic and ordres de grandeur, loi 82-21 regimes, Article 33 régularisation,
batteries/autoconsommation, garanties (from the equipment warranty table), délais and process,
monitoring/SAV. **Do NOT add questions about financing, bank products, incentives or taxes** (those
facts are not verified). Emit **FAQPage structured data** for the full set with **no duplicate or
conflicting FAQPage markup against the homepage**. In the sitemap, **linked from the footer and
nav**.

### W6 — Public guides/ressources hub at /guides + three seed articles — [x]

Build a **public** guides/ressources hub at `/guides` plus three seed articles drawn STRICTLY from
facts already published on the site or confirmed repo data, with **NO new figures and NO
tariff/cost claims** (the site's electricity-tariff basis is being aligned separately): (1) "Loi
82-21 expliquée simplement" from the loi-82-21 page, (2) "Faut-il des batteries ?" from the
existing FAQ answer, (3) "Onduleur hybride ou onduleur réseau ?" from the équipement page. Clean
editorial layout matching the design, **Article structured data**, indexed, in the sitemap. Add one
**"Guides" entry to the top nav** and link the hub from the footer. **Note in the report** that the
editorial calendar and any tariff/cost articles are pending Meryem's copy and the site-wide tariff
alignment.

### W7 — Public MRE section/page — [x]

Build a **public**, indexed MRE page — "Vous êtes Marocain·e à l'étranger ? Nous installons et
suivons l'installation de votre villa au Maroc, à distance, de l'étude au monitoring" — using ONLY
the site's existing positioning and its WhatsApp-first, remote-diagnostic reality; **no new factual
claims**. In the sitemap, **linked from résidentiel and the footer**.

### W8 — Public "Nos garanties / engagements" page — [x]

Build a **public**, indexed "Nos garanties / engagements" page that turns the existing equipment
warranty table into a reassurance page: the **12-year product / 25-year ≥84,8% performance /
10-year inverter & battery / 20-year structure / 2-year workmanship** figures already on the site,
plus the existing "monitoring Deye Cloud, SAV proactif, accès client" commitment. **Do NOT invent
any response-time SLA or underperformance policy.** In the sitemap, **linked from équipement and
the segment pages**.

### W9 — Sitewide internal linking + BreadcrumbList structured data — [x]

Improve internal linking across all public pages and add **BreadcrumbList** structured data
sitewide: cross-link **équipement ↔ résidentiel/professionnel**, **loi-82-21 ↔
regularization-article-33 ↔ professionnel**, and the new **city pages ↔ case studies ↔ segment
pages**. **Purely additive; touch no lead-flow code.**

### W10 — Format displayed phone number in header & footer — [x]

Format the **displayed** phone number in the header and footer as **+212 6 61 85 04 10** for
readability. The **`tel:` link target stays unchanged** (display-only change).

---

**ACROSS W2–W10 (founder's cross-cutting constraints):** no invented facts — every figure traces
to what's already published on the site or confirmed repo data; **no new dependencies**; the **live
lead form and its data flow untouched**; **one self-merged PR per task** per the protected-main
convention; **Lighthouse held on every page**; and a plain-language report listing the new public
URLs to click. NOTE: these are **public, indexed** pages (a deliberate exception to the preview-lab
"build everything private / noindex" standing rule for this batch — the founder asked for live
public pages), but the **live lead form and its data flow must stay byte-for-byte unchanged**.

---

### W11 — Correct the residential electricity tariff (régie ONEE barème) in the estimator + public figures — [x]

> Added 2026-06-17 via "add to web plan". This **resolves WG2** (tariff harmonization): the
> founder has supplied the verified June 2026 régie figures, so this is no longer gated.
> Activate **only the régie barème** below — no delegataire numbers ship yet.

**Do:**

1. **Correct the régie barème in the estimator.** First **read the current `estimatorBrain.ts`
   and anywhere else the tariff is defined** to see what's actually there — don't assume. The
   correct régie **"usage domestique"** grid, **consumer prices TTC (VAT 20 % already
   included — do NOT add VAT on top)**, is:
   - **0–100 kWh = 0,9010**; **101–150 = 1,0732** — these two billed **progressively** (each
     tranche at its own rate) **when monthly consumption ≤ 150 kWh**;
   - then **SELECTIVE billing when monthly consumption > 150 kWh** (the **whole month** billed
     at the single band's rate): **151–210 = 1,0732**; **211–310 = 1,1676**;
     **311–510 = 1,3817**; **> 510 = 1,5958**.
   - Band boundaries carry a **built-in 10 kWh tolerance**, so use **210 / 310 / 510** (not
     200/300/500).
   - This **replaces** the previous values where 201–300 was 1,18, 301–500 was 1,45 and >500
     was 1,66 (those upper rates were too high — 1,66 was the **force-motrice** rate, not
     domestic). **Keep** the existing bill→consumption inversion and savings logic; just feed
     it these corrected rates and boundaries.

2. **Make the tariff grid city-dependent** (a small per-city map keyed by city) because
   Morocco has two regimes: the **régie/government barème** (Marrakech, Agadir, El Jadida and
   all ONEE/régie areas) and **higher contractual grids** in the three ex-délégataire cities
   (Casablanca/Lydec, Rabat/Redal, Tanger/Amendis). **For now set EVERY city to the régie
   barème above** as the conservative default — this under-states savings slightly in the
   three délégataire cities, which is the **safe** posture (never the reverse). Add
   **Casablanca, Rabat, Tanger** as explicit entries **equal to the régie barème for now**,
   each with an **inline comment** documenting the known real-bill premium so a future session
   can drop in the exact grid: Casablanca/Lydec ≈ **+10,5 %** on the upper bands (real-bill HT
   1,0220 for 151–210, 1,1119 for 211–310, 1,5193 for >510); Tanger/Amendis the **most
   expensive**; Rabat/Redal the **least** (closest to the barème); exact full grids await one
   real recent bill per city. **Do not invent or ship any délégataire number beyond this** —
   only the verified régie barème is active.

3. **Unit tests** pinning the corrected régie model (energy portion, régie barème): a
   **~480 MAD** energy bill ⇒ **~347 kWh/month** (311–510 band); a **~1 480 MAD** energy bill
   ⇒ **~927 kWh/month / ~11 100 kWh/year** (>510 band); a **~135 MAD** energy bill ⇒
   **~141 kWh/month** (progressive). Also assert the **selective jumps** across boundaries
   (210→211, 310→311, 510→511) and that the **bill→kWh inversion still converges** across
   those jumps.

4. **Record the tariff basis** in `ESTIMATOR_BRAIN_NOTES.md` (documentation only): the régie
   barème numbers, the **VAT-20 %/TTC** basis, the **10 kWh tolerance** boundaries, the
   **two-regime (régie vs délégataire)** reality, and that délégataire exact grids are
   **pending real-bill calibration**.

5. **Align the public site.** Find **every place** the résidentiel and professionnel pages
   (and any ROI/savings illustration) use a flat **~1,4 MAD/kWh** and align them to this
   **régie selective barème**, so the public figures and the estimator share the same correct
   basis. **Keep** the existing "ordres de grandeur — jamais un devis" framing and the honest
   MAD ranges — this is an **accuracy correction**, not a redesign. Use the **régie barème**
   (the conservative basis) for public illustrative figures.

**Standing rules (this task):** touch **only `apps/web`**; the **live lead form and its entire
data flow** (1 000 MAD threshold, consent, WhatsApp deeplink, webhook, CAPI) **unchanged**; the
estimator **preview routes stay private** (noindex, not in nav, excluded from sitemap,
unlinked); **no new dependencies**; **one self-merged PR** to main; **Lighthouse held**.
**Plain-language report:** the exact **old→new** rates and boundaries now in the estimator,
what the per-city structure looks like and that **all cities currently use the conservative
régie barème**, which **public figures changed** (with page paths), confirmation the **live
lead flow is untouched**, and the **three worked-test values passing**.

---

### W12 — Estimator brain v3: full-search optimum, "Optimum" button with constrained re-opt, pitched/tuile roof model + roof-type toggle — [x]

> Added 2026-06-17 via "add to web plan". Build as the **next brain session** on a **NEW
> private preview route cloned from the current latest preview**. **READ FIRST:** confirm
> `/preview/toiture-3d-pro-5` is the latest, then read the actual `estimatorBrainV2.ts` engine
> code and the pro-5 page to see exactly which option groups, comparison table, azimuth/tilt/
> margin controls and obstacle handling already exist — **do NOT assume from notes**. Name the
> new route the next **`/preview/toiture-3d-pro-6`** and **leave pro-5 untouched as the
> baseline**. Everything stays **private** (noindex, not in nav, excluded from sitemap,
> unlinked). Use subagents for context room if needed but ship **ONE self-merged PR** (no waves,
> no GitHub tracking). The live public site and the live lead form (1 000 MAD threshold,
> consent, WhatsApp deeplink, webhook, CAPI) stay **byte-identical** — the estimator only
> pre-fills the existing flow.

**Do:**

1. **Fix "the optimum is wrong because the table tries too few combinations."** Widen the
   **search space** the recommendation is computed over: sweep **tilt** over a fine range (not
   2–3 presets), sweep **azimuth** (roof-aligned vs true-south — **compose with the already-
   shipped azimuth work, don't duplicate it**), evaluate **both portrait and paysage**, and
   evaluate **roof-edge margin on vs off** — every combination scored on **total kWh and
   match-to-need**, capped at the **needed-panel count**, with all existing physical bounds
   holding. **Decouple the SEARCH SPACE (now rich) from the DISPLAYED comparison table** (keep
   it clean and legible: the recommended config plus a few honest alternatives, not fifty rows).
   The recommended/optimum config must be the **true winner of the full search**, not merely the
   best of the few visible table rows.

2. **Add an "Optimum" button with constrained re-optimization.** Clicking Optimum with **nothing
   pinned** resets **ALL controls** to the globally recommended configuration (the one the brain
   already computes as "Recommandé"). Key behaviour: if the user has manually changed **one
   control** (e.g. tilt 15°, or forced Est-Ouest), clicking Optimum **HOLDS that one pinned
   choice** and **re-solves every OTHER control** (orientation, layout, azimuth, margin, panel
   count) to the best config given that pin — then **re-renders the 3D** and recomputes kWc,
   kWh/an, % of bill, and the savings band **through the existing engine**. Each option group
   **keeps showing which option is "Recommandé"** regardless of what is currently selected, so
   the user always sees they picked one but another is recommended. **No invented numbers;
   surplus beyond self-consumption stays valued at 0** (no LV net-billing in Morocco).

3. **Support pitched / tiled-roof (tuile) villas, not only flat roofs.** Today the estimator
   models a flat roof (panels on tilted ballasted racks with winter-solstice row spacing). Add a
   **SECOND roof model** for sloped/tuile roofs where panels mount **FLUSH on the slope**.
   Research note (verified): pitch CANNOT be measured from Moroccan imagery (top-down satellite
   only; no aerial flights, no usable Street View — Aurora/Project Sunroof rely on LiDAR + HD
   aerial photogrammetry and otherwise fall back to user-drawn roof + manual slope), so **pitch
   must be user-supplied**. Build pitched mode as: the user traces the roof plane on the
   satellite map as now, then **sets the slope angle** for that plane (a control with sensible
   Moroccan tuile presets, e.g. **~15° / ~22° / ~30°, adjustable**) and **indicates the plane's
   facing / down-slope direction** so its azimuth is known. Pitched-mode physics must be exact:
   panels lie flush → **array TILT EQUALS the roof pitch** and **array AZIMUTH EQUALS the roof
   facing**, both **imposed by the roof, shown read-only ("imposé par la toiture"), NOT chosen
   and NOT swept** by the optimizer; coplanar panels on one plane **do NOT self-shade → NO
   inter-row spacing within a plane** (tile edge-to-edge minus a small maintenance/fire-access
   gap) — this packs far more panels than a flat roof of the same area, and the engine must
   reflect that, **not reuse the flat-roof row pitch**. **Production per plane comes from PVGIS
   at that plane's real tilt+azimuth** (PVGIS already in stack — this makes the sloped numbers
   honest). **Ideally allow more than one plane** (e.g. two-sided roof), placing panels only on
   worthwhile planes and **honestly flagging/skipping a north-facing slope**. The needed-panel
   cap, the savings cap, and "size to need not to roof" all apply identically.

4. **Add the roof-type toggle (the "tile button").** A clear control switching the estimator
   between **"Toit plat"** (existing flat-roof model, unchanged, **default**) and **"Toit en
   pente / tuiles"** (the new flush model). Switching mode shows the controls that apply and
   hides/disables those that don't (in pitched mode tilt and azimuth become read-only
   roof-imposed values; flat-roof tent/rack options that don't apply are disabled). The
   **flat-roof path must stay byte-identical to pro-5** when "Toit plat" is selected (**guard
   with a test**). The Optimum button (item 2) works in both modes: in flat mode it sweeps the
   full space; in pitched mode (tilt/azimuth fixed by the roof) "optimum" is **which planes to
   use and how many panels** (sized to need, capped), plus layout where it still has freedom.

**Verification honesty:** the build agent cannot render the interactive map locally
(MapTiler/Mapbox keys live in Cloudflare), so **anchor every geometry/visual change to
code-checkable invariants** (flush panels coplanar with the plane; tilt == pitch and
azimuth == facing in pitched mode; zero row gap within a plane; every panel footprint inside the
plane polygon; Σ footprints ≤ usable area; flat-roof path unchanged) and **state clearly in the
report what only the owner's phone can confirm** on the rendered map.

**Keep every standing estimator rule** (see STANDING RULES): respect the needed-panel cap (never
overfill a roomy roof — surplus is uncompensated in Morocco); no invented numbers (every figure
traces to PVGIS, confirmed tariff/physics, or sound logic; savings never exceed avoidable energy
cost; impossible counts blocked by the footprint bound); build private (noindex, not in nav,
excluded from sitemap, unlinked); **no new dependencies** (Three.js geometry + existing PVGIS +
the in-house solar math cover this — if you genuinely think you need a new dependency, **STOP and
leave a note** rather than adding one); **one self-merged PR**; **live public site and lead form
unchanged**.

**Plain-language report (no diffs):** the new `/preview/toiture-3d-pro-6` URL with pro-5
preserved; how the Optimum button behaves with nothing pinned vs with one control pinned (a
worked example); what the search space now covers and why the optimum is now the true winner; how
pitched/tuile mode works, what the user enters (slope + facing) and why pitch is asked for rather
than measured; a worked sloped-roof example (a south-facing ~30° plane: panel count, kWc, kWh/an
vs the same roof treated flat); confirmation the flat-roof path is unchanged and the live site +
lead flow untouched; and exactly what to check on the phone.

---

### W13 — Public "À propos / Notre approche" page (founder + method) — [x]

> Added 2026-06-17 via "add to web plan".

Build a **public**, indexed "À propos / Notre approche" page, following the repo's
**accented-slug convention** for the URL (e.g. `/à-propos`), presenting the **founder** and the
**method**, built **STRICTLY from facts already published on the site**: docteur-ingénieur, plus
de 10 ans d'expertise R&D, chaque étude validée personnellement par le fondateur, la méthode
« l'étude d'abord, le chantier ensuite », production mesurée sur Deye Cloud, conformité loi 82-21
de bout en bout, matériel tier-1 uniquement, chantiers réels visitables. **Do NOT invent any
personal biography, motivation, or backstory, and do NOT name any former employer or company** —
only restate and structure what the site already states. **No bracketed placeholders:** the page
must read complete and honest from the published facts alone. Frame it around the founder's
**standards and method** (not a fictional life story), and keep it **DISTINCT from
`/pourquoi-taqinor`** (which lists differentiators) — this page centers the **founder and the
method**, do not duplicate that page. **Indexed, in the sitemap, added to the top nav and the
footer**, and **cross-linked to `/pourquoi-taqinor`, `/realisations`, and the diagnostic**. **In
the report, note that two optional enhancements remain for owner sign-off:** a personal
founder-story paragraph and naming the founder's industry background — **neither added without
approval**.

### W14 — Reframe réalisations away from a small project count (recency framing) — [x]

> Added 2026-06-17 via "add to web plan".

Reframe the réalisations presentation so it **never anchors on a small project count**. **Keep all
five case studies (remove none)**, but change the **réalisations page heading** and the **homepage
evidence-section heading** to a **recency framing** such as « Nos dernières réalisations » /
« Réalisations récentes », and **lead with the substantial dimensions already true (43,48 kWc
installés · 3 villes · chantiers visitables)** rather than anything that reads as a fixed total.
**Sweep all pages and remove any remaining phrasing that frames the work as exactly N projects.**

### W15 — Per-city annual sunshine-hours figures on the five city landing pages — [x] (already present)

> Added 2026-06-17 via "add to web plan".

Give each of the **five city landing pages its own accurate annual sunshine-hours figure** from
**public meteorological data** for that specific city (Casablanca, Rabat, Marrakech, Tanger,
Agadir), instead of the shared « ≈ 3 000 h/an » currently used on all of them. **Use real public
meteo figures only — invent no numbers; if an accurate public figure for a city can't be sourced,
keep an honest shared framing** rather than invent. **Keep the « à titre indicatif » honesty and
the existing « nos chantiers les plus proches » handling** for cities without a local install.

### W16 — Guarantees reassurance teaser on homepage + résidentiel + professionnel — [x]

> Added 2026-06-17 via "add to web plan".

Surface the existing guarantees as a **short reassurance teaser on the homepage and on the
résidentiel and professionnel pages** — a brief block built **only from the figures already on the
`/garanties` page** (12 ans produit, 25 ans ≥ 84,8 % performance, 10 ans onduleur & batterie,
20 ans structure, 2 ans main-d'œuvre, monitoring Deye Cloud avec accès client) that **links to
`/garanties`**. **Invent no new SLA or underperformance policy.**

### W17 — Verify (and if needed fix) the homepage shares the site header & footer — [x] (verified, already correct)

> Added 2026-06-17 via "add to web plan".

**Verify the homepage uses the same shared header and footer as the rest of the site:** the updated
nav (with **Guides** and **FAQ**), the formatted phone **+212 6 61 85 04 10**, and the full footer
(**Ressources** + « **Installation solaire par ville** » sections). **If the homepage is not
inheriting the shared layout, fix it** so it matches every other page. **If it already matches,
confirm that in the report.**

### W18 — Tighten homepage internal linking into /realisations & case studies — [x]

> Added 2026-06-17 via "add to web plan".

Tighten internal linking from the homepage into the new pages: **link the homepage evidence gallery
and the homepage fiches chantier through to `/realisations` and to the matching individual
case-study pages.** **Purely additive; touch no lead-flow code.**

### W19 — FAQ schema hygiene (no duplicate FAQPage) + clean /faq — [x]

> Added 2026-06-17 via "add to web plan".

Check FAQ schema hygiene: ensure **no duplicate or conflicting FAQPage structured data** between
the homepage FAQ and the `/faq` page, and that **`/faq` reads cleanly**. **Expand `/faq` only from
answers already established on the site** if it is thin — **add no questions about financing, banks,
incentives or taxes** (those facts are not verified).

---

**ACROSS W13–W19 (founder's cross-cutting constraints):** no invented facts — every figure traces
to what is already published, confirmed repo data, or public meteo data; **no new dependencies**;
the **live lead form and its entire data flow** (1 000 MAD threshold, consent, WhatsApp deeplink,
webhook, CAPI) **untouched**; the **estimator preview routes stay private** (noindex, not in nav,
excluded from sitemap, unlinked); **one self-merged PR per task** per the protected-main
convention; **Lighthouse held on every page**. Plain-language report listing **every new and
changed public URL to click**, plus confirmation the **live lead flow is untouched**. NOTE: like
W2–W10 these are **public, indexed** pages (the deliberate exception to the preview-lab
"build everything private / noindex" standing rule).

---

### W20 — Estimator brain v4: PVGIS as production source of truth + fine-grid TRUE-optimum search (flat roofs) — [ ]

> Added 2026-06-17 via "add to web plan". Build as the **next brain session** on a **NEW private
> preview route cloned from the latest existing `/preview/toiture-3d-pro-N`** — **read the repo
> first to find the highest N (the current v6)** and name the new route the **next number in
> sequence**, leaving every prior preview **byte-for-byte intact** as a baseline.

The fix: **make PVGIS the production source of truth and recommend the TRUE optimum** instead of the
best of a few table rows. **First read the current `estimatorBrain.ts` (and `estimatorBrainV2.ts`/
`estimatorBrainV3.ts`) and wherever production is computed to see what's actually there — don't
assume.** Today the brain compares a small fixed set (~6 configs) and recommends the best of those,
which misses the real optimum because it usually lies **between or outside** those discrete rows.

**Do (flat roofs):**

1. Replace the fixed-set pick with a **genuine search**: query PVGIS at the roof's **EXACT GPS** to
   get the specific yield (**kWh per kWc per year**) for each candidate plane, and **sweep a fine
   grid** — **tilt in small steps (about 5° up to ~35°)**, **azimuth** including **true south**, the
   **roof-aligned bearing**, and **east–west tents**, each in **portrait and landscape** — then
   recommend the **genuine maximum**.
2. Compare configs on **total annual kWh and on match-to-need, NOT on panel count** (per-panel yield
   drops as orientation moves off the optimum, and PVGIS captures that), and **respect the existing
   needed-panel cap throughout** (never overfill a roomy roof — surplus is uncompensated in Morocco).
3. **Keep the comparison table** for transparency with **PVGIS-honest numbers per standard config**,
   but the **RECOMMENDED choice is whatever the full search found**: when the optimum is not one of
   the standard rows, show it as **its own clearly-labelled row** ("Optimum calculé — inclinaison X°,
   orientation Y") with its exact tilt/azimuth/layout, **badge it "Recommandé"**, and give a
   **one-line plain-language reason** it beats the standard configs (e.g. fits N panels and covers
   100 % of the need where plein-sud 30° fits fewer and covers W %).

**PVGIS specifics to get right:** use the **v5_2 PVcalc/seriescalc API already in the stack**; the
azimuth parameter (**"aspect"**) convention is **SOUTH = 0°, EAST = −90°, WEST = +90°,
NORTH = 180°** (map the roof's compass facing to this correctly — **a wrong sign silently corrupts
production**); use **mountingplace = "free"** for flat-roof racked panels; and
**optimalangles=1 / optimalinclination=1** can anchor the per-location optimum in a single call.

**Keep it fast and inside PVGIS rate limits:** query **specific yield per (tilt, azimuth) per
location only** (it's independent of system size — **scale by kWc afterwards**), use a
**coarse-then-fine sweep** (coarse grid to find the basin, then refine around the best) instead of a
uniform fine grid, **cache** results **per rounded location + config**, and **reuse** them across the
comparison table and across orientation/layout toggles. **Degrade gracefully** to the engine's
existing in-house solar-geometry estimate (**labelled "estimé"**) if PVGIS is unreachable.

### W21 — Estimator brain v5: pitched/tiled-roof support, flush coplanar layout, roof-type chosen FIRST — [ ]

> Added 2026-06-17 via "add to web plan". Build on a **further NEW preview route cloned from the
> optimizer route just built in W20** (**next number in sequence**, all prior routes left intact).

Add support for **non-flat pitched/tiled roofs with a flush-mounted layout, chosen BEFORE tracing.**

**Do:**

1. **Add a roof-type step that comes FIRST**, before the area/roof trace: **flat terrace vs
   pitched/tiled roof**. **Flat keeps the W20 optimizer behaviour unchanged** (racks, tilt/azimuth
   sweep, inter-row spacing).
2. **Pitched/tiled is a fundamentally different layout:** panels lie **FLAT against the roof slope
   (flush / coplanar)**, not on tilted racks — the **panel tilt EQUALS the roof pitch** and the
   **azimuth EQUALS the way the roof faces**, so **there is nothing to optimize, the roof gives
   both**. **Ask the client the roof pitch** with sensible presets (e.g. **15° / 22° / 30° / 45°**)
   and an adjustable default, and let them **set/confirm the slope's facing direction using the
   existing map compass** (a 2D satellite trace can't tell which way a roof slopes, so the client
   indicates it).
3. **No inter-row spacing on pitched roofs:** because every panel shares the roof's plane, no row
   shades the next — **drop the winter-solstice row pitch entirely** on pitched roofs and **tile the
   plane densely**, limited only by the **usable area, the existing edge/ridge/eave setback, and the
   obstacle keep-outs** (portrait vs landscape still by whichever fits more).
4. **Production for a pitched roof comes from PVGIS at that single (pitch, facing) pair for the exact
   GPS**, using **mountingplace = "building"** (flush panels run hotter with less rear ventilation —
   this honestly and slightly lowers yield and correctly reflects an off-south or off-optimal-tilt
   roof).
5. **3D:** render the pitched roof as the **inclined plane defined by the chosen pitch and facing**,
   with the panels lying **FLUSH on that plane** (no triangular racks, no standing frames), keeping
   the roof's **traced satellite photo on the inclined surface** as today. The build agent **cannot
   see the rendered map** (map keys live in Cloudflare), so **anchor this to code-checkable
   geometry** — **every panel coplanar with the roof plane, every panel corner inside the traced
   polygon and on that plane** — rather than to how it looks; final visual alignment is confirmed on
   the phone.

**Scope for this version:** a **SINGLE primary roof plane** (one pitch, one facing), which covers
mono-pitch roofs and the best slope of a multi-slope roof; **multi-plane gable/hip roofs** (two-plus
slopes, each its own facing) are **deliberately out of this version**.

---

**ACROSS W20–W21 (founder's cross-cutting constraints):** every figure traces to **PVGIS, confirmed
tariff/physics, or sound logic** — **no invented numbers**, savings never exceed the avoidable energy
cost, impossible panel counts stay blocked by the **footprint bound**; the **needed-panel cap** is
always respected; **no new dependencies** (PVGIS, MapLibre, Mapbox, Three.js are already in the
stack); **each task is its own self-merged PR to protected main** (the accepted path — don't flag
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
- 2026-06-17 — W2–W10 done (SEO public-pages batch, one PR): shipped a public, indexed set —
  5 city landing pages (`/installation-solaire-{casablanca,rabat,marrakech,tanger,agadir}`),
  5 case studies + a `/realisations` hub, `/faq`, `/guides` + 3 articles, `/pourquoi-taqinor`,
  `/marocains-du-monde` (MRE), `/garanties`. All facts trace to what the site already publishes
  (centralised in `src/lib/realisations.ts`); nothing invented — Nouaceur shows no production
  figure (none published) and réf. 134 shows no inverter/battery (not published); city sunshine
  hours are flagged as indicative public météo data (`CITY_PAGES_NOTES.md`); only Casablanca
  claims a local chantier, the other 4 cities stay honest ("nearest chantiers"). Structured data:
  Service+areaServed (city pages), Article (case studies + guides), one FAQPage (via the existing
  `Faq` component, no homepage conflict), and a new `Breadcrumb` component emitting BreadcrumbList
  sitewide. W9 internal-linking: homepage gallery + fiches → case studies, équipement↔segments/
  garanties, loi-82-21↔article-33↔professionnel, footer expanded (Ressources + per-city links),
  Guides + FAQ added to nav (Régularisation stays reachable via the always-on Article 33 ribbon +
  footer). W10: header/footer display "+212 6 61 85 04 10" via a new `phoneDisplayIntl`; the `tel:`
  target and JSON-LD phone (`NAP.phone`) are unchanged. Lead form + `/api/simulate` byte-for-byte
  untouched. `astro build` clean (all routes prerendered, sitemap regenerated); 537 web tests green
  (updated `elevation.test.ts` 9→14 top-level pages, added `tests/seo-pages.test.ts`). Auto-deploys
  via Cloudflare on merge to main. PENDING (report): the guides editorial calendar and any
  tariff/cost articles await Meryem's copy + the site-wide tariff alignment ([[WG2]]).
- 2026-06-17 — W11 done (régie ONEE tariff correction): replaced the estimator's old (too-high)
  selective grid with the founder's verified June-2026 RÉGIE barème, prix consommateur TTC (TVA
  20 % already in the rates). OLD→NEW rates: progressive 0,90→**0,9010** (0–100) and 1,07→**1,0732**
  (101–150); selective 1,07→**1,0732** (151–210), 1,18→**1,1676** (211–310), 1,45→**1,3817**
  (311–510), and **1,66→1,5958** (>510 — the 1,66 was the force-motrice rate, not domestic).
  Boundaries stay at the effective 210/310/510 (nominal 200/300/500 + the built-in 10 kWh tolerance).
  Corrected identically in both engines (`estimatorBrain.ts` for pro-3 and `estimatorBrainV2.ts` for
  pro-4/pro-5). Added a per-city tariff structure (`TariffGrid`, `REGIE_TARIFF`, `TARIFF_BY_CITY`,
  `tariffForCity`) wired through `recommend(..., city)` / `recommend(..., {city})`: Casablanca, Rabat
  and Tanger are explicit map entries **all currently equal to the régie barème** (conservative
  default that slightly under-states savings in the three ex-délégataire cities — the safe side),
  each carrying an inline comment with the known real-bill premium (Casa ≈ +10,5 %, Tanger dearest,
  Rabat closest to the barème) for a future calibration once a real bill per city exists. Public
  figures aligned to the same régie basis: `résidentiel` 25-year illustration now "de l'ordre de
  12 000 à 16 000 MAD/an (barème régie ONEE)" instead of the old "≈18 000" (which exceeded the
  avoidable-energy-cost cap; the "4–6 ans" payback still holds), `billRange.ts` ROI-band note
  updated, and the pro-3/4/5 footnotes now read "barème régie ONEE (sélectif, TTC)" instead of the
  stale "1,4 MAD/kWh". Three worked test values pinned and green (≈135 MAD→≈141 kWh/mo progressive;
  ≈480 MAD→≈347 kWh/mo on 311–510; ≈1 480 MAD→≈927 kWh/mo ≈11 100 kWh/yr on >510) plus selective-jump
  and bill→kWh-convergence assertions and a city-map test. Tariff basis recorded in
  `ESTIMATOR_BRAIN_NOTES.md` §4. Preview routes stay private (noindex, sitemap-excluded); lead form +
  data flow byte-for-byte untouched. 543 web tests green; `astro build` clean. Resolves the régie
  half of [[WG2]] — Lydec/Redal/Amendis exact grids stay gated until a real bill per city. Auto-deploys
  via Cloudflare on push to main.
- 2026-06-17 — W12 done (estimator brain v3): new private `/preview/toiture-3d-pro-6` (noindex,
  sitemap-excluded, unlinked), built as a clone of pro-5 on a NEW pure engine `src/lib/estimatorBrainV3.ts`
  that COMPOSES on V2 without editing it (pro-3/4/5 byte-for-byte intact). Three additions, all tested
  (`tests/estimatorBrainV3.test.ts`, 22 cases + `tests/estimatorPreviewPro6.test.ts`): (1) FULL-SEARCH
  OPTIMUM — the "Optimum" button computes the true winner over the whole cartesian product (family ×
  fine tilt 5°→opt × azimuth {plein sud, aligné toit} × portrait/paysage × margin keep/remove), each
  capped at the bill-derived need, scored on placed energy; the rich search space is decoupled from the
  clean comparison table; proven never worse than V2's reco. (2) CONSTRAINED RE-OPT — pinning one
  control (e.g. tilt 15°, or forced Est-Ouest) holds it and re-solves every other; the "Recommandé"
  badges stay the GLOBAL optimum regardless of what's pinned. (3) PITCHED/TUILE ROOF MODEL — a roof-type
  toggle "Toit plat (défaut) / Toit en pente"; in pitched mode panels mount FLUSH (no solar row gap,
  edge-to-edge minus a 0,15 m maintenance gap → packs strictly more than a flat roof of the same area),
  array tilt = roof pitch and azimuth = roof facing, both IMPOSED/read-only ("imposé par la toiture",
  never swept), pitch + facing are USER-SUPPLIED (not measurable on Moroccan top-down imagery), production
  per plane from PVGIS at the real tilt+azimuth, multi-plane ready with north-facing planes skipped/flagged.
  Needed-panel cap, savings cap and "size to need" hold in both modes. FLAT path is byte-identical to pro-5
  (same `recommend(...)` call; the 3D `flush` flag defaults false; guarded by tests). No new dependencies
  (Three.js + existing PVGIS + in-house math). 581 web tests green; `astro build` clean; `tsc --noEmit`
  0 errors; pro-6 confirmed absent from the sitemap. PHONE-ONLY to confirm (build can't render the map):
  the flush 3D visual (schematic — building stays a flat volume, only panels carry the pitch), satellite
  alignment, touch ergonomics. Preview URL to open: `/preview/toiture-3d-pro-6`. Auto-deploys via
  Cloudflare on push to main.
- 2026-06-17 — W13 done (À propos / Notre approche): new public, indexed page at `/à-propos`
  (accented-slug convention, like `/résidentiel` / `/équipement`), centred on the FOUNDER and the
  METHOD, built strictly from facts already published on the site (docteur-ingénieur, 10+ ans R&D,
  chaque étude validée personnellement, « l'étude d'abord, le chantier ensuite », production mesurée
  Deye Cloud, conformité loi 82-21 de bout en bout, matériel tier-1, chantiers visitables). No
  invented biography/motivation, no former employer named, no bracketed placeholders — reads complete
  from published facts. Kept DISTINCT from `/pourquoi-taqinor` (the founder's standards + a 4-step
  method, with a clear renvoi to Pourquoi for the differentiator list). Added to the top nav and the
  footer (Ressources), cross-linked to `/pourquoi-taqinor`, `/realisations` and the diagnostic
  (`/contact#simulateur`). Indexed + in the sitemap (no noindex, not under /preview/). Tests updated:
  elevation top-level page count 14→15 + à-propos added to the ELEVATED list, and seo-pages public
  files/routes + nav/footer link checks extended. 584 web tests green. Lead form/data flow untouched.
  TWO OPTIONAL enhancements remain for owner sign-off (NOT added without approval): a personal
  founder-story paragraph, and naming the founder's industry background. Auto-deploys via Cloudflare
  on push to main. URL to open: `/à-propos`.
- 2026-06-17 — W14 done (recency reframing): the réalisations page no longer reads as a fixed total.
  `/realisations` heading is now « Nos dernières réalisations » (kicker « Réalisations récentes »)
  and LEADS with the substantial dimensions already true — 43,48 kWc installés · 3 villes (calculées
  depuis `realisations.ts`, jamais en dur) · chantiers visitables sur demande. The homepage evidence
  gallery heading changed from « Nos installations, telles quelles » to « Nos dernières réalisations »
  (kicker « Réalisations récentes »). All 5 case studies kept (none removed). Sitewide sweep for
  « N projets/installations/chantiers/réalisations » phrasing found nothing that frames the work as a
  small fixed total: the only count is the VideoChantier label « 30 secondes de chantier — 3
  installations réelles », which is scoped to the 30-second montage's content (3 sites filmed), not a
  portfolio total, so left accurate. 584 web tests green. Public/indexed pages only; lead form
  untouched. URLs to open: `/realisations` and `/` (gallery section).
- 2026-06-17 — W15 verified ALREADY PRESENT (no code change needed). The five city pages already
  render their OWN per-city sunshine figure via `c.sunshineHours` (Casablanca ≈ 2 950, Rabat ≈ 2 900,
  Marrakech ≈ 3 000, Tanger ≈ 2 800, Agadir ≈ 3 400) — these are differentiated public climate
  normals set during the W2 batch, documented in `CITY_PAGES_NOTES.md`, each shown with the honest
  « ≈ » prefix + « Ensoleillement annuel indicatif » framing, and the « nos chantiers les plus
  proches » handling already covers cities without a local install. No page uses a shared « ≈ 3 000 »
  across all cities (the only national « 2 800 à 3 400 h » framing lives in the diagnostic copy and
  schema text, which is correctly national, not per-city). A test already pins the « ≈ » indicative
  prefix per city. Nothing to build. URLs to open: `/installation-solaire-agadir` (≈ 3 400) vs
  `/installation-solaire-tanger` (≈ 2 800).
- 2026-06-17 — W16 done (garanties reassurance teaser): new shared component
  `src/components/GarantiesTeaser.astro` showing a compact strip of the figures ALREADY on /garanties
  (12 ans produit · 25 ans ≥ 84,8 % · 10 ans onduleur & batterie · 20 ans structure · 2 ans
  main-d'œuvre) plus « monitoring Deye Cloud avec accès client inclus », linking to `/garanties`.
  Placed near the conversion point (just before the diagnostic) on the homepage, résidentiel and
  professionnel. NO invented SLA / underperformance policy (guarded by a test that scopes the
  negative checks to the rendered body, not the docstring). 587 web tests green. Lead form untouched.
  URLs to open: `/`, `/résidentiel`, `/professionnel` (scroll to the « Garanties écrites » strip).
- 2026-06-17 — W17 verified CORRECT (no fix needed). The homepage (`index.astro`) renders through the
  same shared `Layout.astro` as every other page, and that Layout renders `<Header />` + `<Footer />`.
  So the homepage already shows the identical updated nav (Résidentiel, Professionnel, Équipement, Loi
  82-21, À propos, Guides, FAQ), the formatted phone +212 6 61 85 04 10 (`NAP.phoneDisplayIntl`), and
  the full footer (Ressources block + « Installation solaire par ville » section). Locked with a guard
  test (index uses the shared Layout; Layout renders Header + Footer). 588 web tests green. No code
  change to the page was required.
- 2026-06-17 — W18 done (tighten homepage → réalisations linking): the homepage's two evidence blocks
  already linked each card to its matching case study (gallery `→ /realisations/${g.slug}`, fiches
  `→ /realisations/${c.slug}`) and the fiches block had a « Toutes nos réalisations → » hub link; the
  only gap was that the evidence GALLERY had no hub link. Added a single additive « Voir toutes nos
  réalisations → » link to `/realisations` at the foot of the gallery, so BOTH evidence sections now
  reach the hub AND every individual case study. Purely additive — no lead-flow code touched. Guard
  test added (≥ 2 hub links; both template case-study links; every réalisation slug referenced). 589
  web tests green. URL to open: `/` (gallery + fiches sections).
- 2026-06-17 — W19 done (FAQ schema hygiene): the homepage short FAQ and the dedicated `/faq` page
  share the same `Faq` component and several questions overlap, so BOTH were emitting a FAQPage
  JSON-LD — a cross-page duplicate. Added a `schema` prop to `Faq.astro` (default true) that gates the
  JSON-LD; the homepage now renders `<Faq items={faq} schema={false} />` (keeps the visual accordion,
  drops the schema), leaving `/faq` as the SINGLE owner of the FAQPage structured data. `/faq` is
  already comprehensive (13 Q&A: prix/ordres de grandeur, loi 82-21 + 3 régimes, Article 33,
  batteries, garanties, délais/process, monitoring) with NO financing/bank/incentive/tax questions —
  no expansion needed, reads cleanly. Tests extended (component gates the script; homepage passes
  schema={false} and emits no inline FAQPage; /faq keeps it). 590 web tests green; `astro build`
  clean. URLs: `/` (FAQ accordion, no FAQPage now) and `/faq` (sole FAQPage).
