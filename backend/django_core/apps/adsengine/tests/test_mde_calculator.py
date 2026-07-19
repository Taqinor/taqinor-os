"""PUB87 — Tests de la vue mince MDE/puissance (calculateur opérateur).

Prouve que l'endpoint expose la math DÉJÀ testée de ``mde.py`` (jours pour
détecter un effet cible + MDE par horizon), gaté ``adsengine_view``, et refuse
proprement (400) toute entrée invalide — jamais une 500.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import mde

User = get_user_model()

URL = '/api/django/adsengine/experiences/mde/'


class MdeCalculatorEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Mde Co', slug='mde-co')

    def _api(self, perms):
        role = Role.objects.create(
            company=self.company, nom='r-' + perms[0], permissions=perms)
        user = User.objects.create_user(
            username='u-' + perms[0], password='x', company=self.company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_returns_days_and_horizons_matching_mde_module(self):
        api = self._api(['adsengine_view'])
        resp = api.get(URL, {'p': 0.02, 'volume': 300, 'cible': 0.20})
        self.assertEqual(resp.status_code, 200)
        # Les jours DOIVENT être exactement mde.days_to_detect (vue mince).
        self.assertEqual(resp.data['jours_pour_cible'],
                         mde.days_to_detect(0.02, 0.20, 300))
        self.assertIn('+20 %', resp.data['phrase_fr'])
        horizons = {h['jours'] for h in resp.data['mde_par_horizon']}
        self.assertEqual(horizons, {7, 14, 28})

    def test_default_target_is_20_percent(self):
        api = self._api(['adsengine_view'])
        resp = api.get(URL, {'p': 0.02, 'volume': 300})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['cible_relative'], 0.20)

    def test_invalid_p_returns_400_not_500(self):
        api = self._api(['adsengine_view'])
        for bad in ('0', '1', '1.5', 'abc', ''):
            resp = api.get(URL, {'p': bad, 'volume': 300})
            self.assertEqual(resp.status_code, 400)

    def test_invalid_volume_returns_400(self):
        api = self._api(['adsengine_view'])
        resp = api.get(URL, {'p': 0.02, 'volume': 0})
        self.assertEqual(resp.status_code, 400)

    def test_gated_view_permission(self):
        api = self._api(['unrelated_perm'])
        resp = api.get(URL, {'p': 0.02, 'volume': 300})
        self.assertEqual(resp.status_code, 403)
