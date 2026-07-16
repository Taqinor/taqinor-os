from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChambreViewSet, FolioViewSet, PlanTarifaireViewSet, ReservationViewSet,
    TableauBordView, TacheMenageViewSet, TypeChambreViewSet,
)

router = DefaultRouter()
router.register(r'types-chambre', TypeChambreViewSet)
router.register(r'chambres', ChambreViewSet)
router.register(r'plans-tarifaires', PlanTarifaireViewSet)
router.register(r'reservations', ReservationViewSet)
router.register(r'folios', FolioViewSet)
router.register(r'taches-menage', TacheMenageViewSet)

urlpatterns = [
    path('tableau-bord/', TableauBordView.as_view(), name='hospitality-tableau-bord'),
    path('', include(router.urls)),
]
