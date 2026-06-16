from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InstallationViewSet, InterventionViewSet, ParcInstalleViewSet,
    TypeInterventionViewSet,
)

router = DefaultRouter()
router.register(r'chantiers', InstallationViewSet)
router.register(r'interventions', InterventionViewSet)
router.register(r'types-intervention', TypeInterventionViewSet)
router.register(r'parc', ParcInstalleViewSet, basename='parc')

urlpatterns = [
    path('', include(router.urls)),
]
