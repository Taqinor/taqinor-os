"""VX208 — taxonomie de sévérité/catégorie + dédoublonnage/compteurs/undo.

Couvre : (a) `severity.py` classe `INCIDENT_CRITICAL` au-dessus de `DIGEST` ;
(b) `DIGEST` ne compte jamais dans le compteur ACTIONS de `unread-count` ;
(c) `read-all` renvoie les ids marqués (undo exact via `mark_unread`)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from . import severity
from .models import EventType, Notification

User = get_user_model()


class SeverityTaxonomyUnitTests(TestCase):
    """Tests unitaires purs sur `severity.py` (aucune DB)."""

    def test_incident_critical_ranks_above_digest(self):
        self.assertLess(
            severity.severity_rank(EventType.INCIDENT_CRITICAL),
            severity.severity_rank(EventType.DIGEST))

    def test_digest_is_never_an_action(self):
        self.assertFalse(severity.is_action(EventType.DIGEST))

    def test_unknown_event_type_falls_back_safely(self):
        # Un type non répertorié (futur EventType) ne casse jamais.
        self.assertEqual(severity.severity_of('__unknown__'), severity.NORMAL)
        self.assertEqual(severity.category_of('__unknown__'), 'general')
        self.assertFalse(severity.is_action('__unknown__'))


class AttentionCountersTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='VX208 Co')
        self.user = User.objects.create_user(
            username='vx208_user', password='pw', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_digest_never_inflates_actions_counter(self):
        Notification.objects.create(
            company=self.company, recipient=self.user,
            event_type=EventType.DIGEST, title='Récap du jour')
        Notification.objects.create(
            company=self.company, recipient=self.user,
            event_type=EventType.LEAD_ASSIGNED, title='Nouveau lead')

        resp = self.api.get('/api/django/notifications/notifications/unread-count/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['unread'], 2)
        self.assertEqual(resp.data['actions'], 1)
        self.assertEqual(resp.data['infos'], 1)

    def test_serializer_exposes_severity_category_is_action(self):
        Notification.objects.create(
            company=self.company, recipient=self.user,
            event_type=EventType.INCIDENT_CRITICAL, title='Incident')
        resp = self.api.get('/api/django/notifications/notifications/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        item = results[0]
        self.assertEqual(item['severity'], 'critique')
        self.assertEqual(item['category'], 'qhse')
        self.assertTrue(item['is_action'])

    def test_read_all_returns_exact_ids_for_undo(self):
        n1 = Notification.objects.create(
            company=self.company, recipient=self.user,
            event_type=EventType.LEAD_ASSIGNED, title='A')
        n2 = Notification.objects.create(
            company=self.company, recipient=self.user,
            event_type=EventType.LEAD_ASSIGNED, title='B')

        resp = self.api.post('/api/django/notifications/notifications/read-all/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['updated'], 2)
        self.assertCountEqual(resp.data['ids'], [n1.id, n2.id])

        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertTrue(n1.read)
        self.assertTrue(n2.read)

        # Undo exact via mark_unread pour CHAQUE id renvoyé (jamais un
        # "tout non-lu" qui déborderait sur d'autres notifs).
        for nid in resp.data['ids']:
            r = self.api.post(f'/api/django/notifications/notifications/{nid}/unread/')
            self.assertEqual(r.status_code, 200, r.content)
        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertFalse(n1.read)
        self.assertFalse(n2.read)
