"""Routes du module GRC & Conformité (NTGRC).

Monté par ``erp_agentique/urls.py`` sous ``api/django/grc/`` (et donc aussi
sous ``api/v1/grc/``). Le 2ᵉ segment correspond à la clé
``module_manifest['key']`` (``grc``) pour que le gatage 404 des modules
désactivés vise le bon module.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
