"""Tests NTAGR11 — Matériel agricole (pattern flotte, heures moteur).

Couvre : enregistrement d'un matériel, ajout d'une utilisation qui incrémente
les heures moteur cumulées, filtres, cross-tenant refusé."""
from decimal import Decimal

from django.test import TestCase

from apps.agriculture.models import (
    CampagneCulturale, Exploitation, MaterielAgricole, Parcelle,
)

from .helpers import auth, make_company, make_user, rows


class MaterielAgricoleApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-mat-a', 'Ferme Matériel A')
        self.co_b = make_company('agr-mat-b', 'Ferme Matériel B')
        self.admin_a = make_user(self.co_a, 'agr-mat-admin-a', 'admin')
        exploitation = Exploitation.objects.create(company=self.co_a, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Blé')
        self.materiel = MaterielAgricole.objects.create(
            company=self.co_a, nom='Tracteur MF 1', type_materiel='tracteur')

    def test_create_materiel(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/materiels-agricoles/', {
            'nom': 'Moissonneuse Claas', 'type_materiel': 'moissonneuse',
            'numero_serie': 'SN-001',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['heures_moteur'], '0.0')

    def test_create_utilisation_increments_heures_moteur(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/utilisations-materiel/', {
            'materiel': self.materiel.id, 'campagne': self.campagne.id,
            'date': '2026-06-10', 'heures_utilisees': '3.5',
            'cout_carburant_mad': '120.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.materiel.refresh_from_db()
        self.assertEqual(self.materiel.heures_moteur, Decimal('3.5'))

        # Deuxième utilisation — les heures s'accumulent (jamais écrasées).
        resp2 = api.post('/api/django/agriculture/utilisations-materiel/', {
            'materiel': self.materiel.id, 'date': '2026-06-11',
            'heures_utilisees': '2.0',
        }, format='json')
        self.assertEqual(resp2.status_code, 201, resp2.data)
        self.materiel.refresh_from_db()
        self.assertEqual(self.materiel.heures_moteur, Decimal('5.5'))

    def test_filter_utilisations_by_materiel_and_campagne(self):
        self.materiel.utilisations.create(
            company=self.co_a, campagne=self.campagne, date='2026-06-10',
            heures_utilisees=Decimal('1'))
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/utilisations-materiel/', {
            'materiel_id': self.materiel.id, 'campagne_id': self.campagne.id,
        })
        self.assertEqual(len(rows(resp)), 1)

    def test_cross_tenant_materiel_on_utilisation_rejected(self):
        materiel_b = MaterielAgricole.objects.create(
            company=self.co_b, nom='Tracteur B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/utilisations-materiel/', {
            'materiel': materiel_b.id, 'date': '2026-06-10',
            'heures_utilisees': '1.0',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_cross_tenant_materiel_not_visible(self):
        MaterielAgricole.objects.create(company=self.co_b, nom='Tracteur B')
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/materiels-agricoles/')
        self.assertEqual(len(rows(resp)), 1)
