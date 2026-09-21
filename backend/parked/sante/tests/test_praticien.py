"""NTSAN1 — App `sante` + modèle `Praticien` : CRUD scopé tenant.

Couvre : société posée côté serveur (jamais du corps), isolation entre
sociétés (A ne voit pas les praticiens de B).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Praticien

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class PraticienApiTests(TestCase):
    BASE = '/api/django/sante/praticiens/'

    def setUp(self):
        self.co_a = make_company('sante-a', 'Clinique A')
        self.co_b = make_company('sante-b', 'Clinique B')
        self.user_a = make_user(self.co_a, 'sante-a')
        self.user_b = make_user(self.co_b, 'sante-b')

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE, {'nom': 'Dr. Alami', 'specialite': 'Généraliste'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Praticien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_list_isolation(self):
        Praticien.objects.create(company=self.co_a, nom='Dr. Alami')
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_migration_is_clean(self):
        """Critère d'acceptation NTSAN1 : migration propre (le modèle se crée
        et se récupère sans erreur)."""
        obj = Praticien.objects.create(company=self.co_a, nom='Dr. Bennani')
        self.assertTrue(Praticien.objects.filter(pk=obj.pk).exists())
