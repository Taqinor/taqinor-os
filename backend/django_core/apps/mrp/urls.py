"""Routes de l'app `mrp`, montées sous `/api/django/mrp/…` (et `/api/v1/mrp/…`)
via `erp_agentique.urls`."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PosteDeChargeViewSet

router = DefaultRouter()
router.register(r'postes-charge', PosteDeChargeViewSet, basename='mrp-poste-charge')

urlpatterns = [
    path('', include(router.urls)),
]
