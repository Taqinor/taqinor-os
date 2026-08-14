"""Routes de l'app `mrp`, montées sous `/api/django/mrp/…` (et `/api/v1/mrp/…`)
via `erp_agentique.urls`."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GammeViewSet, OperationGammeViewSet, OperationOFViewSet,
    OrdreFabricationViewSet, PosteDeChargeViewSet, mrp_run_view,
)

router = DefaultRouter()
router.register(r'postes-charge', PosteDeChargeViewSet, basename='mrp-poste-charge')
router.register(r'gammes', GammeViewSet, basename='mrp-gamme')
router.register(r'operations-gamme', OperationGammeViewSet, basename='mrp-operation-gamme')
router.register(
    r'ordres-fabrication', OrdreFabricationViewSet, basename='mrp-ordre-fabrication')
router.register(r'operations-of', OperationOFViewSet, basename='mrp-operation-of')

urlpatterns = [
    path('mrp-run/', mrp_run_view, name='mrp-run'),
    path('', include(router.urls)),
]
