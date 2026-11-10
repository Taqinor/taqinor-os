"""T8 — édition en masse du catalogue produit + export Excel."""
import uuid
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
        kw.setdefault('sku', f"SKU-{uuid.uuid4().hex[:8]}")
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

    def test_set_category_vide_retire_la_categorie_sans_500(self):
        # api-fuzz stock B : ``categorie_id: ""`` (publié) levait ValueError -> 400.
        cat = Categorie.objects.create(company=self.company, nom='Onduleurs')
        p = self.mk(categorie=cat)
        resp = self.bulk(action='set_category', ids=[p.id], categorie_id='')
        self.assertEqual(resp.status_code, 200, resp.content)
        p.refresh_from_db()
        self.assertIsNone(p.categorie_id)

    def test_marque_publiee_sans_nul(self):
        # api-fuzz-full 27/10 : « K\x00… » était publié conforme puis refusé
        # (400 du pilote) — le corps publie le motif sans NUL (ChaineStricte).
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.stock import urls as stock_urls
        from core.champs_stricts import MOTIF_SANS_NUL
        schema = SchemaGenerator(patterns=[
            path('api/django/stock/', include(stock_urls)),
        ]).get_schema(request=None, public=True)
        operation = schema['paths']['/api/django/stock/produits/bulk/']['post']
        ref = operation['requestBody']['content']['application/json'][
            'schema']['$ref'].rsplit('/', 1)[-1]
        marque = schema['components']['schemas'][ref]['properties']['marque']
        self.assertEqual(marque['pattern'], MOTIF_SANS_NUL)


class TestBulkExportAndScope(ProductBulkBase):
    def test_export_xlsx(self):
        p = self.mk(nom='Panneau')
        resp = self.api.post('/api/django/stock/produits/export-xlsx/',
                             {'ids': [p.id]}, format='json')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_export_xlsx_ids_non_entiers_400_jamais_500(self):
        """ENF11 — ids non entiers / corps liste : 400."""
        url = '/api/django/stock/produits/export-xlsx/'
        for corps in ({'ids': [{}]}, {'ids': ['abc']}, [None, None]):
            resp = self.api.post(url, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))

    def test_cannot_touch_other_company(self):
        other = Company.objects.create(slug='pb-other', nom='Autre')
        foreign = Produit.objects.create(
            company=other, nom='X', sku='X-1', prix_vente=Decimal('500'))
        resp = self.bulk(action='set_price', ids=[foreign.id], mode='fixed', valeur='1')
        self.assertEqual(resp.data['total'], 0)
        foreign.refresh_from_db()
        self.assertEqual(foreign.prix_vente, Decimal('500'))

    def test_exports_exigent_stock_export(self):
        """ASEC70 (C-ASEC-VER4-040, D-ASEC-VER4-1) — un rôle personnalisé
        ``stock_voir`` seul : 403 ``droit_manquant`` aux exports Excel des
        produits ET des mouvements, aucun job d'export ; le même rôle avec
        ``stock_export`` exporte. Mutant : retirer une garde ⇒ échec."""
        from apps.roles.models import Role
        from core.models import BackgroundJob
        p = self.mk(nom='Panneau')
        lecteur = Role.objects.create(company=self.company, nom='Lecteur stock',
                                      permissions=['stock_voir'])
        user = User.objects.create_user(
            username='pb_lecteur', password='x', role_legacy='normal',
            role=lecteur, company=self.company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        jobs = BackgroundJob.objects.count()
        for url, corps in (('/api/django/stock/produits/export-xlsx/', {'ids': [p.id]}),
                           ('/api/django/stock/mouvements/export-xlsx/', {})):
            resp = api.post(url, corps, format='json')
            self.assertEqual(resp.status_code, 403, (url, resp.content))
            self.assertEqual(resp.json()['code'], 'droit_manquant', url)
        self.assertEqual(BackgroundJob.objects.count(), jobs)
        lecteur.permissions = ['stock_voir', 'stock_export']
        lecteur.save(update_fields=['permissions'])
        resp = api.post('/api/django/stock/produits/export-xlsx/', {'ids': [p.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_agregation_xlsx_exige_stock_export(self):
        """ASEC88 (C-ASEC-VER5-070, D-ASEC-VER4-1) — le VRAI rôle système
        Commercial (``stock_voir`` sans ``stock_export``) : 403
        ``droit_manquant`` à ``agregation/?export=xlsx``, 200 JSON sans
        ``export`` ; l'Admin Ventes (porte ``stock_export``) exporte.
        Mutant : ôter ``agregation=`` de ``droits_de_la_grille`` ⇒ échec."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            ADMIN_VENTES_PERMISSIONS, COMMERCIAL_PERMISSIONS, ROLE_ADMIN_VENTES)
        self.mk(nom='Panneau')
        url = '/api/django/stock/mouvements/agregation/?group_by=produit'
        clients = {}
        for nom, perms in (('Commercial', COMMERCIAL_PERMISSIONS),
                           (ROLE_ADMIN_VENTES, ADMIN_VENTES_PERMISSIONS)):
            role = Role.objects.create(company=self.company, nom=nom, permissions=list(perms))
            user = User.objects.create_user(username=f'pb_{role.pk}', password='x',
                                            role=role, company=self.company)
            clients[nom] = APIClient()
            clients[nom].credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = clients['Commercial'].get(f'{url}&export=xlsx')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(resp.json()['code'], 'droit_manquant')
        resp = clients['Commercial'].get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsInstance(resp.json(), list)
        resp = clients[ROLE_ADMIN_VENTES].get(f'{url}&export=xlsx')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('spreadsheetml', resp['Content-Type'])
