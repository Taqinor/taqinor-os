"""ASEC44 — le plan de quotas d'API est en lecture seule pour l'admin du
tenant (seule la plateforme le modifie), et le schéma OpenAPI public est
throttlé par IP.

Constats C-ASEC-013 (volet quotas) et C-ASEC-024 (volet OpenAPI).
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ApiUsagePlan

User = get_user_model()
URL_PLAN = '/api/django/publicapi/plan/'
URL_OPENAPI = '/api/public/v1/openapi.json'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class QuotasEtOpenApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ASEC44 Q', slug='asec44-q')
        self.directeur = User.objects.create_user(
            username='asec44q_admin', password='x', company=self.company,
            role_legacy='admin')
        self.plateforme = User.objects.create_user(
            username='asec44q_staff', password='x', company=self.company,
            role_legacy='admin', is_superuser=True, is_staff=True)

    def tearDown(self):
        # Le seau de throttle vit dans le cache local du worker : le vider
        # pour ne pas faire tomber en 429 un test suivant du même process.
        cache.clear()

    def test_quotas_lecture_seule_tenant(self):
        r = _api(self.directeur).get(URL_PLAN)
        self.assertEqual(r.status_code, 200, r.content)
        plan = ApiUsagePlan.objects.get(company=self.company)
        avant = (plan.code, plan.quota_par_mois)
        r2 = _api(self.directeur).patch(
            URL_PLAN, {'code': 'entreprise', 'quota_par_mois': 5_000_000},
            format='json')
        self.assertEqual(r2.status_code, 403, r2.content)
        plan.refresh_from_db()
        self.assertEqual((plan.code, plan.quota_par_mois), avant)
        r3 = _api(self.plateforme).patch(
            URL_PLAN, {'code': 'pro'}, format='json')
        self.assertEqual(r3.status_code, 200, r3.content)
        plan.refresh_from_db()
        self.assertEqual(plan.code, 'pro')

    def test_openapi_public_throttle(self):
        client = APIClient()
        statuts = [client.get(URL_OPENAPI).status_code for _ in range(40)]
        self.assertEqual(statuts[0], 200)
        self.assertIn(429, statuts)
