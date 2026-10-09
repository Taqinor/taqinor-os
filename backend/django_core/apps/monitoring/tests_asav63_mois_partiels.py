"""ASAV63 — le premier et le dernier mois PARTIELS sont normalisés par jours
couverts avant tout PR mensuel, pente de dégradation et baseline de soiling.

Run :
    python manage.py test apps.monitoring.tests_asav63_mois_partiels -v2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import analytics
from apps.monitoring.models import MonitoringConfig, ProductionReading
from authentication.models import Company

TODAY = date(2026, 10, 8)
NOMINAL = Decimal('32.88')  # 12 000 kWh / 365 j


class MoisPartielsTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav63-co', defaults={'nom': 'ASAV63 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV63')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV63', client=client,
            puissance_installee_kwc=Decimal('7.00'))
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))

    def _releves(self, chute_dernier_mois=None):
        for i in range(366):
            jour = TODAY - timedelta(days=365 - i)
            kwh = NOMINAL
            if chute_dernier_mois and jour.month == 9 and jour.year == 2026:
                kwh = NOMINAL * Decimal('0.8')
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                energy_kwh=kwh, period_days=1)

    def test_nominal_sans_degradation(self):
        self._releves()
        m = analytics.om_metrics(self.inst, today=TODAY)
        self.assertGreaterEqual(float(m['degradation_pct_per_year']), -1.0)
        self.assertLessEqual(float(m['degradation_pct_per_year']), 1.0)
        dernier = m['monthly_pr'][-1]
        self.assertAlmostEqual(float(dernier['pr_pct']), 100.0, delta=2.0)
        self.assertFalse(m['soiling_suspected'])

    def test_nominal_sans_soiling(self):
        self._releves()
        s = analytics.soiling_assessment(self.inst, today=TODAY)
        self.assertFalse(s['recommend_cleaning'])
        self.assertLess(float(s['estimated_soiling_loss_pct']), 5.0)

    def test_vraie_chute_signalee(self):
        self._releves(chute_dernier_mois=True)
        m = analytics.om_metrics(self.inst, today=TODAY)
        septembre = next(p for p in m['monthly_pr'] if p['month'] == '2026-09')
        self.assertAlmostEqual(float(septembre['pr_pct']), 80.0, delta=2.0)
        s = analytics.soiling_assessment(self.inst, today=TODAY)
        # Le dernier mois (1-8 octobre) est nominal ; la chute de septembre
        # reste visible dans la série et dans la baseline.
        self.assertIsNotNone(s['baseline_pr_pct'])
