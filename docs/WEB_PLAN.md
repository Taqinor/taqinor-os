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

- [ ] WJ127 — (@lane: web-journey) **Repli teaser honnête pour les cas SANS estimation (finding 2, MEDIUM).** Les
  cartes d'erreur/edge (`mt-estimate-toolarge`, `-toolarge-pro`, callback agricole indispo) vivent
  DANS `#mt-doc` désormais masqué : un visiteur industriel à 2 000 000 MAD ne voit plus le message
  honnête « à cette échelle, étude dédiée » — seulement le teaser générique « Recevez votre étude
  complète… ». Parité a11y inversée (le lecteur d'écran reçoit GATED_ANNOUNCE, le voyant non).
  Fix : une variante figure-free du hook teaser pour ces chemins (« votre projet relève d'une étude
  dédiée — un conseiller vous rappelle »), FR/EN/AR, sans divulguer de chiffre. (@lane: web-journey)
  (@model: sonnet)
- [ ] WJ128 — (@lane: web-proposal) **Robustesse prix/capacité du simulateur batterie (findings 3+4, LOW).** Dans
  `proposition/[token].astro`/`batterySim.ts` : (a) si la ligne batterie de l'offre matche le
  mot-clé mais ne porte ni réf ni « N kWh » lisible, `resolveOfferBattery` retombe à 5 kWh tout en
  affichant le prix réel — dissocier « capacité connue » de « prix réel » (afficher « sur étude » si
  la capacité n'est pas sûre) ; (b) `BATTERY_KEYWORDS /batter…/` prend la PREMIÈRE ligne qui matche —
  une ligne accessoire « câble batterie » listée avant le pack gagnerait : préférer la ligne au plus
  gros montant/capacité ; (c) si l'offre quote > 3 unités, le slider (max 3) ne peut jamais afficher
  le prix réel (n === offeredUnits jamais atteint) — élargir le max au nombre offert ou afficher le
  vrai total. (@lane: web-proposal) (@model: sonnet)
- [ ] WJ129 — (@lane: web-proposal) **Durcissements mineurs (findings 5+6, NITS).** `batterySim.ts` : `clamp01` renvoie
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

---

## NEEDS YOUR INPUT — ungated; each waits on something only you can give (with my recommendation)

**Auto-gating is OFF (2026-06-21).** A web run no longer skips a task for being a new dep, an
architecture change, or a taste call — it builds and NOTES it. What remains here genuinely needs
**you**: a real-world data drop, a Cloudflare dashboard secret, or a taste/business call.

### BLOCKED on a backend prerequisite not yet on `main` (composition guard)

- **WJ115 — `/suivi/<token>` post-sign status page.** Waits on **PLAN2 QX34** (the ERP endpoint
  that serves the milestone timeline). QX34 is still unchecked in `docs/PLAN2.md`, so the JSON
  contract the page must render does not exist on `main` yet — building the consumer against an
  invented shape is exactly the coupling the founder's composition guard forbids. Unblocks
  automatically the moment QX34 lands (a future PLAN2/QX run) — no founder action needed, just
  ordering.
- **WJ116 — parrainage real links.** Waits on **PLAN2 QX35** (webhook auto-creates `Parrainage`
  + real referral codes). The task itself reads « **Once QX35 lands** … » — the code mechanism it
  must describe does not exist yet, so writing the copy now would be fabrication. Unblocks when
  QX35 lands.

*Neither needs anything from you — they need the two backend tasks built first. They return to the
BUILD QUEUE automatically on the next web run after QX34/QX35 are on `main`.*

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

