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


# APRF32 — skip retiré : `company`/`unite` sont chargés par ProduitViewSet et
# le libellé d'unité vient d'une carte mémoïsée (`_unite_libelle_map`).
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
        # YOPSB13 — précondition société : le dépôt principal est matérialisé
        # PARESSEUSEMENT au 1er accès (services.ensure_emplacements). Sans ce
        # warm-up, le TOUT PREMIER GET porte 2 requêtes de création unique
        # (INSERT emplacement) qui gonflaient le compte (17 à froid vs 15 en
        # régime) et faisaient croire à une croissance (17 != 15). Toute vraie
        # société a déjà ce dépôt : on le matérialise ici pour mesurer le
        # régime permanent (la vraie garde N+1), pas le coût unique d'amorçage.
        from apps.stock.services import ensure_emplacements
        ensure_emplacements(self.company)

    def _seed_produits(self, count, start=0):
        # APRF32 — unités variées (dont une sans libellé au référentiel).
        from apps.parametres.models import UniteMesure
        for code, lib in (('m', 'Mètre'), ('kg', 'Kilogramme')):
            UniteMesure.objects.get_or_create(
                company=self.company, code=code,
                defaults={'libelle': lib, 'actif': True})
        unites = ['m', 'kg', 'sans-libelle']
        for i in range(start, start + count):
            Produit.objects.create(
                company=self.company, nom=f'Produit{i}', sku=f'SKU-{i}',
                categorie=self.categorie, fournisseur=self.fournisseur,
                prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
                quantite_stock=10, unite_stock=unites[i % len(unites)])

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_produits(5)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(PRODUITS_URL + '?page_size=50')
        self.assertEqual(resp.status_code, 200)
        count_at_10 = len(ctx_10.captured_queries)

        self._seed_produits(45, start=5)  # total 50
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(PRODUITS_URL + '?page_size=50')
        self.assertEqual(resp.status_code, 200)
        count_at_25 = len(ctx_25.captured_queries)

        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes '
            '(N+1) — vérifier select_related sur ProduitViewSet.queryset '
            '(categorie, fournisseur).')

    def test_query_count_stays_within_fixed_budget(self):
        self._seed_produits(50)
        with self.assertMaxQueries(24):
            resp = self.api.get(PRODUITS_URL + '?page_size=50')
        self.assertEqual(resp.status_code, 200)

    def test_unite_stock_display_inchange(self):
        self._seed_produits(3)
        resp = self.api.get(PRODUITS_URL + '?page_size=50')
        rows = resp.json().get('results', resp.json())
        par_nom = {r['nom']: r['unite_stock_display'] for r in rows}
        self.assertEqual(par_nom['Produit0'], 'Mètre')
        self.assertEqual(par_nom['Produit1'], 'Kilogramme')
        self.assertEqual(par_nom['Produit2'], 'sans-libelle')
