"""Routes du module « Veille appels d'offres » (``apps.veille_ao``) — VAO6.

Préfixe ``/api/django/veille_ao/…``, monté depuis ``_APP_URLS`` dans
``erp_agentique/urls.py``.

Le 2ᵉ segment d'URL est **identique à la clé de manifeste** (`veille_ao`, avec
un underscore, pas un tiret) : le gatage 404 des modules désactivés
(``core.permissions.DisabledModuleMiddleware``) dérive du segment, et un
segment en tiret imposerait une entrée ``core/permissions.PREFIX_TO_MODULE``.
Une garde le vérifie dans ``tests/test_smoke.py``.

Le routeur est vide à la création du module : les ViewSets s'enregistrent ici
au fur et à mesure (sources, avis, mots-clés, règles d'exclusion).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
