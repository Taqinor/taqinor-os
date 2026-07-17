"""NTAPI7 — plans d'API nommés (gratuit/pro/entreprise) + admin endpoint.

`GET/PATCH /api/django/publicapi/plan/` : société TOUJOURS forcée depuis
`request.user.company` (jamais du corps) ; changer le palier d'UNE société ne
modifie jamais les limites d'une AUTRE (aucune fuite inter-société).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ApiUsagePlan

User = get_user_model()


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def _session_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntapi7UsagePlanTests(TestCase):
    def setUp(self):
        self.co_a = _company('ntapi7-a', 'NTAPI7 A')
        self.co_b = _company('ntapi7-b', 'NTAPI7 B')
        self.admin_a = _admin(self.co_a, 'admin-a-ntapi7')
        self.admin_b = _admin(self.co_b, 'admin-b-ntapi7')

    def test_get_creates_default_free_plan(self):
        self.assertFalse(ApiUsagePlan.objects.filter(company=self.co_a).exists())
        resp = _session_client(self.admin_a).get('/api/django/publicapi/plan/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['code'], ApiUsagePlan.Palier.GRATUIT)
        self.assertTrue(ApiUsagePlan.objects.filter(company=self.co_a).exists())

    def test_patch_updates_named_plan_and_quotas(self):
        client = _session_client(self.admin_a)
        resp = client.patch(
            '/api/django/publicapi/plan/',
            {'code': 'entreprise', 'quota_par_mois': 5_000_000,
             'quota_burst': 200, 'nb_webhooks_max': 25}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['code'], 'entreprise')
        self.assertEqual(resp.data['quota_par_mois'], 5_000_000)
        plan = ApiUsagePlan.objects.get(company=self.co_a)
        self.assertEqual(plan.code, 'entreprise')
        self.assertEqual(plan.quota_burst, 200)
        self.assertEqual(plan.nb_webhooks_max, 25)

    def test_patch_never_leaks_across_tenants(self):
        # Société B change son plan ; la société A garde ses défauts.
        _session_client(self.admin_b).patch(
            '/api/django/publicapi/plan/',
            {'code': 'pro', 'quota_par_mois': 999}, format='json')
        resp_a = _session_client(self.admin_a).get('/api/django/publicapi/plan/')
        self.assertEqual(resp_a.data['code'], ApiUsagePlan.Palier.GRATUIT)
        self.assertNotEqual(resp_a.data['quota_par_mois'], 999)
        plan_b = ApiUsagePlan.objects.get(company=self.co_b)
        self.assertEqual(plan_b.code, 'pro')

    def test_company_field_not_writable_from_body(self):
        # Une tentative de forcer `company` depuis le corps est ignorée (le
        # champ n'existe même pas dans le serializer) — la société reste
        # celle de l'utilisateur connecté.
        resp = _session_client(self.admin_a).patch(
            '/api/django/publicapi/plan/',
            {'company': self.co_b.id, 'code': 'pro'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ApiUsagePlan.objects.filter(
            company=self.co_a, code='pro').exists())
        self.assertFalse(ApiUsagePlan.objects.filter(
            company=self.co_b, code='pro').exists())

    def test_requires_admin_tier(self):
        limited = User.objects.create_user(
            username='limited-ntapi7', password='x', company=self.co_a,
            role_legacy='normal')
        resp = _session_client(limited).get('/api/django/publicapi/plan/')
        self.assertEqual(resp.status_code, 403)

    def test_get_includes_consumed_usage_ntapi22(self):
        # NTAPI22 — le portail développeur affiche le « quota consommé » :
        # additif au contrat existant, jamais de fuite inter-société.
        resp = _session_client(self.admin_a).get('/api/django/publicapi/plan/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('usage_jour', resp.data)
        self.assertIn('usage_mois', resp.data)
        self.assertEqual(resp.data['usage_jour'], 0)
        self.assertEqual(resp.data['usage_mois'], 0)
