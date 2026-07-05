"""Tests ZACC14 — Vérification du n° d'identifiant fiscal / ICE des tiers.

Couvre : un client sans ICE et un fournisseur à ICE court apparaissent dans
le rapport avec le motif, les tiers conformes sont exclus, un particulier
sans ICE n'apparaît jamais (non pertinent), cross-company isolé, export
csv.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors as compta_selectors
from apps.crm.models import Client
from apps.stock.models import Fournisseur

User = get_user_model()


def make_company(slug='zacc14-co', nom='ZACC14 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestSelector(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_client_entreprise_sans_ice_signale(self):
        Client.objects.create(
            company=self.company, nom='Client SARL',
            type_client=Client.TypeClient.ENTREPRISE, ice='')
        rapport = compta_selectors.controle_identifiants_tiers(self.company)
        self.assertEqual(len(rapport['clients']), 1)
        self.assertEqual(rapport['clients'][0]['motif'], 'ice_absent')

    def test_client_entreprise_ice_conforme_exclu(self):
        Client.objects.create(
            company=self.company, nom='Client Conforme',
            type_client=Client.TypeClient.ENTREPRISE, ice='001234567000012')
        rapport = compta_selectors.controle_identifiants_tiers(self.company)
        self.assertEqual(rapport['clients'], [])

    def test_particulier_sans_ice_jamais_signale(self):
        Client.objects.create(
            company=self.company, nom='Particulier',
            type_client=Client.TypeClient.PARTICULIER, ice='')
        rapport = compta_selectors.controle_identifiants_tiers(self.company)
        self.assertEqual(rapport['clients'], [])

    def test_fournisseur_ice_court_signale(self):
        Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ICE court', ice='12345')
        rapport = compta_selectors.controle_identifiants_tiers(self.company)
        self.assertEqual(len(rapport['fournisseurs']), 1)
        self.assertEqual(rapport['fournisseurs'][0]['motif'], 'ice_invalide')

    def test_fournisseur_ice_conforme_exclu(self):
        Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Conforme',
            ice='001234567000012')
        rapport = compta_selectors.controle_identifiants_tiers(self.company)
        self.assertEqual(rapport['fournisseurs'], [])

    def test_isolation_societe(self):
        autre = make_company('zacc14-autre', 'Autre Co')
        Client.objects.create(
            company=autre, nom='Autre Client',
            type_client=Client.TypeClient.ENTREPRISE, ice='')
        rapport = compta_selectors.controle_identifiants_tiers(self.company)
        self.assertEqual(rapport['clients'], [])


class TestEndpoint(TestCase):
    def setUp(self):
        self.company = make_company('zacc14-api-co', 'ZACC14 API Co')
        self.user = make_user(self.company, 'zacc14-admin')
        self.api = auth(self.user)
        Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ICE court', ice='999')

    def test_endpoint_json(self):
        resp = self.api.get('/api/django/compta/etats/controle-ice/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['fournisseurs']), 1)

    def test_endpoint_csv(self):
        resp = self.api.get(
            '/api/django/compta/etats/controle-ice/?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'fournisseur', resp.content)
