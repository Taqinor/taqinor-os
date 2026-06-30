from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActifFlotteViewSet,
    AffectationConducteurViewSet,
    AssuranceVehiculeViewSet,
    BaremeVignetteViewSet,
    CarteCarburantViewSet,
    CarteGriseVehiculeViewSet,
    ConducteurViewSet,
    EcheanceEntretienViewSet,
    EcheanceReglementaireViewSet,
    EnginRoulantViewSet,
    EtatDesLieuxViewSet,
    GarageViewSet,
    InfractionViewSet,
    OrdreReparationViewSet,
    PieceFlotteViewSet,
    PlanEntretienViewSet,
    PneumatiqueViewSet,
    PleinCarburantViewSet,
    ReferentielFlotteViewSet,
    ReservationVehiculeViewSet,
    SinistreViewSet,
    VehiculeViewSet,
    VisiteTechniqueViewSet,
)

router = DefaultRouter()
router.register(r'vehicules', VehiculeViewSet)
router.register(r'engins', EnginRoulantViewSet)
router.register(r'referentiels', ReferentielFlotteViewSet)
router.register(r'actifs', ActifFlotteViewSet)
router.register(r'conducteurs', ConducteurViewSet)
router.register(r'affectations', AffectationConducteurViewSet)
router.register(r'reservations', ReservationVehiculeViewSet)
router.register(r'etats-des-lieux', EtatDesLieuxViewSet)
router.register(r'pleins', PleinCarburantViewSet)
router.register(r'cartes', CarteCarburantViewSet)
router.register(r'plans-entretien', PlanEntretienViewSet)
router.register(r'echeances-entretien', EcheanceEntretienViewSet)
router.register(r'garages', GarageViewSet)
router.register(r'ordres-reparation', OrdreReparationViewSet)
router.register(r'pneumatiques', PneumatiqueViewSet)
router.register(r'pieces', PieceFlotteViewSet)
router.register(r'echeances-reglementaires', EcheanceReglementaireViewSet)
router.register(r'baremes-vignette', BaremeVignetteViewSet)
router.register(r'assurances', AssuranceVehiculeViewSet)
router.register(r'visites-techniques', VisiteTechniqueViewSet)
router.register(r'cartes-grises', CarteGriseVehiculeViewSet)
router.register(r'sinistres', SinistreViewSet)
router.register(r'infractions', InfractionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
