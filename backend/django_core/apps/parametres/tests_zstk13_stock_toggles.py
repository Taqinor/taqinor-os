"""ZSTK13 — réglages société stock (barcode / lots-séries / colisage).

Trois drapeaux additifs sur ``CompanyProfile``, tous ``True`` par défaut —
une société existante qui n'y touche jamais garde un comportement (et une
UI) strictement identique. Le passage à ``False`` est un masquage
d'affichage frontend pur (aucune donnée détruite, aucun endpoint retiré) ;
côté backend on vérifie seulement les défauts + la persistance via
l'endpoint du profil entreprise (``CompanyProfileSerializer`` fields='__all__').
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import CompanyProfile

User = get_user_model()

UPDATE_URL = '/api/django/parametres/update/'
GET_URL = '/api/django/parametres/'


class TestZstk13StockTogglesDefaults(TestCase):
    def test_defaults_true_byte_identical_behaviour(self):
        company = Company.objects.get_or_create(
            slug='zstk13-co', defaults={'nom': 'ZSTK13 Co'})[0]
        profile = CompanyProfile.get(company=company)
        self.assertTrue(profile.stock_lots_series_actif)
        self.assertTrue(profile.stock_colisage_actif)
        self.assertTrue(profile.stock_scan_actif)


class TestZstk13StockTogglesPersistence(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='zstk13-co2', defaults={'nom': 'ZSTK13 Co 2'})[0]
        self.admin = User.objects.create_user(
            username='zstk13_admin', password='x', role_legacy='admin',
            company=self.company)

    def _client(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_admin_can_disable_lots_series(self):
        api = self._client(self.admin)
        resp = api.patch(UPDATE_URL, {
            'stock_lots_series_actif': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['stock_lots_series_actif'])
        # Les deux autres drapeaux ne bougent pas (masquage indépendant).
        self.assertTrue(resp.data['stock_colisage_actif'])
        self.assertTrue(resp.data['stock_scan_actif'])
        profile = CompanyProfile.objects.get(company=self.company)
        self.assertFalse(profile.stock_lots_series_actif)

    def test_toggles_served_on_get(self):
        api = self._client(self.admin)
        resp = api.get(GET_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('stock_lots_series_actif', resp.data)
        self.assertIn('stock_colisage_actif', resp.data)
        self.assertIn('stock_scan_actif', resp.data)
        self.assertTrue(resp.data['stock_lots_series_actif'])
