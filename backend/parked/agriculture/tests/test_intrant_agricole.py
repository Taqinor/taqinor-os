"""Tests NTAGR5 — IntrantAgricole : catalogue lié à ``stock.Produit``.

Couvre : création d'un intrant lié à un produit stock existant, refus si le
produit n'existe pas (ou appartient à une autre société), un produit sans
fiche agricole reste utilisable normalement ailleurs (aucune mutation du
produit stock), filtre ``?categorie=``.

Le produit stock est créé directement via ``apps.stock.models.Produit``
UNIQUEMENT pour construire la fixture de test (setUp) — la production
(``serializers.py``) ne lit le produit QUE via ``apps.stock.selectors``,
jamais un import de modèle (CLAUDE.md, frontière cross-app)."""
from django.test import TestCase

from apps.agriculture.models import IntrantAgricole
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user, rows


class IntrantAgricoleApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-intrant-a', 'Ferme Intrant A')
        self.co_b = make_company('agr-intrant-b', 'Ferme Intrant B')
        self.admin_a = make_user(self.co_a, 'agr-intrant-admin-a', 'admin')
        self.produit_a = Produit.objects.create(
            company=self.co_a, nom='Engrais NPK 15-15-15', prix_vente=250)
        self.produit_b = Produit.objects.create(
            company=self.co_b, nom='Produit société B', prix_vente=100)

    def test_create_intrant_linked_to_existing_stock_product(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/intrants-agricoles/', {
            'produit_id': self.produit_a.id, 'categorie': 'engrais',
            'dose_reference_par_ha': '200.000',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        intrant = IntrantAgricole.objects.get(id=resp.data['id'])
        self.assertEqual(intrant.company_id, self.co_a.id)
        self.assertEqual(intrant.produit_id, self.produit_a.id)
        self.assertEqual(resp.data['produit_nom'], 'Engrais NPK 15-15-15')

    def test_create_intrant_rejects_unknown_product_id(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/intrants-agricoles/', {
            'produit_id': 999999, 'categorie': 'engrais',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_intrant_rejects_other_company_product(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/intrants-agricoles/', {
            'produit_id': self.produit_b.id, 'categorie': 'engrais',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_product_without_agri_sheet_stays_usable(self):
        # Aucune fiche agricole créée pour produit_a : le produit stock
        # reste inchangé et normalement utilisable ailleurs.
        self.assertFalse(
            IntrantAgricole.objects.filter(produit_id=self.produit_a.id).exists())
        produit = Produit.objects.get(id=self.produit_a.id)
        self.assertEqual(produit.nom, 'Engrais NPK 15-15-15')

    def test_filter_by_categorie(self):
        produit2 = Produit.objects.create(
            company=self.co_a, nom='Semence blé', prix_vente=80)
        IntrantAgricole.objects.create(
            company=self.co_a, produit_id=self.produit_a.id, categorie='engrais')
        IntrantAgricole.objects.create(
            company=self.co_a, produit_id=produit2.id, categorie='semence')

        api = auth(self.admin_a)
        resp = api.get(
            '/api/django/agriculture/intrants-agricoles/', {'categorie': 'semence'})
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]['categorie'], 'semence')
