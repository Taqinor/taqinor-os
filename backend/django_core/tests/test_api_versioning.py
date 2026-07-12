"""YAPIC7 — stratégie de versionnement unique (URLPathVersioning).

Prouve, EN ISOLATION contre la classe DRF + les réglages du projet (même
méthode que ``core/tests/test_pagination_cap.py`` pour YAPIC1, sans passer
par une route réelle — cf. docs/api-conventions.md §3 : aucune route de ce
repo ne capture de segment ``<version>``, donc on ne peut pas prouver ce
comportement en tapant une URL) :

  * ``request.version`` vaut ``'v1'`` par défaut (aucun kwarg ``version``
    dans l'URL, exactement le cas de TOUTES les routes de ce repo) ;
  * une version explicitement demandée mais hors ``ALLOWED_VERSIONS`` est
    refusée PROPREMENT (``rest_framework.exceptions.NotFound``), jamais une
    exception non gérée ni une 404 Django brute ;
  * les anciens ET les nouveaux préfixes résolvent vers les MÊMES vues
    (``erp_agentique.urls._APP_URLS`` monté deux fois, zéro duplication).
"""
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.versioning import URLPathVersioning


class URLPathVersioningUnitTests(SimpleTestCase):
    """La classe DRF, configurée comme le projet la configure."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.versioning = URLPathVersioning()

    def _drf_request(self, url='/api/v1/stock/produits/'):
        return Request(self.factory.get(url))

    def test_settings_wire_url_path_versioning(self):
        rf = settings.REST_FRAMEWORK
        self.assertEqual(
            rf['DEFAULT_VERSIONING_CLASS'],
            'rest_framework.versioning.URLPathVersioning',
        )
        self.assertEqual(rf['DEFAULT_VERSION'], 'v1')
        self.assertEqual(rf['ALLOWED_VERSIONS'], ('v1',))

    def test_default_version_is_v1_without_url_kwarg(self):
        # Aucune route de ce repo ne capture de kwarg `version` (voir
        # docs/api-conventions.md §3) : `determine_version` retombe donc
        # systématiquement sur DEFAULT_VERSION, quel que soit le préfixe.
        request = self._drf_request()
        version = self.versioning.determine_version(request)
        self.assertEqual(version, 'v1')

    def test_unknown_version_is_cleanly_rejected(self):
        # Simule ce qui se passerait SI un jour une route capturait un
        # kwarg `version` hors ALLOWED_VERSIONS : rejet propre DRF, pas un
        # crash ni une 404 Django brute.
        request = self._drf_request()
        with self.assertRaises(NotFound):
            self.versioning.determine_version(request, version='v2')

    def test_allowed_version_v1_is_accepted_explicitly(self):
        request = self._drf_request()
        version = self.versioning.determine_version(request, version='v1')
        self.assertEqual(version, 'v1')


class DualPrefixResolutionTests(SimpleTestCase):
    """Le préfixe historique ET le nouveau préfixe v1 résolvent — même vue."""

    def test_legacy_token_prefix_still_resolves(self):
        # Zéro rupture : les endpoints hors _APP_URLS (JWT, schéma...)
        # restent inchangés, non dupliqués sous /api/v1/.
        legacy = resolve('/api/django/token/refresh/')
        self.assertIsNotNone(legacy.func)

    def test_v1_stock_prefix_resolves_to_same_view_as_legacy(self):
        legacy = resolve('/api/django/stock/produits/')
        v1 = resolve('/api/v1/stock/produits/')
        self.assertEqual(legacy.func.cls, v1.func.cls)
