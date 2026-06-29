from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActifFlotteViewSet,
    AffectationConducteurViewSet,
    ConducteurViewSet,
    EnginRoulantViewSet,
    EtatDesLieuxViewSet,
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

urlpatterns = [
    path('', include(router.urls)),
]
