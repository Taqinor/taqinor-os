"""Tests des idées « brouillon » (NTIDE18).

Couvre : création avec ``draft=True`` reste invisible des AUTRES utilisateurs
(liste/détail/tableau de bord) mais reste visible de son auteur, ``draft``
non modifiable par PATCH direct, action ``publier`` (réservée à l'auteur, la
rend visible de toute la société), isolation multi-société.
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


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class DraftIdeeTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-draft-a', 'A')
        self.author = make_user(self.co_a, 'innov-draft-author')
        self.other = make_user(self.co_a, 'innov-draft-other')
        self.admin_a = make_user(self.co_a, 'innov-draft-admin', role='admin')

    def test_create_draft_true(self):
        resp = auth(self.author).post(
            self.BASE, {'titre': 'Une idée en cours', 'draft': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Idee.objects.get(id=resp.data['id'])
        self.assertTrue(obj.draft)

    def test_draft_hidden_from_list_for_other_user(self):
        Idee.objects.create(
            company=self.co_a, titre='Brouillon privé', auteur=self.author, draft=True)
        resp = auth(self.other).get(self.BASE)
        self.assertEqual(len(rows(resp)), 0)

    def test_draft_visible_in_list_for_author(self):
        Idee.objects.create(
            company=self.co_a, titre='Brouillon privé', auteur=self.author, draft=True)
        resp = auth(self.author).get(self.BASE)
        self.assertEqual(len(rows(resp)), 1)

    def test_draft_detail_404_for_other_user(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Brouillon privé', auteur=self.author, draft=True)
        resp = auth(self.other).get(f'{self.BASE}{idee.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_draft_excluded_from_dashboard(self):
        Idee.objects.create(
            company=self.co_a, titre='Brouillon privé', auteur=self.author, draft=True)
        Idee.objects.create(company=self.co_a, titre='Publiée')
        resp = auth(self.admin_a).get(f'{self.BASE}tableau-bord/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['par_statut']['total'], 1)

    def test_draft_not_writable_via_patch(self):
        idee = Idee.objects.create(company=self.co_a, titre='X', auteur=self.author)
        resp = auth(self.author).patch(
            f'{self.BASE}{idee.id}/', {'draft': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertFalse(idee.draft)

    def test_publier_by_author_makes_visible(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Brouillon privé', auteur=self.author, draft=True)
        resp = auth(self.author).post(f'{self.BASE}{idee.id}/publier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertFalse(idee.draft)
        resp_other = auth(self.other).get(self.BASE)
        self.assertEqual(len(rows(resp_other)), 1)

    def test_publier_refused_for_non_author(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Brouillon privé', auteur=self.author, draft=True)
        resp = auth(self.admin_a).post(f'{self.BASE}{idee.id}/publier/')
        self.assertEqual(resp.status_code, 403)
        idee.refresh_from_db()
        self.assertTrue(idee.draft)

    def test_create_without_draft_defaults_false(self):
        resp = auth(self.author).post(
            self.BASE, {'titre': 'Idée normale'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Idee.objects.get(id=resp.data['id'])
        self.assertFalse(obj.draft)
