from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CommentaireVarianceViewSet, CycleBudgetaireViewSet, DepartementViewSet,
    DriversViewSet, HypotheseRecrutementViewSet, LigneBudgetDepartementViewSet,
    LignePrevisionGlissanteViewSet, LigneScenarioViewSet,
    PrevisionGlissanteViewSet, ScenarioBudgetaireViewSet,
    SoumissionBudgetDepartementViewSet, VarianceViewSet,
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
router.register(
    r'hypotheses-recrutement', HypotheseRecrutementViewSet,
    basename='fpa-hypothese-recrutement')
router.register(r'scenarios', ScenarioBudgetaireViewSet, basename='fpa-scenario')
router.register(
    r'lignes-scenario', LigneScenarioViewSet, basename='fpa-ligne-scenario')
router.register(r'variance', VarianceViewSet, basename='fpa-variance')
router.register(
    r'commentaires-variance', CommentaireVarianceViewSet,
    basename='fpa-commentaire-variance')
router.register(r'drivers', DriversViewSet, basename='fpa-drivers')

urlpatterns = [
    path('', include(router.urls)),
]
