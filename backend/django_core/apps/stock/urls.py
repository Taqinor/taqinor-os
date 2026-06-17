from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProduitViewSet, CategorieViewSet, FournisseurViewSet,
    MouvementStockViewSet, MarqueViewSet, BonCommandeFournisseurViewSet,
    EmplacementStockViewSet, TransfertStockViewSet,
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

urlpatterns = [
    path('', include(router.urls)),
]
