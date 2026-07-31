"""Tests de la timeline des changements de statut d'UNE idée (NTIDE53).

Couvre : ``selectors.timeline_idee`` (point de départ implicite « ouvert » à
J+0, un point par transition avec ``jours_depuis_creation``), l'endpoint
``GET /api/django/innovation/idees/<id>/timeline/`` (même palier que le
détail/l'historique — tout utilisateur connecté ayant accès à l'idée),
isolation multi-société (404).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors, services
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


class TimelineIdeeSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide53-a', 'A')
        self.resp_a = make_user(
            self.co_a, 'ntide53-resp', role='responsable')

    def test_starting_point_is_ouvert_at_j0(self):
        idee = Idee.objects.create(company=self.co_a, titre='Une idée')
        points = selectors.timeline_idee(idee)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['statut'], Idee.Statut.OUVERT)
        self.assertEqual(points[0]['jours_depuis_creation'], 0)

    def test_one_point_per_transition_with_day_offset(self):
        idee = Idee.objects.create(company=self.co_a, titre='Une idée')
        Idee.objects.filter(pk=idee.pk).update(
            created_at=timezone.now() - timedelta(days=10))
        idee.refresh_from_db()

        services.transitionner(
            idee, target=Idee.Statut.EXAMINEE, user=self.resp_a)
        services.transitionner(
            idee, target=Idee.Statut.RETENUE, user=self.resp_a)

        points = selectors.timeline_idee(idee)
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0]['statut'], Idee.Statut.OUVERT)
        self.assertEqual(points[1]['statut'], Idee.Statut.EXAMINEE)
        self.assertEqual(points[2]['statut'], Idee.Statut.RETENUE)
        # Les transitions ont eu lieu « aujourd'hui » (10 jours après la
        # création simulée) : le décalage doit être positif et cohérent.
        self.assertEqual(points[1]['jours_depuis_creation'], 10)
        self.assertEqual(points[2]['jours_depuis_creation'], 10)

    def test_isolated_per_idea(self):
        idee1 = Idee.objects.create(company=self.co_a, titre='Une')
        idee2 = Idee.objects.create(company=self.co_a, titre='Autre')
        services.transitionner(
            idee1, target=Idee.Statut.EXAMINEE, user=self.resp_a)
        self.assertEqual(len(selectors.timeline_idee(idee2)), 1)


class TimelineIdeeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide53-api-a', 'A')
        self.co_b = make_company('innov-ntide53-api-b', 'B')
        self.normal_a = make_user(self.co_a, 'ntide53-api-normal')
        self.user_b = make_user(self.co_b, 'ntide53-api-b')
        self.idee = Idee.objects.create(company=self.co_a, titre='Une idée')

    def _url(self, idee):
        return f'/api/django/innovation/idees/{idee.id}/timeline/'

    def test_any_logged_in_user_can_view(self):
        resp = auth(self.normal_a).get(self._url(self.idee))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)

    def test_cross_tenant_404(self):
        resp = auth(self.user_b).get(self._url(self.idee))
        self.assertEqual(resp.status_code, 404)

    def test_anonymous_refused(self):
        resp = APIClient().get(self._url(self.idee))
        self.assertEqual(resp.status_code, 401)
