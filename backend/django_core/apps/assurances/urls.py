"""Routes du registre des assurances & sinistres d'entreprise (NTASS).

Montées sous ``/api/django/assurances/…`` (et ``/api/v1/assurances/…``) via
``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActifCouvertViewSet, AttestationAssuranceViewSet, AssureurViewSet,
    CourtierViewSet, DeclarationSinistreViewSet, EcheancePrimeViewSet,
    GarantiePoliceViewSet, PoliceAssuranceViewSet,
)

router = DefaultRouter()
router.register(r'assureurs', AssureurViewSet, basename='assurances-assureur')
router.register(r'courtiers', CourtierViewSet, basename='assurances-courtier')
router.register(r'polices', PoliceAssuranceViewSet, basename='assurances-police')
router.register(
    r'garanties-police', GarantiePoliceViewSet,
    basename='assurances-garantie-police')
router.register(
    r'echeances-prime', EcheancePrimeViewSet,
    basename='assurances-echeance-prime')
router.register(
    r'actifs-couverts', ActifCouvertViewSet,
    basename='assurances-actif-couvert')
router.register(
    r'declarations-sinistre', DeclarationSinistreViewSet,
    basename='assurances-declaration-sinistre')
router.register(
    r'attestations', AttestationAssuranceViewSet,
    basename='assurances-attestation')

urlpatterns = [
    path('', include(router.urls)),
]
