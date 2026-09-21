"""Tests NTAGR3 — Étapes de campagne horodatées avec coût par étape.

Couvre : ajout d'une étape avec son coût, agrégation correcte via le
sélecteur ``cout_total_campagne`` (étapes sans coût ignorées), filtre
``?campagne_id=``.
"""
from decimal import Decimal

from django.test import TestCase

from apps.agriculture.models import (
    CampagneCulturale, Exploitation, Parcelle,
)
from apps.agriculture.selectors import cout_total_campagne

from .helpers import auth, make_company, make_user, rows


class EtapeCampagneApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-etape-a', 'Ferme Étape A')
        self.admin_a = make_user(self.co_a, 'agr-etape-admin-a', 'admin')
        exploitation = Exploitation.objects.create(
            company=self.co_a, nom='Domaine')
        parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=parcelle, culture='Tomate',
            statut='en_cours')

    def test_add_etape_with_cost(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': self.campagne.id, 'type_etape': 'fertilisation',
            'date': '2026-03-15', 'description': 'Engrais NPK',
            'cout_mad': '350.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            self.campagne.etapes.get(id=resp.data['id']).company_id,
            self.co_a.id)

    def test_cout_total_campagne_aggregates_and_ignores_costless_steps(self):
        self.campagne.etapes.create(
            company=self.co_a, type_etape='semis', date='2026-03-01',
            cout_mad=Decimal('100.00'))
        self.campagne.etapes.create(
            company=self.co_a, type_etape='irrigation', date='2026-03-10',
            cout_mad=Decimal('50.50'))
        # Étape prévisionnelle sans coût — ignorée, pas comptée comme zéro.
        self.campagne.etapes.create(
            company=self.co_a, type_etape='recolte', date='2026-06-01')

        self.assertEqual(
            cout_total_campagne(self.campagne), Decimal('150.50'))

    def test_filter_by_campagne(self):
        exploitation2 = Exploitation.objects.create(
            company=self.co_a, nom='Domaine 2')
        parcelle2 = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation2, nom='Parcelle 2')
        autre_campagne = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=parcelle2, culture='Orge')
        self.campagne.etapes.create(
            company=self.co_a, type_etape='semis', date='2026-03-01')
        autre_campagne.etapes.create(
            company=self.co_a, type_etape='semis', date='2026-03-01')

        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/etapes-campagne/', {
            'campagne_id': self.campagne.id,
        })
        self.assertEqual(len(rows(resp)), 1)

    def test_cross_tenant_campagne_rejected(self):
        co_b = make_company('agr-etape-b', 'Ferme Étape B')
        exploitation_b = Exploitation.objects.create(
            company=co_b, nom='Domaine B')
        parcelle_b = Parcelle.objects.create(
            company=co_b, exploitation=exploitation_b, nom='Parcelle B')
        campagne_b = CampagneCulturale.objects.create(
            company=co_b, parcelle=parcelle_b, culture='Maïs')

        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': campagne_b.id, 'type_etape': 'semis',
            'date': '2026-03-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
