"""Tests du rôle « Viewer » — lecture seule agrégée (NTIDE49).

Un rôle portant UNIQUEMENT la permission ERP fine ``ideas_agrege_voir``
(``permissions.IDEAS_AGGREGATE_PERMISSION``) :
  * lit les agrégats (tableau de bord idées/campagnes, résumé feedback) ;
  * n'a JAMAIS accès au détail (liste/fiche idée, campagne, feedback) ;
  * ne peut ni voter ni proposer.

Le palier normal existant (Commercial/Technicien/Utilisateur, ``ideas_vote``
= tout connecté) n'est PAS régressé : seul un rôle portant explicitement
``ideas_agrege_voir`` (et rien qui le fasse « responsable »/« admin ») est
restreint."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee
from apps.innovation.permissions import IDEAS_AGGREGATE_PERMISSION
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_viewer(company, username):
    role = Role.objects.create(
        company=company, nom='Viewer', est_systeme=False,
        permissions=[IDEAS_AGGREGATE_PERMISSION])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def make_normal(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='normal')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ViewerAggregateAccessTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide49-a', 'A')
        self.viewer = make_viewer(self.co_a, 'ntide49-viewer')
        Idee.objects.create(company=self.co_a, titre='Une idée')

    def test_viewer_can_read_idees_tableau_bord(self):
        resp = auth(self.viewer).get('/api/django/innovation/idees/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_viewer_can_read_campagnes_tableau_bord(self):
        resp = auth(self.viewer).get('/api/django/innovation/campagnes/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_viewer_can_read_feedback_resume(self):
        resp = auth(self.viewer).get('/api/django/innovation/feedback-resume/')
        self.assertEqual(resp.status_code, 200, resp.data)


class ViewerNoDetailNoVoteNoProposeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide49-b', 'A')
        self.viewer = make_viewer(self.co_a, 'ntide49-viewer-b')
        self.idee = Idee.objects.create(company=self.co_a, titre='Une idée')

    def test_viewer_refused_on_idees_list(self):
        resp = auth(self.viewer).get('/api/django/innovation/idees/')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_refused_on_idee_detail(self):
        resp = auth(self.viewer).get(f'/api/django/innovation/idees/{self.idee.id}/')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_cannot_propose(self):
        resp = auth(self.viewer).post(
            '/api/django/innovation/idees/', {'titre': 'Nouvelle idée'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_cannot_vote(self):
        resp = auth(self.viewer).post(
            '/api/django/innovation/votes/', {'idee': self.idee.id},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_refused_on_campagnes_list(self):
        resp = auth(self.viewer).get('/api/django/innovation/campagnes/')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_refused_on_feedback_list(self):
        resp = auth(self.viewer).get('/api/django/innovation/feedback-produit/')
        self.assertEqual(resp.status_code, 403)


class NormalRoleUnaffectedTests(TestCase):
    """Le palier normal (tout connecté, IsAnyRole) n'est PAS régressé par
    NTIDE49 — seul un rôle portant explicitement ``ideas_agrege_voir`` est
    restreint."""

    def setUp(self):
        self.co_a = make_company('innov-ntide49-c', 'A')
        self.normal = make_normal(self.co_a, 'ntide49-normal-c')

    def test_normal_still_can_list_and_propose(self):
        resp = auth(self.normal).get('/api/django/innovation/idees/')
        self.assertEqual(resp.status_code, 200)
        resp = auth(self.normal).post(
            '/api/django/innovation/idees/', {'titre': 'Idée normale'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_normal_still_refused_on_aggregate(self):
        resp = auth(self.normal).get('/api/django/innovation/idees/tableau-bord/')
        self.assertEqual(resp.status_code, 403)
