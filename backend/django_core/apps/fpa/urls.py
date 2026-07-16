from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CycleBudgetaireViewSet, DepartementViewSet, LigneBudgetDepartementViewSet,
)

router = DefaultRouter()
router.register(r'departements', DepartementViewSet, basename='fpa-departement')
router.register(
    r'cycles-budgetaires', CycleBudgetaireViewSet,
    basename='fpa-cycle-budgetaire')
router.register(
    r'lignes-budget-departement', LigneBudgetDepartementViewSet,
    basename='fpa-ligne-budget-departement')

urlpatterns = [
    path('', include(router.urls)),
]
