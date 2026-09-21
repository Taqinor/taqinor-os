"""Tests de la déduplication de suggestions (NTIDE20).

Couvre : recherche simple titre+description, top 3 par votes, empty q → [],
isolation multi-société, exclusion des brouillons d'autrui et des idées
masquées.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='normal')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DedupIdeeTests(TestCase):
    BASE = '/api/django/innovation/idees/similaires/'

    def setUp(self):
        self.co_a = make_company('innov-dedup-a', 'A')
        self.co_b = make_company('innov-dedup-b', 'B')
        self.user_a = make_user(self.co_a, 'innov-dedup-a')
        self.user_b = make_user(self.co_b, 'innov-dedup-b')

    def test_matches_titre(self):
        Idee.objects.create(company=self.co_a, titre='Ajouter un export PDF')
        resp = auth(self.user_a).get(self.BASE, {'q': 'export'})
        self.assertEqual(resp.status_code, 200)
        titres = [r['titre'] for r in resp.data['results']]
        self.assertIn('Ajouter un export PDF', titres)

    def test_matches_description(self):
        Idee.objects.create(
            company=self.co_a, titre='X', description='Concerne le module SAV')
        resp = auth(self.user_a).get(self.BASE, {'q': 'SAV'})
        self.assertEqual(len(resp.data['results']), 1)

    def test_empty_q_returns_empty(self):
        Idee.objects.create(company=self.co_a, titre='Une idée')
        resp = auth(self.user_a).get(self.BASE, {'q': ''})
        self.assertEqual(resp.data['results'], [])

    def test_limited_to_top_3_by_votes(self):
        for i, votes in enumerate([1, 5, 3, 9, 2]):
            Idee.objects.create(
                company=self.co_a, titre=f'Export idée {i}', votes_count=votes)
        resp = auth(self.user_a).get(self.BASE, {'q': 'export'})
        results = resp.data['results']
        self.assertEqual(len(results), 3)
        self.assertEqual([r['votes_count'] for r in results], [9, 5, 3])

    def test_isolated_per_company(self):
        Idee.objects.create(company=self.co_b, titre='Export côté B')
        resp = auth(self.user_a).get(self.BASE, {'q': 'export'})
        self.assertEqual(resp.data['results'], [])

    def test_excludes_others_drafts(self):
        other = make_user(self.co_a, 'innov-dedup-other')
        Idee.objects.create(
            company=self.co_a, titre='Export brouillon', auteur=other, draft=True)
        resp = auth(self.user_a).get(self.BASE, {'q': 'export'})
        self.assertEqual(resp.data['results'], [])

    def test_excludes_masquees(self):
        Idee.objects.create(
            company=self.co_a, titre='Export masqué', archived=True)
        resp = auth(self.user_a).get(self.BASE, {'q': 'export'})
        self.assertEqual(resp.data['results'], [])
