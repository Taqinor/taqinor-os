"""ASAV70 — un épisode de sous-performance a une fin : quand l'évaluation
devient impossible (aucune donnée, données périmées, référence retirée, site
retiré), le drapeau ouvert est fermé avec le motif « données indisponibles ».

Run :
    python manage.py test apps.monitoring.tests_asav70_fin_episode -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import services
from apps.monitoring.models import (
    MonitoringConfig, ProductionReading, UnderperformanceFlag,
)
from apps.monitoring.selectors import fleet_overview
from authentication.models import Company


class FinEpisodeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav70-co', defaults={'nom': 'ASAV70 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV70')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV70', client=client,
            puissance_installee_kwc=Decimal('5.00'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.today = timezone.localdate()
        for i in range(30):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=self.today - timedelta(days=i), period_days=1,
                energy_kwh=Decimal('5'))
        res = services.evaluate_underperformance(
            self.inst, today=self.today)
        self.assertTrue(res['underperforming'])
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)

    def _drapeau(self):
        return UnderperformanceFlag.objects.get(installation=self.inst)

    def _ferme_avec_motif(self):
        drapeau = self._drapeau()
        self.assertFalse(drapeau.is_open)
        self.assertEqual(drapeau.motif_cloture, 'donnees_indisponibles')
        self.assertTrue(drapeau.note_cloture)
        self.assertIsNotNone(drapeau.date_cloture)

    def test_sans_donnees_ferme(self):
        ProductionReading.objects.filter(installation=self.inst).delete()
        services.evaluate_underperformance(self.inst, today=self.today)
        self._ferme_avec_motif()
        ov = fleet_overview(self.company, today=self.today)
        self.assertEqual(ov['open_alerts'], 0)

    def test_reference_retiree_ferme(self):
        MonitoringConfig.objects.filter(pk=self.config.pk).update(
            expected_annual_kwh=None)
        services.evaluate_underperformance(self.inst, today=self.today)
        self._ferme_avec_motif()

    def test_donnees_perimees_ferme(self):
        services.evaluate_underperformance(
            self.inst, today=self.today + timedelta(days=400))
        self._ferme_avec_motif()

    def test_site_retire_ferme(self):
        Installation.objects.filter(pk=self.inst.pk).update(parc_actif=False)
        self.inst.refresh_from_db()
        services.evaluate_underperformance(self.inst, today=self.today)
        self._ferme_avec_motif()

    def test_nouvel_episode(self):
        ProductionReading.objects.filter(installation=self.inst).delete()
        services.evaluate_underperformance(self.inst, today=self.today)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 0)
        for i in range(30):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=self.today - timedelta(days=i), period_days=1,
                energy_kwh=Decimal('5'))
        services.evaluate_underperformance(self.inst, today=self.today)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(installation=self.inst).count(),
            2)
