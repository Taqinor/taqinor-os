from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    PatientViewSet, PraticienViewSet, RendezVousViewSet, SalleViewSet)

router = DefaultRouter()
router.register(r'praticiens', PraticienViewSet, basename='sante-praticien')
router.register(r'salles', SalleViewSet, basename='sante-salle')
router.register(r'patients', PatientViewSet, basename='sante-patient')
router.register(r'rendezvous', RendezVousViewSet, basename='sante-rendezvous')

urlpatterns = [
    path('', include(router.urls)),
]
