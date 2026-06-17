"""F1 — Outillage (équipement durable) catalogue tests.

Run:
    docker compose exec django_core python manage.py test apps.stock.tests_outillage -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Outillage, Produit, MouvementStock
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/stock/outillage/'


class OutillageBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='out-co', defaults={'nom': 'Out Co'})[0]
        self.other = Company.objects.get_or_create(
            slug='out-co-2', defaults={'nom': 'Other Co'})[0]
        self.user = User.objects.create_user(
            username='out_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestOutillageCrud(OutillageBase):
    def test_create_forces_company_from_request(self):
        # company is NEVER read from the body — even a spoofed one is ignored.
        resp = self.api.post(BASE, {
            'nom': 'Perceuse Bosch', 'categorie': 'Électroportatif',
            'asset_tag': 'TAQ-001', 'emplacement': 'camionnette',
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tool = Outillage.objects.get(nom='Perceuse Bosch')
        self.assertEqual(tool.company, self.company)
        self.assertEqual(tool.statut, Outillage.Statut.DISPONIBLE)  # default
        self.assertEqual(tool.emplacement, 'camionnette')

    def test_list_is_company_scoped(self):
        Outillage.objects.create(company=self.company, nom='À moi')
        Outillage.objects.create(company=self.other, nom='Pas à moi')
        resp = self.api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in resp.data]
        self.assertIn('À moi', noms)
        self.assertNotIn('Pas à moi', noms)

    def test_filter_by_emplacement_and_statut(self):
        Outillage.objects.create(
            company=self.company, nom='Au dépôt',
            emplacement='depot', statut='disponible')
        Outillage.objects.create(
            company=self.company, nom='En réparation',
            emplacement='camionnette', statut='en_reparation')
        r1 = self.api.get(BASE, {'emplacement': 'depot'})
        self.assertEqual([r['nom'] for r in r1.data], ['Au dépôt'])
        r2 = self.api.get(BASE, {'statut': 'en_reparation'})
        self.assertEqual([r['nom'] for r in r2.data], ['En réparation'])

    def test_asset_tag_unique_per_company(self):
        Outillage.objects.create(
            company=self.company, nom='A', asset_tag='DUP')
        resp = self.api.post(BASE, {'nom': 'B', 'asset_tag': 'DUP'},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        # but the same tag is fine in another company
        Outillage.objects.create(
            company=self.other, nom='C', asset_tag='DUP')

    def test_blank_asset_tags_do_not_collide(self):
        # several tools with no asset tag must coexist (partial unique index).
        Outillage.objects.create(company=self.company, nom='X', asset_tag='')
        resp = self.api.post(BASE, {'nom': 'Y'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestOutillageSeparateFromStock(OutillageBase):
    def test_outil_is_not_a_sellable_produit(self):
        # An Outillage row never appears among Produit (sellable stock) and
        # creating one posts no stock movement.
        Outillage.objects.create(company=self.company, nom='Échelle')
        self.assertEqual(
            Produit.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            MouvementStock.objects.filter(company=self.company).count(), 0)
