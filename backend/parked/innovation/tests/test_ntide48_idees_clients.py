"""Tests de la « boîte à idées publique » (NTIDE48, gated).

Couvre : ``InnovationSettings.idees_clients_actif`` (toggle OFF par défaut,
audité), ``Idee.client_id`` (opaque, nullable), et le masquage des idées
client aux équipes (visibles seulement au palier admin)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import Idee, InnovationSettings

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class InnovationSettingsToggleTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide48-a', 'A')

    def test_off_by_default(self):
        settings, _ = InnovationSettings.objects.get_or_create(company=self.co_a)
        self.assertFalse(settings.idees_clients_actif)

    def test_settings_endpoint_exposes_toggle(self):
        admin = make_user(self.co_a, 'ntide48-admin', role_legacy='admin')
        resp = auth(admin).patch(
            '/api/django/innovation/parametres/',
            {'idees_clients_actif': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['idees_clients_actif'])
        settings = InnovationSettings.objects.get(company=self.co_a)
        self.assertTrue(settings.idees_clients_actif)

    def test_settings_change_audited(self):
        from apps.parametres.models_audit import SettingsAuditLog

        admin = make_user(self.co_a, 'ntide48-audit-admin', role_legacy='admin')
        auth(admin).patch(
            '/api/django/innovation/parametres/',
            {'idees_clients_actif': True}, format='json')
        self.assertTrue(
            SettingsAuditLog.objects.filter(
                company=self.co_a, section='innovation',
                field='idees_clients_actif').exists())


class ClientIdeeMaskingTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide48-mask-a', 'A')
        self.admin = make_user(self.co_a, 'ntide48-mask-admin', role_legacy='admin')
        self.normal = make_user(self.co_a, 'ntide48-mask-normal')
        self.idee_client = Idee.objects.create(
            company=self.co_a, titre='Idée client', client_id=42)
        self.idee_interne = Idee.objects.create(
            company=self.co_a, titre='Idée interne')

    def test_client_id_null_by_default(self):
        self.assertIsNone(self.idee_interne.client_id)

    def test_normal_user_does_not_see_client_idee_in_list(self):
        resp = auth(self.normal).get(self.BASE)
        titres = [r['titre'] for r in rows(resp)]
        self.assertNotIn('Idée client', titres)
        self.assertIn('Idée interne', titres)

    def test_normal_user_gets_404_on_client_idee_detail(self):
        resp = auth(self.normal).get(f'{self.BASE}{self.idee_client.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_admin_sees_client_idee_in_list(self):
        resp = auth(self.admin).get(self.BASE)
        titres = [r['titre'] for r in rows(resp)]
        self.assertIn('Idée client', titres)

    def test_admin_can_view_client_idee_detail(self):
        resp = auth(self.admin).get(f'{self.BASE}{self.idee_client.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['client_id'], 42)

    def test_client_id_not_patchable(self):
        resp = auth(self.admin).patch(
            f'{self.BASE}{self.idee_interne.id}/',
            {'client_id': 99}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.idee_interne.refresh_from_db()
        self.assertIsNone(self.idee_interne.client_id)

    def test_client_idee_excluded_from_dedup_suggestions(self):
        results = selectors.idees_similaires(self.co_a, 'Idée')
        titres = [r['titre'] for r in results]
        self.assertNotIn('Idée client', titres)
        self.assertIn('Idée interne', titres)
