"""Routes du module GRC & Conformité (NTGRC).

Monté par ``erp_agentique/urls.py`` sous ``api/django/grc/`` (et donc aussi
sous ``api/v1/grc/``). Le 2ᵉ segment correspond à la clé
``module_manifest['key']`` (``grc``) pour que le gatage 404 des modules
désactivés vise le bon module.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import deposer_demande_droit, suivre_demande_droit

router = DefaultRouter()

urlpatterns = [
    # NTGRC2 — portail PUBLIC de dépôt/suivi d'une demande de droit
    # (loi 09-08). AllowAny + throttle ; déclarés AVANT le routeur pour que
    # « public » ne puisse jamais être capté par un préfixe de viewset.
    path('public/demande-droit/', deposer_demande_droit,
         name='grc-demande-droit-depot'),
    path('public/demande-droit/<str:token>/', suivre_demande_droit,
         name='grc-demande-droit-suivi'),
    path('', include(router.urls)),
]
