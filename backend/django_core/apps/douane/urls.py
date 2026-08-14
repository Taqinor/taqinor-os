"""Routes douane (NTLOG), montées sous ``/api/django/douane/…`` (et
``/api/v1/douane/…``) via ``erp_agentique.urls``. Volet import (NTLOG10-13/
21/22/26/30) BLOCKED — voir ``apps/douane/apps.py``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DossierExportViewSet, PieceDossierExportViewSet

router = DefaultRouter()
router.register(r'dossiers-export', DossierExportViewSet, basename='douane-dossier-export')
router.register(
    r'dossiers-export-pieces', PieceDossierExportViewSet,
    basename='douane-piece-dossier-export')

urlpatterns = [
    path('', include(router.urls)),
]
