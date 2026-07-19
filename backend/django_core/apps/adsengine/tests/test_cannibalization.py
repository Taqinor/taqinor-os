"""PUB95 — Tests de la détection de cannibalisation (série temporelle simple).

Prouve : (1) le cœur pur ``compare_before_after`` rend un verdict avec intervalle
HONNÊTE (Poisson), et dit « données insuffisantes » sous le plancher / quand les
intervalles se chevauchent ; (2) sur fixtures, une chute nette de l'organique
après un changement de dépense → verdict cannibalisation ; une hausse →
incremental ; (3) le rapport FR est produit.
"""
import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead

from apps.adsengine import cannibalization


class CompareBeforeAfterPureTests(SimpleTestCase):
    def test_insufficient_under_min_leads(self):
        res = cannibalization.compare_before_after(2, 28, 3, 28)
        self.assertTrue(res['insufficient_data'])
        self.assertEqual(res['verdict'], 'insufficient_data')

    def test_clear_drop_is_cannibalisation(self):
        res = cannibalization.compare_before_after(20, 28, 3, 28)
        self.assertEqual(res['verdict'], 'cannibalisation')
        self.assertFalse(res['insufficient_data'])
        # Intervalle honnête présent (jamais un point-estimate sec).
        self.assertEqual(len(res['pre_ci']), 2)
        self.assertLess(res['post_ci'][1], res['pre_ci'][0])

    def test_clear_rise_is_incremental(self):
        res = cannibalization.compare_before_after(3, 28, 20, 28)
        self.assertEqual(res['verdict'], 'incremental')

    def test_overlapping_intervals_are_indeterminate(self):
        res = cannibalization.compare_before_after(8, 28, 10, 28)
        self.assertEqual(res['verdict'], 'indetermine')

    def test_empty_window_is_insufficient(self):
        res = cannibalization.compare_before_after(20, 0, 3, 28)
        self.assertTrue(res['insufficient_data'])


class CannibalizationReportModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cann Co', slug='cann-co')
        self.change_date = datetime.date(2026, 6, 15)

    def _leads(self, canal, count, day):
        """Crée ``count`` leads d'un canal à une date précise (date_creation est
        auto_now_add → repositionné)."""
        when = timezone.make_aware(
            datetime.datetime.combine(day, datetime.time(12, 0)))
        for _ in range(count):
            lead = Lead.objects.create(
                company=self.company, nom='Prospect', canal=canal)
            Lead.objects.filter(pk=lead.pk).update(date_creation=when)

    def test_organic_drop_after_spend_change_flags_cannibalisation(self):
        # 20 leads organiques répartis AVANT, 3 APRÈS le changement de dépense.
        for i in range(20):
            self._leads(Lead.Canal.SITE_WEB, 1,
                        self.change_date - datetime.timedelta(days=1 + i % 27))
        for i in range(3):
            self._leads(Lead.Canal.SITE_WEB, 1,
                        self.change_date + datetime.timedelta(days=i))
        report = cannibalization.cannibalization_report(
            self.company, change_date=self.change_date, window_days=28)
        self.assertEqual(report['verdict'], 'cannibalisation')
        self.assertEqual(report['pre_total'], 20)
        self.assertEqual(report['post_total'], 3)
        self.assertIn('cannibalisation', report['rapport_fr'].lower())

    def test_paid_leads_excluded_from_organic_signal(self):
        # Que des leads PAYANTS → aucun organique/parrainage → insuffisant.
        for i in range(30):
            self._leads(Lead.Canal.META_ADS, 1,
                        self.change_date + datetime.timedelta(days=i % 20 - 10))
        report = cannibalization.cannibalization_report(
            self.company, change_date=self.change_date, window_days=28)
        self.assertTrue(report['insufficient_data'])
        self.assertEqual(report['pre_total'], 0)
        self.assertEqual(report['post_total'], 0)

    def test_referral_counts_toward_organic_signal(self):
        # Le parrainage compte dans le signal organique/parrainage.
        for i in range(15):
            self._leads(Lead.Canal.REFERENCE, 1,
                        self.change_date - datetime.timedelta(days=1 + i))
        for i in range(15):
            self._leads(Lead.Canal.REFERENCE, 1,
                        self.change_date + datetime.timedelta(days=i))
        report = cannibalization.cannibalization_report(
            self.company, change_date=self.change_date, window_days=28)
        self.assertEqual(report['pre_total'], 15)
        self.assertEqual(report['post_total'], 15)
        self.assertFalse(report['insufficient_data'])
