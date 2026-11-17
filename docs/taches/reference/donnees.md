# Référence des DONNÉES — `apps/taches`

Référence UNIQUE du schéma. Une lane ne rouvre jamais les specs pour savoir comment une chose s'appelle : elle lit
ce fichier et `api.md`. Primauté appliquée : socle §0/§8 → arbitrages A1-A14 → spec-7 (mots, routes du front) →
vérifications (C1…C48, B/M) → specs → design-s1. Chemins relatifs à `backend/django_core/`.

## 0. Bases vérifiées dans le code (cette session)

| Nom imposé | Où | Ce qu'il apporte |
|---|---|---|
| `core.models.TenantModel` | `core/models.py:62` | `company` FK CASCADE (`related_name='%(app_label)s_%(class)s_set'`), `created_at`, `updated_at` |
| `core.models.SoftDeleteModel` | `core/models.py:155` | `is_deleted`, `deleted_at`, `deleted_by` ; `objects` = vivants, `all_objects` = tout ; `soft_delete(user, record=…)` (:181), `restore()` (:227) |
| `core.champs_plateforme.VerrouOptimisteMixin` | `core/champs_plateforme.py:31` | `lock_version` +1 à chaque `save()` (pas sur `QuerySet.update()`) |
| `core.mixins.VerrouOptimisteSerializerMixin` | `core/mixins.py:260` | 409 `{detail, code:"conflit_version", lock_version, actuel}` (`core/verrou_optimiste.py:30-39`) |
| `core.viewsets.CompanyScopedModelViewSet` | `core/viewsets.py:65` | `TenantMixin` (queryset société, `perform_create` force `company`), `ScopedPermission` lisant `read_permission`/`write_permission` |

Règles transverses (s'appliquent à CHAQUE modèle ci-dessous) :
- Héritage `TenantModel` partout ; `Projet` et `Tache` = `TenantModel, SoftDeleteModel, VerrouOptimisteMixin`.
- Suppression : TOUJOURS `soft_delete(user, record=False)` (aucune entrée `DeletionRecord`, aucun signal de corbeille,
  socle §2.2) ; les autres modèles sont supprimés en dur.
- `__str__` neutre via un mixin unique `StrNeutreMixin` (`f"{verbose_name} #{pk}"`) : jamais un titre, un nom, une note
  (`_audit_notify` écrit `str(instance)`, verif-securite m15).
- Utilisateurs = `settings.AUTH_USER_MODEL`. Le propriétaire s'appelle `proprietaire` PARTOUT (C33).
- Contrainte d'unicité : champs commençant par `company` ; sur `Projet`/`Tache`, `is_deleted=False` dans `condition`
  (verif-specs-2-3 B2). Noms ≤ 30 caractères, préfixe `taches_`.
- Jours = `timezone.localdate()` dans le fuseau de la société (`TIME_ZONE`, `CELERY_TIMEZONE = 'Africa/Casablanca'`,
  `settings/base.py:1190`).
- Ordre manuel : entiers espacés de 1 024 ; renumérotation de la seule liste concernée par `QuerySet.update()` (ne fait
  pas avancer `lock_version`, verif-specs-2-3 m14).

## 1. Énumérations fermées (`apps/taches/choix.py`)

| Énumération | Valeurs techniques → libellé montré (spec-7 §3, A14-M10) | Source |
|---|---|---|
| `Priorite` (IntegerChoices) | 0 aucune · 1 basse « Priorité basse » · 2 moyenne « Priorité moyenne » · 3 haute « Priorité haute » | socle §3 |
| `StatutTache` | `a_faire` · `en_attente` « En attente de… » · `fait` « Faite » · `annule` « Abandonnée » | socle §3, s7 |
| `StatutProjet` | `actif` · `en_pause` « En pause » · `termine` « Terminé » · `archive` « Archivé » | socle §3 |
| `IssueProjet` | `''` · `atteint` · `abandonne` | s4 §I |
| `Moment` | `''` · `matin` · `apres_midi` · `soir` « Ce soir » | socle §3 |
| `Source` | `manuel` · `rapide` · `assistant` (repère à l'écran, A5) · `capture` · `activite` · `recurrence` · `modele` · `suggestion` | C31 |
| `Couleur` | `bleu` · `vert` · `orange` · `violet` · `rose` · `jaune` · `cyan` · `gris` | socle « palette fermée » (clés : décision I1) |
| `Visibilite` | `prive` | socle §3, D-TCH-1 |
| `LienEtat` | `''` · `ok` · `archive` · `introuvable` · `inaccessible` · `efface` | s6a §3.2 |
| `CibleLiable` | `crm.lead` · `crm.client` · `ventes.devis` (seules cibles à sélecteur de visibilité) | A3 |
| `Frequence` | `quotidien` · `jours_ouvres` · `hebdo` · `mensuel` · `annuel` | s2 §3.5 |
| `ModeRecurrence` | `calendrier` · `apres_fait` | s2 §3.5 |
| `ModeRythme` | `pousser` « En faire plus » (défaut) · `tenir` « Garder ce rythme » · `libre` « Sans objectif » | s5a, s7 |
| `SourceObjectif` | `defaut` (« valeur par défaut ») · `calcule` · `accepte` · `dit` · `libre` | C13 |
| `CapaciteSource` | `defaut` · `historique` (« habituel ») · `reglage` (« ton réglage ») | s3 §3.4 |
| `StatutJour` | `conge` · `non_ouvre` · `sans_donnees` · `evalue` (seul `evalue` entre dans les règles) | s5a §3.2 |
| Sections de la journée (clés de `aujourdhui/`) | `essentiel` « Essentiel » · `journee` « Prévu » · `ce_soir` « Ce soir » · `propose` « Proposé pour aujourd'hui » · `a_decider` « À revoir » · `en_attente` « En attente » · `faites` « Faites » | s7 r2 §3-4, A14-M1 |
| `MotifRevoir` (section technique `a_decider`, montrée « À revoir ») | `reportee_3_fois` · `jour_passe` · `echeance_passee` · `echeance_proche` | s3 §3.1, s7, A14-M10 |
| `Decision` (une seule énum, sous-ensembles par route) | `aujourdhui` · `demain` (J+1) · `prochain_jour_ouvre` (« Reporter », prochain jour travaillé) · `jour` (+ date, « Choisir un jour ») · `un_jour` (« En réserve ») · `abandonner` | s3, s7, A14 |
| `StatutRappel` | `en_attente` · `envoye` · `manque` (retard > 2 h, jamais envoyé) · `annule` | s3 §3.9 |
| `SourceRappel` / `AncreRappel` | `manuel` · `repetition` · `bloc` / `''` · `jour_prevu` · `echeance` | s3 §4 |
| `UsageJeton` | `capture` (préfixe `tqc_`) · `flux` (`tqf_`) · `tuile` (`tqt_`) | socle §2.5, s6b §1 |
| `TypeIncitation` canal `push` | `plan_matin` · `bilan_soir` · `revue_semaine` (remplace le bilan ce jour-là) · `relance` (« Message de 15 h », heure réglée) | C14, s7 r2 §3 |
| `TypeIncitation` canal `ecran` | `proposition_palier` · `derive_tenir` · `garde_taille` · `constat` · `pause` · `retour` · `revelation` | C14, s5a, A14-B1, s7 §7 |
| `ReponseIncitation` | `''` · `oui` · `pas_maintenant` · `garder` · `garder_ce_rythme` · `passer` · `taches_changees` · `reactiver` · `remettre_dans_propose` · `une_par_une` · `ok` · `ignoree` · `expiree` | s5a, A14-B1 |
| `CanalIncitation` | `push` · `ecran` | C14 |
| `FamilleSuggestion` | `devis_accepte` (allumée) · `chantier_receptionne` (allumée) · `chantier_annule` (allumée) · `visite_validee` (éteinte) | s6a §3.7, A4 |
| `StatutSuggestion` | `proposee` · `acceptee` · `refusee` · `retiree` | s6a §4 |
| `DecisionRevue` | `''` · `garder` · `pause` · `terminer` · `passe` (montré « Suivant ») | s4 §H, verif-spec-7 §4 |
| `SourcePreference` | `ecran` · `copilote` · `carte` (constat accepté) | s5b §5 |
| `EventType` (app `notifications`, en fin d'énum) | `TACHES_PLAN_DU_JOUR` · `TACHES_BILAN_SOIR` (bilan + revue) · `TACHES_RELANCE` · `TACHES_RAPPEL` (rappel posé + push de test) | s6b §3, C14, C43, verif-specs-4-6 M3 |

Clés de cartes `IncitationCoach.cle` : push → `''` ; `proposition_palier` → `monter` · `baisser` · `premier` ·
`journee_type` ; `derive_tenir` → `sous` · `au_dessus` ; `garde_taille` → `''` ; `constat` → `C1`…`C8` ; `pause` → le
type push en pause ; `retour` → `''` ; `revelation` → `mon_iphone` · `ranger_copilote` · `planifier_projet` · `revue`.
Réponses permises par carte : `monter` {oui, pas_maintenant, garder_ce_rythme (3e refus de suite)} · `baisser` {oui,
garder} · `premier` {ok} · `journee_type` {oui, pas_maintenant} · `derive_tenir` {garder, passer} · `garde_taille`
{taches_changees, ok} · `constat` {oui, pas_maintenant} · `pause` {reactiver, ok} · `retour` {remettre_dans_propose,
une_par_une} · `revelation` {ok}. Push : `ignoree` posé par la tâche nocturne seulement.

## 2. Modèles

Colonnes héritées non répétées : `id`, `company`, `created_at`, `updated_at` (+ `is_deleted`, `deleted_at`,
`deleted_by`, `lock_version` sur Projet et Tache).

### 2.1 `Projet` (`TenantModel, SoftDeleteModel, VerrouOptimisteMixin`)

| Champ | Type Django | Nul / défaut | Valeurs | Source |
|---|---|---|---|---|
| `proprietaire` | `ForeignKey(AUTH_USER_MODEL, CASCADE)` `# on_delete: données personnelles, suivent le compte` | — | même société | socle §3, §8 |
| `nom` | `CharField(120)` | — | 1-120 car. | socle |
| `nom_cle` | `CharField(120, editable=False)` | — | `saisie.cle_nom(nom)` | I2 (s2 §3.2) |
| `objectif` | `TextField` | `blank` `''` | « Ce sera fini quand… » | socle, s4 §B |
| `icone` | `CharField(8)` | `blank` `''` | un emoji | socle |
| `couleur` | `CharField(16, choices=Couleur)` | couleur d'office (s4 §A) | palette | socle |
| `priorite` | `PositiveSmallIntegerField(choices=Priorite)` | 0 | 0-3 ; demandée à l'étape 1 de Planifier le projet | socle, A14-M3 |
| `statut` | `CharField(12, choices=StatutProjet)` | `actif` | | socle |
| `statut_depuis` | `DateTimeField` | `default=timezone.now` | posé à chaque changement de statut | s4, verif-specs-4-6 m12 |
| `date_debut`, `echeance` | `DateField` | `null` | | socle |
| `termine_le` | `DateTimeField` | `null` | | socle |
| `issue` | `CharField(10, choices=IssueProjet)` | `blank` `''` | | s4 §I |
| `bilan`, `risque` | `CharField(280)` | `blank` | | s4 |
| `domaine` | `CharField(40)` | `blank` | montré « Groupe » | s4, s7 §3 |
| `planification_le` | `DateTimeField` | `null` | « À planifier » ⇔ actif ∧ nul ∧ 0 ouverte | s4 (C41) |
| `rang` | `IntegerField` | 0 | pas 1 024 | socle |
| `confidentiel` | `BooleanField` | `False` | | socle §2.7 |
| `visibilite` | `CharField(10, choices=Visibilite)` | `prive` | | socle |
| `affichage` | `JSONField` | `default=dict` | clés `tri`, `groupe`, `montrer_faites` | s2 §4 |

Contrainte `taches_projet_nom_uniq` : `UniqueConstraint(fields=['company','proprietaire','nom_cle'],
condition=Q(is_deleted=False))`. Index `taches_projet_stat_idx` (company, proprietaire, statut).

### 2.2 `Section` (`TenantModel`) — montrée « Étape » ; sert aussi de phase

| Champ | Type | Nul / défaut | Source |
|---|---|---|---|
| `projet` | `ForeignKey(Projet, CASCADE)` `# on_delete: composition, l'étape n'existe que dans son projet` | — | socle |
| `nom` / `nom_cle` | `CharField(120)` / `CharField(120, editable=False)` | — | socle, I2 |
| `rang` | `IntegerField` | 0 | socle |
| `date_debut`, `date_fin` | `DateField` | `null` | socle, s4 |

Contrainte `taches_section_nom_uniq` (company, projet, nom_cle) (verif-specs-2-3 m5 : sert le `get_or_create` de
« section inconnue créée »). Index `taches_section_rang_idx` (projet, rang). Suppression dure ; ses tâches passent
« Sans étape » (`Tache.section` SET_NULL). Propriétaire = `projet.proprietaire`.

### 2.3 `Tache` (`TenantModel, SoftDeleteModel, VerrouOptimisteMixin`)

| Champ | Type Django | Nul / défaut | Valeurs / règle | Source |
|---|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` `# on_delete: données personnelles, suivent le compte` | — | | socle |
| `projet` | `FK(Projet, CASCADE, null)` `# on_delete: composition, la purge du projet emporte ses tâches` | `null` = sans projet | | socle |
| `section` | `FK(Section, SET_NULL, null)` `# on_delete: étape supprimée → « Sans étape »` | `null` | même projet | socle |
| `parent` | `FK('self', CASCADE, null, related_name='enfants')` `# on_delete: composition, sous-tâche` | `null` | un niveau | socle |
| `titre` | `CharField(280)` | — | 1-280 | socle, s6b §5 (I3) |
| `notes` | `TextField` | `blank` | jamais servies à l'assistant, au flux, à la tuile | socle §2.5 |
| `statut` | `CharField(12, choices=StatutTache)` | `a_faire` | | socle |
| `en_attente_de` | `CharField(200)` | `blank` | texte libre | socle |
| `priorite` | `PositiveSmallIntegerField(choices=Priorite)` | 0 | | socle |
| `jour_prevu` | `DateField` | `null` | lecture seule hors `planifier()` | socle §4 |
| `moment` | `CharField(12, choices=Moment)` | `blank` `''` | dérivé si `heure_debut` posée | socle, s3 §3.1 |
| `heure_debut` | `TimeField` | `null` | heure murale | s3 §4 (C10) |
| `echeance` / `echeance_heure` | `DateField` / `TimeField` | `null` | | socle |
| `quelque_jour` | `BooleanField` | `False` | montré « En réserve » | socle, A14-M10 |
| `estimation_minutes` | `PositiveSmallIntegerField` | `null` | 5-960 ; redimensionnement par pas de 15 | s2, verif-specs-2-3 M14 |
| `duree_reelle_minutes` | `PositiveIntegerField` | `null` | | socle |
| `rang_projet`, `rang_jour` | `IntegerField` | `null` | pas 1 024 | socle |
| `premier_jour_prevu` | `DateField` | `null` | posé une fois | socle |
| `reports` | `PositiveSmallIntegerField` | 0 | +1 par `F()`/`select_for_update` | socle, verif-specs-2-3 M6 |
| `reports_tranches` | `PositiveSmallIntegerField` | 0 | | s3 §4 |
| `triee_le` | `DateTimeField` | `null` | voir invariant 1 | s2 §4 |
| `client_id` | `CharField(64)` | `null` | UUID du client (+ `:<n>` par ligne) | s2, C9, verif-specs-4-6 M5 |
| `source` | `CharField(12, choices=Source)` | `manuel` | | C31 |
| `jalon` | `BooleanField` | `False` | | s4 §C |
| `bloquee_par` | `FK('self', SET_NULL, null, related_name='bloque')` `# on_delete: prérequis purgé → tâche débloquée` | `null` | montrée « En attente de… » (une tâche) | s4 §C, s7 r2 §3 |
| `content_type` | `FK(ContentType, SET_NULL, null)` `# on_delete: lien perdu, tâche gardée` | `null` | `CibleLiable` | socle, I4 |
| `object_id` | `PositiveIntegerField` | `null` | | socle |
| `lien_libelle` | `CharField(200)` | `blank` | `selectors.libelle_de_cible()` (jamais `str(lead)`) | socle, verif-securite m7 |
| `lien_etat` / `lien_verifie_le` | `CharField(12, choices=LienEtat)` / `DateTimeField` | `''` / `null` | | s6a §4 |
| `activite_origine` | `FK('records.Activity', SET_NULL, null)` `# on_delete: activité purgée, tâche gardée` | `null` | | socle |
| `recurrence` | `FK(RegleRecurrence, SET_NULL, null)` `# on_delete: règle supprimée, occurrences gardées` | `null` | | socle |
| `occurrence_du` | `DateField` | `null` | | socle |
| `confidentiel` | `BooleanField` | `False` | drapeau propre ; l'effectif = `est_confidentielle()` | socle, A6 |
| `fait_le` / `annule_le` | `DateTimeField` | `null` | | socle |

Contraintes :
- `taches_tache_cli_uniq` (company, proprietaire, client_id) `condition=Q(client_id__isnull=False, is_deleted=False)`.
- `taches_tache_act_uniq` (company, activite_origine) `condition=Q(activite_origine__isnull=False, is_deleted=False)`.
- `taches_tache_occ_uniq` (company, recurrence, occurrence_du) `condition=Q(recurrence__isnull=False,
  occurrence_du__isnull=False, is_deleted=False)` (verif-specs-2-3 m6).
- `taches_heure_sans_jour_ck` : `CheckConstraint(Q(heure_debut__isnull=True) | Q(jour_prevu__isnull=False))`.
- `taches_ech_heure_ck` : `CheckConstraint(Q(echeance_heure__isnull=True) | Q(echeance__isnull=False))`.

Index : `taches_tache_jour_idx` (company, proprietaire, statut, jour_prevu) · `taches_tache_ech_idx` (company,
proprietaire, statut, echeance) · `taches_tache_proj_idx` (projet, section, rang_projet) · `taches_tache_fait_idx`
(company, proprietaire, fait_le) · `taches_tache_boite_idx` (company, proprietaire, projet, triee_le) ·
`taches_tache_bloq_idx` (company, proprietaire, bloquee_par) · `taches_tache_lien_idx` (company, proprietaire,
content_type, object_id) · `taches_tache_purge_idx` (company, is_deleted, deleted_at). `Meta.ordering = ['rang_projet','id']`.

### 2.4 `ElementChecklist` (`TenantModel`) — « Check-list · point »

`tache` FK(Tache, CASCADE) `# on_delete: composition` · `libelle` Char(255) · `fait` Bool False · `fait_le` DateTime
null · `rang` Integer 0. Index `taches_check_rang_idx` (tache, rang). Source : socle, s2.

### 2.5 `Etiquette` et `EtiquetteTache` (`TenantModel`)

`Etiquette` : `proprietaire` FK CASCADE `# on_delete: données personnelles` · `nom` Char(40) · `nom_cle` Char(40,
editable=False) · `couleur` Char(16, choices=Couleur) défaut `gris`. Contrainte `taches_etiq_nom_uniq` (company,
proprietaire, nom_cle). `EtiquetteTache` : `tache` FK CASCADE `# on_delete: composition` · `etiquette` FK CASCADE
`# on_delete: étiquette supprimée → retirée des tâches`. Contrainte `taches_etiqt_uniq` (company, tache, etiquette).
Source : socle §2.3, s2 §4.

### 2.6 `RegleRecurrence` (`TenantModel`)

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `frequence` Char(12, Frequence) · `intervalle`
PositiveSmallInt 1 (≥ 1) · `jours_semaine` Char(7) `'0000000'` (lun→dim, `1` = jour retenu) · `jour_du_mois` SmallInt
null (1-31, −1 = dernier) · `rang_dans_mois` SmallInt null (1-4, −1 = dernier ; avec un seul jour dans le masque) ·
`mode` Char(12, ModeRecurrence) `calendrier` · `date_debut` Date · `date_fin` Date null · `actif` Bool True.
Source : socle, s2 §3.5, §4.

### 2.7 `PlanJour` (`TenantModel`) — instantané et compteurs d'un jour

| Champ | Type | Nul / défaut | Source |
|---|---|---|---|
| `proprietaire` | FK CASCADE `# on_delete: données personnelles` | — | socle |
| `jour` | `DateField` | — | socle |
| `planifie_le`, `cloture_le`, `app_ouverte_le` | `DateTimeField` | `null` | socle ; `app_ouverte_le` I5 (trou T12) |
| `reflexion` | `CharField(280)` | `blank` | s7 « un mot » |
| `objectif_du_jour` | `PositiveSmallIntegerField` | `null` | s5a (C23) |
| `capacite_minutes` / `capacite_source` | `PositiveSmallIntegerField` / `CharField(12, CapaciteSource)` | `null` / `''` | s3 |
| `statut_jour` | `CharField(12, StatutJour)` | `''` (non clos) | s5a |
| `compte_rythme`, `micro_comptees`, `essentiels_choisis`, `essentiels_faits`, `plan_prevues`, `plan_faites` | `PositiveSmallIntegerField` | 0 | s5a (C23) |
| `minutes_prevues`, `minutes_faites` | `PositiveIntegerField` | 0 | design-s1 (C23) |
| `taille_mediane_min` | `PositiveSmallIntegerField` | `null` | s5a |

Contrainte `taches_planjour_uniq` (company, proprietaire, jour) (porte le `get_or_create`). Ligne créée paresseusement
par la validation du plan, une complétion, ou `POST vu/`.

### 2.8 `LignePlanJour` (`TenantModel`)

`plan` FK(PlanJour, CASCADE) `# on_delete: composition` · `tache` FK(Tache, CASCADE, null) `# on_delete: composition,
compteurs figés sur PlanJour` · `activite_id` PositiveInt null (opaque, vérifié par `activites_ouvertes_pour`) ·
`prevue_au_plan` Bool · `faite` Bool False · `reportee` Bool False · `essentielle` Bool False.
Contraintes `taches_ligne_uniq` (company, plan, tache) `condition=Q(tache__isnull=False)` · `taches_ligne_act_uniq`
(company, plan, activite_id) `condition=Q(activite_id__isnull=False)` · `taches_ligne_cible_ck` : exactement un de
`tache`, `activite_id`. Pas de `titre_fige` (I6). Source : socle, design-s1, s3.

### 2.9 `ReglagesRythme` (`TenantModel`) — interrupteurs et état typés (C4)

| Champ | Type | Défaut | Source |
|---|---|---|---|
| `proprietaire` | FK CASCADE `# on_delete: données personnelles` | — | C33 |
| `mode` | `CharField(12, ModeRythme)` | `pousser` | s5a |
| `comprendre_mon_rythme` | `BooleanField` | `True` | socle §8 (= `suivi_actif` de s5b) |
| `palier` | `PositiveSmallIntegerField` | `null` (= froid, objectif 5 « par défaut ») | s5a |
| `palier_source` | `CharField(12)` `''`/`calcule`/`accepte`/`dit` | `''` | s5a, C13 |
| `bloc_debut` | `DateField` | `null` | s5a |
| `refus_montee`, `blocs_a_sauter`, `echec_n` | `PositiveSmallIntegerField` | 0 | s5a |
| `baisse_refusee`, `essai_restant` | `BooleanField` | `False` | s5a |
| `meilleur_tenu`, `echec_niveau`, `ref_taille_min` | `PositiveSmallIntegerField` | `null` | s5a |
| `echec_le`, `tenir_fixee_le`, `tenir_silence_jusquau` | `DateField` | `null` | s5a |
| `tenir_reference` | `DecimalField(4,2)` | `null` | s5a |
| `titres_notifications` / `titres_calendrier` / `titres_tuile` | `BooleanField` | `False` / `True` / `True` | socle §2.8, s6b |
| `rappel_avant_bloc_min` | `PositiveSmallIntegerField` | `null` (éteint) | s3 |
| `projet_arret_jours` | `PositiveSmallIntegerField` | 10 (5-30) | s4 §E |
| `familles_suggestions` | `JSONField` | les 3 familles allumées | s6a, A4 |
| `suggestions_societe` | `BooleanField` | `False` (admin seul) | s6a |
| `erp_dans_journee` | `BooleanField` | `True` | s6a |
| `pauses_sollicitations` | `JSONField` | `[]` (types push en pause) | s5a §3.9 (I7) |

Contrainte `taches_reglages_uniq` (company, proprietaire). Créée par `get_or_create` au premier `creer_taches()` ou au
premier `POST vu/` ; seuls les comptes qui ont cette ligne reçoivent des sollicitations (I8).

### 2.10 `Preference` (`TenantModel`) — ce qu'il a DIT, prime sur toute inférence

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `cle` Char(30, choices) · `valeur` JSONField ·
`source` Char(10, SourcePreference) · `dite_le` DateTime `auto_now`. Contrainte `taches_pref_cle_uniq` (company,
proprietaire, cle). Une clé absente = défaut. Source : socle §3, C4, C27.

| `cle` (union dédoublonnée C4) | `valeur` | Défaut si absente | Effet | Anciens noms retirés |
|---|---|---|---|---|
| `capacite_jour_min` | entier 30-720 | capacité calculée, sinon 240 « valeur par défaut » | temps disponible | — |
| `objectif_dit` | entier 1-12 | — | objectif immédiat (A2.1) | — |
| `jours_travailles` | chaîne de 7 `0/1`, lun→dim | calendrier de la société | jours travaillés | `jours_off` |
| `jours_courts` | liste d'entiers 0-6 | `[]` | objectif `max(1, N−1)` ce jour-là | `vendredi=120` |
| `conges` | liste `{"du","au"}` (dates, du ≤ au) | `[]` | rien n'est sollicité ni évalué | `conges_du/au` |
| `heure_matin` | `"HH:MM"` ou `"off"` | `"08:30"` | plan du matin | `heure_plan_matin` |
| `relance_jour` | `"HH:MM"` ou `"off"` | `"15:00"` | Message de 15 h | `rappel_journee` |
| `heure_soir` | `"HH:MM"` ou `"off"` | `"18:00"` | bilan du soir | `heure_bilan_soir` |
| `heure_limite` | `"HH:MM"` | `"20:00"` | sollicitations seules ; un rappel posé sonne toujours | `heure_limite_rappels` |
| `revue_semaine` | entier 0-6, `"auto"`, `"off"` | `"auto"` (dernier jour travaillé) | revue de la semaine | `semaine_revue` |
| `essentiel_le_matin` | booléen | `false` | essentiels en tête du plan, moment matin | — |
| `note_libre` | liste ≤ 10 chaînes ≤ 200 | `[]` | une DONNÉE, jamais une consigne | — |

Hors `Preference` (réglages typés de `ReglagesRythme`) : `mode`, `comprendre_mon_rythme`, `titres_*`,
`rappel_avant_bloc_min`, `projet_arret_jours`, familles. Le Copilote ne peut donc jamais toucher un réglage de vie
privée (C4, verif-securite m8).

### 2.11 `IncitationCoach` (`TenantModel`) — journal des sollicitations, dédoublonnage ET cartes à réponse

| Champ | Type | Nul / défaut | Source |
|---|---|---|---|
| `proprietaire` | FK CASCADE `# on_delete: données personnelles` | — | C33 |
| `jour` | `DateField` | — | socle |
| `type` / `cle` | `CharField(24, TypeIncitation)` / `CharField(24)` | — / `''` | C14, §1 |
| `canal` | `CharField(8, CanalIncitation)` | — | C14 |
| `donnees` | `JSONField` | `dict` | tous les nombres ET leur calcul, des id jamais des titres (s5a crit. 10) |
| `montre_le`, `ouvert_le`, `repondu_le` | `DateTimeField` | `null` | s5a §3.9 |
| `reponse` | `CharField(24, ReponseIncitation)` | `''` | |
| `expire_le` | `DateField` | `null` (cartes : J+7) | s5a §3.5 |

Contrainte `taches_incit_uniq` (company, proprietaire, type, jour, cle) : marqueur d'émission (rejeu du balayage =
rien) et unicité des cartes. Index `taches_incit_jour_idx` (company, proprietaire, jour). Pas de champ `texte` : le
texte est rendu à la lecture par `moteur/gabarits.py` avec `nom_pour()` (I9). Les « propositions de rythme » SONT ces
lignes (canal `ecran`) : il n'y a pas d'autre modèle de proposition.

### 2.12 `Rappel` (`TenantModel`)

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `tache` FK CASCADE `# on_delete: composition` ·
`ancre` Char(12, AncreRappel) `''` · `decalage_jours` SmallInt 0 (−7…0) · `jour` Date · `heure` Time (heure murale) ·
`statut` Char(12, StatutRappel) `en_attente` · `envoye_le` DateTime null · `source` Char(12, SourceRappel) `manuel`.
Index `taches_rappel_du_idx` (company, jour, heure) `condition=Q(statut='en_attente')` · `taches_rappel_tache_idx`
(company, tache). Source : s3 §3.9, §4 (C1 : remplace `Tache.rappel_le`).

### 2.13 `JetonAcces` (`TenantModel`) — pas de suppression douce, pas d'admin Django

`proprietaire` FK CASCADE `# on_delete: suit le compte` · `usage` Char(10, UsageJeton) · `prefixe` Char(8) (non
secret) · `jeton_hash` Char(64, `unique=True`) (SHA-256 hex ; nom compris par `GLOBAL_NAME_RE` de
`scripts/check_unique_scoping.py:57`, verif-specs-4-6 M6) · `libelle` Char(60) blank · `dernier_usage_le` DateTime null
(écrit au plus une fois par minute) · `revoque_le` DateTime null. Contrainte `taches_jeton_actif_uniq` (company,
proprietaire, usage) `condition=Q(revoque_le__isnull=True)`. Pas d'expiration. Source : socle §2.5, s6b §1.

### 2.14 `GesteAnnulable` (`TenantModel`) — l'UNIQUE mécanisme d'annulation (A7, C2)

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `type` Char(24) (§4) · `message` Char(200) (texte du
toast) · `operations` JSONField (liste §4) · `annule_le` DateTime null. Index `taches_geste_date_idx` (company,
proprietaire, created_at). Purge à 7 jours. Source : s2 §4, C2, A7.

### 2.15 `VueEnregistree` (`TenantModel`)

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `nom` Char(60) · `filtres` JSONField à clés fermées
(`q`, `projets`, `etiquettes`, `priorite_min`, `statuts`, `periode`, `echeance`, `tri`, `groupe`, `inclure_faites` ;
clé inconnue → 400 nommé) · `rang` Integer 0. Contrainte `taches_vue_nom_uniq` (company, proprietaire, nom). 30 au plus
par propriétaire (service). Source : s2 §3.6, §4.

### 2.16 `ModeleProjet` (`TenantModel`)

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `nom` Char(120) · `contenu` JSONField `{"v":1,
"objectif","sections":[{"nom","decalage_debut","decalage_fin"}],"taches":[{"titre","section_index","priorite","jalon",
"decalage_jour","decalage_echeance","parent_index","bloquee_par_index","checklist":[…],"notes"?}]}` · `cree_depuis`
FK(Projet, SET_NULL, null) `# on_delete: le modèle survit au projet`. Contrainte `taches_modele_nom_uniq` (company,
proprietaire, nom). Source : s4 §G, §4.

### 2.17 `RevueProjet` (`TenantModel`)

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `projet` FK(Projet, CASCADE) `# on_delete:
composition` · `semaine` Date (lundi) · `intention` Char(200) blank · `prochaine_action` FK(Tache, SET_NULL, null)
`# on_delete: tâche purgée, revue gardée` · `decision` Char(10, DecisionRevue) `''` · `focus` Bool False ·
`faites_semaine` PositiveSmallInt 0. Contraintes `taches_revueprj_uniq` (company, projet, semaine) ·
`taches_revue_focus_uniq` (company, proprietaire, semaine) `condition=Q(focus=True)`. Source : s4 §H, §4.

### 2.18 `SuggestionTache` (`TenantModel`) — suggestions venues de l'ERP

`proprietaire` FK CASCADE `# on_delete: données personnelles` (= destinataire strict, A4) · `famille` Char(24,
FamilleSuggestion) · `cle` Char(80) (`devis_accepte:<pk>`…) · `titre_propose` Char(200) (gabarit SANS nom de client,
A4, verif-securite M5) · `content_type` FK(ContentType, SET_NULL, null) `# on_delete: suggestion gardée jusqu'à sa
purge` · `object_id` PositiveInt null · `lead_ref` PositiveInt null (effacement 09-08) · `statut` Char(12,
StatutSuggestion) `proposee` · `tache` FK(Tache, SET_NULL, null) `# on_delete: tâche purgée, trace gardée` ·
`decidee_le` DateTime null. Contrainte `taches_sugg_cle_uniq` (company, proprietaire, cle) (refusée = jamais
reproposée). Index `taches_sugg_boite_idx` (company, proprietaire, statut, created_at). Pas de `lien_libelle` : le nom
se lit par le lien, à l'ouverture, avec les droits du moment (A4).

Gabarits de titre : `devis_accepte` « Préparer le chantier du devis accepté » (A4) · `chantier_receptionne`
« Demander un avis au client : chantier réceptionné » · `chantier_annule` « Comprendre l'annulation du chantier » ·
`visite_validee` « Préparer le devis : visite validée ». Le lien d'une suggestion de chantier vise le LEAD du chantier
(seule cible liable, A3).

### 2.19 `AgendaExterne` (`TenantModel`) — AVANCÉ, dernière vague (A14-M8), migration 0002

`proprietaire` FK CASCADE `# on_delete: données personnelles` · `url` Char(500) (https seulement) · `libelle` Char(60)
blank · `actif` Bool True · `dernier_chargement_le` DateTime null · `dernier_etat` Char(20) blank (`ok`,
`refusee`, `trop_grande`, `delai`, `illisible`). Contrainte `taches_agext_uniq` (company, proprietaire) : un seul par
utilisateur (I10). Les événements ne sont JAMAIS stockés en base : cache borné. L'URL n'est jamais rendue en entier
par l'API (hôte seul).

## 3. Invariants (chacun testable)

1. **À trier** = tâche vivante, `parent` nul, `projet` nul, `triee_le` nul, `statut ∈ {a_faire, en_attente}`.
   `creer_taches()` pose `triee_le = now` dès que la saisie a reconnu un projet, un jour ou « En réserve », PAR TOUTE
   PORTE, capture comprise (A1, A14-M6) ; un rappel tapé sans jour pose aussi `jour_prevu` = jour du rappel (A14-M6).
   `triee_le` est aussi posé par : `planifier()`, un déplacement vers un projet, « Garder sans projet », terminer,
   abandonner, supprimer. Terminer un projet avec `taches_ouvertes='boite'` remet `projet` ET `triee_le` à nul (T14).
2. Une tâche À trier n'apparaît dans AUCUNE section de la journée ni dans Proposé ; elle n'est comptée que dans
   `a_trier.boite_reception`.
3. **À revoir** (section technique `a_decider`) contient exactement, après le préfiltre de l'invariant 10 : reportée
   (`reports ≥ reports_tranches + 3` ∧ `jour_prevu ≤ J`) ; `jour_prevu < J` ; `echeance < J` ; `echeance ∈ ]J, J + 2
   jours travaillés]` ∧ (`jour_prevu` nul ∨ `jour_prevu > echeance`) ; et les activités ERP dues avant J. Premier motif
   vrai dans cet ordre (`MotifRevoir`).
4. **Report** : `reports += 1` ssi l'ancien `jour_prevu ≤ J` ET le nouveau est plus tard ou « En réserve ». Futur →
   futur, avancer, poser un premier jour : 0. Ne comptent JAMAIS : `decaler`, `instancier`, « Alléger ma journée »
   (A14-M7), « Les remettre dans Proposé » (A14-B1), le passage de minuit. `trancher`/décision « garder » pose
   `reports_tranches = reports`.
5. **Récurrence** : au plus une occurrence ouverte (`a_faire`/`en_attente`) par `RegleRecurrence` ; la suivante naît
   à la clôture (terminer, sauter) ; une manquée reste seule ; rouvrir supprime (`record=False`) la suivante si sa
   `lock_version` n'a pas bougé.
6. **Prérequis** : au plus un (`bloquee_par`) ; jamais soi-même ; même propriétaire ; aucune boucle (remontée ≤ 50
   maillons, au-delà ou boucle → 400). Bloquée ⇔ prérequis vivant et `statut ∉ {fait, annule}`.
7. **Sous-tâche** : `parent.parent_id` nul ; même propriétaire ; `projet` et `section` = ceux du parent (déplacer le
   parent déplace ses enfants) ; terminer un parent termine ses sous-tâches ouvertes ; jamais dans À trier, dans une
   section du jour, dans Proposé, au flux ni à la tuile ; comptée 0 dans le compte du rythme.
8. **Confidentiel hérité** : `est_confidentielle(t) = t.confidentiel ∨ t.projet.confidentiel ∨ t.parent.confidentiel ∨
   t.parent.projet.confidentiel`. Aucun corps servi à l'assistant, au flux, à la tuile, aux notifications ni aux
   suggestions ne contient le titre d'une tâche ou le nom d'un projet confidentiel (test canari, A6).
9. **Même propriétaire** sur tout identifiant reçu : projet, section, parent, bloquee_par, étiquettes, éléments de
   check-list, ids de réordonnancement et de lot, lignes de plan (tâches ET activités via `activites_ouvertes_pour`),
   triage, rappels, récurrences, propositions, revue, prochaine action, projet cible, modèle, suggestion, geste, jeton,
   vue ; sinon 404 (ou « Projet inexistant. » au champ), rien d'écrit (test de balayage).
10. **Préfiltre de la journée** (`taches_de_la_journee`, C17) : vivante, `parent` nul, non bloquée, projet `actif` ou
    (projet nul ∧ `triee_le` non nul), et (`statut ∈ {a_faire, en_attente}` ∧ ¬`quelque_jour`, ou `statut = fait` ∧
    `fait_le` local = J). Le MÊME préfiltre sert l'écran, la pastille, le flux et la tuile.
11. **Pastille** `n` = nombre d'éléments ouverts des sections `essentiel` + `journee` + `ce_soir` (tâches ET activités
    ERP) + lignes de `propose.pour_objectif` (Proposé montré, s7 r2 §2 corrige C16), plafonné à 99 ; ni À revoir, ni
    En attente, ni la suite dépliée de Proposé, ni À trier, ni obligations.
12. **Flux et tuile** : tâches `a_faire` du préfiltre, jamais faites, À revoir, en attente, À trier, En réserve ;
    jamais de notes.
13. **`progression.faites` = `compte_du_jour`** (C8) : fait propre 1, parent 1, sous-tâche 0, routine (récurrence
    quotidienne ou jours ouvrés) 0, autre récurrence 1, activité ERP close par lui 1, micro-tâche (≤ 10 min) 2 au plus
    par jour, rouverte retirée, abandonnée 0. Écran, tuile, bilan, moteur lisent CE nombre.
14. **Heure murale** : `jour_prevu`, `heure_debut`, `echeance`, `echeance_heure`, `Rappel.jour/heure` stockés en
    date + heure locales, jamais en instant UTC pré-calculé ; heure doublée = la première, inexistante = minute valide
    suivante.
15. `jour_prevu`, `heure_debut` et `moment` ne changent que par `services.planifier()` (PATCH les refuse en lecture
    seule) ; `heure_debut` exige `jour_prevu` ; `moment` dérivé de l'heure (< 12 h matin, < 18 h après-midi, sinon soir).
16. `statut = fait` ⇔ `fait_le` non nul ; `annule` ⇔ `annule_le` non nul ; rouvrir les remet à nul.
17. Un projet ne passe `termine` que par `terminer` ; `issue` obligatoire.
18. Au plus 3 lignes `essentielle` par `PlanJour` ; revalider le plan n'ajoute que des lignes ; « Alléger » retire les
    lignes des tâches renvoyées dans Proposé.
19. Rappels : ≤ 5 `en_attente` par tâche, ≤ 100 par utilisateur ; tâche close, abandonnée ou supprimée → ses rappels
    `annule`.
20. Un seul jeton actif par usage ; `capture` ne fait que créer une tâche pour son propriétaire ; jamais le jeton
    d'agenda de `reporting`.
21. Annuler ne lit jamais un état envoyé par le navigateur ; seuls les champs de la liste blanche §4 sont restaurés.
22. Au plus 3 notifications de sollicitation par jour (rappels posés et push de test hors compte) ; aucune hors fenêtre
    de la société, après `heure_limite`, en congé, un jour non travaillé, pour un compte inactif ; une sollicitation
    hors fenêtre est SAUTÉE, jamais différée.
23. Lien ERP : cible ∈ `CibleLiable` ET visible par l'utilisateur via le sélecteur de l'app cible ; `libelle` servi
    vide hors `ok` (« Lead effacé » pour `efface`).
24. Objectif entre 1 et 12 ; jamais imposé à la baisse ; un cran au plus par proposition.
25. Un seul projet « de la semaine » par propriétaire et par semaine.
26. Aucun objet `taches` dans la corbeille de l'ERP, la recherche globale, `record_targets`, ni le décompte
    `_traces_du_compte`.

## 4. Opérations annulables (`GesteAnnulable.operations`) et liste blanche

Types de geste : `creation`, `modification`, `planification`, `deplacement`, `terminaison`, `reouverture`,
`suppression`, `restauration`, `conversion`, `lot`, `decalage`, `instanciation`, `plan_du_jour`, `bilan_du_soir`,
`allegement`, `retour_absence`, `decision`, `rappel`, `preference`, `rythme`, `suggestion`, `revue`.

Une opération : `{"op":"champ","objet":"tache","id":41,"champ":"jour_prevu","avant":"2026-11-17","apres":"2026-11-19"}`
· `{"op":"creation","objet":"tache","id":90}` (inverse : `soft_delete(record=False)` ou suppression dure) ·
`{"op":"suppression_douce","objet":"projet","id":3}` (inverse : `restore()`) · `{"op":"suppression_dure",
"objet":"section","id":8,"valeurs":{…}}` (inverse : recréation au même `pk`). Conflit = valeur courante ≠ `apres` (ou
objet disparu) → l'objet est rendu dans `conflits`, inchangé. Toute FK restaurée est revérifiée « même propriétaire ».

| `objet` | Champs restaurables |
|---|---|
| `tache` | titre, notes, statut, fait_le, annule_le, priorite, jour_prevu, moment, heure_debut, echeance, echeance_heure, quelque_jour, estimation_minutes, projet, section, reports, reports_tranches, premier_jour_prevu, rang_projet, rang_jour, triee_le, en_attente_de, bloquee_par, jalon, confidentiel, `lien` (revalidé par `resolve_target`) |
| `projet` | nom, objectif, icone, couleur, priorite, statut, statut_depuis, date_debut, echeance, termine_le, issue, bilan, risque, domaine, planification_le, rang, confidentiel, affichage |
| `section` | nom, rang, date_debut, date_fin |
| `element_checklist` | libelle, fait, fait_le, rang |
| `etiquette_tache`, `ligne_plan_jour`, `revue_projet` | création / suppression seulement |
| `plan_jour` | planifie_le, cloture_le, reflexion, objectif_du_jour |
| `rappel` | statut, jour, heure |
| `preference` | valeur (création / suppression) |
| `reglages_rythme` | mode, palier, palier_source, bloc_debut, refus_montee, blocs_a_sauter, baisse_refusee, essai_restant, tenir_reference, tenir_fixee_le, tenir_silence_jusquau, pauses_sollicitations |
| `suggestion_tache` | statut, tache, decidee_le |
| `incitation_coach` | reponse, repondu_le |

Jamais : `proprietaire`, `company`, `parent`, `content_type`/`object_id` bruts, `client_id`, `source`, `lock_version`,
un champ de `JetonAcces`, « Tout effacer ».

## 5. Fonctions uniques imposées

| Fonction | Fichier | Contrat |
|---|---|---|
| `taches_de(user)` (+ `projets_de`, `sections_de`, `etiquettes_de`, `rappels_de`, `gestes_de`… bâtis sur le même filtre) | `selectors.py` | `company=user.company` ET `proprietaire=user` (sections : `projet__proprietaire`) ; derrière TOUTE lecture, viewsets compris |
| `taches_de_la_journee(user, jour)` | `selectors.py` | préfiltre invariant 10 |
| `compter_journee(user, jour)` | `selectors.py` | `n` de l'invariant 11 ; servi par `badge/` ET recalculé par `aujourdhui/` (même fonction) ; passé à `notify(badge=n)` |
| `Tache.est_confidentielle()` / `Projet.est_confidentiel()` | `confidentialite.py` | invariant 8 |
| `nom_pour(obj, usage)` | `confidentialite.py` | `usage ∈ {ecran, assistant, flux, tuile, notification}` → titre réel ; « Tâche confidentielle »/« Projet confidentiel » (assistant, flux, tuile) ; « Tâche » (flux/tuile, titres coupés) ; `None` (notification : le gabarit sans titre est utilisé). Tout générateur de phrase l'appelle |
| `creer_taches(user, lignes, *, source, porte, client_id=None, lien=None, parent=None)` | `services.py` | seul créateur ; trois portes `POST taches/`, `POST saisie-rapide/`, `POST capture/` (+ suggestions, conversion, récurrence, modèles) ; idempotence par lecture `Tache.all_objects.filter(company, proprietaire, client_id)` puis `IntegrityError` relue ; pose `triee_le` (inv. 1) ; rend `geste_id` |
| `planifier(tache, *, jour_prevu, moment, heure_debut, quelque_jour, compter_report=True, verrou=None)` | `services.py` | seul chemin qui déplace un jour ; `select_for_update()` ; `reports` par `F()` ; appelé par planifier, lot, rituels, trancher, alléger, retour, décaler et instancier (`compter_report=False`), assistant |
| `enregistrer_geste()` / `annuler_geste()` | `gestes.py` | §4 |
| `jours_travailles_de(user, du, au)` / `prochain_jour_travaille(user, jour)` | `selectors.py` | `jours_ouvres_entre` (`notifications/calendar_utils.py:164`) ∩ `Preference.jours_travailles` − `conges` ; un seul appel par lecture |
| `filtrer_q(qs, q)` | `selectors.py` | mots ET, `icontains` sans accents sur titre, notes, projet, étiquettes (C22) |
| `url_de_cible(cible, id)` / `libelle_de_cible(cible, obj)` | `selectors.py` | `contract_samples/liens_cibles.json` ; libellé sans étape de lead |
| `neglige(projets, faites_14j)` | `moteur/sante.py` | sert la revue, la relance et le constat C8 (C18) |

## 6. Migrations

1. `apps/taches/migrations/0001_initial.py` — les 19 modèles §2.1-2.18, contraintes et index ; dépendances
   `authentication` (dernière), `contenttypes 0002`, `records 0014_attachment_file_key_index` (dernière vue dans cette
   session ; reprendre la dernière au moment du build). Écrite par UNE lane « socle » qui livre aussi `models.py`,
   `choix.py`, `confidentialite.py`, `selectors.py` (signatures), `urls.py` complet, un fichier de vues par lane
   (`views_saisie.py`, `views_journee.py`, `views_agenda.py`, `views_projets.py`, `views_rythme.py`,
   `views_presence.py`, `views_erp.py`, `views_reglages.py`) dont chaque vue rend 501 tant que sa lane n'a pas
   livré, `sweeps.py` (les deux tâches, imports locaux vers `balayage.py` et `nocturne.py`) et `contract_samples/*.json`.
   Elle atterrit SEULE sur `main` (PACT10) ; ensuite les autres lanes ne touchent ni `models.py` ni `migrations/`.
2. `0002_agendaexterne.py` — `AgendaExterne`, dernière vague (A14-M8), lane « agenda externe ».
3. Tout autre ajout de champ = `0003+`, séquentiel, par une seule lane à la fois.
4. Hors `taches` (tâche séparée, propriétaire `parametres`) : `apps/notifications/migrations/0079_eventtype_taches.py`
   (3 `AlterField`, `max_length=40`, patron `0078_eventtype_travail_de_fond_echoue.py`).

## 7. Modules de code PUR (sans base, stdlib, fonctions ≤ 60 lignes logiques)

| Fichier | Fonctions | Règle tenue |
|---|---|---|
| `apps/taches/saisie.py` | `normaliser(texte)` (’ ‘ ʼ → ', espace insécable → espace, verif-specs-2-3 M12) · `cle_nom(nom)` · `analyser(texte, maintenant, projets, etiquettes, ignorer, porte)` (masquer → candidats `[(type, motif, convertisseur)]` → choisir sans chevauchement → assembler) · `decouper_collage(textes, …)` | s2 §3.1-3.3 + : « tous les N mois / every N months », moment dérivé de l'heure, « 10 h » avec espace (A14-M6) ; porte `capture` : seuls jour, heure, moment, échéance, priorité, durée, projet EXISTANT (A1) ; 1re ligne suivie d'au moins deux lignes = projet proposé (A14-M9) ; titre de groupe « … : » |
| `apps/taches/moteur/recurrence.py` | `premiere_occurrence(regle)` · `prochaine_occurrence(regle, occurrence_du, aujourdhui, fait_le, est_ouvre)` · `libelle_regle(regle)` | s2 §3.5, annexe B (25 cas) |
| `apps/taches/moteur/classement.py` | `placer(t, J, plan)` (§3 inv. 3, 10) · `cle_tri(item, J, n_ouvres)` (k1-k7 ; activité `pmax = priorite = 0` ; focus ⇒ `pmax = 3`) · `explication(item)` (≤ 3 faits) · `capacite(reglage, minutes_9j, jours_28)` · `proposer_plan(pool, objectif, capacite, exclure, inclure)` | s3 §3.1-3.4, C18, verif-specs-2-3 m7 |
| `apps/taches/moteur/sante.py` | `avancement` · `burnup` · `sans_prochaine_action` (≥ 1 ouverte exigée) · `a_l_arret` · `echeance_menacee` · `neglige` · `constat_projets` | s4 §E-F, verif-specs-4-6 m7 |
| `apps/taches/moteur/decalage.py` | `decaler(dates, delta, est_travaille, aujourdhui)` (Δ < 0 : jour travaillé précédent ; refus jugé après rectification) · `instancier(contenu, date_lancement, est_travaille)` · `figer_modele(projet_dict, inclure_notes)` | s4 §B, §G, verif-specs-4-6 m8 |
| `apps/taches/moteur/rythme.py` | `compte_du_jour` · `statut_jour` · `journee_reussie` · `palier_initial` · `plafonner_jours(comptes)` (2 × médiane + 1, A2.3) · `evaluer_bloc` (monter ≥ 5/10, baisser ≤ 3/10, A2.2) · `clore_bloc` · `objectif_dit(etat, nombre, sens)` (immédiat, A2.1) · `reference_tenir` · `bande_tenir` · `derive_tenir` · `objectif_affiche` · `basculer` · `arrondir` (au plus proche, la demie vers le bas) · `constats(donnees)` C1-C8 · `retour_absence(jours, taches)` | s5a §3, §7, A2, A14-B1 |
| `apps/taches/moteur/sollicitations.py` | `due(type, maintenant, prefs, fenetre)` (tick dans [heure, heure + 15 min)) · `choisir_relance(candidats)` · `etat_decroissance(ignorees)` (pause après 14) · `variante(ordinal)` (`% 3`) · `plafond_atteint(journal)` | s5a §3.9, socle §5 |
| `apps/taches/moteur/gabarits.py` | `texte(type, cle, donnees, variante, nom_pour)` | §8 |
| `apps/taches/moteur/flux.py` | `evenements_flux(taches, jour, reglages, nom_pour)` → formes `{uid, date \| start_dt + end_dt, summary, description:''}` de `reporting.calendar.build_ics` ; 8 journées entières par jour, puis « + N autres tâches » ; UID `tache-<id>` | s6b §4 |

## 8. Gabarits de sollicitation (`moteur/gabarits.py`, trois variantes par rotation)

Titres push : `plan_matin` « Aujourd'hui » · `relance` « Message de 15 h » (l'heure de `relance_jour`) · `bilan_soir` « Bilan du soir » ·
`revue_semaine` « Revue de la semaine » · rappel « Rappel ». Corps = des comptes (titres seulement si
`titres_notifications` et non confidentielle). Le matin ne compte que les tâches DU JOUR (A14-B1).

- Matin, `pousser` : « Ta journée : 7 tâches prévues. Objectif 5. » · « Bonjour. 7 tâches t'attendent ; objectif du
  jour : 5. » · « Plan du jour : choisis ton essentiel (objectif 5). »
- Matin, `tenir` (A2.5) : « Ta journée : 7 tâches prévues. Ton rythme : 4 à 6. » · « Bonjour. 7 tâches t'attendent ;
  ton rythme : 4 à 6. » · « Plan du jour : choisis ton essentiel (rythme 4 à 6). »
- Matin, `libre` (A2.5) : « Ta journée : 7 tâches prévues. » · « Bonjour. 7 tâches t'attendent. » · « Plan du jour :
  choisis ton essentiel. »
- Message de 15 h, échéance : « 1 tâche a son échéance aujourd'hui. » · « Échéance aujourd'hui : 1 tâche encore
  ouverte. » · « Avant ce soir : 1 tâche à échéance. » ; dérive `pousser` : « 2 faites sur 5 ; ton essentiel est encore
  ouvert. » ; dérive `tenir` : « 7 faites, ta zone est 4 à 6 : le reste peut attendre demain. » ; projet négligé
  (A2.5) : « Ton projet prioritaire n'a pas avancé depuis 14 jours. » (avec titres : « « {projet} » n'a pas avancé
  depuis 14 jours. »).
- Soir : « Bilan : 4 faites sur 6 prévues. » · « Journée close ? 4 tâches faites. » · « 4 faites, 2 à placer. »
  (accord : « 1 faite »).
- Bilan (écran) : `pousser` « Aujourd'hui : 6 faites · objectif 5 atteint · essentiel fait · plan tenu 4 sur 5. »
  (sinon « 3 faites (objectif 5) · … ») ; `tenir` « Aujourd'hui : 6 faites (ton rythme : 4 à 6) · essentiel fait ·
  plan tenu 4 sur 5. » ; `libre` « Aujourd'hui : 6 faites · essentiel fait · plan tenu 4 sur 5. » ; détail « 2
  micro-tâches comptées sur 4 ». UN constat au plus en dessous (A14-M4).
- Cartes : monter « Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ? » [Oui, 6] [Pas
  maintenant] · baisser « Ces 10 jours travaillés, 6 tâches ou plus : 2 fois. Revenir à 5 pour un temps ? » [Oui, 5]
  [Garder 6] · taille « Tes tâches terminées sont plus courtes qu'au départ (22 min en médiane contre 33) : je ne
  propose pas de monter. » [Mes tâches ont changé] · premier « J'ai 10 jours de toi : ta journée type est 3 tâches. Ton
  objectif passe de 5 (valeur par défaut) à 3. » · tenir « Ces 14 jours travaillés : 3,4 tâches par jour, sous ta zone
  4 à 6. Garder 5 ou passer à 3 ? » · pause « J'ai mis en pause le rappel du matin. Le réactiver ? » · retour
  (A14-B1 ; fin de congé ou ≥ 3 jours travaillés sans ouverture, une fois) « Tu reviens après 10 jours : 18 tâches
  attendaient. » [Les remettre dans Proposé] [Les voir une par une] ·
  semaine « Du 16 au 20/11 : 26 tâches en 5 jours (précédente : 23). Journées réussies 3 sur 5 · essentiel 4 sur 5 ·
  plan tenu 21 sur 27. Samedi : 2. » · constats C1-C8 : phrases de s5a §3.8, noms via `nom_pour`.
- Nouvelle tâche capturée (A1) : « Ajouté pour demain 10 h : appeler le fournisseur » ; rien reconnu : « C'est noté :
  appeler Karim » (titre coupé à 60 car.).

## 9. Purges et rétention (tâche `taches.nocturne`)

Tâche ou projet supprimé : 30 jours puis suppression dure (socle §8) · `GesteAnnulable` : 7 jours · `SuggestionTache`
: visible 7 jours, purgée à 30 · `IncitationCoach`, `PlanJour`, `LignePlanJour` : 90 jours (I11) · `Rappel` non
`en_attente` : 30 jours (I11) · « Comprendre mon rythme » coupé : suppression des cartes `constat`, `proposition_palier`,
`derive_tenir`, `garde_taille`, remise à nul de `tenir_*`, `ref_taille_min`, `meilleur_tenu`, `echec_*`, des champs
de rythme de `PlanJour` (`statut_jour`, `compte_rythme`, `micro_comptees`, `taille_mediane_min`), capacité « habituelle »
et signal (d) d'échéance menacée tus (verif-securite m14). Export et « Tout effacer » couvrent les 20 modèles §2.

## Décisions de l'intégrateur

- **I1** Clés de palette : huit clés neutres ; l'esthétique en fixe le rendu ; en ajouter = un `AlterField`.
- **I2** `nom_cle` (normalisé sans casse, accents, espaces, `-`, `_`) sur Projet, Section, Etiquette : une seule clé
  sert l'analyseur (`#nom`) ET l'unicité ; sinon « Chantier X » et « chantier x » coexistent malgré la règle s2 §3.2.
- **I3** `titre` Char(280) partout (design-s1 255, s6b 280) : la plus large des deux, une seule validation.
- **I4** `Tache.content_type` SET_NULL (design-s1 CASCADE) : s6a veut une tâche « JAMAIS supprimée » par son lien.
- **I5** `PlanJour.app_ouverte_le` + route `POST vu/` : comble le trou T12 (statut `sans_donnees`, notification
  « ignorée ») sans écriture dans un GET.
- **I6** `LignePlanJour.titre_fige` supprimé et `tache` en CASCADE : le titre copié survivait à la purge et à
  l'effacement (verif-securite M2 b, M5, m13) ; les compteurs du jour restent sur `PlanJour`.
- **I7** `ReglagesRythme.pauses_sollicitations` : la carte « Le réactiver ? » doit écrire quelque part ; un type en
  pause n'émet plus rien, donc l'ouverture ne peut pas remettre à zéro.
- **I8** Sollicitations réservées aux comptes qui ont une `ReglagesRythme` (premier usage) : sinon tout utilisateur
  interne recevrait un plan du matin sans avoir jamais ouvert Tâches.
- **I9** `IncitationCoach` sans `texte` : texte rendu à la lecture (nom confidentiel, effacement 09-08 sans copie).
- **I10** Un seul agenda externe par utilisateur en v1 (le plus simple ; la contrainte se lève par migration).
- **I11** Rétention 90 jours (plan, lignes, journal) et 30 jours (rappels clos) : aucune règle ne lit plus de 42 jours
  calendaires ; minimisation 09-08 (trou T4). À valider par l'orchestrateur.
- **I12** Section technique `a_decider` gardée (noms d'API inchangés, A13) ; montrée « À revoir » (A14-M10).
- **I13** Constats C4 et C6 : pas de clé `Preference` dans l'union C4 ; C4 = un bouton du plan sans mémoire, C6 = correction
  automatique du budget ; C1 et C2 écrivent `essentiel_le_matin` (source `carte`).
- **I14** Révélations : seules celles que le serveur peut détecter sont des cartes (`mon_iphone` dès le premier collage,
  A14-M5 ; `ranger_copilote` À trier ≥ 5 ; `planifier_projet` ; `revue`) ; les astuces de geste (« tape #… »,
  « balaie… », raccourcis clavier) restent côté navigateur.
- **I15** Projet supprimé : sa restauration restaure ses tâches supprimées dans le même geste ; une tâche restaurée dont
  le projet reste supprimé revient dans À trier.
- **I16** Suggestions de chantier liées au lead du chantier (le chantier n'est pas liable, A3).

## Ce que les specs demandaient et que je n'ai PAS repris

- `Tache.rappel_le` (s2) → `Rappel` (C1) ; `heure_prevue` (s2) → `heure_debut` (C10) ; `Tache.assigne_a` (design-s1, absent
  du socle) ; statut `en_cours` (design-s1 ; socle `en_attente`).
- `Annulation` + `annulations/{id}/appliquer/` (s5b) et le corps `decaler/annuler` (s4) → `GesteAnnulable` (C2, A7, M4).
- `GesteAnnulable.avant` avec `lock_version_apres` (s2) → opérations par champ (C2).
- design-s1 : `ReglagesRythme.objectif_nb_jour`, `objectif_auto`, `heure_plan`, `heure_cloture`, `conges_du/au`,
  `max_incitations_jour`, `jeton_capture_hash` (→ Preference, plafond du socle, `JetonAcces`) ; `PlanJour.nb_*` et
  `nb_reportees` (C23) ; `IncitationCoach.texte`, canal `assistant` (C14, I9) ; étiquettes `records.Tag` (socle §2.3) ;
  `record_targets`, `searchable_models`, restaurateur de corbeille (socle §2.2-2.4) ; alimentation de `ma_file` et du
  flux iCal d'équipe (s6a §3.6, s3 §3.7) ; modes `progresser/maintenir` (C42).
- Clés `Preference` de s5b (`heure_limite_rappels`, `heure_plan_matin`, `heure_bilan_soir`, `rappel_journee`,
  `jours_off`, `semaine_revue`, format « vendredi=120 ») → noms s5a (C4, C27) ; `mode_rythme`, `titres_notifications`,
  `comprendre_mon_rythme`, `rappel_avant_bloc_min`, `projet_arret_jours` en Preference → `ReglagesRythme` (C4) ;
  `texte_dit` (non stocké : minimisation).
- `JetonAcces.empreinte` → `jeton_hash` (M6) ; `cree_le` (= `created_at`).
- `Projet.planifie_le` → `planification_le` (C41) ; `Projet.visibilite = partage` (rien construit, D-TCH-1).
- `SuggestionTache.destinataire` → `proprietaire` (C33) ; `SuggestionTache.lien_libelle` et titres avec `{client}`
  (A4, M5) ; liens facture, chantier, ticket et les 9 autres cibles déclarées (A3, jusqu'à leur sélecteur de visibilité).
- `LignePlanJour.titre_fige` (I6) ; index `taches_tache_cible_idx` (remplacé par `taches_tache_lien_idx`).
- Seuil de montée 6/10 et « arrondi inférieur » (s5a) → 5/10 et demie vers le bas (A2) ; proposer la journée type à
  chaque baisse quand l'écart ≥ 3 (verif-spec-5a constat 7 : ajoute un comportement non mesuré).
- Capture « sans analyse, toujours dans la Boîte » (s2 §3.4, s6b §5, C3) → analysée et rangée comme comprise (A1,
  A14-M6) ; « En réserve » non lu par la porte capture (absent de la liste A1).
- Lecture « Ailleurs dans l'ERP » dans `aujourdhui/` → route paresseuse (s6a §2, trou T13) ; textes « Mes tâches » et
  « Ma journée » → « Tâches », « Aujourd'hui » (A13, s7) ; « Tâche privée » (s5b) → « Tâche confidentielle » (s7 §3).
- Texte mot pour mot de Réglages → Vie privée (A9) : texte d'écran, hors de cette référence des données.
