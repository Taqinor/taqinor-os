# Contrat des reponses agregees — GENERE, ne pas editer a la main.
#
# Regenerer : `python scripts/check_api_shapes.py --write`
#
# Chaque ligne est la forme REELLE du dictionnaire renvoye par le serveur,
# lue dans le code (vue -> selecteur -> dictionnaire), pour un endpoint que le
# frontend appelle. C'est le document qui manquait le 03/08/2026 : la moitie
# frontend et la moitie backend d'une meme fonctionnalite n'avaient pas la
# meme forme sous les yeux, et le test de l'ecran mockait l'INVERSE EXACT de
# ce que le serveur renvoyait — les deux suites vertes, l'ecran mort.
#
# Un changement de forme cote serveur DOIT apparaitre ici, dans le diff de la
# PR. `scripts/check_api_shapes.py` echoue si un mock de test contredit cette
# liste (champ inexistant, ou nature incompatible).


- frontend/src/api/accessReviewApi.js :: seedStandard -> /api/django/accessreview/sod-rules/seed_standard
    created:inconnu
- frontend/src/api/accessReviewApi.js :: violations -> /api/django/accessreview/sod-rules/violations
    results:inconnu
- frontend/src/api/adminopsApi.js :: ciblesImpersonation -> /api/django/adminops/impersonation/cibles
    societes:liste, utilisateurs:liste
- frontend/src/api/adminopsApi.js :: demarrerImpersonation -> /api/django/adminops/impersonation/<>/demarrer
    access:inconnu, detail:texte, session:inconnu
- frontend/src/api/adminopsApi.js :: listAnnonces -> /api/django/adminops/annonces
    non_lues:nombre, results:inconnu
- frontend/src/api/adminopsApi.js :: listFacturationLicences -> /api/django/adminops/facturation-licences
    results:inconnu, total_du_ttc:inconnu
- frontend/src/api/adminopsApi.js :: sessionImpersonationActive -> /api/django/adminops/impersonation/session-active
    active:booleen, expire_le:inconnu, id:inconnu, message:texte, motif:inconnu, support_nom:inconnu
- frontend/src/api/auditApi.js :: getMeta -> /api/django/audit/meta
    actions:liste, modules:liste, users:liste
- frontend/src/api/auditApi.js :: getObjectAsOf -> /api/django/audit/objets/<>/<>/as-of
    as_of:inconnu, content_type:inconnu, covered_changes:inconnu, detail:texte, fields:inconnu, object_id:texte
- frontend/src/api/auditApi.js :: getObjectHistory -> /api/django/audit/objets/<>/<>/history
    count:nombre, detail:texte, results:inconnu
- frontend/src/api/auditApi.js :: getSecurityEvents -> /api/django/audit/security
    count:nombre, results:inconnu
- frontend/src/api/auditApi.js :: getStats -> /api/django/audit/stats
    buckets:inconnu, date:texte, granularity:inconnu, period:inconnu, total:inconnu
- frontend/src/api/automationApi.js :: proposeDraft -> /api/django/agent/actions/automation-draft
    action_type:inconnu, detail:texte, enabled:inconnu, id:inconnu, nom:inconnu, trigger_type:inconnu
- frontend/src/api/calepinageApi.js :: pose -> /api/django/calepinage/moteur/pose
    engageable:inconnu, hash_entree:inconnu, kwc:inconnu, marges:inconnu, motifs_non_engageable:inconnu, plans:inconnu, preuve:inconnu, repere:inconnu, schema_version:inconnu, total_modules:inconnu, verdict:inconnu, version_moteur:inconnu
- frontend/src/api/calepinageApi.js :: profilsTypes -> /api/django/calepinage/parametres/profils-types
    profils:inconnu
- frontend/src/api/calepinageApi.js :: resultat -> /api/django/calepinage/moteur/resultat/<>
    detail:texte, elements:liste, job_id:inconnu, kind:inconnu, message_erreur:texte, progress_pct:inconnu, resultat:inconnu, statut:inconnu, variante:inconnu
- frontend/src/api/calepinageApi.js :: suggestionPenteDisponible -> /api/django/calepinage/parametres/suggestion-pente
    detail:texte, disponible:inconnu, pays_couvert:inconnu, source:inconnu, source_url:inconnu, suggestions:liste
- frontend/src/api/coreApi.js :: activer -> /api/django/core/modules/<>/activer
    actives:inconnu, detail:texte
- frontend/src/api/coreApi.js :: appliquer -> /api/django/core/bulk-edit/appliquer
    detail:texte, modifies:inconnu
- frontend/src/api/coreApi.js :: delier -> /api/django/core/dossiers/<>/delier
    detache:booleen, detail:texte
- frontend/src/api/coreApi.js :: desactiver -> /api/django/core/modules/<>/desactiver
    dependants:inconnu, desactives:inconnu, detail:texte
- frontend/src/api/coreApi.js :: getPublic -> /api/django/core/dashboards-partages/public/<>
    description:inconnu, detail:texte, layout:inconnu, titre:inconnu
- frontend/src/api/coreApi.js :: installer -> /api/django/core/workflow-templates/installer
    code:inconnu, created:inconnu, definition_id:inconnu, detail:texte, nb_etapes:nombre, nom:inconnu
- frontend/src/api/coreApi.js :: listPending -> /api/django/reporting/approbations-en-attente
    items:inconnu, total:nombre
- frontend/src/api/coreApi.js :: run -> /api/django/core/jobs/run
    detail:texte, status:texte, task:inconnu, task_id:inconnu
- frontend/src/api/crmApi.js :: arreterCadence -> /api/django/crm/leads/<>/relance/arreter
    arretees:inconnu, cadences:texte, motif:texte
- frontend/src/api/crmApi.js :: bulkLeads -> /api/django/crm/leads/bulk
    count:nombre, detail:texte, ok:booleen, op:texte, queue:inconnu, skipped:inconnu, total:nombre, unchanged:inconnu, updated:inconnu
- frontend/src/api/crmApi.js :: checkDevisAuto -> /api/django/crm/leads/<>/devis-auto
    detail:inconnu, ok:booleen
- frontend/src/api/crmApi.js :: clientDataExport -> /api/django/crm/clients/<>/data-export
    documents:inconnu, identite:inconnu
- frontend/src/api/crmApi.js :: confirmerAppointmentWhatsapp -> /api/django/crm/appointments/<>/confirmer-whatsapp
    detail:texte, ics_url:inconnu, message:inconnu, wa_url:inconnu
- frontend/src/api/crmApi.js :: convertirLeadEnClient -> /api/django/crm/leads/<>/convertir-client
    client:inconnu, detail:texte, mode:inconnu
- frontend/src/api/crmApi.js :: deleteLead -> /api/django/crm/leads/<>
    corbeille_id:inconnu, detail:texte, id:inconnu
- frontend/src/api/crmApi.js :: getClientConsolidation -> /api/django/crm/clients/<>/consolidation
    ca_devis_total:texte, ca_factures_total:texte, filiales:liste, nb_devis_total:inconnu, nb_factures_total:inconnu
- frontend/src/api/crmApi.js :: getComptesDormants -> /api/django/crm/clients/dormants
    count:nombre, results:inconnu, seuil:inconnu
- frontend/src/api/crmApi.js :: getEquipesStatistiques -> /api/django/crm/equipes/statistiques
    equipes:inconnu
- frontend/src/api/crmApi.js :: getKpiAdherence -> /api/django/crm/relance-etapes/kpi-adherence
    a_lheure_pct:inconnu, absences_declarees:inconnu, annulees_moteur:nombre, conversion_par_stage:inconnu, leads_sans_touche:inconnu, par_etape:inconnu, periode_jours:inconnu, sautees_humaines:nombre, tendance_a_lheure:inconnu, touches_en_retard_ouvertes:nombre, touches_faites:nombre, vitesse_premier_contact:inconnu
- frontend/src/api/crmApi.js :: getLeadJalonsDevis -> /api/django/crm/leads/<>/jalons-devis
    results:inconnu
- frontend/src/api/crmApi.js :: getLeadPhotoToit -> /api/django/crm/leads/<>/photo-toit
    texture_calage:inconnu, url:inconnu, visite_id:inconnu
- frontend/src/api/crmApi.js :: getLeadPointsContact -> /api/django/crm/leads/<>/points-contact
    count:inconnu, cout_total:inconnu, first_touch:inconnu, last_touch:inconnu, lead_id:inconnu, timeline:inconnu
- frontend/src/api/crmApi.js :: getLeadVisites -> /api/django/crm/leads/<>/visites
    visites:inconnu
- frontend/src/api/crmApi.js :: getMesStatsRelance -> /api/django/crm/relance-etapes/mes-stats
    a_faire_maintenant:inconnu, a_lheure_7j_pct:inconnu, cadences_completees_14j:inconnu, en_retard:inconnu, serie_jours_sans_retard:inconnu
- frontend/src/api/crmApi.js :: getMonPortefeuille -> /api/django/crm/clients/mon-portefeuille
    count:nombre, results:inconnu
- frontend/src/api/crmApi.js :: getRelanceEtapeMessage -> /api/django/crm/relance-etapes/<>/message
    crochets:inconnu, langue:inconnu, message:inconnu, phone:inconnu, placeholders_manquants:inconnu, repli_langue:inconnu, wa_url:inconnu
- frontend/src/api/crmApi.js :: getRelanceEtapeMessageLangue -> /api/django/crm/relance-etapes/<>/message
    crochets:inconnu, langue:inconnu, message:inconnu, phone:inconnu, placeholders_manquants:inconnu, repli_langue:inconnu, wa_url:inconnu
- frontend/src/api/crmApi.js :: getRelanceEtapesDues -> /api/django/crm/relance-etapes
    count:nombre, results:inconnu
- frontend/src/api/crmApi.js :: getRelanceEtapesLead -> /api/django/crm/relance-etapes
    count:nombre, results:inconnu
- frontend/src/api/crmApi.js :: getRelances -> /api/django/crm/leads/relances
    count:nombre, results:inconnu
- frontend/src/api/crmApi.js :: getSlaBreach -> /api/django/crm/leads/sla-breach
    count:nombre, results:inconnu, sla_hours:inconnu
- frontend/src/api/crmApi.js :: mintQuestionnaireLien -> /api/django/crm/leads/<>/questionnaire-lien
    detail:texte, expires_at:texte, manquantes:inconnu, questions:inconnu, token:inconnu, url:inconnu, url_interne:inconnu
- frontend/src/api/crmApi.js :: parrainageStats -> /api/django/crm/parrainages/stats
    par_statut:inconnu, recompenses_total:texte, recompenses_versees:texte, total:inconnu
- frontend/src/api/crmApi.js :: renderMessageTemplate -> /api/django/crm/message-templates/<>/render
    texte:inconnu
- frontend/src/api/crmApi.js :: replayWebsiteLeadPayload -> /api/django/crm/website-lead-payloads/<>/replay
    detail:inconnu, payload:inconnu
- frontend/src/api/crmApi.js :: resoudreGps -> /api/django/crm/leads/resoudre-gps
    detail:texte, gps_lat:texte, gps_lng:texte, precision:inconnu
- frontend/src/api/crmApi.js :: restaurerCorbeille -> /api/django/core/corbeille/<>/restaurer
    record:inconnu, restored:booleen
- frontend/src/api/crmApi.js :: scanCarteVisite -> /api/django/crm/leads/scan-carte
    detail:inconnu, doublons:inconnu, email:inconnu, nom:inconnu, prenom:inconnu, societe:inconnu, telephone:inconnu
- frontend/src/api/crmApi.js :: searchClients -> /api/django/crm/clients/search
    results:inconnu
- frontend/src/api/crmApi.js :: villeStatut -> /api/django/crm/leads/ville-statut
    candidats:inconnu, gps_hors_zone:inconnu, position:inconnu, proches:inconnu, statut:inconnu, ville_canonique:inconnu
- frontend/src/api/crmApi.js :: whatsappDevis -> /api/django/crm/leads/<>/whatsapp-devis
    detail:texte, links:inconnu, message:inconnu, phone:inconnu, wa_url:inconnu
- frontend/src/api/crmApi.js :: whatsappRelanceEtape -> /api/django/crm/relance-etapes/<>/whatsapp
    crochets:inconnu, detail:texte, etape:inconnu, langue:inconnu, message:inconnu, phone:inconnu, placeholders_manquants:inconnu, repli_langue:inconnu, wa_url:inconnu
- frontend/src/api/crmApi.js :: whatsappRelanceEtapeLangue -> /api/django/crm/relance-etapes/<>/whatsapp
    crochets:inconnu, detail:texte, etape:inconnu, langue:inconnu, message:inconnu, phone:inconnu, placeholders_manquants:inconnu, repli_langue:inconnu, wa_url:inconnu
- frontend/src/api/customFieldsApi.js :: reorder -> /api/django/custom-fields/definitions/reorder
    count:nombre, detail:texte, ok:booleen
- frontend/src/api/demoApi.js :: resetDemo -> /api/django/companies/<>/reset-demo
    detail:texte, slug:inconnu
- frontend/src/api/gedApi.js :: comparerVersions -> /api/django/ged/documents/<>/comparer
    detail:texte, diff_texte:inconnu, message:texte, metadonnees:inconnu, texte_disponible:booleen
- frontend/src/api/gedApi.js :: docqa -> /api/django/ged/documents/docqa
    enabled:inconnu, results:inconnu
- frontend/src/api/gedApi.js :: dossierPreuveArchivage -> /api/django/ged/archivages-legaux/<>/dossier-preuve
    archive_le:inconnu, controles:liste, document:inconnu, hash_integrite_au_depot:inconnu, motif:inconnu
- frontend/src/api/gedApi.js :: genererModele -> /api/django/ged/modeles-document/<>/generer
    created:inconnu, detail:texte, document:inconnu, document_nom:inconnu
- frontend/src/api/gedApi.js :: getAnalytique -> /api/django/ged/analytique
    approbations:inconnu, signatures:inconnu
- frontend/src/api/gedApi.js :: getMesFavoris -> /api/django/ged/mes-favoris
    documents:inconnu, dossiers:inconnu
- frontend/src/api/gedApi.js :: getMesRecents -> /api/django/ged/mes-recents
    consultes:inconnu, deposes:inconnu
- frontend/src/api/gedApi.js :: getQuotaEtat -> /api/django/ged/quotas-stockage/etat
    depasse:inconnu, illimite:booleen, quota_octets:inconnu, restant_octets:inconnu, usage_octets:inconnu
- frontend/src/api/gedApi.js :: getTableauBordSignatures -> /api/django/ged/demandes-signature/tableau-bord
    colonnes:inconnu, total:inconnu
- frontend/src/api/gedApi.js :: leverLegalHold -> /api/django/ged/legal-holds/<>/lever
    detail:texte, leves:inconnu
- frontend/src/api/gedApi.js :: ocrPiece -> /api/django/ged/documents/<>/ocr-piece
    detail:inconnu, document:inconnu, en_validation:inconnu, metadonnees:inconnu, ocr_enabled:inconnu
- frontend/src/api/gedApi.js :: officeOuvrir -> /api/django/ged/documents/<>/office-ouvrir
    detail:texte, document_id:inconnu, editor_url:inconnu
- frontend/src/api/gedApi.js :: purgerDocument -> /api/django/ged/documents/<>/purger
    detail:texte
- frontend/src/api/gedApi.js :: scanLot -> /api/django/ged/documents/scan-lot
    detail:texte, documents:inconnu, erreurs:inconnu, files:texte, folder:texte
- frontend/src/api/gedApi.js :: semanticSearch -> /api/django/ged/documents/semantique
    mode:texte, results:inconnu
- frontend/src/api/gedApi.js :: toggleFavoriDocument -> /api/django/ged/documents/<>/favori
    favori:booleen
- frontend/src/api/gedApi.js :: verifierIntegriteArchives -> /api/django/ged/archivages-legaux/verifier-integrite
    altere:nombre, indisponible:nombre, ok:nombre, total:nombre
- frontend/src/api/iaApi.js :: getAgentActionLogs -> /api/django/agent/logs
    count:nombre, results:inconnu
- frontend/src/api/iaApi.js :: getAgentActions -> /api/django/agent/actions
    actions:inconnu, count:nombre
- frontend/src/api/iaApi.js :: undoAgentAction -> /api/django/agent/logs/<>/annuler
    action_key:inconnu, confirmed_at:inconnu, detail:texte, executed_at:inconnu, id:inconnu, is_undoable:inconnu, object_repr:inconnu, risk_level:inconnu, undone_at:inconnu, user:inconnu
- frontend/src/api/identityApi.js :: acknowledge -> /api/django/identity/login-banner
    acknowledged:booleen
- frontend/src/api/identityApi.js :: get -> /api/django/identity/login-banner
    login_banner_text:texte
- frontend/src/api/identityApi.js :: grant -> /api/django/identity/break-glass
    active_jusqu_a:inconnu, detail:texte, id:inconnu
- frontend/src/api/identityApi.js :: posture -> /api/django/identity/posture
    active_sessions:inconnu, dormant_accounts:inconnu, expired_secrets:inconnu, ip_allowlist_active:inconnu, items_faibles:inconnu, mfa_pct:inconnu, overdue_review_campaigns:inconnu, score:inconnu, soc2_iso27001_ready:booleen, sod_open_violations:inconnu, sso_configured:inconnu
- frontend/src/api/importApi.js :: getExportObjects -> /api/django/imports/export-objects
    default_format:inconnu, formats:liste, objects:inconnu
- frontend/src/api/importApi.js :: saveMapping -> /api/django/imports/mapping
    detail:texte, id:inconnu, mapping:inconnu, nom:inconnu, target:inconnu
- frontend/src/api/installationsApi.js :: ajouterPhoto -> /api/django/installations/interventions/<>/ajouter-photo
    detail:inconnu, filename:inconnu, id:inconnu, phase:inconnu, slot:inconnu, url:texte
- frontend/src/api/installationsApi.js :: appliquerCoutStockDossier -> /api/django/installations/dossiers-import/<>/appliquer-cout-stock
    bon_commande_id:inconnu, detail:texte, lignes:inconnu, lignes_maj:inconnu
- frontend/src/api/installationsApi.js :: besoinMateriel -> /api/django/installations/chantiers/<>/besoin-materiel
    installation:inconnu, items:inconnu, nb_manques:nombre, reference:inconnu
- frontend/src/api/installationsApi.js :: cocherChecklist -> /api/django/installations/chantiers/<>/cocher-checklist
    completion:inconnu, detail:texte, equipements_crees:inconnu, items:inconnu
- frontend/src/api/installationsApi.js :: confirmerToolReturn -> /api/django/installations/interventions/<>/confirmer-tool-return
    non_rendus:inconnu, tool_returns:inconnu
- frontend/src/api/installationsApi.js :: creerInterventionsStandard -> /api/django/installations/chantiers/<>/creer-interventions-standard
    created:inconnu, detail:texte, existants:inconnu
- frontend/src/api/installationsApi.js :: declarerRebutAssemblage -> /api/django/installations/ordres-assemblage/<>/declarer-rebut
    id:inconnu, motif_rebut:inconnu, produit:inconnu, quantite:inconnu, reference:inconnu
- frontend/src/api/installationsApi.js :: getChantierCout -> /api/django/installations/chantiers/<>/cout
    devis_total_ht:inconnu, devis_total_ttc:inconnu, installation:inconnu, labour:objet, marge:inconnu, marge_taux:inconnu, materiel:objet, reference:inconnu
- frontend/src/api/installationsApi.js :: getChecklist -> /api/django/installations/chantiers/<>/checklist
    completion:inconnu, installation:inconnu, items:inconnu
- frontend/src/api/installationsApi.js :: getCode -> /api/django/installations/interventions/<>/code
    intervention:inconnu, qr_svg:inconnu, token:inconnu
- frontend/src/api/installationsApi.js :: getCrewTime -> /api/django/installations/interventions/<>/crew-time
    arrivee_site_le:inconnu, depart_depot_le:inconnu, duree_sur_site_min:inconnu, labour_jours:inconnu, retour_depot_le:inconnu, trajet_aller_min:inconnu
- frontend/src/api/installationsApi.js :: getEtapesChantier -> /api/django/installations/chantiers/<>/etapes
    etape_courante:inconnu, etapes:inconnu, installation:inconnu, reference:inconnu
- frontend/src/api/installationsApi.js :: getInterventionPublique -> /api/django/public/installations/intervention/<>
    date_prevue:inconnu, detail:texte, distance_km:inconnu, eta_minutes:inconnu, fenetre_debut:inconnu, fenetre_fin:inconnu, site_ville:inconnu, statut:inconnu, statut_display:inconnu, technicien_avatar_url:inconnu, technicien_nom:inconnu
- frontend/src/api/installationsApi.js :: getInterventionRapportPublic -> /api/django/public/installations/intervention-rapport/<>
    chantier_reference:inconnu, consommation:inconnu, date_realisee:inconnu, detail:texte, equipe:inconnu, pdf_url:texte, photos:inconnu, reserves:inconnu, serials:inconnu, signataire_nom:inconnu, signe_le:inconnu, site_ville:inconnu, statut:inconnu, statut_display:inconnu, type_intervention_display:inconnu
- frontend/src/api/installationsApi.js :: getLandedCostDossier -> /api/django/installations/dossiers-import/<>/landed-cost
    dossier_id:inconnu, lignes:inconnu, total_fob:nombre, total_frais:nombre, total_landed:nombre
- frontend/src/api/installationsApi.js :: getLienClientIntervention -> /api/django/installations/interventions/<>/lien-client
    path:inconnu, token:inconnu, url:inconnu
- frontend/src/api/installationsApi.js :: getLienRapportIntervention -> /api/django/installations/interventions/<>/lien-rapport
    path:inconnu, token:inconnu, url:inconnu
- frontend/src/api/installationsApi.js :: getMaTournee -> /api/django/installations/interventions/ma-tournee
    date:inconnu, stops:inconnu
- frontend/src/api/installationsApi.js :: getPhotoQa -> /api/django/installations/interventions/<>/photo-qa
    actif:inconnu, signalements:inconnu
- frontend/src/api/installationsApi.js :: getPhotos -> /api/django/installations/interventions/<>/photos
    autres:inconnu, created_at:inconnu, filename:inconnu, groupes:inconnu, id:inconnu, intervention:inconnu, mime:inconnu, obligatoires_manquants:liste, sans_creneau:inconnu, uploaded_by_nom:inconnu, url:texte
- frontend/src/api/installationsApi.js :: getRegimeSuggestion -> /api/django/installations/chantiers/regime-suggestion
    code:inconnu, label:inconnu, seuil_anre_kwc:inconnu, seuil_declaration_kwc:inconnu
- frontend/src/api/installationsApi.js :: getSousTraitants -> /api/django/installations/sous-traitants
    count:nombre, next:inconnu, previous:inconnu, results:inconnu
- frontend/src/api/installationsApi.js :: getTourneeLivraison -> /api/django/installations/tournee-livraison
    depart:texte, jour:texte, sans_gps:inconnu, total:inconnu, tournee:inconnu
- frontend/src/api/installationsApi.js :: overageReview -> /api/django/installations/interventions/overage-review
    interventions:inconnu, seuil_pct:inconnu
- frontend/src/api/installationsApi.js :: supprimerLigneConsommation -> /api/django/installations/interventions/<>/supprimer-ligne-consommation
    detail:texte
- frontend/src/api/installationsApi.js :: supprimerMemo -> /api/django/installations/interventions/<>/supprimer-memo
    detail:texte
- frontend/src/api/installationsApi.js :: supprimerPhoto -> /api/django/installations/interventions/<>/supprimer-photo
    detail:texte
- frontend/src/api/installationsApi.js :: supprimerSerial -> /api/django/installations/interventions/<>/supprimer-serial
    detail:texte
- frontend/src/api/installationsApi.js :: syncField -> /api/django/installations/sync
    applied:inconnu, detail:texte, errors:inconnu, replayed:inconnu, results:inconnu
- frontend/src/api/monitoringApi.js :: emailOmReport -> /api/django/monitoring/configs/<>/email-om-report
    sent:inconnu
- frontend/src/api/monitoringApi.js :: getClientPortal -> /api/django/monitoring/configs/client-portal
    client:nombre, co2_kg:inconnu, co2_kg_par_kwh:inconnu, co2_tonnes:inconnu, detail:texte, economies_mad:inconnu, systems_count:inconnu, tarif_mad_par_kwh:inconnu, total_production_kwh:inconnu
- frontend/src/api/monitoringApi.js :: getCo2 -> /api/django/monitoring/configs/<>/co2
    co2_kg:inconnu, co2_kg_par_kwh:inconnu, co2_tonnes:nombre, installation:inconnu, production_kwh:inconnu
- frontend/src/api/monitoringApi.js :: getCo2Fleet -> /api/django/monitoring/configs/co2-fleet
    co2_kg_par_kwh:inconnu, systems:inconnu, total_co2_kg:inconnu, total_co2_tonnes:inconnu, total_production_kwh:inconnu
- frontend/src/api/monitoringApi.js :: getFleet -> /api/django/monitoring/configs/fleet
    fleet_pr_pct:inconnu, open_alerts:inconnu, systems:inconnu, systems_active:inconnu, total_kwc:inconnu, total_production_kwh:inconnu, window_days:inconnu
- frontend/src/api/monitoringApi.js :: getOmMetrics -> /api/django/monitoring/configs/<>/om-metrics
    availability_pct:inconnu, degradation_pct_per_year:inconnu, expected_kwh:inconnu, installation:inconnu, monthly_pr:inconnu, pr_pct:inconnu, production_kwh:inconnu, soiling_suspected:inconnu, window_days:inconnu
- frontend/src/api/monitoringApi.js :: getSoiling -> /api/django/monitoring/configs/<>/soiling
    baseline_pr_pct:inconnu, current_pr_pct:inconnu, days_since_cleaning:inconnu, estimated_soiling_loss_pct:inconnu, installation:inconnu, last_cleaning_date:inconnu, reasons:inconnu, recommend_cleaning:inconnu
- frontend/src/api/monitoringApi.js :: getWarrantyCurve -> /api/django/monitoring/warranties/<>/curve
    has_warranty:booleen, installation:inconnu, manufacturer_recourse:inconnu, points:inconnu, threshold_pct:inconnu
- frontend/src/api/monitoringApi.js :: getWarrantyStatus -> /api/django/monitoring/warranties/<>/status
    actual_kwh:inconnu, compensation_mad:inconnu, guaranteed_kwh:inconnu, has_warranty:booleen, shortfall_kwh:inconnu, within_tolerance:inconnu, year:inconnu, year_in_progress:inconnu
- frontend/src/api/monitoringApi.js :: syncNow -> /api/django/monitoring/configs/<>/sync-now
    imported:inconnu, ok:booleen, provider:inconnu, ratio_pct:inconnu, ticket:inconnu, underperforming:inconnu
- frontend/src/api/notificationsApi.js :: accuserLectureAnnonce -> /api/django/notifications/annonces/<>/accuser-lecture
    lu:booleen
- frontend/src/api/notificationsApi.js :: attentionSummary -> /api/django/notifications/attention-summary
    actions_dues:inconnu, approbations:inconnu, aujourdhui:inconnu, en_retard:inconnu, mentions_non_lues:inconnu
- frontend/src/api/notificationsApi.js :: calendarCheck -> /api/django/notifications/calendar/check
    date:texte, detail:texte, is_jour_ouvre:inconnu, prochain_jour_ouvre:texte
- frontend/src/api/notificationsApi.js :: getVapidPublicKey -> /api/django/notifications/push/vapid-public-key
    public_key:inconnu
- frontend/src/api/notificationsApi.js :: markAllRead -> /api/django/notifications/notifications/read-all
    ids:inconnu, updated:inconnu
- frontend/src/api/notificationsApi.js :: messagesAccueilALire -> /api/django/notifications/messages-accueil/a-lire
    messages:inconnu
- frontend/src/api/notificationsApi.js :: pushSubscribe -> /api/django/notifications/push/subscribe
    detail:texte, id:inconnu
- frontend/src/api/notificationsApi.js :: pushUnsubscribe -> /api/django/notifications/push/unsubscribe
    deleted:inconnu, detail:texte
- frontend/src/api/notificationsApi.js :: unreadCount -> /api/django/notifications/notifications/unread-count
    actions:inconnu, infos:nombre, unread:inconnu
- frontend/src/api/offlinesyncApi.js :: envoyerLot -> /api/django/offlinesync/operations/batch
    applied:inconnu, conflicts:inconnu, detail:texte, errors:inconnu, replayed:inconnu, results:inconnu
- frontend/src/api/offlinesyncApi.js :: resoudreConflit -> /api/django/offlinesync/operations/<>/resoudre
    detail:texte, operation:inconnu, resultat:inconnu
- frontend/src/api/parametresApi.js :: getEmailTemplates -> /api/django/parametres/email-templates/effective
    results:inconnu
- frontend/src/api/parametresApi.js :: getMesSauvegardes -> /api/django/core/mes-sauvegardes
    dernier_drill:inconnu, derniere_sauvegarde:inconnu, rpo_planifie:inconnu, rto_annonce_heures:inconnu
- frontend/src/api/parametresApi.js :: getStatutsEffective -> /api/django/parametres/statuts/effective
    detail:texte, domaine:inconnu, results:inconnu
- frontend/src/api/parametresApi.js :: getTranslationOverrides -> /api/django/parametres/traductions/effective
    overrides:inconnu
- frontend/src/api/parametresApi.js :: getUsageLimites -> /api/django/core/usage-limites
    genere_le:texte, ressources:inconnu
- frontend/src/api/parametresApi.js :: saveEmailTemplates -> /api/django/parametres/email-templates/bulk
    detail:texte, results:inconnu
- frontend/src/api/parametresApi.js :: saveStatuts -> /api/django/parametres/statuts/bulk
    detail:texte, domaine:inconnu, results:inconnu
- frontend/src/api/parametresApi.js :: saveTranslationOverrides -> /api/django/parametres/traductions/bulk
    detail:texte, overrides:inconnu
- frontend/src/api/portailApi.js :: accepter -> /api/django/portail/mes-devis/<>/accepter
    detail:inconnu, reference:inconnu, statut:inconnu
- frontend/src/api/portailApi.js :: confirmer -> /api/django/portail/mes-bons-commande/<>/confirmer
    date_confirmee:texte, date_confirmee_fournisseur:inconnu, detail:texte, id:inconnu, numero_confirmation_fournisseur:texte, reference:inconnu
- frontend/src/api/portailApi.js :: get -> /api/django/portail/ma-preference
    langue:inconnu, langues_disponibles:inconnu
- frontend/src/api/portailApi.js :: lienAcces -> /api/django/portail/comptes-portail/<>/lien-acces
    detail:texte, lien:inconnu, token_acces:inconnu
- frontend/src/api/portailApi.js :: payer -> /api/django/portail/mes-factures/<>/payer
    detail:texte, montant:texte, paiement_en_ligne_actif:inconnu, paiement_id:inconnu, reference:inconnu, statut:inconnu, virement:objet
- frontend/src/api/portailApi.js :: photos -> /api/django/portail/mes-chantiers/<>/photos
    detail:texte, results:inconnu
- frontend/src/api/portailApi.js :: provisionnerAcces -> /api/django/portail/comptes-portail/<>/provisionner-acces
    actif:inconnu, cree:inconnu, detail:texte, email:inconnu, username:inconnu, utilisateur_id:inconnu
- frontend/src/api/portailApi.js :: regenererJeton -> /api/django/portail/comptes-portail/<>/regenerer-jeton
    detail:texte, token_apercu:inconnu
- frontend/src/api/portailApi.js :: set -> /api/django/portail/ma-preference
    langue:inconnu, langues_disponibles:inconnu
- frontend/src/api/publicapiApi.js :: getCatalogue -> /api/django/publicapi/catalogue
    events:liste, scopes:liste
- frontend/src/api/publicapiApi.js :: getChangelog -> /api/public/v1/changelog
    results:liste
- frontend/src/api/publicapiApi.js :: getDocs -> /api/django/publicapi/docs
    authentification:objet, base_url:texte, endpoints:liste, endpoints_bulk:objet, endpoints_ecriture:objet, endpoints_lecture_simple:objet, introduction:texte, parametres_communs:objet, scopes:liste, titre:texte, version:texte, webhooks:objet
- frontend/src/api/publicapiApi.js :: getMonitoring -> /api/django/publicapi/monitoring
    appels:objet, depuis:texte, fenetre_jours:inconnu, jobs:objet, top_endpoints:inconnu, webhooks:objet
- frontend/src/api/publicapiApi.js :: getOpenApiSchema -> /api/public/v1/openapi.json
    components:objet, info:objet, openapi:inconnu, paths:inconnu, security:liste, servers:liste
- frontend/src/api/publicapiApi.js :: ocrToCrm -> /api/django/publicapi/ocr-to-crm
    detail:texte, devis_id:inconnu, devis_reference:inconnu, lead_id:inconnu, mode:inconnu
- frontend/src/api/publicapiApi.js :: sandboxTry -> /api/django/publicapi/sandbox/try
    detail:texte, resource:inconnu, results:inconnu, sandbox:booleen
- frontend/src/api/recordsApi.js :: getMyActivities -> /api/django/records/activities/mine
    a_venir:liste, aujourdhui:liste, en_retard:liste
- frontend/src/api/recordsApi.js :: markActivityDone -> /api/django/records/activities/<>/done
    activity:inconnu, chained:inconnu, next:inconnu, suggestion:inconnu
- frontend/src/api/recordsApi.js :: snoozeApprobation -> /api/django/records/activities/snooze-approbation
    detail:texte, ok:booleen, snoozed_until:texte
- frontend/src/api/recordsApi.js :: unfollow -> /api/django/records/followers/<>
    detail:texte
- frontend/src/api/reportingApi.js :: approbationsEnAttente -> /api/django/reporting/approbations-en-attente
    items:inconnu, total:nombre
- frontend/src/api/reportingApi.js :: auditAnalytics -> /api/django/audit/analytics
    action_mix:inconnu, daily_counts:inconnu, detail:texte, failed_logins:inconnu, from:texte, object_churn:inconnu, to:texte, top_users:inconnu, total_entries:inconnu, window_days:inconnu
- frontend/src/api/reportingApi.js :: commercialDashboard -> /api/django/reporting/commercial/dashboard
    detail:texte, funnel:inconnu, leaderboard:inconnu, sales_velocity:inconnu, time_in_stage:inconnu, time_to_first_touch:inconnu, total_leads:nombre, total_signes:inconnu, win_rate_pct:inconnu
- frontend/src/api/reportingApi.js :: deciderApprobationsEnMasse -> /api/django/reporting/approbations-en-attente/decider-en-masse
    detail:texte, resultats:inconnu
- frontend/src/api/reportingApi.js :: effectiveDashboardConfig -> /api/django/reporting/dashboard-config/effective
    cards:inconnu, config_id:inconnu, menu_tier:inconnu, source:texte
- frontend/src/api/reportingApi.js :: evaluerFormuleClasseur -> /api/django/reporting/classeurs/<>/evaluer
    detail:texte, valeur:inconnu
- frontend/src/api/reportingApi.js :: executerRapportDefinition -> /api/django/reporting/rapport-definitions/<>/executer
    detail:texte, pivot:inconnu, rows:inconnu
- frontend/src/api/reportingApi.js :: funnelVelocity -> /api/django/reporting/pipeline/velocity
    detail:texte, velocity:inconnu
- frontend/src/api/reportingApi.js :: getCalendarSubscription -> /api/django/reporting/calendar/subscription
    token:inconnu, url:inconnu
- frontend/src/api/reportingApi.js :: getNotifications -> /api/django/reporting/notifications
    activites_en_retard:inconnu, contrats_a_renouveler:inconnu, detail:texte, factures_impayees:inconnu, garanties_expirantes:inconnu, total:inconnu, visites_dues:inconnu
- frontend/src/api/reportingApi.js :: getPipeline -> /api/django/reporting/pipeline
    detail:texte, devis_par_statut:inconnu, gagnes:objet, par_etape:inconnu, perdus_par_motif:liste, prevision_ponderee:texte
- frontend/src/api/reportingApi.js :: integriteInsight -> /api/django/reporting/insights/integrite
    detail:texte, familles:inconnu, total_anomalies:inconnu
- frontend/src/api/reportingApi.js :: kpiBadges -> /api/django/reporting/reports/kpi-federes
    badges:inconnu, count:nombre, tuiles:inconnu
- frontend/src/api/reportingApi.js :: kpiFederes -> /api/django/reporting/reports/kpi-federes
    badges:inconnu, count:nombre, tuiles:inconnu
- frontend/src/api/reportingApi.js :: rafraichirClasseur -> /api/django/reporting/classeurs/<>/rafraichir
    cellules:inconnu
- frontend/src/api/reportingApi.js :: rescheduleCalendar -> /api/django/reporting/calendar/reschedule
    date:texte, detail:texte, ok:booleen
- frontend/src/api/reportingApi.js :: savTauxAttache -> /api/django/reporting/insights/sav-taux-attache
    avec_contrat:inconnu, detail:texte, taux_pct:inconnu, total:inconnu
- frontend/src/api/reportingApi.js :: savTicketsCoutMoyen -> /api/django/reporting/insights/sav-tickets-cout-moyen
    detail:texte, rows:inconnu
- frontend/src/api/reportingApi.js :: search -> /api/django/reporting/search
    detail:texte, groups:inconnu, query:inconnu
- frontend/src/api/reportingApi.js :: winLossBySource -> /api/django/reporting/commercial/win-loss-by-source
    by_canal:inconnu, by_source_technique:inconnu, detail:texte, summary:objet, top_loss_reasons:inconnu
- frontend/src/api/rolesApi.js :: getPermissionCatalog -> /api/django/roles/permission-catalog
    permissions:inconnu, routes:inconnu
- frontend/src/api/rolesApi.js :: getPermissionsDisponibles -> /api/django/roles/permissions-disponibles
    modules:inconnu, permissions:inconnu
- frontend/src/api/savApi.js :: actionsGroupeesTickets -> /api/django/sav/tickets/actions-groupees
    echecs:inconnu, ids:texte, nb_echecs:nombre, nb_traites:nombre, operation:texte, priorite:texte, statut:texte, technicien:texte, traites:inconnu
- frontend/src/api/savApi.js :: creerDevisTicket -> /api/django/sav/tickets/<>/creer-devis
    detail:texte, devis_id:inconnu, devis_reference:inconnu
- frontend/src/api/savApi.js :: creerLeadDepuisTicket -> /api/django/sav/tickets/<>/creer-lead
    created:inconnu, lead_id:inconnu
- frontend/src/api/savApi.js :: creerProblemeDepuisRegroupement -> /api/django/sav/problemes/creer-depuis-regroupement
    id:inconnu, nb_tickets:nombre, reference:inconnu, titre:inconnu
- frontend/src/api/savApi.js :: delierTicketProbleme -> /api/django/sav/problemes/<>/delier-ticket
    delie:booleen, nb_tickets:nombre, probleme:inconnu, ticket:inconnu
- frontend/src/api/savApi.js :: facturerTicket -> /api/django/sav/tickets/<>/facturer
    couverture:inconnu, facture_id:inconnu, facture_reference:inconnu
- frontend/src/api/savApi.js :: genererFactureTicket -> /api/django/sav/tickets/<>/generer-facture
    detail:texte, facture_id:inconnu, facture_reference:inconnu, sous_garantie:inconnu
- frontend/src/api/savApi.js :: genererVisitesDues -> /api/django/sav/contrats-maintenance/generer-dus
    ok:booleen, tickets_generes:inconnu
- frontend/src/api/savApi.js :: getEquipementPartageQr -> /api/django/sav/equipements/<>/partage-qr
    qr:inconnu, url:inconnu
- frontend/src/api/savApi.js :: getPiecesCompatibles -> /api/django/sav/tickets/<>/pieces-compatibles
    results:inconnu
- frontend/src/api/savApi.js :: getProblemeTickets -> /api/django/sav/problemes/<>/tickets
    results:liste
- frontend/src/api/savApi.js :: getRegroupementsSuggeres -> /api/django/sav/problemes/regroupements-suggeres
    fenetre_jours:inconnu, results:inconnu, seuil:inconnu
- frontend/src/api/savApi.js :: getRentabiliteContrats -> /api/django/sav/contrats-maintenance/rentabilite
    detail:texte, results:inconnu
- frontend/src/api/savApi.js :: getSavFiabiliteParc -> /api/django/sav/insights/sav-fiabilite
    couts_inclus:inconnu, results:inconnu
- frontend/src/api/savApi.js :: getSavFileAction -> /api/django/sav/tickets/file-action
    buckets:inconnu
- frontend/src/api/savApi.js :: getSavResumeParEquipe -> /api/django/sav/insights/sav-resume-equipe
    results:inconnu
- frontend/src/api/savApi.js :: getTicketsSimilaires -> /api/django/sav/tickets/<>/similaires
    results:inconnu
- frontend/src/api/savApi.js :: getTriageIa -> /api/django/sav/tickets/<>/triage-ia
    disponible:booleen, erreur:texte, kb_articles:inconnu, suggestion:inconnu
- frontend/src/api/savApi.js :: lienClientTicket -> /api/django/sav/tickets/<>/lien-client
    token:inconnu, url:inconnu
- frontend/src/api/savApi.js :: lierTicketProbleme -> /api/django/sav/problemes/<>/lier-ticket
    cree:inconnu, lien_id:inconnu, nb_tickets:nombre, probleme:inconnu, ticket:inconnu
- frontend/src/api/savApi.js :: neplusSuivreTicket -> /api/django/sav/tickets/<>/suivre
    suivi:booleen
- frontend/src/api/savApi.js :: planifierTournee -> /api/django/sav/contrats-maintenance/planifier-tournee
    detail:inconnu, ok:booleen, tickets_planifies:inconnu
- frontend/src/api/savApi.js :: removeTicketPiece -> /api/django/sav/tickets/<>/pieces/<>
    detail:texte
- frontend/src/api/savApi.js :: suivreTicket -> /api/django/sav/tickets/<>/suivre
    suivi:booleen
- frontend/src/api/statuspageApi.js :: prefillIncident -> /api/django/statuspage/historique-statut/<>/prefill-incident
    composants:liste, debute_le:inconnu, region:inconnu, severite:inconnu, titre:texte
- frontend/src/api/stockApi.js :: bulkProduits -> /api/django/stock/produits/bulk
    detail:texte, ok:booleen, skipped:inconnu, total:nombre, updated:inconnu
- frontend/src/api/stockApi.js :: comparerTcoFournisseurs -> /api/django/stock/produits/<>/comparer-tco
    cout_rupture_jour:texte, fournisseurs:inconnu, produit:inconnu
- frontend/src/api/stockApi.js :: deciderCandidatureFournisseur -> /api/django/stock/fournisseurs/<>/decider-candidature
    detail:texte, id:inconnu, statut_validation:inconnu
- frontend/src/api/stockApi.js :: envoyerEmailBcf -> /api/django/stock/bons-commande-fournisseur/<>/envoyer-email
    detail:texte, email_statut:inconnu, log_id:inconnu, statut:inconnu
- frontend/src/api/stockApi.js :: exploserKit -> /api/django/stock/kits/<>/exploser
    detail:texte, kit_id:inconnu, kit_nom:inconnu, lignes:inconnu, quantite_kit:inconnu
- frontend/src/api/stockApi.js :: forceDeleteFournisseur -> /api/django/stock/fournisseurs/<>/force-delete
    bloquants:inconnu, detail:texte
- frontend/src/api/stockApi.js :: forceDeleteProduit -> /api/django/stock/produits/<>/force-delete
    bloquants:inconnu, detail:texte
- frontend/src/api/stockApi.js :: getChecklistClotureAchats -> /api/django/stock/achats-parametres/checklist-cloture
    demandes_en_attente_anciennes:liste, detail:texte, documents_expires:inconnu, factures_en_exception:liste, nb_demandes_en_attente_anciennes:nombre, nb_documents_expires:nombre, nb_factures_en_exception:nombre, periode:inconnu, seuil_jours:nombre
- frontend/src/api/stockApi.js :: getComptesAPayer -> /api/django/stock/factures-fournisseur/comptes-a-payer
    results:inconnu, total_du:texte
- frontend/src/api/stockApi.js :: getFavorisCatalogueAchat -> /api/django/stock/catalogue-achat/favoris
    epingles:inconnu, produit_ids:inconnu, recents:inconnu
- frontend/src/api/stockApi.js :: getFournisseur360 -> /api/django/stock/fournisseurs/<>/vue-360
    accords_prix:inconnu, accords_prix_actifs:nombre, bcf_en_retard:inconnu, bcf_ouverts:inconnu, conformite_documents_manquants:nombre, conformite_ok:booleen, factures_ouvertes:inconnu, fournisseur_id:inconnu, nb_retours_avoirs:inconnu, receptions_attendues:inconnu, score_performance:inconnu, solde_total_du:texte
- frontend/src/api/stockApi.js :: getKitDisponibilite -> /api/django/stock/kits/<>/disponibilite
    composants:inconnu, detail:texte, goulots:inconnu, kit_id:inconnu, kit_nom:inconnu, kits_assemblables:inconnu
- frontend/src/api/stockApi.js :: getOnboardingFournisseur -> /api/django/stock/fournisseurs/<>/onboarding
    dossier:inconnu, obligatoire:inconnu, progression:inconnu
- frontend/src/api/stockApi.js :: getProduitUtiliseDans -> /api/django/stock/produits/<>/utilise-dans
    chantiers:inconnu, devis:inconnu, leads:inconnu, limite:inconnu
- frontend/src/api/stockApi.js :: inventaire -> /api/django/stock/produits/inventaire
    ajustes:nombre, detail:texte, inchanges:nombre, mouvements:liste
- frontend/src/api/stockApi.js :: performanceFournisseur -> /api/django/stock/fournisseurs/<>/performance
    avg_lead_time_days:inconnu, fill_rate_pct:inconnu, fournisseur_id:inconnu, fournisseur_nom:inconnu, incidents_qualite_critiques_ouverts:inconnu, nb_bons:inconnu, nb_retours:inconnu, otd_a_lheure_pct:inconnu, otd_ecart_moyen_jours:inconnu, otif_nb_incomplet:inconnu, otif_nb_retard:inconnu, otif_total_livraisons:inconnu, return_rate_pct:inconnu, taux_otif_pct:inconnu, total_achats_ht:texte
- frontend/src/api/stockApi.js :: prixEffectifFournisseur -> /api/django/stock/prix-fournisseurs/effectif
    detail:texte, prix_effectif:inconnu
- frontend/src/api/stockApi.js :: produitPrevisionnel -> /api/django/stock/produits/<>/previsionnel
    disponible:inconnu, entrees_attendues:inconnu, produit_id:inconnu, solde_projete:inconnu, sorties_attendues:inconnu, timeline:inconnu
- frontend/src/api/stockApi.js :: rebuterProduit -> /api/django/stock/produits/<>/rebuter
    detail:texte, mouvement_id:inconnu, valeur_perdue:texte
- frontend/src/api/stockApi.js :: resolveCode -> /api/django/stock/produits/resolve
    chantier:inconnu, client:inconnu, created:inconnu, date_fin_garantie:inconnu, date_peremption:inconnu, detail:texte, gs1:inconnu, id:inconnu, label:inconnu, nb_tickets_ouverts:inconnu, numero_lot:inconnu, numero_serie:inconnu, quantite:inconnu, quantite_restante:inconnu, reference:inconnu, route:texte, serie:texte, sku:texte, statut:inconnu, type:texte
- frontend/src/api/stockApi.js :: scanGs1ReceptionFournisseur -> /api/django/stock/receptions-fournisseur/scan-gs1
    date_peremption:inconnu, detail:texte, numero_lot:inconnu, numeros_serie:inconnu, produit_id:inconnu, produit_nom:inconnu
- frontend/src/api/stockApi.js :: setFavorisCatalogueAchat -> /api/django/stock/catalogue-achat/favoris
    epingles:inconnu, produit_ids:inconnu, recents:inconnu
- frontend/src/api/stockApi.js :: validerInventaireSession -> /api/django/stock/inventaire-sessions/<>/valider
    ajustes:inconnu, detail:texte, inchanges:inconnu
- frontend/src/api/stockApi.js :: valorisation -> /api/django/stock/produits/valorisation
    lignes:inconnu, par_emplacement:liste, total:inconnu
- frontend/src/api/stockApi.js :: whatsappBcf -> /api/django/stock/bons-commande-fournisseur/<>/whatsapp
    detail:texte, message:inconnu, phone:inconnu, statut:inconnu, url:inconnu, wa_url:inconnu
- frontend/src/api/tiersApi.js :: doublons -> /api/django/tiers/tiers/doublons
    clusters:inconnu, count:nombre
- frontend/src/api/trashApi.js :: restaurer -> /api/django/trash/corbeille/<>/restaurer
    element:inconnu, restaure:booleen
- frontend/src/api/uxviewsApi.js :: importFavoris -> /api/django/uxviews/favoris/importer
    importes:inconnu, non_resolues:inconnu
- frontend/src/api/uxviewsApi.js :: importSavedViews -> /api/django/uxviews/saved-views/importer
    created:inconnu, erreurs:inconnu
- frontend/src/api/ventesApi.js :: applyPreset -> /api/django/ventes/devis/<>/apply-preset
    detail:texte, lignes_created:nombre, skipped_priceless:nombre
- frontend/src/api/ventesApi.js :: arrondiCaisseFacture -> /api/django/ventes/factures/<>/arrondi-caisse
    applicable:inconnu, ecart:texte, montant_arrondi:texte, montant_du:texte, pas:texte
- frontend/src/api/ventesApi.js :: contacterSuperieur -> /api/django/ventes/devis/<>/contacter-superieur
    detail:texte, recipients:liste
- frontend/src/api/ventesApi.js :: deletePreset -> /api/django/ventes/presets/<>
    detail:texte
- frontend/src/api/ventesApi.js :: dgiConformiteFacture -> /api/django/ventes/factures/<>/dgi-conformite
    conforme:booleen, detail:texte, problemes:inconnu
- frontend/src/api/ventesApi.js :: dupliquerVarianteGamme -> /api/django/ventes/devis/<>/dupliquer-variante-gamme
    detail:texte, gamme:inconnu, gammes:liste, source:inconnu
- frontend/src/api/ventesApi.js :: envoyerEmailDevis -> /api/django/ventes/devis/<>/envoyer-email
    detail:inconnu, devis_statut:inconnu, email_statut:inconnu, log_id:inconnu, proposal_path:inconnu, statut:texte
- frontend/src/api/ventesApi.js :: envoyerEmailFacture -> /api/django/ventes/factures/<>/envoyer-email
    detail:texte, email_log_id:inconnu, to_email:inconnu
- frontend/src/api/ventesApi.js :: etatPdfDevis -> /api/django/ventes/devis/<>/etat-pdf
    date:inconnu, devis:inconnu, erreur:inconnu, fichier_pdf:inconnu, statut:inconnu
- frontend/src/api/ventesApi.js :: exportStatus -> /api/django/ventes/export/status/<>
    detail:texte, download_url:inconnu, filename:inconnu, status:texte
- frontend/src/api/ventesApi.js :: genererPdfDevis -> /api/django/ventes/devis/<>/generer-pdf
    detail:texte, task_id:inconnu
- frontend/src/api/ventesApi.js :: genererPdfFacture -> /api/django/ventes/factures/<>/generer-pdf
    detail:texte, task_id:inconnu
- frontend/src/api/ventesApi.js :: getCashFlowForecast -> /api/django/ventes/insights/cash-flow
    buckets:inconnu, rows:inconnu, total_en_cours:inconnu
- frontend/src/api/ventesApi.js :: getClientReleve -> /api/django/ventes/clients/<>/releve
    avoirs:inconnu, client:objet, detail:texte, lignes:inconnu, paiements:inconnu, totaux:objet
- frontend/src/api/ventesApi.js :: getDevisActionBoard -> /api/django/ventes/devis/action-requise
    buckets:inconnu, devis:inconnu, wa_drafts:inconnu
- frontend/src/api/ventesApi.js :: getLectureClientDevis -> /api/django/ventes/devis/<>/lecture-client
    friction:inconnu, sections:inconnu
- frontend/src/api/ventesApi.js :: getPrefillSite -> /api/django/ventes/devis/prefill-site
    client:inconnu, detail:texte, profil:inconnu
- frontend/src/api/ventesApi.js :: getSimulationStatus -> /api/django/ventes/devis/<>/simulation-status/<>
    detail:texte, simulation:inconnu, status:texte
- frontend/src/api/ventesApi.js :: getVarianteConfig -> /api/django/ventes/devis/variante-config
    detail:texte, variante_pct:texte
- frontend/src/api/ventesApi.js :: lienPaiementFacture -> /api/django/ventes/factures/<>/lien-paiement
    detail:inconnu, expires_at:texte, montant:texte, montant_a_payer:texte, pay_url:inconnu, provider:inconnu, statut:inconnu, token:inconnu
- frontend/src/api/ventesApi.js :: patchEtudeParams -> /api/django/ventes/devis/<>/etude-params
    detail:texte, etude_params:inconnu
- frontend/src/api/ventesApi.js :: postEtudeHorairePreview -> /api/django/ventes/etude-horaire/preview
    avertissements:inconnu, consommation:objet, detail:texte, dimensionnement:inconnu, estimation_conso:inconnu, etude:inconnu, profil:objet
- frontend/src/api/ventesApi.js :: resoudrePlanCommission -> /api/django/ventes/plans-commission/resoudre
    owner:inconnu, plan:inconnu, source:inconnu
- frontend/src/api/ventesApi.js :: setVarianteConfig -> /api/django/ventes/devis/variante-config
    detail:texte, variante_pct:texte
- frontend/src/api/ventesApi.js :: shareLinkDevis -> /api/django/ventes/devis/<>/share-link
    detail:inconnu, gamme:inconnu, niveau:inconnu, otp_lecture:inconnu, path:inconnu, path_interne:inconnu, sections:objet, token:inconnu, token_interne:inconnu
- frontend/src/api/ventesApi.js :: simulerEtudeDevis -> /api/django/ventes/devis/<>/simuler
    detail:texte, job_id:inconnu, status:texte, status_url:inconnu, zones:nombre
- frontend/src/api/ventesApi.js :: superiorContactStatus -> /api/django/ventes/devis/<>/superior-contact-status
    requested:booleen, requested_at:inconnu, seen:booleen, seen_by:inconnu
- frontend/src/api/ventesApi.js :: whatsappDevis -> /api/django/ventes/devis/<>/whatsapp
    detail:texte, devis_statut:inconnu, message:inconnu, phone:inconnu, url:inconnu, wa_url:inconnu
- frontend/src/api/ventesApi.js :: whatsappFacture -> /api/django/ventes/factures/<>/whatsapp
    detail:texte, message:inconnu, phone:inconnu, url:inconnu, wa_url:inconnu
- frontend/src/api/ventesApi.js :: whatsappPreviewDevis -> /api/django/ventes/devis/<>/whatsapp-preview
    detail:texte, devis_statut:inconnu, gamme:inconnu, message:inconnu, phone:inconnu, preview:booleen, url:inconnu, wa_url:inconnu
- frontend/src/api/visitesApi.js :: createVisite -> /api/django/visites/visites
    arrivee_le:inconnu, checklist:inconnu, client_panel:objet, commercial:inconnu, completude:objet, date_prevue:inconnu, date_realisee:inconnu, devis:inconnu, en_route_le:inconnu, id:inconnu, lead:inconnu, mesures:inconnu, modifiable:inconnu, notes:texte, photo_toit:objet, qualification:inconnu, raison_lecture_seule:inconnu, statut:inconnu
- frontend/src/api/visitesApi.js :: getMaJournee -> /api/django/visites/ma-journee
    date:texte, en_retard_count:nombre, visites:liste
- frontend/src/api/visitesApi.js :: getVisite -> /api/django/visites/visites/<>
    arrivee_le:inconnu, checklist:inconnu, client_panel:objet, commercial:inconnu, completude:objet, date_prevue:inconnu, date_realisee:inconnu, devis:inconnu, en_route_le:inconnu, id:inconnu, lead:inconnu, mesures:inconnu, modifiable:inconnu, notes:texte, photo_toit:objet, qualification:inconnu, raison_lecture_seule:inconnu, statut:inconnu
- frontend/src/api/visitesApi.js :: rechercherLeads -> /api/django/visites/leads-recherche
    results:inconnu
- frontend/src/features/adminops/adminopsApi.js :: appliquerPackage -> /api/django/adminops/config-packages/appliquer
    custom_fields:inconnu, detail:texte, message_templates:inconnu, roles_custom:inconnu
- frontend/src/features/adminops/adminopsApi.js :: previsualiserPackage -> /api/django/adminops/config-packages/previsualiser
    custom_fields:inconnu, detail:texte, message_templates:inconnu, roles_custom:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: acquitterSimulation -> /api/django/adsengine/plans-vol/autonomie/acquitter-simulation
    actif:inconnu, detail:texte, manquantes:liste, portes:inconnu, pret:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: autonomie -> /api/django/adsengine/plans-vol/autonomie
    actif:inconnu, detail:texte, manquantes:liste, portes:inconnu, pret:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: backtest -> /api/django/adsengine/regles/<>/backtest
    label_fr:inconnu, proposals:inconnu, range:objet, reason:texte, summary:objet, supported:booleen, template_key:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: checklist -> /api/django/adsengine/creatifs/checklist
    allowed:inconnu, forbidden:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: conclude -> /api/django/adsengine/experiences/<>/conclure
    decision_log:inconnu, detail:texte, node:inconnu, validated:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: createEngagement -> /api/django/adsengine/audiences/engagement
    audience_id:texte, detail:texte, error:inconnu, preset:inconnu, retention_days:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: deliveryEstimate -> /api/django/adsengine/audiences/delivery-estimate
    detail:texte, error:inconnu, estimate:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: desactiverAutonomie -> /api/django/adsengine/plans-vol/autonomie/desactiver
    actif:inconnu, detail:texte, manquantes:liste, portes:inconnu, pret:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: detectors -> /api/django/adsengine/anomalies/detecteurs
    detecteurs:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: dryRun -> /api/django/adsengine/regles/dry-run
    detail:texte, objets_touches:inconnu, resume_fr:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: engagementPresets -> /api/django/adsengine/audiences/engagement
    detail:texte, presets:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: fullBackfill -> /api/django/adsengine/campaigns/backfill-complet
    detail:texte, queued:booleen
- frontend/src/features/adsengine/adsengineApi.js :: generateGroundedVariants -> /api/django/adsengine/generation/variantes-ancrees
    detail:texte, enabled:booleen
- frontend/src/features/adsengine/adsengineApi.js :: generateVariants -> /api/django/adsengine/creatifs/<>/variantes
    variants_created:nombre
- frontend/src/features/adsengine/adsengineApi.js :: journal -> /api/django/adsengine/regles/journal
    detail:texte, results:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: preflight -> /api/django/adsengine/plans-vol/preflight
    detail:texte, portes:inconnu, pret:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: simulate -> /api/django/adsengine/plans-vol/simulate
    allocations:liste, cree_le:texte, decisions:liste, id:inconnu, nom:inconnu, scenarios:liste
- frontend/src/features/adsengine/adsengineApi.js :: syncNow -> /api/django/adsengine/campaigns/sync-now
    campaigns:nombre, detail:texte, synced:booleen
- frontend/src/features/adsengine/adsengineApi.js :: validate -> /api/django/adsengine/plans-vol/validate
    detail:texte, ok:inconnu, raisons:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: veille -> /api/django/adsengine/concurrents/veille
    brief_material:inconnu, cadence:inconnu, finding:inconnu
- frontend/src/features/entites/entitesApi.js :: groupe -> /api/django/entites/entites/groupe
    disponible:booleen, effectif_note:texte, entites:inconnu, total:objet
- frontend/src/features/entites/entitesApi.js :: noter -> /api/django/entites/entites/<>/noter
    ok:booleen

# ===========================================================================
# RESSOURCES SERVIES PAR UN SERIALISEUR DRF (PACT177)
# ===========================================================================
#
# Le bloc ci-dessus fige les AGREGATS (un dictionnaire litteral lu dans le
# code). Celui-ci fige les RESSOURCES : `serializer_class` -> `Meta.fields` ->
# modele. On y trouve les NOMS de champs exposes et, pour chaque champ a
# `choices`, SES VALEURS — c'est la que vit le vocabulaire qu'un ecran invente
# (`type` pour `kind`, `statut` pour `status`).
#
# Une vue dont le serialiseur n'est pas resoluble statiquement
# (`get_serializer_class` dynamique, `fields = '__all__'`, `exclude = …`, ou
# une `list()`/`retrieve()` ecrite a la main) est ABSENTE d'ici : un doute ne
# rougit jamais.

- frontend/src/api/accessReviewApi.js :: get -> /api/django/accessreview/campaigns/<>  [AccessReviewCampaignSerializer]
    champs: created_at, date_debut, date_fin, id, items, nom, perimetre, perimetre_ref, statut, updated_at
    perimetre ∈ {all, module, role}
    statut ∈ {close, ouverte}
- frontend/src/api/auditApi.js :: getEntries -> /api/django/audit/entries  [AuditLogSerializer]
    champs: action, action_label, actor_username, detail, id, model, module, object_id, object_repr, timestamp, timestamp_local, utilisateur, via_portail
    action ∈ {accept, create, delete, email, export, login, login_failed, logout, notify, payment, pdf, refuse, security_alert, status, switch_company, update, whatsapp}
- frontend/src/api/automationApi.js :: createDelegation -> /api/django/automation/approval-delegations  [ApprovalDelegationSerializer]
    champs: date_creation, date_debut, date_fin, delegant, delegant_nom, id, suppleant, suppleant_nom
- frontend/src/api/automationApi.js :: deleteApprovalRequestType -> /api/django/automation/approval-request-types/<>  [ApprovalRequestTypeSerializer]
    champs: champs_config, champs_optionnels, champs_requis, date_creation, date_modification, description, enabled, id, min_approbations, nom, palier_approbateur, piece_jointe_obligatoire, sequence_approbateurs
    palier_approbateur ∈ {admin, responsable}
    sequence_approbateurs ∈ {parallele, sequentiel}
- frontend/src/api/automationApi.js :: deleteDelegation -> /api/django/automation/approval-delegations/<>  [ApprovalDelegationSerializer]
    champs: date_creation, date_debut, date_fin, delegant, delegant_nom, id, suppleant, suppleant_nom
- frontend/src/api/automationApi.js :: deleteRule -> /api/django/automation/rules/<>  [AutomationRuleSerializer]
    champs: action_config, action_type, action_type_display, approval_threshold, date_creation, date_modification, enabled, id, nom, ordre, requires_approval, trigger_config, trigger_type, trigger_type_display
    action_type ∈ {assign_record, create_activity, create_custom_record, create_sav_ticket, for_each, send_email, send_sms, send_whatsapp, server_action, set_field, wait}
    trigger_type ∈ {chantier_status, custom_record_saved, date_echeance_champ, demande_achat_approuvee, devis_accepted, dossier_echeance_depassee, facture_overdue, langue_changed, lead_stage_change, maintenance_due, projet_phase_change, projet_status_change, record_state_change, rfq_attribuee, stock_below_threshold, warranty_expiring, webhook_inbound}
- frontend/src/api/automationApi.js :: getApprovalRequestTypes -> /api/django/automation/approval-request-types  [ApprovalRequestTypeSerializer]
    champs: champs_config, champs_optionnels, champs_requis, date_creation, date_modification, description, enabled, id, min_approbations, nom, palier_approbateur, piece_jointe_obligatoire, sequence_approbateurs
    palier_approbateur ∈ {admin, responsable}
    sequence_approbateurs ∈ {parallele, sequentiel}
- frontend/src/api/automationApi.js :: getApprovals -> /api/django/automation/approvals  [AutomationApprovalSerializer]
    champs: context, date_creation, decided_at, decided_by, decided_by_nom, description, id, requested_by, requested_by_nom, rule, rule_nom, status, status_display, target_id, target_model
    status ∈ {approved, pending, rejected}
- frontend/src/api/automationApi.js :: getDelegations -> /api/django/automation/approval-delegations  [ApprovalDelegationSerializer]
    champs: date_creation, date_debut, date_fin, delegant, delegant_nom, id, suppleant, suppleant_nom
- frontend/src/api/automationApi.js :: getRules -> /api/django/automation/rules  [AutomationRuleSerializer]
    champs: action_config, action_type, action_type_display, approval_threshold, date_creation, date_modification, enabled, id, nom, ordre, requires_approval, trigger_config, trigger_type, trigger_type_display
    action_type ∈ {assign_record, create_activity, create_custom_record, create_sav_ticket, for_each, send_email, send_sms, send_whatsapp, server_action, set_field, wait}
    trigger_type ∈ {chantier_status, custom_record_saved, date_echeance_champ, demande_achat_approuvee, devis_accepted, dossier_echeance_depassee, facture_overdue, langue_changed, lead_stage_change, maintenance_due, projet_phase_change, projet_status_change, record_state_change, rfq_attribuee, stock_below_threshold, warranty_expiring, webhook_inbound}
- frontend/src/api/automationApi.js :: getRuns -> /api/django/automation/runs  [AutomationRunSerializer]
    champs: id, message, rule, rule_nom, status, status_display, target_id, target_model, timestamp
    status ∈ {failed, noop, pending_approval, simulation, skipped, success}
- frontend/src/api/coreApi.js :: revoke -> /api/django/core/dashboards-partages/<>  [PartageDashboardSerializer]
    champs: actif, created_at, dashboard, expires_at, id, token, updated_at
- frontend/src/api/coreApi.js :: updateLayout -> /api/django/core/dashboards/<>  [DashboardSerializer]
    champs: created_at, description, id, layout, owner, partage, titre, updated_at
- frontend/src/api/crmApi.js :: createAppointment -> /api/django/crm/appointments  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: createConcurrentPerte -> /api/django/crm/concurrents-perte  [ConcurrentPerteSerializer]
    champs: company, concurrent_nom, concurrent_prix, date_modification, devise, id, lead, lead_nom, motif, notes, saisi_le, saisi_par, saisi_par_nom
- frontend/src/api/crmApi.js :: createDefi -> /api/django/crm/defis  [DefiSerializer]
    champs: actif, cible_equipe, company, created_at, id, metrique, metrique_display, nom, periode_debut, periode_fin, recompense
    metrique ∈ {ca_signe, nb_contacts, nb_devis, nb_leads, nb_rdv}
- frontend/src/api/crmApi.js :: createPointContact -> /api/django/crm/points-contact  [PointContactSerializer]
    champs: canal, canal_libelle, company, cout, date_contact, date_modification, detail, id, lead, lead_nom, ordre, saisi_le, saisi_par, saisi_par_nom, source
    canal ∈ {autre, meta_ads, reference, site_web, telephone, walk_in, whatsapp_ctwa}
- frontend/src/api/crmApi.js :: createSavedView -> /api/django/crm/vues-enregistrees  [SavedViewSerializer]
    champs: created_at, id, name, page, payload, rank, user
- frontend/src/api/crmApi.js :: createSiteProfile -> /api/django/crm/site-profiles  [SiteProfileSerializer]
    champs: client, company, conso_mensuelle_kwh, date_creation, date_modification, ete_differente, facture_ete, facture_hiver, gps_lat, gps_lng, id, inclinaison_deg, ombrage, ombrage_notes, orientation, pompe_cv, pompe_debit_m3h, pompe_hmt_m, raccordement, regularisation_8221, surface_toiture_m2, tranche_onee, type_installation, type_toiture
    ombrage ∈ {aucun, important, partiel}
    orientation ∈ {autre, est, ouest, sud, sud_est, sud_ouest}
    raccordement ∈ {aucun, inconnu, monophase, triphase}
    type_installation ∈ {agricole, commercial, industriel, residentiel}
    type_toiture ∈ {autre, bac_acier, fibrociment, terrasse_beton, tole_metal, tuiles}
- frontend/src/api/crmApi.js :: deleteAppointment -> /api/django/crm/appointments/<>  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: deleteEquipe -> /api/django/crm/equipes/<>  [EquipeCommercialeSerializer]
    champs: actif, company, date_creation, id, membres, nb_membres, nom, responsable, responsable_nom
- frontend/src/api/crmApi.js :: deleteMessageTemplate -> /api/django/crm/message-templates/<>  [MessageTemplateSerializer]
    champs: archived, corps, date_creation, date_modification, id, langue, langue_display, nom
    langue ∈ {darija, fr}
- frontend/src/api/crmApi.js :: deleteParrainage -> /api/django/crm/parrainages/<>  [ParrainageSerializer]
    champs: company, date_creation, filleul_client, filleul_display_nom, filleul_lead, filleul_nom, id, notes, parrain, parrain_nom, recompense, statut, statut_display
    statut ∈ {converti, en_attente, recompense_versee}
- frontend/src/api/crmApi.js :: deleteSavedView -> /api/django/crm/vues-enregistrees/<>  [SavedViewSerializer]
    champs: created_at, id, name, page, payload, rank, user
- frontend/src/api/crmApi.js :: getAppointments -> /api/django/crm/appointments  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: getConcurrentsPerte -> /api/django/crm/concurrents-perte  [ConcurrentPerteSerializer]
    champs: company, concurrent_nom, concurrent_prix, date_modification, devise, id, lead, lead_nom, motif, notes, saisi_le, saisi_par, saisi_par_nom
- frontend/src/api/crmApi.js :: getDefis -> /api/django/crm/defis  [DefiSerializer]
    champs: actif, cible_equipe, company, created_at, id, metrique, metrique_display, nom, periode_debut, periode_fin, recompense
    metrique ∈ {ca_signe, nb_contacts, nb_devis, nb_leads, nb_rdv}
- frontend/src/api/crmApi.js :: getEquipes -> /api/django/crm/equipes  [EquipeCommercialeSerializer]
    champs: actif, company, date_creation, id, membres, nb_membres, nom, responsable, responsable_nom
- frontend/src/api/crmApi.js :: getMessageTemplate -> /api/django/crm/message-templates/<>  [MessageTemplateSerializer]
    champs: archived, corps, date_creation, date_modification, id, langue, langue_display, nom
    langue ∈ {darija, fr}
- frontend/src/api/crmApi.js :: getMessageTemplates -> /api/django/crm/message-templates  [MessageTemplateSerializer]
    champs: archived, corps, date_creation, date_modification, id, langue, langue_display, nom
    langue ∈ {darija, fr}
- frontend/src/api/crmApi.js :: getParrainages -> /api/django/crm/parrainages  [ParrainageSerializer]
    champs: company, date_creation, filleul_client, filleul_display_nom, filleul_lead, filleul_nom, id, notes, parrain, parrain_nom, recompense, statut, statut_display
    statut ∈ {converti, en_attente, recompense_versee}
- frontend/src/api/crmApi.js :: getPlansActivite -> /api/django/crm/plans-activite  [PlanActiviteSerializer]
    champs: actif, company, date_creation, etapes, id, nom
- frontend/src/api/crmApi.js :: getSiteProfiles -> /api/django/crm/site-profiles  [SiteProfileSerializer]
    champs: client, company, conso_mensuelle_kwh, date_creation, date_modification, ete_differente, facture_ete, facture_hiver, gps_lat, gps_lng, id, inclinaison_deg, ombrage, ombrage_notes, orientation, pompe_cv, pompe_debit_m3h, pompe_hmt_m, raccordement, regularisation_8221, surface_toiture_m2, tranche_onee, type_installation, type_toiture
    ombrage ∈ {aucun, important, partiel}
    orientation ∈ {autre, est, ouest, sud, sud_est, sud_ouest}
    raccordement ∈ {aucun, inconnu, monophase, triphase}
    type_installation ∈ {agricole, commercial, industriel, residentiel}
    type_toiture ∈ {autre, bac_acier, fibrociment, terrasse_beton, tole_metal, tuiles}
- frontend/src/api/crmApi.js :: getVisitesExternes -> /api/django/crm/visites-externes  [VisiteExterneSerializer]
    champs: appareil_id, contexte, created_at, duree_s, id, ip, langue, lead, lead_nom, point, point_display, terminee, token_suffixe, user_agent
    point ∈ {booking, proposition, questionnaire, tunnel_lead, visite_site}
- frontend/src/api/crmApi.js :: getWebsiteLeadPayloads -> /api/django/crm/website-lead-payloads  [WebsiteLeadPayloadSerializer]
    champs: company, error, id, lead, lead_nom, payload, processed, received_at, remote_addr, source, source_display
    source ∈ {meta_lead_ads, website}
- frontend/src/api/crmApi.js :: listSavedViews -> /api/django/crm/vues-enregistrees  [SavedViewSerializer]
    champs: created_at, id, name, page, payload, rank, user
- frontend/src/api/crmApi.js :: updateAppointment -> /api/django/crm/appointments/<>  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: updateSiteProfile -> /api/django/crm/site-profiles/<>  [SiteProfileSerializer]
    champs: client, company, conso_mensuelle_kwh, date_creation, date_modification, ete_differente, facture_ete, facture_hiver, gps_lat, gps_lng, id, inclinaison_deg, ombrage, ombrage_notes, orientation, pompe_cv, pompe_debit_m3h, pompe_hmt_m, raccordement, regularisation_8221, surface_toiture_m2, tranche_onee, type_installation, type_toiture
    ombrage ∈ {aucun, important, partiel}
    orientation ∈ {autre, est, ouest, sud, sud_est, sud_ouest}
    raccordement ∈ {aucun, inconnu, monophase, triphase}
    type_installation ∈ {agricole, commercial, industriel, residentiel}
    type_toiture ∈ {autre, bac_acier, fibrociment, terrasse_beton, tole_metal, tuiles}
- frontend/src/api/customFieldsApi.js :: deleteDef -> /api/django/custom-fields/definitions/<>  [CustomFieldDefSerializer]
    champs: actif, code, conditions, formule, ia_prompt, id, libelle, module, obligatoire, options, ordre, relation_module, rollup_config, type, verrouille, visible_liste
    module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    relation_module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    type ∈ {boolean, choice, date, fichier, formula, ia, number, relation, rollup, text}
- frontend/src/api/customFieldsApi.js :: getDefs -> /api/django/custom-fields/definitions  [CustomFieldDefSerializer]
    champs: actif, code, conditions, formule, ia_prompt, id, libelle, module, obligatoire, options, ordre, relation_module, rollup_config, type, verrouille, visible_liste
    module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    relation_module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    type ∈ {boolean, choice, date, fichier, formula, ia, number, relation, rollup, text}
- frontend/src/api/demoApi.js :: setPresentationMode -> /api/django/companies/<>  [CompanySerializer]
    champs: actif, benchmarking_opt_in, date_creation, est_demo, id, mode_presentation_actif, nom, slug, tours_actifs
- frontend/src/api/demoApi.js :: setToursActifs -> /api/django/companies/<>  [CompanySerializer]
    champs: actif, benchmarking_opt_in, date_creation, est_demo, id, mode_presentation_actif, nom, slug, tours_actifs
- frontend/src/api/gedApi.js :: createAcl -> /api/django/ged/acls  [AclGedSerializer]
    champs: client, client_nom, created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: createAnnotation -> /api/django/ged/annotations  [AnnotationDocumentSerializer]
    champs: auteur, auteur_nom, contenu, created_at, id, page, type_annotation, version, x, y
- frontend/src/api/gedApi.js :: createCabinet -> /api/django/ged/cabinets  [CabinetSerializer]
    champs: created_at, description, id, nom, updated_at
- frontend/src/api/gedApi.js :: createChampSignature -> /api/django/ged/champs-signature  [ChampSignatureSerializer]
    champs: created_at, demande, hauteur, id, largeur, modele, page, requis, role, type_champ, type_champ_ref, type_champ_ref_detail, updated_at, valeur, x, y
- frontend/src/api/gedApi.js :: createCoffre -> /api/django/ged/coffres  [CoffreSerializer]
    champs: client, created_at, created_by, description, document_count, id, nom, proprietaire, proprietaire_nom, updated_at
- frontend/src/api/gedApi.js :: createDemandeDocument -> /api/django/ged/demandes-document  [DemandeDocumentSerializer]
    champs: created_at, created_by, derniere_relance_le, destinataire_email, destinataire_nom, document, echeance, exigence, folder, folder_nom, id, libelle, nombre_relances, statut, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: createDepotPublic -> /api/django/ged/depots-publics  [DepotPublicSerializer]
    champs: actif, created_at, created_by, created_by_nom, depots_effectues, expires_at, folder, folder_nom, id, is_accessible, is_expired, message, octets_deposes, quota_fichiers, quota_octets, token, updated_at
- frontend/src/api/gedApi.js :: createDossier -> /api/django/ged/dossiers  [FolderSerializer]
    champs: cabinet, cabinet_nom, created_at, id, nom, parent, parent_nom, path, updated_at
- frontend/src/api/gedApi.js :: createExigence -> /api/django/ged/exigences-dossier  [ExigenceDossierSerializer]
    champs: cabinet, created_at, created_by, description, folder, id, libelle, obligatoire, updated_at
- frontend/src/api/gedApi.js :: createModeleDocument -> /api/django/ged/modeles-document  [ModeleDocumentSerializer]
    champs: actif, cabinet_cible, categorie, corps_html, created_at, created_by, created_by_nom, description, dossier_cible, id, nom, sections, updated_at
- frontend/src/api/gedApi.js :: createPartage -> /api/django/ged/partages  [PartageGedSerializer]
    champs: actif, created_at, created_by, created_by_nom, document, document_nom, expires_at, has_password, id, is_accessible, is_expired, password, public_url, quota_exhausted, quota_max, telechargements, token, updated_at, watermark
- frontend/src/api/gedApi.js :: createPlanificationDocument -> /api/django/ged/planifications  [PlanificationDocumentSerializer]
    champs: assigne_a, assigne_a_nom, created_at, created_by, document, document_nom, echeance, faite, id, libelle, notifiee
- frontend/src/api/gedApi.js :: createPolitiqueRetention -> /api/django/ged/politiques-retention  [PolitiqueRetentionSerializer]
    champs: actif, action_echeance, cabinet, cabinet_nom, created_at, created_by, created_by_nom, description, duree_conservation_jours, folder, folder_nom, id, is_destructive, nom, scope, type_document, updated_at
- frontend/src/api/gedApi.js :: createRegleAclMetadonnee -> /api/django/ged/regles-acl-metadonnee  [RegleAclMetadonneeSerializer]
    champs: actif, condition_group, created_at, created_by, id, niveau, nom, priorite, role, role_nom, updated_at
- frontend/src/api/gedApi.js :: createRegleDossier -> /api/django/ged/regles-dossier  [RegleDossierSerializer]
    champs: actif, actions, condition_group, created_at, created_by, folder, folder_nom, id, nom, ordre, updated_at
- frontend/src/api/gedApi.js :: createRoutageDocumentaire -> /api/django/ged/routages-documentaires  [RoutageDocumentaireSerializer]
    champs: actif, cabinet_cible, cabinet_cible_nom, created_at, created_by, dossier_cible, id, source, tags_defaut, updated_at
- frontend/src/api/gedApi.js :: createTag -> /api/django/ged/tags  [DocumentTagSerializer]
    champs: chemin, couleur, created_at, description, document_count, id, nom, parent, parent_nom, slug, updated_at
- frontend/src/api/gedApi.js :: createTagAssignment -> /api/django/ged/tag-assignments  [DocumentTagAssignmentSerializer]
    champs: created_at, created_by, document, document_nom, id, tag, tag_nom
- frontend/src/api/gedApi.js :: createTamponSociete -> /api/django/ged/tampons-societe  [TamponSocieteSerializer]
    champs: created_at, id, libelle
- frontend/src/api/gedApi.js :: createVue -> /api/django/ged/vues  [VueGedEnregistreeSerializer]
    champs: created_at, criteres, est_a_moi, id, nom, partagee, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: deleteAcl -> /api/django/ged/acls/<>  [AclGedSerializer]
    champs: client, client_nom, created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: deleteChampSignature -> /api/django/ged/champs-signature/<>  [ChampSignatureSerializer]
    champs: created_at, demande, hauteur, id, largeur, modele, page, requis, role, type_champ, type_champ_ref, type_champ_ref_detail, updated_at, valeur, x, y
- frontend/src/api/gedApi.js :: deleteCoffre -> /api/django/ged/coffres/<>  [CoffreSerializer]
    champs: client, created_at, created_by, description, document_count, id, nom, proprietaire, proprietaire_nom, updated_at
- frontend/src/api/gedApi.js :: deleteExigence -> /api/django/ged/exigences-dossier/<>  [ExigenceDossierSerializer]
    champs: cabinet, created_at, created_by, description, folder, id, libelle, obligatoire, updated_at
- frontend/src/api/gedApi.js :: deletePlanificationDocument -> /api/django/ged/planifications/<>  [PlanificationDocumentSerializer]
    champs: assigne_a, assigne_a_nom, created_at, created_by, document, document_nom, echeance, faite, id, libelle, notifiee
- frontend/src/api/gedApi.js :: deletePolitiqueRetention -> /api/django/ged/politiques-retention/<>  [PolitiqueRetentionSerializer]
    champs: actif, action_echeance, cabinet, cabinet_nom, created_at, created_by, created_by_nom, description, duree_conservation_jours, folder, folder_nom, id, is_destructive, nom, scope, type_document, updated_at
- frontend/src/api/gedApi.js :: deleteRegleAclMetadonnee -> /api/django/ged/regles-acl-metadonnee/<>  [RegleAclMetadonneeSerializer]
    champs: actif, condition_group, created_at, created_by, id, niveau, nom, priorite, role, role_nom, updated_at
- frontend/src/api/gedApi.js :: deleteRegleDossier -> /api/django/ged/regles-dossier/<>  [RegleDossierSerializer]
    champs: actif, actions, condition_group, created_at, created_by, folder, folder_nom, id, nom, ordre, updated_at
- frontend/src/api/gedApi.js :: deleteRoutageDocumentaire -> /api/django/ged/routages-documentaires/<>  [RoutageDocumentaireSerializer]
    champs: actif, cabinet_cible, cabinet_cible_nom, created_at, created_by, dossier_cible, id, source, tags_defaut, updated_at
- frontend/src/api/gedApi.js :: deleteTag -> /api/django/ged/tags/<>  [DocumentTagSerializer]
    champs: chemin, couleur, created_at, description, document_count, id, nom, parent, parent_nom, slug, updated_at
- frontend/src/api/gedApi.js :: deleteTagAssignment -> /api/django/ged/tag-assignments/<>  [DocumentTagAssignmentSerializer]
    champs: created_at, created_by, document, document_nom, id, tag, tag_nom
- frontend/src/api/gedApi.js :: deleteTamponSociete -> /api/django/ged/tampons-societe/<>  [TamponSocieteSerializer]
    champs: created_at, id, libelle
- frontend/src/api/gedApi.js :: deleteVue -> /api/django/ged/vues/<>  [VueGedEnregistreeSerializer]
    champs: created_at, criteres, est_a_moi, id, nom, partagee, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: getAcls -> /api/django/ged/acls  [AclGedSerializer]
    champs: client, client_nom, created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: getCabinets -> /api/django/ged/cabinets  [CabinetSerializer]
    champs: created_at, description, id, nom, updated_at
- frontend/src/api/gedApi.js :: getChampsSignature -> /api/django/ged/champs-signature  [ChampSignatureSerializer]
    champs: created_at, demande, hauteur, id, largeur, modele, page, requis, role, type_champ, type_champ_ref, type_champ_ref_detail, updated_at, valeur, x, y
- frontend/src/api/gedApi.js :: getCoffres -> /api/django/ged/coffres  [CoffreSerializer]
    champs: client, created_at, created_by, description, document_count, id, nom, proprietaire, proprietaire_nom, updated_at
- frontend/src/api/gedApi.js :: getDemandesApprobation -> /api/django/ged/demandes-approbation  [DemandeApprobationSerializer]
    champs: approbateur, approbateur_nom, commentaire, created_at, decision_le, demandeur, demandeur_nom, document, document_nom, document_statut, id, is_pending, statut, statut_display, updated_at
- frontend/src/api/gedApi.js :: getDemandesDocument -> /api/django/ged/demandes-document  [DemandeDocumentSerializer]
    champs: created_at, created_by, derniere_relance_le, destinataire_email, destinataire_nom, document, echeance, exigence, folder, folder_nom, id, libelle, nombre_relances, statut, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: getDepotsPublics -> /api/django/ged/depots-publics  [DepotPublicSerializer]
    champs: actif, created_at, created_by, created_by_nom, depots_effectues, expires_at, folder, folder_nom, id, is_accessible, is_expired, message, octets_deposes, quota_fichiers, quota_octets, token, updated_at
- frontend/src/api/gedApi.js :: getDocuments -> /api/django/ged/documents  [DocumentSerializer]
    champs: coffre, contact_id, contact_label, created_at, created_by, created_by_nom, custom_data, derniere_version, description, est_dans_corbeille, est_document_lien, est_verrouille_avertissement, folder, folder_nom, id, is_locked, locked_at, locked_by, locked_by_nom, nom, proprietaire, proprietaire_nom, reference, statut, statut_display, supprime_le, supprime_par, supprime_par_nom, tags, transitions_autorisees, updated_at, url_externe, verrou_avertissement_le, verrou_avertissement_motif, verrou_avertissement_par, verrou_avertissement_par_nom, version_count, watermark_diffusion
- frontend/src/api/gedApi.js :: getDocumentsList -> /api/django/ged/documents  [DocumentSerializer]
    champs: coffre, contact_id, contact_label, created_at, created_by, created_by_nom, custom_data, derniere_version, description, est_dans_corbeille, est_document_lien, est_verrouille_avertissement, folder, folder_nom, id, is_locked, locked_at, locked_by, locked_by_nom, nom, proprietaire, proprietaire_nom, reference, statut, statut_display, supprime_le, supprime_par, supprime_par_nom, tags, transitions_autorisees, updated_at, url_externe, verrou_avertissement_le, verrou_avertissement_motif, verrou_avertissement_par, verrou_avertissement_par_nom, version_count, watermark_diffusion
- frontend/src/api/gedApi.js :: getDossiers -> /api/django/ged/dossiers  [FolderSerializer]
    champs: cabinet, cabinet_nom, created_at, id, nom, parent, parent_nom, path, updated_at
- frontend/src/api/gedApi.js :: getExigences -> /api/django/ged/exigences-dossier  [ExigenceDossierSerializer]
    champs: cabinet, created_at, created_by, description, folder, id, libelle, obligatoire, updated_at
- frontend/src/api/gedApi.js :: getJournalAcces -> /api/django/ged/journal-acces  [JournalAccesSerializer]
    champs: adresse_ip, created_at, document, document_nom, id, type_acces, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: getLotsEnvoi -> /api/django/ged/lots-envoi  [LotEnvoiSerializer]
    champs: created_at, created_by, id, libelle, modele, modele_nom, nb_envoyes, nb_erreurs, nb_refuses, nb_signes, nb_vus, resultats, total, updated_at
- frontend/src/api/gedApi.js :: getModelesDocument -> /api/django/ged/modeles-document  [ModeleDocumentSerializer]
    champs: actif, cabinet_cible, categorie, corps_html, created_at, created_by, created_by_nom, description, dossier_cible, id, nom, sections, updated_at
- frontend/src/api/gedApi.js :: getPartages -> /api/django/ged/partages  [PartageGedSerializer]
    champs: actif, created_at, created_by, created_by_nom, document, document_nom, expires_at, has_password, id, is_accessible, is_expired, password, public_url, quota_exhausted, quota_max, telechargements, token, updated_at, watermark
- frontend/src/api/gedApi.js :: getPlanificationsDocument -> /api/django/ged/planifications  [PlanificationDocumentSerializer]
    champs: assigne_a, assigne_a_nom, created_at, created_by, document, document_nom, echeance, faite, id, libelle, notifiee
- frontend/src/api/gedApi.js :: getPolitiquesRetention -> /api/django/ged/politiques-retention  [PolitiqueRetentionSerializer]
    champs: actif, action_echeance, cabinet, cabinet_nom, created_at, created_by, created_by_nom, description, duree_conservation_jours, folder, folder_nom, id, is_destructive, nom, scope, type_document, updated_at
- frontend/src/api/gedApi.js :: getQuotaStockage -> /api/django/ged/quotas-stockage  [QuotaStockageSerializer]
    champs: created_at, depasse, id, quota_octets, updated_at, utilise_octets
- frontend/src/api/gedApi.js :: getReglesAclMetadonnee -> /api/django/ged/regles-acl-metadonnee  [RegleAclMetadonneeSerializer]
    champs: actif, condition_group, created_at, created_by, id, niveau, nom, priorite, role, role_nom, updated_at
- frontend/src/api/gedApi.js :: getReglesDossier -> /api/django/ged/regles-dossier  [RegleDossierSerializer]
    champs: actif, actions, condition_group, created_at, created_by, folder, folder_nom, id, nom, ordre, updated_at
- frontend/src/api/gedApi.js :: getRolesSignataire -> /api/django/ged/roles-signataire  [RoleSignataireSerializer]
    champs: auth_extra, couleur, created_at, created_by, id, nom, peut_changer_signataire, updated_at
- frontend/src/api/gedApi.js :: getRoutagesDocumentaires -> /api/django/ged/routages-documentaires  [RoutageDocumentaireSerializer]
    champs: actif, cabinet_cible, cabinet_cible_nom, created_at, created_by, dossier_cible, id, source, tags_defaut, updated_at
- frontend/src/api/gedApi.js :: getSignatairesDemande -> /api/django/ged/signataires-demande  [SignataireDemandeSerializer]
    champs: created_at, date_action, demande, derniere_relance_le, email, id, motif_refus, nb_relances, nom, notifie_le, ordre, role, role_auth_extra, role_couleur, role_signataire, role_signataire_nom, statut, telephone, updated_at
- frontend/src/api/gedApi.js :: getTagAssignments -> /api/django/ged/tag-assignments  [DocumentTagAssignmentSerializer]
    champs: created_at, created_by, document, document_nom, id, tag, tag_nom
- frontend/src/api/gedApi.js :: getTags -> /api/django/ged/tags  [DocumentTagSerializer]
    champs: chemin, couleur, created_at, description, document_count, id, nom, parent, parent_nom, slug, updated_at
- frontend/src/api/gedApi.js :: getTamponsSociete -> /api/django/ged/tampons-societe  [TamponSocieteSerializer]
    champs: created_at, id, libelle
- frontend/src/api/gedApi.js :: getTypesChampSignature -> /api/django/ged/types-champ-signature  [TypeChampSignatureSerializer]
    champs: actif, astuce, auto_remplir, code, created_at, created_by, hauteur_defaut, id, largeur_defaut, lecture_seule, libelle, mode_saisie, options, placeholder, updated_at
- frontend/src/api/gedApi.js :: getValidationsOcr -> /api/django/ged/validations-ocr  [ValidationOcrDocumentSerializer]
    champs: champs_extraits, created_at, document, document_nom, id, score_confiance, updated_at, valide, valide_le, valide_par, valide_par_nom
- frontend/src/api/gedApi.js :: getVues -> /api/django/ged/vues  [VueGedEnregistreeSerializer]
    champs: created_at, criteres, est_a_moi, id, nom, partagee, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: renameDossier -> /api/django/ged/dossiers/<>  [FolderSerializer]
    champs: cabinet, cabinet_nom, created_at, id, nom, parent, parent_nom, path, updated_at
- frontend/src/api/gedApi.js :: setQuotaStockage -> /api/django/ged/quotas-stockage  [QuotaStockageSerializer]
    champs: created_at, depasse, id, quota_octets, updated_at, utilise_octets
- frontend/src/api/gedApi.js :: updateAcl -> /api/django/ged/acls/<>  [AclGedSerializer]
    champs: client, client_nom, created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: updatePlanificationDocument -> /api/django/ged/planifications/<>  [PlanificationDocumentSerializer]
    champs: assigne_a, assigne_a_nom, created_at, created_by, document, document_nom, echeance, faite, id, libelle, notifiee
- frontend/src/api/gedApi.js :: updatePolitiqueRetention -> /api/django/ged/politiques-retention/<>  [PolitiqueRetentionSerializer]
    champs: actif, action_echeance, cabinet, cabinet_nom, created_at, created_by, created_by_nom, description, duree_conservation_jours, folder, folder_nom, id, is_destructive, nom, scope, type_document, updated_at
- frontend/src/api/gedApi.js :: updateRegleAclMetadonnee -> /api/django/ged/regles-acl-metadonnee/<>  [RegleAclMetadonneeSerializer]
    champs: actif, condition_group, created_at, created_by, id, niveau, nom, priorite, role, role_nom, updated_at
- frontend/src/api/gedApi.js :: updateRegleDossier -> /api/django/ged/regles-dossier/<>  [RegleDossierSerializer]
    champs: actif, actions, condition_group, created_at, created_by, folder, folder_nom, id, nom, ordre, updated_at
- frontend/src/api/gedApi.js :: updateRoutageDocumentaire -> /api/django/ged/routages-documentaires/<>  [RoutageDocumentaireSerializer]
    champs: actif, cabinet_cible, cabinet_cible_nom, created_at, created_by, dossier_cible, id, source, tags_defaut, updated_at
- frontend/src/api/gedApi.js :: updateTag -> /api/django/ged/tags/<>  [DocumentTagSerializer]
    champs: chemin, couleur, created_at, description, document_count, id, nom, parent, parent_nom, slug, updated_at
- frontend/src/api/identityApi.js :: forget -> /api/django/identity/trusted-devices/<>  [TrustedDeviceSerializer]
    champs: approuve_le, expire_le, id, is_active, label, revoque_le
- frontend/src/api/installationsApi.js :: createBinAffectation -> /api/django/installations/bin-affectations  [BinAffectationSerializer]
    champs: bin, date_creation, date_modification, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: createBinLocation -> /api/django/installations/bin-locations  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: createColis -> /api/django/installations/colis  [ColisSerializer]
    champs: controle_par, created_by, date_controle, date_creation, date_modification, id, installation, lignes, note, poids_kg, reference, statut, statut_display
    statut ∈ {controle, expedie, preparation}
- frontend/src/api/installationsApi.js :: createColisLigne -> /api/django/installations/colis-lignes  [ColisLigneSerializer]
    champs: colis, controle_ok, designation, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: createControleQualiteModele -> /api/django/installations/controle-qualite-modeles  [ControleQualiteModeleSerializer]
    champs: active, date_creation, date_modification, id, items, kit
- frontend/src/api/installationsApi.js :: createDemandeAchat -> /api/django/installations/demandes-achat  [DemandeAchatSerializer]
    champs: approuvee_par, archivee, bon_commande, chantier, created_by, date_archivage, date_besoin, date_creation, date_decision, date_modification, epinglee, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: createDemandeAchatLigne -> /api/django/installations/demandes-achat-lignes  [DemandeAchatLigneSerializer]
    champs: demande, designation, id, prix_estime, produit, produit_nom, quantite, total_estime
- frontend/src/api/installationsApi.js :: createDemandeTransfert -> /api/django/installations/demandes-transfert  [DemandeTransfertSerializer]
    champs: approuve_par, created_by, date_approbation, date_creation, date_execution, date_modification, destination, destination_nom, id, motif, motif_refus, produit, produit_nom, quantite, reference, source, source_nom, statut, statut_display
    statut ∈ {approuve, demande, execute, refuse}
- frontend/src/api/installationsApi.js :: createDossierImport -> /api/django/installations/dossiers-import  [DossierImportSerializer]
    champs: bon_commande, created_by, date_arrivee_port, date_creation, date_dedouanement, date_depart, date_modification, designation, fournisseur, fournisseur_nom, id, incoterm, incoterm_display, note, numero_bl, numero_conteneur, port_arrivee, reference, statut_douane, statut_douane_display
    incoterm ∈ {cfr, cif, dap, ddp, exw, fob}
    statut_douane ∈ {arrive_port, commande, dedouane, en_douane, expedie, livre}
- frontend/src/api/installationsApi.js :: createEtapeAssemblageKit -> /api/django/installations/etapes-assemblage  [EtapeAssemblageSerializer]
    champs: duree_attendue_min, id, instructions, kit, libelle, ordre, piece_jointe
- frontend/src/api/installationsApi.js :: createFraisImport -> /api/django/installations/frais-import  [FraisImportSerializer]
    champs: categorie, categorie_display, created_by, date_creation, date_frais, dossier, id, libelle, montant
    categorie ∈ {assurance, autre, douane, fret, manutention, transit, tva_import}
- frontend/src/api/installationsApi.js :: createGpsConsentement -> /api/django/installations/gps-consentements  [GpsConsentRecordSerializer]
    champs: consent_recorded_at, consent_ref, id, is_active, recorded_by, revoked_at, revoked_reason, technicien, technicien_nom
- frontend/src/api/installationsApi.js :: createKit -> /api/django/installations/kits  [KitSerializer]
    champs: active, composants, created_by, date_creation, date_modification, id, nom, note, produit_compose, produit_compose_nom, reference_interne
- frontend/src/api/installationsApi.js :: createKitComposant -> /api/django/installations/kit-composants  [KitComposantSerializer]
    champs: designation, id, kit, produit, produit_nom, quantite, taux_perte_pct
- frontend/src/api/installationsApi.js :: createLandedCostLigne -> /api/django/installations/landed-cost-lignes  [LandedCostLigneSerializer]
    champs: cout_fob_unitaire, date_creation, designation, dossier, id, produit, produit_nom, quantite, valeur_fob
- frontend/src/api/installationsApi.js :: createLigneAssemblage -> /api/django/installations/ordre-assemblage-lignes  [OrdreAssemblageLigneSerializer]
    champs: designation, id, ordre, origine, produit, produit_nom, quantite
    origine ∈ {ajout, kit}
- frontend/src/api/installationsApi.js :: createLivraison -> /api/django/installations/livraisons  [LivraisonSerializer]
    champs: adresse_site, cout_transport, created_by, date_creation, date_modification, date_prevue, depot, depot_nom, id, installation, installation_reference, lignes, mode_acheminement, mode_acheminement_display, note, numero_suivi, reference, statut, statut_display, stock_mouvemente, transporteur, transporteur_nom, transporteur_obj_nom
    mode_acheminement ∈ {depot, direct_site}
    statut ∈ {annulee, en_transit, livree, planifiee}
- frontend/src/api/installationsApi.js :: createLivraisonLigne -> /api/django/installations/livraison-lignes  [LivraisonLigneSerializer]
    champs: designation, id, livraison, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: createOrdreAssemblage -> /api/django/installations/ordres-assemblage  [OrdreAssemblageSerializer]
    champs: chantier, cout_prevu, created_by, date_creation, date_modification, date_prevue, date_terminaison, devis, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, motif_annulation, note, ordre_sous_traitance, quantite, quantite_produite, reference, responsable, responsable_nom, revision_kit_numero, sous_traitant, statut, statut_display, stock_mouvemente, temps_prevu_min, temps_reel_min
    statut ∈ {annule, en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: createOrdreDemontage -> /api/django/installations/ordres-demontage  [OrdreDemontageSerializer]
    champs: created_by, date_creation, date_modification, date_terminaison, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, note, quantite, reference, statut, statut_display, stock_mouvemente
    statut ∈ {planifie, termine}
- frontend/src/api/installationsApi.js :: createPickList -> /api/django/installations/pick-lists  [PickListSerializer]
    champs: created_by, date_creation, date_modification, id, installation, lignes, note, reference, statut, statut_display
    statut ∈ {emis, en_cours, termine}
- frontend/src/api/installationsApi.js :: createPreuveLivraison -> /api/django/installations/preuves-livraison  [PreuveLivraisonSerializer]
    champs: created_by, date_creation, date_modification, gps_lat, gps_lng, horodatage, id, livraison, note, photo, signataire_nom, signature_data
- frontend/src/api/installationsApi.js :: createPutAway -> /api/django/installations/putaways  [PutAwaySerializer]
    champs: bin_effectif, bin_effectif_code, bin_suggere, bin_suggere_code, created_by, date_creation, date_modification, date_rangement, emplacement, id, note, produit, produit_nom, quantite, range_par, reference_reception, statut, statut_display
    statut ∈ {a_ranger, range}
- frontend/src/api/installationsApi.js :: createSessionComptage -> /api/django/installations/sessions-comptage  [SessionComptageSerializer]
    champs: classe_abc, classe_abc_display, created_by, date_creation, date_modification, date_planifiee, emplacement, id, intitule, lignes, note, reference, statut, statut_display
    classe_abc ∈ {A, B, C, toutes}
    statut ∈ {en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: createTransporteur -> /api/django/installations/transporteurs  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/installationsApi.js :: deleteBinAffectation -> /api/django/installations/bin-affectations/<>  [BinAffectationSerializer]
    champs: bin, date_creation, date_modification, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: deleteBinLocation -> /api/django/installations/bin-locations/<>  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: deleteColisLigne -> /api/django/installations/colis-lignes/<>  [ColisLigneSerializer]
    champs: colis, controle_ok, designation, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: deleteDemandeAchat -> /api/django/installations/demandes-achat/<>  [DemandeAchatSerializer]
    champs: approuvee_par, archivee, bon_commande, chantier, created_by, date_archivage, date_besoin, date_creation, date_decision, date_modification, epinglee, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: deleteDemandeAchatLigne -> /api/django/installations/demandes-achat-lignes/<>  [DemandeAchatLigneSerializer]
    champs: demande, designation, id, prix_estime, produit, produit_nom, quantite, total_estime
- frontend/src/api/installationsApi.js :: deleteEquipeTerrain -> /api/django/installations/equipes/<>  [EquipeSerializer]
    champs: actif, chef, chef_nom, created_by, date_creation, date_modification, description, id, membres, membres_noms, nb_membres, nom
- frontend/src/api/installationsApi.js :: deleteEtapeAssemblageKit -> /api/django/installations/etapes-assemblage/<>  [EtapeAssemblageSerializer]
    champs: duree_attendue_min, id, instructions, kit, libelle, ordre, piece_jointe
- frontend/src/api/installationsApi.js :: deleteFicheChamp -> /api/django/installations/fiche-intervention-champs/<>  [FicheInterventionChampSerializer]
    champs: cle, id, libelle, obligatoire, ordre, template, type_champ, unite
    type_champ ∈ {case, mesure, nombre, texte}
- frontend/src/api/installationsApi.js :: deleteFicheTemplate -> /api/django/installations/fiche-intervention-templates/<>  [FicheInterventionTemplateSerializer]
    champs: actif, champs, id, nom, protege, type_intervention
- frontend/src/api/installationsApi.js :: deleteFraisImport -> /api/django/installations/frais-import/<>  [FraisImportSerializer]
    champs: categorie, categorie_display, created_by, date_creation, date_frais, dossier, id, libelle, montant
    categorie ∈ {assurance, autre, douane, fret, manutention, transit, tva_import}
- frontend/src/api/installationsApi.js :: deleteKitComposant -> /api/django/installations/kit-composants/<>  [KitComposantSerializer]
    champs: designation, id, kit, produit, produit_nom, quantite, taux_perte_pct
- frontend/src/api/installationsApi.js :: deleteLandedCostLigne -> /api/django/installations/landed-cost-lignes/<>  [LandedCostLigneSerializer]
    champs: cout_fob_unitaire, date_creation, designation, dossier, id, produit, produit_nom, quantite, valeur_fob
- frontend/src/api/installationsApi.js :: deleteLigneAssemblage -> /api/django/installations/ordre-assemblage-lignes/<>  [OrdreAssemblageLigneSerializer]
    champs: designation, id, ordre, origine, produit, produit_nom, quantite
    origine ∈ {ajout, kit}
- frontend/src/api/installationsApi.js :: deleteLivraison -> /api/django/installations/livraisons/<>  [LivraisonSerializer]
    champs: adresse_site, cout_transport, created_by, date_creation, date_modification, date_prevue, depot, depot_nom, id, installation, installation_reference, lignes, mode_acheminement, mode_acheminement_display, note, numero_suivi, reference, statut, statut_display, stock_mouvemente, transporteur, transporteur_nom, transporteur_obj_nom
    mode_acheminement ∈ {depot, direct_site}
    statut ∈ {annulee, en_transit, livree, planifiee}
- frontend/src/api/installationsApi.js :: deleteLivraisonLigne -> /api/django/installations/livraison-lignes/<>  [LivraisonLigneSerializer]
    champs: designation, id, livraison, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: deleteOrdreAssemblage -> /api/django/installations/ordres-assemblage/<>  [OrdreAssemblageSerializer]
    champs: chantier, cout_prevu, created_by, date_creation, date_modification, date_prevue, date_terminaison, devis, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, motif_annulation, note, ordre_sous_traitance, quantite, quantite_produite, reference, responsable, responsable_nom, revision_kit_numero, sous_traitant, statut, statut_display, stock_mouvemente, temps_prevu_min, temps_reel_min
    statut ∈ {annule, en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: deleteOrdreDemontage -> /api/django/installations/ordres-demontage/<>  [OrdreDemontageSerializer]
    champs: created_by, date_creation, date_modification, date_terminaison, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, note, quantite, reference, statut, statut_display, stock_mouvemente
    statut ∈ {planifie, termine}
- frontend/src/api/installationsApi.js :: deleteRegleApprobationAchat -> /api/django/installations/regles-approbation-achat/<>  [RegleApprobationAchatSerializer]
    champs: actif, autorise_depassement_budget, chantier, date_creation, id, libelle, montant_max, montant_min, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, programme
    niveau_approbation ∈ {administrateur, direction, responsable}
- frontend/src/api/installationsApi.js :: deleteStageChantier -> /api/django/installations/etapes-chantier/<>  [StageModeleSerializer]
    champs: actif, bloquant, checklist_pct_min, cle, exige_checklist, exige_dossier, exige_materiel, exige_pack, exige_photos, exige_series, exige_tests, id, libelle, ordre, photos_min, protege, statut_legacy, statut_legacy_display
- frontend/src/api/installationsApi.js :: deleteTransporteur -> /api/django/installations/transporteurs/<>  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/installationsApi.js :: getAppelsCommande -> /api/django/installations/appels-commande  [AppelCommandeSerializer]
    champs: chantier, created_by, date_appel, date_creation, id, ligne, montant, note, quantite
- frontend/src/api/installationsApi.js :: getApprobationsBcf -> /api/django/installations/approbations-bcf  [ApprobationBCFSerializer]
    champs: approuve_par, bcf, date_approbation, id, montant_approuve, note, palier, palier_display
- frontend/src/api/installationsApi.js :: getBinAffectations -> /api/django/installations/bin-affectations  [BinAffectationSerializer]
    champs: bin, date_creation, date_modification, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: getBinLocation -> /api/django/installations/bin-locations/<>  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: getBinLocations -> /api/django/installations/bin-locations  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: getColis -> /api/django/installations/colis/<>  [ColisSerializer]
    champs: controle_par, created_by, date_controle, date_creation, date_modification, id, installation, lignes, note, poids_kg, reference, statut, statut_display
    statut ∈ {controle, expedie, preparation}
- frontend/src/api/installationsApi.js :: getColisLignes -> /api/django/installations/colis-lignes  [ColisLigneSerializer]
    champs: colis, controle_ok, designation, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: getColisList -> /api/django/installations/colis  [ColisSerializer]
    champs: controle_par, created_by, date_controle, date_creation, date_modification, id, installation, lignes, note, poids_kg, reference, statut, statut_display
    statut ∈ {controle, expedie, preparation}
- frontend/src/api/installationsApi.js :: getCommandesCadre -> /api/django/installations/commandes-cadre  [CommandeCadreSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display
    statut ∈ {actif, brouillon, clos}
- frontend/src/api/installationsApi.js :: getComptageLignes -> /api/django/installations/comptage-lignes  [ComptageLigneSerializer]
    champs: compte, designation, ecart, id, produit, produit_nom, quantite_comptee, quantite_theorique, session
- frontend/src/api/installationsApi.js :: getContratsPrixFournisseur -> /api/django/installations/contrats-prix-fournisseur  [ContratPrixFournisseurSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display, version
    statut ∈ {actif, brouillon, expire}
- frontend/src/api/installationsApi.js :: getControleQualiteModeles -> /api/django/installations/controle-qualite-modeles  [ControleQualiteModeleSerializer]
    champs: active, date_creation, date_modification, id, items, kit
- frontend/src/api/installationsApi.js :: getDemandeAchat -> /api/django/installations/demandes-achat/<>  [DemandeAchatSerializer]
    champs: approuvee_par, archivee, bon_commande, chantier, created_by, date_archivage, date_besoin, date_creation, date_decision, date_modification, epinglee, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: getDemandeTransfert -> /api/django/installations/demandes-transfert/<>  [DemandeTransfertSerializer]
    champs: approuve_par, created_by, date_approbation, date_creation, date_execution, date_modification, destination, destination_nom, id, motif, motif_refus, produit, produit_nom, quantite, reference, source, source_nom, statut, statut_display
    statut ∈ {approuve, demande, execute, refuse}
- frontend/src/api/installationsApi.js :: getDemandesAchat -> /api/django/installations/demandes-achat  [DemandeAchatSerializer]
    champs: approuvee_par, archivee, bon_commande, chantier, created_by, date_archivage, date_besoin, date_creation, date_decision, date_modification, epinglee, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: getDemandesTransfert -> /api/django/installations/demandes-transfert  [DemandeTransfertSerializer]
    champs: approuve_par, created_by, date_approbation, date_creation, date_execution, date_modification, destination, destination_nom, id, motif, motif_refus, produit, produit_nom, quantite, reference, source, source_nom, statut, statut_display
    statut ∈ {approuve, demande, execute, refuse}
- frontend/src/api/installationsApi.js :: getDossierImport -> /api/django/installations/dossiers-import/<>  [DossierImportSerializer]
    champs: bon_commande, created_by, date_arrivee_port, date_creation, date_dedouanement, date_depart, date_modification, designation, fournisseur, fournisseur_nom, id, incoterm, incoterm_display, note, numero_bl, numero_conteneur, port_arrivee, reference, statut_douane, statut_douane_display
    incoterm ∈ {cfr, cif, dap, ddp, exw, fob}
    statut_douane ∈ {arrive_port, commande, dedouane, en_douane, expedie, livre}
- frontend/src/api/installationsApi.js :: getDossiersImport -> /api/django/installations/dossiers-import  [DossierImportSerializer]
    champs: bon_commande, created_by, date_arrivee_port, date_creation, date_dedouanement, date_depart, date_modification, designation, fournisseur, fournisseur_nom, id, incoterm, incoterm_display, note, numero_bl, numero_conteneur, port_arrivee, reference, statut_douane, statut_douane_display
    incoterm ∈ {cfr, cif, dap, ddp, exw, fob}
    statut_douane ∈ {arrive_port, commande, dedouane, en_douane, expedie, livre}
- frontend/src/api/installationsApi.js :: getEquipesTerrain -> /api/django/installations/equipes  [EquipeSerializer]
    champs: actif, chef, chef_nom, created_by, date_creation, date_modification, description, id, membres, membres_noms, nb_membres, nom
- frontend/src/api/installationsApi.js :: getEtapesAssemblageKit -> /api/django/installations/etapes-assemblage  [EtapeAssemblageSerializer]
    champs: duree_attendue_min, id, instructions, kit, libelle, ordre, piece_jointe
- frontend/src/api/installationsApi.js :: getFicheTemplates -> /api/django/installations/fiche-intervention-templates  [FicheInterventionTemplateSerializer]
    champs: actif, champs, id, nom, protege, type_intervention
- frontend/src/api/installationsApi.js :: getFraisImport -> /api/django/installations/frais-import  [FraisImportSerializer]
    champs: categorie, categorie_display, created_by, date_creation, date_frais, dossier, id, libelle, montant
    categorie ∈ {assurance, autre, douane, fret, manutention, transit, tva_import}
- frontend/src/api/installationsApi.js :: getGeofenceAlertes -> /api/django/installations/geofence-alertes  [GeofenceAlertSerializer]
    champs: acquittee, acquittee_le, acquittee_par, created_at, distance_site_km, id, intervention, position, rayon_attendu_km, technicien, technicien_nom, type_franchissement, type_franchissement_display
    type_franchissement ∈ {entree, sortie}
- frontend/src/api/installationsApi.js :: getGpsConsentements -> /api/django/installations/gps-consentements  [GpsConsentRecordSerializer]
    champs: consent_recorded_at, consent_ref, id, is_active, recorded_by, revoked_at, revoked_reason, technicien, technicien_nom
- frontend/src/api/installationsApi.js :: getKitComposants -> /api/django/installations/kit-composants  [KitComposantSerializer]
    champs: designation, id, kit, produit, produit_nom, quantite, taux_perte_pct
- frontend/src/api/installationsApi.js :: getKitsAssemblage -> /api/django/installations/kits  [KitSerializer]
    champs: active, composants, created_by, date_creation, date_modification, id, nom, note, produit_compose, produit_compose_nom, reference_interne
- frontend/src/api/installationsApi.js :: getLandedCostLignes -> /api/django/installations/landed-cost-lignes  [LandedCostLigneSerializer]
    champs: cout_fob_unitaire, date_creation, designation, dossier, id, produit, produit_nom, quantite, valeur_fob
- frontend/src/api/installationsApi.js :: getLignesAssemblage -> /api/django/installations/ordre-assemblage-lignes  [OrdreAssemblageLigneSerializer]
    champs: designation, id, ordre, origine, produit, produit_nom, quantite
    origine ∈ {ajout, kit}
- frontend/src/api/installationsApi.js :: getLivraison -> /api/django/installations/livraisons/<>  [LivraisonSerializer]
    champs: adresse_site, cout_transport, created_by, date_creation, date_modification, date_prevue, depot, depot_nom, id, installation, installation_reference, lignes, mode_acheminement, mode_acheminement_display, note, numero_suivi, reference, statut, statut_display, stock_mouvemente, transporteur, transporteur_nom, transporteur_obj_nom
    mode_acheminement ∈ {depot, direct_site}
    statut ∈ {annulee, en_transit, livree, planifiee}
- frontend/src/api/installationsApi.js :: getLivraisonLignes -> /api/django/installations/livraison-lignes  [LivraisonLigneSerializer]
    champs: designation, id, livraison, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: getLivraisons -> /api/django/installations/livraisons  [LivraisonSerializer]
    champs: adresse_site, cout_transport, created_by, date_creation, date_modification, date_prevue, depot, depot_nom, id, installation, installation_reference, lignes, mode_acheminement, mode_acheminement_display, note, numero_suivi, reference, statut, statut_display, stock_mouvemente, transporteur, transporteur_nom, transporteur_obj_nom
    mode_acheminement ∈ {depot, direct_site}
    statut ∈ {annulee, en_transit, livree, planifiee}
- frontend/src/api/installationsApi.js :: getOrdreAssemblage -> /api/django/installations/ordres-assemblage/<>  [OrdreAssemblageSerializer]
    champs: chantier, cout_prevu, created_by, date_creation, date_modification, date_prevue, date_terminaison, devis, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, motif_annulation, note, ordre_sous_traitance, quantite, quantite_produite, reference, responsable, responsable_nom, revision_kit_numero, sous_traitant, statut, statut_display, stock_mouvemente, temps_prevu_min, temps_reel_min
    statut ∈ {annule, en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: getOrdreDemontage -> /api/django/installations/ordres-demontage/<>  [OrdreDemontageSerializer]
    champs: created_by, date_creation, date_modification, date_terminaison, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, note, quantite, reference, statut, statut_display, stock_mouvemente
    statut ∈ {planifie, termine}
- frontend/src/api/installationsApi.js :: getOrdresAssemblage -> /api/django/installations/ordres-assemblage  [OrdreAssemblageSerializer]
    champs: chantier, cout_prevu, created_by, date_creation, date_modification, date_prevue, date_terminaison, devis, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, motif_annulation, note, ordre_sous_traitance, quantite, quantite_produite, reference, responsable, responsable_nom, revision_kit_numero, sous_traitant, statut, statut_display, stock_mouvemente, temps_prevu_min, temps_reel_min
    statut ∈ {annule, en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: getOrdresDemontage -> /api/django/installations/ordres-demontage  [OrdreDemontageSerializer]
    champs: created_by, date_creation, date_modification, date_terminaison, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, note, quantite, reference, statut, statut_display, stock_mouvemente
    statut ∈ {planifie, termine}
- frontend/src/api/installationsApi.js :: getPickList -> /api/django/installations/pick-lists/<>  [PickListSerializer]
    champs: created_by, date_creation, date_modification, id, installation, lignes, note, reference, statut, statut_display
    statut ∈ {emis, en_cours, termine}
- frontend/src/api/installationsApi.js :: getPickListLignes -> /api/django/installations/pick-list-lignes  [PickListLigneSerializer]
    champs: bin, bin_code, designation, id, ordre, pick_list, preleve, produit, produit_nom, quantite_demandee, quantite_prelevee
- frontend/src/api/installationsApi.js :: getPickLists -> /api/django/installations/pick-lists  [PickListSerializer]
    champs: created_by, date_creation, date_modification, id, installation, lignes, note, reference, statut, statut_display
    statut ∈ {emis, en_cours, termine}
- frontend/src/api/installationsApi.js :: getPositionsTechniciens -> /api/django/installations/positions-techniciens  [PositionTechnicienSerializer]
    champs: accuracy_m, captured_at, distance_site_km, hors_perimetre, id, intervention, lat, lng, technicien, technicien_nom
- frontend/src/api/installationsApi.js :: getPreuveLivraison -> /api/django/installations/preuves-livraison/<>  [PreuveLivraisonSerializer]
    champs: created_by, date_creation, date_modification, gps_lat, gps_lng, horodatage, id, livraison, note, photo, signataire_nom, signature_data
- frontend/src/api/installationsApi.js :: getPreuvesLivraison -> /api/django/installations/preuves-livraison  [PreuveLivraisonSerializer]
    champs: created_by, date_creation, date_modification, gps_lat, gps_lng, horodatage, id, livraison, note, photo, signataire_nom, signature_data
- frontend/src/api/installationsApi.js :: getPutAway -> /api/django/installations/putaways/<>  [PutAwaySerializer]
    champs: bin_effectif, bin_effectif_code, bin_suggere, bin_suggere_code, created_by, date_creation, date_modification, date_rangement, emplacement, id, note, produit, produit_nom, quantite, range_par, reference_reception, statut, statut_display
    statut ∈ {a_ranger, range}
- frontend/src/api/installationsApi.js :: getPutAways -> /api/django/installations/putaways  [PutAwaySerializer]
    champs: bin_effectif, bin_effectif_code, bin_suggere, bin_suggere_code, created_by, date_creation, date_modification, date_rangement, emplacement, id, note, produit, produit_nom, quantite, range_par, reference_reception, statut, statut_display
    statut ∈ {a_ranger, range}
- frontend/src/api/installationsApi.js :: getReceptionsNonFacturees -> /api/django/installations/receptions-non-facturees  [ReceptionNonFactureeSerializer]
    champs: bon_commande, created_by, date_creation, date_lettrage, date_modification, date_reception, facture, id, lettre, libelle, montant_a_provisionner, montant_provision, note, reception
- frontend/src/api/installationsApi.js :: getRecetteRecord -> /api/django/installations/recettes-commissioning/<>  [CommissioningRecordSerializer]
    champs: continuite_terre_ohm, continuite_terre_ok, date_essai, doc_datasheets_ok, doc_dossier_ok, doc_schema_ok, id, installation, instrument_etalonnage_expire, instrument_id, instrument_nom, instrument_numero_serie, isolement_mohm, isolement_ok, iv_readings, observations, passe, performance_ok, polarite_ok, production_attendue_kw, production_test_kw, resultat, resultat_display, securite_coupure_ok, securite_signalisation_ok, technicien, ventes_recette_id, visuel_cablage_ok, visuel_structure_ok, visuel_terre_ok
    resultat ∈ {conforme, en_cours, non_conforme, reserves}
- frontend/src/api/installationsApi.js :: getReglesApprobationAchat -> /api/django/installations/regles-approbation-achat  [RegleApprobationAchatSerializer]
    champs: actif, autorise_depassement_budget, chantier, date_creation, id, libelle, montant_max, montant_min, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, programme
    niveau_approbation ∈ {administrateur, direction, responsable}
- frontend/src/api/installationsApi.js :: getSessionComptage -> /api/django/installations/sessions-comptage/<>  [SessionComptageSerializer]
    champs: classe_abc, classe_abc_display, created_by, date_creation, date_modification, date_planifiee, emplacement, id, intitule, lignes, note, reference, statut, statut_display
    classe_abc ∈ {A, B, C, toutes}
    statut ∈ {en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: getSessionsComptage -> /api/django/installations/sessions-comptage  [SessionComptageSerializer]
    champs: classe_abc, classe_abc_display, created_by, date_creation, date_modification, date_planifiee, emplacement, id, intitule, lignes, note, reference, statut, statut_display
    classe_abc ∈ {A, B, C, toutes}
    statut ∈ {en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: getSeuilsApprobationBcf -> /api/django/installations/seuils-approbation-bcf  [SeuilApprobationBCFSerializer]
    champs: actif, date_creation, date_modification, id, seuil_responsable
- frontend/src/api/installationsApi.js :: getStagesChantier -> /api/django/installations/etapes-chantier  [StageModeleSerializer]
    champs: actif, bloquant, checklist_pct_min, cle, exige_checklist, exige_dossier, exige_materiel, exige_pack, exige_photos, exige_series, exige_tests, id, libelle, ordre, photos_min, protege, statut_legacy, statut_legacy_display
- frontend/src/api/installationsApi.js :: getTransporteurs -> /api/django/installations/transporteurs  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/installationsApi.js :: updateBinAffectation -> /api/django/installations/bin-affectations/<>  [BinAffectationSerializer]
    champs: bin, date_creation, date_modification, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: updateBinLocation -> /api/django/installations/bin-locations/<>  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: updateColis -> /api/django/installations/colis/<>  [ColisSerializer]
    champs: controle_par, created_by, date_controle, date_creation, date_modification, id, installation, lignes, note, poids_kg, reference, statut, statut_display
    statut ∈ {controle, expedie, preparation}
- frontend/src/api/installationsApi.js :: updateColisLigne -> /api/django/installations/colis-lignes/<>  [ColisLigneSerializer]
    champs: colis, controle_ok, designation, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: updateComptageLigne -> /api/django/installations/comptage-lignes/<>  [ComptageLigneSerializer]
    champs: compte, designation, ecart, id, produit, produit_nom, quantite_comptee, quantite_theorique, session
- frontend/src/api/installationsApi.js :: updateControleQualiteModele -> /api/django/installations/controle-qualite-modeles/<>  [ControleQualiteModeleSerializer]
    champs: active, date_creation, date_modification, id, items, kit
- frontend/src/api/installationsApi.js :: updateDemandeAchat -> /api/django/installations/demandes-achat/<>  [DemandeAchatSerializer]
    champs: approuvee_par, archivee, bon_commande, chantier, created_by, date_archivage, date_besoin, date_creation, date_decision, date_modification, epinglee, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: updateDemandeTransfert -> /api/django/installations/demandes-transfert/<>  [DemandeTransfertSerializer]
    champs: approuve_par, created_by, date_approbation, date_creation, date_execution, date_modification, destination, destination_nom, id, motif, motif_refus, produit, produit_nom, quantite, reference, source, source_nom, statut, statut_display
    statut ∈ {approuve, demande, execute, refuse}
- frontend/src/api/installationsApi.js :: updateDossierImport -> /api/django/installations/dossiers-import/<>  [DossierImportSerializer]
    champs: bon_commande, created_by, date_arrivee_port, date_creation, date_dedouanement, date_depart, date_modification, designation, fournisseur, fournisseur_nom, id, incoterm, incoterm_display, note, numero_bl, numero_conteneur, port_arrivee, reference, statut_douane, statut_douane_display
    incoterm ∈ {cfr, cif, dap, ddp, exw, fob}
    statut_douane ∈ {arrive_port, commande, dedouane, en_douane, expedie, livre}
- frontend/src/api/installationsApi.js :: updateEtapeAssemblageKit -> /api/django/installations/etapes-assemblage/<>  [EtapeAssemblageSerializer]
    champs: duree_attendue_min, id, instructions, kit, libelle, ordre, piece_jointe
- frontend/src/api/installationsApi.js :: updateKit -> /api/django/installations/kits/<>  [KitSerializer]
    champs: active, composants, created_by, date_creation, date_modification, id, nom, note, produit_compose, produit_compose_nom, reference_interne
- frontend/src/api/installationsApi.js :: updateKitComposant -> /api/django/installations/kit-composants/<>  [KitComposantSerializer]
    champs: designation, id, kit, produit, produit_nom, quantite, taux_perte_pct
- frontend/src/api/installationsApi.js :: updateLigneAssemblage -> /api/django/installations/ordre-assemblage-lignes/<>  [OrdreAssemblageLigneSerializer]
    champs: designation, id, ordre, origine, produit, produit_nom, quantite
    origine ∈ {ajout, kit}
- frontend/src/api/installationsApi.js :: updateLigneDemontage -> /api/django/installations/ordre-demontage-lignes/<>  [OrdreDemontageLigneSerializer]
    champs: designation, id, ordre, produit, produit_nom, quantite_attendue, quantite_recuperee
- frontend/src/api/installationsApi.js :: updateLivraison -> /api/django/installations/livraisons/<>  [LivraisonSerializer]
    champs: adresse_site, cout_transport, created_by, date_creation, date_modification, date_prevue, depot, depot_nom, id, installation, installation_reference, lignes, mode_acheminement, mode_acheminement_display, note, numero_suivi, reference, statut, statut_display, stock_mouvemente, transporteur, transporteur_nom, transporteur_obj_nom
    mode_acheminement ∈ {depot, direct_site}
    statut ∈ {annulee, en_transit, livree, planifiee}
- frontend/src/api/installationsApi.js :: updateLivraisonLigne -> /api/django/installations/livraison-lignes/<>  [LivraisonLigneSerializer]
    champs: designation, id, livraison, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: updateOrdreAssemblage -> /api/django/installations/ordres-assemblage/<>  [OrdreAssemblageSerializer]
    champs: chantier, cout_prevu, created_by, date_creation, date_modification, date_prevue, date_terminaison, devis, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, motif_annulation, note, ordre_sous_traitance, quantite, quantite_produite, reference, responsable, responsable_nom, revision_kit_numero, sous_traitant, statut, statut_display, stock_mouvemente, temps_prevu_min, temps_reel_min
    statut ∈ {annule, en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: updateOrdreDemontage -> /api/django/installations/ordres-demontage/<>  [OrdreDemontageSerializer]
    champs: created_by, date_creation, date_modification, date_terminaison, emplacement_destination, emplacement_source, id, kit, kit_nom, lignes, note, quantite, reference, statut, statut_display, stock_mouvemente
    statut ∈ {planifie, termine}
- frontend/src/api/installationsApi.js :: updatePickListLigne -> /api/django/installations/pick-list-lignes/<>  [PickListLigneSerializer]
    champs: bin, bin_code, designation, id, ordre, pick_list, preleve, produit, produit_nom, quantite_demandee, quantite_prelevee
- frontend/src/api/installationsApi.js :: updatePreuveLivraison -> /api/django/installations/preuves-livraison/<>  [PreuveLivraisonSerializer]
    champs: created_by, date_creation, date_modification, gps_lat, gps_lng, horodatage, id, livraison, note, photo, signataire_nom, signature_data
- frontend/src/api/installationsApi.js :: updateRecette -> /api/django/installations/recettes-commissioning/<>  [CommissioningRecordSerializer]
    champs: continuite_terre_ohm, continuite_terre_ok, date_essai, doc_datasheets_ok, doc_dossier_ok, doc_schema_ok, id, installation, instrument_etalonnage_expire, instrument_id, instrument_nom, instrument_numero_serie, isolement_mohm, isolement_ok, iv_readings, observations, passe, performance_ok, polarite_ok, production_attendue_kw, production_test_kw, resultat, resultat_display, securite_coupure_ok, securite_signalisation_ok, technicien, ventes_recette_id, visuel_cablage_ok, visuel_structure_ok, visuel_terre_ok
    resultat ∈ {conforme, en_cours, non_conforme, reserves}
- frontend/src/api/installationsApi.js :: updateSessionComptage -> /api/django/installations/sessions-comptage/<>  [SessionComptageSerializer]
    champs: classe_abc, classe_abc_display, created_by, date_creation, date_modification, date_planifiee, emplacement, id, intitule, lignes, note, reference, statut, statut_display
    classe_abc ∈ {A, B, C, toutes}
    statut ∈ {en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: updateTransporteur -> /api/django/installations/transporteurs/<>  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/monitoringApi.js :: addCleaning -> /api/django/monitoring/cleanings  [CleaningEventSerializer]
    champs: date, date_creation, id, installation, note
- frontend/src/api/monitoringApi.js :: addReading -> /api/django/monitoring/readings  [ProductionReadingSerializer]
    champs: date, date_creation, energy_kwh, external_id, id, installation, note, period_days, source, source_display
    source ∈ {auto, manual}
- frontend/src/api/monitoringApi.js :: deleteCleaning -> /api/django/monitoring/cleanings/<>  [CleaningEventSerializer]
    champs: date, date_creation, id, installation, note
- frontend/src/api/monitoringApi.js :: deleteReading -> /api/django/monitoring/readings/<>  [ProductionReadingSerializer]
    champs: date, date_creation, energy_kwh, external_id, id, installation, note, period_days, source, source_display
    source ∈ {auto, manual}
- frontend/src/api/monitoringApi.js :: deleteWarranty -> /api/django/monitoring/warranties/<>  [ProductionWarrantySerializer]
    champs: compensation_mad_per_kwh, date_creation, date_modification, degradation_pct_per_year, guaranteed_year1_kwh, id, installation, note, start_year, tolerance_pct
- frontend/src/api/monitoringApi.js :: getCleanings -> /api/django/monitoring/cleanings  [CleaningEventSerializer]
    champs: date, date_creation, id, installation, note
- frontend/src/api/monitoringApi.js :: getConfigForInstallation -> /api/django/monitoring/configs  [MonitoringConfigSerializer]
    champs: credentials, date_modification, enabled, expected_annual_kwh, has_credentials, id, installation, is_auto, last_sync, provider, provider_label
- frontend/src/api/monitoringApi.js :: getConfigs -> /api/django/monitoring/configs  [MonitoringConfigSerializer]
    champs: credentials, date_modification, enabled, expected_annual_kwh, has_credentials, id, installation, is_auto, last_sync, provider, provider_label
- frontend/src/api/monitoringApi.js :: getReadings -> /api/django/monitoring/readings  [ProductionReadingSerializer]
    champs: date, date_creation, energy_kwh, external_id, id, installation, note, period_days, source, source_display
    source ∈ {auto, manual}
- frontend/src/api/monitoringApi.js :: getWarranties -> /api/django/monitoring/warranties  [ProductionWarrantySerializer]
    champs: compensation_mad_per_kwh, date_creation, date_modification, degradation_pct_per_year, guaranteed_year1_kwh, id, installation, note, start_year, tolerance_pct
- frontend/src/api/notificationsApi.js :: createAnnonce -> /api/django/notifications/annonces  [AnnonceSerializer]
    champs: auteur, auteur_username, cible_departement_nom, cible_role, cible_type, cible_type_label, corps, created_at, date_expiration, date_publication, date_publication_effective, epinglee, id, is_expiree, lecture_obligatoire, lus_count, publiee, titre, updated_at
    cible_type ∈ {departement, role, tous}
- frontend/src/api/notificationsApi.js :: createHoliday -> /api/django/notifications/holidays  [HolidaySerializer]
    champs: created_at, date, id, nom, recurrent_annuel
- frontend/src/api/notificationsApi.js :: createMessageAccueil -> /api/django/notifications/messages-accueil  [MessageAccueilSerializer]
    champs: auteur, auteur_nom, corps, created_at, destinataire, destinataire_nom, id, lu_le, visible_a_partir_de
- frontend/src/api/notificationsApi.js :: createWhatsAppTemplate -> /api/django/notifications/whatsapp-templates  [WhatsAppTemplateSerializer]
    champs: active, body_fr, categorie, categorie_label, created_at, groupe, id, language, motif_rejet, name, statut_approbation, statut_approbation_label, updated_at
    categorie ∈ {marketing, utility}
    statut_approbation ∈ {approuve, brouillon, rejete, soumis}
- frontend/src/api/notificationsApi.js :: deleteAnnonce -> /api/django/notifications/annonces/<>  [AnnonceSerializer]
    champs: auteur, auteur_username, cible_departement_nom, cible_role, cible_type, cible_type_label, corps, created_at, date_expiration, date_publication, date_publication_effective, epinglee, id, is_expiree, lecture_obligatoire, lus_count, publiee, titre, updated_at
    cible_type ∈ {departement, role, tous}
- frontend/src/api/notificationsApi.js :: deleteHoliday -> /api/django/notifications/holidays/<>  [HolidaySerializer]
    champs: created_at, date, id, nom, recurrent_annuel
- frontend/src/api/notificationsApi.js :: deleteMessageAccueil -> /api/django/notifications/messages-accueil/<>  [MessageAccueilSerializer]
    champs: auteur, auteur_nom, corps, created_at, destinataire, destinataire_nom, id, lu_le, visible_a_partir_de
- frontend/src/api/notificationsApi.js :: deleteRoutingRule -> /api/django/notifications/routing-rules/<>  [NotificationRoutingRuleSerializer]
    champs: created_at, enabled, event_label, event_type, id, target_role, target_role_label, target_user
    event_type ∈ {annonce_published, annonce_read_reminder, api_taux_erreur_eleve, api_webhook_desactive, approval_decided, approval_escalated, approval_reminder, approval_requested, bcf_cancelled, bcf_late, bcf_relance_proposee, bon_commande_cree, caisse_ecart_anormal, chantier_assigne, chantier_due, chantier_materiel_confirme, chat_mention, chat_message, client_contact_request, compte_a_reactiver, consentement_retire_traite, contrat_signe, crm_bilan_hebdo, da_decidee, da_soumise_stale, devis_accepted, devis_expired, devis_nudge_due, devis_opened, devis_reply, devis_superior_contact_requested, digest, dossier_echeance_depassee, education_reinscription_relance, export_reversibilite_pret, facture_overdue, facture_payee, feedback_digest, feedback_starred, fetes_mobiles_a_saisir, flotte_budget_depassement, flotte_dtc_critique, flotte_zone_alerte, ged_signature_expiration_proche, hot_lead_unread, idea_realisee, idea_received, idea_retenue, idea_vote, impersonation_requested, incident_critical, innovation_campagne, intervention_annulee, intervention_assignee, intervention_replanifiee, lead_assigned, lead_callback_requested, lead_callback_sla_breach, lead_new, lead_non_contacte, lead_rattrape, maintenance_due, maintenance_window_announced, monitoring_rapport, nps_promoteur, paie_echeance_rappel, paie_rib_divergence, paie_run_pret, portail_devis_pret, portail_facture_echue, portail_jalon_chantier_atteint, portail_ticket_maj, post_social_rappel, premier_contact_depasse, product_announcement, projet_retard, projet_statut_change, relance_due, sav_activite_due, sav_equipement_remplace, sav_ticket_breaching, sav_ticket_followed_update, sav_ticket_opened, sav_ticket_resolu, sav_visites_auto_generees, scm_cycle_sop_ouvert, scm_ecart_prevision_important, scm_previsions_generees, security_alert, security_change, snooze_reveil, stock_expiration_soon, stock_low, supplier_doc_expiring, tranche_a_facturer, transport_etape_retard, usage_quota_seuil_franchi, uxviews_favoris_obsoletes, uxviews_vue_equipe_modifiee, veille_ao_alarme_silence, veille_ao_nouveaux_avis, visite_retour_terrain, visite_terrain_a_refaire, visite_terrain_a_valider, visite_terrain_assignee, visite_terrain_validee, visiteur_appareil_partage, visiteur_concurrent_suspecte, warranty_expiring}
- frontend/src/api/notificationsApi.js :: deleteWhatsAppTemplate -> /api/django/notifications/whatsapp-templates/<>  [WhatsAppTemplateSerializer]
    champs: active, body_fr, categorie, categorie_label, created_at, groupe, id, language, motif_rejet, name, statut_approbation, statut_approbation_label, updated_at
    categorie ∈ {marketing, utility}
    statut_approbation ∈ {approuve, brouillon, rejete, soumis}
- frontend/src/api/notificationsApi.js :: getAnnonces -> /api/django/notifications/annonces  [AnnonceSerializer]
    champs: auteur, auteur_username, cible_departement_nom, cible_role, cible_type, cible_type_label, corps, created_at, date_expiration, date_publication, date_publication_effective, epinglee, id, is_expiree, lecture_obligatoire, lus_count, publiee, titre, updated_at
    cible_type ∈ {departement, role, tous}
- frontend/src/api/notificationsApi.js :: getHolidays -> /api/django/notifications/holidays  [HolidaySerializer]
    champs: created_at, date, id, nom, recurrent_annuel
- frontend/src/api/notificationsApi.js :: getMessagesAccueil -> /api/django/notifications/messages-accueil  [MessageAccueilSerializer]
    champs: auteur, auteur_nom, corps, created_at, destinataire, destinataire_nom, id, lu_le, visible_a_partir_de
- frontend/src/api/notificationsApi.js :: getRoutingRules -> /api/django/notifications/routing-rules  [NotificationRoutingRuleSerializer]
    champs: created_at, enabled, event_label, event_type, id, target_role, target_role_label, target_user
    event_type ∈ {annonce_published, annonce_read_reminder, api_taux_erreur_eleve, api_webhook_desactive, approval_decided, approval_escalated, approval_reminder, approval_requested, bcf_cancelled, bcf_late, bcf_relance_proposee, bon_commande_cree, caisse_ecart_anormal, chantier_assigne, chantier_due, chantier_materiel_confirme, chat_mention, chat_message, client_contact_request, compte_a_reactiver, consentement_retire_traite, contrat_signe, crm_bilan_hebdo, da_decidee, da_soumise_stale, devis_accepted, devis_expired, devis_nudge_due, devis_opened, devis_reply, devis_superior_contact_requested, digest, dossier_echeance_depassee, education_reinscription_relance, export_reversibilite_pret, facture_overdue, facture_payee, feedback_digest, feedback_starred, fetes_mobiles_a_saisir, flotte_budget_depassement, flotte_dtc_critique, flotte_zone_alerte, ged_signature_expiration_proche, hot_lead_unread, idea_realisee, idea_received, idea_retenue, idea_vote, impersonation_requested, incident_critical, innovation_campagne, intervention_annulee, intervention_assignee, intervention_replanifiee, lead_assigned, lead_callback_requested, lead_callback_sla_breach, lead_new, lead_non_contacte, lead_rattrape, maintenance_due, maintenance_window_announced, monitoring_rapport, nps_promoteur, paie_echeance_rappel, paie_rib_divergence, paie_run_pret, portail_devis_pret, portail_facture_echue, portail_jalon_chantier_atteint, portail_ticket_maj, post_social_rappel, premier_contact_depasse, product_announcement, projet_retard, projet_statut_change, relance_due, sav_activite_due, sav_equipement_remplace, sav_ticket_breaching, sav_ticket_followed_update, sav_ticket_opened, sav_ticket_resolu, sav_visites_auto_generees, scm_cycle_sop_ouvert, scm_ecart_prevision_important, scm_previsions_generees, security_alert, security_change, snooze_reveil, stock_expiration_soon, stock_low, supplier_doc_expiring, tranche_a_facturer, transport_etape_retard, usage_quota_seuil_franchi, uxviews_favoris_obsoletes, uxviews_vue_equipe_modifiee, veille_ao_alarme_silence, veille_ao_nouveaux_avis, visite_retour_terrain, visite_terrain_a_refaire, visite_terrain_a_valider, visite_terrain_assignee, visite_terrain_validee, visiteur_appareil_partage, visiteur_concurrent_suspecte, warranty_expiring}
- frontend/src/api/notificationsApi.js :: getWhatsAppTemplates -> /api/django/notifications/whatsapp-templates  [WhatsAppTemplateSerializer]
    champs: active, body_fr, categorie, categorie_label, created_at, groupe, id, language, motif_rejet, name, statut_approbation, statut_approbation_label, updated_at
    categorie ∈ {marketing, utility}
    statut_approbation ∈ {approuve, brouillon, rejete, soumis}
- frontend/src/api/notificationsApi.js :: list -> /api/django/notifications/notifications  [NotificationSerializer]
    champs: body, category, created_at, event_label, event_type, id, is_action, link, read, read_at, reason, reason_label, severity, title
    event_type ∈ {annonce_published, annonce_read_reminder, api_taux_erreur_eleve, api_webhook_desactive, approval_decided, approval_escalated, approval_reminder, approval_requested, bcf_cancelled, bcf_late, bcf_relance_proposee, bon_commande_cree, caisse_ecart_anormal, chantier_assigne, chantier_due, chantier_materiel_confirme, chat_mention, chat_message, client_contact_request, compte_a_reactiver, consentement_retire_traite, contrat_signe, crm_bilan_hebdo, da_decidee, da_soumise_stale, devis_accepted, devis_expired, devis_nudge_due, devis_opened, devis_reply, devis_superior_contact_requested, digest, dossier_echeance_depassee, education_reinscription_relance, export_reversibilite_pret, facture_overdue, facture_payee, feedback_digest, feedback_starred, fetes_mobiles_a_saisir, flotte_budget_depassement, flotte_dtc_critique, flotte_zone_alerte, ged_signature_expiration_proche, hot_lead_unread, idea_realisee, idea_received, idea_retenue, idea_vote, impersonation_requested, incident_critical, innovation_campagne, intervention_annulee, intervention_assignee, intervention_replanifiee, lead_assigned, lead_callback_requested, lead_callback_sla_breach, lead_new, lead_non_contacte, lead_rattrape, maintenance_due, maintenance_window_announced, monitoring_rapport, nps_promoteur, paie_echeance_rappel, paie_rib_divergence, paie_run_pret, portail_devis_pret, portail_facture_echue, portail_jalon_chantier_atteint, portail_ticket_maj, post_social_rappel, premier_contact_depasse, product_announcement, projet_retard, projet_statut_change, relance_due, sav_activite_due, sav_equipement_remplace, sav_ticket_breaching, sav_ticket_followed_update, sav_ticket_opened, sav_ticket_resolu, sav_visites_auto_generees, scm_cycle_sop_ouvert, scm_ecart_prevision_important, scm_previsions_generees, security_alert, security_change, snooze_reveil, stock_expiration_soon, stock_low, supplier_doc_expiring, tranche_a_facturer, transport_etape_retard, usage_quota_seuil_franchi, uxviews_favoris_obsoletes, uxviews_vue_equipe_modifiee, veille_ao_alarme_silence, veille_ao_nouveaux_avis, visite_retour_terrain, visite_terrain_a_refaire, visite_terrain_a_valider, visite_terrain_assignee, visite_terrain_validee, visiteur_appareil_partage, visiteur_concurrent_suspecte, warranty_expiring}
    reason ∈ {assigne_a_vous, manager, regle_de_routage, vous_suivez}
- frontend/src/api/offlinesyncApi.js :: getOperation -> /api/django/offlinesync/operations/<>  [OfflineOperationSerializer]
    champs: client_op_id, conflit, created_at, date_creation, date_resolution, date_traitement, erreur, id, module, module_libelle, op_type, payload, resolution, resolution_libelle, resultat, statut, statut_libelle, updated_at
    module ∈ {crm, installations, sav, stock, ventes, visites}
    resolution ∈ {fusion, mienne, serveur}
    statut ∈ {appliquee, conflit, en_attente, rejetee}
- frontend/src/api/offlinesyncApi.js :: listConflits -> /api/django/offlinesync/operations  [OfflineOperationSerializer]
    champs: client_op_id, conflit, created_at, date_creation, date_resolution, date_traitement, erreur, id, module, module_libelle, op_type, payload, resolution, resolution_libelle, resultat, statut, statut_libelle, updated_at
    module ∈ {crm, installations, sav, stock, ventes, visites}
    resolution ∈ {fusion, mienne, serveur}
    statut ∈ {appliquee, conflit, en_attente, rejetee}
- frontend/src/api/offlinesyncApi.js :: listOperations -> /api/django/offlinesync/operations  [OfflineOperationSerializer]
    champs: client_op_id, conflit, created_at, date_creation, date_resolution, date_traitement, erreur, id, module, module_libelle, op_type, payload, resolution, resolution_libelle, resultat, statut, statut_libelle, updated_at
    module ∈ {crm, installations, sav, stock, ventes, visites}
    resolution ∈ {fusion, mienne, serveur}
    statut ∈ {appliquee, conflit, en_attente, rejetee}
- frontend/src/api/outillageApi.js :: createOutil -> /api/django/outillage/outils  [OutillageSerializer]
    champs: a_calibrer, asset_tag, categorie, date_achat, date_creation, date_derniere_calibration, date_modification, date_prochaine_calibration, emplacement, emplacement_nom, id, intervalle_calibration_mois, nom, note, numero_serie, statut, statut_display
    statut ∈ {disponible, en_intervention, en_reparation, perdu}
- frontend/src/api/outillageApi.js :: deleteKitItem -> /api/django/outillage/kit-items/<>  [KitOutillageItemSerializer]
    champs: id, kit, ordre, outil, outil_nom
- frontend/src/api/outillageApi.js :: deleteOutil -> /api/django/outillage/outils/<>  [OutillageSerializer]
    champs: a_calibrer, asset_tag, categorie, date_achat, date_creation, date_derniere_calibration, date_modification, date_prochaine_calibration, emplacement, emplacement_nom, id, intervalle_calibration_mois, nom, note, numero_serie, statut, statut_display
    statut ∈ {disponible, en_intervention, en_reparation, perdu}
- frontend/src/api/outillageApi.js :: getOutil -> /api/django/outillage/outils/<>  [OutillageSerializer]
    champs: a_calibrer, asset_tag, categorie, date_achat, date_creation, date_derniere_calibration, date_modification, date_prochaine_calibration, emplacement, emplacement_nom, id, intervalle_calibration_mois, nom, note, numero_serie, statut, statut_display
    statut ∈ {disponible, en_intervention, en_reparation, perdu}
- frontend/src/api/outillageApi.js :: getOutils -> /api/django/outillage/outils  [OutillageSerializer]
    champs: a_calibrer, asset_tag, categorie, date_achat, date_creation, date_derniere_calibration, date_modification, date_prochaine_calibration, emplacement, emplacement_nom, id, intervalle_calibration_mois, nom, note, numero_serie, statut, statut_display
    statut ∈ {disponible, en_intervention, en_reparation, perdu}
- frontend/src/api/outillageApi.js :: updateOutil -> /api/django/outillage/outils/<>  [OutillageSerializer]
    champs: a_calibrer, asset_tag, categorie, date_achat, date_creation, date_derniere_calibration, date_modification, date_prochaine_calibration, emplacement, emplacement_nom, id, intervalle_calibration_mois, nom, note, numero_serie, statut, statut_display
    statut ∈ {disponible, en_intervention, en_reparation, perdu}
- frontend/src/api/parametresApi.js :: createCadenceRelanceEtape -> /api/django/parametres/cadence-relance  [CadenceRelanceEtapeSerializer]
    champs: actif, cadence, canal, delai_jours, delai_minutes, dimanche_ok, heure_cible, id, libelle, ordre, samedi_ok, template_cle
    cadence ∈ {apres_devis, contact, deuxieme_affaire, generique, reveil}
    canal ∈ {appel, email, visite, whatsapp}
- frontend/src/api/parametresApi.js :: createConditionPaiement -> /api/django/parametres/conditions-paiement  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: createRealisation -> /api/django/parametres/realisations  [RealisationSerializer]
    champs: actif, date_creation, id, lien_suivi, lien_video, mise_en_service, puissance_kwc, titre, url_page, ville
- frontend/src/api/parametresApi.js :: createTauxTva -> /api/django/parametres/taux-tva  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: createUniteMesure -> /api/django/parametres/unites-mesure  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/parametresApi.js :: deleteCadenceRelanceEtape -> /api/django/parametres/cadence-relance/<>  [CadenceRelanceEtapeSerializer]
    champs: actif, cadence, canal, delai_jours, delai_minutes, dimanche_ok, heure_cible, id, libelle, ordre, samedi_ok, template_cle
    cadence ∈ {apres_devis, contact, deuxieme_affaire, generique, reveil}
    canal ∈ {appel, email, visite, whatsapp}
- frontend/src/api/parametresApi.js :: deleteConditionPaiement -> /api/django/parametres/conditions-paiement/<>  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: deleteRealisation -> /api/django/parametres/realisations/<>  [RealisationSerializer]
    champs: actif, date_creation, id, lien_suivi, lien_video, mise_en_service, puissance_kwc, titre, url_page, ville
- frontend/src/api/parametresApi.js :: deleteTauxTva -> /api/django/parametres/taux-tva/<>  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: deleteUniteMesure -> /api/django/parametres/unites-mesure/<>  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/parametresApi.js :: getCadenceRelance -> /api/django/parametres/cadence-relance  [CadenceRelanceEtapeSerializer]
    champs: actif, cadence, canal, delai_jours, delai_minutes, dimanche_ok, heure_cible, id, libelle, ordre, samedi_ok, template_cle
    cadence ∈ {apres_devis, contact, deuxieme_affaire, generique, reveil}
    canal ∈ {appel, email, visite, whatsapp}
- frontend/src/api/parametresApi.js :: getConditionsPaiement -> /api/django/parametres/conditions-paiement  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: getRealisations -> /api/django/parametres/realisations  [RealisationSerializer]
    champs: actif, date_creation, id, lien_suivi, lien_video, mise_en_service, puissance_kwc, titre, url_page, ville
- frontend/src/api/parametresApi.js :: getTauxTva -> /api/django/parametres/taux-tva  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: getUnitesMesure -> /api/django/parametres/unites-mesure  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/parametresApi.js :: updateCadenceRelanceEtape -> /api/django/parametres/cadence-relance/<>  [CadenceRelanceEtapeSerializer]
    champs: actif, cadence, canal, delai_jours, delai_minutes, dimanche_ok, heure_cible, id, libelle, ordre, samedi_ok, template_cle
    cadence ∈ {apres_devis, contact, deuxieme_affaire, generique, reveil}
    canal ∈ {appel, email, visite, whatsapp}
- frontend/src/api/parametresApi.js :: updateConditionPaiement -> /api/django/parametres/conditions-paiement/<>  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: updateRealisation -> /api/django/parametres/realisations/<>  [RealisationSerializer]
    champs: actif, date_creation, id, lien_suivi, lien_video, mise_en_service, puissance_kwc, titre, url_page, ville
- frontend/src/api/parametresApi.js :: updateTauxTva -> /api/django/parametres/taux-tva/<>  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: updateUniteMesure -> /api/django/parametres/unites-mesure/<>  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/portailApi.js :: patch -> /api/django/portail/comptes-portail/<>  [ComptePortailClientSerializer]
    champs: actif, client, date_creation, derniere_connexion, email, id, token_apercu
- frontend/src/api/recordsApi.js :: createTag -> /api/django/records/tags  [TagSerializer]
    champs: couleur, created_at, id, nom
- frontend/src/api/recordsApi.js :: deleteTag -> /api/django/records/tags/<>  [TagSerializer]
    champs: couleur, created_at, id, nom
- frontend/src/api/recordsApi.js :: getActivityTypes -> /api/django/records/activity-types  [ActivityTypeSerializer]
    champs: delai_defaut_jours, delai_jours, est_systeme, icone, id, mode_enchainement, nom, ordre, type_suivant
    mode_enchainement ∈ {aucun, declencher, suggerer}
- frontend/src/api/recordsApi.js :: getTags -> /api/django/records/tags  [TagSerializer]
    champs: couleur, created_at, id, nom
- frontend/src/api/reportingApi.js :: createClasseur -> /api/django/reporting/classeurs  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: createKpiAlerte -> /api/django/reporting/kpi-alertes  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, metric_cle, metric_definition, mode_detection, mode_detection_label, nom, operateur, operateur_label, seuil, source, updated_at
    kpi ∈ {couverture_i18n_pct, documents_non_fr_pct, encours_echu_total, jours_depuis_dernier_drill_reussi, quota_le_plus_charge_pct, uptime_moyen_12_mois, valeur_stock_totale}
    mode_detection ∈ {anomalie, seuil, variation}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
    source ∈ {catalogue, metrique}
- frontend/src/api/reportingApi.js :: createRapportDefinition -> /api/django/reporting/rapport-definitions  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: createSavedReport -> /api/django/reporting/saved-reports  [SavedReportSerializer]
    champs: canal, cible_id, created_at, definition, destinataires_whatsapp, heure_envoi, id, jour_du_mois, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, monthly, none, weekly}
    target_kind ∈ {dashboard, query, sales, service, stock}
- frontend/src/api/reportingApi.js :: deleteClasseur -> /api/django/reporting/classeurs/<>  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: deleteDashboardConfig -> /api/django/reporting/dashboard-config/<>  [DashboardConfigSerializer]
    champs: cards, created_at, id, menu_tier, updated_at, user
- frontend/src/api/reportingApi.js :: deleteKpiAlerte -> /api/django/reporting/kpi-alertes/<>  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, metric_cle, metric_definition, mode_detection, mode_detection_label, nom, operateur, operateur_label, seuil, source, updated_at
    kpi ∈ {couverture_i18n_pct, documents_non_fr_pct, encours_echu_total, jours_depuis_dernier_drill_reussi, quota_le_plus_charge_pct, uptime_moyen_12_mois, valeur_stock_totale}
    mode_detection ∈ {anomalie, seuil, variation}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
    source ∈ {catalogue, metrique}
- frontend/src/api/reportingApi.js :: deleteRapportDefinition -> /api/django/reporting/rapport-definitions/<>  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: deleteSavedReport -> /api/django/reporting/saved-reports/<>  [SavedReportSerializer]
    champs: canal, cible_id, created_at, definition, destinataires_whatsapp, heure_envoi, id, jour_du_mois, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, monthly, none, weekly}
    target_kind ∈ {dashboard, query, sales, service, stock}
- frontend/src/api/reportingApi.js :: getClasseur -> /api/django/reporting/classeurs/<>  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: listClasseurs -> /api/django/reporting/classeurs  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: listDashboardConfigs -> /api/django/reporting/dashboard-config  [DashboardConfigSerializer]
    champs: cards, created_at, id, menu_tier, updated_at, user
- frontend/src/api/reportingApi.js :: listKpiAlertes -> /api/django/reporting/kpi-alertes  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, metric_cle, metric_definition, mode_detection, mode_detection_label, nom, operateur, operateur_label, seuil, source, updated_at
    kpi ∈ {couverture_i18n_pct, documents_non_fr_pct, encours_echu_total, jours_depuis_dernier_drill_reussi, quota_le_plus_charge_pct, uptime_moyen_12_mois, valeur_stock_totale}
    mode_detection ∈ {anomalie, seuil, variation}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
    source ∈ {catalogue, metrique}
- frontend/src/api/reportingApi.js :: listRapportDefinitions -> /api/django/reporting/rapport-definitions  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: listSavedReports -> /api/django/reporting/saved-reports  [SavedReportSerializer]
    champs: canal, cible_id, created_at, definition, destinataires_whatsapp, heure_envoi, id, jour_du_mois, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, monthly, none, weekly}
    target_kind ∈ {dashboard, query, sales, service, stock}
- frontend/src/api/reportingApi.js :: updateClasseur -> /api/django/reporting/classeurs/<>  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: updateKpiAlerte -> /api/django/reporting/kpi-alertes/<>  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, metric_cle, metric_definition, mode_detection, mode_detection_label, nom, operateur, operateur_label, seuil, source, updated_at
    kpi ∈ {couverture_i18n_pct, documents_non_fr_pct, encours_echu_total, jours_depuis_dernier_drill_reussi, quota_le_plus_charge_pct, uptime_moyen_12_mois, valeur_stock_totale}
    mode_detection ∈ {anomalie, seuil, variation}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
    source ∈ {catalogue, metrique}
- frontend/src/api/reportingApi.js :: updateRapportDefinition -> /api/django/reporting/rapport-definitions/<>  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: updateSavedReport -> /api/django/reporting/saved-reports/<>  [SavedReportSerializer]
    champs: canal, cible_id, created_at, definition, destinataires_whatsapp, heure_envoi, id, jour_du_mois, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, monthly, none, weekly}
    target_kind ∈ {dashboard, query, sales, service, stock}
- frontend/src/api/rolesApi.js :: createRole -> /api/django/roles  [RoleSerializer]
    champs: entites_visibles, est_systeme, id, nom, perimetre, permissions, users, users_count
- frontend/src/api/rolesApi.js :: deleteRole -> /api/django/roles/<>  [RoleSerializer]
    champs: entites_visibles, est_systeme, id, nom, perimetre, permissions, users, users_count
- frontend/src/api/rolesApi.js :: getRole -> /api/django/roles/<>  [RoleSerializer]
    champs: entites_visibles, est_systeme, id, nom, perimetre, permissions, users, users_count
- frontend/src/api/rolesApi.js :: getRoles -> /api/django/roles  [RoleSerializer]
    champs: entites_visibles, est_systeme, id, nom, perimetre, permissions, users, users_count
- frontend/src/api/rolesApi.js :: patchRole -> /api/django/roles/<>  [RoleSerializer]
    champs: entites_visibles, est_systeme, id, nom, perimetre, permissions, users, users_count
- frontend/src/api/rolesApi.js :: updateRole -> /api/django/roles/<>  [RoleSerializer]
    champs: entites_visibles, est_systeme, id, nom, perimetre, permissions, users, users_count
- frontend/src/api/savApi.js :: deleteCategorieEquipement -> /api/django/sav/categories-equipement/<>  [CategorieEquipementSerializer]
    champs: alias_email, commentaire, equipe_responsable, equipe_responsable_nom, id, nb_equipements, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: deleteCategorieTicket -> /api/django/sav/categories-ticket/<>  [CategorieTicketSerializer]
    champs: actif, id, libelle, ordre
- frontend/src/api/savApi.js :: deleteCauseDefaillance -> /api/django/sav/causes-defaillance/<>  [CauseDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: deleteCompatibilitePiece -> /api/django/sav/compatibilites-piece/<>  [CompatibilitePieceSerializer]
    champs: date_creation, id, note, piece, piece_nom, produit_equipement, produit_equipement_nom, remplace_par, remplace_par_nom
- frontend/src/api/savApi.js :: deleteContrat -> /api/django/sav/contrats-maintenance/<>  [ContratMaintenanceSerializer]
    champs: a_renouveler, actif, client, client_nom, date_creation, date_debut, date_expiration, date_renouvellement, deplacements_inclus_an, derniere_facturation, derniere_visite, droits_restants, due, duree_mois, en_periode_grace, equipements, equipements_detail, expire, facturation_active, facturation_due, id, installation, notes, periodicite, pieces_couvertes_pct, prix, prochaine_facturation, prochaine_visite, renouvellement_du, sla_resolution_days, sla_response_days, visites_incluses_an
    periodicite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/savApi.js :: deleteEquipeMaintenance -> /api/django/sav/equipes-maintenance/<>  [EquipeMaintenanceSerializer]
    champs: actif, capacite_max_tickets_ouverts, date_creation, id, membres, membres_count, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: deleteProbleme -> /api/django/sav/problemes/<>  [ProblemeSerializer]
    champs: anciennete_jours, cause_racine, created_at, description, id, impact, nb_tickets, reference, statut, statut_display, titre, updated_at
    statut ∈ {en_analyse, identifie, resolu}
- frontend/src/api/savApi.js :: deleteRemedeDefaillance -> /api/django/sav/remedes-defaillance/<>  [RemedeDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: deleteReponseType -> /api/django/sav/reponses-type/<>  [ReponseTypeSerializer]
    champs: archived, canaux_autorises, corps, date_creation, id, nouveau_statut, titre
- frontend/src/api/savApi.js :: deleteWorksheetModele -> /api/django/sav/worksheet-modeles/<>  [WorksheetMaintenanceModeleSerializer]
    champs: actif, champs, date_creation, id, nom, type_ticket_applicable
    type_ticket_applicable ∈ {correctif, preventif, tous}
- frontend/src/api/savApi.js :: getCategoriesEquipement -> /api/django/sav/categories-equipement  [CategorieEquipementSerializer]
    champs: alias_email, commentaire, equipe_responsable, equipe_responsable_nom, id, nb_equipements, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: getCategoriesTicket -> /api/django/sav/categories-ticket  [CategorieTicketSerializer]
    champs: actif, id, libelle, ordre
- frontend/src/api/savApi.js :: getCausesDefaillance -> /api/django/sav/causes-defaillance  [CauseDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: getChecklistTemplates -> /api/django/sav/checklist-templates  [MaintenanceChecklistTemplateSerializer]
    champs: actif, id, items, nom, protege
- frontend/src/api/savApi.js :: getCompatibilitesPiece -> /api/django/sav/compatibilites-piece  [CompatibilitePieceSerializer]
    champs: date_creation, id, note, piece, piece_nom, produit_equipement, produit_equipement_nom, remplace_par, remplace_par_nom
- frontend/src/api/savApi.js :: getContrats -> /api/django/sav/contrats-maintenance  [ContratMaintenanceSerializer]
    champs: a_renouveler, actif, client, client_nom, date_creation, date_debut, date_expiration, date_renouvellement, deplacements_inclus_an, derniere_facturation, derniere_visite, droits_restants, due, duree_mois, en_periode_grace, equipements, equipements_detail, expire, facturation_active, facturation_due, id, installation, notes, periodicite, pieces_couvertes_pct, prix, prochaine_facturation, prochaine_visite, renouvellement_du, sla_resolution_days, sla_response_days, visites_incluses_an
    periodicite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/savApi.js :: getEquipesMaintenance -> /api/django/sav/equipes-maintenance  [EquipeMaintenanceSerializer]
    champs: actif, capacite_max_tickets_ouverts, date_creation, id, membres, membres_count, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: getProblemes -> /api/django/sav/problemes  [ProblemeSerializer]
    champs: anciennete_jours, cause_racine, created_at, description, id, impact, nb_tickets, reference, statut, statut_display, titre, updated_at
    statut ∈ {en_analyse, identifie, resolu}
- frontend/src/api/savApi.js :: getRemedesDefaillance -> /api/django/sav/remedes-defaillance  [RemedeDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: getReponsesType -> /api/django/sav/reponses-type  [ReponseTypeSerializer]
    champs: archived, canaux_autorises, corps, date_creation, id, nouveau_statut, titre
- frontend/src/api/savApi.js :: getWorksheetModeles -> /api/django/sav/worksheet-modeles  [WorksheetMaintenanceModeleSerializer]
    champs: actif, champs, date_creation, id, nom, type_ticket_applicable
    type_ticket_applicable ∈ {correctif, preventif, tous}
- frontend/src/api/stockApi.js :: createAcompteFournisseur -> /api/django/stock/acomptes-fournisseur  [AcompteFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, date_creation, date_versement, facture_imputee, id, mode, mode_display, montant, montant_consomme, montant_non_consomme, note
    mode ∈ {autre, carte, cheque, effet, especes, virement}
- frontend/src/api/stockApi.js :: createAvoirFournisseur -> /api/django/stock/avoirs-fournisseur  [AvoirFournisseurSerializer]
    champs: created_by, date_creation, date_mise_a_jour, facture_origine, fournisseur, fournisseur_nom, id, imputations, montant_disponible, montant_ht, montant_impute, montant_ttc, montant_tva, note, reference, retour, retour_reference, statut, statut_display
    statut ∈ {brouillon, impute, valide}
- frontend/src/api/stockApi.js :: createCategorieFournisseur -> /api/django/stock/categories-fournisseur  [CategorieFournisseurSerializer]
    champs: archived, id, nom
- frontend/src/api/stockApi.js :: createConditionnementProduit -> /api/django/stock/conditionnements  [ConditionnementProduitSerializer]
    champs: code_barres, date_creation, facteur, id, nom, produit, produit_nom, unite_stock
- frontend/src/api/stockApi.js :: createContactFournisseur -> /api/django/stock/contacts-fournisseur  [ContactFournisseurSerializer]
    champs: email, fonction, fournisseur, id, nom, telephone
- frontend/src/api/stockApi.js :: createDocumentFournisseur -> /api/django/stock/documents-fournisseur  [DocumentFournisseurSerializer]
    champs: date_creation, date_emission, date_expiration, dossier, est_valide, filename, id, mime, note, reference, taille, type_document, type_document_display
    type_document ∈ {assurance, attestation_cnss, attestation_fiscale, autre, rc, rib_certifie}
- frontend/src/api/stockApi.js :: createDossierOnboarding -> /api/django/stock/dossiers-onboarding-fournisseur  [DossierOnboardingFournisseurSerializer]
    champs: date_creation, date_decision, documents, fournisseur, fournisseur_nom, id, motif_rejet, note, progression, statut, statut_display, valide_par
    statut ∈ {documents_recus, en_attente, rejete, valide}
- frontend/src/api/stockApi.js :: createFicheTechnique -> /api/django/stock/fiches-techniques  [FicheTechniqueSerializer]
    champs: bat_c_rate_charge, bat_c_rate_decharge, bat_chimie, bat_dod_pct, bat_kwh_nominal, bat_kwh_usable, bat_max_charge_kw, bat_max_decharge_kw, bat_max_modules_par_banc, bat_temp_max_c, bat_temp_min_c, bat_v_nominal, bifacial, date_creation, date_mise_a_jour, epaisseur_mm, id, imp_a, isc_a, largeur_mm, longueur_mm, noct_c, ond_ac_kw, ond_bat_aucune, ond_bat_max_charge_kw, ond_bat_max_decharge_kw, ond_bat_v_max, ond_bat_v_min, ond_conso_nuit_w, ond_courbe_rendement, ond_i_max_mppt_a, ond_isc_max_mppt_a, ond_mppt_v_max, ond_mppt_v_min, ond_n_mppt, ond_phases, ond_rendement_cec_pct, ond_rendement_euro_pct, ond_rendement_max_pct, ond_v_demarrage_v, ond_v_max_abs, opt_ac_i_max_a, opt_ac_kw, opt_ac_tension_v, opt_ac_unites_max_par_branche, opt_i_out_max_a, opt_modules_max_par_chaine, opt_pmax_out_w, opt_v_out_max, opt_v_out_min, opt_v_out_nominal_v, pdf, pdf_filename, pdf_mime, pdf_size, pdf_url, pmax_wc, poids_kg, produit, produit_garantie, produit_marque, produit_nom, rendement_par_irradiance, rendement_pct, techno_cellule, temp_coeff_pmax_pct_c, temp_coeff_voc_pct_c, tolerance_pmax_max_pct, tolerance_pmax_min_pct, type_fiche, uc_w_m2k, uv_w_m3sk, vmp_v, voc_v
    bat_chimie ∈ {autre, lfp, lmo, lto, nca, nmc, plomb_agm, plomb_gel, plomb_ouvert}
    type_fiche ∈ {autre, batterie, module, onduleur, optimiseur}
- frontend/src/api/stockApi.js :: createInventaireSession -> /api/django/stock/inventaire-sessions  [InventaireSessionSerializer]
    champs: created_by, created_by_username, date_creation, date_mise_a_jour, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: createModeleBcf -> /api/django/stock/modeles-bcf  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: createNomenclatureCodeBarres -> /api/django/stock/nomenclatures-code-barres  [NomenclatureCodeBarresSerializer]
    champs: actif, date_creation, date_mise_a_jour, id, nom, regles, type_nomenclature
    type_nomenclature ∈ {default, gs1}
- frontend/src/api/stockApi.js :: createPrixFournisseur -> /api/django/stock/prix-fournisseurs  [PrixFournisseurSerializer]
    champs: date_debut, date_dernier_achat, date_fin, delai_livraison_jours, fournisseur, fournisseur_nom, id, paliers, prix_achat, produit, produit_nom, ref_produit_fournisseur
- frontend/src/api/stockApi.js :: createProduit -> /api/django/stock/produits  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: createReceptionFournisseur -> /api/django/stock/receptions-fournisseur  [ReceptionFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, date_reception, fournisseur_nom, id, lignes, note, recu_par, recu_par_username, reference, statut, statut_display, total_recu
    statut ∈ {annule, brouillon, confirme}
- frontend/src/api/stockApi.js :: createRegleCodeBarres -> /api/django/stock/regles-code-barres  [RegleCodeBarresSerializer]
    champs: encode, est_regex, id, motif, nomenclature, priorite
    encode ∈ {emplacement, lot, produit, quantite, serie}
- frontend/src/api/stockApi.js :: createRetourFournisseur -> /api/django/stock/retours-fournisseur  [RetourFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, fournisseur, fournisseur_nom, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: deleteAcompteFournisseur -> /api/django/stock/acomptes-fournisseur/<>  [AcompteFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, date_creation, date_versement, facture_imputee, id, mode, mode_display, montant, montant_consomme, montant_non_consomme, note
    mode ∈ {autre, carte, cheque, effet, especes, virement}
- frontend/src/api/stockApi.js :: deleteCategorieFournisseur -> /api/django/stock/categories-fournisseur/<>  [CategorieFournisseurSerializer]
    champs: archived, id, nom
- frontend/src/api/stockApi.js :: deleteConditionnementProduit -> /api/django/stock/conditionnements/<>  [ConditionnementProduitSerializer]
    champs: code_barres, date_creation, facteur, id, nom, produit, produit_nom, unite_stock
- frontend/src/api/stockApi.js :: deleteContactFournisseur -> /api/django/stock/contacts-fournisseur/<>  [ContactFournisseurSerializer]
    champs: email, fonction, fournisseur, id, nom, telephone
- frontend/src/api/stockApi.js :: deleteFicheTechnique -> /api/django/stock/fiches-techniques/<>  [FicheTechniqueSerializer]
    champs: bat_c_rate_charge, bat_c_rate_decharge, bat_chimie, bat_dod_pct, bat_kwh_nominal, bat_kwh_usable, bat_max_charge_kw, bat_max_decharge_kw, bat_max_modules_par_banc, bat_temp_max_c, bat_temp_min_c, bat_v_nominal, bifacial, date_creation, date_mise_a_jour, epaisseur_mm, id, imp_a, isc_a, largeur_mm, longueur_mm, noct_c, ond_ac_kw, ond_bat_aucune, ond_bat_max_charge_kw, ond_bat_max_decharge_kw, ond_bat_v_max, ond_bat_v_min, ond_conso_nuit_w, ond_courbe_rendement, ond_i_max_mppt_a, ond_isc_max_mppt_a, ond_mppt_v_max, ond_mppt_v_min, ond_n_mppt, ond_phases, ond_rendement_cec_pct, ond_rendement_euro_pct, ond_rendement_max_pct, ond_v_demarrage_v, ond_v_max_abs, opt_ac_i_max_a, opt_ac_kw, opt_ac_tension_v, opt_ac_unites_max_par_branche, opt_i_out_max_a, opt_modules_max_par_chaine, opt_pmax_out_w, opt_v_out_max, opt_v_out_min, opt_v_out_nominal_v, pdf, pdf_filename, pdf_mime, pdf_size, pdf_url, pmax_wc, poids_kg, produit, produit_garantie, produit_marque, produit_nom, rendement_par_irradiance, rendement_pct, techno_cellule, temp_coeff_pmax_pct_c, temp_coeff_voc_pct_c, tolerance_pmax_max_pct, tolerance_pmax_min_pct, type_fiche, uc_w_m2k, uv_w_m3sk, vmp_v, voc_v
    bat_chimie ∈ {autre, lfp, lmo, lto, nca, nmc, plomb_agm, plomb_gel, plomb_ouvert}
    type_fiche ∈ {autre, batterie, module, onduleur, optimiseur}
- frontend/src/api/stockApi.js :: deleteModeleBcf -> /api/django/stock/modeles-bcf/<>  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: deleteNomenclatureCodeBarres -> /api/django/stock/nomenclatures-code-barres/<>  [NomenclatureCodeBarresSerializer]
    champs: actif, date_creation, date_mise_a_jour, id, nom, regles, type_nomenclature
    type_nomenclature ∈ {default, gs1}
- frontend/src/api/stockApi.js :: deletePrixFournisseur -> /api/django/stock/prix-fournisseurs/<>  [PrixFournisseurSerializer]
    champs: date_debut, date_dernier_achat, date_fin, delai_livraison_jours, fournisseur, fournisseur_nom, id, paliers, prix_achat, produit, produit_nom, ref_produit_fournisseur
- frontend/src/api/stockApi.js :: deleteProduit -> /api/django/stock/produits/<>  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: deleteRegleCodeBarres -> /api/django/stock/regles-code-barres/<>  [RegleCodeBarresSerializer]
    champs: encode, est_regex, id, motif, nomenclature, priorite
    encode ∈ {emplacement, lot, produit, quantite, serie}
- frontend/src/api/stockApi.js :: getAcomptesFournisseur -> /api/django/stock/acomptes-fournisseur  [AcompteFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, date_creation, date_versement, facture_imputee, id, mode, mode_display, montant, montant_consomme, montant_non_consomme, note
    mode ∈ {autre, carte, cheque, effet, especes, virement}
- frontend/src/api/stockApi.js :: getAvoirsFournisseurDe -> /api/django/stock/avoirs-fournisseur  [AvoirFournisseurSerializer]
    champs: created_by, date_creation, date_mise_a_jour, facture_origine, fournisseur, fournisseur_nom, id, imputations, montant_disponible, montant_ht, montant_impute, montant_ttc, montant_tva, note, reference, retour, retour_reference, statut, statut_display
    statut ∈ {brouillon, impute, valide}
- frontend/src/api/stockApi.js :: getCatalogueAchat -> /api/django/stock/catalogue-achat  [CatalogueAchatSerializer]
    champs: categorie, categorie_nom, fournisseur_prefere, fournisseur_prefere_nom, id, nom, prix_achat_dernier, sku
- frontend/src/api/stockApi.js :: getCategoriesFournisseur -> /api/django/stock/categories-fournisseur  [CategorieFournisseurSerializer]
    champs: archived, id, nom
- frontend/src/api/stockApi.js :: getConditionnementsProduit -> /api/django/stock/conditionnements  [ConditionnementProduitSerializer]
    champs: code_barres, date_creation, facteur, id, nom, produit, produit_nom, unite_stock
- frontend/src/api/stockApi.js :: getContactsFournisseurDe -> /api/django/stock/contacts-fournisseur  [ContactFournisseurSerializer]
    champs: email, fonction, fournisseur, id, nom, telephone
- frontend/src/api/stockApi.js :: getDocumentsConformiteFournisseur -> /api/django/stock/documents-conformite-fournisseur  [DocumentConformiteFournisseurSerializer]
    champs: date_creation, date_emission, date_expiration, date_modification, est_valide, fournisseur, fournisseur_nom, id, note, obligatoire, reference, type_document, type_document_display
    type_document ∈ {arf, assurance, autre, cnss, rc}
- frontend/src/api/stockApi.js :: getFichesTechniques -> /api/django/stock/fiches-techniques  [FicheTechniqueSerializer]
    champs: bat_c_rate_charge, bat_c_rate_decharge, bat_chimie, bat_dod_pct, bat_kwh_nominal, bat_kwh_usable, bat_max_charge_kw, bat_max_decharge_kw, bat_max_modules_par_banc, bat_temp_max_c, bat_temp_min_c, bat_v_nominal, bifacial, date_creation, date_mise_a_jour, epaisseur_mm, id, imp_a, isc_a, largeur_mm, longueur_mm, noct_c, ond_ac_kw, ond_bat_aucune, ond_bat_max_charge_kw, ond_bat_max_decharge_kw, ond_bat_v_max, ond_bat_v_min, ond_conso_nuit_w, ond_courbe_rendement, ond_i_max_mppt_a, ond_isc_max_mppt_a, ond_mppt_v_max, ond_mppt_v_min, ond_n_mppt, ond_phases, ond_rendement_cec_pct, ond_rendement_euro_pct, ond_rendement_max_pct, ond_v_demarrage_v, ond_v_max_abs, opt_ac_i_max_a, opt_ac_kw, opt_ac_tension_v, opt_ac_unites_max_par_branche, opt_i_out_max_a, opt_modules_max_par_chaine, opt_pmax_out_w, opt_v_out_max, opt_v_out_min, opt_v_out_nominal_v, pdf, pdf_filename, pdf_mime, pdf_size, pdf_url, pmax_wc, poids_kg, produit, produit_garantie, produit_marque, produit_nom, rendement_par_irradiance, rendement_pct, techno_cellule, temp_coeff_pmax_pct_c, temp_coeff_voc_pct_c, tolerance_pmax_max_pct, tolerance_pmax_min_pct, type_fiche, uc_w_m2k, uv_w_m3sk, vmp_v, voc_v
    bat_chimie ∈ {autre, lfp, lmo, lto, nca, nmc, plomb_agm, plomb_gel, plomb_ouvert}
    type_fiche ∈ {autre, batterie, module, onduleur, optimiseur}
- frontend/src/api/stockApi.js :: getInventaireSession -> /api/django/stock/inventaire-sessions/<>  [InventaireSessionSerializer]
    champs: created_by, created_by_username, date_creation, date_mise_a_jour, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: getInventaireSessions -> /api/django/stock/inventaire-sessions  [InventaireSessionSerializer]
    champs: created_by, created_by_username, date_creation, date_mise_a_jour, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: getInventairesAnnuels -> /api/django/stock/inventaires-annuels  [InventaireAnnuelSerializer]
    champs: date_creation, date_reference, donnees, exercice, id, nb_lignes, total_valeur
- frontend/src/api/stockApi.js :: getKits -> /api/django/stock/kits  [KitProduitSerializer]
    champs: composants, date_creation, date_mise_a_jour, description, disponibilite_potentielle, id, is_archived, nb_composants, nom, sku
- frontend/src/api/stockApi.js :: getLotsEntrepot -> /api/django/stock/lots-entrepot  [LotEntrepotSerializer]
    champs: date_creation, date_modification, date_peremption, emplacement, emplacement_nom, est_perime, id, numero_lot, produit, produit_nom, quantite_recue, quantite_restante, reference_reception
- frontend/src/api/stockApi.js :: getModeleBcf -> /api/django/stock/modeles-bcf/<>  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: getModelesBcf -> /api/django/stock/modeles-bcf  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: getNomenclaturesCodeBarres -> /api/django/stock/nomenclatures-code-barres  [NomenclatureCodeBarresSerializer]
    champs: actif, date_creation, date_mise_a_jour, id, nom, regles, type_nomenclature
    type_nomenclature ∈ {default, gs1}
- frontend/src/api/stockApi.js :: getProduit -> /api/django/stock/produits/<>  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: getProduits -> /api/django/stock/produits  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: getProduitsArchived -> /api/django/stock/produits  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: getReceptionFournisseur -> /api/django/stock/receptions-fournisseur/<>  [ReceptionFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, date_reception, fournisseur_nom, id, lignes, note, recu_par, recu_par_username, reference, statut, statut_display, total_recu
    statut ∈ {annule, brouillon, confirme}
- frontend/src/api/stockApi.js :: getReceptionsFournisseur -> /api/django/stock/receptions-fournisseur  [ReceptionFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, date_reception, fournisseur_nom, id, lignes, note, recu_par, recu_par_username, reference, statut, statut_display, total_recu
    statut ∈ {annule, brouillon, confirme}
- frontend/src/api/stockApi.js :: getRetourFournisseur -> /api/django/stock/retours-fournisseur/<>  [RetourFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, fournisseur, fournisseur_nom, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: getRetoursFournisseur -> /api/django/stock/retours-fournisseur  [RetourFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, fournisseur, fournisseur_nom, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: getRetoursFournisseurDe -> /api/django/stock/retours-fournisseur  [RetourFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, created_by_username, date_creation, fournisseur, fournisseur_nom, id, lignes, motif, reference, statut, statut_display
    statut ∈ {annule, brouillon, valide}
- frontend/src/api/stockApi.js :: patchProduit -> /api/django/stock/produits/<>  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: updateAcompteFournisseur -> /api/django/stock/acomptes-fournisseur/<>  [AcompteFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, created_by, date_creation, date_versement, facture_imputee, id, mode, mode_display, montant, montant_consomme, montant_non_consomme, note
    mode ∈ {autre, carte, cheque, effet, especes, virement}
- frontend/src/api/stockApi.js :: updateCategorieFournisseur -> /api/django/stock/categories-fournisseur/<>  [CategorieFournisseurSerializer]
    champs: archived, id, nom
- frontend/src/api/stockApi.js :: updateConditionnementProduit -> /api/django/stock/conditionnements/<>  [ConditionnementProduitSerializer]
    champs: code_barres, date_creation, facteur, id, nom, produit, produit_nom, unite_stock
- frontend/src/api/stockApi.js :: updateContactFournisseur -> /api/django/stock/contacts-fournisseur/<>  [ContactFournisseurSerializer]
    champs: email, fonction, fournisseur, id, nom, telephone
- frontend/src/api/stockApi.js :: updateFicheTechnique -> /api/django/stock/fiches-techniques/<>  [FicheTechniqueSerializer]
    champs: bat_c_rate_charge, bat_c_rate_decharge, bat_chimie, bat_dod_pct, bat_kwh_nominal, bat_kwh_usable, bat_max_charge_kw, bat_max_decharge_kw, bat_max_modules_par_banc, bat_temp_max_c, bat_temp_min_c, bat_v_nominal, bifacial, date_creation, date_mise_a_jour, epaisseur_mm, id, imp_a, isc_a, largeur_mm, longueur_mm, noct_c, ond_ac_kw, ond_bat_aucune, ond_bat_max_charge_kw, ond_bat_max_decharge_kw, ond_bat_v_max, ond_bat_v_min, ond_conso_nuit_w, ond_courbe_rendement, ond_i_max_mppt_a, ond_isc_max_mppt_a, ond_mppt_v_max, ond_mppt_v_min, ond_n_mppt, ond_phases, ond_rendement_cec_pct, ond_rendement_euro_pct, ond_rendement_max_pct, ond_v_demarrage_v, ond_v_max_abs, opt_ac_i_max_a, opt_ac_kw, opt_ac_tension_v, opt_ac_unites_max_par_branche, opt_i_out_max_a, opt_modules_max_par_chaine, opt_pmax_out_w, opt_v_out_max, opt_v_out_min, opt_v_out_nominal_v, pdf, pdf_filename, pdf_mime, pdf_size, pdf_url, pmax_wc, poids_kg, produit, produit_garantie, produit_marque, produit_nom, rendement_par_irradiance, rendement_pct, techno_cellule, temp_coeff_pmax_pct_c, temp_coeff_voc_pct_c, tolerance_pmax_max_pct, tolerance_pmax_min_pct, type_fiche, uc_w_m2k, uv_w_m3sk, vmp_v, voc_v
    bat_chimie ∈ {autre, lfp, lmo, lto, nca, nmc, plomb_agm, plomb_gel, plomb_ouvert}
    type_fiche ∈ {autre, batterie, module, onduleur, optimiseur}
- frontend/src/api/stockApi.js :: updateModeleBcf -> /api/django/stock/modeles-bcf/<>  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: updateNomenclatureCodeBarres -> /api/django/stock/nomenclatures-code-barres/<>  [NomenclatureCodeBarresSerializer]
    champs: actif, date_creation, date_mise_a_jour, id, nom, regles, type_nomenclature
    type_nomenclature ∈ {default, gs1}
- frontend/src/api/stockApi.js :: updatePrixFournisseur -> /api/django/stock/prix-fournisseurs/<>  [PrixFournisseurSerializer]
    champs: date_debut, date_dernier_achat, date_fin, delai_livraison_jours, fournisseur, fournisseur_nom, id, paliers, prix_achat, produit, produit_nom, ref_produit_fournisseur
- frontend/src/api/stockApi.js :: updateProduit -> /api/django/stock/produits/<>  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_fixe_ht, prix_par_panneau_ht, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, role_devis, role_devis_effectif, role_devis_source, seuil_alerte, sku, specs_solaire, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: updateRegleCodeBarres -> /api/django/stock/regles-code-barres/<>  [RegleCodeBarresSerializer]
    champs: encode, est_regex, id, motif, nomenclature, priorite
    encode ∈ {emplacement, lot, produit, quantite, serie}
- frontend/src/api/stockApi.js :: uploadFicheTechniquePdf -> /api/django/stock/fiches-techniques/<>  [FicheTechniqueSerializer]
    champs: bat_c_rate_charge, bat_c_rate_decharge, bat_chimie, bat_dod_pct, bat_kwh_nominal, bat_kwh_usable, bat_max_charge_kw, bat_max_decharge_kw, bat_max_modules_par_banc, bat_temp_max_c, bat_temp_min_c, bat_v_nominal, bifacial, date_creation, date_mise_a_jour, epaisseur_mm, id, imp_a, isc_a, largeur_mm, longueur_mm, noct_c, ond_ac_kw, ond_bat_aucune, ond_bat_max_charge_kw, ond_bat_max_decharge_kw, ond_bat_v_max, ond_bat_v_min, ond_conso_nuit_w, ond_courbe_rendement, ond_i_max_mppt_a, ond_isc_max_mppt_a, ond_mppt_v_max, ond_mppt_v_min, ond_n_mppt, ond_phases, ond_rendement_cec_pct, ond_rendement_euro_pct, ond_rendement_max_pct, ond_v_demarrage_v, ond_v_max_abs, opt_ac_i_max_a, opt_ac_kw, opt_ac_tension_v, opt_ac_unites_max_par_branche, opt_i_out_max_a, opt_modules_max_par_chaine, opt_pmax_out_w, opt_v_out_max, opt_v_out_min, opt_v_out_nominal_v, pdf, pdf_filename, pdf_mime, pdf_size, pdf_url, pmax_wc, poids_kg, produit, produit_garantie, produit_marque, produit_nom, rendement_par_irradiance, rendement_pct, techno_cellule, temp_coeff_pmax_pct_c, temp_coeff_voc_pct_c, tolerance_pmax_max_pct, tolerance_pmax_min_pct, type_fiche, uc_w_m2k, uv_w_m3sk, vmp_v, voc_v
    bat_chimie ∈ {autre, lfp, lmo, lto, nca, nmc, plomb_agm, plomb_gel, plomb_ouvert}
    type_fiche ∈ {autre, batterie, module, onduleur, optimiseur}
- frontend/src/api/uxviewsApi.js :: createFavori -> /api/django/uxviews/favoris  [FavoriUtilisateurSerializer]
    champs: created_at, id, libelle, modele, object_id, ordre, owner, updated_at
- frontend/src/api/uxviewsApi.js :: deleteFavori -> /api/django/uxviews/favoris/<>  [FavoriUtilisateurSerializer]
    champs: created_at, id, libelle, modele, object_id, ordre, owner, updated_at
- frontend/src/api/uxviewsApi.js :: listFavoris -> /api/django/uxviews/favoris  [FavoriUtilisateurSerializer]
    champs: created_at, id, libelle, modele, object_id, ordre, owner, updated_at
- frontend/src/api/ventesApi.js :: createListePrix -> /api/django/ventes/listes-prix  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: createPlanCommission -> /api/django/ventes/plans-commission  [PlanCommissionSerializer]
    champs: actif, base, base_display, created_at, id, montant_par_kwc, owner, owner_nom, paliers, taux_pct
    base ∈ {ca_devis_signe, marge_interne, par_kwc}
- frontend/src/api/ventesApi.js :: deleteListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: deleteNiveauRelance -> /api/django/ventes/niveaux-relance/<>  [FollowupLevelSerializer]
    champs: canal, delai_jours, frais_fixes, id, message, nom, ordre, taux_interet_annuel
    canal ∈ {appel, courrier, email, whatsapp}
- frontend/src/api/ventesApi.js :: deletePlanCommission -> /api/django/ventes/plans-commission/<>  [PlanCommissionSerializer]
    champs: actif, base, base_display, created_at, id, montant_par_kwc, owner, owner_nom, paliers, taux_pct
    base ∈ {ca_devis_signe, marge_interne, par_kwc}
- frontend/src/api/ventesApi.js :: getListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: getListesPrix -> /api/django/ventes/listes-prix  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: getNiveauxRelance -> /api/django/ventes/niveaux-relance  [FollowupLevelSerializer]
    champs: canal, delai_jours, frais_fixes, id, message, nom, ordre, taux_interet_annuel
    canal ∈ {appel, courrier, email, whatsapp}
- frontend/src/api/ventesApi.js :: getPlansCommission -> /api/django/ventes/plans-commission  [PlanCommissionSerializer]
    champs: actif, base, base_display, created_at, id, montant_par_kwc, owner, owner_nom, paliers, taux_pct
    base ∈ {ca_devis_signe, marge_interne, par_kwc}
- frontend/src/api/ventesApi.js :: patchListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: updateListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: updatePlanCommission -> /api/django/ventes/plans-commission/<>  [PlanCommissionSerializer]
    champs: actif, base, base_display, created_at, id, montant_par_kwc, owner, owner_nom, paliers, taux_pct
    base ∈ {ca_devis_signe, marge_interne, par_kwc}
- frontend/src/features/adminops/adminopsApi.js :: listPackages -> /api/django/adminops/config-packages  [ConfigPackageSerializer]
    champs: contenu, contenu_purge, cree_par, date_creation, id, nom, version
- frontend/src/features/adminops/adminopsApi.js :: listSandbox -> /api/django/adminops/sandbox  [SandboxEnvironmentSerializer]
    champs: cree_par, date_creation, date_expiration, erreur, id, prolongations_count, sandbox_company, statut
    statut ∈ {echec, en_creation, expire, pret}
- frontend/src/features/adsengine/adsengineApi.js :: allDecisions -> /api/django/adsengine/decisions  [DecisionLogSerializer]
    champs: action, allocations, created_at, experiment, id, inputs, posteriors, summary_fr, updated_at
- frontend/src/features/adsengine/adsengineApi.js :: armStats -> /api/django/adsengine/stats-bras  [ArmDailyStatSerializer]
    champs: arm, clicks, conversations, created_at, date, id, impressions, spend, updated_at
- frontend/src/features/adsengine/adsengineApi.js :: arms -> /api/django/adsengine/bras  [ExperimentArmSerializer]
    champs: ad_id, created_at, creative_asset, experiment, hook_id, id, is_active, label, updated_at, visual_id
- frontend/src/features/adsengine/adsengineApi.js :: create -> /api/django/adsengine/regles  [RulePolicySerializer]
    champs: cadence_hours, conditions, cooldown_hours, created_at, dry_run, enabled, id, last_evaluated_at, last_result, mode, params, template_key, updated_at
    mode ∈ {auto, propose}
- frontend/src/features/adsengine/adsengineApi.js :: log -> /api/django/adsengine/actions  [EngineActionSerializer]
    champs: applied_at, approved_by, auto, created_at, error, id, kind, payload, proposed_by, reason_fr, result, status, updated_at
    kind ∈ {create_ad, create_adset, create_campaign, edit_copy, pause, rebalance_budget, rename, rotate_creative, set_spend_cap}
    status ∈ {appliquee, approuvee, echouee, proposee, rejetee}
- frontend/src/features/adsengine/adsengineApi.js :: nodes -> /api/django/adsengine/noeuds-hypothese  [AssumptionNodeSerializer]
    champs: alpha, alpha0, beta, beta0, classe, created_at, dead_branch, demi_vie_semaines, enjeux_s, enonce_fr, id, invalidation_links, last_tested_at, parent, pertinence_r, statut, tags_saison, updated_at
    classe ∈ {angle, audience_structure, creatif}
    statut ∈ {assumed, retired, stale, testing, validated}
- frontend/src/features/adsengine/adsengineApi.js :: pending -> /api/django/adsengine/actions  [EngineActionSerializer]
    champs: applied_at, approved_by, auto, created_at, error, id, kind, payload, proposed_by, reason_fr, result, status, updated_at
    kind ∈ {create_ad, create_adset, create_campaign, edit_copy, pause, rebalance_budget, rename, rotate_creative, set_spend_cap}
    status ∈ {appliquee, approuvee, echouee, proposee, rejetee}
- frontend/src/features/adsengine/adsengineApi.js :: rawItems -> /api/django/adsengine/backlog-creatif  [CreativeBacklogItemSerializer]
    champs: asset, batch, created_at, earliest_date, id, seasonal_tag, source, status, target_campaign, updated_at
    source ∈ {manuel, recombinaison}
    status ∈ {en_file, programme, publie, retire}
