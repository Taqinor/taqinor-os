"""Tests de l'autocomplétion auteur (NTIDE54).

Couvre : ``selectors.auteurs_autocomplete`` (filtre ``?q=`` icontains, scopé
société, triée par username) et l'endpoint
``GET /api/django/innovation/idees/auteurs/`` (palier admin/responsable
uniquement — surface d'administration des formulaires de création en masse).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors

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


class AuteursAutocompleteSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide54-a', 'A')
        self.co_b = make_company('innov-ntide54-b', 'B')
        make_user(self.co_a, 'alice')
        make_user(self.co_a, 'albert')
        make_user(self.co_a, 'bob')
        make_user(self.co_b, 'alice-b')

    def test_no_filter_returns_company_users_only(self):
        results = selectors.auteurs_autocomplete(self.co_a)
        usernames = {r['username'] for r in results}
        self.assertEqual(usernames, {'alice', 'albert', 'bob'})

    def test_q_filters_icontains(self):
        results = selectors.auteurs_autocomplete(self.co_a, 'al')
        usernames = {r['username'] for r in results}
        self.assertEqual(usernames, {'alice', 'albert'})

    def test_isolated_per_company(self):
        results = selectors.auteurs_autocomplete(self.co_a, 'alice-b')
        self.assertEqual(results, [])

    def test_limit_respected(self):
        for i in range(15):
            make_user(self.co_a, f'user{i:02d}')
        results = selectors.auteurs_autocomplete(self.co_a, 'user', limit=5)
        self.assertEqual(len(results), 5)


class AuteursAutocompleteApiTests(TestCase):
    BASE = '/api/django/innovation/idees/auteurs/'

    def setUp(self):
        self.co_a = make_company('innov-ntide54-api-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide54-api-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'ntide54-api-normal')

    def test_admin_can_search(self):
        resp = auth(self.admin_a).get(self.BASE, {'q': 'ntide54'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(len(resp.data['results']), 1)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
