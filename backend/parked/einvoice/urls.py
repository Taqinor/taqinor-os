"""Routes de facturation électronique DGI (NTMAR), montées sous
``/api/django/einvoice/…`` (et ``/api/v1/einvoice/…``) via ``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FactureElectroniqueViewSet, TransmissionDGIViewSet

router = DefaultRouter()
router.register(
    r'factures-electroniques', FactureElectroniqueViewSet,
    basename='einvoice-facture')
router.register(
    r'transmissions', TransmissionDGIViewSet, basename='einvoice-transmission')

urlpatterns = [
    path('', include(router.urls)),
]
