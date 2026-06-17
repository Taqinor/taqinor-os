"""N84 — calendrier / agenda (multi-tenant, agrégation + replanification)."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from authentication.models import Company

User = get_user_model()


class TestCalendar(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cal-co', defaults={'nom': 'Cal Co'})[0]
        self.other = Company.objects.create(slug='cal-other', nom='Autre')
        self.user = User.objects.create_user(
            username='cal_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _chantier(self, **kw):
        return Installation.objects.create(
            company=self.company, reference=kw.pop('reference', 'CH-1'),
            client=self.client_obj, **kw)

    def test_pose_event_in_window_and_scoped(self):
        soon = date.today() + timedelta(days=5)
        self._chantier(reference='CH-POSE', date_pose_prevue=soon)
        # Chantier d'une autre société : ne doit pas apparaître.
        Installation.objects.create(
            company=self.other, reference='CH-X',
            client=Client.objects.create(company=self.other, nom='B'),
            date_pose_prevue=soon)
        resp = self.api.get('/api/django/reporting/calendar/')
        self.assertEqual(resp.status_code, 200)
        poses = [e for e in resp.data['events'] if e['type'] == 'pose']
        self.assertEqual(len(poses), 1)
        self.assertEqual(poses[0]['link_id'], self._only_pk('CH-POSE'))
        self.assertTrue(poses[0]['editable'])

    def _only_pk(self, ref):
        return Installation.objects.get(company=self.company,
                                        reference=ref).pk

    def test_type_filter_excludes_others(self):
        soon = date.today() + timedelta(days=3)
        self._chantier(reference='CH-MES', date_mise_en_service=soon)
        self._chantier(reference='CH-P', date_pose_prevue=soon)
        resp = self.api.get('/api/django/reporting/calendar/?types=pose')
        self.assertEqual(resp.status_code, 200)
        types = {e['type'] for e in resp.data['events']}
        self.assertEqual(types, {'pose'})

    def test_reschedule_pose_updates_date(self):
        soon = date.today() + timedelta(days=5)
        inst = self._chantier(reference='CH-R', date_pose_prevue=soon)
        new = (date.today() + timedelta(days=12)).isoformat()
        resp = self.api.post(
            '/api/django/reporting/calendar/reschedule/',
            {'type': 'pose', 'id': inst.pk, 'date': new}, format='json')
        self.assertEqual(resp.status_code, 200)
        inst.refresh_from_db()
        self.assertEqual(inst.date_pose_prevue.isoformat(), new)

    def test_reschedule_rejects_computed_type(self):
        resp = self.api.post(
            '/api/django/reporting/calendar/reschedule/',
            {'type': 'visite_maintenance', 'id': 1,
             'date': date.today().isoformat()}, format='json')
        self.assertEqual(resp.status_code, 400)
