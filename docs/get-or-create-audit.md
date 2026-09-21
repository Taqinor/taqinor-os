# Audit get_or_create / update_or_create (YDATA15)

Généré par `python scripts/check_get_or_create.py`. Chaque appel liste ses clés de lookup (hors `defaults`) — chaque clé PARTAGÉE devrait correspondre à une `UniqueConstraint`/`unique_together` company-scopée sur le modèle cible pour être course-safe. Advisory : ce sweep ne corrige rien (correctifs = ERROR_PLAN).

| Fichier:ligne | Appel | Récepteur | Clés de lookup |
|---|---|---|---|
| `backend/django_core/apps/accessreview/sod.py:137` | get_or_create | SodRule.objects | company, permission_a, permission_b |
| `backend/django_core/apps/adminops/config_package_service.py:111` | update_or_create | Role.objects | company, nom |
| `backend/django_core/apps/adminops/config_package_service.py:121` | update_or_create | CustomFieldDef.objects | code, company, module |
| `backend/django_core/apps/adminops/config_package_service.py:131` | update_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/adminops/plan_seeds.py:59` | get_or_create | PlanLicence.objects | code |
| `backend/django_core/apps/adminops/views_annonces.py:149` | get_or_create | LectureAnnonce.objects | annonce, utilisateur |
| `backend/django_core/apps/adsengine/brief.py:469` | update_or_create | WeeklyBrief.objects | company, period_start |
| `backend/django_core/apps/adsengine/calendar.py:69` | get_or_create | CreativeCalendarEvent.objects | company, date_debut, tag |
| `backend/django_core/apps/adsengine/comments.py:74` | update_or_create | CommentMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/field_tests.py:316` | update_or_create | FieldTestResult.objects | company, ft |
| `backend/django_core/apps/adsengine/flightrunner.py:136` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/flightrunner.py:222` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/flightrunner.py:518` | update_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/flightrunner.py:528` | update_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/instagram.py:55` | update_or_create | InstagramMediaMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/instagram.py:84` | update_or_create | InstagramCommentMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_adsengine.py:40` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/management/commands/seed_adsengine.py:68` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/management/commands/seed_fact_table.py:91` | get_or_create | FactEntry.objects | cle, table |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py:137` | update_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py:141` | update_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py:159` | update_or_create | AdMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/models.py:656` | update_or_create | cls.objects | company, content_type, date, dimension, key, object_id |
| `backend/django_core/apps/adsengine/models.py:1329` | update_or_create | cls.objects | arm, company, date |
| `backend/django_core/apps/adsengine/models.py:1596` | update_or_create | cls.objects | company, period_start |
| `backend/django_core/apps/adsengine/policy.py:40` | get_or_create | CreativePolicy.objects | company |
| `backend/django_core/apps/adsengine/posterior_drift.py:158` | get_or_create | EngineAlert.objects | company, entity_key, resolved |
| `backend/django_core/apps/adsengine/receivers.py:78` | update_or_create | MetaLeadMirror.objects | company, leadgen_id |
| `backend/django_core/apps/adsengine/reconciliation.py:350` | update_or_create | RS.objects | campaign, company, date |
| `backend/django_core/apps/adsengine/rule_templates.py:628` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/rule_templates.py:737` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/simulator.py:87` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/simulator.py:596` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/simulator.py:814` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/sync.py:56` | get_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:87` | get_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:116` | get_or_create | AdMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:181` | update_or_create | AdCreativeMirror.objects | ad, company |
| `backend/django_core/apps/adsengine/sync.py:242` | update_or_create | PagePostMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:326` | update_or_create | InsightSnapshot.objects | company, content_type, date, object_id |
| `backend/django_core/apps/adsengine/tasks.py:2327` | update_or_create | InsightMonthlyRollup.objects | company_id, content_type_id, month, object_id, year |
| `backend/django_core/apps/adsengine/views.py:2390` | get_or_create | MetaConnection.objects | company |
| `backend/django_core/apps/adsengine/views.py:2603` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/views.py:2610` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/whatsapp_webhook.py:221` | update_or_create | CtwaReferral.objects | company, wa_message_id |
| `backend/django_core/apps/automation/templates.py:252` | get_or_create | AutomationRule.objects | company, nom |
| `backend/django_core/apps/automation/views.py:514` | get_or_create | IncomingWebhookTrigger.objects | rule |
| `backend/django_core/apps/calepinage/services/modeles.py:55` | get_or_create | Tag.objects | company, nom |
| `backend/django_core/apps/calepinage/services/modeles.py:88` | get_or_create | TaggedItem.objects | content_type, object_id, tag |
| `backend/django_core/apps/calepinage/views/calepinages.py:133` | get_or_create | IdempotencyRecord.objects | company, endpoint, key |
| `backend/django_core/apps/calepinage/views/reglementaire.py:136` | get_or_create | DossierReglementaire.objects | calepinage, company, gabarit |
| `backend/django_core/apps/crm/management/commands/snapshot_forecast_hebdo.py:58` | update_or_create | ForecastSnapshot.objects | categorie, company, owner_id, semaine_iso |
| `backend/django_core/apps/crm/services.py:205` | get_or_create | LeadPlaybookProgress.objects | lead, tache |
| `backend/django_core/apps/crm/services.py:9623` | get_or_create | Playbook.objects | company, nom |
| `backend/django_core/apps/crm/services.py:9630` | get_or_create | PlaybookEtape.objects | playbook, stage |
| `backend/django_core/apps/crm/services.py:9632` | get_or_create | PlaybookTache.objects | etape, libelle |
| `backend/django_core/apps/crm/views.py:2566` | get_or_create | LeadTag.objects | company, nom |
| `backend/django_core/apps/crm/views.py:2580` | get_or_create | MotifPerte.objects | company, nom |
| `backend/django_core/apps/crm/views.py:2592` | get_or_create | MotifPerte.objects | company, nom |
| `backend/django_core/apps/crm/views.py:2649` | get_or_create | Canal.objects | cle, company |
| `backend/django_core/apps/customfields/blueprint.py:201` | update_or_create | modele.objects |  |
| `backend/django_core/apps/customfields/catalogue.py:99` | get_or_create | CustomObjectDef.objects | code, company |
| `backend/django_core/apps/customfields/catalogue.py:106` | get_or_create | CustomFieldDef.objects | code, company, module |
| `backend/django_core/apps/dataimport/services.py:440` | update_or_create | ImportMapping.objects | company, entity, nom |
| `backend/django_core/apps/dataimport/services.py:486` | get_or_create | ExternalRef.objects | company, external_id, external_system |
| `backend/django_core/apps/dataimport/translations_i18n.py:112` | update_or_create | TranslationOverride.objects | company, key, locale |
| `backend/django_core/apps/ged/management/commands/migrate_attachments_to_ged.py:57` | get_or_create | Cabinet.objects | company, nom |
| `backend/django_core/apps/ged/management/commands/migrate_attachments_to_ged.py:163` | get_or_create | DocumentLien.objects | content_type, document, object_id |
| `backend/django_core/apps/ged/management/commands/seed_types_champ_signature.py:30` | get_or_create | TypeChampSignature.objects | code, company |
| `backend/django_core/apps/ged/services.py:333` | update_or_create | ValidationOcrDocument.objects | document |
| `backend/django_core/apps/ged/services.py:681` | get_or_create | DocumentTagAssignment.objects | document, tag |
| `backend/django_core/apps/ged/services.py:854` | get_or_create | Cabinet.objects | company, nom |
| `backend/django_core/apps/ged/services.py:3947` | get_or_create | DocumentLien.objects | company, content_type, document, object_id |
| `backend/django_core/apps/ged/services.py:4625` | get_or_create | DocumentTag.objects | company, slug |
| `backend/django_core/apps/ged/services.py:5857` | get_or_create | Folder.objects | cabinet, company, nom, parent |
| `backend/django_core/apps/ged/views.py:1997` | get_or_create | DocumentLien.objects | content_type, document, object_id |
| `backend/django_core/apps/installations/field_capture.py:79` | get_or_create | MaterielConsommation.objects | intervention |
| `backend/django_core/apps/installations/field_capture.py:334` | get_or_create | SafetyChecklistSlot.objects | cle, company |
| `backend/django_core/apps/installations/field_capture.py:344` | get_or_create | SafetySignoff.objects | intervention |
| `backend/django_core/apps/installations/field_services.py:54` | get_or_create | ShotListSlot.objects | cle, company |
| `backend/django_core/apps/installations/field_services.py:156` | get_or_create | InterventionPreparation.objects | intervention |
| `backend/django_core/apps/installations/field_services.py:357` | get_or_create | FicheInterventionReleve.objects | intervention |
| `backend/django_core/apps/installations/services.py:112` | get_or_create | ChecklistEtapeModele.objects | cle, company, template |
| `backend/django_core/apps/installations/services.py:391` | get_or_create | DocumentProjet.objects | installation, type_doc |
| `backend/django_core/apps/installations/services.py:511` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py:778` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py:863` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py:1113` | get_or_create | StageModele.objects | cle, company |
| `backend/django_core/apps/installations/services.py:1700` | get_or_create | CommissioningRecord.objects | installation |
| `backend/django_core/apps/installations/services.py:1909` | get_or_create | HandoverPack.objects | installation |
| `backend/django_core/apps/installations/services.py:1971` | get_or_create | ReservationAssemblage.objects | ordre, produit_id |
| `backend/django_core/apps/installations/services.py:2995` | get_or_create | SerieEntrepot.objects | company, numero_serie, produit_id |
| `backend/django_core/apps/installations/services.py:3643` | get_or_create | JalonProjet.objects | installation, phase |
| `backend/django_core/apps/installations/services.py:3732` | get_or_create | EmplacementStock.objects | company, nom |
| `backend/django_core/apps/installations/views/approbation_bcf.py:100` | update_or_create | ApprobationBCF.objects | bcf, company |
| `backend/django_core/apps/installations/views/checklist_etape.py:103` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/checklist_template.py:103` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/installation.py:91` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/installation.py:658` | update_or_create | PhotoChecklistMeta.objects | attachment |
| `backend/django_core/apps/installations/views/intervention.py:135` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/intervention.py:1020` | get_or_create | PhotoAnnotation.objects | attachment |
| `backend/django_core/apps/installations/views/intervention.py:1567` | get_or_create | ToolReturn.objects | intervention, outil_id |
| `backend/django_core/apps/installations/views/program.py:152` | get_or_create | link_model.objects | projet |
| `backend/django_core/apps/installations/views/safety.py:103` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/shotlist.py:102` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/type_intervention.py:102` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/monitoring/models.py:204` | get_or_create | cls.objects | company |
| `backend/django_core/apps/monitoring/services.py:44` | get_or_create | MonitoringConfig.objects | installation |
| `backend/django_core/apps/monitoring/services.py:208` | get_or_create | UnderperformanceFlag.objects | installation, is_open |
| `backend/django_core/apps/notifications/management/commands/seed_holidays_ci.py:73` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_holidays_fr.py:75` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_holidays_sn.py:73` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_ma_holidays.py:63` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_ma_holidays.py:75` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/selectors.py:149` | update_or_create | Holiday.objects | company, date, pays |
| `backend/django_core/apps/notifications/services.py:933` | get_or_create | AnnonceLecture.objects | annonce, utilisateur |
| `backend/django_core/apps/notifications/services.py:1021` | get_or_create | AnnonceRelance.objects | annonce, utilisateur |
| `backend/django_core/apps/notifications/services.py:1071` | get_or_create | ApprovalReminderState.objects | content_type, object_id |
| `backend/django_core/apps/notifications/services.py:1222` | update_or_create | SnoozedItem.objects | object_id, source, user |
| `backend/django_core/apps/notifications/views.py:141` | get_or_create | NotificationPreference.objects | event_type, user |
| `backend/django_core/apps/notifications/views.py:225` | get_or_create | WorkingHoursConfig.objects | company |
| `backend/django_core/apps/notifications/views.py:533` | update_or_create | PushSubscription.objects | endpoint |
| `backend/django_core/apps/outillage/views.py:32` | get_or_create | KitOutillage.objects | company, nom |
| `backend/django_core/apps/parametres/fetes_mobiles.py:97` | update_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/parametres/models_company.py:1012` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_company.py:1017` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_documents.py:100` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_documents.py:102` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_payment_terms.py:89` | get_or_create | cls.objects | company, delai_jours, escompte_pct, fin_de_mois |
| `backend/django_core/apps/parametres/models_pos.py:72` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_relance.py:389` | get_or_create | cls.objects | cadence, company, ordre |
| `backend/django_core/apps/parametres/models_tariff.py:187` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_tariff.py:189` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_taxes.py:103` | get_or_create | cls.objects | code, company |
| `backend/django_core/apps/parametres/models_units.py:83` | get_or_create | cls.objects | code, company |
| `backend/django_core/apps/parametres/traductions_manquantes.py:63` | get_or_create | TraductionManquante.objects | cle, company, langue |
| `backend/django_core/apps/parametres/views_config.py:198` | get_or_create | DocumentTemplates.objects | company |
| `backend/django_core/apps/parametres/views_email.py:124` | get_or_create | EmailTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_messages.py:118` | get_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_messages.py:148` | get_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_statuses.py:138` | get_or_create | StatutConfig.objects | cle, company, domaine |
| `backend/django_core/apps/parametres/views_translations.py:137` | get_or_create | TranslationOverride.objects | company, key, locale |
| `backend/django_core/apps/portail/services.py:301` | get_or_create | ComptePortailClient.objects | client, company |
| `backend/django_core/apps/portail/services.py:318` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/portail/services.py:394` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/portail/services.py:557` | update_or_create | JalonChantierPortail.objects | chantier_id, cle_phase, company |
| `backend/django_core/apps/portail/services.py:680` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/portail/views_client.py:572` | get_or_create | AcceptationDevisPortail.objects | company, devis |
| `backend/django_core/apps/portail/views_client.py:675` | get_or_create | PaiementFacturePortail.objects | company, facture, statut |
| `backend/django_core/apps/portail/views_externes.py:495` | update_or_create | PreferencePortail.objects | utilisateur |
| `backend/django_core/apps/publicapi/idempotency.py:64` | get_or_create | IdempotencyRecord.objects | api_key, endpoint, idempotency_key |
| `backend/django_core/apps/records/services.py:104` | get_or_create | Follower.objects | company, content_type, object_id, sous_type, user |
| `backend/django_core/apps/records/views.py:956` | get_or_create | TaggedItem.objects | content_type, object_id, tag |
| `backend/django_core/apps/roles/management/commands/init_roles.py:87` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/sav/models.py:167` | get_or_create | cls.objects | company |
| `backend/django_core/apps/sav/services.py:1134` | get_or_create | TicketFollower.objects | company, ticket, user |
| `backend/django_core/apps/sav/views.py:1280` | get_or_create | TicketFollower.objects | company, ticket, user |
| `backend/django_core/apps/sav/views.py:1923` | get_or_create | TicketChecklistItem.objects | cle, ticket |
| `backend/django_core/apps/statuspage/tasks.py:71` | get_or_create | UptimeDayBucket.objects | company, composant, date, region |
| `backend/django_core/apps/statuspage/tasks.py:137` | update_or_create | ComponentStatus.objects | company, nom, region |
| `backend/django_core/apps/statuspage/tasks.py:155` | update_or_create | ComponentStatus.objects | company, nom, region |
| `backend/django_core/apps/statuspage/views.py:349` | get_or_create | StatusSubscriber.objects | email |
| `backend/django_core/apps/stock/management/commands/backfill_unites_mesure.py:52` | get_or_create | UniteMesure.objects | code, company |
| `backend/django_core/apps/stock/management/commands/seed_catalogue.py:1689` | get_or_create | Categorie.objects | company, nom |
| `backend/django_core/apps/stock/management/commands/seed_catalogue.py:2027` | get_or_create | Categorie.objects | company, nom |
| `backend/django_core/apps/stock/models.py:531` | get_or_create | cls.objects | company |
| `backend/django_core/apps/stock/models_negoce_params.py:64` | get_or_create | cls.objects | company |
| `backend/django_core/apps/stock/services.py:201` | get_or_create | EmplacementStock.objects | company, nom |
| `backend/django_core/apps/stock/services.py:336` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:342` | get_or_create | StockEmplacement.objects | emplacement, produit |
| `backend/django_core/apps/stock/services.py:377` | get_or_create | PrixFournisseur.objects | fournisseur, produit |
| `backend/django_core/apps/stock/services.py:407` | get_or_create | StockEmplacement.objects | company, emplacement, produit |
| `backend/django_core/apps/stock/services.py:1310` | get_or_create | LotEntrepot.objects.select_for_update() | company, numero_lot, produit |
| `backend/django_core/apps/stock/services.py:1502` | get_or_create | SousTraitantProfile.objects | fournisseur |
| `backend/django_core/apps/stock/services.py:1971` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:2204` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3914` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3933` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3980` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:4006` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:6147` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/stock/services_transfert_deux_temps.py:100` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services_transfert_deux_temps.py:162` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services_wms.py:1013` | get_or_create | PlanComptageTournant.objects | classe_abc, company |
| `backend/django_core/apps/stock/views/catalogue_achat.py:138` | get_or_create | FavorisCatalogueAchat.objects | company, utilisateur |
| `backend/django_core/apps/stock/views/marque.py:57` | get_or_create | Marque.objects | company, nom |
| `backend/django_core/apps/uxviews/models.py:174` | get_or_create | cls.objects | company |
| `backend/django_core/apps/uxviews/views.py:98` | update_or_create | EcranRecent.objects | company, ecran, owner |
| `backend/django_core/apps/uxviews/views.py:585` | get_or_create | FavoriUtilisateur.objects | company, content_type, object_id, owner |
| `backend/django_core/apps/ventes/domain/facturation_ops.py:706` | get_or_create | Produit.objects | company, sku |
| `backend/django_core/apps/ventes/domain/gammes.py:256` | get_or_create | ParametresGammes.objects | company |
| `backend/django_core/apps/ventes/views/liste_prix.py:90` | update_or_create | LignePrixListe.objects | liste, produit |
| `backend/django_core/apps/ventes/views/remise_encaissement.py:127` | get_or_create | LigneRemiseEncaissement.objects | paiement, remise |
