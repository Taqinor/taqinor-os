# Module map — TAQINOR ↔ Odoo (ODX1)

Canonical mapping table between TAQINOR OS backend apps (`backend/django_core/apps/*`
plus `authentication`/`core`, which live outside `apps/`) and their nearest Odoo module
equivalent. This is the reference other ODX tasks (ODX9–ODX20) point their moves at —
each "target after move" column names the future home; "today" reflects what actually
sits in the app right now (verified against `docs/CODEMAP.md` §4 and the app source on
2026-07-05).

Scope note: this file documents structure only. No code changes. Model relocations
(ODX9–ODX20) are separate, later tasks; nothing here pre-authorizes a move.

## Legend

- **Odoo equivalent** — the closest stock Odoo app/module.
- **Today (verified)** — what the TAQINOR app actually contains right now, including
  any model that is verified to be MISPLACED relative to its natural Odoo home (called
  out explicitly — these are exactly the ODX9–ODX20 move targets).
- **Target after ODX moves** — where the misplaced content ends up; "—" means no move
  is planned for this app.

## Business-core domain apps

| TAQINOR app | Odoo equivalent | Today (verified) | Target after ODX moves |
|---|---|---|---|
| `apps/crm` | CRM | Lead/Opportunity-style records (contact, pipeline, energy profile, roof/site, light survey), `LeadActivity` chatter. STAGES.py funnel is a separate, not-yet-wired layer (rule #2). | Gains `Partenaire`/`SoumissionLeadPartenaire`/`CommissionPartenaire`/`TerritoireCommercial` from `compta` (ODX13 — resellers/territories belong in CRM's natural home). |
| `apps/ventes` | Sales (quotations, orders) + Invoicing (today) | Devis/BonCommande/Facture/Avoir/Paiement chain, quote engine (`quote_engine/`, rule #4), references factory, solar sizing. Invoicing (Facture/LigneFacture/Paiement/Avoir/LigneAvoir/FollowupLevel/RelanceLog) still lives here today — Odoo splits Sales from Invoicing. | Gains sales-config models from `compta` (CodePromotion, ModeleDevis, SessionGuidedSelling, DemandeApprobationConfig, ECatalogue, DocumentProposition, SimulationPublique/Financement, OffreFinancement, LigneIncitation, EcheancierPaiement, TranchePaiement — ODX14). Loses Invoicing-shaped models to new `apps/facturation` (ODX17/18) — Facture/LigneFacture/Paiement/Avoir/LigneAvoir/FollowupLevel/RelanceLog move out, db_table frozen, shims kept. |
| `apps/stock` | Inventory | Produit/Emplacements/MouvementStock master data, valuation, lots/serial, barcode. Supplier-purchase models (PrixFournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, ReceptionFournisseur, LigneReceptionFournisseur, FactureFournisseur, LigneFactureFournisseur, PaiementFournisseur, RetourFournisseur, LigneRetourFournisseur) still live here today — Odoo splits these into Purchase. | Loses the supplier-purchase models to new `apps/achats` (ODX19/20); Fournisseur/Produit/MouvementStock/Emplacements stay in stock as master data (res.partner/product equivalent), referenced by achats via string-FK + `selectors.py`. |
| `apps/installations` | Field Service | Chantier/jalons/interventions/light-survey execution, project docs. | — |
| `apps/sav` | Helpdesk + Repairs | Equipment registry, tickets, `ContratMaintenance` (client maintenance contracts + preventive visits), inverter alarms. | — (client equipment + `ContratMaintenance` stay here; this is NOT the internal fleet-maintenance surface — see `apps/flotte` row). |

## Recurring-revenue / CLM cluster (verified overlap, no move needed)

| TAQINOR app | Odoo equivalent | Note |
|---|---|---|
| `apps/contrats` | Sign + Contracts (subscriptions/CLM) | The master juridical/CLM system: state machine, e-sign (loi 53-05), avenants, résiliation, indexation, `EcheancierContrat`/`LigneEcheance` → standard `ventes.Facture` via `references.py`, MRR selectors. |
| `apps/sav` (`ContratMaintenance`) | Repairs/maintenance subscription | Own preventive-visit cadence + `facturer()` → standard `ventes.Facture`, independent `facturation_active` guard. Coexists deliberately with `apps/contrats` (different lifecycle owner); `ContratLien` is the loose cross-app link. |
| `apps/compta` (`AbonnementMonitoring`, FG244) | Subscriptions | Status + `prochaine_echeance` tracking only, no invoicing wired. **Relocation decision pending founder (ODX16)**: proposed default = `apps/monitoring` (references supervision configs it tracks), alternative = `apps/ventes` (recurring revenue). Recorded here per ODX16's "Done" requirement; not yet moved. |

## Compta split targets (ODX9–ODX18)

`apps/compta` today holds several models verified to be OUTSIDE its Odoo-equivalent
scope (Accounting: chart of accounts, journals, ledger, statements, TVA, fiscal). The
table below is the authoritative move list ODX9–ODX18 execute against — each row names
the ODX task performing the move, using the state-only recipe (frozen `db_table`,
`SeparateDatabaseAndState`, re-export shims in `apps/compta/models.py`, zero SQL).

| Models (today in `apps/compta`) | Move to | Odoo equivalent | ODX task |
| --- | --- | --- | --- |
| Marketing campaign/sequence/NPS objects (FG201-208/238-241) | `apps/marketing` (new) | Email/SMS Marketing + Automation | ODX9 (models) / ODX10 (views/urls/frontend) |
| AppelOffre, BordereauPrix, LigneBordereau, CautionSoumission, DossierSoumission, PieceSoumission, EcheanceAO, ResultatAO (FG222-227) | `apps/ao` (new) | No direct Odoo equivalent — Moroccan public/private tender differentiator | ODX11 |
| ComptePortailClient, AcceptationDevisPortail, PaiementFacturePortail, DocumentClientPortail, JalonChantierPortail, DemandeTicketPortail (FG228-233) | `apps/portail` (new) | Portal | ODX12 (AUTH-sensitive — auth mechanism moved as-is, no access widening) |
| Partenaire, SoumissionLeadPartenaire, CommissionPartenaire, TerritoireCommercial (FG234-237) | `apps/crm` | CRM (resellers/territories) | ODX13 |
| CodePromotion, ModeleDevis, SessionGuidedSelling, DemandeApprobationConfig, ECatalogue, DocumentProposition, SimulationPublique, SimulationFinancement, OffreFinancement, LigneIncitation, EcheancierPaiement, TranchePaiement (FG209-221) | `apps/ventes` | Sales (quotation templates, pricelists, online quotes) | ODX14 |
| NoteFrais, RapportNoteFrais, PlafondNoteFrais, BaremeIndemnite, IndemniteChantier (FG135/136 + ZACC6/XACC27/XACC28) | `apps/frais` (new) | Expenses | ODX15 — **DONE**; duplicate decision = *document the boundary* (see below) |
| AbonnementMonitoring (FG244) | `apps/monitoring` or `apps/ventes` | Subscriptions | ODX16 — DECISION pending (see recurring-revenue cluster row above) |

The GL posting itself (écritures, period lock FG115) stays in `apps/compta` regardless
of which satellite app owns the front-end object — satellites call
`apps/compta/services.py`, never write GL rows directly (services.py boundary,
CLAUDE.md).

### ODX15 — expense-note duplicate: the boundary is DOCUMENTED, not merged

Two expense models exist and **both stay**. Merging them would mean a destructive
data migration and an irreversible product decision, so ODX15 took the revertible
option and froze the boundary instead. No third surface was created.

| | `rh.NoteDeFrais` (FG199) | `frais.NoteFrais` (FG135) |
| --- | --- | --- |
| Purpose | employee **self-service declaration** from the RH portal | **validation + accounting posting** by a responsable |
| Employee FK | `rh.DossierEmploye` (HR record) | `AUTH_USER_MODEL` (ERP account) |
| Lifecycle | `soumise → approuvee → remboursee / refusee`, status flips only | `brouillon → soumise → validee → remboursee / rejetee` |
| Accounting | **none** — no journal entry, no treasury account, no period lock | posts 6143/4432 on validation, 4432/treasury on reimbursement, honours the FG115 period lock |
| Reference | none | `NDF-YYYYMM-NNNN` via `apps/ventes/utils/references.py` |
| Route | `/api/django/rh/notes-frais/` | `/api/django/frais/notes-frais/` (+ legacy `/api/django/compta/notes-frais/`) |
| Table | `rh_notedefrais` | `compta_notefrais` (frozen by the state-only move) |

The two have **no FK and no import between them** — they were already independent and
remain so. If the founder later wants one funnel, the natural follow-up is a one-way
promotion (`rh.NoteDeFrais` *approuvee* → create a `frais.NoteFrais` through
`apps/frais/services.py`), which is additive; that is deliberately NOT built here.

`apps/frais` owns the entry and the reference data (notes, reports, policy caps,
mileage scales, site allowances); `apps/compta` keeps the posting. `apps/frais`
references accounts/entries/treasury by **string FK only** (`'compta.CompteComptable'`…)
and calls `apps/compta/services.py` for every journal entry — enforced by the
`frais-models-decoupled` import-linter contract. `apps/frais/services.py` and
`selectors.py` are the app's façade so callers (e.g. `apps/paie`, XPAI25) never touch
`apps/compta.models`.

## New Invoicing / Purchase split (ODX17-20)

| Move | From | To (new app) | Odoo equivalent | ODX task |
| --- | --- | --- | --- | --- |
| Facture, LigneFacture, Paiement, Avoir, LigneAvoir, FollowupLevel, RelanceLog | `apps/ventes` | `apps/facturation` (new) | Invoicing (separate from Sales) | ODX17 (models, state-only) / ODX18 (views/urls/recouvrement/frontend) |
| PrixFournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, ReceptionFournisseur, LigneReceptionFournisseur, FactureFournisseur, LigneFactureFournisseur, PaiementFournisseur, RetourFournisseur, LigneRetourFournisseur | `apps/stock` | `apps/achats` (new) | Purchase | ODX19 (models, state-only) / ODX20 (views/urls/stock-flow/frontend) |

Invariants that survive every move above unchanged: `/proposal` stays the only
client quote-PDF path (rule #4); invoices keep their own legacy PDF; numbering stays on
`apps/ventes/utils/references.py` (never `count()+1`); `Produit.prix_achat` /
`PrixFournisseur` never reach client-facing output; STAGES.py funnel (rule #2) is
untouched by any of these moves.

## Foundation / technical layer apps (no Odoo storefront equivalent — exempt from moves)

| TAQINOR app | Role |
|---|---|
| `core` (not under `apps/`) | Base foundation layer: abstract models, event bus (`core/events.py`), AI scorers, BPM engine, soft-delete/idempotency/money-rounding bases. Imports no domain app (`.importlinter` `core-foundation-is-a-base-layer`). |
| `authentication` (not under `apps/`) | Tenant root, users, JWT, `Company`. |
| `apps/roles` | RBAC |
| `apps/records` | Generic activities + attachments |
| `apps/customfields` | Admin-defined custom fields |
| `apps/parametres` | Company profile, business settings, message templates |
| `apps/reporting` | Dashboards/KPIs/insights/audit views (no models) |
| `apps/audit` | Activity log / audit trail |
| `apps/documents` | Field-execution PDFs (no models) |
| `apps/dataimport` | CSV/XLSX import (no models) |
| `apps/contact` | Public contact form (parked, no models) |
| `apps/monitoring` | Production supervision (N50-52) — candidate home for `AbonnementMonitoring` (ODX16) |
| `apps/notifications` | Unified notification engine |
| `apps/automation` | No-code rules engine |
| `apps/publicapi` | Public REST API + webhooks |
| `apps/agent` | Agentic action catalogue (Group R) |
| `apps/chat` | Internal team messaging ("Discuss" equivalent) |
| `apps/pos` | Point of sale surface |
| `apps/tiers` | `res.partner`-style third-party consolidation (Client/Fournisseur/Partenaire unification + doublons cross-referencing, ARC18-21). Foundation layer — string-FK targets only; no ODX move. |

## Odoo modules with a TAQINOR home already, no move needed

| TAQINOR app | Odoo equivalent | Note |
|---|---|---|
| `apps/flotte` | Fleet + Maintenance | Internal fleet already lives here (Vehicule/EnginRoulant/PlanEntretien/EcheanceEntretien/OrdreReparation) plus `apps/outillage` for durable tools/kits — **no move required**; this is distinct from `sav.ContratMaintenance` (client-facing maintenance contracts, stays in sav). |
| `apps/ged` | Documents | DMS: Cabinet/Folder/Document/Version, ACL, retention, watermarking. |
| `apps/contrats` | Sign / Contracts | See recurring-revenue cluster above. |
| `apps/kb` | Knowledge | Articles, ACL, templates. |
| `apps/chat` | Discuss | Internal messaging, no move. |
| `apps/rh` | Employees / Time Off / Attendances | Employee master, pointage, competences, habilitations. |
| `apps/paie` | Payroll | CNSS/AMO/IR parameters, bulletins, rubriques. |
| `apps/gestion_projet` | Project | Multi-chantier programs, WBS, budgets, resourcing. |
| `apps/qhse` | Quality | NCR/CAPA, audits, risk evaluations, LOTO. |
| `apps/litiges` | (no exact Odoo module — closest: Helpdesk escalation) | Disputes/claims register. |
| `apps/outillage` | Maintenance (tooling side) | Durable field tools & kits, pairs with `apps/flotte`. |

## Order of moves (ODX9 → ODX20)

1. ODX9 (marketing models) → ODX10 (marketing views/urls/frontend)
2. ODX11 (ao models+views, `@after: ODX2`)
3. ODX12 (portail models+views, AUTH-sensitive, `@after: ODX2`)
4. ODX13 (crm partners/territories, `@after: ODX2`)
5. ODX14 (ventes sales-config, `@after: ODX2`)
6. ODX15 (frais — DONE; duplicate decision = document the boundary, see above)
7. ODX16 (AbonnementMonitoring relocation — gated on founder decision, `@after: ODX1`)
8. ODX17 (facturation models) → ODX18 (facturation views/urls/recouvrement/frontend)
9. ODX19 (achats models) → ODX20 (achats views/urls/stock-flow/frontend)
10. ODX22 (extend import-linter contracts to the post-split graph, `@after: ODX10, ODX18, ODX20`)

Every move in this order uses the same state-only recipe: `db_table` frozen to its
current name, `SeparateDatabaseAndState` migrations (state ops only, revertible),
re-export shims left in the source app's `models.py` for existing callers, and old URLs
kept serving identically alongside the new ones. Zero raw SQL, in keeping with rule #1
(and by extension the same discipline applied to this repo's own Postgres, not just any
future Odoo integration).

## Decisions taken (duplicate-model reconciliations)

### WIR86 — Programme/Projet multi-chantiers: `gestion_projet` is canonical (2026-07-18)

**The duplicate.** Two near-identical Projet families existed side by side, with zero
references between them:

| | `apps/installations` (FG291-301) | `apps/gestion_projet` |
|---|---|---|
| Models | 7 (`Projet`, `ProjetTache`, `ProjetChantier`, `ProjetDevis`, `ProjetTicket`, `BudgetProjet`, `BudgetEngagement`) in `models_program.py` | 39 (`Projet`, `PhaseProjet`, `Tache`, `DependanceTache`, `Jalon`, baselines, ressources, timesheets, risques, situations, portail client…) |
| Endpoints | 7 (`/installations/programmes/`, `programme-taches/`, `programme-chantiers/`, `programme-devis/`, `programme-tickets/`, `programme-budgets/`, `programme-engagements/`) | 39 (`/gestion-projet/projets/`, `projet-chantiers/`, `budgets/`, `lignes-budget/`, …) |
| Frontend | **none** (0 references) | `frontend/src/api/gestionProjetApi.js` + `frontend/src/features/gestion_projet/*` — live, incl. the devis → projet creation flow |
| Cross-app FKs in | 1 (`installations.DemandeAchat.programme`) | 0 |

**Decision: consolidate on `apps/gestion_projet`.** It is the richer family (39 vs 7
models), it is the only one wired to a UI, and it is the one a user can already reach.
Building a second, distinct frontend for the `installations` family (the alternative
WIR86 offered) would have duplicated a live surface — rejected.

**Retirement plan — engaged, phase 1 landed, nothing destroyed.** No data is deleted and
no table is dropped by this decision; it is reversible by removing one mixin.

1. **Phase 1 (done, WIR86).** The 7 `installations` program endpoints are **frozen and
   deprecated**: `DeprecatedProgrammeSurfaceMixin`
   (`apps/installations/views/program.py`) stamps every response with the RFC 8594
   `Deprecation: true` header and `Link: </api/django/gestion-projet/projets/>;
   rel="successor-version"`. Behaviour, permissions and company scoping are byte-for-byte
   unchanged (`apps/installations/tests_wir86_programme_deprecie.py`). **Standing rule
   from here on: no new feature, no new field, no frontend screen on the `installations`
   program family — new project work goes to `apps/gestion_projet`.**
2. **Phase 2 (later, needs real production data).** Reconcile any rows that actually
   exist: copy each `installations.Projet` into a `gestion_projet.Projet`, and repoint
   `installations.DemandeAchat.programme` — the single cross-model FK — at the loose
   `projet_id` style `gestion_projet` uses (that app deliberately references chantiers
   and clients by plain id, so no cross-app model import is needed).
3. **Phase 3 (only after phase 2 is verified in production).** Drop the 7 tables with a
   normal revertable Django migration, remove the routes, and delete
   `models_program.py` + its tests. Not before — a table drop is the only irreversible
   step in the sequence, so it stays a separate, explicit task.

**Which fields survive the merge.** `gestion_projet.Projet` lacks a few things
`installations.Projet` carried (`site_adresse`/`site_ville`, a real `client` FK, and the
flat `BudgetProjet` envelope `budget_materiel`/`budget_main_oeuvre`/
`budget_sous_traitance`/`budget_divers` + `tarif_jour_mo` + `seuil_alerte_pct`). Phase 2
must add the missing ones to `gestion_projet` (or map the envelope onto
`LigneBudgetProjet` rows) before anything is dropped — a merge that silently loses the
budget envelope would be a data loss, not a consolidation.

### WIR113 — Suivi GPS terrain (XFSM23): WEB-FIRST, and NTMOB9 reconciled (2026-07-18)

**The question.** Three backend families shipped with zero frontend references —
`gps-consentements/`, `positions-techniciens/`, `geofence-alertes/`
(`apps/installations/models_gps_tracking.py`, `views/gps_tracking.py`). Were they
waiting on a separate mobile app, or should the web app own them?

**Decision: WEB-FIRST.** There is no separate mobile codebase in this repo, and none is
planned in any open queue. Field work already happens through this responsive React
frontend: "Ma journée" is the technician's daily screen, and the F6 check-in already
calls the browser's `geolocation` API from it. Even NTMOB9 — the task that appeared to
imply a mobile app — specifies `watchPosition`, i.e. a **browser** API. So "mobile" here
means the responsive web app, and the missing piece was simply the supervisor screen.

**Built:** `frontend/src/pages/installations/SuiviGpsPage.jsx` at
`/planification/suivi-gps` (`responsable`/`admin` only, matching the backend's
`IsResponsableOrAdmin`): consent tab (record / read / revoke), live map tab (Leaflet
`MapView`, last known position per technician, red marker = outside the site perimeter),
geofence-alert tab (list + acknowledge). API wrappers appended to
`frontend/src/api/installationsApi.js`; tests in `SuiviGpsPage.test.jsx`.

**Privacy invariant the screen enforces.** Consent is explicit and revocable: the create
dialog requires an affirmative confirmation checkbox, every consent row can be revoked,
and the backend already refuses (403) any position `ping` without an active consent.
There is no silent tracking path, and this screen is the only place consent is granted.

**NTMOB9 reconciled.** NTMOB9 proposed a new `installations.PointageGeofence` model for
geofenced check-in/out. That data already exists: consent in `GpsConsentRecord`, the
position in `PositionTechnicien`, the perimeter crossing in `GeofenceAlert`. NTMOB9 is
annotated with the WIR80 guard (`docs/new_tasks_plan.md`) and must be built as at most a
small `entree|sortie` addition to the existing models plus the `watchPosition` wiring in
"Ma journée" — never as a second table.
