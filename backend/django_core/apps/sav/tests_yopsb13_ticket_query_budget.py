"""YOPSB13 — budget de requêtes sur GET /api/django/sav/tickets/ (liste).

TicketViewSet.queryset a DÉJÀ select_related('client', 'installation',
'equipement', 'equipement__produit', 'technicien_responsable')
.prefetch_related('interventions') (apps/sav/views.py) — ce test est la
garde de RÉGRESSION : le nombre de requêtes ne doit PAS grandir avec le
nombre de lignes (peuple 10 puis 25 tickets, chacun avec un équipement
lié à un produit)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance, Equipement, Ticket
from apps.stock.models import Produit
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
TICKETS_URL = '/api/django/sav/tickets/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TicketListQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Budget SAV SARL')
        self.user = User.objects.create_user(
            username='budget_sav_user', password='x', role_legacy='admin',
            company=self.company)
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Budget',
            email='budget-sav@example.com', telephone='+212600000003')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='SAV-BUDGET-SKU',
            prix_vente=Decimal('1000'))

    def _seed_tickets(self, count, start=0):
        for i in range(start, start + count):
            equipement = Equipement.objects.create(
                company=self.company, produit=self.produit,
                numero_serie=f'SN-{i}')
            Ticket.objects.create(
                company=self.company, reference=f'TCK-{i:04d}',
                client=self.client_obj, equipement=equipement)

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_tickets(10)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(TICKETS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_10 = len(ctx_10.captured_queries)

        self._seed_tickets(15, start=10)  # total 25
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(TICKETS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_25 = len(ctx_25.captured_queries)

        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes '
            '(N+1) — vérifier select_related/prefetch_related sur '
            'TicketViewSet.queryset (client, installation, equipement, '
            'equipement__produit, technicien_responsable, interventions).')

    def test_query_count_stays_within_fixed_budget(self):
        self._seed_tickets(10)
        with self.assertMaxQueries(20):
            resp = self.api.get(TICKETS_URL)
        self.assertEqual(resp.status_code, 200)

    def test_query_count_flat_with_active_contract(self):
        """APRF31 — client SOUS CONTRAT (registre + quota) : 10 puis 25
        tickets coûtent le même nombre de requêtes, couverture identique."""
        from django.utils import timezone

        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, actif=True,
            date_debut=timezone.localdate(), deplacements_inclus_an=100,
            visites_incluses_an=100)
        self._seed_tickets(10)
        for eq in Equipement.objects.filter(company=self.company)[:5]:
            contrat.equipements.add(eq)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(TICKETS_URL)
        self.assertEqual(resp.status_code, 200)
        couvertures_10 = {
            r['reference']: (r['equipement_couvert'], r['couverture_proposee'])
            for r in (resp.data['results'] if isinstance(resp.data, dict)
                      else resp.data)}

        self._seed_tickets(15, start=10)  # total 25
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(TICKETS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            len(ctx_10.captured_queries), len(ctx_25.captured_queries),
            'N+1 sur la couverture de contrat (registre / droits).')
        rows = (resp.data['results'] if isinstance(resp.data, dict)
                else resp.data)
        for r in rows:
            if r['reference'] in couvertures_10:
                self.assertEqual(
                    couvertures_10[r['reference']],
                    (r['equipement_couvert'], r['couverture_proposee']))
