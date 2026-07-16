from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    ActeMedicalViewSet, ActeRealiseViewSet, AdmissionViewSet,
    ConventionViewSet, FactureSanteViewSet, GrilleTarifaireViewSet,
    PatientViewSet, PraticienViewSet, PriseEnChargeViewSet, RendezVousViewSet,
    SalleViewSet)

router = DefaultRouter()
router.register(r'praticiens', PraticienViewSet, basename='sante-praticien')
router.register(r'salles', SalleViewSet, basename='sante-salle')
router.register(r'patients', PatientViewSet, basename='sante-patient')
router.register(r'rendezvous', RendezVousViewSet, basename='sante-rendezvous')
router.register(r'admissions', AdmissionViewSet, basename='sante-admission')
router.register(
    r'actes-medicaux', ActeMedicalViewSet, basename='sante-acte-medical')
router.register(r'conventions', ConventionViewSet, basename='sante-convention')
router.register(
    r'grilles-tarifaires', GrilleTarifaireViewSet,
    basename='sante-grille-tarifaire')
router.register(
    r'actes-realises', ActeRealiseViewSet, basename='sante-acte-realise')
router.register(
    r'prises-en-charge', PriseEnChargeViewSet, basename='sante-prise-en-charge')
router.register(
    r'factures-sante', FactureSanteViewSet, basename='sante-facture-sante')

urlpatterns = [
    path('', include(router.urls)),
]
