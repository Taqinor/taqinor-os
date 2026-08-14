from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .public_views import quai_checkin_view
from .views import (
    ProduitViewSet, CategorieViewSet, FournisseurViewSet,
    MouvementStockViewSet, MarqueViewSet, BonCommandeFournisseurViewSet,
    EmplacementStockViewSet, TransfertStockViewSet, PrixFournisseurViewSet,
    RetourFournisseurViewSet, ReceptionFournisseurViewSet,
    FactureFournisseurViewSet, PaiementFournisseurViewSet,
    InventaireSessionViewSet, KitProduitViewSet,
    FicheTechniqueViewSet,
    DocumentConformiteFournisseurViewSet, AchatsParametresViewSet,
    ContactFournisseurViewSet, CategorieFournisseurViewSet,
    AcompteFournisseurViewSet, AvoirFournisseurViewSet,
    LotEntrepotViewSet, InventaireAnnuelViewSet, RevalorisationStockViewSet,
    ConditionnementProduitViewSet, ModeleBonCommandeFournisseurViewSet,
    NomenclatureCodeBarresViewSet, RegleCodeBarresViewSet,
    CatalogueAchatViewSet,
    BudgetDepartementViewSet, EngagementBudgetViewSet,
    DossierOnboardingFournisseurViewSet, DocumentFournisseurViewSet,
    VaguePickingViewSet, UniteLogistiqueViewSet, QuaiViewSet,
    RendezVousTransporteurViewSet, ExpeditionTransporteurViewSet,
    PlanComptageTournantViewSet,
    scanner_resoudre_view, scanner_mouvement_view,
)

router = DefaultRouter()
router.register(r'produits', ProduitViewSet)
router.register(r'categories', CategorieViewSet)
router.register(r'fournisseurs', FournisseurViewSet)
router.register(r'mouvements', MouvementStockViewSet)
router.register(r'marques', MarqueViewSet)
router.register(r'bons-commande-fournisseur', BonCommandeFournisseurViewSet)
router.register(r'emplacements', EmplacementStockViewSet)
router.register(r'transferts', TransfertStockViewSet)
router.register(r'prix-fournisseurs', PrixFournisseurViewSet)
router.register(r'retours-fournisseur', RetourFournisseurViewSet)
router.register(r'receptions-fournisseur', ReceptionFournisseurViewSet)
router.register(r'factures-fournisseur', FactureFournisseurViewSet)
router.register(r'paiements-fournisseur', PaiementFournisseurViewSet)
router.register(r'inventaire-sessions', InventaireSessionViewSet)
router.register(r'kits', KitProduitViewSet)
router.register(r'fiches-techniques', FicheTechniqueViewSet)
router.register(
    r'documents-conformite-fournisseur', DocumentConformiteFournisseurViewSet)
router.register(
    r'achats-parametres', AchatsParametresViewSet,
    basename='achats-parametres')
router.register(r'contacts-fournisseur', ContactFournisseurViewSet)
router.register(r'categories-fournisseur', CategorieFournisseurViewSet)
router.register(r'acomptes-fournisseur', AcompteFournisseurViewSet)
router.register(r'avoirs-fournisseur', AvoirFournisseurViewSet)
router.register(r'lots-entrepot', LotEntrepotViewSet)
router.register(r'inventaires-annuels', InventaireAnnuelViewSet)
router.register(r'revalorisations-stock', RevalorisationStockViewSet)
router.register(r'conditionnements', ConditionnementProduitViewSet)
router.register(r'modeles-bcf', ModeleBonCommandeFournisseurViewSet)
router.register(
    r'nomenclatures-code-barres', NomenclatureCodeBarresViewSet)
router.register(r'regles-code-barres', RegleCodeBarresViewSet)
# NTP2P3 — catalogue interne d'achat (lecture seule, sans prix de vente).
router.register(
    r'catalogue-achat', CatalogueAchatViewSet, basename='catalogue-achat')
# NTP2P4 — budgets d'engagement par département + engagements (lecture seule).
router.register(r'budgets-departement', BudgetDepartementViewSet)
router.register(r'engagements-budget', EngagementBudgetViewSet)
# NTP2P7 — onboarding fournisseur : dossier + pièces légales (MinIO).
router.register(
    r'dossiers-onboarding-fournisseur', DossierOnboardingFournisseurViewSet)
router.register(r'documents-fournisseur', DocumentFournisseurViewSet)
# -- Groupe NTWMS -- couche ENTREPOT --
router.register(r'vagues-picking', VaguePickingViewSet)
router.register(r'unites-logistiques', UniteLogistiqueViewSet)
router.register(r'quais', QuaiViewSet)
router.register(r'rendez-vous-transporteur', RendezVousTransporteurViewSet)
router.register(r'expeditions', ExpeditionTransporteurViewSet)
router.register(
    r'plans-comptage-tournant', PlanComptageTournantViewSet)

urlpatterns = [
    # NTWMS8 - kiosque de quai (chemin nomme par la tache : /stock/public/...).
    path('public/quai-checkin/', quai_checkin_view,
         name='stock-quai-checkin'),
    # NTWMS5 - poste scanner mobile (resolution universelle + mouvement scanne).
    path('scanner/resoudre/', scanner_resoudre_view,
         name='stock-scanner-resoudre'),
    path('scanner/mouvement/', scanner_mouvement_view,
         name='stock-scanner-mouvement'),
    path('', include(router.urls)),
]
