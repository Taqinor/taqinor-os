"""CIQ643 — plus d'attendu « 1 500 kWh/kWc » inventé.

Sans ``expected_annual_kwh`` semé, aucune alerte de sous-performance : statut
« en attente de référence ». Avec un attendu semé, comportement identique.
"""
import inspect
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import analytics, selectors, services
from apps.monitoring.models import (
    MonitoringConfig, ProductionReading, UnderperformanceFlag,
)
from authentication.models import Company


class TestSansAttenduInvente(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ciq643-co', defaults={'nom': 'CIQ643 Co'})[0]
        client = Client.objects.create(
            company=self.company, nom='C', prenom='T',
            email='ciq643@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CIQ643-1', client=client,
            puissance_installee_kwc=Decimal('5.00'))
        self.today = date(2026, 6, 1)
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=self.today - timedelta(days=10),
            energy_kwh=Decimal('100'), period_days=365)

    def test_sans_attendu_aucun_drapeau_statut_en_attente(self):
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)
        res = services.evaluate_underperformance(
            self.inst, today=self.today)
        self.assertFalse(res['evaluated'])
        self.assertFalse(res['underperforming'])
        self.assertIsNone(res['flag'])
        self.assertEqual(res['data_status'], 'en_attente_reference')
        self.assertEqual(UnderperformanceFlag.objects.count(), 0)

    def test_expected_recent_none_sans_reference(self):
        config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)
        self.assertIsNone(
            services._expected_recent_kwh(self.inst, config, 365))

    def test_attendu_seme_comportement_identique(self):
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('7500'))
        res = services.evaluate_underperformance(
            self.inst, today=self.today)
        self.assertTrue(res['evaluated'])
        self.assertTrue(res['underperforming'])
        self.assertEqual(res['data_status'], 'evaluated')
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)

    def test_om_metrics_sans_reference_pas_de_pr(self):
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)
        m = analytics.om_metrics(self.inst, today=self.today)
        self.assertIsNone(m['pr_pct'])
        self.assertIsNone(m['expected_kwh'])

    def test_constante_supprimee(self):
        for mod in (services, analytics, selectors):
            self.assertNotIn(
                'DEFAULT_PRODUCTIBLE_KWH_KWC', inspect.getsource(mod))
