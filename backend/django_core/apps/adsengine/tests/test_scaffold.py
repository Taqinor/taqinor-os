"""ENG1 — Tests du scaffold de l'app ``adsengine``.

Vérifie que l'app est installée, routée sous ``/api/django/adsengine/`` et que
l'endpoint de liveness ``status/`` répond ``{"ok": true}`` à un utilisateur
authentifié (401 pour un anonyme).
"""
from django.apps import apps as django_apps
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = None


def _user_model():
    from django.contrib.auth import get_user_model
    return get_user_model()


STATUS_URL = '/api/django/adsengine/status/'


class AdsengineScaffoldTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ads Co', slug='ads-co')
        self.user = _user_model().objects.create_user(
            username='ads_user', password='x', company=self.company)

    def _auth(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_app_is_installed(self):
        self.assertTrue(django_apps.is_installed('apps.adsengine'))

    def test_status_ok_for_authenticated_user(self):
        resp = self._auth().get(STATUS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'ok': True})

    def test_status_requires_authentication(self):
        resp = APIClient().get(STATUS_URL)
        self.assertIn(resp.status_code, (401, 403))
