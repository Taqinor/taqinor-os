from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DevisViewSet,
    LigneDevisViewSet,
    BonCommandeViewSet,
    FactureViewSet,
    LigneFactureViewSet,
)

router = DefaultRouter()
router.register(r'devis', DevisViewSet)
router.register(r'devis-lignes', LigneDevisViewSet)
router.register(r'bons-commande', BonCommandeViewSet)
router.register(r'factures', FactureViewSet)
router.register(r'factures-lignes', LigneFactureViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
