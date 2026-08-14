"""Routes de l'app `mrp`, montées sous `/api/django/mrp/…` (et `/api/v1/mrp/…`)
via `erp_agentique.urls`."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GammeViewSet, OperationGammeViewSet, PosteDeChargeViewSet

router = DefaultRouter()
router.register(r'postes-charge', PosteDeChargeViewSet, basename='mrp-poste-charge')
router.register(r'gammes', GammeViewSet, basename='mrp-gamme')
router.register(r'operations-gamme', OperationGammeViewSet, basename='mrp-operation-gamme')

urlpatterns = [
    path('', include(router.urls)),
]
