from django.urls import include, path
from rest_framework.routers import DefaultRouter

# PACT26 — les 8 ViewSets AO (AOF1) ainsi que les ViewSets marketing (ODX10)
# et portail (ODX12) NE SONT PLUS ré-enregistrés ici : le double montage
# historique sous ``/api/django/compta/…`` a été retiré (139 doubles montages
# mesurés) après vérification qu'aucun appelant frontend n'utilisait la
# variante ``/compta/…`` de ces ressources. Chacune n'est plus servie que sous
# son PROPRE préfixe : ``apps.ao.urls`` (``/ao/…``), ``apps.marketing.urls``
# (``/marketing/…``), ``apps.portail.urls`` (``/portail/…``).

from .views import (
    desinscription_publique, double_optin_confirmer,
    redirection_lien_tracke,
    enquete_publique, enquete_soumettre, enquete_certificat_pdf,
    evenement_inscription_publique,
    PostSocialViewSet,
    CalendrierMarketingView, CalendrierMarketingRescheduleView,
    webhook_brevo_campagne, webhook_sms_stop,
    portail_mon_releve, portail_mon_releve_pdf, portail_contester_facture,
    BaremeIndemniteViewSet, BordereauRemiseViewSet, BudgetViewSet,
    AcompteISViewSet, ConventionFiscaleViewSet,
    CaisseViewSet, CautionBancaireViewSet, CentreCoutViewSet,
    CessionImmobilisationViewSet, CodePromotionViewSet,
    # PACT163 / XACC15 — charges constatées d'avance (étalement).
    ChargeConstateeAvanceViewSet,
    CommissionPayoutRunViewSet, ComparateurDevisViewSet,
    CompteComptableViewSet, CompteTresorerieViewSet, ContratAvancementViewSet,
    DeclarationTVAViewSet, DemandeApprobationConfigViewSet,
    DemandeApprobationRibViewSet,
    DotationAmortissementViewSet, ECatalogueViewSet,
    EcritureComptableViewSet, EffetViewSet, EntiteConsolidationViewSet,
    EtatsComptablesViewSet, ExerciceComptableViewSet,
    ImmobilisationViewSet,
    IndemniteChantierViewSet, JournalViewSet,
    LignePrevisionnelTresorerieViewSet,
    ModeleDevisViewSet, NoteFraisViewSet,
    ParametresTresorerieView, PaymentRunViewSet, PouvoirBancaireViewSet,
    PlanRelanceTresorerieViewSet,
    PeriodeComptableViewSet, PilotageViewSet, PlafondNoteFraisViewSet,
    PlanComptableViewSet,
    ProvisionCreanceViewSet, ProvisionViewSet,
    RapportNoteFraisViewSet,
    RapprochementBancaireViewSet, RapprochementViewSet,
    RetenueGarantieViewSet, RetenueSourceViewSet,
    SessionGuidedSellingViewSet, TimbreFiscalViewSet,
    TravauxEnCoursViewSet, VirementInterneViewSet,
    DocumentPropositionViewSet, SimulationPubliqueViewSet,
    SimulationFinancementViewSet, OffreFinancementViewSet,
    LigneIncitationViewSet, EcheancierPaiementViewSet, TranchePaiementViewSet,
    ComparateurCashFinancementViewSet,
    PartenaireViewSet, SoumissionLeadPartenaireViewSet,
    CommissionPartenaireViewSet, TerritoireCommercialViewSet,
    AbonnementMonitoringViewSet,
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
    CleRepartitionViewSet, LigneCleRepartitionViewSet, RunAllocationViewSet,
    AllocationRecurrenteViewSet, EngagementComptableViewSet,
    ModeleClotureViewSet, TacheClotureModeleViewSet, InstanceClotureViewSet,
    TacheClotureViewSet, AccrualClotureViewSet, JustificationVariationViewSet,
    RapprochementCompteViewSet, LigneJustificationCompteViewSet,
    ComposantImmobilisationViewSet, DepreciationImmobilisationViewSet,
    MutationImmobilisationViewSet, ImmobilisationEnCoursViewSet,
    LigneImmobilisationEnCoursViewSet,
    ContratRevenuViewSet, ObligationPerformanceViewSet,
    EcheancierReconnaissanceViewSet,
    ModeleEcritureViewSet, LigneModeleEcritureViewSet,
    AbonnementEcritureViewSet,
    # WIR279 — XACC14 (emprunts/crédits-bails) + XACC19 (états paramétrables).
    EmpruntViewSet, EcheanceEmpruntViewSet, EtatPersonnaliseViewSet,
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
# PACT163 / XACC15 — étalement des charges constatées d'avance.
router.register(r'charges-avance', ChargeConstateeAvanceViewSet)
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
router.register(r'acomptes-is', AcompteISViewSet)
router.register(r'conventions-fiscales', ConventionFiscaleViewSet)
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
# PACT26 — campagnes/envois-campagne/…/appels : double montage retiré, ces
# ressources ne sont plus servies que sous ``apps.marketing.urls`` (ODX10).
# XMKT35 — posts réseaux sociaux (calendrier de contenu, publication gated).
router.register(r'posts-sociaux', PostSocialViewSet)
router.register(r'codes-promotion', CodePromotionViewSet)
router.register(r'modeles-devis', ModeleDevisViewSet)
router.register(r'guided-selling', SessionGuidedSellingViewSet)
router.register(r'comparateur-devis', ComparateurDevisViewSet,
                basename='comparateur-devis')
router.register(r'approbations-config', DemandeApprobationConfigViewSet)
# PACT160 / XACC24 — approbation des changements de RIB fournisseur.
router.register(r'approbations-rib', DemandeApprobationRibViewSet)
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
# PACT26 — appels-offres/…/resultats-ao : double montage retiré (AOF1), ne
# sont plus servis que sous ``apps.ao.urls`` (préfixe ``/ao/…``).
# PACT26 — comptes-portail/…/demandes-ticket-portail : double montage retiré
# (ODX12), ne sont plus servis que sous ``apps.portail.urls``.
# ── Portail client, partenaires & fidélité (FG229–FG244) ────────────────────
router.register(r'partenaires', PartenaireViewSet)
router.register(r'soumissions-lead-partenaire', SoumissionLeadPartenaireViewSet)
router.register(r'commissions-partenaire', CommissionPartenaireViewSet)
# WIR81 — UNIQUE préfixe de ``crm.TerritoireCommercial`` (FG236). Le double
# montage ODX13 (une seconde route /api/django/crm/territoires-commerciaux/)
# a été retiré : ce modèle n'est qu'un référentiel de zones (legacy) et NON le
# moteur d'assignation des leads, qui est ``apps.territoires.Territoire``.
router.register(r'territoires-commerciaux', TerritoireCommercialViewSet)
# PACT26 — enquetes-nps/…/regles-upsell : double montage retiré (ODX10), ne
# sont plus servis que sous ``apps.marketing.urls``.
router.register(r'abonnements-monitoring', AbonnementMonitoringViewSet)
# ── Comptabilité générale — mappings, auxiliaires & pièces (COMPTA2/3/10) ────
router.register(r'mappings-compte', MappingCompteViewSet)
router.register(r'comptes-auxiliaires', CompteAuxiliaireViewSet)
router.register(r'pieces-justificatives', PieceJustificativeViewSet)
router.register(r'pistes-audit', PisteAuditComptableViewSet,
                basename='pisteaudit')
# ── XFAC14 — Compensation AR/AP (netting) ───────────────────────────────────
router.register(r'compensations', CompensationViewSet)
# PACT26 — enquetes/evenements-marketing/…/domaines-envoi (XMKT27-33) :
# double montage retiré, ne sont plus servis que sous ``apps.marketing.urls``.
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
# ── NTFIN — Allocations & comptabilité d'engagement (encumbrance) ──────────
router.register(r'cles-repartition', CleRepartitionViewSet)
router.register(r'lignes-cle-repartition', LigneCleRepartitionViewSet)
router.register(r'allocations', RunAllocationViewSet)
router.register(r'allocations-recurrentes', AllocationRecurrenteViewSet)
router.register(r'engagements', EngagementComptableViewSet)
# ── NTFIN — Close management (clôture rapide) ──────────────────────────────
router.register(r'modeles-cloture', ModeleClotureViewSet)
router.register(r'taches-cloture-modele', TacheClotureModeleViewSet)
router.register(r'instances-cloture', InstanceClotureViewSet)
router.register(r'taches-cloture', TacheClotureViewSet)
router.register(r'accruals-cloture', AccrualClotureViewSet)
router.register(r'justifications-variation', JustificationVariationViewSet)
# ── NTFIN — Rapprochements de comptes de bilan (workflow 4 yeux) ───────────
router.register(r'rapprochements-compte', RapprochementCompteViewSet)
router.register(r'lignes-justification-compte', LigneJustificationCompteViewSet)
# ── NTFIN — Immobilisations avancées ───────────────────────────────────────
router.register(r'composants-immobilisation', ComposantImmobilisationViewSet)
router.register(r'depreciations-immobilisation',
                DepreciationImmobilisationViewSet)
router.register(r'mutations-immobilisation', MutationImmobilisationViewSet)
router.register(r'immobilisations-en-cours', ImmobilisationEnCoursViewSet)
router.register(r'lignes-immobilisation-en-cours',
                LigneImmobilisationEnCoursViewSet)
# ── NTFIN — Reconnaissance du revenu IFRS 15 ───────────────────────────────
router.register(r'contrats-revenu', ContratRevenuViewSet)
router.register(r'obligations-performance', ObligationPerformanceViewSet)
router.register(r'echeances-reconnaissance', EcheancierReconnaissanceViewSet)
# ── XACC8 / WIR107 — Modèles d'écriture & écritures récurrentes ────────────
router.register(r'modeles-ecriture', ModeleEcritureViewSet)
router.register(r'lignes-modele-ecriture', LigneModeleEcritureViewSet)
router.register(r'abonnements-ecriture', AbonnementEcritureViewSet)
# ── WIR279 — XACC14 : emprunts & crédits-bails contractés par la société ────
router.register(r'emprunts', EmpruntViewSet)
router.register(r'echeances-emprunt', EcheanceEmpruntViewSet)
# ── WIR279 — XACC19 : états comptables PARAMÉTRABLES. Préfixe délibérément
# DISTINCT de `etats/` (EtatsComptablesViewSet, les états FIGÉS) : les deux
# coexistent, celui-ci est additionnel.
router.register(r'etats-personnalises', EtatPersonnaliseViewSet)

urlpatterns = [
    # XMKT30 (partiel) — calendrier marketing agrégé (campagnes + posts
    # sociaux XMKT35 aujourd'hui ; autres sources à brancher, même contrat).
    path('calendrier-marketing/', CalendrierMarketingView.as_view(),
         name='calendrier-marketing'),
    path('calendrier-marketing/reschedule/',
         CalendrierMarketingRescheduleView.as_view(),
         name='calendrier-marketing-reschedule'),
    # headless: rappel d'etat entrant de Brevo, appele par leur serveur
    path('webhooks/brevo/', webhook_brevo_campagne, name='webhook-brevo-campagne'),
    # headless: rappel STOP entrant de l'operateur SMS, aucun ecran en face
    path('webhooks/sms-stop/', webhook_sms_stop, name='webhook-sms-stop'),
    # headless: lien de desinscription clique depuis un courriel, hors ERP
    path('desinscription/<str:token>/', desinscription_publique,
         name='desinscription-publique'),
    # headless: lien de confirmation double opt-in clique depuis un courriel
    path('double-optin/<str:token>/', double_optin_confirmer,
         name='double-optin-confirmer'),
    # headless: redirection de lien tracke — le navigateur suit un 302, pas axios
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
    # headless: portail client ouvert par lien tokenise, aucun ecran ERP en face
    path('portail/<str:token>/mon-releve/', portail_mon_releve,
         name='portail-mon-releve'),
    # headless: PDF du releve ouvert par le client dans son navigateur
    path('portail/<str:token>/mon-releve/pdf/', portail_mon_releve_pdf,
         name='portail-mon-releve-pdf'),
    # headless: contestation postee depuis le portail client tokenise
    path('portail/<str:token>/factures/<int:facture_id>/contester/',
         portail_contester_facture, name='portail-contester-facture'),
    # NTTRE27 — réglages trésorerie (singleton par société, GET/PATCH).
    path('parametres-tresorerie/', ParametresTresorerieView.as_view(),
         name='parametres-tresorerie'),
    path('', include(router.urls)),
]
