"""Tests des votes sur idées (NTIDE2).

Couvre : unicité (idee, votant), incrément/décrément dénormalisé de
``votes_count``, l'auteur ne peut pas voter pour sa propre idée
(« Voter ← auteurs en lecture », NTIDE5), suppression réservée au votant ou à
l'admin, isolation multi-société, et les deux sélecteurs (``recents``/
``mes-idees``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee, VoteIdee

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


class VoteIdeeApiTests(TestCase):
    BASE = '/api/django/innovation/votes/'

    def setUp(self):
        self.co_a = make_company('innov-vote-a', 'A')
        self.co_b = make_company('innov-vote-b', 'B')
        self.author = make_user(self.co_a, 'innov-vote-author')
        self.voter1 = make_user(self.co_a, 'innov-vote-voter1')
        self.voter2 = make_user(self.co_a, 'innov-vote-voter2')
        self.user_b = make_user(self.co_b, 'innov-vote-b-user')
        self.admin_a = make_user(self.co_a, 'innov-vote-admin', role='admin')
        self.idee = Idee.objects.create(
            company=self.co_a, titre='Une idée', auteur=self.author)

    def test_vote_creates_and_increments_count(self):
        resp = auth(self.voter1).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 1)
        vote = VoteIdee.objects.get(idee=self.idee, votant=self.voter1)
        self.assertEqual(vote.company, self.co_a)

    def test_duplicate_vote_rejected(self):
        auth(self.voter1).post(self.BASE, {'idee': self.idee.id}, format='json')
        resp = auth(self.voter1).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 1)

    def test_author_cannot_vote_own_idea(self):
        resp = auth(self.author).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 0)

    def test_vote_cross_company_idee_rejected(self):
        resp = auth(self.user_b).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        self.assertIn(resp.status_code, (400, 403, 404))
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 0)

    def test_destroy_vote_by_owner_decrements(self):
        resp = auth(self.voter1).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        vote_id = resp.data['id']
        resp_del = auth(self.voter1).delete(f'{self.BASE}{vote_id}/')
        self.assertEqual(resp_del.status_code, 204)
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 0)

    def test_destroy_vote_never_goes_negative(self):
        vote = VoteIdee.objects.create(
            company=self.co_a, idee=self.idee, votant=self.voter1)
        # votes_count déjà à 0 (créé directement en base, pas via services.voter).
        auth(self.voter1).delete(f'{self.BASE}{vote.id}/')
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 0)

    def test_destroy_vote_by_other_user_forbidden(self):
        resp = auth(self.voter1).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        vote_id = resp.data['id']
        resp_del = auth(self.voter2).delete(f'{self.BASE}{vote_id}/')
        self.assertEqual(resp_del.status_code, 403)
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.votes_count, 1)

    def test_destroy_vote_by_admin_allowed(self):
        resp = auth(self.voter1).post(
            self.BASE, {'idee': self.idee.id}, format='json')
        vote_id = resp.data['id']
        resp_del = auth(self.admin_a).delete(f'{self.BASE}{vote_id}/')
        self.assertEqual(resp_del.status_code, 204)

    def test_recents_endpoint(self):
        auth(self.voter1).post(self.BASE, {'idee': self.idee.id}, format='json')
        resp = auth(self.voter1).get(f'{self.BASE}recents/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_mes_idees_endpoint(self):
        auth(self.voter1).post(self.BASE, {'idee': self.idee.id}, format='json')
        resp = auth(self.author).get(f'{self.BASE}mes-idees/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['idee'], self.idee.id)

    def test_mes_idees_empty_for_non_author(self):
        auth(self.voter1).post(self.BASE, {'idee': self.idee.id}, format='json')
        resp = auth(self.voter2).get(f'{self.BASE}mes-idees/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)
