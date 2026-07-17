"""Tests NTAGR13 — PointIrrigation + RelevePointIrrigation.

Couvre : création d'un point d'irrigation avec source pompage solaire
optionnelle (lue via ``installations.selectors``, jamais un import de
modèle), enregistrement d'un relevé, cross-tenant refusé."""
from unittest.mock import patch

from django.test import TestCase

from apps.agriculture.models import Exploitation, Parcelle, PointIrrigation

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
