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
