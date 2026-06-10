from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProduitViewSet, CategorieViewSet, FournisseurViewSet, MouvementStockViewSet

router = DefaultRouter()
router.register(r'produits', ProduitViewSet)
router.register(r'categories', CategorieViewSet)
router.register(r'fournisseurs', FournisseurViewSet)
router.register(r'mouvements', MouvementStockViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
