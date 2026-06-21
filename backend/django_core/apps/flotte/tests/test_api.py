"""Tests API du module Gestion de flotte (FLOTTE2).

Couvre : société posée côté serveur (jamais lue du corps de requête), isolation
entre sociétés (A ne voit jamais le parc de B), et accès réservé au palier
Administrateur/Responsable (un rôle normal reçoit 403).
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


class FlotteApiTests(TestCase):
    BASE = '/api/django/flotte/vehicules/'

    def setUp(self):
        self.co_a = make_company('flotte-a', 'A')
        self.co_b = make_company('flotte-b', 'B')
        self.user_a = make_user(self.co_a, 'flotte-a')
        self.user_b = make_user(self.co_b, 'flotte-b')

    def _payload(self, immatriculation='A-1234-B'):
        # Corps de création minimal valide (PAS de 'company').
        return {'immatriculation': immatriculation}

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        # Tentative d'injection d'une autre société — doit être ignorée.
        body = dict(self._payload(), company=self.co_b.id)
        resp = api.post(self.BASE, body, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Vehicule.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_list_isolation(self):
        Vehicule.objects.create(
            company=self.co_a, immatriculation='A-0001-A')
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'flotte-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
