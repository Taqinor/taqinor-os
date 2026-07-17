# Audit get_or_create / update_or_create (YDATA15)

Généré par `python scripts/check_get_or_create.py`. Chaque appel liste ses clés de lookup (hors `defaults`) — chaque clé PARTAGÉE devrait correspondre à une `UniqueConstraint`/`unique_together` company-scopée sur le modèle cible pour être course-safe. Advisory : ce sweep ne corrige rien (correctifs = ERROR_PLAN).

| Fichier:ligne | Appel | Récepteur | Clés de lookup |
|---|---|---|---|
| `backend/django_core/apps/accessreview/sod.py:127` | get_or_create | SodRule.objects | company, permission_a, permission_b |
| `backend/django_core/apps/adsengine/brief.py:178` | update_or_create | WeeklyBrief.objects | company, period_start |
| `backend/django_core/apps/adsengine/flightrunner.py:375` | update_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/flightrunner.py:385` | update_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_adsengine.py:40` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/management/commands/seed_adsengine.py:68` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py:137` | update_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py:141` | update_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/management/commands/seed_synthetic_account.py:159` | update_or_create | AdMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/models.py:449` | update_or_create | cls.objects | company, content_type, date, dimension, key, object_id |
| `backend/django_core/apps/adsengine/models.py:908` | update_or_create | cls.objects | arm, company, date |
| `backend/django_core/apps/adsengine/models.py:1132` | update_or_create | cls.objects | company, period_start |
| `backend/django_core/apps/adsengine/policy.py:40` | get_or_create | CreativePolicy.objects | company |
| `backend/django_core/apps/adsengine/receivers.py:59` | update_or_create | MetaLeadMirror.objects | company, leadgen_id |
| `backend/django_core/apps/adsengine/reconciliation.py:350` | update_or_create | RS.objects | campaign, company, date |
| `backend/django_core/apps/adsengine/rule_templates.py:345` | get_or_create | RulePolicy.objects | company, template_key |
| `backend/django_core/apps/adsengine/simulator.py:85` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/sync.py:56` | get_or_create | AdCampaignMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:87` | get_or_create | AdSetMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:116` | get_or_create | AdMirror.objects | company, meta_id |
| `backend/django_core/apps/adsengine/sync.py:181` | update_or_create | AdCreativeMirror.objects | ad, company |
| `backend/django_core/apps/adsengine/sync.py:238` | update_or_create | InsightSnapshot.objects | company, content_type, date, object_id |
| `backend/django_core/apps/adsengine/views.py:1014` | get_or_create | MetaConnection.objects | company |
| `backend/django_core/apps/adsengine/views.py:1096` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/adsengine/views.py:1103` | get_or_create | GuardrailConfig.objects | company |
| `backend/django_core/apps/assurances/services.py:340` | update_or_create | IndemnisationSinistre.objects | declaration |
| `backend/django_core/apps/automation/views.py:400` | get_or_create | IncomingWebhookTrigger.objects | rule |
| `backend/django_core/apps/chat/services.py:152` | get_or_create | MessageMention.objects | mentioned_user, message |
| `backend/django_core/apps/chat/services.py:258` | get_or_create | UserChatStatus.objects | user |
| `backend/django_core/apps/chat/services.py:433` | get_or_create | Conversation.objects | company, kind, name |
| `backend/django_core/apps/chat/services.py:441` | get_or_create | ConversationMember.objects | conversation, user |
| `backend/django_core/apps/chat/services.py:466` | get_or_create | ThreadFollow.objects | root_message, user_id |
| `backend/django_core/apps/chat/services.py:469` | get_or_create | ThreadFollow.objects | root_message, user |
| `backend/django_core/apps/chat/services.py:512` | get_or_create | ThreadFollow.objects | root_message, user |
| `backend/django_core/apps/chat/services.py:868` | get_or_create | RetentionPolicy.objects | company, conversation_kind |
| `backend/django_core/apps/chat/views.py:73` | get_or_create | ConversationMember.objects | conversation, user |
| `backend/django_core/apps/chat/views.py:82` | get_or_create | ConversationMember.objects | conversation, user |
| `backend/django_core/apps/chat/views.py:170` | get_or_create | ConversationMember.objects | conversation, user |
| `backend/django_core/apps/compta/receivers.py:200` | get_or_create | EnqueteNPS.objects | chantier_id, company |
| `backend/django_core/apps/compta/services.py:213` | get_or_create | PlanComptable.objects | code, company |
| `backend/django_core/apps/compta/services.py:218` | get_or_create | CompteComptable.objects | company, numero |
| `backend/django_core/apps/compta/services.py:253` | get_or_create | Journal.objects | code, company |
| `backend/django_core/apps/compta/services.py:1141` | get_or_create | PeriodeComptable.objects | company, date_debut, date_fin |
| `backend/django_core/apps/compta/services.py:1456` | get_or_create | ExerciceComptable.objects | company, date_debut, date_fin |
| `backend/django_core/apps/compta/services.py:1520` | get_or_create | Journal.objects | code, company |
| `backend/django_core/apps/compta/services.py:1688` | get_or_create | Journal.objects | code, company |
| `backend/django_core/apps/compta/services.py:1820` | get_or_create | PlanAmortissement.objects | company, immobilisation |
| `backend/django_core/apps/compta/services.py:1986` | get_or_create | CompteComptable.objects | company, numero |
| `backend/django_core/apps/compta/services.py:3753` | get_or_create | Rapprochement.objects | bon_commande_id, company |
| `backend/django_core/apps/compta/services.py:4076` | get_or_create | ParametresTresorerie.objects | company |
| `backend/django_core/apps/compta/services.py:5430` | get_or_create | ObligationFiscale.objects | company, periode_debut, periode_fin, type_obligation |
| `backend/django_core/apps/compta/services.py:5436` | get_or_create | ObligationFiscale.objects | company, periode_debut, periode_fin, type_obligation |
| `backend/django_core/apps/compta/services.py:5448` | get_or_create | ObligationFiscale.objects | company, periode_debut, periode_fin, type_obligation |
| `backend/django_core/apps/compta/services.py:5463` | get_or_create | ObligationFiscale.objects | company, periode_debut, periode_fin, type_obligation |
| `backend/django_core/apps/compta/services.py:5477` | get_or_create | ObligationFiscale.objects | company, periode_debut, periode_fin, type_obligation |
| `backend/django_core/apps/compta/services.py:5482` | get_or_create | ObligationFiscale.objects | company, periode_debut, periode_fin, type_obligation |
| `backend/django_core/apps/compta/services.py:6231` | get_or_create | CentreCout.objects | code, company |
| `backend/django_core/apps/compta/services.py:6517` | get_or_create | EntiteConsolidation.objects | company, entite |
| `backend/django_core/apps/compta/services.py:6740` | update_or_create | StatutEngagementContact.objects | company, destinataire |
| `backend/django_core/apps/compta/services.py:6751` | update_or_create | StatutEngagementContact.objects | company, destinataire |
| `backend/django_core/apps/compta/services.py:7395` | get_or_create | RebondSoft.objects | company, destinataire |
| `backend/django_core/apps/compta/services.py:7577` | get_or_create | SuppressionMarketing.objects | company, destinataire |
| `backend/django_core/apps/compta/services.py:7627` | get_or_create | SuppressionMarketing.objects | company, destinataire |
| `backend/django_core/apps/compta/services.py:7812` | get_or_create | AbonnementListe.objects | destinataire, liste |
| `backend/django_core/apps/compta/services.py:8973` | get_or_create | OuverturePartage.objects | company, token |
| `backend/django_core/apps/compta/services.py:9013` | get_or_create | MessageWhatsAppEntrant.objects | company, wa_message_id |
| `backend/django_core/apps/compta/services.py:9902` | get_or_create | MappingCompte.objects | clef, company, type_clef |
| `backend/django_core/apps/compta/services.py:10761` | get_or_create | PlanAmortissementFiscal.objects | company, plan_comptable |
| `backend/django_core/apps/compta/services.py:11119` | update_or_create | LigneReevaluation.objects | item, reevaluation |
| `backend/django_core/apps/compta/services.py:11241` | get_or_create | VentilationAnalytique.objects | company, ligne_ecriture |
| `backend/django_core/apps/compta/services.py:12606` | update_or_create | LiasseRemontee.objects | company, cycle, entite |
| `backend/django_core/apps/compta/services.py:12951` | get_or_create | ReferentielComptable.objects | code, company |
| `backend/django_core/apps/contrats/management/commands/seed_motifs_resiliation.py:40` | get_or_create | MotifResiliation.objects | code, company |
| `backend/django_core/apps/contrats/management/commands/seed_plans_recurrents.py:34` | get_or_create | PlanRecurrent.objects | company, nom |
| `backend/django_core/apps/contrats/views.py:2527` | get_or_create | ParametresLocation.objects | company |
| `backend/django_core/apps/credit/services.py:224` | update_or_create | LimiteCredit.objects | client |
| `backend/django_core/apps/credit/tasks.py:76` | update_or_create | EncoursCache.objects | client |
| `backend/django_core/apps/credit/views.py:375` | get_or_create | ReglageCredit.objects | company |
| `backend/django_core/apps/crm/services.py:3247` | get_or_create | MessageTemplate.objects | company, nom |
| `backend/django_core/apps/crm/views.py:1395` | get_or_create | Canal.objects | cle, company |
| `backend/django_core/apps/dataimport/services.py:224` | update_or_create | ImportMapping.objects | company, entity, nom |
| `backend/django_core/apps/dataimport/services.py:261` | get_or_create | ExternalRef.objects | company, external_id, external_system |
| `backend/django_core/apps/education/models.py:755` | get_or_create | cls.objects | company |
| `backend/django_core/apps/education/services_planning.py:81` | get_or_create | Seance.objects | classe, company, date, heure_debut, matiere |
| `backend/django_core/apps/education/viewsets.py:426` | update_or_create | Presence.objects | company, eleve, seance |
| `backend/django_core/apps/education/viewsets.py:499` | update_or_create | Note.objects | company, eleve, evaluation |
| `backend/django_core/apps/flotte/management/commands/seed_baremes_vignette.py:75` | get_or_create | BaremeVignette.objects | annee, company, cv_max, cv_min, energie |
| `backend/django_core/apps/flotte/management/commands/seed_referentiels_flotte.py:79` | get_or_create | ReferentielFlotte.objects | code, company, domaine |
| `backend/django_core/apps/fpa/services.py:68` | get_or_create | SoumissionBudgetDepartement.objects | company, cycle, departement |
| `backend/django_core/apps/fpa/services.py:228` | update_or_create | LignePrevisionGlissante.objects | categorie, company, mois_relatif, prevision |
| `backend/django_core/apps/fpa/views.py:292` | get_or_create | PrevisionGlissante.objects | company, date_reference, departement_id |
| `backend/django_core/apps/ged/management/commands/migrate_attachments_to_ged.py:57` | get_or_create | Cabinet.objects | company, nom |
| `backend/django_core/apps/ged/management/commands/migrate_attachments_to_ged.py:163` | get_or_create | DocumentLien.objects | content_type, document, object_id |
| `backend/django_core/apps/ged/management/commands/seed_types_champ_signature.py:30` | get_or_create | TypeChampSignature.objects | code, company |
| `backend/django_core/apps/ged/services.py:323` | update_or_create | ValidationOcrDocument.objects | document |
| `backend/django_core/apps/ged/services.py:671` | get_or_create | DocumentTagAssignment.objects | document, tag |
| `backend/django_core/apps/ged/services.py:844` | get_or_create | Cabinet.objects | company, nom |
| `backend/django_core/apps/ged/services.py:3663` | get_or_create | DocumentLien.objects | company, content_type, document, object_id |
| `backend/django_core/apps/ged/services.py:4270` | get_or_create | DocumentTag.objects | company, slug |
| `backend/django_core/apps/ged/services.py:5502` | get_or_create | Folder.objects | cabinet, company, nom, parent |
| `backend/django_core/apps/ged/views.py:1860` | get_or_create | DocumentLien.objects | content_type, document, object_id |
| `backend/django_core/apps/gestion_projet/services.py:520` | update_or_create | ClotureProjet.objects | projet |
| `backend/django_core/apps/gestion_projet/services.py:937` | update_or_create | Indisponibilite.objects | company, motif, ressource |
| `backend/django_core/apps/gestion_projet/services.py:1052` | get_or_create | ReglageTemps.objects | company |
| `backend/django_core/apps/gestion_projet/services.py:1322` | get_or_create | JourFerie.objects | calendrier, company, date |
| `backend/django_core/apps/gestion_projet/views.py:563` | get_or_create | EvaluationProjet.objects | company, projet |
| `backend/django_core/apps/innovation/services.py:139` | get_or_create | InnovationSettings.objects | company |
| `backend/django_core/apps/innovation/services.py:180` | get_or_create | Tag.objects | company, nom |
| `backend/django_core/apps/innovation/services.py:186` | get_or_create | TaggedItem.objects | content_type, object_id, tag |
| `backend/django_core/apps/innovation/views.py:527` | get_or_create | InnovationSettings.objects | company |
| `backend/django_core/apps/installations/field_capture.py:79` | get_or_create | MaterielConsommation.objects | intervention |
| `backend/django_core/apps/installations/field_capture.py:334` | get_or_create | SafetyChecklistSlot.objects | cle, company |
| `backend/django_core/apps/installations/field_capture.py:344` | get_or_create | SafetySignoff.objects | intervention |
| `backend/django_core/apps/installations/field_services.py:54` | get_or_create | ShotListSlot.objects | cle, company |
| `backend/django_core/apps/installations/field_services.py:156` | get_or_create | InterventionPreparation.objects | intervention |
| `backend/django_core/apps/installations/field_services.py:350` | get_or_create | FicheInterventionReleve.objects | intervention |
| `backend/django_core/apps/installations/services.py:102` | get_or_create | ChecklistEtapeModele.objects | cle, company, template |
| `backend/django_core/apps/installations/services.py:360` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py:604` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py:689` | get_or_create | StockReservation.objects | installation, produit_id |
| `backend/django_core/apps/installations/services.py:1026` | get_or_create | StageModele.objects | cle, company |
| `backend/django_core/apps/installations/services.py:1520` | get_or_create | CommissioningRecord.objects | installation |
| `backend/django_core/apps/installations/services.py:1729` | get_or_create | HandoverPack.objects | installation |
| `backend/django_core/apps/installations/services.py:1791` | get_or_create | ReservationAssemblage.objects | ordre, produit_id |
| `backend/django_core/apps/installations/services.py:2619` | get_or_create | SerieEntrepot.objects | company, numero_serie, produit_id |
| `backend/django_core/apps/installations/services.py:2796` | get_or_create | JalonProjet.objects | installation, phase |
| `backend/django_core/apps/installations/services.py:2881` | get_or_create | EmplacementStock.objects | company, nom |
| `backend/django_core/apps/installations/views/approbation_bcf.py:100` | update_or_create | ApprobationBCF.objects | bcf, company |
| `backend/django_core/apps/installations/views/checklist_etape.py:103` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/checklist_template.py:103` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/installation.py:151` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/intervention.py:105` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/intervention.py:950` | get_or_create | PhotoAnnotation.objects | attachment |
| `backend/django_core/apps/installations/views/intervention.py:1495` | get_or_create | ToolReturn.objects | intervention, outil_id |
| `backend/django_core/apps/installations/views/program.py:120` | get_or_create | link_model.objects | projet |
| `backend/django_core/apps/installations/views/rfq.py:204` | get_or_create | RFQConsultation.objects | fournisseur, rfq |
| `backend/django_core/apps/installations/views/safety.py:103` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/shotlist.py:102` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/installations/views/type_intervention.py:102` | get_or_create | TypeIntervention.objects | cle, company |
| `backend/django_core/apps/kb/management/commands/seed_kb_templates.py:295` | get_or_create | KbArticle.objects | company, titre |
| `backend/django_core/apps/kb/services.py:37` | get_or_create | KbLecture.objects | article, utilisateur |
| `backend/django_core/apps/monitoring/models.py:197` | get_or_create | cls.objects | company |
| `backend/django_core/apps/monitoring/services.py:35` | get_or_create | MonitoringConfig.objects | installation |
| `backend/django_core/apps/monitoring/services.py:182` | get_or_create | UnderperformanceFlag.objects | installation, is_open |
| `backend/django_core/apps/notifications/management/commands/seed_ma_holidays.py:72` | get_or_create | Holiday.objects | company, date, nom |
| `backend/django_core/apps/notifications/services.py:842` | get_or_create | AnnonceLecture.objects | annonce, utilisateur |
| `backend/django_core/apps/notifications/services.py:929` | get_or_create | AnnonceRelance.objects | annonce, utilisateur |
| `backend/django_core/apps/notifications/services.py:978` | get_or_create | ApprovalReminderState.objects | content_type, object_id |
| `backend/django_core/apps/notifications/services.py:1102` | update_or_create | SnoozedItem.objects | object_id, source, user |
| `backend/django_core/apps/notifications/views.py:137` | get_or_create | NotificationPreference.objects | event_type, user |
| `backend/django_core/apps/notifications/views.py:221` | get_or_create | WorkingHoursConfig.objects | company |
| `backend/django_core/apps/notifications/views.py:436` | update_or_create | PushSubscription.objects | endpoint |
| `backend/django_core/apps/outillage/views.py:32` | get_or_create | KitOutillage.objects | company, nom |
| `backend/django_core/apps/paie/services.py:117` | get_or_create | ParametrePaie.objects | company, date_effet |
| `backend/django_core/apps/paie/services.py:125` | get_or_create | BaremeIR.objects | company, date_effet |
| `backend/django_core/apps/paie/services.py:299` | get_or_create | Rubrique.objects | code, company |
| `backend/django_core/apps/paie/services.py:372` | get_or_create | TypeEntreePonctuelle.objects | code, company |
| `backend/django_core/apps/paie/services.py:2749` | get_or_create | EcheanceDeclarative.objects | company, periode, type_echeance |
| `backend/django_core/apps/paie/services.py:4940` | get_or_create | CumulAnnuel.objects.select_for_update() | annee, company, profil |
| `backend/django_core/apps/paie/services.py:5627` | get_or_create | StructurePaie.objects | code, company |
| `backend/django_core/apps/paie/services.py:5637` | get_or_create | StructurePaieRubrique.objects | rubrique, structure |
| `backend/django_core/apps/paie/services.py:5663` | get_or_create | RubriqueEmploye.objects | profil, rubrique |
| `backend/django_core/apps/parametres/models_company.py:640` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_company.py:645` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_documents.py:100` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_documents.py:102` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_payment_terms.py:89` | get_or_create | cls.objects | company, delai_jours, escompte_pct, fin_de_mois |
| `backend/django_core/apps/parametres/models_tariff.py:137` | get_or_create | cls.objects | company |
| `backend/django_core/apps/parametres/models_tariff.py:139` | get_or_create | cls.objects | pk |
| `backend/django_core/apps/parametres/models_taxes.py:103` | get_or_create | cls.objects | code, company |
| `backend/django_core/apps/parametres/models_units.py:83` | get_or_create | cls.objects | code, company |
| `backend/django_core/apps/parametres/views_config.py:163` | get_or_create | DocumentTemplates.objects | company |
| `backend/django_core/apps/parametres/views_email.py:124` | get_or_create | EmailTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_messages.py:106` | get_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_messages.py:136` | get_or_create | MessageTemplate.objects | cle, company |
| `backend/django_core/apps/parametres/views_statuses.py:138` | get_or_create | StatutConfig.objects | cle, company, domaine |
| `backend/django_core/apps/parametres/views_translations.py:130` | get_or_create | TranslationOverride.objects | company, key, locale |
| `backend/django_core/apps/publicapi/idempotency.py:64` | get_or_create | IdempotencyRecord.objects | api_key, endpoint, idempotency_key |
| `backend/django_core/apps/qhse/management/commands/seed_aspects_environnementaux_solaire.py:72` | get_or_create | AspectEnvironnemental.objects | activite, aspect, company |
| `backend/django_core/apps/qhse/management/commands/seed_clauses_norme.py:87` | get_or_create | ClauseNorme.objects | company, numero, referentiel |
| `backend/django_core/apps/qhse/management/commands/seed_codes_defaut_solaire.py:79` | get_or_create | CodeDefaut.objects | code, company |
| `backend/django_core/apps/qhse/management/commands/seed_exigences_maroc.py:107` | get_or_create | ConformiteEnvironnementale.objects | company, intitule |
| `backend/django_core/apps/qhse/management/commands/seed_itp_solaire.py:205` | get_or_create | PlanInspectionModele.objects | code, company |
| `backend/django_core/apps/qhse/management/commands/seed_itp_solaire.py:221` | get_or_create | PointControleModele.objects | company, ordre, plan |
| `backend/django_core/apps/qhse/services.py:51` | get_or_create | PlanInspectionChantier.objects | chantier_id, company, modele |
| `backend/django_core/apps/qhse/services.py:1080` | get_or_create | ControleReception.objects | company, plan, reception_id |
| `backend/django_core/apps/qhse/services.py:1457` | get_or_create | AnalyseNcr.objects | company, non_conformite |
| `backend/django_core/apps/qhse/services.py:1846` | get_or_create | RisqueOpportuniteCapa.objects | capa, company, risque_opportunite |
| `backend/django_core/apps/qhse/services.py:1912` | get_or_create | AccuseLecture.objects | company, diffusion, user |
| `backend/django_core/apps/qhse/services.py:1928` | get_or_create | AccuseLecture.objects | company, diffusion, user |
| `backend/django_core/apps/qhse/services.py:2440` | update_or_create | LigneBilanCarbone.objects | bilan, company, libelle |
| `backend/django_core/apps/qhse/services.py:2579` | get_or_create | DemandeChangementCapa.objects | capa, company, demande_changement |
| `backend/django_core/apps/records/services.py:104` | get_or_create | Follower.objects | company, content_type, object_id, sous_type, user |
| `backend/django_core/apps/records/views.py:986` | get_or_create | TaggedItem.objects | content_type, object_id, tag |
| `backend/django_core/apps/rh/services.py:114` | get_or_create | SoldeConge.objects.select_for_update() | annee, company, employe |
| `backend/django_core/apps/rh/services.py:151` | get_or_create | SoldeConge.objects.select_for_update() | annee, company, employe |
| `backend/django_core/apps/rh/services.py:421` | get_or_create | SoldeConge.objects | annee, company, employe |
| `backend/django_core/apps/rh/services.py:453` | get_or_create | SoldeConge.objects.select_for_update() | annee, company, employe |
| `backend/django_core/apps/rh/services.py:2379` | update_or_create | InscriptionFormation.objects | participant, session |
| `backend/django_core/apps/rh/services.py:2472` | get_or_create | SoldeConge.objects.select_for_update() | annee, company, employe |
| `backend/django_core/apps/rh/services.py:2529` | update_or_create | CompetenceEmploye.objects | company, competence_id, employe |
| `backend/django_core/apps/rh/services.py:2560` | get_or_create | CampagneEvaluation.objects | annee, company, intitule |
| `backend/django_core/apps/rh/services.py:2671` | get_or_create | EvaluationEmploye.objects | campagne, company, employe |
| `backend/django_core/apps/rh/views.py:1782` | get_or_create | ReglageRH.objects | company |
| `backend/django_core/apps/rh/views.py:3949` | update_or_create | NoteEntretien.objects | entretien, evaluateur |
| `backend/django_core/apps/roles/management/commands/init_roles.py:53` | get_or_create | Role.objects | company, nom |
| `backend/django_core/apps/sante/models.py:708` | get_or_create | cls.objects | company |
| `backend/django_core/apps/sav/models.py:138` | get_or_create | cls.objects | company |
| `backend/django_core/apps/sav/services.py:1055` | get_or_create | TicketFollower.objects | company, ticket, user |
| `backend/django_core/apps/sav/views.py:1229` | get_or_create | TicketFollower.objects | company, ticket, user |
| `backend/django_core/apps/sav/views.py:1711` | get_or_create | TicketChecklistItem.objects | cle, ticket |
| `backend/django_core/apps/stock/management/commands/backfill_unites_mesure.py:52` | get_or_create | UniteMesure.objects | code, company |
| `backend/django_core/apps/stock/management/commands/seed_catalogue.py:391` | get_or_create | Categorie.objects | company, nom |
| `backend/django_core/apps/stock/management/commands/seed_catalogue.py:550` | get_or_create | Categorie.objects | company, nom |
| `backend/django_core/apps/stock/models.py:411` | get_or_create | cls.objects | company |
| `backend/django_core/apps/stock/services.py:197` | get_or_create | EmplacementStock.objects | company, nom |
| `backend/django_core/apps/stock/services.py:316` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:322` | get_or_create | StockEmplacement.objects | emplacement, produit |
| `backend/django_core/apps/stock/services.py:357` | get_or_create | PrixFournisseur.objects | fournisseur, produit |
| `backend/django_core/apps/stock/services.py:387` | get_or_create | StockEmplacement.objects | company, emplacement, produit |
| `backend/django_core/apps/stock/services.py:1186` | get_or_create | LotEntrepot.objects | company, numero_lot, produit |
| `backend/django_core/apps/stock/services.py:1348` | get_or_create | SousTraitantProfile.objects | fournisseur |
| `backend/django_core/apps/stock/services.py:1730` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:1900` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3583` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3602` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3649` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:3675` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py:5090` | get_or_create | PrixFournisseur.objects | fournisseur, produit |
| `backend/django_core/apps/stock/services.py:5103` | update_or_create | PalierPrixFournisseur.objects | prix_fournisseur, qte_min |
| `backend/django_core/apps/stock/views/marque.py:57` | get_or_create | Marque.objects | company, nom |
| `backend/django_core/apps/ventes/services.py:2456` | get_or_create | Produit.objects | company, nom |
| `backend/django_core/apps/ventes/services.py:3790` | get_or_create | Produit.objects | company, sku |
| `backend/django_core/apps/ventes/views/liste_prix.py:72` | update_or_create | LignePrixListe.objects | liste, produit_id |
| `backend/django_core/apps/ventes/views/remise_encaissement.py:81` | get_or_create | LigneRemiseEncaissement.objects | paiement, remise |
| `backend/django_core/apps/voip/services.py:26` | get_or_create | VoipParametres.objects | company |
| `backend/django_core/apps/voip/services.py:128` | get_or_create | ActivityType.objects | company, nom |
| `backend/django_core/apps/voip/views.py:46` | get_or_create | VoipIdentifiantUtilisateur.objects | company, utilisateur |
| `backend/django_core/apps/voip/views.py:51` | get_or_create | VoipIdentifiantUtilisateur.objects | company, utilisateur |
