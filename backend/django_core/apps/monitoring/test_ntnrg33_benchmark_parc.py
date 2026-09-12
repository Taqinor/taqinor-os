"""NTNRG33 — Benchmarking inter-sites (PR relatif, classement du parc).

Couvre :
  * un seul système classable → pas de classement trompeur (rang/percentile
    `None`) ;
  * ≥2 systèmes → classement correct (meilleur PR = rang 1, percentile 100) ;
  * un système sans attendu exploitable est EXCLU du classement (jamais un
    PR inventé) ;
  * isolation société (jamais un système d'une autre société dans le
    classement) ;
  * endpoint HTTP.

Run :
    python manage.py test apps.monitoring.test_ntnrg33_benchmark_parc -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig, ProductionReading
from apps.monitoring.selectors import benchmark_parc

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_inst(company, ref):
    client = Client.objects.create(
        company=company, nom='Cli', prenom=ref,
        email=f'{ref.lower()}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        puissance_installee_kwc=Decimal('10'))


class TestBenchmarkParc(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg33-co', defaults={'nom': 'NTNRG33 Co'})
        self.today = date(2026, 6, 30)

    def test_isolated_system_not_ranked(self):
        inst = make_inst(self.company, 'NTNRG33-1')
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal('12000'))
        ProductionReading.objects.create(
            company=self.company, installation=inst,
            date=self.today, period_days=365, energy_kwh=Decimal('9000'))
        result = benchmark_parc(self.company, window_days=365, today=self.today)
        self.assertEqual(result['systems_ranked'], 1)
        self.assertIsNone(result['systems'][0]['rang'])
        self.assertIsNone(result['systems'][0]['percentile'])

    def test_two_systems_ranked_best_first(self):
        good = make_inst(self.company, 'NTNRG33-GOOD')
        bad = make_inst(self.company, 'NTNRG33-BAD')
        MonitoringConfig.objects.create(
            company=self.company, installation=good,
            expected_annual_kwh=Decimal('10000'))
        MonitoringConfig.objects.create(
            company=self.company, installation=bad,
            expected_annual_kwh=Decimal('10000'))
        ProductionReading.objects.create(
            company=self.company, installation=good,
            date=self.today, period_days=365, energy_kwh=Decimal('9500'))
        ProductionReading.objects.create(
            company=self.company, installation=bad,
            date=self.today, period_days=365, energy_kwh=Decimal('5000'))
        result = benchmark_parc(self.company, window_days=365, today=self.today)
        self.assertEqual(result['systems_ranked'], 2)
        systems = {s['installation']: s for s in result['systems']}
        self.assertEqual(systems[good.id]['rang'], 1)
        self.assertEqual(systems[good.id]['percentile'], Decimal('100.00'))
        self.assertEqual(systems[bad.id]['rang'], 2)
        self.assertEqual(systems[bad.id]['percentile'], Decimal('50.00'))

    def test_system_without_expected_is_excluded(self):
        inst_ok = make_inst(self.company, 'NTNRG33-OK')
        inst_sans_attendu = make_inst(self.company, 'NTNRG33-NOEXP')
        MonitoringConfig.objects.create(
            company=self.company, installation=inst_ok,
            expected_annual_kwh=Decimal('10000'))
        # Config sans expected_annual_kwh ET puissance nulle → aucun attendu
        # estimable (`_expected_recent_kwh` no-op).
        MonitoringConfig.objects.create(
            company=self.company, installation=inst_sans_attendu)
        inst_sans_attendu.puissance_installee_kwc = None
        inst_sans_attendu.save(update_fields=['puissance_installee_kwc'])
        ProductionReading.objects.create(
            company=self.company, installation=inst_ok,
            date=self.today, period_days=365, energy_kwh=Decimal('9000'))
        result = benchmark_parc(self.company, window_days=365, today=self.today)
        ids = [s['installation'] for s in result['systems']]
        self.assertIn(inst_ok.id, ids)
        self.assertNotIn(inst_sans_attendu.id, ids)

    def test_isolation_societe(self):
        autre_co, _ = Company.objects.get_or_create(
            slug='ntnrg33-autre-co', defaults={'nom': 'NTNRG33 Autre Co'})
        inst_autre = make_inst(autre_co, 'NTNRG33-AUTRE')
        MonitoringConfig.objects.create(
            company=autre_co, installation=inst_autre,
            expected_annual_kwh=Decimal('10000'))
        ProductionReading.objects.create(
            company=autre_co, installation=inst_autre,
            date=self.today, period_days=365, energy_kwh=Decimal('9000'))
        result = benchmark_parc(self.company, window_days=365, today=self.today)
        self.assertEqual(result['systems_ranked'], 0)


class TestBenchmarkEndpoint(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg33-view-co', defaults={'nom': 'NTNRG33 View Co'})
        self.user = User.objects.create_user(
            username='ntnrg33_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)

    def test_benchmark_endpoint_ok(self):
        r = self.api.get('/api/django/monitoring/configs/benchmark/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('systems_ranked', r.data)
        self.assertIn('systems', r.data)
