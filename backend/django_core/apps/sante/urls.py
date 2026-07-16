from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    ActeMedicalViewSet, AdmissionViewSet, PatientViewSet, PraticienViewSet,
    RendezVousViewSet, SalleViewSet)

router = DefaultRouter()
router.register(r'praticiens', PraticienViewSet, basename='sante-praticien')
router.register(r'salles', SalleViewSet, basename='sante-salle')
router.register(r'patients', PatientViewSet, basename='sante-patient')
router.register(r'rendezvous', RendezVousViewSet, basename='sante-rendezvous')
router.register(r'admissions', AdmissionViewSet, basename='sante-admission')
router.register(
    r'actes-medicaux', ActeMedicalViewSet, basename='sante-acte-medical')

urlpatterns = [
    path('', include(router.urls)),
]
