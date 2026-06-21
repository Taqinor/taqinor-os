"""Tests API de la Gestion documentaire (GED).

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les documents de B), et accès réservé au palier
Administrateur/Responsable (un rôle normal reçoit 403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.ged.models import Document

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


class GedApiTests(TestCase):
    BASE = '/api/django/ged/documents/'

    def setUp(self):
        self.co_a = make_company('ged-a', 'A')
        self.co_b = make_company('ged-b', 'B')
        self.user_a = make_user(self.co_a, 'ged-a')
        self.user_b = make_user(self.co_b, 'ged-b')

    def _payload(self):
        return {'titre': 'Contrat client'}

    def _model_kwargs(self):
        return {'titre': 'Contrat client'}

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Document.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        # created_by est posé côté serveur.
        self.assertEqual(obj.created_by, self.user_a)

    def test_list_isolation(self):
        Document.objects.create(company=self.co_a, **self._model_kwargs())
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'ged-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
