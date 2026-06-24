from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActifFlotteViewSet,
    EnginRoulantViewSet,
    ReferentielFlotteViewSet,
    VehiculeViewSet,
)

router = DefaultRouter()
router.register(r'vehicules', VehiculeViewSet)
router.register(r'engins', EnginRoulantViewSet)
router.register(r'referentiels', ReferentielFlotteViewSet)
router.register(r'actifs', ActifFlotteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
