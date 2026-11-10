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


def _au_profil(annuel, debut, fin, facteur=1):
    """AMON29 — production nominale de ``[debut, fin]`` au profil mensuel
    du devis, × ``facteur``."""
    return (services.attendu_entre(Decimal(annuel), debut, fin)
            * Decimal(str(facteur))).quantize(Decimal('0.01'))


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
        # AMON29 — journaliers au profil mensuel (``kwh_par_jour / NOMINAL``
        # = part du nominal produite).
        for i in range(jours):
            jour = self.today - timedelta(days=jours - 1 - i)
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                energy_kwh=_au_profil('12000', jour, jour,
                                      kwh_par_jour / NOMINAL),
                period_days=1)

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

    def _systeme(self, ref, annuel, mise_en_service):
        inst = Installation.objects.create(
            company=self.company, reference=ref,
            client=self.inst.client, puissance_installee_kwc=Decimal('5.00'),
            date_mise_en_service=mise_en_service)
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal(annuel))
        return inst

    def _releve(self, inst, jours_avant, facteur=1, periode=30):
        jour = self.today - timedelta(days=jours_avant)
        ProductionReading.objects.create(
            company=self.company, installation=inst, date=jour,
            energy_kwh=_au_profil(
                '9000', jour, jour + timedelta(days=periode - 1), facteur),
            period_days=periode)

    def test_retard_de_saisie_sans_drapeau(self):
        """AMON22 — réel et attendu sur les seuls jours couverts : deux
        mensuels sains saisis avec 15 j de retard ⇒ ≈ 100 %, aucun drapeau ;
        un relevé à cheval sur aujourd'hui ne compte que sa part passée ;
        témoin à la moitié du nominal ⇒ drapeau."""
        inst = self._systeme(
            'CHT-AMON22', '9000', self.today - timedelta(days=75))
        self._releve(inst, 75)
        self._releve(inst, 45)
        res = services.evaluate_underperformance(inst, today=self.today)
        self.assertEqual(res['data_status'], 'evaluated')
        self.assertAlmostEqual(float(res['ratio_pct']), 100.0, delta=1.0)
        self.assertFalse(
            UnderperformanceFlag.objects.filter(installation=inst).exists())
        # Relevé [J−15 ; J+15) : seule la part ≤ aujourd'hui compte (au
        # prorata des jours ; l'écart au profil mensuel reste < 3 points).
        self._releve(inst, 15)
        res = services.evaluate_underperformance(inst, today=self.today)
        self.assertAlmostEqual(float(res['ratio_pct']), 100.0, delta=3.0)
        # Témoin : moitié du nominal ⇒ drapeau.
        temoin = self._systeme(
            'CHT-AMON22-T', '9000', self.today - timedelta(days=75))
        self._releve(temoin, 75, facteur='0.5')
        self._releve(temoin, 45, facteur='0.5')
        res = services.evaluate_underperformance(temoin, today=self.today)
        self.assertTrue(res['underperforming'])
        self.assertTrue(UnderperformanceFlag.objects.filter(
            installation=temoin, is_open=True).exists())

    def test_premier_hiver_au_profil_sans_drapeau(self):
        """AMON29 — l'attendu suit le profil mensuel du devis : un système
        conforme au profil, mis en service le 01/09, n'est pas signalé au
        15/01 ; le même à 70 % du profil l'est (témoin)."""
        from datetime import date

        quinze_janvier = date(2027, 1, 15)
        for ref, facteur, signale in (('CHT-AMON29', 1, False),
                                      ('CHT-AMON29-T', '0.7', True)):
            inst = self._systeme(ref, '12000', date(2026, 9, 1))
            debuts = [date(2026, m, 1) for m in (9, 10, 11, 12)]
            periodes = [(d, (date(d.year + d.month // 12, d.month % 12 + 1, 1)
                             - d).days) for d in debuts]
            periodes.append((date(2027, 1, 1), 14))
            for jour, periode in periodes:
                ProductionReading.objects.create(
                    company=self.company, installation=inst, date=jour,
                    energy_kwh=_au_profil(
                        '12000', jour, jour + timedelta(days=periode - 1),
                        facteur),
                    period_days=periode)
            res = services.evaluate_underperformance(
                inst, today=quinze_janvier)
            self.assertEqual(res['underperforming'], signale, ref)
            if not signale:
                self.assertAlmostEqual(
                    float(res['ratio_pct']), 100.0, delta=1.0)
        # Fenêtre de 365 j pleine : l'attendu est l'annuel (Σ poids = 1).
        self.assertAlmostEqual(float(services.attendu_entre(
            Decimal('12000'), date(2026, 1, 1), date(2026, 12, 31))),
            12000.0, delta=0.5)

    def _mensuels(self, inst, annuel, mois, facteur=1):
        """AMON97 — relevés mensuels au profil, datés du 1er, période =
        jours du mois (2026)."""
        import calendar
        from datetime import date
        for m in mois:
            jour = date(2026, m, 1)
            periode = calendar.monthrange(2026, m)[1]
            ProductionReading.objects.create(
                company=self.company, installation=inst, date=jour,
                energy_kwh=_au_profil(
                    annuel, jour, jour + timedelta(days=periode - 1),
                    facteur),
                period_days=periode)

    def test_rapport_mensuel_releves_mensuels_en_retard(self):
        """AMON97 — PR du rapport mensuel sur la fenêtre COUVERTE : un
        système sain relevé au mois jusqu'en octobre, lu le 15/11, sert
        ≈ 100 % (et non 60,66) ; journaliers sains jusqu'au 15/11, fenêtre
        non bornée : ≈ 100 % (et non 103,79) ; témoin à 60 % : < 65."""
        from datetime import date
        quinze = date(2026, 11, 15)
        sain = self._systeme('CHT-AMON97', '6000', date(2026, 1, 1))
        self._mensuels(sain, '6000', range(1, 11))
        data = build_om_report_data(sain, period='monthly', today=quinze)
        self.assertGreaterEqual(float(data['pr_pct']), 99.0)
        self.assertLessEqual(float(data['pr_pct']), 101.0)
        journaliers = self._systeme('CHT-AMON97-J', '6000', None)
        for i in range(46):
            jour = date(2026, 10, 1) + timedelta(days=i)
            ProductionReading.objects.create(
                company=self.company, installation=journaliers, date=jour,
                energy_kwh=_au_profil('6000', jour, jour), period_days=1)
        data = build_om_report_data(
            journaliers, period='monthly', today=quinze)
        self.assertGreaterEqual(float(data['pr_pct']), 99.0)
        self.assertLessEqual(float(data['pr_pct']), 101.0)
        temoin = self._systeme('CHT-AMON97-T', '6000', date(2026, 1, 1))
        self._mensuels(temoin, '6000', range(1, 11), facteur='0.6')
        data = build_om_report_data(temoin, period='monthly', today=quinze)
        self.assertLess(float(data['pr_pct']), 65.0)
