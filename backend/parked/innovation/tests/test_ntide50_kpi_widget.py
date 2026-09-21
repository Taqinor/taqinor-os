"""Tests du widget « Idées cette semaine » (NTIDE50).

Couvre : ``selectors.kpi_innovation`` (compte de la semaine + top idée
votée, tuiles normalisées id/label/valeur), la déclaration comme provider
KPI fédéré (ARC40, ``platform.py``), et l'endpoint fédéré
``GET /reporting/reports/kpi-federes/`` (drill-down /innovation/idees,
consommé côté client)."""
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


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KpiInnovationSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide50-a', 'A')

    def test_no_ideas_this_week(self):
        tuiles = selectors.kpi_innovation(self.co_a)
        ids = {t['id'] for t in tuiles}
        self.assertIn('innovation_idees_semaine', ids)
        self.assertNotIn('innovation_top_idee_semaine', ids)
        compte = next(t for t in tuiles if t['id'] == 'innovation_idees_semaine')
        self.assertEqual(compte['valeur'], 0)

    def test_counts_and_top_vote(self):
        Idee.objects.create(company=self.co_a, titre='Idée A', votes_count=5)
        Idee.objects.create(company=self.co_a, titre='Idée B', votes_count=2)
        tuiles = selectors.kpi_innovation(self.co_a)
        compte = next(t for t in tuiles if t['id'] == 'innovation_idees_semaine')
        self.assertEqual(compte['valeur'], 2)
        top = next(t for t in tuiles if t['id'] == 'innovation_top_idee_semaine')
        self.assertEqual(top['valeur'], 5)
        self.assertIn('Idée A', top['label'])

    def test_old_idea_excluded(self):
        ancienne = timezone.now() - timedelta(days=10)
        idee = Idee.objects.create(company=self.co_a, titre='Vieille idée')
        Idee.objects.filter(pk=idee.pk).update(created_at=ancienne)
        tuiles = selectors.kpi_innovation(self.co_a)
        compte = next(t for t in tuiles if t['id'] == 'innovation_idees_semaine')
        self.assertEqual(compte['valeur'], 0)

    def test_draft_and_archived_excluded(self):
        Idee.objects.create(company=self.co_a, titre='Brouillon', draft=True)
        Idee.objects.create(company=self.co_a, titre='Masquée', archived=True)
        tuiles = selectors.kpi_innovation(self.co_a)
        compte = next(t for t in tuiles if t['id'] == 'innovation_idees_semaine')
        self.assertEqual(compte['valeur'], 0)

    def test_tiles_shape(self):
        Idee.objects.create(company=self.co_a, titre='Idée')
        for t in selectors.kpi_innovation(self.co_a):
            self.assertIn('id', t)
            self.assertIn('label', t)
            self.assertIn('valeur', t)


class KpiInnovationPlatformRegistrationTests(TestCase):
    def test_declared_as_kpi_provider(self):
        from apps.innovation.platform import PLATFORM
        self.assertIn(
            'apps.innovation.selectors.kpi_innovation',
            PLATFORM['kpi_providers'])


class KpiFederesEndpointTests(TestCase):
    BASE = '/api/django/reporting/reports/kpi-federes/'

    def setUp(self):
        self.co_a = make_company('innov-ntide50-ep-a', 'A')
        self.admin = make_user(self.co_a, 'ntide50-ep-admin', role_legacy='admin')
        Idee.objects.create(company=self.co_a, titre='Idée fédérée')

    def test_innovation_tile_appears_in_federated_endpoint(self):
        resp = auth(self.admin).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {t['id'] for t in resp.data['tuiles']}
        self.assertIn('innovation_idees_semaine', ids)
