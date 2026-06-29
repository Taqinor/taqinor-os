from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActifFlotteViewSet,
    AffectationConducteurViewSet,
    CarteCarburantViewSet,
    ConducteurViewSet,
    EcheanceEntretienViewSet,
    EnginRoulantViewSet,
    EtatDesLieuxViewSet,
    GarageViewSet,
    OrdreReparationViewSet,
    PieceFlotteViewSet,
    PlanEntretienViewSet,
    PneumatiqueViewSet,
    PleinCarburantViewSet,
    ReferentielFlotteViewSet,
    ReservationVehiculeViewSet,
    VehiculeViewSet,
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

urlpatterns = [
    path('', include(router.urls)),
]
