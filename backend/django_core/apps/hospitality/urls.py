from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChambreViewSet, FolioViewSet, PlanTarifaireViewSet, ReservationViewSet,
    TacheMenageViewSet, TypeChambreViewSet,
)

router = DefaultRouter()
router.register(r'types-chambre', TypeChambreViewSet)
router.register(r'chambres', ChambreViewSet)
router.register(r'plans-tarifaires', PlanTarifaireViewSet)
router.register(r'reservations', ReservationViewSet)
router.register(r'folios', FolioViewSet)
router.register(r'taches-menage', TacheMenageViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
