# Audit X3 « parametres » — dossier d'évaluation (L2, 08/10/2026)

Unité **X3** (paramètres, notifications, automatisation, onboarding, bus d'événements), groupe **APAR**, niveau **L2**. Claim : branche `audit-X3`.

Méthode : `docs/audits/METHODE.md` v2. Sorties brutes (lanes, verdicts, sondes) : scratchpad de la session — ici la
commande, le SHA et un extrait court seulement.

## 1. Charte (phase 1)
SHA lu : origin/main (branche audit-X3). Pile locale : checkout `C:\dev\taqinor-os` sur un origin/main récent (dire son SHA :
`git -C C:\dev\taqinor-os log -1 --oneline`, et `git diff --stat <ce SHA> HEAD -- <fichiers sondés>` avant toute sonde).

## Système et frontière
X3 possède : `backend/django_core/apps/parametres/**` (≈ 30 000 l. hors tests/migrations), `apps/notifications/**` (≈ 16 000),
`apps/automation/**` (≈ 9 600), `apps/onboarding/**`, `backend/django_core/core/events/**` (paquet, 1 622 l.) et
`core/event_coverage.py` (surfaces append-only), `frontend/src/pages/parametres/**` (≈ 20 000), `features/parametres/**`,
`features/notifications/**`, `pages/onboarding/**`, `features/onboarding/**`, `pages/approbations/**`,
`frontend/src/api/{parametresApi,notificationsApi,automationApi}.js`. `docs/ownership.yml` PRIME
(`python scripts/check_ownership.py --owner-of`). Lu : chaque LECTEUR d'un réglage dans les autres apps (grep). Apps parquées hors périmètre.

## Objet
Contrat X3 : un réglage est lu UNE seule fois (un seul lecteur canonique, pas de repli codé en dur divergent ailleurs) ; changer
un réglage est tracé (avant/après, qui) et réservé au bon rôle ; un document envoyé/signé garde sa version figée (CGV, mentions,
taux) ; aucun texte client codé en dur hors des gabarits ; un message WhatsApp/e-mail = ce que l'étape promet, jamais envoyé
à un contact en opposition (`ne_plus_contacter`, loi 09-08) ni hors des heures ; chaque événement du bus a un émetteur ET un abonné
vivants (sinon listé et justifié dans `ALLOWED_UNCONSUMED`) ; les automatisations n'écrivent que des champs autorisés, dans la
société, et les webhooks publics sont authentifiés et limités. Personas : Administrateur (réglages), Commercial, Technicien
responsable ; société 43 en second locataire.

## NE PAS REFAIRE
Tâches ouvertes déjà déposées dans `docs/plans/PLAN_AUDIT_PARAMETRES.md` (ASEC, ADOC, AGNR…), SPL (registres partagés), NT*
(new_tasks_plan), ERR-* : CITER, jamais redéposer.

## Critères retenus
C2, C3, C4, C5, C6, C7, C9, C10, C11, C13. (C1 seulement via textes/taux imprimés ; C14 : X6.)

## Étapes (identifiants stables)
- P1 réglages société : P1.1 profil société (ICE, RIB, logos, mentions), P1.2 taxes/TVA/unités/conditions de paiement,
  P1.3 tarifs ONEE/82-21/tarifs officiels, P1.4 statuts et étapes configurables (STAGES.py, règle #2), P1.5 feature flags/licence.
- P2 textes : P2.1 gabarits documents/e-mails/messages, P2.2 i18n/traductions, P2.3 CGV et version figée à l'envoi.
- P3 notifications : P3.1 création/routage/préférences, P3.2 heures calmes/fériés, P3.3 WhatsApp BSP/e-mail sortants, P3.4
  jetons d'approbation, P3.5 digests et balayages.
- P4 automatisation : P4.1 moteur/règles/actions (set_field), P4.2 déclencheurs (bus, webhooks entrants publics), P4.3 simulation.
- P5 bus d'événements : P5.1 signaux déclarés, émetteurs, abonnés, `ALLOWED_UNCONSUMED`, P5.2 abonnés qui supposent un ordre ou
  avalent une erreur dans la transaction de l'émetteur.
- P6 onboarding et approbations (écrans + API).
- P7 écrans paramètres : erreurs sous le champ, pagination, rôle.

## Scénarios H×H
- Un Commercial tente de modifier un réglage société / une règle d'automatisation ⇒ refusé (403/404) et rien n'est écrit.
- Un réglage (TVA, mention, CGV) modifié après l'envoi d'un devis ⇒ le PDF/la page du devis envoyé ne change pas.
- Une règle d'automatisation `set_field` ⇒ n'écrit jamais un champ hors liste blanche ni un objet d'une autre société.
- Un contact en opposition ⇒ aucun message sortant (tous canaux) ; heures calmes respectées (Africa/Casablanca).
- Chaque signal de `core/events` : émetteur ET abonné vivants (grep), sinon justifié.

## Détecteurs (scout)
`python scripts/check_parked_apps.py` ; `python scripts/check_api_shapes.py` ; `python scripts/check_api_contract.py` ;
`python scripts/check_ecrans_atteignables.py` ; `python scripts/rapport_backend_sombre.py` ; `python scripts/check_services_appeles.py` ;
`python scripts/check_stages.py` ; `python scripts/check_tests_source_regex.py` ; `cd backend/django_core && lint-imports` ;
couverture d'événements : exécuter la vérification de `core/event_coverage.py` (lire comment elle est appelée par les tests ;
sinon script python AST/grep : `.send(`/`send_robust(` vs `.connect(`/`@receiver` par signal) ;
grep des envois sortants (`send_mail`, `EmailMessage`, `whatsapp`, `send_template`) et de leurs gardes `ne_plus_contacter`.

## 2. Plan des lanes et coût (phase 3)
| Ronde | Lanes (modèle / effort) |
|---|---|
| Scouts | détecteurs, dédoublonnage (haiku / low) |
| R2 jugement | LPAR1 réglages société · LPAR2 textes/gabarits/i18n (sonnet/high) · LPAR3 tarifs/rétention/tâches (sonnet/medium) · LNOTIF notifications · LAUTO automatisation · LBUS bus d'événements + onboarding (opus/high) · LFRONT écrans (sonnet/medium) |
| R3 porte empirique | VA (opus/high : LNOTIF, LAUTO, LBUS) · VB (opus/high : LPAR1-3) · VC (sonnet/high : LFRONT) — jamais l'auteur ; sondes en transaction ANNULÉE |
| Tâches | 1 rédacteur (opus/high) |
| Critique | 1 critique de complétude (opus/high) — aucun appel Fable |

14 agents, ≈ 3,7 M jetons de sous-agents.

## 3. Manifeste de couverture (phase 4)
**Détecteurs** (scout) : 11/11 exécutés, exit 0 — `check_parked_apps`, `check_api_shapes`, `check_api_contract`, `check_ecrans_atteignables`,
`rapport_backend_sombre`, `check_services_appeles`, `check_stages`, `check_tests_source_regex`, `lint-imports`, couverture d'événements,
grep des envois sortants. **Réserve :** le comptage du scout « 44 signaux sans abonné » (regex) est FAUX — il range `devis_accepted`
et `lead_created`, qui ont des abonnés vivants, parmi les orphelins ; il n'a servi à aucun constat. La table émetteur/abonné qui
fait foi est celle de la lane LBUS, vérifiée par VA (constats C-APAR-011, 024, 036, 037).

**Fichiers lus / non lus par lane** (extrait ; liste complète au scratchpad) :
- **LAUTO** :
  LUS en entier : `apps/automation/actions.py` (1-610), `engine.py` (1-671), `signals.py` (1-320), `public_views.py`
  (1-154), `public_urls.py`, `simulation.py` (1-257), `list_sources.py` (1-127), `beat_tasks.py` (1-399),
  `templates.py` (1-266), `views.py` (1-619), `selectors.py`, `urls.py`, `test_aud822_beat_idempotence.py` (1-171).
  LUS par plages : `serializers.py` 1-200 (+ grep 200-315 et diff ASEC30) ; `services.py` 148-230, 317-451 ;
  `models.py` 36-48, 89-94, 129-149, 234-250 (grep), 444-472 (grep), 770-860 ; `apps.py` (fin) ; `tests.py`
  1175-1290 ; `test_aud836_fuseau_casablanca.py` 1-30. Hors surface lus pour les coutures : `reporting/approbations.py`
  340-440, 566-640 ; `core/ui_extensions_api.py` 1-140 ; `core/ui_extensions.py` 88-110 ; `crm/activity.py` 12-42,
- **LBUS** :
  LUS (intégralement ou plages) :
  - `backend/django_core/core/events/__init__.py` 1-431 (intégral) ; liste des `Signal()` de tous les modules
  `core/events/{acquisition,calepinage,chantiers,devis,facturation,lead,parked,sav,stock}.py` (grep, lignes de déclaration).
  - `backend/django_core/core/event_coverage.py` 1-547 (intégral).
  - `backend/django_core/apps/onboarding/` : receivers.py, apps.py, models.py, services.py (intégraux), selectors.py 1-120,
  views.py (grep structure), urls.py ; migrations listées (non lues).
  - Récepteurs : apps/automation/signals.py 25-64, 200-320 ; apps/automation/engine.py 130-150, 226-298 ;
- **LFRONT** :
  LUS (plages) : `ParametresEntreprise.jsx` 60-90, 250-290, 465-495, 636-650, 740-860, 955-990 ; `features/parametres/store/parametresSlice.js` 10-30, 85-105 ; `features/parametres/module.config.jsx` 1-80 ; `AutomatisationsSection.jsx` 75-135, 195-345 ; `ApiWebhooksSection.jsx` 580-632 ; `ChecklistSection.jsx` 68-100 ; `NotificationsAdminSection.jsx` 120-200 (+ grep des catch) ; `pages/approbations/ApprobationsPage.jsx` 265-300, 640-690 ; `peComponents.jsx` 130-175 ; `DonneesSection.jsx` 440-448, 708-714 ; `EquipeSection.jsx` 112-126 ; `KpiAlertesPage.jsx` 76-86 ; `api/resource.js`, `lib/frenchError.js`, `lib/apiError.js` (en-tête), `hooks/useHasPermission.js` 40-75. Backend lu pour la preuve croisée : `core/pagination.py`, `apps/parametres/views_profile.py` 145-200, `apps/automation/serializers.py` 50-135, `apps/automation/views.py` 95-160, `apps/parametres/models_company.py` 208-230.
  Grep transverses sur toute la surface : `window.confirm|alert|prompt`, `type="number"`, `.results ??`, `catch { /* */ }`, `response?.data?.detail ??`, `page_size`.
  NON LUS (ou seulement par grep) : `TarificationSection.jsx` (1 342 l.), `DonneesSection.jsx` hors plages ci-dessus, `ApiWebhooksSection.jsx` 1-579 et 633-867, `AvanceSection.jsx`, `ConfidentialiteSection.jsx`, `SecuriteCompteSection.jsx`, `CadenceRelanceEditor.jsx`, `DevisSection.jsx`, `SocieteSection.jsx`, `LeadsSection.jsx`, `ReferentielsSection.jsx`, `ApplicationsSection.jsx`, `ExportsPlanifiesSection.jsx`, `KitsSection.jsx`, `features/parametres/CustomObjectRecordsPage.jsx` et `ObjetsPersonnalisesPage.jsx` (grep confirm seulement), `features/notifications/AnnoncesPage.jsx`, `features/onboarding/**`, `pages/onboarding/DemarrageWizard.jsx` (grep), `api/{parametresApi,notificationsApi,automationApi}.js` (parametresApi 1-10 seulement), reste d'`ApprobationsPage.jsx`. Aucun test exécuté (vitest non lancé : lane de lecture).
- **LNOTIF** :
  LUS (plages) — apps/notifications : `whatsapp_bsp.py` (entier), `views_whatsapp_bsp.py` (entier),
  `approval_tokens.py` (entier), `services.py` 1-475, 476-700, 717-770, 860-1110, 1185-1330, 1340-1419,
  `sweeps.py` 1-240, 296-320, 640-887, `tasks.py` (entier), `digests.py` 35-192, `signals.py` 40-125, 340-445,
  576-644 (index), `views.py` 47-130 (index), 167-250, 394-636, `serializers.py` 60-117, `selectors.py` 90-160,
  `models.py` 198-250, 620-660 (partiel), `urls.py` (grep).
  Hors surface lus pour preuve : reporting/approbations.py 151-156, 346-440, 566-635 ; reporting/tests_approbations.py
  236-248 ; automation/services.py 365-385 ; automation/views.py 255-275 ; automation/models.py (grep) ;
- **LPAR1** :
  LU (intégral ou plages utiles) : docs/audits/METHODE.md §A.4 et §C.1 ; charte X3 ; `apps/parametres/` : models_statuses.py, statuses_defaults.py, views_statuses.py, serializers_statuses.py,
  models_taxes.py, models_payment_terms.py, models_units.py, views_referentiels.py, serializers_referentiels.py, models_approvals.py, views_approvals.py, serializers_approvals.py,
  models_audit.py, views_audit.py, views_profile.py, views_config.py (80-397), serializers_company.py (1-555), tax_id_validators.py, views_documents.py (36-97), views_tariff.py (57-125),
  views_uploads.py (26-170), views_messages.py (56-170), views_email.py (60-137), serializers_email.py (1-55), views_translations.py (28-160), views_gabarits.py (28-133),
  views_realisations.py, serializers_realisations.py, views_onboarding.py (55-103), onboarding_pays.py (48-80), views_fetes_mobiles.py (66-92), signals.py, urls.py, views.py, views_common.py,
  selectors.py (20-215, 632-691), localisation.py (1-80), models_company.py (14-60, 195-250, 312-350, 1015-1115 + liste des champs) ; core/mixins.py, core/viewsets.py (docstring), core/tz_display.py ;
  authentication/permissions.py (IsAdminOrResponsableTier, IsAnyRole, HasPermissionOrLegacy), authentication/role_tiers.py, authentication/models.py (menu_tier) ;
- **LPAR2** :
  LU (intégralement) : `backend/django_core/apps/parametres/gabarits.py`, `gabarits_contexte.py`, `models_documents.py`, `models_email.py`, `localisation.py`, `i18n_labels.py`, `i18n_resolver.py`,
  `i18n_wizard_core.py`, `glossaire_export.py`, `models_translations.py`, `views_gabarits.py`, `views_documents.py`, `serializers_documents.py`, `serializers_email.py`, `core/templating.py`.
  LU (plages) : `models_messages.py` l.1-120, 400-700 (modèle, `get_corps`, `Cle`), 876-1122 (variantes, formes e-mail, identités, relance_email_j10, textes CIQ/AGR) — les blocs darija/variantes segment l.120-400 et 700-876 non relus ligne à ligne ;
  `models_relance.py` l.1-60 + inventaire des `template_cle` (script : toutes les clés ont un défaut) — le reste (cadences, créneaux) non lu ; `views_messages.py` (en entier : 60-175 + dict), `views_email.py` (en entier),
  `views_config.py` l.28-135, 148-300, 340-420 ; `views_statuses.py` l.25-80 ; `urls.py` (grep) ; `tests_asec31_parametres_modifier.py` l.1-60.
  LU HORS SURFACE (lecteurs, pour les 4 questions) : `ventes/domain/envoi.py` l.60-190 ; `ventes/quote_engine/builder.py` l.1485-1530, 3525-3600 ; `generate_devis_premium.py` l.795-960, 4935-4975 ;
  `ventes/public/payload_conditions.py` l.80-125 ; `ventes/utils/whatsapp.py` l.15-215 ; `ventes/email_service.py` l.205-340, 385-460 ; `ventes/views/devis_envoi.py` l.176-300 ; `ventes/domain/recouvrement.py` l.370-430 ;
- **LPAR3** :
  Lus en entier : `retention.py`, `feature_flags.py`, `services_licence.py`, `signup_hooks.py`, `scheduled.py`, `tarifs_officiels.py`,
  `fetes_mobiles.py`, `onboarding_pays.py`, `models_realisations.py`, `management/commands/purge_audit_retention.py`, `views_fetes_mobiles.py`,
  `views_onboarding.py` (l. 20-140), `admin.py` (parametres), `adminops/admin.py`.
  Lus par plages : `tariff.py` 20-235 et 380-400 (le reste — TOU, compensation, fiscalité, FDA, sensibilités, 235-380 inversion facture→kWh, 400-1484 — NON lu) ;
  `models_tariff.py` 36-135 ; `pvgis.py` 1-120 ; `pvgis_profils.py` 1-230 et 925-970 (courbes 230-925 et 970-1184 NON lus) ; `lieux_maroc.py` 1-40 ;
  `selectors.py` 181-275 (`tariff_for`, `residential_tranches_for`, `tou_pour`).
  Hors surface, lus pour recouper : `audit/selectors.py:161-202`, `audit/management/commands/purge_audit_log.py`, `core/feature_flags.py` 30-190,

## 4. Run live (phase 4-c/4-d)
- `/parametres` (admin) : page chargée ; requêtes de l'écran `parametres/`, `parametres/messages/`, `parametres/audit/`,
  `notifications/*` toutes 200 ; aucun `console.error` produit par l'écran (les 401 relevés sont ceux d'avant connexion).
- `GET parametres/audit/` : 14 entrées (démo) — le défaut de pagination (C-APAR « count = taille de page ») ne se manifeste pas
  sous 50 entrées ; il est prouvé par la sonde du vérificateur VB.
- Refus d'un rôle non admin, opposition sur les envois, automatisations hors société, purge de rétention : prouvés par les sondes
  HTTP/service des vérificateurs (transactions annulées), PAS rejoués à l'écran — la tâche d'acceptation live du groupe les rejoue.

## 5. Registre des constats (phase 4 → 6)


## RÉFUTÉS (avec argument)
- **LNOTIF-11 « code mort WhatsApp sortant sans appelant, sans garde d'opposition »** — RÉFUTÉ par VA : `send_whatsapp_campaign_message`
  a un appelant vivant (`reporting/diffusion_views.py:120-131` ← `scheduled_reports.py:473-474`, diffusion NTDATA39) ; les destinataires
  sont des numéros saisis par l'admin sur le rapport, pas des contacts CRM (`ne_plus_contacter` sans objet) ; `BspProvider.get_wa_url`
  exécuté renvoie `provider: 'manual'` ⇒ statut `MANUAL`, pas `SENT` ; `_send_via_api` non appelé = scaffold GATED fondateur documenté.
- **LPAR1-2 (b) « ConditionPaiement sans lecteur »** — RÉFUTÉ par VB : `facturation/models.py:440-444` (ARC24) lit
  `condition_paiement_ref.libelle` à la création d'une facture (sonde p14 : `conditions_paiement = 'PROBEVB 37 jours'`).
- **LFRONT-1 « l'admin ne voit que "Ajout impossible." »** — RÉFUTÉ par VC : l'intercepteur global `api/axios.js:108-122` affiche
  d'abord le message serveur (nommant le champ et les couples autorisés, rejoué en node sur la vraie réponse 400) ; résidu S4 → OPTIONNEL.
- **LFRONT-2 « échecs silencieux (révocation de clé, rotation de secret) »** — RÉFUTÉ par VC : aucun appel ne passe `suppressErrorToast` ;
  403/400/429/5xx/réseau déclenchent le toast global avec la vraie cause ; seuls 404/401 restent muets (voulu) ; résidu S4 → OPTIONNEL.
- **Détecteur 10 (`detecteurs.md`) « 44 signaux orphelins sans abonné ni justification »** — RÉFUTÉ par LBUS (table AST
  `lbus/bus_table.py`, 82 signaux) et VA (`unproduced= set()`) : `orphan_signals()` est VIDE après `django.setup()` ; les 11 émis sans
  abonné sont listés `ALLOWED_UNCONSUMED`. La sortie du scout provient vraisemblablement d'un appel sans registre Django chargé. Le vrai
  défaut de couverture est le sens inverse (abonné sans émetteur) → C-APAR-036.
- **Détecteur 11 « garde `ne_plus_contacter` absente de `send_whatsapp_campaign_message` »** — RÉFUTÉ (même argument que LNOTIF-11 :
  destinataires saisis par l'admin, pas des leads). L'absence de garde d'opposition RÉELLE est celle de l'automatisation (C-APAR-020,
  déjà couverte par ACRM17).

## PLAUSIBLES (non promus — sous-volets non rejoués, rattachés à leur constat parent quand il est prouvé)
- C-APAR-022 : arrivée réelle d'un push sur un navigateur après déconnexion (exige un navigateur + clés VAPID) — non rejoué.
- C-APAR-023 : course réelle à deux requêtes simultanées — seule la fenêtre déterministe (deux instances périmées) est rejouée.
- C-APAR-011 : chaînes `intervention_completed` / `workflow_etape_activee` non rejouées (STATIQUE) ; panne naturelle de
  `completer_par_evenement` non connue (course `unique_together (user, item)` plausible) — la panne de la sonde est injectée.
- C-APAR-007 : volet devis (DATE_ECHEANCE_CHAMP) non exécuté ; C-APAR-032 : volet SLA (SLA inactif en démo).
- C-APAR-013 : branche `company is None` du signal (toutes sociétés) lue, non rejouée ; C-APAR-040 : non-atomicité de l'import lue, non rejouée.
- C-APAR-048 : cron serveur hors dépôt non vérifié (production hors périmètre des sondes).
- C-APAR-049 : existence de traductions réelles d'apps parquées (0 en démo ; probablement déjà purgées le 1er octobre).
- C-APAR-031 : déclenchement nocturne réel (exige une connexion Meta active).
- C-APAR-015 : destinataire du brouillon WhatsApp (aucun responsable démo avec téléphone).
- C-APAR-053 : même 500 sur les AUTRES référentiels à contrainte d'unicité incluant `company` (non balayé) — APAR37 les énumère.
- C-APAR-056 : volume réel de produits en production (> 200 ?) non sondé.
- Frères hors périmètre signalés aux propriétaires (non sondés) : `installations.decider_demande_achat` sans verrou (C-APAR-023) ;
  `sav/selectors.py:956-966` et `reporting/reports.py:363` sans `annule` (C-APAR-030) ; `pre_echeance` à lien vide (C-APAR-015) ;
  source `ged` de l'agrégateur d'approbations (C-APAR-004) ; ajoutés par la critique (grep 08/10, non sondés) : `ventes/domain/facturation_ops.py:601`
  facture de contrat de maintenance à TVA 20 codée (facturation, C-APAR-012) ; `crm/public_chat_views.py:39` « un commercial TAQINOR » dans
  le message d'absence du chat public de toute société (lead, C-APAR-017) ; `records/platform_guards.py:619` `BRANDING_RE` sans « Taqinor »
  en casse mixte (securite, action de classe de C-APAR-017).

## OPTIONNEL (S4 / style / durcissement — aucune tâche)
- **LBUS-4 (VA : S3→S4)** — l'outbox « fiable » (`emit_reliable`/`subscribe_durable`, NTPLT9/10) n'a ni producteur ni abonné ; le beat
  `core-dispatch-outbox` */5 balaie une table vide. Aucun effet utilisateur prouvé (la fenêtre de perte des émetteurs `on_commit` est hypothétique).
- **LPAR3-10 (VB : S3→S4)** — `notifier_traductions_manquantes_hebdo` marque « notifiées » sans regarder le retour de `notify_many` ;
  rouge seulement sous simulation (`notify` → None), aucune condition naturelle de la démo ne le déclenche.
- **LFRONT-1 résidu (VC)** — double toast (global avec la vraie cause, puis « Ajout impossible. ») et message pas sous `action_config`.
- **LFRONT-2 résidu (VC)** — un 404 « clé déjà supprimée » reste sans toast (voulu, `axios.js:118`) ; message contextuel souhaitable.
- **LFRONT-8 (VC : S3→S4)** — refus d'une demande avec le motif codé « Refusé » (décision, auteur, horodatage exacts) ; traité de fait par APAR41.
- Lanes (non vérifiés, hors mandat S1-S3) : `NotificationRoutingRuleSerializer.target_user` non borné à la société (oracle d'id) et PATCH
  partiel en 400 ; `skip_email=True` saute le report N1 de tous les canaux ; balayages quotidiens sans marqueur (garantie, maintenance,
  SAV > 7 j) ; jeton d'approbation sans société scellée ; relance YEVNT9 à `approvers[0]` ; jetons perdus au report N1 (LNOTIF O) ;
  jeton webhook dans le chemin d'URL (décision produit), `_assign_record` accepte un inactif, brouillon IA sans `_valider_set_field`,
  `date.today()` UTC des marqueurs, marqueurs archivables (LAUTO O-2..O-6) ; onboarding sans filtre société sur l'item (latent),
  `facture_paid` émis sans abonné, `emit_reliable` muet sur nom inconnu, commentaires périmés, doublon `budget_cycle_clos` (traité par
  APAR43) (LBUS O) ; `?user=abc`/`?limit=-5` → 500 (traité par APAR32), `TauxTVA.taux`/`escompte_pct` sans borne, `selectors._profile`
  avale tout, clés MinIO de logo sans préfixe société, `CompanyProfile.get(None)` relit le pk=1, contrôle manuel dans `messages_endpoint`
  (traité par APAR5), `prix_transport_ttc` sans appelant (LPAR1 O) ; `resolve_langue_sortie` traite « fr » comme absent, `_NUDGE_MSG`
  signé TAQINOR (vendeur), `civilite` vide, textes admin non échappés dans le PDF (LPAR2 O) ; six copies du barème résidentiel
  identiques aujourd'hui sans garde pour `TarificationSection`/`estimatorBrainV2.ts`, `module_dans_le_plan` fail-open, soft-delete vu
  comme absent, `Realisation.save(update_fields)`, trois productibles par défaut (couvert AMOT3/AMOT64) (LPAR3 O) ; 20 toasts fixes de
  NotificationsAdminSection, `.catch(() => {})` d'Automatisations, `catch` fixes du DemarrageWizard (LFRONT O).

## 6. Couverture non atteinte et limites (phase 6)
Voir l’en-tête du groupe (Non couvert) dans le plan du propriétaire.
