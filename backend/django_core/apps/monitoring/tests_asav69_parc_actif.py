"""ASAV69 — un système RETIRÉ du parc (`parc_actif=False`) n'est ni évalué ni
signalé (drapeau, ticket SAV) ; ses alertes ne comptent plus au parc.

Run :
    python manage.py test apps.monitoring.tests_asav69_parc_actif -v2
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import (
    MonitoringConfig, MonitoringSettings, ProductionReading,
    UnderperformanceFlag,
)
from apps.monitoring.selectors import fleet_overview
from apps.monitoring.tasks import balayage_quotidien
from apps.sav.models import Ticket
from authentication.models import Company


class ParcActifTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav69-co', defaults={'nom': 'ASAV69 Co'})
        reglages = MonitoringSettings.get(self.company)
        reglages.auto_create_ticket = True
        reglages.save()
        self.today = timezone.localdate()

    def _systeme(self, ref, *, parc_actif):
        client = Client.objects.create(
            company=self.company, nom='Client', prenom=ref)
        inst = Installation.objects.create(
            company=self.company, reference=ref, client=client,
            puissance_installee_kwc=Decimal('5.00'), parc_actif=parc_actif)
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal('12000'))
        for i in range(30):
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=self.today - timedelta(days=i), period_days=1,
                energy_kwh=Decimal('5'))
        return inst

    def test_site_retire_non_evalue(self):
        retire = self._systeme('ASAV69-RETIRE', parc_actif=False)
        actif = self._systeme('ASAV69-ACTIF', parc_actif=True)
        with mock.patch('apps.monitoring.services.sync_system',
                        return_value=(0, 'noop')):
            balayage_quotidien()
        self.assertFalse(UnderperformanceFlag.objects.filter(
            installation=retire).exists())
        self.assertFalse(Ticket.objects.filter(
            client=retire.client).exists())
        self.assertTrue(UnderperformanceFlag.objects.filter(
            installation=actif, is_open=True).exists())
        self.assertTrue(Ticket.objects.filter(client=actif.client).exists())

    def test_open_alerts_filtre(self):
        retire = self._systeme('ASAV69-R2', parc_actif=False)
        actif = self._systeme('ASAV69-A2', parc_actif=True)
        for inst in (retire, actif):
            UnderperformanceFlag.objects.create(
                company=self.company, installation=inst, is_open=True,
                ratio_pct=Decimal('10'))
        ov = fleet_overview(self.company, today=self.today)
        self.assertEqual(ov['open_alerts'], 1)
