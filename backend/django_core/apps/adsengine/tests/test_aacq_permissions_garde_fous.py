"""AACQ12 — Champs de garde-fous et règles autonomes à permission DISTINCTE.

Bascules ENG8 (armement) et règle ``mode='auto'`` hors simulation →
``adsengine_autonomy_toggle`` ; plafonds (quotidien, mensuel, variation hebdo)
→ ``adsengine_approve``. Sur les deux surfaces (``guardrail/`` et
``garde-fous/<id>/``) et sur ``regles/``. Un simple ``adsengine_manage`` garde
l'accès au reste (règle en proposition / simulation, autres champs).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import GuardrailConfig, RulePolicy

User = get_user_model()
BASE = '/api/django/adsengine'
MANAGE = ['adsengine_view', 'adsengine_manage']


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PermissionsGardeFousTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PGF', slug='aacq12-pgf')
        self.commercial = make_user(self.company, 'aacq12-com', MANAGE)
        self.approbateur = make_user(
            self.company, 'aacq12-appr', MANAGE + ['adsengine_approve'])
        self.admin = make_user(
            self.company, 'aacq12-admin',
            MANAGE + ['adsengine_approve', 'adsengine_autonomy_toggle'])
        self.cfg = GuardrailConfig.objects.create(company=self.company)

    def _etat_cfg(self):
        self.cfg.refresh_from_db()
        return (self.cfg.auto_rotate_creative,
                self.cfg.auto_rebalance_within_band,
                self.cfg.daily_budget_ceiling_mad,
                self.cfg.monthly_budget_ceiling_mad,
                self.cfg.weekly_change_pct_max)

    # ── garde-fous : bascules d'autonomie ─────────────────────────────────
    def test_bascules_refusees_sans_autonomy_toggle(self):
        for user in (self.commercial, self.approbateur):
            for url, body in (
                    (f'{BASE}/guardrail/', {'auto_rotate_creative': True}),
                    (f'{BASE}/garde-fous/{self.cfg.pk}/',
                     {'auto_rebalance_within_band': True})):
                with self.subTest(user=user.username, url=url):
                    avant = self._etat_cfg()
                    resp = auth(user).patch(url, body, format='json')
                    self.assertEqual(resp.status_code, 403, resp.data)
                    self.assertIn('autonomie', str(resp.data['detail']))
                    self.assertEqual(self._etat_cfg(), avant)
        self.cfg.refresh_from_db()
        self.assertFalse(services.capability_enabled(
            self.cfg, 'rotate_creative'))
        self.assertFalse(services.capability_enabled(
            self.cfg, 'rebalance_budget'))

    def test_plafonds_refuses_sans_approve(self):
        for url, body in (
                (f'{BASE}/guardrail/', {'max_daily_budget_mad': 5000}),
                (f'{BASE}/garde-fous/{self.cfg.pk}/',
                 {'monthly_budget_ceiling_mad': 999999}),
                (f'{BASE}/garde-fous/{self.cfg.pk}/',
                 {'weekly_change_pct_max': 100})):
            with self.subTest(url=url, body=body):
                avant = self._etat_cfg()
                resp = auth(self.commercial).patch(url, body, format='json')
                self.assertEqual(resp.status_code, 403, resp.data)
                self.assertIn('approbateur', str(resp.data['detail']))
                self.assertEqual(self._etat_cfg(), avant)

    def test_approbateur_plafonds_ok_bascules_403(self):
        resp = auth(self.approbateur).patch(
            f'{BASE}/garde-fous/{self.cfg.pk}/',
            {'monthly_budget_ceiling_mad': 9000, 'weekly_change_pct_max': 30},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = auth(self.approbateur).patch(
            f'{BASE}/guardrail/', {'max_daily_budget_mad': 400},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cfg.refresh_from_db()
        self.assertEqual(self.cfg.monthly_budget_ceiling_mad, 9000)
        self.assertEqual(self.cfg.daily_budget_ceiling_mad, 400)

    def test_admin_200_partout(self):
        resp = auth(self.admin).patch(f'{BASE}/guardrail/', {
            'auto_rotate_creative': True, 'max_daily_budget_mad': 5000},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = auth(self.admin).patch(f'{BASE}/garde-fous/{self.cfg.pk}/', {
            'auto_rebalance_within_band': True,
            'monthly_budget_ceiling_mad': 999999,
            'weekly_change_pct_max': 100}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._etat_cfg(), (True, True, 5000, 999999, 100))

    def test_commercial_garde_le_reste(self):
        # Le formulaire complet renvoyé à l'identique (plafonds inchangés) +
        # un champ libre modifié → 200.
        resp = auth(self.commercial).patch(f'{BASE}/guardrail/', {
            'max_daily_budget_mad': self.cfg.daily_budget_ceiling_mad,
            'auto_rotate_creative': False, 'pacing_band_pct': 25},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cfg.refresh_from_db()
        self.assertEqual(self.cfg.pacing_band_pct, 25)

    # ── règles ────────────────────────────────────────────────────────────
    def test_regle_auto_reelle_refusee_sans_autonomy_toggle(self):
        body = {'template_key': 'frequency_high', 'enabled': True,
                'mode': 'auto', 'dry_run': False}
        for user in (self.commercial, self.approbateur):
            with self.subTest(user=user.username):
                resp = auth(user).post(f'{BASE}/regles/', body, format='json')
                self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(RulePolicy.objects.filter(
            company=self.company).exists())

    def test_regle_put_vers_auto_refuse(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='frequency_high')
        resp = auth(self.commercial).put(f'{BASE}/regles/{rule.pk}/', {
            'template_key': 'frequency_high', 'enabled': True,
            'mode': 'auto', 'dry_run': False}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        rule.refresh_from_db()
        self.assertEqual(rule.mode, RulePolicy.Mode.PROPOSE)
        self.assertTrue(rule.dry_run)
        self.assertFalse(rule.enabled)

    def test_commercial_cree_regle_proposition_ou_simulation(self):
        resp = auth(self.commercial).post(f'{BASE}/regles/', {
            'template_key': 'frequency_high', 'enabled': True,
            'dry_run': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = auth(self.commercial).post(f'{BASE}/regles/', {
            'template_key': 'zero_delivery', 'enabled': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_admin_cree_regle_auto(self):
        resp = auth(self.admin).post(f'{BASE}/regles/', {
            'template_key': 'frequency_high', 'enabled': True,
            'mode': 'auto', 'dry_run': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
