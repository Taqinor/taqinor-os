"""Tests — endpoint GET /ventes/roof-config/ (config carte du builder 3D ERP).

Vérifie : authentification requise, et que les clés carte d'environnement
(PUBLIC_MAPTILER_KEY / PUBLIC_MAPBOX_TOKEN) sont reflétées telles quelles, avec
``available`` piloté par la présence de la clé MapTiler."""
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRoofConfig(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='rc-co', defaults={'nom': 'RC Co'})
        self.user = User.objects.create_user(
            username='rc_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.url = '/api/django/ventes/roof-config/'

    def test_requires_auth(self):
        """Sans session, l'endpoint est refusé (401/403)."""
        anon = APIClient()
        resp = anon.get(self.url)
        self.assertIn(resp.status_code, (401, 403))

    @mock.patch.dict(os.environ, {
        'PUBLIC_MAPTILER_KEY': 'maptiler-test-key',
        'PUBLIC_MAPBOX_TOKEN': 'mapbox-test-token',
    })
    def test_returns_keys_when_present(self):
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['available'])
        self.assertEqual(resp.data['maptilerKey'], 'maptiler-test-key')
        self.assertEqual(resp.data['mapboxToken'], 'mapbox-test-token')

    @mock.patch.dict(os.environ, {
        'PUBLIC_MAPTILER_KEY': '',
    }, clear=False)
    def test_unavailable_without_maptiler_key(self):
        # On retire explicitement la clé MapTiler (et un éventuel token Mapbox).
        with mock.patch.dict(os.environ, {'PUBLIC_MAPTILER_KEY': ''}):
            os.environ.pop('PUBLIC_MAPBOX_TOKEN', None)
            resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['available'])
        self.assertEqual(resp.data['maptilerKey'], '')
        self.assertIsNone(resp.data['mapboxToken'])
