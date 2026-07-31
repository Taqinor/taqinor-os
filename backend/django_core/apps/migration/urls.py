"""Routes du groupe NTMIG — montées sous ``/api/django/migration/``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LotMigrationViewSet, ProjetMigrationViewSet

router = DefaultRouter()
router.register(
    r'projets-migration', ProjetMigrationViewSet,
    basename='migration-projet')
router.register(
    r'lots-migration', LotMigrationViewSet, basename='migration-lot')

urlpatterns = [
    path('', include(router.urls)),
]
