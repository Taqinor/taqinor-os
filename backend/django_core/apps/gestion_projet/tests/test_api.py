"""Tests API de la Gestion de projet.

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les projets de B), et accès réservé au palier
Administrateur/Responsable (un utilisateur ``normal`` reçoit un 403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Projet

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


class GestionProjetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gestion_projet-a', 'A')
        self.co_b = make_company('gestion_projet-b', 'B')
        self.user_a = make_user(self.co_a, 'gestion_projet-a')
        self.user_b = make_user(self.co_b, 'gestion_projet-b')

    def _payload(self):
        return {'code': 'P-001', 'nom': 'Centrale toiture Casa'}

    def _model_kwargs(self):
        return {'code': 'P-001', 'nom': 'Centrale toiture Casa'}

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Projet.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_list_isolation(self):
        Projet.objects.create(company=self.co_a, **self._model_kwargs())
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gestion_projet-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
