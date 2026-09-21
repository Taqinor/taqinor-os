"""Tests de l'autocomplétion du contexte (NTIDE10).

Couvre : les 5 contextes existants les plus fréquents, contextes vides
ignorés, isolation multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import Idee

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContextesFrequentsTests(TestCase):
    BASE = '/api/django/innovation/idees/contextes/'

    def setUp(self):
        self.co_a = make_company('innov-ctx-a', 'A')
        self.user_a = make_user(self.co_a, 'innov-ctx-user')

    def _seed(self, company, contexte, n):
        for i in range(n):
            Idee.objects.create(
                company=company, titre=f'{contexte}-{i}', contexte=contexte)

    def test_top5_by_frequency(self):
        self._seed(self.co_a, 'SAV', 5)
        self._seed(self.co_a, 'Devis', 4)
        self._seed(self.co_a, 'Stock', 3)
        self._seed(self.co_a, 'Leads', 2)
        self._seed(self.co_a, 'Chantiers', 1)
        self._seed(self.co_a, 'RH', 1)  # 6ᵉ contexte, hors du top 5
        data = selectors.contextes_frequents(self.co_a)
        self.assertEqual(data, ['SAV', 'Devis', 'Stock', 'Leads', 'Chantiers'])

    def test_empty_contexte_ignored(self):
        Idee.objects.create(company=self.co_a, titre='Sans contexte')
        data = selectors.contextes_frequents(self.co_a)
        self.assertEqual(data, [])

    def test_endpoint_scoped_to_company(self):
        co_b = make_company('innov-ctx-b', 'B')
        self._seed(co_b, 'AutreSociete', 3)
        self._seed(self.co_a, 'SAV', 1)
        resp = auth(self.user_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], ['SAV'])
