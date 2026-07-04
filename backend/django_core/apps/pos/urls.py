from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CommandeRetraitViewSet,
    ConfigMaterielPOSViewSet,
    SessionCaisseViewSet,
    VenteComptoirViewSet,
)

router = DefaultRouter()
router.register(r'ventes', VenteComptoirViewSet, basename='pos-vente')
router.register(r'sessions', SessionCaisseViewSet, basename='pos-session')
router.register(r'retraits', CommandeRetraitViewSet, basename='pos-retrait')
router.register(
    r'config-materiel', ConfigMaterielPOSViewSet, basename='pos-config-materiel')

urlpatterns = [
    path('', include(router.urls)),
]
