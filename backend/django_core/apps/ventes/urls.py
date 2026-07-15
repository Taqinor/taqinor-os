from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DevisViewSet,
    LigneDevisViewSet,
    BonCommandeViewSet,
    FactureViewSet,
    LigneFactureViewSet,
    PaiementViewSet,
    AvoirViewSet,
    NoteDebitViewSet,  # ZFAC4
    email_config,
    client_credit_warning,
    releve_dry_run,
    releve_commit,
    roof_config,
    RoofLayoutViewSet,  # FG245
    FicheTechniqueViewSet,  # FG254
    DevisPresetViewSet,  # QJ16-wiring
    RegulatoryDossierViewSet,  # FG268
    DossierChecklistItemViewSet,  # FG268
    DossierExchangeViewSet,  # FG269
    SubventionDossierViewSet,  # FG270
    Regularisation8221ViewSet,  # FG271
    CommissioningTestViewSet,  # FG274
    IVCurveCaptureViewSet,  # FG275
    AsBuiltPackViewSet,  # FG276
    AttestationConformiteViewSet,  # FG277
    TestPerformanceReceptionViewSet,  # FG278
    AttestationREViewSet,  # FG287
    RemiseEncaissementViewSet,  # XFSM19
    MandatPaiementViewSet,  # XCTR22
    ListePrixViewSet,  # XSAL1-2
    prix_applicable_view,  # XSAL3
)
from .recouvrement import (
    FollowupLevelViewSet,
    ParametrageRelanceClientViewSet,  # ZFAC8
    PromessePaiementViewSet,
    relances_list,
    balance_agee,
    client_releve,
    client_releve_pdf,
    lettre_relance_pdf,
    client_score_comportement,  # XFAC15
    dossier_contentieux,  # XFAC21
)
from .public_views import (
    proposal_data, proposal_accept, proposal_pdf,
    # QW5 — mêmes vues QJ27, aliasées ici sous le mount `ventes/` (le site
    # les appelle ici, pas sous `public/` — jamais de logique dupliquée).
    proposal_contact_request, proposal_request_otp,
    proposal_engagement,  # XSAL16
    proposal_virement_declare,  # QX33be
    proposal_activate_option,  # XSAL5
    suivi_public,  # QX34
)
from .dashboard_view import dashboard_quote_to_cash
from .insights_view import cash_flow_forecast, analyse_facturation_view  # ZFAC10
from .journal_view import journal_ventes, export_comptable, export_status
from .numbering_view import numerotation_audit, numerotation_preview
from .extra_docs_views import lettre_relance_premium, fiche_remise_premium
from .diagram_views import schema_unifilaire, schema_unifilaire_devis  # FG252
from .roof_load_view import roof_load_check  # FG253
from .connection_declaration_view import declaration_raccordement  # FG272
from .calendrier_view import calendrier_reglementaire  # FG273

router = DefaultRouter()
router.register(r'devis', DevisViewSet)
router.register(r'devis-lignes', LigneDevisViewSet)
router.register(r'bons-commande', BonCommandeViewSet)
router.register(r'factures', FactureViewSet)
router.register(r'factures-lignes', LigneFactureViewSet)
router.register(r'paiements', PaiementViewSet)
router.register(r'avoirs', AvoirViewSet)
router.register(r'notes-debit', NoteDebitViewSet, basename='note-debit')
# FG245 — calepinage toiture (placement panneaux), compte calculé serveur.
router.register(r'calepinages', RoofLayoutViewSet, basename='calepinage')
# FG254 / DC35 — bibliothèque de fiches techniques normalisées (datasheets).
router.register(r'fiches-techniques', FicheTechniqueViewSet,
                basename='fiche-technique')
router.register(r'niveaux-relance', FollowupLevelViewSet,
                basename='niveau-relance')
# ZFAC8 — réglage responsable/mode de relance par client.
router.register(r'parametrages-relance-client', ParametrageRelanceClientViewSet,
                basename='parametrage-relance-client')
# XFAC5 — promesses de paiement (suspendent la relance auto jusqu'à échéance).
router.register(r'promesses-paiement', PromessePaiementViewSet,
                basename='promesse-paiement')
# QJ16-wiring — presets de devis (list + destroy uniquement).
# La création passe par POST /devis/{id}/save-preset/ sur le DevisViewSet.
router.register(r'presets', DevisPresetViewSet, basename='devis-preset')
# FG268 — dossiers réglementaires de raccordement + checklist par étape.
router.register(r'dossiers-reglementaires', RegulatoryDossierViewSet,
                basename='dossier-reglementaire')
router.register(r'dossiers-checklist', DossierChecklistItemViewSet,
                basename='dossier-checklist')
# FG269 — journal de la navette opérateur (échanges ONEE/distributeur).
router.register(r'dossiers-echanges', DossierExchangeViewSet,
                basename='dossier-echange')
# FG270 — éligibilité & suivi des subventions/incitations.
router.register(r'subventions', SubventionDossierViewSet,
                basename='subvention')
# FG271 — workflow de régularisation Article 33 / déclarations 82-21.
router.register(r'regularisations-8221', Regularisation8221ViewSet,
                basename='regularisation-8221')
# FG274 — fiches de recette IEC 62446 (mise en service).
router.register(r'recettes-mes', CommissioningTestViewSet,
                basename='recette-mes')
# FG275 — captures de courbe I-V par string.
router.register(r'courbes-iv', IVCurveCaptureViewSet,
                basename='courbe-iv')
# FG276 — packs documentaires as-built.
router.register(r'packs-asbuilt', AsBuiltPackViewSet,
                basename='pack-asbuilt')
# FG277 — attestations de conformité électrique.
router.register(r'attestations-conformite', AttestationConformiteViewSet,
                basename='attestation-conformite')
# FG278 — tests de performance de réception (PR initial).
router.register(r'tests-pr-reception', TestPerformanceReceptionViewSet,
                basename='test-pr-reception')
# FG287 — attestations d'énergie renouvelable.
router.register(r'attestations-re', AttestationREViewSet,
                basename='attestation-re')
# XFSM19 — rapprochement des encaissements terrain par technicien.
router.register(r'remises-encaissement', RemiseEncaissementViewSet,
                basename='remise-encaissement')
# XCTR22 — mandats de paiement récurrent (tokenisation carte).
router.register(r'listes-prix', ListePrixViewSet, basename='liste-prix')  # XSAL1-2
router.register(r'mandats-paiement', MandatPaiementViewSet,
                basename='mandat-paiement')

urlpatterns = [
    # Q6/Q7 — Proposition web tokenisée (données JSON + e-signature). Jeton
    # ShareLink (long, imprévisible, expirant) ; pas de login. Placé AVANT le
    # routeur pour ne pas être avalé par la route /devis/.
    path('proposal/<str:token>/', proposal_data, name='proposal-data'),
    path('proposal/<str:token>/accept/', proposal_accept,
         name='proposal-accept'),
    # Flux PDF CLIENT du devis derrière le même jeton de proposition (W116) —
    # affichage inline. Placé AVANT le routeur (comme les autres routes
    # proposal/) pour ne pas être avalé par la route /devis/.
    path('proposal/<str:token>/pdf/', proposal_pdf, name='proposal-pdf'),
    # QW5 — le site poste sur CE mount (ventes/), pas sur public/ où ces vues
    # QJ27 vivent déjà (apps/ventes/public_urls.py) — sans cet alias, 404.
    # Même vue, jamais de logique dupliquée.
    path('proposal/<str:token>/contact/', proposal_contact_request,
         name='proposal-contact-ventes'),
    path('proposal/<str:token>/otp/', proposal_request_otp,
         name='proposal-otp-ventes'),
    # XSAL16 — beacon d'engagement par section (backend only ; l'émission
    # côté page proposition part dans docs/WEB_PLAN.md).
    path('proposal/<str:token>/engagement/', proposal_engagement,
         name='proposal-engagement'),
    # QX33be — déclaration de virement d'acompte (client).
    path('proposal/<str:token>/virement/', proposal_virement_declare,
         name='proposal-virement-ventes'),
    # XSAL5 — activation self-service d'une ligne optionnelle (avant signature).
    path('proposal/<str:token>/activer-option/', proposal_activate_option,
         name='proposal-activate-option-ventes'),
    # QX34 — suivi post-signature public en lecture seule (timeline jalons).
    path('suivi/<str:token>/', suivi_public, name='suivi-public'),
    # Export comptable : journal des ventes + résumé TVA (.xlsx).
    path('journal-ventes/', journal_ventes, name='journal-ventes'),
    # Export comptable DGI (groundwork) : factures validées d'une plage,
    # ventilation TVA par ligne + ICE + totaux, en .xlsx OU .csv. FG49 :
    # ?layout=grand-livre → grand-livre codé par compte CGNC (fiduciaire).
    path('export-comptable/', export_comptable, name='export-comptable'),
    # SCA41 — statut + téléchargement pré-signé d'un export xlsx asynchrone
    # (voie déclenchée au-delà du seuil de lignes), borné société.
    path('export/status/<str:token>/', export_status, name='export-status'),
    # Audit de la numérotation séquentielle (trous/doublons) — admin.
    path('numerotation-audit/', numerotation_audit, name='numerotation-audit'),
    # Aperçu du prochain numéro RÉEL par type de pièce (L770/L786).
    path('numerotation-preview/', numerotation_preview,
         name='numerotation-preview'),
    # Recouvrement (vue/consigne/impression — jamais d'envoi).
    path('relances/', relances_list, name='relances-list'),
    path('balance-agee/', balance_agee, name='balance-agee'),
    path('clients/<int:client_id>/releve/', client_releve, name='client-releve'),
    path('clients/<int:client_id>/releve-pdf/', client_releve_pdf,
         name='client-releve-pdf'),
    # XFAC15 — badge de comportement de paiement (fiche client).
    path('clients/<int:client_id>/score-comportement/',
         client_score_comportement, name='client-score-comportement'),
    # XFAC21 — dossier contentieux / passage en recouvrement externe.
    path('clients/<int:client_id>/dossier-contentieux/',
         dossier_contentieux, name='client-dossier-contentieux'),
    path('factures/<int:facture_id>/lettre-relance-pdf/', lettre_relance_pdf,
         name='lettre-relance-pdf'),
    # Documents premium ADDITIFS (langage visuel du devis) — rendus à la volée.
    # Lettre de relance premium niveau 1/2/3 (?niveau=) et fiche de remise.
    path('factures/<int:facture_id>/lettre-relance-premium/',
         lettre_relance_premium, name='lettre-relance-premium'),
    path('chantiers/<int:chantier_id>/fiche-remise-premium/',
         fiche_remise_premium, name='fiche-remise-premium'),
    # FG252 — brouillon de schéma unifilaire (SVG), dossier technique.
    # Placé AVANT le routeur pour ne pas être avalé par la route /devis/.
    path('devis/<int:pk>/schema-unifilaire/', schema_unifilaire_devis,
         name='devis-schema-unifilaire'),
    path('schema-unifilaire/', schema_unifilaire, name='schema-unifilaire'),
    # FG272 — déclaration de raccordement BT/MT pré-remplie (JSON ou PDF).
    # Placée AVANT le routeur pour ne pas être avalée par la route /devis/.
    path('devis/<int:pk>/declaration-raccordement/',
         declaration_raccordement, name='devis-declaration-raccordement'),
    # FG253 — aide au calcul de charge structure toiture (alerte dépassement).
    path('toiture/charge/', roof_load_check, name='toiture-charge'),
    # N87 — état du compte d'envoi email (informatif, lecture seule).
    path('email-config/', email_config, name='email-config'),
    # Config carte pour l'outil de conception 3D de toiture (ERP même origine) :
    # clé MapTiler / token Mapbox d'environnement, lus par la page ToitureDesign.
    path('roof-config/', roof_config, name='roof-config'),
    # FG41 — avertissement plafond de crédit client (soft warning, jamais blocage).
    path('clients/<int:client_id>/credit-warning/', client_credit_warning,
         name='client-credit-warning'),
    # FG42 — import relevé bancaire (dry-run + commit).
    path('paiements/import-releve/dry-run/', releve_dry_run,
         name='paiements-import-releve-dry-run'),
    path('paiements/import-releve/commit/', releve_commit,
         name='paiements-import-releve-commit'),
    # FG45 — tableau de bord Quote-to-Cash (agrégation lecture seule).
    path('dashboard/', dashboard_quote_to_cash, name='ventes-dashboard'),
    # FG47 — prévision cash-flow / encaissements à venir (lecture seule).
    path('insights/cash-flow/', cash_flow_forecast, name='ventes-cash-flow'),
    path('etats/analyse-facturation/', analyse_facturation_view,
         name='ventes-analyse-facturation'),
    # FG273 — calendrier réglementaire & alertes d'expiration (lecture seule).
    path('calendrier-reglementaire/', calendrier_reglementaire,
         name='calendrier-reglementaire'),
    # XSAL3 — résolution de prix (liste client + règles/paliers XSAL1-2).
    path('prix-applicable/', prix_applicable_view, name='prix-applicable'),
    path('', include(router.urls)),
]
