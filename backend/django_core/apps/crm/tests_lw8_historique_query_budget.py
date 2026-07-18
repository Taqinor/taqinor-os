"""LW8 — budget de requêtes sur GET /api/django/crm/leads/<id>/historique/.

Avant fix : ``lead.activites.all()`` sans ``select_related('user',
'attachment')`` — ``LeadActivitySerializer.get_user_nom``/``get_attachment_*``
retouchent chacune une FK PAR LIGNE (N+1 réel, recon 02 §5). Ce test peuple
plusieurs activités avec des utilisateurs ET des pièces jointes distincts et
vérifie que le nombre de requêtes reste borné, quel que soit le nombre
d'activités — casser volontairement le ``select_related`` de
``LeadViewSet.historique`` (apps/crm/views.py) fait échouer ce test."""
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


class HistoriqueQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='LW8 SARL')
        self.owner = User.objects.create_user(
            username='lw8_owner', password='x', role_legacy='admin',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='LW8 Lead', owner=self.owner)
        self.api = _api(self.owner)

    def _seed_activites(self, count, start=0):
        ct = ContentType.objects.get_for_model(Lead)
        for i in range(start, start + count):
            author = User.objects.create_user(
                username=f'lw8_user_{i}', password='x',
                role_legacy='utilisateur', company=self.company)
            attachment = Attachment.objects.create(
                company=self.company, content_type=ct, object_id=self.lead.id,
                filename=f'note_{i}.jpg', uploaded_by=author,
            )
            LeadActivity.objects.create(
                company=self.company, lead=self.lead, user=author,
                kind=LeadActivity.Kind.NOTE, body=f'Note {i}',
                attachment=attachment,
            )

    def test_query_count_does_not_grow_with_activity_count(self):
        url = f'/api/django/crm/leads/{self.lead.id}/historique/'
        self._seed_activites(3)
        with CaptureQueriesContext(connection) as ctx_3:
            resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        count_at_3 = len(ctx_3.captured_queries)

        self._seed_activites(8, start=3)  # total 11
        with CaptureQueriesContext(connection) as ctx_11:
            resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        count_at_11 = len(ctx_11.captured_queries)

        self.assertEqual(
            count_at_3, count_at_11,
            'Le nombre de requêtes a grandi avec le nombre d\'activités '
            '(N+1) — vérifier select_related(\'user\',\'attachment\') sur '
            'LeadViewSet.historique.')

    def test_query_count_stays_within_fixed_budget(self):
        """Plafond absolu (≤4) — attrape aussi un N+1 dès la 1ère ligne."""
        self._seed_activites(6)
        url = f'/api/django/crm/leads/{self.lead.id}/historique/'
        with self.assertMaxQueries(4):
            resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 6)
