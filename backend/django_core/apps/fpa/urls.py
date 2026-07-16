from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CycleBudgetaireViewSet, DepartementViewSet

router = DefaultRouter()
router.register(r'departements', DepartementViewSet, basename='fpa-departement')
router.register(
    r'cycles-budgetaires', CycleBudgetaireViewSet,
    basename='fpa-cycle-budgetaire')

urlpatterns = [
    path('', include(router.urls)),
]
