# Vérification contradictoire de la référence (`reference/donnees.md`, `reference/api.md`)

Lu en entier : consignes, socle, arbitrages A1-A15, les deux cibles ; sections Données/API des specs 2-6b ;
`verif-coherence.md` ; constats B/M des cinq autres rapports. Scripts jetables (lancés ici) dans
`docs/taches/travail/verifref/` : `routes.py` (tables de routes), `champs.py` (champs ↔ JSON), `noms.py` (noms
≤ 30), `enums.py` (longueurs), `gardes.py` + `faux_models.py` (vraies fonctions `check_file` du dépôt). Rien d'autre
modifié. Aucun test Django, aucune base.

**Bilan : 0 BLOQUANT, 10 MAJEUR, 22 MINEUR.**

## 1. Rien de perdu

### Orphelins (dans une spec ou un rapport, absents de la référence et de « non repris »)
1. Débits `flux` 60/h et `tuile` 120/h, classe `taches/throttles.py` sur le patron `CalendrierIcsThrottle` (spec-6b:11). L'API ne cite que capture (api.md:328) ; `grep throttl` = 0.
2. `records.services.cloturer_a_faire_personnel` qui clôt la source d'une conversion (spec-6a:86, :130). `grep` = 0.
3. Fournisseur d'effacement `core/dsr.py` pour `taches` (A4, verif-securite M5). `grep dsr` = 0.
4. File hors ligne multi-comptes : chaque op porte `(company_id, user_id)`, cache par utilisateur, purge à la déconnexion (verif-specs-4-6 M4, MAJEUR). `grep auth-logout` = 0.
5. `docs/rbac-endpoint-inventory.md` à régénérer (verif-securite m2 ; `core/tests/test_endpoint_permission_inventory.py:52-64` rougit sinon). `grep rbac` = 0.
6. `rang` dans ITEM (spec-3:152) et la règle d'ordre d'affichage d'une section (verif-specs-2-3 M13).
7. Manifeste `apps/taches/platform.py`, `permissions_registre.py`, `appSkus.js` (trou T11). Rien dans la référence.

Renommages faits mais non annoncés (MINEUR) : lot `corbeille`→`supprimer`, geste `corbeille`→`suppression`
(spec-2:159, :186), `convertir-activite {"activite_id"}` singulier retiré (spec-6a:86).

### Couverture (✓ appliqué · ~ partiel · ✗ non)
| Lot | Statut |
|---|---|
| C1-C12, C14-C39, C41-C48 | ✓ (C7, C16, C40 remplacés par spec-7 r2, primauté respectée) |
| C13 | ✓ ; `constats` rendus en forme PROPOSITION au lieu de `{code,phrase,donnees,action}` (assumé) |
| C21 | ~ : file hors ligne gardée, garde multi-comptes absente (orphelin 4) |
| T1 ~ (texte de vérité hors réf.) · T2-T5 ✓ · T6 ~ (cartes `revelation`) · T7-T9 hors réf. · T10 ✓ · T11 ✗ · T12-T15 ✓ | |
| verif-2-3 B1, B2, M1-M8, M10-M12, M14 | ✓ ; M9 hors réf. ; **M13 ~** (orphelin 6) |
| verif-4-6 B1, M1-M3, M5, M6, M8, M9 | ✓ ; **M4 ✗** ; M7 hors réf. (A8) |
| sécurité M1-M4 | ✓ ; **M5 ~** (titres neutres, `titre_fige` retiré, mais pas de DSR) ; **M6 ✗** (A9) |
| verif-5a 1-3 · verif-spec-7 B1, M1-M11 | ✓ |
| A1-A8, A10-A14 | ✓ (A3 ~ : sélecteurs de visibilité non nommés) |
| **A9** | ✗ « texte d'écran, hors de cette référence » (donnees.md:601) alors qu'A9 le veut « dans la référence » |
| **A15** | ✗ sur 4 points sur 7 (MAJ-1 à MAJ-3, min-2) ; les deux en-têtes citent encore « A1-A14 » (donnees.md:4, api.md:4) |

## 2. Cohérence interne

- `routes.py` : **107** couples méthode × chemin dans §3, pas 102 (api.md:294). Les 16 actions de §7 existent toutes
  dans §3 avec la même méthode (« actions absentes de §3 : aucune »). Les chemins cités seulement en prose sont tous
  dans « non repris » (`a-venir/`, `annulations/…`, `coach/…`, `decaler/annuler/`, `saisie-rapide/apercu/`).
- `champs.py` : champs du modèle absents de toute l'API, à servir ou à justifier : `Projet.affichage` (lu ET écrit
  nulle part, alors que c'est un réglage de l'utilisateur), `termine_le`, `statut_depuis`, `planification_le` ;
  `IncitationCoach.ouvert_le` (aucune route ne l'écrit) ; `VueEnregistree.filtres`, `ModeleProjet.contenu` (corps CRUD
  non décrits). Les clés JSON hors données sont toutes dérivées (sections, compteurs, `explication`…), sauf `repere.p60`
  (AVANCÉ de s5a, cohérent).
- Énumérations dans les exemples : toutes valides vis-à-vis de §1, sauf la palette (MAJ-1) et deux listes non fermées :
  `sante.code` `tout_fait` (api.md:80) n'a aucune fonction dans `moteur/sante.py` (donnees.md:494) ;
  `obligations[].famille` n'est pas une énumération.
- Invariants recalculés sur l'exemple `aujourdhui/` : pastille 4 + 1 = 5 ✓ ; `plan_lignes` 4 / `plan_tenues` 1 ✓ ;
  `minutes_prevues` 75 et `sans_estimation` 1 ✓ ; `a_decider` reportée 3 fois ✓ ; `lock_version:0` possible
  (`core/champs_plateforme.py:31-34`, 0 à la création) ✓. `progression.prevues` n'est défini nulle part (5 = nombre
  d'éléments du jour ici, ou l'objectif ?) : min-21.
- Doublons : `GET convertir-activite/` ≡ `aujourdhui.a_trier.a_convertir` ; `GET recurrences/{id}/` ≡ `TACHE.recurrence` ;
  `GET preferences/` ≡ `RYTHME.preferences` ; `mode` écrit par `POST rythme/` ET `PATCH reglages/` (MAJ-6) ;
  `PUT revue/projets/{id}` `terminer` ≈ `POST projets/{id}/terminer/` (`boite`) — un seul service exigé.

## 3. Faisabilité Django

- Gardes réelles sur une transcription (`gardes.py`) : `check_unique_scoping.check_file` → seul `unique=True` =
  `JetonAcces.jeton_hash` (passe par `GLOBAL_NAME_RE`, `scripts/check_unique_scoping.py:57-61`), 0 constat ;
  `check_on_delete.check_file` → 0 constat (tous les CASCADE commentés, tous les SET_NULL `null=True`) ;
  `TIMESTAMP_NAME_RE` (`check_naive_datetime.py:65-68`) → 0 DateField fautif (`echec_le`, `expire_le`,
  `tenir_fixee_le` passent : le motif ne lit pas `_le`).
- `noms.py` : 40 noms, le plus long 25 caractères, tous préfixés `taches_`. `enums.py` : toutes les valeurs tiennent
  dans leur `max_length` (`inaccessible` et `sans_donnees` à 12/12, `jours_ouvres` à 12/12).
- Baselines `apps/records/platform_baselines/` : aucun modèle en `*Activity`, aucune FK `company` à la main, viewsets
  sur `CompanyScopedModelViewSet`, pas de `statut`+`Ligne<X>`+`montant_ttc` : rien ne s'y ajoute.
- Migration 0001 : aucune dépendance circulaire entre modèles distincts (FK auto-référentes seulement) ; aucun nom de
  modèle déjà pris avec un accesseur inverse par défaut (seuls `installations.Projet`/`ModeleProjet` existent, avec
  `related_name` explicites, `apps/installations/models_program.py:34-79`). Dernière migration `records` = 0014 ✓,
  `notifications` = 0078 ✓.
- `SoftDeleteModel.restore()` émet TOUJOURS `record_soft_restored` (`core/models.py:227-239`, sans drapeau `record`) :
  deux UPDATE inoffensifs dans `trash`/`DeletionRecord`. Restaurer un projet dont le nom est repris lèvera
  `IntegrityError` sur `taches_projet_nom_uniq` : la 409 `{"nom":…}` d'api.md:404 suppose un `atomic()` + `except` —
  à écrire dans le service.
- Django **5.2.19** (`requirements.txt`) : `CheckConstraint` prend `condition=` (mot-clé), pas `Q(…)` positionnel
  (donnees.md:164-165) ; les `JSONField` à défaut liste exigent un appelable (`default=list`, donnees.md:239, 242).
- `nom_cle` (`editable=False`) : où est-il calculé ? Un `bulk_create` de sections (planification) ou un
  `QuerySet.update(nom=…)` laisse `''` → collision de `taches_section_nom_uniq` dès la 2e section.

## 4. Faisabilité API

- OpenAPI, paramètres : bien posés (api.md:30-32). Ajouter les types non JSON (`text/calendar`, `text/plain` de capture).
- **Pagination absente** (MAJ-8). **Classe de jeton** : pas de liste fermée d'authentifications dans les gardes ; la
  garde de locataire n'impose rien à un `APIView` nu (`check_tenant_isolation.py:64-66`) ; l'inventaire ne lit que
  `permission_classes` → `IsAuthenticatedInterne` suffit. Le vrai trou est la société (MAJ-4).
- Verrou : `VerrouOptimisteSerializerMixin` est opt-in et ne marche qu'en mise à jour de sérialiseur
  (`core/mixins.py:263-290`). « Obligatoire » (400) et les routes d'action (`planifier/`, `planification/`) demandent un
  code propre : `version_envoyee()` + comparaison sous `select_for_update`, `ConflitVersion` avec `actuel` = TACHE.
  À écrire dans `planifier(verrou=…)`.
- Idempotence : `IdempotencyRecord` est unique par `(company, endpoint, key)`, pas par utilisateur
  (`core/idempotency.py:156-160`, `:250-253`) : deux collègues avec la même clé et le même corps rejouent la réponse
  de l'autre (titres, notes). Purge à 24 h (`core/tasks.py:183`).
- **`GET aujourdhui/` — requêtes** (estimation non mesurée) : auth + permission + module ≈ 3-4 ; réglages 1 ;
  préférences 1 ; fériés 1-2 ; PlanJour + lignes 2 ; jeu de tâches du jour avec annotations 1-2 ; réserve de Proposé 1 ;
  focus de semaine 1 ; capacité (9 jours) 1 ; cartes 1 ; compteurs À trier 2-3 ; activités ERP + `peut_cloturer` +
  closes du jour 2-3 → **≈ 18-23 sans familles** ; visites, interventions, touches + 3-6 → **≈ 22-29**. ≤ 18 ne tient
  qu'avec un seul jeu de tâches partitionné en Python et des agrégats conditionnels. `badge/` ≤ 6 (api.md:535) est
  **intenable** : R16 lui fait calculer Proposé, donc la moitié des requêtes ci-dessus (≈ 12-15).
- 107 routes : ≈ 45 sont du CRUD de viewset (checklist, étiquettes, vues, sections, modèles, projets, tâches) — coût
  marginal ; ≈ 60 sont des actions, chacune avec sérialiseur, schéma, test. Fusions sans perte : retirer
  `GET convertir-activite/`, `GET recurrences/{id}/`, `GET preferences/`, `GET checklist/[{id}/]`,
  `GET sections/{id}/` (déjà dans la fiche, la vue projet ou RYTHME) ; `mode` seulement par `POST rythme/`.

## 5. Vie privée

- Ids reçus : invariant 9 couvre presque tout. Manquent `journee/proposition` `inclure`/`exclure` (un id étranger doit
  être ignoré, jamais chargé), `agenda/?projet=`, `checklist/` POST (`tache`), `sections/` POST (`projet`).
- Routes à jeton : bonnes règles de vérification, mais la société n'est pas transmise (MAJ-4) et les débits flux/tuile
  manquent (orphelin 1).
- Tâche confidentielle : écran = titre ; assistant/flux/tuile = « Tâche confidentielle » ; push = sans titre ✓. Fuite
  par recherche : `filtrer_q` cherche dans les **notes** (donnees.md:468) ; sous `X-Taqinor-Assistant`, `recherche/`
  révèle qu'une note contient un mot, et que une tâche confidentielle correspond à « Karim ».
- `Tache.lien_libelle` est une copie du nom du lead : aucun mécanisme ne l'efface (MAJ-7) et `aujourdhui/` le sert
  sans revérifier la visibilité (seule la fiche revérifie, api.md:228).

## 6. Découpage en lanes

Goulots que la référence laisse ouverts : `services.py` (creer_taches, planifier, gestes : tous les domaines),
`serializers.py` (ITEM/TACHE/PROJET partagés), `selectors.py`, `models.py` (champs 0003+), le client d'API front, le
composant de ligne ITEM, `module.config.jsx`, et quatre fichiers régénérés (`docs/openapi-schema.yml`,
`docs/rbac-endpoint-inventory.md`, `frontend/src/test/fixtures/contractSamples.js`, `docs/CODEMAP.md`).
Découpage proposé (paquets, gardes compatibles : `models/*.py`, `services/*.py`, `views/*.py`, `serializers/*.py`
sont tous lus, `check_unique_scoping.py:79-84`, `check_read_modify_write.py:64`, `check_tenant_isolation.py:10-13`) :
- **L0 socle (seul, d'abord)** : `models/{projets,taches,journee,rythme,presence,erp,gestes}.py` + 0001, `choix.py`,
  `confidentialite.py`, `selectors/base.py` (taches_de…, jours travaillés), `services/{planification,gestes}.py`,
  `serializers/formes.py` (ITEM, TACHE, TACHE_ECRITE, PROJET, PROPOSITION, LIEN), `urls.py` complet, `views/*.py`
  vides, `apps.py`, `platform.py`, `contract_samples/`; front `module.config.jsx` complet + pages vides +
  `features/taches/api/client.js` + `ui/LigneTache.jsx`. Module ÉTEINT (MAJ-10).
- **L1 saisie** : `saisie.py`, `moteur/recurrence.py`, `services/creation.py`, `views/saisie.py` + `serializers/saisie.py`
  (saisie-rapide, taches CRUD, lot, checklist, étiquettes, vues, recherche, gestes) ; pages Saisie, À trier, Fiche,
  Recherche, Supprimées ; `api/saisie.js`.
- **L2 journée** : `moteur/classement.py`, `selectors/journee.py`, `views/journee.py` (aujourdhui, badge, vu, journee/*,
  rappels), `views/agenda.py` ; pages Aujourd'hui, Bilan, Agenda.
- **L3 projets** : `moteur/{sante,decalage}.py`, `views/projets.py` (projets, sections, modèles, revue) ; pages Projets,
  Un projet, Archive, Modèles, Revue.
- **L4 rythme** : `moteur/{rythme,sollicitations,gabarits}.py`, `nocturne.py`, `views/rythme.py`, `views/reglages.py` ;
  pages Mon rythme, Réglages.
- **L5 présence** (@after L2, L4) : `auth_jeton.py`, `throttles.py`, `moteur/flux.py`, `balayage.py`,
  `views/presence.py` ; `useBadgeTaches.js`, `captureQueue.js`, `iphone/*`, Mon iPhone.
- **L6 ERP** (@after L1) : `selectors/erp.py`, `services/erp.py`, `receivers.py`, `dsr.py`, `views/erp.py`
  (suggestions, ailleurs, convertir-activite, mes-donnees, tout-effacer) ; puis `agenda-externe` (0002).
- **L7 assistant** (@after L1-L4) : `agent_actions.py`, `features/taches/cartes/*`.
- Fichiers étrangers : une tâche par propriétaire (A8). `openapi-schema.yml`, `rbac-endpoint-inventory.md`,
  `CODEMAP.md` : régénérés UNE fois par l'orchestrateur après le dernier fold, jamais par une lane.

## Constats

### MAJEUR
- **MAJ-1 Palette (A15 ✗).** Huit clés `bleu…gris` (donnees.md:42, I1) contre les dix de spec-8 (`terre`, `ambre`,
  `olive`, `vert`, `menthe`, `ciel`, `bleu`, `indigo`, `prune`, `rose`, `spec-8-langage-visuel.md:32-33`). Les exemples
  (`orange`, `violet`, `cyan`, `gris`) et le défaut d'`Etiquette` (`gris`) seraient refusés. → Prendre les dix clés,
  réécrire les exemples, choisir un défaut d'étiquette dans la palette.
- **MAJ-2 Rétention de `PlanJour` (A15 ✗).** 90 jours (donnees.md:540, I11) au lieu de 400. → `PlanJour` 400 j ;
  `LignePlanJour` et journal 90 j inchangés ; retirer « à valider » d'I11.
- **MAJ-3 Sollicitations sans tâche (A15 ✗).** `ReglagesRythme` est créée au premier `POST vu/` (donnees.md:244, I8) :
  ouvrir Aujourd'hui une fois (c'est l'accueil, api.md:476) suffit pour recevoir un plan du matin. → Ne créer
  `ReglagesRythme` que dans `creer_taches()` ; `vu/` lit sans créer ; la condition d'émission est « une tâche existe ».
- **MAJ-4 Société des routes à jeton.** « Société = `jeton.company` » (api.md:17) contre « `company=user.company` »
  (donnees.md:459). Sans JWT, `ActiveCompanyMiddleware` ne pose pas la société active
  (`authentication/models.py:225-234`) : un multi-sociétés aurait ses captures et sa tuile dans l'espace de sa société
  d'attache, et `taches_voir` serait lu dans la mauvaise société. → `JetonAccesAuthentication` vérifie
  `user_can_operate(user, jeton.company_id)` puis pose `user.company = jeton.company` en mémoire ; test dédié.
- **MAJ-5 « garder » introuvable.** L'invariant 4 dit « `trancher`/décision « garder » pose `reports_tranches` »
  (donnees.md:374-375) ; `Decision` n'a pas `garder` (donnees.md:53) ; spec-3 crit. 4 l'exige (spec-3:178). Si `jour`
  ne réarme pas, la tâche revient en À revoir aussitôt. → « `trancher` `aujourdhui` ou `jour` (ex-`garder`) pose
  `reports_tranches = reports` » ; réécrire le critère.
- **MAJ-6 `PATCH reglages/` trop large.** « N'accepte que les champs de `ReglagesRythme` » (api.md:434) inclut `palier`,
  `bloc_debut`, `echec_*`, `meilleur_tenu` : le client contourne l'invariant 24 et A2. → Liste blanche : `titres_*`,
  `rappel_avant_bloc_min`, `projet_arret_jours`, `familles_suggestions`, `suggestions_societe` (admin),
  `erp_dans_journee`, `comprendre_mon_rythme`, `pauses_sollicitations` ; `mode` seulement par `POST rythme/`.
- **MAJ-7 Effacement 09-08 sans fournisseur.** Orphelin 3. `lien_libelle` garde le nom (donnees.md:151), `lien_etat
  efface` n'est posé par personne. → `register_dsr_provider('taches', export=…, erase=…)` (`core/dsr.py:86`) qui vide
  `lien_libelle`, pose `efface`, supprime les `SuggestionTache` du `lead_ref` ; test.
- **MAJ-8 Pagination non décidée.** Défaut `StandardPagination` 50 (`settings/base.py:694-698`) ; `projets.json` a
  l'enveloppe, `suggestions.json` non (api.md:350) ; `check_liste_page1` rougit tout écran qui lit `.results` sans
  `next`. → Par liste : paginée + `fetchAllPages`, ou `pagination_class=None` + plafond déclaré (≤ 20 suggestions,
  ≤ 30 vues, étiquettes) ; enveloppe écrite dans chaque échantillon.
- **MAJ-9 Hors ligne multi-comptes.** Orphelin 4. → `saisie-rapide/` accepte `proprietaire_attendu` (id) et répond 409
  `{"code":"autre_compte"}` s'il diffère ; clé de cache `taches:aujourdhui:<user>:<jour>` ; vidage sur
  `taqinor:auth-logout`.
- **MAJ-10 Le socle seul sur `main`.** donnees.md:474-481 fait atterrir seul un socle de ~100 vues en 501 ;
  l'auto-déploiement le met en prod, et `taches_voir` est accordé à tous les rôles internes (socle §8). → Le socle
  déclare le code de droit sans l'accorder ; l'octroi aux rôles, l'`appSku` et l'entrée de nav partent dans la dernière
  vague ; ajouter `serializers/`, `services/`, `selectors/` découpés (§6).

### MINEUR
min-1 107 routes, pas 102. min-2 Notification de 15 h → `?ouvrir=alleger` (api.md:490) contre A15 (« ouvre
Aujourd'hui ») ; en-têtes « A1-A14 ». min-3 A9 : le texte de Vie privée doit avoir une place dans la référence.
min-4 Orphelin 1. min-5 Orphelin 2. min-6 Orphelin 5. min-7 Deux 409 hors forme du verrou (api.md:404-405, :420) :
ajouter `code` (`nom_pris`, `proposition_expiree`) pour que le client les distingue. min-8 `_avec_idempotence(…,
suffixe=f'u{user.pk}')` sur toutes les routes `taches`. min-9 TACHE ne sert que `confidentielle` (effectif) alors que
PATCH écrit `confidentiel` : servir les deux. min-10 Servir `affichage`, `issue`, `bilan`, `termine_le` dans PROJET ;
énumérer le corps de `PATCH projets/{id}/`. min-11 `ouvert_le` jamais écrit : `POST vu/` le pose sur les push du jour.
min-12 Sous l'en-tête assistant, `filtrer_q` ignore notes et tâches confidentielles. min-13 Budgets `badge/` et
`aujourdhui/` irréalistes (§4). min-14 `CheckConstraint(condition=…)`, `default=list`. min-15 `nom_cle` calculé dans un
seul `save()` ; `bulk_create` interdit sur les trois modèles. min-16 « Toute écriture rend `geste_id` » contredit par
`agenda-externe/` (api.md:444), `PATCH reglages/`, CRUD, `reordonner/` : lister les exceptions. min-17 Invariant 15 :
ajouter « sauf `annuler_geste()` ». min-18 Objectif dit stocké deux fois (`Preference.objectif_dit`, `palier_source='dit'`) :
une source. min-19 Compteurs de `ReglagesRythme` (`refus_montee += 1`) et statuts vérifiés dans `services/*` :
`select_for_update()` (`check_read_modify_write.py:177-300`). min-20 Supprimer un parent supprime ses sous-tâches
dans le même geste. min-21 Définir `progression.prevues` ; supprimer `tout_fait` ou lui donner sa fonction ; fermer
`obligations.famille`. min-22 `NOTIFICATIONS_TOUJOURS_IMMEDIATES` est remplaçable par l'env
(`settings/base.py:1566-1570`) : ajouter `taches_rappel` au défaut ET vérifier le `.env` de prod (geste de Reda), avec
l'édition `base.py` comptée.

## Facultatif
Contrat import-linter `taches-models-decoupled` ; `related_name='+'` sur les deux `content_type` ; noms `_le` réservés
aux `DateTimeField` (`echec_le`, `expire_le`, `tenir_fixee_le` sont des dates).

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
