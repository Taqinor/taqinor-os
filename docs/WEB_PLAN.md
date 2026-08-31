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
- **RULE A (founder):** The founder NEVER appears on the homepage as a portrait or a personal
  "I sign every study" section. His photo, story and philosophy live ONLY on the dedicated
  /à-propos page. The homepage may carry at most a SUBTLE institutional expertise cue —
  credentials, not a face (e.g. "études conçues par des ingénieurs — expertise R&D télécom /
  ex-Huawei-Ericsson-STMicro") — linking to /à-propos. Do not add a founder portrait or
  signature block to index.astro in any locale.
- **RULE B (no install count):** NEVER publish or foreground the NUMBER/COUNT of installations
  anywhere public (a small count reads as "just started"). Proof leads with magnitude + verified
  quality that don't telegraph the job count — total kWc installed, total measured production
  (kWh), CO₂ avoided, per-project documented/visitable/monitored installs, warranties,
  engineering pedigree. Honesty rule still holds (never fabricate) — the point is to never
  FEATURE the countable installations figure. Revisit only when the count is genuinely
  impressive (hundreds+).

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

### WJ117–WJ126 — 4 MODES + RÈGLE ANTI-CONCURRENT + DÉFAUTS VÉRIFIÉS (fondateur 2026-07-16 ; recherche 5 volets + audit adversarial)

*Même commande fondateur. Défauts constatés (audit + capture d'écran fondateur) : cases de
choix sans état sélectionné VISIBLE (bug cascade layers CSS confirmé Tailwind v4 : `.cine-card`
non-layered bat le layer utilities Tailwind, global.css:386-405 ; VÉRIFIÉ — aucun sélecteur
`[aria-pressed]` CSS sur `.cine-card`/`.mt-*` (il en existe 2 SEULEMENT sur `.rp9-*`,
preview/toiture-3d-pro-11.astro:1013/1215)) ; 3D proposition sur fond bleu nuit = le fond CSS
`.roof3d-stage` var(--color-azur-950,#0a1a33) [token].astro:3405 (la scène Three.js est
transparente, setClearColor 0,0 viewerOnly.ts:716), sans photo satellite : [token].astro:2921
appelle createRoofViewer SANS roofImage, et buildPublicRoofImageSpec (export viewerOnly.ts:280 ;
usage doc :1-36) n'est JAMAIS appelé dans le fichier ; commentaire :305 « backend n'expose pas
roof_layout » PÉRIMÉ — QJ26 l'expose (public_views.py:517 via `_safe_roof_layout`), test
test_qj26_roof_layout_proposal.py présent ; adaptateur [lng,lat]→[lat,lng]
requis) ; courbe journalière générique double-gaussienne (proposalCurve.ts:46-52) alors que
BASELINE_SHAPE marocaine (soirée dominante, applianceConsumption.ts:111-116) existe déjà ;
aucun simulateur batterie (sans/avec = 2 presets). RÈGLE FONDATEUR (anti-concurrent,
2026-07-16) : le document d'estimation détaillé N'EST PLUS rendu pendant la saisie publique —
la beauté vit sur la page tokenisée + les PDF.*

**GARDE DE COMPOSITION (convention « attend <ID> »).** WJ122/WJ123 (@after QX51), WJ124
(@after QX48) et WJ126 (@after QX49) dépendent de tâches BACKEND (PLAN2) qu'un run « work on
the web plan » (édite UNIQUEMENT apps/web) NE PEUT PAS construire — elles restent
`[BLOCKED: attend QXnn]` tant que la QX correspondante n'est pas sur `main` ; ne JAMAIS
hand-roller un substitut backend dans apps/web. WJ117/118/119/120/121/125 sont web-only
(WJ120 @after WJ119 est intra-web).

**SUIVI (revue adversariale Fable, 2026-07-16 — findings non-bloquants de la passe WJ125).**
La passe Fable a bloqué et fait corriger la fuite du compteur de panneaux 3D (WJ125 finding 1,
corrigée dans ce batch). Les findings restants sont notés ici comme tâches de suivi :

- [x] WJ127 — **Repli teaser honnête pour les cas SANS estimation (finding 2, MEDIUM).** Les
  cartes d'erreur/edge (`mt-estimate-toolarge`, `-toolarge-pro`, callback agricole indispo) vivent
  DANS `#mt-doc` désormais masqué : un visiteur industriel à 2 000 000 MAD ne voit plus le message
  honnête « à cette échelle, étude dédiée » — seulement le teaser générique « Recevez votre étude
  complète… ». Parité a11y inversée (le lecteur d'écran reçoit GATED_ANNOUNCE, le voyant non).
  Fix : une variante figure-free du hook teaser pour ces chemins (« votre projet relève d'une étude
  dédiée — un conseiller vous rappelle »), FR/EN/AR, sans divulguer de chiffre. (@lane: web-journey)
  (@model: sonnet)
- [x] WJ128 — **Robustesse prix/capacité du simulateur batterie (findings 3+4, LOW).** Dans
  `proposition/[token].astro`/`batterySim.ts` : (a) si la ligne batterie de l'offre matche le
  mot-clé mais ne porte ni réf ni « N kWh » lisible, `resolveOfferBattery` retombe à 5 kWh tout en
  affichant le prix réel — dissocier « capacité connue » de « prix réel » (afficher « sur étude » si
  la capacité n'est pas sûre) ; (b) `BATTERY_KEYWORDS /batter…/` prend la PREMIÈRE ligne qui matche —
  une ligne accessoire « câble batterie » listée avant le pack gagnerait : préférer la ligne au plus
  gros montant/capacité ; (c) si l'offre quote > 3 unités, le slider (max 3) ne peut jamais afficher
  le prix réel (n === offeredUnits jamais atteint) — élargir le max au nombre offert ou afficher le
  vrai total. (@lane: web-proposal) (@model: sonnet)
- [x] WJ129 — **Durcissements mineurs (findings 5+6, NITS).** `batterySim.ts` : `clamp01` renvoie
  `hi` (1.0, borne la plus optimiste) sur entrée non-finie — le `??` ne rattrape que null/undefined ;
  utiliser le constant par défaut documenté sur NaN (inatteignable des appelants actuels, mais piège).
  Et documenter le décalage sémantique télémétrie : en chemin gaté, `estimation/viewed` se déclenche
  bien que rien de chiffré ne soit rendu, et `contact/reached` au même instant (discontinuité de
  conversion dans les dashboards funnel). (@lane: web-proposal) (@model: haiku)

---

### 2026-07-02 BATTERY — BEST-IN-WORLD SITE & JOURNEY (founder request; 11-agent research fan-out)

**Where this comes from.** Reda asked (2026-07-02) to make taqinor.ma **the best solar-installer
website in the world**, with a clear **list of services**, the quote journey (`/devis/mon-toit`)
**tied tightly to the site** (every quote/study CTA routes through it), and the journey itself
elevated to world-best. An 11-agent parallel fan-out produced this battery: 6 codebase audits (CTA
routing, journey end-to-end, services IA, technical SEO, trust/content readiness, art-director
critique) + 5 web-research agents (world-best solar sites: 1KOMMA5°/Enpal/Otovo/Aira/Palmetto/
Sunrun/Tesla; quote-funnel mechanics: Otovo/Tesla/EnergySage/Aurora/OpenSolar + form-conversion
research; services taxonomy; CRO/trust for WhatsApp-first markets; Morocco market + regulatory
mid-2026). Every task carries a one-line **Why** — the small per-choice explanation Reda asked
for. Key re-verified facts baked in: **ANRE's BT residential net-billing tariff is STILL
unpublished mid-2026** (self-consumption-first framing STAYS); the MT/HT surplus tariff went live
2026 with a 12-month validity window (any figure must carry its window); Google Solar API still
has NO Morocco coverage.

**Cross-cutting constraints (unchanged, every task below):** stay strictly in `apps/web/**`; the
lead webhook contract (validateLead → `/api/capture-lead` → CRM, 1 000 MAD qualify, consent/UTM/
fbclid) keeps working; **no invented numbers** — every figure traces to PVGIS / a confirmed
constant / a cited primary source; savings stay self-consumption-first until ANRE publishes the BT
tariff; all new text **FR + AR** (fus'ha — research: Darija belongs in FAQ phrasing coverage, not
body copy); WhatsApp-first; Lighthouse 97–100, zero CLS, <3 s mid-range Android, reduced-motion
respected; `/internal/` and `/proposition/` STAY private (W245 re-classifies ONLY
`/devis/mon-toit`); scaffolds needing real assets ship flagged `pending real content from Reda`
(see WG5–WG11), never fabricated; **no countdown timers or manufactured urgency ever** (research:
reads cheap on a considered purchase — honest response-time promises + real validity dates only).

**Structural choices made here (the "why" behind the architecture):**
- **Index the journey (W245).** The old "devis tunnel = private end-to-end" sitemap/noindex
  decision predates WJ36 making `/devis/mon-toit` the site-wide primary CTA (87 files point at it
  today). A noindex, sitemap-excluded, footer-absent primary page wastes the site's highest-intent
  keywords ("devis panneaux solaires maroc"). `/internal/` + `/proposition/[token]` remain private.
- **One funnel, not two (W249).** The legacy `DiagnosticForm` (posting to `/api/simulate`) still
  runs live on 12 pages in parallel with the journey — contradicting Reda's "all quote/study
  buttons go through /devis/mon-toit". Consolidate: the journey is the only capture path,
  `/contact` becomes a pure talk-to-a-human page, `/api/simulate` code stays intact (fallback, not
  deleted).
- **Keep existing service URLs.** Research favors a hub-and-spoke services architecture; the site
  already HAS the spokes at root URLs with earned search equity (`/résidentiel`,
  `/pompage-solaire`…). We elevate `/nos-solutions` into the true hub and complete the catalogue
  instead of migrating URLs — same architectural win, zero redirect risk.

---

### WA1–WA37 — TRILINGUAL SITE AUDIT (founder RULE A/B + fact-check + iPhone rendering + battery, 2026-07-04)

*A read-only audit pass (8 parallel research/fact-check/mobile agents + a live iPhone-viewport probe). Every task below corrects a REAL defect verified against the live source or a primary source. IDs are net-new (WA-namespace) to avoid collision with W###/WJ##. Where a task reverses a prior shipped task, that prior task is annotated SUPERSEDED above.*

**STEP 1 — founder RULE A (no homepage founder portrait) + RULE B (no featured install count).**


**STEP 2 — fact-check corrections (each verified against a primary source or a committed constant).**

- [BLOCKED: founder must name the exact JA Solar DeepBlue model (3.0 PERC=25yr/84,8% vs 4.0 n-type=30yr/87,4%)] WA12 — **Give the JA Solar DeepBlue panel a real fiches.ts entry (or correct its inline warranty).** `équipement.astro` describes a JA Solar DeepBlue panel with "garantie performance 25 ans" (no %) but there is NO `fiches.ts` entry for it, so it never got datasheet scrutiny; JA Solar's DeepBlue 4.0/Pro publishes a 30-year linear warranty to ≥ 87,4 %. Add a proper `fiches.ts` entry with the real datasheet link, or correct the inline years/% to the datasheet. **Why:** an unsourced warranty on a named product; brings it under the same datasheet discipline as the other panels. @files: apps/web/src/pages/équipement.astro, apps/web/src/pages/en/équipement.astro, apps/web/src/pages/ar/équipement.astro, apps/web/src/lib/fiches.ts **(CORRECTED 2026-07-04: model-dependent — do NOT blanket-apply 30 yr/87,4 %. Confirm the installed JA model FIRST: JA DeepBlue 3.0 (PERC) = 25 yr / ≥ 84,8 % (so the page's current "25 ans" would be CORRECT), DeepBlue 4.0 (n-type) = 30 yr / ≥ 87,4 %. The Nouaceur install lists "6 × JA Solar" with no model — get the model from the founder, then add the fiches.ts entry with THAT model's datasheet.)**

**STEP 4 — battery honesty (founder hypothesis CONFIRMED for daily self-consumption cycling; see report).**


**STEP 3 — iPhone / Safari mobile rendering (founder-reported). Root cause first, then per-defect.**


### WB1–WB35 — DEEP AUDIT ROUND 2 (Fable frontier pass + 12-agent deep dive, 2026-07-04)

*A deeper "go deep" pass over the SAME site (a Fable adjudication/completeness critic + parallel deep lanes for SEO/i18n, a11y, estimator-math, city pages, content, legal/privacy/security). Every task below is verified against the live source or a primary source, and de-duped against WA1–37. WA1–37 are kept and corrected in place (above), not replaced. Highest-value trust/correctness items first.*

**TRUST & NUMBERS INTEGRITY (highest value — the site's core "measured, not promised" positioning).**

- [BLOCKED: needs the Deye/Huawei distributor warranty certificate to confirm/cite the 10-year term] WB5 — **Confirm the flat "Garantie 10 ans" on Deye + Huawei inverters against the Moroccan distributor's warranty documents (like WA13).** `fiches.ts` + the garanties table publish Deye SUN-…-SG04LP and Huawei SUN2000 at a flat 10 years, but both makers' standard terms vary by market/channel. Attach/cite the distributor certificate; if the local term is shorter, publish the real term or the paid-extension path — never a flat 10 without a source. **Why:** inverters are the component most likely to actually claim warranty within the horizon; no number change without the founder's distributor doc. @files: apps/web/src/lib/fiches.ts, apps/web/src/pages/garanties.astro (+en/ar), apps/web/src/lib/serviceFaq.ts

**FACT / CONTENT ACCURACY.**


**SEO / i18n / LINKS.**


**ESTIMATOR / SOLAR-MATH.**


**ACCESSIBILITY (WCAG 2.2).**


**LEGAL / PRIVACY / CONSENT / SECURITY (all ADDITIVE — the lead webhook contract stays intact; no change to validateLead / the 1000 MAD threshold / the consent-UTM-fbclid fields).**


**WC — iPhone/mobile + i18n fix follow-ups (added 2026-07-04). The fixes themselves are ALREADY CODED on branch `claude/competent-solomon-1449e2` (header overflow, Arabic "TAQINOR" logo flip, hero flash + honest Deye numbers, RTL WhatsApp-glyph mirror, Ken-Burns-mobile-off perf); these are the REMAINING verify/measure items only:**
  - DONE 2026-07-05: the W323 gate (`apps/web/scripts/lighthouse-gate.mjs` + `lighthouse.config.mjs`) already existed and already targets `home` (route `/`) with a 97-100 floor; extended it to print, per audited route, LCP time (ms), total page weight (KB), JS+CSS weight (KB), and request count — pulled from Lighthouse's own `largest-contentful-paint`/`total-byte-weight`/`network-requests` audits (no new instrumentation). Also fixed a real latent bug: the script imports `chrome-launcher` directly but it was missing from `package.json` devDependencies (only present transitively via `lighthouse`); added `"chrome-launcher": "^1.2.1"` matching the version already resolved in `package-lock.json` (no lockfile regen needed, no npm install run here). **Actual before/after NUMBERS are `[BLOCKED: needs a live run — no browser/build/deploy available in this worktree]`** — not fabricated; run `node apps/web/scripts/lighthouse-gate.mjs --base-url=<preview-url>` against the site before and after the perf change to get real figures. The CI-wiring step (adding this as a `web-build-test` step) is still open — the WIRING NOTE in `lighthouse.config.mjs` calls that out of scope for `.github/workflows` edits from `apps/web`-only work. @files: apps/web/scripts/lighthouse-gate.mjs, apps/web/package.json

**WC4–WC12 — founder round 2 (added 2026-07-05, from Reda's on-device review). "Fix the website once and for all."**

**WN1–WN8 — "don't look new/small" content audit (added 2026-07-05 from a deep site scan; founder said LOG-don't-run — a later run drains these; goal: remove anything that reads as brand-new/tiny/unfinished, NEVER invent facts).**

### Groupe QJW — Parcours devis côté site (tunnel unifié + page proposition déclarative)

> **Ce que c'est.** La moitié `apps/web` du programme de reconstruction du parcours devis (audit L3 du
> 29/08/2026). Le reste du programme — backend, générateur React, scripts, contrats — vit dans
> `docs/PLAN2.md` sous le **Groupe QJR** ; **ce groupe ne touche RIEN hors de `apps/web/**`**.
>
> **Deux surfaces, deux dettes vérifiées.** (1) Le tunnel `mon-toit` existe en TROIS copies complètes
> (FR 5 089 l, AR 4 140 l, EN 4 481 l), chacune avec son propre `buildBody` (FR:4496, AR:3673,
> EN:3934), déjà séparées par un bloc de fonctionnalité entier : les visiteurs non francophones ne
> voient JAMAIS le bloc L-WEBT (occupation_jour + 4 bascules d'équipement + leurs champs kW/créneau =
> 16 colonnes `crm.Lead` vivantes au total, V15) ni le jeton anti-fraude `appareilId`. Les trois copies importent
> DÉJÀ `validateLead`/`buildClientRef`/`buildIdempotencyKey` de `lib/lead.ts` — le patron du module
> partagé est prouvé sur cette surface exacte, c'est une extension d'une décision existante, pas une
> architecture nouvelle. (2) La page proposition câble à la main ~25 mises à jour du DOM via 53
> `querySelector` entre les lignes 8200 et 8900 d'un `.astro` de 10 168 lignes, dans quatre fonctions
> qu'il faut chacune informer de chaque champ — et un champ (le tableau de trésorerie année par année)
> a DÉJÀ été oublié à la première livraison puis rattrapé après coup (commentaire de la page à
> `[...token].astro:8511`).
>
> **DÉPENDANCE CROISÉE — comment elle s'exprime ici.** `plan_lanes.py` ne sait pas résoudre un
> `@after` vers un identifiant d'un AUTRE fichier de plan : les tâches qui attendent le backend
> portent donc une mention **`[GATED: attend le merge M0 du groupe QJR …]`** en tête de leur texte,
> et `(@after:)` ne relie QUE des tâches QJW entre elles. Avant de démarrer une tâche gated,
> **vérifier réellement sur `origin/main`** que `apps/ventes/contract_samples/devis_overrides.json`
> et `taille_detail.json` sont présents.
>
> **RÈGLES DE BASCULE (identiques au groupe QJR, rappelées ici parce qu'elles sont la moitié du
> travail).** FR d'abord (c'est le SUPERSET : rien n'est perdu), puis EN, puis AR ; **un commit par
> locale** ; chaque commit SUPPRIME le `buildBody` local de sa page ; **jamais deux implémentations
> qui coexistent** ; `npm run build` dans `apps/web` **après CHAQUE `.astro` touché** (une régression
> de script inline Astro est exactement la classe que vite attrape et qu'eslint ne voit pas) ; les 12
> tests de locale existants doivent rester verts avant de passer à la locale suivante.

- [x] QJW1 — **[GATE LEVÉ 2026-08-29 : contrats QJR vérifiés sur `origin/main`]** **[GATED: attend le merge M0 du groupe QJR (contrats sur `main`) — vérifier que `apps/ventes/contract_samples/taille_detail.json` ET `proposal_data.json` sont présents sur `origin/main` avant de démarrer]** — **`apps/web` entre dans PACT10 : répertoire de contrats + garde d'égalité avec le jumeau backend** : vérifié en session, `find apps/web -name contract_samples` ne renvoie RIEN et `scripts/check_api_shapes.py` ne mentionne que `frontend/src/api/*.js` — tout le site public est aujourd'hui HORS PACT10. Créer `apps/web/src/contract_samples/` avec `taille_detail.json` ET `proposal_data.json` copiés depuis `backend/django_core/apps/ventes/contract_samples/`, plus une garde (vitest dans `apps/web/tests/`) affirmant que chaque copie `apps/web` est JSON-ÉGALE à son jumeau backend, de sorte que les deux moitiés ne peuvent plus dériver (origine: QJF13 moitié `apps/web` + la copie `apps/web` de QJF14). **Done =** répertoire créé avec les deux échantillons, garde verte, garde ROUGE si on modifie une copie sans son jumeau, `npm run build` vert. Files: `apps/web/src/contract_samples/taille_detail.json`, `apps/web/src/contract_samples/proposal_data.json`, `apps/web/tests/contractSamplesParite.test.ts`. (ROUTINE) (@lane: qjw/contrats-web) (@model: sonnet)
- [x] QJW2 — **`champs.ts` — le registre des champs du tunnel** : `apps/web/src/lib/tunnel/champs.ts` : UN tableau de descripteurs `{ cle, webhookKey, domId, modes[], lire(etat), nettoyer, requis }`. Le DÉRIVER en diffant les trois implémentations de `buildBody` clé par clé — la copie FR est le SUPERSET (elle seule porte le bloc L-WEBT : `occupation_jour` + 4 bascules d'équipement + leurs champs kW/créneau — 16 colonnes `crm.Lead` vivantes manquantes AU TOTAL en AR/EN, bloc L-WEBT + equip_piscine_pompe_kw/equip_ve_km_semaine/equip_clim_pieces (V15), plus `appareilId`). Le registre devient la source unique de vérité de ce que le tunnel collecte. Le livrer SEUL, importé par rien (origine: QJF30). **Done =** registre couvrant le superset FR, aucune page ne l'importe encore, `npm run build` vert. Files: `apps/web/src/lib/tunnel/champs.ts`. (ARCH) (@lane: qjw/tunnel) (@model: sonnet)
- [x] QJW3 — **`corps.ts` — LE seul `buildBody`, piloté par le registre** : `apps/web/src/lib/tunnel/corps.ts` : `construireCorps(etat, ctx): { body, errors }`. PUR — prend un objet d'état simple, rend un objet simple, aucun DOM et aucun Astro. Doit reproduire EXACTEMENT la discipline existante « nettoyer ou omettre, jamais fabriquer » : une question non posée est une clé ABSENTE, jamais un défaut fabriqué (les booléens `equip_*` ne deviennent que `true`, jamais un `false` fabriqué ; `cleanBoundedSignedNumber` autorise négatif et zéro sans inventer une valeur manquante). Il appelle le `validateLead` existant de `lib/lead.ts` plutôt que de ré-implémenter le miroir de pré-contrôle en ligne. **Fondre ici le commentaire périmé `regionAgricole` relevé par l'audit (web-tunnel-3) : le corriger ou le supprimer dans le même commit, il documente un comportement qui n'existe plus** (origine: QJF31 ⊕ R4-B2.24). **Done =** module + tests unitaires verts, aucune page ne l'importe encore, commentaire `regionAgricole` traité, `npm run build` vert. Files: `apps/web/src/lib/tunnel/corps.ts`, `apps/web/tests/tunnelCorps.test.ts`. (ARCH) (@lane: qjw/tunnel) (@model: opus) (@after: QJW2)
- [x] QJW4 — **`i18n.ts` — la couche locale à exhaustivité vérifiée à la compilation** : `apps/web/src/lib/tunnel/i18n.ts` : un `Record<Cle, string>` par locale pour les libellés et les erreurs, clé sur l'union de clés du registre QJW2. Parce que le type est un `Record` sur cette union, **ajouter un champ SANS ses trois traductions devient une erreur `tsc`, pas une omission silencieuse** — c'est la moitié de la garantie de parité qui ne coûte rien à l'exécution. **Le balisage reste par locale (la mise en page RTL arabe diffère réellement) : seules les CHAÎNES et la LOGIQUE sont partagées** (origine: QJF32). **Done =** trois locales complètes, une clé ajoutée sans traduction fait échouer `tsc` (démontré dans le message de commit), `npm run build` vert. Files: `apps/web/src/lib/tunnel/i18n.ts`. (ROUTINE) (@lane: qjw/tunnel) (@model: sonnet) (@after: QJW2)
- [x] QJW5 — **BASCULE : les trois `.astro` importent `construireCorps` ; les trois copies de `buildBody` sont supprimées** : **UN COMMIT PAR LOCALE, FR d'abord** (superset, donc rien n'est perdu), puis EN, puis AR. Chaque commit supprime ENTIÈREMENT le `buildBody` local de sa page — aucun double chemin. AR et EN gagnent au passage le bloc de champs L-WEBT et `appareilId`, ce qui EST le vrai correctif de bug (web-tunnel-1 : les réponses des visiteurs non francophones et le signal anti-fraude appareil ne sont aujourd'hui JAMAIS collectés). Vérifier le chemin de soumission de chaque locale avec les 12 tests de locale existants TOUJOURS VERTS avant de passer à la suivante ; **`npm run build` dans `apps/web` après chaque bascule** (origine: QJF33). **Done =** trois `buildBody` supprimés, trois pages sur le module partagé, 12 tests de locale verts, `npm run build` vert après chacun des trois commits. Files: `apps/web/src/pages/devis/mon-toit.astro`, `apps/web/src/pages/en/devis/mon-toit.astro`, `apps/web/src/pages/ar/devis/mon-toit.astro`. (ARCH) (@lane: qjw/tunnel) (@model: opus) (@after: QJW3, QJW4)
- [x] QJW6 — **Test de parité — égalité d'ENSEMBLES sur les clés émises** : `apps/web/tests/tunnelParite.test.ts`, trois assertions. (1) COMPORTEMENTALE, celle qui compte : donner UN objet d'état fixe à `construireCorps` par locale et affirmer que l'ENSEMBLE des clés émises est identique. L'égalité d'ensembles échoue AUTOMATIQUEMENT sur tout nouveau champ ajouté à une seule locale — exactement ce que les 12 tests de locale existants sont structurellement incapables de faire (vérifié : chacun n'épingle que sa propre fonctionnalité par regex, et c'est pour ça que les 9 champs L-WEBT et `appareilId` sont passés inaperçus). (2) STRUCTURELLE : pour chaque descripteur portant un `domId`, affirmer que l'identifiant apparaît dans les TROIS sources `.astro` — attrape la dérive du balisage pendant que le balisage reste par locale. (3) L'exhaustivité i18n est déjà imposée par `tsc` (QJW4), aucune assertion nécessaire (origine: QJF34). **Done =** test vert après la bascule, ROUGE si on ajoute un champ à une seule locale (démontré), `npm run build` vert. Files: `apps/web/tests/tunnelParite.test.ts`. (ROUTINE) (@lane: qjw/tunnel) (@model: sonnet) (@after: QJW5)
- [x] QJW7 — **[GATE LEVÉ 2026-08-29]** **[GATED: attend le merge M0 du groupe QJR (contrats sur `main`) — vérifier que `apps/ventes/contract_samples/taille_detail.json` est présent sur `origin/main`, puis que QJW1 en a livré la copie dans `apps/web/src/contract_samples/`]** — **`liaisons.ts` — les deux tables de liaison** : `apps/web/src/lib/proposition/liaisons.ts`. HERO : `{ cle, valeur:'[data-hero-ttc-value]', enveloppe:'[data-hero-ttc-card]', carte:'[data-taille-ttc-value]' }[]` — 7 entrées remplaçant les 7 appels câblés à la main d'`appliquerChampHero` dans `synchroniserDetailPage` (`8426`) et leurs ~14 recherches de constantes. PROFONDS : `{ cle, noeuds, enveloppe?, lire(d: TailleDetail), peindre(noeuds, v) }[]` — 6 entrées pour les chapitres profonds (économies mois par mois, total, banque batterie, donut de couverture, cumul 25 ans, payback, tableau année par année). Les types viennent de l'`interface TailleDetail` existante (`apps/web/src/lib/tailleDetail.ts`, 242 l). Le livrer SEUL, importé par rien (origine: QJF40). **Done =** deux tables couvrant 7 + 6 entrées, typées contre `TailleDetail`, aucun import en production, `npm run build` vert. Files: `apps/web/src/lib/proposition/liaisons.ts`. (ARCH) (@lane: qjw/proposition) (@model: sonnet) (@after: QJW1)
- [x] QJW8 — **`swap.ts` — le moteur générique appliquer / restaurer** : `apps/web/src/lib/proposition/swap.ts` : `capturerOriginaux(liaisons)` (moissonne `textContent`/`innerHTML` UNE fois à l'initialisation — aujourd'hui `originaux` est construit à la main champ par champ), `appliquer(liaisons, detail)`, `restaurer(liaisons, originaux)`, `marquerChargement(liaisons, bool)`. **DISCIPLINE À PRÉSERVER VERBATIM, c'est la règle fondateur sur cette page : un `lire` qui rend `null` CACHE l'enveloppe — il ne substitue JAMAIS et ne relit JAMAIS l'original sous une autre carte.** Le code actuel est explicite (« JAMAIS un readback sur l'original sous une autre carte — le bug corrigé par cette revue », doc d'`appliquerChampHero` ; et « Le laisser afficher les douze mois du devis officiel sous une autre carte serait un chiffre réel attribué à la mauvaise offre », `appliquerDetail`). L'encoder UNE fois dans le moteur pour qu'aucune liaison future ne puisse se tromper (origine: QJF41). **Done =** moteur + tests verts, test prouvant qu'un `lire` rendant `null` cache l'enveloppe et n'écrit AUCUNE valeur, aucun import en production, `npm run build` vert. Files: `apps/web/src/lib/proposition/swap.ts`, `apps/web/tests/propositionSwap.test.ts`. (ARCH) (@lane: qjw/proposition) (@model: opus) (@after: QJW7)
- [x] QJW9 — **BASCULE : le script inline utilise le moteur de liaison ; les fonctions câblées à la main sont supprimées** *(vérif navigateur : FAITE le 30/08 via harnais local — astro dev + mock servant les échantillons de contrat officiels ; Éco → Max → Recommandé : les champs hero et les chapitres profonds suivent la carte avec les valeurs du contrat, le retour restaure un DOM sémantiquement identique (seul l'ordre de sérialisation d'un attribut `hidden` reposé diffère), et `recommande` n'appelle jamais le réseau — restauré du cache comme conçu ; clics dispatchés en JS, le pointeur réel étant le seul élément simulé)* : remplacer `synchroniserDetailPage` (`8426`), `restaurerDetail` (`8584`), `appliquerDetail` (`8609`) et `marquerChargement` (`8574`) par des appels dans `swap.ts` pilotés par `liaisons.ts`, et SUPPRIMER les ~50 recherches de nœuds constantes dont elles dépendent, dans le MÊME commit. Cible : la région de swap passe de ~500 lignes de câblage à ~60 lignes d'orchestration. `chargerDetail` (`8672`) et `appliquer` (`8716`) gardent leur rôle d'orchestration. **`npm run build` dans `apps/web` — une régression de script inline Astro est exactement ce qu'eslint ne verra pas. VÉRIFICATION HUMAINE EN NAVIGATEUR EXIGÉE (R4-C.7) : cliquer Eco / Recommandé / Max échange bien les SEPT champs hero et les SIX chapitres profonds, et revenir à Recommandé restaure les valeurs rendues en SSR À L'OCTET** (origine: QJF42). **Done =** les quatre fonctions supprimées, région de swap ≤ ~60 lignes, `npm run build` vert, vérification navigateur faite et rapportée (les trois offres, aller et retour). Files: `apps/web/src/pages/proposition/[...token].astro`. (ARCH) (@lane: qjw/proposition) (@model: opus) (@after: QJW8)
- [x] QJW10 — **Garde de couverture — le test qui aurait attrapé l'oubli du tableau de trésorerie** : `apps/web/tests/propositionLiaisons.test.ts` : affirmer que CHAQUE clé feuille de `apps/web/src/contract_samples/taille_detail.json` est SOIT liée dans HERO/PROFONDS, SOIT listée dans un tableau explicite `NON_AFFICHE` avec une raison ÉCRITE. Une nouvelle clé de charge utile devient alors un test rouge jusqu'à ce que quelqu'un décide, par écrit, de l'afficher ou de ne pas l'afficher. C'est la réponse structurelle directe à l'incident documenté : le tableau de trésorerie année par année n'avait pas été câblé dans le swap à la première livraison et a dû être rattrapé après coup (commentaire `[...token].astro:8511`, « revue Fable 29/08/2026 ») (origine: QJF43). **Done =** test vert avec toutes les clés soit liées soit justifiées, ROUGE si on ajoute une clé à l'échantillon sans décision, `npm run build` vert. Files: `apps/web/tests/propositionLiaisons.test.ts`. (ROUTINE) (@lane: qjw/proposition) (@model: sonnet) (@after: QJW9)
- [x] QJW11 — **[GATE LEVÉ 2026-08-29]** **[GATED: attend le merge M0 du groupe QJR (contrats sur `main`) — vérifier que `apps/ventes/contract_samples/proposal_data.json` est présent sur `origin/main`, puis que QJW1 en a livré la copie dans `apps/web/src/contract_samples/`]** — **Lecteur typé de `proposal_data` dans `apps/web`** : ajouter `lireProposal(payload): Proposal` à `apps/web/src/lib/proposition.ts` (4 555 l), dans la MÊME forme de parseur que `tailleDetail.ts:226` utilise déjà, validé dans les tests contre `apps/web/src/contract_samples/proposal_data.json`. Aujourd'hui la page `.astro` lit la charge utile en dict libre sans aucune forme partagée, donc un renommage de clé côté backend est INVISIBLE jusqu'à ce que la page s'affiche vide. C'est la moitié cliente du contrat PACT10 que le groupe QJR livre côté serveur (origine: QJF44). **Done =** lecteur typé + tests contre l'échantillon, un renommage de clé simulé fait rougir au lieu de rendre une page vide, `npm run build` vert. Files: `apps/web/src/lib/proposition.ts`, `apps/web/tests/propositionPayload.test.ts`. (ARCH) (@lane: qjw/proposition) (@model: sonnet) (@after: QJW1)
- [x] QJW12 — **Miroirs T5 du site public sur la valeur prouvee (jumelle de QJR26, decision fondateur D5 du 29/08)** : aligner `apps/web/src/lib/regieTariff.ts` (~:15), `apps/web/src/lib/estimatorBrainV2.ts` (~:123) et recalculer `apps/web/tests/savingsTranchesFondateur.test.ts` (montants DERIVES du nouveau tarif, jamais recopies) sur T5 = 1.381704 TTC — la valeur de `backend/django_core/apps/ventes/quote_engine/bareme.py`, prouvee contre la facture SRM n° 643769639 ; relire les 4 pages de blog FR/EN/AR citant 1,405116 et corriger la ou le chiffre est presente comme tarif actuel (mention historique datee = OK). Depuis le merge M1 du groupe QJR, l'ERP est aligne et l'estimateur public SURESTIME la facture T5 d'environ 1,7 % — cette tache ferme l'ecart. **Done =** grep `405116` vide dans apps/web hors mentions historiques datees, tests recalcules verts, build vert. Files: `apps/web/src/lib/regieTariff.ts`, `apps/web/src/lib/estimatorBrainV2.ts`, `apps/web/tests/savingsTranchesFondateur.test.ts`, pages de blog concernees.
- [ ] QJW13 — **Le repli local du formulaire de conversion cesse de diverger du moteur du site** : `apps/web/src/lib/billRange.ts:75-87` porte une table statique `LOCAL_BANDS` (kWc et payback par tranche de facture) que `lib/lead.ts:1019-1053` `runSimulation` sert au prospect (a) quand `SIMULATOR_API_URL` n'est pas configurée et (b) sur TOUT échec réseau/HTTP/parse (`catch { return fallback; }`) — un chemin réellement exécutable, couvert par `tests/lead.test.ts:364`. Or le même site possède un moteur bien plus précis pour EXACTEMENT la même question (`lib/billEstimate.ts` → `lib/estimatorBrainV2.ts` : barème ONEE réel par tranche, table PVGIS par ville, `PRODUCTION_NET_FACTOR` calé sur les 20 % de pertes du fondateur), utilisé par `InstantEstimator.astro` en page d'accueil. Écart reproduit à la main : pour 3 000 MAD/mois le moteur donne ≈ 16 kWc là où la table promet « 5 à 9 kWc » (+78 % sur le plafond) ; pour 5 000 MAD/mois, ≈ 26,5 kWc contre « 9 à 15 kWc ». Deux endroits du même site répondent différemment à la même question pour le même prospect, sur LE composant de conversion principal (`DiagnosticForm.astro:4`, affichage `:409-411`). Appeler `estimateFromBill()` depuis `runSimulation` (ou recalculer `LOCAL_BANDS` à partir de lui) plutôt que de maintenir une table à la main. **Done =** repli local et estimateur d'accueil rendent le même kWc pour la même facture sur cinq points de contrôle, test de parité, build vert. Files: `apps/web/src/lib/billRange.ts`, `apps/web/src/lib/lead.ts`, `apps/web/tests/`. (ROUTINE) (@lane: qjw/diagnostic) (@model: sonnet)
- [ ] QJW14 — **Le CAPI respecte la bannière de consentement** : `apps/web/src/lib/lead.ts:1360-1399` `fireCapi` ne lit JAMAIS `tq_consent` (grep : la clé n'existe que dans `visite.ts`, `Layout.astro`, `ConsentBanner.astro`), et il est appelé inconditionnellement dès `record.qualified` par `pages/api/simulate.ts:76-80` et `pages/api/preview-lead.ts:96-99`. Un visiteur qui clique explicitement « Refuser » puis soumet le formulaire voit quand même téléphone, ville et email hachés partir chez Meta. **Décision fondateur à trancher DANS la tâche** : est-ce voulu (le CAPI étant lié à un acte explicite du prospect plutôt qu'à la navigation anonyme), ou faut-il gater ? Selon la réponse : lire `tq_consent` côté client avant l'appel, ou transmettre le flag au serveur, ou documenter explicitement le choix dans `ConsentBanner.astro`. **Done =** comportement tranché et documenté, test couvrant « Refuser puis soumettre ». Files: `apps/web/src/lib/lead.ts`, `apps/web/src/pages/api/simulate.ts`, `apps/web/src/pages/api/preview-lead.ts`, `apps/web/src/components/ConsentBanner.astro`. (DECISION) (@lane: qjw/diagnostic) (@model: sonnet)
- [ ] QJW15 — **Lot de finition des formulaires diagnostic** : (a) les deux formulaires n'envoient AUCUN jeton de déduplication (`DiagnosticForm.astro:375-387`, `DiagnosticFormEnriched.astro:380-392`), contrairement au tunnel `/devis/mon-toit` qui génère `buildIdempotencyKey`/`buildClientRef` précisément pour ce cas (`mon-toit.astro:2519-2529`) — le `submitBtn.disabled` protège du double-clic mais pas d'une resoumission après rechargement, et le CRM n'a alors aucun signal pour fusionner ; réutiliser les deux fonctions, déjà présentes dans `lib/lead.ts`. (b) le CSS `input[aria-invalid="true"]` (`DiagnosticForm.astro:224`, `DiagnosticFormEnriched.astro:232`) est mort : le script ne pose jamais l'attribut, donc ni repérage au lecteur d'écran ni bordure d'erreur — le poser sur le champ fautif et le retirer à la correction. (c) garde honeypot asymétrique : `pages/api/simulate.ts` (formulaire LIVE) n'importe pas `isHoneypotTripped` alors que `preview-lead.ts:67` l'appelle, et **aucun** des deux composants ne rend le champ `website_url` (contrairement à `mon-toit.astro:1200` et `contact.astro:148`) — donc la garde de preview est un no-op ; ajouter le champ aux deux `.astro` ET l'appel à `simulate.ts`, ou retirer l'appel mort. **Done =** les trois points traités, tests correspondants, build vert. Files: `apps/web/src/components/DiagnosticForm.astro`, `apps/web/src/components/DiagnosticFormEnriched.astro`, `apps/web/src/pages/api/simulate.ts`, `apps/web/src/pages/api/preview-lead.ts`. (ROUTINE) (@lane: qjw/diagnostic) (@model: sonnet)
- [ ] QJW16 — **[GATED: à ne construire qu'AVANT une promotion de `DiagnosticFormEnriched` en production] Les champs enrichis atteignent réellement le lead** : `DiagnosticFormEnriched.astro:393-401` collecte et transmet `supplyType`, `roofArea`, `orientation`, `estimatedKwc` (`pages/api/preview-lead.ts:80-81` les conserve dans `record.enrichment`), mais `backend/django_core/apps/crm/webhooks.py` ne contient AUCUNE référence à `enrichment` / `estimatedKwc` / `roofAreaM2` / `supplyType` (grep : 0 occurrence) : les valeurs survivent dans le payload brut (`WebsiteLeadPayload`) sans être mappées sur aucun champ de `crm.Lead`, et un commercial ouvrant la fiche ne voit pas ce que le prospect a répondu. Le code l'admet lui-même (`DiagnosticFormEnriched.astro:10` : « affichage CRM = tâche taqinor-os séparée »). Impact LIMITÉ aujourd'hui — ce composant n'est utilisé que par `preview/diagnostic.astro`, page privée `noindex` hors nav — d'où le gating : le câblage backend doit précéder la promotion, jamais la suivre. **Note :** la moitié backend (mapping dans `_extract_web_questionnaire`) sort du périmètre `apps/web` et devra faire l'objet d'une tâche PLAN2 jumelle portant `@after` sur elle (PACT11). **Done =** décision de promotion prise, ou tâche jumelle backend créée et les quatre champs visibles sur la fiche lead. Files: `apps/web/src/components/DiagnosticFormEnriched.astro`. (DECISION) (@lane: qjw/diagnostic) (@model: sonnet)

> **Suite du Groupe QJW — la moitié `apps/web` de la contre-visite du 30/08/2026.** La vérification
> post-build du parcours devis (12 lanes de lecture seule + ronde adversariale, **0 constat réfuté**)
> a produit sept constats qui vivent entièrement sous `apps/web/**` ; la moitié backend/générateur
> part dans `docs/PLAN2.md` sous le **Groupe QJR2**. Rapport complet :
> https://claude.ai/code/artifact/e18dd134-8974-4871-bdd4-3cf81f5361e2
>
> **Aucune de ces tâches n'attend quoi que ce soit du backend** : les contrats qu'elles consomment
> (`apps/ventes/contract_samples/proposal_data.json`, `taille_detail.json`, `devis_overrides.json`)
> sont **déjà sur `main`** depuis le merge M0 du Groupe QJR — rien n'est gated ici, aucune ne porte
> de mention d'attente. **Ordre :** QJW17 d'abord (bug HAUT visible au premier chargement de page).
> `npm run build` dans `apps/web` après CHAQUE `.astro` touché ; les tests de locale existants
> restent verts avant de passer à la suite.

- [ ] QJW17 — **`restaurer` cesse d'aplatir le bloc « total avec » à chaque chargement de page** : `src/lib/proposition/liaisons.ts:248` déclare `totalAvec` avec la capture par défaut `texte` sur `[data-detail-eco-total-avec-bloc]`, or ce nœud (`pages/proposition/[...token].astro:3648-3651`) **contient deux `<span>` enfants** — l'étiquette `data-i18n` et le montant stylé `dir="ltr"` ; `swap.reposer` (`swap.ts:95`) fait `el.textContent = orig.contenu`, ce qui les **détruit**, et `restaurer` tourne **au chargement** via `appliquer()` (`[...token].astro:8669`) → `chargerDetail()` → `restaurerDetail()` (`:8510`). Conséquence corrigée par R3 — le défaut est **pire que décrit** et vaut HAUT : le client voit un texte **FR+EN+AR mélangé dès le premier affichage** (le crochet de traduction ayant disparu), et le sélecteur de langue ne pilote plus ce bloc. La garantie « identité byte-à-byte après un aller-retour » annoncée à `[...token].astro:8418` et `liaisons.ts:29-30` est donc fausse (origine: fresh-bugs-3, medium→**HAUT** par R3). Capturer/restaurer en **préservant les nœuds enfants** (capture de type « fragment », pas `texte`), et faire que le crochet i18n survive à l'aller-retour. **Done =** test ROUGE d'abord : aller-retour capture/restauration sur `[data-detail-eco-total-avec-bloc]` → les deux `<span>` disparaissent ; vert après = DOM identique à l'octet, `data-i18n` intact, bascule FR/EN/AR pilotant encore le bloc après restauration ; `npm run build` vert. Files: `apps/web/src/lib/proposition/liaisons.ts`, `apps/web/src/lib/proposition/swap.ts`, `apps/web/tests/propositionLiaisons.test.ts`. (ROUTINE) (@lane: qjw/proposition-contrevisite) (@model: opus)
- [ ] QJW18 — **Le pourcentage DANS le donut se repeint quand le client charge une taille Eco/Max** : `src/lib/proposition/liaisons.ts:328-335` — la liaison de couverture déplace bien l'arc (`stroke-dasharray` recalculé sur `data-detail-donut-r`) mais le nombre au centre passe par `const val = unHtml(noeuds, 'valeur')`, et `unHtml` **renvoie `null` pour le nœud `<text>` SVG** : la peinture est silencieusement sautée, donc **l'arc décrit la nouvelle taille pendant que le chiffre garde le pourcentage du devis officiel** — deux chiffres contradictoires dans la même figure, sous les yeux du client (origine: fresh-bugs-2, medium confirmé sans réserve par R3). Étendre `unHtml` / la liaison au texte SVG (le `<text>` SVG n'a pas d'`innerHTML` : passer par `textContent`), sans changer le format d'affichage. **Done =** test ROUGE d'abord : chargement d'une taille Eco → arc à jour, chiffre inchangé ; vert après = arc et chiffre décrivent la même taille ; un cas où la donnée manque OMET le chiffre au lieu d'en peindre un faux ; `npm run build` vert. Files: `apps/web/src/lib/proposition/liaisons.ts`, `apps/web/tests/propositionLiaisons.test.ts`. (ROUTINE) (@lane: qjw/proposition-contrevisite) (@model: opus) (@after: QJW17)
- [ ] QJW19 — **Une réponse de détail en retard ne déclare plus « chargé » une section encore en vol** : `src/pages/proposition/[...token].astro:8535` — une requête de détail qui revient tard efface `aria-busy` sur des chapitres qu'une requête **plus récente et toujours en vol** a légitimement marqués occupés ; ces chapitres restent **masqués**, si bien que la technologie d'assistance annonce une région stabilisée alors qu'elle est vide et encore en chargement (origine: fresh-bugs-13, medium confirmé sans réserve par R3). Attacher l'effacement d'`aria-busy` à l'identité de la requête qui l'a posé (jeton de requête), comme le fait déjà la garde anti-réponse-périmée du reste de la page. **Done =** test ROUGE d'abord : requête A lente + requête B rapide → à l'arrivée de A, `aria-busy` retiré alors que B est en vol ; vert après = seul le retour de la requête courante l'efface, les chapitres masqués redeviennent visibles au bon moment ; `npm run build` vert. Files: `apps/web/src/pages/proposition/[...token].astro`, `apps/web/tests/propositionAriaBusy.test.ts`. (ROUTINE) (@lane: qjw/proposition-contrevisite) (@model: sonnet) (@after: QJW18)
- [ ] QJW20 — **`proposal_data` reçoit sa table de couverture des FEUILLES, comme `taille_detail`** : `apps/web/tests/propositionPayload.test.ts:125` porte bien une table `CLES_LUES` (« la garde qui justifie tout le module »), mais c'est une table des clés que la page **lit**, pas une table de **couverture des feuilles** : une clé ajoutée à `proposal_data` — la principale charge utile client de la page proposition — peut donc arriver **sans qu'aucun test ne force une décision** à son sujet (lue, ou refusée avec une raison écrite). `taille_detail` a cette machinerie depuis QJW10 et c'est la deuxième meilleure du dépôt ; `proposal_data` est le seul surface non gardée **des deux côtés à la fois** (origine: addition-walkthrough-8, confirmé par R3). Construire la table par énumération des **feuilles** de l'échantillon de contrat commité **`apps/ventes/contract_samples/proposal_data.json`** — le même fichier auquel s'apparie la moitié serveur (QJR228 dans `PLAN2.md`), chaque moitié tournant seule. **Done =** une feuille ajoutée à `proposal_data.json` et non déclarée (ni lue, ni refusée avec raison) fait ROUGIR le test (cas négatif exécuté) ; les refus actuels écrits un par un ; suite web verte. Files: `apps/web/tests/propositionPayload.test.ts`. (ROUTINE) (@lane: qjw/proposition-contrevisite) (@model: sonnet)
- [ ] QJW21 — **La garde de parité du tunnel passe par le `lireEtatTunnel` de CHAQUE page** : `apps/web/tests/tunnelParite.test.ts:108-125` construit un `etatComplet()` **à la main** puis appelle `construireCorps(etat, …)` pour les trois locales : la garde compare donc trois fois la MÊME lecture et **ne peut pas voir** la seule omission qu'elle existe pour attraper — une locale dont la page ne LIT jamais la nouvelle question reste verte (origine: addition-walkthrough-2, HAUT confirmé). Faire partir chaque locale de son propre `lireEtatTunnel()` (le lecteur réel de sa page, `mon-toit.astro` fr/en/ar) sur un DOM peuplé, puis comparer les corps émis. **Done =** test négatif EXÉCUTÉ : un champ retiré du seul DOM anglais fait rougir la garde (aujourd'hui elle reste verte) ; les 12 tests de locale existants toujours verts ; `npm run build` vert après chaque `.astro` touché. Files: `apps/web/tests/tunnelParite.test.ts`, `apps/web/src/pages/devis/mon-toit.astro`, `apps/web/src/pages/en/devis/mon-toit.astro`, `apps/web/src/pages/ar/devis/mon-toit.astro`. (ROUTINE) (@lane: qjw/tunnel-contrevisite) (@model: opus)
- [ ] QJW22 — **La liste blanche de `lead.ts` est appariée au registre du tunnel, et le test porte sur le corps APRÈS liste blanche** : `src/pages/api/capture-lead.ts:71` — un champ correctement déclaré dans le registre du tunnel est **silencieusement jeté avant le webhook** s'il n'a pas AUSSI été ajouté à la main à la liste blanche de `lib/lead.ts`, et les tests de parité assertent sur le corps **d'AVANT** la liste blanche : ils ne peuvent structurellement pas le voir. R3 abaisse à **medium** — les 69 clés du registre sont toutes traitées aujourd'hui, c'est donc un **piège de maintenance latent**, pas une perte de données en production (origine: addition-walkthrough-4). Écrire la garde de parité registre ↔ liste blanche, et **déplacer l'assertion sur le corps POST-liste-blanche** (celui qui part réellement au webhook). **Done =** test négatif EXÉCUTÉ : une clé ajoutée au registre et absente de la liste blanche fait rougir la garde (aujourd'hui verte) ; les assertions de parité portent sur le corps réellement émis ; suite web verte. Files: `apps/web/src/lib/lead.ts`, `apps/web/src/pages/api/capture-lead.ts`, `apps/web/tests/tunnelParite.test.ts`. (ROUTINE) (@lane: qjw/tunnel-contrevisite) (@model: sonnet) (@after: QJW21)
- [ ] QJW23 — **Une passe de vérification de types couvre enfin les scripts `.astro`** : `apps/web/tsconfig.check.json:14` — **aucune vérification de types ne tourne sur les scripts des pages `.astro`**, si bien que le contrat typé entre le registre du tunnel (`src/lib/tunnel/champs.ts`) et les trois pages n'est appliqué qu'à l'intérieur de `src/lib` : côté page, tout est du JavaScript non vérifié (origine: addition-walkthrough-3, medium confirmé). Ajouter la passe (`astro check` ou l'extension du périmètre `tsconfig.check.json`) et la brancher au gate web existant ; les erreurs préexistantes se traitent, ou se consignent une par une dans une liste gelée avec leur raison — **jamais un gate désarmé** pour passer. **Done =** la passe tourne dans le gate web et rougit sur une erreur de type introduite dans un script `.astro` (cas négatif exécuté) ; l'inventaire des erreurs préexistantes est soit vidé, soit gelé avec ses raisons ; `npm run build` vert. Files: `apps/web/tsconfig.check.json`, `apps/web/package.json`. (ROUTINE) (@lane: qjw/typecheck) (@model: sonnet) (@after: QJW21)

---

## NEEDS YOUR INPUT — ungated; each waits on something only you can give (with my recommendation)

**Auto-gating is OFF (2026-06-21).** A web run no longer skips a task for being a new dep, an
architecture change, or a taste call — it builds and NOTES it. What remains here genuinely needs
**you**: a real-world data drop, a Cloudflare dashboard secret, or a taste/business call.

### BLOCKED on a backend prerequisite — RÉSOLU 2026-08-30 (section conservée pour mémoire)

- **[x] WJ115 (already present)** — le gate QX34 est levé ET la moitié web existe déjà sur `main`,
  vérifiée contre le code réel : backend `suivi_public` (`public_views.py`) + sélecteur
  `devis_milestones` (lecture seule, tokenisé, jamais de marge) ; côté site
  `pages/suivi/[token].astro` + `lib/suivi.ts` (contrat QX34 documenté, libellés AR, garde
  anti-date-inventée) + `tests/suiviWJ115.test.ts` (vert dans les suites complètes du 29/08).
  Construite lors du drain round-6 puis pointée (commit « WJ115/WJ116 — tick plan ») ; cette note
  de blocage était un reliquat périmé.
- **[x] WJ116 (already present)** — QX35 est LIVE côté backend (code `Client.code_parrainage`
  déterministe `TQ-<id>`, création auto du `Parrainage`, avancement à l'acceptation du devis) et
  la page `/parrainage` (FR/EN/AR) communique la vraie mécanique — jamais un code auto-choisi ;
  `tests/parrainageWJ116.test.ts` vert (recalibré au run du 29/08). Reliquat de note périmé
  également. Le MONTANT de la récompense reste gated par **WG14** (décision fondateur), comme
  prévu — la page publie la mécanique sans chiffre inventé.

### GATE DECISIONS — RESOLVED by Reda 2026-07-03 (a build run honors these; do NOT re-ask)

**Business / feature calls (decided):**
- **Response-time promise (WG9): « Réponse WhatsApp sous 1 h, 7j/7 ».** WJ58 + every response-window
  reference (W255/W331/W332/marocains-du-monde) use « sous 1 h, 7j/7 » (FR) / equivalent AR.
- **Production guarantee (WG12): YES — build the W352 scaffold, gated.** Section ships but shows NO
  number until Reda supplies the floor % + remedy (still-needed data below).
- **Referral / parrainage (WG14): YES — build W338** (+ W343/W344 links). Publish the mechanic + terms
  copy; the reward amount + trigger milestone stay blank until Reda gives them (still-needed below).
- **Commerce (WG13): build W353 « réserver un créneau de visite » (NO payment).** Online deposit /
  CMI is DECLINED for now — do NOT build any payment integration.
- **AI assistant: NO chatbot for now — free prep only.** Build W379 (llms.txt) + W380 (facts.ts); do
  NOT build the on-site AI-assistant concept.
- **Promote the 3D roof tool live (WG1): NO — keep `/preview/*` private for now.** Do not surface
  toiture-3d-pro-11 publicly; no `PUBLIC_MAPTILER_KEY` needed yet. (WJ2's lite in-capture 3D stays.)
- **PWA (W357): YES — installable + minimal offline caching** (no push notifications).
- **Financing content (WG11 / W258/W261/W336): publish ONLY primary-source-verified facts.** Research
  + cite each named program during the build; drop anything unconfirmed; never a partnership claim or
  invented rate.

**Standing operating consent for a build run (decided):**
- **Dependencies:** free npm packages MAY be added when a task needs one (NOTE each in the DONE LOG);
  any PAID service still stops-and-asks.
- **Cloudflare secrets:** Reda WILL set a dashboard secret when told exactly which — build each such
  feature no-op-safe (does nothing until the secret exists) and hand over the exact key + value. The
  one currently implied: `PUBLIC_CF_ANALYTICS_TOKEN` (WJ94).
- **Lead fields:** additive OPTIONAL CRM fields (email, GPS pin, mode, utility, financing intent,
  foreign-phone flag…) are APPROVED — the 1 000 MAD threshold + consent + webhook contract stay
  byte-for-byte unchanged; every new field is optional and never blocks a submit.

**STILL NEEDED FROM REDA (real data/content — a build run scaffolds these no-op-safe and leaves the
task open until the data lands):** WG5 Google Business Profile + client reviews · WG6 testimonials
(text + 2–3 WhatsApp-shot videos) · WG7 case-study photos/production data + any install outside
Casablanca · WG8 ICE/RC + social URLs + any installer accreditation · WG10 entretien tier
names/inclusions/SLAs/prices · WG12 exact production-guarantee floor % + remedy · WG14 referral
reward amount + trigger milestone · WG15 create the « Taqinor Solaire Maroc » WhatsApp Channel (then
the site adds the follow link) · WG16 warranty-exclusions list + pay-from-abroad mechanics + a legal
skim of the CGI art. 123-22° corporate-VAT section · WG2 délégataire tariff grids (one recent bill
each for Lydec/Redal/Amendis).

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
- **W187 — 1 remaining manufacturer logo** (Dyness). *Update 2026-07-11: 6 of 7 are now SHIPPED —
  Huawei / Nexans / JA Solar / Jinko / Canadian Solar / Deye sourced from Wikimedia + Wikipedia and
  wired.* Only **Dyness** has NO reachable official asset (absent from Wikimedia / Wikidata / GitHub;
  dyness.com + brandfetch are blocked by the egress allowlist). **MY RECOMMENDATION: drop one file** —
  the official Dyness logo as `apps/web/public/brands/dyness.png` (or `.svg`); it then renders
  automatically (flip its `logo` in `brands.ts` from `null`). Word-mark fallback is fine meanwhile.

**Founder shopping list from the 2026-07-02 trust audit — each unlocks already-built components
(everything below is REAL data only; the site's integrity rule renders nothing until you supply it):**

- **WG5 — Google Business Profile + client reviews (THE #1 trust unlock).** Confirm/claim the GBP
  listing, then ask each of the 5 real completed installs' clients for a Google review (staggered
  over weeks — review VELOCITY beats a one-day batch, for both Google and skeptical readers). Fill
  `GOOGLE_RATING` (+ URL) in `apps/web/src/lib/testimonials.ts` and StarRating lights up site-wide.
  Note (research): Google no longer shows SERP stars from a business's own on-site schema — real
  GBP reviews are the only path to stars in search.
- **WG6 — Testimonials: 3–5 written quotes + 2–3 WhatsApp-shot client videos (20–30 s).** Name +
  city + kWc per quote (geo-tagged proof converts best). Phone-shot beats studio (research:
  UGC-style earns more trust). Fills `TESTIMONIALS` and the WJ57/W282 video slots.
- **WG-DEYE (added 2026-07-04) — Real per-site Deye production + roster corrections.** This session
  REMOVED the fabricated ANNUAL production figures (21 406 / 14 271 / 7 135 kWh/an — they shared one
  impossible identical yield factor and matched no Deye reading). The ONLY production number the site
  now shows is the real cumulative Deye fleet total « 6,56 MWh » on the homepage hero (2,62 + 1,41 +
  1,40 + 1,13 MWh across the 4 monitored plants). To restore honest PER-INSTALLATION figures, supply:
  (1) the real, DISTINCT Deye Cloud reading per chantier + its exact commissioning month (today only a
  cumulative « depuis la mise en service » exists — no legitimate annual yet); (2) a chantier PHOTO of
  the Aïn Diab plant (Britel, 10 kWc, 2,62 MWh — the biggest producer, not yet on the site) so it can
  join the realisations roster; (3) ~~the 2 Huawei FusionSolar figures~~ **PROVIDED 2026-07-05:
  Omar taouss = 3,41 MWh, Villa Haj ELOFIR = 34,22 MWh (cumulative measured production) — now in
  MEASURED_FLEET (WC6); still need their kWc + a photo each to add as full realisation cards**;
  (4) confirmation that the El Jadida 17,04 kWc (réf. 468) install is real/posé — it is NOT on Deye
  (the « 43,48 kWc installés » aggregate is being REMOVED site-wide per WC5 regardless). **Supersedes WG7's outdated « a year of
  Deye Cloud data now exists » line.** Until supplied, the site stays honest (cumulative-only, no
  invented annuals). Full context + TODO in `apps/web/src/lib/realisations.ts` (MEASURED_FLEET + header note).
- **WG7 — Complete the thin case studies + widen the map.** casablanca-6-kwc + el-jadida-6-kwc have
  1 photo each and missing onduleur/production data — a year of Deye Cloud data now exists to fill
  them. And the moment ANY install lands outside Casablanca–Settat (Rabat/Marrakech/Tanger/Agadir),
  document it — 4 of 5 declared service cities currently have zero local proof by our own honesty
  rule. Ongoing habit: per completed chantier → photos (wide + close + before/during/after), ref,
  kWc, equipment, measured production.
- **WG8 — Legal + social identity.** Social profile URLs if active accounts exist (never
  placeholders); ICE/RC for mentions légales + footer; any installer-level accreditation
  (agrément/registration, RC Pro insurance) as verifiable CertLogoRow entries. Unlocks W286–W288.
- **WG9 — The response-time number you'll actually honor.** « Réponse WhatsApp sous X, 7j/7 » —
  research says the first responder wins most deals, but only a KEPT promise builds trust. Current
  honest default stays « 24–48 h »; commit to faster only if the team can hold it. Unlocks the
  stronger WJ58 badge.
- **WG10 — Entretien tiers: names, inclusions, SLAs, prices.** Validate the 2–3 contrat-d'entretien
  tiers W255 scaffolds (e.g. Essentiel / Confort / Premium — visites/an, monitoring alerting,
  response-time engagement, indicative price). The SAV ERP module makes the promise real; only you
  can set the commitments.
- **WG11 — Financing facts verification (blocks W258/W261 specifics).** Before ANY named figure is
  published: CAM « Saquii Solaire » current terms + FDA ~30 % pump-subsidy process (DPA/ORMVA);
  whether any bank (CIH/AWB/BOA/CAM) currently packages a residential green loan (a competitor
  CLAIMS partnerships — verify with the banks, never copy the claim); PROMASOL/AMEE amounts +
  Taqinor's own AMEE status; exact décret/décision references + validity windows for the 82-21
  explainer (W259). Pages ship with the verified subset only.

**Round-2 founder gates (2026-07-02) — each unlocks specific round-2 tasks; no invented values:**

- **WG12 — Production-guarantee commitment (blocks W352).** A « Garantie de production Taqinor »
  is the strongest world-tier differentiator, and your measured Deye Cloud data could back one —
  but only YOU can set the terms: the annual-kWh floor framing (e.g. « ≥ X % de la production
  estimée, sinon … »), the remedy if it's missed, and any exclusions. Give me the commitment and
  W352 ships it; until then the block stays a `pending founder commitment` scaffold that renders
  nothing. **MY RECOMMENDATION: worth doing — it's a genuine moat competitors can't copy without
  measured fleet data, and you have it.**
- **WG13 — Commerce-in-the-funnel decisions (blocks W353 windows + the deposit question).** Two
  separate calls: (a) the honest visit-window options for the « réserver un créneau de visite
  technique » step (W353 builds the picker; you supply the real windows the team can honor — e.g.
  « matin / après-midi », « cette semaine / la semaine prochaine »); and (b) whether to accept an
  **online deposit** (CMI/card) at the proposal — this is a NEW paid integration + a real
  commercial/AR decision, so it stays a founder call, NOT built until you say go. **MY
  RECOMMENDATION: ship (a) now (zero new dependency, real momentum), decide (b) later.**
- **WG14 — Referral reward amount + trigger milestone (blocks W338's live figure).** The
  /parrainage page + personal links build with ZERO backend change (they ride the existing
  utm_campaign passthrough), but the page can't state a reward until you set two things: the amount
  (or « avantage », if not cash) and the milestone that earns it (devis signé ? facture payée ?).
  Until then W338 ships the mechanic + terms copy with the figure gated. **MY RECOMMENDATION:
  pick a simple « X MAD quand votre filleul signe » — solar spreads neighbour-to-neighbour and you
  already built the CRM Parrainage model.**
- **WG15 — WhatsApp Channel (unlocks the footer follow-link in W348/W350).** Create a « Taqinor
  Solaire Maroc » WhatsApp Channel (Meta's free broadcast primitive — the MENA equivalent of an
  email list) and send me the URL; the website adds a « Suivez nos chantiers » link only once it
  exists (never a dead link). **MY RECOMMENDATION: 10-minute setup, real retention channel for a
  WhatsApp-first audience — do it.**
- **WG16 — Fact/legal skims before publishing (blocks W331 exclusions, W332 payment mechanics,
  W336 corporate-tax section).** Three small confirmations, each a liability-sensitive fact I won't
  publish unguessed: (a) the exact warranty **exclusions** list for /garanties; (b) the real
  **pay-from-abroad** path for MRE clients (accepted method, currency, staged milestones — no
  invented fees); (c) a one-pass legal skim of the **CGI art. 123-22° corporate-VAT** + 20-year
  depreciation section for /professionnel (these are cited code articles, not partnership claims,
  but tax content deserves a check). Pages ship with only the confirmed subset. **MY
  RECOMMENDATION: (b) and (c) are the two that most move real buyers — prioritize those.**

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

- 2026-08-29 — QJW2 : le registre `src/lib/tunnel/champs.ts` (69 descripteurs) est devenu la source unique de ce que le tunnel collecte, dérivé en diffant les trois `buildBody` réels (FR = superset L-WEBT + appareilId).
- 2026-08-29 — QJW3 : `construireCorps` (pur, piloté par le registre, « nettoyer ou omettre, jamais fabriquer ») remplace la logique de corps ; 38 tests ; le commentaire périmé `regionAgricole` corrigé dans les trois pages.
- 2026-08-29 — QJW4 : couche i18n typée `Record` sur l'union du registre — une clé sans ses trois traductions casse `tsc` (rouge démontré) ; les messages d'erreur EN/AR sont au passage vraiment localisés (FR byte-identique).
- 2026-08-29 — QJW5 : BASCULE des trois locales (un commit chacune, FR→EN→AR) — les trois `buildBody` supprimés ; les visiteurs EN/AR soumettent enfin les 16 champs L-WEBT et le jeton anti-fraude `appareilId` (mesuré avant/après) ; 7 fichiers de tests recalibrés d'épingles-texte vers des assertions de comportement (gardes renforcées, piège du « vacuum-green » évité).
- 2026-08-29 — QJW6 : test de parité par égalité d'ensembles des clés émises + présence des domId dans les trois sources ; les deux rouges démontrés puis annulés.
- 2026-08-29 — WJ127 : les cas sans estimation (trop grand, agricole indispo) montrent désormais un teaser honnête figure-free FR/EN/AR (« étude dédiée — un conseiller vous rappelle »), parité lecteur d'écran rétablie ; 14 tests.
- 2026-08-29 — WJ128 : simulateur batterie de la proposition — capacité inconnue affichée « sur étude » au lieu d'un chiffre catalogue deviné (le prix réel reste indépendant), la ligne batterie retenue est la plus lourde du devis (plus jamais un « câble batterie »), le plafond du curseur (déjà corrigé le 26/08) extrait en fonction pure testée.
- 2026-08-29 — WJ129 : `clamp01` retombe sur la constante documentée sur entrée non-finie (plus jamais la borne optimiste) ; le décalage sémantique des beacons du chemin gaté (`estimation/viewed` sans rendu + `contact/reached` au même instant) documenté sur place dans les trois locales.
- 2026-08-29 — GATE QJR LEVÉ EN COURS DE RUN : le merge M0 du groupe QJR (PLAN2) a atterri sur `origin/main` pendant la construction — `taille_detail.json` + `proposal_data.json` vérifiés présents, la lane proposition gated est repartie dans le même run.
- 2026-08-29 — QJW1 : `apps/web/src/contract_samples/` créé (les deux échantillons SHA-256-identiques à leurs jumeaux backend) + garde vitest d'égalité JSON (rouge démontré sur divergence).
- 2026-08-29 — QJW7 : `liaisons.ts` — 7 entrées HERO (slot Économie dédoublé eco/eco_payback discriminé par `siKind`, 6 actives à la fois) + 6 entrées PROFONDS, typées contre `TailleDetail`.
- 2026-08-29 — QJW8 : `swap.ts` — le moteur générique capture/applique/restaure/masque avec LA discipline fondatrice encodée (un `lire` → null CACHE l'enveloppe, ne substitue jamais, ne relit jamais l'original sous une autre carte) ; 18 tests dont la preuve du masquage-sans-écriture.
- 2026-08-29 — QJW9 : la région de swap de la page proposition passe de ~500 lignes de câblage à ~45 lignes d'orchestration (garde ≤60) ; les ~50 constantes de nœuds supprimées ; 2 améliorations volontaires (restauration du `hidden` serveur par nœud, masquage de chargement couvrant tout le tableau) ; la vérification navigateur réelle N'EST PAS revendiquée — remplacée par un test jsdom de restauration byte-à-byte (aller-retour simple, triple, et après échec réseau) car aucun chemin de fixture local n'existe ; clic réel à faire par Reda sur une proposition live.
- 2026-08-29 — QJW10 : garde de couverture — chaque clé feuille de `taille_detail.json` est liée OU justifiée par écrit dans `NON_AFFICHE` (rouge démontré sur clé non décidée) ; c'est le test qui aurait attrapé l'oubli du tableau de trésorerie.
- 2026-08-29 — QJW11 : `lireProposal` typé dans `lib/proposition.ts`, même forme de parseur que `tailleDetail.ts`, validé contre l'échantillon ; un renommage de clé simulé fait rougir trois tests au lieu de rendre une page vide.
- 2026-08-30 — VÉRIF NAVIGATEUR QJW9 FAITE (harnais local) : astro dev pointé sur un mock servant les échantillons de contrat officiels (proposal_data + taille_detail + offres_tailles, zéro invention) ; la page rend la proposition d'exemple, le clic Éco/Max charge le détail servi (`taille/eco|max/?variante=avec`, valeurs du contrat — 9 940 et 23 490 MAD — aux bons endroits), le retour Recommandé restaure un DOM sémantiquement identique SANS appel réseau (restauré des originaux en cache). Seule différence relevée : l'ordre de sérialisation de l'attribut `hidden` reposé par la restauration (aucune différence sémantique). CONSTAT au passage : le bloc `offres_tailles` de l'échantillon `proposal_data.json` est un STUB documentaire (3 clés/2 champs) qui ne correspond pas à la forme `offres[]` réellement consommée par la page — la vraie forme vit dans `offres_tailles.json` ; à harmoniser côté QJR (backend) pour que l'échantillon embarqué pilote aussi les cartes.
- 2026-08-30 — WJ115/WJ116 : sur « go » fondateur après vérification QX34/QX35, constat que les DEUX étaient déjà construites et testées sur `main` (page `/suivi/[token]` + `lib/suivi.ts` + test ; mécanique parrainage réelle + test) — marquées `[x] (already present)`, notes de blocage périmées purgées de NEEDS YOUR INPUT. Aucun code changé ; le montant de la récompense parrainage reste gated WG14.
- 2026-08-31 — QJW12 : le site public rejoint la valeur T5 prouvée (1,381704 TTC, facture SRM n° 643769639) — `regieTariff.ts` + grille `estimatorBrainV2.ts` corrigés avec provenance documentée, montants du test re-DÉRIVÉS ligne à ligne (jamais recopiés, l'ancien écart ~1,5 % chiffré en commentaire), les 3 langues du blog affichent le tarif prouvé ; seuls résidus « 405116 » = 4 commentaires datés documentant la correction. 9/9 tests verts + tsc propre sur l'arbre intégré ; 2 timeouts fuzz W48 constatés = flake de charge locale (aucune assertion rouge), CI = gate de référence.
- 2026-08-29 — NOTES DE RUN : aucune nouvelle dépendance npm ; 69 échecs vitest pré-existants dans 4 fichiers carte/capture = artefact d'environnement local (jonction node_modules, « Denied ID maplibre-gl.css?url »), vérifiés identiques sur la base avant travaux, verts en CI ; collision de numérotation relevée : les IDs WJ128/WJ129 avaient déjà servi pour le schéma SLD (tests `propositionSldWJ128/129`) — numérotation du plan à assainir au prochain « clean the plans ».

