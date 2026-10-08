"""ASEC11-revue — « rendre le calendrier seulement » (décision fondateur).

Commercial et Technicien gardent la replanification de l'agenda
(``POST reporting/calendar/reschedule/``) ; rapports sauvegardés, config du
tableau de bord et alertes KPI restent réservés admin/responsable.

Run :
    python manage.py test apps.reporting.tests_asec11_revue_calendrier
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

URL_RESCHEDULE = '/api/django/reporting/calendar/reschedule/'


class CalendrierSeulementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='ASEC11 cal', slug='asec11-cal-co')
        call_command('init_roles', verbosity=0)
        cls.roles = {r.nom: r for r in Role.objects.filter(company=cls.company)}

    def _api(self, nom_role):
        user = User.objects.create_user(
            username=f'asec11c_{nom_role.replace(" ", "_").lower()}',
            password='x', company=self.company, role=self.roles[nom_role])
        api = APIClient()
        api.force_authenticate(user)
        return api

    def test_commercial_et_technicien_replanifient(self):
        # Type non éditable → 400 : la garde est passée (403 sinon).
        for nom_role in ('Commercial', 'Technicien'):
            with self.subTest(role=nom_role):
                resp = self._api(nom_role).post(
                    URL_RESCHEDULE,
                    {'type': 'maintenance', 'id': 1, 'date': '2026-10-08'},
                    format='json')
                self.assertEqual(resp.status_code, 400,
                                 getattr(resp, 'data', None))

    def test_viewer_et_commercial_terrain_refuses(self):
        for nom_role in ('Viewer', 'Commercial terrain'):
            with self.subTest(role=nom_role):
                resp = self._api(nom_role).post(
                    URL_RESCHEDULE,
                    {'type': 'activite', 'id': 1, 'date': '2026-10-08'},
                    format='json')
                self.assertEqual(resp.status_code, 403)

    def test_rapports_config_alertes_restent_admin_responsable(self):
        for nom_role in ('Commercial', 'Technicien'):
            api = self._api(nom_role)
            for url in ('/api/django/reporting/saved-reports/',
                        '/api/django/reporting/dashboard-config/',
                        '/api/django/reporting/kpi-alertes/'):
                with self.subTest(role=nom_role, url=url):
                    resp = api.post(url, {}, format='json')
                    self.assertEqual(resp.status_code, 403)
