"""ARC40 — endpoint KPI fédéré piloté par le registre plateforme.

Couvre : (1) un provider déclaré par manifeste apparaît SANS toucher
apps/reporting ; (2) un superuser sans société reçoit une liste vide. Le
scope société et le gatage ``ModuleToggle`` sur un VRAI provider déclaré
(calepinage) sont couverts dans ``tests_cal218_kpis.py`` — pas dupliqués ici.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/reports/kpi-federes/'


def fake_kpi_provider(company):
    """Provider fictif pour le test « déclaré ⇒ apparaît sans toucher
    reporting » (référencé en dotted par un manifeste simulé)."""
    return [{'id': 'fake_arc40', 'label': 'Tuile fictive ARC40', 'valeur': 42}]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KpiFederesTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='arc40-kpi', defaults={'nom': 'ARC40 KPI Co'})[0]
        self.other = Company.objects.create(slug='arc40-other', nom='Autre')
        self.user = User.objects.create_user(
            username='arc40_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def _tiles_by_id(self, resp):
        return {t['id']: t for t in resp.data['tuiles']}


class TestRegistryDriven(KpiFederesTestCase):
    def test_declared_provider_appears_without_touching_reporting(self):
        """Un provider déclaré par un manifeste fictif (dotted vers une
        fonction de CE module de test) apparaît dans l'endpoint fédéré sans
        aucune modification d'apps/reporting."""
        from core import platform as core_platform

        vrais = core_platform.collect_platform_manifests()
        faux = dict(vrais)
        faux['module_fictif_arc40'] = {
            'module': 'module_fictif_arc40',
            'kpi_providers': [
                'apps.reporting.tests_kpi_federes.fake_kpi_provider'],
            'record_targets': [], 'searchable_models': [],
            'customfield_models': [], 'import_specs': [],
            'agent_actions_module': '', 'automation_state_fields': [],
        }

        with mock.patch(
                'core.platform.collect_platform_manifests',
                side_effect=lambda: faux):
            resp = self.api.get(URL)
        tuiles = self._tiles_by_id(resp)
        self.assertIn('fake_arc40', tuiles)
        self.assertEqual(tuiles['fake_arc40']['valeur'], 42)

    def test_superuser_without_company_gets_empty_list(self):
        su = User.objects.create_superuser(
            username='arc40_su', password='x', email='arc40su@example.com')
        resp = auth(su).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['tuiles'], [])
