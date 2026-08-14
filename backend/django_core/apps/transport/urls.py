from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(
    'ordres-transport', views.OrdreTransportViewSet, basename='ordres-transport')
router.register(
    'lignes-transport', views.LigneOrdreTransportViewSet,
    basename='lignes-transport')
router.register(
    'etapes-transport', views.EtapeTransportViewSet, basename='etapes-transport')
router.register(
    'couts-fret', views.CoutFretReelViewSet, basename='couts-fret')
router.register(
    'litiges-transport', views.LitigeTransportViewSet,
    basename='litiges-transport')
router.register(
    'reserves-reception', views.ReserveReceptionViewSet,
    basename='reserves-reception')
router.register(
    'facteurs-emission-co2', views.FacteurEmissionCO2ViewSet,
    basename='facteurs-emission-co2')

urlpatterns = [
    path('', include(router.urls)),
]
