"""YOPSB13 — budget de requêtes sur GET /api/django/crm/leads/ (liste).

Couvre : le nombre de requêtes SQL exécutées par la liste des leads ne doit
PAS grandir avec le nombre de lignes (O(1), pas O(n)) — peuple 10 puis 25
leads (avec owner + client + devis liés, exactement ce que LeadSerializer
touche via owner_nom/owner_poste/owner_avatar/client_nom/devis) et vérifie
que le compte de requêtes ne bouge pas. Casser volontairement le
select_related/prefetch_related de LeadViewSet (apps/crm/views.py) fait
échouer ce test — c'est le contrat de la garde N+1 (YOPSB13)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
LEADS_URL = '/api/django/crm/leads/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LeadListQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Budget SARL')
        self.owner = User.objects.create_user(
            username='budget_owner', password='x', role_legacy='admin',
            company=self.company)
        self.api = _api(self.owner)
        # Pré-chauffe le cache ContentType : LeadViewSet.list() appelle
        # ContentType.objects.get_for_model(Lead) (next_activity_map), mis en
        # cache PROCESS-WIDE au 1er appel. Sans ça, le tout premier GET-avec-
        # leads porte cette requête unique (11) alors que le 2e ne l'a plus
        # (10), simulant une croissance. On mesure ainsi le régime permanent
        # (la vraie garde N+1), pas ce coût de cache unique.
        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.get_for_model(Lead)

    def _seed_leads(self, count, start=0):
        for i in range(start, start + count):
            client = Client.objects.create(
                company=self.company, nom=f'Client{i}', prenom='Test')
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead{i}', owner=self.owner,
                client=client)
            # get_devis() itère obj.devis.order_by(...) — au moins un devis
            # par lead pour exercer réellement le prefetch_related('devis').
            # `start` décale la référence : le 2e appel (croissance 10→25) ne
            # doit PAS réutiliser BUDGET-0000..0009 (collision unique company+ref).
            from apps.ventes.models import Devis
            Devis.objects.create(
                company=self.company, lead=lead, client=client,
                created_by=self.owner, reference=f'BUDGET-{i:04d}')

    def test_query_count_does_not_grow_with_row_count(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._seed_leads(10)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(LEADS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_10 = len(ctx_10.captured_queries)

        self._seed_leads(15, start=10)  # total 25
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(LEADS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_25 = len(ctx_25.captured_queries)

        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes '
            '(N+1) — vérifier select_related/prefetch_related sur '
            'LeadViewSet.queryset (owner, client, devis).')

    def test_query_count_stays_within_fixed_budget(self):
        """Plafond absolu (pas seulement « ne grandit pas ») — attrape aussi
        un N+1 introduit dès la toute première ligne."""
        self._seed_leads(10)
        with self.assertMaxQueries(15):
            resp = self.api.get(LEADS_URL)
        self.assertEqual(resp.status_code, 200)
