"""LW30 — ``chatter_recent`` embarqué sur le GET détail (RETRIEVE uniquement).

Les 50 dernières ``LeadActivity`` (select_related user/attachment, tri
épingle-d'abord LW28) sont embarquées dans la réponse ``GET
/leads/<id>/`` — jamais dans ``GET /leads/`` (payload de liste). Le budget de
requêtes ne doit PAS grandir avec le nombre d'activités (même garde N+1 que
LW8, recon 02 §5)."""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.records.models import Attachment
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LeadDetailChatterRecentTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='LW30 SARL')
        self.owner = User.objects.create_user(
            username='lw30_owner', password='x', role_legacy='admin',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='LW30 Lead', owner=self.owner)
        self.api = _api(self.owner)

    def _detail_url(self):
        return f'/api/django/crm/leads/{self.lead.id}/'

    def _seed_activites(self, count, start=0):
        ct = ContentType.objects.get_for_model(Lead)
        for i in range(start, start + count):
            author = User.objects.create_user(
                username=f'lw30_user_{i}', password='x',
                role_legacy='utilisateur', company=self.company)
            attachment = Attachment.objects.create(
                company=self.company, content_type=ct, object_id=self.lead.id,
                filename=f'note_{i}.jpg', uploaded_by=author)
            LeadActivity.objects.create(
                company=self.company, lead=self.lead, user=author,
                kind=LeadActivity.Kind.NOTE, body=f'Note {i}',
                attachment=attachment)

    # ── Présent sur RETRIEVE, borné à 50, épingle-d'abord ────────────────────

    def test_chatter_recent_present_on_retrieve(self):
        self._seed_activites(3)
        resp = self.api.get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('chatter_recent', resp.data)
        self.assertEqual(len(resp.data['chatter_recent']), 3)

    def test_chatter_recent_capped_at_50(self):
        self._seed_activites(55)
        resp = self.api.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['chatter_recent']), 50)

    def test_chatter_recent_pinned_first(self):
        self._seed_activites(3)
        oldest = LeadActivity.objects.filter(lead=self.lead).order_by(
            'created_at').first()
        pin_url = (f'/api/django/crm/leads/{self.lead.id}/activites/'
                   f'{oldest.id}/epingler/')
        pin_resp = self.api.post(pin_url)
        self.assertEqual(pin_resp.status_code, 200, pin_resp.data)

        resp = self.api.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['chatter_recent']
        self.assertEqual(rows[0]['id'], oldest.id)
        self.assertTrue(rows[0]['pinned'])

    # ── Absent sur list() ────────────────────────────────────────────────────

    def test_chatter_recent_absent_from_list(self):
        self._seed_activites(2)
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            self.assertNotIn('chatter_recent', row)

    # ── Budget de requêtes borné (pas de N+1) ────────────────────────────────

    def test_query_count_does_not_grow_with_activity_count(self):
        self._seed_activites(3)
        with CaptureQueriesContext(connection) as ctx_3:
            resp = self.api.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)
        count_at_3 = len(ctx_3.captured_queries)

        self._seed_activites(12, start=3)  # total 15
        with CaptureQueriesContext(connection) as ctx_15:
            resp = self.api.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)
        count_at_15 = len(ctx_15.captured_queries)

        self.assertEqual(
            count_at_3, count_at_15,
            'Le nombre de requêtes a grandi avec le nombre d\'activités '
            '(N+1) — vérifier select_related(\'user\',\'attachment\') sur '
            'LeadSerializer.get_chatter_recent.')

    def test_query_count_stays_within_fixed_budget(self):
        """Plafond absolu généreux (comportement RETRIEVE existant déjà
        chargé : owner/client/devis + next_activity + stage_since_days +
        chatter_recent) — attrape un N+1 dès la 1ère ligne d'activité."""
        self._seed_activites(10)
        with self.assertMaxQueries(15):
            resp = self.api.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)
