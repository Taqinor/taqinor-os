"""Tests NTAGR15 — LotRecolte (lié à stock, jamais un second système de lots).

Couvre : création avec numéro unique par société (race-safe via
``core.numbering``, jamais ``count()+1``), rattachement optionnel à un lot
stock physique existant, filtre par campagne, cross-tenant refusé."""
from django.test import TestCase

from apps.agriculture.models import CampagneCulturale, Exploitation, LotRecolte, Parcelle
from apps.agriculture.services import creer_lot_recolte

from .helpers import auth, make_company, make_user, rows


class LotRecolteApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-lot-a', 'Ferme Lot A')
        self.admin_a = make_user(self.co_a, 'agr-lot-admin-a', 'admin')
        exploitation = Exploitation.objects.create(company=self.co_a, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Orange',
            statut='recoltee')

    def test_create_lot_recolte_assigns_numero_lot(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/lots-recolte/', {
            'campagne': self.campagne.id, 'date_recolte': '2026-06-15',
            'quantite_qtl': '120.50', 'calibre': '60-70mm', 'qualite': 'A',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['numero_lot'])
        self.assertTrue(resp.data['numero_lot'].startswith('LOT-'))

    def test_numero_lot_unique_and_sequential_per_company(self):
        lot1 = creer_lot_recolte(
            company=self.co_a, campagne=self.campagne, date_recolte='2026-06-15',
            quantite_qtl='10')
        lot2 = creer_lot_recolte(
            company=self.co_a, campagne=self.campagne, date_recolte='2026-06-16',
            quantite_qtl='15')
        self.assertNotEqual(lot1.numero_lot, lot2.numero_lot)

    def test_create_lot_with_optional_stock_lot_id(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/lots-recolte/', {
            'campagne': self.campagne.id, 'date_recolte': '2026-06-15',
            'quantite_qtl': '50', 'stock_lot_id': 'LOTENT-2026-0007',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['stock_lot_id'], 'LOTENT-2026-0007')

    def test_lot_without_stock_lot_id_still_creates(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/lots-recolte/', {
            'campagne': self.campagne.id, 'date_recolte': '2026-06-15',
            'quantite_qtl': '5',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['stock_lot_id'], '')

    def test_filter_by_campagne(self):
        creer_lot_recolte(
            company=self.co_a, campagne=self.campagne, date_recolte='2026-06-15',
            quantite_qtl='10')
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/lots-recolte/', {
            'campagne_id': self.campagne.id,
        })
        self.assertEqual(len(rows(resp)), 1)

    def test_cross_tenant_campagne_rejected(self):
        co_b = make_company('agr-lot-b', 'Ferme Lot B')
        exploitation_b = Exploitation.objects.create(company=co_b, nom='Domaine B')
        parcelle_b = Parcelle.objects.create(
            company=co_b, exploitation=exploitation_b, nom='Parcelle B')
        campagne_b = CampagneCulturale.objects.create(
            company=co_b, parcelle=parcelle_b, culture='Blé')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/lots-recolte/', {
            'campagne': campagne_b.id, 'date_recolte': '2026-06-15',
            'quantite_qtl': '10',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_lot_numero_not_client_settable(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/lots-recolte/', {
            'campagne': self.campagne.id, 'date_recolte': '2026-06-15',
            'quantite_qtl': '10', 'numero_lot': 'HACKED-0001',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['numero_lot'], 'HACKED-0001')

    def test_cross_tenant_lot_not_visible(self):
        co_b = make_company('agr-lot-c', 'Ferme Lot C')
        exploitation_b = Exploitation.objects.create(company=co_b, nom='Domaine B')
        parcelle_b = Parcelle.objects.create(
            company=co_b, exploitation=exploitation_b, nom='Parcelle B')
        campagne_b = CampagneCulturale.objects.create(
            company=co_b, parcelle=parcelle_b, culture='Blé')
        creer_lot_recolte(
            company=co_b, campagne=campagne_b, date_recolte='2026-06-15',
            quantite_qtl='10')
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/lots-recolte/')
        self.assertEqual(len(rows(resp)), 0)
        self.assertEqual(LotRecolte.objects.count(), 1)
