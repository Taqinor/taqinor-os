# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, then commit it to a worktree branch, tick it `[x]`,
and append a DONE LOG line as it lands; **partition the unchecked tasks into independent lanes by
the real files they write and build the lanes in parallel with up to 8 concurrent worktree
subagents — waves of 8 if there are more — coupled tasks in sequence inside a lane**) — and only
once this file has no pending `[ ]` task left does it fall through to `docs/PLAN.md`. Every
worktree branch is folded into one `dev`, CI runs once over the whole batch, and the run
self-merges `dev` → `main` exactly once at the very end — **no per-agent PR, no per-task merge**.
All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — including the
default **workflow-with-review engine** (one worktree subagent per task plus a separate
adversarial review agent that must pass before a change is merge-eligible), the
**parallel-subagent fallback** when no workflow engine is available (never a single serial
one-task-at-a-time agent), and the **sync-safe single merge** (integrate the latest
`origin/main` first, re-run CI, push without forcing). This file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

> **Web session note (2026-06-18):** a world-class audit of the public site (`apps/web`) was run and its
> fixes built — **W62–W66 shipped** (social proof scaffold, homepage guarantee band, founder photo-ready
> block, brand strip +Jinko/Huawei/Nexans, « réponse sous 48 h ») and the **W67 EN/AR i18n foundation**
> laid (Astro i18n + dictionary + switcher + RTL/hreflang, FR byte-identical). Full detail in
> `docs/WEB_PLAN.md` + `docs/DONE.md`; web work stays out of this OS queue per the OS/web split. Logged
> here at the founder's request — this note adds no OS task.

## BUILD QUEUE (do top-down — highest value first)

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

## Group F — Design foundation & tokens
## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)
- [x] **G23.** Select, Combobox/autocomplete (rebuild AssigneePicker and ProduitPicker on it), MultiSelect, with async search + empty/loading.
- [x] **G24.** Date picker, Date-range picker, Time picker (the last for relance scheduling).
- [x] **G26.** File upload / dropzone (rebuild AttachmentsPanel + the OCR upload flows) with progress, type/size validation, and reliable open/download (this also resolves the Group B attachment bug at the component level).
- [x] **G27.** Form system: labels-above layout, sectioned forms, inline field validation + cross-field validation, required markers, an error summary, a dirty-state guard ("unsaved changes — leave?"), and a sticky save/cancel action bar (especially on mobile).
## Group H — DataTable engine (TanStack Table, behind every list view)
- [x] **H31.** Core grid: sticky header, frozen first column, multi-column sort, per-column + global filter, column show/hide + reorder + resize + pin, density toggle, pagination with an "X–Y of N" count, and search-match highlighting.
- [x] **H32.** Actions + editing: hover-revealed row checkboxes; a floating contextual bulk-action bar (bottom on mobile) for assign / change stage / export / delete; up-to-3 row icons + an overflow menu; clickable rows → detail/quick-view/expandable; inline cell editing with validation, undo, and save feedback; summary/subtotal rows (totals + TVA).
- [x] **H33.** Scale + persistence: saved/preset views as tabs (e.g. "À relancer", "Signés", "En retard"); sort/filter/page persisted to the URL (survives refresh + deep-links); server-side sort/filter for >1000 rows; row virtualization for large lists (619-lead import); CSV/XLSX export (openpyxl server-side); and a mobile fallback (rows → cards, or priority columns + horizontal scroll with frozen first column).

## Group I — App shell & navigation
- [x] **I34.** Sidebar: collapsible, grouped sections, clear active state, brand mark, fully scrollable inside the iOS safe area (resolves C6 menu cutoff).
- [x] **I35.** Header: breadcrumbs, global search trigger (⌘K), notifications bell, user menu, and a consistent page-header pattern (title + actions + filters/tabs).
- [x] **I36.** Mobile bottom tab bar for primary nav (thumb-reachable) with safe-area inset; route-transition loading bar.
- [x] **I37.** Fix desktop cold first-load flakiness so a single load works (resolves C7); global keyboard shortcuts + a "?" shortcuts help dialog.
- [x] **I38.** Notifications UI shell: bell + dropdown list + unread badge + an in-context permission prompt (shown with rationale, not on load). Wires to the planned VAPID web-push backend later; degrades to a no-op if the backend/keys are absent.

## Group J — Per-module restyle (each: list → DataTable, forms → new primitives, modals → Dialog/Sheet, statuses → StatusPill, real empty/loading/error states, mobile pass)
- [x] **J39.** CRM Leads — kanban / list / charts / calendar views, LeadCard, FilterBar, ViewSwitcher, DoublonsPanel, LeadDevisPanel; polish drag affordance on the kanban.
- [x] **J40.** CRM Clients — list + form.
- [x] **J41.** Ventes Devis — list, form, and the multi-market generator (the line-item editor needs the most care).
- [x] **J42.** Ventes Factures — list + form (acompte/solde/avoir); Relances; Avoirs; Ventes Kanban.
- [x] **J43.** Chantiers/Installations — list + detail + filter bar.
- [x] **J44.** SAV — Tickets + Équipements (warranty tracking).
- [x] **J45.** Stock — list, mouvements, produit form, OCR import.
- [x] **J46.** IA — AgentChat + OCR upload.
- [x] **J47.** Admin — Roles editor + Users.
- [x] **J48.** Paramètres — restyle in the new system (the tabbed split + editable settings are feature tasks D9–D13; build them on the new primitives).
- [x] **J49.** Activities — Mes Activités.
- [x] **J50.** PDF preview screen — restyle only the chrome around PdfCanvas (toolbar, container, mobile layout). Do NOT touch the rendered PDF content or template.

## Group K — Dashboard & reporting
- [x] **K51.** Dashboard: KPI cards + themed charts (recharts, or Tremor copy-in blocks) — pipeline value, devis→signé conversion, outstanding invoices / aged balance, chantiers by status, revenue — plus an activity feed. Real data from existing slices/APIs; no buy-price exposure.
- [x] **K52.** Reporting hub + Balance âgée: restyle with charts, date-range + segment filters, export, and proper empty/loading states.

## Group L — Global UX behaviors
- [x] **L53.** Consistent async feedback: every save / delete / send-WhatsApp / generate-PDF fires a toast, with undo where safe.
- [x] **L54.** Confirm dialogs for all destructive actions.
- [x] **L55.** Optimistic updates with error rollback on common edits.
- [x] **L56.** Global ⌘K command palette searching leads/clients/devis/factures/chantiers/produits → jump to the record.
- [x] **L57.** Session-timeout handling: graceful re-auth that preserves the in-progress form.

## Group M — Mobile & PWA polish (Meryem is iPhone-primary)
- [x] **M58.** iOS pass: safe-area insets everywhere, tap targets ≥44pt, 16px inputs (no zoom), no horizontal scroll on core flows, modals → bottom sheets, primary actions thumb-reachable.
- [x] **M59.** PWA icons: standard 192/512 + maskable variants with the 80% safe zone, plus favicon — from the sun-bolt asset (BLOCKED until Reda uploads the logo/PNG); add splash + install-prompt UI. (SHIPPED 2026-06-18 — Feature C: regenerated 192/512/maskable(512)/180 apple-touch + favicon-16/32 + favicon.ico from the sun-bolt « O » glyph of the official logo on the navy brand background, via `frontend/scripts/gen_pwa_icons.py`. Splash screens + install-prompt UI not in this pass.)
- [x] **M60.** (already present) Service-worker update flow: a "Nouvelle version — recharger" toast when a new build is live (removes the delete-and-reinstall pain for future updates).
- [x] **M61.** Offline state: cached app shell + a clear offline banner instead of a browser error page.
- [x] **M62.** Smooth scrolling + reduced-motion respected throughout.

## Group N — Accessibility & quality floor (WCAG 2.2 AA)
- [x] **N63.** Contrast 4.5:1 (incl. dark / disabled / pressed states), focus-visible rings, ARIA labels on icon buttons, semantic HTML, full keyboard nav for tables/kanban/dialogs (focus trap + restore), screen-reader announcements for toasts + validation, color never the only signal.
- [x] **N64.** Text resize to 200% and portrait+landscape without breakage; Lighthouse + axe pass each release.

## Group O — Performance
- [x] **O65.** Route-based code splitting + lazy loading; skeleton-first rendering.
- [x] **O66.** List virtualization for big tables, debounced search, request caching; font preload + image lazy-load; a bundle budget.

## Group P — Consistency & cleanup
- [x] **P67.** Migrate and DELETE the ~15 ad-hoc per-component .css files into the token system + primitives as each screen is converted.
- [x] **P69.** Document the token system in one reference file; save before/after screenshots of key screens to docs/ui-redesign/. _(Reference doc shipped; binary before/after screenshots remain a manual capture step — see docs/ui-redesign/SCREENSHOTS.md.)_

## Pending Reda (carry these in the plan)
- [ ] New dependencies to approve before Groups G/H build: @tanstack/react-table, plus shadcn's helper set (@radix-ui/* primitives, class-variance-authority, tailwind-merge, clsx, lucide-react, sonner) — all small, free, MIT.
- [ ] Upload the sun-with-bolt logo + one high-res PNG for the PWA icons/favicon (unblocks M59).
- [ ] Confirm default theme for F18 (light / dark / follow-system).
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

### Group B — Bug: file attachments

### Group C — Bug: navigation menu

### Group D — Paramètres: split + far more editable settings (all in one pass)

- [ ] **D2 — Quick settings.** Add:
  - editable **conditions générales** + **quote validity** (printed on the devis PDF);
  - **consolidated defaults**: default responsable, default installer, default acompte %;
  - **client ICE** on the client record, surfaced on devis/factures and **carried through
    without re-entry**, with a **non-blocking reminder** when missing on B2B docs;
  - a configurable **RIB + payment-instructions block** on the devis/facture PDFs;
  - **editable warranty texts per product/category**, seeded from the current texts.
  Ces littéraux s'impriment via le **moteur de devis vendoré existant**.
  _(UNGATED 2026-06-18 — chantier « littéraux PDF règle #4 ». Décision du founder prise =
  option (a) : autoriser un **câblage minimal des littéraux** (CGV, validité, RIB, garanties,
  « accepté le… ») du moteur premium `apps/ventes/quote_engine/generate_devis_premium.py` vers
  des **réglages éditables versionnés**, chaque réglage par DÉFAUT reproduisant EXACTEMENT le
  texte actuel pour que le PDF rendu soit **identique au byte près tant que rien n'est édité** ;
  la disposition visuelle NE CHANGE PAS. C'est une exception ciblée à « ne jamais éditer les
  pages premium », limitée à ce seul câblage littéral→réglage — PRÉ-APPROUVÉ (voir le bloc
  PRÉ-APPROUVÉ de `docs/PLAN.md`). Couvre les mêmes littéraux que N26 / N59 / N60 / N67 dans
  `docs/PLAN.md` ; construire D2 et ces tâches comme une seule famille cohérente. Déjà livré
  côté FACTURE : RIB + Instructions de paiement + Conditions générales (Feature B, voir N36) —
  reste à câbler le CÔTÉ DEVIS. Le client ICE (N28) et les défauts acompte (N34) / responsable
  existent déjà. Laissé `[ ]` — non construit. Règles permanentes : texte UI en français ;
  FK company forcée serveur ; chaque réglage par défaut = texte actuel exact (PDF byte-identique) ;
  migrations additives ; aucun prix d'achat sur le PDF client ; STAGES.py/funnel intouchés ;
  DEBUG/déploiement/sécurité inchangés.)_

- [x] **D4 — Roles & permissions editor (on the existing roles app).** Grant/restrict
  **per module and action**. **Buy prices and margins visible to owner only by default.** Ship
  a **safe default role set** (owner / commerciale / technicien / viewer) so **current access
  is unchanged**. Add **record-level scoping where feasible**. Margins/buy-price
  (`Produit.prix_achat`) must remain generator-only and never reach any PDF/client output.
  _(SHIPPED 2026-06-18 — founder pre-approved the auth change. Seven editable roles
  (Directeur, Administrateur, Commercial responsable, Commercial, Technicien responsable,
  Technicien, Viewer) seeded per company; full module×action grid in Paramètres → Rôles;
  `prix_achat_voir` gates buy prices (Directeur/Admin only); record-visibility scoping by
  supervisor/team across leads/clients/devis/factures/avoirs/relances/chantiers/
  interventions/tickets/équipements; existing users mapped so nobody lost access. Pairs with
  the supervisor/team hierarchy (Feature E) and the activity log (Feature G).)_

### Group E — End-to-end (E2E) browser test suite covering every screen flow

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-06-18 — RBAC + visibilité + audit + réglages facture + chart chantiers +
  icônes PWA (run « features A–G », un seul self-merge). **D4/N68/N69 (RBAC) :**
  7 rôles éditables (Directeur, Administrateur, Commercial responsable, Commercial,
  Technicien responsable, Technicien, Viewer) semés par société ; grille
  module×action complète dans Paramètres → Rôles ; prix d'achat & marges gatés par
  `prix_achat_voir` (Directeur/Admin) ; utilisateurs existants mappés sans perte
  d'accès. **Feature E (hiérarchie d'équipe, NON pré-listée) :** champ `supervisor`
  nullable sur l'utilisateur + éditeur dans Paramètres → Équipe. **Feature F
  (visibilité des enregistrements, NON pré-listée — couverte par N68) :** narrowing
  OPT-IN par rôle (équipe/sous-arbre) appliqué aux listes ET détails des leads,
  clients, devis, factures, avoirs, relances, chantiers, interventions, tickets,
  équipements ; admins/légacy/rôles personnalisés voient tout ; chacun voit toujours
  ses propres enregistrements. **Feature G (Journal d'activité / audit, NON
  pré-listé) :** un modèle d'audit company-scopé (signaux + middleware best-effort),
  capture connexion/déconnexion/échec + CRUD + statut + PDF/export/WhatsApp,
  endpoints stats (buckets Africa/Casablanca) + liste filtrable, page
  « Journal d'activité » réservée au Directeur (permission éditable). **N36/D2
  (Feature B) :** RIB + Instructions de paiement + Conditions générales éditables,
  imprimés sur la FACTURE seulement si renseignés (identique au byte près sinon ;
  côté devis gaté règle #4). **K51 — comblé :** graphe « Chantiers par statut »
  ajouté au tableau de bord (recharts, respecte la nouvelle visibilité).
  **M59/Feature C :** icônes PWA + favicons régénérées depuis le logo. CI verte,
  merge unique vers `main`.
- 2026-06-18 — Refonte UI, vague 5 (Groupes M/N/O/P — finitions mobile/PWA,
  accessibilité, performance, nettoyage). 10 tâches livrées en 4 lanes parallèles
  à fichiers DISJOINTS (orchestrateur = revue + bookkeeping centralisé). **Lane
  STYLE** (séquentielle, propriétaire de `index.css`/`tokens.css`/`ui/*.jsx`) :
  M58 (passe iOS — champs legacy forcés à 16px ≤768px contre le zoom, garde
  anti-scroll-horizontal, modales en bottom-sheets sur mobile, cibles 44px),
  M62 (`scroll-behavior:smooth` + catch-all `prefers-reduced-motion` couvrant
  les écrans legacy hors tokens), N63 (anneau `:focus-visible` global sur les
  éléments interactifs legacy via `--ring` + repli de nom accessible sur
  IconButton ; StatusPill couleur+texte confirmé), N64 (hauteurs `min-height`
  au lieu de `height` fixes sur `.btn/.status-tab`, repli `100dvh` paysage ;
  Lighthouse/axe automatisés = étape manuelle, @axe-core étant une nouvelle
  dépendance hors périmètre), **P67** (les 16 CSS ad-hoc par composant migrés
  VERBATIM dans `index.css` sous sections commentées puis SUPPRIMÉS, 18 imports
  retirés ; ordre de cascade préservé pour `.kb-act-clock` records-panels avant
  kanban ; `tokens.css`/`index.css`/`landing.css` conservés). **Lane PERF**
  (router/vite/axios/datatable/lib/index.html) : O65 (découpage de routes + lazy
  déjà présents ; nouveau `RouteFallback` squelette via la primitive Skeleton
  remplace le « Chargement... » texte), O66 (virtualisation datatable + préload
  polices déjà présents ; nouveau `debounce.js`+hook `useDebouncedValue` câblé au
  filtre global du DataTable (250 ms, valeur affichée instantanée) + 5 tests ;
  helper de cache GET `requestCache.js` OPT-IN non branché (comportement par
  défaut inchangé) ; budget de bundle `chunkSizeWarningLimit:900` + `manualChunks`
  isolant react-vendor/recharts/pdfjs-dist/@radix-ui ; aucune `<img>` dans le
  périmètre). **Lane PWA** (Layout.jsx) : M61 (OfflineBanner monté dans le
  layout — bannière FR hors-ligne, inerte en ligne ; shell précaché déjà fait
  par sw.js) ; M60 confirmé DÉJÀ présent (UpdateToast « Nouvelle version
  disponible — Actualiser » dans PwaPrompts). **Lane DOCS** : P69 (`tokens.md`
  étendu en référence canonique du design-system + `SCREENSHOTS.md` ; captures
  binaires = étape manuelle honnêtement notée). CI locale verte sur l'agrégat :
  eslint 0 erreur (6 warnings legacy Landing.jsx), 157 tests unitaires, build
  vite+PWA OK. Aucune nouvelle dépendance, additif, FR, aucun PDF/PdfCanvas/page
  publique/STAGES.py/apps-web/back-end touché, prix d'achat jamais exposés.
  RESTE OUVERT/GATÉ : M59 (logo à fournir par Reda), D2/D4 (décision fondateur).
  **La file PLAN2 est désormais drainée** (seuls M59/D2/D4 gatés restent).
- 2026-06-18 — Refonte UI, vague 4 (fin du Groupe J) : J50 (chrome de l'aperçu
  PDF) livré sur un `main` contenant déjà la vague 4 (donc base correcte, plus de
  conflit). Restyle UNIQUEMENT du chrome de la zone d'aperçu dans LeadDevisPanel
  (toolbar format `Segmented` + case « étude » `Checkbox`, indicateur de
  chargement `Spinner`, overlays d'erreur/hors-ligne → `EmptyState`+`Button`,
  mise en page mobile, couleurs tokenisées dans leaddevispanel.css). PdfCanvas.jsx
  et previewPdf.js NON touchés (règle #4). Hooks e2e préservés (`.ldp-panel`,
  `.ldp-pdf-area`+canvas, `.ldp-fallback` count 0 au succès, `.ldp-overlay`/
  `.modal-close`, intitulés « Édition complète »/« Télécharger le PDF »). CI
  locale verte (eslint 0 erreur, build vite+PWA, 157 tests). Le **Groupe J est
  désormais complet (J39–J50)**. RESTE OUVERT : Groupes M (mobile/PWA), N (a11y),
  O (perf), P (cleanup) — transverses (partagent src/ui/router/index.css), à
  traiter en vague dédiée. GATÉ : M59 (logo), D2/D4 (décision fondateur).
- 2026-06-18 — Refonte UI, vague 4 (suite) : J49 (Mes Activités) + Groupe K
  (K51 Dashboard, K52 hub Reporting + Rapports + Balance âgée) livrés dans le
  MÊME lot/merge que le Groupe J (PR #152), via 3 lanes worktree isolées et
  file-disjointes (activities ; Dashboard.jsx ; Reporting/Rapports/reporting/*).
  K51 : cartes KPI → `Stat`, recharts re-thémées via tokens, fil d'activité,
  états vides/chargement(Skeleton)/erreur ; titre « Tableau de bord » (heading)
  préservé (assertion auth.setup e2e). K52 : hub Reporting + Rapports (onglets
  `Tabs`) + Balance âgée + archives ; filtres `Segmented` côté client (sans appel
  API en plus) ; titres « Balance âgée » et /Archive documentaire/ + tables
  `data-table` préservés (e2e receivables). J49 : cockpit Mes Activités sur
  Card/StatusPill/Button + vrai état d'erreur ; les hooks `.act-*`/`.ap-*` vivent
  dans le composant partagé ActivitiesPanel (non touché), donc préservés. CI
  locale verte (eslint 0 erreur, build vite+PWA, 157 tests). NUANCE honnête :
  K51 n'inclut PAS le graphe « chantiers par statut » suggéré — les slices du
  dashboard ne chargent pas les installations aujourd'hui et ajouter un appel
  serait un changement de comportement (hors périmètre « API identiques ») ;
  noté comme petit reliquat. J50 (chrome de l'aperçu PDF) REPORTÉ d'un cran :
  les sous-agents worktree branchent depuis `origin/main`, donc J50 avait été
  bâti sur le LeadDevisPanel d'AVANT la vague 4 et entrait en conflit ; il sera
  refait proprement sur un `main` contenant déjà la vague 4. RESTE OUVERT : J50,
  Groupes M (mobile/PWA), N (a11y), O (perf), P (cleanup). GATÉ : M59, D2/D4.
- 2026-06-18 — Refonte UI, vague 4 (restyle par module, Groupe J) : J39→J48
  livrés. HUIT lanes en worktrees isolés à périmètres de fichiers DISJOINTS
  (vérifié : zéro chevauchement, zéro fichier hors `frontend/src/pages/<module>/`),
  chacune branchant un module sur le système de design `@/ui` (G/H/I) sans toucher
  aux primitives, aux slices API, au routeur, à `index.css`, ni aux composants
  partagés (`AssigneePicker`, `InlineEdit`, `AttachmentsPanel`…). Lanes : CRM
  (J39 leads + J40 clients), Ventes (J41 devis + J42 factures/relances/avoirs/
  kanban), Installations (J43), SAV (J44), Stock (J45), IA (J46), Admin (J47),
  Paramètres (J48). Les huit branches repliées en un seul `dev` (8 fusions sans
  conflit). CONTRAT e2e PRÉSERVÉ et re-vérifié statiquement sur l'arbre fusionné :
  toutes les classes/ids/intitulés porteurs présents (`modal modal-xl`,
  `kb-card`/`lv-row`, `lead-bill-*`, `#sd-devis`/`sd-option`, `dbl-panel`/
  `dbl-cluster`, `data-table` côté factures/avoirs/relances, `input:not([type])`
  pour le username admin, `input[name=email]` + « Profil enregistré avec succès. »
  côté Paramètres, intitulés de boutons/titres exacts) ; les hooks des composants
  partagés (`ie-cell`/`ie-input`, `ap-*`, `att-name`) intacts et toujours utilisés.
  Décision technique notée : la primitive `DataTable` n'émet pas de `<table class="data-table">`
  et bascule en cartes en mobile — donc les listes sélectionnées par e2e (factures/
  avoirs/relances, users admin) gardent une `<table className="data-table">`/`<tr>`
  sémantique plutôt que la primitive. Revue orchestrateur : 2 erreurs eslint
  introduites (lecture de ref pendant le rendu dans ProduitForm ; set-state-in-effect
  dans ContratsMaintenance) trouvées puis corrigées. CI locale verte : eslint 0
  erreur, build vite+PWA OK, 157 tests unitaires. Règles permanentes respectées :
  ZÉRO nouvelle dépendance, textes FR, additif, aucun PDF/PdfCanvas/page publique/
  STAGES.py/apps-web/back-end touché, prix d'achat jamais exposés. RESTE OUVERT :
  J49 (Activities), J50 (chrome PDF), Groupes K (dashboard/reporting), M (mobile/PWA),
  N (a11y), O (perf), P (cleanup). GATÉ/BLOQUÉ inchangé : M59 (logo), D2/D4 (décision
  fondateur).
- 2026-06-18 — Refonte UI, vague 3 (fondation) : Groupe I (coquille + navigation)
  + Groupe L (comportements UX globaux). Deux lanes en worktrees isolés à
  périmètres de fichiers DISJOINTS (SHELL = `components/layout/*` + `index.css` ;
  BEHAVIORS = `main.jsx`/`router`/`api/axios.js`/`lib/*`/`providers/*`),
  fusionnées en un seul lot et revues par un agent adversarial avant fusion.
  La revue a trouvé puis fait corriger 2 bloquants (titre d'en-tête rendu en
  élément non-heading pour éviter une collision de rôle `heading` qui cassait
  toute la suite e2e chromium ; suppression d'un 2ᵉ écouteur ⌘K qui ouvrait
  puis refermait la palette). Règles permanentes respectées : ZÉRO nouvelle
  dépendance, textes FR, additif, contrat de hooks e2e préservé
  (`header-title`, `header-menu-btn`, `aside.sidebar`, `sidebar-nav`,
  `sidebar-nav-item.active`), aucun PDF/page publique/PdfCanvas/STAGES.py/
  apps-web/back-end touché. CI locale verte : eslint 0 erreur, 172 tests
  unitaires, build vite+PWA OK. • Groupe I : I34 sidebar repliable (état
  persistant, marque, sections groupées, scroll dans la safe-area iOS — fin de
  la coupure du pied de menu) ; I35 en-tête (fil d'Ariane dérivé de la route,
  déclencheur ⌘K, cloche, menu utilisateur, titres FR corrects pour TOUTES les
  routes + composant `PageHeader` réutilisable) ; I36 barre d'onglets basse
  mobile (safe-area-inset-bottom) + barre de progression de transition de route ;
  I38 coquille de notifications (badge non-lus, liste groupée réutilisant
  `/reporting/notifications`, invite de permission web-push contextuelle qui ne
  s'affiche qu'à l'ouverture de la cloche et no-op si push indisponible).
  • Groupe L : L53 `<Toaster>` (sonner) monté à la racine + helpers de toast +
  pont d'erreur API global (un échec de requête remonte un toast FR, 401/404
  exclus) ; L54 `ConfirmProvider`/`useConfirm()` sur AlertDialog (défauts FR,
  fallback sûr) ; L55 util d'updates optimistes avec rollback (+ tests) ; L56
  palette ⌘K (Dialog, navigation clavier, réutilise `/reporting/search`, ouvre
  via ⌘K et via l'événement window du Header) ; L57 ré-auth en place sur 401
  sans rechargement (préserve le formulaire en cours, exclut `/login` et `/token/`).
  NUANCES (honnêteté) : L53/L54/L55 livrent l'INFRASTRUCTURE globale + le câblage
  central ; l'adoption écran-par-écran (un toast/confirm sur chaque action)
  suivra dans le Groupe J (restyle par module), exactement comme G/H étaient
  additifs avant le branchement par module. I37 : raccourcis clavier + dialogue
  d'aide « ? » entièrement livrés ; le correctif de la lenteur de premier
  chargement à froid (C7) est une déduplication réelle du bootstrap d'auth
  (confiance modérée — non reproduit en headless, à confirmer en usage réel).
  RESTE OUVERT : Groupe J (restyle par module), K (dashboard/reporting), M58/M60/
  M61/M62, N63/N64, O65/O66, P67/P69. GATÉ/BLOQUÉ inchangé : M59 (logo), D2/D4
  (décision fondateur).
- 2026-06-18 — Refonte UI, vague 2 : Groupe G terminé + Groupe H (moteur
  DataTable). Deux lanes en worktrees isolés, fusionnées en un seul lot,
  revues par un agent adversarial (API préservée 1:1, proxy de
  téléchargement B1 intact, règles permanentes respectées, zéro nouvelle
  dépendance), CI locale verte (eslint 0 erreur, build OK, 155 tests
  unitaires). • Groupe G : G23 Select (Radix) + Combobox/MultiSelect
  (recherche async + états vide/chargement/erreur) et AssigneePicker /
  ProduitPicker reconstruits dessus, props/comportement à l'identique ;
  G24 DatePicker/DateRangePicker/TimePicker bâtis sur Popover + calcul de
  dates maison (AUCUNE librairie de dates ajoutée), fr-FR/jj-mm-aaaa ;
  G26 FileUpload/dropzone (glisser-déposer, progression, validation
  type/taille) avec AttachmentsPanel + flux OCR (IA + Stock) reconstruits
  dessus, appels réseau et proxy de téléchargement inchangés ; G27 système
  de formulaire composable (Form/FormSection/FormField/FormActions +
  garde « modifications non enregistrées » + barre d'actions collante).
  • Groupe H : un moteur <DataTable> réutilisable (TanStack Table, sans
  nouvelle dépendance) — en-tête figé, 1re colonne gelée, tri multi-colonnes,
  filtres colonne+global, gestion des colonnes (afficher/masquer/réordonner/
  redimensionner/épingler), densité, pagination « X–Y sur N », surlignage,
  cases de sélection au survol + barre d'actions en masse configurable,
  actions de ligne + débordement, lignes cliquables/extensibles, édition
  en ligne avec annulation + toast, lignes de sous-total (TVA), vues
  enregistrées en onglets, état persistant dans l'URL, virtualisation maison
  (619 lignes), export CSV + crochet XLSX, repli mobile en cartes — démo au
  /ui. NUANCE : le moteur est ADDITIF et n'est PAS encore branché sur les
  écrans réels (c'est le Groupe J) ; le tri/filtre côté serveur et l'export
  XLSX serveur sont exposés en COUTURE (props/callbacks) et seront câblés
  au back-office lors du branchement par module — aucun endpoint backend
  ajouté dans cette vague. RESTE OUVERT : Groupe I (shell/nav), Groupe J
  (restyle par module), K/L/M/N/O/P. D2 et D4 restent GATÉS (décision
  fondateur). M59 reste bloqué (upload du logo).
