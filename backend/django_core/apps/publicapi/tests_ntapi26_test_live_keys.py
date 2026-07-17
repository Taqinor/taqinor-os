"""NTAPI26 — clés en mode `test` vs `live` (préfixe distinct, isolation).

Une clé `environnement='test'` porte le préfixe `tqk_test_`, est émise
DIRECTEMENT sur la société-jumelle sandbox (NTAPI27) et ne peut donc jamais
créer/lire de données réelles ; une clé `live` porte `tqk_live_` et n'a
aucun moyen d'atteindre le sandbox.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead

from .constants import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS, ENV_TEST, ENV_LIVE
from .models import ApiKey, SandboxTenant

User = get_user_model()


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def _session_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntapi26TestLiveKeysTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi26', 'NTAPI26')
        self.admin = User.objects.create_user(
            username='ntapi26-admin', password='x', company=self.co,
            role_legacy='admin')

    def test_live_key_default_prefix(self):
        key, raw = ApiKey.issue(
            company=self.co, label='v', scopes=[SCOPE_READ_LEADS])
        self.assertEqual(key.environnement, ENV_LIVE)
        self.assertTrue(raw.startswith('tqk_live_'))

    def test_test_key_prefix_and_creates_sandbox(self):
        api = _session_client(self.admin)
        resp = api.post('/api/django/publicapi/keys/', {
            'label': 'clé de test', 'scopes': [SCOPE_READ_LEADS, SCOPE_WRITE_LEADS],
            'environnement': ENV_TEST,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['key'].startswith('tqk_test_'))
        key = ApiKey.objects.get(pk=resp.data['id'])
        self.assertEqual(key.environnement, ENV_TEST)
        tenant = SandboxTenant.objects.get(company=self.co)
        # La clé test est émise SUR la société-jumelle, pas sur la société réelle.
        self.assertEqual(key.company_id, tenant.sandbox_company_id)
        self.assertNotEqual(key.company_id, self.co.id)

    def test_test_key_reads_only_sandbox_leads_never_real_data(self):
        Lead.objects.create(company=self.co, nom='Client réel')
        api = _session_client(self.admin)
        resp = api.post('/api/django/publicapi/keys/', {
            'label': 'clé de test', 'scopes': [SCOPE_READ_LEADS],
            'environnement': ENV_TEST,
        }, format='json')
        raw_test_key = resp.data['key']

        listing = _key_client(raw_test_key).get('/api/public/leads/')
        self.assertEqual(listing.status_code, 200)
        names = [row['nom'] for row in listing.data['results']]
        self.assertNotIn('Client réel', names)
        self.assertTrue(len(names) > 0)  # les leads de démo NTAPI27 sont là

    def test_test_key_can_create_lead_isolated_from_production(self):
        api = _session_client(self.admin)
        resp = api.post('/api/django/publicapi/keys/', {
            'label': 'clé de test écriture', 'scopes': [SCOPE_WRITE_LEADS],
            'environnement': ENV_TEST,
        }, format='json')
        raw_test_key = resp.data['key']

        create_resp = _key_client(raw_test_key).post(
            '/api/public/leads-write/', {'nom': 'Nouveau lead sandbox'},
            format='json')
        self.assertEqual(create_resp.status_code, 201)
        # Jamais créé sous la société réelle.
        self.assertFalse(
            Lead.objects.filter(company=self.co, nom='Nouveau lead sandbox').exists())

    def test_live_key_never_reaches_sandbox(self):
        live_key, live_raw = ApiKey.issue(
            company=self.co, label='live', scopes=[SCOPE_READ_LEADS],
            environnement=ENV_LIVE)
        resp = _key_client(live_raw).post('/api/public/sandbox/reset/')
        self.assertEqual(resp.status_code, 403)
