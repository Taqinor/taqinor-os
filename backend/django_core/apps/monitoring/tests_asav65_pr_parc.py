"""ASAV65 — le PR du parc ne compte que les systèmes qui ont un attendu
(numérateur ET dénominateur) ; la production totale reste affichée à part.

Run :
    python manage.py test apps.monitoring.tests_asav65_pr_parc -v2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig, ProductionReading
from apps.monitoring.selectors import fleet_overview
from authentication.models import Company

TODAY = date(2026, 10, 8)


class PrParcTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav65-co', defaults={'nom': 'ASAV65 Co'})

    def _systeme(self, ref, *, attendu):
        client = Client.objects.create(
            company=self.company, nom='Client', prenom=ref)
        inst = Installation.objects.create(
            company=self.company, reference=ref, client=client,
            puissance_installee_kwc=Decimal('5.00'))
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=attendu)
        since = TODAY - timedelta(days=365)
        for i in range(366):
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=since + timedelta(days=i), period_days=1,
                energy_kwh=Decimal('27.40'))
        return inst

    def test_pr_parc_sans_attendu_exclu(self):
        avec = self._systeme('ASAV65-A', attendu=Decimal('10000'))
        sans = self._systeme('ASAV65-B', attendu=None)
        ov = fleet_overview(self.company, today=TODAY)
        self.assertAlmostEqual(float(ov['fleet_pr_pct']), 100.0, delta=0.5)
        # La production totale reste celle des deux systèmes.
        self.assertGreater(float(ov['total_production_kwh']), 20000)
        par_id = {s['installation']: s for s in ov['systems']}
        self.assertFalse(par_id[avec.id]['sans_reference'])
        self.assertTrue(par_id[sans.id]['sans_reference'])
        self.assertIsNone(par_id[sans.id]['pr_pct'])
