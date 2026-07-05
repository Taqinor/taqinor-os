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

### WJ39–WJ59 — QUOTE JOURNEY ROUND 3: defects found + world-best deltas (2026-07-02)

**A — Defects the deep audit found (fix first; two are live bugs):**
- [x] WJ39 — **Fix the English journey: `/en/devis/mon-toit` renders ~90 % in FRENCH and its mode buttons print the literal string "undefined".** The FR/AR dual-node toggle defaults to FR and `applyLang()` is never called for EN (unlike AR which calls `applyLang('ar')`); the EN MODES array has `{id,label,desc}` but the JSX reads `m.fr/m.ar/m.desc_fr/m.desc_ar`. Replace the dual-node markup with real English strings (or call an EN-equivalent applyLang) and fix the MODES references; audit every data-i18n block in the file. **Why:** the entire EN audience — the exact people this route exists for — currently sees a broken half-French page; worst live defect found. @files: apps/web/src/pages/en/devis/mon-toit.astro
- [x] WJ40 — **Fix the 4 EN/AR pages whose bottom CtaBand hardcodes the bare FR `/devis/mon-toit` path.** en/résidentiel (l.247), en/professionnel (l.262), ar/résidentiel (l.240), ar/professionnel (l.255) bypass the locale helper used everywhere else — replace with the `L('/devis/mon-toit')` pattern their own hero CTAs already use. **Why:** EN/AR visitors on the two highest-traffic segment pages get silently dropped onto the French journey. @files: apps/web/src/pages/en/résidentiel.astro, apps/web/src/pages/en/professionnel.astro, apps/web/src/pages/ar/résidentiel.astro, apps/web/src/pages/ar/professionnel.astro
- [x] WJ41 — **Localize the map/geocoder system messages + AR placeholders.** All live status text in `roofPro11/mapDraw.ts` + `captureBoot.ts` (loading, « Adresse introuvable », trace-crosses-itself…) is hardcoded French — thread an `opts.strings`/locale param from the three mon-toit variants; also translate the bare `placeholder=` attributes (rp9-address, mt-fallback-address) on the AR route, which the dual-node toggle cannot reach. **Why:** the single most interactive moment of the funnel speaks French to AR/EN visitors mid-task. @files: apps/web/src/scripts/roofPro11/captureBoot.ts, apps/web/src/scripts/roofPro11/mapDraw.ts, apps/web/src/pages/ar/devis/mon-toit.astro, apps/web/src/pages/en/devis/mon-toit.astro
- [x] WJ42 — **Fix the proposal signature-stamp locale leak.** `stampEl.textContent = frenchStamp()` (l.1383) destroys the AR-aware dual-node markup and never re-registers with `propI18nBusyLabels` — wrap it in a registered re-render (same pattern as `renderSubmitLabel`) and produce an Arabic-formatted timestamp in AR mode. **Why:** one French line flips back on an otherwise fully-AR page at the exact moment of signature. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ43 — **English variant for the proposal page.** `/proposition/[token]` toggles only FR/AR — add EN as a third toggle language (or an `/en/proposition/[token]` route). **Why:** the marocains-du-monde segment the site explicitly serves receives its most commercially critical link with zero English. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ44 — **Expired-proposal warning at the signature itself.** `resolveValidity()` computes `expired` but only the hero reacts — add a visible « offre échue — demandez un devis actualisé » banner directly above `#sign-form` when expired (and check the accept proxy's behavior on expired tokens degrades gracefully). **Why:** a client can currently fill the whole signature on a dead offer with no warning at the point of action. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ45 — **Offline/slow-network states on both journey pages.** `navigator.onLine` + online/offline listeners → a clear « pas de connexion — vos réponses sont conservées, on réessaie dès le retour du réseau » banner instead of the generic fetch-catch message. **Why:** spotty mobile networks are the Moroccan norm; today the user only learns of a failure after a silent timeout. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/proposition/[token].astro
- [x] WJ46 — **Fix exit-intent misfires + move the prompt to the peak-interest moment.** The bare `visibilitychange→hidden` trigger fires when the user switches to the camera/gallery to photograph their meter — the exact action the form invites. Add a grace window / suppress while the file picker is open; and (research) show the « Recevez ce devis sur WhatsApp en 1 clic » offer at the moment the instant estimate renders (peak engagement, works on mobile) rather than only as an exit trap. **Why:** exit-intent is desktop-only and increasingly ignored; the estimate-render moment is the honest, mobile-real equivalent. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WJ47 — **Split `bootCaptureOnly` into its own lazy chunk.** mon-toit dynamically imports all of `roof-tool-pro11.ts`, dragging scene3d/optimizer/matrix (internal-tool code) into the public capture bundle — import `roofPro11/captureBoot` directly and verify with a bundle-size check. **Why:** mobile visitors pay a heavy JS tax for code the capture page never runs. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/scripts/roof-tool-pro11.ts

**B — Capture elevation (funnel research):**
- [x] WJ48 — **Estimate-step polish: anticipation, image pickers, honest caveats, competitive line.** Add a branded 1.5–2.5 s « calcul de votre potentiel… » animation before the estimate renders (Enpal's tested anticipation device — never an instant flash); convert text dropdowns (type de toit…) into tappable image cards; keep kWc + économies + amortissement on the SAME screen pre-contact (Tesla's zero-extra-click transparency — verify, fix if gated); one-line caveat « estimation préliminaire, affinée après visite » beside the number; and the competitive positioning line « estimation immédiate — pas une simple demande de rappel sous 24 h » (verified: masolaire.ma's "devis" is callback-only). **Why:** these are the four highest-frequency patterns separating top funnels from good ones, each cheap. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WJ49 — **Restage the optional-refinement block (10+ questions in one `<details>`).** Split into 2–3 value-framed groups (« pour affiner la taille » / « pour le financement ») with ≤5 fields visible per stage, and re-check the total pre-CTA field count against the 7-field abandonment cliff (Formstack 2025); keep every field optional and forwarded as today (WJ30/31 contract intact). **Why:** form research is unambiguous — one long panel gets ignored or kills completion; staged asks don't. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WJ50 — **Context-rich per-page wa.me prefills + voice-note invitation.** Every WhatsApp CTA site-wide carries a page-specific, locale-specific prefilled message (page, estimate summary when known) so the team opens each chat already informed and each entry point is distinguishable in the CRM; add « vous pouvez aussi envoyer un vocal avec une photo de votre facture » to the journey's WhatsApp copy. **Why:** prefilled wa.me converts far better than blank chats in MENA, and a large share of Moroccan customers naturally reply by voice note. @files: apps/web/src/components/StickyCta.astro, apps/web/src/components/Footer.astro, apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/whatsapp.ts
- [x] WJ51 — **Explicit contact-preference toggle.** Turn the blanket « pas d'appels commerciaux » promise into a named choice — « Uniquement sur WhatsApp » vs « Un conseiller peut m'appeler » — forwarded through the webhook (maps to the CRM's canal field). **Why:** EnergySage's single contact-preference control is its most-cited trust differentiator; it also gives the team real routing data. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts
- [x] WJ52 — **Post-submit reference code.** Return/derive a short reference from the capture flow and show it in the success block (« mentionnez le code … sur WhatsApp ») so the 24–48 h wait has an artifact; keep it web-side (no new backend requirement — echo a client-generated code through the webhook payload). A full `/suivi/[ref]` status page is the later, backend-backed step (would need a PLAN2 twin — do NOT build the backend here). **Why:** the post-submit void is the weakest moment of an otherwise strong funnel. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts

**C — Proposal elevation (close-rate research):**
- [x] WJ53 — **Cash vs échelonné toggle with live monthly recalculation.** On the proposal, an interactive « payer comptant / paiement échelonné (X mois) » toggle recomputing an indicative monthly figure from the TTC total, clearly flagged « à confirmer — hors offre bancaire ferme »; renders on top of the existing WJ10/WJ32 financing block, no invented rates. **Why:** every 2026 proposal-software vendor converges on interactive financing math as THE close-rate lever, ahead of visual polish. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ54 — **« Demander une modification » structured revision request.** A lightweight form on the proposal (ajuster kWc / changer batterie / autre + free text) posting through the existing proposition-contact proxy as a structured revision request. **Why:** lets an undecided client negotiate without a phone call — the pattern EnergySage's no-pressure reputation is built on. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/pages/api/proposition-contact.ts
- [x] WJ55 — **Proposal view/engagement telemetry.** Fire first-view and scrolled-to-financing events from `/proposition/[token]` through a same-origin proxy to the existing lead webhook (event type field; reuse LEAD_WEBHOOK secret — no new secret), so the CRM can time follow-up to the moment the client is actually reading the numbers. **Why:** Aurora-class proposals are trackable; follow-up timed to a re-open converts far better than calendar drips. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/pages/api/ (new same-origin proxy)
- [x] WJ56 — **WhatsApp share + tablet presentation QA.** A « Partager sur WhatsApp » action on the proposal (share the tokenized link with a spouse/co-decider without re-entering anything), and an explicit layout QA pass at tablet/desktop widths so a rep can present the same page live in person. **Why:** solar decisions are two-person decisions, and the best proposals serve async AND live-presented modes from one URL. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ57 — **Trust at the signature itself.** Place one short testimonial (video slot when WG6 lands, text fallback) + the cert/warranty badges immediately above the e-sign block — not only in the higher trust sections. **Why:** bottom-of-funnel testimonial placement measurably outperforms scattered placement, and a single-installer flow must supply at the sign moment the reassurance a marketplace supplies via competing bids. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ58 — **Honest response-time promise near every capture/sign CTA.** A static badge « Réponse WhatsApp sous X, 7j/7 » with X = the number Reda commits to in WG9 (ship with the current honest « 24–48 h » until then; NEVER a countdown). **Why:** speed-to-lead research says the first responder wins most deals — but only a kept promise builds trust, so the number is founder-gated. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/proposition/[token].astro (@after: WG9 for the faster number)
- [x] WJ59 — **Step-level funnel analytics (same-origin, no new dependency).** A tiny privacy-light beacon (step reached / step abandoned, no personal data) posted to a same-origin endpoint that forwards to the existing webhook, so the next optimization round targets the REAL drop-off step. **Why:** research shows progress bars shift abandonment rather than remove it — without step data we're guessing where the funnel leaks. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/api/ (new)

---

### W245–W252 — JOURNEY ↔ SITE TIE-IN: make `/devis/mon-toit` the site's one front door (2026-07-02)

- [x] W245 — **Index the journey.** Remove `noindex` from the `/devis/mon-toit` family (FR/EN/AR), narrow the sitemap exclusion so ONLY `/internal/` + `/proposition/` (+previews) stay excluded, and give the page real landing-page SEO: meta description selling the free instant estimate, OG image, hreflang (already in STATIC_TRANSLATED), and meta copy claiming the verified differentiator (« estimation instantanée + design 3D + signature en ligne » — no surveyed Moroccan competitor combines all three). **Why:** the site's #1 conversion page is invisible to the search intent it exists to serve; the "private tunnel" decision predates it becoming the primary CTA. @files: apps/web/src/pages/devis/mon-toit.astro (+ en/ar), apps/web/astro.config.mjs
- [x] W246 — **Footer: journey link + warm close.** Add the locale-aware journey link as a prominent footer action, plus a slim closing brand strip (one confident line + zellige mark) and a single low-friction WhatsApp recapture. **Why:** the most important page has zero footer presence on any locale, and the footer currently ends cold on a legal line — the last thing a non-converting visitor sees should be a warm door, not a sitemap. @files: apps/web/src/components/Footer.astro
- [x] W247 — **RegimeSelector CTA → journey.** Its « faites vérifier votre dossier » button routes to `/contact` while its guide-page twin correctly routes to the journey — align it (locale-aware). **Why:** a high-intent regulatory CTA leaks out of the funnel; last CTA the routing audit found off-journey. @files: apps/web/src/components/RegimeSelector.astro
- [x] W248 — **Link the journey from the 2 blog posts that mention it without a link.** batterie-lfp… (l.106) and prix-installation… (l.90) name the simulator/diagnostic with no href — add the inline link the other posts already have. **Why:** telling a reader a free tool exists without a path to it is a free conversion left on the table. @files: apps/web/src/content/blog/batterie-lfp-dyness-deye-huawei.md, apps/web/src/content/blog/prix-installation-solaire-maroc-2026.md
- [x] W249 — **One funnel: retire the parallel DiagnosticForm captures.** Remove the `<DiagnosticForm/>` mounts from index/résidentiel/professionnel/contact (FR/EN/AR — 12 files), replacing them with the W250 inline instant-estimate widget (or a rich CTA card into the journey); repurpose `/contact` as a pure « parler à un humain » page (WhatsApp, phone, NAP, rappel — keep it indexed and restore a clear footer label); keep `DiagnosticForm.astro` + `/api/simulate` in the codebase untouched as the documented fallback. **Why:** two divergent capture funnels on the same pages split attribution and contradict the founder's one-journey instruction; contact-as-human-page is what visitors expect it to be. @files: apps/web/src/pages/{index,résidentiel,professionnel,contact}.astro (+ en/ar), apps/web/src/components/DiagnosticForm.astro (untouched)
- [x] W250 — **Inline instant-estimate widget on the homepage (the estimator IS the funnel).** A lightweight bill-input module (facture → live kWc + ≈MAD/mois range from the existing engine) embedded high on the homepage, repeated as a compact pre-footer module, its CTA deep-linking into `/devis/mon-toit` with the entered bill prefilled. **Why:** every world-tier site (Enpal/Otovo/Palmetto/Sunrun) puts the instant estimate ON the landing page 2–4×; taqinor's single biggest CRO asset currently requires a click away to feel. @files: apps/web/src/pages/index.astro (+ en/ar), apps/web/src/components/ (new widget), apps/web/src/lib/billEstimate.ts
- [x] W251 — **Header CTA carries a proof fragment.** On long-scroll pages (guides/blog), the sticky header CTA pairs the brass button with a small live proof element (install count / rating once WG5 lands) instead of the button alone. **Why:** Enpal's persistent-nav-with-review-count measurably outperforms a bare button on educational content. @files: apps/web/src/components/Header.astro
- [x] W252 — **« Comment ça marche » 4-step band under the hero, matching the REAL journey.** Estimation instantanée → Étude personnalisée signée → Devis + signature en ligne → Installation & SAV — the exact stages the built journey actually delivers, shown as the near-universal 3-4-icon device. **Why:** a visible defined process is an implicit objection-handler (« que se passe-t-il après le formulaire ? ») and ours is truthfully better than competitors'. @files: apps/web/src/pages/index.astro (+ en/ar)

---

### W253–W264 — SERVICES: the complete, findable catalogue (founder ask, 2026-07-02)

- [x] W253 — **Elevate `/nos-solutions` into the TRUE services hub.** Add the missing EV-charging card (page exists, invisible); a « Comment on finance votre projet » strip; visible cross-links to équipement + garanties (« ce que vous recevez »); frame the free étude/diagnostic as a first-class service; fix the « Six métiers » copy + JSON-LD `hasPart` to the real count; and make the hub RICHER than the homepage teaser (icons it currently lacks, one-line « quand la choisir » qualifier per card). **Why:** the hub undercounts the real offer (services audit found 9–10 real service lines, hub says six) and is currently poorer than the homepage grid it duplicates — the click must be rewarded. @files: apps/web/src/pages/nos-solutions.astro (+ en/ar), apps/web/src/pages/index.astro
- [x] W254 — **EV-charging page: translate + surface.** Create en/ + ar/ mirrors of `recharge-voiture-electrique-solaire.astro` (same elevation pattern as the other 6), add it to Header/Footer Solutions arrays, homepage solutions, and STATIC_TRANSLATED. **Why:** a fully-built 387-line pillar page is invisible in every nav on every locale — free inventory. @files: apps/web/src/pages/recharge-voiture-electrique-solaire.astro (+ new en/ar), apps/web/src/components/{Header,Footer}.astro, apps/web/src/i18n/pages.ts
- [x] W255 — **Maintenance & SAV as a headline capability + productized entretien tiers.** Re-lead `maintenance-monitoring` so ticket-backed SAV/dépannage is a co-equal headline (the ERP runs a real SAV module — a differentiator currently reduced to a phrase), and scaffold 2–3 NAMED contrat-d'entretien tiers (inclusions per tier; response-time SLAs + prices flagged `pending founder validation`), each tier with a prefilled WhatsApp CTA. **Why:** research shows O&M sells as named tiers, never as « contactez-nous », and after-sales is Taqinor's most defensible real asset. @files: apps/web/src/pages/maintenance-monitoring.astro (+ en/ar)
- [x] W256 — **« Étude & diagnostic gratuit » as a first-class service.** A dedicated hub card + section (or slim page) presenting the free study as a service in itself — explicitly « gratuit, sans engagement, design 3D de votre toit offert » (risk-reversal framing research validates) — CTA into the journey. **Why:** the free study is currently only a process step; competitors sell it as a product, and it targets « étude solaire gratuite » searches. @files: apps/web/src/pages/nos-solutions.astro (+ en/ar)
- [x] W257 — **Monitoring presented by outcomes, not specs.** 2–3 phone-mockup views (production live, alerte, économies à date — rendered from the site's own honest visuals, no fake dashboards), one sentence each, plus « alerte WhatsApp en cas d'anomalie » — on maintenance-monitoring. **Why:** buyers ask « est-ce que je vois ma production sur mon téléphone ? », not which protocol; screenshot-outcome framing is the universal pattern. @files: apps/web/src/pages/maintenance-monitoring.astro (+ en/ar)
- [x] W258 — **Financement page: named, verified Moroccan mechanisms.** Restructure `/financement` around the real named stack — per segment: agricole (CAM « Saquii Solaire » + FDA ~30 % pump subsidy via DPA/ORMVA), entreprises (exonération TVA équipement, leasing type Maghrebail Energy Lease), résidentiel (prêts verts bancaires) — EVERY named program gated on WG11 verification before publishing, zero partnership claims. **Why:** named checkable mechanisms beat « financement disponible » copy and no surveyed competitor surfaces the full stack; but a wrong claim would be worse than none. @files: apps/web/src/pages/financement.astro (+ en/ar) (@after: WG11)
- [x] W259 — **Loi 82-21 currency pass — « Où en est la loi ? » dated explainer.** Across loi-82-21 + regularization + guides: a clearly dated block distinguishing what is LIVE (MT/HT surplus tariff, décret d'application 2026 — verify exact décret number/dates against BO/ANRE primary sources before publishing) from what is PENDING (BT résidentiel — expected ~2027), with validity windows on every tariff figure and a « faites régulariser votre installation existante » CTA. **Why:** the 2026 decree made 82-21 real news — homeowners now find it and wrongly assume it applies to them; being the most CURRENT honest source is a rankable differentiator competitors haven't built. @files: apps/web/src/pages/loi-82-21.astro, apps/web/src/pages/regularization-article-33.astro, apps/web/src/pages/guides/loi-82-21-expliquee.astro (+ en/ar)
- [x] W260 — **Professionnel: facility-type sub-cards.** Split the single « hangars, usines, hôtels, cliniques » block into self-identification cards (entrepôt/usine · hangar agro-industriel · commerce/hôtellerie · collectivités) each with one relevant proof point. **Why:** C&I buyers self-identify by building type before thinking in kWc — the pattern every strong C&I page uses. @files: apps/web/src/pages/professionnel.astro (+ en/ar)
- [x] W261 — **Pompage page to sibling parity, farmer-first.** Real hero image (reuse the agricole quote-engine hero assets), an honest capability stats band, a diagram of the 4-variable sizing (débit/HMT/forage/besoins), diesel/butane-vs-solar framing mirroring the agricole quote PDF (same story, same numbers), and a financing/subvention card (FDA 30 % + Saquii — gated WG11, labeled « à vérifier auprès de votre DPA »). **Why:** the page is visibly a tier below its siblings while agricole is a real revenue line — and farmers evaluate against fuel cost, not kWc. @files: apps/web/src/pages/pompage-solaire.astro (+ en/ar) (@after: WG11 for the financing card)
- [x] W262 — **Zones desservies, honestly.** An explicit service-area block (axe Casablanca–Rabat + the real named cities) on the hub + contact, consistent with actual capacity — no implicit « tout le Maroc ». **Why:** explicit geographic honesty outperforms vague national claims on trust, and matches the site's own integrity rule. @files: apps/web/src/pages/nos-solutions.astro, apps/web/src/pages/contact.astro (+ en/ar)
- [x] W263 — **Shared service FAQ bank + itemized warranties.** One reusable FAQ set (fréquence d'entretien, comment le prix est calculé, inclus/exclus, délais, garanties) localized per service page ABOVE its CTA, and a per-component warranty table (panneaux/onduleur/batterie/main-d'œuvre, real years) surfaced on product-touching pages instead of only inside the PDF. **Why:** in-page FAQs close objections before the CTA (Aira/Sunrun pattern) and itemized warranty terms are treated by buyers as primary content, not fine print. @files: apps/web/src/components/ (FAQ bank), apps/web/src/pages/{résidentiel,professionnel,pompage-solaire,batteries-stockage}.astro (+ en/ar)
- [x] W264 — **Header menus: hierarchy + honest split.** Reuse the existing per-solution SVG icons as leading glyphs in the Solutions dropdown, visually feature the primary paths, and split « Ressources » so service-adjacent items (financement, marocains-du-monde) read as offer, not blog. Keep CSS-only + keyboard-accessible. **Why:** flat 8-item text menus slow the primary choice; financing filed under « resources » undersells a decision-critical service. @files: apps/web/src/components/Header.astro

---

### W265–W279 — HOMEPAGE & SITE ELEVATION ROUND 4 (art-director critique + world-best research)

- [x] W265 — **One mid-page light tonal break on the homepage.** Render one section (e.g. the 25-year investment story) as a light blanc-azur editorial band around position 3–4 so the narrative breathes dark→light→dark. **Why:** eight consecutive navy card-grids read as one long list — the single strongest structural gap vs the world tier. @files: apps/web/src/pages/index.astro (+ en/ar)
- [x] W266 — **The founder moment (human presence).** A short first-person signed note + real portrait (use the existing `FounderPortrait.astro` — currently built but mounted NOWHERE; replace à-propos's duplicate inline block with it) in the « Pourquoi Taqinor » section: « Je signe chaque étude — Reda Kasri ». **Why:** the copy promises founder-signed studies and a no-call-center team but the site never shows a single face — intimacy claimed, never demonstrated. @files: apps/web/src/pages/index.astro (+ en/ar), apps/web/src/pages/à-propos.astro, apps/web/src/components/FounderPortrait.astro **(SUPERSEDED 2026-07-04 by WA1 — founder RULE A: NO founder portrait or "je signe chaque étude" on the homepage; the portrait/signature belongs ONLY on /à-propos.)**
- [x] W267 — **Money-framed hero.** Beside the 21 406 kWh proof figure, a money sub-line derived from the same real install (« ≈ X MAD effacés de la facture chaque année », computed honestly from the measured production × the real tariff logic) — money leads, kWh stays as credibility. **Why:** homeowners can't price a kWh; WJ9 already proved the money-first reframe on the proposal — the homepage hero never got it. @files: apps/web/src/pages/index.astro (+ en/ar)
- [x] W268 — **Monumental proof band.** Reflow the 2×2 trust dl into a full-width 4-across band with `.fig-lg` numerals and thin brass rules (GarantiesTeaser's own pattern). **Why:** « la preuve avant la promesse » is the brand thesis but currently renders as a spec table, not a statement. @files: apps/web/src/pages/index.astro (+ en/ar)
- [x] W269 — **Cinéma du chantier: actual motion.** Reuse the hero's deferred-muted-loop technique in VideoChantier — on scroll-into-view (reduced-motion + saveData gated), swap the poster for a 3–6 s muted teaser loop, play button overlaid for full playback. **Why:** a section named « cinema » that renders a frozen JPEG undercuts its own promise; the technique already exists in the codebase. @files: apps/web/src/components/VideoChantier.astro
- [x] W270 — **WhatsAppMock plays out the conversation.** Staggered bubble arrival + brief typing indicator on scroll-into-view (reduced-motion → all visible instantly). **Why:** « on répond en quelques minutes » is asserted next to a static mock — demonstrating it is the whole point of the section. @files: apps/web/src/components/WhatsAppMock.astro
- [x] W271 — **Proof gallery: lightbox + city filter.** Click-to-enlarge lightbox (caption ville · kWc · production, keyboard + reduced-motion safe) on the homepage gallery, plus light client-side city filter chips (Toutes · Casablanca · El Jadida · Nouaceur) over data the cards already carry. **Why:** the flagship photography deserves a linger moment, and « des installations près de chez moi » is a known relevance lift — both from existing data. @files: apps/web/src/pages/index.astro (+ en/ar)
- [x] W272 — **Fix the double-CTA close on landing pages.** Where the estimate widget/CTA already closes résidentiel/professionnel, differentiate or drop the redundant trailing CtaBand — the second band offers a DISTINCT next step (WhatsApp humain / voir une réalisation proche), never the same ask twice. **Why:** two identical asks back-to-back deflate the close. (Pairs with W249/W250.) @files: apps/web/src/pages/résidentiel.astro, apps/web/src/pages/professionnel.astro (+ en/ar)
- [x] W273 — **Copy-distinctiveness pass.** Replace the 2–3 most-repeated boilerplate phrases (« étude gratuite », « dimensionné sur votre facture », « matériel tier-1ᵉʳ ») with page-specific lines rooted in real differentiators (mesuré sur Deye Cloud, l'étude signée par le fondateur, named towns) — every claim stays factual; no two pages open on the same promise. **Why:** honest proof deserves better than generic-solar scaffolding around it. @files: apps/web/src/pages/*.astro (copy only)
- [x] W274 — **Chapter-numbering consistency.** The 01/02/03 azur eyebrow system exists only on the homepage — extend it to the landing pages' major sections (or remove it); one editorial system, applied everywhere. **Why:** a half-applied magazine device reads as an oversight, not a style. @files: apps/web/src/pages/{résidentiel,professionnel,pompage-solaire}.astro (+ en/ar)
- [x] W275 — **Stronger below-the-fold cue on the hero.** Pair the easy-to-miss chevron with a short label (« Voir nos réalisations mesurées ») or let a sliver of the next section peek above the fold. **Why:** on a 100svh photographic hero, one faint chevron is the only signal that the site continues. @files: apps/web/src/pages/index.astro, apps/web/src/styles/global.css
- [x] W276 — **« Notre moteur, conçu au Maroc » — the in-house engineering story.** A homepage section telling the truthful story: Taqinor built its own bill-driven estimator, 3D roof engine and premium quote engine (1KOMMA5° TechLab pattern) — with a live link into the journey to feel it. **Why:** a real installer-that-is-also-a-tech-company story is rare, truthful here, and differentiates more than any badge. @files: apps/web/src/pages/index.astro (+ en/ar)
- [x] W277 — **« Pourquoi la traçabilité compte » quality section.** A factual, cited block referencing the 2025 OMPC-flagged underperforming-imported-panels affair (≈25 % under rated output — cite the press, name no installer), countered by Taqinor's real brand/datasheet/warranty documents per line. Verify citations against the sources before publishing. **Why:** the cheap-panel fear is THE Moroccan quality objection, and a dated real event legitimizes the answer far better than « méfiez-vous des arnaques ». @files: apps/web/src/pages/équipement.astro, apps/web/src/pages/pourquoi-taqinor.astro (+ en/ar)
- [x] W278 — **Coupures & prépayé (Nour): the resilience segment.** Content block/guide addressing prepaid-meter households (auto cut-off at zero balance — verify Nour mechanics against ONEE primary sources first) and coupures anxiety, where the honest pitch is battery autonomy, independent of the BT-tariff gate. **Why:** a distinct, real pain point the savings-first framing misses entirely — and batteries are already in the catalogue. @files: apps/web/src/pages/batteries-stockage.astro or apps/web/src/pages/guides/electricite-pendant-les-coupures.astro (+ en/ar)
- [x] W279 — **« Impact Taqinor » honest yearly page.** A small page deriving cumulative real figures (kWc installés, production mesurée, CO₂ évité computed honestly) from REALISATIONS — scaled to what 5 installs honestly support today, designed to grow. **Why:** an accountability anchor (1KOMMA5° impact-report pattern) that press/partners can cite — small now, compounding. @files: apps/web/src/pages/ (new), apps/web/src/lib/realisations.ts (read-only) **(SUPERSEDED 2026-07-04 by WA5 — founder RULE B: /impact-taqinor must NOT headline "{installCount} installations" or "aujourd'hui elle est petite"; lead with kWc/kWh/CO₂, never the raw install count.)**

---

### W280–W289 — TRUST & PROOF ENGINE (audit: components exist, wiring + real content missing)

- [x] W280 — **Wire the no-op-safe trust components onto the high-consideration pages.** InstallCounter + CertLogoRow → à-propos + garanties; StarRating → contact; CertLogoRow + BrandStrip → realisations — all render nothing until data lands, so this is pure zero-risk wiring. **Why:** the pages a skeptical prospect visits to decide (à-propos, garanties, realisations, contact) currently carry ZERO trust components while the funnel pages carry them all. @files: apps/web/src/pages/{à-propos,garanties,contact}.astro, apps/web/src/pages/realisations/index.astro (+ en/ar) **(PARTIALLY SUPERSEDED 2026-07-04 by WA2 — founder RULE B: keep the trust wiring, but InstallCounter's raw install-COUNT tile must be dropped; only the kWc figure may stay.)**
- [x] W281 — **VideoChantier on /realisations.** Mount the existing component + real chantier-a.mp4 below the gallery. **Why:** the dedicated proof hub has photos but no video while the asset sits production-ready, used only on the homepage. @files: apps/web/src/pages/realisations/index.astro (+ en/ar)
- [x] W282 — **Video-testimonial slot (scaffold).** Extend Testimonials.astro with a self-hosted mp4/webm slot (WhatsApp-shot UGC style — research: unpolished beats produced on trust), rendered only when WG6 supplies real clips; text/photo fallback unchanged. **Why:** video testimonials are the single strongest bottom-funnel lift and the channel (WhatsApp) makes collection trivially easy. @files: apps/web/src/components/Testimonials.astro (@after: WG6 for real clips)
- [x] W283 — **Case-study caption standard.** Every gallery/realisations entry carries « [Ville] — X kWc — installé en Y jours — Z kWh mesurés » (only real measured fields; omit what isn't measured). **Why:** captioned proof doubles as a calibration tool (« un toit comme le mien ») — bare photo grids don't. @files: apps/web/src/lib/realisations.ts, apps/web/src/pages/realisations/index.astro
- [x] W284 — **Precise counters, never rounded.** Sweep displayed stats to derive precise figures from REALISATIONS (43,48 kWc style) instead of any rounded/static number. **Why:** specificity itself reads as proof (Enpal's 2 436 533 requests pattern) — and derived counters can't silently go stale. @files: apps/web/src/pages/index.astro, apps/web/src/components/InstallCounter.astro **(PARTIALLY SUPERSEDED 2026-07-04 by WA2/WA3 — founder RULE B: precise kWc/kWh/CO₂ counters are fine, but the raw install-COUNT must never be a featured stat.)**
- [x] W285 — **« Visiter un chantier » becomes an action.** Third WhatsApp quick-link on /contact (« Je souhaite visiter une installation réelle ») matching the invitation pourquoi-taqinor already makes. **Why:** the site's rarest trust offer (visitable, monitored, real installs — no surveyed competitor has it) currently has no button. @files: apps/web/src/pages/contact.astro (+ en/ar)
- [x] W286 — **Footer social row (data-gated).** A social-icons row rendering only the URLs WG8 supplies — never placeholder icons. **Why:** an absent social presence is a legitimacy check many prospects run; fabricated handles would be worse than none. @files: apps/web/src/components/Footer.astro (@after: WG8)
- [x] W287 — **ICE/RC legal identity (data-gated).** Add the company registration (ICE/RC) to mentions-légales and optionally the footer legal line once WG8 supplies it. **Why:** B2B buyers verify legal identity before signing large contracts; it's currently nowhere on the site. @files: apps/web/src/pages/mentions-legales.astro, apps/web/src/components/Footer.astro (@after: WG8)
- [x] W288 — **`sameAs` entity wiring (data-gated).** Add the sameAs array (GBP, socials) to the LocalBusiness JSON-LD from NAP/testimonials data once WG5/WG8 supply URLs — no-op until then. **Why:** the cheapest entity-consolidation signal Google documents, currently missing. @files: apps/web/src/layouts/Layout.astro (@after: WG5, WG8)
- [x] W289 — **« Installations visitables, production mesurée » as an indexable pillar.** Elevate /realisations with an SEO-framed intro section + appropriate schema so the measured-data/visitable angle ranks for « installation panneaux solaires casablanca avis »-class queries. **Why:** verified as a whitespace — none of ~10 surveyed Moroccan competitors publish measured production or visitable sites; it deserves to be findable, not just a homepage block. @files: apps/web/src/pages/realisations/index.astro (+ en/ar)

---

### W290–W299 — SEO / AEO / CONTENT REACH (technical audit + 2026 search research)

- [x] W290 — **HowTo schema on the two step-by-step pages.** guides/combien-de-panneaux (étapes facture→kWc→panneaux) + regularization-article-33 (5 étapes), alongside their existing Article schema. **Why:** literal step-content with zero HowTo markup is free rich-result eligibility. @files: apps/web/src/pages/guides/combien-de-panneaux-pour-ma-maison.astro, apps/web/src/pages/regularization-article-33.astro
- [x] W291 — **`image` field in Article/BlogPosting JSON-LD.** Wire the already-computed OG image URL into the schema objects (blog template + guides). **Why:** Google explicitly recommends it for Article rich results; the URL already exists, only the wiring is missing. @files: apps/web/src/pages/blog/[...slug].astro, apps/web/src/pages/guides/*.astro
- [x] W292 — **Category OG images.** Dedicated OG images for the service pages + one generic « guides » + one « blog » (7 images cover 110+ pages today; everything else shares the homepage image on WhatsApp/social shares). **Why:** in a WhatsApp-first market, the link preview IS the first impression of every shared page. @files: apps/web/public/og/, page ogSlug props
- [x] W293 — **Evergreen « Prix panneaux solaires Maroc » pillar.** A non-dated landing page carrying the honest indicative brackets already researched for the 2026 blog post (designed for yearly refresh, validity-dated figures), internally linked from résidentiel/nos-solutions/guides/blog; the dated post links to it as canonical context. **Why:** the site's highest-commercial-intent head term currently lives only in a dated blog post that will age out. @files: apps/web/src/pages/ (new), apps/web/src/content/blog/prix-installation-solaire-maroc-2026.md
- [x] W294 — **Close the guides EN/AR gap (8 guides).** Translate the remaining FR-only guides to EN + AR (AR first for the money guides: quelle-taille-de-batterie, combien-de-panneaux, on-grid-off-grid) following the existing mirror pattern; register in STATIC_TRANSLATED for hreflang. **Why:** 9 of 12 guides serve only FR intent while AR organic search is a distinct large audience the site invested in everywhere else. @files: apps/web/src/pages/{en,ar}/guides/ (new), apps/web/src/i18n/pages.ts
- [x] W295 — **Blog EN/AR for the two money posts.** Translate prix-installation-solaire-maroc-2026 + rentabilite-solaire-par-ville-maroc, add /blog to the localized routing once en/ar blog routes exist. **Why:** the blog is 100 % FR-only including its highest-value pricing article — the MRE segment the site targets reads EN. @files: apps/web/src/content/blog/, apps/web/src/pages/{en,ar}/blog/ (new), apps/web/src/i18n/pages.ts
- [x] W296 — **City-page thinness guard.** For CITIES entries with `hasLocalInstall:false`, add real city-specific differentiation (regional distributor name, honest « nearest install » distance framing) — and if a page can't be honestly differentiated, canonicalize/noindex it until a real local install exists. **Why:** near-identical stat tiles across programmatic city pages is the classic doorway-page pattern Google demotes — honesty and SEO point the same way here. @files: apps/web/src/pages/installation-solaire-[city].astro, apps/web/src/lib/cityContent.ts
- [x] W297 — **AEO/GEO pass: make the answers quotable.** Restructure the highest-value FAQ/guide content (82-21, prix, financement, coupures) into self-contained Q&A blocks with clean FAQPage coverage so AI assistants (Google AI Overviews / ChatGPT) can cite taqinor.ma as the source for Moroccan solar questions. **Why:** AI-referred sessions are a real 2026 channel with different structuring rules than classic SEO — and the site's honest, dated, cited content style is exactly what answer engines reward. @files: apps/web/src/pages/faq.astro, apps/web/src/pages/guides/*.astro (+ en/ar)
- [x] W298 — **Schema type + NAP consistency.** Evaluate the most specific correct LocalBusiness subtype for a solar installer (against the real schema.org hierarchy — only switch if genuinely more specific/correct), and reconcile the NAP string byte-for-byte with the Google Business Profile listing once WG5 confirms it. **Why:** entity-trust consolidation is cheap and cumulative; a NAP formatting drift silently dilutes it. @files: apps/web/src/layouts/Layout.astro, apps/web/src/lib/nap.ts (@after: WG5 for the GBP string)
- [x] W299 — **Topic-cluster internal-linking pass.** Systematic hub↔spoke↔guide↔blog linking per cluster (prix/résidentiel · pompage/agricole · 82-21/régularisation · batteries/coupures), so every money page is reachable from its cluster and vice-versa. **Why:** research is unanimous that clustered internal linking (not more pages) is what makes existing content rank; the site has the content, not yet the mesh. @files: apps/web/src/pages/ (links only), apps/web/src/components/RelatedLinks.astro

---

### 2026-07-02 ROUND 2 — EXHAUSTIVE DEEP PASS (founder request; 18-agent fan-out + 2 adversarial critics)

**Where this comes from.** Reda asked for a second, exhaustive round on top of the same-day round-1
battery. 16 specialist agents attacked the dimensions round 1 did NOT cover — WCAG/RTL
accessibility, performance, editorial content quality, the deep page templates, a pixel-level
proposal audit, the capture journey's full failure-state machine, security/privacy, trilingual
drift, estimation-number integrity, award-tier design craft, B2B/C&I selling, referral & post-sale,
the measurement stack, the content-distribution engine, page-level competitor teardowns, and
on-site AI — then 2 adversarial critics (six persona walkthroughs; the "true world #1" bar) hunted
for what BOTH rounds still missed. Every task below is net-new vs round 1 and carries its one-line
**Why**. Same cross-cutting constraints as the round-1 battery (webhook contract, no invented
numbers, self-consumption-first, FR+AR, Lighthouse 97–100, zero CLS, reduced-motion, no fake
urgency).

**Conflicts resolved here:** (a) the security audit suggested `robots.txt Disallow: /devis/` — that
would fight W245 (journey becomes indexable); resolution: W319 adds ONLY `/proposition/` to
robots.txt. (b) The i18n/estimator audits proved WJ22 (climate confidence band) and WJ23
(per-utility tariffs) are marked done but live ONLY in the private lab — WJ71/WJ70 surface them or
correct the record. (c) Design-craft tasks explicitly BUILD ON queued round-1 tasks (W246/W252/
W264/W265/W270) — coordinate, never duplicate.

**F0 — Fix-first honesty & correctness (site-wide):**
- [x] W300 — **Correct the BT-tariff overreach on 6+ pages (FR+AR).** Three guides, three blog posts, regularization-article-33 (+AR mirrors) state the 0,18–0,21 DH/kWh surplus tariff as settled fact FOR THE <11 kW residential (BT) declaration case — but ANRE's decision covers MT/HT only; BT is unpublished. Verify Decision 04/26's scope against ANRE primary sources; add the « tarif MT/HT uniquement — BT résidentiel non encore publié » caveat everywhere it's missing (or the confirming citation if BT is genuinely covered), and fix CONTENT_SEO_NOTES.md's PUBLISH-SAFE tag that seeded the drift. **Why:** the site's single honesty rule is « no invented numbers » — this is the one place it's currently broken, on the highest-stakes regulatory topic. @files: apps/web/src/pages/guides/{quelle-taille-de-batterie,faut-il-des-batteries,onduleur-hybride-ou-reseau}.astro (+ar), apps/web/src/content/blog/{loi-82-21-autoproduction-2026,batterie-stocker-ou-revendre-maroc,rentabilite-solaire-par-ville-maroc}.md, apps/web/src/pages/regularization-article-33.astro, apps/web/CONTENT_SEO_NOTES.md
- [x] W301 — **Reconcile the 25-year degradation figures.** A blog post's generic « 80–85 % à 25 ans » reads as a downgrade of the site's precise ≥ 84,8 % warranty — reframe as « notre garantie va au-delà du standard (80–85 %) : ≥ 84,8 % » and fix the CONTENT_SEO_NOTES summary. **Why:** two numbers for the same fact is exactly what a skeptical reader checks. @files: apps/web/src/content/blog/rentabilite-solaire-par-ville-maroc.md, apps/web/CONTENT_SEO_NOTES.md
- [x] W302 — **Kill the French leaks in EN/AR figures: « ans », « 84,8 », comma-decimals.** The EN AND AR mirrors of garanties/résidentiel/professionnel/financement + GarantiesTeaser literally render « 25 ans » (French unit word) inside English/Arabic sentences; « 84,8 % » (French comma) sits next to « 84.8 % » in the same files; en/résidentiel + en/professionnel mix comma- and period-decimals (11,36 vs 11.36). Sweep all of it — numbers stay byte-identical, only unit words/separators localize. **Why:** broken bilingual text on the exact trust numbers a prospect reads to decide. @files: apps/web/src/pages/{en,ar}/{garanties,résidentiel,professionnel,financement}.astro, apps/web/src/components/GarantiesTeaser.astro
- [x] W303 — **Guides get dates, authors, reading time.** Add a « Vérifié le [date] » + author byline to the guide template (the blog already has the mechanism) and wire the existing estimateReadingTime util + a freshness badge into guides/index cards. **Why:** guides carry volatile tariff facts with zero visible date — an E-E-A-T and trust gap the blog already solved. @files: apps/web/src/pages/guides/*.astro, apps/web/src/pages/guides/index.astro, apps/web/src/lib/readingTime.ts
- [x] W304 — **De-duplicate the three overlapping inverter/backup guides.** on-grid-off-grid = architecture overview; electricite-pendant-les-coupures = the deep EPS page; onduleur-hybride-ou-reseau loses its duplicated anti-îlotage/82-21 paragraphs to one-line cross-links. **Why:** three near-duplicate explanations dilute topical authority instead of building it. @files: apps/web/src/pages/guides/{on-grid-off-grid-ou-hybride,electricite-pendant-les-coupures,onduleur-hybride-ou-reseau}.astro
- [x] W305 — **Small content-quality fixes.** Gloss or cut the unexplained « CAN BMS » acronym; refresh the EV post's aging fuel-price figure (or add « prix au [date] » note + updatedDate); cross-link the guide↔blog battery-cost twins. **Why:** three cheap fixes the content audit caught that each chip at the plain-language/consistency discipline. @files: apps/web/src/pages/guides/onduleur-hybride-ou-reseau.astro, apps/web/src/content/blog/recharger-voiture-electrique-solaire-cout-maroc.md, apps/web/src/pages/guides/faut-il-des-batteries.astro
- [x] W306 — **Two missing high-anxiety guides: roof structural load + home insurance.** « Mon toit peut-il supporter des panneaux ? » (weight/m², Moroccan roof types needing a structural check) and an insurance FAQ section (declaring the install, typical coverage — generic, non-legal-advice). **Why:** the two most-asked pre-purchase objections a best-in-class Moroccan solar library answers and this site doesn't. @files: apps/web/src/pages/guides/ (new), apps/web/src/pages/garanties.astro
- [x] W307 — **Publish the promised chantier-retrospective blog post.** The welcome post (2026-06-21) explicitly promised real-chantier stories; none exists — write one from a real REALISATIONS entry (El Jadida 17,04 kWc). **Why:** an unkept editorial promise on the founder's own blog, and the strongest content format the site has data for. @files: apps/web/src/content/blog/ (new), apps/web/src/lib/realisations.ts (read-only)

**G0 — Trilingual parity backfill (drift the sweep proved):**
- [x] W308 — **Port the elevated realisations hub to EN/AR.** FR got the lightbox + hover-zoom + case-study nudge (W178/W179/W204) after the mirrors were translated — EN (91 lines) and AR (92) vs FR (351) browse a visibly older proof page. Port it, keeping localized alt/labels. **Why:** the dedicated proof page is a tier poorer in the two locales the MRE audience uses most. @files: apps/web/src/pages/{en,ar}/realisations/index.astro
- [x] W309 — **Port the phased Avant/Pendant/Après case-study galleries to EN/AR.** The phase data already exists in realisations.ts — EN/AR templates just never got the phased sections + lightbox (FR 516 lines vs EN 196/AR 204). **Why:** a template gap, not a data gap, on the page meant to prove the work. @files: apps/web/src/pages/{en,ar}/realisations/[slug].astro
- [x] W310 — **Restore the dropped KeyFigure + Callout blocks in EN/AR faut-il-des-batteries.** Both mirrors silently lost the 6 000-cycles stat block and the « bon réflexe » tip the FR version carries. **Why:** the money guide steering battery purchases is missing its two most persuasive elements in exactly the locales flagged as translation priorities. @files: apps/web/src/pages/{en,ar}/guides/faut-il-des-batteries.astro
- [x] W311 — **RTL logical-property fixes in shared components.** Callout + RegimeSelector accent borders (border-left → border-inline-start), WhatsAppMock bubble tails/corner-cuts (fixed left/right offsets), Header hover-underline (left-0 → inset-inline-start-0). **Why:** four small physical-CSS leaks that visibly misalign under dir=rtl on a site that claims RTL-native design. @files: apps/web/src/components/{Callout,RegimeSelector,WhatsAppMock,Header}.astro
- [x] W312 — **Wire or delete the 9 dead i18n dictionary keys.** breadcrumb.home exists in ui.ts but 49+ pages hardcode « Accueil/Home » inline; 8 more keys have zero callers. Either wire Breadcrumb + callers to the dictionary or delete the dead keys. **Why:** a dictionary that half-lies about what's live is a maintenance trap. @files: apps/web/src/i18n/ui.ts, apps/web/src/components/Breadcrumb.astro
- [x] W313 — **CI locale-parity drift guard.** A small script (check-locale-parity) asserting, for every STATIC_TRANSLATED path + realisations/cities slugs, equal h2/h3/section counts AND an equal set of imported components between FR and its EN/AR mirrors — fail with a diff list. **Why:** every drift W308–W310 fixes was invisible until a manual file-by-file diff; the next FR elevation will silently outpace the mirrors again without a guard. @files: apps/web/scripts/ (new), CI web-build-test wiring
- [x] W314 — **Make the closed mobile menu truly unreachable.** #mobile-menu keeps focusable links behind aria-hidden="true" — toggle `inert` alongside aria-hidden in the same handler. **Why:** keyboard users silently tab into invisible links on every page; an ARIA-authoring violation with a one-attribute fix. @files: apps/web/src/components/Header.astro

**H0 — Security & privacy hardening:**
- [x] W315 — **Ship security headers from the Worker.** CSP (self + api.taqinor.ma + MapTiler + PVGIS; inline-script allowance or nonces), HSTS, frame-ancestors 'none', Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy (geolocation self), nosniff — injected in redirect-entry.mjs (the existing response-wrapping point) + a headers test mirroring cache.test.ts. **Why:** every response today ships with ZERO hardening headers; Referrer-Policy also protects the proposal token from leaking to third-party tile hosts. @files: apps/web/worker/redirect-entry.mjs, apps/web/worker/ (new headers.mjs + test)
- [x] W316 — **Rate-limit the unprotected endpoints.** proposition-accept, proposition-contact, roof-yield/roof-production/roof-estimate (PVGIS amplification), and the [token] page's server-side fetch — same shared rateLimit pattern capture-lead already uses, distinct buckets, generous tuning for the interactive roof endpoints. **Why:** the e-signature and token-guessing paths currently have no throttle at all while every lead endpoint does. @files: apps/web/src/pages/api/{proposition-accept,proposition-contact,roof-yield,roof-production,roof-estimate}.ts, apps/web/src/pages/proposition/[token].astro
- [x] W317 — **Same-origin checks + honeypot on the public POST surface.** Verify Origin/Sec-Fetch-Site on all four POST proxies (403 on cross-site), and add a hidden honeypot field rejected server-side to the capture forms. **Why:** « same-origin proxy » is currently documentation, not enforcement, and IP rate-limiting alone is per-isolate best-effort. @files: apps/web/src/pages/api/*.ts, apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts (additive only — webhook contract untouched)
- [x] W318 — **Privacy policy tells the whole truth + GDPR addendum + consent copy.** Rewrite « ce que nous collectons » (FR/EN/AR) to disclose the full real field set (GPS pin, roof outline, address, email, energy profile, financing intent, the drawn e-signature image); add a GDPR section for the EU-resident MRE segment (lawful basis, access/erasure rights, contact); update the e-sign consent line to mention the drawn-signature image. **Why:** the policy currently describes 5 fields while the journey collects ~15 — a real loi 09-08/CNDP information-duty gap, and the site explicitly serves EU residents. @files: apps/web/src/pages/politique-de-confidentialite.astro (+en/ar), apps/web/src/pages/proposition/[token].astro
- [x] W319 — **robots.txt defense-in-depth for the proposal tunnel.** Add `Disallow: /proposition/` (and /internal/; keep /preview/) — deliberately NOT /devis/ (W245 makes the journey indexable). **Why:** the PII-bearing tokenized pages currently rely on meta-noindex alone, which requires fetching the page first. @files: apps/web/public/robots.txt

**I0 — Performance & delivery diet:**
- [x] W320 — **Preconnect hints for the map origin.** `<link rel="preconnect">` to api.maptiler.com (+raster host) on the three journey heads. **Why:** the capture page's most interactive moment pays a serial DNS+TLS handshake today (~100–300 ms on cold connections). @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)
- [x] W321 — **Immutable caching for static assets.** public/_headers with `Cache-Control: public, max-age=31536000, immutable` for /fonts/*, /photos/*, /videos/*, /fiches/*, /og/*. **Why:** a WhatsApp-shared multi-session journey means repeat visits; today assets rely on an unconfirmed platform default. @files: apps/web/public/_headers (new)
- [x] W322 — **Deploy diet: delete the 4.3 MB dead brand folder + retire the legacy pro2–pro10 lab.** public/brand/ is base64-PNG-in-SVG with zero code references; the 10 superseded preview routes each build a full three+maplibre chunk. **Why:** pure dead weight in every deploy and build. @files: apps/web/public/brand/ (delete), apps/web/src/pages/preview/toiture-3d-pro-{2..10}.astro + their scripts (founder-confirmed pro-11 is final)
- [x] W323 — **CI Lighthouse gate covering the pages that matter.** Lighthouse-CI in web-build-test over /, /devis/mon-toit, /proposition/[token] (seeded), /en/, /ar/ asserting the 97–100 floor AND the LCP element on the two journey pages (map-init-gated and chart-JS-gated — a score alone can pass while the meaningful content lags). **Why:** « Lighthouse 97–100 » is in every task's acceptance criteria but is currently an unenforced aspiration measured manually on 7 FR pages. @files: apps/web CI config, apps/web/scripts/
- [x] W324 — **Defer maplibre-gl until the visitor opens the map step.** After WJ47, maplibre (~200 KB+) still dominates the capture bundle — load it on map-step entry, not page boot, so bill-only estimators never pay it. **Why:** the single heaviest real payload on the highest-intent page, avoidable for the majority path. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/scripts/roofPro11/captureBoot.ts (@after: WJ47)
- [x] W325 — **Compress OG images in the generator.** pngquant/sharp pass in generate-og.mjs before W292 multiplies the count (current files are 183–325 KB). **Why:** in a WhatsApp-first market the link preview IS the first impression — and it should load instantly. @files: apps/web/scripts/generate-og.mjs (@before/with: W292)

**J0 — Template depth (produits, réalisations, villes, FAQ, MRE…):**
- [x] W326 — **Product pages: availability schema, pairings, comparison table.** Offer/availability block in the fiche JSON-LD (no invented prices), structured {years, note} warranty, a « se combine avec » block via fichesByCategorie + RelatedLinks (built, unused there), and ONE comparison table on /équipement (2 panel brands × 2 inverter lines, facts already in fiches.ts). **Why:** the product surface has no rich-result eligibility, dead-ends after one product, and never compares — three staples of best-in-class spec pages. @files: apps/web/src/pages/produits/[slug].astro, apps/web/src/pages/équipement.astro, apps/web/src/lib/fiches.ts
- [x] W327 — **Case studies: client voice + peer comparison.** Optional clientQuote field rendered in the récit (no-op until WG6 supplies real quotes) + a « kWc le plus proche du vôtre » nearest-case link. **Why:** five case studies read as installer self-report, and no case study offers the « one like mine » next step buyers actually want. @files: apps/web/src/lib/caseStudies.ts, apps/web/src/pages/realisations/[slug].astro
- [x] W328 — **City pages: derive real differences, disclose delegataire reality.** Use the committed sunshineHours delta (2 800 Rabat → 3 400 Agadir) to nuance the ROI band per city instead of one verbatim stat block, and add the « barème Lydec/Redal/Amendis à confirmer sur votre facture » line on the 3 delegataire cities until WG2 lands. **Why:** honest differentiation from data the pages already carry, and a live tariff-accuracy risk on the 3 biggest urban markets. @files: apps/web/src/pages/installation-solaire-[city].astro, apps/web/src/lib/cityContent.ts
- [x] W329 — **Blog library UX: themes + guide cross-links.** Theme/tag field in the content schema, filter chips on blog/index (mirroring guides' groups), and a « guide associé » link on posts sharing a theme. **Why:** the blog is one flat undifferentiated grid while its topics cluster exactly onto existing guides. @files: apps/web/src/pages/blog/index.astro, apps/web/src/content/config
- [x] W330 — **FAQ: visible clusters + deep-linkable anchors.** Render the 8 topic clusters already implied in faq.ts comments as h2 sections with a stable id per question. **Why:** a flat 20-item accordion undermines findability AND the W297 AEO goal of independently citable answers. @files: apps/web/src/pages/faq.astro, apps/web/src/components/Faq.astro
- [x] W331 — **Garanties/financement: worked example, exclusions, claim process.** One fully-worked numeric walkthrough on /financement (bill → kWc → investissement → économie → payback, published figures only); a « ce qui n'est pas couvert » exclusions clause + a « si la performance tombe sous 84,8 % » scenario box + a « comment faire jouer votre garantie » step list (contact channel, install ref + photo of the fault, honest response window tied to WG9) on /garanties. **Why:** decision pages state numbers without ever walking one; warranties list only inclusions (stating exclusions reads MORE honest — Aira's pattern); and no page tells an owner how to actually USE a warranty. Exclusions verified by Reda (WG16). @files: apps/web/src/pages/financement.astro, apps/web/src/pages/garanties.astro (+en/ar)
- [x] W332 — **MRE page: the three real blockers — procuration, timezone, paying from abroad.** A factual procuration/delegate-signing answer, an honest Morocco-time response window under the « fuseau horaire » claim (ties WG9), and a « comment payer depuis l'étranger » section (real accepted path: virement to the company account in MAD, staged milestones — mechanics confirmed via WG16, no invented fees). **Why:** the persona walkthrough showed the page sells trust but never answers the three mechanical questions that decide whether a remote purchase can proceed. @files: apps/web/src/pages/marocains-du-monde.astro (+en/ar) (@after: WG16)
- [x] W333 — **Pourquoi-Taqinor: name the alternative.** One factual contrast line per pillar (e.g. « la plupart des devis au Maroc partent d'un kit standard avant de voir votre facture »), no competitor named — can lean on the W277 OMPC fact as evidence. **Why:** the differentiation page proves competence but never frames the comparison a shopper is actually making. @files: apps/web/src/pages/pourquoi-taqinor.astro (+en/ar)
- [x] W334 — **24-hour energy-flow diagram on batteries.** A 4-panel jour/soir/coupure/nuit visual (solaire→consommation→batterie→réseau) with existing iconography. **Why:** « production le jour, stockage le soir » is currently prose only — Aira proved the visual version of this exact explainer. @files: apps/web/src/pages/batteries-stockage.astro (+en/ar)

**K0 — B2B/C&I depth on /professionnel:**
- [x] W335 — **CFO-grade finance framing.** Add the « économie cumulée sur 20 ans » derived line to the existing proBrackets table (existing constants, no new numbers), split each segment card into a financial line + a technical/operational line, and a two-column « Achat (CAPEX) / Leasing (OPEX) » structural comparator (who owns, who books depreciation, day-one cash flow — no named bank rates; W258/WG11 fill the named boxes). **Why:** C&I buyers evaluate solar as a financing decision; the page today shows only cash-purchase brackets in one undifferentiated voice. @files: apps/web/src/pages/professionnel.astro (+en/ar)
- [x] W336 — **The corporate tax facts nobody uses: TVA 123-22° + amortissement 20 ans.** A founder/legal-skimmed section citing CGI art. 123-22° (import-VAT exemption on solar equipment as fixed asset for VAT-registered companies, 36-month window + 2026 extension) and the standard 20-year/5 % linear depreciation — cited code articles, not partnership claims. **Why:** the two universal CFO levers, verified real for Morocco, absent from every competitor page — and the site currently states only the residential non-exemption. (@after: WG16 legal skim) @files: apps/web/src/pages/professionnel.astro, apps/web/src/pages/financement.astro (+en/ar)
- [x] W337 — **B2B entry offer + procurement trust.** Reframe the /professionnel entry CTA as « Audit énergétique gratuit de votre site » (same journey/webhook), add the « visiter un chantier » invitation (W285's pattern) to its contextual links, and mount CertLogoRow + an RC-Pro/assurance line near the pricing table once WG8 lands. **Why:** an audit-sounding first step outperforms « devis » for buyers who must build an internal case, and procurement scrutiny is highest exactly where the trust artifacts currently aren't. @files: apps/web/src/pages/professionnel.astro (+en/ar) (@after: WG8 for the trust strip)

**L0 — Referral, post-sale & the doors that don't exist:**
- [x] W338 — **/parrainage: the public face of the referral system the ERP already has.** Landing page (FR/EN/AR) explaining the mechanic in plain language, personal links riding the EXISTING utm_campaign passthrough (…/devis/mon-toit?utm_source=parrainage&utm_campaign=<code> — zero backend change for v1), clear terms copy (self-referral ban, reward paid on real milestone), digital-opt-in framing (never door-to-door), its own OG image, footer link. Reward amount + trigger milestone stay gated (WG14) — no invented figure. **Why:** apps/crm has a full Parrainage model and internal page but the website has zero surface — the plumbing exists, the tap was never installed; solar spreads neighbor-to-neighbor. @files: apps/web/src/pages/parrainage.astro (new, +en/ar), apps/web/src/components/Footer.astro (@after: WG14 for the reward figure)
- [x] W339 — **« Déjà client ? » SAV/urgence door.** A visible block on /contact (+footer link): « un souci sur votre installation ? » with a dedicated WhatsApp/tel path prefilled as an existing-client fault report (routes to the SAV team — separate from the sales lead webhook, which stays untouched) + a one-line « que faire si votre onduleur affiche une erreur » reassurance. **Why:** the persona walkthrough's sharpest miss — an existing client with a Sunday inverter fault currently has NO path on the entire public site; every door is prospect-shaped. @files: apps/web/src/pages/contact.astro (+en/ar), apps/web/src/components/Footer.astro
- [x] W340 — **« Après votre installation » + Espace client entry.** A narrative section (mise en service → suivi de production → ouvrir un ticket SAV → garanties) grounded in the real ERP capability, plus an « Espace client » footer/header entry pointing to the real monitoring access (Deye Cloud) — content-only; any custom portal is backend and stays out. **Why:** ownership experience is now baseline world-tier sales content, and the site's realest differentiator (a live SAV system) has no public door. @files: apps/web/src/pages/maintenance-monitoring.astro (+en/ar), apps/web/src/components/{Header,Footer}.astro
- [x] W341 — **Milestone review-request asset.** A shareable « Comment ça s'est passé ? » WhatsApp-prefilled message/page template the team sends at day 14–21 post-install, linking to the GBP review URL once WG5 lands. **Why:** review requests timed to a milestone convert far better than immediate asks — this is the WHEN/HOW layer on top of WG5's claim task. @files: apps/web/src/ (small asset) (@after: WG5)
- [x] W342 — **« L'installation la plus proche de chez vous ».** On the estimate result (and proposal), surface the nearest real case study by the city/GPS already captured (haversine over the small REALISATIONS array, client-side) — honestly scoped to the real cities. **Why:** peer proximity is the strongest documented adoption driver in early solar markets, and the data (their pin, our installs) already exists on both sides. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/proposition/[token].astro, apps/web/src/lib/realisations.ts
- [x] W343 — **Post-signature referral composer.** On the proposal's signed/thank-you state, a « Partager avec un proche » WhatsApp composer with the client's tagged parrainage link — distinct from WJ56's co-decider share of the SAME proposal. **Why:** the moment of highest satisfaction is the moment referral asks convert; WhatsApp-native loops are the proven MENA mechanic. @files: apps/web/src/pages/proposition/[token].astro (@after: W338)
- [x] W344 — **Realisations → referral soft CTA.** « Un proche a un profil similaire ? Recommandez Taqinor » on each case study, linking /parrainage. **Why:** the strongest trust asset currently dead-ends at photos. @files: apps/web/src/pages/realisations/[slug].astro (@after: W338)
- [x] W345 — **Presse & partenaires block.** On à-propos (or a slim page): a dedicated press/partnership contact channel distinct from the sales form, a one-line factsheet (founding, city, real install count from realisations.ts, ICE/RC once WG8 lands), a downloadable logo. **Why:** a journalist or bank doing due diligence is currently funneled into « Obtenir mon étude gratuite » — the site has no door for the people who legitimize it. @files: apps/web/src/pages/à-propos.astro (+en/ar)

**M0 — Content-distribution engine (the site's side):**
- [x] W346 — **LiteVideo primitive + the no-iframe standing rule.** Extract VideoChantier's (already correct) click-to-play facade into a reusable LiteVideo.astro (src/poster/aspectRatio/alt — vertical-ready), and add the STANDING RULE: social video on /, the journey, /realisations and the proposal is self-hosted MP4 behind the facade; third-party iframes only ever on the blog. **Why:** the facade pattern is ~800 ms of LCP protection; codifying it prevents the first careless YouTube embed from breaking the perf budget. @files: apps/web/src/components/{VideoChantier,LiteVideo}.astro, this file (STANDING RULES)
- [x] W347 — **« Compteur à zéro » video scaffold.** VideoCompteur slot (LiteVideo) on the homepage + proposal near the savings figures, flagged `pending real footage from Reda` (15–30 s of a real client's meter/app showing the drop). **Why:** the single most persuasive clip genre in solar marketing, and the site has real installs to film it at. @files: apps/web/src/components/ (new), apps/web/src/pages/index.astro, apps/web/src/pages/proposition/[token].astro
- [x] W348 — **Lead magnets, WhatsApp-first and ungated.** « 10 questions à poser avant de signer » page (/ressources/, FR+AR, guides template, indexable, NO email gate — WhatsApp CTA primary); the « Analyse gratuite de votre facture » named entry card (nos-solutions + homepage → journey pre-set to the bill step); the printable pompage sizing worksheet (HMT/débit/heures/culture) inviting a photo back via wa.me. **Why:** checklists are the highest-converting magnet format, but for THIS audience WhatsApp delivery beats every email gate — and the bill-analysis offer repackages the existing engine as a third low-friction door. @files: apps/web/src/pages/ressources/ (new), apps/web/src/pages/nos-solutions.astro, apps/web/src/pages/pompage-solaire.astro (+en/ar)
- [x] W349 — **The zero-form door: « envoyez une photo de votre facture sur WhatsApp — on s'occupe de tout ».** A prominent form-bypass entry on pompage-solaire and as the homepage hero's secondary action, deep-linking a wa.me prefill that asks for a bill photo/voice note; include one short Darija line alongside the fus'ha AR. **Why:** the persona walkthrough proved the low-literacy WhatsApp-only visitor (a real segment, esp. agricole) cannot complete ANY wizard — the site needs one honest door that requires reading nothing. @files: apps/web/src/pages/pompage-solaire.astro, apps/web/src/pages/index.astro (+en/ar), apps/web/src/lib/whatsapp.ts
- [x] W350 — **/liens social hub + case-study bio-links.** A minimal link-in-bio page (logo + 5 buttons: réalisations, estimation, WhatsApp, blog, Channel once created) and per-install landing targets + wa.me prefills on case studies so every social post has one consistent trackable destination. **Why:** Instagram/TikTok allow exactly one link; today it would dump onto the homepage with zero context. @files: apps/web/src/pages/liens.astro (new), apps/web/src/pages/realisations/[slug].astro
- [x] W351 — **The 1-install→4-assets repurposing pipeline, written down.** A short checklist doc per completed install (case-study entry, blog retrospective, one vertical clip, proposal-proof photos) + update WJ13/WJ57 acceptance to « video testimonial preferred, photo fallback » + verify what the blog « scheduler » actually is before extending it. **Why:** the growth engine is a process, not a feature — formalizing it turns every field visit into four assets instead of one. @files: docs/ (short note), this file (WJ13/WJ57 note)

**N0 — World-#1 plays (the true-#1 critic's gaps):**
- [x] W352 — **« Garantie de production Taqinor » scaffold.** A distinct block on /garanties framing an honest annual-kWh floor guarantee (modeled from PVGIS, stated remedy), shipped `pending founder commitment` — no number until WG12. **Why:** a measurable production guarantee is the strongest single world-tier differentiator, and Taqinor's own measured Deye Cloud data could credibly back one. @files: apps/web/src/pages/garanties.astro (+en/ar) (@after: WG12)
- [x] W353 — **« Réserver un créneau de visite technique » v1.** Post-estimate step offering honest visit windows (static picker forwarded through the existing webhook as a preference — no calendar dependency); the online-deposit (CMI) question stays a WG13 founder decision, NOT built. **Why:** the funnel dead-ends at « on vous répond sous 24–48 h » while world-tier funnels let a decided buyer commit to a slot in-session. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar), apps/web/src/lib/lead.ts (additive field) (@after: WG13 for the windows)
- [x] W354 — **/production-mesuree: rolling public fleet transparency.** A small page (or homepage band) rendering the honestly-dated cumulative measured production from realisations.ts (« cumul mesuré sur nos installations au [date] »), refreshed per Deye Cloud export (WG7 cadence). **Why:** live-ish public transparency on real production is a brand-gravity play no Moroccan competitor can copy without the data. @files: apps/web/src/pages/ (new), apps/web/src/lib/realisations.ts **(PARTIALLY SUPERSEDED 2026-07-04 by WA4 — founder RULE B: /production-mesuree must NOT headline "{installCount} installations, un seul compteur"; frame around measured kWh/kWc, never the install count.)**
- [x] W355 — **/ensoleillement-maroc: publish the data moat.** Render YIELD_TABLE as a public, citable « productible solaire par ville, inclinaison et orientation » resource (dated PVGIS source note), linked from the orientation + combien-de-panneaux guides. **Why:** category leaders publish a dataset others must link to; ours sits locked in a TS file. @files: apps/web/src/pages/ (new), apps/web/src/lib/yieldTable.ts
- [x] W356 — **A takeaway at the estimate step.** « Enregistrer mon estimation » generating a lightweight client-side one-pager (kWc + fourchette + caveat + wa.me link) as PNG/PDF or a stable share URL. **Why:** the public estimate — the site's #1 CTA — currently evaporates when the tab closes; WhatsApp-first buyers share artifacts. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] W357 — **Installable, offline-tolerant PWA.** Manifest → standalone + maskable icon + a minimal service worker caching the shell + the visitor's last estimate (scope: caching only, no push). NOTE in DONE LOG as a new capability. **Why:** a spotty-network, mid-range-Android market is exactly where installable + offline-recall earns real usage; WJ45 only adds a banner. @files: apps/web/public/site.webmanifest, apps/web/ (sw)
- [x] W358 — **/embed/estimation partner widget.** An iframe-safe, chrome-less instant-estimate route (reusing billEstimate) deep-linking back to the full journey with the bill prefilled + utm_source=partner. **Why:** turning the best tool into distribution — partner sites (agri suppliers, real-estate) become lead channels competitors can't match. @files: apps/web/src/pages/embed/ (new)
- [x] W359 — **/methodologie-estimation transparency page.** The honest model, published: PVGIS source, losses, self-consumption-first savings and why (ANRE BT unpublished), « préliminaire, affiné après visite », linked from the journey + proposal assumptions block. **Why:** radical method transparency converts the site's real integrity discipline into a visible trust asset — and it's the grounding page any future AI layer cites. @files: apps/web/src/pages/ (new), apps/web/src/pages/devis/mon-toit.astro
- [x] W360 — **The honest cost of waiting.** On the estimate reveal: « chaque mois d'attente ≈ Y MAD non économisés » derived from the same self-consumption savings figure — no countdown, no invented rate. **Why:** reframing delay as ongoing loss is the strongest urgency-free motivator, and the number already exists in the engine. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)

**O0 — Award-tier craft (design research; every item reduced-motion-gated, zero-CLS, Lighthouse-neutral):**
- [x] W361 — **Native scroll-driven animation layer + scroll-scrubbed counters.** Progressive `animation-timeline: view()` under @supports for the .v2-rise/.cine-in reveals (IO fallback stays), and the trust/garanties figure bands scrub with scroll instead of fire-once count-ups. **Why:** compositor-thread scroll motion is 2026's defining « how did they do that » feel — and it's CHEAPER than the JS observer it replaces. @files: apps/web/src/styles/{v2,global}.css, apps/web/src/components/V2Enhance.astro, apps/web/src/lib/countup.ts
- [x] W362 — **Motion token system.** 2–3 shared --ease-*/--dur-* custom properties refactored through the existing reveals/hovers/shimmers. **Why:** the site's motion is correct but unauthored — one shared curve accent is what makes motion read as designed. @files: apps/web/src/styles/global.css (+v2, v3-photo-motion refs)
- [x] W363 — **Grain over the navy gradients.** A ~2–3 % opacity tiling SVG feTurbulence .grain-overlay on the hero scrim, .seam-lumiere, .diag-lumiere, .cine-card. **Why:** kills visible dark-gradient banding — the cheapest « expensive » tell on premium dark themes. @files: apps/web/src/styles/global.css
- [x] W364 — **View-transition morphs: gallery photo → case-study hero.** Cross-document view transitions with matching view-transition-name per install image (+ stable names for logo/CTA); Astro auto-respects reduced-motion. **Why:** the morph pairs already exist unused — MPA continuity that reads instantly as high craft. @files: apps/web/src/layouts/Layout.astro, apps/web/src/pages/index.astro, apps/web/src/pages/realisations/
- [x] W365 — **The signature moment: one brass light-sweep across the hero headline.** One-shot masked gradient sweep after load (never delaying LCP paint), reusing the .seam shimmer easing. **Why:** « la lumière vient des chantiers » is the brand thesis — the headline is the one place the light never touches. @files: apps/web/src/pages/index.astro
- [x] W366 — **Zellige draws itself.** Replace the scale/rotate pop with an SVG stroke-dashoffset line-draw of the star (static final state for no-JS/reduced-motion); same for ZelligeDivider. **Why:** self-drawing line-work suits a geometric mark far better than a generic pop — a crafted reveal for near-zero cost. @files: apps/web/src/components/{ZelligeSignature,ZelligeDivider}.astro
- [x] W367 — **text-wrap: pretty on prose.** Body copy, leads and blog/guide paragraphs (balance stays on headings); verify AR line-rhythm unaffected. **Why:** the most recognizable « typeset by a human » tell in editorial-tier sites, one CSS line. @files: apps/web/src/styles/{global,prose}.css
- [x] W368 — **Magnetic primary CTA.** ~8 px pointermove translate on the hero brass button, (pointer:fine) + reduced-motion gated, transform-only. **Why:** micro-craft invested exactly where the single-CTA discipline points every visitor. @files: apps/web/src/pages/index.astro
- [x] W369 — **Footer as the last art-directed frame.** An oversized wordmark/brand line + large zellige glyph + generous air ABOVE the (untouched) link grid — coordinates with W246's journey-link/strip, does not duplicate it. **Why:** world-tier sites end on a designed moment; ours ends on a sitemap. @files: apps/web/src/components/Footer.astro (@with: W246)
- [x] W370 — **Mega-panel menu with a live preview card.** Two-column Solutions dropdown: links (W264's glyphs) + a featured card (real install thumb + measured figure) swapping on hover — CSS-first, keyboard-safe. **Why:** menu-as-content is the craft tier above W264's glyph pass. @files: apps/web/src/components/Header.astro (@after: W264)
- [x] W371 — **ONE pinned scrollytelling beat: the journey section.** The « comment ça se passe » steps highlight as paired copy scrolls past a sticky column (view-timeline/IO), collapsing to the plain grid on mobile + reduced-motion. **Why:** one restrained pinned narrative is the pattern juries reward — and the linear journey story fits it perfectly. @files: apps/web/src/pages/index.astro (@with: W252)
- [x] W372 — **Tonal rhythm system (beyond W265's single band).** Compose a 3–4 beat dark↔light homepage rhythm with the existing .seam-lumiere/.diag-lumiere transitions at every boundary — every tonal cut becomes a crafted seam. **Why:** W265 inserts one light room; the award tier is a composed rhythm. @files: apps/web/src/pages/index.astro, apps/web/src/styles/global.css (@after: W265)
- [x] W373 — **Hero depth layer.** One slower-parallax brass light-mote/vignette plane over the hero (transform/opacity only, never touching LCP first paint). **Why:** single-plane heroes read flat next to the layered depth current winners use — and the hero already claims « cinéma ». @files: apps/web/src/pages/index.astro, apps/web/src/components/V2Enhance.astro
- [x] W374 — **Crafted link hovers.** Mask/clip-path underline drawing from the leading edge (RTL-aware logical properties) on nav + inline links; reduced-motion collapses to the instant underline. **Why:** the one generic interaction pattern left on an otherwise-authored site. @files: apps/web/src/components/Header.astro, apps/web/src/styles/global.css
- [x] W375 — **One monumental type moment.** A pull-figure/eyebrow at clamp ~8–10 rem using the Archivo width axis on one homepage section (the proof band), body kept calm; zero-CLS verified. **Why:** dramatic scale contrast is the clearest art-directed typography tell — the current scale tops out conservative. @files: apps/web/src/styles/v2.css, apps/web/src/pages/index.astro
- [x] W376 — **Reading progress on guides/blog.** A 2 px brass scroll()-driven reading bar (fixed, zero-CLS, reduced-motion-gated) on long article templates. **Why:** long-form affordance every editorial-tier site ships and ours lacks. @files: apps/web/src/pages/blog/[...slug].astro, apps/web/src/pages/guides/, apps/web/src/styles/global.css
- [x] W377 — **[data-choreo] entrance choreography primitive.** One reusable staggered-entrance util (per-child --i, view-timeline driven) applied to WhatsAppMock, Testimonials, CertLogoRow — extends W270 into a system. **Why:** grouped elements sharing one authored entrance language is systemic craft, not per-component tweaks. @files: apps/web/src/styles/v2.css, apps/web/src/components/ (@with: W270)
- [x] W378 — **Make the Archivo width axis an interaction.** Whisper-subtle font-stretch transition (112 → 118 %) on the hero h1 reveal / nav hover, reduced-motion-gated, LCP-safe. **Why:** the site ships a 62–125 % variable width axis and only ever renders 3 frozen values — its built-in signature move, unused. @files: apps/web/src/styles/global.css, apps/web/src/pages/index.astro

**P0 — Machine-readable & governance:**
- [x] W379 — **llms.txt + explicit AI-crawler policy.** A <8 KB llms.txt (pitch + canonical links) and explicit GPTBot/ClaudeBot/PerplexityBot/Google-Extended lines in robots.txt (content bots allowed; /internal/ /proposition/ /preview/ stay disallowed). Honest expectations: a B2A signal, not an SEO lever. **Why:** cheap insurance for the AI-answer channel, consistent with the private-route rule. @files: apps/web/public/{llms.txt,robots.txt}
- [x] W380 — **facts.ts — one canonical machine-readable facts source.** Aggregate (not restate) the existing canonical values from nap.ts, billRange.ts, the FAQ array, garanties data into one exported artifact any grounding layer (llms.txt, a future assistant, W359's methodology page) cites. **Why:** the site's honest facts live scattered in five files; one aggregation point prevents every future consumer from re-deriving them ad hoc. @files: apps/web/src/lib/facts.ts (new)
- [x] W381 — **UTM governance doc.** The closed utm_source/utm_medium vocabulary + casing rule, capturing what current campaigns already imply. **Why:** the lead schema forwards UTM verbatim — an undocumented vocabulary drifts within a quarter and corrupts attribution. @files: docs/utm-governance.md (new)

---

### WJ60–WJ94 — QUOTE JOURNEY ROUND 4: state machine, numbers integrity, proposal round 2, a11y/RTL, funnel intelligence (2026-07-02)

**A — Capture state machine (the failure paths a real Moroccan network hits):**
- [x] WJ60 — **Client fetch timeouts + honest failure copy + pending label.** AbortSignal.timeout on the roof-config and capture-lead fetches (server proxies already do this); ≥500/malformed responses get « problème technique de notre côté — réessayez » instead of the field-blaming message; submit button reads « Envoi en cours… » during the wait. **Why:** slow 3G currently hangs the UI forever, then blames the visitor's data for our server errors. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)
- [x] WJ61 — **Wizard state survives refresh and back.** Persist step/mode/bill/pin/outline/optional answers to sessionStorage (rehydrate on load, clear on success), pushState per step so browser-back steps back instead of leaving, beforeunload guard once data is entered. **Why:** a phone call or accidental back-swipe currently destroys everything typed, silently — the single costliest UX failure in the funnel. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)
- [x] WJ62 — **Map failure states become visible.** geolocate 'error' → « Localisation refusée — cherchez votre adresse ou posez le repère »; mid-session tile/style errors reveal the existing manual-address fallback panel instead of console.warn; map controls move to top-left under RTL (opts.dir). **Why:** GPS denial is currently total silence and a mid-session MapTiler failure strands the visitor on a broken map. @files: apps/web/src/scripts/roofPro11/captureBoot.ts (localized via WJ41's strings)
- [x] WJ63 — **No French at the moment of failure, in any locale.** Translate the EN page's four hardcoded French error literals (validation summary, generic server error, network failure, exit-modal phone prompt), and stop rendering server-sent French (validateLead strings, the 429 rate message) raw — the client always prefers its own localized copy. **Why:** the highest-stakes microcopy (what you read when something goes wrong) is French on the EN page and leaks French onto AR. @files: apps/web/src/pages/en/devis/mon-toit.astro, apps/web/src/pages/ar/devis/mon-toit.astro
- [x] WJ64 — **Accept the diaspora's phone numbers.** Extend the phone path to accept a valid foreign E.164 (+33/+34…) flagged phoneIsForeign, forwarded as an additive field — the exact audience of marocains-du-monde currently gets a flat « Numéro invalide » and cannot submit at all. **Why:** the site invests in an MRE segment its own form locks out. @files: apps/web/src/lib/phone.ts, apps/web/src/lib/lead.ts (additive; 1 000 MAD logic untouched)
- [x] WJ65 — **Input sanity + smallest-screen fixes + honest no-JS exit.** Client-side MAX_BILL cap (« estimation indisponible — vérifiez le montant » instead of a confident absurd number), require ≥1 letter in the name (emoji/symbol names currently pass), mode selector stacks below ~360 px (grid-cols-1 sm:grid-cols-3), and a noscript block with a wa.me/tel exit. **Why:** four verified edge failures, each of which currently produces a silent lie or a dead end. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar), apps/web/src/lib/lead.ts
- [x] WJ66 — **Duplicate-lead protection + delivery-failure visibility.** A client-generated per-session idempotency token in the payload (additive field; CRM-side dedupe = PLAN2 cross-ref), and server-side alerting on repeated forwardLead failures. **Why:** retries create indistinguishable duplicate leads, and a silent CRM outage currently shows every visitor a false « enregistré » for days with no one alerted. @files: apps/web/src/lib/lead.ts, apps/web/src/pages/api/capture-lead.ts (additive only)
- [x] WJ67 — **« Pourquoi on vous demande ça » micro-transparency.** A one-line collapsible beside the exact-bill input (« le montant exact permet un calcul juste — jamais partagé »). **Why:** Palmetto's tested pattern for the one field that feels intrusive; copy-only. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)
- [x] WJ68 — **Professionnel journey mode.** When the pro mode (or W260's facility cards) is the entry: optional raison sociale, facility type carried through, and « combien de sites ? » (1 / 2–5 / 6+) — all optional, additive through the webhook. **Why:** C&I visitors currently fall into a single-family-shaped form with no way to signal company or portfolio scale. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts

**B — Numbers integrity (one engine, one truth):**
- [x] WJ69 — **One estimation engine.** Repoint billEstimate.ts from estimatorBrain (V1) to estimatorBrainV2 (same signatures), mark V1 + roof.ts's PANEL_WATT=550 as deprecated-lab-only, and reconcile the two battery cost constants (applianceConsumption's 3 500–6 000 range vs V2's uncalled 4 500 point) into ONE sourced value before anything ever renders it. **Why:** three parallel engines with duplicated constants WILL drift — the public journey currently runs the oldest one. @files: apps/web/src/lib/{billEstimate,estimatorBrain,estimatorBrainV2,applianceConsumption,roof}.ts
- [x] WJ70 — **Make the distributeur selector honest.** Either wire the collected ONEE/Lydec/Redal choice into a WJ23-aware estimate (V2's documented Lydec ≈ +10,5 % top-tranche premium) or state next to the selector that the figure is the conservative ONEE baseline for all distributors until WG2's real grids land. **Why:** the form currently collects a choice that provably changes nothing the visitor sees — worse than not asking. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/billEstimate.ts
- [x] WJ71 — **Surface WJ22's honesty band — or correct the record.** The climate-derate confidence band is gated behind a toggle that exists ONLY in the private lab; decide: default it on for the public estimate + proposal (companion function in billEstimate using V2's climateDerateFactor), or amend WJ22's done-note to say « lab-only ». **Why:** the plan currently implies client-facing honesty that isn't shipped. @files: apps/web/src/lib/billEstimate.ts, apps/web/src/pages/devis/mon-toit.astro, docs/WEB_PLAN.md (note)
- [x] WJ72 — **One number style end-to-end.** Shared formatKwc/format helpers so the instant estimate (raw « 7.5 kWc » period-decimal today) and the proposal (« 11,00 kWc » French comma) read as one system; sweep the proposal's hardcoded ranges (« 20–25 ans ») for the same convention; wrap Latin figures in <bdi>/unicode-bidi isolates in AR instead of forcing whole lines LTR. **Why:** a client comparing their estimate screenshot to their proposal sees two different number languages — and AR figures currently break sentence flow. @files: apps/web/src/lib/proposition.ts, apps/web/src/pages/devis/mon-toit.astro (+en/ar), apps/web/src/pages/proposition/[token].astro
- [x] WJ73 — **Explain the estimate-vs-proof gap.** The site's own hero installs measure ≈1 256 kWh/kWc/yr while the modeled table used for every estimate assumes 1 650 south-optimal — one honest line near the proof stats (« les installations réelles ne sont pas toutes plein sud à 29° — l'étude affine ») turns an arithmetic « gotcha » into a demonstrated-honesty point. **Why:** a numerate visitor doing division on our own flagship numbers currently finds a 24 % unexplained overshoot. @files: apps/web/src/pages/index.astro, apps/web/src/pages/installation-solaire-[city].astro
- [x] WJ74 — **Stamp and pin the yield table.** GENERATED_AT + PVGIS TMY window constants written by the generator, explicit startyear/endyear pinned in generate-yield-table.mjs, yearly refresh noted in the DONE LOG. **Why:** the table backing every estimate has no staleness marker and non-reproducible generation parameters. @files: apps/web/src/lib/yieldTable.ts, apps/web/scripts/generate-yield-table.mjs
- [x] WJ75 — **Document the 25-year escalation assumption.** State whether the backend's eco_a_cumul assumes tariff escalation; align or explicitly caveat the client-side 0 %-escalation fallback next to the 25-year headline. **Why:** the proposal's most persuasive number silently mixes two different growth assumptions depending on payload. @files: apps/web/src/lib/proposition.ts, apps/web/src/pages/proposition/[token].astro

**C — Proposal round 2 (pixel audit):**
- [x] WJ76 — **Stop the share-preview privacy leak.** og:title currently broadcasts « Proposition [REF] — [Client name] » over the homepage image on every WhatsApp forward of a private tokenized link — switch to a neutral generic og:title + a dedicated neutral branded proposal OG image. **Why:** a privacy leak at the exact moment a client shares their proposal with family. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/layouts/Layout.astro
- [x] WJ77 — **Reorder the persuasion arc: believe → want → act.** Credibility block + objection FAQ move ABOVE the signature; the CO₂/impact emotional beat becomes the last thing before the sign form. **Why:** proof currently arrives AFTER the ask — the one structural flaw in an otherwise strong page. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ78 — **Design the moment after signature.** Scroll the confirmation into view, a reduced-motion-safe celebration cue, inline next-steps (« Et après ? ») + PDF download in the success block, and echo the drawn signature (or a « signature enregistrée ✓ » seal) as the client's visible artifact. **Why:** the highest-intent moment in the whole business currently just hides a form. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ79 — **Finish the AR success state (extends WJ42).** The success stamp (« Réf. ») and « signé le … » time are hard-French even in AR — register them with the i18n busy-label system + ar-MA timestamp. **Why:** the reassurance moment right after signing flips to French for Arabic clients. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ80 — **Charts that speak the page's language — and the phone's.** AR month labels threaded into renderProposalChart/renderYearCurve (dual-node or re-render), a visible peak/annual value annotation, legible labels at phone widths, tap-to-reveal values (hover titles are invisible on touch). **Why:** the two most persuasive visuals are French-only and numberless on the mobile devices the audience actually uses. @files: apps/web/src/lib/{proposalChart,proposalCurve}.ts, apps/web/src/pages/proposition/[token].astro
- [x] WJ81 — **Never a blank white proposal.** Timeout + friendly retry on the SSR fetch (or a streaming shell painting the branded frame first), and a 15 s AbortController on the sign submit with « la connexion est lente — réessayez ou WhatsApp » instead of an eternal disabled « Signature… ». **Why:** the most commercially critical page currently hangs blank on slow networks and can trap a client mid-signature. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ82 — **Dead offers can't be signed.** Explicit states for refuse/expire/withdrawn statuses (localized, sign form + sticky suppressed); when expired, submit disabled and the sticky CTA becomes « Demander un devis actualisé »; verify the accept proxy 4xx-es cleanly on stale tokens. **Why:** a refused or expired quote currently renders as a fully live, signable proposal from both the inline form AND the persistent bottom bar. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/lib/proposition.ts (@with: WJ44)
- [x] WJ83 — **Zero-total guard.** A totals-less payload currently renders « 0 MAD TTC, clé en main » as a real price — hide price + CTA and show « prix communiqué par votre conseiller »; surface or simplify the near-dead ecoHero caption while there. **Why:** one degenerate payload away from quoting a client zero dirhams. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/lib/proposition.ts
- [x] WJ84 — **A printable proposal.** @media print hiding the lang switch/sticky/3D overlay with a clean light print, or a visible « pour un PDF officiel, utilisez Télécharger le devis » hint. **Why:** Ctrl-P on a proposal is a natural instinct that currently produces dark-on-dark chaos with floating chrome. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ85 — **Differentiate the doubt-point CTAs.** « Poser une question » and « Discuter » currently share one identical waLink — distinct prefills per intent + the voice-note invitation. **Why:** three buttons, two of which do the same thing, read as filler at the page's decision point. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ86 — **No visible scaffolds on a sales document.** « (Photos à venir.) » and the placeholder founder quote render as live text on client proposals — gate them to render NOTHING until WG5/WG6 content lands (the no-op pattern the trust components already use). **Why:** « coming soon » on someone's own proposal reads as an unfinished product at the trust-critical moment. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ87 — **Sign on behalf of the household.** Optional « je signe au nom de [propriétaire / mon foyer] » field beside the consent (FR/AR, EN with WJ43), captured additively in the accept payload; legal wording via WG16. **Why:** the MRE buying for his parents — and any couple deciding remotely — currently has no honest way to record a delegated/joint decision. @files: apps/web/src/pages/proposition/[token].astro

**D — Journey accessibility & RTL (WCAG 2.2 findings):**
- [x] WJ88 — **Screen-reader-complete capture form.** aria-describedby wiring error text to inputs (the pattern DiagnosticForm already uses), real h2 landmarks per step on a page that currently has ONE heading in 1 200 lines, a single clean estimate announcement (not skeleton+result double-fire in the live region), a ≥24 px exit-modal close target, and role="application" removed from the keyboard-inert map. **Why:** the site's most important page is currently near-unnavigable by screen reader — and every fix is small. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)
- [x] WJ89 — **RTL details that break the AR journey.** Literal « → / ← » arrow glyphs (unmirrored, untranslated) become the existing auto-mirrored SVG chevron; dir="ltr" added to the four numeric inputs (facture hiver/été, kWh, roof age) that phone/email already have. **Why:** wrong-direction arrows and RTL-jumping digits on exactly the fields that matter most. @files: apps/web/src/pages/ar/devis/mon-toit.astro (+fr/en for consistency)
- [x] WJ90 — **The 3D and the charts for everyone.** Keyboard controls on the proposal roof viewer (tabindex + arrow-rotate + ± zoom, hint copy updated) and a lang parameter on the SVG chart's title/desc so AR mode isn't announced in French. **Why:** the founder's « rotate and zoom YOUR home » promise currently excludes keyboard users entirely. @files: apps/web/src/scripts/roofPro11/viewerOnly.ts, apps/web/src/lib/proposalCurve.ts, apps/web/src/pages/proposition/[token].astro

**E — Funnel intelligence (the layer above WJ55/WJ59):**
- [x] WJ91 — **telemetryEvents.ts — the closed vocabulary.** One const dictionary (journey_step_viewed/_completed/_abandoned, estimate_rendered, whatsapp_clicked, proposal_viewed, proposal_scrolled_to_financing, proposal_signed; props step_id/mode/locale/page; step_ids mapped to the REAL steps) imported by both WJ55 and WJ59, plus a test asserting the beacon schema NEVER carries name/phone/email/address/GPS/outline (the redactLeadForLog discipline). **Why:** event vocabularies drift per call-site within a quarter, and one PII slip breaks the whole privacy-light premise. @files: apps/web/src/lib/telemetryEvents.ts (new) (@before: WJ55/WJ59 build)
- [x] WJ92 — **CAPI match quality.** Add hashed em (when email captured) + a per-submission event_id echoed in the CAPI payload and the lead record; the outcome-loop follow-up (backend fires on QUOTE_SENT/SIGNED) is a PLAN2 cross-ref, not built here. **Why:** Meta grades lead campaigns on Event Match Quality — the two biggest levers are currently absent and cost nothing. @files: apps/web/src/lib/lead.ts (additive)
- [x] WJ93 — **Cookieless measurement doctrine + staged-rollout primitive.** Written policy (no Set-Cookie/persisted IDs anywhere in analytics/experiments — this is what keeps the site consent-banner-free for EU visitors; no inferential A/B below ~50 conversions/variant/week — staged rollouts + funnel comparison instead), plus the tiny edgeVariant helper (per-request draw, no cookie) as the substrate. **Why:** the alternative — a cookie-based test tool — silently drags in a GDPR banner and produces noise-driven « winners » at this traffic level. @files: docs/experimentation-policy.md (new), apps/web/src/lib/edgeVariant.ts (new)
- [x] WJ94 — **Cloudflare Web Analytics beacon.** Env-gated (PUBLIC_CF_ANALYTICS_TOKEN, no-op unset), cookie-free, for sitewide traffic/CWV sanity — funnel truth stays in the WJ55/WJ59 event stream. **Why:** free, zero-consent visibility the site currently has none of. @files: apps/web/src/layouts/Layout.astro

---

### WJ95–WJ107 — QUOTE JOURNEY ROUND 5: real render defects + desktop/i18n/a11y + honest "call me" wiring (founder forensic audit, 2026-07-05)

**Why.** A 6-agent read-only forensic audit found the round-1–4 journey *submits* but has real
client-visible defects (a desktop white-on-white dropdown, a map that never renders, a mobile-only
desktop layout) and several controls that look wired but aren't (a "Demander un rappel" button that
is really just a WhatsApp link). These are the **website (`apps/web`) half**; the matching ERP
receivers are **Group QW in `docs/PLAN2.md`** (cross-referenced per task). Callback wiring uses the
free path (founder decision 2026-07-05). Nothing here touches the lead-data flow's honesty rules or
adds a paid dependency.

- [ ] WJ95 — **Fix the desktop white-on-white `<select>` (systemic).** Add a GLOBAL `select option { background-color: var(--color-nuit,#070b1d); color:#fff }` fallback (plus `color-scheme: dark` on the controls) in `global.css`, right after the existing `color-scheme:dark` block — porting the fix that ALREADY exists scoped-to-4-IDs in `preview/toiture-3d-pro-11.astro:1117-1133` but was never applied to the production forms. Root cause: `html{color-scheme:dark}` + `inputClass`'s `text-white` inherited into `<option>` with no option-background fallback → invisible until hover on desktop Chromium/Windows. Affects 9 selects on `/devis/mon-toit` (tranche, mono/tri, distributeur…). **Why:** the single most-reported desktop bug — the pickers look empty until you hover a row. @files: apps/web/src/styles/global.css
- [ ] WJ96 — **Make the roof map actually render, and make a bad key VISIBLE.** **(a) SHIPPED 2026-07-05 — CONFIRMED LIVE ROOT CAUSE.** Live `/api/roof-config` returned `available:true` with BOTH a MapTiler key AND a `mapboxToken` set; `buildSatelliteStyle` switches to `api.mapbox.com` tiles when a Mapbox token exists, but the live CSP (`worker/headers.mjs`) only allowed `api.maptiler.com` — so the browser blocked every Mapbox tile and the map stayed blank (silently). It worked before the Mapbox token because MapTiler tiles were allowed. Fix landed: added `https://api.mapbox.com` to BOTH `img-src` and `connect-src` + a test asserting it in both directives. (The "misnamed `PUBLIC_MAPTILER_KEY`" hypothesis was DISPROVEN — the key is set correctly.) REMAINING: (b) log a clear Worker warning + a non-prod diagnostic when a map key resolves empty (client fallback stays graceful) so a future mis-config isn't invisible; (c) call `ensureMapBooted()` for a sessionStorage-resumed visitor who lands past step 0. **Why:** the founder reported the map never shows to clients — (a) was the cause and is fixed; (b)/(c) are robustness. @files: apps/web/worker/headers.mjs, apps/web/tests/headers.test.ts, apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/api/roof-config.ts
- [ ] WJ97 — **Turn `/contact` "Demander un rappel" into a REAL, distinct callback request.** Today it's a raw `wa.me` link mislabeled as a phone callback that never reaches the CRM. Give it a short inline name+phone capture that POSTs a lead through the webhook with `contactPreference=phone_ok` (distinct from every WhatsApp CTA) and honest "on vous rappelle" copy, keeping a SEPARATE clearly-labeled WhatsApp option beside it. Pairs with ERP QW3/QW4/QW5. **Why:** the founder's exact ask — "call me" must be a real, distinct signal, not another WhatsApp link, and it must be clear which is which. @files: apps/web/src/pages/contact.astro, apps/web/src/lib/lead.ts
- [ ] WJ98 — **Give `/devis/mon-toit` a real desktop layout.** Widen the wizard beyond `max-w-2xl` on ≥lg (use the freed width for the map/estimate beside the form where it helps) and give `#rp9-map` a desktop-appropriate height instead of the phone `44dvh` strip. **Why:** the highest-intent page renders as a narrow mobile column in a mostly-empty desktop viewport — reads unfinished. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar)
- [ ] WJ99 — **Stop the proposal page silently degrading to French under EN/AR.** Add `data-en` to the `data-i18n` nodes in `StarRating.astro` + `CertLogoRow.astro`, and localize their FR-only `aria-label`s + the signature-canvas `aria-label` (a static attribute never retranslated). **Why:** the most commercially critical page in the funnel shows French labels the moment a client switches to English/Arabic. @files: apps/web/src/components/StarRating.astro, apps/web/src/components/CertLogoRow.astro, apps/web/src/pages/proposition/[token].astro
- [ ] WJ100 — **Close nav/footer translation gaps + kill locale-table drift.** Translate "Blog" and "Fiches techniques"; fold the ad-hoc inline `{fr,en,ar}` label tables in `Header.astro`/`Footer.astro` into the central `i18n/ui.ts` dictionary (they've already drifted into two copies of the same string). **Why:** EN/AR nav shows French labels; duplicated tables guarantee more drift. @files: apps/web/src/components/Header.astro, apps/web/src/components/Footer.astro, apps/web/src/i18n/ui.ts
- [ ] WJ101 — **Keyboard-accessible signature step.** The `#sign-pad` canvas is pointer-only. Add a keyboard-operable path (or an explicit "signature optionnelle — votre nom + les cases suffisent" affordance with `tabindex`/instructions), since the legal flow already works from name+checkboxes. **Why:** keyboard/AT users currently hit a dead control at the sign moment. @files: apps/web/src/pages/proposition/[token].astro
- [ ] WJ102 — **Make the exit-intent modal set the rest of the document `inert` while open** (match the mobile-nav pattern already used in `Header.astro`). **Why:** background content stays in the tab order for assistive tech that doesn't fully honor `aria-modal`. @files: apps/web/src/pages/devis/mon-toit.astro
- [ ] WJ103 — **Reposition the sticky CTA under RTL.** `#sticky-cta` is fixed to the physical right (`sm:right-6`); only its internal flex mirrors. Move the pill itself to the visual start edge under `dir="rtl"`. **Why:** in Arabic the pill sits on the wrong side. @files: apps/web/src/styles/global.css, apps/web/src/components/StickyCta.astro
- [ ] WJ104 — **Instrument the funnel as discrete events.** Via the existing `telemetryEvents.ts` (PII-safe/consent-respecting), emit `calculator_started`, `estimate_viewed`, `generate_lead`, `callback_requested` (DISTINCT from a WhatsApp opt-in), `proposal_viewed`, `proposal_signed` so per-step drop-off is measurable. **Why:** the funnel is one undifferentiated "submit" event today; no step analytics. @files: apps/web/src/lib/telemetryEvents.ts, apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/proposition/[token].astro
- [ ] WJ105 — **Set a concrete callback expectation + let the client pick a window.** Next to the "un conseiller peut m'appeler" choice, show a real SLA ("un conseiller vous rappelle sous ~1 h ouvrée") and let the client pick a preferred callback window (reuse the existing visit-window control), forwarded as an additive field paired with ERP QW2/QW3. **Why:** best-practice speed-to-lead sets expectations + a time window; the fields exist but aren't offered as a callback preference. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar), apps/web/src/lib/lead.ts
- [ ] WJ106 — **Remove the dead FR/AR in-page toggle on `/devis/mon-toit`** (now that `/ar/devis/mon-toit` is the canonical Arabic route) and **decide the fate of the orphaned `DiagnosticFormEnriched.astro`** (only imported by noindex `/preview/*`): promote it to replace `DiagnosticForm.astro` or delete it. **Why:** two competing ways to reach Arabic + a shipped-but-unreachable duplicate form. @files: apps/web/src/pages/devis/mon-toit.astro (+en/ar), apps/web/src/components/DiagnosticFormEnriched.astro
- [ ] WJ107 — **Homepage quick-estimate ↔ full wizard continuity.** The homepage InstantEstimator/short capture never asks raccordement, exact bill, or contact preference — so a homepage lead is silently narrower than a `/devis/mon-toit` lead (the likely source of the "tranche never arrives" impression). Make the short widget hand off to `/devis/mon-toit` carrying what it already has (prefill) and label it as a quick start. **Why:** no captured field should silently be narrower depending on which door the visitor used. @files: apps/web/src/pages/index.astro, apps/web/src/lib/lead.ts

---

### WJ1–WJ24 — QUOTE JOURNEY: BEST-IN-WORLD ELEVATION (research-driven, 2026-06-24)

**Why.** A June-2026 deep audit of TAQINOR's quote journey (website pin+bill capture → CRM lead →
seller designs the roof in 3D in the ERP → premium quote → tokenized web proposal + e-sign) against
the best solar platforms in the world (Aurora, OpenSolar, Solargraf, Pylon, Tesla, Otovo, Demand IQ,
Solo, EnergySage, Bodhi) plus Morocco market + conversion-science research. These are the **website
(`apps/web`) half**; the matching ERP tasks are **Group QJ in `docs/PLAN2.md`** (cross-referenced per
task). The goal: make the journey the best in the world for BOTH the homeowner/business CLIENT and the
COMMERCIAL user.

**Cross-cutting constraints (every WJ task).** Stay strictly inside `apps/web/**`. The live lead form
→ CRM **webhook contract stays working** (a task may evolve the capture UX but must keep posting a
valid lead + the 1 000 MAD qualify logic + consent/UTM/fbclid). Private estimator previews stay
private (noindex/not-in-nav/sitemap-excluded/unlinked). **No invented numbers** — every figure traces
to PVGIS / a confirmed constant / sound logic; **savings are self-consumption-first (loi 82-21): value
only self-consumed kWh; any surplus-injection line stays OFF until the founder confirms ANRE's BT
residential net-billing tariff (still unpublished)** → see NEEDS YOUR INPUT. **Google Solar API does
NOT cover Morocco — do NOT design around auto roof detection**; reuse TAQINOR's own engine. All new
text **FR + AR**; **WhatsApp-first**; Lighthouse 97–100, reduced-motion respected, zero CLS, <3 s on a
mid-range Android. New scaffolds needing real assets (photos, reviews, certs) ship **flagged `pending
real content from Reda`, never fabricated**.

**A — Capture (turn the website into an instant-estimate magnet):**
- [x] WJ1 — **Instant ballpark BEFORE the contact gate.** address + bill → an instant savings RANGE (kWc, ≈MAD/mois économisés, amortissement ~N ans) from the existing estimator engine, shown *before* asking for contact; make the roof PIN **optional / post-estimate** (estimate from the bill alone, refine with the pin afterwards). Keep the webhook contract + 1 000 MAD logic intact. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts
- [x] WJ2 — **Show panels on THEIR roof at capture.** Wire the private 3D estimator (`toiture-3d-pro-11`) into the public capture as an optional "voir les panneaux sur votre toit" step (lite, mobile-first), reusing the existing builder — the Aurora/Otovo effect, built on our own engine since Google Solar API is unavailable in Morocco. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/scripts/roof-tool-pro11.ts
- [x] WJ3 — **WhatsApp-first capture + email/opt-in.** Primary "Recevoir mon estimation sur WhatsApp" `wa.me` CTA with the estimate prefilled; capture email + WhatsApp opt-in (`lead.ts` already supports `whatsappOptIn`) and forward both through the webhook. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts
- [x] WJ4 — **Capture reliability.** Align client/server validation (inline `required` + `aria-invalid` matching `validateLead`, field-level errors before the round-trip) and fix the **keyless-map dead-end** (allow an address-only submit when no MapTiler key, instead of blocking forever on the pin). @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts
- [x] WJ5 — **Honest sub-1 000 MAD path.** Stop showing a false "demande enregistrée" to sub-threshold bills that never reach the CRM; show a tailored message / nurture path instead. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/api/capture-lead.ts
- [x] WJ6 — **Mobile wizard + reassurance.** Multi-step capture with a labeled progress bar ("Votre toit → Votre facture → Votre estimation"), a mode selector (résidentiel / professionnel / agricole), big tap targets, and no-pressure microcopy ("gratuit, sans engagement · réponse sous 24–48 h · on vous répond sur WhatsApp, pas d'appels commerciaux") — FR + AR. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WJ7 — **Abandon recovery.** Exit-intent / "recevez votre estimation sur WhatsApp" capturing just the number when a mobile user abandons mid-flow. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WJ8 — **Trust at the point of capture.** Real install photos + client count + named Moroccan towns + loi 82-21 conformité + warranty badges placed beside the CTA (scaffold + flag `pending real content from Reda`). @files: apps/web/src/pages/devis/mon-toit.astro

**B — Client proposal (the page that closes the sale):**
- [x] WJ9 — **Headline reframe: money over time.** Bold 25-year cumulative savings + payback above the fold, anchored on the rising-bill *cost of doing nothing*, with monthly framing ("≈ X MAD/mois") beside the total. Renders backend figures (cross-ref PLAN2 QJ13). @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ10 — **Financing comparison block.** Cash vs indicative green-loan monthly vs "X MAD/mois de mensualité < votre facture actuelle", flagged "à confirmer"; renders the data from backend (cross-ref PLAN2 QJ12). @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ11 — **Real e-signature UX.** Typed-signature canvas + "j'accepte de signer électroniquement" consent checkbox + show the timestamp/ref back to the client, posting the richer payload to the backend (cross-ref PLAN2 QJ10). Keep it embedded + mobile-frictionless, no download. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/pages/api/proposition-accept.ts
- [x] WJ12 — **In-proposal contact at every doubt point.** "Discuter sur WhatsApp" (`wa.me` prefilled with the devis ref) + "Demander un rappel" + "Poser une question" beside the price/sign sections. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ13 — **Credibility block on the proposal.** Warranties (20–25 ans), certifications (IEC 61215/61730, IRESEN/AMEE), real install photos, install count, a founder welcome note (FR/AR) — scaffold + flag `pending real content`. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ14 — **Environmental impact in human terms** (tonnes CO₂/an ≈ arbres plantés) computed honestly from the production figure, as an emotional closer. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ15 — **Honest validity window.** "Devis valable jusqu'au [date]" on the hero + sticky CTA, from the real backend expiry — never a resetting timer. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ16 — **Animated production-vs-consumption curve** (sunrise→night) with a graceful "année type" fallback (clearly labelled) when monthly data is absent, so the most persuasive visual never disappears. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ17 — **Arabic-first, RTL-native** across capture + estimate + proposal + signature (mirrored layout, AR switcher in Arabic script, 1.6–1.8× line-height, correct AR+Latin/number handling) — designed, not bolt-on translated. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/pages/devis/mon-toit.astro
- [x] WJ18 — **Mobile performance <3 s** on mid-range Android/3G: defer/lazy the 3D, compress imagery, SSR the proposal shell; keep Lighthouse 97–100, zero CLS. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/pages/devis/mon-toit.astro

**C — 3D estimator / builder engine (shared by the website lab AND the ERP design tool):**
- [x] WJ19 — **Shadow-tracing shading → honest production.** Let the user outline visible shadows on the satellite image; back-out obstruction heights from the sun azimuth/elevation at the imagery timestamp + shadow length, cast them in Three.js AND **derate the PVGIS hourly production** (Pylon's method — near-LIDAR accuracy, no paid API). @files: apps/web/src/scripts/roof-tool-pro11.ts, apps/web/src/lib/productionEngine.ts
- [x] WJ20 — **One-click auto-layout.** Auto-fill the traced roof with panels (respecting setbacks + obstacle no-go zones) so a visitor/seller stops hand-placing — pure geometry on data we already have. @files: apps/web/src/scripts/roof-tool-pro11.ts
- [x] WJ21 — **Sun-path animation + irradiance heatmap.** Animate shadows across the day/season in the existing Three.js view and color the roof by solar access (engineering proof + sales "wow"; pure astronomy, no API). @files: apps/web/src/scripts/roof-tool-pro11.ts
- [x] WJ22 — **Honest climate-loss layer.** Apply temperature derate (~8 % MA summer) + soiling/dust + diffuse/haze to production (PVGIS exposes the components) — fixes the ~15–20 % coastal-summer overstatement — and render production/savings as a **confidence band**, not a single number. @files: apps/web/src/lib/estimatorBrainV2.ts, apps/web/src/lib/productionEngine.ts
- [x] WJ23 — **Tariff fidelity + 82-21 savings honesty.** Per-utility (ONEE / Lydec / Redal) editable tranche tables; self-consumption-first savings (offset the expensive top tranches first); an OPTIONAL surplus-injection line that stays OFF until the founder confirms ANRE's BT tariff (no invented numbers). Mirror the ERP engine (PLAN2 QJ13). @files: apps/web/src/lib/estimatorBrainV2.ts, apps/web/src/lib/yieldTable.ts
- [x] WJ24 — **Deeper battery model + export fidelity.** Battery DoD + round-trip efficiency + degradation + real LFP pack sizes + 25-yr cashflow (indicative cost flagged); and `serializeLayout` keeps full per-pan geometry/azimuth so the ERP quote/PDF reflect the real multi-plane design (pairs with PLAN2 QJ21). @files: apps/web/src/lib/applianceConsumption.ts, apps/web/src/scripts/roof-tool-pro11.ts

**D — Client-facing interactive 3D on the proposal (founder request 2026-07-01):**

*Reda: when the client opens the returned quote he must see HIS OWN HOME with the solar panels in 3D — zoom, rotate — and have everything clearly explained. Today `/proposition/[token]` shows only a static PNG (`roof_image_url`); the interactive Three.js builder (`roof-tool-pro11.ts` / `roofPro11/scene3d.ts`) already lives in `apps/web` but is only used in the private estimator. Backend unlock = PLAN2 **QJ26** exposes the sanitized `roof_layout` in the public proposal payload; these WJ tasks render + explain it on the client page. Keep the lead-form webhook contract untouched; all text FR + AR; Lighthouse 97–100, zero CLS, <3 s on a mid-range Android; reduced-motion respected.*

- [x] WJ25 — **Interactive read-only 3D of the client's roof on the proposal.** Extract a rotate/zoom/pan **read-only** viewer from the existing builder (a new `roofPro11/viewerOnly.ts` reusing `scene3d.ts` geometry/materials — no editing UI, no map-draw, no optimizer), mount it on `/proposition/[token]` hydrated from the backend's `roof_layout` (PLAN2 QJ26) + the `roof_image_url` as poster/fallback. Orbit + pinch-zoom on touch, mouse-drag + wheel on desktop; lazy-loaded so it never blocks first paint. **Done =** a proposal with a stored layout shows the client's real roof + panels in an interactive 3D the client can turn and zoom, a proposal without a layout keeps the static hero, and it degrades to the PNG when WebGL is unavailable. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/scripts/roofPro11/viewerOnly.ts, apps/web/src/lib/proposition.ts (cross-ref PLAN2 QJ26)
- [x] WJ26 — **« Tout est expliqué » guided layer over the 3D.** Around the viewer, add a client-legible explanation: a legend + on-model annotations (panels per pan/zone, orientation, tilt, kWc, estimated annual production) read from the layout/proposal payload, plus a short guided walkthrough ("voici votre toit → voici vos panneaux → voici ce qu'ils produisent → voici votre économie") with plain-language captions and reduced-motion-safe hints for how to rotate/zoom. No invented numbers — every figure traces to the backend/PVGIS. FR + AR. **Done =** a first-time client understands what they're looking at without help, every figure is server-sourced, and the walkthrough is skippable + accessible. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/lib/proposition.ts
- [x] WJ27 — **Mobile, performance & fallback hardening for the viewer.** Defer/lazy the Three.js bundle (dynamic import on scroll/tap), reuse the cached materials/disposal + WebGL-context-loss recovery already in `roofPro11`, cap DPR/geometry on low-end devices, keep zero CLS (reserved poster box), honour `prefers-reduced-motion` (static poster + manual orbit only), and provide a clean no-WebGL / slow-network fallback to the PNG. Target < 3 s to interactive on a mid-range Android/3G and Lighthouse 97–100. **Done =** the proposal keeps its performance budget with the 3D added, the viewer is smooth on a mid-range phone, and every fallback path is graceful + tested. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/scripts/roofPro11/viewerOnly.ts
- [x] WJ28 — **Best-in-world proposal elevation with the 3D as centerpiece.** A world-class visual/UX pass on `/proposition/[token]` that makes the interactive roof the hero and threads the whole page into one confident, beautiful narrative (hierarchy, spacing, motion restraint, the site's v3 grade discipline — warm grade, brass only on CTAs, single zellige signature), so the client journey feels premium and effortless from open → understand → sign. Do NOT touch the lead-form/webhook contract or the e-sign payload; polish only. FR + AR; reduced-motion; zero CLS. **Done =** the proposal reads as the best solar proposal page in the world on mobile + desktop, the 3D + savings + e-sign flow as one story, and nothing regresses the existing WJ9–WJ16 content or the sign contract. @files: apps/web/src/pages/proposition/[token].astro
- [x] WJ29 — **« Être contacté » / « Demander un rappel » actually notifies the team.** Today the proposal's « Demander un rappel » / « Discuter sur WhatsApp » are client-side `wa.me` links only — no one is server-notified. Wire a real « être contacté » / « demander un rappel » action that POSTs a contact-request through an `apps/web` same-origin proxy to the new backend endpoint (PLAN2 QJ27), so the client's handler AND their superior get notified — while keeping the instant `wa.me` option alongside. Confirm to the client (« nous vous rappelons »). Keep the lead-form/webhook contract untouched; FR + AR; zero CLS. **Done =** clicking « être contacté » sends a server-side contact-request that reaches the handler + superior, shows a clear confirmation, and degrades gracefully if the endpoint is unavailable. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/pages/api/proposition-contact.ts (new proxy) (cross-ref PLAN2 QJ27)

**E — Best-in-world journey audit gaps (2026-07-01):**

*From the same 3-axis audit (content collected / delivered / UX) as PLAN2 Group QK. These are the apps/web-only gaps that survived the dedupe against WJ1–WJ29. Cross-cutting rules unchanged: stay in `apps/web/**`, keep the lead-form/webhook contract, FR + AR, no invented numbers, Lighthouse 97–100, zero CLS, <3 s mid-range Android, reduced-motion, private routes stay private, scaffolds flagged « pending real content from Reda ».*

- [x] WJ30 — **Stop dropping the captured fields in `lead.ts` (the #1 intake defect).** `validateLead` whitelists only `fullName/phone/city/roofType/billRange/consent/whatsappOptIn/fbclid/utm` and SILENTLY DISCARDS `email`, exact `factureHiver`/`factureEte`, `eteDifferente`, `raccordement`, `roofPoint`/`gpsLat`/`gpsLng`, `roofOutline`, and `mode`. Widen `ValidatedLead`/`validateLead` + the `capture-lead` proxy to pass all of them through to the webhook (which PLAN2 QK1 maps), keeping the 1 000 MAD qualify + consent/UTM contract intact. **Done =** a web lead forwards the exact bill, GPS pin, roof outline, mode, utility, email + language; the lead-form contract still holds; tests cover the pass-through. @files: apps/web/src/lib/lead.ts, apps/web/src/pages/api/capture-lead.ts (cross-ref PLAN2 QK1)
- [x] WJ31 — **Best-in-world capture questions (low-friction, all optional).** Add to `mon-toit.astro`: a distributeur selector (ONEE/Lydec/Redal + « je ne sais pas »), an optional « kWh si connu » + a meter/bill photo upload (→ PLAN2 QK6 OCR), a one-tap ombrage (aucun/partiel/important) + roof-age, battery + future-load chips (clim/VE/pompe), two qualifiers (propriétaire/locataire/décideur; projet maintenant/3 mois/renseignement) + financing intent, and forward the active FR/AR language → `langue_preferee`. All optional, forwarded via WJ30, no hit to completion. **Done =** the capture collects utility, real consumption/photo, shading, roof-age, intent + qualification signals, FR+AR, tests cover the new fields. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/lead.ts
- [x] WJ32 — **Proposal content completeness.** On `[token].astro`: render the backend financing block (PLAN2 QK3) instead of the local generic calc; show per-line marque + garantie + fiche-technique link (already in the payload); a « Et après ? » next-steps timeline (Signature → Visite 48–72 h → Installation 7–14 j → Mise en service); a « Nos hypothèses » disclosure (PLAN2 QK4); a post-install monitoring/accompagnement block; a 4–5 item objection-handling FAQ accordion; and the `variants` side-by-side « autres tailles » strip (already exposed by QJ15, unused today). FR+AR, no fabricated numbers. **Done =** the proposal delivers financing, warranties/datasheets, timeline, hypotheses, monitoring, FAQ and variant comparison, each degrading cleanly, build green. @files: apps/web/src/pages/proposition/[token].astro, apps/web/src/lib/proposition.ts
- [x] WJ33 — **Journey correctness fixes (i18n + accessibility).** Fix the FR/AR toggle that flattens nested markup (`applyLang` `el.textContent=` in `mon-toit.astro` → dual-node show/hide or sanitized innerHTML; set `dir`/`lang` on `<html>`, not just a local section), and harden the exit-intent modal (focus trap + Esc + focus restoration; build the WhatsApp `href` on input change, not only on click). **Done =** the language toggle preserves markup + applies document-level RTL, the modal is keyboard-accessible, axe/build green. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WJ34 — **Perceived-performance & delight.** Reserved-box skeletons for the map + estimate compute, a blur-up/LQIP poster for the proposal hero image, a reduced-motion-gated count-up on the hero money figures, a « génération du PDF… » affordance on the download link, and `env(safe-area-inset-bottom)` on the sticky CTA. **Done =** the slow moments show graceful loading, the hero figures animate (or land instantly under reduced-motion), the sticky CTA respects the safe area, zero CLS + Lighthouse 97–100 hold. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/proposition/[token].astro
- [x] WJ35 — **Premium trust + v3 grade on the journey pages.** Build the empty-but-premium social-proof components (star rating, testimonial card/carousel, animated install-count, cert-logo row), flagged « pending real content from Reda », and apply the site's v3 elevation grade (ZelligeSignature closing seal, `.v3-grade` on the roof photo, taller hero rhythm, `.section` spacing) to BOTH `mon-toit` and the proposal — which today sit a tier below the elevated homepage. Never fabricate reviews/photos. **Done =** the journey pages carry premium trust slots ready for Reda's content + read at the v3 tier, no fabricated content, build green. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/proposition/[token].astro, apps/web/src/components/

**F — Quote button: wire every « get a quote / get a study » CTA to the new journey (founder request 2026-07-01):**

*Reda: every « obtenir un devis » / « étude gratuite » CTA must wire DIRECTLY to the new quote-journey page — and the button should ENHANCE the (already good-looking) site, not degrade it. Audit found ALL quote/study CTAs currently point at `/contact#simulateur` (the old diagnostic form), never at the new `/devis/mon-toit` journey; they flow through a few shared components (`Header.astro`, `StickyCta.astro`, `CtaBand.astro`) + the hero in `index.astro`, so rewiring those rewires the whole site (100+ pages, FR/EN/AR). Best-practice research (Enpal/Otovo/Tesla/Sunrun/1KOMMA5° + DTC): ONE brass primary CTA repeated verbatim across header/hero/mid/footer/mobile-sticky, brass reserved exclusively for that action (others → outline/text), a reassurance strip, thumb-zone mobile sticky, AR/RTL mirroring + text-expansion. Reuse the existing `.glow` brass-on-Majorelle styling — no visual downgrade.*

- [x] WJ36 — **Rewire every quote/study CTA to `/devis/mon-toit` + one-primary-CTA discipline.** Point the shared CTA surfaces — `Header.astro` (desktop + mobile nav), `StickyCta.astro`, `CtaBand.astro` (default `href`), and the `index.astro` hero (`#simulateur`) — at the journey (`/devis/mon-toit`, locale-aware once WJ38 lands) instead of `/contact#simulateur`, so all FR/EN/AR pages funnel into the journey. Establish ONE brass primary CTA repeated verbatim (header anchor / hero loudest / one mid-page / footer / mobile sticky); demote every OTHER filled button in the same viewport to outline/text so brass = the action; keep WhatsApp as the secondary path; remove dead/duplicate CTAs. Primary label « Obtenir mon étude gratuite » / «احصل على دراستي المجانية». Keep the lead-form/webhook + the `/contact` page intact (don't delete it, just stop routing the primary CTA there). **Done =** every quote/study CTA site-wide opens `/devis/mon-toit`, exactly one brass primary action per view, no orphan CTAs, build green. @files: apps/web/src/components/Header.astro, apps/web/src/components/StickyCta.astro, apps/web/src/components/CtaBand.astro, apps/web/src/pages/index.astro, the i18n dictionaries
- [x] WJ37 — **Enhance the quote button (premium, on-brand) + reassurance + mobile sticky.** Keep the site's premium feel: reuse the `.glow` / `.glow-hero` brass-on-Majorelle button styling (no downgrade), add the reassurance strip « Gratuit · Sans engagement · Réponse sous 24–48 h · Sur WhatsApp » (AR: «مجاناً · دون أي التزام · رد خلال 24–48 ساعة · عبر واتساب») under the primary CTA, a thumb-zone mobile sticky bar with `env(safe-area-inset-bottom)`, WCAG-AA contrast on brass, and motion restraint (subtle hover only — no pulsing). AR/RTL: flip directional arrows, header CTA top-left in RTL, and let the button container FLEX (don't fix width to the FR string — AR runs ~25–35 % longer). **Done =** the enhanced CTA reads premium (not garish) on FR + AR, desktop + mobile, with the trust strip + safe-area sticky, zero CLS, Lighthouse 97–100. @files: apps/web/src/components/Header.astro, apps/web/src/components/StickyCta.astro, apps/web/src/components/CtaBand.astro, apps/web/src/styles/global.css, the i18n dictionaries
- [x] WJ38 — **Localize the journey entry (`/en/` + `/ar/` `devis/mon-toit`).** The capture page is FR-only today; add the `/en/devis/mon-toit` + `/ar/devis/mon-toit` routes (or a locale-aware capture) so localized CTAs land on a localized journey, not a French page — AR is RTL-native (WJ17/WJ33 discipline). Keep the lead webhook contract intact. **Done =** an EN or AR visitor clicking the quote CTA lands on an EN/AR journey, FR unchanged, build green. @files: apps/web/src/pages/devis/mon-toit.astro (+ en/ar routes), the i18n dictionaries (@after: WJ36)

---

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

### W236–W244 — WHOLE-SITE « THE BEST » ELEVATION: EN + AR MIRRORS (founder request 2026-06-22)

**Context.** Founder asked to elevate the WHOLE site to "the best" — KEEP the Majorelle
night-blue (`--color-nuit` #070b1d), NEVER black. **The FR site is DONE and live (2026-06-22):**
homepage + résidentiel, professionnel, pompage-solaire, batteries-stockage,
maintenance-monitoring, regularization-article-33, pourquoi-taqinor, garanties, financement,
nos-solutions, loi-82-21, recharge-voiture-electrique-solaire, marocains-du-monde, à-propos.
Also shipped: homepage portrait removed + "docteur-ingénieur" trust card → "Loi 82-21 ·
Conformité incluse" + trust-band overlap fix; new `ZelligeSignature.astro`; `.v3-grade`
golden-hour grade in `v3-photo-motion.css`. This group finishes the rollout — the **English
then Arabic mirrors**, same treatment.

**THE ELEVATION PLAYBOOK** (reference: `apps/web/src/pages/index.astro` +
`apps/web/src/pages/preview/accueil-v3.astro`, both on main — study & match):
- Elevate the existing v2 «Cinéma du chantier» system; reuse existing components/classes/tokens;
  **NO new deps; apps/web only; live pages = NOT noindex**.
- **Keep ALL content/numbers VERBATIM. Lead form (`DiagnosticForm`) byte-for-byte unchanged.**
- **Brass discipline:** gold ONLY on `.lum`/`.fig` key figures + the primary CTA; demote stray
  brass eyebrows/borders/links to `text-lune` (dark) / `text-azur-*` (light) / white.
- **Warm grade:** add class `v3-grade` (on main) to CONTENT photos only — NEVER the LCP/hero.
- Taller cinematic hero (~90–100svh) where a photo hero exists; one motion language
  (`.cine-in`/`.v2-rise`); `.section`/`.section-lg` spacing; `<ZelligeSignature/>` at most once.
- **Overlap guard:** monumental-figure bands with long values use ≤2 columns + `fig-md` +
  `min-w-0` (the homepage trust-band fix) so big figures never collide.
- **À-propos (each language) = the FOUNDER/TEAM page:** founder portrait `fondateur-portrait`
  present at a MODEST size (~240px, smaller than the old homepage version), NOT a giant hero.

- [x] W236 — Elevate EN homepage `apps/web/src/pages/en/index.astro` to mirror the FR index (portrait-free, Loi 82-21 trust card, taller hero, brass discipline, zellige signature, overlap-safe trust band).
- [x] W237 — Elevate EN solution pages: `en/résidentiel.astro`, `en/professionnel.astro`, `en/pompage-solaire.astro`, `en/batteries-stockage.astro`, `en/maintenance-monitoring.astro`, `en/regularization-article-33.astro`.
- [x] W238 — Elevate EN secondary pages: `en/pourquoi-taqinor.astro`, `en/garanties.astro`, `en/financement.astro`, `en/nos-solutions.astro`, `en/loi-82-21.astro`, `en/marocains-du-monde.astro` (+ any `en/recharge-…` if present).
- [x] W239 — Elevate EN `en/à-propos.astro` → founder/team page + modest founder portrait (~240px).
- [x] W240 — Elevate AR homepage `apps/web/src/pages/ar/index.astro`; verify the `dir="rtl"` layout holds (hero, trust band, zellige signature, spacing).
- [x] W241 — Elevate AR solution pages: `ar/résidentiel.astro`, `ar/professionnel.astro`, `ar/pompage-solaire.astro`, `ar/batteries-stockage.astro`, `ar/maintenance-monitoring.astro`, `ar/regularization-article-33.astro` — RTL-checked.
- [x] W242 — Elevate AR secondary pages: `ar/pourquoi-taqinor.astro`, `ar/garanties.astro`, `ar/financement.astro`, `ar/nos-solutions.astro`, `ar/loi-82-21.astro`, `ar/marocains-du-monde.astro` — RTL-checked.
- [x] W243 — Elevate AR `ar/à-propos.astro` → founder/team page + modest founder portrait (~240px), RTL-checked.
- [x] W244 — Brass-discipline consistency sweep on remaining content pages (FR/EN/AR `faq`, `guides/*`, `realisations/*`): apply ONLY the brass-discipline + spacing pass (no hero rebuild). Coordinate with the concurrent SEO/content session — skip any page it is mid-editing, do the rest.

---

### W222–W235 — HOMEPAGE « THE BEST » ELEVATION v3 (founder request 2026-06-22)

**Why.** After every polish round the founder still felt the homepage was "not the best" and
asked whether the blue should become black. Design session outcome (2026-06-22): **keep the
Majorelle blue** — it is Moroccan brand equity (Jardin Majorelle / YSL) and a deep slightly-blue
night reads *more* premium than flat black, which would erase the identity. The agreed direction
is **"elevated blue + Moroccan soul, applied with discipline"**: it ELEVATES the existing v2
« élégance retenue » / « Cinéma du chantier » system — it does not replace it. The levers (from
2026 best-in-class research) are **restraint, not reinvention**: more air, one consistent warm
photo grade, brass used only on figures + the primary CTA, a single zellige signature, one
editorial line, a taller cinematic hero, and the dark→light arc resolving in the lit diagnostic.

**How it ships — PREVIEW-FIRST (live site untouched).** Build the whole elevated homepage on a
**private preview route** `apps/web/src/pages/preview/accueil-v3.astro` (noindex, not in nav, out
of sitemap via the `/preview/` filter, unlinked), **reusing the existing v2 components**
(Layout, V2Enhance, Header, Footer, DiagnosticForm, Picture, Testimonials, FounderPortrait,
BrandStrip, Faq, Article33Ribbon). The live `/` (`index.astro`) and the entire lead form / lead
pipe stay **byte-for-byte unchanged** until the founder promotes it (W235 — a taste decision).
**No new dependencies. Touch only `apps/web`. Lighthouse held 97–100, reduced-motion respected,
zero layout shift. No invented figures** — reuse only already-published Taqinor data.

- [x] W222 (already present) — Scaffold `preview/accueil-v3.astro` as a faithful clone of the current homepage composition (same sections, same data, same components) so it renders identically to live `/` first — the baseline we then elevate. Inherit the `/preview/` noindex + sitemap guards. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W223 (already present) — Taller cinematic hero: raise to ~100svh desktop, photo full-bleed as the protagonist, eyebrow + counting figure + headline anchored low, ONE primary brass CTA + WhatsApp ghost, scroll chevron. Keep count-up + Ken Burns; reduced-motion safe; zero CLS. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W224 (already present) — Restraint on proof: feature **3** hero installations on the homepage (El Jadida 17,04 kWc · 21 406 kWh/an, Casablanca 11,36 kWc · 14 271 kWh/an, El Jadida 5,68 kWc · 7 135 kWh/an) + a quiet "Voir toutes les réalisations →" link; the full 8-photo gallery stays on the réalisations page. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W225 (already present) — Warm "golden-hour" photo grade: ONE consistent, subtle grade (CSS filter or warm scrim) applied uniformly to homepage photography so it reads shot-by-one-hand; must not break AA contrast of overlaid text. @files: apps/web/src/styles/v3-photo-motion.css, apps/web/src/pages/preview/accueil-v3.astro
- [x] W226 (already present) — Brass discipline: gold appears ONLY on key figures (`.lum`) and the primary CTA; demote stray brass eyebrows/borders to lune/azur tokens elsewhere on the preview. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W227 (already present) — New `ZelligeSignature.astro`: a refined single zellige motif divider + one editorial line (« Chaque chiffre de ce site est mesuré, pas promis. » / « L'étude d'abord. Le chantier ensuite. ») used ONCE between proof and solutions; brass hairline, reduced-motion safe. @files: apps/web/src/components/ZelligeSignature.astro, apps/web/src/pages/preview/accueil-v3.astro
- [x] W228 (already present) — Spacing & rhythm: apply `.section` / `.section-lg` vertical-rhythm tokens consistently so every section breathes; keep the dark→light seam into the diagnostic. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W229 (already present) — Type discipline: lock display/body to the canonical Archivo/Hanken scale + two weights; tighten hero/section headline sizes & tracking per the elevated direction; zero CLS via the existing fallback metrics. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W230 (already present) — Motion personality: one coherent discreet reveal language (`.cine-in` stagger) on section entrances, no gratuitous effects, all gated behind `prefers-reduced-motion`; verify zero CLS. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W231 (already present) — Restore + sequence the full section set (Article 33 ribbon, proof, signature, solutions, pourquoi-Taqinor/trust, parcours, témoignages, fondateur, brand strip, FAQ, diagnostic, footer) in the agreed order — long-but-spacious, not short. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W232 (already present) — Mobile + RTL pass: verify hero, proof, zellige signature and spacing hold at phone width and on the Arabic (dir=rtl) rendering; fix any overflow/crop. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W233 — A11y + perf gate: AA contrast in full sun on all new text-over-photo, focus rings intact, Lighthouse 97–100, zero layout shift; extend the apps/web vitest guards where applicable. @files: apps/web/src/pages/preview/accueil-v3.astro, apps/web/tests
- [x] W234 — Private review aid: link `/preview/accueil-v3` from the existing private preview index (or add a one-line note) so the founder can open and judge it; noindex preserved. @files: apps/web/src/pages/preview/accueil-v3.astro
- [x] W235 — Promote the v3 homepage to live. APPROVED + DONE (founder, 2026-06-24): the elevated v3 composition was already integrated directly into the live `/` (`index.astro` carries ZelligeSignature + `.v3-grade` + ~100svh hero), so the live homepage IS the v3. The now-redundant `/preview/accueil-v3` preview route + its W233 test were deleted, and the accueil-v3 entry removed from `/preview/index.astro`. Live lead form / data flow unchanged.

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

- [x] W112 — **Client "où est votre toit ?" capture (public, panels HIDDEN).** A new
  minimal public route (e.g. `/devis/mon-toit`) that reuses roofPro11's MapTiler address
  search + satellite map, lets the client **drop a pin on their roof** (drawing the
  outline is OPTIONAL, not required), and enter contact + bill, then submits the
  pin (+ optional outline) + contact to the backend (Q2), creating a Lead. Add a
  **`captureOnly` flag** to `initRoofToolPro8` that boots map + geocoder + pin/trace ONLY
  and never instantiates the optimizer/scene-panels/production UI. **Done =** the client
  can pin + submit on phone & desktop; no panel/optimizer/production UI ever appears; the
  pin reaches the backend. Files: new `apps/web/src/pages/devis/mon-toit.astro`,
  `roof-tool-pro11.ts` (captureOnly branch), reuse `roofPro11/mapDraw.ts`.

- [x] W113 — **Layout serialize + hydrate (the linchpin).** Add serialize/deserialize of
  the tool state (`AreaRecord[]`, and the lighter pin/outline) and extend
  `initRoofToolPro8` boot to **hydrate from the backend** via a token URL param
  (`?lead=<token>` for the client's pin, `?devis=<id>` for a saved layout), fetching from
  the Q1/Q2 endpoints through a small Astro API proxy. **Done =** a saved pin/outline (and
  a saved finalized layout) reload into the tool identically; round-trip vitest.
  Files: `roofPro11/prefill.ts` (load fns), `roof-tool-pro11.ts` (boot hydration),
  `apps/web/src/pages/api/roof-layout.ts` (proxy).

- [x] W114 — **Meriem design + finalize (where the panels appear, privately).** An
  internal/gated route that boots the FULL tool **hydrated with the client's pin** (W113);
  Meriem draws the outline if the client didn't, runs the existing auto-fill/optimizer,
  edits, then a **"Valider & générer le devis"** action serializes the finalized layout +
  kWc/count/production and POSTs it to the backend (Q1) and triggers Devis creation (Q3).
  **Done =** open a client pin → draw/autofill → finalize → a Devis is created and the
  layout saved. Files: `apps/web/src/pages/internal/devis-design.astro` (or reuse the
  preview route gated), `roof-tool-pro11.ts` (finalize action), api proxy.

- [x] W115 — **3D snapshot export.** Wire `renderer.domElement.toDataURL('image/png')`
  (`roofPro11/scene3d.ts`) to capture the finished roof-with-panels render and upload it
  to the backend (Q4) on finalize (W114). **Done =** finalizing produces + stores a clean
  PNG of the 3D roof; vitest/asserts the data-URL is produced. Files:
  `roofPro11/scene3d.ts` (snapshot fn), W114 finalize wiring.

- [x] W116 — **Client web proposal page (the "much better UI" link we send).** A premium,
  mobile-first **public** route (e.g. `/proposition/<token>`) that fetches the quote data
  (Q6) and renders the proposal as a beautiful web page — NOT just a PDF: a hero with the
  roof render, the facture **avant → après** + couverture %, the two options, the
  equipment, the garanties, and a **sticky "Signer" CTA**. Mirrors the v2 PDF design
  language (navy/gold, DM Serif/DM Sans). **Done =** the token link renders the full
  proposal responsively on phone + desktop; Lighthouse mobile ≥ 90. Files: new
  `apps/web/src/pages/proposition/[token].astro` + components + the Q6 fetch.

- [x] W117 — **In-page e-signature.** On the web proposal, a "Signer en ligne" flow: pick
  an option, type name + check "Bon pour accord" → POST to Q7 → success state ("Devis
  accepté ✓"), with the signed PDF offered as a download. **Done =** signing flips the
  Devis to *accepté* and shows confirmation; invalid/expired token handled. Files:
  `proposition/[token].astro` signature component, `apps/web/src/pages/api/` proxy.

- [x] W118 — **Delivery: send the proposal link (email / WhatsApp).** On finalize (W114),
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

### WA1–WA37 — TRILINGUAL SITE AUDIT (founder RULE A/B + fact-check + iPhone rendering + battery, 2026-07-04)

*A read-only audit pass (8 parallel research/fact-check/mobile agents + a live iPhone-viewport probe). Every task below corrects a REAL defect verified against the live source or a primary source. IDs are net-new (WA-namespace) to avoid collision with W###/WJ##. Where a task reverses a prior shipped task, that prior task is annotated SUPERSEDED above.*

**STEP 1 — founder RULE A (no homepage founder portrait) + RULE B (no featured install count).**

- [x] WA1 — **Remove the founder portrait/signature from the homepage in all 3 locales; keep it only on /à-propos.** `<FounderPortrait/>` renders on `index.astro` (FR L637), `en/index.astro` (L570), `ar/index.astro` (L560); the component has `FOUNDER_PHOTO='fondateur-portrait'` (portrait ACTIVE) so the real photo + name "Reda Kasri" + first-person "Je signe chaque étude — Reda Kasri" is live on every homepage today. Remove the `<FounderPortrait/>` render (and its import) from all three homepages and replace it with a SUBTLE, text-only institutional expertise cue (credentials, not a face — e.g. "études conçues par des ingénieurs — expertise R&D télécom, ex-Huawei/Ericsson/STMicroelectronics") linking to /à-propos; keep the full portrait section on /à-propos only. **Why:** founder RULE A — no founder face/first-person signature on the homepage in any locale (supersedes W266). @files: apps/web/src/pages/index.astro, apps/web/src/pages/en/index.astro, apps/web/src/pages/ar/index.astro (component: apps/web/src/components/FounderPortrait.astro; keep it for /à-propos)
- [x] WA2 — **Drop the raw install-COUNT tile from InstallCounter; keep only the kWc figure.** `components/InstallCounter.astro` renders `{count}` (`REALISATIONS.length`) as an animated `.fig.lum` stat labelled "Installations documentées" / "تركيبات موثقة" beside the (allowed) kWc figure; it is mounted on /à-propos (FR/EN/AR). Remove the install-count `install-counter__item` (and its sr-only count text), keeping the "kWc installés" item and the count-up behaviour for kWc only. **Why:** founder RULE B — the countable installations figure must never be a featured public stat; kWc stays (partially supersedes W280/W284). @files: apps/web/src/components/InstallCounter.astro
- [x] WA3 — **Replace the "{installCount} installations" factsheet stat on /à-propos with a non-count fact.** Independent of the widget, `à-propos.astro` itself prints `{installCount} installations` as a stat ("Réalisations documentées publiquement", FR ~L235 / EN ~L225 / AR ~L217). Swap it for a fact already used elsewhere (kWc installés, nombre de villes, or "installations visitables sur demande" as realisations/index.astro does). **Why:** founder RULE B — raw install count as a headline/factsheet stat. @files: apps/web/src/pages/à-propos.astro, apps/web/src/pages/en/à-propos.astro, apps/web/src/pages/ar/à-propos.astro
- [x] WA4 — **Reframe /production-mesuree away from the install count.** `production-mesuree.astro` (FR/EN/AR) derives `installCount = REALISATIONS.length` and prints it as an `<h2>` ("{installCount} installations, un seul compteur/counter/عدّاد") and in the lead. Reframe the headline + lead around measured kWh / kWc (already on the page); do not print the install count. **Why:** founder RULE B (partially supersedes W354). @files: apps/web/src/pages/production-mesuree.astro, apps/web/src/pages/en/production-mesuree.astro, apps/web/src/pages/ar/production-mesuree.astro **(CORRECTED 2026-07-04: also reframe the `<KeyFigure value={withMeasuredProduction.length} unit={"/ " + installCount}>` denominator on this page ×3 locales — it surfaces the raw count too; or explicitly exempt "non-featured denominators" in the WA6 policy so the guard has one consistent rule.)**
- [x] WA5 — **Reframe /impact-taqinor away from the install count and the "small on purpose" line.** `impact-taqinor.astro` (FR-only) prints `{installCount}` in the lead ("ce que nos {installCount} installations publiées produisent… aujourd'hui elle est petite, volontairement") and as `<h2>{installCount} installations, un seul bilan</h2>` (L90, L101). Lead with the cumulative kWc / measured kWh / CO₂ (already the page's real content); remove the raw count and the "petite, volontairement" job-count telegraphing; keep every figure honest and derived from realisations.ts. **Why:** founder RULE B (partially supersedes W279). @files: apps/web/src/pages/impact-taqinor.astro **(CORRECTED 2026-07-04: /impact-taqinor is TRILINGUAL, not FR-only — apply to all three; @files += apps/web/src/pages/en/impact-taqinor.astro, apps/web/src/pages/ar/impact-taqinor.astro, both of which print installCount in the lead + the `<h2>`.)**
- [x] WA6 — **Add a lightweight regression guard for RULE A + RULE B.** Add a unit/build test (Vitest, alongside the existing web tests) asserting (a) no homepage `index.astro` in any locale imports or renders `FounderPortrait`, and (b) no page/component surfaces `REALISATIONS.length` as user-visible copy labelled "installations/chantiers/réalisations". **Why:** both rules were violated by well-intentioned prior tasks (W266/W279/W284); a guard stops the next elevation pass from silently re-adding them. @files: apps/web/src/ (new test file, e.g. src/pages/__tests__ or existing test dir) **(CORRECTED 2026-07-04: scope the guard over ALL of src/pages (not just homepages) — installCount/REALISATIONS.length reaches user copy on à-propos ×3, impact-taqinor ×3, production-mesuree ×3 and realisations/index ×3 ("{REALISATIONS.length} chantiers"); include EN "installations/projects" + AR "تركيبات" labels; make it allowlist-based so an intentional denominator kept per the WA4 policy doesn't false-fail.)**

**STEP 2 — fact-check corrections (each verified against a primary source or a committed constant).**

- [x] WA7 — **Align the two dated blog posts' ONEE/régie tariff grid to the founder-verified REGIE_TARIFF (or caveat it historical).** `content/blog/rentabilite-solaire-par-ville-maroc.md` and `content/blog/prix-installation-solaire-maroc-2026.md` (+ their en/ar mirrors) cite the tranche grid 0,90 / 1,07 / 1,18 / 1,45 / 1,66 DH/kWh (sourced to ~2015 aggregators), but the live estimator's `estimatorBrainV2.ts` `REGIE_TARIFF` ("vérifié par le fondateur, juin 2026") is 0,9010 / 1,0732 / 1,1676 / 1,3817 / 1,5958 with different tranche boundaries. Update the blog tables to the REGIE_TARIFF values, or explicitly mark them historical/superseded and point to /methodologie-estimation + /ensoleillement-maroc as the live source. **Why:** the same tariff reads differently on the estimator vs the blog — a reader checking their bracket against the blog gets the wrong marginal rate. @files: apps/web/src/content/blog/rentabilite-solaire-par-ville-maroc.md, apps/web/src/content/blog/prix-installation-solaire-maroc-2026.md, apps/web/src/pages/en/blog/rentabilite-solaire-par-ville-maroc.astro, apps/web/src/pages/ar/blog/rentabilite-solaire-par-ville-maroc.astro, apps/web/src/pages/en/blog/prix-installation-solaire-maroc-2026.astro, apps/web/src/pages/ar/blog/prix-installation-solaire-maroc-2026.astro
- [x] WA8 — **Reconcile the Marrakech (+ Casa/Agadir) PVOUT figures between the blog and the site's own PVGIS yield table.** `rentabilite-solaire-par-ville-maroc.md` labels Marrakech "1 779 (point confirmé)" (MDPI Resources 2024, 13(10):140, PR 78%), but `/ensoleillement-maroc` (built from `yieldTable.ts`, PVGIS TMY 2005–2020, 86% PR) gives Marrakech ~1 650 kWh/kWc — an ~8% gap for the same city on the same domain (Casa 1620–1700 vs 1650; Agadir 1750–1820 vs 1686). Either reconcile the numbers, or add an explicit line noting the MDPI figure uses a different (lower) system-loss/PR assumption than Taqinor's own PVGIS extraction, so the two aren't read as contradicting. **Why:** two "PVOUT for Marrakech" numbers on the same site undermine the stated PVGIS-integrity policy. @files: apps/web/src/content/blog/rentabilite-solaire-par-ville-maroc.md, apps/web/src/pages/en/blog/rentabilite-solaire-par-ville-maroc.astro, apps/web/src/pages/ar/blog/rentabilite-solaire-par-ville-maroc.astro
- [x] WA9 — **Remove the residual residential grid-injection framing left in the blog after W300.** `prix-installation-solaire-maroc-2026.md` still states surplus "peut être injecté… à hauteur de 20 %… rachetée au tarif ANRE de 0,21/0,18 DH/kWh", and `rentabilite-solaire-par-ville-maroc.md` repeats the hedged version. The ANRE 04/26 tariff (0,18/0,21) is published for MT/HT/THT only; the BT residential tariff is UNPUBLISHED (verified: BO / ANRE decision 19-02-2026). Reword to state plainly that no residential (BT) net-billing/injection rate exists yet and assume no export revenue — matching /methodologie-estimation's stricter framing. **Why:** self-consumption-first / no-invented-number rule; residual overreach W300 didn't fully catch. @files: apps/web/src/content/blog/prix-installation-solaire-maroc-2026.md, apps/web/src/content/blog/rentabilite-solaire-par-ville-maroc.md **(CORRECTED 2026-07-04: same framing also lives in the EN/AR blog mirrors — @files += apps/web/src/pages/en/blog/{prix-installation-solaire-maroc-2026,rentabilite-solaire-par-ville-maroc}.astro + the ar/ mirrors; reword all locales. See also WB11 — the same missing-BT-caveat defect on /batteries-stockage.)**
- [x] WA10 — **Add "très haute tension (THT)" to the live-tariff scope in the "Où en est la loi ?" boxes.** All three law pages (FR/EN/AR) describe the published ANRE 04/26 buyback tariff as covering "MT/HT" only, but the same pages' regime description says the autorisation regime covers "moyenne, haute ou très haute tension", and the ANRE decision covers medium, high AND very-high voltage. Add "et très haute tension" / "and very high voltage" / "والعالي جداً" to the tariff sentence. **Why:** internal inconsistency — the tariff box under-describes its own scope vs the regime description on the same page. @files: apps/web/src/pages/loi-82-21.astro, apps/web/src/pages/en/loi-82-21.astro, apps/web/src/pages/ar/loi-82-21.astro, apps/web/src/pages/regularization-article-33.astro, apps/web/src/pages/en/regularization-article-33.astro, apps/web/src/pages/ar/regularization-article-33.astro, apps/web/src/pages/guides/loi-82-21-expliquee.astro, apps/web/src/pages/en/guides/loi-82-21-expliquee.astro, apps/web/src/pages/ar/guides/loi-82-21-expliquee.astro
- [x] WA11 — **Reconcile the panel performance-warranty figure to the EXACT datasheet linked in fiches.ts.** The site publishes "Garantie performance 25 ans · ≥ 84,8 %" site-wide (garanties/équipement ×3 locales + `fiches.ts` `canadian-solar-710`/`jinko-710`), but the Canadian Solar TOPBiHiKu7 datasheet linked in `fiches.ts` states a 30-year linear warranty to ≥ 87,4 % (1st-yr ≤1%, then ≤0,4%/yr), and the Jinko Tiger Neo 66HL5-BDV datasheet states 30 yr / 87,4 %. Verify against the exact linked PDFs and correct the years/% to match the datasheet (or confirm the specific module variant's warranty document), then propagate to all ~8 literals + fiches.ts. NOTE: this conflicts with W301, which standardized on 84,8 %/25 ans — reconcile that too. **Why:** a warranty number that doesn't match its own cited datasheet is a hard credibility risk on the exact figure a buyer checks. @files: apps/web/src/pages/garanties.astro, apps/web/src/pages/en/garanties.astro, apps/web/src/pages/ar/garanties.astro, apps/web/src/pages/équipement.astro, apps/web/src/pages/en/équipement.astro, apps/web/src/pages/ar/équipement.astro, apps/web/src/lib/fiches.ts **(CORRECTED 2026-07-04 — Fable adjudication against the ACTUAL linked PDFs: the site UNDERSTATES its own panels. Both linked N-type TOPCon modules publish produit 12 ans · performance LINÉAIRE 30 ans · ≥ 87,4 % à 30 ans (≤1 % an 1 puis ≤0,4 %/an — soit ≥ 89,4 % à 25 ans). "84,8 %/25 ans" is the OLD PERC schedule and is on NO datasheet the site links; remove it everywhere (the blog's "va au-delà du standard : ≥84,8 %" line inverts reality). Sources: Canadian Solar TOPBiHiKu7 CS7N-TB-AG datasheet v1.62C3; Jinko Tiger Neo JKM710-735N-66HL5-BDV. SCOPE is ~30 surfaces in 25+ files, not 8 — add lib/serviceFaq.ts (feeds the /faq FAQPage JSON-LD), components/GarantiesTeaser.astro, pages/{faq,financement,index,pourquoi-taqinor,professionnel,résidentiel}.astro +en/ar, pages/proposition/[token].astro, guides/entretien-et-duree-de-vie-des-panneaux ×3, ressources/10-questions, content/blog/rentabilite +en/ar, and derived copy ("10 à 25 ans", "dix-neuf à vingt-et-une années qui restent", the "25 ans" investment tiles). Keep product-vs-performance distinct and never cross-copy bifacial/monofacial variants. Implement via the new WB3 warranty.ts single source of truth so this can't recur. W301 is SUPERSEDED.)**
- [BLOCKED: founder must name the exact JA Solar DeepBlue model (3.0 PERC=25yr/84,8% vs 4.0 n-type=30yr/87,4%)] WA12 — **Give the JA Solar DeepBlue panel a real fiches.ts entry (or correct its inline warranty).** `équipement.astro` describes a JA Solar DeepBlue panel with "garantie performance 25 ans" (no %) but there is NO `fiches.ts` entry for it, so it never got datasheet scrutiny; JA Solar's DeepBlue 4.0/Pro publishes a 30-year linear warranty to ≥ 87,4 %. Add a proper `fiches.ts` entry with the real datasheet link, or correct the inline years/% to the datasheet. **Why:** an unsourced warranty on a named product; brings it under the same datasheet discipline as the other panels. @files: apps/web/src/pages/équipement.astro, apps/web/src/pages/en/équipement.astro, apps/web/src/pages/ar/équipement.astro, apps/web/src/lib/fiches.ts **(CORRECTED 2026-07-04: model-dependent — do NOT blanket-apply 30 yr/87,4 %. Confirm the installed JA model FIRST: JA DeepBlue 3.0 (PERC) = 25 yr / ≥ 84,8 % (so the page's current "25 ans" would be CORRECT), DeepBlue 4.0 (n-type) = 30 yr / ≥ 87,4 %. The Nouaceur install lists "6 × JA Solar" with no model — get the model from the founder, then add the fiches.ts entry with THAT model's datasheet.)**
- [x] WA13 — **Confirm & caveat the Dyness DL5.0C warranty term (10 yr vs regional 7 yr).** The site states the Dyness DL5.0C battery warranty flatly as "10 ans, ≥ 70 % de capacité"; some regional Dyness DL5.0C warranty documents show a 7-year 70%-retention variant depending on market. Confirm which warranty document Taqinor's Moroccan distributor actually issues and align the site (or caveat the term). All other DL5.0C specs (LFP, 6000+ cycles @90% DoD, 5,12 kWh, 51,2 V, IEC 62619/UN38.3) verified correct. **Why:** avoid overstating a warranty term that varies by market. @files: apps/web/src/lib/fiches.ts, apps/web/src/pages/garanties.astro (+ en/ar)
- [x] WA14 — **Fix the panel footprint (m²) in two guides to the datasheet/repo constant.** `combien-de-panneaux-pour-ma-maison.astro` says "chaque panneau occupe ~2,2 à 2,3 m²" and "5 à 6 m²/kWc"; `mon-toit-peut-il-supporter-des-panneaux.astro` says ~1,7 à 1,9 m² (feeding its "18–21 kg/m²"). The real TOPBiHiKu7 710W panel is 2384×1303 mm = 3,11 m², 37,8 kg — already committed as `PANEL2_LONG_M`/`PANEL2_SHORT_M` in `src/lib/roofPro2.ts` and used by the real sizing engine. Correct to ≈3,1 m²/panel, ≈4,3–4,4 m²/kWc, ≈12 kg/m² module-only (the "villa 4 kWc → 22–24 m²" example becomes ≈17–18 m²). **Why:** the guides contradict the codebase's own committed panel geometry and the datasheet; same wrong numbers duplicated in EN/AR. @files: apps/web/src/pages/guides/combien-de-panneaux-pour-ma-maison.astro, apps/web/src/pages/guides/mon-toit-peut-il-supporter-des-panneaux.astro, apps/web/src/pages/en/guides/combien-de-panneaux-pour-ma-maison.astro, apps/web/src/pages/ar/guides/combien-de-panneaux-pour-ma-maison.astro, apps/web/src/pages/ar/guides/mon-toit-peut-il-supporter-des-panneaux.astro **(CORRECTED 2026-07-04: also add apps/web/src/pages/en/guides/mon-toit-peut-il-supporter-des-panneaux.astro (EN mirror exists). Datasheet geometry confirmed: 2384×1303 mm = 3,11 m², 37,8 kg → ≈12,2 kg/m² module-only.)**
- [x] WA15 — **Reconcile the per-city optimal tilt in the orientation guide with the site's own yield table.** `orientation-inclinaison-ombrage.astro` lists graduated per-city optimal tilts (Agadir 27°, Marrakech 28°, Casa/Rabat 29°, Tanger 31°) sourced to "PVGIS / Global Solar Atlas", but `yieldTable.ts` (and `optimalSouthTiltDeg()` in `estimatorBrainV2.ts`, which searches that grid) has all five cities peaking at 30°. Either reconcile the guide to a flat ~30° (matching the committed data) or explain the assumption difference. **Why:** the guide's numbers don't reproduce from the site's own cited data source; duplicated in EN/AR. @files: apps/web/src/pages/guides/orientation-inclinaison-ombrage.astro, apps/web/src/pages/en/guides/orientation-inclinaison-ombrage.astro, apps/web/src/pages/ar/guides/orientation-inclinaison-ombrage.astro

**STEP 4 — battery honesty (founder hypothesis CONFIRMED for daily self-consumption cycling; see report).**

- [x] WA16 — **Fix the three broken guide-card links on /ar/batteries-stockage.** In `ar/batteries-stockage.astro` the "أدلة البطاريات والتخزين" section's three `<a>` cards (chemistry / sizing / outages) ALL point to `L('/guides/faut-il-des-batteries')`, while FR/EN link each card to its own guide (`/guides/batterie-lithium-ou-gel`, `/guides/quelle-taille-de-batterie`, `/guides/electricite-pendant-les-coupures`). Fix the three hrefs to mirror FR/EN (link targets only, no copy change). **Why:** Arabic readers on the chemistry/sizing cards are sent to the wrong (and identical) guide — a real navigation bug. @files: apps/web/src/pages/ar/batteries-stockage.astro
- [x] WA17 — **Add a levelized cost-per-usable-kWh section to the lithium-vs-gel guide.** In `guides/batterie-lithium-ou-gel.astro` (+ en/ar), add one short section combining the guide's already-published DoD and cycle-life figures into an explicit "coût par kWh réellement utile sur la durée de vie" framing: because gel/plomb needs ~4–5× more replacement units than LFP over one LFP lifetime AND delivers only ~50% DoD vs ~80–90% for LFP, its all-in cost per usable kWh is typically several times higher despite the lower sticker price — cited as a market range (reuse the existing indicative 3 000–4 000 DH/kWh LFP figure flagged indicative in `faut-il-des-batteries.astro`; note independent TCO studies find a multi-fold gap). No invented MAD price. **Why:** the guide has all the facts but stops short of the levelized-cost conclusion that actually answers "is gel a waste of money" — the founder's core question. @files: apps/web/src/pages/guides/batterie-lithium-ou-gel.astro, apps/web/src/pages/en/guides/batterie-lithium-ou-gel.astro, apps/web/src/pages/ar/guides/batterie-lithium-ou-gel.astro
- [x] WA18 — **Name the one genuine gel/lead-acid exception in the lithium-vs-gel guide's close.** Add one sentence to the closing paragraph naming the narrow case where gel/plomb remains defensible: very occasional backup-only use with shallow, infrequent discharge (NOT daily self-consumption cycling), where calendar life rather than cycle life binds and low upfront cost isn't punished by frequent replacement. Keep the existing self-consumption-first conclusion; no invented numbers. **Why:** the guide currently reads "gel is always inferior" — true for Taqinor's actual use case but omitting the one legitimate exception; naming it makes the recommendation more credible. @files: apps/web/src/pages/guides/batterie-lithium-ou-gel.astro, apps/web/src/pages/en/guides/batterie-lithium-ou-gel.astro, apps/web/src/pages/ar/guides/batterie-lithium-ou-gel.astro

**STEP 3 — iPhone / Safari mobile rendering (founder-reported). Root cause first, then per-defect.**

- [x] WA19 — **Add `viewport-fit=cover` to the viewport meta (makes all existing safe-area CSS actually work).** `Layout.astro` L125 sets `<meta name="viewport" content="width=device-width, initial-scale=1">` with no `viewport-fit=cover`, so every `env(safe-area-inset-*)` rule already in the code (StickyCta, devis/mon-toit, proposition) resolves to 0 on iPhone — the safe-area handling is currently inert. Add `, viewport-fit=cover`. **Why:** single highest-leverage iPhone fix; notch/home-indicator safe areas start working across the whole site. Bites 390×844 (Dynamic Island) and all notched iPhones. @files: apps/web/src/layouts/Layout.astro
- [x] WA20 — **Enlarge the mobile hamburger toggle to ≥44px.** `Header.astro` `#menu-toggle` is `border p-2` around a 20×20 SVG ≈ 36×36px; set `p-3` or `min-h-11 min-w-11`. **Why:** the only control to open mobile nav is under the 44px iOS tap target; easy mis-tap at 375×667. @files: apps/web/src/components/Header.astro
- [x] WA21 — **Enlarge TestimonialCarousel prev/next buttons to 44px.** `.testimonial-carousel__btn` is `2rem` (32px); set ≥ `2.75rem`. **Why:** below tap-target minimum wherever the carousel embeds (mon-toit/proposition), 375–390px. @files: apps/web/src/components/TestimonialCarousel.astro
- [x] WA22 — **Give the gallery lightbox close/arrow buttons safe-area insets + logical properties.** `.lightbox-close { top:1.25rem; right:1.25rem }` and `.lightbox-arrow--prev/--next { left/right:1rem }` use physical offsets with no safe-area; use `top: max(1.25rem, env(safe-area-inset-top))` and `inset-inline-end/start`. **Why:** the fullscreen fixed overlay can put the X/arrows under the sensor housing / rounded corner on iPhone 14 landscape. @files: apps/web/src/pages/realisations/index.astro, apps/web/src/pages/index.astro, apps/web/src/pages/realisations/[slug].astro
- [x] WA23 — **Mirror the lightbox prev/next arrows in RTL (/ar).** `.lightbox-arrow--prev{left}` / `--next{right}` are hardcoded physical and not in the `[dir="rtl"]` overrides, and the chevron SVGs aren't flipped — so on `/ar/realisations` and `/ar` "previous/next" point the wrong logical way. Add a `[dir="rtl"]` swap (or `inset-inline-*`) + the `scaleX(-1)` treatment other chevrons already get. **Why:** RTL navigation direction is reversed vs the rest of the mirrored page. @files: apps/web/src/pages/ar/realisations/index.astro, apps/web/src/pages/ar/index.astro
- [x] WA24 — **Enlarge homepage gallery zoom/close buttons to 44px.** `index.astro` (+ ar/index) gallery zoom-trigger + lightbox-close are `h-9 w-9`/`2.25rem` (~36px); bump to `2.75rem`. **Why:** small circular icons over photo cards are common mis-tap points on a thumb-driven 375–390px screen. @files: apps/web/src/pages/index.astro, apps/web/src/pages/ar/index.astro
- [x] WA25 — **Restore a 1-column mobile step on the AR homepage trust-stats grid.** `ar/index.astro` trust stats use `grid-cols-2 lg:grid-cols-4` (no 1-col step) while FR uses `grid-cols-1 sm:grid-cols-3`; set `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`. **Why:** two narrow columns each holding a stat + Arabic body copy crowd the gutter at 375–390px. @files: apps/web/src/pages/ar/index.astro
- [x] WA26 — **Collapse the /résidentiel 3-col figure grid on phones.** `résidentiel.astro` (+ ar) uses `grid-cols-3` with `whitespace-nowrap` figures ("3–7 ans", "< 11 kW") that never step down before `sm:`; use `grid-cols-1 sm:grid-cols-3`. **Why:** three ~106px columns of nowrap figures at 24px are tight/clip-risk on iPhone SE 375px; AR equivalents are longer. @files: apps/web/src/pages/résidentiel.astro, apps/web/src/pages/ar/résidentiel.astro
- [x] WA27 — **Collapse the /pompage-solaire capacity-band grid on phones.** `pompage-solaire.astro` (+ ar) `<dl class="… grid-cols-3 gap-3 …">` never collapses; use `grid-cols-1 sm:grid-cols-3`. **Why:** "Champ et variateur, comme nos toitures" wrapping in a ~110px column beside "4"/"0 %" is cramped at 375px. @files: apps/web/src/pages/pompage-solaire.astro, apps/web/src/pages/ar/pompage-solaire.astro
- [x] WA28 — **Use `dvh` for the roof-capture map height.** `devis/mon-toit.astro` (+ en/ar) map container is `h-[44vh]`; change to `h-[44dvh]`. **Why:** iOS Safari resizes `vh` when the URL bar collapses, visibly resizing the live map/pin canvas mid-interaction while the user places roof points (390×844, 375×667). @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/ar/devis/mon-toit.astro, apps/web/src/pages/en/devis/mon-toit.astro
- [x] WA29 — **Enlarge the exit-intent modal close button.** `devis/mon-toit.astro` exit-intent close is `min-h-6 min-w-6` (~24px); set `min-h-11 min-w-11`. **Why:** meets the bare 24px WCAG floor but misses the ~44px iOS comfort target for a modal an abandoning mobile user must dismiss fast. @files: apps/web/src/pages/devis/mon-toit.astro
- [x] WA30 — **Make the AR mon-toit project-type card labels logical (`text-start`).** `ar/devis/mon-toit.astro` `.mt-mode` labels use hardcoded `text-left` with no `[dir="rtl"]` override, so "Résidentiel/Professionnel/Agricole" copy stays left-aligned inside the RTL page. Use `text-start` (or a `[dir="rtl"]` rule). **Why:** copy reads backwards relative to the mirrored page. @files: apps/web/src/pages/ar/devis/mon-toit.astro
- [x] WA31 — **Make the AR map toolbar value logical (`ms-auto`).** `ar/devis/mon-toit.astro` map-toolbar "Repère: —" value uses physical `ml-auto`; use `ms-auto`. **Why:** in RTL it should push to the visual-start edge; `ml-auto` keeps it on the FR-side, un-mirrored. @files: apps/web/src/pages/ar/devis/mon-toit.astro
- [x] WA32 — **Use `dvh` for the proposal hero/error min-heights.** `proposition/[token].astro` uses `min-h-[72vh] sm:min-h-[78vh]` (hero, L486/L515) and `min-h-[60vh]` (expired-link screen, L410); switch all three to `dvh`. **Why:** the full-bleed roof-photo hero with overlaid heading/CTA grows/shrinks and reflows on Safari URL-bar collapse (390×844, 375×667). @files: apps/web/src/pages/proposition/[token].astro
- [x] WA33 — **Fix the proposal language-switch chips (tap size + safe-area-inset-top).** `.prop-lang-switch` chips (FR/EN/عربي) are `px-2.5 py-1` (<44px) and the fixed switcher at `top:3` has no `env(safe-area-inset-top)`. Bump to `min-h-11`/`py-2.5` and add safe-area top. **Why:** three small adjacent buttons in the fixed top corner are a mis-tap zone and can sit under the Dynamic Island at 375–390px. @files: apps/web/src/pages/proposition/[token].astro
- [x] WA34 — **Pad the proposal signature "Effacer/Clear" control.** `#sign-clear` is a bare text link (`text-xs … underline`) with no block sizing, sitting beside the signature canvas; wrap with `py-2 px-3`. **Why:** a thumb aiming for it can land on the canvas and draw a stray mark (375–390px). @files: apps/web/src/pages/proposition/[token].astro
- [x] WA35 — **Contain overscroll on the proposal "autres tailles" card strip.** The `flex gap-4 overflow-x-auto` row has no `overscroll-behavior`; add `overscroll-behavior-x: contain`. **Why:** swiping near the strip boundary on iOS can trigger the browser back/forward edge gesture or rubber-band the page (390×844, 375×667). @files: apps/web/src/pages/proposition/[token].astro
- [x] WA36 — **Use `dvh` in the embed estimation widget.** `embed/estimation.astro` L199 `.embed-body { min-height: 100vh }` → `100dvh` (or drop it — the widget is meant to size to content). **Why:** the partner-iframe widget fights its host and misbehaves with iOS `vh`. @files: apps/web/src/pages/embed/estimation.astro
- [x] WA37 — **Verify the founder-provided "fondateur-portrait" asset flow after WA1.** With WA1 removing the homepage portrait, confirm the `FOUNDER_PHOTO` asset + `process-photos.mjs` pipeline still renders correctly on /à-propos only (no dead/duplicate image reference), and that `à-propos` shows the full portrait section it was designed for. **Why:** WA1 changes where the portrait mounts; make sure the one remaining mount (/à-propos) is intact and the asset isn't orphaned. @files: apps/web/src/pages/à-propos.astro, apps/web/src/components/FounderPortrait.astro

### WB1–WB35 — DEEP AUDIT ROUND 2 (Fable frontier pass + 12-agent deep dive, 2026-07-04)

*A deeper "go deep" pass over the SAME site (a Fable adjudication/completeness critic + parallel deep lanes for SEO/i18n, a11y, estimator-math, city pages, content, legal/privacy/security). Every task below is verified against the live source or a primary source, and de-duped against WA1–37. WA1–37 are kept and corrected in place (above), not replaced. Highest-value trust/correctness items first.*

**TRUST & NUMBERS INTEGRITY (highest value — the site's core "measured, not promised" positioning).**

- [x] WB1 — **Fix the uniform-yield exposure in "production mesurée" figures.** All four non-null productions in `realisations.ts` are the SAME per-kWc factor ≈1256,2 kWh/kWc: 21 406 = 17,04×1256,2 (El Jadida), 14 271 = 11,36×1256,2 (Casablanca), 7 135 = 5,68×1256,2 (twice, two different installs). Real Deye Cloud meters on different orientations/cities cannot yield identical per-kWc production to 4 sig figs — these read as derived from one yield factor, yet every surface labels them "production mesurée / suivie sur Deye Cloud" and pourquoi-taqinor stakes the brand on "un relevé, pas une projection". WJ73's homepage note even teaches visitors to do the production÷kWc division that exposes it. Ask the founder for the TRUE per-site annual Deye Cloud readings and publish those; until distinct real readings exist, relabel the derived figures (e.g. "estimée à partir du rendement mesuré du chantier réf. …") or set `productionNum: null` per the file's own integrity rule, and reword the WJ73 note. **Why:** the #1 differentiator is falsifiable in 30 seconds with a calculator — one competitor screenshot kills the "measured, not promised" positioning. @files: apps/web/src/lib/realisations.ts, apps/web/src/pages/index.astro (+en/ar), apps/web/src/pages/résidentiel.astro, apps/web/src/pages/production-mesuree.astro (+en/ar), apps/web/src/pages/realisations/**
- [x] WB2 — **Qualify the homepage hero money line with the self-consumption condition (3 locales) + the résidentiel twin.** `heroMoneyLine` values ~100 % of the 21 406 kWh at the top marginal tariffs (≈ 29 600–34 200 "MAD effacés chaque année"); résidentiel says 6 kWc "effacent 12 000 à 16 000 MAD". With NO residential (BT) net-billing tariff published, only the SELF-CONSUMED share offsets the bill — exported surplus is worth 0 MAD. Add the honest qualifier ("pour la part autoconsommée" / "if self-consumed" / AR equivalent) or scale by a stated self-consumption assumption; keep the range mechanics. **Why:** the largest number on the money page overstates savings by the export share, contradicting the site's own self-consumption-first doctrine. Source: ANRE 04/26 covers MT/HT/THT only, BT unpublished. @files: apps/web/src/pages/index.astro, apps/web/src/pages/en/index.astro, apps/web/src/pages/ar/index.astro, apps/web/src/pages/résidentiel.astro
- [x] WB3 — **Create `src/lib/warranty.ts` as the single source of truth for every warranty figure + a Vitest guard.** Constants: panel product 12 ans, panel performance 30 ans / ≥ 87,4 % (with the ≤1 %/≤0,4 %/an schedule), inverter 10 ans (pending WB5 confirm), battery 10 ans / ≥ 70 %, structure 20 ans, pose 2 ans — imported by garanties/équipement/faq/financement (×3), GarantiesTeaser, serviceFaq, fiches.ts (incl. JSON-LD `warranty`), proposition/[token], pourquoi-taqinor, résidentiel/professionnel, ressources/10-questions. Add a test asserting no page re-hardcodes a warranty literal. **Why:** "84,8 %/25 ans" propagated to 25+ files precisely because no constant exists — same discipline STAGES.py enforces for stage names; this is the durable vehicle for the WA11 fix. @files: apps/web/src/lib/warranty.ts (new) + all WA11 call sites
- [x] WB4 — **De-hardcode the drift-prone derived stats on pourquoi-taqinor and résidentiel.** `pourquoi-taqinor.astro` (×3) hardcodes "43,48 kWc" while index/impact derive that total from REALISATIONS; `résidentiel.astro` hardcodes figcaption kWc/production ("5,68 kWc · 7 135 kWh/an" ×2) and the "10 à 25 ans" span. Derive the total via `REALISATIONS.reduce(...)`, figcaption data via a realisation lookup, the warranty span from WB3. **Why:** the next chantier added to realisations.ts silently falsifies three prominent trust pages; index already solved this (W284) — finish it. @files: apps/web/src/pages/pourquoi-taqinor.astro (+en/ar), apps/web/src/pages/résidentiel.astro (+ar)
- [BLOCKED: needs the Deye/Huawei distributor warranty certificate to confirm/cite the 10-year term] WB5 — **Confirm the flat "Garantie 10 ans" on Deye + Huawei inverters against the Moroccan distributor's warranty documents (like WA13).** `fiches.ts` + the garanties table publish Deye SUN-…-SG04LP and Huawei SUN2000 at a flat 10 years, but both makers' standard terms vary by market/channel. Attach/cite the distributor certificate; if the local term is shorter, publish the real term or the paid-extension path — never a flat 10 without a source. **Why:** inverters are the component most likely to actually claim warranty within the horizon; no number change without the founder's distributor doc. @files: apps/web/src/lib/fiches.ts, apps/web/src/pages/garanties.astro (+en/ar), apps/web/src/lib/serviceFaq.ts

**FACT / CONTENT ACCURACY.**

- [x] WB6 — **Fix the Rabat + Tanger French `roiNuance` factual inversions (they say the opposite of their own EN/AR + the data).** `cityContent.ts` FR says Rabat "a le deuxième gisement le plus mesuré de nos cinq villes" (L365) and Tanger "a le gisement le plus mesuré de nos cinq villes" (L607) — i.e. best/2nd-best. But by the site's own `CITIES.sunshineHours` (Agadir 3400 > Marrakech 3000 > Casa 2950 > Rabat 2900 > Tanger 2800) Rabat is 2nd-WEAKEST and Tanger is the WEAKEST — and the EN/AR translations correctly say "lightest"/"أخفّ". Change FR "le plus" → "le plus faible"/"le moins" so it matches its siblings and the data (Tanger's FR even self-contradicts: "le plus mesuré" then "pousse vers la partie haute de la bande 3–7 ans", which is low-resource logic). **Why:** the canonical FR locale tells a French visitor a below-average city is above-average. @files: apps/web/src/lib/cityContent.ts (lines 365, 607)
- [x] WB7 — **Reword the delegataire "barème propre" claim — it contradicts the repo's own LOCKED tariff research.** `cityContent.ts` `delegataireNote` for Casablanca/Lydec (L250-252), Rabat/Redal (L368-370) and Tanger/Amendis (L610-612) each say "votre facture porte son barème propre, pas un tarif générique." But `CONTENT_SEO_NOTES.md` §2 (LOCKED 2026-06-21) states, sourced, that Lydec/Redal/Amendis "bill the same ONEE grid" (RADEEF/RADEM publish identical tranche values), and `estimatorBrainV2.ts` equates all three to `REGIE_TARIFF`. Reword to "nous vérifions votre tranche sur votre relevé" without implying a proprietary schedule. **Why:** a live indexed page contradicts the codebase's own locked, sourced tariff note on the exact three cities it names. @files: apps/web/src/lib/cityContent.ts (lines 250-252, 368-370, 610-612)
- [x] WB8 — **Caveat the Amendis reference on the Tanger city page — the distributor is being wound down (2025–2027).** Amendis's Tanger concession is being progressively replaced by the regional SRM from June 2025 (decree 2.23.1033). The Tanger `delegataireNote` names Amendis with no freshness caveat on a page meant to stay indexed past 2027. Add a light caveat or reference the successor. **Why:** the specific distributor the page hangs its "we verify it on your bill" claim on is scheduled to stop existing within the site's lifetime. @files: apps/web/src/lib/cityContent.ts (tanger delegataireNote ~L610)
- [x] WB9 — **(Optional, founder call) Name the real régies for Marrakech + Agadir.** `cityContent.ts` leaves `delegataireNote` undefined for Marrakech/Agadir ("pas de délégataire nommé/vérifié — on n'invente pas le nom"). RADEEMA (Marrakech, radeema.ma) and the Souss-Massa SRM (Agadir, successor to RAMSA) are real, sourced public entities — the caution can be closed. **Why:** two of five city pages are conspicuously thinner on the "who bills you" fact the other three highlight, now that real names exist to cite. @files: apps/web/src/lib/cityContent.ts (marrakech, agadir entries)
- [x] WB10 — **(Low) Re-verify Agadir's `sunshineHours` (≈3 400 h/an) before featuring the superlative.** Independent published figures put Agadir nearer ~3 130 h/an; it's the one of the five cities furthest from an easy cross-check, and it feeds the "le meilleur gisement de nos cinq villes" claim in FR/EN/AR. Re-check the source or soften the superlative. **Why:** a marketing superlative rests on the least-cross-checkable input. @files: apps/web/src/lib/realisations.ts (CITIES agadir.sunshineHours), apps/web/src/lib/cityContent.ts (agadir ×3)
- [x] WB11 — **Add the "BT tariff not yet published" caveat to the /batteries-stockage stocker-vs-revendre FAQ (FR + EN).** The batteries FAQ states flatly "le tarif de rachat ANRE est de 0,18 à 0,21 DH/kWh" and "plafonne l'injection à 20 %" as settled for a residential audience, dropping the BT-not-published caveat that `/loi-82-21` and `/guides/quelle-taille-de-batterie` correctly carry. Add the same caveat or point to /loi-82-21. **Why:** a homeowner reading only this page believes their villa's rachat rate is confirmed — which the site itself says is false for BT. Same defect class as WA9, different page. @files: apps/web/src/pages/batteries-stockage.astro (~L116-117), apps/web/src/pages/en/batteries-stockage.astro (~L125)
- [x] WB12 — **Hoist the copy-pasted guide `verifiedDate` into a shared per-slug map.** All 12 guides + guides/index.astro independently hardcode `const verifiedDate = new Date('2026-07-03')` — one global literal duplicated 13×, rendered as "Vérifié le 3 juillet 2026" on every card/byline. Move it to a shared metadata map keyed by slug so each guide's review date is independently editable and the hub reads the same source. **Why:** a "verified" freshness signal that can't diverge per page isn't tracking freshness — it's a constant masquerading as one. @files: apps/web/src/pages/guides/index.astro + all 12 apps/web/src/pages/guides/*.astro
- [x] WB13 — **Gloss the jargon on first use on top-of-funnel pages.** "HMT" appears twice unglossed on the /nos-solutions pompage card (L88-89) though /pompage-solaire defines it; "onduleur hybride" is unglossed on /professionnel (L92); "kWc" first appears on /résidentiel in the hero "Extrait d'étude" card (L140) with no inline definition. Add a short first-use gloss (or link to the explaining guide) on each. **Why:** hub/marketing pages are the first touchpoint and shouldn't assume prior jargon exposure. @files: apps/web/src/pages/nos-solutions.astro, apps/web/src/pages/professionnel.astro, apps/web/src/pages/résidentiel.astro
- [x] WB14 — **Give the commercial pages a concise, quotable lead-answer for the cost/ROI question (AEO).** On /résidentiel and /professionnel the cost/ROI answer exists only inside a table or a 5-sentence hedged paragraph, and the headings aren't phrased as the question ("Combien coûte…?", "Quel retour…?"). Add a 1–2 sentence extractable answer co-located with a question-phrased heading (numbers already published; no new figures). **Why:** answer engines (and skimming buyers) can't extract a cost/ROI answer that's buried behind trust-building hedges. @files: apps/web/src/pages/résidentiel.astro, apps/web/src/pages/professionnel.astro (+en/ar)

**SEO / i18n / LINKS.**

- [x] WB15 — **Register /methodologie-estimation in the i18n translation registry (currently emits NO hreflang).** All three locale files exist and are real, linked, indexable pages, but `/methodologie-estimation` is absent from `STATIC_TRANSLATED` in `i18n/pages.ts`, so `localesForPath` returns `['fr']` → zero hreflang tags on any of the 3 URLs (self-flagged in the page comments). Add it to `STATIC_TRANSLATED`. **Why:** Google can't connect the FR/EN/AR versions of a real indexed page. @files: apps/web/src/i18n/pages.ts
- [x] WB16 — **Fix the homepage hreflang alternates (and language switcher) dropping the trailing slash → 301 hop.** `localizePath()` (`i18n/utils.ts`) and `localizeNavHref()` (`i18n/pages.ts`) special-case the root so the EN/AR homepage URLs come out as `/en` and `/ar` (no trailing slash), which the site's own `trailingSlashRedirect` worker 301-redirects to `/en/` `/ar/`. So the homepage's `hreflang="en"/"ar"` alternates point at redirecting URLs, and every homepage language-switch click takes a 301 hop. Emit the trailing-slash form for the root. **Why:** hreflang targets must be the final resolving URL; redirecting alternates are flagged by validators, and the switcher adds a needless redirect. @files: apps/web/src/i18n/utils.ts, apps/web/src/i18n/pages.ts
- [x] WB17 — **Strengthen internal links into /production-mesuree and /impact-taqinor.** Both are indexed proof pages but are absent from the header/footer nav and are only cross-linked within the small ensoleillement/methodologie/proof cluster (not true orphans, but weakly discoverable). Add contextual links from higher-traffic pages — e.g. /realisations, /pourquoi-taqinor, /maintenance-monitoring RelatedLinks. **Why:** weak internal linking → little discovery/PageRank; no visitor reaches them via a natural journey. @files: apps/web/src/pages/{realisations/index,pourquoi-taqinor,maintenance-monitoring}.astro (+en/ar)
- [x] WB18 — **Normalize the parrainage hardcoded locale hrefs to `L()` + clear a stale comment.** `en/parrainage.astro` (Breadcrump `href:'/en'` L81; RelatedLinks `/en/…` literals L201-203) and `ar/parrainage.astro` (L82, L198-200) hardcode locale-prefixed hrefs instead of using `L()`, the only pages in the en/ar trees to do so — correct today but fragile (they bypass the anti-dead-link fallback). Also `ar/realisations/[slug].astro:266-267` has a stale comment claiming `/parrainage` isn't registered (it is). **Why:** consistency + removes a latent dead-link-if-a-mirror-is-removed trap. @files: apps/web/src/pages/en/parrainage.astro, apps/web/src/pages/ar/parrainage.astro, apps/web/src/pages/ar/realisations/[slug].astro
- [x] WB19 — **Relocalize the EV-blog CTA on the EN/AR recharge pages.** `en/` and `ar/recharge-voiture-electrique-solaire.astro` hardcode-link `/blog/recharger-voiture-electrique-solaire-cout-maroc` (a real but FR-only blog post), sending EN/AR readers to French content with no mirror. Either translate that post or soften/relocalize the CTA (e.g. link to the EN/AR pillar instead). **Why:** a language dead-end mid-journey on a pillar page. @files: apps/web/src/pages/en/recharge-voiture-electrique-solaire.astro (L333), apps/web/src/pages/ar/recharge-voiture-electrique-solaire.astro (L323)

**ESTIMATOR / SOLAR-MATH.**

- [x] WB20 — **Fix the multi-zone savings over-count in the roof tool.** In the pro-11 "zones de panneaux" feature each zone computes its savings capped against the FULL bill, then `aggregateAreas` sums them (`roofAreas.ts:42-43` `total.savingsLow += r.savingsLow; total.savingsHigh += r.savingsHigh;`) and `zones.ts:87` prints the sum — so N zones can display up to N× the true maximum avoidable bill (each zone's `annualSavingsMad` is capped at the whole avoidable bill, `estimatorBrainV2.ts:730`). Split the bill across zones (per-zone share) or cap the aggregate against the whole-bill saving once. The `roofAreas.ts` header comment already falsely claims zones are capped to their own bill share. **Why:** a public interactive tool can show 2×+ the real savings on a multi-zone roof. @files: apps/web/src/lib/roofAreas.ts, apps/web/src/scripts/roofPro11/optimizer.ts, apps/web/src/scripts/roofPro11/zones.ts
- [x] WB21 — **Fix the double day-weighting in the PVGIS-fallback monthly reconstruction.** `productionEngine.ts:295` builds `monthlyKwh = annualKwh × w × DAYS_IN_MONTH[m] / (wTotal × 30.4375)` then re-normalizes to the annual total by a single global factor — so the intended per-month day-weighting is applied on top of already-monthly weights, over-weighting short months (Feb). Drop the redundant `×DAYS_IN_MONTH/30.4375` term (or the re-normalization) — only one is correct. Bounded impact (fallback path only). **Why:** the fallback monthly split isn't the documented "Σ mensuelle = annuel with plausible seasonality". @files: apps/web/src/lib/productionEngine.ts
- [x] WB22 — **(Low) Mark/retire the lab-only estimator engines to prevent future divergence.** `estimatorBrain.ts` (V1) is documented "DÉPRÉCIÉ, LABO SEULEMENT" and `roof.ts` (generic-550 W layout) is only used by preview labs, not the public path (which is V2). Add a one-line "lab-only, not the public engine" banner to each (or retire them) so a future edit doesn't accidentally wire a stale engine into a client page. **Why:** two live estimator lineages invite a "two engines disagree" bug later. @files: apps/web/src/lib/estimatorBrain.ts, apps/web/src/lib/roof.ts

**ACCESSIBILITY (WCAG 2.2).**

- [x] WB23 — **Localize/remove the hardcoded French `aria-label` in WhatsAppMock.** The "online" status `aria-label="en ligne"` (L97) and the "read" receipt `aria-label="lu"` (L154) never localize, so EN/AR screen readers announce French, and even in FR the aria-label replaces (Label-in-Name) the visible translated text. Drop the redundant one and pull the other from the existing `STR` table (or use `sr-only` text). **Why:** WCAG 2.5.3 Label-in-Name + wrong-language announcement on the translated component. @files: apps/web/src/components/WhatsAppMock.astro (L97, L154)
- [x] WB24 — **Add a captions track to the self-hosted videos (WCAG 1.2.2).** `LiteVideo.astro` injects a plain `<video controls autoplay>` with no `<track kind="captions">` and no prop to supply one; real jobsite footage (chantier) and the planned "compteur" testimonial carry speech/ambient audio. Add an optional `captionsSrc`/`captionsLang` prop, render `<track kind="captions" … default>` when supplied, and source real VTT files before the videos carry meaningful speech. **Why:** prerecorded audio-video needs captions. @files: apps/web/src/components/LiteVideo.astro, apps/web/src/components/VideoChantier.astro, apps/web/src/components/VideoCompteur.astro

**LEGAL / PRIVACY / CONSENT / SECURITY (all ADDITIVE — the lead webhook contract stays intact; no change to validateLead / the 1000 MAD threshold / the consent-UTM-fbclid fields).**

- [x] WB25 — **Add a CNDP declaration line to the privacy policy (3 locales).** `politique-de-confidentialite.astro` references loi 09-08 but never names a CNDP declaration/authorization number. Add the declaration number (or an honest "déclaration en cours"). **Why:** core Morocco data-protection compliance gap. @files: apps/web/src/pages/politique-de-confidentialite.astro (+en/ar)
- [x] WB26 — **Disclose the funnel-beacon / step-level telemetry in the privacy policy (3 locales).** `funnelBeacon.ts` collects anonymous per-tab step-reached/abandoned events, never mentioned in the policy. Add a short paragraph alongside the fbclid/UTM section. **Why:** behavioral collection undisclosed (omission, not a false "no tracking" claim). @files: apps/web/src/pages/politique-de-confidentialite.astro (+en/ar)
- [x] WB27 — **Disclose the CRM + Meta CAPI sub-processors / international transfer in the privacy policy (3 locales).** The policy discloses only Cloudflare hosting, but `lib/lead.ts` forwards qualified leads to a CRM webhook (German-hosted backend) and to Meta's Conversions API (hashed fields). Name these data flows. **Why:** sub-processor / international-transfer disclosure gap. @files: apps/web/src/pages/politique-de-confidentialite.astro (+en/ar)
- [x] WB28 — **Give the privacy policy a concrete retention period (3 locales).** The retention line ("le temps de son traitement commercial, puis aussi longtemps qu'une relation client existe", L39) has no measurable window. State a concrete duration or deletion trigger. **Why:** common CNDP-audit gap. @files: apps/web/src/pages/politique-de-confidentialite.astro (+en/ar)
- [x] WB29 — **Gate the pre-consent fbclid/UTM capture.** `Layout.astro:191-206` runs on every page for every visitor and persists `fbclid`/`utm_*` to sessionStorage before any consent exists. Defer the read to submit-time, or gate behind a lightweight tracking-consent signal — additive, does not touch the fbclid/UTM lead fields. **Why:** tracking identifiers captured pre-consent sitewide. @files: apps/web/src/layouts/Layout.astro
- [x] WB30 — **Gate the pre-consent funnel beacon.** `devis/mon-toit.astro` (~L1575/1823/2367) fires `'reached'`/`'abandoned'` beacons from step 0, while the consent checkbox only appears at step 3 — no consent state is read. Gate beacon calls behind reaching the consent step (or a sitewide analytics-consent signal) — additive. **Why:** behavioral beacons fire before consent. @files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/lib/funnelBeacon.ts
- [x] WB31 — **Add a minimal analytics/tracking consent banner.** No consent banner exists sitewide, yet fbclid/UTM + funnel-beacon capture already happen pre-consent (WB29/WB30). Add a lightweight banner (covers today's sessionStorage/beacon capture and future pixel/CAPI additions). **Why:** durable fix for the pre-consent capture + future-proofing. @files: apps/web/src/layouts/Layout.astro (new component)
- [x] WB32 — **Add the honeypot check to /api/preview-lead.** `capture-lead.ts` calls `isHoneypotTripped(body)`; the mirror endpoint `preview-lead.ts` doesn't. Add the same check — additive, no threshold/shape change. **Why:** inconsistent spam guard between mirror endpoints. @files: apps/web/src/pages/api/preview-lead.ts, apps/web/src/lib/lead.ts
- [x] WB33 — **Tighten `fullName` server validation to require a letter.** `validateLead` accepts `length ≥ 2`, so a direct POST with `fullName: "😀😀"` passes the server though the client (`mon-toit.astro`) enforces a `\p{L}` check. Add the same at-least-one-letter check server-side — additive tightening, not a shape change. **Why:** emoji-only names bypass the server via direct API call. @files: apps/web/src/lib/lead.ts
- [x] WB34 — **Add `X-Frame-Options: DENY` alongside `frame-ancestors`.** `applySecurityHeaders` (`worker/headers.mjs`) sets CSP `frame-ancestors 'none'` but no `X-Frame-Options` — add DENY for older UAs/scanners that don't honor CSP framing. **Why:** defense-in-depth clickjacking header missing. @files: apps/web/worker/headers.mjs
- [x] WB35 — **Explicitly disable camera/microphone/payment in Permissions-Policy.** `worker/headers.mjs` sets only `geolocation=(self)`; the site uses none of camera/mic/payment. Extend to `camera=(), microphone=(), payment=()`. **Why:** low-cost hardening, no functional impact. @files: apps/web/worker/headers.mjs

**WC — iPhone/mobile + i18n fix follow-ups (added 2026-07-04). The fixes themselves are ALREADY CODED on branch `claude/competent-solomon-1449e2` (header overflow, Arabic "TAQINOR" logo flip, hero flash + honest Deye numbers, RTL WhatsApp-glyph mirror, Ken-Burns-mobile-off perf); these are the REMAINING verify/measure items only:**
- [ ] WC1 — **Verify the 2026-07-04 mobile/RTL fixes on real iPhone viewports (375×667 + 390×844) in FR, EN AND Arabic (RTL).** Confirm on the phone viewport, with screenshots: (a) the hamburger is always reachable with ZERO horizontal overflow at 375px and the top-bar « Obtenir mon étude gratuite » CTA is hidden on mobile; (b) the compact globe language dropdown opens and switches locale; (c) the Arabic « TAQINOR » wordmark reads correctly (never « ROTAQIN »); (d) the hero shows the static « 6,56 MWh » figure with NO flash/disappear and no count-up; (e) the WhatsApp glyph on the Arabic `/devis/mon-toit` submit button is NOT mirrored. Then a regression sweep at 375/390px of homepage, header/menu, `/devis/mon-toit`, a guide, a service page, and the `/ar` mirror for overflow/RTL/clipping/FOUC/sub-44px tap targets. **Why:** the fixes were coded but the live-render verification was deferred (dev server races concurrent edits; several pages do build-time network fetches). @files: apps/web/src/components/Header.astro, apps/web/src/components/Logo.astro, apps/web/src/components/LanguageSwitcher.astro, apps/web/src/pages/index.astro (+ en/ar)
- [ ] WC2 — **Measure homepage load before/after the perf changes and record LCP / total bytes / JS+CSS weight / request count.** Use the W323 CI Lighthouse gate (or a local lighthouse run) to confirm the count-up removal + Ken-Burns-off-below-1024px reduced weight and that the LCP element (the static hero « 6,56 MWh » headline) paints immediately. **Why:** the founder asked for measured before/after numbers; measuring was deferred with the direct runs. @files: apps/web/scripts, apps/web CI config
- [ ] WC3 — **RTL lightbox arrows (minor).** The realisations lightbox prev/next arrows use physical `left:`/`right:` with no `[dir="rtl"]` rule, so on `/ar` they don't mirror (prev sits on the left). Add `[dir="rtl"]` flips for `.lightbox-arrow--prev/--next` and `.slug-lightbox-arrow--prev/--next`. **Why:** small RTL correctness nit surfaced in the 2026-07-04 QA sweep. @files: apps/web/src/pages/en/realisations/index.astro, apps/web/src/pages/ar/realisations/[slug].astro (+ fr [slug] if the same classes exist)

---

## NEEDS YOUR INPUT — ungated; each waits on something only you can give (with my recommendation)

**Auto-gating is OFF (2026-06-21).** A web run no longer skips a task for being a new dep, an
architecture change, or a taste call — it builds and NOTES it. What remains here genuinely needs
**you**: a real-world data drop, a Cloudflare dashboard secret, or a taste/business call.

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
- **W187 — 6 manufacturer logo SVGs** (Canadian Solar, JA Solar, Jinko, Deye, Dyness, Nexans). Blocked
  by network egress (only npm is reachable; the open web returns 403), not by a decision. **MY
  RECOMMENDATION: drop a zip of the 6 official monochrome SVGs** (from each brand's media kit — correct
  colours + license-clean, better than random web logos). Wiring them into `public/brands/` +
  `brands.ts` is then trivial (S). The text word-mark fallback is fine meanwhile — low urgency.

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
  join the realisations roster; (3) the 2 Huawei FusionSolar installation figures (not yet pulled);
  (4) confirmation that the El Jadida 17,04 kWc (réf. 468) install is real/posé — it is NOT on Deye —
  else it should come out of the « 43,48 kWc installés » total. **Supersedes WG7's outdated « a year of
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

### 2026-07-04 — Deep-audit round-2 drain (WA1–WA37, WB1–WB35): 70 shipped, 2 blocked, one merge
- Founder RULE A/B enforced: removed the founder portrait from all 3 homepages (WA1) and the raw install-count from InstallCounter/à-propos/production-mesuree/impact (WA2–WA5); added a Vitest regression guard (WA6) so a future pass can't silently re-add either.
- Panel warranty reconciled to the ACTUAL linked N-type TOPCon datasheets (30 ans / ≥ 87,4 %, product 12 ans) across 38 surfaces / 25 files, behind a new single source of truth src/lib/warranty.ts + a regression test (WA11, WB3). Old "84,8 % / 25 ans" PERC figure removed everywhere.
- Content correctness: blog tariff grid → REGIE_TARIFF, PVOUT methodology note, injection/BT-unpublished framing (WA7–WA9, WB11); law pages THT scope (WA10); panel m²/tilt/battery guides reconciled to repo constants (WA14–WA18); cityContent régie/tariff/superlative fixes (WB6–WB10); jargon glosses + AEO lead-answers (WB13–WB14).
- Production-figure integrity: the 4 uniform-yield "measured" figures are now labelled "estimée à partir du rendement mesuré" sitewide (WB1) — awaiting the founder's TRUE per-site Deye Cloud readings to de-flag; hero/résidentiel money lines qualified "pour la part autoconsommée" (WB2); drift-prone kWc/warranty/figcaption stats de-hardcoded (WB4); verifiedDate hoisted to guideMeta.ts (WB12).
- i18n/SEO/links: methodologie-estimation hreflang (WB15), root trailing-slash alternates (WB16), production-mesuree/impact internal links (WB17), parrainage/recharge dead-link fixes (WB18–WB19).
- Estimator math bugs: multi-zone savings over-count capped (WB20), PVGIS-fallback double day-weighting removed (WB21), lab-only engines banner (WB22).
- Mobile/iPhone/RTL: viewport-fit=cover (WA19), ≥44px tap targets (WA20/WA21/WA24), dvh heights (WA28/WA32/WA36), safe-area lightbox + RTL mirroring (WA22/WA23), logical props + grid collapses (WA25–WA27, WA30/WA31), proposal chips/overscroll (WA33–WA35).
- A11y + privacy/security: WhatsAppMock aria localization (WB23), video captions plumbing (WB24), privacy policy CNDP/telemetry/sub-processors/retention (WB25–WB28), pre-consent fbclid/beacon gating + a lightweight trilingual consent banner (WB29–WB31), honeypot on preview-lead + fullName letter check (WB32–WB33), X-Frame-Options + Permissions-Policy hardening (WB34–WB35).
- BLOCKED on founder input (left [ ]): WA12 (exact JA Solar DeepBlue model) and WB5 (Deye/Huawei distributor warranty certificate). Founder follow-ups: supply the real per-site Deye Cloud annual readings (WB1) and the JA/inverter warranty documents; the /realisations case-study long-form narratives still describe the 4 estimated installs as Deye-Cloud-measured and want either the true readings or a narrative pass.
- Verified locally in the prod-parity build: astro build green (all pages + sitemap), full vitest suite green except two pre-existing Windows-only flakes (a CRLF `
`-indexOf on untouched scene3d.ts, and a fixed-seed fuzz test exceeding its 90s limit on this box) — both green on CI Linux.


- 2026-07-02 — WJ2, WJ17–WJ38 (23 tasks, one run, one merge): drained the whole quote-journey
  build queue across parallel worktree lanes with per-task model selection (opus for the
  3D-engine physics lane, sonnet for the feature/UI lanes). Capture (`devis/mon-toit`): optional
  lite « voir les panneaux sur votre toit » 3D step (WJ2), all the previously-dropped lead fields
  now forwarded to the webhook — exact bill, GPS pin, roof outline, mode, utility, email, language
  (WJ30), best-in-world optional questions in a collapsed panel — distributeur, kWh, shading,
  roof-age, battery + future-load chips, owner/decider + timeline qualifiers (WJ31), and a fixed
  FR/AR dual-node toggle + document-level RTL + keyboard-accessible exit-intent modal (WJ33).
  Proposal (`proposition/[token]`): interactive read-only 3D of the client's own roof + « Tout est
  expliqué » guided layer (WJ25/26), perf/fallback hardening (WJ27), premium v3-grade elevation
  with the 3D as centerpiece (WJ28), a real « être contacté » server-notify proxy that degrades to
  WhatsApp until the backend endpoint ships (WJ29), and content completeness — backend financing,
  per-line marque/garantie, next-steps timeline, hypotheses, monitoring, objection FAQ, variant
  strip (WJ32). 3D engine (private `toiture-3d-pro-11` + libs, all additive + opt-in so pro-3/4/5
  stay byte-identical): shadow-tracing derate (WJ19), one-click auto-layout (WJ20), sun-path +
  solar-access heatmap (WJ21), honest climate-loss confidence band (WJ22), per-utility tariff
  tables + self-consumption-first savings with the ANRE surplus-injection line parked OFF (WJ23),
  deeper LFP battery model + widened `serializeLayout` per-pan geometry (WJ24). Journey polish:
  perceived-performance/delight skeletons + count-up + PDF affordance (WJ34), premium trust
  scaffolds flagged « pending real content from Reda » + v3 grade on both pages (WJ35), <3 s mobile
  perf/lazy-3D (WJ18), Arabic-first RTL-native across both pages (WJ17). CTAs: every quote/study CTA
  site-wide rewired to `/devis/mon-toit` with one-brass-primary discipline (WJ36), reassurance strip
  + safe-area mobile sticky + RTL button flex (WJ37), and localized `/en/` + `/ar/` journey routes
  with locale-aware CTA targeting (WJ38). +162 vitest tests. No new dependency. The live lead-form
  webhook contract stayed byte-for-byte unchanged throughout. NEEDS-YOUR-INPUT carried forward: the
  ANRE BT surplus-injection tariff (injection line ships disabled), and the backend `roof_layout`
  (QJ26) + contact-request (QJ27) endpoints (the 3D viewer + rappel notify degrade gracefully until
  those land).
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
- 2026-06-22 — W112: public client capture `/devis/mon-toit` — `captureOnly` boot of roof-tool-pro11 (map+geocoder+pin ONLY, never instantiates optimizer/scene-panels/production); new `/api/capture-lead` mirrors `preview-lead` and attaches `roofPoint`/`roofOutline`/`billKwh`, reuses the EXISTING lead webhook (no new secret). Live lead flow + `DiagnosticFormEnriched` untouched.
- 2026-06-22 — W113: pure `serializeLayout`/`deserializeLayout` + `hydrateFromLead` in `roofPro11/prefill.ts`; full boot optionally hydrates a lead's pin (round-trip unit-tested).
- 2026-06-22 — W114: internal Meriem atelier `/internal/devis-design` (noindex) — minimal ERP login (`POST /api/django/token/`, access token in sessionStorage; **NOTE: first authenticated surface in apps/web**) → hydrates the client pin → full builder → « Valider & générer le devis » POSTs the NEW backend `POST /api/django/ventes/devis/from-layout/`, then saves the layout. **NOTE: depends on the backend endpoint shipped this batch → ERP must be deployed via `scripts/deploy-prod.ps1`.**
- 2026-06-22 — W115: `scene3d.snapshot()` → renderer-canvas `toDataURL` PNG; design page uploads it multipart to `POST .../devis/<id>/roof-image/` on finalize.
- 2026-06-22 — W116: premium client web proposal `/proposition/<token>` (server-fetch of the public Q6 endpoint, noindex), roof hero + facture avant→après + couverture + options + explicit HT→remise→TVA→TTC chain + sticky « Signer » CTA, v2 design tokens (Majorelle blue, brass only on figures+CTA).
- 2026-06-22 — W117: in-page e-signature via same-origin `/api/proposition-accept` proxy → `POST Q7 accept/` (status flip THROUGH the existing accept service — rule #4 preserved); idempotent double-submit handled; invalid/expired token → friendly state.
- 2026-06-22 — W118: finalize surfaces the tokenized proposal URL + `wa.me` deep link + `mailto:` + copy-to-clipboard (degrades to a plain link without phone/email); SendGrid backend send left out of apps/web scope.
- 2026-06-22 — BACKEND (**NOTE: not apps/web — needs `scripts/deploy-prod.ps1` to go live**): new `POST /api/django/ventes/devis/from-layout/` (wraps the existing `build_devis_from_layout` → Devis `brouillon` + mints a `ShareLink` proposal token), `POST .../devis/<id>/share-link/`, and the Lead serializer now exposes read-only `roof_point`/`roof_outline`/`bill_kwh`. Company forced server-side; no status changes (rule #4).
- 2026-06-22 — W236: EN homepage `en/index.astro` rebuilt to mirror the elevated FR home — removed the homepage FounderPortrait, replaced the "Doctor-engineer" trust card with "Law 82-21 · Compliance included", ~100svh cinematic hero (count-up + scroll chevron + hero-scrim-v3), ZelligeSignature once, brass discipline, overlap-safe trust band (fig-md/min-w-0/≤2 cols), v3-grade on content photos only. All figures verbatim; DiagnosticForm byte-for-byte unchanged. No new deps.
- 2026-06-22 — W237: 6 EN solution pages (résidentiel, professionnel, pompage-solaire, batteries-stockage, maintenance-monitoring, regularization-article-33) elevated to match their FR counterparts — cinematic hero where the FR page has one, brass eyebrows demoted to text-lune, v3-grade content photos, .section/seam-soft rhythm. Text + numbers verbatim.
- 2026-06-22 — W238: 6 EN secondary pages (pourquoi-taqinor, garanties, financement, nos-solutions, loi-82-21, marocains-du-monde) elevated — brass discipline, Breadcrumb added on loi-82-21 + cinematic hero on marocains-du-monde to match FR. No `en/recharge-…` exists (FR-only). Text + numbers verbatim.
- 2026-06-22 — W239: EN `en/à-propos.astro` made the founder/team page with a modest ~240px fondateur-portrait (not a giant hero), eyebrow demoted; text verbatim.
- 2026-06-22 — W240: AR homepage `ar/index.astro` rebuilt to mirror the FR home with RTL verified — founder portrait removed, Law 82-21 trust card uses existing Arabic site vocabulary (القانون 82-21 / مطابقة مُدرَجة — no invented claim), overlap-safe trust band, hero count-up + chevron, ZelligeSignature once. Arabic text + numbers verbatim; DiagnosticForm unchanged.
- 2026-06-22 — W241: 6 AR solution pages elevated to match the FR counterparts, RTL-logical classes preserved/converted (border-s/ps/ms, rtl:-scale-x-100); cinematic heros where FR has them; Arabic text + numbers verbatim.
- 2026-06-22 — W242: 6 AR secondary pages elevated — brass discipline, Breadcrumb added on loi-82-21, cinematic hero on marocains-du-monde, RTL verified. Arabic text + numbers verbatim.
- 2026-06-22 — W243: AR `ar/à-propos.astro` made the founder/team page with a modest ~240px fondateur-portrait, RTL verified; Arabic text verbatim.
- 2026-06-22 — W244: brass-discipline + spacing consistency sweep across FR/EN/AR `faq`, `guides/*`, `realisations/*` — stray brass eyebrows demoted to text-lune and brass link-borders to azur/white; no hero rebuilt, no section reordered, no text/number changed, AR RTL classes preserved. NOTE: no new dependency, no auth change; live lead form + data flow untouched. Built on `wp/webplan-enar-elevation`; `astro build` green; vitest 2970 pass (6 estimator-runtime timeouts are the known Windows jsdom flakes — pass at 30s timeout, unrelated to these page edits).

- 2026-06-24 — WJ1: instant ballpark BEFORE the contact gate on `/devis/mon-toit` — new pure lib `billEstimate.ts` turns a bill (MAD/mois) alone into kWc + ≈MAD/mois économisés + amortissement, reusing the committed `estimatorBrain` (self-consumption-first, loi 82-21, NO surplus/net-billing line); roof pin now optional/post-estimate; non-chiffrable bill → French "estimation indisponible", never a fabricated value. Webhook contract + 1 000 MAD logic intact.
- 2026-06-24 — WJ3: WhatsApp-first capture — primary "Recevoir mon estimation sur WhatsApp" `wa.me` CTA with the estimate prefilled; email + WhatsApp opt-in captured and forwarded (email added ADDITIVELY to the capture-lead record; `whatsappOptIn` already flowed through `validateLead`).
- 2026-06-24 — WJ4: capture reliability — inline `required` + `aria-invalid` validation aligned to `validateLead`, field-level errors + focus before the round-trip; keyless-map dead-end fixed (address-only submit allowed when no MapTiler key).
- 2026-06-24 — WJ5: honest sub-1 000 MAD path — UI now branches on the server-returned `qualified`; sub-threshold gets a tailored nurture message + WhatsApp instead of a false "demande enregistrée".
- 2026-06-24 — WJ6: mobile wizard — multi-step capture (Votre toit → Votre facture → Votre estimation) with labeled progress bar, résidentiel/professionnel/agricole mode selector, big tap targets, no-pressure microcopy — FR + AR (data-i18n toggle, RTL on AR).
- 2026-06-24 — WJ7: abandon recovery — exit-intent (mouse-leave desktop / tab-hidden mobile) modal capturing just the number into a prefilled `wa.me` link.
- 2026-06-24 — WJ8: trust at point of capture — loi 82-21 conformité + 25-yr warranty + IEC 61215/61730 + service towns beside the CTA; real install photos + client count SCAFFOLDED and flagged `pending real content from Reda` (never fabricated).
- 2026-06-24 — WJ9: proposal headline reframe — bold 25-yr cumulative savings + payback above the fold, anchored on the rising-bill cost of doing nothing, "≈ X MAD/mois" framing; prefers backend `eco_a_cumul`, else computed from annual×horizon (documented), null → no fabricated figure.
- 2026-06-24 — WJ10: financing comparison block — cash (backend TTC) vs indicative green-loan monthly range flagged "à confirmer", "< votre facture actuelle" when backend bills present.
- 2026-06-24 — WJ11: real e-signature UX — hand-rolled native `<canvas>` typed-signature pad (touch+mouse, NO library) + "j'accepte de signer électroniquement" consent + timestamp/ref shown back; posts a BACKWARD-COMPATIBLE enriched payload to `proposition-accept` (3 optional ignorable fields, signature data-URL size-capped). Devis still flips to accepté via the unchanged backend contract.
- 2026-06-24 — WJ12: in-proposal contact — "Discuter sur WhatsApp" (`wa.me` prefilled with the devis ref) + "Demander un rappel" (tel:) + "Poser une question" beside the price/sign sections.
- 2026-06-24 — WJ13: credibility block — warranties 20–25 ans + IEC 61215/61730 + IRESEN/AMEE + loi 82-21 + founder welcome note (FR + AR); install photos/count/towns scaffolded + flagged `pending real content`.
- 2026-06-24 — WJ14: environmental impact in human terms — tonnes CO₂/an ≈ arbres plantés computed from the backend production figure (0,81 kg CO₂/kWh ONEE grid, 22 kg/arbre/an, factors shown); hidden when production absent.
- 2026-06-24 — WJ15: honest validity window — "Devis valable jusqu'au [date]" on hero + sticky CTA sourced ONLY from the real backend `date_validite`; expired-state message; no resetting countdown.
- 2026-06-24 — WJ16: animated production-vs-consumption curve (sunrise→night) in pure SVG keyed to real production, with a clearly-labelled "année type" fallback when monthly data is absent; draw/sun animation gated behind prefers-reduced-motion; zero CLS.
- 2026-06-24 — W233: a11y/perf test guard added (`tests/accueilV3W233.test.ts`, 14 cases) — accueil-v3 noindex, single h1, `.v3-grade` NOT on the hero/LCP, reduced-motion gating, and the new preview index noindex + links accueil-v3.
- 2026-06-24 — W234: private review aid — new `/preview/index.astro` (noindex, NOT in nav, sitemap-excluded) listing all `/preview/*` routes with `/preview/accueil-v3` featured, so the founder can open and judge them.
- 2026-06-24 — W222–W232: verified ALREADY-PRESENT against the live `preview/accueil-v3.astro` (438 lines, gold ref) — taller cinematic hero, 3-install restraint, warm v3-grade, brass discipline, ZelligeSignature, spacing/type/motion discipline, full section sequence, mobile/RTL — all built in a prior wave; marked `[x] (already present)`, no rebuild.
- 2026-06-24 — W235 (PROMOTION APPROVED): the v3 homepage elevation was already live on `/` (index.astro), so the founder approved it as the official homepage. Deleted the redundant `/preview/accueil-v3.astro` + its W233 test (`tests/accueilV3W233.test.ts`) and removed its entry from `/preview/index.astro`. Live homepage, lead form and data flow unchanged; the v3-grade CSS + ZelligeSignature component stay (used by the live home).

- 2026-07-03 — WEB DRAIN WAVE 1 (28 tasks, 8 parallel worktree lanes, one integration branch): FIX-FIRST honesty + defects landed. WJ39 rebuilt the broken English `/en/devis/mon-toit` (was ~90% French with "undefined" mode buttons) into real English; WJ41 localized all map/geocoder status messages + AR placeholders; WJ46 fixed exit-intent misfiring on the meter-photo picker + moved the WhatsApp offer to the estimate-render moment; WJ47 split the capture boot into its own lazy chunk (no more Three.js in the public capture bundle). WJ42/43/44/82/77 rebuilt the proposal page: tri-node FR/EN/AR toggle (full English proposal added), locale-correct signature stamp, expired/dead-offer states can no longer be signed, persuasion arc reordered proof-before-ask. WJ40 fixed 4 EN/AR segment pages dropping visitors onto the French journey; W302 swept "25 ans"/comma-decimal French leaks out of EN/AR figures (incl. a real GarantiesTeaser locale bug); W272 differentiated double-CTA closes. W300 corrected the BT-tariff overreach across 3 guides+3 blog posts+regularization (the one honesty-rule breach), W301 reconciled the 25-yr degradation figures, W305 small content fixes. W314 made the closed mobile menu truly inert; W264 gave the header menus hierarchy + honest offer/blog split; W251 wired a no-op-safe header proof fragment (lights up when GOOGLE_RATING lands). W334 added a 24h battery energy-flow diagram; W278 added the Nour/prepaid + coupures resilience block; W279 shipped a new /impact-taqinor page with every figure derived from realisations.ts. W315 shipped Worker security headers (CSP/HSTS/Referrer-Policy/Permissions-Policy/nosniff), W319/W379 hardened robots.txt + added llms.txt + AI-crawler policy, W321 added immutable static-asset caching. W381 (UTM governance doc), WJ93 (cookieless-experiment policy + edgeVariant helper), W351 (asset-repurposing pipeline doc). Combined validation: astro build clean (all pages), tsc clean, rtlToggleWJ17 test updated to the tri-node contract; not yet merged (accumulating toward the single end-of-run merge).

- 2026-07-03 — WEB DRAIN WAVE 2 (36 tasks, 8 parallel worktree lanes on one integration branch). Capture funnel resilience: fetch timeouts + honest failure copy + pending labels (WJ60), wizard state survives refresh/back via sessionStorage + pushState (WJ61), visible map-failure states (WJ62), no-French-at-failure in any locale (WJ63), input sanity + smallest-screen + noscript exit (WJ65), exact-bill micro-transparency (WJ67) — and fixed a latent wave-1 bug where /en journey validation threw a silent ReferenceError (VALIDATION_ERROR_EN was frontmatter-scoped but read from a client script). Proposal round 2: post-signature moment + signature echo (WJ78), AR success-state finish (WJ79), zero-total guard (WJ83), printable @media print (WJ84), distinct doubt-point CTA intents (WJ85), scaffold-hiding until real content (WJ86). Homepage elevation: 4-step « comment ça marche » band (W252), a light tonal break (W265), the founder moment via FounderPortrait (W266, supersedes the 2026-06-22 « épuré » decision), an honest money-framed hero range derived from the RÉGIE tariff (W267), monumental proof band (W268), gallery lightbox + city filter (W271). Footer: journey link + warm close (W246), art-directed frame (W369), data-gated social row (W286), RC/ICE already present (W287). Guides: dated « où en est la loi » 82-21 explainer (W259), HowTo schema (W290), de-dup of 3 overlapping guides (W304), 2 new high-anxiety guides — roof load + insurance (W306), guide dates/authors/reading-time (W303). Services catalogue: free-study product (W256), honest service-area (W262), named maintenance tiers gated on WG10 (W255), monitoring-by-outcomes phone mockups (W257), farmer-first pompage (W261). City pages: honest per-city ROI nuance + delegataire disclosure (W328/W296). Products: Offer/availability schema + comparison table (W326), « traçabilité » quality section framed from the 2025 OMPC panel affair (W277). Combined validation: astro build clean (149 pages); the wave's source-assertion tests reconciled (estimatorBrain decoupled from the public homepage via a new public-safe regieTariff.ts; captureBoot .once test mock; FounderPortrait test flipped per W266). Not merged yet — 64/193 done, accumulating toward the single end-of-run merge.

- 2026-07-03 — WEB DRAIN WAVE 3 (37 tasks, 8 parallel worktree lanes on one integration branch). Capture funnel round 3: estimate anticipation + tappable image cards + honest caveats (WJ48), staged optional-refinement groups (WJ49), contact-preference toggle (WJ51), post-submit reference code (WJ52), screen-reader-complete form (WJ88), RTL chevrons + dir=ltr numerics (WJ89). Proposal round 3: cash/échelonné toggle (WJ53), WhatsApp share + tablet QA (WJ56), trust-at-signature (WJ57), localized/annotated charts (WJ80), never-blank-proposal timeouts (WJ81), sign-on-behalf field (WJ87). Realisations: standard captions from real fields (W283), VideoChantier mount (W281), indexable measured/visitable pillar + ItemList schema (W289), EN/AR ports of the elevated hub + phased galleries (W308/W309), no-op client-quote + nearest-case link (W327). B2B/financing: professionnel facility sub-cards (W260), CFO-grade CAPEX/OPEX framing (W335), verified named financing mechanisms — CAM Saquii, FDA 30%, Maghrebail, CGI 123-22° — with the unverifiable residential bank claim dropped (W258/W336), garanties worked example + exclusions + claim process (W331), free-audit B2B entry + WG8-gated trust scaffold (W337). SEO/content-reach: Article/BlogPosting image schema (W291), evergreen prix pillar (W293), AEO Q&A blocks (W297), closed the guides EN/AR gap — 12 new mirrors (W294), EN/AR money-blog routes (W295). New transparency pages: /production-mesuree (W354), /ensoleillement-maroc publishing the yield table (W355), facts.ts aggregator (W380). Referral & doors: /parrainage with gated reward (W338), « déjà client ? » SAV door separate from sales webhook (W339), presse & partenaires block (W345). MRE + differentiation: procuration/timezone/pay-from-abroad blockers (W332), per-pillar contrast lines (W333). Combined validation: astro build clean (185 pages); full test green apart from the mechanical elevation page-count bump (26 pages) and the pre-existing Windows-CRLF local flake. 101/193 done, accumulating toward the single end-of-run merge. Pending: /og/parrainage.png asset (manual); hreflang registration for impact-taqinor/production-mesuree/ensoleillement-maroc/parrainage (later lane).

- 2026-07-03 — WEB DRAIN WAVE 4 (33 tasks, 8 lanes; a mid-wave server rate-limit storm was recovered by cherry-picking each lane's completed web commits, keeping concurrent OS-plan PR#307 commits out of the web branch). Journey: preconnect + deferred maplibre (W320/W324), visit-slot picker (W353), estimate takeaway PNG (W356), honest cost-of-waiting (W360), privacy-light funnel beacon → optional FUNNEL_WEBHOOK_URL (WJ59, avoids CRM phantom-lead flooding). Proposal: revision-request form (WJ54), view/scroll telemetry gated on real phone (WJ55), keyboard-navigable 3D viewer (WJ90), endpoint rate-limiting (W316), post-signature referral composer (W343), and WJ75 — which caught a REAL ~25× understatement bug in the 25-year savings headline (annual eco_a_cumul shown as cumulative) and fixed it. Homepage: WhatsAppMock conversation animation (W270), « notre moteur conçu au Maroc » story (W276), counters derived from REALISATIONS (W284), gallery/RegimeSelector→journey routing (W247), blog-journey links (W248), en/ar faut-il-des-batteries restored (W310), blog themes + filter chips (W329). Trust: no-op-safe components wired on à-propos/garanties/contact/realisations (W280), visit-a-chantier contact link (W285), video-testimonial scaffold (W282), FAQ clusters + anchors (W330). Layout/infra: LocalBusiness kept (no genuine solar subtype) + sameAs data-gated + breadcrumb dict wired (W298/W288/W312), installable offline-tolerant PWA with brand-derived maskable icon + caching-only SW (W357). Award-tier CSS craft: motion tokens (W362), grain overlay (W363), text-wrap pretty (W367). New surfaces: /production-mesuree, /ensoleillement-maroc, /embed/estimation partner widget (W358, noindex+out-of-sitemap), OG-image compression (W325). Combined validation: astro build clean (186 pages); reconciled the wave's assertions — decoupled BLOG_THEMES into src/lib/blogThemes.ts so /blog stops dragging node:fs (real build fix), reworded the estimator-file comment, updated the RegimeSelector + embed-page test contracts. 134/193 done, one branch, no merge yet. NEW optional secret for Reda (measurement, no-op until set): FUNNEL_WEBHOOK_URL. Pending manual: /og/parrainage.png; /embed/* CSP frame-ancestors loosening (worker follow-up); hreflang registration for the new standalone pages.

- 2026-07-03 — WEB DRAIN WAVE 5 (25 tasks, 5 lanes). Estimator numbers-integrity: one engine — billEstimate repointed to estimatorBrainV2 with proven byte-identical output, battery-cost constants reconciled to one source (WJ69); honest distributeur caveat instead of fake personalization (WJ70); climate confidence band surfaced on the estimate (WJ71); diaspora foreign-phone acceptance (WJ64), CAPI hashed-email + event_id (WJ92), idempotency + delivery-failure alerting (WJ66), professionnel journey mode (WJ68), telemetryEvents.ts closed vocabulary + PII-safety test (WJ91). Award-tier craft: native scroll-driven animation-timeline + scrubbed counters (W361), hero light-sweep (W365), magnetic CTA (W368), hero depth layer (W373), Archivo width-axis interaction (W378), self-drawing zellige (W366). RTL + nav: logical-property fixes across Callout/RegimeSelector/WhatsAppMock/Header (W311), mega-panel Solutions menu with a real install preview card (W370), chapter-numbering extended to the landing pages (W274). Content/trust: chantier-retrospective blog post from the real El Jadida case (W307), privacy policy full field-set disclosure + GDPR section + e-sign consent (W318), LiteVideo primitive extracted (W346), production-guarantee scaffold gated on WG12 (W352), realisations referral CTA (W344), milestone review-request helper gated on WG5 (W341). Infra: 4 new pages hreflang-registered, env-gated Cloudflare analytics beacon (WJ94), locale-parity drift-guard script (W313 — which found real FR-richer-than-EN/AR drift on ~8 pages, noted for a later parity pass). Combined validation: astro build clean (187 pages); full test green apart from two known local-only flakes (the estimatorHardeningW48 fuzz test needs ~97s and hits its 90s cap only under full-suite CPU load — passes in isolation and on CI; the estimatorPreviewPro11 CRLF check). 159/193 done, one branch, no merge yet. FOLLOW-UPS noted: repoint funnelBeacon/proposition telemetry to telemetryEvents.ts (WJ91 consumers); the W346 « no third-party iframe outside the blog » STANDING RULE; the W313 EN/AR parity gaps.
- 2026-07-03 — WJ74: stamped + pinned the yield table — `generate-yield-table.mjs` now pins `PVGIS_TMY_STARTYEAR`/`PVGIS_TMY_ENDYEAR` (2005–2020) explicitly into every PVGIS `PVcalc` request (was left to the server's implicit sliding default) and stamps the generated file with `GENERATED_AT` (ISO timestamp of the run) plus the pinned window as exported constants, so staleness/reproducibility are now visible in-file. Applied the same header stamp to the currently-committed `yieldTable.ts` (2026-07-03 marker) without re-fetching PVGIS data — no numbers changed. Yearly refresh: re-run `node scripts/generate-yield-table.mjs` once a year and note the new `GENERATED_AT` here.
- 2026-07-03 — W322: deploy diet — deleted the dead `apps/web/public/brand/` folder (4.3 MB, base64-PNG-in-SVG, zero code references confirmed by repo-wide grep before deletion) and retired the legacy `/preview/toiture-3d-pro-{2..10}` lab: 9 `.astro` pages + their 9 dedicated `src/scripts/roof-tool-pro{2..10}.ts` scripts deleted (pro-11 is the founder-confirmed canonical builder; the `lib/roofPro2.ts`, `lib/estimatorBrainV2..V7.ts` etc. modules underneath stay — they're live dependencies of pro-11/billEstimate/proposition, not the deleted pages/scripts). Cleaned up dangling references: `/preview/index.astro` list trimmed to the surviving routes, dead cross-links to pro-2..10 removed from pro-11's footer nav. Deleted 8 test files fully dedicated to the removed pages (estimatorPreview.test.ts [pro-3], estimatorPreviewPro{5,6,7,8,9,10}.test.ts, estimator3dFixes.test.ts [pro-3]); surgically pruned `roof-preview.test.ts` (removed the pro-2-only describe block + trimmed the MapLibre/Three.js KNOWN-file allowlists) and `estimatorPreviewPro11.test.ts` (replaced the now-false "pro-3..pro-10 baselines preserved" assertion with a library-level V7/V8 isolation invariant, since that's the real thing worth guarding); repointed `roofTypeSelectPro9.test.ts`'s page-wiring block from the deleted pro-9 page to pro-11 (same eager-wiring pattern, still live) instead of losing that regression coverage. Verified via repo-wide grep that nothing else imports any deleted file. tsc (tsconfig.check.json) clean; isolated re-run of every touched/adjacent test file green (187/188, the 1 fail is a pre-existing CRLF-formatting flake in estimatorPreviewPro11.test.ts confirmed present before this change via git-stash A/B). NOTE: a full combined `vitest run tests/` surfaced ~58 unrelated failures (estimatorRuntimePro10Pro11/captureBootW112/site-content-and-look) from a `Denied ID .../node_modules/maplibre-gl/dist/maplibre-gl.css?url` Vite path-security error — reproduced identically on the pre-change commit via git-stash A/B, so it's a pre-existing environment issue from the cross-worktree node_modules junction (Vite's fs allow-list rejecting a resolved path outside this worktree's root), not a regression from this task.
- 2026-07-03 — W350: shipped `/liens` — a minimal link-in-bio hub (logo + 4 buttons: réalisations, estimation gratuite, WhatsApp, blog + a phone fallback), indexable, mobile-first, zero new dependency (reuses Logo.astro, lib/nap.ts, lib/whatsapp.ts — no Linktree-style third party). The 5th button (WhatsApp Channel) is OMITTED per the task's own "once created" gate — the channel doesn't exist yet, so no link was fabricated; add it here the day it's created. Also added per-install WhatsApp prefills on case studies (`realisations/[slug].astro`): a new `caseStudyWhatsappText()` helper in `lib/whatsapp.ts` builds a message citing the exact ville/kWc/ref of the installation the visitor is reading, wired as a distinct secondary WhatsApp button below the CtaBand (StickyCta's generic WhatsApp button is untouched). New test coverage in `tests/whatsapp.test.ts` for the new helper (10/10 green). tsc (tsconfig.check.json) clean; targeted vitest run (whatsapp/redirect/i18n-realisations) green.
- 2026-07-03 — W323: shipped the CI Lighthouse gate under apps/web/scripts/ — `lighthouse.config.mjs` (the 97-100 floor, the 4 categories, the 5 routes: /, /devis/mon-toit, /proposition/[token] seeded, /en/, /ar/, plus the LCP-selector expectation on the two journey pages: `#mt-stage` on /devis/mon-toit's map-init-gated capture area, `.chart-svg` on the proposal's chart-JS-gated savings/production chart) and `lighthouse-gate.mjs` (the runner — audits every route, asserts the floor, and asserts the ACTUAL LCP element Lighthouse reports matches the expected selector, not just that the score cleared the floor). Zero new dependency: reuses the already-installed `lighthouse` + `chrome-launcher` (no `@lhci/cli`, which would be a new external dependency to stop-and-ask on). The seeded `/proposition/[token]` route reads a REAL backend record by token; without a real seeded token (env `LIGHTHOUSE_PROPOSITION_TOKEN`) the gate SKIPS that one route with a clear message rather than auditing a 404 or fabricating data. Verified end-to-end against a local static-file smoke fixture (not the full site — no full astro build per the task): confirmed real score parsing, the LCP-element match AND mismatch paths, and the seeded-route skip path all produce correct PASS/FAIL/SKIP output and exit codes; also caught and fixed a real bug during that verification (Chrome's Windows tmp-profile cleanup can throw a transient EPERM that was crashing the process before it could print results — now caught non-fatally). CI WIRING IS OUT OF SCOPE per this task's own framing (`.github/**` edits) — the founder/OS-run must add a step to the `web-build-test` job that builds+serves apps/web then runs `node apps/web/scripts/lighthouse-gate.mjs --base-url=<served-url>` (see the WIRING NOTE atop lighthouse.config.mjs); until that step is added this gate runs standalone/locally only and does not yet block CI.

- 2026-07-03 — WEB DRAIN WAVE 6a (17 tasks, 6 file-disjoint lanes). Journey now a first-class indexed landing page: /devis/mon-toit removed from noindex + sitemap-excluded set, real SEO/hreflang (W245); honest « Réponse WhatsApp sous 1 h, 7j/7 » badge near every capture/sign CTA (WJ58); offline/slow-network banners on both journey pages (WJ45); same-origin + honeypot hardening on the public POST surface, keeping roof-* endpoints decoupled from lead/CRM (W317); unified kWc/number formatting across estimate + proposal + AR bidi isolation (WJ72); « l'installation la plus proche de chez vous » via bounded haversine over real installs (W342); a /methodologie-estimation transparency page (W359). EV-charging page translated (EN/AR) + surfaced in nav (W254); « après votre installation » + Espace-client (Deye Cloud) door (W340); shared service-FAQ bank + real-year warranty tables on the 4 service pages (W263); reading-progress bar on blog/guides (W376) + a [data-choreo] entrance primitive (W377); one pinned scrollytelling beat on the homepage journey band (W371). Deploy diet: deleted the 4.3 MB dead brand folder + retired the legacy pro-2…pro-10 preview lab (pages+scripts+8 dead tests, keeping pro-11 + the shared libs), stamped/pinned the PVGIS yield table (WJ74), shipped a /liens link-in-bio hub + per-install WhatsApp (W350), and a Lighthouse-gate config/runner reusing existing deps (W323 — .github wiring is a founder follow-up). Combined validation: astro build clean (184 pages); full test green apart from the mechanical elevation page-count bump (28) and the pre-existing CRLF flake. 176/193 done. Remaining: 17 deep cross-file bridges (6b) then the single merge.

- 2026-07-03 — WEB DRAIN WAVE 6b-1 + 6b-2 (14 cross-file bridges). One funnel: retired the parallel DiagnosticForm captures from index/résidentiel/professionnel + turned /contact into a pure « parler à un humain » page (W249, DiagnosticForm+/api/simulate kept as documented fallback); the homepage now captures via the inline InstantEstimator widget, twice (W250), sourced from the same engine. Journey↔site tie-in: /nos-solutions elevated into the true services hub with derived counts (W253), the zero-form « envoyez une photo sur WhatsApp » door incl. a Darija line (W349), an honest estimate-vs-proof yield line (WJ73), per-page/context wa.me prefills + voice-note invite (WJ50), lead-magnet pages/worksheets (W348). Proposal: neutral OG title/image so a shared tokenized link leaks no client PII (WJ76), a VideoCompteur scaffold near the savings figures (W347). Award-tier craft: crafted clip-path link hovers (W374), a below-the-fold hero cue (W275), a composed dark↔light tonal rhythm (W372), one monumental type moment (W375), and native cross-document view-transition morphs gallery→case-study (W364, deliberately not SPA-routing). Combined validation: astro build clean (186 pages); reconciled two intentional-change tests (homepage-craft's DiagnosticForm-aside assertion → InstantEstimator per W249; the i18n anti-dead-link guard now respects FR+AR-only pages per W348's PARTIAL_TRANSLATED). 190/193 done. Remaining: 3 whole-site bridges (W292 OG images, W299 internal-linking, W273 copy-distinctiveness) then the single merge.

- 2026-07-03 — WEB DRAIN WAVE 6b-3 (final 3 whole-site bridges) — BUILD QUEUE FULLY DRAINED. Category OG images: 9 new dedicated OG PNGs (service pages + generic guides/blog) from real catalogued install photos, ogSlug wired on every page that used to fall back to the homepage image; existing OG PNGs left byte-identical (W292). Topic-cluster internal-linking: hub↔spoke↔guide↔blog closed across the prix/résidentiel, pompage/agricole, 82-21/régularisation and batteries/coupures clusters via RelatedLinks, every href verified against a real route in all 3 locales — no dead links (W299). Copy-distinctiveness: the real duplication was in meta descriptions + a handful of byte-identical CtaBand closing lines, replaced with page-specific factual lines (measured Deye Cloud proof, product names, named towns) — no two pages open on the same promise, no invented facts (W273). FINAL VALIDATION of the whole run: astro build clean (186 pages), full vitest 3691/3692 (the 1 fail is the pre-existing Windows-CRLF-only estimatorPreviewPro11 massing check — green on CI Linux), tsc clean. 193/193 tasks done across one integration branch → single sync-safe self-merge to main (auto-deploys via Cloudflare).
