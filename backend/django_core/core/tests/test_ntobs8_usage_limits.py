"""NTOBS8 — page « Limites & usage » unifiée (lecture seule, aucun nouveau
compteur stocké)."""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.parametres.models import CompanyProfile

from core import usage_limits
from core.models import ApiUsageRecord

User = get_user_model()
# Résolu par nom (jamais un import statique d'apps.publicapi, non-fondation) :
# core reste une couche de base même en test — même patron
# que core.tests.test_rls_cross_tenant_denial (AUD422, ".importlinter").
ApiKey = django_apps.get_model('publicapi', 'ApiKey')


class UsageApiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs8b')

    def test_aggregates_requests_per_key_this_month(self):
        key = ApiKey.objects.create(
            company=self.company, label='Intégration ERP',
            key_hash='hash-ntobs8-1', prefix='tqk_a1')
        ApiUsageRecord.objects.create(
            company=self.company, api_key=key,
            jour=timezone.now().date(), nb_requetes=42)

        res = usage_limits._usage_api(self.company)
        self.assertEqual(res['utilise'], 42)
        self.assertEqual(len(res['par_cle']), 1)
        self.assertEqual(res['par_cle'][0]['cle'], 'Intégration ERP')
        self.assertEqual(res['par_cle'][0]['requetes'], 42)


class UsageUtilisateursTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs8c')

    def test_counts_active_users_against_plan_limit(self):
        User.objects.create_user('u1', password='x', company=self.company)
        User.objects.create_user('u2', password='x', company=self.company)
        inactif = User.objects.create_user(
            'u3', password='x', company=self.company)
        inactif.is_active = False
        inactif.save(update_fields=['is_active'])
        CompanyProfile.objects.create(company=self.company, nb_sieges_max=5)

        res = usage_limits._usage_utilisateurs(self.company)
        self.assertEqual(res['utilise'], 2)
        self.assertEqual(res['limite'], 5)

    def test_no_profile_means_illimite(self):
        User.objects.create_user('u1', password='x', company=self.company)
        res = usage_limits._usage_utilisateurs(self.company)
        self.assertIsNone(res['limite'])


class UsageSummaryTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs8d')

    def test_returns_at_least_three_real_resources(self):
        summary = usage_limits.usage_summary(self.company)
        self.assertGreaterEqual(len(summary['ressources']), 3)

    def test_import_csv_constant_always_present(self):
        summary = usage_limits.usage_summary(self.company)
        noms = [r['nom'] for r in summary['ressources']]
        self.assertIn('Taille max import CSV/XLSX', noms)


class UsageLimitesEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs8e')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_endpoint_returns_scoped_usage(self):
        resp = self.client.get('/api/django/core/usage-limites/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('ressources', resp.data)

    def test_requires_authentication(self):
        resp = APIClient().get('/api/django/core/usage-limites/')
        self.assertEqual(resp.status_code, 401)
