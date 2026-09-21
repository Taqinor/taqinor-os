"""Routes de conformité fiscale marocaine (NTMAR), montées sous
``/api/django/fiscal/…`` (et ``/api/v1/fiscal/…``) via ``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttestationTenantViewSet, BeneficiaireEffectifViewSet,
    EcheanceFiscaleViewSet, ObligationFiscaleViewSet, VeilleReglementaireViewSet,
    tableau_conformite_view,
)

router = DefaultRouter()
router.register(r'obligations', ObligationFiscaleViewSet, basename='fiscal-obligation')
router.register(r'echeances', EcheanceFiscaleViewSet, basename='fiscal-echeance')
router.register(
    r'attestations-tenant', AttestationTenantViewSet, basename='fiscal-attestation')
router.register(
    r'beneficiaires-effectifs', BeneficiaireEffectifViewSet, basename='fiscal-ubo')
router.register(r'veille', VeilleReglementaireViewSet, basename='fiscal-veille')

urlpatterns = [
    path('tableau-conformite/', tableau_conformite_view, name='fiscal-tableau-conformite'),
    path('', include(router.urls)),
]
