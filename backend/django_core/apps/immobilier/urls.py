from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BailViewSet, BatimentViewSet, BudgetChargesViewSet, DepenseChargesViewSet,
    EcheanceLoyerViewSet, LocalViewSet, LocataireViewSet, NiveauViewSet,
    RelanceLoyerViewSet, SiteViewSet,
)

router = DefaultRouter()
router.register(r'sites', SiteViewSet)
router.register(r'batiments', BatimentViewSet)
router.register(r'niveaux', NiveauViewSet)
router.register(r'locaux', LocalViewSet)
router.register(r'locataires', LocataireViewSet)
router.register(r'baux', BailViewSet)
router.register(r'echeances-loyer', EcheanceLoyerViewSet)
router.register(r'relances-loyer', RelanceLoyerViewSet)
router.register(r'budgets-charges', BudgetChargesViewSet)
router.register(r'depenses-charges', DepenseChargesViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
