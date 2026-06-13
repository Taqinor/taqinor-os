from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import InstallationViewSet, InterventionViewSet

router = DefaultRouter()
router.register(r'chantiers', InstallationViewSet)
router.register(r'interventions', InterventionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
