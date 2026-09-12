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

VTA3 y enregistrera le ``VisiteTerrainViewSet`` relogé depuis ``apps.crm``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
