"""Tests de la timeline « idées par jour » (NTIDE23).

Couvre : agrégation par jour (``selectors.timeline``), filtres statut/
contexte, isolation multi-société, brouillons/masquées exclues (même
patron que le tableau de bord, NTIDE6), accès réservé au palier
Directeur/Admin (``IdeasSeeAll``, NTIDE22).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import Idee

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


class TimelineSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide23-a', 'A')
        self.co_b = make_company('innov-ntide23-b', 'B')

    def test_groups_by_day(self):
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        i1 = Idee.objects.create(company=self.co_a, titre='1')
        i2 = Idee.objects.create(company=self.co_a, titre='2')
        i3 = Idee.objects.create(company=self.co_a, titre='3')
        Idee.objects.filter(pk=i1.pk).update(created_at=today)
        Idee.objects.filter(pk=i2.pk).update(created_at=today)
        Idee.objects.filter(pk=i3.pk).update(created_at=yesterday)
        data = selectors.timeline(self.co_a)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[-1]['date'], today.date().isoformat())
        self.assertEqual(data[-1]['nombre'], 2)

    def test_filters_statut(self):
        Idee.objects.create(company=self.co_a, titre='1', statut=Idee.Statut.OUVERT)
        Idee.objects.create(company=self.co_a, titre='2', statut=Idee.Statut.RETENUE)
        data = selectors.timeline(self.co_a, statut=Idee.Statut.RETENUE)
        self.assertEqual(sum(r['nombre'] for r in data), 1)

    def test_filters_contexte(self):
        Idee.objects.create(company=self.co_a, titre='1', contexte='SAV')
        Idee.objects.create(company=self.co_a, titre='2', contexte='Stock')
        data = selectors.timeline(self.co_a, contexte='sav')
        self.assertEqual(sum(r['nombre'] for r in data), 1)

    def test_excludes_draft_and_archived(self):
        Idee.objects.create(company=self.co_a, titre='brouillon', draft=True)
        Idee.objects.create(company=self.co_a, titre='masquée', archived=True)
        Idee.objects.create(company=self.co_a, titre='normale')
        data = selectors.timeline(self.co_a)
        self.assertEqual(sum(r['nombre'] for r in data), 1)

    def test_isolated_per_company(self):
        Idee.objects.create(company=self.co_b, titre='autre société')
        data = selectors.timeline(self.co_a)
        self.assertEqual(data, [])


class TimelineApiTests(TestCase):
    BASE = '/api/django/innovation/timeline/'

    def setUp(self):
        self.co_a = make_company('innov-ntide23-api-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide23-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'ntide23-normal', role='normal')

    def test_admin_can_view_timeline(self):
        Idee.objects.create(company=self.co_a, titre='X')
        resp = auth(self.admin_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
