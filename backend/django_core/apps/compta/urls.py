from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    desinscription_publique, double_optin_confirmer,
    redirection_lien_tracke,
    enquete_publique, enquete_soumettre, enquete_certificat_pdf, EnqueteViewSet,
    evenement_inscription_publique, EvenementMarketingViewSet,
    InscriptionEvenementViewSet,
    SupportOfflineViewSet,
    DomaineEnvoiViewSet,
    TypeEvenementViewSet,
    BilletEvenementViewSet,
    QuestionEvenementViewSet,
    CommunicationEvenementViewSet,
    PostSocialViewSet,
    CalendrierMarketingView, CalendrierMarketingRescheduleView,
    webhook_brevo_campagne, webhook_sms_stop,
    portail_mon_releve, portail_mon_releve_pdf, portail_contester_facture,
    AppelTelephoniqueViewSet,
    BaremeIndemniteViewSet, BordereauRemiseViewSet, BudgetViewSet,
    CaisseViewSet, CampagneViewSet, CautionBancaireViewSet, CentreCoutViewSet,
    EnvoiCampagneViewSet, ListeDiffusionViewSet, AbonnementListeViewSet,
    ApprobationEnvoiCampagneViewSet,
    SegmentMarketingViewSet,
    CessionImmobilisationViewSet, CodePromotionViewSet,
    CommissionPayoutRunViewSet, ComparateurDevisViewSet,
    CompteComptableViewSet, CompteTresorerieViewSet, ContratAvancementViewSet,
    DeclarationTVAViewSet, DemandeApprobationConfigViewSet,
    DotationAmortissementViewSet, ECatalogueViewSet,
    EcritureComptableViewSet, EffetViewSet, EntiteConsolidationViewSet,
    EtapeSequenceViewSet, InscriptionSequenceViewSet,
    EtatsComptablesViewSet, ExerciceComptableViewSet, FormulaireIntakeViewSet,
    ImmobilisationViewSet,
    IndemniteChantierViewSet, JournalViewSet,
    LignePrevisionnelTresorerieViewSet, MessageWhatsAppEntrantViewSet,
    ModeleDevisViewSet, NoteFraisViewSet, OuverturePartageViewSet,
    ParametresTresorerieView, PaymentRunViewSet, PouvoirBancaireViewSet,
    PlanRelanceTresorerieViewSet,
    PeriodeComptableViewSet, PilotageViewSet, PlafondNoteFraisViewSet,
    PlanComptableViewSet,
    ProvisionCreanceViewSet, ProvisionViewSet,
    RapportNoteFraisViewSet,
    RapprochementBancaireViewSet, RapprochementViewSet,
    RelanceDevisAbandonneViewSet,
    RetenueGarantieViewSet, RetenueSourceViewSet, SequenceRelanceViewSet,
    SessionGuidedSellingViewSet, TimbreFiscalViewSet,
    TravauxEnCoursViewSet, VirementInterneViewSet,
    DocumentPropositionViewSet, SimulationPubliqueViewSet,
    SimulationFinancementViewSet, OffreFinancementViewSet,
    LigneIncitationViewSet, EcheancierPaiementViewSet, TranchePaiementViewSet,
    ComparateurCashFinancementViewSet, AppelOffreViewSet, BordereauPrixViewSet,
    LigneBordereauViewSet, CautionSoumissionViewSet, DossierSoumissionViewSet,
    PieceSoumissionViewSet, EcheanceAOViewSet, ResultatAOViewSet,
    ComptePortailClientViewSet, AcceptationDevisPortailViewSet,
    PaiementFacturePortailViewSet, DocumentClientPortailViewSet,
    JalonChantierPortailViewSet, DemandeTicketPortailViewSet,
    PartenaireViewSet, SoumissionLeadPartenaireViewSet,
    CommissionPartenaireViewSet, TerritoireCommercialViewSet,
    EnqueteNPSViewSet, AvisClientViewSet,
    CompteFideliteViewSet, MouvementFideliteViewSet,
    RegleUpsellViewSet, AbonnementMonitoringViewSet,
    MappingCompteViewSet, CompteAuxiliaireViewSet,
    PieceJustificativeViewSet,
    PisteAuditComptableViewSet,
    BalanceOuvertureViewSet,
    ModeleRapprochementViewSet,
    ProvisionsPeriodeViewSet,
    ObligationFiscaleViewSet,
    FamilleTvaNonDeductibleViewSet,
    LettrageViewSet,
    CompensationViewSet,
    CycleConsolidationViewSet, LiasseRemonteeViewSet,
    MappingConsolidationViewSet, OperationIntercoViewSet,
    MargeInterneStockViewSet, EliminationTitresViewSet,
    ReferentielComptableViewSet, AjustementGaapViewSet,
    AxeAnalytiqueViewSet, ImputationAxeViewSet,
)

router = DefaultRouter()
router.register(r'plans', PlanComptableViewSet)
router.register(r'comptes', CompteComptableViewSet)
router.register(r'journaux', JournalViewSet)
router.register(r'ecritures', EcritureComptableViewSet)
router.register(r'tresorerie', CompteTresorerieViewSet)
router.register(r'periodes', PeriodeComptableViewSet)
router.register(r'exercices', ExerciceComptableViewSet)
router.register(r'immobilisations', ImmobilisationViewSet)
router.register(r'dotations', DotationAmortissementViewSet)
router.register(r'cessions', CessionImmobilisationViewSet)
router.register(r'rapprochements', RapprochementBancaireViewSet)
router.register(r'modeles-rapprochement', ModeleRapprochementViewSet)
router.register(r'rapprochements-3voies', RapprochementViewSet,
                basename='rapprochement-3voies')
router.register(r'caisses', CaisseViewSet)
router.register(r'virements', VirementInterneViewSet)
router.register(r'previsionnel', LignePrevisionnelTresorerieViewSet)
router.register(r'effets', EffetViewSet)
router.register(r'bordereaux', BordereauRemiseViewSet)
router.register(r'payment-runs', PaymentRunViewSet)
router.register(r'pouvoirs-bancaires', PouvoirBancaireViewSet)
router.register(r'plans-relance-tresorerie', PlanRelanceTresorerieViewSet)
router.register(r'notes-frais', NoteFraisViewSet)
router.register(r'rapports-notes-frais', RapportNoteFraisViewSet)
router.register(r'plafonds-notes-frais', PlafondNoteFraisViewSet)
router.register(r'baremes-indemnite', BaremeIndemniteViewSet)
router.register(r'indemnites-chantier', IndemniteChantierViewSet)
router.register(r'declarations-tva', DeclarationTVAViewSet)
router.register(r'retenues-source', RetenueSourceViewSet)
router.register(r'timbres-fiscaux', TimbreFiscalViewSet)
router.register(r'retenues-garantie', RetenueGarantieViewSet)
router.register(r'cautions-bancaires', CautionBancaireViewSet)
router.register(r'contrats-avancement', ContratAvancementViewSet)
router.register(r'travaux-en-cours', TravauxEnCoursViewSet)
router.register(r'commission-payout-runs', CommissionPayoutRunViewSet)
router.register(r'budgets', BudgetViewSet)
router.register(r'centres-cout', CentreCoutViewSet)
router.register(r'provisions-creances', ProvisionCreanceViewSet)
router.register(r'provisions', ProvisionViewSet)
router.register(r'entites-consolidation', EntiteConsolidationViewSet)
router.register(r'pilotage', PilotageViewSet, basename='pilotage')
router.register(r'etats', EtatsComptablesViewSet, basename='etats')
router.register(r'lettrage', LettrageViewSet, basename='lettrage')
router.register(r'balance-ouverture', BalanceOuvertureViewSet,
                basename='balance-ouverture')
router.register(r'provisions-periode', ProvisionsPeriodeViewSet,
                basename='provisions-periode')
router.register(r'obligations-fiscales', ObligationFiscaleViewSet)
router.register(r'familles-tva-non-deductibles', FamilleTvaNonDeductibleViewSet)
# ── Croissance commerciale / marketing / CPQ (FG201–FG214) ──────────────────
router.register(r'campagnes', CampagneViewSet)
# XMKT35 — posts réseaux sociaux (calendrier de contenu, publication gated).
router.register(r'posts-sociaux', PostSocialViewSet)
router.register(r'envois-campagne', EnvoiCampagneViewSet)
router.register(r'approbations-envoi-campagne', ApprobationEnvoiCampagneViewSet)
router.register(r'listes-diffusion', ListeDiffusionViewSet)
router.register(r'abonnements-liste', AbonnementListeViewSet)
router.register(r'segments-marketing', SegmentMarketingViewSet)
router.register(r'sequences-relance', SequenceRelanceViewSet)
router.register(r'etapes-sequence', EtapeSequenceViewSet)
router.register(r'inscriptions-sequence', InscriptionSequenceViewSet)
router.register(r'relances-devis-abandonnes', RelanceDevisAbandonneViewSet)
router.register(r'ouvertures-partage', OuverturePartageViewSet)
router.register(r'formulaires-intake', FormulaireIntakeViewSet)
router.register(r'messages-whatsapp', MessageWhatsAppEntrantViewSet,
                basename='message-whatsapp')
router.register(r'appels', AppelTelephoniqueViewSet)
router.register(r'codes-promotion', CodePromotionViewSet)
router.register(r'modeles-devis', ModeleDevisViewSet)
router.register(r'guided-selling', SessionGuidedSellingViewSet)
router.register(r'comparateur-devis', ComparateurDevisViewSet,
                basename='comparateur-devis')
router.register(r'approbations-config', DemandeApprobationConfigViewSet)
router.register(r'ecatalogues', ECatalogueViewSet)
# ── Financement, appels d'offres & portail (FG215–FG228) ────────────────────
router.register(r'documents-proposition', DocumentPropositionViewSet)
router.register(r'simulations-publiques', SimulationPubliqueViewSet)
router.register(r'simulations-financement', SimulationFinancementViewSet)
router.register(r'offres-financement', OffreFinancementViewSet)
router.register(r'lignes-incitation', LigneIncitationViewSet)
router.register(r'echeanciers-paiement', EcheancierPaiementViewSet)
router.register(r'tranches-paiement', TranchePaiementViewSet)
router.register(r'comparateur-financement', ComparateurCashFinancementViewSet,
                basename='comparateur-financement')
router.register(r'appels-offres', AppelOffreViewSet)
router.register(r'bordereaux-prix', BordereauPrixViewSet)
router.register(r'lignes-bordereau', LigneBordereauViewSet)
router.register(r'cautions-soumission', CautionSoumissionViewSet)
router.register(r'dossiers-soumission', DossierSoumissionViewSet)
router.register(r'pieces-soumission', PieceSoumissionViewSet)
router.register(r'echeances-ao', EcheanceAOViewSet)
router.register(r'resultats-ao', ResultatAOViewSet)
router.register(r'comptes-portail', ComptePortailClientViewSet)
# ── Portail client, partenaires & fidélité (FG229–FG244) ────────────────────
router.register(r'acceptations-devis-portail', AcceptationDevisPortailViewSet)
router.register(r'paiements-facture-portail', PaiementFacturePortailViewSet)
router.register(r'documents-client-portail', DocumentClientPortailViewSet)
router.register(r'jalons-chantier-portail', JalonChantierPortailViewSet)
router.register(r'demandes-ticket-portail', DemandeTicketPortailViewSet)
router.register(r'partenaires', PartenaireViewSet)
router.register(r'soumissions-lead-partenaire', SoumissionLeadPartenaireViewSet)
router.register(r'commissions-partenaire', CommissionPartenaireViewSet)
router.register(r'territoires-commerciaux', TerritoireCommercialViewSet)
router.register(r'enquetes-nps', EnqueteNPSViewSet)
router.register(r'avis-clients', AvisClientViewSet)
router.register(r'comptes-fidelite', CompteFideliteViewSet)
router.register(r'mouvements-fidelite', MouvementFideliteViewSet)
router.register(r'regles-upsell', RegleUpsellViewSet)
router.register(r'abonnements-monitoring', AbonnementMonitoringViewSet)
# ── Comptabilité générale — mappings, auxiliaires & pièces (COMPTA2/3/10) ────
router.register(r'mappings-compte', MappingCompteViewSet)
router.register(r'comptes-auxiliaires', CompteAuxiliaireViewSet)
router.register(r'pieces-justificatives', PieceJustificativeViewSet)
router.register(r'pistes-audit', PisteAuditComptableViewSet,
                basename='pisteaudit')
# ── XFAC14 — Compensation AR/AP (netting) ───────────────────────────────────
router.register(r'compensations', CompensationViewSet)
# ── XMKT27 — Constructeur d'enquêtes ────────────────────────────────────────
router.register(r'enquetes', EnqueteViewSet)
# ── XMKT28 — Événements marketing légers ────────────────────────────────────
router.register(r'evenements-marketing', EvenementMarketingViewSet)
router.register(r'inscriptions-evenement', InscriptionEvenementViewSet)
router.register(r'types-evenement', TypeEvenementViewSet)
router.register(r'billets-evenement', BilletEvenementViewSet)
router.register(r'questions-evenement', QuestionEvenementViewSet)
router.register(r'communications-evenement', CommunicationEvenementViewSet)
# ── XMKT29 — Ponts QR pour supports offline ─────────────────────────────────
router.register(r'supports-offline', SupportOfflineViewSet)
# ── XMKT33 — Assistant d'authentification du domaine d'envoi ───────────────
router.register(r'domaines-envoi', DomaineEnvoiViewSet)
# ── NTFIN — Consolidation multi-sociétés (grand groupe) ────────────────────
router.register(r'cycles-consolidation', CycleConsolidationViewSet,
                basename='cycle-consolidation')
router.register(r'liasses-remontee', LiasseRemonteeViewSet)
router.register(r'mappings-consolidation', MappingConsolidationViewSet)
router.register(r'operations-interco', OperationIntercoViewSet)
router.register(r'marges-internes-stock', MargeInterneStockViewSet)
router.register(r'eliminations-titres', EliminationTitresViewSet)
# ── NTFIN — Multi-référentiel & analytique multi-axes ──────────────────────
router.register(r'referentiels-comptables', ReferentielComptableViewSet)
router.register(r'ajustements-gaap', AjustementGaapViewSet)
router.register(r'axes-analytiques', AxeAnalytiqueViewSet)
router.register(r'imputations-axes', ImputationAxeViewSet)

urlpatterns = [
    # XMKT30 (partiel) — calendrier marketing agrégé (campagnes + posts
    # sociaux XMKT35 aujourd'hui ; autres sources à brancher, même contrat).
    path('calendrier-marketing/', CalendrierMarketingView.as_view(),
         name='calendrier-marketing'),
    path('calendrier-marketing/reschedule/',
         CalendrierMarketingRescheduleView.as_view(),
         name='calendrier-marketing-reschedule'),
    path('webhooks/brevo/', webhook_brevo_campagne, name='webhook-brevo-campagne'),
    path('webhooks/sms-stop/', webhook_sms_stop, name='webhook-sms-stop'),
    path('desinscription/<str:token>/', desinscription_publique,
         name='desinscription-publique'),
    path('double-optin/<str:token>/', double_optin_confirmer,
         name='double-optin-confirmer'),
    path('r/<str:token>/', redirection_lien_tracke,
         name='redirection-lien-tracke'),
    path('enquetes-publiques/<str:token>/', enquete_publique,
         name='enquete-publique'),
    path('enquetes-publiques/<str:token>/soumettre/', enquete_soumettre,
         name='enquete-soumettre'),
    path('reponses-enquete/<int:reponse_id>/certificat/', enquete_certificat_pdf,
         name='enquete-certificat-pdf'),
    path('evenements-marketing/<int:evenement_id>/inscription-publique/',
         evenement_inscription_publique, name='evenement-inscription-publique'),
    # XFAC26/27 — Portail client self-service (token, sans login).
    path('portail/<str:token>/mon-releve/', portail_mon_releve,
         name='portail-mon-releve'),
    path('portail/<str:token>/mon-releve/pdf/', portail_mon_releve_pdf,
         name='portail-mon-releve-pdf'),
    path('portail/<str:token>/factures/<int:facture_id>/contester/',
         portail_contester_facture, name='portail-contester-facture'),
    # NTTRE27 — réglages trésorerie (singleton par société, GET/PATCH).
    path('parametres-tresorerie/', ParametresTresorerieView.as_view(),
         name='parametres-tresorerie'),
    path('', include(router.urls)),
]
