"""Tests des permissions granulaires nommées (NTIDE22).

Ne re-teste PAS chaque comportement métier (déjà couvert par test_actions,
test_dashboard, test_moderation, test_vote, test_export, test_bulk) : vérifie
que les QUATRE gardes nommées (``IdeasSeeAll``/``IdeasVote``/
``IdeasChangeStatus``/``IdeasModerate``) sont bien celles posées sur les
viewsets, et que leur palier par défaut correspond à la spec (Directeur/Admin
pour ``ideas_see_all``, tout connecté pour ``ideas_vote``, Directeur/
Responsable pour ``ideas_change_status`` et ``ideas_moderate``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee
from apps.innovation.permissions import (
    IdeasChangeStatus, IdeasSeeAll, IdeasVote,
)
from apps.innovation.views import IdeeViewSet, VoteIdeeViewSet

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


class NamedPermissionClassesWiredTests(TestCase):
    """Les gardes nommées NTIDE22 sont bien celles déclarées sur les
    viewsets (pas re-substituées par un générique)."""

    def test_ideeviewset_default_is_ideas_vote(self):
        self.assertIn(IdeasVote, IdeeViewSet.permission_classes)

    def test_voteideeviewset_default_is_ideas_vote(self):
        self.assertIn(IdeasVote, VoteIdeeViewSet.permission_classes)

    def test_tableau_bord_uses_ideas_see_all(self):
        view = IdeeViewSet.tableau_bord
        self.assertIn(IdeasSeeAll, view.kwargs['permission_classes'])

    def test_export_xlsx_uses_ideas_see_all(self):
        view = IdeeViewSet.export_xlsx
        self.assertIn(IdeasSeeAll, view.kwargs['permission_classes'])

    def test_bulk_uses_ideas_see_all(self):
        view = IdeeViewSet.bulk
        self.assertIn(IdeasSeeAll, view.kwargs['permission_classes'])

    def test_transitions_use_ideas_change_status(self):
        for name in ('examiner', 'retenir', 'realiser', 'fermer'):
            view = getattr(IdeeViewSet, name)
            self.assertIn(
                IdeasChangeStatus, view.kwargs['permission_classes'],
                f'{name} devrait être gardé par IdeasChangeStatus')


class IdeasSeeAllTierTests(TestCase):
    """``ideas_see_all`` — palier Directeur/Admin par défaut (tableau de
    bord), refusé au palier limité."""

    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide22-a', 'A')
        self.resp_a = make_user(self.co_a, 'ntide22-resp', role='responsable')
        self.normal_a = make_user(self.co_a, 'ntide22-normal', role='normal')

    def test_responsable_allowed_on_tableau_bord(self):
        resp = auth(self.resp_a).get(f'{self.BASE}tableau-bord/')
        self.assertEqual(resp.status_code, 200)

    def test_normal_refused_on_tableau_bord(self):
        resp = auth(self.normal_a).get(f'{self.BASE}tableau-bord/')
        self.assertEqual(resp.status_code, 403)

    def test_normal_refused_on_export_xlsx(self):
        resp = auth(self.normal_a).get(f'{self.BASE}export-xlsx/')
        self.assertEqual(resp.status_code, 403)

    def test_normal_refused_on_bulk(self):
        resp = auth(self.normal_a).post(
            f'{self.BASE}bulk/', {'ids': [1], 'action': 'set_statut'},
            format='json')
        self.assertEqual(resp.status_code, 403)


class IdeasVoteTierTests(TestCase):
    """``ideas_vote`` — tout utilisateur interne connecté, sans palier."""

    def setUp(self):
        self.co_a = make_company('innov-ntide22-vote-a', 'A')
        self.normal_a = make_user(
            self.co_a, 'ntide22-vote-normal', role='normal')
        self.idee = Idee.objects.create(company=self.co_a, titre='Une idée')

    def test_normal_role_can_list(self):
        resp = auth(self.normal_a).get('/api/django/innovation/idees/')
        self.assertEqual(resp.status_code, 200)

    def test_normal_role_can_vote(self):
        resp = auth(self.normal_a).post(
            '/api/django/innovation/votes/', {'idee': self.idee.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class IdeasChangeStatusTierTests(TestCase):
    """``ideas_change_status`` — palier Directeur/Responsable."""

    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide22-cs-a', 'A')
        self.resp_a = make_user(
            self.co_a, 'ntide22-cs-resp', role='responsable')
        self.normal_a = make_user(
            self.co_a, 'ntide22-cs-normal', role='normal')
        self.idee = Idee.objects.create(company=self.co_a, titre='Une idée')

    def test_responsable_allowed_to_examiner(self):
        resp = auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/examiner/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_normal_refused_on_examiner(self):
        resp = auth(self.normal_a).post(f'{self.BASE}{self.idee.id}/examiner/')
        self.assertEqual(resp.status_code, 403)


class IdeasModerateTierTests(TestCase):
    """``ideas_moderate`` — palier Directeur/Responsable (masquer)."""

    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide22-mod-a', 'A')
        self.resp_a = make_user(
            self.co_a, 'ntide22-mod-resp', role='responsable')
        self.normal_a = make_user(
            self.co_a, 'ntide22-mod-normal', role='normal')
        self.idee = Idee.objects.create(company=self.co_a, titre='Une idée')

    def test_responsable_allowed_to_masquer(self):
        resp = auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/masquer/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_normal_refused_on_masquer(self):
        resp = auth(self.normal_a).post(f'{self.BASE}{self.idee.id}/masquer/')
        self.assertEqual(resp.status_code, 403)
