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
## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)
- [ ] **G23.** Select, Combobox/autocomplete (rebuild AssigneePicker and ProduitPicker on it), MultiSelect, with async search + empty/loading.
- [ ] **G24.** Date picker, Date-range picker, Time picker (the last for relance scheduling).
- [ ] **G26.** File upload / dropzone (rebuild AttachmentsPanel + the OCR upload flows) with progress, type/size validation, and reliable open/download (this also resolves the Group B attachment bug at the component level).
- [ ] **G27.** Form system: labels-above layout, sectioned forms, inline field validation + cross-field validation, required markers, an error summary, a dirty-state guard ("unsaved changes — leave?"), and a sticky save/cancel action bar (especially on mobile).
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
- [ ] **P69.** Document the token system in one reference file; save before/after screenshots of key screens to docs/ui-redesign/.

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

- [ ] **D4 — Roles & permissions editor (on the existing roles app).** Grant/restrict
  **per module and action**. **Buy prices and margins visible to owner only by default.** Ship
  a **safe default role set** (owner / commerciale / technicien / viewer) so **current access
  is unchanged**. Add **record-level scoping where feasible**. Margins/buy-price
  (`Produit.prix_achat`) must remain generator-only and never reach any PDF/client output.
  _(2026-06-17 — STOP-AND-ASK : changement d'autorisations/RBAC = nouvelle
  architecture, aligné sur le GATED G4 de PLAN.md ; laissé `[ ]`, à traiter sur
  décision du founder. D1–D3 et D5 restent constructibles.)_

### Group E — End-to-end (E2E) browser test suite covering every screen flow

---

## DONE LOG (agent appends one plain-language line per completed task)
