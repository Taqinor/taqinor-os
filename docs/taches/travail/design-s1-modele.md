# S1 — Architecture & modèle de données du gestionnaire de tâches (`apps/taches`)

Paths relative to `backend/django_core/` unless noted. Every claim cites a file read in this session.

## 1. Structuring decision — **A (new app `apps/taches`, federating `records.Activity`)**

### Case for B (extend `records.Activity`)
- One row type literally; `mine` (records/views.py:461-484), `ma-file` (:487-652), the iCal feed (reporting/calendar.py:491-500) and snooze (views.py:708-738) would show tasks for free.
- B' variant (a `taches` OneToOne extension on a personal Activity) keeps records' columns untouched and still gets those surfaces.

### Case against B (decisive)
1. **Activity is already triple-duty**: planned activity + generic chatter (ARC8, models.py:123-130, `kind` creation/modification/note) + personal to-do (XKB4, models.py:144-155). Every chatter log of every lead lives in this table. Adding project/section/rank/priority/estimate/recurrence/day-plan columns, or a project FK, to the chatter table is the foundation bloat the brief warns about; projects/sections would have to live in `records` too.
2. **Platform primitives cannot be retro-fitted**: Activity is a hand-rolled-company model frozen in the SCA4 baseline (`records/platform_baselines/handrolled_models.txt:246`), not `TenantModel`; it has no soft delete and no `lock_version`. Making it `SoftDeleteModel` would swap the default manager (core/models.py:175) under every chatter query in the repo.
3. **Visibility semantics block the future**: `personnelle=True` means "creator only, never a colleague, even an admin" (views.py:390-393). Sharing a project or assigning a task later contradicts that flag; B' inherits the same trap plus `activity_type` PROTECT, ZSAL1 chaining and `auto_relance`.
4. **Write permissions are wrong for a personal tool**: create/done/snooze require `IsResponsableOrAdmin` (views.py:383, 656, 709). A `normal` role cannot add or close its own to-do today.
5. **Ownership**: `apps/records/**` belongs to the `securite` unit (docs/ownership.yml:482). B means deep, risky edits in a foreign, security-owned app.

### Rejected C
`core.Dossier` (core/models.py:759-877, type `projet_transverse`, checklist :928) is a TEAM case object: closed type catalogue, no colour/objective/sections/order, and it lives under the strictest import-linter contract (`.importlinter:448-509`). Wrong fit. A new generic "work item" in `core` would be overreach.

### How A stays ONE system for the user
- **One place to type**: every quick capture (taches screen, command palette, the « + À faire » of `MesActivitesPage.jsx:249-355`) POSTs `taches/taches/`. Personal `Activity` creation stays in the API for compatibility (views.py:424-434). No UI calls it anymore.
- **One daily list**: `GET taches/aujourdhui/` returns the user's tasks plus their open activities, read-only, through a NEW `apps/records/selectors.py` (records has none today, as the Glob of `apps/records/*.py` shows). It is `activites_ouvertes_pour(user, jusquau)` and centralises the snooze rule and the archived-target rule now copied three times (views.py:470-472, 517-524; calendar.py:493-494).
- **Done anywhere = done everywhere**: an activity in the list is closed through its EXISTING endpoint `records/activities/<id>/done/`. That keeps the chatter log (views.py:907) and the chaining (:960). The aggregate sends `peut_cloturer` (risk 3).
- **Convert**: `convertir-activite` turns a PERSONAL activity into a task (`activite_origine`, unique). It closes the source through a new thin `records.services.cloturer_a_faire_personnel()`. An ERP-assigned activity is never closed by conversion. Instead « lier une tâche » creates a task on the same target.
- **VX83 "one queue" decision honoured**: `ma_file` declares itself THE single cross-module queue, « jamais une nouvelle app inbox » (views.py:489-494). Taches therefore FEEDS it with `apps.taches.selectors.affectations_pour(user)`, kind `tache`, using the existing contract `{kind,title,due,link,urgency}` (sav/selectors.py:1429, installations/selectors.py:2814). That means one append-only block in `ma_file` plus `_EFFORT_ESTIME_PAR_KIND['tache']` (views.py:244). It also feeds the iCal feed with `selectors.evenements_calendrier(user, start, end)` appended to `_user_calendar_events` (calendar.py:433-502). Timed events use the VX245 `start_dt` form (calendar.py:556-560).

## 2. Data model (`apps/taches/models.py`)

All models inherit `core.models.TenantModel` (core/models.py:62; `company` + timestamps). Users are FKs to `settings.AUTH_USER_MODEL`. Every CASCADE carries `# on_delete:`. Every unique constraint starts with `company`. Index names are explicit and ≤ 30 characters (Django E034). Dates use `timezone.localdate()` (Africa/Casablanca). Do not copy `date.today()` from calendar.py:445.

**Projet** (`TenantModel, SoftDeleteModel, VerrouOptimisteMixin`). The last two come from core/models.py:155 and core/champs_plateforme.py:31.
- `proprietaire` FK user, CASCADE (personal data follows its account).
- `nom` Char(120); `objectif` Text blank; `icone` Char(8) blank.
- `couleur` Char(16), choices = a closed palette of keys (theme-safe in dark mode), default `bleu`.
- `priorite` `Priorite(IntegerChoices)`: 0 aucune / 1 basse / 2 moyenne / 3 haute, default 0. Shared with Tache and sortable.
- `statut` Char(12): `actif`/`en_pause`/`termine`/`archive`, default `actif`.
- `date_debut`, `echeance`: Date null (the planning phase); `termine_le` DateTime null.
- `rang` Integer default 0.
- `visibilite` Char(10): `prive`/`partage`, default `prive`. Only `prive` is served in v1. This is the extension point for a future `MembreProjet(projet, user, role)`.
- Constraint `taches_projet_nom_uniq` (company, proprietaire, nom) WHERE `is_deleted=False`. It lets quick-add resolve `#nom` and create the « Nouveau projet » on the fly.
- Index `taches_projet_stat_idx` (company, proprietaire, statut).

**Section** (TenantModel). It is a section and also a planning phase.
- `projet` FK, CASCADE (composition).
- `nom` Char(120); `rang` Integer; `date_debut`, `date_fin` Date null.
- Index `taches_section_rang_idx` (projet, rang).
- Hard delete. Its tasks fall to "no section" (SET_NULL below).

**Tache** (`TenantModel, SoftDeleteModel, VerrouOptimisteMixin`).
- `proprietaire` FK user, CASCADE. `assigne_a` FK user, SET_NULL, null. It is read-only and equal to the owner in v1 (the assignment seam).
- `projet` FK Projet, null (null = Boîte de réception), CASCADE (a trash purge follows its project). `section` FK, SET_NULL, null.
- `parent` FK self, null, CASCADE (sub-task, one level, enforced in the service).
- `titre` Char(255); `notes` Text blank.
- `statut` Char(10): `a_faire`/`en_cours`/`fait`/`annule`. `fait_le`, `annule_le`: DateTime null.
- `priorite` Priorite.
- `jour_prevu` Date null: "when I will do it" (Things *When*). `moment` Char(10): ''/`matin`/`apres_midi`/`soir` (« Ce soir »).
- `echeance` Date null and `echeance_heure` Time null: the hard deadline, kept separate from the planned day.
- `quelque_jour` Bool default False (Someday).
- `estimation_minutes` PositiveSmallInt null; `duree_reelle_minutes` PositiveInt null (deferred UI).
- `rang_projet` Integer: order inside inbox/project/section. `rang_jour` Integer: order inside Today.
- `premier_jour_prevu` Date null; `reports` PositiveSmallInt default 0. The service increments it only when `jour_prevu` moves later, on rollover, or on an explicit report.
- `source` Char(12): `manuel`/`rapide`/`assistant`/`raccourci`/`activite`/`recurrence`/`import`.
- ERP link without importing models: `content_type` FK ContentType, null, CASCADE, plus `object_id` PositiveInt null. It is validated by `records.serializers.resolve_target` (records/serializers.py:44-85: allowed target + same company + lead scope). `lien_libelle` Char(200) is a snapshot, following the `DossierLien.libelle` pattern (core/models.py:900).
- `activite_origine` FK `'records.Activity'`, SET_NULL, null. Records is a foundation app, so the FK is permitted.
- `recurrence` FK RegleRecurrence, SET_NULL, null; `occurrence_du` Date null.
- Constraints: `taches_tache_act_uniq` (company, activite_origine) WHERE not null; `taches_tache_occ_uniq` (company, recurrence, occurrence_du) WHERE not null.
- Indexes:
  - `taches_tache_jour_idx` (company, proprietaire, statut, jour_prevu)
  - `taches_tache_ech_idx` (company, proprietaire, statut, echeance)
  - `taches_tache_proj_idx` (projet, section, rang_projet)
  - `taches_tache_fait_idx` (company, proprietaire, fait_le)
  - `taches_tache_cible_idx` (content_type, object_id)
- Meta ordering `['rang_projet', 'id']`.

**ElementChecklist** (TenantModel).
- `tache` FK, CASCADE.
- `libelle` Char(255); `fait` Bool; `fait_le` DateTime null; `rang` Integer.
- Index `taches_check_rang_idx` (tache, rang).

**RegleRecurrence** (TenantModel). The smallest sound design: one open instance at a time, the next one created when the current one is completed. Missed occurrences never pile up as guilt, and no beat sweep is needed.
- `proprietaire` FK user, CASCADE.
- `frequence` Char(12): `quotidien`/`jours_ouvres`/`hebdo`/`mensuel`/`annuel`.
- `intervalle` PositiveSmallInt default 1; `jours_semaine` Char(7) bitmask `'1111100'`; `jour_du_mois` SmallInt null.
- `mode` Char(12): `calendrier`/`apres_fait`.
- `date_debut` Date; `date_fin` Date null; `actif` Bool.
- `prochaine_occurrence(regle, apres)` is a PURE stdlib function (`calendar.monthrange` for month-end clamping). dateutil is used in production (outillage/models.py:81) but is NOT pinned in `requirements*.txt` (the grep found nothing). Idempotence comes from `taches_tache_occ_uniq`.

**PlanJour** (TenantModel). This is the daily snapshot and the stats row.
- `proprietaire` FK, CASCADE; `jour` Date. Unique `taches_planjour_uniq` (company, proprietaire, jour), which backs `get_or_create`.
- `objectif_nb` PositiveSmallInt null (the goal in force that day); `capacite_minutes` null.
- `planifie_le`, `cloture_le` DateTime null; `reflexion` Text blank.
- Counters refreshed by the service: `nb_prevues`, `nb_faites`, `nb_importantes_prevues`, `nb_importantes_faites`, `minutes_prevues`, `minutes_faites`, `nb_reportees`.
- The row is created lazily for any day with a plan or a completion. That gives "non-missing days" for the WalkIT rule (60th percentile of the last 9 days) without a separate stats table.

**LignePlanJour** (TenantModel). It separates "planned in the morning" from "added later", which an honest plan-completion ratio needs.
- `plan` FK, CASCADE; `tache` FK, SET_NULL, null; `activite_id` PositiveInt null (opaque).
- `titre_fige` Char(255); `prevue_au_plan` Bool; `faite` Bool; `reportee` Bool.
- Unique `taches_ligne_uniq` (company, plan, tache).

**ReglagesRythme** (TenantModel).
- `utilisateur` FK, CASCADE. Unique `taches_reglages_uniq` (company, utilisateur).
- `mode` Char(12): `progresser`/`maintenir`/`libre`.
- `objectif_nb_jour` PositiveSmallInt null; `objectif_auto` Bool.
- `jours_travailles` Char(7); `conges_du`, `conges_au` Date null (vacation mode, no streak penalty).
- `heure_plan`, `heure_cloture` Time null.
- `max_incitations_jour` PositiveSmallInt default 2 (habituation cap).
- `jeton_capture_hash` Char(64) blank; `jeton_capture_cree_le`. For Siri/Scriptable later, rotated like the ICS token (calendar.py:625-631).

**IncitationCoach** (TenantModel). The coach log.
- `utilisateur` FK, CASCADE; `jour` Date.
- `type` Char(20): `plan_matin`/`cloture_soir`/`surcharge`/`report_repete`/`objectif_ajuste`/`retour_info`.
- `canal` Char(10): `ecran`/`push`/`assistant`.
- `texte` Text; `donnees` JSON (every figure plus its computation, for the zero-invented-number rule).
- `montre_le`, `ouvert_le` DateTime null; `reponse` Char(10): ''/`accepte`/`ignore`/`refuse`.
- Unique `taches_incit_uniq` (company, utilisateur, jour, type). The daily total cap is enforced in the service against `max_incitations_jour`.

**Ordering strategy.** Gapped integers (step 1 024): insert at the midpoint means one write. When the gap is exhausted, the service renumbers that list only. This is the house precedent of contiguous integer `ordre` with `reordonner` (uxviews/views.py:608-631), made one-write. Fractional strings (lexorank) would need a library. Floats degrade.

**Core vs deferred.**
- v1-core: Projet, Section, Tache, ElementChecklist, RegleRecurrence, PlanJour, LignePlanJour, ReglagesRythme.
- v1.1: IncitationCoach plus the coach lane; Tache.parent UI; `duree_reelle`; capture token; tags/comments/attachments (risk 2); search; offline.
- Labels: reuse `records.Tag`/`TaggedItem` (records/models.py:238-295). No own model.

## 3. API (`/api/django/taches/…`, mounted via `_APP_URLS`; viewsets on `CompanyScopedModelViewSet` core/viewsets.py:65)

| Method + path | Purpose |
|---|---|
| CRUD `projets/` (+`POST {id}/reordonner/`, `GET {id}/vue/`) | sidebar list; project screen = sections + tasks grouped, one call |
| CRUD `sections/` (+`reordonner`) | sections/phases |
| CRUD `taches/` filters `vue=boite\|a_venir\|quelque_jour\|fait`, `projet`, `section`, `q` | lists; DELETE = soft delete |
| `POST taches/{id}/terminer/`, `/rouvrir/` | returns task + next recurrence instance + refreshed day counters |
| `POST taches/{id}/planifier/` `{jour_prevu, moment, quelque_jour}` | the only path that moves the date and counts reports |
| `POST taches/{id}/reordonner/` `{liste:'jour'\|'projet', avant_id, apres_id}` | drag |
| `POST taches/saisie-rapide/` `{texte}` | deterministic parser (`#projet`, `!p1`, `demain`, `ce soir`, `15 min`); creates the project when `#nom` is unknown; returns task + what was understood |
| `POST taches/convertir-activite/` `{activite_id}` | conversion (§1) |
| CRUD `checklist/` (+`reordonner`) | checklist |
| `GET aujourdhui/?jour=` | THE aggregate |
| `GET a-venir/?du=&au=` | 7 to 14 days, grouped by day |
| `POST journee/planifier/`, `POST journee/cloturer/` | morning plan (capacity warning); evening shutdown (reflection + explicit choice for each leftover: tomorrow / someday / drop, never silent) |
| `GET rythme/?jours=28` | stats + suggested goal with its trace |
| `GET/PATCH reglages/` | pace settings |
| `GET coach/`, `POST coach/{id}/reponse/` (v1.1) | nudges |

**Permissions.** `read_permission='taches_voir'`, `write_permission='taches_gerer'` (the `ScopedPermission` hooks, core/viewsets.py:94-102; same pattern as visites/views.py:225,256). `get_queryset` = `super()` filtered on `proprietaire=request.user`. Admins never see another user's rows, consistent with XKB4 (views.py:390-393).

Lists are paginated with the project default. `aujourdhui` is not paginated but capped at 200 rows, with `tronque: true`.

```json
{"jour":"2026-11-17","objectif":{"nb":5,"mode":"maintenir","source":"auto","trace":"60e centile de 9 jours : …"},
 "progression":{"prevues":6,"faites":2,"importantes_prevues":2,"importantes_faites":1,"minutes_prevues":210,"capacite_minutes":360},
 "plan":{"planifie_le":null,"cloture_le":null},
 "en_retard":[ITEM], "journee":[ITEM], "ce_soir":[ITEM],
 "a_trier":{"boite_reception":3},
 "ailleurs":{"approbations":2,"mentions":1,"lien":"/activites"},
 "incitations":[]}
```
`ITEM = {"type":"tache"|"activite","id":12,"titre":"…","projet":{"id":3,"nom":"…","couleur":"vert"}|null,"priorite":3,"jour_prevu":"…","moment":"","echeance":"…","echeance_heure":null,"estimation_minutes":30,"reports":2,"lien":{"cible":"crm.lead","id":1637,"libelle":"…","url":"/crm/leads/1637"}|null,"checklist":{"faits":1,"total":3},"recurrente":true,"lock_version":4,"peut_cloturer":true}`

The `ailleurs` counters come from the same sources `ma_file` reads (views.py:549-596). Today never re-lists approvals or mentions; it points to the one queue.

**`contract_samples/`** (PACT10, landed first): `aujourdhui.json`, `tache.json`, `projet_vue.json`, `saisie_rapide.json`, `journee.json` (plan + clôture), `rythme.json`, `reglages.json`. Each is exported in `frontend/src/test/fixtures/contractSamples.js`.

## 4. Permissions, manifest, platform, events
- **Permissions.** Two codes are enough: data is private, so codes only gate the module. Add `taches_partager` when sharing lands. Grant both to every system role. Roles carrying an app marker are a WHITELIST (permissions_registre.py:1102-1116, Commercial terrain): they need `permission_app('taches')` too, which is an open question.
- **Manifest** (`apps.py`, pattern outillage/apps.py:8-16): `{'key':'taches','sku':'solar_core','label':'Tâches','icone':'check','depends':[],'categorie':'Productivité'}`.
- **`platform.py`** (outillage/platform.py:11-21):
  - v1: `record_targets: []`.
  - v1.1: `record_targets: ['taches.tache','taches.projet']`, `searchable_models: ['taches.tache']` plus a `_spec_tache` filtered on the owner in `reporting/search.py:430`, and `agent_actions_module: 'apps.taches.agent_actions'`.
- **Trash**: `SoftDeleteModel.soft_delete` already emits `record_soft_deleted` (core/models.py:213-224). In `ready()`, register `enregistrer_restaurateur('taches.projet'|'taches.tache', …)` (trash/registry.py:27). The project restorer refuses on a live name clash with `taches_projet_nom_uniq`.
- **Events**: none in v1. A declared signal without a receiver fails YEVNT7 (core/event_coverage.py:7-16, `ALLOWED_UNCONSUMED` :45), and every signal must be catalogued (core/event_catalog.py:45). When a consumer exists (crm logging « tâche liée faite » on the lead chatter), add `core/events/taches.py` `tache_terminee` plus the catalog entry plus the receiver in the same PR.
- **import-linter**: add a day-1 `taches-models-decoupled` contract (copy of calepinage, `.importlinter:293-305`). Append `apps.taches` to `tiers-is-a-base-layer`, which is exhaustive by enumeration (`.importlinter:345-349`).

## 5. Risks → mitigation
1. **VX83 single-queue decision** (views.py:489-494): feed `ma_file`, show only counters for the other kinds. That keeps one queue and is not a second inbox.
2. **Private-task leak through records**: `resolve_target` checks company only, plus the lead scope (records/serializers.py:72-99). Registering `taches.*` targets would let any colleague who knows an id read comments, attachments and tags. Mitigation: a cross-owner task (securite unit, opus) adds an optional model hook `est_visible_par(user)` that `resolve_target` honours. Until it lands, no `record_targets`.
3. **Activity writes are `IsResponsableOrAdmin`** (views.py:383,656,709): Today carries `peut_cloturer`. A `normal` user still sees the item but closes it at its source.
4. **Ownership and claims**:
   - `pages/activities/**` belongs to `lead` (ownership.yml:449).
   - `/activites` is mounted by `features/crm/module.config.jsx:128`, and crm is claimed by the live session.
   - `records/**` belongs to `securite` (ownership.yml:482).
   Keep these as small, separate, append-only tasks: the `ma_file` block, the selector, the quick-add re-point. Route them per the multi-owner rule, after the claim is released. `apps/taches/**` itself is greenfield.
5. **Closed `EventType` enum** (notifications/models.py:69 uses `EventType.choices`): push is deferred to the coach lane. One `notifications` AlterField migration plus a real producer (YEVNT7 checks `notify(EventType.X)` producers).
6. **Migrations**: one new app chain, no edit to records' chain (0014 is its last). Index names stay ≤ 30 characters as listed. Conditional uniques need `condition=Q(...)`.
7. **`SoftDeleteManager` hides deleted rows**: the federation and the stats queries use `objects`; the trash uses `all_objects` (core/models.py:175-176).
8. **Name confusion with parked `gestion_projet.Tache`**: different app_label, so no clash. Never reuse the label `gestion_projet`.

## Open questions
- Should roles with an app marker (Commercial terrain) get the Tâches tile?
- Should labels reuse the company-wide `records.Tag` vocabulary? Personal labels would appear in colleagues' pickers.
- Should legacy open personal activities be bulk-converted once (a "tout convertir" button) or drained naturally?
- Should a task linked to a lead write a line on the lead chatter when done? It is team-visible, so it must be opt-in.
