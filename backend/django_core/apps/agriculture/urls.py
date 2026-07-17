from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CampagneCulturaleViewSet, EquipeSaisonniereViewSet, EtapeCampagneViewSet,
    ExploitationViewSet, IntrantAgricoleViewSet, MaterielAgricoleViewSet,
    ParcelleViewSet, PointageAgricoleViewSet, PointIrrigationViewSet,
    RelevePointIrrigationViewSet, UtilisationMaterielViewSet,
)

router = DefaultRouter()
router.register(r'exploitations', ExploitationViewSet)
router.register(r'parcelles', ParcelleViewSet)
router.register(r'campagnes', CampagneCulturaleViewSet)
router.register(r'etapes-campagne', EtapeCampagneViewSet)
router.register(r'intrants-agricoles', IntrantAgricoleViewSet)
router.register(r'equipes-saisonnieres', EquipeSaisonniereViewSet)
router.register(r'pointages', PointageAgricoleViewSet)
router.register(r'materiels-agricoles', MaterielAgricoleViewSet)
router.register(r'utilisations-materiel', UtilisationMaterielViewSet)
router.register(r'points-irrigation', PointIrrigationViewSet)
router.register(r'releves-irrigation', RelevePointIrrigationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
