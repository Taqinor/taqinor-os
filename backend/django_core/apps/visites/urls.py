"""Routes du module « Visites terrain » (``apps.visites``) — VTA1.

Préfixe ``/api/django/visites/…``, monté depuis ``_APP_URLS`` dans
``erp_agentique/urls.py``.

Le 2ᵉ segment d'URL est **identique à la clé de manifeste** (``visites``) : le
gatage 404 des modules désactivés (``core.permissions.DisabledModuleMiddleware``)
dérive du segment, et un segment divergent imposerait une entrée
``core/permissions.PREFIX_TO_MODULE``. Une garde le vérifie dans
``tests/test_smoke.py``.

Les basenames sont préfixés ``visites-`` : le dépôt monte plusieurs routeurs et
deux entrées de même nom feraient renvoyer silencieusement la mauvaise URL à
``reverse()``.

VTA3 — le ``VisiteTerrainViewSet`` est relogé ici depuis ``apps.crm``. Le
préfixe complet est donc ``/api/django/visites/visites/…`` : le 1ᵉʳ ``visites``
est le MODULE (et sa clé de manifeste), le 2ᵉ la RESSOURCE — le contrat
``contract_samples/visite_terrain.json`` l'écrit exactement ainsi.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import VisiteTerrainViewSet

router = DefaultRouter()
router.register(r'visites', VisiteTerrainViewSet, basename='visites-visite')

urlpatterns = [
    path('', include(router.urls)),
]
