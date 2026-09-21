"""WIR77 — le ContratSerializer expose le nom du client lié (client_nom).

Résolu cross-app via ``crm.selectors.client_label`` (jamais un import de
crm.Client). Couvre : nom présent, None sans client, isolation cross-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat
from apps.crm.models import Client

User = get_user_model()

BASE = '/api/django/contrats/contrats/'


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


class Wir77ClientNomTests(TestCase):
    def setUp(self):
        self.co = make_company('wir77', 'Co')
        self.user = make_user(self.co, 'wir77')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Zniber', prenom='Sara')

    def test_client_nom_resolved(self):
        c = Contrat.objects.create(
            company=self.co, objet='Maintenance', client_id=self.client_obj.id)
        resp = auth(self.user).get(f'{BASE}{c.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['client_nom'], 'Sara Zniber')

    def test_client_nom_none_without_client(self):
        c = Contrat.objects.create(company=self.co, objet='Sans client')
        resp = auth(self.user).get(f'{BASE}{c.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['client_nom'])

    def test_client_nom_none_cross_company(self):
        # Un client_id d'une AUTRE société ne fuite pas de nom.
        other_co = make_company('wir77-other', 'Other')
        other_client = Client.objects.create(company=other_co, nom='Etranger')
        c = Contrat.objects.create(
            company=self.co, objet='X', client_id=other_client.id)
        resp = auth(self.user).get(f'{BASE}{c.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['client_nom'])
