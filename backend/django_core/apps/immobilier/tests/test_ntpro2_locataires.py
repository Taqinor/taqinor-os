"""NTPRO2 — Locataires (personnes/sociétés) distincts du CRM.

Couvre : un locataire peut être lié à un client ventes (crm.Client) EXISTANT
sans duplication (résolution email puis téléphone via apps.crm.selectors),
la résolution ne crée jamais un nouveau client, et l'isolation tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.immobilier.models import Locataire
from apps.immobilier.services import resolve_client_ventes_for_locataire

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


class Ntpro2LocatairesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-loc-a', 'Immo Loc A')
        self.co_b = make_company('immo-loc-b', 'Immo Loc B')
        self.admin_a = make_user(self.co_a, 'immo-loc-admin-a')
        self.admin_b = make_user(self.co_b, 'immo-loc-admin-b')

    def test_resolve_links_existing_client_by_email(self):
        client = Client.objects.create(
            company=self.co_a, nom='Bennani', email='bennani@example.com')
        locataire = Locataire.objects.create(
            company=self.co_a, nom='Bennani', email='bennani@example.com')
        client_id = resolve_client_ventes_for_locataire(locataire)
        locataire.refresh_from_db()
        self.assertEqual(client_id, client.id)
        self.assertEqual(locataire.client_ventes_id, client.id)

    def test_resolve_never_creates_duplicate_client(self):
        avant = Client.objects.filter(company=self.co_a).count()
        locataire = Locataire.objects.create(
            company=self.co_a, nom='Introuvable', email='inconnu@example.com')
        client_id = resolve_client_ventes_for_locataire(locataire)
        self.assertIsNone(client_id)
        self.assertEqual(
            Client.objects.filter(company=self.co_a).count(), avant)

    def test_resolve_idempotent_when_already_linked(self):
        client = Client.objects.create(company=self.co_a, nom='Idempotent')
        locataire = Locataire.objects.create(
            company=self.co_a, nom='Idempotent', client_ventes_id=client.id)
        # Aucun email/téléphone à matcher — si l'idempotence ne court-circuitait
        # pas, la résolution renverrait None et écraserait le lien existant.
        client_id = resolve_client_ventes_for_locataire(locataire)
        self.assertEqual(client_id, client.id)

    def test_create_locataire_via_api_resolves_client(self):
        Client.objects.create(
            company=self.co_a, nom='Alaoui', email='alaoui@example.com')
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/locataires/', {
            'nom': 'Alaoui', 'email': 'alaoui@example.com',
            'company': self.co_b.id,  # tentative d'injection — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        locataire = Locataire.objects.get(id=resp.data['id'])
        self.assertEqual(locataire.company_id, self.co_a.id)
        self.assertIsNotNone(locataire.client_ventes_id)

    def test_tenant_isolation(self):
        Locataire.objects.create(company=self.co_a, nom='A')
        Locataire.objects.create(company=self.co_b, nom='B')
        resp = auth(self.admin_a).get('/api/django/immobilier/locataires/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(noms, ['A'])
