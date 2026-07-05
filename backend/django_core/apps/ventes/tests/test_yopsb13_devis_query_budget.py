"""YOPSB13 — budget de requêtes sur GET /api/django/ventes/devis/ (liste).

DevisViewSet.queryset a DÉJÀ select_related('client', 'created_by')
.prefetch_related('lignes') (apps/ventes/views/devis.py) — ce test est la
garde de RÉGRESSION : le nombre de requêtes ne doit PAS grandir avec le
nombre de lignes (peuple 10 puis 25 devis, chacun avec 2 lignes)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
DEVIS_URL = '/api/django/ventes/devis/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DevisListQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Budget Devis SARL')
        self.user = User.objects.create_user(
            username='budget_devis_user', password='x', role_legacy='admin',
            company=self.company)
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Budget',
            email='budget@example.com', telephone='+212600000002')

    def _seed_devis(self, count, start=0):
        for i in range(start, start + count):
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-{i:04d}',
                client=self.client_obj, created_by=self.user,
                taux_tva=Decimal('20'))
            for j, (desig, pu) in enumerate(
                    [('Onduleur', '11700'), ('Panneau', '1100')]):
                produit = Produit.objects.create(
                    company=self.company, nom=desig, sku=f'{i}-{j}-{desig}',
                    prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                    quantite_stock=100)
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=desig,
                    quantite=Decimal('1'), prix_unitaire=Decimal(pu))

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_devis(10)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_10 = len(ctx_10.captured_queries)

        self._seed_devis(15, start=10)  # total 25
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_25 = len(ctx_25.captured_queries)

        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes '
            '(N+1) — vérifier select_related/prefetch_related sur '
            'DevisViewSet.queryset (client, created_by, lignes).')

    def test_query_count_stays_within_fixed_budget(self):
        self._seed_devis(10)
        with self.assertMaxQueries(15):
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
