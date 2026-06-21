"""Tests du module Gestion de flotte (FLOTTE2).

Couvre : isolation par société (A ne voit/touche pas B), société posée côté
serveur (jamais lue du corps de requête), filtres et recherche, pour la ressource
Véhicule.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import Vehicule

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class FlotteVehiculeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('flotte-a', 'Flotte A')
        self.co_b = make_company('flotte-b', 'Flotte B')
        self.admin_a = make_user(self.co_a, 'flotte-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'flotte-admin-b', 'admin')

    # ── FLOTTE2 : véhicules ──
    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': '1234-A-56', 'marque': 'Dacia',
            'modele': 'Duster', 'energie': 'diesel', 'kilometrage': 12000,
            'valeur': '180000.00', 'statut': 'actif',
            # Tentative d'injection d'une autre société — doit être ignorée.
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        veh = Vehicule.objects.get(id=resp.data['id'])
        self.assertEqual(veh.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        Vehicule.objects.create(company=self.co_a, immatriculation='AAA-1')
        Vehicule.objects.create(company=self.co_b, immatriculation='BBB-1')
        resp = auth(self.admin_a).get('/api/django/flotte/vehicules/')
        immats = [r['immatriculation'] for r in rows(resp)]
        self.assertIn('AAA-1', immats)
        self.assertNotIn('BBB-1', immats)

    def test_cannot_retrieve_other_company_vehicule(self):
        b_veh = Vehicule.objects.create(
            company=self.co_b, immatriculation='BBB-2')
        resp = auth(self.admin_a).get(
            f'/api/django/flotte/vehicules/{b_veh.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_statut_and_energie(self):
        Vehicule.objects.create(
            company=self.co_a, immatriculation='V-ACTIF', statut='actif',
            energie='diesel')
        Vehicule.objects.create(
            company=self.co_a, immatriculation='V-MAINT', statut='maintenance',
            energie='electrique')
        api = auth(self.admin_a)
        r1 = api.get('/api/django/flotte/vehicules/?statut=maintenance')
        self.assertEqual([x['immatriculation'] for x in rows(r1)], ['V-MAINT'])
        r2 = api.get('/api/django/flotte/vehicules/?energie=electrique')
        self.assertEqual([x['immatriculation'] for x in rows(r2)], ['V-MAINT'])

    def test_search_and_display_fields(self):
        Vehicule.objects.create(
            company=self.co_a, immatriculation='X-99', marque='Renault',
            energie='hybride', statut='actif')
        resp = auth(self.admin_a).get(
            '/api/django/flotte/vehicules/?search=Renault')
        row = rows(resp)[0]
        self.assertEqual(row['immatriculation'], 'X-99')
        self.assertEqual(row['energie_display'], 'Hybride')
        self.assertEqual(row['statut_display'], 'Actif')
