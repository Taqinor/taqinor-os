"""Tests API de la Base de connaissances.

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les articles de B), et accès réservé au palier
Administrateur/Responsable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb.models import KbArticle

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


class KbApiTests(TestCase):
    BASE = '/api/django/kb/articles/'

    def setUp(self):
        self.co_a = make_company('kb-a', 'A')
        self.co_b = make_company('kb-b', 'B')
        self.user_a = make_user(self.co_a, 'kb-a')
        self.user_b = make_user(self.co_b, 'kb-b')

    def _payload(self):
        return {'titre': 'Procédure SAV', 'corps': 'Contenu interne.'}

    def _model_kwargs(self):
        return {'titre': 'Procédure SAV', 'corps': 'Contenu interne.'}

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticle.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.auteur, self.user_a)

    def test_list_isolation(self):
        KbArticle.objects.create(company=self.co_a, **self._model_kwargs())
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'kb-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
