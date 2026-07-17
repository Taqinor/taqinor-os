from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CycleBudgetaireViewSet, DepartementViewSet, LigneBudgetDepartementViewSet,
    LignePrevisionGlissanteViewSet, PrevisionGlissanteViewSet,
    SoumissionBudgetDepartementViewSet,
)

router = DefaultRouter()
router.register(r'departements', DepartementViewSet, basename='fpa-departement')
router.register(
    r'cycles-budgetaires', CycleBudgetaireViewSet,
    basename='fpa-cycle-budgetaire')
router.register(
    r'lignes-budget-departement', LigneBudgetDepartementViewSet,
    basename='fpa-ligne-budget-departement')
router.register(
    r'soumissions-budget', SoumissionBudgetDepartementViewSet,
    basename='fpa-soumission-budget')
router.register(
    r'previsions-glissantes', PrevisionGlissanteViewSet,
    basename='fpa-prevision-glissante')
router.register(
    r'lignes-prevision-glissante', LignePrevisionGlissanteViewSet,
    basename='fpa-ligne-prevision-glissante')

urlpatterns = [
    path('', include(router.urls)),
]
