"""Tests NTAGR13 — PointIrrigation + RelevePointIrrigation.

Couvre : création d'un point d'irrigation avec source pompage solaire
optionnelle (lue via ``installations.selectors``, jamais un import de
modèle), enregistrement d'un relevé, cross-tenant refusé, et (WIR141)
l'endpoint ``cout-irrigation`` d'une campagne."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.agriculture.models import (
    CampagneCulturale, Exploitation, Parcelle, PointIrrigation,
)

from .helpers import auth, make_company, make_user, rows


class PointIrrigationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-irr-a', 'Ferme Irrigation A')
        self.admin_a = make_user(self.co_a, 'agr-irr-admin-a', 'admin')
        exploitation = Exploitation.objects.create(company=self.co_a, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation, nom='Parcelle 1')

    def test_create_point_irrigation_puits(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/points-irrigation/', {
            'parcelle': self.parcelle.id, 'type_source': 'puits',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_point_irrigation_pompage_solaire_installation_scoped(self):
        api = auth(self.admin_a)
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=object(),
        ):
            resp = api.post('/api/django/agriculture/points-irrigation/', {
                'parcelle': self.parcelle.id, 'type_source': 'pompage_solaire',
                'installation_id': 42,
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_point_irrigation_unknown_installation_rejected(self):
        api = auth(self.admin_a)
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=None,
        ):
            resp = api.post('/api/django/agriculture/points-irrigation/', {
                'parcelle': self.parcelle.id, 'type_source': 'pompage_solaire',
                'installation_id': 999,
            }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_releve_irrigation(self):
        point = PointIrrigation.objects.create(
            company=self.co_a, parcelle=self.parcelle, type_source='puits')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/releves-irrigation/', {
            'point': point.id, 'date': '2026-06-10', 'volume_m3': '15.50',
            'cout_energie_mad': '45.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_releve_solaire_can_omit_cout_energie(self):
        point = PointIrrigation.objects.create(
            company=self.co_a, parcelle=self.parcelle,
            type_source='pompage_solaire', installation_id=42)
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/releves-irrigation/', {
            'point': point.id, 'date': '2026-06-10', 'volume_m3': '20.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['cout_energie_mad'])

    def test_filter_releves_by_point(self):
        point = PointIrrigation.objects.create(
            company=self.co_a, parcelle=self.parcelle, type_source='puits')
        point.releves.create(
            company=self.co_a, date='2026-06-10', volume_m3='10.00')
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/releves-irrigation/', {
            'point_id': point.id,
        })
        self.assertEqual(len(rows(resp)), 1)

    def test_cross_tenant_parcelle_rejected(self):
        co_b = make_company('agr-irr-b', 'Ferme Irrigation B')
        exploitation_b = Exploitation.objects.create(company=co_b, nom='Domaine B')
        parcelle_b = Parcelle.objects.create(
            company=co_b, exploitation=exploitation_b, nom='Parcelle B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/points-irrigation/', {
            'parcelle': parcelle_b.id, 'type_source': 'puits',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class CampagneCoutIrrigationEndpointTests(TestCase):
    """WIR141 — ``GET campagnes/<id>/cout-irrigation/`` (sélecteurs NTAGR14,
    jusqu'ici sans appelant REST)."""

    def setUp(self):
        self.co = make_company('agr-irr-cockpit', 'Ferme Cockpit Irrigation')
        self.admin = make_user(self.co, 'agr-irr-cockpit-admin', 'admin')
        exploitation = Exploitation.objects.create(
            company=self.co, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co, parcelle=self.parcelle, culture='Blé',
            date_semis='2026-01-01', date_recolte_prevue='2026-06-30')

    def test_returns_paid_cost_and_solar_volume(self):
        payant = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle, type_source='reseau')
        payant.releves.create(
            company=self.co, date='2026-03-01', volume_m3=Decimal('10'),
            cout_energie_mad=Decimal('80.00'))
        solaire = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle,
            type_source='pompage_solaire', installation_id=1)
        solaire.releves.create(
            company=self.co, date='2026-03-02', volume_m3=Decimal('25'))

        api = auth(self.admin)
        url = (
            f'/api/django/agriculture/campagnes/{self.campagne.id}'
            '/cout-irrigation/')
        resp = api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['cout_irrigation_mad'], '80.00')
        self.assertEqual(resp.data['volume_irrigation_solaire_m3'], '25')
