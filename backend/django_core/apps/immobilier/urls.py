from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BatimentViewSet, LocalViewSet, LocataireViewSet, NiveauViewSet,
    SiteViewSet,
)

router = DefaultRouter()
router.register(r'sites', SiteViewSet)
router.register(r'batiments', BatimentViewSet)
router.register(r'niveaux', NiveauViewSet)
router.register(r'locaux', LocalViewSet)
router.register(r'locataires', LocataireViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
