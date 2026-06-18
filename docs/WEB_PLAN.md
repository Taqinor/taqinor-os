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
   the `docs/WEB_PLAN*` files.
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
   preserved, 0 approvals; no per-agent PR, no per-task merge).
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
bound); build private (noindex, not in nav, excluded from the sitemap, unlinked); lands in the run's single end-of-batch self-merge (no per-task PR); the **live public site and lead form unchanged**.

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
lead form and its data flow untouched**; these tasks **land in the run's single end-of-batch self-merge — no per-task PR** per the protected-main
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
unlinked); **no new dependencies**; **lands in the run's single self-merge to main**; **Lighthouse held**.
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
> unlinked). Use subagents for context room if needed but land it in the run's **single self-merge** (no waves,
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
leave a note** rather than adding one); **lands in the run's single self-merge**; **live public site and lead form
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
excluded from sitemap, unlinked); these tasks **land in the run's single end-of-batch self-merge — no per-task PR** per the protected-main
convention; **Lighthouse held on every page**. Plain-language report listing **every new and
changed public URL to click**, plus confirmation the **live lead flow is untouched**. NOTE: like
W2–W10 these are **public, indexed** pages (the deliberate exception to the preview-lab
"build everything private / noindex" standing rule).

---

### W20 — Estimator brain v4: PVGIS as production source of truth + fine-grid TRUE-optimum search (flat roofs) — [x]

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

### W21 — Estimator brain v5: pitched/tiled-roof support, flush coplanar layout, roof-type chosen FIRST — [x]

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

### W22 — Estimator brain v6: TRUE sloped-plane pitched-roof render (flush, no racks) + full optimizer matrix actually DISPLAYED — [x]

> Added 2026-06-17 via "add to web plan". **This is ONE task = ONE new private preview route =
> ONE self-merged PR.** Do **NOT** split it into multiple routes or PRs, and do **NOT** leave
> half of it for a later run — **both fixes below ship together on a single new route.**
> **READ FIRST:** find the **highest existing `/preview/toiture-3d-pro-N` in the actual code**
> (the handoff says **pro-8** but **confirm from the repo, do not trust that number**), **clone
> it to the next number in sequence** as the new route, and leave **every prior preview
> byte-for-byte intact** as the baseline. **Before changing anything, read the current
> `estimatorBrain.ts`, the preview page, and its lazy-loaded 3D script** to see exactly how
> pitched/tiled roofs and the optimizer table are implemented today — **do not assume** — and
> **in the report state plainly what you found wrong** for each of the two problems below.

**FIX 1 — Pitched/tiled roofs must render as an actual SLOPED roof with panels mounted FLUSH on
the slope, NOT a flat roof with tilted racks.** The current build is wrong: on a non-flat roof it
keeps the flat-roof layout and just sets the rack tilt equal to the roof slope, so the 3D still
shows a horizontal roof with panels standing on triangular metal frames — that is a flat-roof
ballasted install, not a pitched-roof install. Correct it so that, when the roof type is
pitched/tiled:
- **(a)** the **3D ROOF SURFACE itself is an inclined plane** — tilted by the chosen roof pitch
  and rotated to the chosen facing direction — with the **traced satellite photo textured onto
  that inclined surface** (a horizontal roof plane is wrong whenever pitch > 0);
- **(b)** **panels lie FLUSH and COPLANAR on that inclined surface** — same plane and same
  surface-normal as the roof — raised only a **small fixed offset** (a few centimetres,
  representing low rails/standoffs) above the roof plane along its normal;
- **(c)** there are **NO triangular racks and NO standing tilt frames** anywhere in the
  pitched-roof scene — that triangular-frame geometry is a **flat-roof-only** thing and must be
  made **conditional on roof type**;
- **(d)** **NO inter-row spacing gaps** — because every panel shares the roof's plane no row
  shades the next, so **tile the plane densely**, limited only by usable area, the
  edge/ridge/eave setback, and the obstacle keep-outs (portrait vs landscape by whichever fits
  more).

The **flat-roof path stays byte-for-byte unchanged** (its tilted racks, tilt/azimuth sweep, and
winter-solstice inter-row spacing all preserved). Because the build agent **cannot see the
rendered map** (the MapTiler/Mapbox keys live in Cloudflare), **anchor this entirely to
code-checkable geometry and pin it with tests** — do not reason about how it looks: assert that
for a pitched roof the **roof-plane normal is the (pitch, facing) normal and is NOT the vertical
up-vector when pitch > 0**; that **every panel's normal equals the roof-plane normal within
tolerance (coplanar)**; that **every panel sits at the same constant small standoff above the
plane** (not varying heights that would imply racks); that **no triangular-rack mesh is
instantiated when roof type is pitched**; and that **every panel corner projects inside the
traced polygon and onto the inclined plane**. Pitched production stays **PVGIS at the single
(pitch, facing) pair, mountingplace = "building"**, as already specified.

**FIX 2 — The optimizer must search AND DISPLAY the full configuration matrix for flat roofs, not
pick from ~6 fixed layouts.** Today the comparison table shows roughly six named configs and
recommends the best of those, which misses the true optimum (it usually lies between the named
rows) and hides most of the option space from the client. Replace the fixed set with a **genuine
dense sweep**, pricing production for every candidate plane from **PVGIS at the roof's EXACT
GPS**: sweep **tilt in 5° steps from 0° up to ~35°**; sweep **azimuth across true south (0°), the
roof-aligned bearing, and a span around south (about south ±45° in ~15° steps) plus the dedicated
east–west back-to-back tent mode**; each of those in **both portrait and landscape**; keeping the
existing **shade-free winter-solstice row spacing** so production stays honest (lower tilt already
yields tighter shade-free spacing and therefore more panels — that count-vs-tilt trade-off is
exactly what the sweep must surface). For every combination compute **panels fitted** (existing
packing + footprint bound), **kWc**, **kWh/an (PVGIS)**, **% of the bill covered**, and the
**savings band**. The **RECOMMENDED choice is the genuine maximum over the WHOLE sweep**, judged
on **total annual kWh and match-to-need** (respecting the **needed-panel cap** throughout — never
overfill a roomy roof, surplus is uncompensated in Morocco), shown as **its own clearly-labelled
row ("Optimum calculé — inclinaison X°, orientation Y, portrait/paysage") badged "Recommandé"**,
with a one-line plain-language reason it beats the standard configs. Then make the comparison
table **actually SHOW the full matrix instead of six rows**: render **every evaluated
configuration in a browsable, sortable table** (sortable at least by **kWh/an, by panel count,
and by % of bill covered**; **grouped or filterable by orientation/layout** so the long list
stays readable **on a phone**), with the **recommended row pinned and highlighted**. Keep PVGIS
fast and inside its rate limits: **specific yield (kWh per kWc per year) per (tilt, azimuth) is
independent of system size, so query it once per plane per location and scale by kWc**; use a
**coarse-then-fine sweep** (coarse grid to find the basin, refine around the best); **cache per
rounded location + plane**; **reuse across the table and across toggles**; **degrade gracefully to
the engine's in-house solar-geometry estimate (labelled "estimé")** if PVGIS is unreachable.
**Note in the report — do NOT build it this pass — that inter-row spacing / ground-coverage-ratio
could become a further optimization axis later, but only with a proper row-to-row self-shading
production model the engine does not yet have** (PVGIS prices a single plane, not row
self-shading), so shipping tighter-than-shade-free spacing now would mean un-modelled shading and
is **deliberately deferred** to keep every number honest.

**Standing rules for this task:** touch **only `apps/web`**; the **new route stays private**
(noindex, not in nav, excluded from sitemap, unlinked); the **live public site and the live lead
form and its entire data flow** (1 000 MAD threshold, consent, WhatsApp deeplink, webhook, CAPI)
stay **byte-for-byte unchanged**; **no new dependencies** (PVGIS, MapLibre, Mapbox, Three.js are
already in the stack); **reduced-motion respected and zero layout shift**; every figure traces to
**PVGIS, confirmed tariff/physics, or sound logic** (no invented numbers, savings never exceed
avoidable energy cost, impossible counts blocked by the footprint bound); **one self-merged PR to
protected main** (the accepted path — don't flag it); **full Vitest suite green with the
pitched-roof geometry tests and the optimizer-sweep tests above added**; **Lighthouse held**.
**Plain-language report only** (no diffs or hashes): the new preview URL to open; what you found
wrong in the current pitched-roof code and the current optimizer/table and what each now does;
confirmation the live site and lead flow are untouched; and the single thing to confirm on the
phone — that **on a pitched roof the 3D shows a sloped roof with panels lying flat against the
slope (no triangles, no row gaps)**, and that the **flat-roof comparison table now lists the full
set of layouts with the true optimum badged**.

---

### W23 — Public "Pompage solaire" service page (`/pompage-solaire`) — [x]

> Added 2026-06-17 via "add to web plan".

Build a **public**, indexed "Pompage solaire" service page (SEO slug, e.g. `/pompage-solaire`) — this
is a **NEW service** Taqinor now offers (agricultural/irrigation solar pumping), so frame it as a
**service capability, NOT as installed evidence**. **Taqinor has no pompage installations yet, so
invent NO Taqinor pompage projects, photos, or production figures.** Write technically accurate
solar-pumping content: how solar pumping works for irrigation and agriculture (panels driving a pump,
**often direct-drive without batteries**, sized to the well depth, **débit / hauteur manométrique
(HMT)** and the crop's water needs, with a **controller/variateur**); the **engineer-led approach
(l'étude d'abord applied to pumping — sized to the real need)**; and **the one genuine fiscal
advantage that is verified and current: solar water-pumping systems benefit from a general VAT
exemption in Morocco covering the pump and the panels** — state it plainly and honestly as an
advantage for agricultural pumping, but **do NOT extend this claim to rooftop residential PV, where it
does not apply**. Match the existing **"Cinéma du chantier"** design and tokens. **Indexed, in the
sitemap**, and (once the nav/footer tasks below run) in the **Solutions dropdown**, the **footer
Solutions column**, the **Nos solutions hub**, and a **homepage Solutions card**; **cross-linked to
the diagnostic and to équipement**.

### W24 — Public "Batteries & stockage" service page — [x]

> Added 2026-06-17 via "add to web plan".

Build a **public**, indexed "Batteries & stockage" service page (SEO slug matching repo conventions)
**strictly from facts already on the site**: the role of storage in autoconsommation (the existing FAQ
already explains batteries are justified for **night-time consumption or continuité de service**, and
that **direct daytime autoconsommation is often the better investment**), and the storage hardware
already posed on `/équipement` and the fiches chantier (**Dyness LFP** and the kWh figures already
shown). **Invent no capacities, prices, or specs not already published.** Engineer voice: when storage
pays and when it does not, sized to the consumption profile, decided in the étude. **Indexed, in the
sitemap**, and to be wired into the Solutions dropdown, footer, hub and homepage cards (tasks below);
**cross-linked to équipement, résidentiel, and the diagnostic**.

### W25 — Public "Maintenance & monitoring" / SAV page — [x]

> Added 2026-06-17 via "add to web plan".

Build a **public**, indexed "Maintenance & monitoring" / SAV page (slug matching repo conventions)
**from facts already on the site**: the **Deye Cloud monitoring with client access included on every
installation** (already stated across the site) and the **engagements already on `/garanties`**. Frame
it as the **post-installation promise** — production suivie en temps réel, accès client, SAV. **Do NOT
invent any response-time SLA, intervention delay, or underperformance policy not already published.**
**Note in the report** that this page gets stronger once real **anonymised Deye Cloud dashboard
screenshots** are added — leave a clean placeholder spot but **ship from verified facts now**.
**Indexed, in the sitemap**, to be wired into Solutions dropdown/footer/hub/homepage (tasks below);
**cross-linked to garanties and équipement**.

### W26 — Public "Financement & rentabilité" page (`/financement`) — [x]

> Added 2026-06-17 via "add to web plan".

Build a **public**, indexed "Financement & rentabilité" page (slug, e.g. `/financement`) framed
**RENTABILITÉ-FIRST and strictly honest** — its job is to reassure an **80 000 MAD** buyer, not to
over-promise. Lead with the investment framing already supported on the site: a well-sized
installation **self-finances in roughly 3 to 7 years** through the avoided electricity cost (**régie
ONEE barème**), and the panels are **guaranteed in performance over 25 years**, so the years after
payback are near-free electricity. **Be transparent and honest:** Taqinor is **not a lender**; there
is **no special residential subsidy**; clients typically pay **cash or via ordinary bank consumer
credit**; for businesses, **green financing lines for renewable-energy projects exist in Morocco**
(state this **generally** — **do NOT name a bank partner Taqinor does not have, do NOT quote any
interest rate, TAEG, or product name, and do NOT claim a residential VAT exemption, which does not
apply to a complete turnkey installation**). Make clear the **étude includes the precise ROI
calculation for the client's own bill**. **No invented numbers** — reuse only the ROI logic and
figures already published on résidentiel/professionnel. **Indexed, in the sitemap**, linked from the
**Ressources dropdown and footer**, and **cross-linked from résidentiel and professionnel**.

### W27 — Upgrade "À propos" with the approved founder pedigree + reconcile with "Pourquoi Taqinor" — [x]

> Added 2026-06-17 via "add to web plan". **Builds on W13**, which created `/à-propos` and deliberately
> deferred naming the founder's industry background pending owner sign-off — that sign-off is now given.

First **check whether `/à-propos` exists in the repo** (it does — built in W13). Build or update it to
name the founder's **real, owner-approved background — a docteur-ingénieur with 10+ years of R&D
experience at Huawei, Ericsson and STMicroelectronics** — plus a short, honest founder narrative
explaining **why an engineer started a solar company** and the conviction behind **"l'étude d'abord"**
(chaque étude validée par le fondateur). **Write only verified facts:** name those three employers and
the doctorate/R&D background, but **invent NO specific projects, dates, titles, team sizes, or personal
anecdotes** (the narrative can be refined by Reda/Meryem later). Keep **`/pourquoi-taqinor`** as the
distinct **differentiator** page (engineering-led sizing, real measured monitoring via Deye Cloud, full
loi 82-21 conformity end to end, tier-1 equipment only, evidence over promises); **ensure the two pages
don't duplicate and are cross-linked**. **À propos goes in the primary nav; Pourquoi Taqinor goes in
the Ressources dropdown** and is **linked from the segment pages**.

### W28 — One shared header + footer on EVERY page (incl. homepage) + new primary nav with Solutions/Ressources dropdowns — [x]

> Added 2026-06-17 via "add to web plan". This is **information architecture, not a redesign**.

Restructure the **entire site navigation into ONE shared header and footer used by EVERY page including
the homepage**. First **read the current header/footer components and confirm which pages use them**:
the homepage `/` is currently serving an **older nav** (Résidentiel · Professionnel · Équipement · Loi
82-21 · Régularisation, unspaced phone, bare footer) while the sub-pages already show Guides · FAQ, the
spaced phone, and a fuller footer — so the homepage either uses a separate/hardcoded header/footer or is
served stale; **make the homepage render the EXACT same shared Header and Footer as every other page**
so the whole site has one identical nav and footer.

The **new primary navigation** is: **Solutions (a dropdown), Réalisations, Équipement, Ressources (a
dropdown), À propos** — plus the existing **"Diagnostic gratuit"** CTA button and the phone shown as
**+212 6 61 85 04 10**.
- The **Solutions** dropdown contains, in this order: **Résidentiel, Professionnel, Pompage solaire,
  Batteries & stockage, Maintenance & monitoring, Régularisation Loi 82-21** (the existing
  `/regularization-article-33` page).
- The **Ressources** dropdown contains: **Guides, FAQ, Loi 82-21 expliquée** (the existing `/loi-82-21`
  page), **Pourquoi Taqinor, Financement & rentabilité, Marocains du monde**.
- **REMOVE the Loi 82-21 explainer (`/loi-82-21`) from the top-level menu** — it stays a **live page,
  indexed and in the sitemap**, now reached **only from the Ressources dropdown, the footer, and
  contextual in-body links** (from the régularisation page, professionnel, and résidentiel), **never
  from the top nav**.

**Dropdowns must be fully accessible:** keyboard-operable (focusable trigger, Escape closes, tab/arrow
through items, correct ARIA), work on touch with a tap on mobile, and **degrade gracefully so if JS
fails the items are still reachable** (the **Solutions trigger also links to the Nos solutions hub**;
the **Ressources trigger can link to the Guides hub**). **Keep the existing "Cinéma du chantier" design,
tokens, Archivo/Hanken type and night-blue palette.** **Apply the new header and footer identically
across all pages and confirm the homepage matches the sub-pages exactly.**

### W29 — Reconcile the footer site-wide + turn the footer "Services" list into REAL links — [x]

> Added 2026-06-17 via "add to web plan". Pairs with W28 (shared footer).

Reconcile the footer **site-wide** so every page shows **one identical footer**, and turn the footer
**"Services" list into REAL links**. Today that section is **plain non-clickable text** and the
**homepage footer is missing sections the sub-pages have**. Make the footer identical everywhere with
these columns:
- **Solutions** — linking each service to its page: **Résidentiel, Professionnel, Pompage solaire,
  Batteries & stockage, Maintenance & monitoring, Régularisation Loi 82-21**;
- **Ressources** — **Réalisations, Guides, FAQ, Loi 82-21 expliquée, Pourquoi Taqinor, Financement &
  rentabilité, Marocains du monde, À propos**;
- **"Installation solaire par ville"** — the **5 city pages**;
- **Contact** — spaced phone **+212 6 61 85 04 10**, email, WhatsApp, zone d'intervention;
- the **legal line** (mentions-légales, confidentialité).

**Only link pages that actually exist — no invented links.**

### W30 — Public "Nos solutions" overview/hub page (`/nos-solutions`) — [x]

> Added 2026-06-17 via "add to web plan". The Solutions dropdown (W28) points to this as its parent and
> no-JS fallback.

Build a **public**, indexed "Nos solutions" overview/hub page (slug e.g. `/nos-solutions`) that the
**Solutions dropdown points to as its parent** and that **doubles as an SEO landing page and the no-JS
fallback for the dropdown**. List each solution with a short description and a link: **Solaire
résidentiel, Solaire professionnel/industriel, Pompage solaire, Batteries & stockage, Maintenance &
monitoring, Régularisation Loi 82-21**. **Use only positioning and facts already on the site — no new
claims or figures.** Clean editorial layout matching the design, **indexed, in the sitemap, linked from
the header (Solutions parent) and footer**.

### W31 — Add a "Nos solutions" section to the homepage — [x]

> Added 2026-06-17 via "add to web plan".

Add a **"Nos solutions" section to the homepage** so services are visible on the **most-visited page**,
not only in the menu: a clean set of **cards** linking to **Résidentiel, Professionnel, Pompage solaire,
Batteries & stockage, Maintenance & monitoring, and Régularisation Loi 82-21**, in the existing design
language, **placed sensibly in the current homepage flow** (e.g. extending the existing **"Deux
métiers"** segment block). **Use only existing positioning — no new claims.** **Keep the homepage's
Lighthouse and zero-CLS intact.**

### W32 — Verify & complete breadcrumbs + internal linking across all public pages — [x]

> Added 2026-06-17 via "add to web plan".

Verify and complete **breadcrumbs and internal linking** across all public pages: **confirm
BreadcrumbList structured data sitewide (add where missing)**, and ensure **contextual in-body
cross-links** between **équipement ↔ résidentiel/professionnel**, **loi-82-21 expliquée ↔ régularisation
Article 33 ↔ professionnel**, the **5 city pages ↔ their matching case studies ↔ the segment pages**,
and the **new Solutions/Pompage/Batteries/Maintenance/Financement pages ↔ équipement and the
diagnostic**. **Purely additive; touch no lead-flow code.**

### W33 — Fix cache-on-deploy so the homepage & all HTML never serve a stale version after a deploy — [x]

> Added 2026-06-17 via "add to web plan". Touches the Worker/Cloudflare cache headers only — keep
> `/api/*` and the lead pipeline byte-for-byte unchanged. If the only safe fix needs a NEW Cloudflare
> dashboard step the founder must set, mark `[BLOCKED]` and list it under MANUAL rather than guessing.

Fix the cache-on-deploy behaviour so the **homepage and all HTML never serve a stale old version after a
deploy** — this is why the homepage currently lags the rest of the site. **Read how the Worker /
Cloudflare Workers Builds setup currently sets cache headers on HTML responses** and make HTML pages
**revalidate on each deploy** (an appropriate `Cache-Control` on HTML so the edge does not serve a stale
document, **or** a cache rule excluding HTML, **or** a purge-on-deploy step — **whatever fits the
existing setup**), while **leaving long-cache on hashed static assets (CSS/JS/fonts/images) untouched**
for performance. **Do not change any other Worker behaviour; keep `/api/*` and the lead pipeline exactly
as they are.** **In the report, state exactly what changed and confirm a fresh deploy now reflects on
`/` without a manual purge** (and note the one-time manual Cloudflare cache purge the founder does by
hand, if any).

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

### W34 — Estimator brain: LIVE constrained optimizer for FLAT roofs (re-solves on every option change, accumulating locks) — [x]

> Added 2026-06-17 via "add to web plan". Build as the **next brain session** on a **NEW private preview
> route cloned from the latest existing `/preview/toiture-3d-pro-N`** — **read the repo first to find the
> highest N (the current latest)** and name the new route the **next number in sequence**, leaving every
> prior preview **byte-for-byte intact** as a baseline.

**Read first (do NOT assume — report what is actually there):** the latest `/preview/toiture-3d-pro-N`,
`estimatorBrain.ts` (and the V2..V6 engines), the preview page, wherever production/PVGIS is computed, and
wherever the option controls (orientation/azimuth, tilt, layout portrait/paysage, margin/setback,
panneaux nécessaires) are wired. In particular establish **whether production already comes from PVGIS at
the exact GPS or from a generic factor**, and **how the current "Recommandé" is currently chosen**.

**The fix:** today the optimizer recommends the best of a few preset rows and does NOT re-solve when the
user changes an option. Replace it with a **live constrained search**. Treat each user-facing option as an
**axis**: orientation/azimuth (plein sud, alignée toit = the roof-aligned bearing, est-ouest tents, and any
south±offset already present), tilt (a fine grid 0–35°), layout (portrait/paysage), the roof-edge
margin/setback (keep/remove), and the panneaux-nécessaires target.

1. **Default state: every axis AUTO** — the optimizer shows the **global optimum** with each axis at its
   best value, each marked **"Recommandé"**.
2. **Locking:** when the user explicitly sets a value on any axis, **LOCK that axis** to that value
   ("votre choix") and **IMMEDIATELY re-solve** over all still-AUTO axes — holding every locked axis fixed
   — to **maximize total annual generation**, then update the displayed option values, the 3D, and **every
   result** (nombre de panneaux, kWc, kWh/an, % de la facture couverte, fourchette d'économies).
3. **Locks ACCUMULATE:** a second lock floats only the remaining AUTO axes holding BOTH; a third locks a
   third; and so on. Setting a new value on an already-locked axis just updates that lock.
4. **"Réinitialiser"** clears ALL locks at once (back to the global optimum); plus a way to **return a
   single axis to AUTO** (e.g. tapping its Recommandé/Auto state re-floats just that axis).
5. **"Highest generation" defined precisely:** panels placed × kWc per panel × the **PVGIS specific yield
   (kWh per kWc per year) at the roof's exact GPS** for that combination's tilt and azimuth — **NEVER a
   generic factor** — where **panels placed = min(needed, what physically fits that layout)**, so the
   **needed-panel cap is ALWAYS respected** (never overfill a roomy roof — surplus is uncompensated in
   Morocco). On a roof that meets the need every config places the needed count → optimum lands on the
   highest-yield orientation/tilt (plein sud at the optimal tilt); on a roof-limited roof the optimizer
   trades density against per-panel yield to maximize total kWh.
6. **Per-axis "Recommandé":** for EVERY axis (locked or not) show which value is "Recommandé" = the value
   that axis **would take if it were freed while the other current locks are held**, so when the user locks
   a sub-optimal value they SEE the recommended value and the generation it costs them (keeps the existing
   rule that the brain always shows the recommended option in each group even when the user chose another).
7. **Keep the comparison table** for transparency with PVGIS-honest numbers per standard config, the
   recommended row badged "Recommandé" — shown as its own **"Optimum calculé — inclinaison X°, orientation
   Y"** row with a one-line plain-language reason when the optimum is not a standard row.

**PVGIS specifics (verify against current PVGIS docs, not memory):** use the **v5_2 PVcalc/seriescalc API
already in the stack**; the azimuth parameter (**"aspect"**) convention is **SOUTH = 0°, EAST = −90°,
WEST = +90°, NORTH = 180°** (map the roof's compass facing correctly — a wrong sign silently corrupts every
number); use **mountingplace = "free"** for flat-roof racked panels; **optimalangles=1 /
optimalinclination=1** can anchor the per-location optimum in one call. **Fast + inside rate limits:**
specific yield is independent of system size, so query per (tilt, azimuth) per location and scale by kWc
afterwards; use a **coarse-then-fine** tilt sweep (coarse grid to find the basin, then refine around the
best) not a uniform fine grid; **cache** results **per rounded location + config** and reuse them across
the table, across every lock/unlock, and across the per-axis "what if freed" computations, so re-solving on
each option change is **instant with no lag**. **Degrade gracefully** to the engine's existing in-house
solar-geometry estimate (labelled **"estimé"**) if PVGIS is unreachable.

---

### W35 — Estimator brain: the SAME live optimizer for PITCHED/tiled roofs (flush coplanar, no tilt axis, orientation fixed) — [x]

> Added 2026-06-17 via "add to web plan". Build on a **further NEW private preview route cloned from the
> flat-optimizer route just built in W34** (**next number in sequence**, every prior route left
> byte-for-byte intact).

**Read first:** confirm the **pitched flush layout** and the **roof-type-first step** are present on the
route you clone, and **PRESERVE that layout and 3D exactly** (panels lying flush and coplanar on the
inclined roof plane, no triangular racks, no inter-row gaps). This task **ADDS the optimizer/options; it
does NOT rebuild the pitched layout.**

Make the pitched optimizer **identical to the flat one (W34)** — same live constrained re-solve, same
accumulate-locks + Réinitialiser, same per-axis "Recommandé" badge, same "highest generation" definition,
same needed-panel cap — with exactly **two physics-forced differences**:

1. **NO tilt axis** — a flush panel's tilt EQUALS the roof pitch fixed by the roof; show the tilt as
   roof-determined, never as an optimizable option.
2. **Orientation locked to "alignée toit"** — a flush panel cannot be turned to true-south or into
   east-west tents, so plein-sud and est-ouest are **physically impossible here and must be omitted** (not
   offered, or shown as non applicable); "alignée toit" is the roof-determined orientation, not a user
   choice.

The **free axes** the optimizer floats on a pitched roof are therefore **layout (portrait/paysage), the
roof-edge margin/setback (keep/remove), and the panneaux-nécessaires target** — the user locks any of these
and the optimizer re-solves the rest exactly as on the flat roof, with the per-group recommended value
shown. **Production** for a pitched roof comes from **PVGIS at the single fixed (pitch, facing) pair for the
exact GPS** using **mountingplace = "building"** (flush panels run hotter with less rear ventilation → a
slightly lower yield, correct for an off-south or off-optimal-tilt roof). Keep the comparison table over
the pitched free space with the recommended row badged. Everything else — caching, graceful PVGIS fallback
labelled "estimé", the cap, the honesty rules — is **identical to the flat optimizer**.

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

### W36 — Site-voice governance doc (`apps/web/STYLE.md`) + kill the recycled-phrase problem (docs only) — [x]

> Added 2026-06-18 via "add to web plan".

Establish the site's voice as a committed governance doc and kill the recycled-phrase problem.
First read every public page in `apps/web` and inventory the signature phrases now repeated
across many pages — at least: "c'est l'étude/le calcul qui décide du matériel, jamais
l'inverse", "la production se mesure, elle ne se promet pas", "pas d'un kit standard", "l'étude
d'abord, le chantier ensuite", "chaque étude validée par le fondateur, docteur-ingénieur", the
identical three-block "L'étude d'abord / Production mesurée / Conforme loi 82-21" trio, and the
"Votre toiture à [ville] mérite une étude sérieuse" closer — plus any others found. Write
`apps/web/STYLE.md` defining: the target buyer (an affluent, skeptical, technically-literate
Moroccan committing 80 000+ MAD to a 25-year, legally-compliant asset, wary of salesy
installers, wanting proof and an accountable human); the voice (confident engineer's restraint —
concrete and measured over adjectival; lead with the real number; vary rhythm page to page;
native idiomatic French; no eco-hype; human/direct/founder-led/monitored, never
call-center-impersonal); and two hard rules every page and every future session must follow:
(1) each signature phrase appears AT MOST ONCE across the whole site (ideally only on the
homepage), every other page expressing the idea in its own fresh words, and CTAs/footer/legal
lines exempt; (2) every city, segment and service page must carry at least one concrete fact
specific to that page, never a generic sentence with only the place/topic swapped in. This is
documentation/governance only — **no page changes in this task**. Part of the run's single end-of-run self-merge (no per-task merge).

### W37 — Rewrite the five city pages so no two share a paragraph (city-specific prose) — [x]

> Added 2026-06-18 via "add to web plan".

Rewrite the five city pages (Casablanca, Rabat, Marrakech, Tanger, Agadir) so no two share a
paragraph and each reads as written about doing solar in THAT city — not a template with the
name swapped. Read each page first; keep every real figure and the page structure, rewrite only
the prose. Each city's hero, body and closer must be distinct, drawing local specificity ONLY
from verified facts: the per-city sunshine figure already on the page, the real Taqinor
installation in or near that city where one exists (Casablanca, El Jadida, Nouaceur refs — real
kWc/production), and the city's own context (climate, typical roof, role). You MAY reference the
local electricity distributor for added specificity ONLY after verifying the currently-correct
operator for that city against the repo's tariff reference / confirmed data (the operator
landscape has been reforming) — if it can't be verified as current, use the régime/étude framing
instead rather than risk a stale name. Replace the identical three-block trio and the "mérite
une étude sérieuse" closer with city-specific writing. Invent nothing; every figure traces to
published or confirmed data. Rewrite each page's title and meta-description to be distinct and
compelling too. Part of the run's single end-of-run self-merge (no per-task merge).

### W38 — Rewrite the three core sales pages (résidentiel, professionnel, équipement) to STYLE.md voice — [x]

> Added 2026-06-18 via "add to web plan".

Rewrite the three core sales pages — résidentiel, professionnel, équipement — to world-class
craft in the STYLE.md voice. Read each first; keep all real figures, the pricing bands with
their real refs, the warranty table, and the page structure — rewrite the prose so each page has
its own rhythm and language, removes every recycled signature phrase (each idea re-expressed
freshly), and leads with concrete evidence. Équipement especially: make the real posed brands
(Canadian Solar, JA Solar, Deye, Huawei, Dyness) and the warranty table read as a confident
technical argument, not a spec dump. Keep "ordres de grandeur — jamais un devis" framing and the
honest ranges. No invented facts. Refresh each page's title/meta-description. Part of the run's single end-of-run self-merge (no per-task merge).

### W39 — Rewrite the service pages (pompage-solaire, batteries-stockage, maintenance-monitoring, financement, nos-solutions) — [x]

> Added 2026-06-18 via "add to web plan".

Rewrite the newer service pages — pompage-solaire, batteries-stockage, maintenance-monitoring,
financement, nos-solutions — in the STYLE.md voice so each is distinct and genuinely useful, not
filler. Read each first and rewrite prose only, preserving the verified constraints already baked
in: pompage stays a service capability with NO fabricated Taqinor pompage projects/figures and
keeps only the genuine solar-pumping VAT-exemption advantage (not extended to residential PV);
financement stays rentabilité-first and strictly honest — names no bank partner, quotes no rate,
claims no residential VAT exemption; batteries and maintenance draw only from facts already on
the site. Make each read as written by someone who knows the engineering, with varied rhythm and
zero recycled blurbs. Refresh titles/meta-descriptions. Part of the run's single end-of-run self-merge (no per-task merge).

### W40 — Rewrite the trust & story pages (pourquoi-taqinor, marocains-du-monde, garanties, guides hub + seed articles, /faq) + reconcile with à-propos — [x]

> Added 2026-06-18 via "add to web plan".

Rewrite the trust and story pages — pourquoi-taqinor, marocains-du-monde, garanties, plus the
guides hub and its seed articles, and the /faq page — in the STYLE.md voice, and reconcile any
duplication so pourquoi-taqinor (differentiators) and à-propos (founder + method) don't overlap
and are cross-linked. Read each first; keep all verified facts (the warranty figures on
garanties, the FAQ answers, the guide content drawn from existing pages) and rewrite the prose to
be sharp, specific and varied. Turn garanties from a table restatement into a real promise (still
inventing no SLA or underperformance policy). Make the FAQ answers genuinely helpful and human,
not boilerplate. Refresh titles/meta-descriptions. Part of the run's single end-of-run self-merge (no per-task merge).

### W41 — Bring the à-propos founder page to its strongest honest form (approved pedigree) — [x]

> Added 2026-06-18 via "add to web plan".

Bring the à-propos founder page to its strongest honest form using the owner-approved pedigree.
Read the current page first. Name the founder's real, approved background — a docteur-ingénieur
with 10+ years of R&D experience at Huawei, Ericsson and STMicroelectronics — and write a
confident, specific founder narrative explaining why an engineer started a solar company and the
conviction behind "l'étude d'abord" (chaque étude validée par le fondateur). Write only verified
facts: name those three employers and the doctorate/R&D background, but invent NO specific
projects, dates, titles, team sizes, or personal anecdotes — leave the narrative refinable by
Reda/Meryem later. This is the page that answers a skeptical buyer's "they've only done a handful
of jobs" with credentials no competitor can claim. Make it the single most convincing page on the
site within those honesty limits. Refresh title/meta-description. Part of the run's single end-of-run self-merge (no per-task merge).

### W42 — Rewrite the five case-study pages from stat readouts into real narratives — [x]

> Added 2026-06-18 via "add to web plan".

Rewrite the five case-study pages (the realisations/... installation pages) from stat readouts
into real narratives, each distinct, built entirely from published facts (real kWc, measured
production, equipment, city, date, photos): the client's situation, the roof and why it was sized
the way it was, the install, and the measured Deye Cloud result. This is where Taqinor's evidence
moat becomes vivid — make each one a story a buyer remembers, inventing nothing. Cross-link each
to its city page and the relevant segment page. Refresh titles/meta-descriptions. One self-merged
PR.

### W43 — Make the evidence feel alive: restrained CSS scroll-reveal + count-up (perf budget, reduced-motion safe) — [x]

> Added 2026-06-18 via "add to web plan".

Make the evidence feel alive across the site, additively and within the performance budget. First
check whether a CSS-only scroll-reveal / count-up motion system already exists in the repo (from
the earlier v2 / élégance-retenue work); if it does, reuse it, and if not, build a tiny one.
Apply restrained, premium motion: the big real figures (production kWh, kWc, 60–90%, 3–7 ans,
25 ans) count up once from zero on scroll into view with final width reserved (zero CLS);
sections reveal with a gentle fade/translate; present the measured production on the homepage and
case studies as a confident dashboard-style readout that makes "mesuré sur Deye Cloud" tangible.
Motion is CSS/transform/opacity plus one small IntersectionObserver ONLY — no animation library,
no new dependency. Fully respect prefers-reduced-motion (no reveals, no count-up, numbers show
final values) and keep every page fully usable with JS off. Lighthouse held 97–100 on every page.
Part of the run's single end-of-run self-merge (no per-task merge).

### W44 — Fix the site serving multiple versions of itself: homepage shares Header/Footer + HTML revalidates on deploy — [x] (verified, already correct)

> Added 2026-06-18 via "add to web plan".

Fix the site serving multiple versions of itself, which is the most un-world-class thing live
right now: the homepage currently renders an older header/footer (5-item nav, unspaced phone,
bare footer) while sub-pages show the newer Solutions/Ressources nav and full footer. Read how
the homepage and the shared Header/Footer components are wired, make the homepage render the EXACT
same shared Header and Footer as every other page so the whole site is identical, and fix the
cache-on-deploy behaviour so HTML revalidates on each deploy and no page serves a stale document
after a merge (an appropriate Cache-Control on HTML, a cache rule excluding HTML, or a
purge-on-deploy step — whatever fits the existing Worker setup), while leaving long-cache on
hashed CSS/JS/font/image assets untouched. Do not change any other Worker behaviour; /api/* and
the lead pipeline stay exactly as they are. In the report, confirm a fresh deploy now reflects on
/ with no manual purge. Part of the run's single end-of-run self-merge (no per-task merge).

### W45 — Final consistency pass: unique titles/meta, BreadcrumbList sitewide, contextual cross-links — [x] (verified)

> Added 2026-06-18 via "add to web plan".

Final consistency pass: confirm no two pages share an identical title or meta-description after
the rewrites, verify BreadcrumbList structured data sitewide (add where missing), and confirm the
contextual in-body cross-links between équipement, résidentiel/professionnel, the loi-82-21
pages, the city pages, the case studies and the new service pages are present and sensible.
Purely additive; touch no lead-flow code. Part of the run's single end-of-run self-merge (no per-task merge).

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

### W46 — Estimator optimizer: re-solve after EVERY lock (not just the first one or two) — diagnose the stop-after-two cause, fix to full depth — [x]

> Added 2026-06-18 via "add to web plan".

Work **IN PLACE on the current latest private preview route `/preview/toiture-3d-pro-N`** — read the
repo to find the highest N (the version being tested on the phone) — and leave the
**immediately-prior route byte-for-byte intact** as a baseline; **do NOT spawn a new route** for this
fix. The live constrained optimizer currently re-solves correctly for the first one or two locked
options but **STOPS re-optimizing once a third or later option is set** — it must re-solve after
**EVERY** lock, for **any number** of accumulated locks, all the way until the user has locked every
axis.

**Do:**

1. **First read `estimatorBrain.ts` and wherever the lock state and the re-solve are wired, and
   DIAGNOSE the real reason it stops after two — do NOT assume the cause** (a hard-coded depth, a
   state update that only fires for the first locks, a loop bounded at two axes, a memo that doesn't
   re-run, a stale closure, etc.) — **and report what it actually was.**
2. Fix it so that **every time the user locks any axis** (orientation/azimuth, tilt, layout
   portrait/paysage, roof-edge margin/setback, panneaux-nécessaires target — whichever the route
   exposes) the optimizer **IMMEDIATELY re-solves over ALL still-AUTO axes holding EVERY locked axis
   fixed**, maximizing total annual generation (placed × kWc × the PVGIS specific yield at the exact
   GPS, placed = min(needed, fits), the needed-panel cap always respected), and updates the displayed
   values, the 3D, and every result — and this continues identically for the 3rd, 4th, 5th… lock
   until nothing is left to float.
3. Setting a new value on an **already-locked axis just updates that lock**; **Réinitialiser clears
   all locks**; the per-axis **"Recommandé" still shows the freed-axis optimum given the current
   locks**.

**Tests:** re-solve fires on the 3rd, 4th and Nth successive lock (not just the first two);
accumulating locks holds all of them while only AUTO axes move; the sequence terminates correctly
when every axis is locked. **One self-merged PR.**

---

### W47 — Pitched-roof flow: add "alignée toit" flush-coplanar as the default/forced orientation + drop the physically-impossible orientations — [x]

> Added 2026-06-18 via "add to web plan".

Same route, **in place** (current latest `/preview/toiture-3d-pro-N`, the immediately-prior route
left byte-for-byte intact). The non-flat (pitched/tiled) flow currently offers some orientation
options but is **MISSING "alignée toit"** — flush panels lying coplanar on the roof slope — which is
the physically-correct mode for a flush install.

**Do:**

1. **First read the pitched flow and REPORT exactly which orientation/options it currently offers.**
2. Make **"alignée toit" present and the default/forced orientation for a pitched roof**: the array
   follows the roof's own facing, every panel **coplanar with the roof plane** (panel normal =
   roof-plane normal), **tilt = the roof pitch** (roof-determined, never an optimizable axis),
   **azimuth = the way the roof faces**.
3. **Remove or mark "non applicable"** any orientation that is physically impossible for a flush panel
   on that route (true-south rotate, est-ouest tents — a flush panel cannot be turned off the roof
   plane).
4. **Preserve the existing flush coplanar 3D exactly:** no triangular racks, no standing frames, no
   inter-row gaps, every panel corner inside the traced polygon and on the plane.
5. Production for the pitched roof stays **PVGIS at the single (pitch, facing) pair with
   `mountingplace="building"`**. The free axes the pitched optimizer floats remain **layout
   (portrait/paysage), margin/setback, and panneaux-nécessaires**, with the **same live re-solve to
   the last lock** from W46.

**Tests:** "alignée toit" is present and default on the pitched flow; the impossible orientations are
not offered; the flush coplanar layout is unchanged (every panel normal = the roof-plane normal);
production uses `mountingplace="building"`. **One self-merged PR.**

---

### W48 — Harden BOTH optimizers (flat + pitched): exhaustive defensive handling + fuzz/property tests — [x]

> Added 2026-06-18 via "add to web plan".

Same route, **in place**. Harden **both engines** — the flat optimizer and the pitched optimizer — to
be robust and exhaustively tested, **without changing any correct behaviour.** Read the engines and
add defensive handling plus tests for every failure and edge case constructible:

- degenerate roof traces (zero or near-zero area, self-intersecting or non-convex polygons, slivers);
- obstacles covering all or most of the roof;
- a roof too small to fit even one panel;
- a needed-panel cap of zero or a huge value;
- every orientation×layout×tilt combination composing with **no NaN / Infinity / negative count**;
- PVGIS returning errors / timeouts / malformed / empty payloads → **graceful fallback to the
  in-house solar-geometry estimate labelled "estimé", never a crash or a blank number**;
- the PVGIS azimuth-sign mapping (**SOUTH=0, EAST=−90, WEST=+90, NORTH=180**) correct in all four
  quadrants;
- the physical bounds ALWAYS holding (Σ panel footprints ≤ usable area; placed = min(needed, fits) ≤
  needed; E-W count ≥ same-tilt south; savings ≤ avoidable energy cost; surplus uncompensated);
- locks accumulating to full depth under fuzzed lock orders;
- the pitched-specific invariants (no tilt axis, orientation fixed to alignée toit, coplanar panels).

Add **property-based / fuzz tests** where they help (random roofs, random lock orders, random configs)
asserting the invariants never break.

**Tests:** full Vitest suite green; **report the final test count and the categories covered.**
**One self-merged PR.**

---

### W49 — Server-side PVGIS production-data engine (yearly / monthly / typical-day / specific-date / daily) — [x]

> Added 2026-06-18 via "add to web plan".

Same route, **in place**. Build a **server-side PVGIS production data engine** that turns the current
config into precise produced-electricity figures at multiple timescales. **CRITICAL: PVGIS rejects
browser/AJAX (CORS) requests, so ALL PVGIS calls MUST be server-side** — read the repo to find how
PVGIS is currently called (it must already be server-side, since browser CORS is blocked) and
**reuse that existing server-side PVGIS path + cache**; do NOT call PVGIS from client JS. Use the
**SAME PVGIS endpoint/version the optimizer already calls** so the window's numbers are consistent
with the optimizer's — confirm which version it is and **do NOT switch the radiation
database/version** (that would silently shift every existing number).

**Compute**, for the exact roof GPS and the current plane (tilt, azimuth, mountingplace = "free" flat
/ "building" pitched), all normalized **per 1 kWc** and then **scaled by the placed system size**
(placed_panels × 0.72 kWc per the Canadian Solar 720 W panel):

- (a) **yearly** production in kWh/an;
- (b) the **12 monthly** production totals in kWh/month;
- (c) the **"typical day" hourly PV-power profile for each month** = the average over all days of that
  month across PVGIS's multi-year record (24 values);
- (d) a **specific calendar date's** hourly profile = that date averaged across the available years (a
  "typical 15 mars", avoiding any single-year arbitrariness);
- (e) **daily** production totals in kWh/day from the hourly profiles.

**Endpoints (verify against current PVGIS docs; pick the minimal-call accurate combination):** PVcalc
returns the monthly + annual averages in one call; DRcalc returns the average daily profile for all 12
months in one call; seriescalc with `pvcalculation=1` returns the full multi-year hourly PV power from
which the typical-day average, any specific date, and the daily/monthly/yearly aggregates can all be
derived — production scales linearly with kWc (query at 1 kWc, scale afterward). **Cache** every PVGIS
result per rounded (lat, lon, tilt, azimuth, mounting) so re-renders and config tweaks are instant and
stay well inside the 30-calls/sec limit. **Reconcile** the timescales so the monthly totals and the
typical days are mutually consistent with the annual figure, and **state the chosen reconciliation.**
Savings, if shown anywhere in this window, reuse the engine's **EXISTING honest capped model**
(self-consumption only, surplus uncompensated in Morocco, never production × tariff uncapped) — invent
no savings number. **Degrade gracefully** to the in-house "estimé" production if PVGIS is unreachable,
clearly labelled.

**Tests:** per-kWc → scaled-by-kWc linearity; typical-day = month-average; specific-date = cross-year
average for that date; monthly/annual reconciliation; the azimuth-sign mapping; mounting "free" vs
"building" by roof type; cache hits avoiding duplicate calls; graceful fallback. **One self-merged
PR.**

---

### W50 — Interactive "Production estimée" window (Année / Mois / Jour) driven by the production engine — [x]

> Added 2026-06-18 via "add to web plan".

Same route, **in place**. Build the interactive **"Production estimée" window** driven by the W49
production data engine and the current optimizer config — it shows the produced electricity for the
real system on the real roof and lets the client explore it.

**Do:**

- A **scope toggle — Année / Mois / Jour.**
  - **Année:** 12 monthly bars (kWh/month) plus the annual total.
  - **Mois:** the selected month's daily production (and/or its typical-day curve) plus the month
    total, with a month picker and prev/next to cycle all 12 months.
  - **Jour:** a 24-hour PV-power curve for the selected day plus that day's kWh — the day **DEFAULTS
    to the selected month's "typical day"** (the month-average profile), and the client can pick a
    specific calendar date and cycle days with prev/next.
- The window reflects the current config and is **editable in place:** the client can adjust the panel
  count (kWc updates) and the figures recompute from the engine; the layout and the GPS come from the
  traced roof / optimizer so the production is position-correct and precise to the real area.
- Show the headline numbers (kWh/an, selected-month kWh, selected-day kWh) and, if savings are shown,
  the **capped honest** monthly/daily savings clearly framed as estimates.
- **French UI copy in the site voice; numbers in site format** (space thousands separator, unit after,
  "~" where appropriate).
- Render the graphs with **lightweight inline SVG — NO chart library, NO new dependency** (the data is
  tiny: 12 bars, 24-point curves, ~31 daily bars). All graphs render from cached engine data so
  cycling months/days is instant.
- **Reduced-motion fully respected** (no animated draw-in; final values shown), **zero layout shift**
  (reserve graph space), **Lighthouse held 97–100.**
- Because the build agent cannot render the map or the charts, anchor correctness to **code-checkable
  logic and tests** (the right series length, the typical-vs-specific-day selection, the kWc scaling,
  the month/day cycling bounds) rather than to appearance — the final visual check is on the phone.

**Tests:** the scope toggle yields the right series; month cycling wraps correctly across all 12
months; the day defaults to the typical day and a picked date overrides it; editing the panel count
rescales every figure; savings (if shown) never exceed the capped value. **One self-merged PR.**

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
- 2026-06-17 — W20 done (estimator brain v4 — PVGIS source of truth + fine-grid TRUE optimum, flat
  roofs): new private `/preview/toiture-3d-pro-7` (noindex, sitemap-excluded, unlinked, lazy-loaded),
  a clone of pro-6 on a NEW pure engine `src/lib/estimatorBrainV4.ts` that COMPOSES on V2/V3 without
  editing them (pro-3/4/5/6 byte-for-byte intact — proven by tests). What changed: the recommended
  optimum is no longer the best of a few table rows but the TRUE maximum of a fine grid (tilt ≈ 5°→35°
  in 5° steps + the table-optimal tilt, azimuth {plein-sud, aligné-toit, Est-Ouest}, portrait/paysage,
  marge keep/remove), each config capped at the bill-derived need and scored on PLACED energy. Each
  candidate is now scored on the SPECIFIC YIELD (kWh/kWc/an) read from PVGIS at the roof's EXACT GPS —
  queried once per (tilt, aspect) via the existing `/api/roof-yield` proxy with kWc=1, cached and
  reused across toggles, scaled by kWc afterwards. PVGIS aspect convention enforced (Sud=0, Est=−90,
  Ouest=+90, Nord=180 via `aspectFromCompass`); flat-roof racked panels now request
  `mountingplace='free'` (added as an OPTIONAL param to `roofEstimate`/`roof-yield`, default
  `'building'` → pro-3/4/5/6 unchanged). When the optimum isn't a standard config it shows as its OWN
  labelled row « Optimum calculé — inclinaison X°, orientation Y », badged « Recommandé », with a
  one-line reason and the source (PVGIS · GPS exact / estimé · table committée); the « Optimum » button
  applies it. PVGIS unreachable for a (tilt, aspect) → graceful fallback to the committed yield table,
  labelled « estimé », never an error. The comparison table is kept. No new dependencies. 613 web
  tests green (engine tests: aspect-sign mapping, optimum = true max over the sweep, PVGIS moves the
  winning tilt vs table-only, graceful fallback, candidate pairs; route/preview guards) + `astro build`
  clean (pro-7 generated, confirmed ABSENT from the sitemap). Method recorded in `BRAIN_V4_NOTES.md`.
  Lead form/data flow byte-for-byte untouched. PHONE-ONLY to confirm (build can't render the map): the
  satellite/3D rendering and the on-map optimum row. URL to open: `/preview/toiture-3d-pro-7`.
- 2026-06-17 — W21 done (estimator brain v5 — pitched/tiled roof, roof-type chosen FIRST): new private
  `/preview/toiture-3d-pro-8` (noindex, sitemap-excluded, unlinked, lazy-loaded), a clone of pro-7 on a
  NEW small pure engine `src/lib/estimatorBrainV5.ts` composing on V3/V4 without editing them
  (pro-3..pro-7 byte-for-byte intact — proven by tests). Deltas: (1) ROOF-TYPE STEP FIRST — « Toit plat
  / Toit en pente (tuiles) » is now Étape 2, BEFORE the address + trace (chips share `data-rooftype`
  with the config panel, both wired); flat keeps the W20/V4 fine-grid PVGIS optimizer byte-identical.
  (2) Pitched stays the V3 flush-coplanar model (panels FLAT on the slope, tilt = pitch, azimuth =
  facing, both IMPOSED, no inter-row spacing) with the pitch USER-SUPPLIED (presets now 15/22/30/**45**°
  + 5–45° slider) and facing confirmed on the map compass. (3) PITCHED PRODUCTION = PVGIS source of
  truth at the single (pitch, facing) pair, pose `mountingplace='building'` (flush panels run hotter →
  honest slight de-rate), queried via `/api/roof-yield` (one leg, kWc=1, cached per pitch|facing,
  scaled by kWc), with graceful fallback to the committed table labelled « estimé » — coverage + savings
  recomputed consistently from the PVGIS figure. Single primary plane (multi-plane deliberately out of
  scope). No new dependencies. 629 web tests green (V5 engine: 45° preset, `building` mounting, one-leg
  PVGIS at (pitch, facing) with boussole→aspect sign; pro-8 route/preview guards: roof-type-before-trace
  ordering, 45° chip, PVGIS-building wiring, baselines + `roof-yield` `building` default preserved) +
  `astro build` clean (pro-8 generated, confirmed ABSENT from the sitemap). Method in `BRAIN_V5_NOTES.md`.
  Lead form/data flow byte-for-byte untouched. PHONE-ONLY to confirm (build can't render the map): the
  flush panels lie flat on the slope and align with the satellite roof. CODE-CHECKABLE invariant met
  (panels coplanar at tilt=pitch); the further visual of an INCLINED TEXTURED roof DECK (vs the current
  flat schematic building volume) is the remaining on-phone visual polish, noted honestly. URL to open:
  `/preview/toiture-3d-pro-8`.
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
- 2026-06-17 — W22 done (estimator brain v6 — TRUE sloped pitched roof + full optimizer matrix
  displayed): new private `/preview/toiture-3d-pro-9`, cloned from the highest existing route
  (pro-8, confirmed from the repo) with pro-3..pro-8 left byte-for-byte intact. New pure module
  `estimatorBrainV6.ts` (composes on V2/V4/V5, no edits to them). FIX 1 — pitched roofs now render
  as a real INCLINED PLANE: the roof surface itself tilts (deck vertices lifted via `pitchedDeckZ`,
  the traced photo stays geo-aligned) and panels lie FLUSH/COPLANAR on it (`flushPanelCenterAt`, a
  constant small standoff along the plane normal), with NO triangular racks in the pitched scene
  (kept behind `!flush`) and no inter-row gaps; anchored to code-checkable geometry + tests
  (normal not vertical when pitch>0, every panel coplanar, constant standoff, up-slope panels
  physically higher). FIX 2 — the flat-roof optimizer now sweeps AND DISPLAYS the full matrix
  (`fineGridMatrixV6`): tilt 0→35° in 5°, azimuth south ±45° in 15° + roof-aligned + east-west,
  portrait/landscape, keep/remove margin, PVGIS specific yield at exact GPS (graceful "estimé"
  fallback), shade-free winter spacing kept; every evaluated config rendered in a sortable
  (kWh/an, panels, % bill) and orientation-filterable table with the genuine optimum pinned and
  badged "Recommandé" — replacing the old ~6 named rows. Row click renders that exact config
  (span azimuth included). 666 web tests green (new `estimatorBrainV6.test.ts` +
  `estimatorPreviewPro9.test.ts`); `astro build` clean. Live site + lead form untouched; map key
  read = `PUBLIC_MAPTILER_KEY` (optional `PUBLIC_MAPBOX_TOKEN`). URL: `/preview/toiture-3d-pro-9`.
- 2026-06-17 — W23–W33 done (IA + content pass, one batch). Five NEW public/indexed pages, all on
  the « Cinéma du chantier » design, every fact traced to what the site already publishes (nothing
  invented): **`/pompage-solaire`** (W23 — new service framed as a CAPABILITY, zero Taqinor pumping
  projects/photos/figures; the verified VAT exemption stated for agricultural pumping only and
  explicitly NOT for rooftop residential PV; débit/HMT/forage/besoins method + Service JSON-LD),
  **`/batteries-stockage`** (W24 — Dyness LFP facts reused verbatim from /équipement: DL5.0C, 5 kWh
  modular to 15 kWh+, 6 000+ cycles 90 % DoD, CAN BMS Deye, 10-year warranty; diurnal vs nocturnal
  reasoning from the existing guide; real 15/10/5 kWh installs already published), **`/maintenance-
  monitoring`** (W25 — Deye Cloud + SAV proactif + dossier technique from /garanties; NO invented
  SLA/response time; an honest styled placeholder card for future anonymised dashboard captures),
  **`/financement`** (W26 — rentabilité-first and strictly honest: 3–7 ans payback / 25 ans / 60–90 %
  / barème ONEE reused; Taqinor is NOT a lender, no residential subsidy, NO residential VAT
  exemption, no bank/rate/product named; the étude computes the client's own ROI), and
  **`/nos-solutions`** (W30 — hub listing the 6 solutions, CollectionPage JSON-LD, parent + no-JS
  fallback of the Solutions dropdown). W27: `/à-propos` now names the owner-approved founder pedigree
  (docteur-ingénieur, 10+ ans R&D chez Huawei, Ericsson et STMicroelectronics) + a short honest
  « pourquoi un ingénieur lance le solaire » narrative (no invented projects/dates/titles), kept
  DISTINCT from and cross-linked both ways with `/pourquoi-taqinor`. W28: ONE shared Header on every
  page (homepage already inherits it via Layout) with a new primary nav — **Solutions ▾, Réalisations,
  Équipement, Ressources ▾, À propos** + Diagnostic CTA + +212 6 61 85 04 10. Solutions ▾ = Résidentiel,
  Professionnel, Pompage solaire, Batteries & stockage, Maintenance & monitoring, Régularisation Loi
  82-21 (trigger → /nos-solutions); Ressources ▾ = Guides, FAQ, Loi 82-21 expliquée, Pourquoi Taqinor,
  Financement & rentabilité, Marocains du monde (trigger → /guides). The Loi 82-21 explainer LEFT the
  top nav (still live + indexed + in sitemap; reached via Ressources, footer, and contextual links).
  Dropdowns are accessible: real-link triggers (no-JS fallback), CSS hover + focus-within reveal,
  ArrowDown opens/focuses, Escape closes, ARIA roles/aria-haspopup/aria-expanded. W29: ONE footer
  everywhere — the old non-clickable « Services » text replaced by a **Solutions** column of REAL links
  + a **Ressources** column (réalisations, guides, faq, loi-82-21 expliquée, pourquoi, financement,
  MRE, à-propos, équipement, garanties) + the 5 city links + Contact + legal. W31: a « Nos solutions »
  card section on the homepage (text cards, zero new images → zero CLS) linking the 6 solutions + the
  hub. W32: breadcrumbs confirmed sitewide (all new pages carry Breadcrumb/BreadcrumbList; homepage is
  root), and contextual cross-links completed (segment pages → Pourquoi Taqinor + the new
  solution/finance pages; loi-82-21 ↔ régularisation ↔ professionnel and city ↔ case-studies ↔ segments
  already present). W33: cache-on-deploy fixed — a pure `worker/cache.mjs` forces HTML documents to
  revalidate (`public, max-age=0, must-revalidate`) in the production Worker, so a deploy is reflected
  on `/` without a manual purge, while hashed assets (served asset-first, excluded from the Worker)
  keep their long immutable cache and `/api/*` JSON is byte-for-byte untouched. 706 web tests green
  (added `tests/cache.test.ts` + `tests/ia-nav.test.ts`; updated elevation count 15→20 and seo-pages);
  `astro build` clean (5 new pages prerendered + in the sitemap, preview routes still excluded,
  `cache.mjs` copied into dist/server and wired into redirect-entry). Live lead form + its entire data
  flow byte-for-byte untouched; estimator preview routes stay private. MANUAL (founder, one-time):
  optionally purge the `/` cache once in the Cloudflare dashboard after this deploy; subsequent deploys
  self-refresh. URLs to open: `/pompage-solaire`, `/batteries-stockage`, `/maintenance-monitoring`,
  `/financement`, `/nos-solutions`, `/à-propos`, `/` (new Solutions section + nav/footer).
- 2026-06-17 — W34 done (estimator brain v7 — LIVE constrained optimizer, flat roofs): new private
  `/preview/toiture-3d-pro-10` (noindex, sitemap-excluded, unlinked, lazy-loaded), a clone of pro-9 on
  a NEW pure engine `src/lib/estimatorBrainV7.ts` that COMPOSES on V2 + V6 without editing them
  (pro-3..pro-9 byte-for-byte intact — proven by a test). What changed: instead of re-solving only when
  the user clicked « Optimum », the flat optimizer now re-solves LIVE on every option change. Each
  option is an AXIS (orientation: plein sud / aligné toit / Est-Ouest · inclinaison 0–35° · pose
  portrait/paysage · marge de rive garder/pleine rive · panneaux nécessaires). Default = every axis
  AUTO → the global optimum, each group badged « Recommandé ». Locking an axis HOLDS it and immediately
  re-solves every still-AUTO axis to maximise total annual generation; locks ACCUMULATE; re-clicking a
  locked value (or the reco/auto chip) re-floats that one axis; « Réinitialiser » (the old Optimum
  button, relabelled) releases all locks. Each group shows its « Recommandé » value = what that axis
  would take if freed with the other current locks held (so the user sees they picked X but Y is
  recommended). « Highest generation » = placed × kWc × the PVGIS specific yield (kWh/kWc/an) at the
  roof's EXACT GPS for that tilt+azimuth (never a generic factor; shared v4YieldCache, coarse-then-fine
  fetch, graceful « estimé » table fallback), with placed = min(needed, what fits) so the needed-panel
  cap is always respected. PVGIS aspect-sign convention (S=0/E=−90/O=+90/N=180) reused via V2's
  aspectForAzimuth. The full V6 matrix table is kept. `renderSelection()` became an alias of the live
  solver so all existing call-sites route through it; the 3D render path, obstacles, the need control,
  and the pitched-roof model (unchanged from pro-9 — W35 will add the live optimizer there) are
  preserved. 770 web tests green (new `estimatorBrainV7.test.ts` 19 cases: true max over the sweep,
  lock-holds-while-others-reoptimize, accumulating locks + reset, per-axis recommended = freed-axis
  optimum, PVGIS azimuth-sign mapping, generation formula + cap never exceeded, graceful fallback; plus
  `estimatorPreviewPro10.test.ts` route/wiring guards; `roof-preview.test.ts` heavy-import lists updated
  for pro-10). `astro build` clean (pro-10 generated, confirmed ABSENT from the sitemap, noindex). Live
  site + lead form byte-for-byte untouched; map key read = `PUBLIC_MAPTILER_KEY` (optional
  `PUBLIC_MAPBOX_TOKEN`). PHONE-ONLY to confirm (build can't render the map): trace a roof, change one
  option and watch every other option re-optimise live to the highest-generation combination. URL to
  open: `/preview/toiture-3d-pro-10`.
- 2026-06-18 — W35 done (estimator brain v8 — SAME live optimizer for PITCHED/tiled roofs): new private
  `/preview/toiture-3d-pro-11` (noindex, sitemap-excluded, unlinked, lazy-loaded), a clone of pro-10 on
  a NEW pure engine `src/lib/estimatorBrainV8.ts` that COMPOSES on V2 + V3 (`packFlushPlane`) without
  editing them (pro-3..pro-10 byte-for-byte intact — proven by a test). The pitched roof now gets the
  IDENTICAL live constrained optimizer as the flat roof (W34), with exactly two physics-forced
  differences: (1) NO tilt axis — a flush panel's tilt EQUALS the roof pitch; (2) orientation is fixed
  to « aligné toit » — a flush panel can't face true-south or form east-west tents, so plein-sud / E-O
  are omitted. The FREE axes in pitched mode are therefore pose (portrait/paysage), roof-edge margin
  (garder/pleine rive) and the panneaux-nécessaires target: locking one holds it and re-solves the rest
  live to maximise generation; locks accumulate; re-clicking a locked value re-floats it; « Réinitialiser »
  releases all; each group shows its « Recommandé » value (the freed-axis optimum with the other locks
  held). Production = placed × kWc × the PVGIS specific yield at the single (pitch, facing) pair for the
  exact GPS, pose `mountingplace='building'` (flush panels run hotter → honest slight de-rate), shared
  cache, graceful « estimé » table fallback. A north-facing slope places zero panels (honest, flagged).
  The flush COPLANAR layout and the pitched 3D (inclined deck, no racks, no inter-row gaps) are byte-for-
  byte the pro-9/V6 model — unchanged. The flat-roof path (W34/V7) is untouched and still live. The page
  now shows the pose + marge controls in BOTH modes (they're the pitched free axes), with the flat-only
  orientation/tilt/azimuth controls hidden in pitched (#rp9-flat-only); a small pitched comparison table
  (pose × marge, ≤4 rows) reuses the matrix table with the optimum badged, and the flat matrix paint is
  guarded off in pitched. 781 web tests green (new `estimatorBrainV8.test.ts` 12 cases: no tilt/orientation
  axis, lock-holds-while-others-reoptimize, accumulating locks + reset, per-axis recommended = freed
  optimum, generation = placed×kWc×PVGIS(building) with the cap never exceeded, graceful fallback, north-
  facing → zero, flush layout unchanged; plus `estimatorPreviewPro11.test.ts` route/wiring guards;
  `roof-preview.test.ts` heavy-import lists updated for pro-11). `astro build` clean (pro-11 generated,
  confirmed ABSENT from the sitemap, noindex). Live site + lead form byte-for-byte untouched; map key
  read = `PUBLIC_MAPTILER_KEY` (optional `PUBLIC_MAPBOX_TOKEN`). PHONE-ONLY to confirm (build can't render
  the map): trace a pitched roof, watch the panels lie flush on the slope, then change the pose/marge and
  watch the rest re-optimise live. URL to open: `/preview/toiture-3d-pro-11`.
- 2026-06-18 — W36 done (site-voice governance, docs only): new `apps/web/STYLE.md` is now the
  editorial voice reference for every page and every future session. It defines the target buyer (an
  affluent, skeptical, technically-literate Moroccan committing 80 000+ MAD to a 25-year loi-82-21
  asset), the voice (an engineer's restraint — lead with the real number, concrete over adjectival,
  vary rhythm page to page, native French, no eco-hype, zero invented facts), and the two hard rules:
  (1) each signature phrase appears AT MOST ONCE site-wide (ideally only on the homepage), every other
  page re-expressing the idea freshly — CTAs/footer/nav/legal/JSON-LD exempt; (2) every city/segment/
  service page carries ≥1 concrete fact unique to it. Includes an evidence-based phrase ledger
  (measured live: « Production mesurée » trio on 9 pages, « kit standard » 7, « jamais l'inverse » 4,
  « docteur-ingénieur » 3) assigning each recycled formula a single canonical home + alternative
  phrasings so the W37–W42 rewrites have an actionable de-dup map. No page changed in this task.
- 2026-06-18 — W37 done (five city pages, no two share a paragraph): the city route was one template
  rendering identical prose for all five cities (only name/intro/sunshine differed). Moved the prose into
  a NEW data module `src/lib/cityContent.ts` (per-slug hero lead, ensoleillement context, three
  per-city service blurbs, closer, unique title + meta) and rewired `installation-solaire-[city].astro`
  to render it — keeping `getStaticPaths`, the Service+areaServed JSON-LD, the inCity/nearby/closest
  realisation logic, the data-tally figures, V2Enhance, Breadcrumb, Article33Ribbon, CtaBand untouched
  (`realisations.ts` left read-only). Each city now leads with a fact unique to it: Casablanca its real
  local chantier (11,36 kWc · 14 271 kWh/an mesurés), Rabat administrative capital ≈ 2 900 h, Marrakech
  among the sunniest ≈ 3 000 h (so the page warns against surdimensionner), Tanger explicitly the lowest
  ≈ 2 800 h, Agadir the sunniest ≈ 3 400 h. Recycled formulas (« jamais l'inverse », « kit standard »,
  the identical trio, « mérite une étude sérieuse ») removed and re-expressed per city; « ≈ » sunshine
  honesty and « chantiers les plus proches » kept; no electricity operator named; no invented numbers.
- 2026-06-18 — W38 done (three core sales pages rewritten to the STYLE.md voice): résidentiel,
  professionnel and équipement now each open on a fact and read in their own rhythm. Résidentiel leads
  on three-input dimensioning (ONEE bill · peak hours · roof orientation → 60–90 % coverage) anchored by
  réf. 400 (11,36 kWc / 14 271 kWh), keeping its price bands with real refs. Professionnel leads on the
  El Jadida case (17,04 kWc → 21 406 kWh/an) and a 3–5-year payback, then the segment-specific loi-82-21
  raccordement threshold. Équipement is reframed from a spec dump into a technical argument — each posed
  brand (Canadian Solar, JA Solar, Deye, Huawei, Dyness) carries its engineering reason and the warranty
  table (12/25/10/20/2 ans) becomes « a guarantee is only worth the dossier that documents it ». Every
  recycled formula removed (« jamais l'inverse », « kit standard », the trio, « validée par le fondateur »
  — now at-home on à-propos) and no banned adjective; all real figures, refs, GarantiesTeaser, JSON-LD,
  V2Enhance/Breadcrumb and links preserved; nothing invented.
- 2026-06-18 — W39 done (five service pages rewritten, each distinct and useful): pompage-solaire leads
  on the genuine agriculture-only fact (solar pumping is TVA-exonéré, pump + panels — explicitly NOT
  residential PV) and keeps its débit/HMT/forage method with no fabricated pumping project. batteries-
  stockage leads on the published Dyness LFP spec (6 000+ cycles à 90 % DoD, 5 kWh-modular, CAN BMS with
  Deye, 10-year warranty). maintenance-monitoring leads on the Deye Cloud reality (real-time production,
  history, alerts, client access) with NO invented SLA. financement stays rentabilité-first and strictly
  honest (3–7 ans / 25 ans / 60–90 % / barème ONEE; no bank, no rate, no residential VAT exemption,
  Taqinor not a lender). nos-solutions keeps its CollectionPage JSON-LD and six links, each summary
  rewritten concrete and distinct. Recycled formulas removed; all JSON-LD '@type', V2Enhance/Breadcrumb
  and links preserved; nothing invented.
- 2026-06-18 — W40 + W41 done together (trust & story pages + the founder page, sharing à-propos).
  W40: pourquoi-taqinor, marocains-du-monde, garanties, the guides hub + its 3 seed articles, and /faq
  rewritten in the STYLE.md voice. pourquoi-taqinor is now PURELY the differentiators list (the founder/
  docteur-ingénieur claim stripped out of it and pointed to à-propos); garanties turned from a table
  restatement into a real promise (84,8 % at 25 years made the load-bearing fact, no invented SLA);
  FAQ answers made human and specific while keeping every figure and adding no financing/bank/tax
  question; faq.astro keeps `<Faq items={faq}>` with no schema={false} and no inline FAQPage (single
  FAQPage preserved). W41: à-propos brought to its strongest honest form on the owner-approved pedigree
  (docteur-ingénieur, 10+ ans R&D chez Huawei, Ericsson et STMicroelectronics) with a deepened « why an
  engineer started a solar company » narrative and « il valide personnellement chaque étude » — no
  invented project/date/title/anecdote. pourquoi-taqinor and à-propos are now distinct and cross-linked
  both ways. All three guides keep their Article JSON-LD; every marker/figure preserved.
- 2026-06-18 — W42 done (five case studies turned from stat readouts into narratives): the [slug] route
  rendered the same generic shape for every study. Added a NEW per-slug narrative module
  `src/lib/caseStudies.ts` (unique title/meta + situation/sizing/install/result built ONLY from the
  published facts) and rewired `realisations/[slug].astro` to render it — keeping `getStaticPaths`, the
  Article JSON-LD, V2Enhance/Breadcrumb, the real photos with alts, and all fact bindings with their
  null-guards (`realisations.ts` left read-only). Each study leads with its own measured number (17,04
  kWc → 21 406 kWh/an; 11,36 → 14 271; 5,68 → 7 135; etc.) and cross-links to its segment page
  (/résidentiel — all five are residential) and to the relevant service city (/installation-solaire-
  casablanca; El Jadida and Nouaceur, off the five service cities, point to the nearest same-region
  service city honestly). No null field is ever printed: réf. 134 names no onduleur/battery, Nouaceur
  states no production is published. No invented client name, quote, date or figure; no « témoignage ».
- 2026-06-18 — W44 verified ALREADY CORRECT (no code change). The homepage (`index.astro`) renders
  entirely through the shared `Layout` (imports Layout, wraps all content in `<Layout …>`), and that
  Layout renders `<Header />` + `<Footer />` — so the homepage already shows the identical
  Solutions/Ressources nav, the formatted +212 6 61 85 04 10 and the full footer as every sub-page;
  there is no inline older header/footer in index.astro. HTML revalidation on deploy is already in place:
  `worker/cache.mjs` exports `HTML_CACHE_CONTROL = 'public, max-age=0, must-revalidate'` and applies it
  only to GET/HEAD text/html responses (wired in `worker/redirect-entry.mjs`), while `astro.config.mjs`
  keeps `_astro`/photos/videos/fonts/og served asset-first with their immutable long cache and `/api/*` +
  the lead pipeline untouched. Both W44 concerns were already satisfied by W17 and W33 — nothing to fix.
- 2026-06-18 — W43 done (evidence feels alive — verified existing system + closed the one gap). The
  CSS-only scroll-reveal + count-up engine already exists (`V2Enhance.astro`: an IntersectionObserver
  that reveals `.v2-rise` and counts `[data-tally]` up from zero, French-formatted, width locked for
  zero CLS, the whole thing behind `if (!reduce)` for prefers-reduced-motion; no animation library, one
  observer). It is already applied to the big figures site-wide — homepage hero stats (43,48 kWc /
  60–90 % / 3–7 ans / 25 ans / 0 MAD), the evidence-gallery cards (kWc + production), and the case-study
  production `<dl>` dashboard (kWc + measured kWh/an) all count up and reveal. The only marquee figures
  not yet animated were on the homepage « Dernière installation livrée » readout, so 17,04 kWc and
  21 406 kWh/an now carry `data-tally` too — completing the measured-production dashboard feel. Two
  presentational attributes only; the DiagnosticForm fields/validation/fetch/data flow are untouched.
  Reduced-motion still fully kills motion; zero new dependency; Lighthouse unaffected.
- 2026-06-18 — W45 verified (final consistency pass, no code change needed). Built the site fresh and
  audited the 34 public pages programmatically: (1) TITLES — zero duplicates; (2) META DESCRIPTIONS —
  zero duplicates (the W37–W42 rewrites gave every page a unique, page-specific title + description).
  (3) BreadcrumbList — present on every content-hierarchy page (cities, case studies, guides + articles,
  segment, service, trust pages); the only pages without are the homepage (it is the root — a one-item
  breadcrumb is meaningless), /contact (the live lead-form page — left untouched per « touch no
  lead-flow code »), and the two legal pages (mentions-legales, politique-de-confidentialite), which are
  deliberately sober by existing design (they sit outside the .v2 elevated treatment and the content
  hierarchy) — a conscious exclusion, not a gap. (4) CONTEXTUAL CROSS-LINKS — confirmed the full graph
  survived the rewrites and is sensible: équipement ↔ résidentiel/professionnel; segment pages →
  équipement + services (pompage, batteries, financement) + pourquoi-taqinor + garanties; loi-82-21 ↔
  regularization-article-33 ↔ professionnel (bidirectional); case studies → their city page + segment +
  équipement + the réalisations hub; service pages → segments + équipement. The build proved there are
  zero dead internal links. Nothing to add or fix.
- 2026-06-18 — W46–W50 done (one run, IN PLACE on the existing private route `/preview/toiture-3d-pro-11`;
  pro-3..pro-10 left byte-for-byte intact). Built with maximum-safe parallelism: 2 concurrent worktree
  lanes (Lane A = W46→W47→W48 on the optimizer engines + the page script; Lane B = W49 on a new
  server-side production engine, disjoint files), then W50 in a wave-2 worktree on top of the folded
  result; one self-merge to main. **W46:** the live optimizer already re-solved over all locks — the real
  defect was the tilt "Recommandé" button handler in `roof-tool-pro11.ts`, which called `pinned.clear()`
  and reset every axis, wiping ALL accumulated locks (so after a couple of locks the screen reverted to
  the global optimum). Fixed to `pinned.delete('tilt')` so freeing one axis HOLDS every other lock and
  only re-optimizes the freed one; re-solve is now correct on the 3rd/4th/Nth lock and terminates when
  all axes are locked. **W47:** the pitched (toit en pente) flow now surfaces « Alignée toit » as a
  present, default, FORCED read-only orientation (panels coplanar, tilt = roof pitch, azimuth = roof
  facing); the physically-impossible orientations (true-south rotate, est-ouest tents, the azimuth group)
  are confined to the flat-only block hidden in pitched mode; production stays PVGIS at the single
  (pitch, facing) pair with `mountingplace="building"`; the flush coplanar 3D is unchanged. **W48:** both
  engines hardened at engine level only (no V2/V3 edits) — every resolved yield (incl. the committed-table
  fallback) routed through a `safeYield` (finite & ≥ 0), a real NaN leak in V8 fixed, fit-count/kwc/annual
  clamped; +42 fuzz/property + hardening tests (degenerate/self-intersecting/zero-area traces, obstacles
  covering the roof, a roof too small for one panel, need-cap 0/huge, PVGIS NaN/Inf/negative/null/empty →
  graceful « estimé » never a crash, the azimuth-sign mapping S=0/E=−90/O=+90/N=180 in all four quadrants,
  invariants holding under randomized lock orders). Valid-input behaviour unchanged. **W49:** new
  server-side PVGIS production-data engine — new `src/lib/productionEngine.ts` + new `/api/roof-production`
  route + additive PVGIS helpers in `roofEstimate.ts` (monthly PVcalc, multi-year hourly seriescalc, DRcalc
  shape fallback; existing `fetchPvgisAnnualKwhAtTilt` untouched, same v5_2 API + radiation DB). Computes
  yearly / 12 monthly / per-month typical-day hourly / specific-date / daily, all per 1 kWc then scaled by
  placed × 0,72 kWc (Canadian Solar 720 W); cached per rounded (lat, lon, tilt, azimuth, mounting);
  reconciliation anchors the hourly shapes to PVcalc E_m/E_y so typical-day → daily → monthly → annual stay
  consistent; graceful « estimé » fallback; ALL PVGIS calls server-side (browser CORS blocked). **W50:**
  the interactive « Production estimée » window on pro-11 (Année = 12 monthly bars + annual total; Mois =
  daily bars + month total with prev/next; Jour = a 24-h PV-power curve defaulting to the month's typical
  day, with a specific-date picker), hand-built inline SVG (no chart library, no new dependency), reading
  the live optimizer config (GPS/tilt/aspect/mounting/placed); editing the panel count rescales every
  figure client-side via the engine helpers (no extra server call); reduced-motion respected, zero layout
  shift; savings reuse the existing capped self-consumption model; the client only ever calls
  `/api/roof-production`. No new dependencies; route stays private (noindex, not in nav, sitemap-excluded,
  unlinked); live public site + lead form byte-for-byte unchanged. Full vitest suite 1299 green across 48
  files; `astro build` + `tsc` clean. PHONE-ONLY to confirm (build can't render the map/3D): on
  `/preview/toiture-3d-pro-11` lock 3–4 options on a flat roof and watch each re-optimize; switch to
  pitched and confirm « Alignée toit » is the flush default with no racks/inter-row gaps; open the
  Production window, cycle months/days, and compare a typical day vs a picked date; confirm PVGIS returns
  real data for a Moroccan address. Map key read = `PUBLIC_MAPTILER_KEY` (optional `PUBLIC_MAPBOX_TOKEN`).
