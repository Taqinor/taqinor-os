from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    ActeMedicalViewSet, ActeRealiseViewSet, AdmissionViewSet,
    ConventionViewSet, DisponibilitesView, FactureSanteViewSet,
    GrilleTarifaireViewSet, HoraireOuverturePraticienViewSet,
    IndisponibilitePraticienViewSet, PaiementSanteViewSet, PatientViewSet,
    PraticienSiteViewSet, PraticienViewSet, PriseEnChargeViewSet,
    RendezVousViewSet, SalleViewSet)

router = DefaultRouter()
router.register(r'praticiens', PraticienViewSet, basename='sante-praticien')
router.register(r'salles', SalleViewSet, basename='sante-salle')
router.register(r'patients', PatientViewSet, basename='sante-patient')
router.register(r'rendezvous', RendezVousViewSet, basename='sante-rendezvous')
router.register(
    r'horaires-ouverture-praticien', HoraireOuverturePraticienViewSet,
    basename='sante-horaire-ouverture-praticien')
router.register(
    r'indisponibilites-praticien', IndisponibilitePraticienViewSet,
    basename='sante-indisponibilite-praticien')
router.register(
    r'sites-praticien', PraticienSiteViewSet, basename='sante-praticien-site')
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
router.register(
    r'paiements-sante', PaiementSanteViewSet, basename='sante-paiement-sante')

urlpatterns = [
    # NTSAN29 — endpoint interne de disponibilités (avant le router : ne
    # doit jamais être capté par un basename DRF).
    path(
        'disponibilites/', DisponibilitesView.as_view(),
        name='sante-disponibilites'),
    path('', include(router.urls)),
]
