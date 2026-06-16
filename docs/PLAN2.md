# Taqinor OS — Build Plan 2 (overflow queue)

Tasks appended here while a run was in progress (docs/PLAN.running existed). Same
STANDING RULES as docs/PLAN.md apply (additive only, multi-tenant, French UI,
STAGES.py pipeline contract is never editable/altered, buy prices never client-facing).

> **Resuming?** Read `docs/HANDOFF.md` first — it records the exact end-state
> (30/102 done, partial-UI follow-ups, GATED items, and how to bring up services +
> run the full CI locally in a fresh container).

---

## BUILD QUEUE (added 2026-06-16) — post-sale, procurement/inventory, Moroccan billing/compliance, editability, platform

### Chantiers / projets & execution
- [ ] N1 — Chantier (projet) object created from an accepted devis, linked to that devis, the lead and the client; carries client identity, full site address + GPS from the lead, a system summary (kWc, type d'installation résidentiel/industriel/agricole, components + bill of materials copied from the devis), planned install date, actual install date, assigned installer from the employee list (default Reda), estimated & actual labour-days, and a chatter + audit log reusing the existing activity-log pattern; uses its OWN ordered chantier status field (Signé, Matériel commandé, Planifié, En cours, Installé, Réceptionné, Clôturé) completely separate from and never modifying the lead pipeline STAGES.py contract.
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
- [ ] N15 — Multi-location stock (at least main dépôt + camionnette), transfers between locations with a transfer record, per-location quantity visibility; default all existing stock to main dépôt so current behaviour is unchanged.
- [ ] N16 — Inventory count & adjustment: admin records a physical count per location and posts the difference as an adjustment with a reason + audit entry.
- [ ] N17 — Per-SKU multiple-supplier price lists (buy prices from several suppliers + last-purchase date); surface the cheapest current supplier when drafting a bon de commande; keep buy prices internal.
- [ ] N18 — Stock valuation per location using average cost from purchase history, shown only in internal views.
- [ ] N19 — Supplier return (retour fournisseur) record for defective/wrong items, decreasing stock and linking to the originating bon de commande; internal use.
- [ ] N20 — Optional QR/barcode labels for stock SKUs and installed systems; printable labels; chatbot or search field resolves a scanned code to the SKU or Système installé.

### Post-sale / client-facing documents
- [x] N21 — PV de réception (procès-verbal de réception des travaux) PDF from a chantier (French, existing PDF engine + company identity): client/site, system summary (kWc/components/type), commissioning date, installer, signature block for client & installer with "Bon pour accord" manuscrit line, checklist-completion summary; no buy prices.
- [x] N22 — Bon de livraison (delivery note) PDF from a chantier or devis (French): delivered items + quantities, delivery date, client signature block; client-facing, no buy prices.
- [x] N23 — Client handover pack PDF (dossier de remise) per chantier (French): system summary, warranty terms per installed component (reuse devis warranty texts), basic operating/maintenance guidance, contact details; client-facing, no buy prices.
- [x] N24 — Attestation generator (French) from a chantier or installed system (e.g. attestation d'installation, attestation de fin de travaux) using configurable templates + company identity; client-facing, no buy prices.

### Devis acceptance trigger
- [x] N25 — Mark a devis accepted on a chosen date with the accepting person's name captured + recorded in the devis chatter, so acceptance is the explicit trigger enabling chantier creation.
- [x] N26 — Lightweight client acceptance capture on a devis (typed name + date + "Bon pour accord" confirmation) recorded on the devis — not a cryptographic e-signature, no external provider — producing a regenerated acceptance copy of the devis PDF stamped "accepté le <date> par <nom>".

### Moroccan legal billing & compliance
- [ ] N27 — Full set of Moroccan legal company identifiers in Paramètres company identity (raison sociale, adresse complète, IF, ICE, RC + tribunal city, patente/taxe professionnelle, RIB); stamp the applicable subset automatically onto every devis, facture, avoir, bon de livraison, PV de réception.
- [ ] N28 — Client ICE field on the client record, surfaced on devis & factures; carry the client ICE from a devis through to the facture without re-entry; non-blocking reminder on B2B documents when client ICE is missing.
- [x] N29 — Facture conformity check verifying every Article 145 CGI mention (seller identity/identifiers, client identity + ICE for B2B, sequential invoice number, emission date, delivery/prestation date, per-line description/quantity/unit-price-HT/TVA-rate/line-total-HT, totals HT/TVA/TTC, payment terms & mode); warn on any missing mention before finalising without blocking an override.
- [x] N30 — Explicit delivery-or-prestation date + payment-terms-and-mode fields on factures; default the delivery date from the linked chantier commissioning date when available.
- [x] N31 — Sequential, continuous, gap-free invoice/quote numbering per document type with no duplicates; surface any detected gap to an admin (build on existing race-safe auto-numbering).
- [x] N32 — Documents archive view per client and per chantier gathering every generated devis/facture/avoir/bon de commande/bon de livraison/PV in one place (10-year retention), stored in existing object storage.
- [ ] N33 — Facture d'acompte + facture de solde workflow: chantier/devis generates a deposit invoice for a configurable percentage on signature and a balance invoice on delivery (balance auto-deducts amounts already invoiced as acompte); both fully conformant Moroccan factures with sequential numbering; existing avoir feature remains for credits.
- [ ] N34 — Configurable default acompte percentage + default payment terms in Paramètres to prefill new acompte invoices, editable per chantier.
- [ ] N35 — Échéancier / installments option on a facture splitting TTC into dated instalments, each marked paid/pending, feeding the existing payment-follow-up + aged-receivables system so reminders work per instalment; no external financing provider, no bank integration.
- [x] N36 — RIB + payment-instructions block on facture and devis PDFs, sourced from Paramètres.
- [ ] N37 — Per-line TVA on devis & factures with an editable TVA rate per line defaulting to a single configurable rate in Paramètres (current behaviour unchanged out of the box); totals chain HT → TVA per rate → TTC; per-rate VAT breakdown in PDF only when >1 rate; configurable TVA-exemption mention when a line is exempt; never hardcode which rate applies to which product.
- [ ] N38 — Local structured-invoice export for factures: UBL 2.1-shaped XML generated & stored locally including ICE/IF/RC from Paramètres + per-line VAT, clearly marked draft preview, no external DGI/clearance endpoint, no credentials — groundwork only.
- [ ] N39 — Clearance-status placeholder field on factures (Non soumise/Soumise/Validée), purely informational and manually set, so the data model is ready for a future DGI flow without any external call today.

### Loi 82-21 / Article 33 regulatory
- [ ] N40 — Dossier réglementaire section on each chantier for loi 82-21 self-production: régime field (déclaration <11 kW raccordée BT / accord de raccordement / autorisation ANRE au-delà de 1 MW), statut field (À déposer/Déposé/Approuvé/Compteur posé), reference numbers, key dates, responsible operator, attached documents via existing file-attachment feature.
- [ ] N41 — List + filter of chantiers and installed systems by regulatory dossier régime & statut so outstanding declarations/approvals are visible in one place.
- [ ] N42 — Article 33 régularisation flag + status on installed-system and lead records, with a filter to find all records needing/undergoing regularisation.
- [ ] N43 — Configurable régime-suggestion: given a chantier kWc + grid-connection type, propose the likely loi 82-21 régime as an overridable default; thresholds editable in Paramètres.

### SAV / maintenance / warranty / monitoring
- [ ] N44 — SAV ticket object linked to a Système installé (and thus client + chantier): type de panne, priorité, canal d'ouverture, date d'ouverture, statut (Ouvert/En cours/Résolu/Clos), assigned technician (default Reda), description, resolution log (activity pattern), time-to-resolution computed on closure; SAV list + kanban grouped by statut.
- [x] N45 — SAV intervention report PDF on closing a ticket (French): reported issue, diagnosis, work done, parts used, client signature block; client-facing, no buy prices.
- [x] N46 — Parts consumption on a SAV ticket optionally decrements stock for parts used and records them on the intervention report; buy prices internal.
- [x] N47 — Contrat d'entretien object linked to one or more Systèmes installés (start date, duration, visit frequency, price, renewal date) auto-generating a schedule of upcoming maintenance visits; surfaces upcoming/overdue visits in a list + on the calendar; a completed visit generates a short maintenance report PDF (French, no buy prices); flags contracts approaching renewal.
- [x] N48 — Warranty tracking on each Système installé and components: store install date + warranty duration per component (default from configured warranty texts), compute warranty end dates, "Garanties qui expirent" view, record warranty claims per component with outcome for an auditable service history.
- [x] N49 — Recurring-revenue view summarising active contrats d'entretien, monthly/annual value, upcoming renewals, lapsed contracts.
- [ ] N50 — Monitoring-integration framework with a swappable provider interface, starting with a Huawei FusionSolar connector that (given per-system credentials in config) pulls recent production data; admin enables it per system; no-ops safely when no provider is configured.
- [ ] N51 — Per-installed-system production view showing recent yield pulled by the monitoring framework when configured, with a manual-entry fallback.
- [ ] N52 — Configurable under-performance rule that (when monitoring data exists) flags a system producing below an expected threshold and optionally auto-creates a SAV ticket; threshold + auto-ticket behaviour editable in Paramètres.
- [ ] N53 — Client energy-yield report PDF (French): a system's production over a period, estimated bill savings, CO2 avoided; client-facing, no buy prices.

### Editability layer (Paramètres hub)
- [ ] N54 — Expand Paramètres into a structured settings hub with grouped sections (company identity & legal identifiers, quote/sizing parameters, TVA & billing, CRM reference data, chantier & checklist defaults, document & message templates, numbering sequences, pricing & tariff tables, warranty texts, roles & permissions, automation rules, notifications), each admin-editable and applied without a deploy; STAGES.py pipeline contract kept out of this surface entirely.
- [x] N55 — Admin audit of settings changes (who/what/when, existing audit pattern).
- [ ] N56 — Make every reference list editable by an admin from Paramètres (CRM tags, lead sources/canaux, loss reasons, activity types, SAV panne types, chantier checklist steps, units of measure, supplier categories, document types) with add/rename/reorder/deactivate; never expose the STAGES.py pipeline as editable.
- [ ] N57 — Deactivating a reference value preserves it on historical records and only removes it from new selections so reports stay consistent.
- [ ] N58 — Make chantier statuses, SAV statuses, and bon-de-commande statuses configurable in label & order from Paramètres while keeping their underlying state-machine semantics intact; never touch the protected lead pipeline.
- [ ] N59 — Document-template editor in Paramètres for the editable text portions of client-facing documents (devis/facture/acompte/avoir/PV de réception/bon de livraison/handover pack/attestation): headers, footers, legal footnotes, CGV, quote-validity text, payment-terms text, with safe placeholders for company/client/system fields; core layout engine intact; buy prices impossible to insert.
- [ ] N60 — Editable conditions générales + configurable quote-validity duration applied to new devis, with the validity date printed on the devis PDF.
- [ ] N61 — Message-template editor in Paramètres for WhatsApp/email/SMS templates (named templates, placeholders, a French default each).
- [ ] N62 — Editable numbering-sequence configuration per document type (devis/facture/acompte/avoir/bon de commande/bon de livraison/chantier/SAV): prefix, padding width, yearly-reset behaviour; engine still guarantees gap-free, non-duplicated sequences.
- [ ] N63 — Editable pricing & sizing engine in Paramètres exposing today's implicit quote parameters (default margin/target price per kWc rules, default discount limits, sizing ratios used by auto-remplir, per-region production factors), editable & versioned; lossless typed-number behaviour preserved.
- [ ] N64 — Editable ONEE electricity tariff tables + tranche thresholds in Paramètres used by the seasonal bill estimator and ROI calculation; current values seeded as defaults.
- [ ] N65 — Editable per-city/region irradiation & production-yield assumptions used to estimate annual production, seeded with Moroccan defaults, selectable on a quote.
- [ ] N66 — Configurable default lead responsable, default installer, default acompte percentage consolidated in one place.
- [ ] N67 — Editable warranty texts per product & per category in Paramètres (printed on devis & handover packs), current researched warranty texts seeded as defaults and used wherever warranties appear.
- [ ] N68 — Roles-and-permissions RBAC editor in Paramètres: define roles, grant/restrict per module & per action (view/create/edit/delete/export), restrict sensitive fields (buy prices, margins) to specific roles, safe default role set (owner/commerciale/technicien/viewer) so current access is unchanged, record-level rules limiting a user to their own assigned leads/chantiers when desired.
- [ ] N69 — Buy prices & internal margins governed by an explicit permission, visible only to roles Reda authorises, default owner-only.
- [x] N70 — Per-user activity & access view so Reda can see who did what.
- [ ] N71 — Admin-defined custom-fields system from Paramètres (text/number/date/boolean/single-select/multi-select/file) on lead/client/chantier/devis/facture/installed-system, rendered generically on forms + available in search & export, values in a dedicated side store (not altering core schema or the migration chain). [extends T11]
- [ ] N72 — No-code automation-rules engine in Paramètres (if-this-then-that over the app's own events): triggers (lead stage change, devis accepted, chantier reaching a status, facture overdue, warranty nearing expiry, maintenance visit due, stock below threshold); actions (send WhatsApp/email/SMS from a template, create activity/task, assign a record, set a field, create a SAV ticket); rules editable/enabled/disabled, all runs logged; complements not duplicates n8n.
- [ ] N73 — Simple approval-step capability in the automation engine so selected actions (e.g. a discount above a configurable threshold) require owner approval before proceeding.
- [ ] N74 — Chantier/onboarding checklists fully configurable as named workflow templates in Paramètres, selected automatically by type d'installation.

### Notifications / dashboards / analytics
- [ ] N75 — Unified notification engine: in-app + (where configured) WhatsApp/email/SMS for key events (new lead assigned, devis accepted, chantier due to install, facture overdue, warranty expiring, maintenance visit due, stock low, SAV ticket opened/breaching target); per-user & per-event preferences in settings; in-app notification centre; reuse planned templates/channels.
- [ ] N76 — Daily & weekly digest notification for Reda & Meryem (jobs to plan, quotes awaiting acceptance, overdue payments, due maintenance, open SAV), in-app and optionally WhatsApp/email.
- [ ] N77 — Tableau de bord home view (French): pipeline value/count by stage, close rate by canal & source, signed kWc & revenue for current month/quarter, chantiers by status, aged-receivables summary (existing follow-up data), active maintenance contracts + upcoming renewals, open SAV count; plain cards + simple charts.
- [ ] N78 — Job costing per chantier: realised margin from captured buy prices vs invoiced amounts; margin-per-job + margin-by-period views visible only to authorised roles.
- [ ] N79 — Saved-reports & custom-views capability: save filtered/grouped views of any major object, pin to dashboard, schedule a periodic export of a saved report by email when email is configured.
- [ ] N80 — Business analytics section: lead-source ROI when ad-spend data is available, average time lead→signature and signature→commissioning, installed kWc over time, as simple charts.

### Import/export / search / calendar / map
- [ ] N81 — Generic import-and-export framework (CSV & XLSX) for major objects (leads/clients/stock/suppliers/installed systems) with column mapping, mandatory 10-row dry-run preview before any full import, duplicate handling, audit per import; generalise the one-off Odoo lead import; real customer-data files never committed to the repo. [extends T9]
- [ ] N82 — Per-object export to CSV/XLSX from every list view respecting the user's column & filter selection and role-based field permissions. [extends T9]
- [ ] N83 — Global search across every object (leads/clients/devis/factures/chantiers/installed systems/bons de commande/SAV tickets/contrats d'entretien/regulatory dossiers) from one box with type-grouped results, respecting role permissions. [extends T5]
- [ ] N84 — Calendar/agenda view of planned installs, scheduled maintenance visits, SAV interventions, follow-up activities; filterable by assignee & type; drag to reschedule where it maps to an editable date.
- [ ] N85 — Map view plotting leads/chantiers/installed systems/scheduled visits by GPS or address, filterable by type & status, for planning site visits without heavyweight routing.

### Chatbot / integrations / API
- [ ] N86 — Extend the unified chatbot to read & act across all new objects (e.g. which chantiers à planifier, which garanties expire this quarter, which factures overdue, what production a named client's system did last month; open a SAV ticket, draft a BC for a chantier shortfall, schedule a maintenance visit), reusing the existing chatbot interface, respecting role permissions.
- [ ] N87 — Email integration to send client-facing documents & follow-ups via a configurable sending account (French templates, attach the relevant PDF, record what was sent on the client/document chatter); complements WhatsApp. [GATED-style: needs provider/cost decision]
- [ ] N88 — Inbound email capture attaching replies to the relevant client/chantier thread when a recognisable reference is present.
- [ ] N89 — Public REST API exposing core objects with token-based API keys managed in settings, scoped permissions, rate limiting, and webhooks on key events (new lead, devis accepted, chantier completed, facture paid).

### PWA / mobile / offline
- [ ] N90 — Installable PWA with Chantiers/Parc installé/SAV/calendar/bon-de-commande screens phone-usable to the same standard as the lead screens; responsive, thumb-reachable primary actions. [extends T2]
- [ ] N91 — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception signature, syncing when back online.
- [ ] N92 — Push notifications to the PWA for high-priority events from the notification engine.

### Localisation / audit / security / data
- [ ] N93 — Full Arabic & Darija localisation as a selectable interface language with RTL layout support across the app, French default, English in code; client-facing document language selectable per client (facture/devis in French or Arabic).
- [ ] N94 — Translation-management surface in settings so interface strings can be reviewed/adjusted per language without a code change.
- [ ] N95 — Comprehensive audit log across all objects (creates/updates/deletes + key actions, who/when), viewable & filterable by an admin, building the per-object chatter into a system-wide trail.
- [ ] N96 — Account security: optional 2FA, visible active sessions with revoke, forced credential-rotation flow; production DEBUG setting left unchanged.
- [ ] N97 — Configurable data export & backup action for the tenant's data (reversibility/retention), real customer-data exports kept out of the repo.

### Growth / multi-tenant platform
- [ ] N98 — Optional referral/parrainage program (referrer→referred-client links, configurable reward per converted referral, simple referral dashboard), toggle in settings.
- [ ] N99 — Optional sales-commission tracking (configurable commission per signed quote or per installed kWc for the commerciale), visible only to authorised roles.
- [ ] N100 — Build out multi-tenant operation on the existing tenant_id foundation (strict per-tenant isolation verification, tenant onboarding flow, per-tenant branding/white-label of client-facing documents, configurable per-plan feature limits, tenant-level billing).
- [ ] N101 — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup for design-partner installers.
- [ ] N102 — After the modules above are built, update the master project document + PLAN + DONE log in plain language to reflect the new post-sale, procurement/inventory, Moroccan billing/compliance, full-editability, and platform additions, noting which shipped and which were skipped.

---

## DONE LOG (PLAN2)

- 2026-06-16 — Run 2 (foundational post-sale wave). Verified real repo state first (chantier/Installation, Fournisseur, devis ACCEPTE, Moroccan legal IDs/client ICE already existed). Shipped on branch claude/optimistic-darwin-s5mxub (push-to-branch, no PR):
  - N2 chantier kanban (drag-to-status + reassign, leads visual language); N3 « Créer chantier » one-click from devis + anti-doublon (verified already present); N4 execution checklist (defaults editable in Paramètres, done/by/when, completion %); N5 photo attachments avant/pendant/après gallery; N6 chantier timeline.
  - N21 PV de réception, N22 bon de livraison, N23 dossier de remise, N24 attestations — new `documents` app PDFs (WeasyPrint, company identity, no buy prices).
  - N25 devis marked accepted (date + accepting name + chatter); N26 « Bon pour accord » capture + stamped « accepté le … par … » copy via the /proposal engine (no premium-page edit).
  - N29 facture Article 145 conformity warnings; N30 facture date de livraison + conditions de paiement (delivery date defaults from chantier MES); N31 numbering-gap detection report; N36 RIB/modalités block on the facture PDF (devis premium left untouched per rule #4).
  - N45 SAV intervention report PDF; N46 parts consumption (optional stock decrement, buy prices internal); N47 contrat d'entretien renewal flag + maintenance report PDF; N48 « garanties qui expirent » view + warranty-claim records.
  - Full local CI green (flake8, stage-check, makemigrations --check, eslint 0 errors, 88 node tests, Vite build, full backend suite). All migrations additive.
- SKIPPED / GATED this run (need external deps, paid services, auth, or new architecture — left unticked): monitoring/FusionSolar (N50-52), automation engine (N72-73), email integration/inbound (N87-88), push notifications (N92), Arabic/Darija i18n (N93-94), 2FA/security (N96), public REST API (N89), multi-tenant platform/console (N100-101). Deep procurement/inventory (N11-N20), parc-installé asset model (N7-N10), and the editability/notifications/analytics blocks (N54-N86) remain queued for future runs.

- 2026-06-16 — Run 3 (parc installé + procurement + editability). Shipped on branch (push-to-branch, no PR):
  - N7 « Système installé » : le chantier réceptionné (mise en service / clôturé) EST le système installé (marqueurs additifs parc_actif + date_reception) ; à la réception, création idempotente d'un Equipement par composant (panneau/onduleur/batterie/pompe/variateur) depuis le devis. N9 saisie des n° de série par composant (ne bloque jamais la checklist). N8 vue Parc installé (liste + filtres client/ville/marque/bande kWc/année + « carte » = liste géolocalisée avec liens OSM, aucune dépendance carto ajoutée). N10 hub par système (composants/garanties/tickets SAV/contrats + statut monitoring « Non configuré »).
  - N11 Bon de commande FOURNISSEUR (stock.BonCommandeFournisseur + lignes SKU/qté/prix d'achat, statuts Brouillon/Envoyé/Reçu, réception partielle → entrée de stock via MouvementStock, numérotation BCF sans trou). N12 PDF fournisseur interne (prix d'achat, jamais client). N13 « Besoin matériel » par chantier (besoin du devis vs stock, manques signalés, brouillon de BCF en un clic).
  - N32 archive documentaire par client et par chantier (devis/factures/avoirs/BC + PV/BL/dossier de remise/attestation, liens de téléchargement existants). N49 vue « CA récurrent » (contrats actifs, valeur mensuelle/annuelle via le nouveau champ additif ContratMaintenance.montant_mensuel, renouvellements à venir, contrats échus). N55 journal d'audit des Paramètres (qui/quoi/ancien→nouveau/quand). N70 vue « Activité utilisateurs » (agrégat des journaux existants crm/installations/sav/stock + audit Paramètres).
  - Full local CI green (flake8, stage-check, makemigrations --check, eslint 0 errors, 106 node tests, Vite build, full backend suite). Migrations additives uniquement (installations 0006, stock 0019, parametres 0011, sav 0004).
  - UI à finaliser plus tard (backend + API prêts) : écran liste/détail des Bons de commande fournisseur (N11/N12) et panneau « besoin matériel » sur la fiche chantier (N13) — exposés via stockApi/installationsApi, non encore branchés dans une page dédiée.
