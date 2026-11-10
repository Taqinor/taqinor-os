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

    def test_pr_parc_releves_en_retard_cent(self):
        """AMON101 — PR système et parc sur la fenêtre COUVERTE de chaque
        système : journaliers au profil jusqu'au 15/10, lus le 15/11 ⇒ PR
        ∈ [99 ; 101] (et non ≈ 93,2) ; un système à 60 % reste < 65 et
        classé dernier."""
        from apps.monitoring.selectors import benchmark_parc
        from apps.monitoring.services import attendu_entre
        quinze = date(2026, 11, 15)
        systemes = {}
        for ref, facteur in (('AMON101-A', 1), ('AMON101-B', 1),
                             ('AMON101-T', Decimal('0.6'))):
            client = Client.objects.create(
                company=self.company, nom='Client', prenom=ref)
            inst = Installation.objects.create(
                company=self.company, reference=ref, client=client,
                puissance_installee_kwc=Decimal('7.00'))
            MonitoringConfig.objects.create(
                company=self.company, installation=inst,
                expected_annual_kwh=Decimal('12000'))
            jour = date(2025, 11, 16)
            while jour <= date(2026, 10, 15):
                ProductionReading.objects.create(
                    company=self.company, installation=inst, date=jour,
                    period_days=1, energy_kwh=(attendu_entre(
                        Decimal('12000'), jour, jour) * facteur).quantize(
                            Decimal('0.01')))
                jour += timedelta(days=1)
            systemes[ref] = inst.id
        ov = fleet_overview(self.company, today=quinze)
        pr = {s['installation']: s['pr_pct'] for s in ov['systems']}
        bench = benchmark_parc(self.company, today=quinze)
        classe = {s['installation']: s for s in bench['systems']}
        for ref in ('AMON101-A', 'AMON101-B'):
            for valeur in (pr[systemes[ref]], classe[systemes[ref]]['pr_pct']):
                self.assertGreaterEqual(float(valeur), 99.0, ref)
                self.assertLessEqual(float(valeur), 101.0, ref)
        temoin = systemes['AMON101-T']
        self.assertLess(float(pr[temoin]), 65.0)
        self.assertEqual(classe[temoin]['rang'], 3)
        # Parc sans le témoin : PR ∈ [99 ; 101].
        Installation.objects.filter(pk=temoin).update(parc_actif=False)
        ov = fleet_overview(self.company, today=quinze)
        self.assertGreaterEqual(float(ov['fleet_pr_pct']), 99.0)
        self.assertLessEqual(float(ov['fleet_pr_pct']), 101.0)
