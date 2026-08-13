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
- frontend/src/api/adminopsApi.js :: sessionImpersonationActive -> /api/django/adminops/impersonation/session-active
    active:booleen, expire_le:inconnu, id:inconnu, message:texte, motif:inconnu, support_nom:inconnu
- frontend/src/api/agricultureApi.js :: coutIrrigation -> /api/django/agriculture/campagnes/<>/cout-irrigation
    cout_irrigation_mad:inconnu, volume_irrigation_solaire_m3:inconnu
- frontend/src/api/aoApi.js :: additif -> /api/django/ao/pieces-consultation/<>/additif
    exigences_a_reverifier:inconnu
- frontend/src/api/aoApi.js :: completude -> /api/django/ao/dossiers-ao/<>/completude
    complet:inconnu, pieces_manquantes:liste, raisons_de_non_depot:inconnu, taux_completude:texte
- frontend/src/api/aoApi.js :: controles -> /api/django/ao/bordereaux-prix/<>/controles
    raisons:inconnu, remettable:booleen
- frontend/src/api/aoApi.js :: controlesAvantDepot -> /api/django/ao/dossiers-ao/<>/controles-avant-depot
    bloquant:inconnu, controles:liste, empreinte:inconnu, nombre_hors_controle:nombre, pieces_hors_controle:liste
- frontend/src/api/aoApi.js :: deverrouiller -> /api/django/ao/economie/<>/deverrouiller
    verrouillee:booleen
- frontend/src/api/aoApi.js :: initialiserChecklist -> /api/django/ao/dossiers-ao/<>/initialiser-checklist
    crees:inconnu, deja_presents:inconnu
- frontend/src/api/aoApi.js :: lancer -> /api/django/ao/calepinage/lancer
    id:inconnu, kind:inconnu, message_erreur:texte, progress_pct:inconnu, resultat:inconnu, statut:inconnu, variante:inconnu
- frontend/src/api/aoApi.js :: resultat -> /api/django/ao/calepinage/resultat/<>
    id:inconnu, kind:inconnu, message_erreur:inconnu, progress_pct:inconnu, resultat:inconnu, statut:inconnu, variante:inconnu
- frontend/src/api/aoApi.js :: tableauMarches -> /api/django/ao/tableau-marches
    capacite:objet, cautions:objet, echeances_dues:nombre, en_cours:objet, marches_en_execution:objet, reussite:objet
- frontend/src/api/aoApi.js :: verrouiller -> /api/django/ao/economie/<>/verrouiller
    verrouillee:booleen
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
- frontend/src/api/btpChantierApi.js :: faireApprouver -> /api/django/btp-chantier/avenants-chantier/<>/faire-approuver
    avenant:inconnu, detail:texte, lien_public:texte
- frontend/src/api/btpChantierApi.js :: lever -> /api/django/btp-chantier/reserves-chantier/<>/lever
    detail:texte, reserve:inconnu, signature:inconnu
- frontend/src/api/comptaApi.js :: appliquer -> /api/django/compta/modeles-rapprochement/<>/appliquer
    detail:inconnu, ecriture_id:inconnu, reference:inconnu
- frontend/src/api/comptaApi.js :: collecter -> /api/django/compta/cycles-consolidation/<>/collecter
    cycle:inconnu, detail:inconnu, liasses:inconnu
- frontend/src/api/comptaApi.js :: etatsConsolides -> /api/django/compta/cycles-consolidation/<>/etats-consolides
    bilan:inconnu, cpc:inconnu
- frontend/src/api/comptaApi.js :: genererFae -> /api/django/compta/provisions-periode/generer-fae
    detail:inconnu, postees:inconnu
- frontend/src/api/comptaApi.js :: genererFnp -> /api/django/compta/provisions-periode/generer-fnp
    detail:inconnu, postees:inconnu
- frontend/src/api/comptaApi.js :: genererOd -> /api/django/compta/taches-cloture/<>/generer-od
    detail:inconnu, ecriture_id:inconnu, tache:inconnu
- frontend/src/api/comptaApi.js :: importer -> /api/django/compta/balance-ouverture/importer
    deja_importee:inconnu, detail:texte, ecriture_id:inconnu, erreurs:inconnu, ok:booleen, reference:inconnu, total:texte
- frontend/src/api/comptaApi.js :: mettreEnService -> /api/django/compta/immobilisations-en-cours/<>/mettre-en-service
    detail:inconnu, encours:inconnu, immobilisation_id:inconnu
- frontend/src/api/comptaApi.js :: ocr -> /api/django/compta/notes-frais/ocr
    champs:inconnu, detail:texte, justificatif:texte
- frontend/src/api/comptaApi.js :: positionTresorerie -> /api/django/compta/etats/position-tresorerie
    comptes:inconnu, projection:inconnu, total:inconnu
- frontend/src/api/comptaApi.js :: posterMouvement -> /api/django/compta/caisses/<>/poster-mouvement
    detail:inconnu, ecriture_id:inconnu, mouvement:inconnu
- frontend/src/api/comptaApi.js :: refacturer -> /api/django/compta/notes-frais/refacturer
    detail:inconnu, facture_id:inconnu, refacture:booleen
- frontend/src/api/comptaApi.js :: reschedule -> /api/django/compta/calendrier-marketing/reschedule
    detail:texte, ok:booleen
- frontend/src/api/contratsApi.js :: appliquerIndexation -> /api/django/contrats/indexations/<>/appliquer
    avenant_id:inconnu, avenant_numero:inconnu, delta:texte, detail:texte, lignes_reappliquees:inconnu, prix_base:texte, prix_revise:texte
- frontend/src/api/contratsApi.js :: campagneRevision -> /api/django/contrats/contrats/campagne-revision
    avenants_crees:inconnu, lignes:liste, preview:booleen, rollback_ids:inconnu
- frontend/src/api/contratsApi.js :: campagneRevisionRollback -> /api/django/contrats/contrats/campagne-revision-rollback
    avenant_ids:liste, compensations_creees:nombre
- frontend/src/api/contratsApi.js :: cautionRetenir -> /api/django/contrats/ordres-location/<>/caution/retenir
    detail:texte, facture_id:inconnu, facture_reference:inconnu, ordre:inconnu
- frontend/src/api/contratsApi.js :: declencherAlertes -> /api/django/contrats/alertes/declencher
    alertes:inconnu, nb_dues:inconnu, nb_envoyees:inconnu, nb_notifications:inconnu
- frontend/src/api/contratsApi.js :: facturerCycleLocation -> /api/django/contrats/ordres-location/<>/facturer-cycle
    detail:texte, facture_id:inconnu, facture_reference:inconnu, ordre:inconnu
- frontend/src/api/contratsApi.js :: facturerLigne -> /api/django/contrats/lignes-echeance/<>/facturer
    detail:texte, facture_id:inconnu, facture_reference:inconnu, ligne:inconnu
- frontend/src/api/contratsApi.js :: genererDevisRenouvellement -> /api/django/contrats/contrats/<>/generer-devis-renouvellement
    detail:texte, devis_id:inconnu, devis_reference:inconnu, note:inconnu
- frontend/src/api/contratsApi.js :: getClv -> /api/django/contrats/contrats/clv
    arpc:inconnu, client_id:inconnu, clv:inconnu, detail:texte, duree_vie_mois:inconnu, plafonnee:inconnu, used_fallback:inconnu
- frontend/src/api/contratsApi.js :: getCohortesRetention -> /api/django/contrats/contrats/cohortes-retention
    cohortes:inconnu, mois_max:inconnu
- frontend/src/api/contratsApi.js :: getMrrMouvements -> /api/django/contrats/contrats/mrr-mouvements
    churn:inconnu, churn_par_motif:inconnu, contraction:inconnu, debut:texte, detail:texte, expansion:inconnu, fin:texte, net:inconnu, net_par_responsable:inconnu, new:inconnu
- frontend/src/api/contratsApi.js :: getReporting -> /api/django/contrats/contrats/reporting
    nb_contrats_renouveles:inconnu, nb_echus:inconnu, nb_renouvellements:inconnu, taux_renouvellement:texte, valeur_active:inconnu, valeur_par_type:inconnu, valeur_totale:inconnu
- frontend/src/api/contratsApi.js :: getStatutsSuivants -> /api/django/contrats/contrats/<>/statuts-suivants
    statut:inconnu, suivants:inconnu
- frontend/src/api/contratsApi.js :: getTableauBord -> /api/django/contrats/contrats/tableau-de-bord
    a_renouveler:inconnu, actifs:inconnu, en_risque:inconnu, exceptions_facturation:inconnu, mrr:inconnu, mrr_combine:inconnu, mrr_par_responsable:inconnu, par_statut:inconnu, par_type:inconnu, total:inconnu, valeur_active:inconnu, valeur_totale:inconnu
- frontend/src/api/contratsApi.js :: penaliteSla -> /api/django/contrats/sla/<>/penalite
    penalite:texte, respecte:inconnu, taux_cible:texte, taux_realise:inconnu
- frontend/src/api/contratsApi.js :: rejouerCycle -> /api/django/contrats/cycles-facturation/<>/rejouer
    detail:texte, facture_id:inconnu, facture_reference:inconnu, log:inconnu
- frontend/src/api/contratsApi.js :: resoudreRegleApprobation -> /api/django/contrats/regles-approbation/resoudre
    regle:inconnu
- frontend/src/api/contratsApi.js :: semerAlertes -> /api/django/contrats/alertes/semer-echeances
    alertes:inconnu, nb_creees:inconnu
- frontend/src/api/contratsApi.js :: signer -> /api/django/contrats/contrats/<>/signer
    contrat_actif:inconnu, contrat_signe:inconnu, detail:texte, signature:inconnu, statut:inconnu
- frontend/src/api/contratsApi.js :: simulerIndexation -> /api/django/contrats/indexations/<>/simuler
    delta:texte, detail:texte, prix_base:texte, prix_revise:texte, valeur_actuelle:texte
- frontend/src/api/contratsApi.js :: traiterReconductions -> /api/django/contrats/contrats/traiter-reconductions
    contrats:inconnu, nb_renouvellements:inconnu, nb_traites:inconnu
- frontend/src/api/coreApi.js :: activer -> /api/django/core/modules/<>/activer
    actives:inconnu, detail:texte
- frontend/src/api/coreApi.js :: appliquer -> /api/django/core/bulk-edit/appliquer
    detail:texte, modifies:inconnu
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
- frontend/src/api/cpqApi.js :: appliquerOffreGroupee -> /api/django/cpq/offres-groupees/<>/appliquer
    detail:texte, lignes_creees:liste, sous_total_ht:texte
- frontend/src/api/cpqApi.js :: demarrerConfigurateur -> /api/django/cpq/configurateur/demarrer
    questions:inconnu, session:texte
- frontend/src/api/cpqApi.js :: genererDevisConfigurateur -> /api/django/cpq/configurateur/<>/generer-devis
    detail:texte, devis_id:inconnu, reference:inconnu
- frontend/src/api/cpqApi.js :: repondreConfigurateur -> /api/django/cpq/configurateur/<>/repondre
    detail:texte
- frontend/src/api/cpqApi.js :: validerCompatibilite -> /api/django/cpq/valider-compatibilite
    avertissements:inconnu, bloquantes:inconnu, detail:texte, valide:booleen, violations:inconnu
- frontend/src/api/crmApi.js :: checkDevisAuto -> /api/django/crm/leads/<>/devis-auto
    detail:inconnu, ok:booleen
- frontend/src/api/crmApi.js :: clientDataExport -> /api/django/crm/clients/<>/data-export
    documents:inconnu, identite:inconnu
- frontend/src/api/crmApi.js :: confirmerAppointmentWhatsapp -> /api/django/crm/appointments/<>/confirmer-whatsapp
    detail:texte, ics_url:inconnu, message:inconnu, wa_url:inconnu
- frontend/src/api/crmApi.js :: convertirLeadEnClient -> /api/django/crm/leads/<>/convertir-client
    client:inconnu, detail:texte, mode:inconnu
- frontend/src/api/crmApi.js :: getClientConsolidation -> /api/django/crm/clients/<>/consolidation
    ca_devis_total:texte, ca_factures_total:texte, filiales:liste, nb_devis_total:inconnu, nb_factures_total:inconnu
- frontend/src/api/crmApi.js :: getEquipesStatistiques -> /api/django/crm/equipes/statistiques
    equipes:inconnu
- frontend/src/api/crmApi.js :: getLeadPointsContact -> /api/django/crm/leads/<>/points-contact
    count:inconnu, cout_total:inconnu, first_touch:inconnu, last_touch:inconnu, lead_id:inconnu, timeline:inconnu
- frontend/src/api/crmApi.js :: getRelances -> /api/django/crm/leads/relances
    count:nombre, results:inconnu
- frontend/src/api/crmApi.js :: getSlaBreach -> /api/django/crm/leads/sla-breach
    count:nombre, results:inconnu, sla_hours:inconnu
- frontend/src/api/crmApi.js :: parrainageStats -> /api/django/crm/parrainages/stats
    par_statut:inconnu, recompenses_total:texte, recompenses_versees:texte, total:inconnu
- frontend/src/api/crmApi.js :: renderMessageTemplate -> /api/django/crm/message-templates/<>/render
    texte:inconnu
- frontend/src/api/crmApi.js :: replayWebsiteLeadPayload -> /api/django/crm/website-lead-payloads/<>/replay
    detail:inconnu, payload:inconnu
- frontend/src/api/crmApi.js :: restaurerCorbeille -> /api/django/core/corbeille/<>/restaurer
    record:inconnu, restored:booleen
- frontend/src/api/crmApi.js :: searchClients -> /api/django/crm/clients/search
    results:inconnu
- frontend/src/api/crmApi.js :: whatsappDevis -> /api/django/crm/leads/<>/whatsapp-devis
    detail:texte, links:inconnu, message:inconnu, phone:inconnu, wa_url:inconnu
- frontend/src/api/customFieldsApi.js :: reorder -> /api/django/custom-fields/definitions/reorder
    count:nombre, detail:texte, ok:booleen
- frontend/src/api/demoApi.js :: resetDemo -> /api/django/companies/<>/reset-demo
    detail:texte, slug:inconnu
- frontend/src/api/educationApi.js :: reinscriptionMasse -> /api/django/education/inscriptions/reinscription-masse
    creees:nombre, deja_existantes:inconnu, inscriptions:inconnu
- frontend/src/api/educationApi.js :: trombinoscope -> /api/django/education/classes/<>/trombinoscope
    count:nombre, results:inconnu
- frontend/src/api/einvoiceApi.js :: controler -> /api/django/einvoice/factures-electroniques/<>/controler
    anomalies:inconnu, conforme:booleen
- frontend/src/api/esgApi.js :: badgeMaturite -> /api/django/esg/catalogue-esg/badge-maturite
    composantes:objet, disclaimer:inconnu, score:inconnu
- frontend/src/api/esgApi.js :: comparer -> /api/django/esg/periodes-esg/comparer
    detail:texte, periode_n:objet, periode_reference:objet, piliers:inconnu
- frontend/src/api/esgApi.js :: couverture -> /api/django/esg/catalogue-esg/couverture
    global_pct:inconnu, piliers:inconnu
- frontend/src/api/flotteApi.js :: alertesEcheances -> /api/django/flotte/echeances-reglementaires/alertes-echeances
    alertes:inconnu, buckets:inconnu, horizon_jours:inconnu, nb_echu:nombre, nb_j15:nombre, nb_j30:nombre, nb_j7:nombre, nb_total:nombre, today:inconnu
- frontend/src/api/flotteApi.js :: anomalies -> /api/django/flotte/cartes/anomalies
    anomalies:inconnu, nb_anomalies:nombre, nb_pleins:nombre, vehicule:texte, vehicule_id:inconnu
- frontend/src/api/flotteApi.js :: echeances -> /api/django/flotte/plans-entretien/echeances
    nb_due:inconnu, nb_plans:nombre, nb_upcoming:inconnu, plans:inconnu
- frontend/src/api/flotteApi.js :: evaluer -> /api/django/flotte/zones-geographiques/evaluer
    alertes:inconnu, nb_alertes:nombre
- frontend/src/api/flotteApi.js :: generer -> /api/django/flotte/echeances-entretien/generer
    echeances:inconnu, nb_creees:inconnu, nb_existantes:inconnu, nb_plans_due:inconnu
- frontend/src/api/flotteApi.js :: masse -> /api/django/flotte/affectations/masse
    detail:texte, echecs:inconnu, reussies:inconnu
- frontend/src/api/flotteApi.js :: ocr -> /api/django/flotte/pleins/ocr
    champs:inconnu, detail:texte, photo:texte
- frontend/src/api/flotteApi.js :: rapportBudget -> /api/django/flotte/rapports/budget
    annee:inconnu, categories:inconnu, total_budgete:nombre, total_realise:nombre
- frontend/src/api/flotteApi.js :: rapportRemplacement -> /api/django/flotte/rapports/remplacement
    a_remplacer:inconnu, budget_annuel_estime:nombre, seuils:objet, vehicules:inconnu
- frontend/src/api/flotteApi.js :: rapprocher -> /api/django/flotte/rappels-constructeur/<>/rapprocher
    nb_vin_matches:inconnu, signalements_crees:liste
- frontend/src/api/flotteApi.js :: rollout -> /api/django/flotte/plans-entretien/<>/rollout
    crees:inconnu, detail:texte, ignores:inconnu
- frontend/src/api/flotteApi.js :: tableauBord -> /api/django/flotte/vehicules/tableau-bord
    couts:objet, echeances:objet, engins:objet, entretien:objet, pool:objet, today:inconnu, vehicules:objet
- frontend/src/api/flotteApi.js :: vehiculeEcoConduite -> /api/django/flotte/vehicules/<>/eco-conduite
    co2_g_par_km:inconnu, co2_kg:inconnu, conso_kwh_100km:inconnu, conso_l_100km:inconnu, distance_totale_km:inconnu, energie:inconnu, facteur_co2_kg_par_litre:inconnu, kwh_total:nombre, litres_total:nombre, nb_pleins:inconnu, nb_surconsommation:inconnu, score_eco:inconnu, vehicule_id:inconnu
- frontend/src/api/flotteApi.js :: vehiculeTco -> /api/django/flotte/vehicules/<>/tco
    actif_flotte_id:inconnu, amortissement_cumule:inconnu, carburant:nombre, cout_par_km:inconnu, cout_total:nombre, distance_totale_km:inconnu, infractions:nombre, part_charges_non_deductibles:inconnu, pct_charges_non_deductibles:inconnu, pneus_pieces:nombre, reparations:nombre, sinistres:nombre, vehicule_id:inconnu
- frontend/src/api/flotteApi.js :: vehiculeTsav -> /api/django/flotte/vehicules/<>/tsav
    annee:inconnu, bareme_id:inconnu, energie:inconnu, exonere:booleen, montant:inconnu, note:texte, puissance_fiscale:inconnu
- frontend/src/api/fpaApi.js :: comparerScenarios -> /api/django/fpa/scenarios/comparer
    base:texte, detail:texte, scenarios:liste
- frontend/src/api/fpaApi.js :: sensibilite -> /api/django/fpa/scenarios/sensibilite
    detail:texte, points:inconnu, variable:inconnu
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
- frontend/src/api/gedApi.js :: leverLegalHold -> /api/django/ged/legal-holds/<>/lever
    detail:texte, leves:inconnu
- frontend/src/api/gedApi.js :: purgerDocument -> /api/django/ged/documents/<>/purger
    detail:texte
- frontend/src/api/gedApi.js :: semanticSearch -> /api/django/ged/documents/semantique
    mode:texte, results:inconnu
- frontend/src/api/gedApi.js :: toggleFavoriDocument -> /api/django/ged/documents/<>/favori
    favori:booleen
- frontend/src/api/gestionProjetApi.js :: getBudgetTotal -> /api/django/gestion-projet/budgets/<>/total
    nb_lignes:inconnu, par_categorie:inconnu, total:texte
- frontend/src/api/gestionProjetApi.js :: getBurndown -> /api/django/gestion-projet/projets/<>/burndown
    charge_totale:texte, detail:texte, points:liste
- frontend/src/api/gestionProjetApi.js :: getGrilleSemaineTemps -> /api/django/gestion-projet/timesheets/semaine
    debut_semaine:inconnu, detail:texte, fin_semaine:inconnu, jours:inconnu, lignes:liste, suggestions:inconnu, total_par_jour:liste, total_semaine:texte
- frontend/src/api/gestionProjetApi.js :: getLienEvaluation -> /api/django/gestion-projet/projets/<>/lien-evaluation
    deja_soumis:booleen, projet_id:inconnu, token:inconnu
- frontend/src/api/gestionProjetApi.js :: getPortefeuille -> /api/django/gestion-projet/projets/portefeuille
    nb_projets:inconnu, projets:liste, total_charge:texte, total_marge_reelle:texte, total_retards:inconnu, total_risques:inconnu
- frontend/src/api/gestionProjetApi.js :: getProjetCoutsEngagesReels -> /api/django/gestion-projet/projets/<>/couts-engages-reels
    budget_id:inconnu, budget_statut:inconnu, budget_version:inconnu, nb_liens_depense:inconnu, par_categorie:liste, total:objet
- frontend/src/api/gestionProjetApi.js :: getProjetPnl -> /api/django/gestion-projet/projets/<>/pnl
    budget_id:inconnu, budget_version:inconnu, cout_budget:texte, cout_reel:texte, cout_reel_affectations:texte, cout_reel_timesheets:texte, couts_par_categorie:liste, marge_pct_reelle:inconnu, marge_prev:texte, marge_reelle:texte, note_revenu:inconnu, revenu:texte
- frontend/src/api/gestionProjetApi.js :: getRapprochementTemps -> /api/django/gestion-projet/timesheets/rapprochement
    debut:texte, detail:texte, ecarts:liste, fin:texte
- frontend/src/api/gestionProjetApi.js :: getTempsManquants -> /api/django/gestion-projet/timesheets/manquants
    debut:texte, detail:texte, fin:texte, lignes:liste
- frontend/src/api/gestionProjetApi.js :: versTicketSav -> /api/django/gestion-projet/taches/<>/vers-ticket-sav
    detail:texte, ticket_reference:inconnu, ticket_sav_id:inconnu
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
- frontend/src/api/immobilierApi.js :: resolveClient -> /api/django/immobilier/locataires/<>/resolve-client
    client_ventes_id:inconnu
- frontend/src/api/importApi.js :: getExportObjects -> /api/django/imports/export-objects
    default_format:inconnu, formats:liste, objects:inconnu
- frontend/src/api/importApi.js :: saveMapping -> /api/django/imports/mapping
    detail:texte, id:inconnu, mapping:inconnu, nom:inconnu, target:inconnu
- frontend/src/api/innovationApi.js :: auteurs -> /api/django/innovation/idees/auteurs
    results:inconnu
- frontend/src/api/innovationApi.js :: contextes -> /api/django/innovation/idees/contextes
    results:inconnu
- frontend/src/api/innovationApi.js :: geolocalisation -> /api/django/innovation/idees/geolocalisation
    results:inconnu
- frontend/src/api/innovationApi.js :: hotspot -> /api/django/innovation/feedback-hotspot
    results:inconnu
- frontend/src/api/innovationApi.js :: incitation -> /api/django/innovation/campagnes/incitation
    campagne:inconnu, campagne_fermee:inconnu, date_fin:inconnu, fermee:booleen
- frontend/src/api/innovationApi.js :: resume -> /api/django/innovation/feedback-resume
    results:inconnu
- frontend/src/api/innovationApi.js :: segmentsDisponibles -> /api/django/innovation/campagnes/segments-disponibles
    results:inconnu
- frontend/src/api/innovationApi.js :: similaires -> /api/django/innovation/idees/similaires
    results:inconnu
- frontend/src/api/innovationApi.js :: timeline -> /api/django/innovation/timeline
    results:inconnu
- frontend/src/api/innovationApi.js :: timelineIdee -> /api/django/innovation/idees/<>/timeline
    results:inconnu
- frontend/src/api/installationsApi.js :: ajouterPhoto -> /api/django/installations/interventions/<>/ajouter-photo
    detail:inconnu, filename:inconnu, id:inconnu, phase:inconnu, slot:inconnu, url:texte
- frontend/src/api/installationsApi.js :: annulerFactureSousTraitant -> /api/django/installations/factures-sous-traitant/<>/annuler
    detail:texte
- frontend/src/api/installationsApi.js :: besoinMateriel -> /api/django/installations/chantiers/<>/besoin-materiel
    installation:inconnu, items:inconnu, nb_manques:nombre, reference:inconnu
- frontend/src/api/installationsApi.js :: cocherChecklist -> /api/django/installations/chantiers/<>/cocher-checklist
    completion:inconnu, detail:texte, equipements_crees:inconnu, items:inconnu
- frontend/src/api/installationsApi.js :: confirmerToolReturn -> /api/django/installations/interventions/<>/confirmer-tool-return
    non_rendus:inconnu, tool_returns:inconnu
- frontend/src/api/installationsApi.js :: creerInterventionsStandard -> /api/django/installations/chantiers/<>/creer-interventions-standard
    created:inconnu, detail:texte, existants:inconnu
- frontend/src/api/installationsApi.js :: envoyerConsultationsRFQ -> /api/django/installations/rfq/<>/envoyer-consultations
    resultats:inconnu
- frontend/src/api/installationsApi.js :: getAffectabiliteSousTraitant -> /api/django/installations/attestations-sous-traitant/affectabilite
    actif:inconnu, affectable:inconnu, date:texte, detail:texte, pieces_expirees:inconnu, sous_traitant:inconnu
- frontend/src/api/installationsApi.js :: getChantierCout -> /api/django/installations/chantiers/<>/cout
    devis_total_ht:inconnu, devis_total_ttc:inconnu, installation:inconnu, labour:objet, marge:inconnu, marge_taux:inconnu, materiel:objet, reference:inconnu
- frontend/src/api/installationsApi.js :: getChecklist -> /api/django/installations/chantiers/<>/checklist
    completion:inconnu, installation:inconnu, items:inconnu
- frontend/src/api/installationsApi.js :: getCode -> /api/django/installations/interventions/<>/code
    intervention:inconnu, qr_svg:inconnu, token:inconnu
- frontend/src/api/installationsApi.js :: getEtapesChantier -> /api/django/installations/chantiers/<>/etapes
    etape_courante:inconnu, etapes:inconnu, installation:inconnu, reference:inconnu
- frontend/src/api/installationsApi.js :: getMaTournee -> /api/django/installations/interventions/ma-tournee
    date:inconnu, stops:inconnu
- frontend/src/api/installationsApi.js :: getPhotoQa -> /api/django/installations/interventions/<>/photo-qa
    actif:inconnu, signalements:inconnu
- frontend/src/api/installationsApi.js :: getPhotos -> /api/django/installations/interventions/<>/photos
    autres:inconnu, created_at:inconnu, filename:inconnu, groupes:inconnu, id:inconnu, intervention:inconnu, mime:inconnu, obligatoires_manquants:liste, sans_creneau:inconnu, uploaded_by_nom:inconnu, url:texte
- frontend/src/api/installationsApi.js :: getRegimeSuggestion -> /api/django/installations/chantiers/regime-suggestion
    code:inconnu, label:inconnu, seuil_anre_kwc:inconnu, seuil_declaration_kwc:inconnu
- frontend/src/api/installationsApi.js :: overageReview -> /api/django/installations/interventions/overage-review
    interventions:inconnu, seuil_pct:inconnu
- frontend/src/api/installationsApi.js :: relancerNonRepondantsRFQ -> /api/django/installations/rfq/<>/relancer-non-repondants
    resultats:inconnu
- frontend/src/api/installationsApi.js :: supprimerLigneConsommation -> /api/django/installations/interventions/<>/supprimer-ligne-consommation
    detail:texte
- frontend/src/api/installationsApi.js :: supprimerMemo -> /api/django/installations/interventions/<>/supprimer-memo
    detail:texte
- frontend/src/api/installationsApi.js :: supprimerPhoto -> /api/django/installations/interventions/<>/supprimer-photo
    detail:texte
- frontend/src/api/installationsApi.js :: supprimerSerial -> /api/django/installations/interventions/<>/supprimer-serial
    detail:texte
- frontend/src/api/kbApi.js :: descendantsCount -> /api/django/kb/articles/<>/descendants-count
    nb_descendants:nombre
- frontend/src/api/kbApi.js :: togglerFavori -> /api/django/kb/articles/<>/toggler-favori
    favori:inconnu
- frontend/src/api/marketingApi.js :: apercuFusion -> /api/django/marketing/campagnes/<>/apercu_fusion
    corps_fusionne:inconnu, detail:texte
- frontend/src/api/marketingApi.js :: cloturerPresences -> /api/django/marketing/evenements-marketing/<>/cloturer-presences
    absents_marques:inconnu
- frontend/src/api/marketingApi.js :: genererIa -> /api/django/marketing/campagnes/generer-ia
    configured:inconnu, corps:inconnu, langue:inconnu, objet:inconnu, ok:inconnu, source:inconnu
- frontend/src/api/marketingApi.js :: genererIaDisponible -> /api/django/marketing/campagnes/generer-ia-disponible
    configured:inconnu
- frontend/src/api/marketingApi.js :: participants -> /api/django/marketing/sequences-relance/<>/participants
    nb_actifs:inconnu, participants:inconnu
- frontend/src/api/marketingApi.js :: planifier -> /api/django/marketing/sequences-relance/<>/planifier
    etapes:inconnu
- frontend/src/api/messagesApi.js :: follow -> /api/django/chat/messages/<>/thread-follow
    status:texte
- frontend/src/api/messagesApi.js :: removeMember -> /api/django/chat/conversations/<>/members/<>
    detail:texte
- frontend/src/api/messagesApi.js :: toggleBookmark -> /api/django/chat/messages/<>/bookmark
    status:inconnu
- frontend/src/api/messagesApi.js :: toggleReaction -> /api/django/chat/messages/<>/react
    detail:texte, message:inconnu, status:inconnu
- frontend/src/api/messagesApi.js :: unfollow -> /api/django/chat/messages/<>/thread-unfollow
    status:texte
- frontend/src/api/migrationApi.js :: chargerLot -> /api/django/migration/lots-migration/<>/charger
    lot:inconnu, resultat:inconnu
- frontend/src/api/monitoringApi.js :: emailOmReport -> /api/django/monitoring/configs/<>/email-om-report
    sent:inconnu
- frontend/src/api/monitoringApi.js :: facturerAbonnement -> /api/django/monitoring/abonnements-monitoring/<>/facturer
    detail:inconnu, facture_id:inconnu, montant_ttc:texte, reference:inconnu
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
- frontend/src/api/notificationsApi.js :: pushSubscribe -> /api/django/notifications/push/subscribe
    detail:texte, id:inconnu
- frontend/src/api/notificationsApi.js :: pushUnsubscribe -> /api/django/notifications/push/unsubscribe
    deleted:inconnu, detail:texte
- frontend/src/api/notificationsApi.js :: unreadCount -> /api/django/notifications/notifications/unread-count
    actions:inconnu, infos:nombre, unread:inconnu
- frontend/src/api/paieApi.js :: appliquerStructure -> /api/django/paie/structures/<>/appliquer
    detail:texte, rattachees:inconnu
- frontend/src/api/paieApi.js :: declarationCimr -> /api/django/paie/periodes/<>/declaration-cimr
    annee:inconnu, lignes:inconnu, mois:inconnu, nombre_affilies:nombre, total_base:inconnu, total_cimr_salariale:inconnu
- frontend/src/api/paieApi.js :: declarationCnss -> /api/django/paie/periodes/<>/declaration-cnss
    annee:inconnu, lignes:inconnu, mois:inconnu, nombre_salaries:nombre, plafond_cnss:inconnu
- frontend/src/api/paieApi.js :: deposerBds -> /api/django/paie/periodes/<>/deposer-bds
    date_depot:inconnu, id:inconnu, profils_couverts:inconnu, type_depot:inconnu
- frontend/src/api/paieApi.js :: deposerBdsComplementaire -> /api/django/paie/periodes/<>/deposer-bds-complementaire
    date_depot:inconnu, depot_principal:inconnu, detail:texte, id:inconnu, profils_couverts:inconnu, type_depot:inconnu
- frontend/src/api/paieApi.js :: etatIr -> /api/django/paie/periodes/<>/etat-ir
    annee:inconnu, lignes:inconnu, mois:inconnu, nombre_salaries:nombre, total_brut_imposable:inconnu, total_exonere_regime:inconnu, total_ir:inconnu, total_net_imposable:inconnu
- frontend/src/api/paieApi.js :: etatIrAnnuel -> /api/django/paie/periodes/etat-ir-annuel
    annee:inconnu, detail:texte, lignes:inconnu, nombre_salaries:nombre, total_brut_imposable:inconnu, total_ir:inconnu, total_net_imposable:inconnu
- frontend/src/api/paieApi.js :: expirerRegimesExoneration -> /api/django/paie/profils/expirer-regimes
    bascules:liste
- frontend/src/api/paieApi.js :: fichierCimr -> /api/django/paie/periodes/<>/fichier-cimr
    lignes:inconnu, nombre_affilies:inconnu, total_base:inconnu, total_cimr_salariale:inconnu
- frontend/src/api/paieApi.js :: fichierDamancom -> /api/django/paie/periodes/<>/fichier-damancom
    lignes:inconnu, nombre_salaries:inconnu, total_brut:inconnu, total_plafonne:inconnu
- frontend/src/api/paieApi.js :: fichierDamancomStrict -> /api/django/paie/periodes/<>/fichier-damancom-strict
    lignes:inconnu, nombre_salaries:nombre
- frontend/src/api/paieApi.js :: importerElementsRh -> /api/django/paie/periodes/<>/importer-elements-rh
    detail:texte, importes:inconnu
- frontend/src/api/paieApi.js :: journalDePaie -> /api/django/paie/periodes/<>/journal-de-paie
    detail:inconnu, ecriture_id:inconnu, reference:inconnu
- frontend/src/api/paieApi.js :: journalVentile -> /api/django/paie/periodes/<>/journal-ventile
    detail:texte, id:inconnu, reference:inconnu
- frontend/src/api/paieApi.js :: livreDePaie -> /api/django/paie/periodes/<>/livre-de-paie
    annee:inconnu, lignes:inconnu, mois:inconnu, nombre_salaries:nombre, totaux:inconnu
- frontend/src/api/paieApi.js :: mouvementsCnss -> /api/django/paie/periodes/<>/mouvements-cnss
    entrees:inconnu, sorties:inconnu
- frontend/src/api/paieApi.js :: notifierEcheancesRetard -> /api/django/paie/periodes/notifier-echeances-retard
    notifiees:nombre
- frontend/src/api/paieApi.js :: payerEcheance -> /api/django/paie/echeances-declaratives/<>/payer
    detail:texte, echeance:inconnu, ecriture_id:inconnu
- frontend/src/api/paieApi.js :: payerOrdreVirement -> /api/django/paie/ordres-virement/<>/payer
    detail:texte, ecriture_id:inconnu, ordre:inconnu
- frontend/src/api/paieApi.js :: rapprochementGl -> /api/django/paie/periodes/<>/rapprochement-gl
    annee:inconnu, coherent:booleen, ecart_total:inconnu, lignes:inconnu, mois:inconnu
- frontend/src/api/paieApi.js :: reporterElements -> /api/django/paie/periodes/<>/reporter-elements
    nombre:nombre, reconduits:liste
- frontend/src/api/paieApi.js :: runGratification -> /api/django/paie/periodes/<>/run-gratification
    bulletins:liste, detail:texte, nombre:nombre
- frontend/src/api/parametresApi.js :: getEmailTemplates -> /api/django/parametres/email-templates/effective
    results:inconnu
- frontend/src/api/parametresApi.js :: getStatutsEffective -> /api/django/parametres/statuts/effective
    detail:texte, domaine:inconnu, results:inconnu
- frontend/src/api/parametresApi.js :: getTranslationOverrides -> /api/django/parametres/traductions/effective
    overrides:inconnu
- frontend/src/api/parametresApi.js :: saveEmailTemplates -> /api/django/parametres/email-templates/bulk
    detail:texte, results:inconnu
- frontend/src/api/parametresApi.js :: saveStatuts -> /api/django/parametres/statuts/bulk
    detail:texte, domaine:inconnu, results:inconnu
- frontend/src/api/parametresApi.js :: saveTranslationOverrides -> /api/django/parametres/traductions/bulk
    detail:texte, overrides:inconnu
- frontend/src/api/portailApi.js :: accepter -> /api/django/portail/mes-devis/<>/accepter
    detail:inconnu, reference:inconnu, statut:inconnu
- frontend/src/api/portailApi.js :: payer -> /api/django/portail/mes-factures/<>/payer
    detail:texte, montant:texte, paiement_en_ligne_actif:inconnu, paiement_id:inconnu, reference:inconnu, statut:inconnu, virement:objet
- frontend/src/api/portailApi.js :: provisionnerAcces -> /api/django/portail/comptes-portail/<>/provisionner-acces
    actif:inconnu, cree:inconnu, detail:texte, email:inconnu, username:inconnu, utilisateur_id:inconnu
- frontend/src/api/posApi.js :: encaisserFacture -> /api/django/pos/ventes/encaisser-facture
    facture:inconnu, id:inconnu, mode:inconnu, montant:texte
- frontend/src/api/posApi.js :: rapportZ -> /api/django/pos/sessions/<>/rapport-z
    nb_ventes:inconnu, par_mode:inconnu, total:texte
- frontend/src/api/posApi.js :: searchClients -> /api/django/crm/clients/search
    results:inconnu
- frontend/src/api/posApi.js :: ticketShareLink -> /api/django/pos/ventes/<>/ticket-share-link
    expires_at:inconnu, token:inconnu
- frontend/src/api/publicapiApi.js :: getCatalogue -> /api/django/publicapi/catalogue
    events:liste, scopes:liste
- frontend/src/api/publicapiApi.js :: getChangelog -> /api/public/changelog
    results:liste
- frontend/src/api/publicapiApi.js :: getDocs -> /api/django/publicapi/docs
    authentification:objet, base_url:texte, endpoints:liste, endpoints_bulk:objet, endpoints_ecriture:objet, endpoints_lecture_simple:objet, introduction:texte, parametres_communs:objet, scopes:liste, titre:texte, version:texte, webhooks:objet
- frontend/src/api/publicapiApi.js :: getOpenApiSchema -> /api/public/v1/openapi.json
    components:objet, info:objet, openapi:inconnu, paths:inconnu, security:liste, servers:liste
- frontend/src/api/publicapiApi.js :: ocrToCrm -> /api/django/publicapi/ocr-to-crm
    detail:texte, lead_id:inconnu, mode:inconnu
- frontend/src/api/publicapiApi.js :: sandboxTry -> /api/django/publicapi/sandbox/try
    detail:texte, resource:inconnu, results:inconnu, sandbox:booleen
- frontend/src/api/qhseApi.js :: compteurs -> /api/django/qhse/observations-securite/compteurs
    a_risque:inconnu, par_superviseur_mois:liste, ratio_sur_pct:inconnu, sures:inconnu, total:inconnu
- frontend/src/api/qhseApi.js :: criticite -> /api/django/qhse/evaluations-risque/<>/criticite
    criticite_max:inconnu, criticite_moyenne:inconnu, nb_lignes:inconnu, par_niveau:inconnu
- frontend/src/api/qhseApi.js :: documentUniqueStatut -> /api/django/qhse/evaluations-risque/document-unique-statut
    chantier_id:inconnu, detail:texte, evaluation_id:inconnu, motif:inconnu, nb_validees:nombre, nb_validees_avec_lignes:nombre, reference:inconnu, valide:booleen
- frontend/src/api/qhseApi.js :: genererRevuesDues -> /api/django/qhse/veilles-reglementaires/generer-revues-dues
    generees:nombre, revues:inconnu
- frontend/src/api/qhseApi.js :: holdPoints -> /api/django/qhse/plans-chantier/<>/hold-points
    nb_bloquants:nombre, nb_hold_points:nombre, peut_avancer:booleen, phases_bloquees:inconnu, points_bloquants:inconnu
- frontend/src/api/qhseApi.js :: moyenne -> /api/django/qhse/retours-client/moyenne
    moyenne:inconnu, total:nombre
- frontend/src/api/qhseApi.js :: peutCloturer -> /api/django/qhse/notations-fin-chantier/peut-cloturer
    chantier_id:inconnu, detail:texte, peut_cloturer:inconnu
- frontend/src/api/qhseApi.js :: relancer -> /api/django/qhse/demandes-changement/relancer
    relances:nombre
- frontend/src/api/qhseApi.js :: suggestionAnalyse -> /api/django/qhse/ia/suggestion-analyse
    disponible:booleen, erreur:texte, suggestion:inconnu
- frontend/src/api/qhseApi.js :: suggestionClassification -> /api/django/qhse/ia/suggestion-classification
    disponible:booleen, erreur:texte, suggestion:inconnu
- frontend/src/api/recordsApi.js :: getMyActivities -> /api/django/records/activities/mine
    a_venir:liste, aujourdhui:liste, en_retard:liste
- frontend/src/api/recordsApi.js :: markActivityDone -> /api/django/records/activities/<>/done
    activity:inconnu, chained:inconnu, next:inconnu, suggestion:inconnu
- frontend/src/api/recordsApi.js :: snoozeApprobation -> /api/django/records/activities/snooze-approbation
    detail:texte, ok:booleen, snoozed_until:texte
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
- frontend/src/api/reportingApi.js :: savTicketsCoutMoyen -> /api/django/reporting/insights/sav-tickets-cout-moyen
    detail:texte, rows:inconnu
- frontend/src/api/reportingApi.js :: search -> /api/django/reporting/search
    detail:texte, groups:inconnu, query:inconnu
- frontend/src/api/reportingApi.js :: winLossBySource -> /api/django/reporting/commercial/win-loss-by-source
    by_canal:inconnu, by_source_technique:inconnu, detail:texte, summary:objet, top_loss_reasons:inconnu
- frontend/src/api/rhApi.js :: appliquerPeriodeFermeture -> /api/django/rh/periodes-fermeture/<>/appliquer
    appliquee:booleen, demandes_creees:nombre
- frontend/src/api/rhApi.js :: creerBesoinDepuisEcart -> /api/django/rh/employes/<>/ecart-competences-creer-besoin-formation
    detail:texte, id:inconnu, theme:inconnu
- frontend/src/api/rhApi.js :: definirCodePointage -> /api/django/rh/employes/<>/definir-code-pointage
    code:texte, detail:texte
- frontend/src/api/rhApi.js :: getIntegration -> /api/django/rh/employes/<>/integration
    faits:inconnu, lignes:inconnu, progression_pct:inconnu, total:inconnu
- frontend/src/api/rhApi.js :: parserCv -> /api/django/rh/candidatures/<>/parser-cv
    candidature:inconnu, champs_remplis:inconnu, detail:texte, tags_suggeres:inconnu
- frontend/src/api/rhApi.js :: repondrePulse -> /api/django/rh/campagnes-pulse/<>/repondre
    detail:texte
- frontend/src/api/rolesApi.js :: getPermissionCatalog -> /api/django/roles/permission-catalog
    permissions:inconnu, routes:inconnu
- frontend/src/api/rolesApi.js :: getPermissionsDisponibles -> /api/django/roles/permissions-disponibles
    permissions:inconnu
- frontend/src/api/savApi.js :: actionsGroupeesTickets -> /api/django/sav/tickets/actions-groupees
    echecs:inconnu, ids:texte, nb_echecs:nombre, nb_traites:nombre, operation:texte, priorite:texte, statut:texte, technicien:texte, traites:inconnu
- frontend/src/api/savApi.js :: creerDevisTicket -> /api/django/sav/tickets/<>/creer-devis
    detail:texte, devis_id:inconnu, devis_reference:inconnu
- frontend/src/api/savApi.js :: creerLeadDepuisTicket -> /api/django/sav/tickets/<>/creer-lead
    created:inconnu, lead_id:inconnu
- frontend/src/api/savApi.js :: facturerTicket -> /api/django/sav/tickets/<>/facturer
    couverture:inconnu, facture_id:inconnu, facture_reference:inconnu
- frontend/src/api/savApi.js :: genererFactureTicket -> /api/django/sav/tickets/<>/generer-facture
    detail:texte, facture_id:inconnu, facture_reference:inconnu, sous_garantie:inconnu
- frontend/src/api/savApi.js :: genererVisitesDues -> /api/django/sav/contrats-maintenance/generer-dus
    ok:booleen, tickets_generes:inconnu
- frontend/src/api/savApi.js :: getInstructionsSuggestions -> /api/django/sav/tickets/<>/instructions-suggestions
    results:inconnu
- frontend/src/api/savApi.js :: getPiecesCompatibles -> /api/django/sav/tickets/<>/pieces-compatibles
    results:inconnu
- frontend/src/api/savApi.js :: getSavFiabiliteParc -> /api/django/sav/insights/sav-fiabilite
    couts_inclus:inconnu, results:inconnu
- frontend/src/api/savApi.js :: getSavResumeParEquipe -> /api/django/sav/insights/sav-resume-equipe
    results:inconnu
- frontend/src/api/savApi.js :: getTicketsSimilaires -> /api/django/sav/tickets/<>/similaires
    results:inconnu
- frontend/src/api/savApi.js :: lienClientTicket -> /api/django/sav/tickets/<>/lien-client
    token:inconnu, url:inconnu
- frontend/src/api/savApi.js :: neplusSuivreTicket -> /api/django/sav/tickets/<>/suivre
    suivi:booleen
- frontend/src/api/savApi.js :: removeTicketPiece -> /api/django/sav/tickets/<>/pieces/<>
    detail:texte
- frontend/src/api/savApi.js :: suivreTicket -> /api/django/sav/tickets/<>/suivre
    suivi:booleen
- frontend/src/api/stockApi.js :: envoyerEmailBcf -> /api/django/stock/bons-commande-fournisseur/<>/envoyer-email
    detail:texte, email_statut:inconnu, log_id:inconnu, statut:inconnu
- frontend/src/api/stockApi.js :: exploserKit -> /api/django/stock/kits/<>/exploser
    detail:texte, kit_id:inconnu, kit_nom:inconnu, lignes:inconnu, quantite_kit:inconnu
- frontend/src/api/stockApi.js :: forceDeleteProduit -> /api/django/stock/produits/<>/force-delete
    bloquants:inconnu, detail:texte
- frontend/src/api/stockApi.js :: getComptesAPayer -> /api/django/stock/factures-fournisseur/comptes-a-payer
    results:inconnu, total_du:texte
- frontend/src/api/stockApi.js :: getFournisseur360 -> /api/django/stock/fournisseurs/<>/vue-360
    accords_prix:inconnu, accords_prix_actifs:nombre, bcf_en_retard:inconnu, bcf_ouverts:inconnu, conformite_documents_manquants:nombre, conformite_ok:booleen, factures_ouvertes:inconnu, fournisseur_id:inconnu, nb_retours_avoirs:inconnu, receptions_attendues:inconnu, score_performance:inconnu, solde_total_du:texte
- frontend/src/api/stockApi.js :: performanceFournisseur -> /api/django/stock/fournisseurs/<>/performance
    avg_lead_time_days:inconnu, fill_rate_pct:inconnu, fournisseur_id:inconnu, fournisseur_nom:inconnu, nb_bons:inconnu, nb_retours:inconnu, otd_a_lheure_pct:inconnu, otd_ecart_moyen_jours:inconnu, return_rate_pct:inconnu, total_achats_ht:texte
- frontend/src/api/stockApi.js :: produitPrevisionnel -> /api/django/stock/produits/<>/previsionnel
    disponible:inconnu, entrees_attendues:inconnu, produit_id:inconnu, solde_projete:inconnu, sorties_attendues:inconnu, timeline:inconnu
- frontend/src/api/stockApi.js :: resolveCode -> /api/django/stock/produits/resolve
    chantier:inconnu, client:inconnu, created:inconnu, date_fin_garantie:inconnu, date_peremption:inconnu, detail:texte, id:inconnu, label:inconnu, nb_tickets_ouverts:inconnu, numero_lot:inconnu, numero_serie:inconnu, quantite:inconnu, quantite_restante:inconnu, reference:inconnu, route:texte, serie:texte, sku:texte, statut:inconnu, type:texte
- frontend/src/api/stockApi.js :: scanGs1ReceptionFournisseur -> /api/django/stock/receptions-fournisseur/scan-gs1
    date_peremption:inconnu, detail:texte, numero_lot:inconnu, numeros_serie:inconnu, produit_id:inconnu, produit_nom:inconnu
- frontend/src/api/stockApi.js :: valorisation -> /api/django/stock/produits/valorisation
    lignes:inconnu, par_emplacement:liste, total:inconnu
- frontend/src/api/stockApi.js :: whatsappBcf -> /api/django/stock/bons-commande-fournisseur/<>/whatsapp
    detail:texte, message:inconnu, phone:inconnu, statut:inconnu, url:inconnu, wa_url:inconnu
- frontend/src/api/tiersApi.js :: doublons -> /api/django/tiers/tiers/doublons
    clusters:inconnu, count:nombre
- frontend/src/api/uxviewsApi.js :: importSavedViews -> /api/django/uxviews/saved-views/importer
    created:inconnu, erreurs:inconnu
- frontend/src/api/veilleAoApi.js :: ignorer -> /api/django/veille_ao/avis/<>/ignorer
    id:inconnu, regle_proposee:inconnu, statut:inconnu
- frontend/src/api/veilleAoApi.js :: retenir -> /api/django/veille_ao/avis/<>/retenir
    appel_offre_cree:inconnu, appel_offre_id:inconnu, id:inconnu, statut:inconnu
- frontend/src/api/ventesApi.js :: applyPreset -> /api/django/ventes/devis/<>/apply-preset
    detail:texte, lignes_created:nombre, skipped_priceless:nombre
- frontend/src/api/ventesApi.js :: approuverEtapeDevis -> /api/django/ventes/devis/<>/approuver-etape
    detail:texte, etape_id:inconnu, toutes_approuvees:inconnu
- frontend/src/api/ventesApi.js :: arrondiCaisseFacture -> /api/django/ventes/factures/<>/arrondi-caisse
    applicable:inconnu, ecart:texte, montant_arrondi:texte, montant_du:texte, pas:texte
- frontend/src/api/ventesApi.js :: bulkFactures -> /api/django/ventes/factures/bulk
    detail:texte
- frontend/src/api/ventesApi.js :: contacterSuperieur -> /api/django/ventes/devis/<>/contacter-superieur
    detail:texte, recipients:liste
- frontend/src/api/ventesApi.js :: dgiConformiteFacture -> /api/django/ventes/factures/<>/dgi-conformite
    conforme:booleen, detail:texte, problemes:inconnu
- frontend/src/api/ventesApi.js :: envoyerEmailDevis -> /api/django/ventes/devis/<>/envoyer-email
    detail:inconnu, devis_statut:inconnu, email_statut:inconnu, log_id:inconnu, proposal_path:inconnu, statut:texte
- frontend/src/api/ventesApi.js :: envoyerEmailFacture -> /api/django/ventes/factures/<>/envoyer-email
    detail:texte, email_log_id:inconnu, to_email:inconnu
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
- frontend/src/api/ventesApi.js :: getPrefillSite -> /api/django/ventes/devis/prefill-site
    client:inconnu, detail:texte, profil:inconnu
- frontend/src/api/ventesApi.js :: getSuiviPartageDevis -> /api/django/ventes/devis/<>/suivi-partage
    ouverture:inconnu, relances:inconnu
- frontend/src/api/ventesApi.js :: getVarianteConfig -> /api/django/ventes/devis/variante-config
    detail:texte, variante_pct:texte
- frontend/src/api/ventesApi.js :: lienPaiementFacture -> /api/django/ventes/factures/<>/lien-paiement
    detail:texte, expires_at:texte, montant:texte, pay_url:inconnu, provider:inconnu, statut:inconnu, token:inconnu
- frontend/src/api/ventesApi.js :: numerotationPreview -> /api/django/ventes/numerotation-preview
    detail:texte
- frontend/src/api/ventesApi.js :: rejeterEtapeDevis -> /api/django/ventes/devis/<>/rejeter-etape
    detail:texte, etape_id:inconnu
- frontend/src/api/ventesApi.js :: setVarianteConfig -> /api/django/ventes/devis/variante-config
    detail:texte, variante_pct:texte
- frontend/src/api/ventesApi.js :: shareLinkDevis -> /api/django/ventes/devis/<>/share-link
    path:texte, token:inconnu
- frontend/src/api/ventesApi.js :: superiorContactStatus -> /api/django/ventes/devis/<>/superior-contact-status
    requested:booleen, requested_at:inconnu, seen:booleen, seen_by:inconnu
- frontend/src/api/ventesApi.js :: whatsappDevis -> /api/django/ventes/devis/<>/whatsapp
    detail:texte, devis_statut:inconnu, message:inconnu, phone:inconnu, url:inconnu, wa_url:inconnu
- frontend/src/api/ventesApi.js :: whatsappFacture -> /api/django/ventes/factures/<>/whatsapp
    detail:texte, message:inconnu, phone:inconnu, url:inconnu, wa_url:inconnu
- frontend/src/api/ventesApi.js :: whatsappPreviewDevis -> /api/django/ventes/devis/<>/whatsapp-preview
    detail:texte, devis_statut:inconnu, message:inconnu, phone:inconnu, preview:booleen, url:inconnu, wa_url:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: dryRun -> /api/django/adsengine/regles/dry-run
    detail:texte, objets_touches:inconnu, resume_fr:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: engagementPresets -> /api/django/adsengine/audiences/engagement
    detail:texte, presets:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: fullBackfill -> /api/django/adsengine/campaigns/backfill-complet
    detail:texte, queued:booleen
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
- frontend/src/features/assurances/assurancesApi.js :: getTableauBord -> /api/django/assurances/tableau-bord
    attestations_expirant_30j:inconnu, montant_indemnise_12m:inconnu, montant_reclame_12m:inconnu, nb_polices_actives:inconnu, polices_actives_par_type:inconnu, polices_expirant_30j:inconnu, prime_annuelle_totale:inconnu, sinistres_clos:inconnu, sinistres_ouverts:inconnu, taux_sinistralite:nombre
- frontend/src/features/assurances/assurancesApi.js :: proposerEcritureIndemnisation -> /api/django/assurances/declarations-sinistre/<>/proposer-ecriture-indemnisation
    detail:inconnu, ecriture_id:inconnu, ecriture_statut:inconnu, indemnisation:inconnu
- frontend/src/features/assurances/assurancesApi.js :: proposerEcriturePrime -> /api/django/assurances/echeances-prime/<>/proposer-ecriture
    detail:inconnu, echeance:inconnu, ecriture_id:inconnu, ecriture_statut:inconnu
- frontend/src/features/entites/entitesApi.js :: noter -> /api/django/entites/entites/<>/noter
    ok:booleen
