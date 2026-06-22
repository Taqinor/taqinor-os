"""Tests du module Gestion de flotte (FLOTTE2 / FLOTTE4).

Couvre : isolation par société (A ne voit/touche pas B), société posée côté
serveur (jamais lue du corps de requête), filtres et recherche, pour les deux
ressources Véhicule et Engin roulant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import EnginRoulant, Vehicule
from apps.flotte.selectors import emplacement_stock_label
from apps.stock.models import EmplacementStock

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


class FlotteEnginRoulantTests(TestCase):
    def setUp(self):
        self.co_a = make_company('flotte-ea', 'Flotte EA')
        self.co_b = make_company('flotte-eb', 'Flotte EB')
        self.admin_a = make_user(self.co_a, 'flotte-eadmin-a', 'admin')

    # ── FLOTTE4 : engins roulants ──
    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/engins/', {
            'nom': 'Nacelle 12m', 'type_engin': 'nacelle',
            'compteur_heures': '350.5', 'valeur': '90000.00',
            'statut': 'actif',
            'company': self.co_b.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        engin = EnginRoulant.objects.get(id=resp.data['id'])
        self.assertEqual(engin.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        EnginRoulant.objects.create(company=self.co_a, nom='Groupe A')
        EnginRoulant.objects.create(company=self.co_b, nom='Groupe B')
        resp = auth(self.admin_a).get('/api/django/flotte/engins/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Groupe A', noms)
        self.assertNotIn('Groupe B', noms)

    def test_cannot_retrieve_other_company_engin(self):
        b_engin = EnginRoulant.objects.create(company=self.co_b, nom='Chariot B')
        resp = auth(self.admin_a).get(
            f'/api/django/flotte/engins/{b_engin.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_type_and_display(self):
        EnginRoulant.objects.create(
            company=self.co_a, nom='Nacelle', type_engin='nacelle')
        EnginRoulant.objects.create(
            company=self.co_a, nom='Groupe', type_engin='groupe_electrogene')
        api = auth(self.admin_a)
        resp = api.get('/api/django/flotte/engins/?type_engin=groupe_electrogene')
        immats = rows(resp)
        self.assertEqual([x['nom'] for x in immats], ['Groupe'])
        self.assertEqual(immats[0]['type_engin_display'], 'Groupe électrogène')


class FlotteEmplacementLinkTests(TestCase):
    """FLOTTE3 — lien Vehicule -> stock.EmplacementStock (id via sélecteur)."""

    def setUp(self):
        self.co_a = make_company('flotte-loc-a', 'Flotte Loc A')
        self.co_b = make_company('flotte-loc-b', 'Flotte Loc B')
        self.admin_a = make_user(self.co_a, 'flotte-loc-admin-a', 'admin')
        self.empl_a = EmplacementStock.objects.create(
            company=self.co_a, nom='Dépôt principal', is_principal=True)
        self.empl_b = EmplacementStock.objects.create(
            company=self.co_b, nom='Dépôt B')

    def test_set_link_same_company_persists(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-1', 'energie': 'diesel',
            'emplacement_stock_id': self.empl_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        veh = Vehicule.objects.get(id=resp.data['id'])
        self.assertEqual(veh.emplacement_stock_id, self.empl_a.id)
        self.assertEqual(resp.data['emplacement_stock_id'], self.empl_a.id)
        # Le libellé est résolu via le sélecteur de stock.
        self.assertEqual(
            resp.data['emplacement_stock_label'], 'Dépôt principal')

    def test_set_link_other_company_rejected(self):
        """Un emplacement d'une AUTRE société est refusé (validation sélecteur)."""
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-2', 'energie': 'diesel',
            'emplacement_stock_id': self.empl_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('emplacement_stock_id', resp.data)
        self.assertFalse(
            Vehicule.objects.filter(immatriculation='L-2').exists())

    def test_set_link_unknown_id_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-3', 'energie': 'diesel',
            'emplacement_stock_id': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_clear_link_via_patch(self):
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation='L-4',
            emplacement_stock_id=self.empl_a.id)
        api = auth(self.admin_a)
        resp = api.patch(
            f'/api/django/flotte/vehicules/{veh.id}/',
            {'emplacement_stock_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        veh.refresh_from_db()
        self.assertIsNone(veh.emplacement_stock_id)
        self.assertIsNone(resp.data['emplacement_stock_label'])

    def test_create_without_link_is_allowed(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-5', 'energie': 'diesel',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['emplacement_stock_id'])
        self.assertIsNone(resp.data['emplacement_stock_label'])

    def test_selector_label_helper(self):
        """Le sélecteur résout le nom, dégrade sur l'id nu, None si vide."""
        self.assertEqual(
            emplacement_stock_label(self.co_a, self.empl_a.id),
            'Dépôt principal')
        # Emplacement d'une autre société : non résolu -> dégrade sur l'id nu.
        self.assertEqual(
            emplacement_stock_label(self.co_a, self.empl_b.id),
            f'#{self.empl_b.id}')
        # Id inexistant -> dégrade sur l'id nu.
        self.assertEqual(
            emplacement_stock_label(self.co_a, 999999), '#999999')
        # Pas de lien -> None.
        self.assertIsNone(emplacement_stock_label(self.co_a, None))
