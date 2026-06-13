# Equipment Registry + SAV Ticket System — Implementation Plan

> **For agentic workers:** Executed inline this session with TDD. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add an after-sales layer to the existing Chantier/Installation module: a first-class, queryable Equipment registry (one row per physical unit, with serial numbers and computed warranty clocks) and a SAV (after-sales service) ticket system whose tickets know whether the equipment they concern is still under warranty.

**Architecture:** One new Django app `apps/sav` holding `Equipement`, `Ticket`, and `TicketActivity` (chatter). Both new tables follow the established `installations` patterns exactly: `TenantMixin` company scoping, the `create_with_reference` numbering utility, an `activity.py` chatter helper cloned from `installations/activity.py`, and the funnel-order + cancel-flag pattern. Two additive numeric warranty fields land on `stock.Produit`; one additive nullable `ticket` FK lands on the existing `installations.Intervention`. Frontend mirrors the installations React patterns (api client, Redux slice, list page with FilterBar, detail modal with sub-sections + chatter, statuses.js constants).

**Tech Stack:** Django 4 + DRF, React/Vite + Redux Toolkit. No new dependencies (month arithmetic via stdlib `calendar`).

**Repo rules honored:** every model has `company` FK; querysets filtered by `request.user.company`; `company` forced server-side. STAGES.py / quote / facture statuses and PDFs untouched. `prix_achat`/margin never client-facing. References via `apps/ventes/utils/references.py`. New ticket lifecycle is its own status set.

---

## File Structure

**Backend — new app `backend/django_core/apps/sav/`:**
- `__init__.py`, `apps.py` — app config (`name = 'apps.sav'`)
- `models.py` — `Equipement`, `Ticket`, `TicketActivity`
- `activity.py` — chatter helper (clone of installations/activity.py, ticket-tracked-fields)
- `serializers.py` — `EquipementSerializer`, `TicketSerializer`, `TicketActivitySerializer`
- `views.py` — `EquipementViewSet`, `TicketViewSet`
- `urls.py` — router registering `equipements`, `tickets`
- `services.py` — `add_months`, warranty computation helper, ticket reference creation
- `tests.py` — backend tests
- `migrations/` — additive migrations

**Backend — edited:**
- `apps/stock/models.py` — add `garantie_mois`, `garantie_production_mois` to `Produit`
- `apps/stock/serializers.py` — expose the two new fields (already `__all__`, just confirm)
- `apps/installations/models.py` — add nullable `ticket` FK to `Intervention`
- `apps/roles/models.py` — add `equipement_voir/gerer`, `sav_voir/gerer` to permission lists
- `erp_agentique/settings/base.py` — register `apps.sav`
- `erp_agentique/urls.py` — mount `api/django/sav/`

**Frontend — new:**
- `frontend/src/api/savApi.js` — equipment + tickets api client
- `frontend/src/features/sav/store/equipementsSlice.js`, `ticketsSlice.js`
- `frontend/src/features/sav/equipement.js` — warranty status helpers/labels
- `frontend/src/features/sav/ticketStatuses.js` — ticket status funnel + labels
- `frontend/src/pages/sav/EquipementsPage.jsx` (+ FilterBar)
- `frontend/src/pages/sav/TicketsPage.jsx` (+ FilterBar, TicketDetail modal)
- `frontend/src/features/sav/__tests__/*.test.js(x)`

**Frontend — edited:**
- `frontend/src/pages/stock/ProduitForm.jsx` — two warranty inputs
- `frontend/src/pages/installations/InstallationDetail.jsx` — equipment sub-section + tickets sub-section
- `frontend/src/router/index.jsx` — `/equipements`, `/sav` routes
- sidebar/nav component — menu entries gated by `equipement_voir` / `sav_voir`
- `frontend/src/app/store.js` (or equivalent) — register new slices

---

## Task 1 — Structured warranty duration on Produit (foundation)

**Files:** Modify `apps/stock/models.py`, `apps/stock/serializers.py`; migration; `frontend/src/pages/stock/ProduitForm.jsx`.

- [ ] Add to `Produit`: `garantie_mois = PositiveIntegerField(null=True, blank=True, help_text='Garantie équipement en mois (laisser vide si non renseignée).')` and `garantie_production_mois = PositiveIntegerField(null=True, blank=True, help_text='Garantie production (panneaux) en mois — souvent 300-360.')`. Leave free-text `garantie` untouched.
- [ ] `makemigrations stock` (additive, both nullable — pre-authorized).
- [ ] Confirm serializer is `fields='__all__'` so the new fields round-trip; no extra exposure of prix_achat introduced.
- [ ] ProduitForm: add two number inputs (`step="1" min="0"`) in the commercial-sheet area, state init `?? ''`, included in payload (send `null` when blank, integer otherwise). Match existing input styling.
- [ ] No warranty numbers invented anywhere. Blank → equipment yields "garantie non renseignée".

---

## Task 2 — Equipement model

**Files:** `apps/sav/models.py`, `apps/sav/services.py`.

Fields: `company` FK (CASCADE, null/blank, related_name='equipements'); `produit` FK `stock.Produit` PROTECT; `numero_serie` CharField(120, blank, null); `installation` FK `installations.Installation` CASCADE related_name='equipements'; `date_pose` DateField(null, blank); `date_fin_garantie` DateField(null, blank) — computed; `date_fin_garantie_production` DateField(null, blank) — computed; `statut` choices EN_SERVICE/REMPLACE/HORS_SERVICE default en_service; `note` TextField(blank,null); `remplace_par_ticket` FK `sav.Ticket` SET_NULL null/blank related_name='equipements_remplaces'; `created_by`, `date_creation`, `date_modification`.

- [ ] `services.add_months(d, months)` using stdlib `calendar.monthrange` (clamp day). No dependency.
- [ ] Model method `recompute_garanties()`: if `date_pose` and `produit.garantie_mois` → `date_fin_garantie = add_months(date_pose, garantie_mois)` else None; same for production.
- [ ] Meta: `unique_together` not needed; index on (company, produit), (company, date_fin_garantie).

---

## Task 3 — Ticket + TicketActivity models, chatter helper

**Files:** `apps/sav/models.py`, `apps/sav/activity.py`.

`Ticket`: `company` FK; `reference` Char(50); `client` FK crm.Client PROTECT related_name='tickets_sav'; `installation` FK installations.Installation CASCADE related_name='tickets'; `equipement` FK sav.Equipement SET_NULL null/blank related_name='tickets'; `type` choices CORRECTIF/PREVENTIF; `statut` funnel choices NOUVEAU→PLANIFIE→EN_COURS→RESOLU→CLOTURE default nouveau + `STATUT_ORDER`; `priorite` BASSE/NORMALE/HAUTE/URGENTE default normale; `description` TextField; `technicien_responsable` FK user SET_NULL; `date_ouverture` DateField(null,blank); `date_resolution` DateField(null,blank); `sous_garantie` choices OUI/NON/A_DETERMINER default a_determiner (manual fallback); `cout` Decimal(10,2) null/blank (internal); `annule` Bool default False + `motif_annulation` Char(255); audit fields.
- [ ] Property `sous_garantie_calcule`: if `equipement_id` and `equipement.date_fin_garantie` → `'oui' if today < date_fin_garantie else 'non'` else `sous_garantie`. (today via `django.utils.timezone.localdate`.)
- [ ] `TicketActivity` mirrors `InstallationActivity` (ticket FK related_name='activites').
- [ ] `apps/sav/activity.py`: clone installations/activity.py — TRACKED_FIELDS {statut, type, priorite, technicien_responsable, equipement, sous_garantie, date_resolution, cout, annule, motif_annulation, description}; choice fields {statut, type, priorite, sous_garantie}; `log_creation/log_changes/log_note`.
- [ ] `makemigrations sav`. Then add `ticket` FK to Intervention (Task 5) and `makemigrations installations`.

---

## Task 4 — Serializers, views, urls, settings/urls wiring

**Files:** `apps/sav/serializers.py`, `views.py`, `urls.py`; `settings/base.py`; `erp_agentique/urls.py`.

- [ ] `EquipementSerializer`: `__all__`, read_only company/created_by/dates-computed/reference n/a; SerializerMethodFields: `produit_nom`, `produit_marque`, `installation_reference`, `client_nom`, `statut_display`, `garantie_etat` (sous_garantie / expire_bientot / hors_garantie / non_renseignee) + `garantie_jours_restants`.
- [ ] `EquipementViewSet(TenantMixin, ModelViewSet)`: search_fields numero_serie/produit nom/marque; ordering incl. date_fin_garantie; get_queryset extra filters: `produit`, `marque`(produit__marque__icontains), `installation`, `client`(installation__client), `garantie` in {sous,hors,expirant,non_renseignee} (expirant = today..today+90), `statut`. perform_create/update call `recompute_garanties()` + save; validate installation/produit belong to company. Permissions: read→`HasPermissionOrLegacy('equipement_voir')`, write→`HasPermissionOrLegacy('equipement_gerer')`, destroy→IsAdminRole.
- [ ] `TicketSerializer`: `__all__`; method fields client_nom, installation_reference, equipement_serie, equipement_produit, technicien_nom, statut_display, type_display, priorite_display, statut_ordre, `sous_garantie_effectif` (= sous_garantie_calcule) + label, `nb_interventions`, nested interventions (read-only, via installations serializer import or inline minimal).
- [ ] `TicketViewSet(TenantMixin, ModelViewSet)`: reference via create_with_reference prefix 'SAV'; perform_create sets created_by, date_ouverture=localdate if blank, log_creation; perform_update snapshot+log_changes; filters statut/type/priorite/technicien/client/sous_garantie + `ouvert` default (exclude resolu/cloture/annule unless asked), annule filter (avec/sans/seuls); ordering with funnel via statut_ordre; actions historique, noter, annuler, reactiver. Validate statut against Ticket.Statut on write. Permissions read→sav_voir, write→sav_gerer, destroy→IsAdminRole.
- [ ] urls.py router: `equipements`, `tickets`. Mount `path('api/django/sav/', include('apps.sav.urls'))`. Register `apps.sav` in INSTALLED_APPS.

---

## Task 5 — Link tickets to interventions (reuse existing model)

**Files:** `apps/installations/models.py`, serializers, views.

- [ ] Add `ticket = models.ForeignKey('sav.Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='interventions')` to `Intervention`. Additive, nullable. Existing installation→intervention behaviour unchanged.
- [ ] `makemigrations installations` (depends on sav migration).
- [ ] InterventionViewSet get_queryset: accept `?ticket=<id>` filter (keep existing `?installation=`). perform_create tenant-validates ticket belongs to company when supplied.
- [ ] On ticket detail, list its interventions + add one (frontend Task 7).

---

## Task 6 — Permissions

**Files:** `apps/roles/models.py`.

- [ ] `ALL_PERMISSIONS` += `equipement_voir`, `equipement_gerer`, `sav_voir`, `sav_gerer` (Admin full via ALL_PERMISSIONS).
- [ ] `RESPONSABLE_PERMISSIONS` (Commerciale) += `equipement_voir`, `sav_voir`, `sav_gerer` (view equipment; open & work tickets). Not `equipement_gerer`.
- [ ] `UTILISATEUR_PERMISSIONS` += `equipement_voir`, `sav_voir` (read-only, consistent with other `_voir`).
- [ ] No existing permission changed. Run `init_roles` after migrate to apply to existing companies (local + prod).
- [ ] prix_achat/margin stays hidden from non-admin exactly as today (no new exposure added).

---

## Task 7 — Frontend

- [ ] `savApi.js`: equipements CRUD + tickets CRUD + ticket historique/noter/annuler/reactiver; interventions by ticket reuse installationsApi.
- [ ] Redux slices `equipementsSlice`, `ticketsSlice` (paginated fetch-all like installationsSlice). Register in store.
- [ ] `equipement.js`: GARANTIE_ETATS labels/colors, `garantieLabel(eq)`; `ticketStatuses.js`: TICKET_STATUSES funnel, labels, colors, `statusOrder`, TYPE/PRIORITE labels, EMPTY_FILTERS.
- [ ] `EquipementsPage.jsx`: global sortable list (serial, produit, marque, installation/client, statut, fin garantie + indicator), FilterBar (search; produit/marque; garantie état incl. "expirant bientôt (90j)"; installation/client; statut), sort by date_fin_garantie. Mobile column hiding like installations ListView.
- [ ] `TicketsPage.jsx` + `TicketDetail`: list (default open; filters statut/type/priorite/technicien/client/sous_garantie; funnel sort), detail modal showing fields, linked equipment + warranty status, interventions list + add-intervention sub-form, chatter (historique + noter), status change, annuler.
- [ ] `InstallationDetail.jsx`: add **Équipements** sub-section (pick produit, serial, date_pose → create; list with warranty indicator) and **Tickets SAV** sub-section (list installation's tickets; open new ticket).
- [ ] Router: `/equipements`, `/sav`. Sidebar entries gated by `hasPermission('equipement_voir')` / `hasPermission('sav_voir')`.
- [ ] ProduitForm warranty inputs (done in Task 1).

---

## Task 8 — Tests

**Backend (`apps/sav/tests.py`, additions to `apps/installations/tests.py`):**
- [ ] `date_fin_garantie` computes = date_pose + produit.garantie_mois; production likewise; empty when garantie_mois unset.
- [ ] Global equipment filters: by produit (model), by garantie état (sous/hors/non_renseignee), by expirant (within 90 days) return exactly the right rows; sort by date_fin_garantie.
- [ ] Ticket `sous_garantie_effectif` reflects linked equipment warranty (oui when today<fin, non when after); manual value used when no equipement.
- [ ] Ticket status change writes a chatter line (old→new) and only accepts statuses from the new list (invalid rejected 400).
- [ ] Linking an intervention to a ticket works (`?ticket=` lists it) and existing installation→intervention link still works (regression).
- [ ] Company-scoping holds across Equipement, Ticket, TicketActivity (other company can't see/touch).
- [ ] Reference numbering uses utility (SAV-YYYYMM-0001, no count+1 collision).
- [ ] Permission gating: equipement_voir/gerer, sav_voir/gerer enforced.

**Frontend (`features/sav/__tests__`):**
- [ ] equipement warranty-label helper returns correct état per fin date.
- [ ] ticketStatuses funnel order + filter helper, matching existing frontend test style.

---

## Self-Review (spec coverage)

- Spec item 1 (structured warranty) → Task 1. ✓
- Spec item 2 (Equipement model incl. computed dates, statut, remplace_par_ticket) → Task 2 + 3 (FK to Ticket). ✓
- Spec item 3 (entry on chantier + global filterable/sortable list incl. 90-day quick view, mobile) → Task 4 (backend filters) + Task 7. ✓
- Spec item 4 (Ticket model, new status set, sous_garantie computed/manual, chatter, annulé flag) → Task 3 + 4. ✓
- Spec item 5 (Intervention.ticket FK, reuse) → Task 5. ✓
- Spec item 6 (ticket views global + per-installation, mobile) → Task 4 + 7. ✓
- Spec item 7 (permissions) → Task 6. ✓
- Spec item 8 (tests) → Task 8. ✓
- Excluded (ContratMaintenance, devis prefill, photos, warranty-text reconciliation) → not built. ✓
