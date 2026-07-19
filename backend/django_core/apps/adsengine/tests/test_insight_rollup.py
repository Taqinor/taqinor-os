"""PUB104 — Tests du rollup/archivage mensuel des snapshots d'insight.

Prouve : le rollup agrège le détail quotidien au-delà de N mois (idempotent),
les totaux additifs sont IDENTIQUES avant/après (rollup + détail restant), le
détail récent n'est jamais touché, et le helper combiné reste invariant à
l'archivage. Scoping société.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine.models import (
    AdCampaignMirror, InsightMonthlyRollup, InsightSnapshot,
)
from apps.adsengine.tasks import rollup_insights_monthly, total_spend_and_leads

TODAY = datetime.date(2026, 7, 15)


class RollupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Roll Co', slug='roll-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='C', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _snap(self, day, spend, leads=0):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=day, spend=Decimal(spend), leads_count=leads, results=leads)

    def test_rolls_up_old_months_and_purges(self):
        # 2 jours d'un mois VIEUX (janvier 2025, > 13 mois avant 2026-07).
        self._snap(datetime.date(2025, 1, 5), '100.00', 2)
        self._snap(datetime.date(2025, 1, 20), '50.00', 1)
        # 1 jour RÉCENT (juillet 2026) — jamais agrégé.
        self._snap(datetime.date(2026, 7, 1), '30.00', 1)
        result = rollup_insights_monthly(today=TODAY)
        self.assertEqual(result['rollups'], 1)
        roll = InsightMonthlyRollup.objects.get(
            company=self.company, year=2025, month=1)
        self.assertEqual(roll.spend, Decimal('150.00'))
        self.assertEqual(roll.leads_count, 3)
        # Détail vieux purgé, détail récent conservé.
        self.assertFalse(InsightSnapshot.objects.filter(
            date=datetime.date(2025, 1, 5)).exists())
        self.assertTrue(InsightSnapshot.objects.filter(
            date=datetime.date(2026, 7, 1)).exists())

    def test_totals_identical_before_after(self):
        self._snap(datetime.date(2025, 1, 5), '100.00', 2)
        self._snap(datetime.date(2025, 2, 10), '80.00', 3)
        self._snap(datetime.date(2026, 7, 1), '30.00', 1)
        before = total_spend_and_leads(self.company, self.camp)
        rollup_insights_monthly(today=TODAY)
        after = total_spend_and_leads(self.company, self.camp)
        self.assertEqual(before['spend'], Decimal('210.00'))
        self.assertEqual(after['spend'], before['spend'])
        self.assertEqual(after['leads_count'], before['leads_count'])

    def test_idempotent(self):
        self._snap(datetime.date(2025, 1, 5), '100.00', 2)
        rollup_insights_monthly(today=TODAY)
        # Deuxième passe : plus de détail vieux → aucun nouveau rollup, pas de
        # doublon (contrainte d'unicité) ; total inchangé.
        result2 = rollup_insights_monthly(today=TODAY)
        self.assertEqual(result2['rollups'], 0)
        self.assertEqual(InsightMonthlyRollup.objects.filter(
            company=self.company, year=2025, month=1).count(), 1)

    def test_no_purge_mode_keeps_detail(self):
        self._snap(datetime.date(2025, 1, 5), '100.00', 2)
        rollup_insights_monthly(today=TODAY, purge=False)
        self.assertTrue(InsightSnapshot.objects.filter(
            date=datetime.date(2025, 1, 5)).exists())
        self.assertEqual(InsightMonthlyRollup.objects.count(), 1)

    def test_company_scoped(self):
        other = Company.objects.create(nom='Other', slug='roll-other')
        other_camp = AdCampaignMirror.objects.create(
            company=other, meta_id='x', name='X', status='PAUSED')
        InsightSnapshot.objects.create(
            company=other, content_type=self.ct, object_id=other_camp.pk,
            date=datetime.date(2025, 1, 5), spend=Decimal('999.00'))
        self._snap(datetime.date(2025, 1, 5), '100.00', 2)
        rollup_insights_monthly(today=TODAY)
        mine = InsightMonthlyRollup.objects.get(company=self.company)
        self.assertEqual(mine.spend, Decimal('100.00'))
        theirs = InsightMonthlyRollup.objects.get(company=other)
        self.assertEqual(theirs.spend, Decimal('999.00'))
