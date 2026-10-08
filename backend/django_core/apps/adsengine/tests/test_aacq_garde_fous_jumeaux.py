"""AACQ13 — Les deux surfaces des garde-fous valident À L'IDENTIQUE.

``guardrail/`` (singleton, alias d'écran) délègue désormais à
``GuardrailConfigSerializer`` comme ``garde-fous/<id>/`` : une saisie invalide
renvoie 400 (jamais 500) sur les DEUX surfaces, la chaîne ``'false'`` est
stockée False, et la configuration relue est inchangée après un refus.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import GuardrailConfig

User = get_user_model()
BASE = '/api/django/adsengine'

INVALIDES = [
    ('daily_budget_ceiling_mad', 'max_daily_budget_mad', 'inf'),
    ('daily_budget_ceiling_mad', 'max_daily_budget_mad', -5),
    ('daily_budget_ceiling_mad', 'max_daily_budget_mad', 10 ** 12),
    ('weekly_change_pct_max', 'weekly_change_pct_max', -1),
]


class GardeFousJumeauxTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='GF', slug='aacq13-gf')
        role = Role.objects.create(
            company=self.company, nom='aacq13-role',
            # AACQ12 — changer un plafond est réservé à adsengine_approve.
            permissions=['adsengine_view', 'adsengine_manage',
                         'adsengine_approve'])
        self.user = User.objects.create_user(
            username='aacq13-admin', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.cfg = GuardrailConfig.objects.create(company=self.company)

    def _surfaces(self, model_field, screen_field, value):
        return [
            ('guardrail/', f'{BASE}/guardrail/', {screen_field: value}),
            ('garde-fous/', f'{BASE}/garde-fous/{self.cfg.pk}/',
             {model_field: value}),
        ]

    def _etat(self):
        self.cfg.refresh_from_db()
        return (self.cfg.daily_budget_ceiling_mad,
                self.cfg.weekly_change_pct_max,
                self.cfg.auto_rotate_creative)

    def test_saisies_invalides_400_sur_les_deux_surfaces(self):
        for model_field, screen_field, value in INVALIDES:
            for nom, url, body in self._surfaces(
                    model_field, screen_field, value):
                with self.subTest(surface=nom, champ=model_field, valeur=value):
                    avant = self._etat()
                    resp = self.api.patch(url, body, format='json')
                    self.assertEqual(resp.status_code, 400, resp.data)
                    self.assertEqual(self._etat(), avant)

    def test_chaine_false_stockee_false_sur_les_deux_surfaces(self):
        for nom, url, body in self._surfaces(
                'auto_rotate_creative', 'auto_rotate_creative', 'false'):
            with self.subTest(surface=nom):
                GuardrailConfig.objects.filter(pk=self.cfg.pk).update(
                    auto_rotate_creative=True)
                resp = self.api.patch(url, body, format='json')
                self.assertEqual(resp.status_code, 200, resp.data)
                self.cfg.refresh_from_db()
                self.assertFalse(self.cfg.auto_rotate_creative)

    def test_saisie_valide_200_sur_les_deux_surfaces(self):
        for nom, url, body in self._surfaces(
                'daily_budget_ceiling_mad', 'max_daily_budget_mad', 150):
            with self.subTest(surface=nom):
                resp = self.api.patch(url, body, format='json')
                self.assertEqual(resp.status_code, 200, resp.data)
                self.cfg.refresh_from_db()
                self.assertEqual(self.cfg.daily_budget_ceiling_mad, 150)

    def test_singleton_erreur_sous_le_nom_d_ecran(self):
        resp = self.api.patch(f'{BASE}/guardrail/',
                              {'max_daily_budget_mad': -5}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('max_daily_budget_mad', resp.data)
