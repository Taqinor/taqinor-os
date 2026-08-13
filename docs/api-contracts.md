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
- frontend/src/api/aiGovernanceApi.js :: rapportPeriode -> /api/django/ai/rapport-periode
    detail:texte, envoye:booleen, metriques:liste, module:inconnu, narratif:inconnu, periode:inconnu, source:inconnu
- frontend/src/api/aiGovernanceApi.js :: rediger -> /api/django/ai/rediger
    brouillon:inconnu, canal:inconnu, content_type:texte, detail:texte, entrees_fil:nombre, envoye:booleen, object_id:inconnu, source:inconnu
- frontend/src/api/aoApi.js :: additif -> /api/django/ao/pieces-consultation/<>/additif
    exigences_a_reverifier:inconnu
- frontend/src/api/aoApi.js :: comparer -> /api/django/ao/calepinage/variantes/comparer
    introuvables:inconnu, lignes:inconnu, reference_modules:inconnu
- frontend/src/api/aoApi.js :: completude -> /api/django/ao/dossiers-ao/<>/completude
    complet:inconnu, pieces_manquantes:liste, raisons_de_non_depot:inconnu, taux_completude:texte
- frontend/src/api/aoApi.js :: controles -> /api/django/ao/bordereaux-prix/<>/controles
    raisons:inconnu, remettable:booleen
- frontend/src/api/aoApi.js :: controlesAvantDepot -> /api/django/ao/dossiers-ao/<>/controles-avant-depot
    bloquant:inconnu, controles:liste, empreinte:inconnu, nombre_hors_controle:nombre, pieces_hors_controle:liste
- frontend/src/api/aoApi.js :: decomposition -> /api/django/ao/calepinage/variantes/<>/marches
    arrivee:inconnu, depart:inconnu, gain_total:inconnu, honnete:booleen, marches:liste, motifs:liste, recit:inconnu
- frontend/src/api/aoApi.js :: deverrouiller -> /api/django/ao/economie/<>/deverrouiller
    verrouillee:booleen
- frontend/src/api/aoApi.js :: initialiserChecklist -> /api/django/ao/dossiers-ao/<>/initialiser-checklist
    crees:inconnu, deja_presents:inconnu
- frontend/src/api/aoApi.js :: lancer -> /api/django/ao/calepinage/lancer
    id:inconnu, kind:inconnu, message_erreur:texte, progress_pct:inconnu, resultat:inconnu, statut:inconnu, variante:inconnu
- frontend/src/api/aoApi.js :: marches -> /api/django/ao/calepinage/variantes/<>/marches
    arrivee:inconnu, depart:inconnu, gain_total:inconnu, honnete:booleen, marches:liste, motifs:liste, recit:inconnu
- frontend/src/api/aoApi.js :: resultat -> /api/django/ao/calepinage/resultat/<>
    id:inconnu, kind:inconnu, message_erreur:inconnu, progress_pct:inconnu, resultat:inconnu, statut:inconnu, variante:inconnu
- frontend/src/api/aoApi.js :: stats -> /api/django/ao/resultats-ao/stats
    gagnes:inconnu, perdus:inconnu, taux_reussite_pct:inconnu, total_decides:inconnu, total_resultats:nombre
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
- frontend/src/api/btpChantierApi.js :: debourseVsFacture -> /api/django/btp-chantier/chantiers/<>/debourse-vs-facture
    avenants_approuves:inconnu, debourse_sec_total:inconnu, facture_total:inconnu, main_oeuvre:inconnu, marge:nombre, materiel:inconnu, situations_facturees:inconnu, sous_traitance:inconnu
- frontend/src/api/btpChantierApi.js :: faireApprouver -> /api/django/btp-chantier/avenants-chantier/<>/faire-approuver
    avenant:inconnu, detail:texte, lien_public:texte
- frontend/src/api/btpChantierApi.js :: lever -> /api/django/btp-chantier/reserves-chantier/<>/lever
    detail:texte, reserve:inconnu, signature:inconnu
- frontend/src/api/comptaApi.js :: accepterSuggestions -> /api/django/compta/rapprochements/<>/accepter-suggestions
    ignorees:inconnu, pointees:inconnu
- frontend/src/api/comptaApi.js :: annexes -> /api/django/compta/cycles-consolidation/<>/annexes
    cycle:inconnu, dettes_consolidees:inconnu, engagements_hors_bilan:nombre, immobilisations_consolidees:inconnu, perimetre:inconnu
- frontend/src/api/comptaApi.js :: appliquer -> /api/django/compta/modeles-rapprochement/<>/appliquer
    detail:inconnu, ecriture_id:inconnu, reference:inconnu
- frontend/src/api/comptaApi.js :: avancement -> /api/django/compta/contrats-avancement/<>/avancement
    constats:liste, contrat_id:inconnu, cout_total_estime:inconnu, dernier_pourcentage:inconnu, libelle:inconnu, marge_estimee:nombre, methode:inconnu, nb_constats:nombre, reference:inconnu, reste_a_reconnaitre:nombre, revenu_reconnu:inconnu, revenu_total:inconnu, statut:inconnu
- frontend/src/api/comptaApi.js :: collecter -> /api/django/compta/cycles-consolidation/<>/collecter
    cycle:inconnu, detail:inconnu, liasses:inconnu
- frontend/src/api/comptaApi.js :: controlesCollecte -> /api/django/compta/cycles-consolidation/<>/controles-collecte
    anomalies:inconnu, bloquant:inconnu
- frontend/src/api/comptaApi.js :: etatsConsolides -> /api/django/compta/cycles-consolidation/<>/etats-consolides
    bilan:inconnu, cpc:inconnu
- frontend/src/api/comptaApi.js :: etic -> /api/django/compta/etats/etic
    date_debut:texte, date_fin:texte, detail:texte, engagements_hors_bilan:objet, exercice:texte, immobilisations:inconnu, principes_methodes:texte, provisions:inconnu, resultat:inconnu, sections:liste
- frontend/src/api/comptaApi.js :: genererDues -> /api/django/compta/abonnements-ecriture/generer-dues
    detail:inconnu, generees:inconnu, ignorees:inconnu
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
    champs:objet, detail:texte, justificatif:texte
- frontend/src/api/comptaApi.js :: ocrImport -> /api/django/compta/rapprochements/<>/ocr-import
    concordant:booleen, detail:inconnu, ecart:inconnu, lignes:inconnu, lignes_creees:inconnu, releve:texte, solde_calcule:inconnu, solde_final_declare:inconnu, solde_initial:inconnu
- frontend/src/api/comptaApi.js :: positionTresorerie -> /api/django/compta/etats/position-tresorerie
    comptes:inconnu, projection:inconnu, total:inconnu
- frontend/src/api/comptaApi.js :: posterMouvement -> /api/django/compta/caisses/<>/poster-mouvement
    detail:inconnu, ecriture_id:inconnu, mouvement:inconnu
- frontend/src/api/comptaApi.js :: previsionnelTresorerie -> /api/django/compta/etats/previsionnel-tresorerie
    date_debut:inconnu, date_rupture_estimee:inconnu, nb_semaines:inconnu, semaines:inconnu, solde_initial:inconnu
- frontend/src/api/comptaApi.js :: refacturer -> /api/django/compta/notes-frais/refacturer
    detail:inconnu, facture_id:inconnu, refacture:booleen
- frontend/src/api/comptaApi.js :: releveFournisseur -> /api/django/compta/etats/releve-fournisseur/<>
    fournisseur:objet, lignes:inconnu, totaux:objet
- frontend/src/api/comptaApi.js :: reschedule -> /api/django/compta/calendrier-marketing/reschedule
    detail:texte, ok:booleen
- frontend/src/api/comptaApi.js :: simuler -> /api/django/compta/cycles-consolidation/<>/simuler
    cycle:inconnu, detail:inconnu, part_minoritaires:inconnu, perimetre:inconnu, resultat_consolide:inconnu, resultat_part_groupe:nombre, simulation:booleen
- frontend/src/api/comptaApi.js :: variationCapitaux -> /api/django/compta/cycles-consolidation/<>/variation-capitaux
    capitaux_cloture_part_groupe:inconnu, capitaux_ouverture:inconnu, cycle:inconnu, dividendes:inconnu, ecart_conversion:inconnu, resultat_part_groupe:inconnu, resultat_part_minoritaires:inconnu
- frontend/src/api/comptaApi.js :: verifier -> /api/django/compta/pistes-audit/verifier
    nb_maillons:nombre, rupture:inconnu, valide:booleen
- frontend/src/api/comptaApi.js :: verifierDisponible -> /api/django/compta/engagements/verifier-disponible
    budget:inconnu, controle:inconnu, detail:inconnu, disponible:inconnu, disponible_apres:inconnu, engage:inconnu, realise:inconnu, statut:inconnu
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
- frontend/src/api/contratsApi.js :: rendre -> /api/django/contrats/contrats/<>/rendre
    gabarit:inconnu, jetons:inconnu, rendu:inconnu
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
- frontend/src/api/cpqApi.js :: resultatConfigurateur -> /api/django/cpq/configurateur/<>/resultat
    actions_declenchees:inconnu, context:inconnu, detail:texte
- frontend/src/api/cpqApi.js :: validerCompatibilite -> /api/django/cpq/valider-compatibilite
    avertissements:inconnu, bloquantes:inconnu, detail:texte, valide:booleen, violations:inconnu
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
- frontend/src/api/crmApi.js :: scanCarteVisite -> /api/django/crm/leads/scan-carte
    detail:inconnu, doublons:inconnu, email:inconnu, nom:inconnu, prenom:inconnu, societe:inconnu, telephone:inconnu
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
    champs:objet, detail:texte, photo:texte
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
- frontend/src/api/flotteApi.js :: vehiculeAmortissement -> /api/django/flotte/vehicules/<>/amortissement
    amortissable:booleen, assujetti_plafond_cgi:inconnu, cumul_amortissements:inconnu, derniere_annee:inconnu, immobilisation_id:inconnu, part_non_deductible:inconnu, plafond_ttc:inconnu, valeur_nette_comptable:inconnu, valeur_origine:inconnu, vehicule_id:inconnu
- frontend/src/api/flotteApi.js :: vehiculeEcoConduite -> /api/django/flotte/vehicules/<>/eco-conduite
    co2_g_par_km:inconnu, co2_kg:inconnu, conso_kwh_100km:inconnu, conso_l_100km:inconnu, distance_totale_km:inconnu, energie:inconnu, facteur_co2_kg_par_litre:inconnu, kwh_total:nombre, litres_total:nombre, nb_pleins:inconnu, nb_surconsommation:inconnu, score_eco:inconnu, vehicule_id:inconnu
- frontend/src/api/flotteApi.js :: vehiculeTco -> /api/django/flotte/vehicules/<>/tco
    actif_flotte_id:inconnu, amortissement_cumule:inconnu, carburant:nombre, cout_par_km:inconnu, cout_total:nombre, distance_totale_km:inconnu, infractions:nombre, part_charges_non_deductibles:inconnu, pct_charges_non_deductibles:inconnu, pneus_pieces:nombre, reparations:nombre, sinistres:nombre, vehicule_id:inconnu
- frontend/src/api/flotteApi.js :: vehiculeTsav -> /api/django/flotte/vehicules/<>/tsav
    annee:inconnu, bareme_id:inconnu, energie:inconnu, exonere:booleen, montant:inconnu, note:texte, puissance_fiscale:inconnu
- frontend/src/api/fpaApi.js :: comparerScenarios -> /api/django/fpa/scenarios/comparer
    base:texte, detail:texte, scenarios:liste
- frontend/src/api/fpaApi.js :: consolidation -> /api/django/fpa/consolidation
    cycle_id:inconnu, depenses_par_categorie:inconnu, detail:texte, marge_brute_previsionnelle:texte, revenu_carnet:texte, revenu_pipeline:texte, revenu_previsionnel:texte, total_depenses:texte
- frontend/src/api/fpaApi.js :: sensibilite -> /api/django/fpa/scenarios/sensibilite
    detail:texte, points:inconnu, variable:inconnu
- frontend/src/api/gedApi.js :: comparerVersions -> /api/django/ged/documents/<>/comparer
    detail:texte, diff_texte:inconnu, message:texte, metadonnees:inconnu, texte_disponible:booleen
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
- frontend/src/api/gedApi.js :: purgerDocument -> /api/django/ged/documents/<>/purger
    detail:texte
- frontend/src/api/gedApi.js :: semanticSearch -> /api/django/ged/documents/semantique
    mode:texte, results:inconnu
- frontend/src/api/gedApi.js :: toggleFavoriDocument -> /api/django/ged/documents/<>/favori
    favori:booleen
- frontend/src/api/gestionProjetApi.js :: autoAffecter -> /api/django/gestion-projet/affectations/auto-affecter
    creations:inconnu, deplacements:inconnu, detail:texte, non_resolues:inconnu, simule:booleen
- frontend/src/api/gestionProjetApi.js :: copierSemaineAffectations -> /api/django/gestion-projet/affectations/copier-semaine
    copiees:inconnu, detail:texte, nb_copiees:nombre, nb_sautees:nombre, sautees:inconnu
- frontend/src/api/gestionProjetApi.js :: copierSemaineTimesheets -> /api/django/gestion-projet/timesheets/copier-semaine
    copiees:inconnu, detail:texte, nb_copiees:nombre, nb_sautees:nombre, sautees:inconnu
- frontend/src/api/gestionProjetApi.js :: genererPlanIa -> /api/django/gestion-projet/projets/<>/generer-plan-ia
    detail:texte, devis_id:texte, taches:inconnu
- frontend/src/api/gestionProjetApi.js :: getBudgetTotal -> /api/django/gestion-projet/budgets/<>/total
    nb_lignes:inconnu, par_categorie:inconnu, total:texte
- frontend/src/api/gestionProjetApi.js :: getBurndown -> /api/django/gestion-projet/projets/<>/burndown
    charge_totale:texte, detail:texte, points:liste
- frontend/src/api/gestionProjetApi.js :: getClassementTemps -> /api/django/gestion-projet/timesheets/classement
    debut:texte, detail:texte, fin:texte, lignes:inconnu
- frontend/src/api/gestionProjetApi.js :: getConflitsAffectation -> /api/django/gestion-projet/ressources/conflits-affectation
    debut:texte, detail:texte, fin:texte, lignes:inconnu, nb_conflits:inconnu, nb_ressources_en_conflit:nombre
- frontend/src/api/gestionProjetApi.js :: getGrilleSemaineTemps -> /api/django/gestion-projet/timesheets/semaine
    debut_semaine:inconnu, detail:texte, fin_semaine:inconnu, jours:inconnu, lignes:liste, suggestions:inconnu, total_par_jour:liste, total_semaine:texte
- frontend/src/api/gestionProjetApi.js :: getLienEvaluation -> /api/django/gestion-projet/projets/<>/lien-evaluation
    deja_soumis:booleen, projet_id:inconnu, token:inconnu
- frontend/src/api/gestionProjetApi.js :: getMatriceRisques -> /api/django/gestion-projet/projets/<>/matrice-risques
    grille:inconnu, top_risques:inconnu, total_ouverts_surveilles:nombre
- frontend/src/api/gestionProjetApi.js :: getNivellementCharge -> /api/django/gestion-projet/ressources/nivellement-charge
    debut:texte, detail:texte, fin:texte, heures_par_jour:inconnu, propositions:inconnu, sous_charges:inconnu, surcharges:inconnu, totaux:objet
- frontend/src/api/gestionProjetApi.js :: getPenalitesRetard -> /api/django/gestion-projet/projets/<>/penalites-retard
    applicable:booleen, decompte_definitif_a_etablir:booleen, exposition:inconnu, exposition_brute:inconnu, jours_depassement:inconnu, montant_marche:inconnu, plafond_montant:inconnu, plafond_penalite_pct:inconnu, plafonnee:inconnu, taux_penalite_retard:inconnu
- frontend/src/api/gestionProjetApi.js :: getPlanDeCharge -> /api/django/gestion-projet/ressources/plan-de-charge
    debut:texte, detail:texte, fin:texte, heures_par_jour:inconnu, lignes:inconnu, nb_surcharges:inconnu
- frontend/src/api/gestionProjetApi.js :: getPortefeuille -> /api/django/gestion-projet/projets/portefeuille
    nb_projets:inconnu, projets:liste, total_charge:texte, total_marge_reelle:texte, total_retards:inconnu, total_risques:inconnu
- frontend/src/api/gestionProjetApi.js :: getProjetAvancement -> /api/django/gestion-projet/projets/<>/avancement
    avancement_pct:nombre, charge_totale:inconnu, taches:inconnu
- frontend/src/api/gestionProjetApi.js :: getProjetCoutsEngagesReels -> /api/django/gestion-projet/projets/<>/couts-engages-reels
    budget_id:inconnu, budget_statut:inconnu, budget_version:inconnu, nb_liens_depense:inconnu, par_categorie:liste, total:objet
- frontend/src/api/gestionProjetApi.js :: getProjetGantt -> /api/django/gestion-projet/projets/<>/gantt
    date_origine:inconnu, duree_projet:inconnu, has_cycle:inconnu, liens:inconnu, taches:inconnu
- frontend/src/api/gestionProjetApi.js :: getProjetPnl -> /api/django/gestion-projet/projets/<>/pnl
    budget_id:inconnu, budget_version:inconnu, cout_budget:texte, cout_reel:texte, cout_reel_affectations:texte, cout_reel_timesheets:texte, couts_par_categorie:liste, marge_pct_reelle:inconnu, marge_prev:texte, marge_reelle:texte, note_revenu:inconnu, revenu:texte
- frontend/src/api/gestionProjetApi.js :: getRapprochementTemps -> /api/django/gestion-projet/timesheets/rapprochement
    debut:texte, detail:texte, ecarts:liste, fin:texte
- frontend/src/api/gestionProjetApi.js :: getTacheDependances -> /api/django/gestion-projet/taches/<>/dependances
    predecesseurs:inconnu, successeurs:inconnu
- frontend/src/api/gestionProjetApi.js :: getTempsManquants -> /api/django/gestion-projet/timesheets/manquants
    debut:texte, detail:texte, fin:texte, lignes:liste
- frontend/src/api/gestionProjetApi.js :: publierAffectations -> /api/django/gestion-projet/affectations/publier
    detail:texte, nb_deja_publiees:inconnu, nb_notifies:inconnu, nb_publiees:nombre
- frontend/src/api/gestionProjetApi.js :: versTicketSav -> /api/django/gestion-projet/taches/<>/vers-ticket-sav
    detail:texte, ticket_reference:inconnu, ticket_sav_id:inconnu
- frontend/src/api/hospitalityApi.js :: tableauBord -> /api/django/hospitality/tableau-bord
    adr:inconnu, detail:texte, no_show_count:inconnu, no_show_rate:inconnu, nuits_disponibles:inconnu, nuits_vendues:inconnu, revenus_chambres:inconnu, revpar:inconnu, taux_occupation:inconnu, total_reservations:inconnu
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
- frontend/src/api/immobilierApi.js :: consommation -> /api/django/immobilier/budgets-charges/<>/consommation
    budget_charges_id:inconnu, ecart:inconnu, ecart_pct:inconnu, montant_budgete_annuel:inconnu, total_reel:inconnu
- frontend/src/api/immobilierApi.js :: repartitionCharges -> /api/django/immobilier/batiments/<>/repartition-charges
    detail:texte, mode_repartition:inconnu, par_local:inconnu, total_depenses:inconnu
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
- frontend/src/api/innovationApi.js :: rapport -> /api/django/innovation/campagnes/<>/rapport
    nb_idees_proposees:inconnu, nb_utilisateurs_cibles:inconnu, taux_conversion:inconnu, top_idees:inconnu
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
- frontend/src/api/installationsApi.js :: deletePaiementSousTraitant -> /api/django/installations/paiements-sous-traitant/<>
    detail:texte
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
- frontend/src/api/installationsApi.js :: getCrewTime -> /api/django/installations/interventions/<>/crew-time
    arrivee_site_le:inconnu, depart_depot_le:inconnu, duree_sur_site_min:inconnu, labour_jours:inconnu, retour_depot_le:inconnu, trajet_aller_min:inconnu
- frontend/src/api/installationsApi.js :: getEtapesChantier -> /api/django/installations/chantiers/<>/etapes
    etape_courante:inconnu, etapes:inconnu, installation:inconnu, reference:inconnu
- frontend/src/api/installationsApi.js :: getFacturesSousTraitant -> /api/django/installations/factures-sous-traitant
    count:nombre, next:inconnu, previous:inconnu, results:inconnu
- frontend/src/api/installationsApi.js :: getLandedCostDossier -> /api/django/installations/dossiers-import/<>/landed-cost
    dossier_id:inconnu, lignes:inconnu, total_fob:nombre, total_frais:nombre, total_landed:nombre
- frontend/src/api/installationsApi.js :: getMaTournee -> /api/django/installations/interventions/ma-tournee
    date:inconnu, stops:inconnu
- frontend/src/api/installationsApi.js :: getPaiementsSousTraitant -> /api/django/installations/paiements-sous-traitant
    count:nombre, next:inconnu, previous:inconnu, results:inconnu
- frontend/src/api/installationsApi.js :: getPhotoQa -> /api/django/installations/interventions/<>/photo-qa
    actif:inconnu, signalements:inconnu
- frontend/src/api/installationsApi.js :: getPhotos -> /api/django/installations/interventions/<>/photos
    autres:inconnu, created_at:inconnu, filename:inconnu, groupes:inconnu, id:inconnu, intervention:inconnu, mime:inconnu, obligatoires_manquants:liste, sans_creneau:inconnu, uploaded_by_nom:inconnu, url:texte
- frontend/src/api/installationsApi.js :: getRegimeSuggestion -> /api/django/installations/chantiers/regime-suggestion
    code:inconnu, label:inconnu, seuil_anre_kwc:inconnu, seuil_declaration_kwc:inconnu
- frontend/src/api/installationsApi.js :: getTourneeLivraison -> /api/django/installations/tournee-livraison
    depart:texte, jour:texte, sans_gps:inconnu, total:inconnu, tournee:inconnu
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
- frontend/src/api/installationsApi.js :: syncField -> /api/django/installations/sync
    applied:inconnu, detail:texte, errors:inconnu, replayed:inconnu, results:inconnu
- frontend/src/api/kbApi.js :: assignationProgression -> /api/django/kb/parcours-assignations/<>/progression
    articles:inconnu, complet:booleen, nombre_lus:inconnu, nombre_total:inconnu, parcours:inconnu, utilisateur:inconnu
- frontend/src/api/kbApi.js :: descendantsCount -> /api/django/kb/articles/<>/descendants-count
    nb_descendants:nombre
- frontend/src/api/kbApi.js :: marquerLu -> /api/django/kb/articles/<>/marquer-lu
    lecteurs:inconnu, nombre:nombre
- frontend/src/api/kbApi.js :: resumeLecture -> /api/django/kb/articles/<>/resume-lecture
    lecteurs:inconnu, nombre:nombre
- frontend/src/api/kbApi.js :: togglerFavori -> /api/django/kb/articles/<>/toggler-favori
    favori:inconnu
- frontend/src/api/litigesApi.js :: analyseConcurrents -> /api/django/litiges/reclamations/analyse-concurrents
    par_concurrent:inconnu, par_motif:inconnu, total_litiges_avec_concurrent:inconnu
- frontend/src/api/marketingApi.js :: apercuFusion -> /api/django/marketing/campagnes/<>/apercu_fusion
    corps_fusionne:inconnu, detail:texte
- frontend/src/api/marketingApi.js :: cloturerPresences -> /api/django/marketing/evenements-marketing/<>/cloturer-presences
    absents_marques:inconnu
- frontend/src/api/marketingApi.js :: enregistrementsAttendus -> /api/django/marketing/domaines-envoi/<>/enregistrements-attendus
    dkim:objet, dmarc:objet, spf:objet
- frontend/src/api/marketingApi.js :: envoyerTest -> /api/django/marketing/campagnes/<>/envoyer-test
    corps_fusionne:inconnu, seeds:liste
- frontend/src/api/marketingApi.js :: genererIa -> /api/django/marketing/campagnes/generer-ia
    configured:inconnu, corps:inconnu, langue:inconnu, objet:inconnu, ok:inconnu, source:inconnu
- frontend/src/api/marketingApi.js :: genererIaDisponible -> /api/django/marketing/campagnes/generer-ia-disponible
    configured:inconnu
- frontend/src/api/marketingApi.js :: importer -> /api/django/marketing/listes-diffusion/<>/importer
    ajoutes:nombre, doublons:nombre, ignores_supprimes:nombre
- frontend/src/api/marketingApi.js :: participants -> /api/django/marketing/sequences-relance/<>/participants
    nb_actifs:inconnu, participants:inconnu
- frontend/src/api/marketingApi.js :: planifier -> /api/django/marketing/sequences-relance/<>/planifier
    etapes:inconnu
- frontend/src/api/marketingApi.js :: precheck -> /api/django/marketing/campagnes/<>/precheck
    avertissements:inconnu, bloque:inconnu
- frontend/src/api/marketingApi.js :: previsualiser -> /api/django/marketing/segments-marketing/<>/previsualiser
    count:nombre, detail:texte, echantillon:inconnu
- frontend/src/api/marketingApi.js :: roi -> /api/django/marketing/campagnes/<>/roi
    budget_mad:inconnu, cout_mad:texte, cout_par_lead_mad:inconnu, nb_leads:inconnu, nb_signes:inconnu, revenu_ttc_mad:texte, roi_pct:inconnu
- frontend/src/api/marketingApi.js :: score -> /api/django/marketing/enquetes-nps/score
    detracteurs:inconnu, nps:inconnu, passifs:inconnu, promoteurs:inconnu, total:inconnu
- frontend/src/api/marketingApi.js :: tester -> /api/django/marketing/enquetes/<>/tester
    barre_progression:inconnu, bouton_retour:inconnu, description_accueil:inconnu, limite_temps_minutes:inconnu, message_fin:inconnu, mode_pagination:inconnu, questions:inconnu, titre:inconnu
- frontend/src/api/messagesApi.js :: close -> /api/django/chat/messages/<>/poll-close
    allow_multiple:inconnu, closed_at:inconnu, detail:texte, is_anonymous:inconnu, my_vote_option_ids:liste, options:liste, poll_id:inconnu, question:inconnu
- frontend/src/api/messagesApi.js :: deleteMessage -> /api/django/chat/messages/<>
    detail:texte
- frontend/src/api/messagesApi.js :: follow -> /api/django/chat/messages/<>/thread-follow
    status:texte
- frontend/src/api/messagesApi.js :: remove -> /api/django/chat/canned-responses/<>
    detail:texte
- frontend/src/api/messagesApi.js :: removeMember -> /api/django/chat/conversations/<>/members/<>
    detail:texte
- frontend/src/api/messagesApi.js :: results -> /api/django/chat/messages/<>/poll-results
    allow_multiple:inconnu, closed_at:inconnu, detail:texte, is_anonymous:inconnu, my_vote_option_ids:liste, options:liste, poll_id:inconnu, question:inconnu
- frontend/src/api/messagesApi.js :: toggleBookmark -> /api/django/chat/messages/<>/bookmark
    status:inconnu
- frontend/src/api/messagesApi.js :: toggleReaction -> /api/django/chat/messages/<>/react
    detail:texte, message:inconnu, status:inconnu
- frontend/src/api/messagesApi.js :: transcrire -> /api/django/chat/transcrire
    detail:texte, enabled:booleen, langue:texte, texte:inconnu
- frontend/src/api/messagesApi.js :: unfollow -> /api/django/chat/messages/<>/thread-unfollow
    status:texte
- frontend/src/api/messagesApi.js :: unreadCount -> /api/django/chat/conversations/unread
    per_conversation:inconnu, total:inconnu
- frontend/src/api/messagesApi.js :: vote -> /api/django/chat/messages/<>/poll-vote
    allow_multiple:inconnu, closed_at:inconnu, detail:texte, is_anonymous:inconnu, my_vote_option_ids:liste, options:liste, poll_id:inconnu, question:inconnu
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
- frontend/src/api/monitoringApi.js :: getWarrantyCurve -> /api/django/monitoring/warranties/<>/curve
    has_warranty:booleen, installation:inconnu, manufacturer_recourse:inconnu, points:inconnu, threshold_pct:inconnu
- frontend/src/api/monitoringApi.js :: getWarrantyStatus -> /api/django/monitoring/warranties/<>/status
    actual_kwh:inconnu, compensation_mad:inconnu, guaranteed_kwh:inconnu, has_warranty:booleen, shortfall_kwh:inconnu, within_tolerance:inconnu, year:inconnu
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
- frontend/src/api/paieApi.js :: affebdsRapprochement -> /api/django/paie/periodes/affebds-rapprochement
    en_trop:inconnu, manquants:inconnu, rapproches:inconnu
- frontend/src/api/paieApi.js :: apercuBulletin -> /api/django/paie/periodes/<>/bulletin
    allocations_familiales:inconnu, amo_patronale:inconnu, amo_salariale:inconnu, brut:inconnu, brut_imposable:inconnu, charges_patronales:inconnu, cimr_salariale:inconnu, cnss_patronale:inconnu, cnss_salariale:inconnu, detail:texte, formation_professionnelle:inconnu, frais_professionnels:inconnu, ir:inconnu, lignes:inconnu, montant_exonere_regime:inconnu, mutuelle_patronale:inconnu, mutuelle_salariale:inconnu, net_a_payer:inconnu, net_avant_saisie:inconnu, net_imposable:inconnu, prime_anciennete:inconnu, provision_conges:inconnu, retenues:inconnu
- frontend/src/api/paieApi.js :: appliquerStructure -> /api/django/paie/structures/<>/appliquer
    detail:texte, rattachees:inconnu
- frontend/src/api/paieApi.js :: declarationCimr -> /api/django/paie/periodes/<>/declaration-cimr
    annee:inconnu, lignes:inconnu, mois:inconnu, nombre_affilies:nombre, total_base:inconnu, total_cimr_salariale:inconnu
- frontend/src/api/paieApi.js :: deposerBds -> /api/django/paie/periodes/<>/deposer-bds
    date_depot:inconnu, id:inconnu, profils_couverts:inconnu, type_depot:inconnu
- frontend/src/api/paieApi.js :: deposerBdsComplementaire -> /api/django/paie/periodes/<>/deposer-bds-complementaire
    date_depot:inconnu, depot_principal:inconnu, detail:texte, id:inconnu, profils_couverts:inconnu, type_depot:inconnu
- frontend/src/api/paieApi.js :: ensureStructuresStandard -> /api/django/paie/structures/ensure-standard
    structures:inconnu
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
- frontend/src/api/paieApi.js :: repriseCommit -> /api/django/paie/cumuls-annuels/reprise-commit
    completes:inconnu, crees:inconnu, detail:texte, ignores:inconnu
- frontend/src/api/paieApi.js :: repriseDryRun -> /api/django/paie/cumuls-annuels/reprise-dry-run
    apercu:inconnu, colonnes:inconnu, detail:texte, mapping:inconnu, matricules_inconnus:inconnu, non_mappees:inconnu, total_lignes:nombre
- frontend/src/api/paieApi.js :: runGratification -> /api/django/paie/periodes/<>/run-gratification
    bulletins:liste, detail:texte, nombre:nombre
- frontend/src/api/paieApi.js :: seedParametresDefaults -> /api/django/paie/parametres/seed-defaults
    bareme:nombre, parametre:nombre, tranches:nombre
- frontend/src/api/paieApi.js :: seedRubriquesDefaults -> /api/django/paie/rubriques/seed-defaults
    rubriques:inconnu
- frontend/src/api/paieApi.js :: seedRubriquesStandard -> /api/django/paie/rubriques/seed-standard
    rubriques:inconnu
- frontend/src/api/paieApi.js :: simulationBulletin -> /api/django/paie/profils/<>/simulation
    amo_salariale:inconnu, brut:inconnu, cimr_salariale:inconnu, cnss_salariale:inconnu, detail:texte, frais_professionnels:inconnu, ir:inconnu, net_a_payer:inconnu, net_imposable:inconnu, prime:inconnu, salaire_simule:inconnu
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
- frontend/src/api/posApi.js :: getDashboard -> /api/django/pos/ventes/dashboard
    nb_ventes:inconnu, panier_moyen:texte, par_caissier:inconnu, par_categorie:inconnu, par_jour:inconnu, par_mode_paiement:inconnu, par_produit:inconnu, par_session:inconnu, taux_retour_pct:texte, total_ttc:texte
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
    detail:texte, devis_id:inconnu, devis_reference:inconnu, lead_id:inconnu, mode:inconnu
- frontend/src/api/publicapiApi.js :: sandboxTry -> /api/django/publicapi/sandbox/try
    detail:texte, resource:inconnu, results:inconnu, sandbox:booleen
- frontend/src/api/qhseApi.js :: calendrier -> /api/django/qhse/calendrier
    declarations_cnss:inconnu, evenements:inconnu, inspections:inconnu, permis:inconnu, today:texte, total:nombre, within_days:inconnu
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
- frontend/src/api/qhseApi.js :: iso9001Readiness -> /api/django/qhse/iso9001-readiness
    criteres:inconnu, nb_criteres:nombre, nb_criteres_sans_donnee:nombre, niveau:inconnu, score_global:inconnu
- frontend/src/api/qhseApi.js :: moyenne -> /api/django/qhse/retours-client/moyenne
    moyenne:inconnu, total:nombre
- frontend/src/api/qhseApi.js :: paretoDefauts -> /api/django/qhse/pareto-defauts
    pareto:inconnu, premier_passage:objet
- frontend/src/api/qhseApi.js :: peutCloturer -> /api/django/qhse/notations-fin-chantier/peut-cloturer
    chantier_id:inconnu, detail:texte, peut_cloturer:inconnu
- frontend/src/api/qhseApi.js :: relancer -> /api/django/qhse/demandes-changement/relancer
    relances:nombre
- frontend/src/api/qhseApi.js :: relancerNotifications -> /api/django/qhse/incidents/relancer-notifications
    relances:nombre
- frontend/src/api/qhseApi.js :: relancerRetards -> /api/django/qhse/capa/relancer-retards
    items:inconnu, notifiees:inconnu, sans_responsable:inconnu, total:nombre
- frontend/src/api/qhseApi.js :: statistiquesTfTg -> /api/django/qhse/incidents/statistiques-tf-tg
    accidents_avec_arret:inconnu, heures_travaillees:texte, jours_perdus:inconnu, periode:objet, tf:inconnu, tg:inconnu
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
- frontend/src/api/rhApi.js :: appliquerPeriodeFermeture -> /api/django/rh/periodes-fermeture/<>/appliquer
    appliquee:booleen, demandes_creees:nombre
- frontend/src/api/rhApi.js :: creerBesoinDepuisEcart -> /api/django/rh/employes/<>/ecart-competences-creer-besoin-formation
    detail:texte, id:inconnu, theme:inconnu
- frontend/src/api/rhApi.js :: definirCodePointage -> /api/django/rh/employes/<>/definir-code-pointage
    code:texte, detail:texte
- frontend/src/api/rhApi.js :: getCockpit -> /api/django/rh/cockpit
    alertes:inconnu, effectif_total:inconnu, masse_salariale_mensuelle:inconnu, par_contrat:inconnu, par_departement:inconnu, par_statut:inconnu, pyramide_anciennete:inconnu, turnover:objet
- frontend/src/api/rhApi.js :: getIntegration -> /api/django/rh/employes/<>/integration
    faits:inconnu, lignes:inconnu, progression_pct:inconnu, total:inconnu
- frontend/src/api/rhApi.js :: getRapportConges -> /api/django/rh/demandes-conge/rapport
    par_employe:inconnu, par_type:inconnu
- frontend/src/api/rhApi.js :: getRapportPresence -> /api/django/rh/pointages/rapport
    detail:texte, par_employe:inconnu, totaux_departement:inconnu
- frontend/src/api/rhApi.js :: getRecrutementStatistiques -> /api/django/rh/recrutement/statistiques
    candidatures_par_ouverture:inconnu, delai_embauche_moyen_jours:inconnu, entonnoir:inconnu, sources:inconnu
- frontend/src/api/rhApi.js :: getRegistreFormation -> /api/django/rh/employes/<>/registre-formation
    employe:inconnu, lignes:inconnu, total:nombre, total_realisees:inconnu
- frontend/src/api/rhApi.js :: getResultatsPulse -> /api/django/rh/campagnes-pulse/<>/resultats
    masque:booleen, nb_reponses:inconnu, score_enps:inconnu
- frontend/src/api/rhApi.js :: getRisqueAttrition -> /api/django/rh/employes/<>/risque-attrition
    band:inconnu, employe_id:inconnu, factors:inconnu, score:inconnu
- frontend/src/api/rhApi.js :: getSyntheseFeedback360 -> /api/django/rh/retours-feedback360/synthese
    anonymise:inconnu, detail:texte, moyennes_par_critere:inconnu, nb_invites:nombre, nb_soumis:inconnu, retours:liste
- frontend/src/api/rhApi.js :: getTableauBordHse -> /api/django/rh/tableau-bord-hse
    accidents_avec_arret:inconnu, accidents_total:inconnu, alertes:objet, heures_travaillees:nombre, incidents_par_chantier:inconnu, jours_arret_total:nombre, periode_jours:inconnu, presqu_accidents_total:inconnu, taux_frequence:inconnu, taux_gravite:inconnu
- frontend/src/api/rhApi.js :: importPointageCsv -> /api/django/rh/pointages/importer
    crees:inconnu, detail:texte, doublons:inconnu, erreurs:inconnu
- frontend/src/api/rhApi.js :: kiosquePointer -> /api/django/rh/pointages/kiosque
    detail:texte, heure:inconnu, nom:inconnu, sens:inconnu
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
- frontend/src/api/savApi.js :: getEquipementPartageQr -> /api/django/sav/equipements/<>/partage-qr
    qr:inconnu, url:inconnu
- frontend/src/api/savApi.js :: getInstructionsSuggestions -> /api/django/sav/tickets/<>/instructions-suggestions
    results:inconnu
- frontend/src/api/savApi.js :: getPiecesCompatibles -> /api/django/sav/tickets/<>/pieces-compatibles
    results:inconnu
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
- frontend/src/api/savApi.js :: neplusSuivreTicket -> /api/django/sav/tickets/<>/suivre
    suivi:booleen
- frontend/src/api/savApi.js :: removeTicketPiece -> /api/django/sav/tickets/<>/pieces/<>
    detail:texte
- frontend/src/api/savApi.js :: suivreTicket -> /api/django/sav/tickets/<>/suivre
    suivi:booleen
- frontend/src/api/stockApi.js :: bulkProduits -> /api/django/stock/produits/bulk
    detail:texte, ok:booleen, skipped:inconnu, total:nombre, updated:inconnu
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
- frontend/src/api/stockApi.js :: getKitDisponibilite -> /api/django/stock/kits/<>/disponibilite
    composants:inconnu, detail:texte, goulots:inconnu, kit_id:inconnu, kit_nom:inconnu, kits_assemblables:inconnu
- frontend/src/api/stockApi.js :: inventaire -> /api/django/stock/produits/inventaire
    ajustes:nombre, detail:texte, inchanges:nombre, mouvements:liste
- frontend/src/api/stockApi.js :: performanceFournisseur -> /api/django/stock/fournisseurs/<>/performance
    avg_lead_time_days:inconnu, fill_rate_pct:inconnu, fournisseur_id:inconnu, fournisseur_nom:inconnu, nb_bons:inconnu, nb_retours:inconnu, otd_a_lheure_pct:inconnu, otd_ecart_moyen_jours:inconnu, return_rate_pct:inconnu, total_achats_ht:texte
- frontend/src/api/stockApi.js :: produitPrevisionnel -> /api/django/stock/produits/<>/previsionnel
    disponible:inconnu, entrees_attendues:inconnu, produit_id:inconnu, solde_projete:inconnu, sorties_attendues:inconnu, timeline:inconnu
- frontend/src/api/stockApi.js :: resolveCode -> /api/django/stock/produits/resolve
    chantier:inconnu, client:inconnu, created:inconnu, date_fin_garantie:inconnu, date_peremption:inconnu, detail:texte, gs1:inconnu, id:inconnu, label:inconnu, nb_tickets_ouverts:inconnu, numero_lot:inconnu, numero_serie:inconnu, quantite:inconnu, quantite_restante:inconnu, reference:inconnu, route:texte, serie:texte, sku:texte, statut:inconnu, type:texte
- frontend/src/api/stockApi.js :: scanGs1ReceptionFournisseur -> /api/django/stock/receptions-fournisseur/scan-gs1
    date_peremption:inconnu, detail:texte, numero_lot:inconnu, numeros_serie:inconnu, produit_id:inconnu, produit_nom:inconnu
- frontend/src/api/stockApi.js :: validerInventaireSession -> /api/django/stock/inventaire-sessions/<>/valider
    ajustes:inconnu, detail:texte, inchanges:inconnu
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
- frontend/src/api/ventesApi.js :: contacterSuperieur -> /api/django/ventes/devis/<>/contacter-superieur
    detail:texte, recipients:liste
- frontend/src/api/ventesApi.js :: deletePreset -> /api/django/ventes/presets/<>
    detail:texte
- frontend/src/api/ventesApi.js :: dgiConformiteFacture -> /api/django/ventes/factures/<>/dgi-conformite
    conforme:booleen, detail:texte, problemes:inconnu
- frontend/src/api/ventesApi.js :: envoyerEmailDevis -> /api/django/ventes/devis/<>/envoyer-email
    detail:inconnu, devis_statut:inconnu, email_statut:inconnu, log_id:inconnu, proposal_path:inconnu, statut:texte
- frontend/src/api/ventesApi.js :: envoyerEmailFacture -> /api/django/ventes/factures/<>/envoyer-email
    detail:texte, email_log_id:inconnu, to_email:inconnu
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
- frontend/src/api/ventesApi.js :: getPrefillSite -> /api/django/ventes/devis/prefill-site
    client:inconnu, detail:texte, profil:inconnu
- frontend/src/api/ventesApi.js :: getSuiviPartageDevis -> /api/django/ventes/devis/<>/suivi-partage
    ouverture:inconnu, relances:inconnu
- frontend/src/api/ventesApi.js :: getVarianteConfig -> /api/django/ventes/devis/variante-config
    detail:texte, variante_pct:texte
- frontend/src/api/ventesApi.js :: lienPaiementFacture -> /api/django/ventes/factures/<>/lien-paiement
    detail:texte, expires_at:texte, montant:texte, pay_url:inconnu, provider:inconnu, statut:inconnu, token:inconnu
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
- frontend/src/features/adminops/adminopsApi.js :: appliquerPackage -> /api/django/adminops/config-packages/appliquer
    custom_fields:inconnu, detail:texte, message_templates:inconnu, roles_custom:inconnu
- frontend/src/features/adminops/adminopsApi.js :: previsualiserPackage -> /api/django/adminops/config-packages/previsualiser
    custom_fields:inconnu, detail:texte, message_templates:inconnu, roles_custom:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: createEngagement -> /api/django/adsengine/audiences/engagement
    audience_id:texte, detail:texte, error:inconnu, preset:inconnu, retention_days:inconnu
- frontend/src/features/adsengine/adsengineApi.js :: deliveryEstimate -> /api/django/adsengine/audiences/delivery-estimate
    detail:texte, error:inconnu, estimate:inconnu
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
- frontend/src/features/assurances/assurancesApi.js :: getCouvertureActif -> /api/django/assurances/couverture-actif
    detail:texte, polices_entreprise:inconnu, polices_flotte:inconnu
- frontend/src/features/assurances/assurancesApi.js :: getTableauBord -> /api/django/assurances/tableau-bord
    attestations_expirant_30j:inconnu, montant_indemnise_12m:inconnu, montant_reclame_12m:inconnu, nb_polices_actives:inconnu, polices_actives_par_type:inconnu, polices_expirant_30j:inconnu, prime_annuelle_totale:inconnu, sinistres_clos:inconnu, sinistres_ouverts:inconnu, taux_sinistralite:nombre
- frontend/src/features/assurances/assurancesApi.js :: proposerEcritureIndemnisation -> /api/django/assurances/declarations-sinistre/<>/proposer-ecriture-indemnisation
    detail:inconnu, ecriture_id:inconnu, ecriture_statut:inconnu, indemnisation:inconnu
- frontend/src/features/assurances/assurancesApi.js :: proposerEcriturePrime -> /api/django/assurances/echeances-prime/<>/proposer-ecriture
    detail:inconnu, echeance:inconnu, ecriture_id:inconnu, ecriture_statut:inconnu
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
- frontend/src/api/aoApi.js :: creer -> /api/django/ao/economie  [EconomieAOSerializer]
    champs: appel_offre, appel_offre_reference, benefice_net_cible_ht, cibles, controle_tresorerie, cout_regime_reduit_ht, cout_regime_standard_ht, cout_revient_ht, created_at, ecart_tresorerie, id, lignes, marge_pct, note_comptable, sous_seuil_psychologique, taux_tva_achat_reduit, taux_tva_achat_standard, taux_tva_vente, total_ht, total_ttc, tva_collectee, tva_deductible, tva_nette_a_reverser, updated_at, verrouillee
- frontend/src/api/aoApi.js :: get -> /api/django/ao/economie/<>  [EconomieAOSerializer]
    champs: appel_offre, appel_offre_reference, benefice_net_cible_ht, cibles, controle_tresorerie, cout_regime_reduit_ht, cout_regime_standard_ht, cout_revient_ht, created_at, ecart_tresorerie, id, lignes, marge_pct, note_comptable, sous_seuil_psychologique, taux_tva_achat_reduit, taux_tva_achat_standard, taux_tva_vente, total_ht, total_ttc, tva_collectee, tva_deductible, tva_nette_a_reverser, updated_at, verrouillee
- frontend/src/api/aoApi.js :: parAffaire -> /api/django/ao/economie  [EconomieAOSerializer]
    champs: appel_offre, appel_offre_reference, benefice_net_cible_ht, cibles, controle_tresorerie, cout_regime_reduit_ht, cout_regime_standard_ht, cout_revient_ht, created_at, ecart_tresorerie, id, lignes, marge_pct, note_comptable, sous_seuil_psychologique, taux_tva_achat_reduit, taux_tva_achat_standard, taux_tva_vente, total_ht, total_ttc, tva_collectee, tva_deductible, tva_nette_a_reverser, updated_at, verrouillee
- frontend/src/api/aoApi.js :: update -> /api/django/ao/economie/<>  [EconomieAOSerializer]
    champs: appel_offre, appel_offre_reference, benefice_net_cible_ht, cibles, controle_tresorerie, cout_regime_reduit_ht, cout_regime_standard_ht, cout_revient_ht, created_at, ecart_tresorerie, id, lignes, marge_pct, note_comptable, sous_seuil_psychologique, taux_tva_achat_reduit, taux_tva_achat_standard, taux_tva_vente, total_ht, total_ttc, tva_collectee, tva_deductible, tva_nette_a_reverser, updated_at, verrouillee
- frontend/src/api/auditApi.js :: getEntries -> /api/django/audit/entries  [AuditLogSerializer]
    champs: action, action_label, actor_username, detail, id, model, module, object_id, object_repr, timestamp, timestamp_local, utilisateur
    action ∈ {accept, create, delete, email, export, login, login_failed, logout, notify, pdf, refuse, security_alert, status, switch_company, update, whatsapp}
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
    action_type ∈ {assign_record, create_activity, create_custom_record, create_sav_ticket, for_each, send_email, send_sms, send_whatsapp, set_field, wait}
    trigger_type ∈ {chantier_status, date_echeance_champ, devis_accepted, facture_overdue, lead_stage_change, maintenance_due, projet_phase_change, projet_status_change, record_state_change, stock_below_threshold, warranty_expiring, webhook_inbound}
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
    action_type ∈ {assign_record, create_activity, create_custom_record, create_sav_ticket, for_each, send_email, send_sms, send_whatsapp, set_field, wait}
    trigger_type ∈ {chantier_status, date_echeance_champ, devis_accepted, facture_overdue, lead_stage_change, maintenance_due, projet_phase_change, projet_status_change, record_state_change, stock_below_threshold, warranty_expiring, webhook_inbound}
- frontend/src/api/automationApi.js :: getRuns -> /api/django/automation/runs  [AutomationRunSerializer]
    champs: id, message, rule, rule_nom, status, status_display, target_id, target_model, timestamp
    status ∈ {failed, noop, pending_approval, simulation, skipped, success}
- frontend/src/api/btpChantierApi.js :: get -> /api/django/btp-chantier/reserves-chantier/<>  [ReserveChantierSerializer]
    champs: chantier, created_at, created_by, date_levee, date_limite, description, gravite, historique, id, leve_par, localisation_plan, lot, motif_contestation, responsable_leve, statut, updated_at
    gravite ∈ {bloquante, majeure, mineure}
    statut ∈ {contestee, en_cours, levee, ouverte}
- frontend/src/api/comptaApi.js :: list -> /api/django/compta/pistes-audit  [PisteAuditComptableSerializer]
    champs: date_creation, ecriture, ecriture_reference, empreinte_contenu, hash, hash_precedent, id, sequence
- frontend/src/api/contratsApi.js :: createAlerte -> /api/django/contrats/alertes  [AlerteContratSerializer]
    champs: contrat, cree_par, date_creation, date_declenchement, date_envoi, id, message, statut, statut_display, type_alerte, type_alerte_display
    statut ∈ {annulee, envoyee, planifiee}
    type_alerte ∈ {echeance, personnalise, preavis}
- frontend/src/api/contratsApi.js :: createCaution -> /api/django/contrats/cautions  [CautionSerializer]
    champs: contrat, date_creation, date_emission, date_expiration, devise, garant, id, montant, note, reference, statut, statut_display, type_caution, type_caution_display
    statut ∈ {active, annulee, appelee, expiree, mainlevee}
    type_caution ∈ {autre, bonne_execution, restitution_acompte, retenue_garantie, societe_mere, soumission}
- frontend/src/api/contratsApi.js :: createClause -> /api/django/contrats/clauses  [ClauseSerializer]
    champs: actif, categorie, corps, corps_localise, date_creation, id, ordre, titre, titre_localise, type_clause, type_clause_display
    type_clause ∈ {autre, confidentialite, financiere, garantie, generale, juridique, resiliation, technique}
- frontend/src/api/contratsApi.js :: createClauseContrat -> /api/django/contrats/clauses-contrat  [ClauseContratSerializer]
    champs: clause, clause_titre, contrat, corps, date_creation, id, ordre, surchargee, titre
- frontend/src/api/contratsApi.js :: createContrat -> /api/django/contrats/contrats  [ContratSerializer]
    champs: client_id, client_nom, confidentialite, confidentialite_display, created_by, custom_data, date_creation, date_debut, date_dernier_renouvellement, date_fin, devise, duree_reconduction_mois, echeance_preavis, id, jours_avant_echeance, jours_avant_preavis, modele, montant, nb_renouvellements, objet, plan_abonnement, plan_recurrent, preavis_jours, preavis_traite, reference, responsable, responsable_nom, sav_contrat_maintenance_id, sequence_dunning, statut, statut_display, tacite_reconduction, type_contrat, type_contrat_display
    confidentialite ∈ {confidentiel, interne, public}
    statut ∈ {actif, brouillon, en_approbation, expire, resilie, signe, suspendu}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: createContratLien -> /api/django/contrats/contrat-liens  [ContratLienSerializer]
    champs: cible_id, contrat, date_creation, id, libelle, type_cible, type_cible_display
    type_cible ∈ {devis, installation, lead, maintenance}
- frontend/src/api/contratsApi.js :: createEcheancier -> /api/django/contrats/echeanciers  [EcheancierContratSerializer]
    champs: contrat, date_creation, devise, facturation_active, id, libelle, lignes, montant_total, periodicite, periodicite_display, statut, statut_display
    periodicite ∈ {annuelle, mensuelle, personnalisee, semestrielle, trimestrielle, unique}
    statut ∈ {actif, annule, brouillon, solde}
- frontend/src/api/contratsApi.js :: createIndexation -> /api/django/contrats/indexations  [IndexationPrixSerializer]
    champs: actif, contrat, date_creation, date_derniere_revision, id, indice, libelle, part_fixe, periodicite, periodicite_display, valeur_base
    periodicite ∈ {a_la_demande, annuelle, semestrielle, trimestrielle}
- frontend/src/api/contratsApi.js :: createJalon -> /api/django/contrats/jalons  [JalonContratSerializer]
    champs: contrat, date_atteinte, date_cible, date_creation, description, id, intitule, numero, statut, statut_display
    statut ∈ {a_venir, annule, atteint, en_cours, en_retard}
- frontend/src/api/contratsApi.js :: createModele -> /api/django/contrats/modeles  [ModeleContratSerializer]
    champs: actif, categorie, clauses, confidentialite_defaut, confidentialite_defaut_display, corps, date_creation, devise_defaut, id, nom, ordre, type_contrat_defaut, type_contrat_defaut_display
    confidentialite_defaut ∈ {confidentiel, interne, public}
    type_contrat_defaut ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: createModeleClause -> /api/django/contrats/modele-clauses  [ModeleContratClauseSerializer]
    champs: clause, id, modele, ordre
- frontend/src/api/contratsApi.js :: createMotifResiliation -> /api/django/contrats/motifs-resiliation  [MotifResiliationSerializer]
    champs: actif, categorie, categorie_display, code, date_creation, id, libelle, ordre
    categorie ∈ {autre, concurrent, fin_projet, insatisfaction, prix}
- frontend/src/api/contratsApi.js :: createObligation -> /api/django/contrats/obligations  [ObligationSerializer]
    champs: contrat, date_creation, date_echeance, date_realisation, description, id, intitule, jalon, ordre, redevable, redevable_display, statut, statut_display
    redevable ∈ {autre, client, prestataire}
    statut ∈ {a_faire, annulee, en_cours, en_retard, faite}
- frontend/src/api/contratsApi.js :: createPartie -> /api/django/contrats/parties  [PartieContratSerializer]
    champs: contact, contact_nom, contrat, email, fonction, id, nom, ordre, telephone, type_partie, type_partie_display
    type_partie ∈ {autre, client, garant, prestataire, temoin}
- frontend/src/api/contratsApi.js :: createPieceConformite -> /api/django/contrats/pieces-conformite  [PieceConformiteSerializer]
    champs: contrat, date_creation, date_expiration, date_fourniture, ged_document_id, id, libelle, note, obligatoire, statut, statut_display, type_piece, type_piece_display
    statut ∈ {expiree, fournie, manquante, refusee, validee}
    type_piece ∈ {assurance, autre, certificat, fiscale, kyc, pv_reception, rib}
- frontend/src/api/contratsApi.js :: createPlanRecurrent -> /api/django/contrats/plans-recurrents  [PlanRecurrentSerializer]
    champs: actif, aligner_debut_periode, date_creation, delai_cloture_auto_jours, id, intervalle, nom, unite, unite_display
    unite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/contratsApi.js :: createRegleApprobation -> /api/django/contrats/regles-approbation  [RegleApprobationSerializer]
    champs: actif, date_creation, id, libelle, montant_max, montant_min, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, type_contrat, type_contrat_display
    niveau_approbation ∈ {administrateur, direction, responsable}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: createRetenue -> /api/django/contrats/retenues-garantie  [RetenueGarantieSerializer]
    champs: contrat, date_creation, date_liberation_effective, date_liberation_prevue, date_retenue, id, montant_base, montant_retenu, note, statut, statut_display, taux
    statut ∈ {annulee, liberee, retenue}
- frontend/src/api/contratsApi.js :: createSla -> /api/django/contrats/sla  [EngagementSLASerializer]
    champs: actif, contrat, date_creation, id, libelle, mode_penalite, mode_penalite_display, penalite_max, taux_cible, unite, valeur_penalite
    mode_penalite ∈ {fixe, pourcentage}
- frontend/src/api/contratsApi.js :: deleteAlerte -> /api/django/contrats/alertes/<>  [AlerteContratSerializer]
    champs: contrat, cree_par, date_creation, date_declenchement, date_envoi, id, message, statut, statut_display, type_alerte, type_alerte_display
    statut ∈ {annulee, envoyee, planifiee}
    type_alerte ∈ {echeance, personnalise, preavis}
- frontend/src/api/contratsApi.js :: deleteCaution -> /api/django/contrats/cautions/<>  [CautionSerializer]
    champs: contrat, date_creation, date_emission, date_expiration, devise, garant, id, montant, note, reference, statut, statut_display, type_caution, type_caution_display
    statut ∈ {active, annulee, appelee, expiree, mainlevee}
    type_caution ∈ {autre, bonne_execution, restitution_acompte, retenue_garantie, societe_mere, soumission}
- frontend/src/api/contratsApi.js :: deleteClause -> /api/django/contrats/clauses/<>  [ClauseSerializer]
    champs: actif, categorie, corps, corps_localise, date_creation, id, ordre, titre, titre_localise, type_clause, type_clause_display
    type_clause ∈ {autre, confidentialite, financiere, garantie, generale, juridique, resiliation, technique}
- frontend/src/api/contratsApi.js :: deleteClauseContrat -> /api/django/contrats/clauses-contrat/<>  [ClauseContratSerializer]
    champs: clause, clause_titre, contrat, corps, date_creation, id, ordre, surchargee, titre
- frontend/src/api/contratsApi.js :: deleteContrat -> /api/django/contrats/contrats/<>  [ContratSerializer]
    champs: client_id, client_nom, confidentialite, confidentialite_display, created_by, custom_data, date_creation, date_debut, date_dernier_renouvellement, date_fin, devise, duree_reconduction_mois, echeance_preavis, id, jours_avant_echeance, jours_avant_preavis, modele, montant, nb_renouvellements, objet, plan_abonnement, plan_recurrent, preavis_jours, preavis_traite, reference, responsable, responsable_nom, sav_contrat_maintenance_id, sequence_dunning, statut, statut_display, tacite_reconduction, type_contrat, type_contrat_display
    confidentialite ∈ {confidentiel, interne, public}
    statut ∈ {actif, brouillon, en_approbation, expire, resilie, signe, suspendu}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: deleteContratLien -> /api/django/contrats/contrat-liens/<>  [ContratLienSerializer]
    champs: cible_id, contrat, date_creation, id, libelle, type_cible, type_cible_display
    type_cible ∈ {devis, installation, lead, maintenance}
- frontend/src/api/contratsApi.js :: deleteEcheancier -> /api/django/contrats/echeanciers/<>  [EcheancierContratSerializer]
    champs: contrat, date_creation, devise, facturation_active, id, libelle, lignes, montant_total, periodicite, periodicite_display, statut, statut_display
    periodicite ∈ {annuelle, mensuelle, personnalisee, semestrielle, trimestrielle, unique}
    statut ∈ {actif, annule, brouillon, solde}
- frontend/src/api/contratsApi.js :: deleteIndexation -> /api/django/contrats/indexations/<>  [IndexationPrixSerializer]
    champs: actif, contrat, date_creation, date_derniere_revision, id, indice, libelle, part_fixe, periodicite, periodicite_display, valeur_base
    periodicite ∈ {a_la_demande, annuelle, semestrielle, trimestrielle}
- frontend/src/api/contratsApi.js :: deleteJalon -> /api/django/contrats/jalons/<>  [JalonContratSerializer]
    champs: contrat, date_atteinte, date_cible, date_creation, description, id, intitule, numero, statut, statut_display
    statut ∈ {a_venir, annule, atteint, en_cours, en_retard}
- frontend/src/api/contratsApi.js :: deleteModele -> /api/django/contrats/modeles/<>  [ModeleContratSerializer]
    champs: actif, categorie, clauses, confidentialite_defaut, confidentialite_defaut_display, corps, date_creation, devise_defaut, id, nom, ordre, type_contrat_defaut, type_contrat_defaut_display
    confidentialite_defaut ∈ {confidentiel, interne, public}
    type_contrat_defaut ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: deleteModeleClause -> /api/django/contrats/modele-clauses/<>  [ModeleContratClauseSerializer]
    champs: clause, id, modele, ordre
- frontend/src/api/contratsApi.js :: deleteMotifResiliation -> /api/django/contrats/motifs-resiliation/<>  [MotifResiliationSerializer]
    champs: actif, categorie, categorie_display, code, date_creation, id, libelle, ordre
    categorie ∈ {autre, concurrent, fin_projet, insatisfaction, prix}
- frontend/src/api/contratsApi.js :: deleteObligation -> /api/django/contrats/obligations/<>  [ObligationSerializer]
    champs: contrat, date_creation, date_echeance, date_realisation, description, id, intitule, jalon, ordre, redevable, redevable_display, statut, statut_display
    redevable ∈ {autre, client, prestataire}
    statut ∈ {a_faire, annulee, en_cours, en_retard, faite}
- frontend/src/api/contratsApi.js :: deletePartie -> /api/django/contrats/parties/<>  [PartieContratSerializer]
    champs: contact, contact_nom, contrat, email, fonction, id, nom, ordre, telephone, type_partie, type_partie_display
    type_partie ∈ {autre, client, garant, prestataire, temoin}
- frontend/src/api/contratsApi.js :: deletePieceConformite -> /api/django/contrats/pieces-conformite/<>  [PieceConformiteSerializer]
    champs: contrat, date_creation, date_expiration, date_fourniture, ged_document_id, id, libelle, note, obligatoire, statut, statut_display, type_piece, type_piece_display
    statut ∈ {expiree, fournie, manquante, refusee, validee}
    type_piece ∈ {assurance, autre, certificat, fiscale, kyc, pv_reception, rib}
- frontend/src/api/contratsApi.js :: deletePlanRecurrent -> /api/django/contrats/plans-recurrents/<>  [PlanRecurrentSerializer]
    champs: actif, aligner_debut_periode, date_creation, delai_cloture_auto_jours, id, intervalle, nom, unite, unite_display
    unite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/contratsApi.js :: deleteRegleApprobation -> /api/django/contrats/regles-approbation/<>  [RegleApprobationSerializer]
    champs: actif, date_creation, id, libelle, montant_max, montant_min, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, type_contrat, type_contrat_display
    niveau_approbation ∈ {administrateur, direction, responsable}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: deleteRetenue -> /api/django/contrats/retenues-garantie/<>  [RetenueGarantieSerializer]
    champs: contrat, date_creation, date_liberation_effective, date_liberation_prevue, date_retenue, id, montant_base, montant_retenu, note, statut, statut_display, taux
    statut ∈ {annulee, liberee, retenue}
- frontend/src/api/contratsApi.js :: deleteSla -> /api/django/contrats/sla/<>  [EngagementSLASerializer]
    champs: actif, contrat, date_creation, id, libelle, mode_penalite, mode_penalite_display, penalite_max, taux_cible, unite, valeur_penalite
    mode_penalite ∈ {fixe, pourcentage}
- frontend/src/api/contratsApi.js :: getAlertes -> /api/django/contrats/alertes  [AlerteContratSerializer]
    champs: contrat, cree_par, date_creation, date_declenchement, date_envoi, id, message, statut, statut_display, type_alerte, type_alerte_display
    statut ∈ {annulee, envoyee, planifiee}
    type_alerte ∈ {echeance, personnalise, preavis}
- frontend/src/api/contratsApi.js :: getAvenants -> /api/django/contrats/avenants  [AvenantSerializer]
    champs: contrat, cree_par, cree_par_username, date_creation, date_effet, description, id, montant_delta, numero, objet, version_creee
- frontend/src/api/contratsApi.js :: getCautions -> /api/django/contrats/cautions  [CautionSerializer]
    champs: contrat, date_creation, date_emission, date_expiration, devise, garant, id, montant, note, reference, statut, statut_display, type_caution, type_caution_display
    statut ∈ {active, annulee, appelee, expiree, mainlevee}
    type_caution ∈ {autre, bonne_execution, restitution_acompte, retenue_garantie, societe_mere, soumission}
- frontend/src/api/contratsApi.js :: getClause -> /api/django/contrats/clauses/<>  [ClauseSerializer]
    champs: actif, categorie, corps, corps_localise, date_creation, id, ordre, titre, titre_localise, type_clause, type_clause_display
    type_clause ∈ {autre, confidentialite, financiere, garantie, generale, juridique, resiliation, technique}
- frontend/src/api/contratsApi.js :: getClauses -> /api/django/contrats/clauses  [ClauseSerializer]
    champs: actif, categorie, corps, corps_localise, date_creation, id, ordre, titre, titre_localise, type_clause, type_clause_display
    type_clause ∈ {autre, confidentialite, financiere, garantie, generale, juridique, resiliation, technique}
- frontend/src/api/contratsApi.js :: getClausesContrat -> /api/django/contrats/clauses-contrat  [ClauseContratSerializer]
    champs: clause, clause_titre, contrat, corps, date_creation, id, ordre, surchargee, titre
- frontend/src/api/contratsApi.js :: getContrat -> /api/django/contrats/contrats/<>  [ContratSerializer]
    champs: client_id, client_nom, confidentialite, confidentialite_display, created_by, custom_data, date_creation, date_debut, date_dernier_renouvellement, date_fin, devise, duree_reconduction_mois, echeance_preavis, id, jours_avant_echeance, jours_avant_preavis, modele, montant, nb_renouvellements, objet, plan_abonnement, plan_recurrent, preavis_jours, preavis_traite, reference, responsable, responsable_nom, sav_contrat_maintenance_id, sequence_dunning, statut, statut_display, tacite_reconduction, type_contrat, type_contrat_display
    confidentialite ∈ {confidentiel, interne, public}
    statut ∈ {actif, brouillon, en_approbation, expire, resilie, signe, suspendu}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: getContratLiens -> /api/django/contrats/contrat-liens  [ContratLienSerializer]
    champs: cible_id, contrat, date_creation, id, libelle, type_cible, type_cible_display
    type_cible ∈ {devis, installation, lead, maintenance}
- frontend/src/api/contratsApi.js :: getContrats -> /api/django/contrats/contrats  [ContratSerializer]
    champs: client_id, client_nom, confidentialite, confidentialite_display, created_by, custom_data, date_creation, date_debut, date_dernier_renouvellement, date_fin, devise, duree_reconduction_mois, echeance_preavis, id, jours_avant_echeance, jours_avant_preavis, modele, montant, nb_renouvellements, objet, plan_abonnement, plan_recurrent, preavis_jours, preavis_traite, reference, responsable, responsable_nom, sav_contrat_maintenance_id, sequence_dunning, statut, statut_display, tacite_reconduction, type_contrat, type_contrat_display
    confidentialite ∈ {confidentiel, interne, public}
    statut ∈ {actif, brouillon, en_approbation, expire, resilie, signe, suspendu}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: getCyclesFacturation -> /api/django/contrats/cycles-facturation  [CycleFacturationLogSerializer]
    champs: date_creation, facture_id, id, motif, nb_tentatives, periode, source_id, source_type, source_type_display, statut, statut_display
    source_type ∈ {contrat, ordre_location, sav_maintenance}
    statut ∈ {echec, genere, saute}
- frontend/src/api/contratsApi.js :: getEcheancier -> /api/django/contrats/echeanciers/<>  [EcheancierContratSerializer]
    champs: contrat, date_creation, devise, facturation_active, id, libelle, lignes, montant_total, periodicite, periodicite_display, statut, statut_display
    periodicite ∈ {annuelle, mensuelle, personnalisee, semestrielle, trimestrielle, unique}
    statut ∈ {actif, annule, brouillon, solde}
- frontend/src/api/contratsApi.js :: getEcheanciers -> /api/django/contrats/echeanciers  [EcheancierContratSerializer]
    champs: contrat, date_creation, devise, facturation_active, id, libelle, lignes, montant_total, periodicite, periodicite_display, statut, statut_display
    periodicite ∈ {annuelle, mensuelle, personnalisee, semestrielle, trimestrielle, unique}
    statut ∈ {actif, annule, brouillon, solde}
- frontend/src/api/contratsApi.js :: getIndexations -> /api/django/contrats/indexations  [IndexationPrixSerializer]
    champs: actif, contrat, date_creation, date_derniere_revision, id, indice, libelle, part_fixe, periodicite, periodicite_display, valeur_base
    periodicite ∈ {a_la_demande, annuelle, semestrielle, trimestrielle}
- frontend/src/api/contratsApi.js :: getJalons -> /api/django/contrats/jalons  [JalonContratSerializer]
    champs: contrat, date_atteinte, date_cible, date_creation, description, id, intitule, numero, statut, statut_display
    statut ∈ {a_venir, annule, atteint, en_cours, en_retard}
- frontend/src/api/contratsApi.js :: getLignesEcheance -> /api/django/contrats/lignes-echeance  [LigneEcheanceSerializer]
    champs: date_creation, date_echeance, date_paiement, echeancier, facture_id, id, libelle, montant, numero, statut, statut_display
    statut ∈ {a_venir, annulee, en_retard, payee}
- frontend/src/api/contratsApi.js :: getModele -> /api/django/contrats/modeles/<>  [ModeleContratSerializer]
    champs: actif, categorie, clauses, confidentialite_defaut, confidentialite_defaut_display, corps, date_creation, devise_defaut, id, nom, ordre, type_contrat_defaut, type_contrat_defaut_display
    confidentialite_defaut ∈ {confidentiel, interne, public}
    type_contrat_defaut ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: getModeleClauses -> /api/django/contrats/modele-clauses  [ModeleContratClauseSerializer]
    champs: clause, id, modele, ordre
- frontend/src/api/contratsApi.js :: getModeles -> /api/django/contrats/modeles  [ModeleContratSerializer]
    champs: actif, categorie, clauses, confidentialite_defaut, confidentialite_defaut_display, corps, date_creation, devise_defaut, id, nom, ordre, type_contrat_defaut, type_contrat_defaut_display
    confidentialite_defaut ∈ {confidentiel, interne, public}
    type_contrat_defaut ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: getMotifsResiliation -> /api/django/contrats/motifs-resiliation  [MotifResiliationSerializer]
    champs: actif, categorie, categorie_display, code, date_creation, id, libelle, ordre
    categorie ∈ {autre, concurrent, fin_projet, insatisfaction, prix}
- frontend/src/api/contratsApi.js :: getObligations -> /api/django/contrats/obligations  [ObligationSerializer]
    champs: contrat, date_creation, date_echeance, date_realisation, description, id, intitule, jalon, ordre, redevable, redevable_display, statut, statut_display
    redevable ∈ {autre, client, prestataire}
    statut ∈ {a_faire, annulee, en_cours, en_retard, faite}
- frontend/src/api/contratsApi.js :: getParties -> /api/django/contrats/parties  [PartieContratSerializer]
    champs: contact, contact_nom, contrat, email, fonction, id, nom, ordre, telephone, type_partie, type_partie_display
    type_partie ∈ {autre, client, garant, prestataire, temoin}
- frontend/src/api/contratsApi.js :: getPiecesConformite -> /api/django/contrats/pieces-conformite  [PieceConformiteSerializer]
    champs: contrat, date_creation, date_expiration, date_fourniture, ged_document_id, id, libelle, note, obligatoire, statut, statut_display, type_piece, type_piece_display
    statut ∈ {expiree, fournie, manquante, refusee, validee}
    type_piece ∈ {assurance, autre, certificat, fiscale, kyc, pv_reception, rib}
- frontend/src/api/contratsApi.js :: getPlansRecurrents -> /api/django/contrats/plans-recurrents  [PlanRecurrentSerializer]
    champs: actif, aligner_debut_periode, date_creation, delai_cloture_auto_jours, id, intervalle, nom, unite, unite_display
    unite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/contratsApi.js :: getReglesApprobation -> /api/django/contrats/regles-approbation  [RegleApprobationSerializer]
    champs: actif, date_creation, id, libelle, montant_max, montant_min, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, type_contrat, type_contrat_display
    niveau_approbation ∈ {administrateur, direction, responsable}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: getResiliations -> /api/django/contrats/resiliations  [ResiliationSerializer]
    champs: contrat, cree_par, cree_par_username, date_creation, date_demande, date_effet, id, motif, motif_ref, motif_ref_libelle, preavis_jours, solde, statut, statut_display, version_creee
    statut ∈ {annulee, demande, effective}
- frontend/src/api/contratsApi.js :: getRetenues -> /api/django/contrats/retenues-garantie  [RetenueGarantieSerializer]
    champs: contrat, date_creation, date_liberation_effective, date_liberation_prevue, date_retenue, id, montant_base, montant_retenu, note, statut, statut_display, taux
    statut ∈ {annulee, liberee, retenue}
- frontend/src/api/contratsApi.js :: getSla -> /api/django/contrats/sla  [EngagementSLASerializer]
    champs: actif, contrat, date_creation, id, libelle, mode_penalite, mode_penalite_display, penalite_max, taux_cible, unite, valeur_penalite
    mode_penalite ∈ {fixe, pourcentage}
- frontend/src/api/contratsApi.js :: getVersions -> /api/django/contrats/versions  [VersionContratSerializer]
    champs: contenu, contrat, cree_le, cree_par, cree_par_username, fichier_key, id, motif, version
- frontend/src/api/contratsApi.js :: updateAlerte -> /api/django/contrats/alertes/<>  [AlerteContratSerializer]
    champs: contrat, cree_par, date_creation, date_declenchement, date_envoi, id, message, statut, statut_display, type_alerte, type_alerte_display
    statut ∈ {annulee, envoyee, planifiee}
    type_alerte ∈ {echeance, personnalise, preavis}
- frontend/src/api/contratsApi.js :: updateCaution -> /api/django/contrats/cautions/<>  [CautionSerializer]
    champs: contrat, date_creation, date_emission, date_expiration, devise, garant, id, montant, note, reference, statut, statut_display, type_caution, type_caution_display
    statut ∈ {active, annulee, appelee, expiree, mainlevee}
    type_caution ∈ {autre, bonne_execution, restitution_acompte, retenue_garantie, societe_mere, soumission}
- frontend/src/api/contratsApi.js :: updateClause -> /api/django/contrats/clauses/<>  [ClauseSerializer]
    champs: actif, categorie, corps, corps_localise, date_creation, id, ordre, titre, titre_localise, type_clause, type_clause_display
    type_clause ∈ {autre, confidentialite, financiere, garantie, generale, juridique, resiliation, technique}
- frontend/src/api/contratsApi.js :: updateClauseContrat -> /api/django/contrats/clauses-contrat/<>  [ClauseContratSerializer]
    champs: clause, clause_titre, contrat, corps, date_creation, id, ordre, surchargee, titre
- frontend/src/api/contratsApi.js :: updateContrat -> /api/django/contrats/contrats/<>  [ContratSerializer]
    champs: client_id, client_nom, confidentialite, confidentialite_display, created_by, custom_data, date_creation, date_debut, date_dernier_renouvellement, date_fin, devise, duree_reconduction_mois, echeance_preavis, id, jours_avant_echeance, jours_avant_preavis, modele, montant, nb_renouvellements, objet, plan_abonnement, plan_recurrent, preavis_jours, preavis_traite, reference, responsable, responsable_nom, sav_contrat_maintenance_id, sequence_dunning, statut, statut_display, tacite_reconduction, type_contrat, type_contrat_display
    confidentialite ∈ {confidentiel, interne, public}
    statut ∈ {actif, brouillon, en_approbation, expire, resilie, signe, suspendu}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: updateEcheancier -> /api/django/contrats/echeanciers/<>  [EcheancierContratSerializer]
    champs: contrat, date_creation, devise, facturation_active, id, libelle, lignes, montant_total, periodicite, periodicite_display, statut, statut_display
    periodicite ∈ {annuelle, mensuelle, personnalisee, semestrielle, trimestrielle, unique}
    statut ∈ {actif, annule, brouillon, solde}
- frontend/src/api/contratsApi.js :: updateIndexation -> /api/django/contrats/indexations/<>  [IndexationPrixSerializer]
    champs: actif, contrat, date_creation, date_derniere_revision, id, indice, libelle, part_fixe, periodicite, periodicite_display, valeur_base
    periodicite ∈ {a_la_demande, annuelle, semestrielle, trimestrielle}
- frontend/src/api/contratsApi.js :: updateJalon -> /api/django/contrats/jalons/<>  [JalonContratSerializer]
    champs: contrat, date_atteinte, date_cible, date_creation, description, id, intitule, numero, statut, statut_display
    statut ∈ {a_venir, annule, atteint, en_cours, en_retard}
- frontend/src/api/contratsApi.js :: updateModele -> /api/django/contrats/modeles/<>  [ModeleContratSerializer]
    champs: actif, categorie, clauses, confidentialite_defaut, confidentialite_defaut_display, corps, date_creation, devise_defaut, id, nom, ordre, type_contrat_defaut, type_contrat_defaut_display
    confidentialite_defaut ∈ {confidentiel, interne, public}
    type_contrat_defaut ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: updateMotifResiliation -> /api/django/contrats/motifs-resiliation/<>  [MotifResiliationSerializer]
    champs: actif, categorie, categorie_display, code, date_creation, id, libelle, ordre
    categorie ∈ {autre, concurrent, fin_projet, insatisfaction, prix}
- frontend/src/api/contratsApi.js :: updateObligation -> /api/django/contrats/obligations/<>  [ObligationSerializer]
    champs: contrat, date_creation, date_echeance, date_realisation, description, id, intitule, jalon, ordre, redevable, redevable_display, statut, statut_display
    redevable ∈ {autre, client, prestataire}
    statut ∈ {a_faire, annulee, en_cours, en_retard, faite}
- frontend/src/api/contratsApi.js :: updatePartie -> /api/django/contrats/parties/<>  [PartieContratSerializer]
    champs: contact, contact_nom, contrat, email, fonction, id, nom, ordre, telephone, type_partie, type_partie_display
    type_partie ∈ {autre, client, garant, prestataire, temoin}
- frontend/src/api/contratsApi.js :: updatePieceConformite -> /api/django/contrats/pieces-conformite/<>  [PieceConformiteSerializer]
    champs: contrat, date_creation, date_expiration, date_fourniture, ged_document_id, id, libelle, note, obligatoire, statut, statut_display, type_piece, type_piece_display
    statut ∈ {expiree, fournie, manquante, refusee, validee}
    type_piece ∈ {assurance, autre, certificat, fiscale, kyc, pv_reception, rib}
- frontend/src/api/contratsApi.js :: updatePlanRecurrent -> /api/django/contrats/plans-recurrents/<>  [PlanRecurrentSerializer]
    champs: actif, aligner_debut_periode, date_creation, delai_cloture_auto_jours, id, intervalle, nom, unite, unite_display
    unite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/contratsApi.js :: updateRegleApprobation -> /api/django/contrats/regles-approbation/<>  [RegleApprobationSerializer]
    champs: actif, date_creation, id, libelle, montant_max, montant_min, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, type_contrat, type_contrat_display
    niveau_approbation ∈ {administrateur, direction, responsable}
    type_contrat ∈ {autre, emploi, fournisseur, garantie, location, maintenance, monitoring, nda, om, ppa, sous_traitance, vente}
- frontend/src/api/contratsApi.js :: updateRetenue -> /api/django/contrats/retenues-garantie/<>  [RetenueGarantieSerializer]
    champs: contrat, date_creation, date_liberation_effective, date_liberation_prevue, date_retenue, id, montant_base, montant_retenu, note, statut, statut_display, taux
    statut ∈ {annulee, liberee, retenue}
- frontend/src/api/contratsApi.js :: updateSla -> /api/django/contrats/sla/<>  [EngagementSLASerializer]
    champs: actif, contrat, date_creation, id, libelle, mode_penalite, mode_penalite_display, penalite_max, taux_cible, unite, valeur_penalite
    mode_penalite ∈ {fixe, pourcentage}
- frontend/src/api/coreApi.js :: get -> /api/django/core/dashboards/<>  [DashboardSerializer]
    champs: created_at, description, id, layout, owner, partage, titre, updated_at
- frontend/src/api/coreApi.js :: revoke -> /api/django/core/dashboards-partages/<>  [PartageDashboardSerializer]
    champs: actif, created_at, dashboard, expires_at, id, token, updated_at
- frontend/src/api/coreApi.js :: updateLayout -> /api/django/core/dashboards/<>  [DashboardSerializer]
    champs: created_at, description, id, layout, owner, partage, titre, updated_at
- frontend/src/api/cpqApi.js :: createContrainteCompatibilite -> /api/django/cpq/contraintes-compatibilite  [ContrainteCompatibiliteSerializer]
    champs: bloquante, id, message_utilisateur, produit_a, produit_b, type
    type ∈ {INCOMPATIBLE, RECOMMANDE, REQUIERT}
- frontend/src/api/cpqApi.js :: createOffreGroupee -> /api/django/cpq/offres-groupees  [OffreGroupeeSerializer]
    champs: actif, date_creation, id, lignes, nom, prix_total
- frontend/src/api/cpqApi.js :: createPrixContractuel -> /api/django/cpq/prix-contractuels  [PrixContractuelSerializer]
    champs: client, created_by, date_creation, date_debut, date_fin, est_actif, id, motif, prix_ht, produit
- frontend/src/api/cpqApi.js :: createQuestionConfigurateur -> /api/django/cpq/configurateur-questions  [QuestionConfigurateurSerializer]
    champs: actif, champ, id, options, ordre, texte, type
    type ∈ {CHOIX_MULTIPLE, CHOIX_UNIQUE, NUMERIQUE}
- frontend/src/api/cpqApi.js :: createRegleApprobationRemise -> /api/django/cpq/regles-approbation-remise  [RegleApprobationRemiseSerializer]
    champs: actif, date_creation, id, libelle, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, remise_max_pct, remise_min_pct
    niveau_approbation ∈ {administrateur, direction, responsable}
- frontend/src/api/cpqApi.js :: createSeuilMarge -> /api/django/cpq/seuils-marge  [SeuilMargeFamilleSerializer]
    champs: categorie, categorie_nom, id, marge_min_pct
- frontend/src/api/cpqApi.js :: deleteContrainteCompatibilite -> /api/django/cpq/contraintes-compatibilite/<>  [ContrainteCompatibiliteSerializer]
    champs: bloquante, id, message_utilisateur, produit_a, produit_b, type
    type ∈ {INCOMPATIBLE, RECOMMANDE, REQUIERT}
- frontend/src/api/cpqApi.js :: deleteOffreGroupee -> /api/django/cpq/offres-groupees/<>  [OffreGroupeeSerializer]
    champs: actif, date_creation, id, lignes, nom, prix_total
- frontend/src/api/cpqApi.js :: deletePrixContractuel -> /api/django/cpq/prix-contractuels/<>  [PrixContractuelSerializer]
    champs: client, created_by, date_creation, date_debut, date_fin, est_actif, id, motif, prix_ht, produit
- frontend/src/api/cpqApi.js :: deleteQuestionConfigurateur -> /api/django/cpq/configurateur-questions/<>  [QuestionConfigurateurSerializer]
    champs: actif, champ, id, options, ordre, texte, type
    type ∈ {CHOIX_MULTIPLE, CHOIX_UNIQUE, NUMERIQUE}
- frontend/src/api/cpqApi.js :: deleteRegleApprobationRemise -> /api/django/cpq/regles-approbation-remise/<>  [RegleApprobationRemiseSerializer]
    champs: actif, date_creation, id, libelle, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, remise_max_pct, remise_min_pct
    niveau_approbation ∈ {administrateur, direction, responsable}
- frontend/src/api/cpqApi.js :: deleteSeuilMarge -> /api/django/cpq/seuils-marge/<>  [SeuilMargeFamilleSerializer]
    champs: categorie, categorie_nom, id, marge_min_pct
- frontend/src/api/cpqApi.js :: getContraintesCompatibilite -> /api/django/cpq/contraintes-compatibilite  [ContrainteCompatibiliteSerializer]
    champs: bloquante, id, message_utilisateur, produit_a, produit_b, type
    type ∈ {INCOMPATIBLE, RECOMMANDE, REQUIERT}
- frontend/src/api/cpqApi.js :: getOffresGroupees -> /api/django/cpq/offres-groupees  [OffreGroupeeSerializer]
    champs: actif, date_creation, id, lignes, nom, prix_total
- frontend/src/api/cpqApi.js :: getPrixContractuels -> /api/django/cpq/prix-contractuels  [PrixContractuelSerializer]
    champs: client, created_by, date_creation, date_debut, date_fin, est_actif, id, motif, prix_ht, produit
- frontend/src/api/cpqApi.js :: getQuestionsConfigurateur -> /api/django/cpq/configurateur-questions  [QuestionConfigurateurSerializer]
    champs: actif, champ, id, options, ordre, texte, type
    type ∈ {CHOIX_MULTIPLE, CHOIX_UNIQUE, NUMERIQUE}
- frontend/src/api/cpqApi.js :: getReglesApprobationRemise -> /api/django/cpq/regles-approbation-remise  [RegleApprobationRemiseSerializer]
    champs: actif, date_creation, id, libelle, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, remise_max_pct, remise_min_pct
    niveau_approbation ∈ {administrateur, direction, responsable}
- frontend/src/api/cpqApi.js :: getSeuilsMarge -> /api/django/cpq/seuils-marge  [SeuilMargeFamilleSerializer]
    champs: categorie, categorie_nom, id, marge_min_pct
- frontend/src/api/cpqApi.js :: updateContrainteCompatibilite -> /api/django/cpq/contraintes-compatibilite/<>  [ContrainteCompatibiliteSerializer]
    champs: bloquante, id, message_utilisateur, produit_a, produit_b, type
    type ∈ {INCOMPATIBLE, RECOMMANDE, REQUIERT}
- frontend/src/api/cpqApi.js :: updateOffreGroupee -> /api/django/cpq/offres-groupees/<>  [OffreGroupeeSerializer]
    champs: actif, date_creation, id, lignes, nom, prix_total
- frontend/src/api/cpqApi.js :: updatePrixContractuel -> /api/django/cpq/prix-contractuels/<>  [PrixContractuelSerializer]
    champs: client, created_by, date_creation, date_debut, date_fin, est_actif, id, motif, prix_ht, produit
- frontend/src/api/cpqApi.js :: updateQuestionConfigurateur -> /api/django/cpq/configurateur-questions/<>  [QuestionConfigurateurSerializer]
    champs: actif, champ, id, options, ordre, texte, type
    type ∈ {CHOIX_MULTIPLE, CHOIX_UNIQUE, NUMERIQUE}
- frontend/src/api/cpqApi.js :: updateRegleApprobationRemise -> /api/django/cpq/regles-approbation-remise/<>  [RegleApprobationRemiseSerializer]
    champs: actif, date_creation, id, libelle, niveau_approbation, niveau_approbation_display, nombre_approbateurs, priorite, remise_max_pct, remise_min_pct
    niveau_approbation ∈ {administrateur, direction, responsable}
- frontend/src/api/cpqApi.js :: updateSeuilMarge -> /api/django/cpq/seuils-marge/<>  [SeuilMargeFamilleSerializer]
    champs: categorie, categorie_nom, id, marge_min_pct
- frontend/src/api/creditApi.js :: createConditionSegment -> /api/django/credit/conditions-segment  [ConditionPaiementSegmentSerializer]
    champs: date_creation, date_modification, delai_paiement_jours, id, mode_hold_override, pct_acompte_defaut, segment
    mode_hold_override ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: createDerogation -> /api/django/credit/derogations  [DerogationCreditSerializer]
    champs: approuvee_par, client, date_creation, date_decision, demandeur, devis, est_valide, id, montant_demande, motif, statut, valide_jusqu_au
    statut ∈ {approuvee, en_attente, expiree, rejetee}
- frontend/src/api/creditApi.js :: createEncoursGaranti -> /api/django/credit/encours-garantis  [EncoursGarantiClientSerializer]
    champs: client, date_agrement, date_creation, id, montant_garanti, police, reference_assureur, statut_agrement
    statut_agrement ∈ {accorde, en_attente, reduit, refuse}
- frontend/src/api/creditApi.js :: createLimite -> /api/django/credit/limites  [LimiteCreditSerializer]
    champs: actif, client, cree_par, date_creation, date_modification, devise, id, mode_hold, montant_limite, motif_null
    mode_hold ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: createPoliceAssurance -> /api/django/credit/polices-assurance  [PoliceAssuranceCreditSerializer]
    champs: actif, assureur, date_creation, date_debut, date_fin, date_modification, franchise, id, numero_police, plafond_global, taux_couverture_pct
- frontend/src/api/creditApi.js :: createSegmentClient -> /api/django/credit/segments-client  [SegmentClientCreditSerializer]
    champs: client, date_modification, id, segment
- frontend/src/api/creditApi.js :: deleteConditionSegment -> /api/django/credit/conditions-segment/<>  [ConditionPaiementSegmentSerializer]
    champs: date_creation, date_modification, delai_paiement_jours, id, mode_hold_override, pct_acompte_defaut, segment
    mode_hold_override ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: deleteEncoursGaranti -> /api/django/credit/encours-garantis/<>  [EncoursGarantiClientSerializer]
    champs: client, date_agrement, date_creation, id, montant_garanti, police, reference_assureur, statut_agrement
    statut_agrement ∈ {accorde, en_attente, reduit, refuse}
- frontend/src/api/creditApi.js :: deleteSegmentClient -> /api/django/credit/segments-client/<>  [SegmentClientCreditSerializer]
    champs: client, date_modification, id, segment
- frontend/src/api/creditApi.js :: getConditionsSegment -> /api/django/credit/conditions-segment  [ConditionPaiementSegmentSerializer]
    champs: date_creation, date_modification, delai_paiement_jours, id, mode_hold_override, pct_acompte_defaut, segment
    mode_hold_override ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: getDerogations -> /api/django/credit/derogations  [DerogationCreditSerializer]
    champs: approuvee_par, client, date_creation, date_decision, demandeur, devis, est_valide, id, montant_demande, motif, statut, valide_jusqu_au
    statut ∈ {approuvee, en_attente, expiree, rejetee}
- frontend/src/api/creditApi.js :: getEncoursGarantis -> /api/django/credit/encours-garantis  [EncoursGarantiClientSerializer]
    champs: client, date_agrement, date_creation, id, montant_garanti, police, reference_assureur, statut_agrement
    statut_agrement ∈ {accorde, en_attente, reduit, refuse}
- frontend/src/api/creditApi.js :: getLimites -> /api/django/credit/limites  [LimiteCreditSerializer]
    champs: actif, client, cree_par, date_creation, date_modification, devise, id, mode_hold, montant_limite, motif_null
    mode_hold ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: getPolicesAssurance -> /api/django/credit/polices-assurance  [PoliceAssuranceCreditSerializer]
    champs: actif, assureur, date_creation, date_debut, date_fin, date_modification, franchise, id, numero_police, plafond_global, taux_couverture_pct
- frontend/src/api/creditApi.js :: getSegmentsClient -> /api/django/credit/segments-client  [SegmentClientCreditSerializer]
    champs: client, date_modification, id, segment
- frontend/src/api/creditApi.js :: updateConditionSegment -> /api/django/credit/conditions-segment/<>  [ConditionPaiementSegmentSerializer]
    champs: date_creation, date_modification, delai_paiement_jours, id, mode_hold_override, pct_acompte_defaut, segment
    mode_hold_override ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: updateLimite -> /api/django/credit/limites/<>  [LimiteCreditSerializer]
    champs: actif, client, cree_par, date_creation, date_modification, devise, id, mode_hold, montant_limite, motif_null
    mode_hold ∈ {aucun, avertissement, blocage}
- frontend/src/api/creditApi.js :: updatePoliceAssurance -> /api/django/credit/polices-assurance/<>  [PoliceAssuranceCreditSerializer]
    champs: actif, assureur, date_creation, date_debut, date_fin, date_modification, franchise, id, numero_police, plafond_global, taux_couverture_pct
- frontend/src/api/creditApi.js :: updateSegmentClient -> /api/django/credit/segments-client/<>  [SegmentClientCreditSerializer]
    champs: client, date_modification, id, segment
- frontend/src/api/crmApi.js :: createAppointment -> /api/django/crm/appointments  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: createCommissionPartenaire -> /api/django/crm/commissions-partenaire  [CommissionPartenaireSerializer]
    champs: base_ht, date_creation, devis_id, id, lead_id, montant, partenaire, paye_le, statut, taux
    statut ∈ {annulee, due, payee}
- frontend/src/api/crmApi.js :: createConcurrentPerte -> /api/django/crm/concurrents-perte  [ConcurrentPerteSerializer]
    champs: company, concurrent_nom, concurrent_prix, date_modification, devise, id, lead, lead_nom, motif, notes, saisi_le, saisi_par, saisi_par_nom
- frontend/src/api/crmApi.js :: createPartenaire -> /api/django/crm/partenaires  [PartenaireSerializer]
    champs: actif, date_activation, date_creation, email, id, nom, numero_agrement, statut_onboarding, taux_commission, telephone, token_acces, type_partenaire, zone
    statut_onboarding ∈ {agree, en_cours, prospect, suspendu}
    type_partenaire ∈ {apporteur, installateur, sous_revendeur}
- frontend/src/api/crmApi.js :: createPointContact -> /api/django/crm/points-contact  [PointContactSerializer]
    champs: canal, canal_libelle, company, cout, date_contact, date_modification, detail, id, lead, lead_nom, ordre, saisi_le, saisi_par, saisi_par_nom, source
    canal ∈ {autre, meta_ads, reference, site_web, telephone, walk_in, whatsapp_ctwa}
- frontend/src/api/crmApi.js :: createSavedView -> /api/django/crm/vues-enregistrees  [SavedViewSerializer]
    champs: created_at, id, name, page, payload, rank, user
- frontend/src/api/crmApi.js :: createSiteProfile -> /api/django/crm/site-profiles  [SiteProfileSerializer]
    champs: client, company, conso_mensuelle_kwh, date_creation, date_modification, ete_differente, facture_ete, facture_hiver, gps_lat, gps_lng, id, inclinaison_deg, ombrage, ombrage_notes, orientation, pompe_cv, pompe_debit_m3h, pompe_hmt_m, raccordement, regularisation_8221, surface_toiture_m2, tranche_onee, type_installation, type_toiture
    ombrage ∈ {aucun, important, partiel}
    orientation ∈ {autre, est, ouest, sud, sud_est, sud_ouest}
    raccordement ∈ {inconnu, monophase, triphase}
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
- frontend/src/api/crmApi.js :: deleteTag -> /api/django/crm/tags/<>  [LeadTagSerializer]
    champs: archived, couleur, en_usage, id, nom
- frontend/src/api/crmApi.js :: getAppointments -> /api/django/crm/appointments  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: getCommissionsPartenaire -> /api/django/crm/commissions-partenaire  [CommissionPartenaireSerializer]
    champs: base_ht, date_creation, devis_id, id, lead_id, montant, partenaire, paye_le, statut, taux
    statut ∈ {annulee, due, payee}
- frontend/src/api/crmApi.js :: getConcurrentsPerte -> /api/django/crm/concurrents-perte  [ConcurrentPerteSerializer]
    champs: company, concurrent_nom, concurrent_prix, date_modification, devise, id, lead, lead_nom, motif, notes, saisi_le, saisi_par, saisi_par_nom
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
- frontend/src/api/crmApi.js :: getPartenaires -> /api/django/crm/partenaires  [PartenaireSerializer]
    champs: actif, date_activation, date_creation, email, id, nom, numero_agrement, statut_onboarding, taux_commission, telephone, token_acces, type_partenaire, zone
    statut_onboarding ∈ {agree, en_cours, prospect, suspendu}
    type_partenaire ∈ {apporteur, installateur, sous_revendeur}
- frontend/src/api/crmApi.js :: getPlansActivite -> /api/django/crm/plans-activite  [PlanActiviteSerializer]
    champs: actif, company, date_creation, etapes, id, nom
- frontend/src/api/crmApi.js :: getSiteProfiles -> /api/django/crm/site-profiles  [SiteProfileSerializer]
    champs: client, company, conso_mensuelle_kwh, date_creation, date_modification, ete_differente, facture_ete, facture_hiver, gps_lat, gps_lng, id, inclinaison_deg, ombrage, ombrage_notes, orientation, pompe_cv, pompe_debit_m3h, pompe_hmt_m, raccordement, regularisation_8221, surface_toiture_m2, tranche_onee, type_installation, type_toiture
    ombrage ∈ {aucun, important, partiel}
    orientation ∈ {autre, est, ouest, sud, sud_est, sud_ouest}
    raccordement ∈ {inconnu, monophase, triphase}
    type_installation ∈ {agricole, commercial, industriel, residentiel}
    type_toiture ∈ {autre, bac_acier, fibrociment, terrasse_beton, tole_metal, tuiles}
- frontend/src/api/crmApi.js :: getSoumissionsLeadPartenaire -> /api/django/crm/soumissions-lead-partenaire  [SoumissionLeadPartenaireSerializer]
    champs: date_soumission, email_prospect, id, lead_id, nom_prospect, note, partenaire, statut, telephone_prospect, ville
    statut ∈ {converti, qualifie, rejete, soumis}
- frontend/src/api/crmApi.js :: getTags -> /api/django/crm/tags  [LeadTagSerializer]
    champs: archived, couleur, en_usage, id, nom
- frontend/src/api/crmApi.js :: getWebsiteLeadPayloads -> /api/django/crm/website-lead-payloads  [WebsiteLeadPayloadSerializer]
    champs: company, error, id, lead, lead_nom, payload, processed, received_at, remote_addr
- frontend/src/api/crmApi.js :: listSavedViews -> /api/django/crm/vues-enregistrees  [SavedViewSerializer]
    champs: created_at, id, name, page, payload, rank, user
- frontend/src/api/crmApi.js :: updateAppointment -> /api/django/crm/appointments/<>  [AppointmentSerializer]
    champs: company, created_by, date_creation, date_modification, id, lead, lead_nom, notes, reminder_sent, scheduled_at, statut, statut_display
    statut ∈ {annule, confirme, effectue, no_show, planifie}
- frontend/src/api/crmApi.js :: updateSiteProfile -> /api/django/crm/site-profiles/<>  [SiteProfileSerializer]
    champs: client, company, conso_mensuelle_kwh, date_creation, date_modification, ete_differente, facture_ete, facture_hiver, gps_lat, gps_lng, id, inclinaison_deg, ombrage, ombrage_notes, orientation, pompe_cv, pompe_debit_m3h, pompe_hmt_m, raccordement, regularisation_8221, surface_toiture_m2, tranche_onee, type_installation, type_toiture
    ombrage ∈ {aucun, important, partiel}
    orientation ∈ {autre, est, ouest, sud, sud_est, sud_ouest}
    raccordement ∈ {inconnu, monophase, triphase}
    type_installation ∈ {agricole, commercial, industriel, residentiel}
    type_toiture ∈ {autre, bac_acier, fibrociment, terrasse_beton, tole_metal, tuiles}
- frontend/src/api/customFieldsApi.js :: deleteDef -> /api/django/custom-fields/definitions/<>  [CustomFieldDefSerializer]
    champs: actif, code, conditions, ia_prompt, id, libelle, module, obligatoire, options, ordre, relation_module, type, verrouille, visible_liste
    module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    relation_module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    type ∈ {boolean, choice, date, fichier, ia, number, relation, text}
- frontend/src/api/customFieldsApi.js :: getDefs -> /api/django/custom-fields/definitions  [CustomFieldDefSerializer]
    champs: actif, code, conditions, ia_prompt, id, libelle, module, obligatoire, options, ordre, relation_module, type, verrouille, visible_liste
    module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    relation_module ∈ {client, devis, document, employe, fournisseur, installation, lead, produit, ticket}
    type ∈ {boolean, choice, date, fichier, ia, number, relation, text}
- frontend/src/api/demoApi.js :: setPresentationMode -> /api/django/companies/<>  [CompanySerializer]
    champs: actif, benchmarking_opt_in, date_creation, est_demo, id, mode_presentation_actif, nom, slug
- frontend/src/api/educationApi.js :: remove -> /api/django/education/emploi-du-temps/<>  [CreneauEmploiDuTempsSerializer]
    champs: actif, classe, heure_debut, heure_fin, id, jour_semaine, matiere_classe, salle
- frontend/src/api/einvoiceApi.js :: list -> /api/django/einvoice/factures-electroniques  [FactureElectroniqueSerializer]
    champs: certificat_ref, date_creation, facture_id, facture_ref, format, genere_le, hash_contenu, id, mode, signature_xml, signe_le, statut, version, xml_key
    format ∈ {cii, ubl}
    mode ∈ {dry_run, reel}
    statut ∈ {brouillon, genere, rejete, signe, transmis}
- frontend/src/api/einvoiceApi.js :: transmissions -> /api/django/einvoice/transmissions  [TransmissionDGISerializer]
    champs: date_creation, einvoice, id, prochaine_tentative, reponse_json, statut, tentatives
    statut ∈ {accepte, en_attente, envoye, rejete}
- frontend/src/api/fiscalApi.js :: echeances -> /api/django/fiscal/echeances  [EcheanceFiscaleSerializer]
    champs: date_creation, date_limite, declaration_id, declaration_type, id, obligation, periode_debut, periode_fin, rappel_envoye_le, statut
    statut ∈ {a_preparer, deposee, payee}
- frontend/src/api/fiscalApi.js :: veille -> /api/django/fiscal/veille  [VeilleReglementaireSerializer]
    champs: date_creation, date_effet, domaine, id, impact_traite, parametre_cible, resume, source_url, statut, titre
    domaine ∈ {cnss, einvoicing, environnement, ir, is, marches, tva}
    statut ∈ {lu, nouveau, traite}
- frontend/src/api/fpaApi.js :: createCommentaireVariance -> /api/django/fpa/commentaires-variance  [CommentaireVarianceSerializer]
    champs: auteur, auteur_nom, categorie, company, cree_le, cycle, departement, id, mois, texte
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: createCycle -> /api/django/fpa/cycles-budgetaires  [CycleBudgetaireSerializer]
    champs: company, date_creation, date_debut, date_fin, exercice_comptable_id, exercice_label, id, nom, statut, type_cycle
    statut ∈ {brouillon, clos, en_validation, ouvert_saisie}
    type_cycle ∈ {annuel, trimestriel}
- frontend/src/api/fpaApi.js :: createHypothese -> /api/django/fpa/hypotheses-recrutement  [HypotheseRecrutementSerializer]
    champs: company, date_creation, date_effet, departement, est_engage, id, poste, prevision_glissante, salaire_brut_estime, statut, type_mouvement
    statut ∈ {confirme, hypothese}
    type_mouvement ∈ {depart, embauche}
- frontend/src/api/fpaApi.js :: createLigneBudget -> /api/django/fpa/lignes-budget-departement  [LigneBudgetDepartementSerializer]
    champs: categorie, commentaire, company, cycle, date_modification, departement, id, mois, montant_prevu
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: createLigneScenario -> /api/django/fpa/lignes-scenario  [LigneScenarioSerializer]
    champs: categorie, company, delta_montant, delta_pct, id, ligne_budget, raison, scenario
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: createMapping -> /api/django/fpa/mapping-categories  [MappingCategorieCompteSerializer]
    champs: categorie, company, compte_cgnc_libelle, compte_cgnc_prefixe, id
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: createScenario -> /api/django/fpa/scenarios  [ScenarioBudgetaireSerializer]
    champs: company, cycle, date_creation, description, est_scenario_base, id, lignes, nom, statut
    statut ∈ {actif, archive, brouillon}
- frontend/src/api/fpaApi.js :: getCommentairesVariance -> /api/django/fpa/commentaires-variance  [CommentaireVarianceSerializer]
    champs: auteur, auteur_nom, categorie, company, cree_le, cycle, departement, id, mois, texte
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: getCycle -> /api/django/fpa/cycles-budgetaires/<>  [CycleBudgetaireSerializer]
    champs: company, date_creation, date_debut, date_fin, exercice_comptable_id, exercice_label, id, nom, statut, type_cycle
    statut ∈ {brouillon, clos, en_validation, ouvert_saisie}
    type_cycle ∈ {annuel, trimestriel}
- frontend/src/api/fpaApi.js :: getCycles -> /api/django/fpa/cycles-budgetaires  [CycleBudgetaireSerializer]
    champs: company, date_creation, date_debut, date_fin, exercice_comptable_id, exercice_label, id, nom, statut, type_cycle
    statut ∈ {brouillon, clos, en_validation, ouvert_saisie}
    type_cycle ∈ {annuel, trimestriel}
- frontend/src/api/fpaApi.js :: getHypotheses -> /api/django/fpa/hypotheses-recrutement  [HypotheseRecrutementSerializer]
    champs: company, date_creation, date_effet, departement, est_engage, id, poste, prevision_glissante, salaire_brut_estime, statut, type_mouvement
    statut ∈ {confirme, hypothese}
    type_mouvement ∈ {depart, embauche}
- frontend/src/api/fpaApi.js :: getLignesBudget -> /api/django/fpa/lignes-budget-departement  [LigneBudgetDepartementSerializer]
    champs: categorie, commentaire, company, cycle, date_modification, departement, id, mois, montant_prevu
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: getLignesScenario -> /api/django/fpa/lignes-scenario  [LigneScenarioSerializer]
    champs: categorie, company, delta_montant, delta_pct, id, ligne_budget, raison, scenario
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: getMappings -> /api/django/fpa/mapping-categories  [MappingCategorieCompteSerializer]
    champs: categorie, company, compte_cgnc_libelle, compte_cgnc_prefixe, id
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: getPrevision -> /api/django/fpa/previsions-glissantes/<>  [PrevisionGlissanteSerializer]
    champs: company, date_creation, date_modification, date_reference, departement, horizon_mois, id, lignes
- frontend/src/api/fpaApi.js :: getPrevisions -> /api/django/fpa/previsions-glissantes  [PrevisionGlissanteSerializer]
    champs: company, date_creation, date_modification, date_reference, departement, horizon_mois, id, lignes
- frontend/src/api/fpaApi.js :: getScenarios -> /api/django/fpa/scenarios  [ScenarioBudgetaireSerializer]
    champs: company, cycle, date_creation, description, est_scenario_base, id, lignes, nom, statut
    statut ∈ {actif, archive, brouillon}
- frontend/src/api/fpaApi.js :: getSoumissions -> /api/django/fpa/soumissions-budget  [SoumissionBudgetDepartementSerializer]
    champs: company, cycle, departement, id, motif_rejet, soumis_le, soumis_par, statut, valide_le, valide_par
    statut ∈ {en_saisie, rejete, soumis, valide}
- frontend/src/api/fpaApi.js :: updateHypothese -> /api/django/fpa/hypotheses-recrutement/<>  [HypotheseRecrutementSerializer]
    champs: company, date_creation, date_effet, departement, est_engage, id, poste, prevision_glissante, salaire_brut_estime, statut, type_mouvement
    statut ∈ {confirme, hypothese}
    type_mouvement ∈ {depart, embauche}
- frontend/src/api/fpaApi.js :: updateLigneBudget -> /api/django/fpa/lignes-budget-departement/<>  [LigneBudgetDepartementSerializer]
    champs: categorie, commentaire, company, cycle, date_modification, departement, id, mois, montant_prevu
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/fpaApi.js :: updateLignePrevision -> /api/django/fpa/lignes-prevision-glissante/<>  [LignePrevisionGlissanteSerializer]
    champs: categorie, company, id, mois_relatif, montant_prevu, prevision, source
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
    source ∈ {driver, manuel, statistique}
- frontend/src/api/fpaApi.js :: updateMapping -> /api/django/fpa/mapping-categories/<>  [MappingCategorieCompteSerializer]
    champs: categorie, company, compte_cgnc_libelle, compte_cgnc_prefixe, id
    categorie ∈ {autre, frais_generaux, investissement, it, marketing, masse_salariale}
- frontend/src/api/gedApi.js :: createAcl -> /api/django/ged/acls  [AclGedSerializer]
    champs: created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
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
    champs: actif, cabinet_cible, categorie, corps_html, created_at, created_by, created_by_nom, description, dossier_cible, id, nom, updated_at
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
    champs: created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
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
    champs: created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
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
    champs: actif, cabinet_cible, categorie, corps_html, created_at, created_by, created_by_nom, description, dossier_cible, id, nom, updated_at
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
- frontend/src/api/gedApi.js :: getVersions -> /api/django/ged/versions  [DocumentVersionSerializer]
    champs: checksum, created_at, document, file_key, filename, id, mime, restored_from, restored_from_version, size, uploaded_by, uploaded_by_nom, version
- frontend/src/api/gedApi.js :: getVues -> /api/django/ged/vues  [VueGedEnregistreeSerializer]
    champs: created_at, criteres, est_a_moi, id, nom, partagee, updated_at, utilisateur, utilisateur_nom
- frontend/src/api/gedApi.js :: renameDossier -> /api/django/ged/dossiers/<>  [FolderSerializer]
    champs: cabinet, cabinet_nom, created_at, id, nom, parent, parent_nom, path, updated_at
- frontend/src/api/gedApi.js :: setQuotaStockage -> /api/django/ged/quotas-stockage  [QuotaStockageSerializer]
    champs: created_at, depasse, id, quota_octets, updated_at, utilise_octets
- frontend/src/api/gedApi.js :: updateAcl -> /api/django/ged/acls/<>  [AclGedSerializer]
    champs: created_at, created_by, document, document_nom, folder, folder_nom, herite, id, niveau, role, role_nom, updated_at, utilisateur, utilisateur_nom
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
- frontend/src/api/gestionProjetApi.js :: createAction -> /api/django/gestion-projet/actions  [ActionProjetSerializer]
    champs: date_cloture, date_creation, description, echeance, id, libelle, priorite, priorite_display, projet, projet_code, responsable, risque, statut, statut_display
    priorite ∈ {basse, haute, moyenne}
    statut ∈ {a_faire, annule, en_cours, fait}
- frontend/src/api/gestionProjetApi.js :: createAffectation -> /api/django/gestion-projet/affectations  [AffectationRessourceSerializer]
    champs: actif_id, actif_type, charge_jours, date_creation, date_debut, date_fin, equipe, equipe_nom, id, note, publie_le, publie_par, quantite, ressource, ressource_nom, statut_publication, statut_publication_display, tache, tache_libelle
    actif_type ∈ {actif_flotte}
    statut_publication ∈ {brouillon, publie}
- frontend/src/api/gestionProjetApi.js :: createBudget -> /api/django/gestion-projet/budgets  [BudgetProjetSerializer]
    champs: date_creation, devise, id, libelle, projet, projet_code, statut, statut_display, total, version
    statut ∈ {archive, brouillon, valide}
- frontend/src/api/gestionProjetApi.js :: createCalendrier -> /api/django/gestion-projet/calendriers  [CalendrierProjetSerializer]
    champs: date_creation, dimanche, id, jeudi, jours_feries, lundi, mardi, mercredi, projet, projet_code, samedi, vendredi
- frontend/src/api/gestionProjetApi.js :: createChantier -> /api/django/gestion-projet/projet-chantiers  [ProjetChantierSerializer]
    champs: chantier_id, date_creation, id, libelle, projet, projet_code
- frontend/src/api/gestionProjetApi.js :: createCommentaire -> /api/django/gestion-projet/commentaires  [CommentaireProjetSerializer]
    champs: auteur, auteur_nom, cible_id, cible_type, cible_type_display, date_creation, id, mentions, projet, projet_code, texte
    cible_type ∈ {action, document, jalon, projet, risque, tache}
- frontend/src/api/gestionProjetApi.js :: createCompteRendu -> /api/django/gestion-projet/comptes-rendus  [CompteRenduReunionSerializer]
    champs: chantier_id, date_creation, date_prochaine_reunion, date_reunion, decisions, id, lieu, ordre_du_jour, participants, points_bloquants, projet, projet_code, redacteur, redacteur_nom, titre
- frontend/src/api/gestionProjetApi.js :: createDependance -> /api/django/gestion-projet/dependances  [DependanceTacheSerializer]
    champs: date_creation, id, lag, predecesseur, projet, successeur, type_dependance, type_dependance_display
    type_dependance ∈ {ff, fs, sf, ss}
- frontend/src/api/gestionProjetApi.js :: createDocument -> /api/django/gestion-projet/documents  [DocumentProjetSerializer]
    champs: date_creation, derniere_version, description, id, nom, projet, projet_code, type_doc, type_doc_display, versions
    type_doc ∈ {autre, contrat, note, photo, plan, pv}
- frontend/src/api/gestionProjetApi.js :: createEquipe -> /api/django/gestion-projet/equipes  [EquipeSerializer]
    champs: date_creation, description, id, membres, membres_detail, nom
- frontend/src/api/gestionProjetApi.js :: createIndisponibilite -> /api/django/gestion-projet/indisponibilites  [IndisponibiliteSerializer]
    champs: date_creation, date_debut, date_fin, id, motif, ressource, ressource_nom, type_indispo
    type_indispo ∈ {arret, conge, formation}
- frontend/src/api/gestionProjetApi.js :: createItemChecklist -> /api/django/gestion-projet/items-checklist  [ItemChecklistTacheSerializer]
    champs: date_creation, fait, fait_le, fait_par, fait_par_nom, id, libelle, ordre, tache
- frontend/src/api/gestionProjetApi.js :: createJalon -> /api/django/gestion-projet/jalons  [JalonSerializer]
    champs: date_creation, date_prevue, date_reelle, description, facturation_pct, id, libelle, phase, projet, projet_code, statut, statut_display, tache
    statut ∈ {a_venir, atteint, manque}
- frontend/src/api/gestionProjetApi.js :: createJourFerie -> /api/django/gestion-projet/jours-feries  [JourFerieSerializer]
    champs: calendrier, date, date_creation, id, libelle
- frontend/src/api/gestionProjetApi.js :: createLien -> /api/django/gestion-projet/projet-liens  [ProjetLienSerializer]
    champs: cible_id, date_creation, id, libelle, projet, projet_code, type_cible, type_cible_display
    type_cible ∈ {achat, devis, facture, ticket}
- frontend/src/api/gestionProjetApi.js :: createLigneBudget -> /api/django/gestion-projet/lignes-budget  [LigneBudgetProjetSerializer]
    champs: budget, categorie, categorie_display, date_creation, id, libelle, montant_prevu, pu, quantite
    categorie ∈ {divers, main_oeuvre, materiel, sous_traitance}
- frontend/src/api/gestionProjetApi.js :: createLotSousTraitance -> /api/django/gestion-projet/lots-sous-traitance  [LotSousTraitanceSerializer]
    champs: date_creation, date_debut, date_fin, description, id, libelle, montant, projet, projet_code, sous_traitant, sous_traitant_nom, statut, statut_display
    statut ∈ {annule, en_cours, prevu, receptionne}
- frontend/src/api/gestionProjetApi.js :: createModele -> /api/django/gestion-projet/modeles  [ModeleProjetSerializer]
    champs: actif, date_creation, description, id, nb_taches, nom, taches, type_installation, type_installation_display
    type_installation ∈ {agricole, autre, industriel, residentiel}
- frontend/src/api/gestionProjetApi.js :: createModeleTache -> /api/django/gestion-projet/modele-taches  [ModeleTacheSerializer]
    champs: charge_estimee, code_wbs, date_creation, id, libelle, modele, ordre, type_phase, type_phase_display
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: createPeriodeVerrouillee -> /api/django/gestion-projet/periodes-verrouillees-temps  [PeriodeVerrouilleeTempsSerializer]
    champs: date_creation, id, mois, verrouille_par, verrouille_par_nom
- frontend/src/api/gestionProjetApi.js :: createPhase -> /api/django/gestion-projet/phases  [PhaseProjetSerializer]
    champs: avancement_pct, date_creation, date_debut_prevue, date_debut_reelle, date_fin_prevue, date_fin_reelle, id, libelle, ordre, projet, projet_code, statut, statut_display, type_phase, type_phase_display
    statut ∈ {a_venir, en_cours, terminee}
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: createPointAvancement -> /api/django/gestion-projet/points-avancement  [PointAvancementSerializer]
    champs: auteur, auteur_nom, avancement_pct, date_creation, date_point, id, prochaines_etapes, projet, projet_code, realisations, risques, sante, sante_display
    sante ∈ {orange, rouge, vert}
- frontend/src/api/gestionProjetApi.js :: createPortailToken -> /api/django/gestion-projet/portail-tokens  [PortailProjetTokenSerializer]
    champs: actif, date_creation, id, projet, projet_code, token
- frontend/src/api/gestionProjetApi.js :: createProjet -> /api/django/gestion-projet/projets  [ProjetSerializer]
    champs: alias_email, budget_total, client_id, code, contrat_id, date_creation, date_debut, date_fin_prevue, delai_execution_jours, description, id, maitre_ouvrage, montant_marche, nom, numero_marche, plafond_penalite_pct, politique_facturation, politique_facturation_display, responsable, statut, statut_display, taux_penalite_retard
    politique_facturation ∈ {forfait, jalons, regie, situations}
    statut ∈ {annule, brouillon, en_cours, en_pause, planifie, termine}
- frontend/src/api/gestionProjetApi.js :: createRecurrenceTache -> /api/django/gestion-projet/recurrences-tache  [RecurrenceTacheSerializer]
    champs: actif, assigne, charge_estimee, date_creation, date_fin, id, intervalle, libelle, nb_generees, nb_occurrences, phase, prochaine_echeance, projet, projet_code, regle, regle_display
    regle ∈ {hebdomadaire, mensuelle}
- frontend/src/api/gestionProjetApi.js :: createRessource -> /api/django/gestion-projet/ressources  [RessourceProfilSerializer]
    champs: actif, competences, cout_horaire, date_creation, id, nom, role, user
- frontend/src/api/gestionProjetApi.js :: createRisque -> /api/django/gestion-projet/risques  [RisqueSerializer]
    champs: categorie, categorie_display, criticite, date_creation, description, id, impact, libelle, mitigation, probabilite, projet, projet_code, proprietaire, statut, statut_display
    categorie ∈ {autre, cout, delai, fournisseur, reglementaire, securite, technique}
    statut ∈ {clos, maitrise, ouvert, surveille}
- frontend/src/api/gestionProjetApi.js :: createSituation -> /api/django/gestion-projet/situations  [SituationTravauxSerializer]
    champs: contrat_id, date_creation, date_validation, facture_id, id, montant_periode_total, numero, periode, projet, projet_code, retenue_garantie_pct, statut, statut_display
    statut ∈ {brouillon, facturee, validee}
- frontend/src/api/gestionProjetApi.js :: createSousTraitant -> /api/django/gestion-projet/sous-traitants  [SousTraitantSerializer]
    champs: actif, contact, date_creation, email, id, nom, specialite, telephone
- frontend/src/api/gestionProjetApi.js :: createTache -> /api/django/gestion-projet/taches  [TacheSerializer]
    champs: assigne, assigne_nom, avancement_pct, charge_estimee, code_wbs, date_creation, date_debut_prevue, date_fin_prevue, date_fin_reelle, description, etiquettes, id, libelle, nb_sous_taches, ordre, parent, pct_checklist_fait, phase, priorite, priorite_display, projet, projet_code, statut, statut_display, ticket_sav_id
    priorite ∈ {basse, haute, normale, urgente}
    statut ∈ {a_faire, bloque, en_cours, termine}
- frontend/src/api/gestionProjetApi.js :: deleteAction -> /api/django/gestion-projet/actions/<>  [ActionProjetSerializer]
    champs: date_cloture, date_creation, description, echeance, id, libelle, priorite, priorite_display, projet, projet_code, responsable, risque, statut, statut_display
    priorite ∈ {basse, haute, moyenne}
    statut ∈ {a_faire, annule, en_cours, fait}
- frontend/src/api/gestionProjetApi.js :: deleteAffectation -> /api/django/gestion-projet/affectations/<>  [AffectationRessourceSerializer]
    champs: actif_id, actif_type, charge_jours, date_creation, date_debut, date_fin, equipe, equipe_nom, id, note, publie_le, publie_par, quantite, ressource, ressource_nom, statut_publication, statut_publication_display, tache, tache_libelle
    actif_type ∈ {actif_flotte}
    statut_publication ∈ {brouillon, publie}
- frontend/src/api/gestionProjetApi.js :: deleteBudget -> /api/django/gestion-projet/budgets/<>  [BudgetProjetSerializer]
    champs: date_creation, devise, id, libelle, projet, projet_code, statut, statut_display, total, version
    statut ∈ {archive, brouillon, valide}
- frontend/src/api/gestionProjetApi.js :: deleteChantier -> /api/django/gestion-projet/projet-chantiers/<>  [ProjetChantierSerializer]
    champs: chantier_id, date_creation, id, libelle, projet, projet_code
- frontend/src/api/gestionProjetApi.js :: deleteCommentaire -> /api/django/gestion-projet/commentaires/<>  [CommentaireProjetSerializer]
    champs: auteur, auteur_nom, cible_id, cible_type, cible_type_display, date_creation, id, mentions, projet, projet_code, texte
    cible_type ∈ {action, document, jalon, projet, risque, tache}
- frontend/src/api/gestionProjetApi.js :: deleteCompteRendu -> /api/django/gestion-projet/comptes-rendus/<>  [CompteRenduReunionSerializer]
    champs: chantier_id, date_creation, date_prochaine_reunion, date_reunion, decisions, id, lieu, ordre_du_jour, participants, points_bloquants, projet, projet_code, redacteur, redacteur_nom, titre
- frontend/src/api/gestionProjetApi.js :: deleteDependance -> /api/django/gestion-projet/dependances/<>  [DependanceTacheSerializer]
    champs: date_creation, id, lag, predecesseur, projet, successeur, type_dependance, type_dependance_display
    type_dependance ∈ {ff, fs, sf, ss}
- frontend/src/api/gestionProjetApi.js :: deleteDocument -> /api/django/gestion-projet/documents/<>  [DocumentProjetSerializer]
    champs: date_creation, derniere_version, description, id, nom, projet, projet_code, type_doc, type_doc_display, versions
    type_doc ∈ {autre, contrat, note, photo, plan, pv}
- frontend/src/api/gestionProjetApi.js :: deleteEquipe -> /api/django/gestion-projet/equipes/<>  [EquipeSerializer]
    champs: date_creation, description, id, membres, membres_detail, nom
- frontend/src/api/gestionProjetApi.js :: deleteIndisponibilite -> /api/django/gestion-projet/indisponibilites/<>  [IndisponibiliteSerializer]
    champs: date_creation, date_debut, date_fin, id, motif, ressource, ressource_nom, type_indispo
    type_indispo ∈ {arret, conge, formation}
- frontend/src/api/gestionProjetApi.js :: deleteItemChecklist -> /api/django/gestion-projet/items-checklist/<>  [ItemChecklistTacheSerializer]
    champs: date_creation, fait, fait_le, fait_par, fait_par_nom, id, libelle, ordre, tache
- frontend/src/api/gestionProjetApi.js :: deleteJalon -> /api/django/gestion-projet/jalons/<>  [JalonSerializer]
    champs: date_creation, date_prevue, date_reelle, description, facturation_pct, id, libelle, phase, projet, projet_code, statut, statut_display, tache
    statut ∈ {a_venir, atteint, manque}
- frontend/src/api/gestionProjetApi.js :: deleteJourFerie -> /api/django/gestion-projet/jours-feries/<>  [JourFerieSerializer]
    champs: calendrier, date, date_creation, id, libelle
- frontend/src/api/gestionProjetApi.js :: deleteLien -> /api/django/gestion-projet/projet-liens/<>  [ProjetLienSerializer]
    champs: cible_id, date_creation, id, libelle, projet, projet_code, type_cible, type_cible_display
    type_cible ∈ {achat, devis, facture, ticket}
- frontend/src/api/gestionProjetApi.js :: deleteLigneBudget -> /api/django/gestion-projet/lignes-budget/<>  [LigneBudgetProjetSerializer]
    champs: budget, categorie, categorie_display, date_creation, id, libelle, montant_prevu, pu, quantite
    categorie ∈ {divers, main_oeuvre, materiel, sous_traitance}
- frontend/src/api/gestionProjetApi.js :: deleteLotSousTraitance -> /api/django/gestion-projet/lots-sous-traitance/<>  [LotSousTraitanceSerializer]
    champs: date_creation, date_debut, date_fin, description, id, libelle, montant, projet, projet_code, sous_traitant, sous_traitant_nom, statut, statut_display
    statut ∈ {annule, en_cours, prevu, receptionne}
- frontend/src/api/gestionProjetApi.js :: deleteModele -> /api/django/gestion-projet/modeles/<>  [ModeleProjetSerializer]
    champs: actif, date_creation, description, id, nb_taches, nom, taches, type_installation, type_installation_display
    type_installation ∈ {agricole, autre, industriel, residentiel}
- frontend/src/api/gestionProjetApi.js :: deleteModeleTache -> /api/django/gestion-projet/modele-taches/<>  [ModeleTacheSerializer]
    champs: charge_estimee, code_wbs, date_creation, id, libelle, modele, ordre, type_phase, type_phase_display
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: deletePeriodeVerrouillee -> /api/django/gestion-projet/periodes-verrouillees-temps/<>  [PeriodeVerrouilleeTempsSerializer]
    champs: date_creation, id, mois, verrouille_par, verrouille_par_nom
- frontend/src/api/gestionProjetApi.js :: deletePhase -> /api/django/gestion-projet/phases/<>  [PhaseProjetSerializer]
    champs: avancement_pct, date_creation, date_debut_prevue, date_debut_reelle, date_fin_prevue, date_fin_reelle, id, libelle, ordre, projet, projet_code, statut, statut_display, type_phase, type_phase_display
    statut ∈ {a_venir, en_cours, terminee}
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: deleteProjet -> /api/django/gestion-projet/projets/<>  [ProjetSerializer]
    champs: alias_email, budget_total, client_id, code, contrat_id, date_creation, date_debut, date_fin_prevue, delai_execution_jours, description, id, maitre_ouvrage, montant_marche, nom, numero_marche, plafond_penalite_pct, politique_facturation, politique_facturation_display, responsable, statut, statut_display, taux_penalite_retard
    politique_facturation ∈ {forfait, jalons, regie, situations}
    statut ∈ {annule, brouillon, en_cours, en_pause, planifie, termine}
- frontend/src/api/gestionProjetApi.js :: deleteRecurrenceTache -> /api/django/gestion-projet/recurrences-tache/<>  [RecurrenceTacheSerializer]
    champs: actif, assigne, charge_estimee, date_creation, date_fin, id, intervalle, libelle, nb_generees, nb_occurrences, phase, prochaine_echeance, projet, projet_code, regle, regle_display
    regle ∈ {hebdomadaire, mensuelle}
- frontend/src/api/gestionProjetApi.js :: deleteRessource -> /api/django/gestion-projet/ressources/<>  [RessourceProfilSerializer]
    champs: actif, competences, cout_horaire, date_creation, id, nom, role, user
- frontend/src/api/gestionProjetApi.js :: deleteRisque -> /api/django/gestion-projet/risques/<>  [RisqueSerializer]
    champs: categorie, categorie_display, criticite, date_creation, description, id, impact, libelle, mitigation, probabilite, projet, projet_code, proprietaire, statut, statut_display
    categorie ∈ {autre, cout, delai, fournisseur, reglementaire, securite, technique}
    statut ∈ {clos, maitrise, ouvert, surveille}
- frontend/src/api/gestionProjetApi.js :: deleteSousTraitant -> /api/django/gestion-projet/sous-traitants/<>  [SousTraitantSerializer]
    champs: actif, contact, date_creation, email, id, nom, specialite, telephone
- frontend/src/api/gestionProjetApi.js :: deleteTache -> /api/django/gestion-projet/taches/<>  [TacheSerializer]
    champs: assigne, assigne_nom, avancement_pct, charge_estimee, code_wbs, date_creation, date_debut_prevue, date_fin_prevue, date_fin_reelle, description, etiquettes, id, libelle, nb_sous_taches, ordre, parent, pct_checklist_fait, phase, priorite, priorite_display, projet, projet_code, statut, statut_display, ticket_sav_id
    priorite ∈ {basse, haute, normale, urgente}
    statut ∈ {a_faire, bloque, en_cours, termine}
- frontend/src/api/gestionProjetApi.js :: getActions -> /api/django/gestion-projet/actions  [ActionProjetSerializer]
    champs: date_cloture, date_creation, description, echeance, id, libelle, priorite, priorite_display, projet, projet_code, responsable, risque, statut, statut_display
    priorite ∈ {basse, haute, moyenne}
    statut ∈ {a_faire, annule, en_cours, fait}
- frontend/src/api/gestionProjetApi.js :: getAffectations -> /api/django/gestion-projet/affectations  [AffectationRessourceSerializer]
    champs: actif_id, actif_type, charge_jours, date_creation, date_debut, date_fin, equipe, equipe_nom, id, note, publie_le, publie_par, quantite, ressource, ressource_nom, statut_publication, statut_publication_display, tache, tache_libelle
    actif_type ∈ {actif_flotte}
    statut_publication ∈ {brouillon, publie}
- frontend/src/api/gestionProjetApi.js :: getBaselines -> /api/django/gestion-projet/baselines  [BaselinePlanningSerializer]
    champs: auteur, auteur_nom, date_creation, id, libelle, nb_lignes, projet, projet_code
- frontend/src/api/gestionProjetApi.js :: getBudgets -> /api/django/gestion-projet/budgets  [BudgetProjetSerializer]
    champs: date_creation, devise, id, libelle, projet, projet_code, statut, statut_display, total, version
    statut ∈ {archive, brouillon, valide}
- frontend/src/api/gestionProjetApi.js :: getCalendriers -> /api/django/gestion-projet/calendriers  [CalendrierProjetSerializer]
    champs: date_creation, dimanche, id, jeudi, jours_feries, lundi, mardi, mercredi, projet, projet_code, samedi, vendredi
- frontend/src/api/gestionProjetApi.js :: getChantiers -> /api/django/gestion-projet/projet-chantiers  [ProjetChantierSerializer]
    champs: chantier_id, date_creation, id, libelle, projet, projet_code
- frontend/src/api/gestionProjetApi.js :: getClotures -> /api/django/gestion-projet/clotures  [ClotureProjetSerializer]
    champs: cloture_par, cloture_par_nom, date_cloture, date_creation, date_reception, id, points_amelioration, points_positifs, projet, projet_code, recommandations
- frontend/src/api/gestionProjetApi.js :: getCommentaires -> /api/django/gestion-projet/commentaires  [CommentaireProjetSerializer]
    champs: auteur, auteur_nom, cible_id, cible_type, cible_type_display, date_creation, id, mentions, projet, projet_code, texte
    cible_type ∈ {action, document, jalon, projet, risque, tache}
- frontend/src/api/gestionProjetApi.js :: getComptesRendus -> /api/django/gestion-projet/comptes-rendus  [CompteRenduReunionSerializer]
    champs: chantier_id, date_creation, date_prochaine_reunion, date_reunion, decisions, id, lieu, ordre_du_jour, participants, points_bloquants, projet, projet_code, redacteur, redacteur_nom, titre
- frontend/src/api/gestionProjetApi.js :: getDependances -> /api/django/gestion-projet/dependances  [DependanceTacheSerializer]
    champs: date_creation, id, lag, predecesseur, projet, successeur, type_dependance, type_dependance_display
    type_dependance ∈ {ff, fs, sf, ss}
- frontend/src/api/gestionProjetApi.js :: getDocuments -> /api/django/gestion-projet/documents  [DocumentProjetSerializer]
    champs: date_creation, derniere_version, description, id, nom, projet, projet_code, type_doc, type_doc_display, versions
    type_doc ∈ {autre, contrat, note, photo, plan, pv}
- frontend/src/api/gestionProjetApi.js :: getEquipes -> /api/django/gestion-projet/equipes  [EquipeSerializer]
    champs: date_creation, description, id, membres, membres_detail, nom
- frontend/src/api/gestionProjetApi.js :: getIndisponibilites -> /api/django/gestion-projet/indisponibilites  [IndisponibiliteSerializer]
    champs: date_creation, date_debut, date_fin, id, motif, ressource, ressource_nom, type_indispo
    type_indispo ∈ {arret, conge, formation}
- frontend/src/api/gestionProjetApi.js :: getItemsChecklist -> /api/django/gestion-projet/items-checklist  [ItemChecklistTacheSerializer]
    champs: date_creation, fait, fait_le, fait_par, fait_par_nom, id, libelle, ordre, tache
- frontend/src/api/gestionProjetApi.js :: getJalons -> /api/django/gestion-projet/jalons  [JalonSerializer]
    champs: date_creation, date_prevue, date_reelle, description, facturation_pct, id, libelle, phase, projet, projet_code, statut, statut_display, tache
    statut ∈ {a_venir, atteint, manque}
- frontend/src/api/gestionProjetApi.js :: getJoursFeries -> /api/django/gestion-projet/jours-feries  [JourFerieSerializer]
    champs: calendrier, date, date_creation, id, libelle
- frontend/src/api/gestionProjetApi.js :: getLiens -> /api/django/gestion-projet/projet-liens  [ProjetLienSerializer]
    champs: cible_id, date_creation, id, libelle, projet, projet_code, type_cible, type_cible_display
    type_cible ∈ {achat, devis, facture, ticket}
- frontend/src/api/gestionProjetApi.js :: getLignesBudget -> /api/django/gestion-projet/lignes-budget  [LigneBudgetProjetSerializer]
    champs: budget, categorie, categorie_display, date_creation, id, libelle, montant_prevu, pu, quantite
    categorie ∈ {divers, main_oeuvre, materiel, sous_traitance}
- frontend/src/api/gestionProjetApi.js :: getLignesSituation -> /api/django/gestion-projet/lignes-situation  [LigneSituationSerializer]
    champs: avancement_cumule_pct, date_creation, id, libelle, montant_cumule, montant_cumule_anterieur, montant_marche_ht, montant_periode, situation
- frontend/src/api/gestionProjetApi.js :: getLotsSousTraitance -> /api/django/gestion-projet/lots-sous-traitance  [LotSousTraitanceSerializer]
    champs: date_creation, date_debut, date_fin, description, id, libelle, montant, projet, projet_code, sous_traitant, sous_traitant_nom, statut, statut_display
    statut ∈ {annule, en_cours, prevu, receptionne}
- frontend/src/api/gestionProjetApi.js :: getModeleTaches -> /api/django/gestion-projet/modele-taches  [ModeleTacheSerializer]
    champs: charge_estimee, code_wbs, date_creation, id, libelle, modele, ordre, type_phase, type_phase_display
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: getModeles -> /api/django/gestion-projet/modeles  [ModeleProjetSerializer]
    champs: actif, date_creation, description, id, nb_taches, nom, taches, type_installation, type_installation_display
    type_installation ∈ {agricole, autre, industriel, residentiel}
- frontend/src/api/gestionProjetApi.js :: getPeriodesVerrouillees -> /api/django/gestion-projet/periodes-verrouillees-temps  [PeriodeVerrouilleeTempsSerializer]
    champs: date_creation, id, mois, verrouille_par, verrouille_par_nom
- frontend/src/api/gestionProjetApi.js :: getPhases -> /api/django/gestion-projet/phases  [PhaseProjetSerializer]
    champs: avancement_pct, date_creation, date_debut_prevue, date_debut_reelle, date_fin_prevue, date_fin_reelle, id, libelle, ordre, projet, projet_code, statut, statut_display, type_phase, type_phase_display
    statut ∈ {a_venir, en_cours, terminee}
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: getPointsAvancement -> /api/django/gestion-projet/points-avancement  [PointAvancementSerializer]
    champs: auteur, auteur_nom, avancement_pct, date_creation, date_point, id, prochaines_etapes, projet, projet_code, realisations, risques, sante, sante_display
    sante ∈ {orange, rouge, vert}
- frontend/src/api/gestionProjetApi.js :: getPortailTokens -> /api/django/gestion-projet/portail-tokens  [PortailProjetTokenSerializer]
    champs: actif, date_creation, id, projet, projet_code, token
- frontend/src/api/gestionProjetApi.js :: getProjet -> /api/django/gestion-projet/projets/<>  [ProjetSerializer]
    champs: alias_email, budget_total, client_id, code, contrat_id, date_creation, date_debut, date_fin_prevue, delai_execution_jours, description, id, maitre_ouvrage, montant_marche, nom, numero_marche, plafond_penalite_pct, politique_facturation, politique_facturation_display, responsable, statut, statut_display, taux_penalite_retard
    politique_facturation ∈ {forfait, jalons, regie, situations}
    statut ∈ {annule, brouillon, en_cours, en_pause, planifie, termine}
- frontend/src/api/gestionProjetApi.js :: getProjets -> /api/django/gestion-projet/projets  [ProjetSerializer]
    champs: alias_email, budget_total, client_id, code, contrat_id, date_creation, date_debut, date_fin_prevue, delai_execution_jours, description, id, maitre_ouvrage, montant_marche, nom, numero_marche, plafond_penalite_pct, politique_facturation, politique_facturation_display, responsable, statut, statut_display, taux_penalite_retard
    politique_facturation ∈ {forfait, jalons, regie, situations}
    statut ∈ {annule, brouillon, en_cours, en_pause, planifie, termine}
- frontend/src/api/gestionProjetApi.js :: getRecurrencesTache -> /api/django/gestion-projet/recurrences-tache  [RecurrenceTacheSerializer]
    champs: actif, assigne, charge_estimee, date_creation, date_fin, id, intervalle, libelle, nb_generees, nb_occurrences, phase, prochaine_echeance, projet, projet_code, regle, regle_display
    regle ∈ {hebdomadaire, mensuelle}
- frontend/src/api/gestionProjetApi.js :: getRessources -> /api/django/gestion-projet/ressources  [RessourceProfilSerializer]
    champs: actif, competences, cout_horaire, date_creation, id, nom, role, user
- frontend/src/api/gestionProjetApi.js :: getRisques -> /api/django/gestion-projet/risques  [RisqueSerializer]
    champs: categorie, categorie_display, criticite, date_creation, description, id, impact, libelle, mitigation, probabilite, projet, projet_code, proprietaire, statut, statut_display
    categorie ∈ {autre, cout, delai, fournisseur, reglementaire, securite, technique}
    statut ∈ {clos, maitrise, ouvert, surveille}
- frontend/src/api/gestionProjetApi.js :: getSituations -> /api/django/gestion-projet/situations  [SituationTravauxSerializer]
    champs: contrat_id, date_creation, date_validation, facture_id, id, montant_periode_total, numero, periode, projet, projet_code, retenue_garantie_pct, statut, statut_display
    statut ∈ {brouillon, facturee, validee}
- frontend/src/api/gestionProjetApi.js :: getSousTraitants -> /api/django/gestion-projet/sous-traitants  [SousTraitantSerializer]
    champs: actif, contact, date_creation, email, id, nom, specialite, telephone
- frontend/src/api/gestionProjetApi.js :: getTaches -> /api/django/gestion-projet/taches  [TacheSerializer]
    champs: assigne, assigne_nom, avancement_pct, charge_estimee, code_wbs, date_creation, date_debut_prevue, date_fin_prevue, date_fin_reelle, description, etiquettes, id, libelle, nb_sous_taches, ordre, parent, pct_checklist_fait, phase, priorite, priorite_display, projet, projet_code, statut, statut_display, ticket_sav_id
    priorite ∈ {basse, haute, normale, urgente}
    statut ∈ {a_faire, bloque, en_cours, termine}
- frontend/src/api/gestionProjetApi.js :: updateAction -> /api/django/gestion-projet/actions/<>  [ActionProjetSerializer]
    champs: date_cloture, date_creation, description, echeance, id, libelle, priorite, priorite_display, projet, projet_code, responsable, risque, statut, statut_display
    priorite ∈ {basse, haute, moyenne}
    statut ∈ {a_faire, annule, en_cours, fait}
- frontend/src/api/gestionProjetApi.js :: updateAffectation -> /api/django/gestion-projet/affectations/<>  [AffectationRessourceSerializer]
    champs: actif_id, actif_type, charge_jours, date_creation, date_debut, date_fin, equipe, equipe_nom, id, note, publie_le, publie_par, quantite, ressource, ressource_nom, statut_publication, statut_publication_display, tache, tache_libelle
    actif_type ∈ {actif_flotte}
    statut_publication ∈ {brouillon, publie}
- frontend/src/api/gestionProjetApi.js :: updateBudget -> /api/django/gestion-projet/budgets/<>  [BudgetProjetSerializer]
    champs: date_creation, devise, id, libelle, projet, projet_code, statut, statut_display, total, version
    statut ∈ {archive, brouillon, valide}
- frontend/src/api/gestionProjetApi.js :: updateCalendrier -> /api/django/gestion-projet/calendriers/<>  [CalendrierProjetSerializer]
    champs: date_creation, dimanche, id, jeudi, jours_feries, lundi, mardi, mercredi, projet, projet_code, samedi, vendredi
- frontend/src/api/gestionProjetApi.js :: updateChantier -> /api/django/gestion-projet/projet-chantiers/<>  [ProjetChantierSerializer]
    champs: chantier_id, date_creation, id, libelle, projet, projet_code
- frontend/src/api/gestionProjetApi.js :: updateCloture -> /api/django/gestion-projet/clotures/<>  [ClotureProjetSerializer]
    champs: cloture_par, cloture_par_nom, date_cloture, date_creation, date_reception, id, points_amelioration, points_positifs, projet, projet_code, recommandations
- frontend/src/api/gestionProjetApi.js :: updateCompteRendu -> /api/django/gestion-projet/comptes-rendus/<>  [CompteRenduReunionSerializer]
    champs: chantier_id, date_creation, date_prochaine_reunion, date_reunion, decisions, id, lieu, ordre_du_jour, participants, points_bloquants, projet, projet_code, redacteur, redacteur_nom, titre
- frontend/src/api/gestionProjetApi.js :: updateEquipe -> /api/django/gestion-projet/equipes/<>  [EquipeSerializer]
    champs: date_creation, description, id, membres, membres_detail, nom
- frontend/src/api/gestionProjetApi.js :: updateJalon -> /api/django/gestion-projet/jalons/<>  [JalonSerializer]
    champs: date_creation, date_prevue, date_reelle, description, facturation_pct, id, libelle, phase, projet, projet_code, statut, statut_display, tache
    statut ∈ {a_venir, atteint, manque}
- frontend/src/api/gestionProjetApi.js :: updateLien -> /api/django/gestion-projet/projet-liens/<>  [ProjetLienSerializer]
    champs: cible_id, date_creation, id, libelle, projet, projet_code, type_cible, type_cible_display
    type_cible ∈ {achat, devis, facture, ticket}
- frontend/src/api/gestionProjetApi.js :: updateLigneBudget -> /api/django/gestion-projet/lignes-budget/<>  [LigneBudgetProjetSerializer]
    champs: budget, categorie, categorie_display, date_creation, id, libelle, montant_prevu, pu, quantite
    categorie ∈ {divers, main_oeuvre, materiel, sous_traitance}
- frontend/src/api/gestionProjetApi.js :: updateLotSousTraitance -> /api/django/gestion-projet/lots-sous-traitance/<>  [LotSousTraitanceSerializer]
    champs: date_creation, date_debut, date_fin, description, id, libelle, montant, projet, projet_code, sous_traitant, sous_traitant_nom, statut, statut_display
    statut ∈ {annule, en_cours, prevu, receptionne}
- frontend/src/api/gestionProjetApi.js :: updateModele -> /api/django/gestion-projet/modeles/<>  [ModeleProjetSerializer]
    champs: actif, date_creation, description, id, nb_taches, nom, taches, type_installation, type_installation_display
    type_installation ∈ {agricole, autre, industriel, residentiel}
- frontend/src/api/gestionProjetApi.js :: updatePhase -> /api/django/gestion-projet/phases/<>  [PhaseProjetSerializer]
    champs: avancement_pct, date_creation, date_debut_prevue, date_debut_reelle, date_fin_prevue, date_fin_reelle, id, libelle, ordre, projet, projet_code, statut, statut_display, type_phase, type_phase_display
    statut ∈ {a_venir, en_cours, terminee}
    type_phase ∈ {appro, etude, mes, pose, reception}
- frontend/src/api/gestionProjetApi.js :: updatePortailToken -> /api/django/gestion-projet/portail-tokens/<>  [PortailProjetTokenSerializer]
    champs: actif, date_creation, id, projet, projet_code, token
- frontend/src/api/gestionProjetApi.js :: updateProjet -> /api/django/gestion-projet/projets/<>  [ProjetSerializer]
    champs: alias_email, budget_total, client_id, code, contrat_id, date_creation, date_debut, date_fin_prevue, delai_execution_jours, description, id, maitre_ouvrage, montant_marche, nom, numero_marche, plafond_penalite_pct, politique_facturation, politique_facturation_display, responsable, statut, statut_display, taux_penalite_retard
    politique_facturation ∈ {forfait, jalons, regie, situations}
    statut ∈ {annule, brouillon, en_cours, en_pause, planifie, termine}
- frontend/src/api/gestionProjetApi.js :: updateRessource -> /api/django/gestion-projet/ressources/<>  [RessourceProfilSerializer]
    champs: actif, competences, cout_horaire, date_creation, id, nom, role, user
- frontend/src/api/gestionProjetApi.js :: updateRisque -> /api/django/gestion-projet/risques/<>  [RisqueSerializer]
    champs: categorie, categorie_display, criticite, date_creation, description, id, impact, libelle, mitigation, probabilite, projet, projet_code, proprietaire, statut, statut_display
    categorie ∈ {autre, cout, delai, fournisseur, reglementaire, securite, technique}
    statut ∈ {clos, maitrise, ouvert, surveille}
- frontend/src/api/gestionProjetApi.js :: updateSousTraitant -> /api/django/gestion-projet/sous-traitants/<>  [SousTraitantSerializer]
    champs: actif, contact, date_creation, email, id, nom, specialite, telephone
- frontend/src/api/gestionProjetApi.js :: updateTache -> /api/django/gestion-projet/taches/<>  [TacheSerializer]
    champs: assigne, assigne_nom, avancement_pct, charge_estimee, code_wbs, date_creation, date_debut_prevue, date_fin_prevue, date_fin_reelle, description, etiquettes, id, libelle, nb_sous_taches, ordre, parent, pct_checklist_fait, phase, priorite, priorite_display, projet, projet_code, statut, statut_display, ticket_sav_id
    priorite ∈ {basse, haute, normale, urgente}
    statut ∈ {a_faire, bloque, en_cours, termine}
- frontend/src/api/hospitalityApi.js :: createChambre -> /api/django/hospitality/chambres  [ChambreSerializer]
    champs: etage, id, nom, numero, statut, statut_display, type_chambre, type_chambre_libelle, vue
    statut ∈ {en_nettoyage, hors_service, libre, occupee, sale}
- frontend/src/api/hospitalityApi.js :: createMainCourante -> /api/django/hospitality/main-courante  [MainCouranteSerializer]
    champs: auteur, auteur_nom, categorie, categorie_display, cible_id, cible_type, date_note, id, texte
    categorie ∈ {autre, consigne, finance, incident, reservation}
- frontend/src/api/hospitalityApi.js :: createPlanTarifaire -> /api/django/hospitality/plans-tarifaires  [PlanTarifaireSerializer]
    champs: canal, canal_display, date_debut, date_fin, id, min_nuits, prix_nuit_ht, type_chambre
    canal ∈ {corporate, ota, rack}
- frontend/src/api/hospitalityApi.js :: createRecette -> /api/django/hospitality/recettes  [RecetteSerializer]
    champs: allergenes, categorie_menu, categorie_menu_display, description, id, ingredients, nom_plat, prix_vente_ht
    categorie_menu ∈ {boisson, dessert, entree, plat}
- frontend/src/api/hospitalityApi.js :: createSalleEvenement -> /api/django/hospitality/salles-evenement  [SalleEvenementSerializer]
    champs: capacite_max, description, id, nom, tarif_location_ht, types_amenagement_disponibles
- frontend/src/api/hospitalityApi.js :: createTypeChambre -> /api/django/hospitality/types-chambre  [TypeChambreSerializer]
    champs: capacite_max, description, id, libelle
- frontend/src/api/hospitalityApi.js :: getChambre -> /api/django/hospitality/chambres/<>  [ChambreSerializer]
    champs: etage, id, nom, numero, statut, statut_display, type_chambre, type_chambre_libelle, vue
    statut ∈ {en_nettoyage, hors_service, libre, occupee, sale}
- frontend/src/api/hospitalityApi.js :: getFolio -> /api/django/hospitality/folios/<>  [FolioSerializer]
    champs: date_cloture, date_creation, facture_id, id, lignes, reservation, statut, statut_display, total_ht
    statut ∈ {ouvert, solde}
- frontend/src/api/hospitalityApi.js :: listChambres -> /api/django/hospitality/chambres  [ChambreSerializer]
    champs: etage, id, nom, numero, statut, statut_display, type_chambre, type_chambre_libelle, vue
    statut ∈ {en_nettoyage, hors_service, libre, occupee, sale}
- frontend/src/api/hospitalityApi.js :: listMainCourante -> /api/django/hospitality/main-courante  [MainCouranteSerializer]
    champs: auteur, auteur_nom, categorie, categorie_display, cible_id, cible_type, date_note, id, texte
    categorie ∈ {autre, consigne, finance, incident, reservation}
- frontend/src/api/hospitalityApi.js :: listPlansTarifaires -> /api/django/hospitality/plans-tarifaires  [PlanTarifaireSerializer]
    champs: canal, canal_display, date_debut, date_fin, id, min_nuits, prix_nuit_ht, type_chambre
    canal ∈ {corporate, ota, rack}
- frontend/src/api/hospitalityApi.js :: listRecettes -> /api/django/hospitality/recettes  [RecetteSerializer]
    champs: allergenes, categorie_menu, categorie_menu_display, description, id, ingredients, nom_plat, prix_vente_ht
    categorie_menu ∈ {boisson, dessert, entree, plat}
- frontend/src/api/hospitalityApi.js :: listSallesEvenement -> /api/django/hospitality/salles-evenement  [SalleEvenementSerializer]
    champs: capacite_max, description, id, nom, tarif_location_ht, types_amenagement_disponibles
- frontend/src/api/hospitalityApi.js :: listTachesMenage -> /api/django/hospitality/taches-menage  [TacheMenageSerializer]
    champs: assignee, chambre, chambre_numero, date_completion, date_creation, id, statut, statut_display, type_tache, type_tache_display
    statut ∈ {a_faire, en_cours, terminee}
    type_tache ∈ {depart, nettoyage_complet, recouche}
- frontend/src/api/hospitalityApi.js :: listTypesChambre -> /api/django/hospitality/types-chambre  [TypeChambreSerializer]
    champs: capacite_max, description, id, libelle
- frontend/src/api/hospitalityApi.js :: updateChambre -> /api/django/hospitality/chambres/<>  [ChambreSerializer]
    champs: etage, id, nom, numero, statut, statut_display, type_chambre, type_chambre_libelle, vue
    statut ∈ {en_nettoyage, hors_service, libre, occupee, sale}
- frontend/src/api/hospitalityApi.js :: updateRecette -> /api/django/hospitality/recettes/<>  [RecetteSerializer]
    champs: allergenes, categorie_menu, categorie_menu_display, description, id, ingredients, nom_plat, prix_vente_ht
    categorie_menu ∈ {boisson, dessert, entree, plat}
- frontend/src/api/identityApi.js :: forget -> /api/django/identity/trusted-devices/<>  [TrustedDeviceSerializer]
    champs: approuve_le, expire_le, id, is_active, label, revoque_le
- frontend/src/api/innovationApi.js :: retirerVote -> /api/django/innovation/votes/<>  [VoteIdeeSerializer]
    champs: date, id, idee, votant, votant_nom
- frontend/src/api/innovationApi.js :: vote -> /api/django/innovation/votes  [VoteIdeeSerializer]
    champs: date, id, idee, votant, votant_nom
- frontend/src/api/installationsApi.js :: createAstreinte -> /api/django/installations/astreintes  [AstreinteSerializer]
    champs: created_by, date_creation, date_debut, date_fin, id, technicien, technicien_nom, telephone_astreinte
- frontend/src/api/installationsApi.js :: createAttestationSousTraitant -> /api/django/installations/attestations-sous-traitant  [AttestationSousTraitantSerializer]
    champs: created_by, date_creation, date_emission, date_expiration, date_modification, est_valide, id, note, obligatoire, organisme, reference, sous_traitant, sous_traitant_nom, type_piece, type_piece_display
    type_piece ∈ {agrement, autre, cnss, fiscale, rc_decennale, rc_travaux}
- frontend/src/api/installationsApi.js :: createBinAffectation -> /api/django/installations/bin-affectations  [BinAffectationSerializer]
    champs: bin, date_creation, date_modification, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: createBinLocation -> /api/django/installations/bin-locations  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: createColis -> /api/django/installations/colis  [ColisSerializer]
    champs: controle_par, created_by, date_controle, date_creation, date_modification, id, installation, lignes, note, poids_kg, reference, statut, statut_display
    statut ∈ {controle, expedie, preparation}
- frontend/src/api/installationsApi.js :: createColisLigne -> /api/django/installations/colis-lignes  [ColisLigneSerializer]
    champs: colis, controle_ok, designation, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: createCommandeCadre -> /api/django/installations/commandes-cadre  [CommandeCadreSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display
    statut ∈ {actif, brouillon, clos}
- frontend/src/api/installationsApi.js :: createCommandeCadreLigne -> /api/django/installations/commandes-cadre-lignes  [CommandeCadreLigneSerializer]
    champs: commande_cadre, designation, id, prix_negocie, produit, produit_nom, volume_consomme, volume_engage, volume_restant
- frontend/src/api/installationsApi.js :: createContratPrixFournisseur -> /api/django/installations/contrats-prix-fournisseur  [ContratPrixFournisseurSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display, version
    statut ∈ {actif, brouillon, expire}
- frontend/src/api/installationsApi.js :: createContratPrixLigne -> /api/django/installations/contrats-prix-lignes  [ContratPrixLigneSerializer]
    champs: contrat, designation, id, prix_convenu, produit, produit_nom, remise_pct
- frontend/src/api/installationsApi.js :: createControleQualiteModele -> /api/django/installations/controle-qualite-modeles  [ControleQualiteModeleSerializer]
    champs: active, date_creation, date_modification, id, items, kit
- frontend/src/api/installationsApi.js :: createDemandeAchat -> /api/django/installations/demandes-achat  [DemandeAchatSerializer]
    champs: approuvee_par, bon_commande, chantier, created_by, date_besoin, date_creation, date_decision, date_modification, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
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
- frontend/src/api/installationsApi.js :: createEvaluationSousTraitant -> /api/django/installations/evaluations-sous-traitant  [EvaluationSousTraitantSerializer]
    champs: chantier, commentaire, date_creation, date_evaluation, date_modification, evalue_par, id, note_delai, note_globale, note_qualite, note_securite, ordre, sous_traitant, sous_traitant_nom
- frontend/src/api/installationsApi.js :: createFraisImport -> /api/django/installations/frais-import  [FraisImportSerializer]
    champs: categorie, categorie_display, created_by, date_creation, date_frais, dossier, id, libelle, montant
    categorie ∈ {assurance, autre, douane, fret, manutention, transit, tva_import}
- frontend/src/api/installationsApi.js :: createGpsConsentement -> /api/django/installations/gps-consentements  [GpsConsentRecordSerializer]
    champs: consent_recorded_at, consent_ref, id, is_active, recorded_by, revoked_at, revoked_reason, technicien, technicien_nom
- frontend/src/api/installationsApi.js :: createIndisponibilite -> /api/django/installations/indisponibilites-ressource  [IndisponibiliteRessourceSerializer]
    champs: camionnette, camionnette_nom, created_by, date_creation, date_debut, date_fin, date_modification, id, motif, technicien, technicien_nom, type_indispo, type_indispo_display
    type_indispo ∈ {arret, autre, conge, formation}
- frontend/src/api/installationsApi.js :: createJalonProjet -> /api/django/installations/jalons-projet  [JalonProjetSerializer]
    champs: atteint, date_cible, date_creation, date_modification, date_reelle, id, installation, libelle, notes, ordre, phase, phase_display, rappel_facturation_envoye, tranche_echeancier
    phase ∈ {appro, etude, mes, pose, reception}
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
- frontend/src/api/installationsApi.js :: createOrdreSousTraitance -> /api/django/installations/ordres-sous-traitance  [OrdreSousTraitanceSerializer]
    champs: chantier, created_by, date_creation, date_echeance, date_emission, date_modification, id, montant, montant_realise, note, prestation, reference, sous_traitant, sous_traitant_nom, statut, statut_display
- frontend/src/api/installationsApi.js :: createPickList -> /api/django/installations/pick-lists  [PickListSerializer]
    champs: created_by, date_creation, date_modification, id, installation, lignes, note, reference, statut, statut_display
    statut ∈ {emis, en_cours, termine}
- frontend/src/api/installationsApi.js :: createPreuveLivraison -> /api/django/installations/preuves-livraison  [PreuveLivraisonSerializer]
    champs: created_by, date_creation, date_modification, gps_lat, gps_lng, horodatage, id, livraison, note, photo, signataire_nom, signature_data
- frontend/src/api/installationsApi.js :: createPutAway -> /api/django/installations/putaways  [PutAwaySerializer]
    champs: bin_effectif, bin_effectif_code, bin_suggere, bin_suggere_code, created_by, date_creation, date_modification, date_rangement, emplacement, id, note, produit, produit_nom, quantite, range_par, reference_reception, statut, statut_display
    statut ∈ {a_ranger, range}
- frontend/src/api/installationsApi.js :: createRFQ -> /api/django/installations/rfq  [RFQSerializer]
    champs: bon_commande, comparatif, consultations, created_by, date_creation, date_limite_reponse, date_modification, demande, id, note, objet, offres, reference, statut, statut_display
    statut ∈ {brouillon, cloturee, envoyee}
- frontend/src/api/installationsApi.js :: createRFQOffre -> /api/django/installations/rfq-offres  [RFQOffreSerializer]
    champs: date_creation, date_modification, delai_jours, fournisseur, fournisseur_nom, fournisseur_nom_libre, id, montant_ht, note, retenue, rfq, validite_jours
- frontend/src/api/installationsApi.js :: createRecurrenceIntervention -> /api/django/installations/recurrences-intervention  [RecurrenceInterventionSerializer]
    champs: actif, date_creation, date_fin, id, installation, installation_reference, intervalle, nb_generees, nb_occurrences, prochaine_echeance, regle, regle_display, technicien_defaut, technicien_defaut_nom, type_intervention
    regle ∈ {annuelle, mensuelle, semestrielle, trimestrielle}
- frontend/src/api/installationsApi.js :: createRetenueGarantieSousTraitant -> /api/django/installations/retenues-garantie-sous-traitant  [RetenueGarantieSousTraitantSerializer]
    champs: created_by, date_constitution, date_creation, date_levee, date_modification, id, levee, montant_a_liberer, montant_base, montant_retenu, note, ordre, ordre_reference, pourcentage
- frontend/src/api/installationsApi.js :: createReunionChantier -> /api/django/installations/reunions-chantier  [ReunionChantierSerializer]
    champs: actions, date_creation, date_modification, date_reunion, decisions, id, installation, ordre_du_jour, presents, redige_par, redige_par_nom, titre
- frontend/src/api/installationsApi.js :: createRevisionDocument -> /api/django/installations/revisions-document  [RevisionDocumentSerializer]
    champs: auteur, auteur_nom, date_creation, date_revision, document, fichier, fichier_url, id, indice, notes
- frontend/src/api/installationsApi.js :: createSessionComptage -> /api/django/installations/sessions-comptage  [SessionComptageSerializer]
    champs: classe_abc, classe_abc_display, created_by, date_creation, date_modification, date_planifiee, emplacement, id, intitule, lignes, note, reference, statut, statut_display
    classe_abc ∈ {A, B, C, toutes}
    statut ∈ {en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: createTransporteur -> /api/django/installations/transporteurs  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/installationsApi.js :: deleteAstreinte -> /api/django/installations/astreintes/<>  [AstreinteSerializer]
    champs: created_by, date_creation, date_debut, date_fin, id, technicien, technicien_nom, telephone_astreinte
- frontend/src/api/installationsApi.js :: deleteBinAffectation -> /api/django/installations/bin-affectations/<>  [BinAffectationSerializer]
    champs: bin, date_creation, date_modification, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: deleteBinLocation -> /api/django/installations/bin-locations/<>  [BinLocationSerializer]
    champs: affectations, allee, archived, casier, categorie, categorie_nom, code, created_by, date_creation, date_modification, emplacement, emplacement_nom, id, note, ordre, zone
- frontend/src/api/installationsApi.js :: deleteColisLigne -> /api/django/installations/colis-lignes/<>  [ColisLigneSerializer]
    champs: colis, controle_ok, designation, id, produit, produit_nom, quantite
- frontend/src/api/installationsApi.js :: deleteCommandeCadreLigne -> /api/django/installations/commandes-cadre-lignes/<>  [CommandeCadreLigneSerializer]
    champs: commande_cadre, designation, id, prix_negocie, produit, produit_nom, volume_consomme, volume_engage, volume_restant
- frontend/src/api/installationsApi.js :: deleteContratPrixLigne -> /api/django/installations/contrats-prix-lignes/<>  [ContratPrixLigneSerializer]
    champs: contrat, designation, id, prix_convenu, produit, produit_nom, remise_pct
- frontend/src/api/installationsApi.js :: deleteDemandeAchat -> /api/django/installations/demandes-achat/<>  [DemandeAchatSerializer]
    champs: approuvee_par, bon_commande, chantier, created_by, date_besoin, date_creation, date_decision, date_modification, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: deleteDemandeAchatLigne -> /api/django/installations/demandes-achat-lignes/<>  [DemandeAchatLigneSerializer]
    champs: demande, designation, id, prix_estime, produit, produit_nom, quantite, total_estime
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
- frontend/src/api/installationsApi.js :: deleteIndisponibilite -> /api/django/installations/indisponibilites-ressource/<>  [IndisponibiliteRessourceSerializer]
    champs: camionnette, camionnette_nom, created_by, date_creation, date_debut, date_fin, date_modification, id, motif, technicien, technicien_nom, type_indispo, type_indispo_display
    type_indispo ∈ {arret, autre, conge, formation}
- frontend/src/api/installationsApi.js :: deleteJalonProjet -> /api/django/installations/jalons-projet/<>  [JalonProjetSerializer]
    champs: atteint, date_cible, date_creation, date_modification, date_reelle, id, installation, libelle, notes, ordre, phase, phase_display, rappel_facturation_envoye, tranche_echeancier
    phase ∈ {appro, etude, mes, pose, reception}
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
- frontend/src/api/installationsApi.js :: deleteRecurrenceIntervention -> /api/django/installations/recurrences-intervention/<>  [RecurrenceInterventionSerializer]
    champs: actif, date_creation, date_fin, id, installation, installation_reference, intervalle, nb_generees, nb_occurrences, prochaine_echeance, regle, regle_display, technicien_defaut, technicien_defaut_nom, type_intervention
    regle ∈ {annuelle, mensuelle, semestrielle, trimestrielle}
- frontend/src/api/installationsApi.js :: deleteTransporteur -> /api/django/installations/transporteurs/<>  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/installationsApi.js :: getAppelsCommande -> /api/django/installations/appels-commande  [AppelCommandeSerializer]
    champs: chantier, created_by, date_appel, date_creation, id, ligne, montant, note, quantite
- frontend/src/api/installationsApi.js :: getApprobationsBcf -> /api/django/installations/approbations-bcf  [ApprobationBCFSerializer]
    champs: approuve_par, bcf, date_approbation, id, montant_approuve, note, palier, palier_display
- frontend/src/api/installationsApi.js :: getAstreintes -> /api/django/installations/astreintes  [AstreinteSerializer]
    champs: created_by, date_creation, date_debut, date_fin, id, technicien, technicien_nom, telephone_astreinte
- frontend/src/api/installationsApi.js :: getAttestationsSousTraitant -> /api/django/installations/attestations-sous-traitant  [AttestationSousTraitantSerializer]
    champs: created_by, date_creation, date_emission, date_expiration, date_modification, est_valide, id, note, obligatoire, organisme, reference, sous_traitant, sous_traitant_nom, type_piece, type_piece_display
    type_piece ∈ {agrement, autre, cnss, fiscale, rc_decennale, rc_travaux}
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
- frontend/src/api/installationsApi.js :: getCommandeCadreLignes -> /api/django/installations/commandes-cadre-lignes  [CommandeCadreLigneSerializer]
    champs: commande_cadre, designation, id, prix_negocie, produit, produit_nom, volume_consomme, volume_engage, volume_restant
- frontend/src/api/installationsApi.js :: getCommandesCadre -> /api/django/installations/commandes-cadre  [CommandeCadreSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display
    statut ∈ {actif, brouillon, clos}
- frontend/src/api/installationsApi.js :: getComptageLignes -> /api/django/installations/comptage-lignes  [ComptageLigneSerializer]
    champs: compte, designation, ecart, id, produit, produit_nom, quantite_comptee, quantite_theorique, session
- frontend/src/api/installationsApi.js :: getContratPrixLignes -> /api/django/installations/contrats-prix-lignes  [ContratPrixLigneSerializer]
    champs: contrat, designation, id, prix_convenu, produit, produit_nom, remise_pct
- frontend/src/api/installationsApi.js :: getContratsPrixFournisseur -> /api/django/installations/contrats-prix-fournisseur  [ContratPrixFournisseurSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display, version
    statut ∈ {actif, brouillon, expire}
- frontend/src/api/installationsApi.js :: getControleQualiteModeles -> /api/django/installations/controle-qualite-modeles  [ControleQualiteModeleSerializer]
    champs: active, date_creation, date_modification, id, items, kit
- frontend/src/api/installationsApi.js :: getDemandeAchat -> /api/django/installations/demandes-achat/<>  [DemandeAchatSerializer]
    champs: approuvee_par, bon_commande, chantier, created_by, date_besoin, date_creation, date_decision, date_modification, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
    priorite ∈ {basse, haute, normale, urgente}
- frontend/src/api/installationsApi.js :: getDemandeTransfert -> /api/django/installations/demandes-transfert/<>  [DemandeTransfertSerializer]
    champs: approuve_par, created_by, date_approbation, date_creation, date_execution, date_modification, destination, destination_nom, id, motif, motif_refus, produit, produit_nom, quantite, reference, source, source_nom, statut, statut_display
    statut ∈ {approuve, demande, execute, refuse}
- frontend/src/api/installationsApi.js :: getDemandesAchat -> /api/django/installations/demandes-achat  [DemandeAchatSerializer]
    champs: approuvee_par, bon_commande, chantier, created_by, date_besoin, date_creation, date_decision, date_modification, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
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
- frontend/src/api/installationsApi.js :: getEtapesAssemblageKit -> /api/django/installations/etapes-assemblage  [EtapeAssemblageSerializer]
    champs: duree_attendue_min, id, instructions, kit, libelle, ordre, piece_jointe
- frontend/src/api/installationsApi.js :: getEvaluationsSousTraitant -> /api/django/installations/evaluations-sous-traitant  [EvaluationSousTraitantSerializer]
    champs: chantier, commentaire, date_creation, date_evaluation, date_modification, evalue_par, id, note_delai, note_globale, note_qualite, note_securite, ordre, sous_traitant, sous_traitant_nom
- frontend/src/api/installationsApi.js :: getFicheTemplates -> /api/django/installations/fiche-intervention-templates  [FicheInterventionTemplateSerializer]
    champs: actif, champs, id, nom, protege, type_intervention
- frontend/src/api/installationsApi.js :: getFraisImport -> /api/django/installations/frais-import  [FraisImportSerializer]
    champs: categorie, categorie_display, created_by, date_creation, date_frais, dossier, id, libelle, montant
    categorie ∈ {assurance, autre, douane, fret, manutention, transit, tva_import}
- frontend/src/api/installationsApi.js :: getGeofenceAlertes -> /api/django/installations/geofence-alertes  [GeofenceAlertSerializer]
    champs: acquittee, acquittee_le, acquittee_par, created_at, distance_site_km, id, intervention, position, rayon_attendu_km, technicien, technicien_nom
- frontend/src/api/installationsApi.js :: getGpsConsentements -> /api/django/installations/gps-consentements  [GpsConsentRecordSerializer]
    champs: consent_recorded_at, consent_ref, id, is_active, recorded_by, revoked_at, revoked_reason, technicien, technicien_nom
- frontend/src/api/installationsApi.js :: getIndisponibilites -> /api/django/installations/indisponibilites-ressource  [IndisponibiliteRessourceSerializer]
    champs: camionnette, camionnette_nom, created_by, date_creation, date_debut, date_fin, date_modification, id, motif, technicien, technicien_nom, type_indispo, type_indispo_display
    type_indispo ∈ {arret, autre, conge, formation}
- frontend/src/api/installationsApi.js :: getJalonsProjet -> /api/django/installations/jalons-projet  [JalonProjetSerializer]
    champs: atteint, date_cible, date_creation, date_modification, date_reelle, id, installation, libelle, notes, ordre, phase, phase_display, rappel_facturation_envoye, tranche_echeancier
    phase ∈ {appro, etude, mes, pose, reception}
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
- frontend/src/api/installationsApi.js :: getOrdresSousTraitance -> /api/django/installations/ordres-sous-traitance  [OrdreSousTraitanceSerializer]
    champs: chantier, created_by, date_creation, date_echeance, date_emission, date_modification, id, montant, montant_realise, note, prestation, reference, sous_traitant, sous_traitant_nom, statut, statut_display
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
- frontend/src/api/installationsApi.js :: getRFQ -> /api/django/installations/rfq/<>  [RFQSerializer]
    champs: bon_commande, comparatif, consultations, created_by, date_creation, date_limite_reponse, date_modification, demande, id, note, objet, offres, reference, statut, statut_display
    statut ∈ {brouillon, cloturee, envoyee}
- frontend/src/api/installationsApi.js :: getRFQConsultations -> /api/django/installations/rfq-consultations  [RFQConsultationSerializer]
    champs: a_repondu, date_creation, date_modification, derniere_relance_le, email_envoye_le, fournisseur, fournisseur_email, fournisseur_nom, fournisseur_telephone, id, nb_relances, offre, rfq, whatsapp_envoye_le
- frontend/src/api/installationsApi.js :: getRFQs -> /api/django/installations/rfq  [RFQSerializer]
    champs: bon_commande, comparatif, consultations, created_by, date_creation, date_limite_reponse, date_modification, demande, id, note, objet, offres, reference, statut, statut_display
    statut ∈ {brouillon, cloturee, envoyee}
- frontend/src/api/installationsApi.js :: getReceptionsNonFacturees -> /api/django/installations/receptions-non-facturees  [ReceptionNonFactureeSerializer]
    champs: bon_commande, created_by, date_creation, date_lettrage, date_modification, date_reception, facture, id, lettre, libelle, montant_a_provisionner, montant_provision, note, reception
- frontend/src/api/installationsApi.js :: getRecurrencesIntervention -> /api/django/installations/recurrences-intervention  [RecurrenceInterventionSerializer]
    champs: actif, date_creation, date_fin, id, installation, installation_reference, intervalle, nb_generees, nb_occurrences, prochaine_echeance, regle, regle_display, technicien_defaut, technicien_defaut_nom, type_intervention
    regle ∈ {annuelle, mensuelle, semestrielle, trimestrielle}
- frontend/src/api/installationsApi.js :: getRetenuesGarantieSousTraitant -> /api/django/installations/retenues-garantie-sous-traitant  [RetenueGarantieSousTraitantSerializer]
    champs: created_by, date_constitution, date_creation, date_levee, date_modification, id, levee, montant_a_liberer, montant_base, montant_retenu, note, ordre, ordre_reference, pourcentage
- frontend/src/api/installationsApi.js :: getReunionsChantier -> /api/django/installations/reunions-chantier  [ReunionChantierSerializer]
    champs: actions, date_creation, date_modification, date_reunion, decisions, id, installation, ordre_du_jour, presents, redige_par, redige_par_nom, titre
- frontend/src/api/installationsApi.js :: getRevisionsDocument -> /api/django/installations/revisions-document  [RevisionDocumentSerializer]
    champs: auteur, auteur_nom, date_creation, date_revision, document, fichier, fichier_url, id, indice, notes
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
- frontend/src/api/installationsApi.js :: updateCommandeCadre -> /api/django/installations/commandes-cadre/<>  [CommandeCadreSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display
    statut ∈ {actif, brouillon, clos}
- frontend/src/api/installationsApi.js :: updateCommandeCadreLigne -> /api/django/installations/commandes-cadre-lignes/<>  [CommandeCadreLigneSerializer]
    champs: commande_cadre, designation, id, prix_negocie, produit, produit_nom, volume_consomme, volume_engage, volume_restant
- frontend/src/api/installationsApi.js :: updateComptageLigne -> /api/django/installations/comptage-lignes/<>  [ComptageLigneSerializer]
    champs: compte, designation, ecart, id, produit, produit_nom, quantite_comptee, quantite_theorique, session
- frontend/src/api/installationsApi.js :: updateContratPrixFournisseur -> /api/django/installations/contrats-prix-fournisseur/<>  [ContratPrixFournisseurSerializer]
    champs: created_by, date_creation, date_debut, date_fin, date_modification, fournisseur, fournisseur_nom, id, intitule, lignes, note, reference, statut, statut_display, version
    statut ∈ {actif, brouillon, expire}
- frontend/src/api/installationsApi.js :: updateContratPrixLigne -> /api/django/installations/contrats-prix-lignes/<>  [ContratPrixLigneSerializer]
    champs: contrat, designation, id, prix_convenu, produit, produit_nom, remise_pct
- frontend/src/api/installationsApi.js :: updateControleQualiteModele -> /api/django/installations/controle-qualite-modeles/<>  [ControleQualiteModeleSerializer]
    champs: active, date_creation, date_modification, id, items, kit
- frontend/src/api/installationsApi.js :: updateDemandeAchat -> /api/django/installations/demandes-achat/<>  [DemandeAchatSerializer]
    champs: approuvee_par, bon_commande, chantier, created_by, date_besoin, date_creation, date_decision, date_modification, fournisseur_suggere, id, lignes, montant_estime, motif_refus, note, objet, priorite, priorite_display, programme, reference, statut, statut_display
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
- frontend/src/api/installationsApi.js :: updateJalonProjet -> /api/django/installations/jalons-projet/<>  [JalonProjetSerializer]
    champs: atteint, date_cible, date_creation, date_modification, date_reelle, id, installation, libelle, notes, ordre, phase, phase_display, rappel_facturation_envoye, tranche_echeancier
    phase ∈ {appro, etude, mes, pose, reception}
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
- frontend/src/api/installationsApi.js :: updateSessionComptage -> /api/django/installations/sessions-comptage/<>  [SessionComptageSerializer]
    champs: classe_abc, classe_abc_display, created_by, date_creation, date_modification, date_planifiee, emplacement, id, intitule, lignes, note, reference, statut, statut_display
    classe_abc ∈ {A, B, C, toutes}
    statut ∈ {en_cours, planifie, termine}
- frontend/src/api/installationsApi.js :: updateTransporteur -> /api/django/installations/transporteurs/<>  [TransporteurSerializer]
    champs: active, contact, created_by, date_creation, date_modification, id, nom, note, tarif_base, telephone, type_transporteur, type_transporteur_display
    type_transporteur ∈ {interne, tiers}
- frontend/src/api/kbApi.js :: createAcl -> /api/django/kb/article-acls  [KbArticleAclSerializer]
    champs: article, date_creation, id, niveau, niveau_display, role, role_display, utilisateur, utilisateur_nom
    niveau ∈ {edition, lecture}
- frontend/src/api/kbApi.js :: createAssignation -> /api/django/kb/parcours-assignations  [KbParcoursAssignationSerializer]
    champs: date_creation, id, parcours, parcours_nom, utilisateur, utilisateur_nom
- frontend/src/api/kbApi.js :: createBloc -> /api/django/kb/blocs  [BlocReutilisableSerializer]
    champs: corps, created_by, created_by_nom, date_creation, date_modification, id, nom, portee, portee_display
    portee ∈ {personnel, societe}
- frontend/src/api/kbApi.js :: createLectureObligatoire -> /api/django/kb/lectures-obligatoires  [KbLectureObligatoireSerializer]
    champs: article, date_creation, echeance, id, role_cible, utilisateur, utilisateur_nom
- frontend/src/api/kbApi.js :: createLien -> /api/django/kb/article-liens  [KbArticleLienSerializer]
    champs: article, cible_id, date_creation, id, libelle, type_cible, type_cible_display
    type_cible ∈ {article, equipement, produit, type_intervention}
- frontend/src/api/kbApi.js :: createParcours -> /api/django/kb/parcours  [KbParcoursSerializer]
    champs: actif, created_by, date_creation, description, id, metier, nom, role_cible, role_cible_display
- frontend/src/api/kbApi.js :: createParcoursArticle -> /api/django/kb/parcours-articles  [KbParcoursArticleSerializer]
    champs: article, article_titre, id, ordre, parcours
- frontend/src/api/kbApi.js :: createPartage -> /api/django/kb/partages  [PartageArticleKbSerializer]
    champs: actif, article, article_titre, consultations, created_by, date_creation, expires_at, id, is_expired, token
- frontend/src/api/kbApi.js :: listAcls -> /api/django/kb/article-acls  [KbArticleAclSerializer]
    champs: article, date_creation, id, niveau, niveau_display, role, role_display, utilisateur, utilisateur_nom
    niveau ∈ {edition, lecture}
- frontend/src/api/kbApi.js :: listAssignations -> /api/django/kb/parcours-assignations  [KbParcoursAssignationSerializer]
    champs: date_creation, id, parcours, parcours_nom, utilisateur, utilisateur_nom
- frontend/src/api/kbApi.js :: listBlocs -> /api/django/kb/blocs  [BlocReutilisableSerializer]
    champs: corps, created_by, created_by_nom, date_creation, date_modification, id, nom, portee, portee_display
    portee ∈ {personnel, societe}
- frontend/src/api/kbApi.js :: listFavoris -> /api/django/kb/favoris  [KbFavoriSerializer]
    champs: article, article_titre, date_creation, id, utilisateur
- frontend/src/api/kbApi.js :: listLecturesObligatoires -> /api/django/kb/lectures-obligatoires  [KbLectureObligatoireSerializer]
    champs: article, date_creation, echeance, id, role_cible, utilisateur, utilisateur_nom
- frontend/src/api/kbApi.js :: listLiens -> /api/django/kb/article-liens  [KbArticleLienSerializer]
    champs: article, cible_id, date_creation, id, libelle, type_cible, type_cible_display
    type_cible ∈ {article, equipement, produit, type_intervention}
- frontend/src/api/kbApi.js :: listParcours -> /api/django/kb/parcours  [KbParcoursSerializer]
    champs: actif, created_by, date_creation, description, id, metier, nom, role_cible, role_cible_display
- frontend/src/api/kbApi.js :: listParcoursArticles -> /api/django/kb/parcours-articles  [KbParcoursArticleSerializer]
    champs: article, article_titre, id, ordre, parcours
- frontend/src/api/kbApi.js :: listPartages -> /api/django/kb/partages  [PartageArticleKbSerializer]
    champs: actif, article, article_titre, consultations, created_by, date_creation, expires_at, id, is_expired, token
- frontend/src/api/kbApi.js :: listVersions -> /api/django/kb/versions  [KbArticleVersionSerializer]
    champs: article, auteur, auteur_nom, contenu, date_creation, id, titre, version
- frontend/src/api/kbApi.js :: removeAcl -> /api/django/kb/article-acls/<>  [KbArticleAclSerializer]
    champs: article, date_creation, id, niveau, niveau_display, role, role_display, utilisateur, utilisateur_nom
    niveau ∈ {edition, lecture}
- frontend/src/api/kbApi.js :: removeBloc -> /api/django/kb/blocs/<>  [BlocReutilisableSerializer]
    champs: corps, created_by, created_by_nom, date_creation, date_modification, id, nom, portee, portee_display
    portee ∈ {personnel, societe}
- frontend/src/api/kbApi.js :: removeLectureObligatoire -> /api/django/kb/lectures-obligatoires/<>  [KbLectureObligatoireSerializer]
    champs: article, date_creation, echeance, id, role_cible, utilisateur, utilisateur_nom
- frontend/src/api/kbApi.js :: removeLien -> /api/django/kb/article-liens/<>  [KbArticleLienSerializer]
    champs: article, cible_id, date_creation, id, libelle, type_cible, type_cible_display
    type_cible ∈ {article, equipement, produit, type_intervention}
- frontend/src/api/kbApi.js :: removeParcoursArticle -> /api/django/kb/parcours-articles/<>  [KbParcoursArticleSerializer]
    champs: article, article_titre, id, ordre, parcours
- frontend/src/api/litigesApi.js :: create -> /api/django/litiges/reclamations  [ReclamationSerializer]
    champs: audit, audit_id, bloque_relances, concurrent_devise, concurrent_nom, concurrent_prix, created_by, date_creation, description, gravite, gravite_display, id, montant_conteste, motif_perte, ncr, ncr_id, objet, reference, source_id, source_type, statut, statut_display, type_reclamation, type_reclamation_display
    gravite ∈ {elevee, faible, moyenne}
    statut ∈ {en_traitement, ouverte, rejetee, resolue}
    type_reclamation ∈ {autre, commercial, delai, financier, qualite, recouvrement}
- frontend/src/api/litigesApi.js :: get -> /api/django/litiges/reclamations/<>  [ReclamationSerializer]
    champs: audit, audit_id, bloque_relances, concurrent_devise, concurrent_nom, concurrent_prix, created_by, date_creation, description, gravite, gravite_display, id, montant_conteste, motif_perte, ncr, ncr_id, objet, reference, source_id, source_type, statut, statut_display, type_reclamation, type_reclamation_display
    gravite ∈ {elevee, faible, moyenne}
    statut ∈ {en_traitement, ouverte, rejetee, resolue}
    type_reclamation ∈ {autre, commercial, delai, financier, qualite, recouvrement}
- frontend/src/api/litigesApi.js :: list -> /api/django/litiges/reclamations  [ReclamationSerializer]
    champs: audit, audit_id, bloque_relances, concurrent_devise, concurrent_nom, concurrent_prix, created_by, date_creation, description, gravite, gravite_display, id, montant_conteste, motif_perte, ncr, ncr_id, objet, reference, source_id, source_type, statut, statut_display, type_reclamation, type_reclamation_display
    gravite ∈ {elevee, faible, moyenne}
    statut ∈ {en_traitement, ouverte, rejetee, resolue}
    type_reclamation ∈ {autre, commercial, delai, financier, qualite, recouvrement}
- frontend/src/api/litigesApi.js :: remove -> /api/django/litiges/reclamations/<>  [ReclamationSerializer]
    champs: audit, audit_id, bloque_relances, concurrent_devise, concurrent_nom, concurrent_prix, created_by, date_creation, description, gravite, gravite_display, id, montant_conteste, motif_perte, ncr, ncr_id, objet, reference, source_id, source_type, statut, statut_display, type_reclamation, type_reclamation_display
    gravite ∈ {elevee, faible, moyenne}
    statut ∈ {en_traitement, ouverte, rejetee, resolue}
    type_reclamation ∈ {autre, commercial, delai, financier, qualite, recouvrement}
- frontend/src/api/litigesApi.js :: update -> /api/django/litiges/reclamations/<>  [ReclamationSerializer]
    champs: audit, audit_id, bloque_relances, concurrent_devise, concurrent_nom, concurrent_prix, created_by, date_creation, description, gravite, gravite_display, id, montant_conteste, motif_perte, ncr, ncr_id, objet, reference, source_id, source_type, statut, statut_display, type_reclamation, type_reclamation_display
    gravite ∈ {elevee, faible, moyenne}
    statut ∈ {en_traitement, ouverte, rejetee, resolue}
    type_reclamation ∈ {autre, commercial, delai, financier, qualite, recouvrement}
- frontend/src/api/messagesApi.js :: createConversation -> /api/django/chat/conversations  [ConversationSerializer]
    champs: alias_email, created_at, created_by, id, is_archived, kind, last_message, member_ids, members, name, unread_count, updated_at
    kind ∈ {channel, dm}
- frontend/src/api/messagesApi.js :: getConversation -> /api/django/chat/conversations/<>  [ConversationSerializer]
    champs: alias_email, created_at, created_by, id, is_archived, kind, last_message, member_ids, members, name, unread_count, updated_at
    kind ∈ {channel, dm}
- frontend/src/api/messagesApi.js :: listConversations -> /api/django/chat/conversations  [ConversationSerializer]
    champs: alias_email, created_at, created_by, id, is_archived, kind, last_message, member_ids, members, name, unread_count, updated_at
    kind ∈ {channel, dm}
- frontend/src/api/messagesApi.js :: updateConversation -> /api/django/chat/conversations/<>  [ConversationSerializer]
    champs: alias_email, created_at, created_by, id, is_archived, kind, last_message, member_ids, members, name, unread_count, updated_at
    kind ∈ {channel, dm}
- frontend/src/api/migrationApi.js :: createLot -> /api/django/migration/lots-migration  [LotMigrationSerializer]
    champs: created_at, crees, dernier_rapport, derogation_at, derogation_motif, derogation_par_nom, derogation_reconcile, entite, erreurs, id, import_job, maj, ordre, projet, source_lignes, source_montant, statut, updated_at
    statut ∈ {analyse, charge, echoue, en_attente, reconcilie}
- frontend/src/api/migrationApi.js :: createProjet -> /api/django/migration/projets-migration  [ProjetMigrationSerializer]
    champs: created_at, cree_par, date_debut, date_fin, id, lots_reconcilies, lots_total, nom, notes, source, statut, updated_at
    source ∈ {csv_generique, excel, odoo, sage}
    statut ∈ {analyse, brouillon, chargement, echoue, reconciliation, termine}
- frontend/src/api/migrationApi.js :: deleteLot -> /api/django/migration/lots-migration/<>  [LotMigrationSerializer]
    champs: created_at, crees, dernier_rapport, derogation_at, derogation_motif, derogation_par_nom, derogation_reconcile, entite, erreurs, id, import_job, maj, ordre, projet, source_lignes, source_montant, statut, updated_at
    statut ∈ {analyse, charge, echoue, en_attente, reconcilie}
- frontend/src/api/migrationApi.js :: deleteProjet -> /api/django/migration/projets-migration/<>  [ProjetMigrationSerializer]
    champs: created_at, cree_par, date_debut, date_fin, id, lots_reconcilies, lots_total, nom, notes, source, statut, updated_at
    source ∈ {csv_generique, excel, odoo, sage}
    statut ∈ {analyse, brouillon, chargement, echoue, reconciliation, termine}
- frontend/src/api/migrationApi.js :: getProjet -> /api/django/migration/projets-migration/<>  [ProjetMigrationSerializer]
    champs: created_at, cree_par, date_debut, date_fin, id, lots_reconcilies, lots_total, nom, notes, source, statut, updated_at
    source ∈ {csv_generique, excel, odoo, sage}
    statut ∈ {analyse, brouillon, chargement, echoue, reconciliation, termine}
- frontend/src/api/migrationApi.js :: listLots -> /api/django/migration/lots-migration  [LotMigrationSerializer]
    champs: created_at, crees, dernier_rapport, derogation_at, derogation_motif, derogation_par_nom, derogation_reconcile, entite, erreurs, id, import_job, maj, ordre, projet, source_lignes, source_montant, statut, updated_at
    statut ∈ {analyse, charge, echoue, en_attente, reconcilie}
- frontend/src/api/migrationApi.js :: listProjets -> /api/django/migration/projets-migration  [ProjetMigrationSerializer]
    champs: created_at, cree_par, date_debut, date_fin, id, lots_reconcilies, lots_total, nom, notes, source, statut, updated_at
    source ∈ {csv_generique, excel, odoo, sage}
    statut ∈ {analyse, brouillon, chargement, echoue, reconciliation, termine}
- frontend/src/api/migrationApi.js :: updateProjet -> /api/django/migration/projets-migration/<>  [ProjetMigrationSerializer]
    champs: created_at, cree_par, date_debut, date_fin, id, lots_reconcilies, lots_total, nom, notes, source, statut, updated_at
    source ∈ {csv_generique, excel, odoo, sage}
    statut ∈ {analyse, brouillon, chargement, echoue, reconciliation, termine}
- frontend/src/api/monitoringApi.js :: addCleaning -> /api/django/monitoring/cleanings  [CleaningEventSerializer]
    champs: date, date_creation, id, installation, note
- frontend/src/api/monitoringApi.js :: addReading -> /api/django/monitoring/readings  [ProductionReadingSerializer]
    champs: date, date_creation, energy_kwh, external_id, id, installation, note, period_days, source, source_display
    source ∈ {auto, manual}
- frontend/src/api/monitoringApi.js :: createAbonnement -> /api/django/monitoring/abonnements-monitoring  [AbonnementMonitoringSerializer]
    champs: client_id, date_creation, date_debut, derniere_facturation, id, installation_id, montant, motif_resiliation, periodicite, prochaine_echeance, statut
    periodicite ∈ {annuel, mensuel}
    statut ∈ {actif, resilie, suspendu}
- frontend/src/api/monitoringApi.js :: deleteCleaning -> /api/django/monitoring/cleanings/<>  [CleaningEventSerializer]
    champs: date, date_creation, id, installation, note
- frontend/src/api/monitoringApi.js :: deleteReading -> /api/django/monitoring/readings/<>  [ProductionReadingSerializer]
    champs: date, date_creation, energy_kwh, external_id, id, installation, note, period_days, source, source_display
    source ∈ {auto, manual}
- frontend/src/api/monitoringApi.js :: deleteWarranty -> /api/django/monitoring/warranties/<>  [ProductionWarrantySerializer]
    champs: compensation_mad_per_kwh, date_creation, date_modification, degradation_pct_per_year, guaranteed_year1_kwh, id, installation, note, start_year, tolerance_pct
- frontend/src/api/monitoringApi.js :: getAbonnements -> /api/django/monitoring/abonnements-monitoring  [AbonnementMonitoringSerializer]
    champs: client_id, date_creation, date_debut, derniere_facturation, id, installation_id, montant, motif_resiliation, periodicite, prochaine_echeance, statut
    periodicite ∈ {annuel, mensuel}
    statut ∈ {actif, resilie, suspendu}
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
- frontend/src/api/notificationsApi.js :: createWhatsAppTemplate -> /api/django/notifications/whatsapp-templates  [WhatsAppTemplateSerializer]
    champs: active, body_fr, categorie, categorie_label, created_at, groupe, id, language, motif_rejet, name, statut_approbation, statut_approbation_label, updated_at
    categorie ∈ {marketing, utility}
    statut_approbation ∈ {approuve, brouillon, rejete, soumis}
- frontend/src/api/notificationsApi.js :: deleteAnnonce -> /api/django/notifications/annonces/<>  [AnnonceSerializer]
    champs: auteur, auteur_username, cible_departement_nom, cible_role, cible_type, cible_type_label, corps, created_at, date_expiration, date_publication, date_publication_effective, epinglee, id, is_expiree, lecture_obligatoire, lus_count, publiee, titre, updated_at
    cible_type ∈ {departement, role, tous}
- frontend/src/api/notificationsApi.js :: deleteHoliday -> /api/django/notifications/holidays/<>  [HolidaySerializer]
    champs: created_at, date, id, nom, recurrent_annuel
- frontend/src/api/notificationsApi.js :: deleteRoutingRule -> /api/django/notifications/routing-rules/<>  [NotificationRoutingRuleSerializer]
    champs: created_at, enabled, event_label, event_type, id, target_role, target_role_label, target_user
    event_type ∈ {annonce_published, annonce_read_reminder, approval_decided, approval_escalated, approval_reminder, approval_requested, bcf_cancelled, bcf_late, bcf_relance_proposee, bon_commande_cree, chantier_assigne, chantier_due, chat_mention, chat_message, client_contact_request, contrat_signe, da_decidee, da_soumise_stale, devis_accepted, devis_expired, devis_nudge_due, devis_opened, devis_reply, devis_superior_contact_requested, digest, education_reinscription_relance, facture_overdue, facture_payee, feedback_digest, feedback_starred, flotte_budget_depassement, flotte_dtc_critique, flotte_zone_alerte, ged_signature_expiration_proche, hot_lead_unread, idea_realisee, idea_received, idea_retenue, idea_vote, impersonation_requested, incident_critical, innovation_campagne, lead_assigned, lead_callback_requested, lead_callback_sla_breach, lead_new, maintenance_due, monitoring_rapport, nps_promoteur, paie_rib_divergence, paie_run_pret, post_social_rappel, product_announcement, projet_retard, projet_statut_change, sav_activite_due, sav_equipement_remplace, sav_ticket_breaching, sav_ticket_followed_update, sav_ticket_opened, sav_ticket_resolu, sav_visites_auto_generees, security_alert, security_change, snooze_reveil, stock_expiration_soon, stock_low, supplier_doc_expiring, uxviews_favoris_obsoletes, veille_ao_alarme_silence, veille_ao_nouveaux_avis, warranty_expiring}
- frontend/src/api/notificationsApi.js :: deleteWhatsAppTemplate -> /api/django/notifications/whatsapp-templates/<>  [WhatsAppTemplateSerializer]
    champs: active, body_fr, categorie, categorie_label, created_at, groupe, id, language, motif_rejet, name, statut_approbation, statut_approbation_label, updated_at
    categorie ∈ {marketing, utility}
    statut_approbation ∈ {approuve, brouillon, rejete, soumis}
- frontend/src/api/notificationsApi.js :: getAnnonces -> /api/django/notifications/annonces  [AnnonceSerializer]
    champs: auteur, auteur_username, cible_departement_nom, cible_role, cible_type, cible_type_label, corps, created_at, date_expiration, date_publication, date_publication_effective, epinglee, id, is_expiree, lecture_obligatoire, lus_count, publiee, titre, updated_at
    cible_type ∈ {departement, role, tous}
- frontend/src/api/notificationsApi.js :: getHolidays -> /api/django/notifications/holidays  [HolidaySerializer]
    champs: created_at, date, id, nom, recurrent_annuel
- frontend/src/api/notificationsApi.js :: getRoutingRules -> /api/django/notifications/routing-rules  [NotificationRoutingRuleSerializer]
    champs: created_at, enabled, event_label, event_type, id, target_role, target_role_label, target_user
    event_type ∈ {annonce_published, annonce_read_reminder, approval_decided, approval_escalated, approval_reminder, approval_requested, bcf_cancelled, bcf_late, bcf_relance_proposee, bon_commande_cree, chantier_assigne, chantier_due, chat_mention, chat_message, client_contact_request, contrat_signe, da_decidee, da_soumise_stale, devis_accepted, devis_expired, devis_nudge_due, devis_opened, devis_reply, devis_superior_contact_requested, digest, education_reinscription_relance, facture_overdue, facture_payee, feedback_digest, feedback_starred, flotte_budget_depassement, flotte_dtc_critique, flotte_zone_alerte, ged_signature_expiration_proche, hot_lead_unread, idea_realisee, idea_received, idea_retenue, idea_vote, impersonation_requested, incident_critical, innovation_campagne, lead_assigned, lead_callback_requested, lead_callback_sla_breach, lead_new, maintenance_due, monitoring_rapport, nps_promoteur, paie_rib_divergence, paie_run_pret, post_social_rappel, product_announcement, projet_retard, projet_statut_change, sav_activite_due, sav_equipement_remplace, sav_ticket_breaching, sav_ticket_followed_update, sav_ticket_opened, sav_ticket_resolu, sav_visites_auto_generees, security_alert, security_change, snooze_reveil, stock_expiration_soon, stock_low, supplier_doc_expiring, uxviews_favoris_obsoletes, veille_ao_alarme_silence, veille_ao_nouveaux_avis, warranty_expiring}
- frontend/src/api/notificationsApi.js :: getWhatsAppTemplates -> /api/django/notifications/whatsapp-templates  [WhatsAppTemplateSerializer]
    champs: active, body_fr, categorie, categorie_label, created_at, groupe, id, language, motif_rejet, name, statut_approbation, statut_approbation_label, updated_at
    categorie ∈ {marketing, utility}
    statut_approbation ∈ {approuve, brouillon, rejete, soumis}
- frontend/src/api/notificationsApi.js :: list -> /api/django/notifications/notifications  [NotificationSerializer]
    champs: body, category, created_at, event_label, event_type, id, is_action, link, read, read_at, reason, reason_label, severity, title
    event_type ∈ {annonce_published, annonce_read_reminder, approval_decided, approval_escalated, approval_reminder, approval_requested, bcf_cancelled, bcf_late, bcf_relance_proposee, bon_commande_cree, chantier_assigne, chantier_due, chat_mention, chat_message, client_contact_request, contrat_signe, da_decidee, da_soumise_stale, devis_accepted, devis_expired, devis_nudge_due, devis_opened, devis_reply, devis_superior_contact_requested, digest, education_reinscription_relance, facture_overdue, facture_payee, feedback_digest, feedback_starred, flotte_budget_depassement, flotte_dtc_critique, flotte_zone_alerte, ged_signature_expiration_proche, hot_lead_unread, idea_realisee, idea_received, idea_retenue, idea_vote, impersonation_requested, incident_critical, innovation_campagne, lead_assigned, lead_callback_requested, lead_callback_sla_breach, lead_new, maintenance_due, monitoring_rapport, nps_promoteur, paie_rib_divergence, paie_run_pret, post_social_rappel, product_announcement, projet_retard, projet_statut_change, sav_activite_due, sav_equipement_remplace, sav_ticket_breaching, sav_ticket_followed_update, sav_ticket_opened, sav_ticket_resolu, sav_visites_auto_generees, security_alert, security_change, snooze_reveil, stock_expiration_soon, stock_low, supplier_doc_expiring, uxviews_favoris_obsoletes, veille_ao_alarme_silence, veille_ao_nouveaux_avis, warranty_expiring}
    reason ∈ {assigne_a_vous, manager, regle_de_routage, vous_suivez}
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
- frontend/src/api/paieApi.js :: createPeriode -> /api/django/paie/periodes  [PeriodePaieSerializer]
    champs: annee, date_cloture, date_creation, date_paiement, id, libelle, mois, statut, type_run
- frontend/src/api/paieApi.js :: deleteAdhesionMutuelle -> /api/django/paie/adhesions-mutuelle/<>  [AdhesionMutuelleSerializer]
    champs: actif, date_creation, date_debut, id, profil, regime, regime_libelle
- frontend/src/api/paieApi.js :: deleteAvance -> /api/django/paie/avances/<>  [AvanceSalarieSerializer]
    champs: actif, date_creation, date_debut, id, libelle, montant_echeance, montant_rembourse, montant_total, nombre_echeances, profil, solde_restant, soldee, type
- frontend/src/api/paieApi.js :: deleteBareme -> /api/django/paie/baremes/<>  [BaremeIRSerializer]
    champs: actif, date_creation, date_effet, id, libelle, tranches, valide_par_fondateur
- frontend/src/api/paieApi.js :: deleteElementVariable -> /api/django/paie/elements-variables/<>  [ElementVariableSerializer]
    champs: categorie_absence, categorie_hs, date_creation, deduit_solde, id, libelle, montant, periode, profil, quantite, reconduire, reconduit_depuis, remunere, rubrique, source, type, type_entree
- frontend/src/api/paieApi.js :: deleteParametre -> /api/django/paie/parametres/<>  [ParametrePaieSerializer]
    champs: actif, date_creation, date_effet, deduction_par_personne_a_charge, id, plafond_cnss, plafond_frais_pro_bas, plafond_frais_pro_haut, plafond_personnes_a_charge, seuil_frais_pro, smag, smig, taux_allocations_familiales, taux_amo_patronal, taux_amo_salarial, taux_cnss_patronal, taux_cnss_salarial, taux_formation_pro, taux_frais_pro_bas, taux_frais_pro_haut, taux_hs_ferie, taux_hs_jour, taux_hs_nuit, valide_par_fondateur
- frontend/src/api/paieApi.js :: deletePeriode -> /api/django/paie/periodes/<>  [PeriodePaieSerializer]
    champs: annee, date_cloture, date_creation, date_paiement, id, libelle, mois, statut, type_run
- frontend/src/api/paieApi.js :: deleteProfil -> /api/django/paie/profils/<>  [ProfilPaieSerializer]
    champs: actif, affilie_amo, affilie_cimr, affilie_cnss, banque, date_creation, employe, employe_nom, heures_travail_mensuel, id, jours_travail_mensuel, mode_paiement, numero_amo, numero_cimr, numero_cnss, regime_date_debut, regime_date_fin, regime_exoneration, regime_plafond_mensuel, rib, salaire_base, structure, taux_cimr_salarial, type_remuneration
- frontend/src/api/paieApi.js :: deleteRegimeMutuelle -> /api/django/paie/regimes-mutuelle/<>  [RegimeMutuelleSerializer]
    champs: actif, date_creation, deductible_net_imposable, id, libelle, mode, palier, part_patronale, part_salariale
- frontend/src/api/paieApi.js :: deleteRubrique -> /api/django/paie/rubriques/<>  [RubriqueSerializer]
    champs: actif, arrondi, avantage_nature, base, code, compte, date_creation, id, imposable, libelle, montant_fixe, ordre, plafond_exoneration, sens_arrondi, soumis_amo, soumis_cimr, soumis_cnss, taux, type
- frontend/src/api/paieApi.js :: deleteRubriqueEmploye -> /api/django/paie/rubriques-employe/<>  [RubriqueEmployeSerializer]
    champs: actif, date_creation, date_debut, date_fin, id, montant, profil, rubrique, rubrique_code, taux
- frontend/src/api/paieApi.js :: deleteSaisie -> /api/django/paie/saisies/<>  [SaisieArretSerializer]
    champs: actif, creancier, date_annulation, date_creation, date_debut, id, montant_echeance, montant_retenu, montant_total, motif_annulation, prioritaire, profil, reference, solde_restant, soldee, statut, type
- frontend/src/api/paieApi.js :: deleteStructure -> /api/django/paie/structures/<>  [StructurePaieSerializer]
    champs: actif, code, date_creation, description, id, libelle, rubriques_defaut
- frontend/src/api/paieApi.js :: getAdhesionsMutuelle -> /api/django/paie/adhesions-mutuelle  [AdhesionMutuelleSerializer]
    champs: actif, date_creation, date_debut, id, profil, regime, regime_libelle
- frontend/src/api/paieApi.js :: getAvances -> /api/django/paie/avances  [AvanceSalarieSerializer]
    champs: actif, date_creation, date_debut, id, libelle, montant_echeance, montant_rembourse, montant_total, nombre_echeances, profil, solde_restant, soldee, type
- frontend/src/api/paieApi.js :: getBaremes -> /api/django/paie/baremes  [BaremeIRSerializer]
    champs: actif, date_creation, date_effet, id, libelle, tranches, valide_par_fondateur
- frontend/src/api/paieApi.js :: getBulletin -> /api/django/paie/bulletins/<>  [BulletinPaieSerializer]
    champs: allocations_familiales, amo_patronale, amo_salariale, brut, brut_imposable, charges_patronales, cimr_salariale, cnss_patronale, cnss_salariale, date_creation, date_paiement, date_validation, formation_professionnelle, frais_professionnels, id, ir, lignes, lu_le, montant_exonere_regime, motif, net_a_payer, net_imposable, paye, periode, personnes_a_charge, prime_anciennete, profil, provision_conges, provision_conges, rectifie, retenues, statut, type_bulletin
- frontend/src/api/paieApi.js :: getBulletins -> /api/django/paie/bulletins  [BulletinPaieSerializer]
    champs: allocations_familiales, amo_patronale, amo_salariale, brut, brut_imposable, charges_patronales, cimr_salariale, cnss_patronale, cnss_salariale, date_creation, date_paiement, date_validation, formation_professionnelle, frais_professionnels, id, ir, lignes, lu_le, montant_exonere_regime, motif, net_a_payer, net_imposable, paye, periode, personnes_a_charge, prime_anciennete, profil, provision_conges, provision_conges, rectifie, retenues, statut, type_bulletin
- frontend/src/api/paieApi.js :: getCumulsAnnuels -> /api/django/paie/cumuls-annuels  [CumulAnnuelSerializer]
    champs: amo_salariale, annee, brut, brut_imposable, charges_patronales, cimr_salariale, cnss_salariale, conges_acquis, conges_pris, date_calcul, date_creation, frais_professionnels, id, ir, net_a_payer, net_imposable, nombre_bulletins, profil, provision_conges
- frontend/src/api/paieApi.js :: getEcheancesDeclaratives -> /api/django/paie/echeances-declaratives  [EcheanceDeclarativeSerializer]
    champs: date_creation, date_limite, date_notification, en_retard, id, periode, statut, type_echeance
- frontend/src/api/paieApi.js :: getElementsVariables -> /api/django/paie/elements-variables  [ElementVariableSerializer]
    champs: categorie_absence, categorie_hs, date_creation, deduit_solde, id, libelle, montant, periode, profil, quantite, reconduire, reconduit_depuis, remunere, rubrique, source, type, type_entree
- frontend/src/api/paieApi.js :: getLignesVirement -> /api/django/paie/lignes-virement  [LigneVirementSerializer]
    champs: beneficiaire, bulletin, date_rejet, id, ligne_correction, montant, motif_rejet, reference, rejetee, rib
- frontend/src/api/paieApi.js :: getOrdreVirement -> /api/django/paie/ordres-virement/<>  [OrdreVirementSerializer]
    champs: compte_emetteur, compte_emetteur_banque, compte_emetteur_libelle, date_creation, date_emission, date_execution, devise, id, libelle, lignes, nombre_lignes, periode, reference, rib_emetteur, statut, total
- frontend/src/api/paieApi.js :: getOrdresVirement -> /api/django/paie/ordres-virement  [OrdreVirementSerializer]
    champs: compte_emetteur, compte_emetteur_banque, compte_emetteur_libelle, date_creation, date_emission, date_execution, devise, id, libelle, lignes, nombre_lignes, periode, reference, rib_emetteur, statut, total
- frontend/src/api/paieApi.js :: getParametres -> /api/django/paie/parametres  [ParametrePaieSerializer]
    champs: actif, date_creation, date_effet, deduction_par_personne_a_charge, id, plafond_cnss, plafond_frais_pro_bas, plafond_frais_pro_haut, plafond_personnes_a_charge, seuil_frais_pro, smag, smig, taux_allocations_familiales, taux_amo_patronal, taux_amo_salarial, taux_cnss_patronal, taux_cnss_salarial, taux_formation_pro, taux_frais_pro_bas, taux_frais_pro_haut, taux_hs_ferie, taux_hs_jour, taux_hs_nuit, valide_par_fondateur
- frontend/src/api/paieApi.js :: getPeriode -> /api/django/paie/periodes/<>  [PeriodePaieSerializer]
    champs: annee, date_cloture, date_creation, date_paiement, id, libelle, mois, statut, type_run
- frontend/src/api/paieApi.js :: getPeriodes -> /api/django/paie/periodes  [PeriodePaieSerializer]
    champs: annee, date_cloture, date_creation, date_paiement, id, libelle, mois, statut, type_run
- frontend/src/api/paieApi.js :: getProfil -> /api/django/paie/profils/<>  [ProfilPaieSerializer]
    champs: actif, affilie_amo, affilie_cimr, affilie_cnss, banque, date_creation, employe, employe_nom, heures_travail_mensuel, id, jours_travail_mensuel, mode_paiement, numero_amo, numero_cimr, numero_cnss, regime_date_debut, regime_date_fin, regime_exoneration, regime_plafond_mensuel, rib, salaire_base, structure, taux_cimr_salarial, type_remuneration
- frontend/src/api/paieApi.js :: getProfils -> /api/django/paie/profils  [ProfilPaieSerializer]
    champs: actif, affilie_amo, affilie_cimr, affilie_cnss, banque, date_creation, employe, employe_nom, heures_travail_mensuel, id, jours_travail_mensuel, mode_paiement, numero_amo, numero_cimr, numero_cnss, regime_date_debut, regime_date_fin, regime_exoneration, regime_plafond_mensuel, rib, salaire_base, structure, taux_cimr_salarial, type_remuneration
- frontend/src/api/paieApi.js :: getRegimesMutuelle -> /api/django/paie/regimes-mutuelle  [RegimeMutuelleSerializer]
    champs: actif, date_creation, deductible_net_imposable, id, libelle, mode, palier, part_patronale, part_salariale
- frontend/src/api/paieApi.js :: getRubriques -> /api/django/paie/rubriques  [RubriqueSerializer]
    champs: actif, arrondi, avantage_nature, base, code, compte, date_creation, id, imposable, libelle, montant_fixe, ordre, plafond_exoneration, sens_arrondi, soumis_amo, soumis_cimr, soumis_cnss, taux, type
- frontend/src/api/paieApi.js :: getRubriquesEmploye -> /api/django/paie/rubriques-employe  [RubriqueEmployeSerializer]
    champs: actif, date_creation, date_debut, date_fin, id, montant, profil, rubrique, rubrique_code, taux
- frontend/src/api/paieApi.js :: getSaisies -> /api/django/paie/saisies  [SaisieArretSerializer]
    champs: actif, creancier, date_annulation, date_creation, date_debut, id, montant_echeance, montant_retenu, montant_total, motif_annulation, prioritaire, profil, reference, solde_restant, soldee, statut, type
- frontend/src/api/paieApi.js :: getStructures -> /api/django/paie/structures  [StructurePaieSerializer]
    champs: actif, code, date_creation, description, id, libelle, rubriques_defaut
- frontend/src/api/paieApi.js :: updateEcheanceDeclarative -> /api/django/paie/echeances-declaratives/<>  [EcheanceDeclarativeSerializer]
    champs: date_creation, date_limite, date_notification, en_retard, id, periode, statut, type_echeance
- frontend/src/api/paieApi.js :: updatePeriode -> /api/django/paie/periodes/<>  [PeriodePaieSerializer]
    champs: annee, date_cloture, date_creation, date_paiement, id, libelle, mois, statut, type_run
- frontend/src/api/parametresApi.js :: createConditionPaiement -> /api/django/parametres/conditions-paiement  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: createTauxTva -> /api/django/parametres/taux-tva  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: createUniteMesure -> /api/django/parametres/unites-mesure  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/parametresApi.js :: deleteConditionPaiement -> /api/django/parametres/conditions-paiement/<>  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: deleteTauxTva -> /api/django/parametres/taux-tva/<>  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: deleteUniteMesure -> /api/django/parametres/unites-mesure/<>  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/parametresApi.js :: getConditionsPaiement -> /api/django/parametres/conditions-paiement  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: getTauxTva -> /api/django/parametres/taux-tva  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: getUnitesMesure -> /api/django/parametres/unites-mesure  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/parametresApi.js :: updateConditionPaiement -> /api/django/parametres/conditions-paiement/<>  [ConditionPaiementSerializer]
    champs: actif, delai_jours, escompte_pct, fin_de_mois, id, libelle
- frontend/src/api/parametresApi.js :: updateTauxTva -> /api/django/parametres/taux-tva/<>  [TauxTVASerializer]
    champs: actif, code, defaut, id, libelle, taux
- frontend/src/api/parametresApi.js :: updateUniteMesure -> /api/django/parametres/unites-mesure/<>  [UniteMesureSerializer]
    champs: actif, code, id, libelle
- frontend/src/api/posApi.js :: createConfigMateriel -> /api/django/pos/config-materiel  [ConfigMaterielPOSSerializer]
    champs: id, imprimante_active, imprimante_ip, imprimante_port
- frontend/src/api/posApi.js :: createRetrait -> /api/django/pos/retraits  [CommandeRetraitSerializer]
    champs: client, client_nom, code_retrait, created_by, date_creation, date_pret, date_retrait, devis, id, lignes, reference, statut, vente_comptoir
    statut ∈ {a_preparer, annule, pret, retire}
- frontend/src/api/posApi.js :: createVente -> /api/django/pos/ventes  [VenteComptoirSerializer]
    champs: caissier, client, client_nom, created_by, date_creation, date_validation, facture, id, lignes, note, reference, session_caisse, statut, taux_tva, total_ht, total_ttc
    statut ∈ {annulee, brouillon, validee}
- frontend/src/api/posApi.js :: getConfigMateriel -> /api/django/pos/config-materiel  [ConfigMaterielPOSSerializer]
    champs: id, imprimante_active, imprimante_ip, imprimante_port
- frontend/src/api/posApi.js :: getProduits -> /api/django/stock/produits  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/posApi.js :: getRetraits -> /api/django/pos/retraits  [CommandeRetraitSerializer]
    champs: client, client_nom, code_retrait, created_by, date_creation, date_pret, date_retrait, devis, id, lignes, reference, statut, vente_comptoir
    statut ∈ {a_preparer, annule, pret, retire}
- frontend/src/api/posApi.js :: getSessions -> /api/django/pos/sessions  [SessionCaisseSerializer]
    champs: caisse_comptable, caissier, cloture_caisse_comptable, commentaire, date_cloture, date_ouverture, ecart_tpe, fond_ouverture, id, montant_compte_cloture, montant_tpe_compte, statut
    statut ∈ {cloturee, ouverte}
- frontend/src/api/posApi.js :: getVente -> /api/django/pos/ventes/<>  [VenteComptoirSerializer]
    champs: caissier, client, client_nom, created_by, date_creation, date_validation, facture, id, lignes, note, reference, session_caisse, statut, taux_tva, total_ht, total_ttc
    statut ∈ {annulee, brouillon, validee}
- frontend/src/api/posApi.js :: ouvrirSession -> /api/django/pos/sessions  [SessionCaisseSerializer]
    champs: caisse_comptable, caissier, cloture_caisse_comptable, commentaire, date_cloture, date_ouverture, ecart_tpe, fond_ouverture, id, montant_compte_cloture, montant_tpe_compte, statut
    statut ∈ {cloturee, ouverte}
- frontend/src/api/posApi.js :: updateConfigMateriel -> /api/django/pos/config-materiel/<>  [ConfigMaterielPOSSerializer]
    champs: id, imprimante_active, imprimante_ip, imprimante_port
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
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, nom, operateur, operateur_label, seuil, updated_at
    kpi ∈ {dso, encours_echu_total, valeur_stock_totale}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
- frontend/src/api/reportingApi.js :: createRapportDefinition -> /api/django/reporting/rapport-definitions  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: createSavedReport -> /api/django/reporting/saved-reports  [SavedReportSerializer]
    champs: created_at, definition, id, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, none, weekly}
    target_kind ∈ {sales, service, stock}
- frontend/src/api/reportingApi.js :: deleteClasseur -> /api/django/reporting/classeurs/<>  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: deleteDashboardConfig -> /api/django/reporting/dashboard-config/<>  [DashboardConfigSerializer]
    champs: cards, created_at, id, menu_tier, updated_at, user
- frontend/src/api/reportingApi.js :: deleteKpiAlerte -> /api/django/reporting/kpi-alertes/<>  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, nom, operateur, operateur_label, seuil, updated_at
    kpi ∈ {dso, encours_echu_total, valeur_stock_totale}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
- frontend/src/api/reportingApi.js :: deleteRapportDefinition -> /api/django/reporting/rapport-definitions/<>  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: deleteSavedReport -> /api/django/reporting/saved-reports/<>  [SavedReportSerializer]
    champs: created_at, definition, id, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, none, weekly}
    target_kind ∈ {sales, service, stock}
- frontend/src/api/reportingApi.js :: getClasseur -> /api/django/reporting/classeurs/<>  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: listClasseurs -> /api/django/reporting/classeurs  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: listDashboardConfigs -> /api/django/reporting/dashboard-config  [DashboardConfigSerializer]
    champs: cards, created_at, id, menu_tier, updated_at, user
- frontend/src/api/reportingApi.js :: listKpiAlertes -> /api/django/reporting/kpi-alertes  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, nom, operateur, operateur_label, seuil, updated_at
    kpi ∈ {dso, encours_echu_total, valeur_stock_totale}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
- frontend/src/api/reportingApi.js :: listRapportDefinitions -> /api/django/reporting/rapport-definitions  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: listSavedReports -> /api/django/reporting/saved-reports  [SavedReportSerializer]
    champs: created_at, definition, id, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, none, weekly}
    target_kind ∈ {sales, service, stock}
- frontend/src/api/reportingApi.js :: updateClasseur -> /api/django/reporting/classeurs/<>  [ClasseurSerializer]
    champs: cellules, created_at, id, liens, partage, titre, updated_at
- frontend/src/api/reportingApi.js :: updateKpiAlerte -> /api/django/reporting/kpi-alertes/<>  [KpiAlerteSerializer]
    champs: actif, created_at, deja_notifie, derniere_evaluation_le, derniere_valeur, destinataire_role, destinataires_utilisateurs, id, kpi, kpi_label, nom, operateur, operateur_label, seuil, updated_at
    kpi ∈ {dso, encours_echu_total, valeur_stock_totale}
    operateur ∈ {inf, inf_egal, sup, sup_egal}
- frontend/src/api/reportingApi.js :: updateRapportDefinition -> /api/django/reporting/rapport-definitions/<>  [RapportDefinitionSerializer]
    champs: created_at, dataset, id, owner_username, partage, partage_label, pivot_spec, spec, titre, updated_at
    partage ∈ {prive, societe}
- frontend/src/api/reportingApi.js :: updateSavedReport -> /api/django/reporting/saved-reports/<>  [SavedReportSerializer]
    champs: created_at, definition, id, last_sent_at, name, pinned, recipients, schedule, schedule_label, target_kind, target_kind_label, updated_at
    schedule ∈ {daily, none, weekly}
    target_kind ∈ {sales, service, stock}
- frontend/src/api/rhApi.js :: attribuerBadge -> /api/django/rh/attributions-badge  [AttributionBadgeSerializer]
    champs: attribue_par, attribue_par_nom, badge, badge_icone, badge_nom, beneficiaire, beneficiaire_nom, date_creation, id, message
- frontend/src/api/rhApi.js :: createAffectationVehicule -> /api/django/rh/affectations-vehicule  [AffectationVehiculeSerializer]
    champs: date_creation, date_debut, date_fin, date_modification, employe, employe_nom, id, note, permis_verifie, statut, statut_display, vehicule_id
    statut ∈ {active, terminee}
- frontend/src/api/rhApi.js :: createCandidature -> /api/django/rh/candidatures  [CandidatureSerializer]
    champs: cv_fichier, date_candidature, date_creation, date_modification, email, emails_auto, employe_cree, employe_cree_nom, etape, etape_display, id, nom, note, ouverture, ouverture_intitule, source, tags_vivier, telephone, vivier, vivier_origine
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: createCauserieSecurite -> /api/django/rh/causeries-securite  [CauserieSecuriteSerializer]
    champs: animateur, animateur_nom, chantier_id, date_causerie, date_creation, date_modification, id, lieu, notes, participants, theme
- frontend/src/api/rhApi.js :: createCertification -> /api/django/rh/certifications  [CertificationSerializer]
    champs: actif, date_creation, date_modification, date_obtention, date_validite, employe, employe_nom, id, note, organisme, type_certification, type_certification_display, valide
    type_certification ∈ {autre, caces_nacelle, conduite, harnais, secourisme_sst, travail_hauteur}
- frontend/src/api/rhApi.js :: createCompetence -> /api/django/rh/competences  [CompetenceSerializer]
    champs: actif, code, date_creation, date_modification, description, domaine, domaine_display, id, libelle
    domaine ∈ {autre, mes_onduleur, pompage, pose_structure, raccordement_ac, raccordement_dc, soudure}
- frontend/src/api/rhApi.js :: createCompetenceEmploye -> /api/django/rh/competences-employe  [CompetenceEmployeSerializer]
    champs: competence, competence_code, competence_libelle, date_creation, date_modification, employe, employe_nom, evalue_le, evalue_par, id, niveau, niveau_display, note
- frontend/src/api/rhApi.js :: createDemandeConge -> /api/django/rh/demandes-conge  [DemandeCongeSerializer]
    champs: date_creation, date_debut, date_decision, date_fin, decide_par, demi_journee_debut, demi_journee_fin, employe, id, jours, justificatif, motif, motif_refus, statut, statut_display, type_absence, type_absence_code
    statut ∈ {annulee, refusee, soumise, validee}
- frontend/src/api/rhApi.js :: createDeviceEmployeMap -> /api/django/rh/devices-employe-map  [EmployeDeviceMapSerializer]
    champs: date_creation, device_user_id, employe, employe_nom, id
- frontend/src/api/rhApi.js :: createElementIntegration -> /api/django/rh/elements-integration  [ElementIntegrationSerializer]
    champs: date_creation, id, libelle, modele, ordre
- frontend/src/api/rhApi.js :: createElementVariablePaie -> /api/django/rh/elements-variables-paie  [ElementsVariablesPaieSerializer]
    champs: annee, commentaire, date_creation, date_export, date_modification, employe, employe_matricule, employe_nom, heures_normales, heures_supp, id, jours_absence, jours_conges, mois, primes, retenues, statut, statut_display
    statut ∈ {brouillon, exporte, valide}
- frontend/src/api/rhApi.js :: createEntretienRecrutement -> /api/django/rh/entretiens-recrutement  [EntretienRecrutementSerializer]
    champs: candidature, date_creation, date_heure, evaluateurs, id, notes, statut, statut_display, type, type_display
    statut ∈ {annule, planifie, realise}
    type ∈ {final, rh, technique, telephonique}
- frontend/src/api/rhApi.js :: createEntretienSortie -> /api/django/rh/entretiens-sortie  [EntretienSortieSerializer]
    champs: commentaire, date, date_creation, date_modification, employe, employe_nom, id, motif_principal, motif_principal_display, questionnaire, recommanderait
    motif_principal ∈ {autre, conditions, distance, management, opportunite, salaire, sante}
- frontend/src/api/rhApi.js :: createGabaritEmailRecrutement -> /api/django/rh/gabarits-email-recrutement  [GabaritEmailRecrutementSerializer]
    champs: actif, corps, date_creation, etape, etape_display, id, objet
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: createGrilleSalariale -> /api/django/rh/grilles-salariales  [GrilleSalarialeSerializer]
    champs: date_creation, date_effet, echelon, id, poste, poste_intitule, salaire_max, salaire_min
- frontend/src/api/rhApi.js :: createHabilitation -> /api/django/rh/habilitations  [HabilitationSerializer]
    champs: actif, date_creation, date_modification, date_obtention, date_validite, employe, employe_nom, id, note, organisme, type_habilitation, type_habilitation_display, valide
    type_habilitation ∈ {autre, b0, b1, b1v, b2, b2v, bc, be, bp, br, h0, h0v, h1, h1v, h2, h2v, hc}
- frontend/src/api/rhApi.js :: createHoraireTravail -> /api/django/rh/horaires-travail  [HoraireTravailSerializer]
    champs: actif, date_creation, date_debut, date_fin, heures_jour_defaut, heures_semaine, id, nom, type_horaire, type_horaire_display
    type_horaire ∈ {ramadan, saisonnier, standard_44h, temps_partiel}
- frontend/src/api/rhApi.js :: createJourBloqueConge -> /api/django/rh/jours-bloques-conge  [JourBloqueCongeSerializer]
    champs: date_creation, date_debut, date_fin, date_modification, departements, id, libelle, motif
- frontend/src/api/rhApi.js :: createLigneParcours -> /api/django/rh/lignes-parcours  [LigneParcoursSerializer]
    champs: date_creation, date_debut, date_fin, description, employe, id, intitule, organisme, type, type_libelle
- frontend/src/api/rhApi.js :: createModeleEvaluation -> /api/django/rh/modeles-evaluation  [ModeleEvaluationSerializer]
    champs: actif, date_creation, date_modification, departement, id, nom, poste_ref, questions
- frontend/src/api/rhApi.js :: createModeleIntegration -> /api/django/rh/modeles-integration  [ModeleIntegrationSerializer]
    champs: actif, date_creation, departement, elements, id, nom, poste_ref
- frontend/src/api/rhApi.js :: createOuverturePoste -> /api/django/rh/ouvertures-poste  [OuverturePosteSerializer]
    champs: approbateur, candidatures, date_cible, date_creation, date_decision, date_modification, date_ouverture, date_soumission, demandeur, departement, departement_nom, description, id, intitule, motif_refus, nombre_postes, poste_ref, poste_ref_intitule, publiee, statut, statut_display, ville
    statut ∈ {annule, brouillon, clos, en_approbation, ouvert, pourvu}
- frontend/src/api/rhApi.js :: createPeriodeFermeture -> /api/django/rh/periodes-fermeture  [PeriodeFermetureSerializer]
    champs: appliquee, appliquee_le, date_creation, date_debut, date_fin, departements, id, libelle, type_absence, type_absence_code
- frontend/src/api/rhApi.js :: createPermisConduire -> /api/django/rh/permis-conduire  [PermisConduireSerializer]
    champs: categorie, categorie_display, date_creation, date_delivrance, date_expiration, date_modification, employe, employe_nom, habilitation_conduite, id, note, numero, valide
    categorie ∈ {A, B, C, D, EB, EC}
- frontend/src/api/rhApi.js :: createPresquAccident -> /api/django/rh/presqu-accidents  [PresquAccidentSerializer]
    champs: chantier_id, date_constat, date_creation, date_modification, declare_par, declare_par_nom, description, gravite_potentielle, gravite_potentielle_display, id, lieu, mesure_corrective, photo_key, reference, statut, statut_display
    gravite_potentielle ∈ {elevee, faible, moyenne}
    statut ∈ {ouvert, traite}
- frontend/src/api/rhApi.js :: createPrimeAttribuee -> /api/django/rh/primes-attribuees  [PrimeAttribueeSerializer]
    champs: annee, date_creation, date_modification, employe, employe_nom, id, mois, montant, motif, statut, statut_display, type_prime, type_prime_libelle
    statut ∈ {payee, proposee, validee}
- frontend/src/api/rhApi.js :: createPromesseEmbauche -> /api/django/rh/promesses-embauche  [PromesseEmbaucheSerializer]
    champs: candidature, candidature_nom, date_creation, date_debut_proposee, date_signature, expires_at, id, poste_propose, salaire_propose, signataire_nom, statut, statut_display, token, type_contrat
    statut ∈ {envoyee, expiree, signee}
    type_contrat ∈ {anapec, cdd, cdi, interim, stage}
- frontend/src/api/rhApi.js :: createRemuneration -> /api/django/rh/remunerations  [RemunerationSerializer]
    champs: date_creation, date_effet, devise, employe, id, montant, motif, periodicite, periodicite_display
    periodicite ∈ {annuel, horaire, journalier, mensuel}
- frontend/src/api/rhApi.js :: createRetourFeedback360 -> /api/django/rh/retours-feedback360  [RetourFeedback360Serializer]
    champs: commentaire, date_invitation, date_soumission, evaluation, id, relation, repondant, repondant_nom, reponses, soumis
    relation ∈ {manager_transversal, pair, subordonne}
- frontend/src/api/rhApi.js :: createTypeLigneParcours -> /api/django/rh/types-ligne-parcours  [TypeLigneParcoursSerializer]
    champs: id, libelle, ordre
- frontend/src/api/rhApi.js :: createTypePrime -> /api/django/rh/types-prime  [TypePrimeSerializer]
    champs: actif, code, date_creation, id, imposable, libelle, montant_defaut, nature, nature_display
    nature ∈ {indemnite, prime}
- frontend/src/api/rhApi.js :: createVisiteMedicale -> /api/django/rh/visites-medicales  [VisiteMedicaleSerializer]
    champs: a_jour, actif, aptitude, aptitude_display, date_creation, date_modification, date_visite, employe, employe_nom, id, medecin, note, organisme, prochaine_visite, restrictions
    aptitude ∈ {apte, apte_avec_restrictions, inapte}
- frontend/src/api/rhApi.js :: deleteElementIntegration -> /api/django/rh/elements-integration/<>  [ElementIntegrationSerializer]
    champs: date_creation, id, libelle, modele, ordre
- frontend/src/api/rhApi.js :: deleteGabaritEmailRecrutement -> /api/django/rh/gabarits-email-recrutement/<>  [GabaritEmailRecrutementSerializer]
    champs: actif, corps, date_creation, etape, etape_display, id, objet
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: deleteGrilleSalariale -> /api/django/rh/grilles-salariales/<>  [GrilleSalarialeSerializer]
    champs: date_creation, date_effet, echelon, id, poste, poste_intitule, salaire_max, salaire_min
- frontend/src/api/rhApi.js :: deleteJourBloqueConge -> /api/django/rh/jours-bloques-conge/<>  [JourBloqueCongeSerializer]
    champs: date_creation, date_debut, date_fin, date_modification, departements, id, libelle, motif
- frontend/src/api/rhApi.js :: deleteModeleEvaluation -> /api/django/rh/modeles-evaluation/<>  [ModeleEvaluationSerializer]
    champs: actif, date_creation, date_modification, departement, id, nom, poste_ref, questions
- frontend/src/api/rhApi.js :: getAffectationsVehicule -> /api/django/rh/affectations-vehicule  [AffectationVehiculeSerializer]
    champs: date_creation, date_debut, date_fin, date_modification, employe, employe_nom, id, note, permis_verifie, statut, statut_display, vehicule_id
    statut ∈ {active, terminee}
- frontend/src/api/rhApi.js :: getAnalysesRisques -> /api/django/rh/analyses-risques-chantier  [AnalyseRisquesChantierSerializer]
    champs: chantier_id, date_analyse, date_creation, date_modification, id, lieu, notes, redacteur, redacteur_nom, risques, statut, statut_display
    statut ∈ {brouillon, valide}
- frontend/src/api/rhApi.js :: getAttributionsBadge -> /api/django/rh/attributions-badge  [AttributionBadgeSerializer]
    champs: attribue_par, attribue_par_nom, badge, badge_icone, badge_nom, beneficiaire, beneficiaire_nom, date_creation, id, message
- frontend/src/api/rhApi.js :: getAvancesSalaire -> /api/django/rh/avances-salaire  [AvanceSalaireSerializer]
    champs: annee_deduction, date_creation, date_demande, date_modification, employe, employe_nom, id, mois_deduction, montant, motif, paie_avance_id, solde_restant, statut, statut_display, valideur
    statut ∈ {approuvee, deduite, demandee, refusee}
- frontend/src/api/rhApi.js :: getAvantagesSociaux -> /api/django/rh/avantages-sociaux  [AvantageSocialSerializer]
    champs: date_adhesion, date_creation, date_fin, date_modification, employe, id, organisme, type, type_display
    type ∈ {assurance_groupe, autre, cimr, mutuelle}
- frontend/src/api/rhApi.js :: getAyantsDroit -> /api/django/rh/ayants-droit  [AyantDroitSerializer]
    champs: couvert_amo, couvert_mutuelle, date_creation, date_modification, date_naissance, employe, id, lien, lien_display, nom
    lien ∈ {autre, conjoint, enfant}
- frontend/src/api/rhApi.js :: getBadgesReconnaissance -> /api/django/rh/badges-reconnaissance  [BadgeReconnaissanceSerializer]
    champs: actif, date_creation, description, icone, id, nom, nombre_attributions
- frontend/src/api/rhApi.js :: getBesoinsFormation -> /api/django/rh/besoins-formation  [BesoinFormationSerializer]
    champs: date_creation, date_modification, echeance, employe, employe_nom, id, notes, obligation_reglementaire, priorite, priorite_display, session_liee, session_liee_intitule, statut, statut_display, theme, type_obligation, type_obligation_display
    priorite ∈ {basse, haute, moyenne}
    statut ∈ {identifie, planifie, satisfait}
    type_obligation ∈ {autre, csf, ofppt}
- frontend/src/api/rhApi.js :: getCampagnesEvaluation -> /api/django/rh/campagnes-evaluation  [CampagneEvaluationSerializer]
    champs: annee, date_creation, date_debut, date_fin, date_modification, description, evaluations, id, intitule, modele, periode, statut, statut_display
    statut ∈ {cloturee, ouverte}
- frontend/src/api/rhApi.js :: getCampagnesPulse -> /api/django/rh/campagnes-pulse  [CampagnePulseSerializer]
    champs: date_creation, date_debut, date_fin, id, question_enps, question_libre
- frontend/src/api/rhApi.js :: getCandidatures -> /api/django/rh/candidatures  [CandidatureSerializer]
    champs: cv_fichier, date_candidature, date_creation, date_modification, email, emails_auto, employe_cree, employe_cree_nom, etape, etape_display, id, nom, note, ouverture, ouverture_intitule, source, tags_vivier, telephone, vivier, vivier_origine
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: getCauseriesSecurite -> /api/django/rh/causeries-securite  [CauserieSecuriteSerializer]
    champs: animateur, animateur_nom, chantier_id, date_causerie, date_creation, date_modification, id, lieu, notes, participants, theme
- frontend/src/api/rhApi.js :: getCertifications -> /api/django/rh/certifications  [CertificationSerializer]
    champs: actif, date_creation, date_modification, date_obtention, date_validite, employe, employe_nom, id, note, organisme, type_certification, type_certification_display, valide
    type_certification ∈ {autre, caces_nacelle, conduite, harnais, secourisme_sst, travail_hauteur}
- frontend/src/api/rhApi.js :: getCompetences -> /api/django/rh/competences  [CompetenceSerializer]
    champs: actif, code, date_creation, date_modification, description, domaine, domaine_display, id, libelle
    domaine ∈ {autre, mes_onduleur, pompage, pose_structure, raccordement_ac, raccordement_dc, soudure}
- frontend/src/api/rhApi.js :: getCompetencesEmploye -> /api/django/rh/competences-employe  [CompetenceEmployeSerializer]
    champs: competence, competence_code, competence_libelle, date_creation, date_modification, employe, employe_nom, evalue_le, evalue_par, id, niveau, niveau_display, note
- frontend/src/api/rhApi.js :: getCompetencesRequises -> /api/django/rh/competences-requises  [CompetenceRequiseSerializer]
    champs: competence, competence_libelle, date_creation, id, niveau_requis, niveau_requis_display, poste
- frontend/src/api/rhApi.js :: getDemandesAllocation -> /api/django/rh/demandes-allocation  [DemandeAllocationSerializer]
    champs: date_creation, date_decision, decide_par, employe, employe_nom, id, jours, motif, statut, statut_display, type_absence, type_absence_code
    statut ∈ {refusee, soumise, validee}
- frontend/src/api/rhApi.js :: getDemandesConge -> /api/django/rh/demandes-conge  [DemandeCongeSerializer]
    champs: date_creation, date_debut, date_decision, date_fin, decide_par, demi_journee_debut, demi_journee_fin, employe, id, jours, justificatif, motif, motif_refus, statut, statut_display, type_absence, type_absence_code
    statut ∈ {annulee, refusee, soumise, validee}
- frontend/src/api/rhApi.js :: getDemandesRh -> /api/django/rh/demandes-rh  [DemandeRHSerializer]
    champs: attachment_id, date_creation, date_modification, employe, employe_nom, id, message, motif_refus, statut, statut_display, traite_le, traite_par, type, type_display
    statut ∈ {refusee, soumise, traitee}
    type ∈ {attestation_domiciliation, attestation_salaire, attestation_travail, autre}
- frontend/src/api/rhApi.js :: getDepartements -> /api/django/rh/departements  [DepartementSerializer]
    champs: actif, code, date_creation, id, nom, parent
- frontend/src/api/rhApi.js :: getDevicesEmployeMap -> /api/django/rh/devices-employe-map  [EmployeDeviceMapSerializer]
    champs: date_creation, device_user_id, employe, employe_nom, id
- frontend/src/api/rhApi.js :: getDevicesKiosque -> /api/django/rh/devices-kiosque  [DeviceKiosqueSerializer]
    champs: actif, date_creation, derniere_utilisation, id, label
- frontend/src/api/rhApi.js :: getDotationsEpi -> /api/django/rh/dotations-epi  [DotationEpiSerializer]
    champs: a_controler, accuse_remise, date_accuse, date_creation, date_dotation, date_modification, date_peremption, date_prochain_controle, date_renouvellement, date_restitution, employe, employe_nom, epi, epi_designation, id, note, perime, quantite, restituee, taille, type_epi, type_epi_display
- frontend/src/api/rhApi.js :: getElementsIntegration -> /api/django/rh/elements-integration  [ElementIntegrationSerializer]
    champs: date_creation, id, libelle, modele, ordre
- frontend/src/api/rhApi.js :: getElementsSortie -> /api/django/rh/elements-sortie  [ElementSortieSerializer]
    champs: date_creation, date_recuperation, employe, id, libelle, note, recupere, type_element, type_element_display
    type_element ∈ {acces_si, autre, badge, cles, epi, ordinateur, outil, telephone, vehicule}
- frontend/src/api/rhApi.js :: getElementsVariablesPaie -> /api/django/rh/elements-variables-paie  [ElementsVariablesPaieSerializer]
    champs: annee, commentaire, date_creation, date_export, date_modification, employe, employe_matricule, employe_nom, heures_normales, heures_supp, id, jours_absence, jours_conges, mois, primes, retenues, statut, statut_display
    statut ∈ {brouillon, exporte, valide}
- frontend/src/api/rhApi.js :: getEntretiensRecrutement -> /api/django/rh/entretiens-recrutement  [EntretienRecrutementSerializer]
    champs: candidature, date_creation, date_heure, evaluateurs, id, notes, statut, statut_display, type, type_display
    statut ∈ {annule, planifie, realise}
    type ∈ {final, rh, technique, telephonique}
- frontend/src/api/rhApi.js :: getEntretiensSortie -> /api/django/rh/entretiens-sortie  [EntretienSortieSerializer]
    champs: commentaire, date, date_creation, date_modification, employe, employe_nom, id, motif_principal, motif_principal_display, questionnaire, recommanderait
    motif_principal ∈ {autre, conditions, distance, management, opportunite, salaire, sante}
- frontend/src/api/rhApi.js :: getEpiCatalogue -> /api/django/rh/epi-catalogue  [EpiCatalogueSerializer]
    champs: actif, date_creation, date_modification, designation, duree_vie_mois, id, intervalle_controle_mois, produit_id, type_epi, type_epi_display
    type_epi ∈ {autre, casque, chaussures, gants_isolants, harnais, lunettes}
- frontend/src/api/rhApi.js :: getEvaluationsEmploye -> /api/django/rh/evaluations-employe  [EvaluationEmployeSerializer]
    champs: auto_evaluation, campagne, date_creation, date_entretien, date_modification, employe, employe_nom, evaluateur, evaluateur_nom, id, issue, issue_details, note_auto, note_globale, objectifs, reponses, statut, statut_display, synthese
    issue ∈ {aucune, augmentation_proposee, formation, pip, promotion}
    statut ∈ {planifie, realise, valide}
- frontend/src/api/rhApi.js :: getFeuillesTemps -> /api/django/rh/feuilles-temps  [FeuilleTempsSerializer]
    champs: cout_calcule, date, date_creation, date_modification, description, employe, employe_nom, heures, id, installation_id, intervention_id, taux_horaire
- frontend/src/api/rhApi.js :: getGabaritsEmailRecrutement -> /api/django/rh/gabarits-email-recrutement  [GabaritEmailRecrutementSerializer]
    champs: actif, corps, date_creation, etape, etape_display, id, objet
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: getGrillesSalariales -> /api/django/rh/grilles-salariales  [GrilleSalarialeSerializer]
    champs: date_creation, date_effet, echelon, id, poste, poste_intitule, salaire_max, salaire_min
- frontend/src/api/rhApi.js :: getHabilitations -> /api/django/rh/habilitations  [HabilitationSerializer]
    champs: actif, date_creation, date_modification, date_obtention, date_validite, employe, employe_nom, id, note, organisme, type_habilitation, type_habilitation_display, valide
    type_habilitation ∈ {autre, b0, b1, b1v, b2, b2v, bc, be, bp, br, h0, h0v, h1, h1v, h2, h2v, hc}
- frontend/src/api/rhApi.js :: getHeuresSupp -> /api/django/rh/heures-supp  [HeuresSuppSerializer]
    champs: date, date_creation, date_modification, employe, employe_nom, heures_normales, heures_nuit, heures_travaillees, hs_100, hs_25, hs_50, id, jour_repos_ferie, montant_majore, note, seuil_journalier, taux_horaire, total_hs
- frontend/src/api/rhApi.js :: getHorairesTravail -> /api/django/rh/horaires-travail  [HoraireTravailSerializer]
    champs: actif, date_creation, date_debut, date_fin, heures_jour_defaut, heures_semaine, id, nom, type_horaire, type_horaire_display
    type_horaire ∈ {ramadan, saisonnier, standard_44h, temps_partiel}
- frontend/src/api/rhApi.js :: getIncidentsPresence -> /api/django/rh/incidents-presence  [IncidentPresenceSerializer]
    champs: date, date_creation, date_modification, employe, employe_nom, id, justifie, justifie_le, justifie_par, minutes_retard, motif, note, type_incident, type_incident_display
    type_incident ∈ {absence_injustifiee, depart_anticipe, retard}
- frontend/src/api/rhApi.js :: getJoursBloquesConge -> /api/django/rh/jours-bloques-conge  [JourBloqueCongeSerializer]
    champs: date_creation, date_debut, date_fin, date_modification, departements, id, libelle, motif
- frontend/src/api/rhApi.js :: getLignesParcours -> /api/django/rh/lignes-parcours  [LigneParcoursSerializer]
    champs: date_creation, date_debut, date_fin, description, employe, id, intitule, organisme, type, type_libelle
- frontend/src/api/rhApi.js :: getModelesEvaluation -> /api/django/rh/modeles-evaluation  [ModeleEvaluationSerializer]
    champs: actif, date_creation, date_modification, departement, id, nom, poste_ref, questions
- frontend/src/api/rhApi.js :: getModelesIntegration -> /api/django/rh/modeles-integration  [ModeleIntegrationSerializer]
    champs: actif, date_creation, departement, elements, id, nom, poste_ref
- frontend/src/api/rhApi.js :: getNotesFrais -> /api/django/rh/notes-frais  [NoteDeFraisSerializer]
    champs: categorie, categorie_display, date_creation, date_frais, date_modification, employe, employe_nom, id, libelle, montant, statut, statut_display
    categorie ∈ {autre, fournitures, hebergement, repas, transport}
    statut ∈ {approuvee, refusee, remboursee, soumise}
- frontend/src/api/rhApi.js :: getOrdresMission -> /api/django/rh/ordres-mission  [OrdreMissionSerializer]
    champs: date_creation, date_depart, date_modification, date_retour, destination, employe, employe_nom, id, motif, moyen_transport, per_diem, reference, statut, statut_display, vehicule_id
    statut ∈ {brouillon, cloture, emis}
- frontend/src/api/rhApi.js :: getOuverturesPoste -> /api/django/rh/ouvertures-poste  [OuverturePosteSerializer]
    champs: approbateur, candidatures, date_cible, date_creation, date_decision, date_modification, date_ouverture, date_soumission, demandeur, departement, departement_nom, description, id, intitule, motif_refus, nombre_postes, poste_ref, poste_ref_intitule, publiee, statut, statut_display, ville
    statut ∈ {annule, brouillon, clos, en_approbation, ouvert, pourvu}
- frontend/src/api/rhApi.js :: getPeriodesFermeture -> /api/django/rh/periodes-fermeture  [PeriodeFermetureSerializer]
    champs: appliquee, appliquee_le, date_creation, date_debut, date_fin, departements, id, libelle, type_absence, type_absence_code
- frontend/src/api/rhApi.js :: getPermisConduire -> /api/django/rh/permis-conduire  [PermisConduireSerializer]
    champs: categorie, categorie_display, date_creation, date_delivrance, date_expiration, date_modification, employe, employe_nom, habilitation_conduite, id, note, numero, valide
    categorie ∈ {A, B, C, D, EB, EC}
- frontend/src/api/rhApi.js :: getPostes -> /api/django/rh/postes  [PosteSerializer]
    champs: actif, code, date_creation, departement, departement_nom, id, intitule
- frontend/src/api/rhApi.js :: getPresencesChantier -> /api/django/rh/presences-chantier  [PresenceChantierSerializer]
    champs: date, date_creation, date_modification, emarge, emarge_le, emarge_par, employe, employe_nom, gps_lat, gps_lng, heure_arrivee, heure_depart, hors_zone, id, installation_id, note, statut, statut_display
    statut ∈ {absent, parti_tot, present, retard}
- frontend/src/api/rhApi.js :: getPresquAccidents -> /api/django/rh/presqu-accidents  [PresquAccidentSerializer]
    champs: chantier_id, date_constat, date_creation, date_modification, declare_par, declare_par_nom, description, gravite_potentielle, gravite_potentielle_display, id, lieu, mesure_corrective, photo_key, reference, statut, statut_display
    gravite_potentielle ∈ {elevee, faible, moyenne}
    statut ∈ {ouvert, traite}
- frontend/src/api/rhApi.js :: getPrimesAttribuees -> /api/django/rh/primes-attribuees  [PrimeAttribueeSerializer]
    champs: annee, date_creation, date_modification, employe, employe_nom, id, mois, montant, motif, statut, statut_display, type_prime, type_prime_libelle
    statut ∈ {payee, proposee, validee}
- frontend/src/api/rhApi.js :: getPromessesEmbauche -> /api/django/rh/promesses-embauche  [PromesseEmbaucheSerializer]
    champs: candidature, candidature_nom, date_creation, date_debut_proposee, date_signature, expires_at, id, poste_propose, salaire_propose, signataire_nom, statut, statut_display, token, type_contrat
    statut ∈ {envoyee, expiree, signee}
    type_contrat ∈ {anapec, cdd, cdi, interim, stage}
- frontend/src/api/rhApi.js :: getRemunerations -> /api/django/rh/remunerations  [RemunerationSerializer]
    champs: date_creation, date_effet, devise, employe, id, montant, motif, periodicite, periodicite_display
    periodicite ∈ {annuel, horaire, journalier, mensuel}
- frontend/src/api/rhApi.js :: getRetoursFeedback360 -> /api/django/rh/retours-feedback360  [RetourFeedback360Serializer]
    champs: commentaire, date_invitation, date_soumission, evaluation, id, relation, repondant, repondant_nom, reponses, soumis
    relation ∈ {manager_transversal, pair, subordonne}
- frontend/src/api/rhApi.js :: getRoster -> /api/django/rh/roster  [AffectationRosterSerializer]
    champs: conflit_conge, creneau, creneau_display, date, date_creation, date_modification, employe, employe_nom, equipe, id, note, semaine_du, vehicule_id
    creneau ∈ {apres_midi, journee, matin}
- frontend/src/api/rhApi.js :: getSanctions -> /api/django/rh/sanctions  [SanctionSerializer]
    champs: auteur, date_creation, date_faits, date_modification, date_notification, duree_jours, employe, employe_nom, id, motif, statut, statut_display, type_sanction, type_sanction_display
    statut ∈ {annulee, contestee, notifiee}
    type_sanction ∈ {avertissement, blame, licenciement, mise_a_pied, mutation, observation, retrogradation}
- frontend/src/api/rhApi.js :: getSessionsFormation -> /api/django/rh/sessions-formation  [SessionFormationSerializer]
    champs: competence_visee, competence_visee_libelle, cout, date_creation, date_debut, date_fin, date_modification, id, inscriptions, intitule, lieu, notes, organisme, statut, statut_display, type, type_display
    statut ∈ {annulee, planifiee, realisee}
    type ∈ {externe, interne}
- frontend/src/api/rhApi.js :: getSoldesConge -> /api/django/rh/soldes-conge  [SoldeCongeSerializer]
    champs: acquis, annee, date_creation, date_modification, disponible, employe, id, pris, report
- frontend/src/api/rhApi.js :: getTentativesQuiz -> /api/django/rh/tentatives-quiz  [TentativeQuizSerializer]
    champs: date_creation, employe, employe_nom, id, quiz, quiz_intitule, reussi, score, session
- frontend/src/api/rhApi.js :: getTypesAbsence -> /api/django/rh/types-absence  [TypeAbsenceSerializer]
    champs: actif, code, date_creation, decompte_jours_ouvres, deduit_solde, id, jours_legaux, jours_max_sans_justificatif, libelle, remunere
- frontend/src/api/rhApi.js :: getTypesLigneParcours -> /api/django/rh/types-ligne-parcours  [TypeLigneParcoursSerializer]
    champs: id, libelle, ordre
- frontend/src/api/rhApi.js :: getTypesPrime -> /api/django/rh/types-prime  [TypePrimeSerializer]
    champs: actif, code, date_creation, id, imposable, libelle, montant_defaut, nature, nature_display
    nature ∈ {indemnite, prime}
- frontend/src/api/rhApi.js :: getVisitesMedicales -> /api/django/rh/visites-medicales  [VisiteMedicaleSerializer]
    champs: a_jour, actif, aptitude, aptitude_display, date_creation, date_modification, date_visite, employe, employe_nom, id, medecin, note, organisme, prochaine_visite, restrictions
    aptitude ∈ {apte, apte_avec_restrictions, inapte}
- frontend/src/api/rhApi.js :: updateCandidature -> /api/django/rh/candidatures/<>  [CandidatureSerializer]
    champs: cv_fichier, date_candidature, date_creation, date_modification, email, emails_auto, employe_cree, employe_cree_nom, etape, etape_display, id, nom, note, ouverture, ouverture_intitule, source, tags_vivier, telephone, vivier, vivier_origine
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: updateElementIntegration -> /api/django/rh/elements-integration/<>  [ElementIntegrationSerializer]
    champs: date_creation, id, libelle, modele, ordre
- frontend/src/api/rhApi.js :: updateElementIntegrationEmploye -> /api/django/rh/elements-integration-employe/<>  [ElementIntegrationEmployeSerializer]
    champs: date, date_creation, employe, fait, fait_par, id, libelle, ordre
- frontend/src/api/rhApi.js :: updateElementSortie -> /api/django/rh/elements-sortie/<>  [ElementSortieSerializer]
    champs: date_creation, date_recuperation, employe, id, libelle, note, recupere, type_element, type_element_display
    type_element ∈ {acces_si, autre, badge, cles, epi, ordinateur, outil, telephone, vehicule}
- frontend/src/api/rhApi.js :: updateElementVariablePaie -> /api/django/rh/elements-variables-paie/<>  [ElementsVariablesPaieSerializer]
    champs: annee, commentaire, date_creation, date_export, date_modification, employe, employe_matricule, employe_nom, heures_normales, heures_supp, id, jours_absence, jours_conges, mois, primes, retenues, statut, statut_display
    statut ∈ {brouillon, exporte, valide}
- frontend/src/api/rhApi.js :: updateGabaritEmailRecrutement -> /api/django/rh/gabarits-email-recrutement/<>  [GabaritEmailRecrutementSerializer]
    champs: actif, corps, date_creation, etape, etape_display, id, objet
    etape ∈ {embauche, entretien, offre, preselection, recu, rejete}
- frontend/src/api/rhApi.js :: updateGrilleSalariale -> /api/django/rh/grilles-salariales/<>  [GrilleSalarialeSerializer]
    champs: date_creation, date_effet, echelon, id, poste, poste_intitule, salaire_max, salaire_min
- frontend/src/api/rhApi.js :: updateHoraireTravail -> /api/django/rh/horaires-travail/<>  [HoraireTravailSerializer]
    champs: actif, date_creation, date_debut, date_fin, heures_jour_defaut, heures_semaine, id, nom, type_horaire, type_horaire_display
    type_horaire ∈ {ramadan, saisonnier, standard_44h, temps_partiel}
- frontend/src/api/rhApi.js :: updateModeleEvaluation -> /api/django/rh/modeles-evaluation/<>  [ModeleEvaluationSerializer]
    champs: actif, date_creation, date_modification, departement, id, nom, poste_ref, questions
- frontend/src/api/rhApi.js :: updateModeleIntegration -> /api/django/rh/modeles-integration/<>  [ModeleIntegrationSerializer]
    champs: actif, date_creation, departement, elements, id, nom, poste_ref
- frontend/src/api/rhApi.js :: updatePrimeAttribuee -> /api/django/rh/primes-attribuees/<>  [PrimeAttribueeSerializer]
    champs: annee, date_creation, date_modification, employe, employe_nom, id, mois, montant, motif, statut, statut_display, type_prime, type_prime_libelle
    statut ∈ {payee, proposee, validee}
- frontend/src/api/rhApi.js :: updateTypePrime -> /api/django/rh/types-prime/<>  [TypePrimeSerializer]
    champs: actif, code, date_creation, id, imposable, libelle, montant_defaut, nature, nature_display
    nature ∈ {indemnite, prime}
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
- frontend/src/api/santeApi.js :: checkin -> /api/django/sante/rendezvous/<>  [RendezVousSerializer]
    champs: annule_par, annule_par_display, cree_par, date_annulation, date_heure_debut, delai_annulation_h, duree_min, id, motif_court, patient, patient_nom, praticien, praticien_nom, salle, statut, statut_display, type_acte
    annule_par ∈ {clinique, patient}
    statut ∈ {absent, annule, arrive, confirme, en_cours, planifie, termine}
- frontend/src/api/santeApi.js :: remove -> /api/django/sante/rendezvous/<>  [RendezVousSerializer]
    champs: annule_par, annule_par_display, cree_par, date_annulation, date_heure_debut, delai_annulation_h, duree_min, id, motif_court, patient, patient_nom, praticien, praticien_nom, salle, statut, statut_display, type_acte
    annule_par ∈ {clinique, patient}
    statut ∈ {absent, annule, arrive, confirme, en_cours, planifie, termine}
- frontend/src/api/savApi.js :: deleteCategorieEquipement -> /api/django/sav/categories-equipement/<>  [CategorieEquipementSerializer]
    champs: alias_email, commentaire, equipe_responsable, equipe_responsable_nom, id, nb_equipements, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: deleteCategorieTicket -> /api/django/sav/categories-ticket/<>  [CategorieTicketSerializer]
    champs: actif, id, libelle, ordre
- frontend/src/api/savApi.js :: deleteCauseDefaillance -> /api/django/sav/causes-defaillance/<>  [CauseDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: deleteCompatibilitePiece -> /api/django/sav/compatibilites-piece/<>  [CompatibilitePieceSerializer]
    champs: date_creation, id, note, piece, piece_nom, produit_equipement, produit_equipement_nom, remplace_par, remplace_par_nom
- frontend/src/api/savApi.js :: deleteContrat -> /api/django/sav/contrats-maintenance/<>  [ContratMaintenanceSerializer]
    champs: actif, client, client_nom, date_creation, date_debut, date_renouvellement, deplacements_inclus_an, derniere_facturation, derniere_visite, droits_restants, due, duree_mois, equipements, equipements_detail, facturation_active, facturation_due, id, installation, notes, periodicite, pieces_couvertes_pct, prix, prochaine_facturation, prochaine_visite, renouvellement_du, sla_resolution_days, sla_response_days, visites_incluses_an
    periodicite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/savApi.js :: deleteEquipeMaintenance -> /api/django/sav/equipes-maintenance/<>  [EquipeMaintenanceSerializer]
    champs: actif, date_creation, id, membres, membres_count, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: deleteRemedeDefaillance -> /api/django/sav/remedes-defaillance/<>  [RemedeDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: deleteReponseType -> /api/django/sav/reponses-type/<>  [ReponseTypeSerializer]
    champs: archived, corps, date_creation, id, nouveau_statut, titre
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
    champs: actif, client, client_nom, date_creation, date_debut, date_renouvellement, deplacements_inclus_an, derniere_facturation, derniere_visite, droits_restants, due, duree_mois, equipements, equipements_detail, facturation_active, facturation_due, id, installation, notes, periodicite, pieces_couvertes_pct, prix, prochaine_facturation, prochaine_visite, renouvellement_du, sla_resolution_days, sla_response_days, visites_incluses_an
    periodicite ∈ {annuel, mensuel, semestriel, trimestriel}
- frontend/src/api/savApi.js :: getEquipesMaintenance -> /api/django/sav/equipes-maintenance  [EquipeMaintenanceSerializer]
    champs: actif, date_creation, id, membres, membres_count, nom, responsable, responsable_nom
- frontend/src/api/savApi.js :: getRemedesDefaillance -> /api/django/sav/remedes-defaillance  [RemedeDefaillanceSerializer]
    champs: archived, id, nom, ordre
- frontend/src/api/savApi.js :: getReponsesType -> /api/django/sav/reponses-type  [ReponseTypeSerializer]
    champs: archived, corps, date_creation, id, nouveau_statut, titre
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
- frontend/src/api/stockApi.js :: createFicheTechnique -> /api/django/stock/fiches-techniques  [FicheTechniqueSerializer]
    champs: date_creation, date_mise_a_jour, id, imp_a, isc_a, pdf, pmax_wc, produit, produit_garantie, produit_marque, produit_nom, rendement_pct, vmp_v, voc_v
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
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: createReceptionFournisseur -> /api/django/stock/receptions-fournisseur  [ReceptionFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, controle_qhse_ouvert, created_by, created_by_username, date_creation, date_reception, fournisseur_nom, id, lignes, note, recu_par, recu_par_username, reference, statut, statut_display, total_recu
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
    champs: date_creation, date_mise_a_jour, id, imp_a, isc_a, pdf, pmax_wc, produit, produit_garantie, produit_marque, produit_nom, rendement_pct, vmp_v, voc_v
- frontend/src/api/stockApi.js :: deleteModeleBcf -> /api/django/stock/modeles-bcf/<>  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: deleteNomenclatureCodeBarres -> /api/django/stock/nomenclatures-code-barres/<>  [NomenclatureCodeBarresSerializer]
    champs: actif, date_creation, date_mise_a_jour, id, nom, regles, type_nomenclature
    type_nomenclature ∈ {default, gs1}
- frontend/src/api/stockApi.js :: deletePrixFournisseur -> /api/django/stock/prix-fournisseurs/<>  [PrixFournisseurSerializer]
    champs: date_debut, date_dernier_achat, date_fin, delai_livraison_jours, fournisseur, fournisseur_nom, id, paliers, prix_achat, produit, produit_nom, ref_produit_fournisseur
- frontend/src/api/stockApi.js :: deleteProduit -> /api/django/stock/produits/<>  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
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
    champs: date_creation, date_mise_a_jour, id, imp_a, isc_a, pdf, pmax_wc, produit, produit_garantie, produit_marque, produit_nom, rendement_pct, vmp_v, voc_v
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
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: getProduits -> /api/django/stock/produits  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: getProduitsArchived -> /api/django/stock/produits  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: getReceptionFournisseur -> /api/django/stock/receptions-fournisseur/<>  [ReceptionFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, controle_qhse_ouvert, created_by, created_by_username, date_creation, date_reception, fournisseur_nom, id, lignes, note, recu_par, recu_par_username, reference, statut, statut_display, total_recu
    statut ∈ {annule, brouillon, confirme}
- frontend/src/api/stockApi.js :: getReceptionsFournisseur -> /api/django/stock/receptions-fournisseur  [ReceptionFournisseurSerializer]
    champs: bon_commande, bon_commande_reference, controle_qhse_ouvert, created_by, created_by_username, date_creation, date_reception, fournisseur_nom, id, lignes, note, recu_par, recu_par_username, reference, statut, statut_display, total_recu
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
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
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
    champs: date_creation, date_mise_a_jour, id, imp_a, isc_a, pdf, pmax_wc, produit, produit_garantie, produit_marque, produit_nom, rendement_pct, vmp_v, voc_v
- frontend/src/api/stockApi.js :: updateModeleBcf -> /api/django/stock/modeles-bcf/<>  [ModeleBonCommandeFournisseurSerializer]
    champs: date_creation, date_mise_a_jour, fournisseur, fournisseur_nom, id, lignes, nom, note
- frontend/src/api/stockApi.js :: updateNomenclatureCodeBarres -> /api/django/stock/nomenclatures-code-barres/<>  [NomenclatureCodeBarresSerializer]
    champs: actif, date_creation, date_mise_a_jour, id, nom, regles, type_nomenclature
    type_nomenclature ∈ {default, gs1}
- frontend/src/api/stockApi.js :: updatePrixFournisseur -> /api/django/stock/prix-fournisseurs/<>  [PrixFournisseurSerializer]
    champs: date_debut, date_dernier_achat, date_fin, delai_livraison_jours, fournisseur, fournisseur_nom, id, paliers, prix_achat, produit, produit_nom, ref_produit_fournisseur
- frontend/src/api/stockApi.js :: updateProduit -> /api/django/stock/produits/<>  [ProduitSerializer]
    champs: avertissement_bloquant, avertissement_vente, bcf_sources_en_commande, categorie, categorie_id, categorie_type, categorie_type_display, code_barres, code_sh, company, courbe_pompe, custom_data, date_creation, date_mise_a_jour, debit_m3j, derniere_date_mouvement, description, description_localise, entite, fournisseur, fournisseur_id, garantie, garantie_mois, garantie_production_mois, hmt_m, id, image_url, is_archived, is_low_stock, is_low_stock_disponible, marge_pct, marque, nb_mouvements, nom, nom_localise, pays_origine, politique_facturation_achat, pompe_cv, pompe_kw, premiere_date_mouvement, prix_achat, prix_vente, quantite_disponible, quantite_en_commande, quantite_reservee, quantite_stock, seuil_alerte, sku, stock_par_emplacement, suivi_serie, tension_v, tva, unite, unite_stock, unite_stock_display
    politique_facturation_achat ∈ {sur_commande, sur_reception}
- frontend/src/api/stockApi.js :: updateRegleCodeBarres -> /api/django/stock/regles-code-barres/<>  [RegleCodeBarresSerializer]
    champs: encode, est_regex, id, motif, nomenclature, priorite
    encode ∈ {emplacement, lot, produit, quantite, serie}
- frontend/src/api/uxviewsApi.js :: createSavedView -> /api/django/uxviews/saved-views  [SavedViewSerializer]
    champs: configuration, created_at, ecran, est_defaut_role, id, nom, owner, owner_nom, role, role_nom, updated_at, visibilite
    visibilite ∈ {EQUIPE, PERSONNELLE}
- frontend/src/api/uxviewsApi.js :: deleteSavedView -> /api/django/uxviews/saved-views/<>  [SavedViewSerializer]
    champs: configuration, created_at, ecran, est_defaut_role, id, nom, owner, owner_nom, role, role_nom, updated_at, visibilite
    visibilite ∈ {EQUIPE, PERSONNELLE}
- frontend/src/api/uxviewsApi.js :: listSavedViews -> /api/django/uxviews/saved-views  [SavedViewSerializer]
    champs: configuration, created_at, ecran, est_defaut_role, id, nom, owner, owner_nom, role, role_nom, updated_at, visibilite
    visibilite ∈ {EQUIPE, PERSONNELLE}
- frontend/src/api/uxviewsApi.js :: updateSavedView -> /api/django/uxviews/saved-views/<>  [SavedViewSerializer]
    champs: configuration, created_at, ecran, est_defaut_role, id, nom, owner, owner_nom, role, role_nom, updated_at, visibilite
    visibilite ∈ {EQUIPE, PERSONNELLE}
- frontend/src/api/ventesApi.js :: createListePrix -> /api/django/ventes/listes-prix  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: deleteListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: deleteNiveauRelance -> /api/django/ventes/niveaux-relance/<>  [FollowupLevelSerializer]
    champs: canal, delai_jours, frais_fixes, id, message, nom, ordre, taux_interet_annuel
    canal ∈ {appel, courrier, email, whatsapp}
- frontend/src/api/ventesApi.js :: getListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: getListesPrix -> /api/django/ventes/listes-prix  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: getNiveauxRelance -> /api/django/ventes/niveaux-relance  [FollowupLevelSerializer]
    champs: canal, delai_jours, frais_fixes, id, message, nom, ordre, taux_interet_annuel
    canal ∈ {appel, courrier, email, whatsapp}
- frontend/src/api/ventesApi.js :: patchListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/ventesApi.js :: updateListePrix -> /api/django/ventes/listes-prix/<>  [ListePrixSerializer]
    champs: archived, company, created_at, date_debut, date_fin, devise, est_active, id, lignes, nom, regles
- frontend/src/api/voipApi.js :: getAppels -> /api/django/voip/appels  [AppelSerializer]
    champs: cible, direction, duree_secondes, ended_at, external_call_id, fournisseur, id, issue, numero, numero_normalise, started_at, statut, utilisateur
    direction ∈ {entrant, sortant}
    statut ∈ {en_cours, initie, manque, sonnant, termine}
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
- frontend/src/features/assurances/assurancesApi.js :: createActifCouvert -> /api/django/assurances/actifs-couverts  [ActifCouvertSerializer]
    champs: actif_libelle, actif_ref, company, date_ajout, id, police, type_actif
    type_actif ∈ {autre, equipement, site, vehicule}
- frontend/src/features/assurances/assurancesApi.js :: createAssureur -> /api/django/assurances/assureurs  [AssureurSerializer]
    champs: actif, adresse, company, email, ice, id, raison_sociale, telephone
- frontend/src/features/assurances/assurancesApi.js :: createAttestation -> /api/django/assurances/attestations  [AttestationAssuranceSerializer]
    champs: company, created_at, date_emission, date_validite, emise_pour, id, police, statut
    statut ∈ {expiree, valide}
- frontend/src/features/assurances/assurancesApi.js :: createCourtier -> /api/django/assurances/courtiers  [CourtierSerializer]
    champs: actif, company, email, id, numero_agrement, raison_sociale, telephone
- frontend/src/features/assurances/assurancesApi.js :: createExigenceMarche -> /api/django/assurances/exigences-assurance-marche  [ExigenceAssuranceMarcheSerializer]
    champs: company, created_at, id, marche_ref, montant_couverture_minimum, statut_verification, type_police_requis, type_police_requis_display
    statut_verification ∈ {a_verifier, conforme, non_conforme}
    type_police_requis ∈ {autre, bris_machine, cyber, decennale, homme_cle, multirisque, perte_exploitation, rc_pro, transport_marchandises}
- frontend/src/features/assurances/assurancesApi.js :: createGarantie -> /api/django/assurances/garanties-police  [GarantiePoliceSerializer]
    champs: company, franchise_montant, franchise_pourcentage, id, libelle_garantie, notes, plafond_indemnisation, police
- frontend/src/features/assurances/assurancesApi.js :: createSinistre -> /api/django/assurances/declarations-sinistre  [DeclarationSinistreSerializer]
    champs: company, conteste, created_at, date_declaration, date_survenance, description, dossier_contentieux_ref, flotte_sinistre_id, id, montant_estime_degats, nature_sinistre, numero_dossier, police, risque_libelle, risque_ref, statut, type_sinistre, type_sinistre_display
    statut ∈ {clos, declare, en_expertise, indemnise, refuse}
    type_sinistre ∈ {autre, cyber, decennale, dommage_materiel, incendie, responsabilite_civile, vol}
- frontend/src/features/assurances/assurancesApi.js :: deleteExigenceMarche -> /api/django/assurances/exigences-assurance-marche/<>  [ExigenceAssuranceMarcheSerializer]
    champs: company, created_at, id, marche_ref, montant_couverture_minimum, statut_verification, type_police_requis, type_police_requis_display
    statut_verification ∈ {a_verifier, conforme, non_conforme}
    type_police_requis ∈ {autre, bris_machine, cyber, decennale, homme_cle, multirisque, perte_exploitation, rc_pro, transport_marchandises}
- frontend/src/features/assurances/assurancesApi.js :: getActifsCouverts -> /api/django/assurances/actifs-couverts  [ActifCouvertSerializer]
    champs: actif_libelle, actif_ref, company, date_ajout, id, police, type_actif
    type_actif ∈ {autre, equipement, site, vehicule}
- frontend/src/features/assurances/assurancesApi.js :: getAssureurs -> /api/django/assurances/assureurs  [AssureurSerializer]
    champs: actif, adresse, company, email, ice, id, raison_sociale, telephone
- frontend/src/features/assurances/assurancesApi.js :: getAttestations -> /api/django/assurances/attestations  [AttestationAssuranceSerializer]
    champs: company, created_at, date_emission, date_validite, emise_pour, id, police, statut
    statut ∈ {expiree, valide}
- frontend/src/features/assurances/assurancesApi.js :: getCourtiers -> /api/django/assurances/courtiers  [CourtierSerializer]
    champs: actif, company, email, id, numero_agrement, raison_sociale, telephone
- frontend/src/features/assurances/assurancesApi.js :: getEcheancesPrime -> /api/django/assurances/echeances-prime  [EcheancePrimeSerializer]
    champs: company, date_echeance_paiement, ecriture_ref, id, montant, periodicite, police, statut
    periodicite ∈ {annuelle, mensuelle, semestrielle, trimestrielle}
    statut ∈ {a_payer, en_retard, payee, proposee_compta}
- frontend/src/features/assurances/assurancesApi.js :: getExigencesMarche -> /api/django/assurances/exigences-assurance-marche  [ExigenceAssuranceMarcheSerializer]
    champs: company, created_at, id, marche_ref, montant_couverture_minimum, statut_verification, type_police_requis, type_police_requis_display
    statut_verification ∈ {a_verifier, conforme, non_conforme}
    type_police_requis ∈ {autre, bris_machine, cyber, decennale, homme_cle, multirisque, perte_exploitation, rc_pro, transport_marchandises}
- frontend/src/features/assurances/assurancesApi.js :: getGaranties -> /api/django/assurances/garanties-police  [GarantiePoliceSerializer]
    champs: company, franchise_montant, franchise_pourcentage, id, libelle_garantie, notes, plafond_indemnisation, police
- frontend/src/features/assurances/assurancesApi.js :: getSinistre -> /api/django/assurances/declarations-sinistre/<>  [DeclarationSinistreSerializer]
    champs: company, conteste, created_at, date_declaration, date_survenance, description, dossier_contentieux_ref, flotte_sinistre_id, id, montant_estime_degats, nature_sinistre, numero_dossier, police, risque_libelle, risque_ref, statut, type_sinistre, type_sinistre_display
    statut ∈ {clos, declare, en_expertise, indemnise, refuse}
    type_sinistre ∈ {autre, cyber, decennale, dommage_materiel, incendie, responsabilite_civile, vol}
- frontend/src/features/assurances/assurancesApi.js :: getSinistres -> /api/django/assurances/declarations-sinistre  [DeclarationSinistreSerializer]
    champs: company, conteste, created_at, date_declaration, date_survenance, description, dossier_contentieux_ref, flotte_sinistre_id, id, montant_estime_degats, nature_sinistre, numero_dossier, police, risque_libelle, risque_ref, statut, type_sinistre, type_sinistre_display
    statut ∈ {clos, declare, en_expertise, indemnise, refuse}
    type_sinistre ∈ {autre, cyber, decennale, dommage_materiel, incendie, responsabilite_civile, vol}
- frontend/src/features/assurances/assurancesApi.js :: updateSinistre -> /api/django/assurances/declarations-sinistre/<>  [DeclarationSinistreSerializer]
    champs: company, conteste, created_at, date_declaration, date_survenance, description, dossier_contentieux_ref, flotte_sinistre_id, id, montant_estime_degats, nature_sinistre, numero_dossier, police, risque_libelle, risque_ref, statut, type_sinistre, type_sinistre_display
    statut ∈ {clos, declare, en_expertise, indemnise, refuse}
    type_sinistre ∈ {autre, cyber, decennale, dommage_materiel, incendie, responsabilite_civile, vol}
