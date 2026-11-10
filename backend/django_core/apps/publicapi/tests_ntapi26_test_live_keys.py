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

from .portees import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS
from .constants import ENV_TEST, ENV_LIVE
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

        listing = _key_client(raw_test_key).get('/api/public/v1/leads/')
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
            '/api/public/v1/leads-write/', {'nom': 'Nouveau lead sandbox'},
            format='json')
        self.assertEqual(create_resp.status_code, 201)
        # Jamais créé sous la société réelle.
        self.assertFalse(
            Lead.objects.filter(company=self.co, nom='Nouveau lead sandbox').exists())

    def test_live_key_never_reaches_sandbox(self):
        live_key, live_raw = ApiKey.issue(
            company=self.co, label='live', scopes=[SCOPE_READ_LEADS],
            environnement=ENV_LIVE)
        resp = _key_client(live_raw).post('/api/public/v1/sandbox/reset/')
        self.assertEqual(resp.status_code, 403)

    def test_emission_bornee_au_code_dedie_et_aux_portees_detenues(self):
        """APFS110 (C-APFS-040, D-APFS-1) — clés et webhooks exigent
        ``integrations_gerer`` en plus du palier, et n'émettent que les portées
        / évènements dont l'acteur porte le code ; compte hérité : repli."""
        from unittest import mock
        from django.core.management import call_command
        from apps.roles.models import Role
        call_command('init_roles', verbosity=0)
        roles = {r.nom: r for r in Role.objects.filter(company=self.co)}
        roles['integrateur'] = Role.objects.create(
            company=self.co, nom='Intégrateur APFS110',
            permissions=['users_voir', 'integrations_gerer', 'crm_voir'])
        cle = {'label': 'k', 'scopes': ['read:leads', 'read:factures', 'devis:write']}
        hook = {'label': 'h', 'target_url': 'https://example.test/hook',
                'events': ['facture.created', 'lead.created']}

        def appels(nom):
            user = User.objects.create_user(
                username=f'apfs110-{nom[:12].replace(" ", "-")}', password='x',
                company=self.co, role=roles[nom])
            api = _session_client(user)
            with mock.patch('apps.publicapi.serializers.validate_webhook_target_url',
                            side_effect=lambda u: u):
                return (api.post('/api/django/publicapi/keys/', cle, format='json'),
                        api.post('/api/django/publicapi/webhooks/', hook, format='json'))
        for nom in ('Admin RH', 'Admin Ventes', 'Technicien responsable', 'Commercial responsable'):
            with self.subTest(role=nom):
                self.assertEqual([r.status_code for r in appels(nom)], [403, 403])
        self.assertFalse(ApiKey.objects.filter(company=self.co).exists())
        k, h = appels('integrateur')
        self.assertEqual((k.status_code, h.status_code), (400, 400))
        self.assertIn('Portée non détenue : read:factures', k.data['scopes'])
        self.assertIn('Évènement non détenu : facture.created', h.data['events'])
        self.assertFalse(ApiKey.objects.filter(company=self.co).exists())
        self.assertEqual([r.status_code for r in appels('Directeur')], [201, 201])
        legacy = _session_client(self.admin)
        self.assertEqual(legacy.post('/api/django/publicapi/keys/', cle, format='json').status_code, 201)
