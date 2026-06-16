# Taqinor OS — Build Plan & Progress

This file is the **single source of truth** for the Taqinor OS build backlog and the
**memory between Claude Code sessions**. Each run works through EVERY unchecked task in this file from top to bottom — not just one — ticking each off in this file as it lands, then does the same for `docs/PLAN2.md` if that file exists, and only stops when both queues are clear (or a usage limit pauses it, in which case re-running resumes from the next unchecked task). The next session reads this file and
continues. Nothing relies on the agent's own memory — the file on disk is the memory.

---

## HOW TO RUN (read this every session)

1. **Read this whole file.**
2. In **BUILD QUEUE** below, find the **first task marked `[ ]`** (not `[x]`, not `[SKIP]`,
   not `[BLOCKED]`). Ignore the GATED and MANUAL sections entirely.
3. **Verify it isn't already built.** Inspect the actual repo and the deployed app. If the
   task already exists and works, mark it `[x] (already present)`, add a line to the DONE
   LOG, commit this file, and move on to the next `[ ]` task — repeat this verify step.
4. **Build only that one task, completely, with tests.** Obey every STANDING RULE below.
5. **CI must pass** (lint, tests run 3×, stage-name check, PDF page-count guardrails) and
   **the CI must include MinIO** so PDF tests actually run. If green: self-merge `dev` →
   `main` (merge commit, history preserved). **Merging to `main` now AUTO-DEPLOYS to
   api.taqinor.ma on its own** — the production server polls `main` about once a minute and
   runs the full deploy (rebuild + migrations + role sync + nginx/Caddy reload + the
   mandatory PDF pre-warm). A pure docs/markdown change (e.g. ticking this file) skips the
   rebuild. **You do not run any deploy command.** `powershell -File scripts\deploy-prod.ps1`
   still works as a **manual fallback** from a PC if ever needed.
6. **Update this file on `main`:** flip the task to `[x]`, append one plain-language line
   (with today's date) to the DONE LOG, and commit the updated file (this commit auto-syncs
   to the server without a rebuild).
7. **STOP and report** in plain language only — no diffs, no commit hashes: which task, what
   changed, exactly what Reda must click/type (with menu paths), and confirm the auto-deploy
   shipped it (the server records each deploy in its own log). Continue to the next `[ ]` task. Do not stop until every task in this file — then every task in `docs/PLAN2.md`, if it exists — is `[x]`, `[SKIP]`, or `[BLOCKED]`.
8. **If a task hits a blocker** (it would need a destructive migration, a paid/external
   dependency that isn't pre-approved, an auth change, or a real decision): do **not** guess
   and do **not** stall. Mark it `[BLOCKED: <one-line reason>]`, move it to the GATED section,
   pick the **next** `[ ]` task instead, and note the block in your report.

**Run from anywhere — web or phone.** Because `main` auto-deploys itself, a task can be run
from Claude Code on the web or from the phone with no PC involved. **One-line starter** to
paste into a fresh cloud session:

> Read `docs/PLAN.md` top to bottom. Work through EVERY `[ ]` task in the BUILD QUEUE in order: verify each isn't already built, build it with tests, tick it `[x]`, add a dated DONE LOG line. Then do the same for `docs/PLAN2.md` if it exists. Get CI fully green (with MinIO) and self-merge `dev` → `main` (this auto-deploys — do not run any deploy command). Report in plain language. Do not stop after one task.

---

## STANDING RULES (every task obeys these)

- **One run = the whole queue, not one task.** Give each independent task its own subagent in its own git worktree so each subagent's context stays small and focused; run tasks that depend on or overlap each other in sequence. Never stop after a single task. (Human-review PRs are still not wanted — the run self-merges its own green work.)
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

### T7 — Quote expiry (on-the-fly) + pipeline-value dashboard — [ ]
- **Expiry:** a quote shows « Expiré » when today is past its validity date (creation + the
  "validité du devis" setting). **Compute on the fly at read/display time — no scheduler, cron, or
  background job, no daily command.** Never move the lead backward; just reflect it visually and in
  filters/queries.
- **Pipeline-value dashboard:** total MAD by stage, a simple weighted forecast, count + value of
  quotes by status, win/loss by motif de perte. Read-only; respects the shared filter bar.

### T8 — Bulk product / catalogue editing — [ ]
Multi-select products → bulk: change sell price (% or fixed — sell price only, never alter
buy-price-visibility rules), set warranty (`garantie_mois` / `garantie_production_mois`), reassign
category and/or brand, export selection to .xlsx. Logged.

### T9 — Reusable import + Excel export everywhere — [ ]
`openpyxl` is pre-approved.
- A **reusable CSV/XLSX import** for leads, clients, and products: a **10-row dry-run** showing
  column→field mapping (and what didn't map) for approval before the full batch, origin-tagged,
  nothing overwritten silently. Keep this **separate** from the one-off 619-lead Odoo migration.
- An **"Exporter Excel" (.xlsx)** button on every list view (leads, clients, quotes, invoices,
  products, chantiers, equipements, SAV tickets) that respects current filters.

### T10 — Quote revisions / versioning — [ ]
Let a sent quote be **revised into a new version** (v2, v3…) that keeps the prior versions readable,
without breaking the lead↔devis links or the numbering scheme. The active/latest version is clearly
marked; superseded versions are read-only with a "remplacé par" link. Additive only.

### T11 — User-defined custom fields — [ ]
Build the **mechanism** (not the specific fields — those are Reda's choice). Let an admin add a custom
field to a module (start with leads, then clients/products), choose its type (text, number, date,
choice, boolean), make it appear on the form and optionally in lists/filters, hide standard fields,
and restore-to-default. Scope question on creation ("appliquer à tous ?"). Additive; if it would need
a destructive migration, `[BLOCKED]`. If `docs/erp-data-model-proposal.md` exists, use it as input.

### T12 — Accountant export: journal des ventes + TVA summary — [ ]
A periodable (month/quarter) **.xlsx export for the comptable**: all issued invoices with their
per-line TVA, plus a **TVA summary split 10% / 20%** reconciled to the centime, and totals HT/TVA/TTC.
Read-only; openpyxl. (This is also direct groundwork for the DGI e-invoicing mandate — see GATED.)

### T13 — Reports hub: sales reports — [ ]
A **"Rapports"** section. Start with **sales/pipeline**: leads & conversion by stage (funnel),
quotes by status and value, sales by responsable / by canal / by period, win-loss by motif de perte.
Read-only, respects filters, each report exportable to .xlsx.

### T14 — Reports hub: stock reports — [ ]
Add to "Rapports": **stock valuation** (sell + buy, buy kept internal/non-client-facing), movement
history report, low-stock list, by category/brand. Exportable to .xlsx.

### T15 — Reports hub: service reports (chantier + SAV) — [ ]
Add to "Rapports": chantier planning load + completion timing, technician activity, SAV open vs
resolved + resolution time, equipment warranties expiring. Exportable to .xlsx.

### T16 — Recurring maintenance contracts — [ ]
A `ContratMaintenance` model (additive) attached to a chantier/client: a preventive-visit
subscription on a schedule that **generates SAV tickets when a visit is due, computed on the fly /
at read time (consistent with T7 — no scheduler)**; a list view and an "à venir" view.

### T17 — (optional, lower priority) Discount approval guard — [ ]
When a quote discount exceeds a configurable threshold, require an admin/owner approval before the
quote can be marked « envoyé » (protects margin once Meryem works quotes solo). Configurable in
Paramètres; default threshold = off so nothing changes until Reda sets it.

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
- 2026-06-16 — T6 done: deferred settings unlocked. Editable Canaux/Sources de lead (Paramètres → CRM) with « Site web » protected from rename/delete and in-use canals undeletable; editable Types d'intervention (Paramètres → Chantiers, system types protected, in-use undeletable); Marque promoted to a real referential model (Paramètres → Stock), backfilled on first read from existing product brands, in-use undeletable; ROI hypotheses (tarif ONEE MAD/kWh, productible kWh/kWc/an) added as editable settings defaulting to today's simulator values. All additive (no destructive migration); the guarded simulator math keeps its internal fallback. Backend safeguards + tests across crm/stock/installations/parametres. (Product-form brand picker is a minor follow-up; the brand referential + backfill is in place.)
- 2026-06-16 — T5 done: global search box in the top bar (leads, clients, devis, factures, chantiers, équipements, tickets SAV — grouped, click to open) + an in-app notification bell (overdue activities, warranties expiring ≤90 days, unpaid/overdue invoices — count + clickable list). Read-only, company-scoped backend endpoints (/reporting/search, /reporting/notifications) with tests.
- 2026-06-16 — T4 done: inline edit-in-place via a reusable InlineEdit cell. Leads list — stage, priorité, relance, tags (responsable was already inline); products catalogue — sell price, quantity, category. Each saves only that field via PATCH, validates server-side, and lead edits log to Historique. Backend tests added.
- 2026-06-16 — T3 done: bulk actions on leads (multi-select in list + kanban, selection toolbar). Bulk reassign / add+remove tag / change stage (no-going-backwards, never moves a Perdu lead, reactivates Froid) / set+clear relance / flag+unflag Perdu / archive+unarchive / admin-only delete (skips leads with linked devis) / export selection to .xlsx. Every change writes a per-lead Historique entry badged « en masse ». Backend POST /crm/leads/bulk/ + /crm/leads/export-xlsx/ (company-scoped); 15 new backend tests + a frontend selection-logic test. Developed on branch claude/gallant-mccarthy-vh5e98 (not merged to main).
