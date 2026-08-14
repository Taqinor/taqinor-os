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

urlpatterns = [
    path('', include(router.urls)),
]
