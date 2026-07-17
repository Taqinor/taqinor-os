"""NTAPI27 — bac à sable API avec données de démo.

`seed_api_sandbox` (idempotent, additif) et `POST /api/public/sandbox/reset/`
(clé `test` seule) : une clé test lit des leads de démo, en crée un, puis un
reset restaure l'état initial.
"""
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

from .constants import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS, ENV_TEST
from .models import ApiKey, SandboxTenant
from .services import get_or_create_sandbox, reset_sandbox, DEMO_LEADS


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi27SandboxTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi27', 'NTAPI27')

    def test_get_or_create_sandbox_seeds_demo_leads(self):
        tenant = get_or_create_sandbox(self.co)
        count = Lead.objects.filter(company=tenant.sandbox_company).count()
        self.assertEqual(count, len(DEMO_LEADS))

    def test_seed_is_idempotent(self):
        tenant = get_or_create_sandbox(self.co)
        tenant_again = get_or_create_sandbox(self.co)
        self.assertEqual(tenant.id, tenant_again.id)
        count = Lead.objects.filter(company=tenant.sandbox_company).count()
        self.assertEqual(count, len(DEMO_LEADS))

    def test_management_command_is_idempotent_and_additive(self):
        call_command('seed_api_sandbox', '--company', self.co.id)
        tenant = SandboxTenant.objects.get(company=self.co)
        first_count = Lead.objects.filter(company=tenant.sandbox_company).count()
        call_command('seed_api_sandbox', '--company', self.co.id)
        second_count = Lead.objects.filter(company=tenant.sandbox_company).count()
        self.assertEqual(first_count, second_count)
        self.assertEqual(first_count, len(DEMO_LEADS))

    def test_reset_deletes_extra_and_restores_initial_state(self):
        tenant = get_or_create_sandbox(self.co)
        Lead.objects.create(
            company=tenant.sandbox_company, nom='Lead créé pendant le test')
        self.assertEqual(
            Lead.objects.filter(company=tenant.sandbox_company).count(),
            len(DEMO_LEADS) + 1)

        reset_sandbox(tenant)

        remaining = Lead.objects.filter(company=tenant.sandbox_company)
        self.assertEqual(remaining.count(), len(DEMO_LEADS))
        self.assertFalse(
            remaining.filter(nom='Lead créé pendant le test').exists())

    def test_end_to_end_test_key_reads_creates_and_resets(self):
        key, raw = ApiKey.issue(
            company=self.co, label='sandbox key',
            scopes=[SCOPE_READ_LEADS, SCOPE_WRITE_LEADS],
            environnement=ENV_TEST)
        # ApiKey.issue seul ne crée pas le sandbox (c'est la vue de création
        # NTAPI22/26 qui le fait) — on le crée explicitement ici, exactement
        # comme le ferait `ApiKeyViewSet.create`.
        tenant = get_or_create_sandbox(self.co)
        key.company = tenant.sandbox_company
        key.save(update_fields=['company'])

        client = _key_client(raw)

        # 1) Lit des leads de démo.
        listing = client.get('/api/public/leads/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data['results']), len(DEMO_LEADS))

        # 2) En crée un.
        create_resp = client.post(
            '/api/public/leads-write/', {'nom': 'Lead créé par la clé test'},
            format='json')
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(
            Lead.objects.filter(company=tenant.sandbox_company).count(),
            len(DEMO_LEADS) + 1)

        # 3) Reset restaure l'état initial.
        reset_resp = client.post('/api/public/sandbox/reset/')
        self.assertEqual(reset_resp.status_code, 200)
        self.assertEqual(
            Lead.objects.filter(company=tenant.sandbox_company).count(),
            len(DEMO_LEADS))
