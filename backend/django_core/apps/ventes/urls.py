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
)

router = DefaultRouter()
router.register(r'devis', DevisViewSet)
router.register(r'devis-lignes', LigneDevisViewSet)
router.register(r'bons-commande', BonCommandeViewSet)
router.register(r'factures', FactureViewSet)
router.register(r'factures-lignes', LigneFactureViewSet)
router.register(r'paiements', PaiementViewSet)
router.register(r'avoirs', AvoirViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
