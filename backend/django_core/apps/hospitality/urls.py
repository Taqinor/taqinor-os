from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChambreViewSet, EvenementBanquetViewSet, FolioViewSet,
    MainCouranteViewSet, PlanTarifaireViewSet, RecetteViewSet,
    ReservationViewSet, SalleEvenementViewSet, TableauBordView,
    TacheMenageViewSet, TypeChambreViewSet,
)

router = DefaultRouter()
router.register(r'types-chambre', TypeChambreViewSet)
router.register(r'chambres', ChambreViewSet)
router.register(r'plans-tarifaires', PlanTarifaireViewSet)
router.register(r'reservations', ReservationViewSet)
router.register(r'folios', FolioViewSet)
router.register(r'taches-menage', TacheMenageViewSet)
router.register(r'main-courante', MainCouranteViewSet)
router.register(r'recettes', RecetteViewSet)
router.register(r'salles-evenement', SalleEvenementViewSet)
router.register(r'evenements', EvenementBanquetViewSet)

urlpatterns = [
    path('tableau-bord/', TableauBordView.as_view(), name='hospitality-tableau-bord'),
    path('', include(router.urls)),
]
