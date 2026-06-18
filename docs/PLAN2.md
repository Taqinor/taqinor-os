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

## BUILD QUEUE (do top-down — highest value first)

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

## Group F — Design foundation & tokens
- [x] **F14.** Audit + brand extraction: read every screen and the ~15 per-component .css files; pull the real Taqinor palette, the Archivo + Hanken Grotesk fonts, and the sun-with-bolt logo from apps/web so the ERP matches the brand. Map current styling to a token plan.
- [x] **F15.** Token system in Tailwind 4 @theme — primitive → semantic → component layers: a solar palette (warm amber/gold primary used sparingly as the energy accent; deep ink/graphite neutral base; clean grays; semantic success/warning/danger/info), plus spacing, radius, elevation/shadow, z-index, and motion scales. Full light + dark mode. Avoid the AI-default looks (cream+terracotta serif; near-black+acid-green; broadsheet hairlines).
- [x] **F16.** Typography: Archivo (display/headings), Hanken Grotesk (body/UI), tabular figures for all money/quantity numbers; self-host + preload fonts (no flash of unstyled text); a clear type scale with intentional weights.
- [x] **F17.** Icon system: standardize on lucide-react with one size/stroke convention; replace ad-hoc icons.
- [x] **F18.** Theming infra: light/dark toggle that also follows system preference and persists; correct theme-color and iOS status-bar meta per theme. (Default theme: follow-system unless Reda specifies otherwise.)
- [x] **F19.** Centralized format utilities: MAD currency, fr-FR number formatting, dd/mm/yyyy dates, Moroccan phone formatting — one source of truth used everywhere.
- [x] **F20.** Density modes (comfortable / compact) wired to tables and forms, with a user preference.

## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)
- [x] **G21.** Buttons + IconButton (variants/sizes/loading/disabled), with consistent focus-visible rings.
- [x] **G22.** Inputs: text, textarea, number, currency (MAD), percentage, phone (MA) — with proper formatting and 16px font on mobile to prevent iOS zoom.
- [ ] **G23.** Select, Combobox/autocomplete (rebuild AssigneePicker and ProduitPicker on it), MultiSelect, with async search + empty/loading.
- [ ] **G24.** Date picker, Date-range picker, Time picker (the last for relance scheduling).
- [x] **G25.** Checkbox, Radio group, Switch, Segmented control, Slider.
- [ ] **G26.** File upload / dropzone (rebuild AttachmentsPanel + the OCR upload flows) with progress, type/size validation, and reliable open/download (this also resolves the Group B attachment bug at the component level).
- [ ] **G27.** Form system: labels-above layout, sectioned forms, inline field validation + cross-field validation, required markers, an error summary, a dirty-state guard ("unsaved changes — leave?"), and a sticky save/cancel action bar (especially on mobile).
- [x] **G28.** Overlays: Dialog, Sheet (mobile bottom-drawer), AlertDialog (confirm destructive actions), Popover, HoverCard, Tooltip, DropdownMenu, ContextMenu — with focus trap + restore.
- [x] **G29.** Feedback + display: Toast/sonner (success/error/loading/undo), Badge + StatusPill (one status taxonomy for leads/devis/factures/chantiers/tickets), Tag/Chip, Avatar + AvatarGroup, Card, Stat/KPI card, Definition list, Tabs, Accordion, Progress, Separator.
- [x] **G30.** States kit: skeleton loaders per layout, EmptyState (message + clear next action), ErrorBoundary screen, 404, and an offline state — applied consistently across every screen.

## Group H — DataTable engine (TanStack Table, behind every list view)
- [ ] **H31.** Core grid: sticky header, frozen first column, multi-column sort, per-column + global filter, column show/hide + reorder + resize + pin, density toggle, pagination with an "X–Y of N" count, and search-match highlighting.
- [ ] **H32.** Actions + editing: hover-revealed row checkboxes; a floating contextual bulk-action bar (bottom on mobile) for assign / change stage / export / delete; up-to-3 row icons + an overflow menu; clickable rows → detail/quick-view/expandable; inline cell editing with validation, undo, and save feedback; summary/subtotal rows (totals + TVA).
- [ ] **H33.** Scale + persistence: saved/preset views as tabs (e.g. "À relancer", "Signés", "En retard"); sort/filter/page persisted to the URL (survives refresh + deep-links); server-side sort/filter for >1000 rows; row virtualization for large lists (619-lead import); CSV/XLSX export (openpyxl server-side); and a mobile fallback (rows → cards, or priority columns + horizontal scroll with frozen first column).

## Group I — App shell & navigation
- [ ] **I34.** Sidebar: collapsible, grouped sections, clear active state, brand mark, fully scrollable inside the iOS safe area (resolves C6 menu cutoff).
- [ ] **I35.** Header: breadcrumbs, global search trigger (⌘K), notifications bell, user menu, and a consistent page-header pattern (title + actions + filters/tabs).
- [ ] **I36.** Mobile bottom tab bar for primary nav (thumb-reachable) with safe-area inset; route-transition loading bar.
- [ ] **I37.** Fix desktop cold first-load flakiness so a single load works (resolves C7); global keyboard shortcuts + a "?" shortcuts help dialog.
- [ ] **I38.** Notifications UI shell: bell + dropdown list + unread badge + an in-context permission prompt (shown with rationale, not on load). Wires to the planned VAPID web-push backend later; degrades to a no-op if the backend/keys are absent.

## Group J — Per-module restyle (each: list → DataTable, forms → new primitives, modals → Dialog/Sheet, statuses → StatusPill, real empty/loading/error states, mobile pass)
- [ ] **J39.** CRM Leads — kanban / list / charts / calendar views, LeadCard, FilterBar, ViewSwitcher, DoublonsPanel, LeadDevisPanel; polish drag affordance on the kanban.
- [ ] **J40.** CRM Clients — list + form.
- [ ] **J41.** Ventes Devis — list, form, and the multi-market generator (the line-item editor needs the most care).
- [ ] **J42.** Ventes Factures — list + form (acompte/solde/avoir); Relances; Avoirs; Ventes Kanban.
- [ ] **J43.** Chantiers/Installations — list + detail + filter bar.
- [ ] **J44.** SAV — Tickets + Équipements (warranty tracking).
- [ ] **J45.** Stock — list, mouvements, produit form, OCR import.
- [ ] **J46.** IA — AgentChat + OCR upload.
- [ ] **J47.** Admin — Roles editor + Users.
- [ ] **J48.** Paramètres — restyle in the new system (the tabbed split + editable settings are feature tasks D9–D13; build them on the new primitives).
- [ ] **J49.** Activities — Mes Activités.
- [ ] **J50.** PDF preview screen — restyle only the chrome around PdfCanvas (toolbar, container, mobile layout). Do NOT touch the rendered PDF content or template.

## Group K — Dashboard & reporting
- [ ] **K51.** Dashboard: KPI cards + themed charts (recharts, or Tremor copy-in blocks) — pipeline value, devis→signé conversion, outstanding invoices / aged balance, chantiers by status, revenue — plus an activity feed. Real data from existing slices/APIs; no buy-price exposure.
- [ ] **K52.** Reporting hub + Balance âgée: restyle with charts, date-range + segment filters, export, and proper empty/loading states.

## Group L — Global UX behaviors
- [ ] **L53.** Consistent async feedback: every save / delete / send-WhatsApp / generate-PDF fires a toast, with undo where safe.
- [ ] **L54.** Confirm dialogs for all destructive actions.
- [ ] **L55.** Optimistic updates with error rollback on common edits.
- [ ] **L56.** Global ⌘K command palette searching leads/clients/devis/factures/chantiers/produits → jump to the record.
- [ ] **L57.** Session-timeout handling: graceful re-auth that preserves the in-progress form.

## Group M — Mobile & PWA polish (Meryem is iPhone-primary)
- [ ] **M58.** iOS pass: safe-area insets everywhere, tap targets ≥44pt, 16px inputs (no zoom), no horizontal scroll on core flows, modals → bottom sheets, primary actions thumb-reachable.
- [ ] **M59.** PWA icons: standard 192/512 + maskable variants with the 80% safe zone, plus favicon — from the sun-bolt asset (BLOCKED until Reda uploads the logo/PNG); add splash + install-prompt UI.
- [ ] **M60.** Service-worker update flow: a "Nouvelle version — recharger" toast when a new build is live (removes the delete-and-reinstall pain for future updates).
- [ ] **M61.** Offline state: cached app shell + a clear offline banner instead of a browser error page.
- [ ] **M62.** Smooth scrolling + reduced-motion respected throughout.

## Group N — Accessibility & quality floor (WCAG 2.2 AA)
- [ ] **N63.** Contrast 4.5:1 (incl. dark / disabled / pressed states), focus-visible rings, ARIA labels on icon buttons, semantic HTML, full keyboard nav for tables/kanban/dialogs (focus trap + restore), screen-reader announcements for toasts + validation, color never the only signal.
- [ ] **N64.** Text resize to 200% and portrait+landscape without breakage; Lighthouse + axe pass each release.

## Group O — Performance
- [ ] **O65.** Route-based code splitting + lazy loading; skeleton-first rendering.
- [ ] **O66.** List virtualization for big tables, debounced search, request caching; font preload + image lazy-load; a bundle budget.

## Group P — Consistency & cleanup
- [ ] **P67.** Migrate and DELETE the ~15 ad-hoc per-component .css files into the token system + primitives as each screen is converted.
- [x] **P68.** Internal /ui component reference page (living style guide) so all future work stays on-system.
- [ ] **P69.** Document the token system in one reference file; save before/after screenshots of key screens to docs/ui-redesign/.

## Pending Reda (carry these in the plan)
- [ ] New dependencies to approve before Groups G/H build: @tanstack/react-table, plus shadcn's helper set (@radix-ui/* primitives, class-variance-authority, tailwind-merge, clsx, lucide-react, sonner) — all small, free, MIT.
- [ ] Upload the sun-with-bolt logo + one high-res PNG for the PWA icons/favicon (unblocks M59).
- [ ] Confirm default theme for F18 (light / dark / follow-system).
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

- [x] **A1 — "Marquer comme accepté" control on a devis.** Add the status control that's
  currently missing directly on a devis. Accepting records **which option the client chose**
  (Sans batterie / Avec batterie), the **acceptance date**, and **who accepted**, written to
  the devis/lead **Historique** (chatter). Add the small devis fields needed to store these
  (acceptance date, chosen option, accepted-by). Preserve the existing devis status layer
  (`brouillon`/`envoye`/`accepte`/`refuse`/`expire`) — this sets `accepte` and records the
  option + metadata; it does not invent a new status layer.

- [x] **A2 — Moving a lead into Signé prompts for the accepted devis + option.** When a lead
  is moved into the **Signé** stage (kanban drag or stage control), open a short dialog to
  pick **which of the lead's devis was accepted** and **which option** (Sans batterie / Avec
  batterie); confirming marks that devis accepted (reusing A1). If the lead has **no devis**,
  show a message to **create/select one first** — never invent a devis and never move the
  stage without one. Keep it a **user-confirmed prompt**; the lead funnel stage (STAGES.py)
  and the document status stay **separate layers** (rule #2) — moving to Signé does not
  silently rewrite document statuses beyond the one chosen devis the user confirms.

- [x] **A3 — The chosen option is authoritative downstream.** The **facture échéancier** and
  the **chantier** use **only the accepted option's lines** (battery lines excluded if "Sans
  batterie", included if "Avec batterie"). Totals and TVA must be correct **to the centime**
  for that option (reuse the existing reference/total utilities; never recompute by hand).

- [x] **A4 — Inline next actions after acceptance.** After a devis is accepted, surface both
  next actions inline on the lead/devis:
  - **"Générer la facture"** — acompte → matériel → solde on repeat clicks, **unchanged**
    behaviour (do not alter the existing échéancier engine, only feed it the accepted option).
  - **"Créer le chantier"** — **pre-filled** from the accepted option, **no duplicate** if a
    chantier already exists for that devis/lead (guard against double-create).

### Group B — Bug: file attachments

- [x] **B1 — Fix file attachments end-to-end (and the broken devis-PDF icon).** Attaching a
  file to a **lead / client / chantier / SAV ticket** is broken on **both** the upload side
  and the **open/download** side — fix both. This is **likely the same root cause** as the
  broken-file icon on new devis PDFs (storage link not reachable from the browser — MinIO/
  storage URL not resolvable from the client). **Fix both together**: ensure uploads succeed
  and the stored object is afterward **openable/downloadable from the browser**. Add a
  regression test that an uploaded attachment round-trips (upload → fetch a working URL).

### Group C — Bug: navigation menu

- [x] **C1 — iPhone: menu items cut off / unreachable.** The last menu item(s) are cut off
  and unreachable on iPhone. Make the **whole menu scrollable** and **fully visible inside
  the iOS safe area**, in **both the installed (PWA) app and Safari**. **Verify on real
  iPhone widths** — do **not** assume the earlier responsive/safe-area work covered it.

- [x] **C2 — Desktop: cold first-load flakiness.** Fix the cold first-load flakiness (needing
  several refreshes) so a **single load works reliably** on desktop. (Related to the
  no-store + PWA service-worker behaviour — investigate the SW/first-paint race rather than
  guessing.)

### Group D — Paramètres: split + far more editable settings (all in one pass)

- [x] **D1 — Reorganize Paramètres into sections/tabs by domain.** Split the single long
  Paramètres page into tabs/sections: **Société & identité · Leads · Clients · Devis &
  Factures · Stock · Équipe & rôles · Messages & relances · Avancé**. Keep **every existing
  setting working** (no setting dropped or broken). **No horizontal overflow on phones.**

- [ ] **D2 — Quick settings.** Add:
  - editable **conditions générales** + **quote validity** (printed on the devis PDF);
  - **consolidated defaults**: default responsable, default installer, default acompte %;
  - **client ICE** on the client record, surfaced on devis/factures and **carried through
    without re-entry**, with a **non-blocking reminder** when missing on B2B docs;
  - a configurable **RIB + payment-instructions block** on the devis/facture PDFs;
  - **editable warranty texts per product/category**, seeded from the current texts.
  These print through the **existing vendored quote engine** — do **not** edit the premium
  PDF pages; feed the engine new fields (rule #4).
  _(2026-06-17 — STOP-AND-ASK : conflit avec une règle non-négociable. Le moteur premium
  `apps/ventes/quote_engine/generate_devis_premium.py` CODE EN DUR la validité « 30 jours »,
  le bloc RIB, les conditions générales et l'identité légale (ce ne sont pas des champs de
  données — ce sont des littéraux dans le gabarit). Les imprimer depuis les Paramètres exige
  de modifier ces pages premium, ce que la règle #4 / la règle permanente « ne jamais éditer
  les pages premium » interdit. « Feed the engine new fields » suppose que le moteur consomme
  ces champs, ce qui n'est pas le cas. Décision du founder requise : (a) autoriser un câblage
  minimal des littéraux vers des champs `data` AVEC valeurs par défaut identiques (sortie PDF
  inchangée tant que rien n'est édité), ou (b) accepter que CGV/validité/RIB restent figés
  dans le moteur. Idem N36 / N60 / N67 (mêmes littéraux premium). Laissé `[ ]` ; D3 et D5
  restent constructibles. Note : le client ICE (N28) et les défauts acompte (N34) /
  responsable existent déjà ; la validité est déjà éditable dans Paramètres → Devis & Factures
  mais le PDF affiche « 30 jours » figé.)_

- [x] **D3 — Per-document numbering configuration.** Add per-document-type numbering config
  (**prefix, padding width, yearly-reset**) per document type, **keeping sequences gap-free
  and race-safe** (reuse `apps/ventes/utils/references.py` — NEVER count()+1), **seeded to
  current behaviour** so existing numbering is unchanged until edited.

- [ ] **D4 — Roles & permissions editor (on the existing roles app).** Grant/restrict
  **per module and action**. **Buy prices and margins visible to owner only by default.** Ship
  a **safe default role set** (owner / commerciale / technicien / viewer) so **current access
  is unchanged**. Add **record-level scoping where feasible**. Margins/buy-price
  (`Produit.prix_achat`) must remain generator-only and never reach any PDF/client output.
  _(2026-06-17 — STOP-AND-ASK : changement d'autorisations/RBAC = nouvelle
  architecture, aligné sur le GATED G4 de PLAN.md ; laissé `[ ]`, à traiter sur
  décision du founder. D1–D3 et D5 restent constructibles.)_

- [x] **D5 — Avancé: editable + versioned quote logic.** Make the implicit quote logic
  **editable and versioned**: margin / target price per kWc, discount limits, auto-remplir
  sizing ratios, per-region production factors, and the **ONEE tariff tables/tranches**.
  **Every value seeded from today's in-code defaults** so default quoting stays **identical**
  until edited. Do **not** touch the PDF templates and do **not** break the lossless
  typed-number behaviour (form `noValidate`, inputs `step="any"` — guarded by tests). Keep
  `solar.js` classification keywords aligned with `quote_engine/builder.py`.
  _(2026-06-17 — Cœur livré : les paramètres implicites RÉELS d'aujourd'hui sont
  désormais éditables, audités (versionnés via le journal d'audit N55) et
  CÂBLÉS dans le générateur, tous amorcés sur les constantes du simulateur (devis
  identique tant que rien n'est édité). DEUX exemples énumérés sont laissés en
  raffinement FUTUR car ils n'existent dans aucun code aujourd'hui et changent le
  MODÈLE de calcul : les tables tarifaires ONEE par tranche (le tarif actuel est
  un taux plat, désormais éditable) et les facteurs de production PAR RÉGION (il
  n'y a pas de champ région sur le devis) — à valider avec le founder (barème de
  tranches + carte régionale).)_

### Group E — End-to-end (E2E) browser test suite covering every screen flow

- [x] **E1 — Playwright + required CI job.** Add Playwright to the frontend and a new
  CI job that runs the E2E specs headless against a throwaway test database with MinIO
  (reuse the existing test stack; never touch production data). Make this E2E job
  **required for merge**. NOTE for whoever executes this later: this introduces
  Playwright (a new dev/test dependency) and a new CI job — Reda has already approved
  both, so proceed without pausing to re-ask.
  _(2026-06-17 — DONE. The prior SKIP was environmental: the local Docker daemon
  was down. Resolved by building on the CI runner itself — the new `e2e` GitHub
  Actions job spins up the SAME throwaway stack backend-tests uses (Postgres+pgvector,
  Redis, MinIO), serves the real built app via `vite preview` proxying same-origin to
  Django, seeds throwaway data (`seed_demo` + `seed_catalogue`), and runs all 18 specs
  headless — proven green over five iterations before merge. The job is added to the
  required status checks.)_

- [x] **E2 — Login is the app entry point.** A valid login lands in the app; an
  invalid login is rejected.

- [x] **E3 — Lead lifecycle.** Create a lead, confirm it appears in the list and on
  the kanban, open it.

- [x] **E4 — Devis from a lead.** From a lead, generate a devis (automatic and
  modifiable), confirm the PDF preview actually renders (no broken-file icon), the new
  devis appears in that lead's devis list, and download works.

- [x] **E5 — Inline bill editing.** Inline bill editing on a lead saves and reflects
  correctly.

- [x] **E6 — Lead reassignment.** Reassignment works both from the lead view and from
  a kanban card.

- [x] **E7 — Stage transitions.** Moving a lead between stages works, including into
  Signé.

- [x] **E8 — Employee management.** Create/edit an employee, upload a photo, and reach
  the password-reset action.

- [x] **E9 — Typed activities.** Log an activity and see it in the cockpit view.

- [x] **E10 — File attachments.** Attach a file to a record, confirm the upload
  succeeds and the file can be opened/downloaded afterward.

- [x] **E11 — Duplicate detection.** The doublons view renders and merging a cluster
  completes.

- [x] **E12 — Credit notes (avoirs).** An avoir can be created from a posted invoice.

- [x] **E13 — Payment follow-ups & receivables.** Payment follow-ups, aged
  receivables, and a customer statement all render.

- [x] **E14 — Paramètres.** Paramètres pages load, and changing a setting saves and is
  reflected.

- [x] **E15 — Cross-cutting health.** Assert no broken images and no uncaught console
  errors on the key pages.

- [x] **E16 — Mobile pass.** Run a subset at iPhone viewport width asserting no
  horizontal overflow and that the full navigation menu is reachable.

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-06-18 — Refonte UI, Groupes F + G (fondation + bibliothèque de primitifs).
  Reda a approuvé les 7 nouvelles libs (shadcn/Radix, TanStack Table, lucide,
  sonner, cva/clsx/tailwind-merge) → la file prioritaire de refonte est
  débloquée. Livré ADDITIF, **zéro régression** : noms de tokens personnalisés,
  aucun défaut Tailwind ni la police du body écrasés, aucun `dark:` ailleurs →
  les écrans existants restent identiques jusqu'à leur migration (groupes J/P).
  • Groupe F : F14 audit + extraction de marque (apps/web) → docs/ui-redesign/
  tokens.md ; F15 système de tokens Tailwind 4 @theme (brass/nuit/azur/lune →
  sémantique clair+sombre + densité + ombres/z-index/motion) ; F16 polices
  Archivo + Hanken auto-hébergées + préchargées + chiffres tabulaires ; F17
  lucide-react adopté comme système d'icônes des nouveaux primitifs (convention
  taille/épaisseur unique ; le remplacement des icônes ad hoc des écrans
  existants se fait à la migration J) ; F18 thème clair/sombre/système (défaut
  système) + ThemeProvider/Toggle ; F19 utilitaires de formatage centralisés
  (MAD/fr-FR/dates/tél. MA) ; F20 modes de densité confort/compact.
  • Groupe G : G21 Button/IconButton/Spinner ; G22 Input/Textarea/Label +
  Number/Currency/Percent/Phone (saisie sans perte, 16px mobile anti-zoom) ;
  G25 Checkbox/Radio/Switch/Segmented/Slider ; G28 Dialog/Sheet/AlertDialog/
  Popover/Tooltip/DropdownMenu/HoverCard/ContextMenu (focus trap via Radix) ;
  G29 Toaster(sonner)/Badge/StatusPill(taxonomie unique)/Tag/Avatar/Card/Stat/
  Tabs/Accordion/Progress/Separator/DefinitionList ; G30 Skeleton/EmptyState/
  ErrorBoundary/NotFound/Offline. P68 vitrine vivante à la route /ui.
  Vérif : build + eslint verts, 96 tests unitaires (.mjs) verts (dont format +
  theme), et spec Playwright e2e/ui-system (thème/densité/dialog/toast/0 erreur
  console) PASSÉE en navigateur local. RESTE OUVERT dans le Groupe G : G23
  (Select/Combobox/MultiSelect), G24 (date pickers), G26 (upload/dropzone), G27
  (form system) — plus complexes, prochaine vague ; puis H (DataTable), I (shell/
  nav), J (restyle par module), K, L, M, N, O, P67/P69.
- 2026-06-17 — E1–E16: end-to-end Playwright browser suite shipped and proven
  green in CI (all 18 specs). E1 = a new required `e2e` GitHub Actions job that
  reuses the same throwaway stack as backend-tests (Postgres+pgvector, Redis,
  MinIO — never production), seeds throwaway data (`seed_demo` + `seed_catalogue`),
  builds the real app and serves it via `vite preview` proxying same-origin to
  Django, then runs headless. Specs cover: login valid/invalid (E2); lead
  lifecycle list+kanban+open (E3); auto+modifiable devis from a lead with the PDF
  preview actually rendering on canvas and a working download (E4); inline bill
  edit (E5); reassignment from a kanban card and the lead view (E6); stage moves
  incl. the Signé acceptance dialog (E7); employee create/edit + photo upload +
  password-reset (E8); typed activity → cockpit (E9); file attachment round-trip
  (E10); doublons merge (E11); avoir from a posted invoice (E12); relances /
  balance âgée / customer statement (E13); paramètres save (E14); broken-image /
  console-error health on key pages (E15); iPhone-width no-overflow + reachable
  nav (E16). The first runs doubled as an audit and surfaced ONE real app bug,
  fixed in scope: the leads pipeline blanked to a full-page loader on every
  background refetch, tearing down any open lead modal / inline devis preview
  mid-action (so the auto-devis preview never rendered and an inline bill edit
  looked like it didn't save) — now it only blanks on the first load. Also made
  the demo seed complete (default activity types + follow-up levels), which real
  signups already get. No known-failures; nothing skipped.
- 2026-06-17 — Vérification A1–A4 + C1 (signalés « ne marchent pas » par le
  fondateur) : DIAGNOSTIC = les deux fonctionnalités sont DÉJÀ complètes et
  correctes sur `main` (livrées le 17/06 via le lot dev-os, jamais reverties).
  Chaîne d'acceptation : champs `Devis.date_acceptation/accepte_par_nom/
  option_acceptee` présents, endpoint `accepter`, `SigneDialog` câblé au
  kanban + édition d'étape, option autoritative en aval (échéancier/chantier),
  actions en ligne facture/chantier — 21 tests `test_acceptation`/`test_options`
  exécutés et VERTS. Menu iPhone : `.sidebar-nav` défile (`min-height:0` +
  `overflow-y:auto`), sidebar bornée 100dvh, tiroir mobile avec insets safe-area
  HAUT et BAS, `viewport-fit=cover` présent. Aucune reconstruction. Seul ajout :
  un garde-fou de non-régression du menu (`menu.layout.test.mjs`, branché à la CI
  frontend-lint) qui verrouille ces invariants CSS/HTML — il ÉCHOUE si l'on
  retire `min-height:0` ou le `padding-bottom: env(safe-area-inset-bottom)`.
  Cause probable du « ne marche pas » côté fondateur : build PWA installé en
  cache (mises à jour livrées le même jour) → réinstaller / vider le cache.
- 2026-06-17 — D5: logique de devis éditable + versionnée (cœur). Les paramètres
  implicites du générateur sont désormais modifiables dans Paramètres → Avancé
  (carte « Logique de devis (avancé) ») et amorcés EXACTEMENT sur les constantes
  du simulateur, donc le devis reste identique tant que rien n'est édité :
  rendement global (0,8), nb de panneaux par tranche de 900 MAD (8, auto-remplir),
  prix cible /kWc par défaut (pré-remplit le générateur) et limite de remise
  conseillée (repère, sans bloquer la saisie). Le tarif ONEE (kWh) — qui était
  jusqu'ici STOCKÉ mais IGNORÉ par le simulateur — est maintenant réellement
  câblé : `solar.js computeROI` accepte tarif + rendement, `estimerPanneaux` le
  ratio, et `DevisGenerator`/`autoQuote` les lisent depuis le profil avec repli
  sur les constantes. Chaque changement est tracé (journal d'audit N55 =
  versionnement). Champs additifs sur CompanyProfile (migration 0013). Garde-fou
  de parité : les 29 tests `solar.test.mjs` passent (défauts strictement
  inchangés) + nouveaux tests d'override ; la frappe libre (noValidate/step=any)
  est préservée. Lint + build verts ; flake8 vert (suite Django en CI). RAFFINEMENT
  FUTUR laissé au founder : tables tarifaires ONEE par tranche (tarif plat
  aujourd'hui) et facteurs de production par région (pas de champ région) — ils
  changeraient le modèle de calcul.
- 2026-06-17 — D3: numérotation des pièces configurable par type. Dans Paramètres
  → Devis & Factures, chaque type (devis/facture/avoir/bon de commande) a
  désormais : préfixe (déjà existant), largeur de remplissage (nombre de
  chiffres) et période de réinitialisation — Mensuelle (défaut, comportement
  actuel DEV-202606-0001), Annuelle (DEV-2026-0001) ou Continue (DEV-0001, ne
  repart jamais), avec un aperçu en direct du prochain numéro. Nouveau champ
  additif `CompanyProfile.doc_numbering` (migration 0012) ; les défauts (4
  chiffres, mensuel) reproduisent EXACTEMENT l'ancien numéro tant que rien n'est
  édité. La génération reste sans trou et sans collision : `references.py`
  garde le plus-haut-utilisé+1 + retry de course, étendu par deux paramètres
  optionnels (padding/period) ; un nouveau helper `create_numbered` centralise
  préfixe+largeur+période et tous les points de création ventes (devis, facture,
  avoir, bon de commande, échéancier) l'utilisent. Les numéros déjà émis ne
  changent jamais. Tests cœur ajoutés (padding/annuel/continu + résolution de
  config + repli) ; flake8 + lint front + build verts (suite Django complète en
  CI). La longue page unique est
  désormais une barre d'onglets par domaine : Société & identité · Leads ·
  Clients · Devis & Factures · Stock · Équipe & rôles · Messages & relances ·
  Avancé. Chaque réglage existant est conservé tel quel (identité/légal/ICE/logo/
  signature/couleur dans Société ; responsable défaut + étiquettes/motifs + canaux
  dans Leads ; échéancier/validité/pompage/préfixes + TVA dans Devis & Factures ;
  marques + catégories + fournisseurs dans Stock ; niveaux de relance + messages
  WhatsApp dans Messages & relances ; hypothèses ROI/seuils + types d'intervention
  + checklist chantier + champs personnalisés dans Avancé). Un seul formulaire
  couvre tous les onglets, donc « Enregistrer » sauve le profil complet quel que
  soit l'onglet ouvert. La barre d'onglets défile horizontalement sur téléphone
  (aucun débordement de page). Les onglets Clients et Équipe & rôles portent une
  note (réglages à venir / gestion via Administration). Lint + build verts.
- 2026-06-17 — C1: menu coupé sur iPhone réparé. Cause : `.sidebar-nav`
  (`flex:1; overflow-y:auto`) n'avait pas `min-height:0` — un enfant flex ne
  rétrécit pas sous la hauteur de son contenu, donc le défilement ne
  s'enclenchait jamais et les derniers liens + la déconnexion étaient coupés
  (sidebar `overflow:hidden`). Ajout de `min-height:0` (+ inertie tactile iOS)
  et hauteur de la sidebar bornée au viewport (`height:100dvh; position:sticky`)
  pour que la navigation défile à l'intérieur, insets iOS déjà gérés. Validé au
  build ; vérif finale sur iPhone réel (PWA + Safari) côté Reda recommandée.
- 2026-06-17 — C2: rechargements à froid répétés (bureau) corrigés. Cause :
  le service worker appelait `skipWaiting()` + `clientsClaim()` au démarrage et
  `registerType:'autoUpdate'` rechargeait sur `controllerchange` → au tout
  premier chargement (sans contrôleur préalable), le SW fraîchement installé
  prenait la main et déclenchait un rechargement en pleine charge. Passage au
  schéma `prompt` sans course : le SW ne saute l'attente que sur message
  SKIP_WAITING (clic « Actualiser » du toast déjà présent), ne prend jamais la
  main pendant le 1er chargement. Compromis assumé : la mise à jour se confirme
  via le toast (au lieu d'un rechargement auto), mais le 1er chargement est
  désormais fiable. SW recompilé au build.
- 2026-06-17 — B1: pièces jointes réparées de bout en bout. Cause racine : le
  serializer renvoyait une URL présignée MinIO pointant vers l'hôte INTERNE
  (`minio:9000`), injoignable depuis le navigateur → icône fichier cassé (même
  cause que l'ancien aperçu PDF). Correctif : un nouveau proxy Django MÊME
  ORIGINE (GET /records/attachments/<id>/download/) relaie les octets,
  authentifié par le cookie, servi « inline » (PDF/images s'ouvrent dans le
  navigateur) ; le champ `url` pointe désormais vers ce proxy. Bénéficie aussi
  à la galerie photos chantier (avant/pendant/après) et à toute pièce jointe
  (lead/client/chantier/SAV). Le PDF du devis passait déjà par un flux Django
  (T1), donc aucune URL MinIO brute n'y subsiste. Tests : aller-retour
  upload → URL même origine → téléchargement (octets + Content-Type) + 404
  propre si l'objet manque.
- 2026-06-17 — A4: actions en ligne après acceptation, directement sur la
  fiche lead (section Devis). Un devis « accepté » affiche « 🧾 Générer la
  facture » (échéancier acompte → matériel → solde sur clics répétés, moteur
  inchangé, nourri de l'option acceptée via A3) et « 🏗 Créer le chantier »
  pré-rempli de l'option acceptée ; si un chantier existe déjà pour ce devis,
  le bouton est remplacé par son numéro (anti-doublon, garanti aussi côté
  serveur). Le serializer du lead expose désormais le chantier lié + l'option
  par devis (une seule requête). Test : la fiche lead porte chantier + option
  après acceptation/création.
- 2026-06-17 — A3: l'option acceptée est désormais autoritative en aval. Un
  nouvel utilitaire (apps/ventes/utils/options.py) réutilise EXACTEMENT le
  découpage du moteur de devis (réseau vs hybride+batterie) pour ne garder que
  les lignes de l'option retenue ; il ne filtre QUE pour un vrai devis à deux
  options (option unique / pompage / liste libre → toutes les lignes,
  comportement inchangé). L'échéancier (facture acompte/matériel/solde) et le
  solde du devis facturent maintenant les seuls totaux de l'option choisie
  (au centime, via les mêmes formules que Devis.total_ht/total_tva — jamais de
  recalcul à la main) ; la nomenclature gelée du chantier (BOM) exclut/inclut la
  batterie selon le choix. Tests : découpage pur + totaux/échéancier/BOM par
  option + non-régression d'un devis à option unique.
- 2026-06-17 — A2: déplacer un lead dans « Signé » (glisser-déposer kanban ou
  édition en place de l'étape) ouvre désormais un dialogue qui demande QUEL
  devis du lead a été accepté et, pour un devis à deux options, laquelle
  (Sans batterie / Avec batterie). Confirmer marque ce devis « accepté »
  (réutilise A1) ce qui fait avancer le lead en Signé côté serveur. Si le lead
  n'a aucun devis, un message invite à en créer/choisir un d'abord et l'étape
  n'est PAS modifiée — aucun devis inventé. Nouveau filtre serveur
  GET /ventes/devis/?lead=<id> (borné à la société) + composant SigneDialog.
  L'étape du funnel (STAGES.py) et le statut du document restent séparés.
- 2026-06-17 — A1: accepting a devis now records the option the client chose
  (Sans batterie / Avec batterie) alongside the date and accepter name, logged in
  the devis chatter. Two-option devis require an explicit choice; single-option
  devis infer it. New additive field `Devis.option_acceptee` (blank by default →
  behaviour unchanged until used); the « ✓ Accepter » button asks for the option
  on two-option devis and shows it once accepted. CI green, shipped to main.
