"""Routes de l'app `mrp`, montées sous `/api/django/mrp/…` (et `/api/v1/mrp/…`)
via `erp_agentique.urls`."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CoutStandardViewSet, GammeViewSet, OperationGammeViewSet, OperationOFViewSet,
    OrdreFabricationViewSet, OrdreModificationViewSet, PosteDeChargeViewSet,
    analyse_couts_view, charge_postes_view, mrp_run_view, oee_tous_postes_view,
)

router = DefaultRouter()
router.register(r'postes-charge', PosteDeChargeViewSet, basename='mrp-poste-charge')
router.register(r'gammes', GammeViewSet, basename='mrp-gamme')
router.register(r'operations-gamme', OperationGammeViewSet, basename='mrp-operation-gamme')
router.register(
    r'ordres-fabrication', OrdreFabricationViewSet, basename='mrp-ordre-fabrication')
router.register(r'operations-of', OperationOFViewSet, basename='mrp-operation-of')
router.register(r'couts-standard', CoutStandardViewSet, basename='mrp-cout-standard')
router.register(r'ecos', OrdreModificationViewSet, basename='mrp-eco')

urlpatterns = [
    path('mrp-run/', mrp_run_view, name='mrp-run'),
    path('charge-postes/', charge_postes_view, name='mrp-charge-postes'),
    path('analyse-couts/', analyse_couts_view, name='mrp-analyse-couts'),
    path('oee-postes/', oee_tous_postes_view, name='mrp-oee-postes'),
    path('', include(router.urls)),
]
