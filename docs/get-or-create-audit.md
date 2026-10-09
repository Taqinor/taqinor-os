# Audit get_or_create / update_or_create (YDATA15)

Généré par `python scripts/check_get_or_create.py`. Chaque appel liste ses clés de lookup (hors `defaults`) — chaque clé PARTAGÉE devrait correspondre à une `UniqueConstraint`/`unique_together` company-scopée sur le modèle cible pour être course-safe. Advisory : ce sweep ne corrige rien (correctifs = ERROR_PLAN).

Clé de CONTENU `fichier::fonction::Modèle` (jamais un numéro de ligne : une insertion en amont ne fait plus remonter les voisins comme nouveaux). Régénéré par `python scripts/check_get_or_create.py --write`.

| Clé | Appel | Récepteur | Clés de lookup |
|---|---|---|---|
| `backend/django_core/apps/accessreview/sod.py::seed_standard_sod_rules::SodRule` | get_or_create | SodRule.objects | company, permission_a, permission_b |
| `backend/django_core/apps/adminops/config_package_service.py::appliquer_import::CustomFieldDef` | update_or_create | CustomFieldDef.objects | code, company, module |
| `backend/django_core/apps/adminops/config_package_service.py::appliquer_import::MessageTemplate` | update_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/adminops/config_package_service.py::appliquer_import::Role` | update_or_create | Role.objects | company, nom |
| `backend/django_core/apps/adminops/plan_seeds.py::seed_plan_solaire::PlanLicence` | get_or_create | PlanLicence.objects | code |
| `backend/django_core/apps/adminops/views_annonces.py::AnnonceProduitMarquerLuView.post::LectureAnnonce` | get_or_create | LectureAnnonce.objects | annonce, utilisateur |
| `backend/django_core/apps/adsengine/brief.py::build_brief::WeeklyBrief` | update_or_create | WeeklyBrief.objects | company, period_start |
| `backend/django_core/apps/adsengine/calendar.py::seed_calendar::CreativeCalendarEvent` | get_or_create | CreativeCalendarEvent.objects | company, date_debut, tag |
| `backend/django_core/apps/adsengine/comments.py::sync_comments::CommentMirror` | update_or_create | CommentMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/field_tests.py::record_result::FieldTestResult` | update_or_create | FieldTestResult.objects | company, ft |
| `backend/django_core/apps/adsengine/flightrunner.py::FlightRunner._mirror_adset::AdSetMirror` | update_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/flightrunner.py::FlightRunner._mirror_campaign::AdCampaignMirror` | update_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/flightrunner.py::FlightRunner.engage_kill_switch::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/flightrunner.py::set_autonomy_active::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/instagram.py::sync_ig_comments::InstagramCommentMirror` | update_or_create | InstagramCommentMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/instagram.py::sync_ig_media::InstagramMediaMirror` | update_or_create | InstagramMediaMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_adsengine.py::Command._seed_guardrails::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/management/commands/seed_adsengine.py::Command._seed_rule_policies::RulePolicy` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/management/commands/seed_fact_table.py::Command.handle::FactEntry` | get_or_create | FactEntry.objects | cle, table |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py::generate_synthetic_account::AdCampaignMirror` | update_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py::generate_synthetic_account::AdMirror` | update_or_create | AdMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py::generate_synthetic_account::AdSetMirror` | update_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/models.py::ArmDailyStat.upsert::cls` | update_or_create | cls.objects | arm, company, date |
| `backend/django_core/apps/adsengine/models.py::InsightBreakdown.upsert::cls` | update_or_create | cls.objects | company, content_type, date, dimension, key, object_id |
| `backend/django_core/apps/adsengine/models.py::PacingState.upsert::cls` | update_or_create | cls.objects | company, period_start |
| `backend/django_core/apps/adsengine/policy.py::ensure_default_policy::CreativePolicy` | get_or_create | CreativePolicy.objects | company |
| `backend/django_core/apps/adsengine/posterior_drift.py::flag_dead_branches::EngineAlert` | get_or_create | EngineAlert.objects | company, entity_key, resolved |
| `backend/django_core/apps/adsengine/receivers.py::on_meta_lead_captured::MetaLeadMirror` | update_or_create | MetaLeadMirror.objects | company, leadgen_id |
| `backend/django_core/apps/adsengine/reconciliation.py::run_daily_reconciliation::RS` | update_or_create | RS.objects | campaign, company, date |
| `backend/django_core/apps/adsengine/rule_templates.py::seed_default_policies::RulePolicy` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/rule_templates.py::seed_strategies::RulePolicy` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/simulator.py::simulate::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/simulator.py::simulate_assumption_scheduler::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/simulator.py::simulate_generation::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/sync.py::sync_ad_creative::AdCreativeMirror` | update_or_create | AdCreativeMirror.objects | ad, company |
| `backend/django_core/apps/adsengine/sync.py::sync_ads::AdMirror` | get_or_create | AdMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py::sync_adsets::AdSetMirror` | get_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py::sync_campaigns::AdCampaignMirror` | get_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py::sync_page_posts::PagePostMirror` | update_or_create | PagePostMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py::upsert_insight::InsightSnapshot` | update_or_create | InsightSnapshot.objects | company, content_type, date, object_id |
| `backend/django_core/apps/adsengine/tasks.py::rollup_insights_monthly::InsightMonthlyRollup` | update_or_create | InsightMonthlyRollup.objects | company_id, content_type_id, month, object_id, year |
| `backend/django_core/apps/adsengine/veille_decouverte.py::ingerer_page::VeilleAnnonceur` | get_or_create | VeilleAnnonceur.objects | company_id, page_id |
| `backend/django_core/apps/adsengine/veille_decouverte.py::ingerer_page::VeillePubVue` | get_or_create | VeillePubVue.objects | ad_archive_id, company_id, requete |
| `backend/django_core/apps/adsengine/views.py::GuardrailSingletonView.get::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/views.py::GuardrailSingletonView.patch::GuardrailConfig` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/views.py::MetaConnectionStatusView.post::MetaConnection` | get_or_create | MetaConnection.objects | company |
| `backend/django_core/apps/adsengine/whatsapp_webhook.py::WhatsAppCloudWebhookView._process::CtwaReferral` | update_or_create | CtwaReferral.objects | company, wa_message_id |
| `backend/django_core/apps/automation/templates.py::installer_modele::AutomationRule` | get_or_create | AutomationRule.objects | company, nom |
| `backend/django_core/apps/calepinage/services/modeles.py::_tag_modele::Tag` | get_or_create | Tag.objects | company, nom |
| `backend/django_core/apps/calepinage/services/modeles.py::marquer_modele::TaggedItem` | get_or_create | TaggedItem.objects | content_type, object_id, tag |
| `backend/django_core/apps/calepinage/views/calepinages.py::ActionIdempotenteMixin.executer_idempotent::IdempotencyRecord` | get_or_create | IdempotencyRecord.objects | company, endpoint, key |
| `backend/django_core/apps/calepinage/views/reglementaire.py::_dossier_en_base::DossierReglementaire` | get_or_create | DossierReglementaire.objects | calepinage, company, gabarit |
| `backend/django_core/apps/crm/management/commands/snapshot_forecast_hebdo.py::snapshot_forecast_hebdo::ForecastSnapshot` | update_or_create | ForecastSnapshot.objects | categorie, company, owner_id, semaine_iso |
| `backend/django_core/apps/crm/mesure_cadence.py::enregistrer_geste_appareil::GesteRelanceAppareil` | get_or_create | GesteRelanceAppareil.objects | company, famille_appareil, geste, jour |
| `backend/django_core/apps/crm/services.py::_rattraper_playbooks_lisant::LeadPlaybookProgress` | get_or_create | LeadPlaybookProgress.objects | lead, tache |
| `backend/django_core/apps/crm/services.py::generer_playbook_progress::LeadPlaybookProgress` | get_or_create | LeadPlaybookProgress.objects | lead, tache |
| `backend/django_core/apps/crm/services.py::seed_playbooks_segment::Playbook` | get_or_create | Playbook.objects | company, nom |
| `backend/django_core/apps/crm/services.py::seed_playbooks_segment::PlaybookEtape` | get_or_create | PlaybookEtape.objects | playbook, stage |
| `backend/django_core/apps/crm/services.py::seed_playbooks_segment::PlaybookTache` | get_or_create | PlaybookTache.objects | etape, libelle |
| `backend/django_core/apps/crm/views.py::completer_motifs_perte::MotifPerte` | get_or_create | MotifPerte.objects | company, nom |
| `backend/django_core/apps/crm/views.py::seed_canaux::Canal` | get_or_create | Canal.objects | cle, company |
| `backend/django_core/apps/crm/views.py::seed_motifs_perte::MotifPerte` | get_or_create | MotifPerte.objects | company, nom |
| `backend/django_core/apps/crm/views.py::seed_tags::LeadTag` | get_or_create | LeadTag.objects | company, nom |
| `backend/django_core/apps/customfields/blueprint.py::importer_blueprint::modele` | update_or_create | modele.objects |  |
| `backend/django_core/apps/customfields/catalogue.py::installer_modele::CustomFieldDef` | get_or_create | CustomFieldDef.objects | code, company, module |
| `backend/django_core/apps/customfields/catalogue.py::installer_modele::CustomObjectDef` | get_or_create | CustomObjectDef.objects | code, company |
| `backend/django_core/apps/dataimport/services.py::_get_or_create_ref::ExternalRef` | get_or_create | ExternalRef.objects | company, content_type, external_id, external_system |
| `backend/django_core/apps/dataimport/services.py::save_mapping::ImportMapping` | update_or_create | ImportMapping.objects | company, entity, nom |
| `backend/django_core/apps/dataimport/translations_i18n.py::importer_traductions_csv::TranslationOverride` | update_or_create | TranslationOverride.objects | company, key, locale |
| `backend/django_core/apps/ged/management/commands/migrate_attachments_to_ged.py::_ensure_landing_folder::Cabinet` | get_or_create | Cabinet.objects | company, nom |
| `backend/django_core/apps/ged/management/commands/migrate_attachments_to_ged.py::_ensure_lien::DocumentLien` | get_or_create | DocumentLien.objects | content_type, document, object_id |
| `backend/django_core/apps/ged/management/commands/seed_types_champ_signature.py::seed_types_champ_signature_for_company::TypeChampSignature` | get_or_create | TypeChampSignature.objects | code, company |
| `backend/django_core/apps/ged/services.py::_appliquer_tag_expediteur::DocumentTag` | get_or_create | DocumentTag.objects | company, slug |
| `backend/django_core/apps/ged/services.py::_resoudre_dossier_cible::Folder` | get_or_create | Folder.objects | cabinet, company, nom, parent |
| `backend/django_core/apps/ged/services.py::assign_tag::DocumentTagAssignment` | get_or_create | DocumentTagAssignment.objects | document, tag |
| `backend/django_core/apps/ged/services.py::classer_signature_completee::DocumentLien` | get_or_create | DocumentLien.objects | company, content_type, document, object_id |
| `backend/django_core/apps/ged/services.py::ensure_cabinet::Cabinet` | get_or_create | Cabinet.objects | company, nom |
| `backend/django_core/apps/ged/services.py::ocr_extraction_avec_validation::ValidationOcrDocument` | update_or_create | ValidationOcrDocument.objects | document |
| `backend/django_core/apps/ged/views.py::DocumentLienViewSet.create::DocumentLien` | get_or_create | DocumentLien.objects | content_type, document, object_id |
| `backend/django_core/apps/installations/field_capture.py::ensure_consommation::MaterielConsommation` | get_or_create | MaterielConsommation.objects | intervention |
| `backend/django_core/apps/installations/field_capture.py::ensure_safety_signoff::SafetySignoff` | get_or_create | SafetySignoff.objects | intervention |
| `backend/django_core/apps/installations/field_capture.py::seed_safety_slots::SafetyChecklistSlot` | get_or_create | SafetyChecklistSlot.objects | cle, company |
| `backend/django_core/apps/installations/field_services.py::ensure_fiche_releve::FicheInterventionReleve` | get_or_create | FicheInterventionReleve.objects | intervention |
| `backend/django_core/apps/installations/field_services.py::ensure_preparation::InterventionPreparation` | get_or_create | InterventionPreparation.objects | intervention |
| `backend/django_core/apps/installations/field_services.py::seed_shotlist_slots::ShotListSlot` | get_or_create | ShotListSlot.objects | cle, company |
| `backend/django_core/apps/installations/services.py::_emplacement_van::EmplacementStock` | get_or_create | EmplacementStock.objects | company, nom |
| `backend/django_core/apps/installations/services.py::_poser_reservation_ecart::StockReservation` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py::_publier_jalon_statut::JalonProjet` | get_or_create | JalonProjet.objects | installation, phase |
| `backend/django_core/apps/installations/services.py::_seed_schema_unifilaire_document::DocumentProjet` | get_or_create | DocumentProjet.objects | installation, type_doc |
| `backend/django_core/apps/installations/services.py::appliquer_mouvement_casier::BinAffectation` | get_or_create | BinAffectation.objects.select_for_update() | bin_id, produit_id |
| `backend/django_core/apps/installations/services.py::ensure_commissioning_record::CommissioningRecord` | get_or_create | CommissioningRecord.objects | installation |
| `backend/django_core/apps/installations/services.py::ensure_default_template::ChecklistEtapeModele` | get_or_create | ChecklistEtapeModele.objects | cle, company, template |
| `backend/django_core/apps/installations/services.py::generer_handover_pack::HandoverPack` | get_or_create | HandoverPack.objects | installation |
| `backend/django_core/apps/installations/services.py::notifier_reception_solde_a_facturer::JalonProjet` | get_or_create | JalonProjet.objects | installation, phase |
| `backend/django_core/apps/installations/services.py::peupler_series_entrepot_reception::SerieEntrepot` | get_or_create | SerieEntrepot.objects | company, numero_serie, produit_id |
| `backend/django_core/apps/installations/services.py::reserver_stock_recu_pour_chantier::StockReservation` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py::seed_reservations_assemblage::ReservationAssemblage` | get_or_create | ReservationAssemblage.objects | ordre, produit_id |
| `backend/django_core/apps/installations/services.py::seed_stages::StageModele` | get_or_create | StageModele.objects | cle, company |
| `backend/django_core/apps/installations/views/approbation_bcf.py::ApprobationBCFViewSet.approuver::ApprobationBCF` | update_or_create | ApprobationBCF.objects | bcf, company |
| `backend/django_core/apps/installations/views/checklist_etape.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/checklist_template.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/installation.py::InstallationViewSet.checklist_photo::PhotoChecklistMeta` | update_or_create | PhotoChecklistMeta.objects | attachment |
| `backend/django_core/apps/installations/views/installation.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/intervention.py::InterventionViewSet._tool_return_response::ToolReturn` | get_or_create | ToolReturn.objects | intervention, outil_id |
| `backend/django_core/apps/installations/views/intervention.py::InterventionViewSet.annoter_photo::PhotoAnnotation` | get_or_create | PhotoAnnotation.objects | attachment |
| `backend/django_core/apps/installations/views/intervention.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/program.py::ProjetViewSet._attach::link_model` | get_or_create | link_model.objects | projet |
| `backend/django_core/apps/installations/views/safety.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/shotlist.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/type_intervention.py::seed_types_intervention::TypeIntervention` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/monitoring/models.py::MonitoringSettings.get::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/monitoring/services.py::evaluate_underperformance::UnderperformanceFlag` | get_or_create | UnderperformanceFlag.objects | installation, is_open |
| `backend/django_core/apps/monitoring/services.py::get_or_create_config::MonitoringConfig` | get_or_create | MonitoringConfig.objects | installation |
| `backend/django_core/apps/notifications/management/commands/seed_holidays_ci.py::Command.handle::Holiday` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_holidays_fr.py::Command.handle::Holiday` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_holidays_sn.py::Command.handle::Holiday` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_ma_holidays.py::seed_holidays_for_company::Holiday` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/management/commands/seed_ma_holidays.py::seed_holidays_for_company::Holiday` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/selectors.py::upsert_holiday::Holiday` | update_or_create | Holiday.objects | company, date, pays |
| `backend/django_core/apps/notifications/services.py::_approval_reminder_state::ApprovalReminderState` | get_or_create | ApprovalReminderState.objects | content_type, object_id |
| `backend/django_core/apps/notifications/services.py::acknowledge_annonce::AnnonceLecture` | get_or_create | AnnonceLecture.objects | annonce, utilisateur |
| `backend/django_core/apps/notifications/services.py::snooze_approbation_item::SnoozedItem` | update_or_create | SnoozedItem.objects | object_id, source, user |
| `backend/django_core/apps/notifications/services.py::sweep_annonce_reminders::AnnonceRelance` | get_or_create | AnnonceRelance.objects | annonce, utilisateur |
| `backend/django_core/apps/notifications/sweeps.py::_reserver_emission::MarqueurEmissionBalayage` | get_or_create | MarqueurEmissionBalayage.objects | cle, company, event_type, periode |
| `backend/django_core/apps/notifications/views.py::NotificationPreferenceViewSet._upsert::NotificationPreference` | get_or_create | NotificationPreference.objects | event_type, user |
| `backend/django_core/apps/notifications/views.py::WorkingHoursConfigViewSet._upsert::WorkingHoursConfig` | get_or_create | WorkingHoursConfig.objects | company |
| `backend/django_core/apps/notifications/views.py::push_subscribe::PushSubscription` | update_or_create | PushSubscription.objects | endpoint |
| `backend/django_core/apps/outillage/views.py::seed_kits_outillage::KitOutillage` | get_or_create | KitOutillage.objects | company, nom |
| `backend/django_core/apps/parametres/models_company.py::CompanyProfile.get._load::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_company.py::CompanyProfile.get._load::cls` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_documents.py::DocumentTemplates.get::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_documents.py::DocumentTemplates.get::cls` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_payment_terms.py::ConditionPaiement.from_triplet::cls` | get_or_create | cls.objects | company, delai_jours, escompte_pct, fin_de_mois |
| `backend/django_core/apps/parametres/models_pos.py::ParametresPos.get::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_relance.py::CadenceRelanceEtape.seed_cadence::cls` | get_or_create | cls.objects | cadence, company, ordre |
| `backend/django_core/apps/parametres/models_tariff.py::TariffSettings._charger::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_tariff.py::TariffSettings._charger::cls` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_taxes.py::TauxTVA.seed_defaults::cls` | get_or_create | cls.objects | code, company |
| `backend/django_core/apps/parametres/models_units.py::UniteMesure.seed_defaults::cls` | get_or_create | cls.objects | code, company |
| `backend/django_core/apps/parametres/traductions_manquantes.py::enregistrer_repli::TraductionManquante` | get_or_create | TraductionManquante.objects | cle, company, langue |
| `backend/django_core/apps/parametres/views_config.py::_import_document_templates::DocumentTemplates` | get_or_create | DocumentTemplates.objects | company |
| `backend/django_core/apps/parametres/views_email.py::EmailTemplateViewSet.bulk::EmailTemplate` | get_or_create | EmailTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_messages.py::_messages_save::MessageTemplate` | get_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_messages.py::_messages_save::MessageTemplate` | get_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_statuses.py::StatutConfigViewSet.bulk::StatutConfig` | get_or_create | StatutConfig.objects | cle, company, domaine |
| `backend/django_core/apps/parametres/views_translations.py::TranslationOverrideViewSet.bulk::TranslationOverride` | get_or_create | TranslationOverride.objects | company, key, locale |
| `backend/django_core/apps/portail/services.py::accepter_invitation_portail::Role` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/portail/services.py::provisionner_compte_partenaire::Role` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/portail/services.py::provisionner_compte_portail_client::ComptePortailClient` | get_or_create | ComptePortailClient.objects | client, company |
| `backend/django_core/apps/portail/services.py::provisionner_compte_portail_client::Role` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/portail/services.py::upsert_jalon_chantier::JalonChantierPortail` | update_or_create | JalonChantierPortail.objects | chantier_id, cle_phase, company |
| `backend/django_core/apps/portail/views_client.py::MesDevisPortailViewSet.accepter::AcceptationDevisPortail` | get_or_create | AcceptationDevisPortail.objects | company, devis |
| `backend/django_core/apps/portail/views_client.py::MesFacturesPortailViewSet.payer::PaiementFacturePortail` | get_or_create | PaiementFacturePortail.objects | company, facture, statut |
| `backend/django_core/apps/portail/views_externes.py::preference_portail::PreferencePortail` | update_or_create | PreferencePortail.objects | utilisateur |
| `backend/django_core/apps/records/services.py::follow::Follower` | get_or_create | Follower.objects | company, content_type, object_id, sous_type, user |
| `backend/django_core/apps/records/views.py::TaggedItemViewSet.create::TaggedItem` | get_or_create | TaggedItem.objects | content_type, object_id, tag |
| `backend/django_core/apps/reporting/calendar.py::regenerer_ics_token::JetonCalendrier` | get_or_create | JetonCalendrier.objects | user |
| `backend/django_core/apps/roles/management/commands/init_roles.py::Command.handle::Role` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/sav/models.py::SavSlaSettings.get::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/sav/services.py::abonner_suiveurs_globaux::TicketFollower` | get_or_create | TicketFollower.objects | company, ticket, user |
| `backend/django_core/apps/sav/views.py::TicketViewSet.checklist::TicketChecklistItem` | get_or_create | TicketChecklistItem.objects | cle, ticket |
| `backend/django_core/apps/sav/views.py::TicketViewSet.suivre::TicketFollower` | get_or_create | TicketFollower.objects | company, ticket, user |
| `backend/django_core/apps/statuspage/tasks.py::_accumuler_uptime_jour::UptimeDayBucket` | get_or_create | UptimeDayBucket.objects | company, composant, date, region |
| `backend/django_core/apps/statuspage/tasks.py::rafraichir_composants::ComponentStatus` | update_or_create | ComponentStatus.objects | company, nom, region |
| `backend/django_core/apps/statuspage/tasks.py::rafraichir_composants::ComponentStatus` | update_or_create | ComponentStatus.objects | company, nom, region |
| `backend/django_core/apps/statuspage/views.py::public_abonner::StatusSubscriber` | get_or_create | StatusSubscriber.objects | email |
| `backend/django_core/apps/stock/management/commands/backfill_unites_mesure.py::Command.handle::UniteMesure` | get_or_create | UniteMesure.objects | code, company |
| `backend/django_core/apps/stock/management/commands/seed_catalogue.py::Command.handle.get_categorie::Categorie` | get_or_create | Categorie.objects | company, nom |
| `backend/django_core/apps/stock/management/commands/seed_catalogue.py::Command.handle::Categorie` | get_or_create | Categorie.objects | company, nom |
| `backend/django_core/apps/stock/models.py::AchatsParametres.for_company::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/stock/models_negoce_params.py::ParametresNegoce.get::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/stock/services.py::alimenter_lot_entrepot::LotEntrepot` | get_or_create | LotEntrepot.objects.select_for_update() | company, numero_lot, produit |
| `backend/django_core/apps/stock/services.py::consommer_et_produire_assemblage::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::consommer_et_produire_assemblage::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::credit_emplacement_destination::StockEmplacement` | get_or_create | StockEmplacement.objects | company, emplacement, produit |
| `backend/django_core/apps/stock/services.py::demonter_composite::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::demonter_composite::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::get_or_create_emplacement_soustraitant::EmplacementStock` | get_or_create | EmplacementStock.objects | company, nom |
| `backend/django_core/apps/stock/services.py::provisionner_compte_fournisseur::Role` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/stock/services.py::rebuter_produit::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::record_purchase_price::PrixFournisseur` | get_or_create | PrixFournisseur.objects | fournisseur, produit |
| `backend/django_core/apps/stock/services.py::record_stock_movement::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::transfer_stock::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::transfer_stock::StockEmplacement` | get_or_create | StockEmplacement.objects | emplacement, produit |
| `backend/django_core/apps/stock/services.py::update_sous_traitant::SousTraitantProfile` | get_or_create | SousTraitantProfile.objects | fournisseur |
| `backend/django_core/apps/stock/services_transfert_deux_temps.py::expedier_transfert::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services_transfert_deux_temps.py::receptionner_transfert::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services_wms.py::assurer_plans_comptage_tournant::PlanComptageTournant` | get_or_create | PlanComptageTournant.objects | classe_abc, company |
| `backend/django_core/apps/stock/views/catalogue_achat.py::CatalogueAchatViewSet.favoris::FavorisCatalogueAchat` | get_or_create | FavorisCatalogueAchat.objects | company, utilisateur |
| `backend/django_core/apps/stock/views/marque.py::seed_marques::Marque` | get_or_create | Marque.objects | company, nom |
| `backend/django_core/apps/uxviews/models.py::UxParametres.get_or_default::cls` | get_or_create | cls.objects | company |
| `backend/django_core/apps/uxviews/views.py::FavoriUtilisateurViewSet.importer::FavoriUtilisateur` | get_or_create | FavoriUtilisateur.objects | company, content_type, object_id, owner |
| `backend/django_core/apps/uxviews/views.py::SavedViewViewSet.list::EcranRecent` | update_or_create | EcranRecent.objects | company, ecran, owner |
| `backend/django_core/apps/ventes/domain/facturation_ops.py::_main_oeuvre_produit::Produit` | get_or_create | Produit.objects | company, sku |
| `backend/django_core/apps/ventes/domain/gammes.py::get_parametres_gammes::ParametresGammes` | get_or_create | ParametresGammes.objects | company |
| `backend/django_core/apps/ventes/views/liste_prix.py::ListePrixViewSet.lignes::LignePrixListe` | update_or_create | LignePrixListe.objects | liste, produit |
| `backend/django_core/apps/ventes/views/remise_encaissement.py::RemiseEncaissementViewSet._creer_remise::LigneRemiseEncaissement` | get_or_create | LigneRemiseEncaissement.objects | paiement, remise |
