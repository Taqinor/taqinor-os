# Taqinor OS — Build Plan & Progress

This file is the **single source of truth** for the Taqinor OS build backlog and the
**memory between Claude Code sessions**. Each run first works through EVERY unchecked task in `docs/PLAN2.md` (if that file exists) from top to bottom — not just one — ticking each off as it lands, then does the same for this file, and only stops when both queues are clear (or a usage limit pauses it, in which case re-running resumes from the next unchecked task). The next session reads this file and
continues. Nothing relies on the agent's own memory — the file on disk is the memory.

---

## HOW TO RUN (read this every session)

1. **Read this whole file.**
2. **Drain the WHOLE queue, PLAN2 first — never just one task.** Check `docs/PLAN2.md` FIRST:
   work through EVERY pending `[ ]` task there that isn't gated/blocked — following PLAN2.md's
   own rules, which are the same as this file's — then drain this file's **BUILD QUEUE** the
   same way. Process EVERY unchecked `[ ]` task (not `[x]`, not `[SKIP]`, not `[BLOCKED]`);
   ignore the GATED and MANUAL sections entirely. Build independent tasks (and independent
   groups of tasks) **in parallel with subagents, each in its own isolated git worktree** so
   two never edit the same files at once; run tasks that depend on each other, or that touch
   the same files, in sequence — derive this ownership from the real code, not from guesses.
3. **Verify each task isn't already built — never trust these ticks or prior reports.**
   Inspect the actual repo and the deployed app. If a task already exists and works, mark it
   `[x] (already present)`, add a line to the DONE LOG, and move on to the next `[ ]` task.
4. **Build each task completely, with tests, and land it to `dev` the moment it's done.** Obey
   every STANDING RULE below. As each task finishes: commit it to `dev`, flip it to `[x]`, and
   append one dated plain-language line to the DONE LOG — so an interrupted run never loses
   finished work and re-firing resumes from the first still-unchecked task. Then **immediately
   continue to the next `[ ]` task. Do NOT merge after each task.**
5. **CI runs ONCE at the end, over the whole batch.** The four required checks must pass:
   backend-lint, backend-tests **with MinIO** (so PDF/storage tests actually run, including the
   PDF page-count guardrails), frontend-lint, and the stage-name check. When all four are
   green, **self-merge `dev` → `main` exactly once** (a single merge commit, history preserved,
   0 approvals). **Merging to `main` AUTO-DEPLOYS to api.taqinor.ma on its own** — the
   production server polls `main` about once a minute and runs the full deploy (rebuild +
   migrations + role sync + nginx/Caddy reload + the mandatory PDF pre-warm). **You do not run
   any deploy command.** `powershell -File scripts\deploy-prod.ps1` still works as a **manual
   fallback** from a PC if ever needed.
6. **Skip-and-note blockers, never stall.** If a task hits a blocker (a destructive migration,
   a paid/external dependency that isn't pre-approved, an auth or cost change, a brand-new
   architectural component, a conflict with a non-negotiable rule, or a real decision): do
   **not** guess and do **not** stall. Mark it `[BLOCKED: <one-line reason>]`, move it to the
   GATED section, and continue with the remaining tasks. A single blocked task must never halt
   the run.
7. **STOP only when** the queue is drained (no buildable `[ ]` task remains in `docs/PLAN2.md`
   then this file), a usage/length cap pauses the run (fine — the plan is idempotent;
   re-firing resumes from the first still-unchecked task), or every remaining task is blocked.
   Then **report once**, in plain language only — no diffs, no commit hashes: every task that
   shipped, what was skipped and why, and exactly what Reda must click/type (with menu paths).

**Run from anywhere — web or phone.** Because `main` auto-deploys itself, a task can be run
from Claude Code on the web or from the phone with no PC involved. **One-line starter** to
paste into a fresh cloud session:

> Read `docs/PLAN.md` top to bottom. Work through EVERY `[ ]` task — **first** `docs/PLAN2.md` (if it exists), **then** this file's BUILD QUEUE. For each: verify it isn't already built, build it with tests, commit it to `dev`, tick it `[x]`, add a dated DONE LOG line, then continue to the next — build independent tasks in parallel (subagents in their own git worktrees) and coupled tasks in sequence. Skip-and-note any blocker (`[BLOCKED: reason]` → GATED) and keep going. At the very end, get the four required CI checks green over the whole batch (with MinIO) and self-merge `dev` → `main` exactly once (this auto-deploys — do not run any deploy command). Report once, in plain language. Do not stop after one task and do not merge per task.

---

## STANDING RULES (every task obeys these)

- **One run = the whole queue, not one task.** Give each independent task its own subagent in its own git worktree so each subagent's context stays small and focused and two tasks never edit the same files at once; run tasks that depend on or overlap each other in sequence. Never stop after a single task. CI runs **once** over the whole batch and the run self-merges `dev` → `main` **exactly once** — no per-task merge. (Human-review PRs are still not wanted — the run self-merges its own green work.)
- **Verify against real code first. Never trust prior reports.** (Round 1 reported a preview
  fix that was never real, because that session's CI was silently broken.)
- **Additive only.** New tables / nullable columns / new defaults. **Never** a destructive
  migration (no dropping columns/tables, no deleting rows). If one is needed → `[BLOCKED]`.
- **Do not touch the DEBUG setting.** It is ON by Reda's explicit decision for the trial.
- **Do not redesign the PDFs.** Keep the existing WeasyPrint engine and the `PDF_ENGINE=legacy`
  fallback. (A full document redesign is a GATED item — see below.)
- **Never expose buy prices / prix revendeur / margins** in any client-facing output, link,
  message, or PDF. This is critical for the WhatsApp public links.
- **Do not change `STAGES.py` semantics.** Six canonical stages are a contract; "Perdu" is a
  boolean flag, never a stage.
- **Keep the contact form parked OFF.**
- **Multi-tenant:** every new model carries a `company` FK, filtered querysets, and a
  server-forced company. No client-supplied company is ever trusted.
- **All new user-facing text in French.** (Code/identifiers in English.)
- **New settings default to today's exact behavior** — nothing changes until Reda edits it.
- After merge, **deploy**, then **one plain-language report**.

**Pre-approved dependencies (do NOT treat as blockers):** `openpyxl` (real .xlsx) and
`vite-plugin-pwa` (build-time dev dependency for the PWA). Anything else new → `[BLOCKED]`.

**Status legend:** `[ ]` to do · `[x]` done · `[SKIP]` not needed / already present ·
`[BLOCKED: reason]` needs a decision (moved to GATED).

---

## ALREADY LIVE — do not rebuild (verify if unsure)

As reported in the build logs (treat as "very likely present, confirm before assuming"):
production on Hetzner at **api.taqinor.ma** (cx23, daily backups, deploy via
`scripts\deploy-prod.ps1`); multi-tenant ERP monorepo; CI now genuinely green **with MinIO**.

- **CRM:** Odoo-style multi-view (kanban default / liste / calendrier / graphique), full solar
  lead record, Historique chatter, lead-primary quoting, per-mode-gated "⚡ Devis auto",
  automatic stage movement, lead↔devis links, real `perdu` flag, reordered lead form,
  Activities + "Mes activités", Pièces jointes, employee avatars, lead routing/assignment,
  employee management, **Doublons workspace + N-way group merge**.
- **Quote generator:** three markets (résidentiel / industriel-commercial étude / agricole
  pompage), simulator-exact screen, prix/kWc, internal margin indicator, **reads saved
  settings** (validité, heures de pompage).
- **Per-line TVA** (panels 10% / else 20%), PDF suite (premium / one-page / étude), payment
  terms by mode, client ICE, seller legal IDs, unified warranties.
- **Invoicing:** Devis→Facture installment factures d'acompte, manual payments, running solde,
  per-line TVA on invoices, **Avoirs** (credit notes), **Relances/Impayés** + balance âgée +
  relevé client.
- **Chantier/Installation** module (lifecycle, interventions, mise en service, planning),
  **Equipment registry** + warranty clocks + "Expirant bientôt", **SAV tickets** (warranty-aware).
- **Stock:** catalogue + Pompage category, Category→Brand redesign, warranties populated.
- **Settings:** Société/Identité + Moroccan legal IDs, Devis (payment terms, validité,
  heures de pompage, prefixes), TVA, CRM tags & motifs de perte, niveaux de relance.
- **Sending:** **"Envoyer par WhatsApp"** on leads/factures/relances, with tokenized public
  PDF links and editable FR + Darija templates (Paramètres → Messages WhatsApp).
- Login is the front door (landing at `/landing`); website → CRM lead pipe live end-to-end.

---

## BUILD QUEUE (do top-down — highest value first)

### T1 — Fix the devis preview (PRIORITY 1, blocks daily quoting) — [x] (already present)
**Symptom (confirmed by screenshot):** on a lead's devis preview panel (titled "Devis — <name>"
with Premium / 1 page / Inclure l'étude toggles, an "Édition complète" button, and a
"Télécharger le PDF" button), the PDF area shows a generic **broken-file icon** instead of the
PDF. Reproduced on quote **DEV-202606-0024** in Premium. The panel UI renders fine; only the PDF
inside fails. A prior session *claimed* to fix this but its CI was broken, so re-diagnose from
scratch — do not assume any previous change is present or correct.
**Do:**
1. Reproduce with DEV-202606-0024 in Premium, then also the 1-page format and the "Inclure
   l'étude" variant.
2. Check the **actual HTTP response (status + content-type)** of the PDF-serving endpoint for
   this quote, for Premium / 1-page / étude.
   - If it errors or returns non-PDF: find why (premium 3-page guardrail, missing data,
     font/chart render failure, etc.) and fix it so the PDF generates. If a quote genuinely
     cannot render, the panel must show a **clear French error** explaining why — never a silent
     broken icon — and the report lists which conditions fail.
   - If it returns a valid PDF but the panel won't show it: fix the inline render. The panel must
     **fetch the PDF authenticated, via the same working path as "Télécharger le PDF", and
     display it from a blob URL** — not a raw URL that loses auth or content-type.
3. Make **both** the inline preview **and** the download work, for all three formats.
4. **Regression test that actually catches this:** assert the preview path returns a valid PDF
   blob AND the preview component renders it — not merely a 200 (the old test missed this). It
   must run against MinIO.
5. **Cache-busting:** ensure the frontend build output is content-hashed/fingerprinted so a fresh
   deploy can never serve stale JS/CSS (the "deployed but old version still shows" problem recurs).
**Acceptance:** open DEV-202606-0024 → the PDF renders in the panel AND downloads, in Premium,
1-page, and étude.

### T2 — Installable PWA / "app version" (like Odoo on mobile) — [x] (already present)
Make the OS installable so Reda and Meryem can "Add to Home Screen" and run it full-screen like a
native app. The "app" is the existing web app — no second codebase. **OS React app only**, not the
Astro marketing site under `apps/web`.
**Do:**
1. Add `vite-plugin-pwa`. Configure `registerType: 'autoUpdate'` with `skipWaiting` +
   `clientsClaim` so an installed app updates to the newest deployed version automatically on next
   open, **without a manual hard refresh**. Fallback: a small French "Nouvelle version disponible —
   actualiser" toast if an update is pending.
2. Web manifest: name "Taqinor OS", short_name "Taqinor", a French description, display
   "standalone", scope "/", start_url "/" (keep current behavior: login when signed out, home when
   signed in), lang "fr", theme/background colors from the app's navy brand tokens.
3. Icons from the existing Taqinor logo asset in the repo: 192×192, 512×512, a 512×512 maskable
   with safe padding, and a 180×180 apple-touch-icon. If no square source exists, center the logo
   on the brand background. Reference in the manifest and index.html.
4. iOS head tags in index.html: `apple-mobile-web-app-capable=yes`, status-bar-style,
   `apple-mobile-web-app-title "Taqinor"`, apple-touch-icon link, theme-color meta.
5. Service worker: precache the app shell + a small branded French offline fallback page. Do **not**
   cache API responses and do **not** attempt offline data entry — the app stays online.
6. French install helper: on Android capture `beforeinstallprompt` → "Installer l'application"
   button (user menu or a small dismissible banner) that triggers the native prompt; on iPhone show
   "Sur iPhone : appuyez sur Partager puis 'Sur l'écran d'accueil'". Hide once installed
   (display-mode: standalone) or where unsupported.
**Acceptance:** installs on Android Chrome and iPhone Safari; launches full-screen; a new deploy is
picked up automatically.

### T3 — Bulk actions on leads — [x]
Multi-select leads in **both** the list and the kanban (checkboxes), with a selection toolbar
showing the count. Bulk actions: reassign responsable; add a tag; remove a tag; change stage
(respect the no-going-backwards funnel rule, never auto-move a Perdu lead, reactivate Froid — same
rules as a single edit); set/clear relance date; flag/unflag Perdu with a reason; archive/unarchive;
admin-only delete (confirmed dialog, blocked with a clear French message if it would orphan linked
quotes/invoices, logged); export selection to .xlsx. Every change writes a per-lead Historique entry
marked « en masse ».

### T4 — Inline list editing (Odoo-style edit-in-place) — [x]
Edit a field without opening the record: on the **leads list** — stage, responsable, relance date,
priorité, tags; on the **products list** — sell price, quantity, category. Each edit saves just that
field, validates server-side, logs to Historique where applicable. Skip any field risky to edit
inline and note it.

### T5 — Global search + in-app notifications — [x]
- A single **global search box** in the top bar across leads, clients, quotes, invoices, chantiers,
  equipements, SAV tickets; results grouped by type; click to open.
- An **in-app notification bell** (no email): overdue activities, warranties expiring within 90 days,
  overdue/unpaid invoices — counts + a clickable list.

### T6 — Unlock the deferred settings (safely) — [x]
Tags and motifs de perte are already editable — leave them. Add:
- Make **Canaux / Sources de lead** editable (add / rename / reorder). The key `site_web` is used by
  the website form webhook: **protect it from rename and deletion** so the pipeline never breaks.
  Also prevent deleting any value currently in use.
- Make **Types d'intervention** editable with the same safeguards.
- Promote **Marque (brand)** from free text to a real model; backfill existing brand strings; product
  form uses a select with free-add.
- Audit hard-coded **ROI constants** (ONEE tariff assumptions, irradiance/ensoleillement) and surface
  them as editable settings. Defaults must equal today's exact values.

### T7 — Quote expiry (on-the-fly) + pipeline-value dashboard — [x]
- **Expiry:** a quote shows « Expiré » when today is past its validity date (creation + the
  "validité du devis" setting). **Compute on the fly at read/display time — no scheduler, cron, or
  background job, no daily command.** Never move the lead backward; just reflect it visually and in
  filters/queries.
- **Pipeline-value dashboard:** total MAD by stage, a simple weighted forecast, count + value of
  quotes by status, win/loss by motif de perte. Read-only; respects the shared filter bar.

### T8 — Bulk product / catalogue editing — [x]
Multi-select products → bulk: change sell price (% or fixed — sell price only, never alter
buy-price-visibility rules), set warranty (`garantie_mois` / `garantie_production_mois`), reassign
category and/or brand, export selection to .xlsx. Logged.

### T9 — Reusable import + Excel export everywhere — [x]
`openpyxl` is pre-approved.
- A **reusable CSV/XLSX import** for leads, clients, and products: a **10-row dry-run** showing
  column→field mapping (and what didn't map) for approval before the full batch, origin-tagged,
  nothing overwritten silently. Keep this **separate** from the one-off 619-lead Odoo migration.
- An **"Exporter Excel" (.xlsx)** button on every list view (leads, clients, quotes, invoices,
  products, chantiers, equipements, SAV tickets) that respects current filters.

### T10 — Quote revisions / versioning — [x]
Let a sent quote be **revised into a new version** (v2, v3…) that keeps the prior versions readable,
without breaking the lead↔devis links or the numbering scheme. The active/latest version is clearly
marked; superseded versions are read-only with a "remplacé par" link. Additive only.

### T11 — User-defined custom fields — [x]
Build the **mechanism** (not the specific fields — those are Reda's choice). Let an admin add a custom
field to a module (start with leads, then clients/products), choose its type (text, number, date,
choice, boolean), make it appear on the form and optionally in lists/filters, hide standard fields,
and restore-to-default. Scope question on creation ("appliquer à tous ?"). Additive; if it would need
a destructive migration, `[BLOCKED]`. If `docs/erp-data-model-proposal.md` exists, use it as input.

### T12 — Accountant export: journal des ventes + TVA summary — [x]
A periodable (month/quarter) **.xlsx export for the comptable**: all issued invoices with their
per-line TVA, plus a **TVA summary split 10% / 20%** reconciled to the centime, and totals HT/TVA/TTC.
Read-only; openpyxl. (This is also direct groundwork for the DGI e-invoicing mandate — see GATED.)

### T13 — Reports hub: sales reports — [x]
A **"Rapports"** section. Start with **sales/pipeline**: leads & conversion by stage (funnel),
quotes by status and value, sales by responsable / by canal / by period, win-loss by motif de perte.
Read-only, respects filters, each report exportable to .xlsx.

### T14 — Reports hub: stock reports — [x]
Add to "Rapports": **stock valuation** (sell + buy, buy kept internal/non-client-facing), movement
history report, low-stock list, by category/brand. Exportable to .xlsx.

### T15 — Reports hub: service reports (chantier + SAV) — [x]
Add to "Rapports": chantier planning load + completion timing, technician activity, SAV open vs
resolved + resolution time, equipment warranties expiring. Exportable to .xlsx.

### T16 — Recurring maintenance contracts — [x]
A `ContratMaintenance` model (additive) attached to a chantier/client: a preventive-visit
subscription on a schedule that **generates SAV tickets when a visit is due, computed on the fly /
at read time (consistent with T7 — no scheduler)**; a list view and an "à venir" view.

### T17 — (optional, lower priority) Discount approval guard — [x]
When a quote discount exceeds a configurable threshold, require an admin/owner approval before the
quote can be marked « envoyé » (protects margin once Meryem works quotes solo). Configurable in
Paramètres; default threshold = off so nothing changes until Reda sets it.

---

## BUILD QUEUE — N1–N102 (post-sale, procurement, Moroccan billing, editability, platform)

Re-homed from the recovered `docs/PLAN2.md` (the overflow queue) on 2026-06-16. The ticks
below were **re-verified against the live `main` code**, task by task — the recovered file's
own ticks were written on a branch that never merged and were unreliable. `[x]` here means the
feature genuinely exists **and is usable** on `main` today; `[ ]` means missing, backend-only
with no usable screen, or only partially meeting the spec. Same STANDING RULES as the rest of
this file apply (additive only, multi-tenant, French UI, STAGES.py pipeline never edited, buy
prices never client-facing). **Reconciliation result: 30 of 102 done, 72 open.**

Two tasks have a working backend on `main` but no usable screen yet — flagged inline as
_Backend ready, frontend pending_: **N11** (supplier-PO management page) and **N29** (facture
conformity warning banner).

### Chantiers / projets & execution
- [x] N1 — Chantier (projet) object created from an accepted devis, linked to that devis, the lead and the client; carries client identity, full site address + GPS from the lead, a system summary (kWc, type d'installation résidentiel/industriel/agricole, components + bill of materials copied from the devis), planned install date, actual install date, assigned installer from the employee list (default Reda), estimated & actual labour-days, and a chatter + audit log reusing the existing activity-log pattern; uses its OWN ordered chantier status field (Signé, Matériel commandé, Planifié, En cours, Installé, Réceptionné, Clôturé) completely separate from and never modifying the lead pipeline STAGES.py contract.
- [x] N2 — Chantiers list view + kanban grouped by chantier status, same visual language and same drag-to-change-status + reassignment behaviour as the lead kanban; each card shows client, ville, kWc, planned install date, installer, status.
- [x] N3 — "Créer chantier" action on a devis and on a lead that creates a chantier from that devis in one click (copying client, site, system summary, bill of materials); prevent more than one chantier per devis.
- [x] N4 — Per-chantier configurable execution checklist; default steps editable in Paramètres (default: matériel reçu, structure posée, panneaux posés, onduleur raccordé, mise en service, photos prises, PV de réception signé); record per step done/by whom/when (existing audit pattern); compute chantier completion percentage from the checklist.
- [x] N5 — Photo & file attachments per chantier (reuse existing file-attachment feature) grouped into avant / pendant / après with a simple gallery view per chantier.
- [x] N6 — Chantier timeline view per job showing signed, material-ordered, planned & actual install, commissioning, and closure dates on one screen.
### Parc installé (installed-systems asset base)
- [x] N7 — Système installé (parc installé) record auto-created when a chantier reaches Réceptionné, capturing client, site address + GPS, kWc, type d'installation, installed components (brand/model + any captured serials), installer, commissioning date, link back to chantier/devis/client, active by default.
- [x] N8 — Parc installé list + map view, searchable/filterable by client, ville, brand, capacity band, install year — the canonical base for warranty/maintenance/monitoring.
- [x] N9 — Optional per-component serial-number capture on the relevant chantier checklist step so serials flow into the Système installé record; never block checklist completion when serials are empty.
- [x] N10 — Per-installed-system detail screen showing components, warranties, linked SAV tickets, maintenance contracts, monitoring status — the single client-asset hub.
### Procurement & inventory
- [x] N11 — Bon de commande fournisseur (purchase order): select supplier from existing supplier list; lines of SKU/quantity/buy price; statuses Brouillon/Envoyé/Reçu; partial receptions; on reception increase stock the same way Bill OCR does; buy prices internal & off every client-facing document; race-safe gapless auto-numbering.
- [x] N12 — Bon de commande PDF for the supplier (French): SKU, description, quantity, unit buy price, company identity from Paramètres; internal-only, never sent to clients.
- [x] N13 — Besoin matériel view per chantier listing components needed from its source devis with current stock availability per item, flagging shortfalls, plus one-click action drafting a bon de commande for the shortfall lines to the relevant supplier.
- [ ] N14 — Stock reservation: creating a chantier reserves required quantities against stock with a reserved-vs-available indicator per SKU; reaching Installé consumes reserved stock; cancelling/closing a chantier releases the reservation; stock view + low-stock alerts account for committed-but-not-consumed quantities.
- [x] N15 — Multi-location stock (at least main dépôt + camionnette), transfers between locations with a transfer record, per-location quantity visibility; default all existing stock to main dépôt so current behaviour is unchanged.
- [x] N16 — Inventory count & adjustment: admin records a physical count per location and posts the difference as an adjustment with a reason + audit entry.
- [x] N17 — Per-SKU multiple-supplier price lists (buy prices from several suppliers + last-purchase date); surface the cheapest current supplier when drafting a bon de commande; keep buy prices internal.
- [x] N18 — Stock valuation per location using average cost from purchase history, shown only in internal views.
- [x] N19 — Supplier return (retour fournisseur) record for defective/wrong items, decreasing stock and linking to the originating bon de commande; internal use.
- [ ] N20 — Optional QR/barcode labels for stock SKUs and installed systems; printable labels; chatbot or search field resolves a scanned code to the SKU or Système installé.
### Post-sale / client-facing documents
- [x] N21 — PV de réception (procès-verbal de réception des travaux) PDF from a chantier (French, existing PDF engine + company identity): client/site, system summary (kWc/components/type), commissioning date, installer, signature block for client & installer with "Bon pour accord" manuscrit line, checklist-completion summary; no buy prices.
- [x] N22 — Bon de livraison (delivery note) PDF from a chantier or devis (French): delivered items + quantities, delivery date, client signature block; client-facing, no buy prices.
- [x] N23 — Client handover pack PDF (dossier de remise) per chantier (French): system summary, warranty terms per installed component (reuse devis warranty texts), basic operating/maintenance guidance, contact details; client-facing, no buy prices.
- [x] N24 — Attestation generator (French) from a chantier or installed system (e.g. attestation d'installation, attestation de fin de travaux) using configurable templates + company identity; client-facing, no buy prices.
### Devis acceptance trigger
- [x] N25 — Mark a devis accepted on a chosen date with the accepting person's name captured + recorded in the devis chatter, so acceptance is the explicit trigger enabling chantier creation.
- [ ] N26 — Lightweight client acceptance capture on a devis (typed name + date + "Bon pour accord" confirmation) recorded on the devis — not a cryptographic e-signature, no external provider — producing a regenerated acceptance copy of the devis PDF stamped "accepté le <date> par <nom>".
### Moroccan legal billing & compliance
- [x] N27 — Full set of Moroccan legal company identifiers in Paramètres company identity (raison sociale, adresse complète, IF, ICE, RC + tribunal city, patente/taxe professionnelle, RIB); stamp the applicable subset automatically onto every devis, facture, avoir, bon de livraison, PV de réception.
- [x] N28 — Client ICE field on the client record, surfaced on devis & factures; carry the client ICE from a devis through to the facture without re-entry; non-blocking reminder on B2B documents when client ICE is missing.
- [x] N29 — Facture conformity check verifying every Article 145 CGI mention (seller identity/identifiers, client identity + ICE for B2B, sequential invoice number, emission date, delivery/prestation date, per-line description/quantity/unit-price-HT/TVA-rate/line-total-HT, totals HT/TVA/TTC, payment terms & mode); warn on any missing mention before finalising without blocking an override.
- [x] N30 — Explicit delivery-or-prestation date + payment-terms-and-mode fields on factures; default the delivery date from the linked chantier commissioning date when available.
- [x] N31 — Sequential, continuous, gap-free invoice/quote numbering per document type with no duplicates; surface any detected gap to an admin (build on existing race-safe auto-numbering).
- [x] N32 — Documents archive view per client and per chantier gathering every generated devis/facture/avoir/bon de commande/bon de livraison/PV in one place (10-year retention), stored in existing object storage.
- [x] N33 — Facture d'acompte + facture de solde workflow: chantier/devis generates a deposit invoice for a configurable percentage on signature and a balance invoice on delivery (balance auto-deducts amounts already invoiced as acompte); both fully conformant Moroccan factures with sequential numbering; existing avoir feature remains for credits.
- [x] N34 — Configurable default acompte percentage + default payment terms in Paramètres to prefill new acompte invoices, editable per chantier.
- [x] N35 — Échéancier / installments option on a facture splitting TTC into dated instalments, each marked paid/pending, feeding the existing payment-follow-up + aged-receivables system so reminders work per instalment; no external financing provider, no bank integration.
- [BLOCKED: devis RIB/payment block is a hardcoded literal in the premium PDF engine — rule #4; same conflict as D2/N60. Facture RIB already prints from Paramètres.] N36 — RIB + payment-instructions block on facture and devis PDFs, sourced from Paramètres.
- [x] N37 — Per-line TVA on devis & factures with an editable TVA rate per line defaulting to a single configurable rate in Paramètres (current behaviour unchanged out of the box); totals chain HT → TVA per rate → TTC; per-rate VAT breakdown in PDF only when >1 rate; configurable TVA-exemption mention when a line is exempt; never hardcode which rate applies to which product.
- [x] N38 — Local structured-invoice export for factures: UBL 2.1-shaped XML generated & stored locally including ICE/IF/RC from Paramètres + per-line VAT, clearly marked draft preview, no external DGI/clearance endpoint, no credentials — groundwork only.
- [x] N39 — Clearance-status placeholder field on factures (Non soumise/Soumise/Validée), purely informational and manually set, so the data model is ready for a future DGI flow without any external call today.
### Loi 82-21 / Article 33 regulatory
- [x] N40 — Dossier réglementaire section on each chantier for loi 82-21 self-production: régime field (déclaration <11 kW raccordée BT / accord de raccordement / autorisation ANRE au-delà de 1 MW), statut field (À déposer/Déposé/Approuvé/Compteur posé), reference numbers, key dates, responsible operator, attached documents via existing file-attachment feature.
- [x] N41 — List + filter of chantiers and installed systems by regulatory dossier régime & statut so outstanding declarations/approvals are visible in one place.
- [x] N42 — Article 33 régularisation flag + status on installed-system and lead records, with a filter to find all records needing/undergoing regularisation.
- [x] N43 — Configurable régime-suggestion: given a chantier kWc + grid-connection type, propose the likely loi 82-21 régime as an overridable default; thresholds editable in Paramètres.
### SAV / maintenance / warranty / monitoring
- [x] N44 — SAV ticket object linked to a Système installé (and thus client + chantier): type de panne, priorité, canal d'ouverture, date d'ouverture, statut (Ouvert/En cours/Résolu/Clos), assigned technician (default Reda), description, resolution log (activity pattern), time-to-resolution computed on closure; SAV list + kanban grouped by statut.
- [x] N45 — SAV intervention report PDF on closing a ticket (French): reported issue, diagnosis, work done, parts used, client signature block; client-facing, no buy prices.
- [ ] N46 — Parts consumption on a SAV ticket optionally decrements stock for parts used and records them on the intervention report; buy prices internal.
- [ ] N47 — Contrat d'entretien object linked to one or more Systèmes installés (start date, duration, visit frequency, price, renewal date) auto-generating a schedule of upcoming maintenance visits; surfaces upcoming/overdue visits in a list + on the calendar; a completed visit generates a short maintenance report PDF (French, no buy prices); flags contracts approaching renewal.
- [x] N48 — Warranty tracking on each Système installé and components: store install date + warranty duration per component (default from configured warranty texts), compute warranty end dates, "Garanties qui expirent" view, record warranty claims per component with outcome for an auditable service history.
- [x] N49 — Recurring-revenue view summarising active contrats d'entretien, monthly/annual value, upcoming renewals, lapsed contracts.
- [ ] N50 — Monitoring-integration framework with a swappable provider interface, starting with a Huawei FusionSolar connector that (given per-system credentials in config) pulls recent production data; admin enables it per system; no-ops safely when no provider is configured.
- [ ] N51 — Per-installed-system production view showing recent yield pulled by the monitoring framework when configured, with a manual-entry fallback.
- [ ] N52 — Configurable under-performance rule that (when monitoring data exists) flags a system producing below an expected threshold and optionally auto-creates a SAV ticket; threshold + auto-ticket behaviour editable in Paramètres.
- [BLOCKED: needs production data from the monitoring framework (N50, gated — external service/credentials).] N53 — Client energy-yield report PDF (French): a system's production over a period, estimated bill savings, CO2 avoided; client-facing, no buy prices.
### Editability layer (Paramètres hub)
- [x] N54 — Expand Paramètres into a structured settings hub with grouped sections (company identity & legal identifiers, quote/sizing parameters, TVA & billing, CRM reference data, chantier & checklist defaults, document & message templates, numbering sequences, pricing & tariff tables, warranty texts, roles & permissions, automation rules, notifications), each admin-editable and applied without a deploy; STAGES.py pipeline contract kept out of this surface entirely.
- [x] N55 — Admin audit of settings changes (who/what/when, existing audit pattern).
- [x] N56 — Make every reference list editable by an admin from Paramètres (CRM tags, lead sources/canaux, loss reasons, activity types, SAV panne types, chantier checklist steps, units of measure, supplier categories, document types) with add/rename/reorder/deactivate; never expose the STAGES.py pipeline as editable.
- [x] N57 — Deactivating a reference value preserves it on historical records and only removes it from new selections so reports stay consistent.
- [ ] N58 — Make chantier statuses, SAV statuses, and bon-de-commande statuses configurable in label & order from Paramètres while keeping their underlying state-machine semantics intact; never touch the protected lead pipeline.
- [BLOCKED: the editable text portions of client docs are hardcoded literals in the premium PDF engine — rule #4 forbids editing it.] N59 — Document-template editor in Paramètres for the editable text portions of client-facing documents (devis/facture/acompte/avoir/PV de réception/bon de livraison/handover pack/attestation): headers, footers, legal footnotes, CGV, quote-validity text, payment-terms text, with safe placeholders for company/client/system fields; core layout engine intact; buy prices impossible to insert.
- [BLOCKED: CGV + validity are hardcoded literals ("30 jours") in the premium PDF engine — rule #4; same conflict as D2. Validity duration is already editable in Paramètres, just not printed dynamically.] N60 — Editable conditions générales + configurable quote-validity duration applied to new devis, with the validity date printed on the devis PDF.
- [x] N61 — Message-template editor in Paramètres for WhatsApp/email/SMS templates (named templates, placeholders, a French default each).
- [ ] N62 — Editable numbering-sequence configuration per document type (devis/facture/acompte/avoir/bon de commande/bon de livraison/chantier/SAV): prefix, padding width, yearly-reset behaviour; engine still guarantees gap-free, non-duplicated sequences.
- [x] N63 — Editable pricing & sizing engine in Paramètres exposing today's implicit quote parameters (default margin/target price per kWc rules, default discount limits, sizing ratios used by auto-remplir, per-region production factors), editable & versioned; lossless typed-number behaviour preserved.
- [BLOCKED: per-tranche tariff tables change the calculation model (flat tariff is already editable from D5) — founder must validate the bracket scale first.] N64 — Editable ONEE electricity tariff tables + tranche thresholds in Paramètres used by the seasonal bill estimator and ROI calculation; current values seeded as defaults.
- [BLOCKED: there is no region field on a quote today; needs a founder-validated regional irradiation map + a new model (per D5).] N65 — Editable per-city/region irradiation & production-yield assumptions used to estimate annual production, seeded with Moroccan defaults, selectable on a quote.
- [ ] N66 — Configurable default lead responsable, default installer, default acompte percentage consolidated in one place.
- [BLOCKED: warranty texts are printed by the premium PDF engine (hardcoded) — rule #4 forbids editing it. Per-product garantie text already exists on the Produit model.] N67 — Editable warranty texts per product & per category in Paramètres (printed on devis & handover packs), current researched warranty texts seeded as defaults and used wherever warranties appear.
- [ ] N68 — Roles-and-permissions RBAC editor in Paramètres: define roles, grant/restrict per module & per action (view/create/edit/delete/export), restrict sensitive fields (buy prices, margins) to specific roles, safe default role set (owner/commerciale/technicien/viewer) so current access is unchanged, record-level rules limiting a user to their own assigned leads/chantiers when desired.
- [ ] N69 — Buy prices & internal margins governed by an explicit permission, visible only to roles Reda authorises, default owner-only.
- [x] N70 — Per-user activity & access view so Reda can see who did what.
- [x] N71 — Admin-defined custom-fields system from Paramètres (text/number/date/boolean/single-select/multi-select/file) on lead/client/chantier/devis/facture/installed-system, rendered generically on forms + available in search & export, values in a dedicated side store (not altering core schema or the migration chain). [extends T11]
- [ ] N72 — No-code automation-rules engine in Paramètres (if-this-then-that over the app's own events): triggers (lead stage change, devis accepted, chantier reaching a status, facture overdue, warranty nearing expiry, maintenance visit due, stock below threshold); actions (send WhatsApp/email/SMS from a template, create activity/task, assign a record, set a field, create a SAV ticket); rules editable/enabled/disabled, all runs logged; complements not duplicates n8n.
- [ ] N73 — Simple approval-step capability in the automation engine so selected actions (e.g. a discount above a configurable threshold) require owner approval before proceeding.
- [ ] N74 — Chantier/onboarding checklists fully configurable as named workflow templates in Paramètres, selected automatically by type d'installation.
### Notifications / dashboards / analytics
- [ ] N75 — Unified notification engine: in-app + (where configured) WhatsApp/email/SMS for key events (new lead assigned, devis accepted, chantier due to install, facture overdue, warranty expiring, maintenance visit due, stock low, SAV ticket opened/breaching target); per-user & per-event preferences in settings; in-app notification centre; reuse planned templates/channels.
- [BLOCKED: scheduled daily/weekly digest delivery needs a scheduler (G9, gated). On-demand summary data is now available via the N49/N80 insights endpoints.] N76 — Daily & weekly digest notification for Reda & Meryem (jobs to plan, quotes awaiting acceptance, overdue payments, due maintenance, open SAV), in-app and optionally WhatsApp/email.
- [x] N77 — Tableau de bord home view (French): pipeline value/count by stage, close rate by canal & source, signed kWc & revenue for current month/quarter, chantiers by status, aged-receivables summary (existing follow-up data), active maintenance contracts + upcoming renewals, open SAV count; plain cards + simple charts.
- [x] N78 — Job costing per chantier: realised margin from captured buy prices vs invoiced amounts; margin-per-job + margin-by-period views visible only to authorised roles.
- [BLOCKED: the "schedule a periodic export by email" half needs a scheduler + email provider (G9/G1, gated). Saved-view persistence deferred with it.] N79 — Saved-reports & custom-views capability: save filtered/grouped views of any major object, pin to dashboard, schedule a periodic export of a saved report by email when email is configured.
- [x] N80 — Business analytics section: lead-source ROI when ad-spend data is available, average time lead→signature and signature→commissioning, installed kWc over time, as simple charts.
### Import/export / search / calendar / map
- [x] N81 — Generic import-and-export framework (CSV & XLSX) for major objects (leads/clients/stock/suppliers/installed systems) with column mapping, mandatory 10-row dry-run preview before any full import, duplicate handling, audit per import; generalise the one-off Odoo lead import; real customer-data files never committed to the repo. [extends T9]
- [x] N82 — Per-object export to CSV/XLSX from every list view respecting the user's column & filter selection and role-based field permissions. [extends T9]
- [x] N83 — Global search across every object (leads/clients/devis/factures/chantiers/installed systems/bons de commande/SAV tickets/contrats d'entretien/regulatory dossiers) from one box with type-grouped results, respecting role permissions. [extends T5]
- [ ] N84 — Calendar/agenda view of planned installs, scheduled maintenance visits, SAV interventions, follow-up activities; filterable by assignee & type; drag to reschedule where it maps to an editable date.
- [ ] N85 — Map view plotting leads/chantiers/installed systems/scheduled visits by GPS or address, filterable by type & status, for planning site visits without heavyweight routing.
### Chatbot / integrations / API
- [ ] N86 — Extend the unified chatbot to read & act across all new objects (e.g. which chantiers à planifier, which garanties expire this quarter, which factures overdue, what production a named client's system did last month; open a SAV ticket, draft a BC for a chantier shortfall, schedule a maintenance visit), reusing the existing chatbot interface, respecting role permissions.
- [ ] N87 — Email integration to send client-facing documents & follow-ups via a configurable sending account (French templates, attach the relevant PDF, record what was sent on the client/document chatter); complements WhatsApp. [GATED-style: needs provider/cost decision]
- [ ] N88 — Inbound email capture attaching replies to the relevant client/chantier thread when a recognisable reference is present.
- [ ] N89 — Public REST API exposing core objects with token-based API keys managed in settings, scoped permissions, rate limiting, and webhooks on key events (new lead, devis accepted, chantier completed, facture paid).
### PWA / mobile / offline
- [x] N90 — Installable PWA with Chantiers/Parc installé/SAV/calendar/bon-de-commande screens phone-usable to the same standard as the lead screens; responsive, thumb-reachable primary actions. [extends T2]
- [ ] N91 — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception signature, syncing when back online.
- [ ] N92 — Push notifications to the PWA for high-priority events from the notification engine.
### Localisation / audit / security / data
- [ ] N93 — Full Arabic & Darija localisation as a selectable interface language with RTL layout support across the app, French default, English in code; client-facing document language selectable per client (facture/devis in French or Arabic).
- [ ] N94 — Translation-management surface in settings so interface strings can be reviewed/adjusted per language without a code change.
- [x] N95 — Comprehensive audit log across all objects (creates/updates/deletes + key actions, who/when), viewable & filterable by an admin, building the per-object chatter into a system-wide trail. [unified activity feed shipped with N70]
- [ ] N96 — Account security: optional 2FA, visible active sessions with revoke, forced credential-rotation flow; production DEBUG setting left unchanged.
- [ ] N97 — Configurable data export & backup action for the tenant's data (reversibility/retention), real customer-data exports kept out of the repo.
### Growth / multi-tenant platform
- [ ] N98 — Optional referral/parrainage program (referrer→referred-client links, configurable reward per converted referral, simple referral dashboard), toggle in settings.
- [ ] N99 — Optional sales-commission tracking (configurable commission per signed quote or per installed kWc for the commerciale), visible only to authorised roles.
- [ ] N100 — Build out multi-tenant operation on the existing tenant_id foundation (strict per-tenant isolation verification, tenant onboarding flow, per-tenant branding/white-label of client-facing documents, configurable per-plan feature limits, tenant-level billing).
- [ ] N101 — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup for design-partner installers.
- [ ] N102 — After the modules above are built, update the master project document + PLAN + DONE log in plain language to reflect the new post-sale, procurement/inventory, Moroccan billing/compliance, full-editability, and platform additions, noting which shipped and which were skipped.

---

## BUILD QUEUE — F1–F24 (field-execution & outillage module — added 2026-06-17)

Reda's "intervention" / field-execution module. **Build order = the order below** (outillage and
the intervention spine first, then the departure gate, then on-site capture, reconciliation, voice,
completion, and the advanced layer last). It is a big queue and **paces against the usage window** —
re-firing "work on the plan" after a cap resets resumes from the next unchecked task. Honour every
STANDING RULE plus the **module-specific constraints** below.

**MODULE CONSTRAINTS (in addition to the STANDING RULES):**
- The lead pipeline **`STAGES.py` stays a fixed CI contract** and is **never** made runtime-editable.
- The new Intervention **`statut` is its own separate state machine** that **never reads from or
  writes to `STAGES.py`** or to the **chantier status field**.
- **Buy prices and margins never appear on any client-facing document**, including the
  **compte-rendu d'intervention**.
- **Voice-memo capture, OCR, and AI photo-QA each add NO external credential and NO per-use cost by
  default**, and **no-op safely** until a provider is explicitly configured in Paramètres. The
  **transcription provider is left unconfigured** — a separate operator decision, added by **no**
  part of these tasks.
- **All photos, voice memos, GPS, and site data are real customer data** → object storage, **never
  committed to the repo**.
- **The production DEBUG setting is left exactly as configured — unchanged by these tasks.**
- **Reuse existing patterns**: file attachments / object storage, audit + chatter, kanban visual
  language + drag-to-change-status, the existing PDF engine, stock reservation + consumption,
  race-safe gapless numbering, Paramètres editability.
- **One session, dev → self-merge to main after tests pass — never split into review PRs.**

- [ ] F1 — **Outillage (équipement durable) catalogue**, kept completely separate from the consumable Stock SKUs. Each tool carries: nom, catégorie, asset tag, optional numéro de série, a current location chosen from the existing stock locations (dépôt + camionnette) plus an **En intervention** state, a statut (Disponible / En intervention / En réparation / Perdu), a purchase date, and an optional photo via the existing file-attachment feature. List view + filter by location and statut. Durable tools are tracked across dépôt, camionnette, and job sites **without ever being treated as sellable stock, consumed, or shown on any client-facing document**.
- [ ] F2 — **Reusable kits d'outillage** as named templates editable in Paramètres (seeded defaults: Kit pose structure, Kit raccordement électrique, Kit mise en service), each an ordered list of required tools drawn from the Outillage catalogue, selectable per type d'intervention. Seeded defaults support add / rename / reorder / deactivate like every other référentiel; deactivation preserves the value on historical records.
- [ ] F3 — **Intervention (sortie chantier) object** belonging to a Chantier (one chantier → several interventions). Carries: type (Pose / Mise en service / SAV / Visite), planned date, an assigned équipe of one+ employees (default = the chantier installer), an assigned camionnette, and **its own ordered `statut`** (À préparer / Prête / En route / Sur site / Terminée / Validée) that is **completely separate from and never modifies the chantier status field or the `STAGES.py` contract**. Chatter + audit log reusing the existing activity-log pattern; linked to its chantier, devis, client, and the site GPS pulled from the chantier.
- [ ] F4 — **Intervention list view + kanban grouped by intervention statut**, reusing the same visual language, drag-to-change-status, and reassignment behaviour as the existing lead and chantier kanbans. Each card shows client, ville, type, planned date, équipe, statut.
- [ ] F5 — **Liste de préparation** generated per intervention: pulls matériel from the chantier bill of materials (copied from its devis) and outils from the selected kit d'outillage. Every matériel line shows required quantity + a **chargé** checkbox; every outil shows a checked checkbox; computes a **préparation completion %**; exposes a **« Tout est chargé »** confirmation that must be set before the intervention can move from À préparer to Prête/En route. Per-line **manquant** flag links into the existing **Besoin matériel** + one-click draft bon de commande flow. Reuses the **existing stock reservation** so preparing an intervention reserves the required quantities and surfaces a manquant as a shortfall.
- [ ] F6 — **GPS check-in on arrival**: stamps an arrival timestamp + coordinates on the intervention using the browser geolocation already used for site GPS (**no new external service**); shows a distance-to-site indicator against the chantier GPS as a presence record; plus a **départ-dépôt** stamp and a **retour** stamp for travel timing.
- [ ] F7 — **Guided photo capture** per intervention driven by a configurable **shot list** (defaults seeded to the solar field-documentation standard, fully editable in Paramètres), grouped **Avant** (état de la toiture et pénétrations existantes, coffret et compteur, tracé du câble, vue d'ensemble du site), **Pendant** (structure et rails avant pose, câblage avant dissimulation, mises à la terre, numéro de série de chaque panneau), **Après** (champ posé, onduleur, compteur de production avec relevé, vue d'ensemble). Every photo stored via the existing file-attachment feature in object storage, tagged to its shot-list slot, stamped with capture timestamp + GPS coordinates as a **visible overlay**, presented in an Avant/Pendant/Après gallery per intervention. **Real site data, never committed to the repo.**
- [ ] F8 — **Required-photo enforcement**: an intervention cannot move to Terminée until every shot-list slot marked **obligatoire** has at least one photo; shows a clear checklist of which obligatoire shots are still missing; the obligatoire flag per slot is editable in Paramètres.
- [ ] F9 — **Per-component serial-number capture** on the relevant Pendant/Après steps: a photo of the plaque signalétique + an editable serial field, with **optional automatic serial extraction behind a swappable OCR interface** that adds **no external credential by default** and safely **no-ops** (returns the manual field) when no provider is configured — exactly like the existing Bill OCR swappable interface. Captured serials flow into the **Système installé** record per the existing parc-installé design and **never block** step or intervention completion when a serial is left empty.
- [ ] F10 — **Photo annotation**: a captured photo can be marked up with simple drawing + a caption to flag an issue, stored as part of the photo record.
- [ ] F11 — **Matériel consommé reconciliation** per intervention: lists every bill-of-materials line with its **prévu** quantity against a **réellement utilisé** quantity, allows extra unplanned lines (e.g. mètres de câble, vis et boulons, connecteurs MC4, presse-étoupes), requires a short justification on any line where utilisé ≠ prévu (justification accepted as typed text **or a voice memo**), and on validation reconciles against the **existing stock reservation + consumption** so real field consumption (not the quote estimate) drives stock movements and feeds the per-chantier job-costing margin. **Buy prices stay internal.**
- [ ] F12 — **Overage review surface**: interventions whose consumption exceeds the quoted quantities **beyond a configurable percentage** are flagged to Reda for review with the justifications attached, feeding restock accuracy + a per-chantier margin-impact alert.
- [ ] F13 — **Voice-memo capture** available anywhere on an intervention (a general note, a note attached to a photo, the justification on a Matériel consommé variance line, a note on a réserve): records audio in the field, stores it via the existing file-attachment feature in object storage, with in-app playback. **No external service for capture/storage; audio is real site data, never committed to the repo.**
- [ ] F14 — **Swappable Transcription interface** with a default **no-op** implementation that labels every voice memo **« Non transcrit — service non configuré »** until a provider is set; the provider + any credential is configurable **only in Paramètres** and **added by no part of this task**; designed for Darija + French code-switching; always keeps the **original audio as source of truth** and the produced transcript editable by Reda or Meryem; mirrors the existing swappable-interface no-op pattern (field captures + stores voice memos fully today, transcription lights up later once a provider is explicitly chosen). **No external credential introduced by default.**
- [ ] F15 — **Crew time tracking** per intervention: on-site duration from the GPS arrival stamp + the Terminée time, travel time from the départ-dépôt + retour stamps, feeding the existing chantier **actual labour-days** field.
- [ ] F16 — **Réserves punch-list** per intervention for items needing a return (e.g. câble manquant, réglage onduleur): each with a description, optional photo, optional voice memo, an assignee, and a resolution; optionally spawning a follow-up intervention or a SAV ticket per the existing SAV design.
- [ ] F17 — **Tool-return reconciliation** on closing an intervention: confirms each outil from the kit is returned to its dépôt or camionnette location, flags any tool not returned, and updates the Outillage statut + location accordingly.
- [ ] F18 — **Consignes de sécurité sign-off** step on an intervention with a configurable checklist (seeded with EPI portés + consignation électrique, editable in Paramètres), recorded with who + when reusing the existing audit pattern.
- [ ] F19 — **Compte-rendu d'intervention PDF** per intervention (French, existing PDF engine + company identity from Paramètres): client + site, the équipe, arrival + departure times, the Avant/Pendant/Après photo set, the serials captured, the matériel réellement consommé with its variance justifications, the réserves, and a client + installer signature block with the manuscrit « Bon pour accord » line. **Client-facing, no buy prices.** Complements the existing PV de réception.
- [ ] F20 — **Optional AI photo-QA** behind a swappable vision interface reusing the **Claude API already in the stack**: when enabled, flags likely-missing or low-quality obligatoire shots (blurred / wrong-subject) so the équipe can fix them before leaving the site; **adds no external credential by default**, safely no-ops when disabled, and **never blocks completion** on its own.
- [ ] F21 — **Offline-tolerant field capture** covering the whole intervention flow — préparation checklist, GPS check-in, photos, serial capture, voice memos, Matériel consommé, réserves, and the signature — queuing locally on a poor connection and syncing when back online (extends the planned offline field capture to the full intervention workflow).
- [ ] F22 — **« Ma journée » crew view** for the logged-in technician showing today's assigned interventions in order, each opening straight into its préparation checklist → on-site capture → completion flow, thumb-reachable and in French, as the single screen a field technicien uses all day; **seed the existing technicien RBAC role** so a technicien sees only their own assigned interventions + chantiers and can capture everything but **never sees buy prices or margins**.
- [ ] F23 — **Per-intervention QR or short code** so scanning a chantier or matériel label resolves straight to its intervention, reusing the existing label + scan-resolution feature.
- [ ] F24 — After F1–F23 are built, **update the master project document + the PLAN + DONE log** in plain language to record the new field-execution + outillage module, the Matériel consommé reconciliation, the voice-memo capture with its swappable transcription interface left unconfigured, the crew-facing « Ma journée » experience, and which items shipped and which were skipped.

---

## GATED — needs Reda's decision before building (agent does NOT auto-build)

The agent must **not** start these. They cost money, change auth, add a new module/architecture, or
need Reda's taste. Reda decides; then I write a focused task and move it into the BUILD QUEUE.

- **G1 — Real email sending** (devis/facture/relance by email). Needs SMTP/SendGrid → a cost/auth
  change. Decision: which provider, OK to add the cost? (WhatsApp link-send already covers "send" for free.)
- **G2 — WhatsApp Business Cloud API** (true auto-send + PDF *attached*, message templates). Cost +
  Meta Business setup. Already your Month-2 roadmap.
- **G3 — Full document visual redesign** (devis/facture/bon de commande). **Needs your gallery
  approval** (taste) — never an unattended run. `PDF_ENGINE=legacy` stays as the fallback.
- **G4 — Custom per-module roles/permissions.** New architecture; becomes important at multi-tenant
  Phase 6. Today Commerciale vs admin works.
- **G5 — Supplier procurement module** (bons de commande fournisseur, goods-in/receiving, supplier
  invoices / accounts payable). A real new module — a multi-session project of its own.
- **G6 — Stock auto-decrement on installation** (a chantier consumes its equipment from stock).
  Accounting impact — confirm the exact rule first.
- **G7 — Quote e-signature.** External dependency / provider.
- **G8 — 2FA / SSO.** Auth change.
- **G9 — Automation engine / scheduler.** For things that must fire on a timer: cold-lead reminders,
  stale-quote nudges, last-chance-close, persisted expiry, and the planned n8n workflows. Decision:
  Celery Beat (in-app) vs n8n (separate). Needed before any "runs by itself daily" automation.
- **G10 — CAPI service** (Meta Conversions API, sends `SignedQuote` on Signé, EMQ ≥ 7.0). Roadmap;
  **gated on fbclid/UTM capture landing in the site form first**.
- **G11 — Chatbot → Reda's Claude API key.** Small, but a cost change — needs the key present + your OK.
- **G12 — MCP server + M365** (Entra ID, Outlook, OneDrive, Teams). Roadmap.
- **G13 — One-off 619-lead Odoo import.** Uses the reusable importer (T9) once built, but **gated on a
  2nd Odoo backup** before any real extraction. File holds PII → gitignored, never in chat/GitHub.
- **G14 — DGI e-invoicing readiness (Morocco).** Mandatory ~**Jan 2027** for businesses with CA >
  500k DH — likely Taqinor's wave. Clearance model: structured **UBL 2.1 / CII** XML + electronic
  signature, validated by the DGI platform before sending; **a PDF is explicitly NOT compliant**.
  **Cannot be built until the DGI platform specs are public** and the décret d'application is
  published. Your per-line TVA + ICE work is the right groundwork. Start when specs publish.
- **G15 — Arabic / Darija UI** (full interface localization, not just message templates). Decide if
  needed and for whom.

---

## MANUAL — Reda's / Meryem's tasks (NOT code; agent never does these)

Tracked here so they aren't lost:
- Enter the real **ICE / IF / RC** on the server (Paramètres → Identifiants légaux) — live invoices
  currently lack the legally-required seller ICE until then.
- Enter the **11 OSP pump prices** on the server (the agricole pump box stays red; don't send an agri
  quote before).
- Enter **real stock quantities** on the server (the ~283 M DH dashboard value is demo quantities).
- **Article 33 / Loi 82-21 outreach** to the install portfolio (decree in force since 9 June —
  overdue, still sendable; Meryem sends; tag replies « Régularisation 82-21 »).
- **Confirm Sami's GitHub org access is removed.**
- **Confirm the PC cleanup ran** (taqinor-secrets.txt + test-leads JSON deleted).
- **Set the default lead responsable** to Meryem (Paramètres → Leads).
- **Personalize the WhatsApp templates** (Paramètres → Messages WhatsApp).
- Optional: add `PUBLIC_BASE_URL=https://api.taqinor.ma` to the server `.env` for cleaner WhatsApp
  links (they already work via auto-redirect).
- **DEBUG:** turn it off when you decide the OS is ready (your call — the agent will not raise it).

---

## DONE LOG (agent appends one plain-language line per completed task)

- *(seeded baseline — see "ALREADY LIVE" above for the full pre-plan state)*
- _next: the agent adds entries here, e.g. "2026-06-15 — T1 done: devis preview renders + downloads in all 3 formats; cache-busting added; deployed."_
- 2026-06-16 — T1 verified already present: /proposal serves a real inline PDF; the lead devis panel fetches it as a blob and renders it with PDF.js (clear FR error on server failure, graceful fallback on network failure); non-mocked regression tests cover Premium / 1-page / étude; Vite content-hashes the build. No change needed.
- 2026-06-16 — T2 verified already present: vite-plugin-pwa configured (autoUpdate, injectManifest sw.js with skipWaiting/clientsClaim), manifest + icons + iOS head tags + offline page, and a French install helper (PwaPrompts.jsx, beforeinstallprompt). No change needed.
- 2026-06-16 — T17 done: discount approval guard. A configurable « seuil d'approbation de remise » (Paramètres → Hypothèses ROI; vide = désactivé, default off). When a devis's remise exceeds the threshold, passing it to « envoyé » requires admin approval — an admin/owner approves implicitly by sending, or via the « Approuver remise » button / POST /ventes/devis/<id>/approuver-remise/. Default off = behaviour unchanged. Tests included.
- 2026-06-16 — T16 done: recurring maintenance contracts. New ContratMaintenance model (client + optional chantier, périodicité mensuel→annuel, date de début). Prochaine visite et statut « dû » calculés à la lecture (aucun planificateur, cohérent T7). « Générer les visites dues » crée des tickets SAV préventifs idempotents et avance la date. New /sav/contrats page (liste + vue « à venir »). Ticket.installation relâché en optionnel (additif) pour permettre une visite au niveau client. Company-scoped, tests.
- 2026-06-16 — T13/T14/T15 done: « Rapports » hub (new sidebar entry /rapports). Sales report (funnel by stage, by responsable incl. won, losses by motif), Stock report (sell + internal buy valuation, by category, low stock), Service report (chantiers by status, technician activity, SAV open vs resolved, warranties ≤90 j). Read-only, company-scoped, each exportable to .xlsx (?export=xlsx). Endpoints /reporting/reports/{sales,stock,service}. Tests included. Buy-price valuation stays internal (never in a client export).
- 2026-06-16 — T12 done: accountant export — journal des ventes + résumé TVA. Periodable (month/quarter/dates) .xlsx with 2 sheets: a per-line journal of every issued invoice (ref/date/client/ICE/désignation/HT/taux/TVA/TTC) and a TVA summary split by rate (10 %/20 %) reconciled to the centime with HT/TVA/TTC totals. GET /ventes/journal-ventes; « Journal comptable » button on the invoices list. Company-scoped, tests.
- 2026-06-16 — T11 done: user-defined custom fields mechanism (additive, JSONField — per docs/erp-data-model-proposal.md). Admins define fields per module (leads/clients/products) in Paramètres — type text/number/date/choice/boolean, optional + required. Values live in each record's custom_data; the lead form renders them dynamically and the server validates (required/type/choice) on create. New CustomFieldDef model + /custom-fields/definitions API + custom_data on Lead/Client/Produit. Company-scoped, tests included.
- 2026-06-16 — T10 done: quote revisions/versioning. A sent devis can be « Révisé » into a new version (v2, v3…) that clones its lines and restarts as brouillon; the previous version becomes inactive, read-only, and shows a « remplacé par » link to its successor. Lead/client links and the DEV- numbering scheme are preserved. Additive (version/version_parent/superseded_by/is_active). Endpoint /ventes/devis/<id>/reviser/ + UI (Réviser button, version badge). Tests included.
- 2026-06-16 — T9 done: reusable CSV/XLSX importer (leads, clients, products) with a dry-run preview (10 rows + column→field mapping + ignored columns) before commit; create-only, duplicates skipped (email/phone/SKU), imported leads origin-tagged « Import ». Endpoints /imports/dry-run, /imports/commit. « Exporter Excel » buttons on every list (leads, clients, products, devis, factures, chantiers, equipements, SAV) honouring the current filter, via dedicated exports + a generic /imports/export/<entity>. Reusable import modal in the UI. Tests included.
- 2026-06-16 — T8 done: bulk product/catalogue editing. Multi-select products in the catalogue → bulk change sell price (% variation or fixed — buy price never touched), set warranty (garantie_mois / garantie_production_mois), reassign category, set brand, and export the selection to .xlsx. Company-scoped backend POST /stock/produits/bulk/ + /export-xlsx/ with an audit log and tests.
- 2026-06-16 — T7 done: quote expiry computed on-the-fly (a pending devis past its validity date shows « Expiré » in the list and the API, never persisted, never moves the lead) + a pipeline-value dashboard in Reporting (total MAD by stage, weighted forecast, devis by status with on-the-fly expiry, win count/value, losses by motif). Read-only, company-scoped, with tests.
- 2026-06-16 — T6 done: deferred settings unlocked. Editable Canaux/Sources de lead (Paramètres → CRM) with « Site web » protected from rename/delete and in-use canals undeletable; editable Types d'intervention (Paramètres → Chantiers, system types protected, in-use undeletable); Marque promoted to a real referential model (Paramètres → Stock), backfilled on first read from existing product brands, in-use undeletable; ROI hypotheses (tarif ONEE MAD/kWh, productible kWh/kWc/an) added as editable settings defaulting to today's simulator values. All additive (no destructive migration); the guarded simulator math keeps its internal fallback. Backend safeguards + tests across crm/stock/installations/parametres. (Product-form brand picker is a minor follow-up; the brand referential + backfill is in place.)
- 2026-06-16 — T5 done: global search box in the top bar (leads, clients, devis, factures, chantiers, équipements, tickets SAV — grouped, click to open) + an in-app notification bell (overdue activities, warranties expiring ≤90 days, unpaid/overdue invoices — count + clickable list). Read-only, company-scoped backend endpoints (/reporting/search, /reporting/notifications) with tests.
- 2026-06-16 — T4 done: inline edit-in-place via a reusable InlineEdit cell. Leads list — stage, priorité, relance, tags (responsable was already inline); products catalogue — sell price, quantity, category. Each saves only that field via PATCH, validates server-side, and lead edits log to Historique. Backend tests added.
- 2026-06-16 — T3 done: bulk actions on leads (multi-select in list + kanban, selection toolbar). Bulk reassign / add+remove tag / change stage (no-going-backwards, never moves a Perdu lead, reactivates Froid) / set+clear relance / flag+unflag Perdu / archive+unarchive / admin-only delete (skips leads with linked devis) / export selection to .xlsx. Every change writes a per-lead Historique entry badged « en masse ». Backend POST /crm/leads/bulk/ + /crm/leads/export-xlsx/ (company-scoped); 15 new backend tests + a frontend selection-logic test. Developed on branch claude/gallant-mccarthy-vh5e98 (not merged to main).
- 2026-06-16 — N40/N41/N42 done: dossier réglementaire loi 82-21 / Article 33 sur chaque chantier — régime (Déclaration BT / Accord de raccordement / Autorisation ANRE / Non concerné), statut du dossier (À déposer/Déposé/Approuvé/Compteur posé), référence, opérateur, dates, et un drapeau « Régularisation Article 33 » ; pièces jointes via la galerie chantier. Filtres serveur + barre de filtres chantier par régime et Art. 33 (le lead garde son indicateur 82-21 existant). Additif + tests.
- 2026-06-16 — N16 done: « Inventaire » (Stock → bouton Inventaire, admin) — saisir un comptage physique par produit ; seuls les écarts publient un mouvement « Ajustement » audité et alignent le stock sur la quantité comptée. Réservé admin, scopé société, additif + tests.
- 2026-06-16 — N39 done: a « Télédéclaration DGI » status (Non soumise/Soumise/Validée) on each facture — informatif, posé à la main dans la modale d'édition de facture, défaut « Non soumise » (comportement inchangé). Prépare le modèle pour un futur flux DGI, sans aucun appel externe. Additif + test.
- 2026-06-16 — N1/N2/N4–N10 done (chantier + parc, by EXTENDING the existing installations/sav models — no parallel model). N1: the chantier funnel is now « Signé → Matériel commandé → Planifié → En cours → Installé → Réceptionné → Clôturé » (legacy statuses kept valid and mapped for display, additive), plus frozen BOM from the devis, jours-homme estimés/réels, milestone dates, default installer = creator. N2: a Kanban view on /chantiers (drag to change status, installer reassign select), beside Liste/Calendrier. N4: configurable execution checklist (Paramètres → Chantiers — Checklist), per-step done/by/when, completion % bar in the chantier detail. N5: photos/files grouped Avant/Pendant/Après (gallery) per chantier. N6: a milestone timeline in the chantier detail. N7: a réceptionné chantier auto-becomes an active « système installé » (parc_actif + date_reception stamped). N8: new « Parc installé » page (/parc) — filter by client/ville/marque/tranche kWc/année + a GPS map-links view (interactive tile map deferred, would need a new dep). N9: optional serial capture on the panneaux/onduleur checklist steps → creates parc équipements, never blocks completion. N10: the chantier detail is the per-système hub (composants, garanties, tickets SAV, contrats de maintenance, statut supervision). Backend additive migrations + tests; frontend lint/build green.
- 2026-06-16 — N11 done (frontend): new « Commandes fournisseur » page (Stock sidebar, /stock/bons-commande-fournisseur). Browse/filter supplier POs, create one (supplier + SKU/qty/buy-price lines), edit while Brouillon, send, receive partial quantities (increments stock), cancel, and download the internal supplier PDF. Buy prices stay internal. Reuses the existing race-safe BCF backend + procurement helpers.
- 2026-06-16 — N29 done (frontend): Article 145 conformity warning now surfaced — an amber « mentions légales manquantes » banner on the facture edit modal (lists each missing mention, never blocks emission) plus a « ⚠ N mention(s) manquante(s) » chip on the factures list, both fed by the existing Facture.mentions_manquantes API field.
- 2026-06-16 — Re-homed the recovered PLAN2 (N1–N102) into this file's BUILD QUEUE and reconciled every tick against the live main code (not the recovered file's stale ticks). 30 done / 72 open. The post-sale PDFs (PV de réception, bon de livraison, dossier de remise, attestations — N21–N24), supplier purchase order backend + PDF + reception + besoin-matériel panel (N11–N13), documents archive (N32), facture Article 145 conformity check (N29), SAV intervention report (N45) and the settings-change audit (N55) were confirmed present from PRs #118/#119. N11 (supplier-PO management page) and N29 (facture conformity warning banner) are backend-ready/frontend-pending. PLAN2.md and the recover-plan2 branch were retired once this landed on main.
- 2026-06-17 — N31 done: audit admin de la numérotation séquentielle. La numérotation reste sans collision à la création (highest+1, retry sur course) ; un nouveau bouton « 🔢 Audit numérotation » (admin, liste des factures) signale les numéros manquants (trous laissés par une suppression) et d'éventuels doublons, par type de pièce (devis/factures/avoirs/bons de commande) et par mois — purement en lecture, aucune renumérotation. Endpoint GET /ventes/numerotation-audit/ + cœur pur testé.
- 2026-06-17 — N38 done: export structuré UBL 2.1 (aperçu BROUILLON) d'une facture, en XML local — travail préparatoire e-facturation DGI. Bouton « ⟨/⟩ UBL » sur chaque facture émise/payée/en retard : génère un XML de forme UBL 2.1 (identité + ICE/IF/RC vendeur, identité + ICE client, dates, TVA par ligne, ventilation HT→TVA→TTC), clairement marqué « non transmis », déposé en local (MinIO best-effort). Aucun appel externe, aucun identifiant. Endpoint GET /ventes/factures/<id>/ubl/ + constructeur pur testé.
- 2026-06-17 — N25 done: acceptation explicite d'un devis. Bouton « ✓ Accepter » sur un devis envoyé : capture le nom de la personne qui accepte + la date choisie, passe le devis en « accepté », consigne l'événement dans un NOUVEAU chatter du devis (DevisActivity, même patron que les chantiers) et avance le funnel CRM. L'acceptation reste le déclencheur de la création de chantier (la date de signature du chantier reprend la date d'acceptation). Endpoints /ventes/devis/<id>/{accepter,historique,noter}/ + tests.
- 2026-06-17 — N43 done: suggestion configurable du régime loi 82-21. À la création d'un chantier, le régime (Déclaration < seuil 1 / Accord de raccordement / Autorisation ANRE > seuil 2) est proposé automatiquement d'après la puissance kWc — défaut MODIFIABLE (un repère « Suggéré : … [Appliquer] » s'affiche aussi sur la fiche chantier, dossier réglementaire). Les deux seuils (défauts 11 kWc et 1 MW) sont éditables dans Paramètres → Hypothèses ROI. Endpoint GET /installations/chantiers/regime-suggestion/?kwc= + cœur pur testé.
- 2026-06-17 — N15 done: stock multi-emplacements. Nouveaux emplacements (Dépôt principal + Camionnette amorcés automatiquement par société, additif), avec transferts entre emplacements traçés (modèle TransfertStock = le « transfer record »). Le total `Produit.quantite_stock` reste canonique et INCHANGÉ : le dépôt principal détient le reste (total − somme des autres), donc tout le stock existant est par défaut au dépôt principal et le comportement actuel ne change pas — un transfert ne fait que ventiler. Écran : bouton « 🚚 Transférer » sur la liste Stock → choisir un produit (voir sa répartition par emplacement), transférer une quantité d'un emplacement à un autre, gérer les emplacements (admin). Backend : EmplacementStock/StockEmplacement/TransfertStock + service transfer_stock (atomique, refuse de dépasser le stock source / source==destination / cross-tenant), endpoints /stock/emplacements/, /stock/produits/<id>/emplacements/, /stock/transferts/. Le principal et un emplacement détenant du stock ne sont pas supprimables. Tests : 7 tests cœur (amorçage idempotent, défaut au principal, transfert sans changer le total, refus over-stock/même emplacement/cross-tenant) exécutés en local + tests API (mêmes patrons que l'appro fournisseur) couverts par la CI ; helper front testé (node) + lint vert.
- 2026-06-17 — N17 done: listes de prix multi-fournisseurs par SKU. Nouveau modèle PrixFournisseur (produit + fournisseur + prix d'achat INTERNE + date du dernier achat ; migration 0018, additif). Un produit peut avoir plusieurs fournisseurs à des prix différents ; le moins cher est proposé automatiquement quand on rédige un bon de commande pour un manque de chantier (resolve_fournisseur préfère le fournisseur le moins cher, puis le fournisseur catalogue). La réception d'un bon de commande met à jour automatiquement le prix d'achat et la date du dernier achat chez ce fournisseur. Le besoin matériel renvoie désormais aussi le fournisseur le moins cher par ligne (fournisseur_min_nom / prix_achat_min). Écran : section « Prix fournisseurs (interne) » dans la fiche produit (en édition) pour ajouter/supprimer des prix par fournisseur, le moins cher marqué ⭐. Les prix d'achat restent INTERNES (jamais sur un document client). Endpoints /stock/prix-fournisseurs/ + /stock/produits/<id>/prix-fournisseurs/. Tests : 5 tests cœur exécutés en local (moins cher / ignore prix nul, upsert + date, besoin surface le moins cher, resolve préfère le moins cher) ; lint front vert.
- 2026-06-17 — N18 done: valorisation du stock par emplacement au coût moyen d'achat. Le coût moyen pondéré est calculé à partir de l'historique des réceptions de bons de commande fournisseur (quantité reçue × prix d'achat), avec repli sur le prix d'achat catalogue quand aucun achat n'a été reçu. La valorisation croise ce coût avec la répartition par emplacement (N15) : valeur par emplacement = quantité × coût moyen, plus un total général. Écran : bouton « 💰 Valorisation » (admin) sur la liste Stock → totaux par emplacement + détail par produit/emplacement. INTERNE uniquement (admin ; les prix d'achat ne sont jamais sur un document client). Endpoint GET /stock/produits/valorisation/. Pas de migration (dérivé des données existantes). Tests : 3 tests cœur (moyenne pondérée, repli prix catalogue, valeur ventilée par emplacement) exécutés en local ; lint front vert.
- 2026-06-17 — N19 done: retour fournisseur (articles défectueux/erronés). Nouveaux modèles RetourFournisseur + LigneRetourFournisseur (migration 0019, additif), numérotés sans trou (préfixe RF), liés optionnellement au bon de commande fournisseur d'origine. La validation DÉCRÉMENTE le stock via MouvementStock (SORTIE) exactement comme partout ailleurs (service apply_retour_fournisseur, idempotent : un retour déjà validé ne re-décrémente pas). Écran : bouton « ↩ Retour fournisseur » dans la fiche d'un bon de commande reçu/envoyé → saisir les quantités à retourner + motif par ligne ; à la validation le stock baisse et un retour lié au BCF est créé. Usage INTERNE (prix d'achat jamais client-facing). Endpoints /stock/retours-fournisseur/ + /valider/. Tests : 4 tests cœur (décrément, idempotence, retour vide refusé, lien BCF) exécutés en local ; lint front vert.
- 2026-06-17 — SKIP/BLOQUÉS (laissés [ ], non construits sans décision du founder — dépendance/coût/auth/architecture nouvelle, conformément aux GATED) : N14 (consommation stock à la pose = G6), N20 (étiquettes QR/code-barres = nouvelle dépendance), N50 (intégration monitoring Huawei FusionSolar = service externe + identifiants), N68 (éditeur RBAC = G4), N69 (permission prix d'achat/marges, dépend RBAC/auth), N72 (moteur d'automatisation/planificateur = G9), N73 (étape d'approbation dans l'automatisation, dépend N72), N85 (carte = nouvelle dépendance carto), N86 (extension chatbot = clé IA G11 + portée), N87 (envoi email = G1 coût/auth), N88 (capture email entrant = externe/coût), N89 (API REST publique = nouvelle architecture + auth/jetons), N91 (capture offline = hors périmètre PWA + nouvelle architecture sync), N92 (push PWA = infra VAPID), N93 (i18n arabe/darija complet = G15), N94 (gestion de traductions, dépend N93), N96 (2FA/sessions = G8 auth), N100 (plateforme multi-tenant = nouvelle architecture), N101 (console tenants + signup = nouvelle architecture/auth). Restent ouverts et CONSTRUCTIBLES pour une prochaine session (additifs) : N26, N36, N46, N47, N49, N51, N52, N53, N58, N59, N60, N62, N64, N65, N66, N67, N70, N74, N75, N76, N78, N79, N80, N84, N95, N97, N98, N99 (+ N102 doc finale).
- 2026-06-17 — Insights batch shipped (N49, N70, N78, N80, N95) — 4 new read-only,
  company-scoped, additive reporting endpoints under /reporting/insights/ (no
  migration, no PDF, no state-machine change), each with backend tests and a new
  card in the « Rapports » page: **N49** revenu récurrent (contrats de maintenance
  actifs → mensuel/annuel équivalent, renouvellements à venir ≤90 j, contrats
  lapsed) ; **N70 + N95** journal d'activité unifié (fusion LeadActivity /
  DevisActivity / InstallationActivity / TicketActivity / SettingsAuditLog, filtres
  ?user / ?type / ?since — « qui a fait quoi » N70 ET la piste d'audit système N95
  dans le même endpoint) ; **N78** coût de revient & marge par chantier (facturé HT
  via le devis lié vs Σ prix_achat × quantités — ADMIN uniquement, prix d'achat
  jamais dans un export client, précédent stock_report) ; **N80** analytics (délai
  moyen lead→signature et signature→mise en service, kWc installés par mois). Tous
  exportables en .xlsx (sauf le prix d'achat brut). Front lint + build + 83 tests
  node verts en local ; suite Django + flake8 + stage-names en CI.
- 2026-06-17 — Re-vérifié contre le code réel et marqué [BLOCKED] (déplacés en
  attente de décision founder) : N36 (RIB sur le PDF devis = littéral du moteur
  premium, règle #4), N53 (dépend du monitoring N50, externe), N59/N60/N67 (textes
  CGV/validité/garantie = littéraux du moteur premium, règle #4), N64/N65 (tables
  tarifaires ONEE par tranche + carte d'irradiation par région = changent le modèle
  de calcul, décision founder), N76/N79 (digest planifié / export planifié = besoin
  d'un planificateur G9). Le reste de la file N (N26, N46, N47, N51, N52, N58, N62,
  N66, N74, N75, N84, N97, N98, N99, N102) reste constructible pour une prochaine
  passe. Le module terrain F1–F24 reste à zéro sur main (F1–F4 sur la branche non
  fusionnée dev-field-exec) — gros module multi-session, hors lot de cette session.
