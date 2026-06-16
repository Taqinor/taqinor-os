"""T8 — édition en masse du catalogue produit + export Excel."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit, Categorie
from authentication.models import Company

User = get_user_model()


class ProductBulkBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='pb-co', defaults={'nom': 'PB Co'})[0]
        self.user = User.objects.create_user(
            username='pb_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def mk(self, **kw):
        kw.setdefault('company', self.company)
        kw.setdefault('nom', 'P')
        kw.setdefault('sku', f"SKU-{Produit.objects.count()+1}")
        kw.setdefault('prix_vente', Decimal('1000'))
        kw.setdefault('prix_achat', Decimal('600'))
        kw.setdefault('quantite_stock', 5)
        return Produit.objects.create(**kw)

    def bulk(self, **payload):
        return self.api.post('/api/django/stock/produits/bulk/', payload, format='json')


class TestBulkPrice(ProductBulkBase):
    def test_percent_increase_keeps_buy_price(self):
        p = self.mk(prix_vente=Decimal('1000'), prix_achat=Decimal('600'))
        resp = self.bulk(action='set_price', ids=[p.id], mode='percent', valeur='10')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.prix_vente, Decimal('1100.00'))
        self.assertEqual(p.prix_achat, Decimal('600'))  # JAMAIS modifié

    def test_fixed_price(self):
        p = self.mk(prix_vente=Decimal('1000'))
        self.bulk(action='set_price', ids=[p.id], mode='fixed', valeur='750')
        p.refresh_from_db()
        self.assertEqual(p.prix_vente, Decimal('750.00'))


class TestBulkWarrantyCategoryBrand(ProductBulkBase):
    def test_set_warranty(self):
        p = self.mk()
        self.bulk(action='set_warranty', ids=[p.id],
                  garantie_mois=24, garantie_production_mois=300)
        p.refresh_from_db()
        self.assertEqual(p.garantie_mois, 24)
        self.assertEqual(p.garantie_production_mois, 300)

    def test_set_category_and_brand(self):
        cat = Categorie.objects.create(company=self.company, nom='Onduleurs')
        p = self.mk()
        self.bulk(action='set_category', ids=[p.id], categorie_id=cat.id)
        self.bulk(action='set_brand', ids=[p.id], marque='VEICHI')
        p.refresh_from_db()
        self.assertEqual(p.categorie_id, cat.id)
        self.assertEqual(p.marque, 'VEICHI')


class TestBulkExportAndScope(ProductBulkBase):
    def test_export_xlsx(self):
        p = self.mk(nom='Panneau')
        resp = self.api.post('/api/django/stock/produits/export-xlsx/',
                             {'ids': [p.id]}, format='json')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_cannot_touch_other_company(self):
        other = Company.objects.create(slug='pb-other', nom='Autre')
        foreign = Produit.objects.create(
            company=other, nom='X', sku='X-1', prix_vente=Decimal('500'))
        resp = self.bulk(action='set_price', ids=[foreign.id], mode='fixed', valeur='1')
        self.assertEqual(resp.data['total'], 0)
        foreign.refresh_from_db()
        self.assertEqual(foreign.prix_vente, Decimal('500'))
