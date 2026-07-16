"""NTDMO13 — endpoint checklist « Premiers pas » + action ignorer."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.onboarding.models import OnboardingChecklistItem
from apps.onboarding.services import marquer_item_complete

User = get_user_model()


class OnboardingProgressEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co', slug='co-pe')
        self.u1 = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.u2 = User.objects.create_user(
            'u2', password='x', company=self.company)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_list_returns_checklist_with_summary(self):
        resp = self._client(self.u1).get('/api/django/onboarding/progress/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('items', resp.data)
        self.assertIn('pourcentage', resp.data)
        self.assertGreater(resp.data['total'], 0)

    def test_progress_differs_per_user(self):
        marquer_item_complete(self.company, self.u1, 'import_clients')
        r1 = self._client(self.u1).get('/api/django/onboarding/progress/')
        r2 = self._client(self.u2).get('/api/django/onboarding/progress/')
        self.assertGreater(r1.data['faits'], r2.data['faits'])

    def test_progress_persists_across_sessions(self):
        marquer_item_complete(self.company, self.u1, 'import_clients')
        # « reconnexion » = nouveau client authentifié.
        r = self._client(self.u1).get('/api/django/onboarding/progress/')
        done = [it for it in r.data['items']
                if it['key'] == 'import_clients']
        self.assertTrue(done and done[0]['fait'])

    def test_ignorer_hides_item_persistently(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        c = self._client(self.u1)
        c.post(f'/api/django/onboarding/progress/{item.id}/ignorer/')
        r = c.get('/api/django/onboarding/progress/')
        keys = {it['key'] for it in r.data['items']}
        self.assertNotIn('import_clients', keys)

    def test_ignorer_tout_marks_termine(self):
        c = self._client(self.u1)
        c.post('/api/django/onboarding/progress/ignorer-tout/')
        r = c.get('/api/django/onboarding/progress/')
        self.assertTrue(r.data['termine'])
