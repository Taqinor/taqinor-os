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

### WA1–WA37 — TRILINGUAL SITE AUDIT (founder RULE A/B + fact-check + iPhone rendering + battery, 2026-07-04)

*A read-only audit pass (8 parallel research/fact-check/mobile agents + a live iPhone-viewport probe). Every task below corrects a REAL defect verified against the live source or a primary source. IDs are net-new (WA-namespace) to avoid collision with W###/WJ##. Where a task reverses a prior shipped task, that prior task is annotated SUPERSEDED above.*

**STEP 2 — fact-check corrections (each verified against a primary source or a committed constant).**

- [BLOCKED: founder must name the exact JA Solar DeepBlue model (3.0 PERC=25yr/84,8% vs 4.0 n-type=30yr/87,4%)] WA12 — **Give the JA Solar DeepBlue panel a real fiches.ts entry (or correct its inline warranty).** `équipement.astro` describes a JA Solar DeepBlue panel with "garantie performance 25 ans" (no %) but there is NO `fiches.ts` entry for it, so it never got datasheet scrutiny; JA Solar's DeepBlue 4.0/Pro publishes a 30-year linear warranty to ≥ 87,4 %. Add a proper `fiches.ts` entry with the real datasheet link, or correct the inline years/% to the datasheet. **Why:** an unsourced warranty on a named product; brings it under the same datasheet discipline as the other panels. @files: apps/web/src/pages/équipement.astro, apps/web/src/pages/en/équipement.astro, apps/web/src/pages/ar/équipement.astro, apps/web/src/lib/fiches.ts **(CORRECTED 2026-07-04: model-dependent — do NOT blanket-apply 30 yr/87,4 %. Confirm the installed JA model FIRST: JA DeepBlue 3.0 (PERC) = 25 yr / ≥ 84,8 % (so the page's current "25 ans" would be CORRECT), DeepBlue 4.0 (n-type) = 30 yr / ≥ 87,4 %. The Nouaceur install lists "6 × JA Solar" with no model — get the model from the founder, then add the fiches.ts entry with THAT model's datasheet.)**

### WB1–WB35 — DEEP AUDIT ROUND 2 (Fable frontier pass + 12-agent deep dive, 2026-07-04)

*A deeper "go deep" pass over the SAME site (a Fable adjudication/completeness critic + parallel deep lanes for SEO/i18n, a11y, estimator-math, city pages, content, legal/privacy/security). Every task below is verified against the live source or a primary source, and de-duped against WA1–37. WA1–37 are kept and corrected in place (above), not replaced. Highest-value trust/correctness items first.*

**TRUST & NUMBERS INTEGRITY (highest value — the site's core "measured, not promised" positioning).**

- [BLOCKED: needs the Deye/Huawei distributor warranty certificate to confirm/cite the 10-year term] WB5 — **Confirm the flat "Garantie 10 ans" on Deye + Huawei inverters against the Moroccan distributor's warranty documents (like WA13).** `fiches.ts` + the garanties table publish Deye SUN-…-SG04LP and Huawei SUN2000 at a flat 10 years, but both makers' standard terms vary by market/channel. Attach/cite the distributor certificate; if the local term is shorter, publish the real term or the paid-extension path — never a flat 10 without a source. **Why:** inverters are the component most likely to actually claim warranty within the horizon; no number change without the founder's distributor doc. @files: apps/web/src/lib/fiches.ts, apps/web/src/pages/garanties.astro (+en/ar), apps/web/src/lib/serviceFaq.ts

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

- [ ] QJW16 — **[GATED: à ne construire qu'AVANT une promotion de `DiagnosticFormEnriched` en production] Les champs enrichis atteignent réellement le lead** : `DiagnosticFormEnriched.astro:393-401` collecte et transmet `supplyType`, `roofArea`, `orientation`, `estimatedKwc` (`pages/api/preview-lead.ts:80-81` les conserve dans `record.enrichment`), mais `backend/django_core/apps/crm/webhooks.py` ne contient AUCUNE référence à `enrichment` / `estimatedKwc` / `roofAreaM2` / `supplyType` (grep : 0 occurrence) : les valeurs survivent dans le payload brut (`WebsiteLeadPayload`) sans être mappées sur aucun champ de `crm.Lead`, et un commercial ouvrant la fiche ne voit pas ce que le prospect a répondu. Le code l'admet lui-même (`DiagnosticFormEnriched.astro:10` : « affichage CRM = tâche taqinor-os séparée »). Impact LIMITÉ aujourd'hui — ce composant n'est utilisé que par `preview/diagnostic.astro`, page privée `noindex` hors nav — d'où le gating : le câblage backend doit précéder la promotion, jamais la suivre. **Note :** la moitié backend (mapping dans `_extract_web_questionnaire`) sort du périmètre `apps/web` et devra faire l'objet d'une tâche PLAN2 jumelle portant `@after` sur elle (PACT11). **Done =** décision de promotion prise, ou tâche jumelle backend créée et les quatre champs visibles sur la fiche lead. Files: `apps/web/src/components/DiagnosticFormEnriched.astro`. (DECISION) (@lane: qjw/diagnostic) (@model: sonnet)

### Heure légale — le Maroc est à GMT depuis le 20/09/2026 (décret 2.26.530, BO 7521)

- [ ] WJ117 — **`dayProfiles.ts` dit encore « UTC+1 sauf Ramadan » et décale l'horloge d'une heure.** Aujourd'hui : `apps/web/src/lib/dayProfiles.ts` (lignes ~267-280, 481, 495 — relevé de l'agent heure-légale du 21/09/2026) répète que « le Maroc vit à UTC+1 toute l'année SAUF pendant le Ramadan » et porte le même décalage d'HORLOGE que `backend/django_core/apps/ventes/ramadan.py` portait avant sa correction (PR #700) : depuis le décret n° 2.26.530 relatif à l'heure légale (BO n° 7521 du 29/06/2026, en vigueur la nuit du 19 au 20/09/2026, GMT définitif, plus aucune bascule ni Ramadan), la courbe journalière publique est décalée d'une heure et sa note est fausse — surface CLIENT-FACING. Mieux : dériver le décalage du fuseau `Africa/Casablanca` à la date (Intl/Temporal, 0 depuis le 20/09/2026, +1 avant), supprimer la branche « Ramadan = UTC+0 » (les HABITUDES du mois, si modélisées, restent), corriger la note affichée ; miroir exact de `decalage_maroc_h`/`note_horaire()` côté ERP. **Done =** test qui affirme un décalage de 0 h le 21/09/2026 et de +1 h le 19/09/2026 ; aucun « UTC+1 » ni « Ramadan … UTC+0 » dans le texte servi ; `npm run build` vert. Files: apps/web/src/lib/dayProfiles.ts, apps/web/src/lib/dayProfiles.test.ts. (@lane: web) (@model:sonnet)

---

### Groupe AGW — Devis agricole côté site (pompage solaire) — audit L3 du 02/10/2026

> **Ce que c'est.** La moitié `apps/web` du **Groupe AGR** de `docs/PLAN.md` (devis agricole, audit L3 du 02/10/2026) : sa provenance, ses décisions fondateur D-AGR-1..13, son ordre de construction M0..M4 et ses règles complètes sont dans l'en-tête de ce groupe. **Ce groupe ne touche RIEN hors de `apps/web/**`** — seule exception écrite : l'annotation de WG11 dans ce fichier par AGW306.
>
> **Décisions utiles ici (TRANCHÉ 02/10/2026, ne jamais re-demander).** D-AGR-6 : on imprime la RÈGLE de l'aide FDA (conditions, plafonds 30 % / 3 000 DH par ha / 3 000 DH par kWc / 30 000 DH par projet, accord AVANT travaux, versement après réalisation, un seul projet par exploitation, Guide FDA 2024 p.20-23), jamais un montant propre au client ni un délai ; « jusqu'à 30 % » disparaît partout ; le texte est recopié du repli daté de `quote_engine/agricole/mentions.py` (AGR306). D-AGR-5 : l'argent montré au client vient du bloc `economie_pompage` déclaré, servi par le serveur dans `synthese_agricole`, jamais d'une bande carburant calculée par le site. D-AGR-1 : la page /proposition ne calcule rien, elle rend `synthese_agricole`. D-AGR-11 : l'arabe et la darija sont écrits maintenant et relus après (AGRM23), sans bloquer. D-AGR-13 : seuls les nouveaux devis comptent ; aucune compatibilité n'est gardée pour les anciens devis agricoles.
>
> **Run POOLÉ obligatoire** : `python scripts/plan_lanes.py docs/PLAN.md docs/WEB_PLAN.md`. Les `@after` AGW → AGR (AGW300 → AGR300, AGW301/AGW302 → AGR301, AGW303/AGW304 → AGR308, AGW306/AGW307 → AGR306, AGW407 → AGR402, AGW408 → AGR411, AGW409 → AGR110) sont ignorés EN SILENCE si `WEB_PLAN.md` est planifié seul. Avant de démarrer une tâche qui attend une moitié backend, vérifier sur `origin/main` que son contrat partagé (`apps/web/src/contract_samples/proposal_data.json`, `hypotheses_pompage.json`) y est.
>
> **Chaînes mono-écrivain** (`plan_lanes.py` ne lit pas les `.astro` : elles sont écrites en `@after`) : `pompage-solaire.astro` ×3 AGW305 → AGW400 → AGW402 → AGW307 ; `devis/mon-toit.astro` ×3 AGW401 → AGW403 → AGW404 → AGW405 ; `proposition/[...token].astro` AGW300 → AGW301 → AGW303 → AGW304 → AGW308. `npm run build` dans `apps/web` après chaque `.astro` touché.
>
> **NE PAS FAIRE (web).** Aucun « jusqu'à 30 % », « up to 30 », « حتى 30 » ni « ≈ 30 % » ; aucun montant ni délai FDA propre au client ; jamais « cumulable » tant que la DPA ne l'a pas écrit (AGRM13) ; aucune bande d'« économie carburant » 75-90 % ni dépense × 12 ; aucun bassin « ×2 » ; aucun CO₂ au facteur réseau sur un pompage ; jamais « eau gratuite », « à vie » ni « illimité » ; aucune exonération de TVA étendue aux panneaux, au variateur ou au kit ; aucune nouvelle clé webhook (`tunnel_webhook_keys.json` inchangé) ; jamais `wrangler deploy` ni commande de déploiement (Cloudflare déploie au merge). Supprimée par l'assemblage : AGW406 (doublon d'AGW306 ; sa garde globale « aucun 30 % » vit dans AGW307).

- [ ] AGW300 — **Page /proposition agricole : plus d'« Économie / an » ni de « Rentabilisé en » résidentiels, plus de CO₂ au facteur réseau.** Aujourd'hui : `apps/web/src/pages/proposition/[...token].astro:573-579` définit `ecoHero` et `paybackHero` à partir de `q.eco_s_ann` et `q.roi_s` sans regarder le mode. Quatre endroits les lisent sans garde `isAgricole` : la carte héros (`:2336-2351` et `:2371-2391`), le repli méthode (`:3605`), le bandeau « Économie estimée / an » (`:4358-4369`) et la carte « Rentabilisé en » (`:4722-4725`). Pourtant, le chapitre économies est déjà exclu en pompage (`:2055`, `:3425`, WJ126). Le bloc CO₂ (`:1551` `environmentalImpact(prodKwh)`, rendu `:7175-7182`) multiplie TOUTE la production PV par `CO2_KG_PER_KWH = 0.81` (`apps/web/src/lib/proposition.ts:1802`, « source à préciser ») : une base fausse pour une pompe qui remplace du butane ou du gasoil. Mieux : une fonction PURE `chiffresEconomiePhare(p)` dans `proposition.ts` renvoie `null` pour les économies et paybacks (sans, avec, héros) quand `resolveInstallMode(p) === 'agricole'`. Elle est utilisée à la SEULE définition `:573-579`, si bien que les 4 endroits s'éteignent d'un coup. `enviro` vaut `null` en agricole. Cette garde double celle d'AGR300 : le serveur ne sert déjà plus ces clés. L'argent agricole reviendra par `synthese_agricole.economies` (AGW304), jamais par ces clés. **Done =** vitest comportemental rouge d'abord sur la fonction pure : un payload agricole AVEC `eco_s_ann` et `roi_s` remplis donne tout à `null`, le résidentiel est inchangé, le CO₂ est `null` en agricole ; `astro check` et build verts ; aller-retour en direct (AGR318). Files: apps/web/src/pages/proposition/[...token].astro, apps/web/src/lib/proposition.ts, apps/web/tests/propositionAgricoleAGW300.test.ts (nouveau). (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR300)
- [ ] AGW301 — **Page /proposition agricole : retirer les cartes « Bassin recommandé ≈ 2 jours », « Subvention FDA … 30 % » et « Fini le carburant », et afficher les heures derrière le m³/jour.** Aujourd'hui, dans `apps/web/src/pages/proposition/[...token].astro` : • `:3095-3103` montre un bassin en m³ = 2 × un besoin FAO-56 bâti sur des constantes « ESTIMÉES … à vérifier » : la règle du zéro chiffre inventé est enfreinte, en ligne ; • `:3104-3112` promet en FR/EN/AR « une aide … pouvant atteindre 30 % » dès que l'irrigation est au goutte-à-goutte, contre Q22 et D-AGR-6, alors que le site public garde déjà ce texte (`apps/web/src/pages/pompage-solaire.astro:434-455`, WG11) ; • `:3114-3123` affirme à TOUT agriculteur « plus de gasoil à acheter … sans facture de carburant », y compris au butane ou sur un forage neuf ; • la carte « Eau / jour » (`:3039-3049`) n'affiche que « à X m HMT », alors que le PDF dit « sur N h de pompage ». Mieux : supprimer les trois cartes (FR/EN/AR) et les champs `bassin_m3` / `fda_eligible` de `AgricoleKpis` (`apps/web/src/lib/proposition.ts:3901-3909`, `agricoleKpis` `:3971-3982`) ; lire `heures_pompage` et afficher « estimation, sur N h de pompage (hypothèse) » sous l'eau/jour. La règle FDA sans montant et la carte d'énergie DÉCLARÉE reviennent par `synthese_agricole` (AGW304). Contrat partagé `proposal_data.json` (check_api_shapes). **Done =** vitest rouge d'abord sur `agricoleKpis` : plus de `bassin_m3` ni de `fda_eligible`, `heures_pompage` lu ; `apps/web/tests/propositionModesWJ126.test.ts:55`, `:132-133`, `:147` et `:158-159`, qui épinglaient le comportement fautif, sont réécrits ; build vert ; l'aller-retour en direct (AGR318) confirme l'absence de « 30 % ». Files: apps/web/src/pages/proposition/[...token].astro, apps/web/src/lib/proposition.ts, apps/web/tests/propositionModesWJ126.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR301, AGW300)
- [ ] AGW302 — **« Nos hypothèses » suit le vrai mode du devis : plus de « Résidentiel (simulateur) » ni de « loi 82-21 / tarif ONEE » sur un pompage, ni sur un industriel ou un commercial.** Aujourd'hui : `proposalAssumptions` (`apps/web/src/lib/proposition.ts:3648-3686`) compare `quote.inst_type` à `'agricole'`, `'industriel'` et `'commercial'` en minuscules, alors que le builder produit « Agricole », « Industrielle » et « Commerciale » (`backend/django_core/apps/ventes/quote_engine/builder.py:3152-3159`) : la branche par défaut « Résidentiel (simulateur) » est TOUJOURS prise. Le « Cadre tarifaire : autoconsommation basse tension (loi 82-21), tarif ONEE » est inconditionnel, contrairement à Q16 (distributeur = SRM régionale), et le bloc est rendu sans condition de mode (`[...token].astro:1963`, `:7156`). Mieux : brancher sur `resolveInstallMode` (`proposition.ts:3949`, clé machine, jamais `inst_type`). En agricole, « Cadre tarifaire » et « Horizon 25 ans » sont remplacés par les hypothèses du pompage lues dans le payload : heures de pompage, HMT retenue et débit à cette HMT, plus leur provenance déclaré/mesuré quand `synthese_agricole` est servie. Aucune mention 82-21 d'autoconsommation ni d'injection. En industriel, commercial et résidentiel : libellé du type corrigé, distributeur nommé « SRM » (Q16). **Done =** vitest rouge d'abord sur les 4 valeurs réelles d'`inst_type` (« Agricole », « Industrielle », « Commerciale », « Résidentielle ») : bon libellé, aucune ligne « 82-21 » ni « ONEE » en agricole, « SRM » ailleurs ; build vert. Files: apps/web/src/lib/proposition.ts, apps/web/tests/propositionHypothesesAGW302.test.ts (nouveau). (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR301)
- [ ] AGW303 — **Jumeau web du document agricole (1/2) : l'eau, le besoin de la culture, le schéma et le point de fonctionnement lus dans `synthese_agricole`, sans aucun calcul dans la page.** Aujourd'hui : « Votre eau au fil des mois » (`apps/web/src/pages/proposition/[...token].astro:3075-3093`) est calculé dans le navigateur par `agricoleMonthlyDelivery` (`apps/web/src/lib/proposition.ts:4070-4085` : m³/jour × 365 répartis selon la part de production ; « AUCUNE série de BESOIN culture n'existe dans ce payload »). La page n'a ni besoin, ni schéma, ni courbe, ni provenance des hypothèses. Mieux : la section `#mode-agricole` rend `synthese_agricole` telle quelle (contrat partagé `proposal_data.json` (check_api_shapes)) : • héros eau/jour (estimation, sur N h) et hectares s'ils sont servis ; • graphe besoin vs livré mensuel (12 barres doubles, mois le plus serré annoncé), OMIS si `besoin_vs_livre` est absent ; • `schema_svg` servi, inséré tel quel (déjà échappé côté serveur) ; • courbe et point omis sans courbe, avec la phrase d'omission servie ; • bloc « D'où viennent ces chiffres » : déclaré par vous le … / mesuré par TAQINOR le … / à confirmer par la visite / besoin agronomique plein ; • pompe existante conservée : plaque et compatibilité. Supprimer `agricoleMonthlyDelivery` et son usage (`[...token].astro:563`). Libellés FR/EN/AR (les `data-ar` sont écrits maintenant et relus après, manuel). **Done =** vitest rouge d'abord sur un extracteur pur `syntheseAgricole(p)` à lecture défensive (clé absente → `null`, série partielle → `null`, jamais un 0 fabriqué) et sur la disparition de `agricoleMonthlyDelivery`. Avec un payload sans `synthese_agricole`, la section garde ses cartes pompe et n'affiche ni graphe ni schéma. Build vert ; aller-retour en direct (AGR318). Files: apps/web/src/pages/proposition/[...token].astro, apps/web/src/lib/proposition.ts, apps/web/tests/propositionModesWJ126.test.ts, apps/web/tests/propositionAgricoleSyntheseAGW303.test.ts (nouveau). (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR308, AGW301)
- [ ] AGW304 — **Jumeau web du document agricole (2/2) : argent déclaré, énergie actuelle, règle de l'aide FDA, garanties pompe/variateur, options du kit et formalités, lus dans `synthese_agricole`.** Aujourd'hui : la page agricole ne dit rien de l'argent (chapitre économies exclu, `apps/web/src/pages/proposition/[...token].astro:2055`, `:3425`). Le bloc garanties (`:2716-2793`) ne connaît que les panneaux et l'onduleur (`equipmentPresence`, `apps/web/src/lib/propositionPage.ts:455-476` : « un variateur n'est pas un onduleur »), plus une garantie de pose « toujours vraie ». Les lignes optionnelles servies dans `options_proposees` (XSAL5) ne sont rendues nulle part, et aucune formalité n'est rappelée. Mieux : rendre ces blocs tels que servis (contrat partagé `proposal_data.json` (check_api_shapes)) : (1) `economies` : dépense déclarée datée, charges, remplacement de la pompe en année 7, économie nette, retour SANS aide, coût du m³ avant/après, bouteilles ou litres par an, phrase de condition ; OMIS si absent ; (2) `energie_actuelle`, seulement si elle est déclarée (butane : bouteilles ; diesel : gasoil et groupe ; réseau : facture) ; (3) la règle FDA servie : conditions, plafonds, accord AVANT travaux, versement après réalisation, non garantie, source Guide FDA 2024. Jamais un montant ni un délai, jamais « jusqu'à 30 % » ; (4) les garanties par composant servies (pompe, variateur, panneaux). En agricole, la garantie de pose codée en dur n'apparaît que si la synthèse la sert ; (5) les options du kit nommées avec leur supplément TTC + « non inclus : forage, génie civil », en lecture seule (l'activation en ligne est AGW308) ; (6) les formalités (82-21 art. 3, 36-15). Aucun « gratuit », « à vie » ni « illimité ». FR/EN/AR. **Done =** vitest rouge d'abord sur les extracteurs purs : bloc absent → `null` ; énergie non déclarée → pas de carte ; aucune valeur numérique dans l'aide FDA en dehors des plafonds de la règle servie ; garanties jamais complétées par une constante. Build vert ; aller-retour en direct (AGR318). Files: apps/web/src/pages/proposition/[...token].astro, apps/web/src/lib/proposition.ts, apps/web/src/lib/propositionPage.ts, apps/web/tests/propositionAgricoleArgentAGW304.test.ts (nouveau). (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR308, AGW303)
- [ ] AGW305 — **Site public : l'exonération de TVA ne « couvre » plus « la pompe comme les panneaux » et n'est plus « vérifiée » avant l'avis du fiscaliste (FR/EN/AR).** Aujourd'hui : `apps/web/src/pages/pompage-solaire.astro:366-370` titre « Avantage fiscal vérifié » et écrit « l'exonération couvre l'ensemble : la pompe comme les panneaux qui l'alimentent ». Les jumelles disent la même chose : `apps/web/src/pages/en/pompage-solaire.astro:357-362` (« Verified tax advantage … the pump as much as the panels ») et `apps/web/src/pages/ar/pompage-solaire.astro:345-350`. Or le CGI 2026 consolidé n'exonère que « les pompes à eau qui fonctionnent à l'énergie solaire … utilisées dans le secteur agricole » (art. 91-I-C-6°, exonération SANS droit à déduction, LF n° 80-18 de 2019, art. 7), et l'art. 99-B-1° place les panneaux photovoltaïques à 10 %. Un client qui lit 0 % sur la page et un autre taux sur son devis tient un litige de prix. Mieux : reformuler dans les 3 langues : « La vente de pompes à eau solaires à usage agricole est exonérée de TVA (art. 91 du CGI). Le traitement des autres éléments du kit figure ligne par ligne sur votre devis. » Retirer « vérifié » ; aucune promesse de taux sur les panneaux, le variateur ou le kit. Les taux du devis ne changent pas (règle de l'orchestrateur : avis ÉCRIT du fiscaliste d'abord, partie D2). Un grep « exonér » sur `apps/web/src/pages/**` cherche les autres jumeaux : toute autre page qui étend l'exonération aux panneaux est corrigée dans le même commit. **Done =** garde de contenu rouge d'abord sur le HTML construit (`astro build`) des 3 langues : aucune page ne contient « la pompe comme les panneaux », « Avantage fiscal vérifié » ou leurs équivalents EN/AR ; build vert. Files: apps/web/src/pages/pompage-solaire.astro, apps/web/src/pages/en/pompage-solaire.astro, apps/web/src/pages/ar/pompage-solaire.astro, apps/web/tests/pompageTvaAGW305.test.ts (nouveau). (ROUTINE) (@lane: web) (@model: sonnet)
- [ ] AGW306 — **Page Financement : la carte « FDA ≈ 30 %, cumulable » devient la règle complète et sourcée de l'aide (FR/EN/AR), avec les mêmes mots que le devis.** Aujourd'hui : `apps/web/src/pages/financement.astro:68-70` (jumelles `en/financement.astro:68-70` et `ar/financement.astro:61-63`) annonce « subvention pompage solaire ≈ 30 % … Cumulable avec la subvention goutte-à-goutte existante ». La carte ne donne ni les plafonds, ni la condition butane, ni l'accord préalable, et ne s'appuie que sur des blogs (agrimaroc, casainvest) ; le Guide FDA est muet sur le cumul. D-AGR-6 (02/10/2026) tranche : on imprime la RÈGLE (conditions ; plafonds 30 % / 3 000 DH par ha / 3 000 DH par kWc / 30 000 DH par projet ; accord AVANT travaux ; versement après réalisation ; un seul projet par exploitation ; Guide FDA 2024 p.20-23), jamais un montant propre au client ni un délai, et « jusqu'à 30 % » disparaît partout. Mieux : réécrire la carte FDA des 3 pages Financement avec la règle complète, son édition et sa source, plus « décision de la DPA/ORMVA, non garantie ; TAQINOR n'est pas organisme subventionneur ». La formulation est recopiée du repli daté de `quote_engine/agricole/mentions.py` (AGR306), pour que site et devis ne disent jamais deux choses. Supprimer « Cumulable » : le cumul n'est pas confirmé par la DPA (manuel). Annoter WG11 dans `docs/WEB_PLAN.md` : D-AGR-6 le lève pour ces seuls faits sourcés. La carte Saquii reste inchangée. **Done =** garde de contenu rouge d'abord sur le HTML construit : aucune page Financement ne contient « ≈ 30 % », « jusqu'à 30 % », « pouvant atteindre » ni « Cumulable » ; chaque carte FDA cite « Guide FDA 2024 », sa date de lecture et « avant travaux » (repris de l'ex-AGW406) ; build vert. Files: apps/web/src/pages/financement.astro, apps/web/src/pages/en/financement.astro, apps/web/src/pages/ar/financement.astro, apps/web/tests/financementFdaAGW306.test.ts (nouveau), docs/WEB_PLAN.md. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR306)
- [ ] AGW307 — **Page Pompage solaire : la carte « Piste de financement — à vérifier » (WG11) publie la règle sourcée de l'aide FDA, sans montant (FR/EN/AR).** Aujourd'hui : `apps/web/src/pages/pompage-solaire.astro:434-455` et ses jumelles `en/pompage-solaire.astro:423-445` et `ar/pompage-solaire.astro:405-420` ne publient « aucun pourcentage ni montant » en attendant WG11. D-AGR-6 tranche désormais ce que l'on imprime : la règle. Mieux : le même texte que le repli daté de `quote_engine/agricole/mentions.py` (AGR306) et que la page Financement (AGW306) : conditions (remplacement du butane, irrigation localisée, compteur), plafonds, accord AVANT travaux, versement après réalisation, un seul projet par exploitation, source Guide FDA 2024 p.20-23, éligibilité décidée par la DPA/ORMVA et non garantie. Le paragraphe Saquii reste inchangé (non vérifié). Jamais « jusqu'à 30 % ». **Done =** garde de contenu rouge d'abord sur le HTML construit des 3 langues : la règle et sa source sont présentes, et aucun « jusqu'à », « pouvant atteindre » ni « ≈ 30 % » n'apparaît ; garde GLOBALE (reprise de l'ex-AGW406) dans `tests/contentInvariantsW131.test.ts` : aucune page de `apps/web/src/pages/**` ne contient « jusqu'à 30 », « up to 30 », « حتى 30 » ni « ≈ 30 % » — elle ne peut passer qu'après AGW301, AGW305, AGW306 et AGW405 ; build vert. Files: apps/web/src/pages/pompage-solaire.astro, apps/web/src/pages/en/pompage-solaire.astro, apps/web/src/pages/ar/pompage-solaire.astro, apps/web/tests/pompageFdaAGW307.test.ts (nouveau), apps/web/tests/contentInvariantsW131.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR306, AGW305, AGW306, AGW301, AGW405, AGW402)
- [ ] AGW308 — **Options du kit à cocher sur /proposition : le client ajoute une option nommée à son devis avant de signer, avec confirmation (endpoint XSAL5 existant).** Aujourd'hui : le serveur sert `options_proposees` (`backend/django_core/apps/ventes/quote_engine/builder.py:3849-3888`, prix = supplément canonique QJR616) et expose déjà `POST …/proposal/<token>/activer-option/` (`backend/django_core/apps/ventes/urls.py:180`, `proposal_activate_option` `public_views.py:4519` : idempotent, aucun statut touché, 409 si le devis est figé). Aucune page ne l'appelle : dans `apps/web/src`, seule la copie du contrat cite `options_proposees`. D-AGR-8 met tout l'accessoire du kit en options nommées à cocher. Mieux : un proxy same-origin `apps/web/src/pages/api/proposition-option.ts`, même convention que `proposition-accept.ts`, vers `/api/django/ventes/proposal/<token>/activer-option/`. Dans la liste d'options d'AGW304, chaque option porte un bouton « Ajouter au devis » qui ouvre une confirmation : « l'option sera ajoutée à votre devis : + X MAD TTC ; elle ne peut pas être retirée en ligne, contactez votre conseiller » (le backend n'a pas d'endpoint de retrait). Après l'appel, la page recharge les totaux servis et ne recalcule jamais un total. En aperçu interne, le bouton est inactif (R4). Un 409 ou un 404 donne un message amical. Contrat partagé `proposal_data.json` (check_api_shapes) ; le chemin est vérifié par le contrôle (c) de `scripts/check_api_shapes.py`. **Done =** vitest rouge d'abord sur le constructeur d'URL et sur la fonction pure qui décide l'affichage (option servie + lien non interne + devis non figé) ; test du proxy (corps `{ligne_id}` transmis, statut renvoyé) ; aller-retour en direct sur la pile locale : l'option ajoutée apparaît dans les totaux du PDF régénéré. Files: apps/web/src/pages/api/proposition-option.ts (nouveau), apps/web/src/lib/proposition.ts, apps/web/src/pages/proposition/[...token].astro, apps/web/tests/propositionOptionAGW308.test.ts (nouveau). (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGW304)
- [ ] AGW401 — **Tunnel : `?mode=agricole` présélectionne VISIBLEMENT la carte Agricole, et l'étape 0 parle de forage ou de parcelle.** Aujourd'hui : mon-toit.astro ne lit aucun paramètre d'URL (grep URLSearchParams/location.search = 0). Le choix de profil n'est jamais présélectionné (apps/web/src/pages/devis/mon-toit.astro:216-221, décision QX : pas de défaut SILENCIEUX). L'étape 0 dit « posez un repère sur votre toit » et montre Pointer/Dessiner mon toit à tous les modes (244-297) ; le groupe n'est masqué que par showFallback (2919-2920). Mieux : dans les 3 tunnels (FR/EN/AR), lire `?mode=` dans la liste fermée des 4 modes. La carte correspondante apparaît sélectionnée (aria-pressed=true) et reste modifiable : c'est l'intention que le visiteur a déclarée en cliquant, donc compatible avec QX. En mode agricole, le texte de l'étape 0 devient « Posez un repère sur votre forage ou votre parcelle » (et ses équivalents EN/AR). Le groupe Pointer/Dessiner mon toit est masqué ; GPS et ville sont conservés. Aucune nouvelle clé webhook (tunnel_webhook_keys.json inchangé). **Done =** test rouge d'abord (tests/monToitTunnel.test.ts) : ?mode=agricole → carte agricole pressée et texte forage, dans les 3 langues ; ?mode=inconnu → aucun mode ; sans paramètre → comportement identique à l'octet. Aller-retour EN DIRECT sur la prévisualisation locale. Files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/en/devis/mon-toit.astro, apps/web/src/pages/ar/devis/mon-toit.astro, apps/web/tests/monToitTunnel.test.ts. (ROUTINE) (@lane: web) (@model: sonnet)
- [ ] AGW400 — **/pompage-solaire envoie au tunnel avec `?mode=agricole` (FR/EN/AR).** Aujourd'hui : les 4 liens de apps/web/src/pages/pompage-solaire.astro (lignes 240, 429, 472, 491) pointent vers /devis/mon-toit sans paramètre. Les pages EN et AR utilisent `devisHref = L('/devis/mon-toit')` (en/pompage-solaire.astro:45, ar/pompage-solaire.astro:43). Un agriculteur doit retrouver sa carte parmi 4. Mieux : chaque lien vers le tunnel depuis les trois pages de pompage porte `?mode=agricole`, que le tunnel lit (AGW401). Les autres pages ne changent pas. **Done =** test rouge d'abord (tests/monToitTunnel.test.ts) : tout href vers le tunnel dans les 3 pages pompage contient mode=agricole, et aucun href de l'accueil n'en contient. Clic en direct sur la prévisualisation → carte agricole sélectionnée. Files: apps/web/src/pages/pompage-solaire.astro, apps/web/src/pages/en/pompage-solaire.astro, apps/web/src/pages/ar/pompage-solaire.astro, apps/web/tests/monToitTunnel.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGW401, AGW305)
- [ ] AGW402 — **Porte WhatsApp pompage : un message de pompage en FR/AR/EN, et l'anglais n'est plus servi en français.** Aujourd'hui : zeroFormWhatsappText n'a qu'un texte « photo de ma facture d'électricité », en FR et en AR (apps/web/src/lib/whatsapp.ts:48-59). /pompage-solaire l'utilise et dit « Envoyez une photo de votre facture » (pompage-solaire.astro:49, 151-153), alors qu'un agriculteur au butane n'a pas de facture. en/pompage-solaire.astro:48 et en/index.astro:47 l'appellent sans langue : l'anglais reçoit le français. Mieux : variante pompage `zeroFormWhatsappText(locale, 'pompage')`. FR : « Bonjour, je souhaite un pompage solaire pour mon exploitation. Je vous envoie ma position et une photo de la plaque de ma pompe (ou de mon forage). » Versions AR (fus'ha + une ligne darija, même patron) et EN. Ajout d'une locale 'en' au texte d'accueil. Le bloc des 3 pages pompage devient « Envoyez sur WhatsApp une photo de la plaque de votre pompe ou de la tête du forage, et un reçu de butane ou de gasoil si vous l'avez. » Ni prix ni promesse d'aide. Darija écrite maintenant, relue par Reda ensuite (D-AGR-11). **Done =** test rouge d'abord (tests/whatsapp.test.ts) : variante pompage FR/AR/EN non vide et sans « facture » ; EN de l'accueil en anglais ; FR de l'accueil identique à l'octet. Les 3 pages pompage utilisent la variante (assertion sur le href). Files: apps/web/src/lib/whatsapp.ts, apps/web/src/pages/pompage-solaire.astro, apps/web/src/pages/en/pompage-solaire.astro, apps/web/src/pages/ar/pompage-solaire.astro, apps/web/src/pages/en/index.astro, apps/web/tests/whatsapp.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGW400)
- [ ] AGW403 — **Tunnel : les heures de pompage ne partent que si le visiteur a touché le curseur.** Aujourd'hui : le curseur vaut 7 avant toute interaction (apps/web/src/pages/devis/mon-toit.astro:762-765). champs.ts:676-683 ne filtre que sur le mode agricole, et lecture.ts:72 lit la valeur brute. Chaque lead agricole porte donc pompage_heures_jour=7, que personne n'a dit (backend/django_core/apps/crm/webhooks.py:1174-1176). Le panneau d'appel saute alors la question (panneau_appel.py:115-126). Mieux : dans les 3 tunnels, le curseur porte `data-touche="1"` dès son premier événement input/change. lecture.ts expose cet état, et champs.ts n'envoie heuresPompage que si le curseur a été touché. L'estimation affichée garde ses 7 h par défaut (HEURES_POMPAGE_DEFAUT, estimatorAgricole.ts:21, hypothèse interne), sans changement visible. **Done =** test rouge d'abord (tests/tunnelCorps.test.ts) : curseur non touché → aucune clé heuresPompage dans le corps ; touché à 7 → heuresPompage=7 ; même résultat en FR, EN et AR. Files: apps/web/src/lib/tunnel/champs.ts, apps/web/src/lib/tunnel/lecture.ts, apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/en/devis/mon-toit.astro, apps/web/src/pages/ar/devis/mon-toit.astro, apps/web/tests/tunnelCorps.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGW401)
- [ ] AGW404 — **Supprimer la bande d'« économie carburant » 75-90 % du tunnel (écran, CRM et message WhatsApp).** Aujourd'hui : FUEL_SAVING_LOW 0,75 / HIGH 0,9 n'ont aucune source et multiplient une dépense « par mois » × 12 (apps/web/src/lib/estimatorAgricole.ts:50-55, 183-187). Le résultat part dans estimateShown → CRM « Économie annuelle » (mon-toit.astro:3815-3816, 3847-3852), dans la carte « Économie carburant » (997-1014), et dans le WhatsApp que le visiteur envoie lui-même (« économies estimées », lastSavingsLabel 3820 → buildWaUrl 4616 → whatsapp.ts:92-95). Même chose dans la page AR (ar/devis/mon-toit.astro:3500-3505). Mieux : retirer FUEL_SAVING_* et fuelSaving* de estimateAgricole. La carte devient « Dépense carburant déclarée : X MAD/mois », la valeur du visiteur telle quelle (sans × 12 ni pourcentage) ; elle est masquée si vide. Pas de ecoMadYear* dans estimateShown en agricole. lastSavingsLabel est vide en agricole. Le texte sous le champ devient « Elle sert à l'étude de votre projet ; l'économie est calculée dans le devis. ». Le tout dans les 3 langues. **Done =** test rouge d'abord (tests/estimatorAgricole.test.ts, tests/wj111AgricoleEstimate.test.ts) : estimateAgricole ne renvoie plus aucune clé fuelSaving* ; estimateShown agricole sans ecoMad* ; captureWhatsappText reçu sans savingsLabel en agricole ; résidentiel inchangé. Files: apps/web/src/lib/estimatorAgricole.ts, apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/en/devis/mon-toit.astro, apps/web/src/pages/ar/devis/mon-toit.astro, apps/web/tests/estimatorAgricole.test.ts, apps/web/tests/wj111AgricoleEstimate.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGW403)
- [ ] AGW405 — **Tunnel : retirer « Subvention FDA : jusqu'à 30 % » (FR/EN/AR) et la promesse « dossier accompagné par nos soins ».** Aujourd'hui : le tunnel affiche « jusqu'à 30 % du coût d'un kit de pompage solaire (dossier accompagné par nos soins) », sous un commentaire « fait vérifié » (apps/web/src/pages/devis/mon-toit.astro:772-775 ; en/devis/mon-toit.astro:719-722 ; ar/devis/mon-toit.astro:709-712). Or le pilote FDA ne vise que le remplacement du butane, exige un accord préalable AVANT travaux, et plafonne l'aide à 30 000 DH par projet (Guide FDA édition 2024, p.20-23, casainvest.ma). La décision Q22 dit « ne rien promettre ». Mieux : texte court, sans pourcentage : « Aide de l'État (FDA) possible pour remplacer une pompe au butane, sous conditions, avec accord préalable de votre DPA/ORMVA AVANT les travaux — détails sur la page Financement. » (et ses équivalents EN/AR). Retirer « dossier accompagné par nos soins » tant que Reda ne l'a pas confirmé (tâche manuelle). Le commentaire cite la source et la date de lecture. **Done =** test rouge d'abord (tests/monToitTunnel.test.ts) : aucune des 3 pages tunnel ne contient « 30 », « up to 30 » ni « حتى 30 » dans le bloc FDA ; le lien vers /financement est présent. Files: apps/web/src/pages/devis/mon-toit.astro, apps/web/src/pages/en/devis/mon-toit.astro, apps/web/src/pages/ar/devis/mon-toit.astro, apps/web/tests/monToitTunnel.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGW404)
- [ ] AGW409 — **Estimateur agricole du tunnel : constantes lues dans le jumeau de la table d'hypothèses du noyau (fin des 0,55/0,50 et du bassin 1×).** Aujourd'hui : `apps/web/src/lib/estimatorAgricole.ts:33-38` porte un rendement 0,55/0,50, un refoulement et un bassin 1× propres au site, divergents de l'ERP (constat C2-18) ; AGW404 n'en retire que la bande carburant. Mieux : AGR110 pose l'échantillon `backend/django_core/apps/ventes/contract_samples/hypotheses_pompage.json` (export de `core/pompage/hypotheses.py` : clé, valeur, statut, source) ; sa copie jumelle `apps/web/src/contract_samples/hypotheses_pompage.json` (JSON-égale, contrôle (a) de `scripts/check_api_shapes.py`) devient la SEULE source des constantes de `estimatorAgricole.ts` (2,725 Wh/m³/m, 1 CV = 0,7355 kW, rendement groupe 0,5 `EST.`, heures de repli) ; suppression des constantes locales et de tout bassin ; chaque chiffre affiché porte « estimation ». Aucune clé webhook nouvelle (`tunnel_webhook_keys.json` inchangé). **Done =** vitest rouge d'abord : les constantes de l'estimateur égalent celles du JSON (lu, jamais recopié) ; aucune constante hydraulique littérale ne reste dans `estimatorAgricole.ts` (assertion du test) ; `check_api_shapes.py` vert ; valeurs attendues recalculées dans le test là où la constante différait ; build vert. Files: apps/web/src/lib/estimatorAgricole.ts, apps/web/src/contract_samples/hypotheses_pompage.json (nouveau), apps/web/tests/estimatorAgricole.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR110, AGW404)
- [ ] AGW407 — **Corriger les commentaires périmés « regionAgricole non persistée ».** Aujourd'hui : apps/web/src/lib/tunnel/champs.ts:692-697 et apps/web/src/lib/lead.ts:478-483 disent que le webhook ne PERSISTE pas encore la région. Or elle l'est depuis WJ124 (backend/django_core/apps/crm/webhooks.py:453-457), et le contrat la déclare (tunnel_webhook_keys.json:419-425). Bientôt, elle aura une colonne (AGR402). Mieux : réécrire les deux commentaires (persistée, et colonne `region_agricole` une fois AGR402 livré), sans aucun changement de code. **Done =** diff limité à des commentaires ; `astro check` et les tests web restent verts. Files: apps/web/src/lib/tunnel/champs.ts, apps/web/src/lib/lead.ts. (ROUTINE) (@lane: web) (@model: haiku) (@after: AGW403, AGR402)
- [ ] AGW408 — **Page publique du questionnaire : section pompage et photos plaque/forage (FR/EN/AR).** Aujourd'hui : QUESTIONNAIRE_SECTIONS et la page /questionnaire/[token] ne connaissent que les sections résidentielles et les photos facture/compteur/tableau (apps/web/src/lib/questionnaire.ts:40-72). Mieux : dessiner les sections `pompage`, `photo_pompe` et `photo_forage` servies par le serveur (AGR411). Chaque question reprend le help_text de la colonne, traduit EN/AR. Champs numériques `step="any"`, mois d'irrigation en 12 boutons, choix fermés identiques au contrat. Les photos suivent le patron des sections photo_*. La page ne dessine que ce que le serveur sert. **Done =** test rouge d'abord (tests/questionnaire.test.ts, tests/questionnaireChampsParite.test.ts) : parité des colonnes avec le contrat `questionnaire_lead.json` ; corps POST attendu ; une section résidentielle n'apparaît jamais si le serveur ne la sert pas ; aller-retour en direct sur un lien de test. Files: apps/web/src/pages/questionnaire/[token].astro, apps/web/src/lib/questionnaire.ts, apps/web/src/pages/api/questionnaire-repondre.ts, apps/web/tests/questionnaire.test.ts, apps/web/tests/questionnaireChampsParite.test.ts. (ROUTINE) (@lane: web) (@model: sonnet) (@after: AGR411)

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

