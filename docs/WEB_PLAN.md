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

- [x] WJ117 — **Fix état sélectionné des cartes (bug cascade layers).** Cause auditée : les
  8 groupes (.mt-mode/.mt-roof-card/.mt-tension/.mt-activity/.mt-water-source/.mt-irrigation/
  .mt-water-unit/.mt-pro-unit) togglent bien border-brass-400 (wireCardGroup :2596, syncMode
  :2170, syncRoof :2205) mais `.cine-card` (global.css:386, NON layered) écrase la couleur
  de bordure des utilitaires (layered). Fix : règle CSS non-layered
  `.cine-card[aria-pressed="true"]` (bordure or 2px + fond teinté brass/10 + ✓ coin +
  label bold) dans global.css — UNE règle répare les 8 groupes × 3 locales ; état keyboard
  focus-visible conservé. **Done =** capture Playwright avant/après sur les 3 profils ;
  test source-level asserte la règle. (@lane: web-journey) (@model: sonnet)
- [x] WJ118 — **Photo satellite sur la 3D de la page client.** [token].astro : appeler
  `buildPublicRoofImageSpec({outline})` (export viewerOnly.ts:280 ; doc/usage :1-36) avec le
  contour = `roof_layout.zones[].vertices` (champ ASSAINI exposé par `_safe_roof_layout`,
  public_views.py:386-392) converti [lng,lat]→[lat,lng], passer `roofImage` à createRoofViewer
  (:2921 — aujourd'hui appelé SANS roofImage ; vérifier que createRoofViewer accepte/applique
  une texture satellite, sinon l'ÉTENDRE) ; supprimer le commentaire périmé (:305) ; le « fond
  bleu » est le fond CSS `.roof3d-stage` (:3405) — basculer en ciel clair/jour quand drapé,
  l'abstrait actuel sinon (dégradation byte-identique sans clé/contour). Attribution
  visible (contrat viewerOnly, champ `attribution`). **Done =** avec MAPTILER/MAPBOX configuré,
  la 3D client montre SON toit photographié ; sans clé, rendu actuel inchangé ; test du
  convertisseur de coordonnées. (@lane: web-proposal) (@model: sonnet)
- [x] WJ119 — **Courbe journalière RÉELLE Maroc + par mode.** proposalCurve.ts : remplacer
  la double-gaussienne (:46-52) par la silhouette marocaine soirée-dominante (porter
  BASELINE_SHAPE, applianceConsumption.ts:111-116 — pic 19h-21h ≈26 % de l'énergie) ;
  variantes : été/intérieur (+40-60 % 13h-18h, clim) et Ramadan (jour −30-40 %, pic iftar,
  bosse suhoor 3h-5h) en toggle discret ; par MODE : industriel = profil d'équipes (1x8/
  2x8/3x8), commercial = archétype catégorie (QX44), agricole = fenêtre de pompage.
  Libellé honnête « profil type au Maroc, ajusté à votre facture » (jamais « mesuré »).
  **Done =** la courbe cesse d'être la même pour une villa et une usine ; sources en
  commentaire ; tests de forme (pic du soir dominant résidentiel). (@lane: web-proposal)
  (@model: sonnet)
- [x] WJ120 — **Simulateur « et avec N batteries ? » sur la page client.** Nouveau bloc
  proposition (résidentiel + commercial) : moteur horaire glouton (jour 2 simulé pour
  éviter le biais de SoC initial) sur courbe conso (WJ119) × courbe solaire existante :
  direct = min(prod, conso) ; surplus → batterie (η one-way ≈0,96, DoD 90-95 % LFP) ;
  déficit ← batterie puis réseau. Unités RÉELLES du catalogue (seed_catalogue.py:48-49) :
  Deyness 5 kWh (BAT-DEY-5) / 10 kWh (BAT-DEY-10) — la CAPACITÉ par unité vient de ces réfs.
  NB : le `?? 5.0` (solar.js:503 = capacité/unité par défaut) et `BATTERY_KWH_PER_DAY=6`
  (applianceConsumption.ts:33 = conso journalière) mesurent des choses DIFFÉRENTES (kWh de
  capacité vs kWh/jour consommés) — ne PAS les « réconcilier » comme si c'était le même
  nombre ; sourcer la capacité du catalogue (5/10), jamais le 6. Slider 0/1/2/3 unités →
  3 chiffres live : autoconsommation
  % (et autosuffisance %, les DEUX libellés distincts), kWh directs/batterie/réseau (aire
  empilée style SolarEdge), heures de secours sur CHARGES ESSENTIELLES (frigo+éclairage+
  box, jamais toute la maison). Hypothèses (DoD/rendement) en note. AUCUN prix batterie
  inventé : si la ligne batterie existe au devis, prix réel ; sinon « sur étude ».
  **Done =** slider live sans re-fetch ; chiffres cohérents avec totaux_avec quand N
  correspond à l'offre ; tests du moteur horaire (cas canoniques). (@lane: web-proposal)
  (@model: opus) (@after: WJ119)
- [x] WJ121 — **4 vrais modes au départ du parcours.** Split de la carte « Professionnel » :
  🏭 Industriel (usine, production) et 🏪 Commercial (hôtel, commerce, services) — FR/EN/AR.
  lead.ts : `LEAD_MODES` (aujourd'hui `['residentiel','professionnel','agricole']`, lead.ts:84)
  + `MAX_BILL_BY_MODE` (:169-173) + règles billRange/qualified gagnent À LA FOIS `industriel`
  ET `commercial` ; `professionnel` n'est plus ÉMIS par le site (alias serveur conservé :
  webhooks.py:185-196 mappe déjà `professionnel`/`professional`→industriel ET `commercial`→
  commercial ET `industriel`→industriel, et `crm.Lead.TypeInstallation` accepte les 4 —
  models.py:296-300). Stepper/labels par mode.
  **Done =** 4 cartes, leads commercial typés `commercial` (et industriel `industriel`) dans le
  CRM, tests capture. (@lane: web-journey) (@model: sonnet)
- [ ] WJ122 — **Panneau questions COMMERCIAL par catégorie.** Étape 2 commerciale : cartes
  catégorie (9 + Autre, pictos) puis 2-4 questions SPÉCIFIQUES à la catégorie choisie
  (même liste que QX44 — hôtel chambres/occupation/piscine ; restaurant chambres froides/
  horaires/cuisson ; boulangerie four/cuisson nocturne ; froid T°/volume/récolte ; école
  effectif/internat/fermeture ; santé imagerie/24h ; hammam-gym mode chauffage eau/soirée ;
  bureau effectif/serveurs/clim ; commerce froid alimentaire/horaires) + facture MAD⇄kWh.
  Estimateur : jour-share par archétype de catégorie (table miroir de QX44, commentée
  SOURCE/ESTIMATION) → puissance/production/autoconso/couverture/économies fourchette.
  Payload : categorieCommerciale + réponses (whitelist QX51). FR/EN/AR. **Done =** hôtel ≠
  bureau à facture égale à l'écran ; payload persisté ; tests. (@lane: web-journey)
  (@model: opus) (@after: WJ121, QX51)
- [ ] WJ123 — **Panneau INDUSTRIEL v2 (équipes, MT, réalisme).** Étape 2 industrielle :
  pattern d'équipes en cartes (Journée 1x8 / 2x8 / 3x8-continu / continu+weekend) →
  day-share et PLAFOND d'autoconsommation honnête (1x8 ~70-85 %, 2x8 ~55-70 %, continu
  ~25-40 % — recherche 2026-07-16) ; puissance souscrite kVA ; 12 mois de kWh (facultatif,
  1 champ « moyenne » + « été différent » réutilisé) ; surface toiture/ombrière/terrain ;
  groupe électrogène kVA + dépense diesel DH/mois (accroche substitution) ; horizon de
  décision. Micro-copy : le solaire déplace les heures PLEINES (~1,01 DH/kWh), la POINTE
  seulement avec batterie — jamais l'inverse. Estimateur v2 avec plafond par équipe ;
  ligne injection potentielle APRÈS QX50 (sinon absente). Payload → QX51. FR/EN/AR.
  **Done =** un 3x8 ne voit plus une autoconso de bureau ; tests plafonds. 
  (@lane: web-journey) (@model: opus) (@after: WJ121, QX51)
- [ ] WJ124 — **Moteur agricole web : culture → eau → pompe.** Étape 2 agricole enrichie :
  culture (cartes ~16 cultures QX48, pictos), région (8 zones dont gharb-loukkos/haouz),
  surface (ha), irrigation, + option « je connais mon débit/HMT » (chemin actuel conservé).
  Sans débit connu : besoin d'eau via le miroir web des tables QX48 (Kc mensuels, pluie
  efficace) → m³/j du mois de pointe → débit requis sur les heures de pompage → pompe/
  variateur/champ via estimateurAgricole existant + suggestion bassin (1-3× jour).
  Honnêteté : pas de prix pompe tant que QXG3 ouvert (« étude gratuite » CTA) ; la série
  mensuelle s'affiche en mini-graphe besoin vs livraison. FR/EN/AR. **Done =** un
  agriculteur (avocat Gharb 5 ha goutte) obtient besoin m³/j crédible cité, pompe CV,
  champ kWc, bassin m³ ; parité avec QX48 testée. (@lane: web-journey) (@model: opus)
  (@after: WJ121, QX48)
- [x] WJ125 — **RÈGLE FONDATEUR anti-concurrent : le document d'estimation ne se montre
  plus pendant la saisie publique.** Le `#mt-doc` détaillé (KPIs chiffrés, graphe, imprimer)
  disparaît du parcours public : à l'étape 3, une CARTE TEASER verrouillée (aperçu flouté
  du document + 1 accroche grossière max — ex. « votre toit peut couvrir une bonne part de
  votre facture » sans kWc/DH précis + « Recevez votre étude complète et personnalisée »)
  → le formulaire contact. Le document complet + Imprimer vivent UNIQUEMENT sur
  /proposition/<token> (envoyé par le commercial). ATTENTION (audit `mon-toit.astro`) :
  `computeEstimate` écrit AUSSI des chiffres HORS `#mt-doc` (qui ferme à :1121) — `mt-nearest-
  install-text`/`-link` (kWc d'une réalisation + km, :1146-1149) et `mt-cost-of-waiting-value`
  (montant MAD, :1156-1160) : gater CES zones AUSSI, pas seulement `#mt-doc` (elles sont déjà
  listées avec les zones de #mt-doc dans `resetDocZones()` :2841-2850) — sinon des chiffres
  fuient malgré le masquage de #mt-doc. `estimateShown` continue d'être calculé et envoyé au
  CRM (le commercial voit tout) — calcul silencieux, rendu gaté. TESTS (vérifié) : `captureWJ`,
  `wj111AgricoleEstimate` et la partie unitaire de `wj112RefineEstimate` testent le CALCUL/l'API
  (qui restent) → verts SANS changement ; ce sont les checks source-texte affirmant que le
  document/squelette d'estimation SE REND (`perceivedPerfWJ34` : `showEstimateSkeleton` /
  `mt-est-skeleton` / `mt-skeleton-shimmer`, et un éventuel check « délai réflexion ≤500 ms » de
  `wj112`) qui sont ADAPTÉS délibérément au nouveau rendu gaté, jamais affaiblis : le calcul
  reste, seul le RENDU public change. FR/EN/AR + mise à jour du bouton « Enregistrer/Imprimer ».
  **Done =** aucune valeur dimensionnante précise visible avant envoi du lien (y compris
  mt-nearest-install / mt-cost-of-waiting) ; capture Playwright des 3 profils ; CRM reçoit
  toujours estimateShown ; tests adaptés documentés.
  (@lane: web-journey) (@model: opus) (@after: WJ121)
- [ ] WJ126 — **Page /proposition : 4 variantes de devis (la vitrine client).** Rendre la
  page tokenisée mode-aware (payload QX49) : AGRICOLE — héros pompe (CV/kW, m³/jour à HMT,
  champ kWc), graphe mensuel eau livrée vs besoin culture, bloc bassin + FDA 30 % (caveat),
  économies diesel ; INDUSTRIEL — tuiles couverture/autoconso/économies par bande,
  mini-cashflow 10 ans, ligne injection (si QX50 active) avec mention ANRE, blocs tranches/
  ISO-CBAM ; COMMERCIAL — tuiles + blocs par catégorie (hôtel saison, restaurant froid,
  école été…) ; RÉSIDENTIEL — inchangé + WJ119/WJ120. Les cartes sans/avec batterie
  restent résidentiel(/commercial pertinent) — jamais sur pompage. PDF téléchargé = le bon
  renderer (QX45/46/47 côté moteur). FR/EN/AR. **Done =** 4 captures Playwright distinctes
  d'une même page selon le mode du devis ; zéro champ résiduel d'un autre mode ; tests
  fixtures par mode. (@lane: web-proposal) (@model: opus) (@after: QX49)

**GARDE DE COMPOSITION (convention « attend <ID> »).** WJ122/WJ123 (@after QX51), WJ124
(@after QX48) et WJ126 (@after QX49) dépendent de tâches BACKEND (PLAN2) qu'un run « work on
the web plan » (édite UNIQUEMENT apps/web) NE PEUT PAS construire — elles restent
`[BLOCKED: attend QXnn]` tant que la QX correspondante n'est pas sur `main` ; ne JAMAIS
hand-roller un substitut backend dans apps/web. WJ117/118/119/120/121/125 sont web-only
(WJ120 @after WJ119 est intra-web).

**SUIVI (revue adversariale Fable, 2026-07-16 — findings non-bloquants de la passe WJ125).**
La passe Fable a bloqué et fait corriger la fuite du compteur de panneaux 3D (WJ125 finding 1,
corrigée dans ce batch). Les findings restants sont notés ici comme tâches de suivi :

- [ ] WJ127 — **Repli teaser honnête pour les cas SANS estimation (finding 2, MEDIUM).** Les
  cartes d'erreur/edge (`mt-estimate-toolarge`, `-toolarge-pro`, callback agricole indispo) vivent
  DANS `#mt-doc` désormais masqué : un visiteur industriel à 2 000 000 MAD ne voit plus le message
  honnête « à cette échelle, étude dédiée » — seulement le teaser générique « Recevez votre étude
  complète… ». Parité a11y inversée (le lecteur d'écran reçoit GATED_ANNOUNCE, le voyant non).
  Fix : une variante figure-free du hook teaser pour ces chemins (« votre projet relève d'une étude
  dédiée — un conseiller vous rappelle »), FR/EN/AR, sans divulguer de chiffre. (@lane: web-journey)
  (@model: sonnet)
- [ ] WJ128 — **Robustesse prix/capacité du simulateur batterie (findings 3+4, LOW).** Dans
  `proposition/[token].astro`/`batterySim.ts` : (a) si la ligne batterie de l'offre matche le
  mot-clé mais ne porte ni réf ni « N kWh » lisible, `resolveOfferBattery` retombe à 5 kWh tout en
  affichant le prix réel — dissocier « capacité connue » de « prix réel » (afficher « sur étude » si
  la capacité n'est pas sûre) ; (b) `BATTERY_KEYWORDS /batter…/` prend la PREMIÈRE ligne qui matche —
  une ligne accessoire « câble batterie » listée avant le pack gagnerait : préférer la ligne au plus
  gros montant/capacité ; (c) si l'offre quote > 3 unités, le slider (max 3) ne peut jamais afficher
  le prix réel (n === offeredUnits jamais atteint) — élargir le max au nombre offert ou afficher le
  vrai total. (@lane: web-proposal) (@model: sonnet)
- [ ] WJ129 — **Durcissements mineurs (findings 5+6, NITS).** `batterySim.ts` : `clamp01` renvoie
  `hi` (1.0, borne la plus optimiste) sur entrée non-finie — le `??` ne rattrape que null/undefined ;
  utiliser le constant par défaut documenté sur NaN (inatteignable des appelants actuels, mais piège).
  Et documenter le décalage sémantique télémétrie : en chemin gaté, `estimation/viewed` se déclenche
  bien que rien de chiffré ne soit rendu, et `contact/reached` au même instant (discontinuité de
  conversion dans les dashboards funnel). (@lane: web-proposal) (@model: haiku)

---

### WJ110–WJ116 — QUOTE JOURNEY ROUND 6: verified capture/estimate defects + proposal conversion layer (2-round adversarial audit + Fable design, 2026-07-10)

*Web half of PLAN2 Groupe QX (cross-referenced per task). All findings adversarially verified
against real code 2026-07-10. Standing rules unchanged: `apps/web/**` only, keep the lead-form/
webhook contract, FR+AR+EN mirrors, no invented numbers, self-consumption-first savings (BT
surplus tariff still unpublished; 20% injection cap), auto-deploy via Cloudflare on merge.*

- [x] WJ110 — **Fire Meta CAPI from the PRIMARY funnel endpoint.** Verified: `api/capture-lead.ts` (the endpoint behind `/devis/mon-toit`, the site-wide primary CTA) never calls `fireCapi`, while the two secondary paths (`simulate.ts:76`, `preview-lead.ts:96`) both do — Meta optimizes campaigns on a non-representative slice. Fix: import `fireCapi` from `../../lib/lead` and call it in the background IIFE after `forwardLead` with the enriched `record`, mirroring simulate.ts's log-on-failure pattern; add the CAPI-call assertion test mirroring simulate's. **Done =** every qualified mon-toit submission fires CAPI exactly once (test). (@lane: web-capture)
- [x] WJ111 — **Stop showing farmers a residential number.** Verified: the step-0 mode selector changes ZERO math — `estimateFromBill(bill, {lat, city})` (mon-toit.astro:1819) is mode-blind; « Agricole (Pompage, ferme) » gets a bill-based kWc/savings/payback card that ignores the real driver (HMT + débit → m³/jour). Fix now: for `mode==='agricole'`, skip the numeric card and show a qualitative card (« Le pompage se dimensionne sur votre HMT et débit — un conseiller vous rappelle avec un calcul adapté », reuse the existing 'unavailable' card pattern :1820-1837) while keeping capture fully working; mirror fr/en/ar. Follow-up (same task if it fits, else note): a lightweight HMT+débit mini-estimator for agricole and an autoconsommation-shaped variant for professionnel; captured pompe fields flow through the existing lead contract. Cite only the two verifiable financing facts for agricole (FDA 30% pump subsidy; CAM « Saquii Solaire »). **Done =** agricole never displays a fabricated residential estimate; résidentiel/professionnel unchanged. (@lane: web-estimate)
- [x] WJ112 — **The refinement fields must move the number (and the number must be instant).** Verified: the « Pour affiner la taille » accordion (distributeur, kWh exact, ombrage, roof age, battery interest…) feeds NOTHING — `estimateFromBill` reads only bill/lat/city; only `distributeur` has an honesty note. And a deliberate 1.5-2.5 s fake « thinking » delay (THINKING_MIN/MAX_MS, :1944) sits on a synchronous computation (reduced-motion already gets 0 ms — the affordance is a choice, not physics). Fix: wire `ombrage` (documented derate multiplier) + exact-kWh + battery interest into the estimate with live updates as each field changes (EnergySage/Enpal pattern: the number reacts), honesty notes where a field is capture-only; cut the delay to ≤500 ms or zero (founder may A/B via the existing funnel-beacon variant hook instead). Mirror fr/en/ar. **Done =** filling ombrage visibly changes production/kWc; no dead « affiner » field without a disclosure; first number in ≤0.5 s. (@lane: web-estimate)
- [x] WJ113 — **City tariff lookup survives real addresses.** Verified: `tariffForCity()` exact-matches literal keys ('Casablanca'…) against free-text geocoded input (« Boulevard Zerktouni, Casablanca, Maroc » never matches) — harmless today (all values equal REGIE_TARIFF) but silently breaks per-utility personalization the day real tariff grids land. Fix: normalize (case-fold, strip diacritics, contains-match against known city names) or use a structured geocoder field. **Done =** real geocoded strings resolve to their city tariff (test). (@lane: web-estimate)
- [x] WJ114 — **Proposal first screen: decide-in-10-seconds layout + personal note.** Storydoc (1.3M sessions): 31% bounce in 10 s, 82% of those who reach section 4 finish; pricing is the most-viewed section; full personalization stack lifts engagement +47%. Fix on `proposition/[token].astro` mobile-first: above the fold with zero scroll — client name, four featured figures (kWc, production annuelle, Total TTC, économie/payback — the CANONICAL numbers), one primary CTA; render the seller's short personal note + name/photo when present in the proposal payload (ERP side passes it through — degrade gracefully when absent); keep Western numerals/LTR money sub-flow in the AR variant. **Done =** mobile viewport shows name+4 figures+CTA with no scroll; personal note renders when provided. (@lane: web-proposal)
- [x] WJ115 — **/suivi/<token> — the post-sign status page (web half of PLAN2 QX34).** New tokenized Astro page (pattern of `proposition/[token].astro`, prerender=false) rendering the milestone timeline the ERP endpoint serves: Devis accepté → Acompte reçu → Matériel commandé → Installation planifiée → Posée → Facture; WhatsApp-shareable, FR/AR, honest empty states, no invented dates. Research: post-sign portals are the emerging installer differentiator (myFreedom, Yes Solar 2025) and the natural referral surface. **Done =** each backend milestone state renders correctly (fixture-driven test); page degrades gracefully on expired token. (@lane: web-suivi) (@after: PLAN2 QX34)
- [x] WJ116 — **Parrainage page: real links instead of « invent your own code ».** Verified: the page tells referrers to hand-craft `?utm_source=parrainage&utm_campaign=<votre-code>` while nothing downstream rewards anyone (PLAN2 QX35 wires the backend). Once QX35 lands: the page's « lien personnel » section explains the real code flow (code delivered by the seller/client space), and the capture wizard preserves the referral params end-to-end (verify against the lead contract — no new field invention). **Done =** page copy matches the real mechanism; referral params verified present in the posted lead payload (test). (@lane: web-parrainage) (@after: PLAN2 QX35)

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

**B — Capture elevation (funnel research):**

**C — Proposal elevation (close-rate research):**

---

### W245–W252 — JOURNEY ↔ SITE TIE-IN: make `/devis/mon-toit` the site's one front door (2026-07-02)


---

### W253–W264 — SERVICES: the complete, findable catalogue (founder ask, 2026-07-02)


---

### W265–W279 — HOMEPAGE & SITE ELEVATION ROUND 4 (art-director critique + world-best research)


---

### W280–W289 — TRUST & PROOF ENGINE (audit: components exist, wiring + real content missing)


---

### W290–W299 — SEO / AEO / CONTENT REACH (technical audit + 2026 search research)


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

**G0 — Trilingual parity backfill (drift the sweep proved):**

**H0 — Security & privacy hardening:**

**I0 — Performance & delivery diet:**

**J0 — Template depth (produits, réalisations, villes, FAQ, MRE…):**

**K0 — B2B/C&I depth on /professionnel:**

**L0 — Referral, post-sale & the doors that don't exist:**

**M0 — Content-distribution engine (the site's side):**

**N0 — World-#1 plays (the true-#1 critic's gaps):**

**O0 — Award-tier craft (design research; every item reduced-motion-gated, zero-CLS, Lighthouse-neutral):**

**P0 — Machine-readable & governance:**

---

### WJ60–WJ94 — QUOTE JOURNEY ROUND 4: state machine, numbers integrity, proposal round 2, a11y/RTL, funnel intelligence (2026-07-02)

**A — Capture state machine (the failure paths a real Moroccan network hits):**

**B — Numbers integrity (one engine, one truth):**

**C — Proposal round 2 (pixel audit):**

**D — Journey accessibility & RTL (WCAG 2.2 findings):**

**E — Funnel intelligence (the layer above WJ55/WJ59):**

---

### WJ95–WJ107 — QUOTE JOURNEY ROUND 5: real render defects + desktop/i18n/a11y + honest "call me" wiring (founder forensic audit, 2026-07-05)

**Why.** A 6-agent read-only forensic audit found the round-1–4 journey *submits* but has real
client-visible defects (a desktop white-on-white dropdown, a map that never renders, a mobile-only
desktop layout) and several controls that look wired but aren't (a "Demander un rappel" button that
is really just a WhatsApp link). These are the **website (`apps/web`) half**; the matching ERP
receivers are **Group QW in `docs/PLAN2.md`** (cross-referenced per task). Callback wiring uses the
free path (founder decision 2026-07-05). Nothing here touches the lead-data flow's honesty rules or
adds a paid dependency.

- Note on WJ106: the orphaned `DiagnosticFormEnriched.astro` also carries an `enrichment` object (`supplyType/roofAreaM2/orientation/estimatedKwc`, `lib/enrichment.ts`) that the CRM webhook currently drops. If WJ106 REVIVES the form, ERP QW2 must add homes for those fields; if it DELETES the form, note the now-dead contract so nobody wires a receiver for it.

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

**B — Client proposal (the page that closes the sale):**

**C — 3D estimator / builder engine (shared by the website lab AND the ERP design tool):**

**D — Client-facing interactive 3D on the proposal (founder request 2026-07-01):**

*Reda: when the client opens the returned quote he must see HIS OWN HOME with the solar panels in 3D — zoom, rotate — and have everything clearly explained. Today `/proposition/[token]` shows only a static PNG (`roof_image_url`); the interactive Three.js builder (`roof-tool-pro11.ts` / `roofPro11/scene3d.ts`) already lives in `apps/web` but is only used in the private estimator. Backend unlock = PLAN2 **QJ26** exposes the sanitized `roof_layout` in the public proposal payload; these WJ tasks render + explain it on the client page. Keep the lead-form webhook contract untouched; all text FR + AR; Lighthouse 97–100, zero CLS, <3 s on a mid-range Android; reduced-motion respected.*


**E — Best-in-world journey audit gaps (2026-07-01):**

*From the same 3-axis audit (content collected / delivered / UX) as PLAN2 Group QK. These are the apps/web-only gaps that survived the dedupe against WJ1–WJ29. Cross-cutting rules unchanged: stay in `apps/web/**`, keep the lead-form/webhook contract, FR + AR, no invented numbers, Lighthouse 97–100, zero CLS, <3 s mid-range Android, reduced-motion, private routes stay private, scaffolds flagged « pending real content from Reda ».*


**F — Quote button: wire every « get a quote / get a study » CTA to the new journey (founder request 2026-07-01):**

*Reda: every « obtenir un devis » / « étude gratuite » CTA must wire DIRECTLY to the new quote-journey page — and the button should ENHANCE the (already good-looking) site, not degrade it. Audit found ALL quote/study CTAs currently point at `/contact#simulateur` (the old diagnostic form), never at the new `/devis/mon-toit` journey; they flow through a few shared components (`Header.astro`, `StickyCta.astro`, `CtaBand.astro`) + the hero in `index.astro`, so rewiring those rewires the whole site (100+ pages, FR/EN/AR). Best-practice research (Enpal/Otovo/Tesla/Sunrun/1KOMMA5° + DTC): ONE brass primary CTA repeated verbatim across header/hero/mid/footer/mobile-sticky, brass reserved exclusively for that action (others → outline/text), a reassurance strip, thumb-zone mobile sticky, AR/RTL mirroring + text-expansion. Reuse the existing `.glow` brass-on-Majorelle styling — no visual downgrade.*


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

  `applyRoofPhoto` reassigns `roofTex` without disposing the previous texture (GPU leak on every
  re-trace at a new bbox); and the `WebGLRenderer`/`panelTex` are never disposed (leak on Astro
  client-nav away). Dispose the old `roofTex` before reassigning (guard the one still on
  `deckMaterial.map`), and add a `customLayer.onRemove` that calls `renderer.dispose()`,
  `panelTex.dispose()`, `roofTex?.dispose()`, `disposeScene()`. Accept: repeated trace/clear cycles
  do not grow GPU texture count; teardown frees the renderer. File: `roof-tool-pro11.ts`.
  frame/rack/ballast `Material`s and the static `BoxGeometry`/`EdgesGeometry` are re-allocated inside
  `buildZoneMeshes`/`renderScene` on every tilt-slider drag / obstacle move / layout edit, forcing
  `MeshPhysicalMaterial` shader recompiles. Cache them once in closure scope (active + `dim` variants)
  and reuse; keep `disposeScene` correct (don't dispose the shared cache, only per-zone meshes).
  Accept: no per-drag material/geometry allocation; visuals unchanged. File: `roof-tool-pro11.ts`.
  (`estimatorBrainV2.ts`) sizes the "+10% coverage" cap off the committed TABLE yield at a hardcoded
  south aspect, while `solveLive`/`solveLivePitched` produce kWh from PVGIS — so the shown coverage %
  drifts from the intended 110%. Thread the winning config's PVGIS per-panel yield into the cap, and
  make `optimalSouthTiltDeg` aspect-aware (scan the winner's real aspect, not `0`). Accept: coverage %
  shown for the auto-optimum is ~110% of the bill at the PVGIS yield actually displayed. Files:
  `estimatorBrainV2.ts`, `estimatorBrainV7.ts`, `estimatorBrainV8.ts`, `roof-tool-pro11.ts` wiring +
  brain unit tests.
  `fineGridMatrixV6(...)` with NO `yieldFn`, scoring the whole matrix on the TABLE while the reco card
  is PVGIS-scored — a transient where the badged matrix optimum and the recommendation name different
  configs. Feed `recomputeMatrix` the same PVGIS-backed `yieldFn` used by `buildMatrix`, or route only
  through `computeMatrixPvgis`. Accept: badged matrix row == reco card config once PVGIS resolves; no
  transient disagreement on the table fallback. File: `roof-tool-pro11.ts`.
  0 panels (roof too small, or all-north pitched pan), `betterLive`/`betterPitched` fall through to
  "fewest panels wins" (arbitrary), and `solveLivePitched` reports `roofLimited:false` with
  `placedCount:0` for a north pan (self-contradictory). Return a flagged `noViableConfig` / expose
  `northFacing` and render an honest French "configuration non viable / pan orienté nord" instead of a
  fabricated winner. Accept: tiny-roof and north-pan cases show the honest message, not a 0-panel
  "winner". Files: `estimatorBrainV7.ts`, `estimatorBrainV8.ts`, `roof-tool-pro11.ts` + unit tests.
  `AbortController`, no request token, and no debounce; two quick searches (or the autorun
  `initialQuery`) race and the slower wins, flying to the wrong address. Add a `geoToken` guard +
  `AbortController` + ~300 ms debounce (mirror the existing `billTimer`). Accept: rapid searches always
  resolve to the last query. File: `roof-tool-pro11.ts`.
  (spherical shoelace cancels) and a garbage layout; `close()` only checks `< 3` vertices. Add a pure
  `isSimplePolygon(ring)` to `roof.ts` (unit-tested) and call it from `addVertex`/`close` to reject a
  crossing edge with a clear French status. Accept: a self-crossing trace is refused with a message,
  never computed. Files: `roof.ts`, `roof-tool-pro11.ts`, `tests/roof.test.ts`.
  wired only to MapLibre `dblclick` (desktop); on touch the only finish is the button, and the 240 ms
  single-click delay silently DISCARDS fast-placed corners (the `if (clickTimer) return;` guard). Add a
  `touchend` double-tap-to-finish (~300 ms) and stop dropping the queued vertex when a second tap is
  not a real dblclick. Accept: phone users can finish by double-tap and no corner is lost when tracing
  quickly. File: `roof-tool-pro11.ts`.
  in the totals but skipped by `appendOtherZones` (`!a.renderPlan`), so it vanishes from the 3D
  multi-zone view — totals and 3D disagree. Capture a `renderPlan` snapshot even at 0 panels, or have
  `appendOtherZones` fall back to drawing the bare ring from `a.vertices`. Accept: every counted zone is
  visible in 3D. File: `roof-tool-pro11.ts`.
  deleting an obstacle (or changing a config axis) while the layout editor is open calls `recalc()`
  which nulls `layoutState` but never re-enters custom layout — the hand-placed panels silently snap to
  the optimum, the panel shows a stale count, and the `+/−` disabled-state and the note go stale. When
  `layoutMode` is on, after any recompute re-enter custom layout (re-snap occupied panels to the nearest
  valid cells of the new lattice via `nearestEmptyCell`) and re-render panel/grid/note. Accept: a custom
  layout survives an obstacle edit (re-snapped, not wiped) and all readouts stay live. File:
  `roof-tool-pro11.ts`.
  up`; on a phone the only move path is the tactile grid. Add `touchstart/touchmove/touchend` handlers
  mirroring the mouse path, gated by `layoutMode`, with a dedicated `LAYOUT_GRAB_PX` (don't overload the
  obstacle `OBSTACLE_TAP_PX`). Accept: a panel can be dragged to a valid cell on touch. File:
  `roof-tool-pro11.ts`.
  fire `clampDim` on every `input`, rewriting "0." / a leading-zero "0.7" to 0.5 mid-keystroke and
  recalc-ing the scene. Clamp on `change`/`blur` (or skip while focused); keep the commit clamp. Accept:
  typing intermediate values no longer snaps the obstacle or fights the user. Files: `roof-tool-pro11.ts`,
  `obstacles.ts`.
  `productionHourly()` returns the typical day of the W50-selected month and `savingsFromHourly` does
  `selfDaily × 365`, so flipping the production month toggle silently changes the headline annual
  savings (Dec understates, Jul overstates). Add `annualSelfConsumptionKwh(scaled, consCurve)` that sums
  `selfConsumptionDailyKwh(consCurve, typicalDayByMonth[m]) × daysInMonth[m]` over 12 months, and route
  annual savings + battery through it; keep the day graph month-aware for display only. Accept: annual
  savings is invariant to the month toggle and equals the 12-month integral. Files:
  `applianceConsumption.ts`, `roof-tool-pro11.ts` + tests.
  one-way ratchet (adding an "en plus" appliance latches `neededAuto=false`, so deleting it never
  shrinks panels/battery); and "Recaler sur ma facture" rescales to bare `billDailyKwh()`, erasing
  legitimate "en plus" energy and unable to restore the appliance-composed shape. Re-derive the
  consumption-driven need each render (`max(billNeeded, consDrivenNeeded)`), fix Recaler to target
  `billDailyKwh + Σ onTop`, and add a "Réinitialiser la courbe" that clears `consHandEdited` and rebuilds
  baseline+appliances. Accept: removing an appliance shrinks the system; Recaler keeps onTop energy; the
  computed shape is restorable. File: `roof-tool-pro11.ts`.
  hardcoded slot windows (`13–23`, `11–15`) ignoring the entered hours, so `distributeAppliance` smears
  a "3 h" load over 10 h (wrong self-consumption shape); and battery sizing, fed a single month's
  production vs a flat-average load, flips between months / returns 0. Set the slot end-hour from the
  entered hours, and size the battery from the annual evening deficit (12-month), not one month. Accept:
  the AC/EV load lands in the right hours; battery count is stable across the month toggle. Files:
  `roof-tool-pro11.ts`, `applianceConsumption.ts` + tests.
  `lf-orient = 'sud'` unconditionally, dropping Est-Ouest (flat) and every pitched face
  (Sud-Est/Sud-Ouest/Est/Ouest). Derive the `enrichment.ORIENTATIONS` id from the winning family/azimuth
  (flat) or `facingAzimuthDeg` (pitched: 180→sud, 135→sud-est, 225→sud-ouest, 90→est, 270→ouest).
  Accept: the prefilled orientation matches the chosen config; still no lead POST from the preview.
  Files: `roof-tool-pro11.ts` + a runtime test.
  étude sur WhatsApp" with a WhatsApp icon but performs NO WhatsApp action (it only prefills and scrolls
  to the diagnostic, which is where the real WhatsApp step lives). Rename it to an honest "Continuer vers
  le diagnostic →" (drop/soften the WhatsApp framing on the preview button). Add `aria-live="polite"` to
  the recommendation `<dl>`, `#rp9-prod-headline`/`#rp9-prod-sub`, and the `#rp9-areas-window` totals so
  the headline numbers are announced to screen readers. Accept: label matches behavior; results announce.
  File: `toiture-3d-pro-11.astro`.

**TIER 2 — COMPLETIONS (needed functions — "complete it with needed function"):**

  `azimuth − 45°` with an arbitrary elevation, so the rendered shadows bear no relation to a real time
  and never prove the anti-shading row pitch the layout is built on. Drive the sun from a real
  solar-position function of the site latitude + a user hour/season control (reuse
  `SOLAR_DECLINATION_DEG`/winter-solstice `designSunElevation` from `roofPro2.ts`); show a worst-case
  (winter noon) inter-row shadow so the spacing reads. Accept: shadows track the chosen hour and the
  rows visibly clear each other at design elevation. Files: `roof-tool-pro11.ts`, `roofPro2.ts`,
  `SOLAR_3D_PRO2_NOTES.md`.
  no picking; the layout editor only works via the 2D grid. Add an `instanceColor` buffer + raycast pick
  to highlight a panel on hover and toggle/remove it directly in the 3D view (desktop click + touch
  long-press), reusing the existing `layoutState`/`occupiedSet`. Accept: clicking a panel in 3D selects/
  removes it and the readouts recompute. File: `roof-tool-pro11.ts`.
  a GPU context loss (mobile background/foreground) blanks the 3D permanently. Add handlers that
  `preventDefault` the loss and rebuild the scene on restore. Accept: backgrounding/restoring the tab
  recovers the 3D. File: `roof-tool-pro11.ts`.
  gable/hip walls, reading as a tilted lid floating over a building. Build simple gable end-walls so a
  pitched roof reads as a roof. Accept: pitched mode shows a closed roof volume, not a floating plane.
  File: `roof-tool-pro11.ts`.
  roof. Add MapLibre's built-in `GeolocateControl` (no new dependency) → `flyTo` zoom 19 on geolocate.
  Accept: the control appears and centres on the device location. File: `roof-tool-pro11.ts`.
  (only "Effacer" restarts), unlike the fully-draggable obstacles. Generalize the obstacle-drag
  machinery to the `rp9-pts` source (drag a corner → update `vertices[i]` → `recalc`) and add an
  "Annuler le dernier point" control during tracing. Accept: a placed corner can be dragged and the last
  point undone. File: `roof-tool-pro11.ts`.
  Switch to `limit=5`, render a dropdown bound to the address field, and `flyTo` only on selection
  (reuses the same MapTiler endpoint, no new key). Accept: typing shows up to 5 Morocco suggestions;
  selecting one flies there. File: `roof-tool-pro11.ts`.
  year-1 production forever; `kwc = count × 0.72` is raw DC with no inverter clip, overstating dense
  E-W tents; the live cards hardcode a literal `× 0.05` bifacial gain instead of the `BIFACIAL_GAIN_*`
  constants. Add `ANNUAL_DEGRADATION` + `DC_AC_RATIO`/`INVERTER_KW` to `estimatorBrainV2.ts`, surface a
  Year-1 / Year-25 savings band, apply the AC clip in the kWh eval, and use the bifacial constants in
  `paintCard`. Accept: an honest 25-yr band shows; E-W kWh respects the AC cap; bifacial line uses the
  flat/tilted constants. Files: `estimatorBrainV2.ts`, `roof-tool-pro11.ts` + tests.
  flat daily average while production is strongly seasonal. Add a summer/winter split
  (`ete_differente`-style toggle) and a per-month autoconsommation mini-chart driven by
  `typicalDayByMonth`. Accept: a seasonal consumption split feeds the 12-month integral and a monthly
  self-consumption chart renders. Files: `applianceConsumption.ts`, `roof-tool-pro11.ts`.
  payback. Add `BATTERY_KWH_USABLE` + a flagged indicative cost param and surface an indicative payback
  next to the recommended battery count (clearly "estimation, pas un devis"). Accept: a payback range
  shows, capped to honest avoided-cost. Files: `applianceConsumption.ts`, `roof-tool-pro11.ts`,
  `APPLIANCES_NOTES.md`.

**TIER 3 — TEST COVERAGE (lock the fixes in):**

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

  `FAQPage`. Add an **Organization/LocalBusiness** block on the homepage using the real business
  name, the phone already on the site, and the real address from the contact/footer — invent nothing,
  omit any field with no real value; set `areaServed` to the cities the site already serves; include
  `geo`/`openingHours` ONLY if real values exist on the site. Add **Service** schema on the service
  pages and a **BreadcrumbList** matching the existing nav. Leave `sameAs` OUT until real social
  profiles exist. Accept: homepage carries valid LocalBusiness JSON-LD; service pages carry Service +
  BreadcrumbList; `/faq` still the only FAQPage; no fabricated fields. Files: `apps/web/**`.
  meta description**, a **self-referencing canonical**, and a complete **Open Graph + Twitter Card**
  set (`og:title`, `og:description`, `og:url`, `og:type`, `og:locale = fr_MA`, `twitter:card`) with a
  **real `og:image` from an existing asset**. Fix pages missing these; leave good ones alone. Accept:
  each public route has exactly one canonical (self-referencing) and a complete OG/Twitter set with a
  real image. Files: `apps/web/**` (head/layout components).
  private estimator preview routes and any `noindex` page are excluded. Safety line: the latest
  `toiture-3d-pro-*` route must NEVER enter the sitemap or nav. Accept: all public pages present, all
  `/preview/*` + noindex pages absent. Files: `apps/web/astro.config.mjs` (sitemap filter).
  disallows the private estimator path as defense-in-depth alongside `noindex`. Accept: robots.txt
  cites the sitemap, allows crawlers, disallows the private estimator path. Files: `apps/web/**`
  (`robots.txt` / its generator).
  parked. Accept: every public route renders `lang="fr"`. Files: `apps/web/**` (root layout).
  one `<h1>` per page with a sane H2/H3 order. Accept: no content image without alt; exactly one h1
  per public page; heading order is sane. Files: `apps/web/**`.
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

  `facingAzimuthDeg`, but a newly-added pitched zone defaults to 180 (south), so two connected pans both tilt
  south. Add a PURE, unit-tested helper (new `apps/web/src/lib/roofAdjacency.ts`) that, given the traced rings
  (lng/lat) of the zones, finds the SHARED/closest edge between two adjacent zones and infers a coherent
  `facingAzimuthDeg` for a pitched zone relative to its neighbour: a two-pan **gable** → the pans face AWAY from
  the shared ridge (opposite azimuths, normal to the shared edge); a **continuation / mono-pente** → the same
  down-slope direction. Return `{ facingAzimuthDeg, connected: boolean, sharedEdge }` plus a confidence so the
  caller falls back to south when no edge is shared. No DOM/Three/map deps. Accept: gable + mono-pente fixtures
  infer the right opposite/equal facings; disjoint zones report `connected:false` and leave the facing to the user.
  Files: `apps/web/src/lib/roofAdjacency.ts`, `apps/web/tests/roofAdjacency.test.ts`.
  `roof-tool-pro11.ts`: when a pitched zone's trace closes (or `+ Ajouter une zone` makes one adjacent to an
  existing pan), set its `facingAzimuthDeg` from the inferred value instead of the hardcoded 180 default — so
  connected pans auto-orient to meet at the ridge. Keep the existing "Face du pan" buttons (`data-facing`) + the
  fine azimuth as a **manual override that wins** and is **per-zone** (selecting a zone shows/edits ITS facing;
  the override persists in the area record via the existing `snapshotActiveAreaGeometry`/restore path), and show a
  one-line note when the facing was auto-inferred vs hand-set. Accept: adding a connected pitched pan auto-faces
  it coherently; the user can override any zone's facing and switching zones reflects the right value. Files:
  `roof-tool-pro11.ts`, `toiture-3d-pro-11.astro` (note/control wiring), `roofPro11/zones.ts` if needed.
  other zones are drawn from their own `renderPlan`, each deck + gable skirt referenced to its OWN eave
  (`eaveUpSlopeCoord`), so two connected pans float as separate tilted lids ("each tilted to one side"). Use the
  W105 adjacency to reference adjacent pitched pans to a COMMON ridge line at the shared edge (matched ridge
  height, eave on the outer edges) so they read as one connected roof; flat zones and disjoint zones unchanged.
  Accept: two connected pitched zones render as a single coherent gable/slope meeting at the ridge, not two
  independent lids. Files: `roofPro11/scene3d.ts`, `roof-tool-pro11.ts` wiring.
  to `packConfig`/`packCells` (`estimatorBrainV2.ts`) and the pitched packers (`estimatorBrainV6/V7/V8.ts` as
  wired) so a panel is retained when its footprint stays within `setbackM` of the edge OR extends at most
  `overhangM` BEYOND it (rails on-roof, panel cantilevers out) — i.e. the corner-test floor becomes `-overhangM`.
  Keep the honesty footprint bound honest: expand `usableAreaM2` by the allowed overhang ring (so the bound
  reflects the rail-supported area, never a fabricated capacity). Default `overhangM = 0` → byte-identical to
  today. Pure → unit tests. Accept: with `overhangM>0` panels may slightly exceed the ring, count rises only by
  the geometric room gained, the footprint bound still holds, and `0` is unchanged. Files: `estimatorBrainV2.ts`,
  `estimatorBrainV6/V7/V8.ts` (as wired), `roofPro2.ts` if shared, `apps/web/tests/*`.
  default 0, beside the marge/retrait control) and thread it into the solve (flat + pitched) so panels can extend
  past the eave/rake — most useful on tilted roofs. Render the overhanging panels correctly in the 3D scene (panel
  cantilevered over the edge on its rails). Honesty: overhang changes only geometric capacity, never the
  bill-derived needed-panel cap (never overfill past the need). Accept: raising the débord lets a few more panels
  place at the edges and they render hanging over the eave; the bill cap and the savings ceiling are unchanged.
  Files: `toiture-3d-pro-11.astro`, `roof-tool-pro11.ts`, `roofPro11/scene3d.ts`, `roofPro11/optimizer.ts` /
  `roofPro11/obstaclesUi.ts` wiring as needed.
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

  minimal public route (e.g. `/devis/mon-toit`) that reuses roofPro11's MapTiler address
  search + satellite map, lets the client **drop a pin on their roof** (drawing the
  outline is OPTIONAL, not required), and enter contact + bill, then submits the
  pin (+ optional outline) + contact to the backend (Q2), creating a Lead. Add a
  **`captureOnly` flag** to `initRoofToolPro8` that boots map + geocoder + pin/trace ONLY
  and never instantiates the optimizer/scene-panels/production UI. **Done =** the client
  can pin + submit on phone & desktop; no panel/optimizer/production UI ever appears; the
  pin reaches the backend. Files: new `apps/web/src/pages/devis/mon-toit.astro`,
  `roof-tool-pro11.ts` (captureOnly branch), reuse `roofPro11/mapDraw.ts`.

  the tool state (`AreaRecord[]`, and the lighter pin/outline) and extend
  `initRoofToolPro8` boot to **hydrate from the backend** via a token URL param
  (`?lead=<token>` for the client's pin, `?devis=<id>` for a saved layout), fetching from
  the Q1/Q2 endpoints through a small Astro API proxy. **Done =** a saved pin/outline (and
  a saved finalized layout) reload into the tool identically; round-trip vitest.
  Files: `roofPro11/prefill.ts` (load fns), `roof-tool-pro11.ts` (boot hydration),
  `apps/web/src/pages/api/roof-layout.ts` (proxy).

  internal/gated route that boots the FULL tool **hydrated with the client's pin** (W113);
  Meriem draws the outline if the client didn't, runs the existing auto-fill/optimizer,
  edits, then a **"Valider & générer le devis"** action serializes the finalized layout +
  kWc/count/production and POSTs it to the backend (Q1) and triggers Devis creation (Q3).
  **Done =** open a client pin → draw/autofill → finalize → a Devis is created and the
  layout saved. Files: `apps/web/src/pages/internal/devis-design.astro` (or reuse the
  preview route gated), `roof-tool-pro11.ts` (finalize action), api proxy.

  (`roofPro11/scene3d.ts`) to capture the finished roof-with-panels render and upload it
  to the backend (Q4) on finalize (W114). **Done =** finalizing produces + stores a clean
  PNG of the 3D roof; vitest/asserts the data-URL is produced. Files:
  `roofPro11/scene3d.ts` (snapshot fn), W114 finalize wiring.

  mobile-first **public** route (e.g. `/proposition/<token>`) that fetches the quote data
  (Q6) and renders the proposal as a beautiful web page — NOT just a PDF: a hero with the
  roof render, the facture **avant → après** + couverture %, the two options, the
  equipment, the garanties, and a **sticky "Signer" CTA**. Mirrors the v2 PDF design
  language (navy/gold, DM Serif/DM Sans). **Done =** the token link renders the full
  proposal responsively on phone + desktop; Lighthouse mobile ≥ 90. Files: new
  `apps/web/src/pages/proposition/[token].astro` + components + the Q6 fetch.

  an option, type name + check "Bon pour accord" → POST to Q7 → success state ("Devis
  accepté ✓"), with the signed PDF offered as a download. **Done =** signing flips the
  Devis to *accepté* and shows confirmation; invalid/expired token handled. Files:
  `proposition/[token].astro` signature component, `apps/web/src/pages/api/` proxy.

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

  page following the existing `/guides/*` pattern (Layout, Breadcrumb, `Article` JSON-LD, CtaBand,
  StickyCta). Explains the sizing METHOD from the ONEE/Lydec bill → annual kWh → kWc → panel count
  (m²/panel geometry, ~1,7–2 m²/panel are general facts), the high-Morocco-irradiation note kept
  qualitative, and routes to the diagnostic. No new price/kWh figure (method only; any Morocco
  kWh/kWc from `CONTENT_SEO_NOTES.md` §3, cited). Accept: clean Article page, single canonical, no invented number,
  internal-linked, listed by W129. File: `apps/web/src/pages/guides/combien-de-panneaux-pour-ma-maison.astro`.

  New guide complementing the existing `onduleur-hybride-ou-reseau` guide: when each system type
  fits (grid-tied = best ROI for ONEE-connected urban homes, off-grid = remote/no-grid, hybrid =
  backup), and the safety fact that a standard grid-tied system disconnects in a blackout
  (anti-îlotage) so backup needs a hybrid + battery. `Article` JSON-LD, no invented number. Accept:
  as W121. File: `apps/web/src/pages/guides/on-grid-off-grid-ou-hybride.astro`.

  the strong local differentiator: dust/sand cleaning cadence, rain self-cleaning, heat de-rating
  (~0,3–0,5 %/°C above 25 °C — general fact), lifespan & degradation tied to the published warranty
  (84,8 % à 25 ans, ~0,5 %/an). `Article` JSON-LD. Accept: as W121. File:
  `apps/web/src/pages/guides/entretien-et-duree-de-vie-des-panneaux.astro`.

  marocain ».** New guide: plein sud optimal, E/O ne perd que ~10–15 %, inclinaison ≈ latitude
  (~30°), impact disproportionné de l'ombre sur une chaîne (cheminée, mur voisin, palmier) et la
  mitigation (optimiseurs/micro-onduleurs). General facts only. `Article` JSON-LD. Accept: as W121.
  File: `apps/web/src/pages/guides/orientation-inclinaison-ombrage.astro`.

  New equipment-choice guide: mono (rendement 19–22 %, meilleur sous la chaleur, moins de surface)
  vs poly; onduleur string (moins cher, une chaîne pénalisée par l'ombre) vs micro/optimiseurs
  (suivi par panneau). General facts; tie equipment names only to what `/équipement` already
  publishes. `Article` JSON-LD. Accept: as W121. File:
  `apps/web/src/pages/guides/monocristallin-ou-polycristallin.astro`.

  battery-chemistry guide complementing the existing `faut-il-des-batteries`: LFP wins on durée de
  vie (3 000–6 000 cycles / 10–15 ans vs 3–5 ans plomb), profondeur de décharge utile (~90 % vs
  ~50 %), rendement et tolérance à la chaleur (atout au Maroc), and LFP safety vs NMC. Anchor brand
  claims on the published Dyness LFP / 10-ans warranty only; no invented price. `Article` JSON-LD.
  Accept: as W121. File: `apps/web/src/pages/guides/batterie-lithium-ou-gel.astro`.

  New battery-sizing guide: tiers (secours seul ~5–10 kWh, autoconsommation du soir ~10–20 kWh,
  quasi-autonomie 20 kWh+), usable-vs-nameplate kWh (DoD), and the Morocco economics — with export
  capped at 20 % and bought back below retail (loi 82-21, live 9 juin 2026), self-shifting a kWh to
  the evening beats exporting it; order of value = consommer en journée → stocker pour le soir →
  exporter les 20 %. Method only; client kWh from the bill stays qualitative. `Article` JSON-LD.
  Accept: as W121. File: `apps/web/src/pages/guides/quelle-taille-de-batterie.astro`.

  batterie ».** New guide: backup ≠ off-grid (the key myth-buster), EPS/secours circuits on a
  Deye/Huawei hybrid, switchover behaviour, and why a standard grid-tie dies in an outage. General
  facts + published brand names only. `Article` JSON-LD. Accept: as W121. File:
  `apps/web/src/pages/guides/electricite-pendant-les-coupures.astro`.

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

  Add a question-led content section answering the top battery queries (do I need one, lifespan,
  sizing tiers, backup-during-outage, store-vs-sell Morocco angle) using the `Faq` component with
  **`schema={false}`** (so `/faq` stays the single `FAQPage` owner), plus internal links to the new
  battery guides (W126–W128) and `/garanties`. Reuse published facts only; no invented price. Live
  lead form untouched. Accept: richer page, still one canonical, no second `FAQPage`, no fabricated
  number; `/en` + `/ar` mirrors left for the FR-first follow-up. File:
  `apps/web/src/pages/batteries-stockage.astro`.

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

  Markdown post using `CONTENT_SEO_NOTES.md` §5: turnkey **fourchettes indicatives** by size
  (3 kWc ~28–42 k, 5 kWc ~45–65 k, 10 kWc ~85–120 k MAD) and **~10 000–14 000 DH/kWc** turnkey —
  explicitly debunk the "4 700 DH/kWc" anchor as kit-only; equipment ranges, roof surcharges, the
  battery add-on (+22–60 k), and the **TVA nuance** (panneaux nus exonérés sans déduction vs pose
  clé-en-main à 20 % avec déduction; onduleurs droits de douane 17,5 %→2,5 %). Every figure labelled
  « indicatif 2026 » with its source; Taqinor's real quote → CTA to the diagnostic, not a hard price.
  Cross-link the sizing guide (W121) + ROI post (W134). Accept: dated post renders with cited ranges,
  no false precision, `BlogPosting` schema. File: `apps/web/src/content/blog/prix-installation-solaire-maroc-2026.md`.

  Uses `CONTENT_SEO_NOTES.md` §3+§2: the **kWh/kWc/yr by city** table (Casablanca 1 500–1 600,
  Marrakech ~1 779, Ouarzazate ~1 850–1 950, etc., cited PVGIS/Solargis), the **"sélective" tranche
  mechanism** (above 150 kWh/mo you pay the high marginal rate on everything — what solar removes),
  and the **5–7 yr payback** consensus. Use the locked ONEE grid from `CONTENT_SEO_NOTES.md` §2
  (date-stamped); if a fresher rate is needed the task locks it from the ONEE/distributor tariff
  source (W140), else publishes the date-stamped range. Cross-link the cost pillar (W133) + loi
  82-21 post (W135). Accept: cited
  city/yield table + payback, freshness-flagged tariffs. File:
  `apps/web/src/content/blog/rentabilite-solaire-par-ville-maroc.md`.

  20 %, rachat 0,18–0,21 DH) ».** Regulatory deep-dive from `CONTENT_SEO_NOTES.md` §1: the three
  regimes + thresholds (≤11 kW déclaration / 11 kW–5 MW accord / >5 MW autorisation), the **9 June
  2026** entry into force, the **20 % surplus cap**, the **net-billing (not net-metering)** fact and
  the **0,18–0,21 DH buyback ≪ retail** consequence (self-consumption is where the value is). Penalties
  + Article 33 18-month window included, locked from the Bulletin Officiel / decree text by W140
  (or stated qualitatively if a primary article reference can't be reached — never a founder ask). Complements the existing `/guides/loi-82-21-expliquee` (this one is dated + numeric).
  Accept: accurate cited regulatory post with the honest self-consumption conclusion. File:
  `apps/web/src/content/blog/loi-82-21-autoproduction-2026.md`.

  Maroc ? »** Economics piece from `CONTENT_SEO_NOTES.md` §6: the **cost-per-100 km** comparison —
  petrol ~93 MAD vs EV-on-grid ~23 MAD (¼) vs EV-on-solar ~0–13 MAD — **with the assumptions stated
  inline** (petrol 6,5 L/100 km, essence 14,27 MAD/L mid-Jun-2026, EV 15 kWh/100 km +10 %, grid
  ~1,40 DH/kWh marginal), the **panels-per-EV (~2–4 × 550 W)** rule, and **7 kW monophasé vs 11/22 kW
  triphasé**. Fuel price date-stamped + flagged biweekly. This is the dated companion to the W120 EV
  service page (link both ways). Accept: cited, assumption-transparent EV-vs-petrol economics. File:
  `apps/web/src/content/blog/recharger-voiture-electrique-solaire-cout-maroc.md`.

  Maroc ».** From `CONTENT_SEO_NOTES.md` §1+§7: with export capped at 20 % and bought back at
  0,18–0,21 DH while you buy at 0,90–1,66 DH, a **stored-and-self-used kWh beats an exported one**;
  the **order of value** (consommer en journée → stocker le soir → exporter les 20 %), generic LFP
  **~3 000–4 000 DH/kWh** (LOCK-FIRST; the 12 400 DH/kWh outlier explicitly excluded), battery
  payback +1–3 yr. Cross-link battery sizing guide (W127) + Dyness post (W138). Accept: the Morocco
  store-vs-sell economics, honestly framed, cited ranges. File:
  `apps/web/src/content/blog/batterie-stocker-ou-revendre-maroc.md`.

  secours ».** Product/spec deep-dive from `CONTENT_SEO_NOTES.md` §7: the **Dyness LFP lineup** (B4850
  2,4 kWh, PowerDepot H5B 5,12 kWh w/ built-in heating, Tower T7/T10/T14, PowerBrick 14,34 kWh — LFP,
  ≥6 000 cycles, 10-yr/70 % warranty) and the **backup differentiator** — **Deye SG-series near-seamless
  ~4–10 ms UPS, no extra box, 48 V LFP, 6 TOU windows** vs **Huawei SUN2000 + Backup Box (<3 s
  changeover, three-phase M0 = no backup)** — plus the LFP lifespan/heat facts (10–15 yr, +10 °C ≈
  halves life, never charge <0 °C). Lock the spec conflicts (efficiency %, H5B 7-vs-10-yr) from the
  official Dyness datasheets via W140; publish what's locked, omit what isn't — no founder ask.
  Complements the chemistry guide (W126). Accept: accurate cited product/backup post. File:
  `apps/web/src/content/blog/batterie-lfp-dyness-deye-huawei.md`.

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

  listing every product from the W141 manifest grouped by catégorie (Panneaux,
  Onduleurs réseau, Onduleurs hybrides, Batteries, Accessoires), each card showing
  marque/modèle + key specs + a "Fiche technique (PDF) ›" download and a link to its
  detail page (W143). Brand-filterable. Mirrors the site's navy/gold + DM Serif/DM
  Sans language. This IS the destination the quote engine already links to
  (`taqinor.ma/produits`). **Done =** `/produits` renders the full grid responsively
  (Lighthouse mobile ≥ 90); each card downloads the right PDF. Files: new
  `apps/web/src/pages/produits/index.astro` + a card component, reads `fiches.ts`.

  from the W141 manifest (`getStaticPaths`) for each slug: hero (marque/modèle/
  catégorie), a clean key-spec table, the embedded/downloadable datasheet, the
  TAQINOR garanties for that family, and a "Demander un devis" CTA. Add JSON-LD
  `Product` structured data (keep `/faq` the sole FAQPage owner — see W98). **Done =**
  every slug renders with specs + PDF + valid Product JSON-LD; included in the
  sitemap; vitest covers one panel + one inverter slug. Files: new
  `apps/web/src/pages/produits/[slug].astro`, reuse SEO head partial.

  the client web proposal (W116), make each equipment line link to its
  `/produits/<slug>` page (match by the same slug map above; unmatched lines stay
  plain text). Add "Produits / Fiches techniques" to the site nav + footer so the
  library is discoverable. **Done =** proposal equipment rows deep-link to the right
  fiche; nav/footer expose `/produits`; vitest asserts the slug map resolves the
  catalogue's panel/inverter/battery names. Files: `proposition/[token].astro`
  (W116), nav/footer components, shared slug map in `fiches.ts`.

  `/produits/<slug>` are in the sitemap (W100), have unique titles/descriptions
  (W99), and that the PDFs are crawlable but not duplicated as canonical pages.
  **Done =** sitemap includes the library; per-page head is unique; Vitest SEO
  invariants (W104) extended to cover `/produits`. Files: sitemap config,
  `produits/*` heads, SEO tests.

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

  now runs one flat navy tone top-to-bottom; the lit final act was removed, so the
  scroll never "arrives." Bring back an illuminated diagnostic act (or a dramatically
  brighter glass-lifted card on a luminous gradient) and wire up the unused
  `.seam-lumiere`. Files: `apps/web/src/components/DiagnosticForm.astro`,
  `apps/web/src/styles/global.css`.
  étude sur WhatsApp", give the button a persistent golden halo (the `.glow` resting
  state barely glows today) and a larger size/weight so it's unmistakably the focal
  point. Files: `apps/web/src/pages/index.astro`, `apps/web/src/styles/global.css`.
  over the cinematic hero as mid-page, with zero scroll JS. Start transparent/borderless
  over the hero → solid + backdrop-blur + condensed height + logo step-down past ~80px
  (reuse the rAF pattern in `StickyCta.astro`). Files: `apps/web/src/components/Header.astro`.
  exists; every link looks identical. Compute the current section from `rootPath` and
  render a brass underline / text on the active item. Files: `apps/web/src/components/Header.astro`.
  border — the weakest element on the site. Add a brand block + phone/WhatsApp CTA buttons,
  a golden hairline/seam top edge, and real column hierarchy. Files: `apps/web/src/components/Footer.astro`.
  (`DSC_0612.JPG`, Nikon 6016×4000) inside a zip; generated 4:5 face-framed AVIF+WebP derivatives
  at 640/480 into `public/photos/fondateur-portrait-*`, set `FOUNDER_PHOTO='fondateur-portrait'`,
  and recorded provenance as a `PHOTOS` entry in `process-photos.mjs`. The doctor-engineer trust
  section now renders the real portrait + "Reda Kasri" caption instead of the text fallback.)*
  Files: `apps/web/src/components/FounderPortrait.astro`, `apps/web/scripts/process-photos.mjs`,
  `apps/web/public/photos/fondateur-portrait-*`.

**— Homepage & hero —**

  darkening) so the golden headline always reads over busy photos. Files: `apps/web/src/pages/index.astro`.
  on tall screens; add `media="(orientation: portrait)"` with a vertical crop. Files:
  `apps/web/src/pages/index.astro`, `apps/web/src/pages/realisations/[slug].astro`, `apps/web/src/components/Picture.astro`.
  one golden `text-4xl` with three plain white `text-xl`). Files: `apps/web/src/pages/index.astro`.
  blur, a top-edge highlight, and a warm brass hover. Files: `apps/web/src/styles/global.css`.
  hairlines with occasional gradient/glow transitions. Files: `apps/web/src/pages/index.astro`,
  `apps/web/src/styles/global.css`.
  down the homepage → wallpaper). Files: `apps/web/src/pages/index.astro`.
  admin bar above the hero. Files: `apps/web/src/components/Article33Ribbon.astro`.
  edge). Files: `apps/web/src/pages/index.astro`.
  baseline glow). Files: `apps/web/src/pages/index.astro`.

**— Navigation chrome —**

  shadow, brass top accent). Files: `apps/web/src/components/Header.astro`.
  existing phone SVG, move the language switcher inside it, and add
  `max-h-[calc(100svh-3.5rem)] overflow-y-auto overscroll-contain`. Files: `apps/web/src/components/Header.astro`.
  palette; add the glow) and add `env(safe-area-inset-bottom)` padding so notched iPhones don't
  bury it. Files: `apps/web/src/components/StickyCta.astro`.
  Files: `apps/web/src/components/Breadcrumb.astro`.
  Files: `apps/web/src/components/LanguageSwitcher.astro`.
  invisible). *(Asset available 2026-06-21: official TAQINOR logo pack — main/inverted/monochrome
  SVGs — at `apps/web/public/brand/`; use it instead of the hand-coded inline mark if it reads
  better.)* Files: `apps/web/src/components/Logo.astro`, `apps/web/src/components/ZelligeDivider.astro`,
  `apps/web/public/brand/`.

**— Design system & consistency —**

  `.v2-body`); 519 ad-hoc `text-*` uses across 40 pages drive drift. Files: `apps/web/src/styles/global.css` + sweep.
  engine** (they bypass it and feel like a different site). Files: `apps/web/src/pages/produits/index.astro`,
  `apps/web/src/pages/produits/[slug].astro`, `politique-de-confidentialite.astro`, `mentions-legales.astro`.
  padding). Files: new `apps/web/src/components/PhotoCaption.astro` + gallery pages.
  `/55`…). Files: `apps/web/src/styles/global.css` + heroes.
  121 magic `py-*` values across 40 files. Files: `apps/web/src/styles/global.css` + sweep.
  Files: `apps/web/src/styles/global.css` + contextual-link rows site-wide.
  "salle blanche" palette-swap with its seam.** Files: `apps/web/src/styles/global.css`, light-section pages.
  `v2-section-title`. Files: those components.
  figure values. Files: `apps/web/STYLE.md` (or new doc), `apps/web/tests/`.

**— Imagery & media —**

  full-size today). Files: `apps/web/src/pages/realisations/index.astro`, `apps/web/src/pages/realisations/[slug].astro`.
  `1.02`/`1.04`/none). Files: `apps/web/src/components/VideoChantier.astro` + gallery pages.
  anti-CLS height). Files: `apps/web/src/pages/index.astro`, `apps/web/src/pages/realisations/[slug].astro`.
  center-cropped). Files: `apps/web/src/components/Picture.astro`, `apps/web/src/lib/realisations.ts`.
  add poster + explicit dims + a save-data/mobile encode). Files: `apps/web/src/components/VideoChantier.astro`.
  multipliers + grayscale→color hover). Files: `apps/web/src/lib/brands.ts`, `apps/web/src/components/BrandStrip.astro`.
  exists). Files: `apps/web/src/pages/realisations/[slug].astro`, `apps/web/src/lib/realisations.ts`.
  `apps/web/src/pages/realisations/[slug].astro`.
  "Cinéma du chantier" claim (keep the hero ungraded for LCP). Files: `apps/web/scripts/` or scoped
  `apps/web/src/styles/v3-photo-motion.css`.
- [x] W187 — **Source real brand-logo SVGs** (Canadian Solar, Huawei, Deye, Jinko, JA Solar,
  Dyness, Nexans) to replace the text word-mark fallback. These are THIRD-PARTY *manufacturer*
  logos for the partner trust-strip — distinct from Taqinor's own mark (W168). *(DONE 2026-07-11:
  re-sourced from the web across every reachable host. Reachable: `commons.wikimedia.org`,
  `upload.wikimedia.org` (also serves each Wikipedia's non-free logo store), `raw.githubusercontent.com`;
  blocked (403/000): the open web, brand sites, en.wikipedia API, jsDelivr/unpkg/iconify. Sourced
  **6 of 7 real official logos**: Huawei / Nexans / JA Solar (official SVG, Commons), Jinko (PD PNG,
  Commons), Canadian Solar (official PNG, Wikipedia EN — nominative use), Deye (PNG, Commons CC BY-SA
  4.0 — attribution in `public/brands/CREDITS.md`, identity confirmed via Wikipedia DE + Wikidata usage).
  All wired in `brands.ts` (greyscale→colour on hover; `<img>` renders SVG+PNG), verified on disk by a
  test, SVGs scanned clean. **Only Dyness** has NO reachable official asset (absent from Wikimedia /
  Wikidata / GitHub logo repos; its only sources dyness.com + brandfetch are behind the egress
  allowlist) → honest word-mark, never fabricated. To finish it, drop `public/brands/dyness.png` (or
  `.svg`) or widen the allowlist.)*
  Files: `apps/web/public/brands/`, `apps/web/src/lib/brands.ts`.

**— Forms & interactive widgets (visual-only; lead mechanics untouched) —**

  checkboxes** (the live `DiagnosticForm` lags the roof tool, which already fixed this). Files:
  `apps/web/src/components/DiagnosticForm.astro`, `DiagnosticFormEnriched.astro`, `RegimeSelector.astro`.
  4px thin). Files: `apps/web/src/components/DiagnosticForm.astro`.
  seam, value-vs-label hierarchy). Files: `apps/web/src/components/DiagnosticForm.astro`.
  swap and the result pops). Files: `DiagnosticForm.astro`, `DiagnosticFormEnriched.astro`, `RegimeSelector.astro`,
  `apps/web/src/styles/global.css` (one `@keyframes spin`).
  state nearly invisible on dark). Files: `apps/web/src/pages/preview/toiture-3d-pro-11.astro`.
  Files: `apps/web/src/components/WhatsAppMock.astro`.
  Files: `DiagnosticForm.astro`, `DiagnosticFormEnriched.astro`, `RegimeSelector.astro`.

**— Content & reading experience —**

  (guides set whole bodies at lead size; blog reinvents prose separately). Files: new shared style,
  `apps/web/src/pages/blog/[...slug].astro`, `apps/web/src/pages/guides/*.astro`.
  articles.** Files: `apps/web/src/pages/guides/index.astro`, `apps/web/src/pages/blog/index.astro`, content schema.
  the protagonist" identity carries into prose. Files: new component + guides/blog.
  component** for the duplicated internal-link chip rows. Files: shared prose style + new component + content pages.
  stop drifting. Files: `installation-solaire-[city].astro` + a short design note.

**— Motion & micro-interactions —**

  add `scroll-padding-top`. Files: `apps/web/src/styles/global.css`.
  have no hover at all). Files: `apps/web/src/styles/global.css` (`.cine-card`) + card wrappers.
  `apps/web/src/pages/index.astro`, `nos-solutions.astro`, `realisations/index.astro`.
  is static text). Files: `apps/web/src/pages/index.astro`.
  repeated across ~40 hero blocks). Files: `apps/web/src/styles/global.css` + heroes.
  (defined, zero usages). Files: `apps/web/src/styles/global.css`, `v3-photo-motion.css`.
  Files: `apps/web/src/styles/global.css`, `v2.css`, `BrandStrip.astro`, `Testimonials.astro`.

**— Shared interaction primitives —**

  links have none; some set `focus:outline-none`). Files: `apps/web/src/styles/global.css` + chrome.
  are flat `transition-colors`). Files: `Header.astro`, `CtaBand.astro`, `StickyCta.astro`.

**— Mobile & responsive —**

  (`43,48 kWc`, `60–90 %`). Files: `index.astro`, `installation-solaire-[city].astro`, `realisations/[slug].astro` (+ mirrors).
  md→lg band). Files: `apps/web/src/pages/équipement.astro` (+ `en/`/`ar/` twins).

**— RTL / Arabic —**

  SVG flipped via `rtl:-scale-x-100`). Files: `apps/web/src/pages/ar/**`.
  borders, spec-row alignment), flip the asymmetric two-column hero grids, and guard `tech-label`
  letter-spacing/uppercase off for Arabic. Files: `apps/web/src/styles/global.css`, `apps/web/src/pages/ar/**`.

**— Performance / rendering / accessibility finish —**

  metric-matched fallbacks** to kill the FOUT flash and font-swap CLS on the LCP `<h1>`. Files:
  `apps/web/src/layouts/Layout.astro`, `apps/web/src/styles/global.css`.
  the dark canvas + scrollbar/autofill) + a `::selection` brass color. Files: `apps/web/src/styles/global.css`.
  *(Shipped 2026-06-21: real brand lockup wired as `apple-touch-icon.png` (256px) + `icon-512.png`
  from the official logo pack; added `site.webmanifest` (name/theme `#070b1d`/bg + 256+512 icons) and
  the `apple-touch-icon`/`manifest` head links; `theme-color` already present; kept the lightweight
  square sun `favicon.svg` for the 16–32px browser tab because the wordmark is illegible at that size.
  Deliberate deviations from the original spec: apple-touch is 256 not 180, no `.ico` (SVG-first), and
  icons are `purpose:"any"` not maskable — the wordmark lockup has no maskable safe-zone. Refine later
  if a dedicated icon-only mark is produced.)* Files: `apps/web/public/apple-touch-icon.png`,
  `apps/web/public/icon-512.png`, `apps/web/public/site.webmanifest`, `apps/web/src/layouts/Layout.astro`.
  Files: `apps/web/src/layouts/Layout.astro`.
  `apps/web/src/styles/v2.css`, `apps/web/src/lib/countup.ts`.
  inks and brass glow. Files: `apps/web/src/styles/global.css`.

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

### 2026-07-16 — WJ117–WJ126 drain (4 modes + règle anti-concurrent) — web-only lanes
- **WJ117 (web-journey):** l'état sélectionné des 8 groupes de cartes du parcours devis est enfin VISIBLE — une règle CSS non-layered `.cine-card[aria-pressed="true"]` dans global.css (bordure brass 2px sans décalage de layout, fond teinté brass 10 %, ✓ en coin RTL-aware, label gras) bat le shorthand `.cine-card` qui écrasait l'utilitaire Tailwind layered togglé par le JS. aria-pressed était déjà câblé sur les 3 locales — zéro changement JS. Test source-level (16 assertions) en substitut des captures Playwright (apps/web n'a que vitest) ; focus-visible W209 intact.
- **WJ121 (web-journey):** la carte « Professionnel » est scindée en 🏭 Industriel et 🏪 Commercial sur les 3 locales de /devis/mon-toit (grille 2×2, stepper/libellés/sous-titres par mode). lead.ts : LEAD_MODES gagne industriel+commercial (l'alias `professionnel` reste accepté pour les sessions en vol mais n'est plus jamais émis — les sessions réhydratées migrent vers industriel) ; MAX_BILL_BY_MODE : les deux nouveaux modes reprennent le plafond professionnel existant (1 M MAD, aucun chiffre inventé) ; qualification 1000 MAD et billRange identiques. TELEMETRY_MODES suit son contrat de miroir. Test bout-en-bout : le webhook CRM reçoit `mode: commercial` / `mode: industriel` verbatim.
- **WJ118 (web-proposal):** la 3D de la page client /proposition/<token> drape enfin la PHOTO SATELLITE du vrai toit — `[token].astro` appelle `buildPublicRoofImageSpec` avec le contour `roof_layout.zones[].vertices` (exposé par le backend depuis QJ26) converti [lng,lat]→[lat,lng] via le nouvel export défensif `roofLayoutOutlineLatLng` (proposition.ts : layout null / zones non-array / points malformés / coords non-finies tous gérés), et passe `roofImage` à `createRoofViewer` (contrat texture+attribution déjà présent depuis WJ25/27). Le fond bascule en ciel clair (`.roof3d-stage--sky`) uniquement quand une photo drape réellement ; sans clé MAPTILER/MAPBOX ou sans contour, rendu actuel byte-identique. Commentaires périmés « backend n'expose pas roof_layout » supprimés. Test du convertisseur (anneau normal/multi-zone/vide/malformé) + assertions source.
- **WJ119 (web-proposal):** la courbe journalière de conso cesse d'être la même double-gaussienne pour une villa et une usine — remplacée par la silhouette marocaine soirée-dominante (BASELINE_SHAPE portée d'applianceConsumption.ts, pic 19h-21h) et déclinée PAR MODE via `resolveProposalCurveMode(inst_type)` : industriel (régimes 1x8/2x8/3x8), commercial (archétype journée générique — QX44 pas construit, repli honnête), agricole (fenêtre de pompage jour, nulle la nuit). Variantes été (clim 13h-18h) et Ramadan (jour −35 %, pic iftar, bosse suhoor) en toggle discret pour résidentiel/commercial. Libellé honnête « profil type au Maroc, ajusté à votre facture » (jamais « mesuré »). Tests de forme (pic du soir dominant résidentiel, 3x8 plat, nuit-zéro agricole, déplacement de part été).
- **WJ120 (web-proposal):** nouveau bloc « et avec N batteries ? » sur /proposition/<token> (résidentiel + commercial uniquement — jamais agricole/pompage). Moteur horaire glouton PUR et testable (`lib/batterySim.ts`) : boucle 24 h jouée DEUX fois en reportant le SoC (résultats jour 2 = régime établi, évite le biais du SoC initial vide) sur courbe conso (WJ119) × courbe solaire ; direct = min(prod, conso), surplus → batterie (η one-way 0,96 ≈ round-trip 0,92 LFP, DoD 0,90), déficit ← batterie puis réseau. Capacité par unité STRICTEMENT du catalogue (BAT-DEY-5 = 5 kWh / BAT-DEY-10 = 10 kWh — commentaire d'avertissement contre la confusion avec BATTERY_KWH_PER_DAY=6, une grandeur différente). Slider 0/1/2/3 → recalcul live sans re-fetch : autoconsommation % ET autosuffisance % (deux libellés distincts, formules commentées), split kWh direct/batterie/réseau en aire empilée SVG (style SolarEdge, aucune lib), heures de secours sur CHARGES ESSENTIELLES (frigo+éclairage+box ≈200 W, ESTIMATION). Prix : ligne batterie réelle du devis si N correspond à l'offre, sinon « sur étude » — jamais un prix inventé. Tests moteur (N=0, monotonie autosuffisance↑/réseau↓, conservation d'énergie, secours ∝ N, jour2 ≠ jour1-vide).
- **WJ125 (web-journey):** RÈGLE FONDATEUR anti-concurrent appliquée — le document d'estimation détaillé ne se rend PLUS pendant la saisie publique. `computeEstimate` calcule toujours `estimateShown` en silence (envoyé au CRM via le webhook, « le commercial voit tout ») puis un drapeau `PUBLIC_ESTIMATE_GATED` fait un retour anticipé AVANT toute écriture de chiffre dans le DOM visible : `showEstimateTeaser` masque `#mt-doc`, `mt-nearest-install`, `mt-cost-of-waiting` et le bouton Imprimer, et révèle une carte TEASER verrouillée (aperçu décoratif sans chiffre + une accroche grossière mode-aware + « Recevez votre étude complète et personnalisée ») → le formulaire contact. Annonce lecteur d'écran figure-free (`GATED_ANNOUNCE`, parité a11y). Le document complet + Imprimer vivent désormais UNIQUEMENT sur /proposition/<token>. FR/EN/AR. Tests : `perceivedPerfWJ34` adapté (nouvelle réalité gatée documentée, rien affaibli), calcul/API (`captureWJ`/`wj111`/`wj112`) intacts et verts, nouveau `teaserGateWJ125` (aucun token chiffré dans le teaser sur les 3 locales, estimateShown atteint toujours le payload).
- **WJ122/WJ123 :** `[BLOCKED: attend QX51]`, **WJ124 :** `[BLOCKED: attend QX48]`, **WJ126 :** `[BLOCKED: attend QX49]` — prérequis backend PLAN2 non présents sur `main` (garde de composition : jamais de substitut backend hand-rollé dans apps/web).
- **Revue adversariale Fable (1 passe, autorisée — batch touchant la règle fondateur anti-fuite) :**
  a bloqué et fait corriger un TROU DE FUITE réel que la revue Opus et l'agent WJ125 avaient tous deux
  manqué — la scène 3D `#mt-panels3d` rendait `ceil(kWc×1000/720)` panneaux pendant le parcours public
  gaté (un concurrent les compte → kWc au sous-kWc près ; « nb panneaux » est une valeur interdite par
  la règle). Corrigé au point de contrôle unique (`updatePanels3dVisibility` force le masquage sous gate,
  3 locales) + test verrou. Findings restants (non-bloquants) → WJ127-WJ129 ci-dessus.
- **À VÉRIFIER PAR LE FONDATEUR (WJ125, hors critères Done) :** le deeplink WhatsApp (message SORTANT du visiteur vers Taqinor) préremplit encore les 2 libellés kWc + économies/an. Les zones DOM énumérées par la règle (#mt-doc, mt-nearest-install, mt-cost-of-waiting) sont toutes gatées ; le préremplissage WhatsApp est un canal de handoff (règle web « ne pas toucher au flux lead sans demander ») — laissé intact, `estimateShown` atteignant déjà le CRM par le webhook. Dire si tu veux aussi retirer ces 2 libellés du préremplissage WhatsApp public.

### 2026-07-11 — W187 real brand logos sourced from the web (founder: "search yourself") — 6/7
- **W187 (brand trust-strip):** re-attempted web sourcing instead of waiting on founder-dropped files, then pushed harder across every reachable host when the first pass got 4. Reachable: `commons.wikimedia.org`, `upload.wikimedia.org` (which ALSO serves each Wikipedia's non-free logo store — the trick that unlocked Canadian Solar), `raw.githubusercontent.com`; blocked (403/000): open web, brand sites, en.wikipedia API, jsDelivr/unpkg/iconify. Sourced **6 of 7 real official logos**: Huawei / Nexans / JA Solar (official SVG, Commons), Jinko (PD PNG, Commons), **Canadian Solar** (official PNG, Wikipedia EN non-free store via computed MD5 path — nominative use), **Deye** (PNG, Commons CC BY-SA 4.0 — attribution in new `public/brands/CREDITS.md`; identity confirmed: the file is used on Wikipedia DE's "Deye" article + Wikidata Q131827394). All wired in `brands.ts`, `<img>` renders SVG+PNG with greyscale→colour on hover, a test verifies each non-null logo is a real on-disk file, SVGs scanned clean. **Only Dyness** has NO reachable official asset (absent from Wikimedia / Wikidata / GitHub logo repos; dyness.com + brandfetch blocked by the allowlist) → honest word-mark, never fabricated; one dropped `dyness.png` finishes it. No new dependency.

### 2026-07-11 — WJ115 + WJ116 unblocked & shipped (2 parallel worktree lanes)
- **Correction of prior report:** an earlier "work on the web plan" run declared the queue empty because WEB_PLAN's blocked notes said QX34/QX35 were unbuilt. Verified against real backend code on `main` (not the stale note): both landed in the 2026-07-10 batch (PR #373) — `/api/django/ventes/suivi/<token>/` (QX34) and the parrainage webhook `handle_parrainage_signup` matching `Client.code_parrainage` (QX35). So WJ115/WJ116 were buildable and were built.
- **WJ115 (web-suivi):** new SSR page `/suivi/<token>` (`prerender=false`, `noindex`, rate-limited, 8 s SSR timeout) rendering the QX34 milestone timeline (accepté → acompte → matériel → installation → facturé) via a pure `lib/suivi.ts` (`suiviEndpoint`, `buildTimeline`, ISO-date guard so a chantier status-string in the `installation.date` field is never printed as a date). FR/AR with RTL + Western-numeral dates, honest 404/timeout/network/429 states each with a pure-link « Réessayer », WhatsApp-share worded for a SUIVI link (not « proposition »). Private: not in nav/sitemap. 23 lib+source tests.
- **WJ116 (web-parrainage):** (a) `/parrainage` (fr/en/ar) copy corrected — the referral code is NOT invented by the referrer; it is the Taqinor-assigned `Client.code_parrainage` (form `TQ-<id>`, e.g. `TQ-482`) delivered by the conseiller / espace client. An invented code matched no client under QX35, so referrers were never credited. (b) Real defect fixed: the PRIMARY funnel `/devis/mon-toit` `buildBody()` never forwarded any `utm_*`/`fbclid`, so ALL referral/UTM attribution (parrainage included) was silently dropped. It now reads the params Layout persists to `sessionStorage` (`tq_<key>`) and merges the six existing contract keys onto the POST body (additive; a submission with no params is byte-identical). fr/en/ar mirrored. Test asserts the copy change, the six wired keys, and that `validateLead` carries `utm_source`/`utm_campaign` into `lead.utm`.
- Combined: full `apps/web` vitest suite 3975/3975 green, `tsc` (src/lib) clean. No new dependency. Lead-webhook contract unchanged (additive only).

### 2026-07-10 — WJ110–WJ116 drain (round 6): 5 shipped across 3 parallel lanes, 2 blocked, one merge
- **WJ110 (web-capture):** the PRIMARY funnel endpoint `api/capture-lead.ts` (behind `/devis/mon-toit`, the site-wide CTA) now fires the Meta CAPI — it never did, so Meta was optimizing on the non-representative secondary paths only. Mirrors `simulate.ts`'s pattern exactly (background/non-blocking, log-on-failure, self-gated on `record.qualified`); no change to lead-posting, the 1000 MAD qualify logic, consent/UTM/fbclid, or the response. New vitest asserts a qualified mon-toit submission fires CAPI once and a sub-threshold one does not.
- **WJ111 (web-estimate):** `/devis/mon-toit` mode « Agricole » no longer shows a fabricated residential kWc/économie card computed from a bill (pompage is driven by HMT + débit, not a bill). It now shows a dedicated qualitative card (« Le pompage se dimensionne sur votre HMT et votre débit — un conseiller vous rappelle… »), fr/en/ar; résidentiel/professionnel untouched; capture (lead + pompe fields) unchanged. Switching mode re-renders live. Followed the site's own stricter WG11 policy and omitted the FDA%/Saquii financing lines (not published as confirmed facts on the site).
- **WJ112 (web-estimate):** the « Pour affiner la taille » accordion now actually moves the number — `ombrage` applies a documented derate (aucun 1.00 / partiel 0.92 / important 0.78, sized into the kWc before display, not cosmetically) and an exact-kWh input overrides the bill-derived need; both recompute live. Roof-age and battery-interest carry honesty notes (capture-only, no honest model to move the number). The fake 1.5–2.5 s « thinking » delay is cut to 250–450 ms (reduced-motion still 0 ms). fr/en/ar mirrored.
- **WJ113 (web-estimate):** `tariffForCity()` now resolves real reverse-geocoded free-text addresses (« Boulevard Zerktouni, Casablanca, Maroc ») via normalize (case-fold + strip diacritics) + contains-match, keeping the exact-match fast path. No tariff VALUE changed (all still equal REGIE_TARIFF today) — only the matching became honest, so per-utility grids will work correctly the day they land.
- **WJ114 (web-proposal):** `proposition/[token].astro` gains a mobile-first « décider en 10 secondes » block above the fold — client name (already shown) + the 4 canonical figures (kWc, production annuelle, Total TTC, économie/payback — reused from the existing computed values, never recomputed, zero-total-guarded) + one primary CTA (same #signer-vs-WhatsApp branching as the sticky CTA). A seller personal-note+name+photo card renders only when the ERP provides it (read defensively via new `sellerNote()`; the payload field does NOT exist yet, so today it renders nothing). AR money kept LTR/Western numerals. NOTE for Reda: the « zero-scroll » fit is device-dependent and was verified by structure/tests, not a live screenshot — eyeball it on a real proposal once one exists.
- **UNBLOCKED & SHIPPED 2026-07-11:** WJ115 (`/suivi/<token>` page) and WJ116 (parrainage real links) — their backend prerequisites PLAN2 QX34 and QX35 landed on `main` in the 2026-07-10 batch (PR #373). Both web halves are now built; see the DONE LOG. No founder action needed.
- Local gate green in the prod-parity worktree: `npm ci` clean, `tsc` clean, `astro build` green (all pages + sitemap; `/proposition/[token]` and `/devis/mon-toit` build), vitest 149/149 across the new + regression modules (captureLead, wj111/112/113, propositionFold, trustComponentsWJ35, lead, preview). No new dependency added. `/preview/*` + `/proposition/` privacy and the lead-webhook contract unchanged.

### 2026-07-05 — WJ95–109 + WC1–12 + WN1–8 drain (35 tasks): 7 parallel lanes, one merge
- **Live data-corruption fix (WJ109):** `api/proposition-track.ts` no longer posts proposal-view pings to the CRM lead-capture webhook (`LEAD_WEBHOOK_URL`) — it now routes pure telemetry (event_type/reference/token, no phone/utm/qualified) to the funnel sink (`FUNNEL_WEBHOOK_URL`, log-only when unset). A client merely OPENING their proposal can no longer overwrite their own CRM lead name. Guard test asserts the new target. Supersedes the need for ERP QW7.
- **Funnel (WJ96–108):** map-config diagnostics + pre-warm for resumed visitors (WJ96 b/c; a was already shipped); `/contact` "Demander un rappel" is now a REAL name+phone callback POST (`contactPreference=phone_ok`, additive `quickCallback` path in lib/lead.ts that honestly relaxes city/roof/bill for that door only — existing mon-toit leads byte-for-byte unchanged) with a separate WhatsApp option (WJ97); `/devis/mon-toit` real desktop layout (WJ98); exit-intent modal sets the doc `inert` (WJ102); missing funnel events wired as a delta over the WJ59 beacon — estimate_viewed/callback_requested/proposal_viewed/proposal_signed (WJ104, needs FUNNEL_WEBHOOK_URL to leave logs); concrete callback SLA + preferred window (WJ105); dead FR/AR in-page toggle removed (WJ106 — `DiagnosticFormEnriched.astro` kept, still imported by preview routes); proposal page EN/AR + a11y (WJ99 data-en + aria; WJ101 keyboard-operable signature); OTP entry step on the sign flow, inert until the backend `ESIGN_OTP_ENABLED` toggle is on (WJ108, new same-origin `api/proposition-otp.ts` proxy). Strong vitest coverage added across all.
- **Homepage/content (WC1–10, HOME lane):** WC5/WC6/WC7/WC8/WC10 verified ALREADY-PRESENT (round-2 removed the 43,48 kWc capacity monument, added the real 44,19 MWh production lead, genericized Deye-Cloud/FusionSolar monitoring prose — only explanatory code comments remain); WC9 client wording "50–100 % selon batteries/usage jour-nuit" already shipped (documented why roof.ts constants stay); WC1 mobile/RTL fixes verified in code + new guard test `wc1MobileRtlFixes.test.ts` (live-device screenshot deferred); WC3 RTL lightbox arrows; WC4 monument-overflow already handled.
- **New work:** WJ95 global `<select>` white-on-white fallback (global.css); WJ100 nav i18n — translate Blog/Fiches techniques, dedupe Espace-client label into i18n/ui.ts; WJ103 sticky-CTA RTL reposition; WN2 realisations city-count → qualitative city list; WN4 maintenance pricing/SLA "pending" hidden → contact-for-pricing; WN1 blog welcome post reframed evergreen + no coming-soon empty-state; WN3/WN7 garanties — definitive exclusions, omit the unfinished production-guarantee card, drop the false ">1-year monitoring" claim (FR/EN/AR); WN5 parrainage "en cours de finalisation" → bespoke reward; WN6 StarRating omits entirely when no real rating; WN8 V2H "à venir" dwell shortened; WC12 wrapped Latin numeric tokens in `dir="ltr"` on 9 remaining /ar content pages (high-traffic pages already done round-3).
- **Already-present / N-A:** WC11 blog dates already staggered + guides are evergreen (no date source); WJ107 homepage InstantEstimator already hands off `?bill=`/UTM to /devis/mon-toit.
- **Noted:** WC2 extended the existing W323 Lighthouse gate to report LCP/total-bytes/JS+CSS/request-count and added `chrome-launcher` as an explicit devDependency (already in the lockfile, `npm ci` verified consistent) — the actual before/after NUMBERS remain BLOCKED pending a live run/deploy (not fabricated). WJ108's OTP path depends on the backend `ESIGN_OTP_ENABLED` toggle + `proposal/<token>/otp/` endpoint (confirmed present in ventes) — inert and invisible until the founder flips the flag. FUNNEL_WEBHOOK_URL must be set (dashboard) for funnel telemetry (WJ104/WJ109) to leave logs. Local gate green: npm ci clean, tsc pass, astro build pass, vitest 2225 pass (the 3 remaining local reds are 2 flaky randomized estimator tests + 1 Windows-CRLF match on an unchanged file — all pass on CI Linux).

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
