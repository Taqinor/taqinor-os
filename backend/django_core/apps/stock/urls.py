from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProduitViewSet, CategorieViewSet, FournisseurViewSet,
    MouvementStockViewSet, MarqueViewSet, BonCommandeFournisseurViewSet,
    EmplacementStockViewSet, TransfertStockViewSet, PrixFournisseurViewSet,
    RetourFournisseurViewSet, ReceptionFournisseurViewSet,
    FactureFournisseurViewSet, PaiementFournisseurViewSet,
    InventaireSessionViewSet, KitProduitViewSet,
    FicheTechniqueViewSet,
    DocumentConformiteFournisseurViewSet, AchatsParametresViewSet,
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

urlpatterns = [
    path('', include(router.urls)),
]
