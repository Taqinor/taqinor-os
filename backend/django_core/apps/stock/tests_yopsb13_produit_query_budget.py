"""YOPSB13 — budget de requêtes sur GET /api/django/stock/produits/ (liste).

ProduitViewSet.queryset a DÉJÀ select_related('categorie', 'fournisseur')
(apps/stock/views/produit.py) — ce test est la garde de RÉGRESSION : le
nombre de requêtes ne doit PAS grandir avec le nombre de lignes (peuple 10
puis 25 produits, chacun avec une catégorie ET un fournisseur liés — les
deux nested serializers exposés par ProduitSerializer)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import Categorie, Fournisseur, Produit
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
PRODUITS_URL = '/api/django/stock/produits/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ProduitListQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Budget Stock SARL')
        self.user = User.objects.create_user(
            username='budget_stock_user', password='x', role_legacy='admin',
            company=self.company)
        self.api = _api(self.user)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Budget')

    def _seed_produits(self, count, start=0):
        for i in range(start, start + count):
            Produit.objects.create(
                company=self.company, nom=f'Produit{i}', sku=f'SKU-{i}',
                categorie=self.categorie, fournisseur=self.fournisseur,
                prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
                quantite_stock=10)

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_produits(10)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(PRODUITS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_10 = len(ctx_10.captured_queries)

        self._seed_produits(15, start=10)  # total 25
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(PRODUITS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_25 = len(ctx_25.captured_queries)

        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes '
            '(N+1) — vérifier select_related sur ProduitViewSet.queryset '
            '(categorie, fournisseur).')

    def test_query_count_stays_within_fixed_budget(self):
        self._seed_produits(10)
        with self.assertMaxQueries(15):
            resp = self.api.get(PRODUITS_URL)
        self.assertEqual(resp.status_code, 200)
