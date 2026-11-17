# Référence des DONNÉES — `apps/taches` (révision 2)

Référence UNIQUE du schéma. Une lane ne rouvre jamais les specs pour savoir comment une chose s'appelle : elle lit ce
fichier et `api.md` ; les algorithmes sont dans `regles.md`, les mots montrés dans `textes.md`. Primauté appliquée :
socle §0/§8 → arbitrages A1-A17 → spec-7 révision 3 (mots, routes du front) → `verif-reference.md`, `verif-spec-7*`
et les autres vérifications (C1…C48, B/M) → specs → design-s1. Chemins relatifs à `backend/django_core/`.

## 0. Bases vérifiées dans le code

| Nom imposé | Où | Ce qu'il apporte |
|---|---|---|
| `core.models.TenantModel` | `core/models.py:62` | `company` FK CASCADE, `created_at`, `updated_at` |
| `core.models.SoftDeleteModel` | `core/models.py:155` | `is_deleted`, `deleted_at`, `deleted_by` ; `objects` vivants, `all_objects` tout ; `soft_delete(user, record=…)` (:181), `restore()` (:227, émet `record_soft_restored`) |
| `core.champs_plateforme.VerrouOptimisteMixin` | `core/champs_plateforme.py:31` | `lock_version` 0 à la création, +1 à chaque `save()` (pas sur `QuerySet.update()`) |
| `core.verrou_optimiste.version_envoyee`, `ConflitVersion` | `core/verrou_optimiste.py:52`, `:39` | lecture de la version envoyée ; 409 `{detail, code:"conflit_version", lock_version, actuel}` |
| `core.viewsets.CompanyScopedModelViewSet` | `core/viewsets.py:65` | `TenantMixin` + `ScopedPermission` (`read_permission`/`write_permission`) |
| `authentication.active_company.user_can_operate` | `authentication/active_company.py:76` | l'utilisateur peut-il opérer dans cette société (routes à jeton) |
| `core.dsr.register_dsr_provider` | `core/dsr.py:86` | fournisseur d'export et d'effacement 09-08 |
| `core.pagination.StandardPagination` | `core/pagination.py:61` | pagination par défaut (50) |

Règles transverses (chaque modèle) :
- `TenantModel` partout ; `Projet` et `Tache` = `TenantModel, SoftDeleteModel, VerrouOptimisteMixin`.
- Suppression d'un Projet ou d'une Tache : TOUJOURS `soft_delete(user, record=False)` (pas de `DeletionRecord`, pas de
  corbeille commune, socle §2.2). Les autres modèles : suppression dure.
- `__str__` neutre par un mixin unique `StrNeutreMixin` (`f"{verbose_name} #{pk}"`), jamais un titre.
- Utilisateur = `settings.AUTH_USER_MODEL`, nommé `proprietaire` PARTOUT (C33).
- Unicité : champs commençant par `company` ; sur Projet/Tache, `is_deleted=False` dans `condition`. Noms ≤ 30
  caractères, préfixe `taches_`. Django 5.2 : `CheckConstraint(condition=…, name=…)` (mot-clé) ; tout `JSONField` à
  défaut liste ou dict prend un appelable (`default=list`, `default=dict`).
- `nom_cle` (Projet, Section, Etiquette) : calculé dans le seul `save()` du modèle par `saisie.cle_nom(nom)` ;
  `bulk_create` et `QuerySet.update(nom=…)` INTERDITS sur ces trois modèles (sinon `''` et collision).
- Jours = `timezone.localdate()` dans le fuseau de la société (`CELERY_TIMEZONE = 'Africa/Casablanca'`).
- Ordre manuel : entiers espacés de 1 024 ; renumérotation de la seule liste concernée par `QuerySet.update()`.
- Tout compteur lu puis réécrit (`reports`, `refus_montee`, `blocs_a_sauter`, `echec_n`…) et tout changement de
  statut vérifié dans un service passe par `select_for_update()` ou `F()` (`check_read_modify_write.py`).

## 1. Énumérations fermées (`apps/taches/choix.py`)

| Énumération | Valeurs techniques → libellé (textes.md §1, spec-7 r3 §3) | Source |
|---|---|---|
| `Priorite` (IntegerChoices) | 0 aucune · 1 basse · 2 moyenne · 3 haute | socle §3 |
| `StatutTache` | `a_faire` · `en_attente` « En attente de… » · `fait` · `annule` « Abandonnée » | socle |
| `StatutProjet` | `actif` · `en_pause` · `termine` · `archive` | socle |
| `IssueProjet` | `''` · `atteint` · `abandonne` | s4 §I |
| `Moment` | `''` · `matin` · `apres_midi` · `soir` « Ce soir » | socle |
| `Creneau` (LignePlanJour, constat C1) | `''` · `matin` (< 12 h) · `apres_midi` (12-16 h) · `fin_journee` (≥ 16 h) | regles manque 6 |
| `Source` | `manuel` · `rapide` · `assistant` (repère, A5) · `capture` · `activite` (conversion ET lien) · `recurrence` · `modele` · `suggestion` | C31 |
| `Couleur` | `terre` · `ambre` · `olive` · `vert` · `menthe` · `ciel` · `bleu` · `indigo` · `prune` · `rose` | A15, spec-8 §3 |
| `Visibilite` | `prive` | socle, D-TCH-1 |
| `LienEtat` | `''` · `ok` · `archive` · `introuvable` · `inaccessible` · `efface` | s6a §3.2 |
| `CibleLiable` | `crm.lead` · `crm.client` · `ventes.devis` | A3 |
| `Frequence` / `ModeRecurrence` | `quotidien` · `jours_ouvres` · `hebdo` · `mensuel` · `annuel` / `calendrier` · `apres_fait` | s2 §3.5 |
| `ModeRythme` | `pousser` « En faire plus » (défaut) · `tenir` « Garder ce rythme » · `libre` « Sans objectif » | s5a, s7 |
| `SourceObjectif` | `defaut` · `calcule` · `accepte` · `dit` · `libre` | C13 |
| `CapaciteSource` | `defaut` · `historique` · `reglage` | s3 §3.4 |
| `StatutJour` | `conge` · `non_ouvre` · `sans_donnees` · `evalue` | s5a §3.2 |
| Sections de la journée | `essentiel` « Essentiel » · `journee` « Prévu » · `ce_soir` · `propose` « Proposé pour aujourd'hui » · `a_decider` « À revoir » · `en_attente` · `faites` | spec-7 r3 §4 |
| `MotifRevoir` | `reportee_3_fois` · `jour_passe` · `echeance_passee` · `echeance_proche` · `activite_passee` (activité ERP due avant J) | s3 §3.1, A17 |
| `Decision` (sous-ensembles par route, api.md) | `aujourdhui` · `garder` (sa date si ≥ J, sinon J) · `prochain_jour_ouvre` « Reporter à lun. 23 » · `jour` (+ date) · `un_jour` « En réserve » · `abandonner` | s3, A17 (MAJ-5), spec-7 r3 |
| `FamilleObligation` | `visite` · `pose` · `intervention` (date seule, bande « Toute la journée », N4) · `touches` (« Suivi des relances ») | s6a, A16-N4, min-21 |
| `CarteDuMoment` (ordre de priorité) | `retour` · `bilan_hier` · `garder` · `alleger` · `faire_bilan` · `rythme` · `revelation` (le brouillon et l'astuce de geste sont posés par le navigateur, spec-7 r3 §4) | spec-7 r3 §4, A17-M1 |
| `CodeSante` | `sans_prochaine_action` · `a_l_arret` · `echeance_menacee` · `neglige` · `tout_fait` | s4 §E-F |
| `AlerteSaisie` | `deux_<type>` · `date_passee` · `heure_passee` · `plusieurs_projets` · `projet_archive` · `date_invalide` · `duree_hors_bornes` | s2, regles manque 12 |
| `TypeJeton` (saisie) | `jour` · `heure` · `moment` · `echeance` · `quelque_jour` · `projet` · `section` · `priorite` · `etiquette` · `duree` · `recurrence` · `rappel` | s2 §3.1 |
| `StatutRappel` / `SourceRappel` / `AncreRappel` | `en_attente` · `envoye` · `manque` · `annule` / `manuel` · `repetition` · `bloc` / `''` · `jour_prevu` · `echeance` | s3 §3.9 |
| `UsageJeton` | `capture` (`tqc_`) · `flux` (`tqf_`) · `tuile` (`tqt_`) | socle §2.5 |
| `TypeIncitation` canal `push` | `plan_matin` « Aujourd'hui » · `bilan_soir` · `revue_semaine` · `relance` « Message de {heure} » | C14, textes IT13 |
| `TypeIncitation` canal `ecran` | `proposition_palier` · `derive_tenir` · `garde_taille` · `constat` · `pause` · `retour` · `revelation` | C14, A14-B1 |
| `ReponseIncitation` | `''` · `oui` · `pas_maintenant` · `garder` · `garder_ce_rythme` · `passer` · `taches_changees` · `reactiver` · `remettre_dans_propose` · `une_par_une` · `ok` · `ignoree` · `expiree` | s5a, A14-B1 |
| `CanalIncitation` | `push` · `ecran` | C14 |
| `FamilleSuggestion` / `StatutSuggestion` | `devis_accepte` · `chantier_receptionne` · `chantier_annule` (allumées) · `visite_validee` (éteinte) / `proposee` · `acceptee` · `refusee` · `retiree` | s6a, A4 |
| `DecisionRevue` | `''` · `garder` · `pause` · `terminer` · `passe` « Suivant » | s4 §H |
| `SourcePreference` | `ecran` · `copilote` · `carte` | s5b §5 |
| `EtatAgendaExterne` | `''` · `ok` · `refusee` · `trop_grande` · `delai` · `illisible` | A14-M8 |
| `EventType` (app `notifications`, fin d'énum) | `TACHES_PLAN_DU_JOUR` · `TACHES_BILAN_SOIR` (bilan + revue) · `TACHES_RELANCE` · `TACHES_RAPPEL` (rappel posé + test) | s6b §3, C14 |

`IncitationCoach.cle` : push `''` ; `proposition_palier` `monter` · `baisser` · `premier` · `journee_type` ;
`derive_tenir` `sous` · `au_dessus` ; `garde_taille` `''` ; `constat` `C1`…`C8` ; `pause` = le type push en pause ;
`retour` `''` ; `revelation` `mon_iphone` · `ranger_copilote` · `planifier_projet` · `revue`. Réponses permises :
`monter` {oui, pas_maintenant, garder_ce_rythme (3e refus de suite)} · `baisser` {oui, garder} · `premier` {oui,
garder} (« [Oui, 3] [Garder 5] » : la baisse du démarrage est proposée, jamais imposée, A2.2, tour 3) · `journee_type`
{oui, pas_maintenant} · `derive_tenir` {garder, passer} · `garde_taille` {taches_changees, ok} · `constat` {oui,
pas_maintenant} (C5 : {ok}) · `pause` {reactiver, ok} · `retour` {remettre_dans_propose, une_par_une} · `revelation`
{ok}. `ignoree` et `expiree` sont posés par la tâche nocturne seulement.

## 2. Modèles

Comptés par script (lignes des tableaux « Champ ») : **20 modèles, 213 champs propres** (hors colonnes héritées),
11 clés `Preference`. Colonnes héritées non répétées : `id`, `company`, `created_at`, `updated_at` (+ `is_deleted`,
`deleted_at`, `deleted_by`, `lock_version` sur Projet et Tache). Colonne « Règle » : valeurs, bornes, `# on_delete:` (commentaire
obligatoire, garde `check_on_delete`) et source.

### 2.1 `Projet` (`TenantModel, SoftDeleteModel, VerrouOptimisteMixin`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `ForeignKey(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles, suivent le compte` · socle |
| `nom` | `CharField(120)` | — | 1-120 · socle |
| `nom_cle` | `CharField(120, editable=False)` | — | `cle_nom(nom)` dans `save()` · I2 |
| `objectif` | `TextField` | `blank` `''` | « Ce sera fini quand… » · s4 |
| `icone` | `CharField(8)` | `blank` | un emoji · socle |
| `couleur` | `CharField(16, choices=Couleur)` | couleur d'office (regles §5) | palette A15 |
| `priorite` | `PositiveSmallIntegerField(choices=Priorite)` | 0 ; né par `#` ou par un collage : 2 « Moyenne » | A16-M3, A17-M3 ; demandée à l'étape 1 de Planifier le projet |
| `statut` | `CharField(12, choices=StatutProjet)` | `actif` | socle |
| `statut_depuis` | `DateTimeField` | `default=timezone.now` | posé à chaque changement de statut · s4 |
| `date_debut`, `echeance` | `DateField` | `null` | socle |
| `termine_le` | `DateTimeField` | `null` | socle |
| `issue` | `CharField(10, choices=IssueProjet)` | `blank` | s4 §I |
| `bilan`, `risque` | `CharField(280)` | `blank` | s4 |
| `domaine` | `CharField(40)` | `blank` | montré « Groupe » · s4 |
| `planification_le` | `DateTimeField` | `null` | « À planifier » ⇔ actif ∧ nul ∧ 0 ouverte · C41 |
| `rang` | `IntegerField` | 0 | pas 1 024 ; « Mettre en haut » = rang du premier − 1 024 |
| `confidentiel` | `BooleanField` | `False` | socle §2.7 |
| `visibilite` | `CharField(10, choices=Visibilite)` | `prive` | socle |
| `affichage` | `JSONField` | `default=dict` | clés fermées `vue` (`liste`/`tableau`/`chronologie`, mémorisée), `tri`, `groupe`, `montrer_faites` · s2, spec-7 r3 |

Contrainte `taches_projet_nom_uniq` (company, proprietaire, nom_cle) `condition=Q(is_deleted=False)`. Index
`taches_projet_stat_idx` (company, proprietaire, statut).

### 2.2 `Section` (`TenantModel`) — « Étape »

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `projet` | `ForeignKey(Projet, CASCADE)` | — | `# on_delete: composition` · socle |
| `nom` | `CharField(120)` | — | socle |
| `nom_cle` | `CharField(120, editable=False)` | — | I2 |
| `rang` | `IntegerField` | 0 | socle |
| `date_debut`, `date_fin` | `DateField` | `null` | s4 |

Contrainte `taches_section_nom_uniq` (company, projet, nom_cle). Index `taches_section_rang_idx` (projet, rang).
Suppression dure ; ses tâches passent « Sans étape ». Propriétaire = `projet.proprietaire`.

### 2.3 `Tache` (`TenantModel, SoftDeleteModel, VerrouOptimisteMixin`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles, suivent le compte` |
| `projet` | `FK(Projet, CASCADE, null)` | `null` | `# on_delete: composition, la purge du projet emporte ses tâches` |
| `section` | `FK(Section, SET_NULL, null)` | `null` | `# on_delete: étape supprimée → « Sans étape »` ; même projet |
| `parent` | `FK('self', CASCADE, null, related_name='enfants')` | `null` | `# on_delete: composition` ; un niveau |
| `titre` | `CharField(280)` | — | 1-280 · I3 |
| `notes` | `TextField` | `blank` | jamais servies à l'assistant, au flux, à la tuile |
| `statut` | `CharField(12, choices=StatutTache)` | `a_faire` | socle |
| `en_attente_de` | `CharField(200)` | `blank` | socle |
| `priorite` | `PositiveSmallIntegerField(choices=Priorite)` | 0 | socle |
| `jour_prevu` | `DateField` | `null` | lecture seule hors `planifier()` |
| `moment` | `CharField(12, choices=Moment)` | `''` | dérivé si `heure_debut` posée |
| `heure_debut` | `TimeField` | `null` | heure murale · C10 |
| `echeance` | `DateField` | `null` | socle |
| `echeance_heure` | `TimeField` | `null` | socle |
| `quelque_jour` | `BooleanField` | `False` | « En réserve » |
| `estimation_minutes` | `PositiveSmallIntegerField` | `null` | 5-960, pas 15 au redimensionnement |
| `duree_reelle_minutes` | `PositiveIntegerField` | `null` | socle |
| `rang_projet` | `IntegerField` | `null` | pas 1 024 |
| `rang_jour` | `IntegerField` | `null` | ordre dans une section du jour (invariant 32) |
| `premier_jour_prevu` | `DateField` | `null` | posé une fois |
| `reports` | `PositiveSmallIntegerField` | 0 | `F()` / `select_for_update` |
| `reports_tranches` | `PositiveSmallIntegerField` | 0 | s3 |
| `triee_le` | `DateTimeField` | `null` | invariant 1 |
| `client_id` | `CharField(64)` | `null` | UUID (+ `:<n>` par ligne) · C9 |
| `source` | `CharField(12, choices=Source)` | `manuel` | C31 |
| `jalon` | `BooleanField` | `False` | s4 |
| `bloquee_par` | `FK('self', SET_NULL, null, related_name='bloque')` | `null` | `# on_delete: prérequis purgé → débloquée` ; « En attente de… » (une tâche), puce « attend : Visite » |
| `content_type` | `FK(ContentType, SET_NULL, null, related_name='+')` | `null` | `# on_delete: lien perdu, tâche gardée` · I4 |
| `object_id` | `PositiveIntegerField` | `null` | socle |
| `lien_libelle` | `CharField(200)` | `blank` | `libelle_de_cible()` ; vidé par l'effacement 09-08 |
| `lien_etat` | `CharField(12, choices=LienEtat)` | `''` | s6a |
| `lien_verifie_le` | `DateTimeField` | `null` | s6a |
| `activite_origine` | `FK('records.Activity', SET_NULL, null, related_name='+')` | `null` | `# on_delete: activité purgée, tâche gardée` ; conversion OU lien (A17) |
| `recurrence` | `FK(RegleRecurrence, SET_NULL, null)` | `null` | `# on_delete: règle supprimée, occurrences gardées` |
| `occurrence_du` | `DateField` | `null` | socle |
| `confidentiel` | `BooleanField` | `False` | drapeau propre ; l'effectif = `est_confidentielle()` |
| `fait_le` | `DateTimeField` | `null` | socle |
| `annule_le` | `DateTimeField` | `null` | socle |

Contraintes : `taches_tache_cli_uniq` (company, proprietaire, client_id) `condition=Q(client_id__isnull=False,
is_deleted=False)` · `taches_tache_act_uniq` (company, activite_origine) `condition=Q(activite_origine__isnull=False,
is_deleted=False)` · `taches_tache_occ_uniq` (company, recurrence, occurrence_du) `condition=Q(recurrence__isnull=False,
occurrence_du__isnull=False, is_deleted=False)` · `taches_heure_sans_jour_ck` `CheckConstraint(condition=
Q(heure_debut__isnull=True) | Q(jour_prevu__isnull=False))` · `taches_ech_heure_ck` `CheckConstraint(condition=
Q(echeance_heure__isnull=True) | Q(echeance__isnull=False))`.
Index : `taches_tache_jour_idx` (company, proprietaire, statut, jour_prevu) · `taches_tache_ech_idx` (company,
proprietaire, statut, echeance) · `taches_tache_proj_idx` (projet, section, rang_projet) · `taches_tache_fait_idx`
(company, proprietaire, fait_le) · `taches_tache_boite_idx` (company, proprietaire, projet, triee_le) ·
`taches_tache_bloq_idx` (company, proprietaire, bloquee_par) · `taches_tache_lien_idx` (company, proprietaire,
content_type, object_id) · `taches_tache_purge_idx` (company, is_deleted, deleted_at). `ordering = ['rang_projet','id']`.

### 2.4 `ElementChecklist` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `tache` | `FK(Tache, CASCADE)` | — | `# on_delete: composition` |
| `libelle` | `CharField(255)` | — | s2 |
| `fait` | `BooleanField` | `False` | s2 |
| `fait_le` | `DateTimeField` | `null` | s2 |
| `rang` | `IntegerField` | 0 | pas 1 024 |

Index `taches_check_rang_idx` (tache, rang).

### 2.5 `Etiquette` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `nom` | `CharField(40)` | — | socle §2.3 |
| `nom_cle` | `CharField(40, editable=False)` | — | I2 |
| `couleur` | `CharField(16, choices=Couleur)` | `ciel` | A15, regles manque 2 |

Contrainte `taches_etiq_nom_uniq` (company, proprietaire, nom_cle).

### 2.6 `EtiquetteTache` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `tache` | `FK(Tache, CASCADE)` | — | `# on_delete: composition` |
| `etiquette` | `FK(Etiquette, CASCADE)` | — | `# on_delete: étiquette supprimée → retirée des tâches` |

Contrainte `taches_etiqt_uniq` (company, tache, etiquette).

### 2.7 `RegleRecurrence` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `frequence` | `CharField(12, choices=Frequence)` | — | s2 §3.5 |
| `intervalle` | `PositiveSmallIntegerField` | 1 | ≥ 1 |
| `jours_semaine` | `CharField(7)` | `'0000000'` | lun→dim, `1` = retenu |
| `jour_du_mois` | `SmallIntegerField` | `null` | 1-31, −1 = dernier |
| `rang_dans_mois` | `SmallIntegerField` | `null` | 1-4, −1 = dernier (un seul jour au masque) |
| `mode` | `CharField(12, choices=ModeRecurrence)` | `calendrier` | s2 |
| `date_debut` | `DateField` | — | s2 |
| `date_fin` | `DateField` | `null` | s2 |
| `actif` | `BooleanField` | `True` | « Arrêter » = `False` |

### 2.8 `PlanJour` (`TenantModel`) — compteurs du jour, SANS aucun titre

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `jour` | `DateField` | — | socle |
| `planifie_le` | `DateTimeField` | `null` | premier « Garder ces N » |
| `cloture_le` | `DateTimeField` | `null` | bilan validé |
| `app_ouverte_le` | `DateTimeField` | `null` | posé par `POST vu/` (I5) |
| `allege_le` | `DateTimeField` | `null` | posé par `journee/alleger/`, remis à nul par l'annulation ; Proposé replié et vide ce jour-là (A16-N6) |
| `reflexion` | `CharField(280)` | `blank` | « un mot » |
| `objectif_du_jour` | `PositiveSmallIntegerField` | `null` | C23 |
| `capacite_minutes` | `PositiveSmallIntegerField` | `null` | s3 |
| `capacite_source` | `CharField(12, choices=CapaciteSource)` | `''` | s3 |
| `statut_jour` | `CharField(12, choices=StatutJour)` | `''` (non clos) | s5a |
| `compte_rythme` | `PositiveSmallIntegerField` | 0 | s5a |
| `micro_comptees` | `PositiveSmallIntegerField` | 0 | s5a |
| `essentiels_choisis` | `PositiveSmallIntegerField` | 0 | s5a |
| `essentiels_faits` | `PositiveSmallIntegerField` | 0 | s5a |
| `plan_prevues` | `PositiveSmallIntegerField` | 0 | « gardées » |
| `plan_faites` | `PositiveSmallIntegerField` | 0 | « gardées faites » |
| `minutes_prevues` | `PositiveIntegerField` | 0 | C23 |
| `minutes_faites` | `PositiveIntegerField` | 0 | C23 |
| `taille_mediane_min` | `PositiveSmallIntegerField` | `null` | s5a |

Contrainte `taches_planjour_uniq` (company, proprietaire, jour). Créée par « Garder ces N », une complétion, ou `vu/`
(seulement si `ReglagesRythme` existe, invariant 29). Conservée 400 jours (A15).

### 2.9 `LignePlanJour` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `plan` | `FK(PlanJour, CASCADE)` | — | `# on_delete: composition` |
| `tache` | `FK(Tache, CASCADE, null)` | `null` | `# on_delete: composition, les compteurs restent sur PlanJour` |
| `activite_id` | `PositiveIntegerField` | `null` | vérifié par `activites_ouvertes_pour(user)` |
| `prevue_au_plan` | `BooleanField` | — | gardée au plan (≠ ajoutée après) |
| `faite` | `BooleanField` | `False` | |
| `reportee` | `BooleanField` | `False` | |
| `essentielle` | `BooleanField` | `False` | ≤ 3 par plan |
| `creneau` | `CharField(12, choices=Creneau)` | `''` | figé à la création (constat C1) · regles manque 6 |
| `rang` | `IntegerField` | `null` | ordre au plan (constat C2) · regles manque 7 |

Contraintes `taches_ligne_uniq` (company, plan, tache) `condition=Q(tache__isnull=False)` · `taches_ligne_act_uniq`
(company, plan, activite_id) `condition=Q(activite_id__isnull=False)` · `taches_ligne_cible_ck` `CheckConstraint(
condition=Q(tache__isnull=False, activite_id__isnull=True) | Q(tache__isnull=True, activite_id__isnull=False))`.
Pas de `titre_fige` (I6).

### 2.10 `ReglagesRythme` (`TenantModel`) — interrupteurs et état typés (C4)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `mode` | `CharField(12, choices=ModeRythme)` | `pousser` | changé par `POST rythme/` SEULEMENT (MAJ-6) |
| `comprendre_mon_rythme` | `BooleanField` | `True` | socle §8 |
| `palier` | `PositiveSmallIntegerField` | `null` (froid : 5 « par défaut ») | 1-12 ; SEULE source de l'objectif, y compris dit (min-18) |
| `palier_source` | `CharField(12)` | `''` | `''` · `calcule` · `accepte` · `dit` |
| `bloc_debut` | `DateField` | `null` | s5a |
| `refus_montee` | `PositiveSmallIntegerField` | 0 | s5a |
| `blocs_a_sauter` | `PositiveSmallIntegerField` | 0 | s5a |
| `echec_n` | `PositiveSmallIntegerField` | 0 | s5a |
| `baisse_refusee` | `BooleanField` | `False` | s5a |
| `essai_restant` | `BooleanField` | `False` | s5a |
| `meilleur_tenu` | `PositiveSmallIntegerField` | `null` | s5a |
| `echec_niveau` | `PositiveSmallIntegerField` | `null` | s5a |
| `ref_taille_min` | `PositiveSmallIntegerField` | `null` | s5a |
| `echec_le` | `DateField` | `null` | s5a |
| `tenir_fixee_le` | `DateField` | `null` | s5a |
| `tenir_silence_jusquau` | `DateField` | `null` | s5a |
| `tenir_reference` | `DecimalField(4,2)` | `null` | s5a |
| `titres_notifications` | `BooleanField` | `False` | socle §2.8 |
| `titres_notifications_demande_le` | `DateTimeField` | `null` | question posée au 1er rappel / Mon iPhone (A17-T4) |
| `titres_calendrier` | `BooleanField` | `True` | s6b |
| `titres_tuile` | `BooleanField` | `True` | s6b |
| `messages_sans_delai` | `BooleanField` | `False` | toast sans délai (spec-7 r3 §6, WCAG 2.2.1) |
| `rappel_avant_bloc_min` | `PositiveSmallIntegerField` | `null` (éteint) | s3 |
| `projet_arret_jours` | `PositiveSmallIntegerField` | 10 | 5-30 · s4 |
| `familles_suggestions` | `JSONField` | `default=` liste des 3 familles allumées (appelable) | s6a, A4 |
| `suggestions_societe` | `BooleanField` | `False` | admin seul |
| `erp_dans_journee` | `BooleanField` | `True` | s6a |
| `pauses_sollicitations` | `JSONField` | `default=list` | types push en pause (I7) |

Contrainte `taches_reglages_uniq` (company, proprietaire). Créée UNIQUEMENT par `creer_taches()` (première tâche, A15,
A17) ; `vu/` ne la crée jamais.

### 2.11 `Preference` (`TenantModel`) — ce qu'il a DIT

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `cle` | `CharField(30, choices=ClePreference)` | — | tableau ci-dessous |
| `valeur` | `JSONField` | — | validée par clé |
| `source` | `CharField(10, choices=SourcePreference)` | `ecran` | s5b |
| `dite_le` | `DateTimeField(auto_now=True)` | — | s5b |

Contrainte `taches_pref_cle_uniq` (company, proprietaire, cle). Clé absente = défaut.

| `cle` | `valeur` | Défaut si absente | Anciens noms retirés |
|---|---|---|---|
| `capacite_jour_min` | entier 30-720 | capacité calculée, sinon 240 | — |
| `jours_travailles` | 7 caractères `0/1`, lun→dim | calendrier de la société | `jours_off` |
| `jours_courts` | liste d'entiers 0-6 | `[]` | `vendredi=120` |
| `conges` | liste `{"du","au"}` (du ≤ au) | `[]` | `conges_du/au` |
| `heure_matin` | `"HH:MM"` ou `"off"` | `"08:30"` | `heure_plan_matin` |
| `relance_jour` | `"HH:MM"` ou `"off"` | `"15:00"` (« Message de 15 h ») | `rappel_journee` |
| `heure_soir` | `"HH:MM"` ou `"off"` | `"18:00"` | `heure_bilan_soir` |
| `heure_limite` | `"HH:MM"` | `"20:00"` (sollicitations seules) | `heure_limite_rappels` |
| `revue_semaine` | entier 0-6, `"auto"`, `"off"` | `"auto"` | `semaine_revue` |
| `essentiel_le_matin` | booléen | `false` | — |
| `note_libre` | liste ≤ 10 chaînes ≤ 200 | `[]` | — |

### 2.12 `IncitationCoach` (`TenantModel`) — journal des sollicitations, dédoublonnage, cartes à réponse

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `jour` | `DateField` | — | socle |
| `type` | `CharField(24, choices=TypeIncitation)` | — | C14 |
| `cle` | `CharField(24)` | `''` | §1 |
| `canal` | `CharField(8, choices=CanalIncitation)` | — | C14 |
| `donnees` | `JSONField` | `default=dict` | des NOMBRES et des ids, jamais un titre ; variables nommées par `textes.md` §3-§4 (`prevues`, `proposees`, `bas`, `haut`, `n_autres`, `restes`, `projet_id`…) |
| `montre_le` | `DateTimeField` | `null` | push envoyé / carte montrée |
| `ouvert_le` | `DateTimeField` | `null` | posé par `POST vu/` sur les push du jour (min-11) |
| `repondu_le` | `DateTimeField` | `null` | |
| `reponse` | `CharField(24, choices=ReponseIncitation)` | `''` | |
| `expire_le` | `DateField` | `null` | cartes J+7 ; `mon_iphone` J+3 (A17-T3) |

Contrainte `taches_incit_uniq` (company, proprietaire, type, jour, cle). Index `taches_incit_jour_idx` (company,
proprietaire, jour). Pas de `texte` : rendu à la lecture (I9). Les « propositions de rythme » SONT ces lignes.

### 2.13 `Rappel` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `tache` | `FK(Tache, CASCADE)` | — | `# on_delete: composition` |
| `ancre` | `CharField(12, choices=AncreRappel)` | `''` | s3 |
| `decalage_jours` | `SmallIntegerField` | 0 | −7…0 |
| `jour` | `DateField` | — | heure murale |
| `heure` | `TimeField` | — | heure murale |
| `statut` | `CharField(12, choices=StatutRappel)` | `en_attente` | s3 |
| `envoye_le` | `DateTimeField` | `null` | s3 |
| `source` | `CharField(12, choices=SourceRappel)` | `manuel` | s3 |

Index `taches_rappel_du_idx` (company, jour, heure) `condition=Q(statut='en_attente')` · `taches_rappel_tache_idx`
(company, tache). Remplace `Tache.rappel_le` (C1).

### 2.14 `JetonAcces` (`TenantModel`) — pas de suppression douce, pas d'admin

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: suit le compte` |
| `usage` | `CharField(10, choices=UsageJeton)` | — | socle §2.5 |
| `prefixe` | `CharField(8)` | — | non secret |
| `jeton_hash` | `CharField(64, unique=True)` | — | SHA-256 hex ; `GLOBAL_NAME_RE` (M6) |
| `libelle` | `CharField(60)` | `blank` | |
| `dernier_usage_le` | `DateTimeField` | `null` | au plus une écriture par minute |
| `revoque_le` | `DateTimeField` | `null` | |

Contrainte `taches_jeton_actif_uniq` (company, proprietaire, usage) `condition=Q(revoque_le__isnull=True)`. Pas
d'expiration. Le raccourci Siri partagé ne contient jamais de jeton (A16-N12).

### 2.15 `GesteAnnulable` (`TenantModel`) — l'UNIQUE mécanisme d'annulation (A7)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `type` | `CharField(24)` | — | §4 |
| `message` | `CharField(200)` | — | texte du toast |
| `operations` | `JSONField` | `default=list` | §4 |
| `annule_le` | `DateTimeField` | `null` | |

Index `taches_geste_date_idx` (company, proprietaire, created_at). Purge à 7 jours.

### 2.16 `VueEnregistree` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `nom` | `CharField(60)` | — | s2 |
| `filtres` | `JSONField` | `default=dict` | clés fermées `q`, `projets`, `etiquettes`, `priorite_min`, `statuts`, `periode`, `echeance`, `tri`, `groupe`, `inclure_faites` ; clé inconnue → 400 nommé |
| `rang` | `IntegerField` | 0 | |

Contrainte `taches_vue_nom_uniq` (company, proprietaire, nom). 30 au plus.

### 2.17 `ModeleProjet` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `nom` | `CharField(120)` | — | s4 |
| `contenu` | `JSONField` | `default=dict` | `{"v":1,"objectif","priorite","sections":[{"nom","decalage_debut","decalage_fin"}],"taches":[{"titre","section_index","priorite","jalon","decalage_jour","decalage_echeance","parent_index","bloquee_par_index","checklist":[],"notes"}]}` ; `notes` seulement si `inclure_notes` |
| `cree_depuis` | `FK(Projet, SET_NULL, null)` | `null` | `# on_delete: le modèle survit au projet` |

Contrainte `taches_modele_nom_uniq` (company, proprietaire, nom).

### 2.18 `RevueProjet` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `projet` | `FK(Projet, CASCADE)` | — | `# on_delete: composition` |
| `semaine` | `DateField` | — | lundi |
| `intention` | `CharField(200)` | `blank` | |
| `prochaine_action` | `FK(Tache, SET_NULL, null)` | `null` | `# on_delete: tâche purgée, revue gardée` |
| `decision` | `CharField(10, choices=DecisionRevue)` | `''` | |
| `focus` | `BooleanField` | `False` | projet de la semaine |
| `faites_semaine` | `PositiveSmallIntegerField` | 0 | |

Contraintes `taches_revueprj_uniq` (company, projet, semaine) · `taches_revue_focus_uniq` (company, proprietaire,
semaine) `condition=Q(focus=True)`.

### 2.19 `SuggestionTache` (`TenantModel`)

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` (= destinataire strict, A4) |
| `famille` | `CharField(24, choices=FamilleSuggestion)` | — | s6a |
| `cle` | `CharField(80)` | — | `devis_accepte:<pk>`… |
| `titre_propose` | `CharField(200)` | — | gabarit SANS nom de client (A4) |
| `content_type` | `FK(ContentType, SET_NULL, null, related_name='+')` | `null` | `# on_delete: suggestion gardée jusqu'à sa purge` |
| `object_id` | `PositiveIntegerField` | `null` | cible liable (chantier → son lead, I16) |
| `lead_ref` | `PositiveIntegerField` | `null` | effacement 09-08 |
| `statut` | `CharField(12, choices=StatutSuggestion)` | `proposee` | |
| `tache` | `FK(Tache, SET_NULL, null)` | `null` | `# on_delete: tâche purgée, trace gardée` |
| `decidee_le` | `DateTimeField` | `null` | |

Contrainte `taches_sugg_cle_uniq` (company, proprietaire, cle). Index `taches_sugg_boite_idx` (company, proprietaire,
statut, created_at). Titres : `textes.md` (gabarits de A4).

### 2.20 `AgendaExterne` (`TenantModel`) — AVANCÉ, dernière vague, migration 0002

| Champ | Type Django | Nul / défaut | Règle · source |
|---|---|---|---|
| `proprietaire` | `FK(AUTH_USER_MODEL, CASCADE)` | — | `# on_delete: données personnelles` |
| `url` | `CharField(500)` | — | https, hôte public ; jamais rendue en entier |
| `libelle` | `CharField(60)` | `blank` | |
| `actif` | `BooleanField` | `True` | |
| `dernier_chargement_le` | `DateTimeField` | `null` | |
| `dernier_etat` | `CharField(20, choices=EtatAgendaExterne)` | `''` | |

Contrainte `taches_agext_uniq` (company, proprietaire). Événements jamais en base : cache borné. Ni flux, ni tuile,
ni assistant.

## 3. Invariants (chacun testable)

1. **À trier** = vivante, `parent` nul, `projet` nul, `triee_le` nul, `statut ∈ {a_faire, en_attente}`.
   `creer_taches()` pose `triee_le = now` dès que la saisie a reconnu un projet, un jour ou « En réserve », par TOUTE
   porte, capture comprise (A1, A14-M6) ; un rappel tapé sans jour pose `jour_prevu` = jour du rappel. Une échéance
   seule ne sort pas d'À trier. `triee_le` est aussi posé par `planifier()`, un déplacement vers un projet, « Garder
   sans projet », terminer, abandonner, supprimer. Projet terminé avec `taches_ouvertes='boite'` : `projet` ET
   `triee_le` remis à nul (T14).
2. Une tâche À trier n'est dans aucune section du jour ni dans Proposé ; elle compte dans `a_trier.boite_reception`.
3. **À revoir** (`a_decider`), premier motif vrai : `reports ≥ reports_tranches + 3` ∧ `jour_prevu ≤ J` ;
   `jour_prevu < J` ; `echeance < J` ; `echeance ∈ ]J, J + 2 jours travaillés]` ∧ (`jour_prevu` nul ∨ `jour_prevu >
   echeance`) ; activité ERP due avant J → `activite_passee`.
4. **Report** : `reports += 1` ssi l'ancien `jour_prevu ≤ J` ET le nouveau est plus tard ou En réserve. Ne comptent
   JAMAIS : futur → futur, avancer, premier jour posé, `decaler`, `instancier`, Alléger (A14-M7), « Les remettre dans
   Proposé » (A14-B1), minuit. `trancher` `aujourdhui`, `garder` ou `jour` pose `reports_tranches = reports`.
5. **Récurrence** : au plus une occurrence ouverte par règle ; la suivante naît à la clôture (terminer, sauter) ;
   rouvrir supprime (`record=False`) la suivante si sa `lock_version` n'a pas bougé.
6. **Prérequis** : un au plus ; jamais soi-même ; même propriétaire ; aucune boucle (≤ 50 maillons, sinon 400).
   Bloquée ⇔ prérequis vivant ∧ `statut ∉ {fait, annule}`.
7. **Sous-tâche** : `parent.parent_id` nul ; même propriétaire ; `projet`/`section` = ceux du parent ; terminer un
   parent termine ses sous-tâches ouvertes ; SUPPRIMER un parent supprime ses sous-tâches dans le même geste (min-20) ;
   jamais dans À trier, une section du jour, Proposé, le flux, la tuile ; comptée 0 au rythme.
8. **Confidentiel hérité** : `est_confidentielle(t) = t.confidentiel ∨ t.projet.confidentiel ∨ t.parent.confidentiel ∨
   t.parent.projet.confidentiel`. Aucun corps servi à l'assistant, au flux, à la tuile, aux notifications ni aux
   suggestions ne contient le titre d'une tâche ou le nom d'un projet confidentiel (test canari, A6).
9. **Même propriétaire** sur tout id reçu : projet, section, parent, bloquee_par, étiquettes, éléments de check-list (et
   le `tache` d'un `POST checklist/`), le `projet` d'un `POST sections/`, ids de réordonnancement et de lot, lignes de
   plan (tâches ET activités via `activites_ouvertes_pour`), triage, rappels, récurrences, propositions, revue,
   prochaine action, projet cible, modèle, suggestion, geste, jeton, vue, activité à lier, `?projet=` de l'agenda ;
   sinon 404 (ou « Projet inexistant. » au champ), rien d'écrit. Exception : un id étranger dans `inclure`/`exclure`
   de `journee/proposition/` est IGNORÉ (lecture). Test de balayage.
10. **Préfiltre de la journée** (`taches_de_la_journee`) : vivante, `parent` nul, non bloquée, projet `actif` ou
    (projet nul ∧ `triee_le` non nul), et (`statut ∈ {a_faire, en_attente}` ∧ ¬`quelque_jour`, ou `fait` ∧ `fait_le`
    local = J). Le même préfiltre sert l'écran, la pastille, le flux, la tuile.
11. **Pastille** `n` = éléments OUVERTS et GARDÉS d'`essentiel` + `journee` + `ce_soir` (tâches et activités ERP),
    plafonné à 99 ; JAMAIS Proposé (A16-N5), ni À revoir, En attente, À trier, obligations. Peut valoir 0.
12. **Flux et tuile** : tâches `a_faire` du préfiltre ; jamais faites, À revoir, en attente, À trier, En réserve ;
    jamais de notes ; activités ERP comptées sans titre (IR15).
13. **`progression.faites` = `compte_du_jour`** (C8) ; `progression.prevues` = `faites` + éléments ouverts gardés
    (Essentiel, Prévu, Ce soir).
14. **Heure murale** : dates et heures stockées locales, jamais d'instant UTC pré-calculé.
15. `jour_prevu`, `heure_debut`, `moment` ne changent que par `services.planifier()` (PATCH les refuse), sauf
    `annuler_geste()` qui restaure l'état d'avant (min-17) ; `heure_debut` exige `jour_prevu` ; `moment` dérivé.
16. `statut = fait` ⇔ `fait_le` non nul ; `annule` ⇔ `annule_le` non nul ; rouvrir les remet à nul.
17. Un projet ne passe `termine` que par `terminer` (projet ou revue, un seul service) ; `issue` obligatoire.
18. ≤ 3 lignes `essentielle` par plan ; revalider n'ajoute que des lignes ; Alléger retire les lignes des tâches
    renvoyées, pose `allege_le` ; Proposé reste replié et vide jusqu'au lendemain.
19. Rappels : ≤ 5 `en_attente` par tâche, ≤ 100 par utilisateur ; tâche close, abandonnée ou supprimée → `annule`.
20. Un seul jeton actif par usage ; `capture` ne fait que créer pour son propriétaire, dans `jeton.company` ; jamais le
    jeton d'agenda de `reporting`.
21. Annuler ne lit jamais un état envoyé par le navigateur ; seuls les champs de la liste blanche §4 sont restaurés.
22. ≤ 3 sollicitations par jour (rappels et push de test hors compte) ; aucune hors fenêtre, après `heure_limite`, en
    congé, un jour non travaillé, pour un compte inactif ; SAUTÉE, jamais différée.
23. Lien ERP : cible ∈ `CibleLiable` ET visible (sélecteur de l'app cible) ; libellé servi vide hors `ok` (« Lead
    effacé » si `efface`) ; la tâche nocturne revérifie les liens des tâches ouvertes.
24. Objectif entre 1 et 12 ; une baisse n'est jamais imposée ; un cran au plus par proposition.
25. Un seul projet de la semaine par propriétaire et par semaine.
26. Aucun objet `taches` dans la corbeille de l'ERP, la recherche globale, `record_targets`, `_traces_du_compte`.
27. Supprimer un projet supprime ses tâches vivantes dans le même geste ; le restaurer les restaure ; une tâche
    restaurée seule dont le projet reste supprimé revient dans À trier (N7).
28. **Module invisible** jusqu'à la dernière vague : `taches_voir` déclaré, accordé à AUCUN rôle ; aucune entrée de
    navigation ni `appSku` (A17, MAJ-10).
29. `ReglagesRythme` n'existe que pour un compte qui a créé au moins une tâche ; sans elle : aucune sollicitation,
    aucune suggestion (IR14), `vu/` n'écrit rien.
30. Une activité ERP liée garde `activite_origine` et n'est PAS close ; seule la conversion d'un à-faire personnel
    clôt sa source (`records.services.cloturer_a_faire_personnel`).
31. Hors ligne : toute op envoyée porte `proprietaire_attendu` ; une op d'un autre compte est refusée (409
    `autre_compte`) et jetée.
32. **Ordre d'affichage d'une section** (M13) : `rang_jour` s'il est posé, sinon `cle_tri` ; `reordonner` numérote
    toute la section. Dans un projet : `rang_projet` puis `id`.

## 4. Opérations annulables et liste blanche

Types : `creation`, `modification`, `planification`, `deplacement`, `terminaison`, `reouverture`, `suppression`,
`restauration`, `conversion`, `lien_activite`, `lot`, `decalage`, `instanciation`, `plan_du_jour`, `bilan_du_soir`,
`allegement`, `retour_absence`, `decision`, `rappel`, `preference`, `rythme`, `suggestion`, `revue`, `essentiel`.
Opérations : `{"op":"champ","objet","id","champ","avant","apres"}` · `{"op":"creation","objet","id"}` (inverse :
`soft_delete(record=False)` ou suppression dure) · `{"op":"suppression_douce","objet","id"}` (inverse `restore()`) ·
`{"op":"suppression_dure","objet","id","valeurs":{…}}` (inverse : recréation au même `pk`). Conflit = valeur courante
≠ `apres` ou objet disparu → `conflits`, inchangé. Toute FK restaurée est revérifiée « même propriétaire ».

| `objet` | Champs restaurables |
|---|---|
| `tache` | titre, notes, statut, fait_le, annule_le, priorite, jour_prevu, moment, heure_debut, echeance, echeance_heure, quelque_jour, estimation_minutes, projet, section, reports, reports_tranches, premier_jour_prevu, rang_projet, rang_jour, triee_le, en_attente_de, bloquee_par, jalon, confidentiel, `lien` (revalidé par `resolve_target`) |
| `projet` | nom, objectif, icone, couleur, priorite, statut, statut_depuis, date_debut, echeance, termine_le, issue, bilan, risque, domaine, planification_le, rang, confidentiel, affichage |
| `section` | nom, rang, date_debut, date_fin |
| `element_checklist` | libelle, fait, fait_le, rang |
| `etiquette_tache`, `ligne_plan_jour`, `revue_projet` | création / suppression |
| `plan_jour` | planifie_le, cloture_le, allege_le, reflexion, objectif_du_jour |
| `rappel` | statut, jour, heure |
| `preference` | valeur (création / suppression) |
| `reglages_rythme` | mode, palier, palier_source, bloc_debut, refus_montee, blocs_a_sauter, baisse_refusee, essai_restant, tenir_reference, tenir_fixee_le, tenir_silence_jusquau, pauses_sollicitations |
| `suggestion_tache` | statut, tache, decidee_le |
| `incitation_coach` | reponse, repondu_le |

Jamais : `proprietaire`, `company`, `parent`, `content_type`/`object_id` bruts, `activite_origine`, `client_id`,
`source`, `lock_version`, `JetonAcces`, « Tout effacer ». Sans `geste_id` (pas d'Annuler) : jetons, `vu/`,
`tout-effacer/`, `PATCH reglages/`, `agenda-externe/`, réordonnancements, clôture d'une activité ERP.

## 5. Fonctions uniques imposées

| Fonction | Fichier | Contrat |
|---|---|---|
| `taches_de(user)` (+ `projets_de`, `sections_de`, `etiquettes_de`, `rappels_de`, `gestes_de`…) | `selectors/base.py` | `company=user.company` ET `proprietaire=user` ; derrière TOUTE lecture |
| `taches_de_la_journee(user, jour)` · `compter_journee(user, jour)` | `selectors/journee.py` | invariants 10, 11 ; `compter_journee` sert `badge/`, `aujourdhui/`, `notify(badge=n)` |
| `est_confidentielle()` · `nom_pour(obj, usage)` | `confidentialite.py` | inv. 8 ; `usage ∈ {ecran, assistant, flux, tuile, notification}` (regles §8) |
| `creer_taches(user, lignes, *, source, porte, client_id=None, lien=None, parent=None, activite=None)` | `services/creation.py` | seul créateur ; idempotence par lecture `all_objects` puis `IntegrityError` relue ; crée `ReglagesRythme` ; pose `triee_le` ; déclenche les révélations à leur événement (I14) ; rend `geste_id` |
| `planifier(tache, *, jour_prevu, moment, heure_debut, quelque_jour, compter_report=True, version=None)` | `services/planification.py` | seul chemin d'un jour ; `select_for_update()` ; si `version` : `version_envoyee` comparée sous verrou, `ConflitVersion(actuel=TACHE)` ; `reports` par `F()` |
| `enregistrer_geste()` · `annuler_geste()` | `services/gestes.py` | §4 |
| `JetonAccesAuthentication(usage)` | `auth_jeton.py` | hache, trouve le jeton actif de CET usage, vérifie compte actif interne, `user_can_operate(user, jeton.company_id)`, `taches_voir`, module actif ; pose `user.company = jeton.company` en mémoire (MAJ-4) |
| `ThrottleCapture` / `ThrottleFlux` / `ThrottleTuile` | `throttles.py` | patron `CalendrierIcsThrottle` (`reporting/calendar.py:77`) : 60/h + 200/j · 60/h · 120/h |
| `jours_travailles_de(user, du, au)` · `prochain_jour_travaille(user, jour)` | `selectors/base.py` | `jours_ouvres_entre` ∩ `jours_travailles` − `conges` |
| `filtrer_q(qs, q, *, assistant=False)` | `selectors/base.py` | mots ET, `icontains` sans accents sur titre, notes, projet, étiquettes ; `assistant=True` : ni notes, ni tâches confidentielles (min-12, IR17) |
| `url_de_cible()` · `libelle_de_cible()` · `cible_visible(user, cible, id)` | `selectors/erp.py` | `liens_cibles.json` ; visibilité par `leads_visibles` (crm), `scope_client_queryset` (clients), `ventes/selectors_libelles.py:35-60` (devis) |
| `fournisseur_dsr_taches` | `dsr.py` (`register_dsr_provider('taches', export=…, erase=…)` dans `apps.py`) | vide `lien_libelle`, pose `efface`, supprime les `SuggestionTache` du `lead_ref` ; export = `mes-donnees/` |
| `neglige(projets, faites_14j)` · `tout_fait(projet)` | `moteur/sante.py` | C18 ; `tout_fait` ⇔ 0 ouverte ∧ ≥ 1 faite |

Abonnés (`receivers.py`, `@abonne_best_effort`, connectés dans `apps.py`) aux signaux existants `devis_accepted`,
`devis_acceptation_annulee`, `chantier_receptionne`, `chantier_annule`, `visite_validee`, `lead_erased` : aucun signal
nouveau (`core/event_coverage.py`).
Étrangers, tâches séparées (A8) : `records.selectors.activites_ouvertes_pour`, `nb_a_faire_personnels`,
`peut_cloturer_activites` ; `records.services.cloturer_a_faire_personnel`, `rouvrir_a_faire_personnel` (securite).

## 6. Migrations et découpage en lanes (MAJ-10, verif-reference §6)

1. `0001_initial.py` — les 20 modèles moins `AgendaExterne` ; dépendances `authentication` (dernière),
   `contenttypes 0002`, `records 0014_attachment_file_key_index` (reprendre la dernière au build).
2. `0002_agendaexterne.py` — dernière vague. 3. Ajouts ultérieurs `0003+`, une lane à la fois.
4. Étranger (parametres) : `notifications/migrations/0079_eventtype_taches.py` (3 `AlterField`, `max_length=40`).

Paquets (les gardes lisent `models/`, `services/`, `views/`, `serializers/`) :
- **L0 socle, seule, d'abord** : `models/{projets,taches,journee,rythme,presence,erp,gestes}.py` + 0001, `choix.py`,
  `confidentialite.py`, `selectors/base.py`, `services/{planification,gestes}.py`, `serializers/formes.py` (ITEM,
  TACHE, TACHE_ECRITE, PROJET, PROPOSITION, LIEN), `urls.py` complet, `views/*.py` vides (501), `apps.py`,
  `platform.py` (manifeste, `agent_actions_module`, `record_targets: []`), `sweeps.py`, `contract_samples/` ; front
  `module.config.jsx` SANS navigation + pages vides + `features/taches/api/client.js` + `ui/LigneTache.jsx`. Droit
  déclaré dans `permissions_registre.py` (tâche étrangère), accordé à aucun rôle.
- **L1 saisie** : `saisie.py`, `moteur/recurrence.py`, `services/creation.py`, `views/saisie.py`, `serializers/saisie.py`.
- **L2 journée** : `moteur/classement.py`, `selectors/journee.py`, `views/journee.py`, `views/agenda.py`.
- **L3 projets** : `moteur/{sante,decalage}.py`, `views/projets.py`.
- **L4 rythme** : `moteur/{rythme,sollicitations,gabarits}.py`, `nocturne.py`, `views/rythme.py`, `views/reglages.py`.
- **L5 présence** (@after L2, L4) : `auth_jeton.py`, `throttles.py`, `moteur/flux.py`, `balayage.py`,
  `views/presence.py` ; front `useBadgeTaches.js`, `captureQueue.js`, `iphone/*`.
- **L6 ERP** (@after L1) : `selectors/erp.py`, `services/erp.py`, `receivers.py`, `dsr.py`, `views/erp.py` ; puis 0002.
- **L7 assistant** (@after L1-L4) : `agent_actions.py`, `features/taches/cartes/*`.
- **Dernière vague** : octroi de `taches_voir` aux rôles internes, navigation, `appSkus.js`. Régénérés UNE fois par
  l'orchestrateur après le dernier fold : `docs/openapi-schema.yml`, `docs/rbac-endpoint-inventory.md`,
  `frontend/src/test/fixtures/contractSamples.js`, `docs/CODEMAP.md`.

## 7. Modules de code PUR (algorithmes : `regles.md`)

| Fichier | Fonctions |
|---|---|
| `saisie.py` | `normaliser`, `cle_nom`, `analyser(texte, maintenant, projets, etiquettes, ignorer, porte)` (porte `capture` : jour, heure, moment, échéance, priorité, durée, projet EXISTANT, « projet <nom> » en tête), `decouper_collage(textes, …)` (projet par collage), `decouper_plan(texte)` |
| `moteur/recurrence.py` | `premiere_occurrence`, `prochaine_occurrence`, `libelle_regle` |
| `moteur/classement.py` | `placer`, `cle_tri`, `explication`, `capacite`, `proposer_plan` |
| `moteur/sante.py` | `avancement`, `burnup`, `sans_prochaine_action`, `a_l_arret`, `echeance_menacee`, `neglige`, `tout_fait`, `constat_projets` |
| `moteur/decalage.py` | `decaler`, `instancier`, `figer_modele` |
| `moteur/rythme.py` | `compte_du_jour`, `statut_jour`, `journee_reussie`, `palier_initial`, `plafonner_jours`, `evaluer_bloc`, `clore_bloc`, `objectif_dit`, `reference_tenir`, `bande_tenir`, `derive_tenir`, `objectif_affiche` (rend aussi la zone en `tenir`), `basculer`, `arrondir`, `constats`, `retour_absence`, `semaine_courte` |
| `moteur/sollicitations.py` | `due`, `choisir_relance`, `etat_decroissance`, `variante`, `plafond_atteint` |
| `moteur/gabarits.py` | `texte(type, cle, donnees, variante, nom_pour)` — textes de `textes.md` §3-§4, aucun ici |
| `moteur/flux.py` | `evenements_flux(…)`, `tuile_pure(…)` (`top`, `reste`, `prochaine_echeance`) |

## 8. Purges et rétention (tâche `taches.nocturne`, A15)

`PlanJour` 400 jours · `LignePlanJour` 90 jours · `IncitationCoach` 90 jours · `Rappel` clos 30 jours ·
`GesteAnnulable` 7 jours · `SuggestionTache` visible 7 jours, purgée à 30 · Tâche ou projet supprimé : 30 jours puis
suppression dure · « Comprendre mon rythme » coupé : cartes `constat`, `proposition_palier`, `derive_tenir`,
`garde_taille` supprimées ; `tenir_*`, `ref_taille_min`, `meilleur_tenu`, `echec_*` remis à nul ; champs de rythme de
`PlanJour` (`statut_jour`, `compte_rythme`, `micro_comptees`, `taille_mediane_min`) effacés ; capacité habituelle et
signal (d) d'échéance menacée tus. Export et « Tout effacer » couvrent les 20 modèles. Le texte de Réglages → Vie
privée (A9) est dans `textes.md` §6.

## Décisions de l'intégrateur

- **I1** (rév. 2) Palette = les 10 clés de spec-8 (A15) ; défaut d'étiquette `ciel`.
- **I2** `nom_cle` normalisé sur Projet, Section, Etiquette : une clé pour l'analyseur ET l'unicité.
- **I3** `titre` Char(280) partout. **I4** `Tache.content_type` SET_NULL : une tâche n'est jamais supprimée par son lien.
- **I5** `PlanJour.app_ouverte_le` + `POST vu/` (trou T12), sans écriture dans un GET.
- **I6** Pas de `titre_fige` ; `LignePlanJour.tache` CASCADE.
- **I7** `pauses_sollicitations` : la carte « Le réactiver ? » doit écrire quelque part.
- **I8** (rév. 2) `ReglagesRythme` née à la première tâche seulement (A15, A17) ; c'est la condition d'émission.
- **I9** `IncitationCoach` sans `texte`. **I10** Un agenda externe par utilisateur.
- **I11** (rév. 2) Rétentions fixées par A15 ; plus rien « à valider ».
- **I12** Section technique `a_decider` gardée, montrée « À revoir ».
- **I13** (rév. 2) Constats acceptés : C1, C2 → `essentiel_le_matin` ; C3 → `jours_courts` ; C4, C6, C8 → la carte
  acceptée (`reponse='oui'`, `donnees`) est lue par le moteur jusqu'au constat suivant du même code ; C7 ouvre À revoir.
- **I14** (rév. 2) Révélations serveur créées à leur événement (`mon_iphone` au 1er collage créé, `ranger_copilote` à
  À trier ≥ 5, `planifier_projet` au 1er projet, `revue` par la nocturne en fin de 1re semaine) ; astuces de geste au
  navigateur (A15).
- **I15** Restaurer un projet restaure ses tâches supprimées avec lui ; tâche seule → À trier.
- **I16** Suggestion de chantier liée au lead du chantier (A3).
- **I17** (rév. 2) Objectif dit : `palier` + `palier_source='dit'` seulement ; la clé `Preference.objectif_dit` est
  retirée (min-18, une source).
- **I18** (rév. 2) Décision `demain` retirée de l'énum : spec-7 r3 « Demain, jamais un bouton de report » ; le bilan
  dit « Reporter à lun. 23 ».

## Ce que les specs demandaient et que je n'ai PAS repris

- `Tache.rappel_le` → `Rappel` (C1) ; `heure_prevue` → `heure_debut` (C10) ; `Tache.assigne_a`, statut `en_cours`
  (design-s1, hors socle).
- `Annulation`, `decaler/annuler`, `GesteAnnulable.avant` à `lock_version_apres` → opérations par champ (C2, A7).
- design-s1 : `objectif_nb_jour`, `objectif_auto`, `heure_plan`, `heure_cloture`, `conges_du/au`,
  `max_incitations_jour`, `jeton_capture_hash` ; `PlanJour.nb_*`, `nb_reportees` (C23) ; `IncitationCoach.texte`,
  canal `assistant` ; `records.Tag` ; `record_targets`, `searchable_models`, restaurateur de corbeille ; `ma_file` et
  flux iCal d'équipe ; modes `progresser/maintenir` (C42).
- Clés `Preference` de s5b → noms s5a (C4, C27) ; `mode_rythme`, `titres_notifications`, `comprendre_mon_rythme`,
  `rappel_avant_bloc_min`, `projet_arret_jours` en Preference → `ReglagesRythme` ; `objectif_dit` (I17) ; `texte_dit`.
- `JetonAcces.empreinte` → `jeton_hash` (M6) ; `cree_le` = `created_at`.
- `Projet.planifie_le` → `planification_le` ; `visibilite = partage`.
- `SuggestionTache.destinataire` → `proprietaire` ; `lien_libelle` et `{client}` dans les titres (A4, M5) ; cibles
  facture, chantier, ticket et les 9 autres (A3).
- `LignePlanJour.titre_fige` (I6) ; `taches_tache_cible_idx`.
- Seuil 6/10 et « arrondi inférieur » → 5/10 et demie vers le bas (A2) ; journée type à chaque baisse (verif-5a c. 7).
- Capture « sans analyse, toujours dans la Boîte » → A1, A14-M6 ; « En réserve » non lu par la capture (A15).
- Valeurs `corbeille` (s2 : type de geste, action de lot) → `suppression` / `supprimer` ; décision `demain` (I18).
- Pastille « + Proposé » (spec-7 r2, ma rév. 1) → gardées seules (A16-N5).
- Visites et poses « à leur heure » (A14-M8) → bande « Toute la journée », date seule (A16-N4).
- Gabarits de phrases (ma rév. 1 §8) → `textes.md` §3-§4, source unique des mots.

## Écarts avec regles.md / textes.md à corriger là-bas

- `regles.md` §4.1 et §4.9 : la pastille compte encore Proposé → gardées seules (A16-N5) ; la clé `cartes_coach` →
  `carte_du_moment` (un objet, ordre spec-7 r3 §4 : retour > [brouillon] > bilan d'hier > garder > alléger > faire le
  bilan > rythme > révélation > [astuce]).
- `regles.md` §4.6 : choix `demain` et 400 sur les `reportee_3_fois` → `prochain_jour_ouvre` (« Tout reporter ») ; les
  reportées 3 fois non nommées restent en place, rendues dans `a_trancher` (tour 3, mineur).
- `regles.md` IR12, manque 14 : `Preference.objectif_dit` n'existe plus (I17) ; message d'erreur sur `objectif` seul.
- `regles.md` manque 15 : une échéance seule laisse la capture dans À trier (`dans:"a_trier"`, invariant 1).
- `regles.md` §1.10 : `projet_commun` → `projets_communs[]`, un par collage (api.md §4).
- `textes.md` §4.2 : carte `premier` → boutons [Oui, {type}] (`oui`) [Garder 5] (`garder`).
- `textes.md` §2.15 : toast 8 s (spec-7 r3 §6), pas 6 s ; §2.17 : ordre de la carte du moment de spec-7 r3 §4.

## Révision 2 : ce qui a changé

1. Primauté jusqu'à A17 et spec-7 r3 ; mots dans `textes.md`, algorithmes dans `regles.md` ; tous les modèles en tableau.
2. Palette à 10 clés, défaut d'étiquette `ciel` (A15, MAJ-1).
3. Rétention `PlanJour` 400 jours (A15, MAJ-2).
4. `ReglagesRythme` née à la première tâche ; `vu/` n'écrit rien sans elle (MAJ-3).
5. Décision `garder` ajoutée, `demain` retirée ; motif `activite_passee` ; familles d'obligation fermées.
6. Pastille = gardées seules (N5) ; Proposé vide et replié après Alléger (`PlanJour.allege_le`, N6).
7. `LignePlanJour.creneau` et `rang` ; `ReglagesRythme.titres_notifications_demande_le` (T4), `messages_sans_delai`.
8. `Preference.objectif_dit` retirée (une source) ; `premier` proposé, jamais imposé.
9. Jeton : société du jeton après `user_can_operate` (MAJ-4) ; débits flux/tuile ; fournisseur DSR (MAJ-7).
10. `CheckConstraint(condition=…)`, `default=list`, `nom_cle` dans le seul `save()`, verrous des compteurs.
11. Suppression d'un parent et d'un projet restaurables en un geste ; lien d'une activité ERP (`activite_origine`).
12. Invariants 27-32 : projet supprimé, module invisible, condition d'émission, lien d'activité, hors ligne, ordre.
13. Lanes L0-L7 et dernière vague ; fichiers régénérés une fois par l'orchestrateur.
14. Gabarits déplacés dans `textes.md` ; `tuile_pure`, `decouper_plan`, `semaine_courte`, `tout_fait` nommés.
