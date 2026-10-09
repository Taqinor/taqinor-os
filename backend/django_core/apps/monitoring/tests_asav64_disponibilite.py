"""ASAV64 — la disponibilité se calcule sur l'UNION des intervalles couverts
`[date, date + period_days)`, pas sur le nombre de lignes.

Run :
    python manage.py test apps.monitoring.tests_asav64_disponibilite -v2
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


class DisponibiliteTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav64-co', defaults={'nom': 'ASAV64 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV64')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV64', client=client,
            puissance_installee_kwc=Decimal('7.00'))
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.since = TODAY - timedelta(days=365)

    def _releve(self, jour, periode=1):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst, date=jour,
            energy_kwh=Decimal('10'), period_days=periode)

    def _dispo(self):
        return analytics.om_metrics(
            self.inst, today=TODAY)['availability_pct']

    def test_releves_mensuels(self):
        for i in range(12):
            self._releve(self.since + timedelta(days=30 * i), periode=30)
        self.assertAlmostEqual(float(self._dispo()), 98.63, delta=0.05)

    def test_releves_journaliers(self):
        for i in range(366):
            self._releve(self.since + timedelta(days=i))
        self.assertEqual(self._dispo(), Decimal('100.00'))

    def test_trou_compte(self):
        for i in range(366):
            if 100 <= i < 130:  # trou de 30 jours
                continue
            self._releve(self.since + timedelta(days=i))
        self.assertAlmostEqual(float(self._dispo()), 92.05, delta=0.05)

    def test_chevauchement_non_double_compte(self):
        self._releve(self.since, periode=30)
        self._releve(self.since + timedelta(days=15), periode=30)
        # Union = 45 jours.
        self.assertAlmostEqual(float(self._dispo()), 45 / 365 * 100, delta=0.05)
