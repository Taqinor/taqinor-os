"""ASAV62 — l'attendu de production se calcule sur la période RÉELLEMENT
couverte (borné par la mise en service / le premier relevé) : un système neuf
qui produit le nominal n'est plus « sous-performant ».

Run :
    python manage.py test apps.monitoring.tests_asav62_attendu_periode -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import analytics, services
from apps.monitoring.models import (
    MonitoringConfig, MonitoringSettings, ProductionReading,
    UnderperformanceFlag,
)
from apps.monitoring.report import build_om_report_data
from authentication.models import Company

NOMINAL = Decimal('32.88')  # 12 000 kWh / 365 j


class AttenduPeriodeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav62-co', defaults={'nom': 'ASAV62 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV62')
        self.today = timezone.localdate()
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV62', client=client,
            puissance_installee_kwc=Decimal('7.00'),
            date_mise_en_service=self.today - timedelta(days=29))
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        reglages = MonitoringSettings.get(self.company)
        reglages.auto_create_ticket = True
        reglages.save()

    def _releves(self, kwh_par_jour, jours=30):
        for i in range(jours):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=self.today - timedelta(days=jours - 1 - i),
                energy_kwh=kwh_par_jour, period_days=1)

    def test_systeme_neuf_nominal_sans_drapeau(self):
        self._releves(NOMINAL)
        res = services.evaluate_underperformance(
            self.inst, today=self.today)
        self.assertTrue(res['evaluated'])
        self.assertFalse(res['underperforming'])
        self.assertAlmostEqual(float(res['ratio_pct']), 100.0, delta=2.0)
        self.assertEqual(UnderperformanceFlag.objects.count(), 0)
        metrics = analytics.om_metrics(self.inst, today=self.today)
        self.assertAlmostEqual(float(metrics['pr_pct']), 100.0, delta=2.0)

    def test_rapport_mensuel_pr(self):
        self._releves(NOMINAL)
        data = build_om_report_data(
            self.inst, period='monthly', today=self.today)
        self.assertAlmostEqual(float(data['pr_pct']), 100.0, delta=2.0)

    def test_sous_performance_reelle_signalee(self):
        self._releves(NOMINAL / 2)
        res = services.evaluate_underperformance(
            self.inst, today=self.today)
        self.assertTrue(res['underperforming'])
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)
