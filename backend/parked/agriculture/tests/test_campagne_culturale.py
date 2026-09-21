"""Tests NTAGR2 — CampagneCulturale : cycle semis→récolte par parcelle.

Couvre : création d'une campagne sur une parcelle libre, refus clair d'une
deuxième campagne ``en_cours`` sur la même parcelle, filtre
``?parcelle_id=&statut=``.
"""
from django.test import TestCase

from apps.agriculture.models import CampagneCulturale, Exploitation, Parcelle

from .helpers import auth, make_company, make_user, rows


class CampagneCulturaleApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-camp-a', 'Ferme Camp A')
        self.admin_a = make_user(self.co_a, 'agr-camp-admin-a', 'admin')
        self.exploitation = Exploitation.objects.create(
            company=self.co_a, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=self.exploitation, nom='Parcelle 1')

    def test_create_campagne_on_free_parcelle(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/campagnes/', {
            'parcelle': self.parcelle.id, 'culture': 'Tomate',
            'variete': 'Roma', 'date_semis': '2026-03-01',
            'date_recolte_prevue': '2026-06-01', 'statut': 'en_cours',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            CampagneCulturale.objects.get(id=resp.data['id']).company_id,
            self.co_a.id)

    def test_second_active_campaign_on_same_parcelle_rejected(self):
        CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Blé',
            statut='en_cours')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/campagnes/', {
            'parcelle': self.parcelle.id, 'culture': 'Orge',
            'statut': 'en_cours',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('statut', resp.data)
        self.assertIn('en_cours', str(resp.data['statut']))

    def test_second_planned_campaign_allowed(self):
        CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Blé',
            statut='en_cours')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/campagnes/', {
            'parcelle': self.parcelle.id, 'culture': 'Orge',
            'statut': 'planifiee',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_closing_active_campaign_allows_new_one(self):
        active = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Blé',
            statut='en_cours')
        api = auth(self.admin_a)
        resp = api.patch(
            f'/api/django/agriculture/campagnes/{active.id}/',
            {'statut': 'cloturee'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = api.post('/api/django/agriculture/campagnes/', {
            'parcelle': self.parcelle.id, 'culture': 'Maïs',
            'statut': 'en_cours',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_filter_by_parcelle_and_statut(self):
        CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Blé',
            statut='cloturee')
        CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Orge',
            statut='en_cours')
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/campagnes/', {
            'parcelle_id': self.parcelle.id, 'statut': 'en_cours',
        })
        cultures = [r['culture'] for r in rows(resp)]
        self.assertEqual(cultures, ['Orge'])
