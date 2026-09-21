"""NTASS1 — App ``assurances`` + modèles ``Assureur``/``Courtier``.

Critère d'acceptation : un admin crée un assureur et un courtier, les deux
apparaissent isolés par société en multi-tenant."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, Courtier

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class AssureurCourtierApiTests(TestCase):
    ASSUREURS = '/api/django/assurances/assureurs/'
    COURTIERS = '/api/django/assurances/courtiers/'

    def setUp(self):
        self.co_a = make_company('assurances-a', 'A')
        self.co_b = make_company('assurances-b', 'B')
        self.user_a = make_user(self.co_a, 'assur-a')
        self.user_b = make_user(self.co_b, 'assur-b')

    def test_create_assureur_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(
            self.ASSUREURS, {'raison_sociale': 'Saham Assurance'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Assureur.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_courtier_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(
            self.COURTIERS,
            {'raison_sociale': 'Courtage Atlas', 'numero_agrement': 'ACAPS-123'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Courtier.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_isolation_between_companies(self):
        Assureur.objects.create(company=self.co_a, raison_sociale='Wafa Assurance')
        Courtier.objects.create(company=self.co_a, raison_sociale='Courtage A')
        api_b = auth(self.user_b)
        self.assertEqual(len(rows(api_b.get(self.ASSUREURS))), 0)
        self.assertEqual(len(rows(api_b.get(self.COURTIERS))), 0)

        api_a = auth(self.user_a)
        self.assertEqual(len(rows(api_a.get(self.ASSUREURS))), 1)
        self.assertEqual(len(rows(api_a.get(self.COURTIERS))), 1)
