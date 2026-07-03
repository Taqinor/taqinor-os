from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppelTelephoniqueViewSet,
    BaremeIndemniteViewSet, BordereauRemiseViewSet, BudgetViewSet,
    CaisseViewSet, CampagneViewSet, CautionBancaireViewSet, CentreCoutViewSet,
    CessionImmobilisationViewSet, CodePromotionViewSet,
    CommissionPayoutRunViewSet, ComparateurDevisViewSet,
    CompteComptableViewSet, CompteTresorerieViewSet, ContratAvancementViewSet,
    DeclarationTVAViewSet, DemandeApprobationConfigViewSet,
    DotationAmortissementViewSet, ECatalogueViewSet,
    EcritureComptableViewSet, EffetViewSet, EntiteConsolidationViewSet,
    EtapeSequenceViewSet,
    EtatsComptablesViewSet, ExerciceComptableViewSet, FormulaireIntakeViewSet,
    ImmobilisationViewSet,
    IndemniteChantierViewSet, JournalViewSet,
    LignePrevisionnelTresorerieViewSet, MessageWhatsAppEntrantViewSet,
    ModeleDevisViewSet, NoteFraisViewSet, OuverturePartageViewSet,
    PaymentRunViewSet,
    PeriodeComptableViewSet, PilotageViewSet, PlanComptableViewSet,
    ProvisionCreanceViewSet, RapprochementBancaireViewSet, RapprochementViewSet,
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
router.register(r'notes-frais', NoteFraisViewSet)
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
router.register(r'entites-consolidation', EntiteConsolidationViewSet)
router.register(r'pilotage', PilotageViewSet, basename='pilotage')
router.register(r'etats', EtatsComptablesViewSet, basename='etats')
router.register(r'balance-ouverture', BalanceOuvertureViewSet,
                basename='balance-ouverture')
router.register(r'provisions-periode', ProvisionsPeriodeViewSet,
                basename='provisions-periode')
router.register(r'obligations-fiscales', ObligationFiscaleViewSet)
router.register(r'familles-tva-non-deductibles', FamilleTvaNonDeductibleViewSet)
# ── Croissance commerciale / marketing / CPQ (FG201–FG214) ──────────────────
router.register(r'campagnes', CampagneViewSet)
router.register(r'sequences-relance', SequenceRelanceViewSet)
router.register(r'etapes-sequence', EtapeSequenceViewSet)
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

urlpatterns = [
    path('', include(router.urls)),
]
