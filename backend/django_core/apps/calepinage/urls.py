"""Routes du module « calepinage » (CAL4).

Montées dans ``erp_agentique/urls.py`` sous ``path('calepinage/', …)``, donc
servies à partir de ``/api/django/calepinage/``. Le 2ᵉ segment d'URL est la clé
``module_manifest['key']`` (``calepinage``) : le gatage 404 des modules
désactivés vise le bon module SANS entrée ``PREFIX_TO_MODULE``.

FORME D'URL UNIQUE (CAL233) — tout l'objet métier est servi sous
``/api/django/calepinage/calepinages/<pk>/…`` (sous-ressources en ``@action``
du routeur DRF) et les réglages société sous
``/api/django/calepinage/parametres/``. Aucune autre famille d'URL n'est
admise : deux familles pour un même objet, c'est l'incident PACT10 par
construction. Un test (``tests/test_structure_urls.py``) le vérifie.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Les enregistrements arrivent avec les viewsets (CAL16+) :
#   router.register(r'calepinages', CalepinageViewSet, basename='calepinage')
#   router.register(r'parametres', ParametresViewSet, basename='cal-parametres')

urlpatterns = [
    path('', include(router.urls)),
]
