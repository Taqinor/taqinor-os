"""ADSENG27 — Tests de la gestion du backlog créatif.

Prouve : le calcul du runway (semaines au rythme du plan), l'alerte « backlog
bas » sous 3 semaines, le plancher de diversité (≥4 accroches distinctes / 3
mois — 12 recombinaisons d'une seule accroche ≠ diversité), et la file ordonnée
par campagne cible.
"""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.adsengine import backlog
from apps.adsengine.models import (
    AdCampaignMirror, CreativeAsset, CreativeBacklogItem,
)

TODAY = datetime.date(2026, 7, 13)


class BacklogTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bk Co', slug='bk-co')

    def _item(self, *, hook_id='H1', earliest=None, campaign=None,
              seasonal='', passed=True):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            hook_id=hook_id,
            policy_stamp={'passed': passed} if passed else {})
        return CreativeBacklogItem.objects.create(
            company=self.company, asset=asset, target_campaign=campaign,
            earliest_date=earliest, seasonal_tag=seasonal,
            status=CreativeBacklogItem.Statut.EN_FILE)

    def test_runway_counts_ready_items_over_rate(self):
        for i in range(5):
            self._item(hook_id=f'H{i}')
        # 5 items prêts, rythme 1/semaine → 5 semaines de runway.
        self.assertEqual(
            backlog.compute_runway(self.company, weekly_rate=1, today=TODAY),
            5.0)

    def test_future_dated_items_not_counted_in_runway(self):
        self._item(earliest=TODAY + datetime.timedelta(days=30))
        self._item(earliest=None)  # prêt maintenant
        self.assertEqual(
            backlog.compute_runway(self.company, weekly_rate=1, today=TODAY),
            1.0)

    def test_low_backlog_alert_under_three_weeks(self):
        # 2 items prêts, rythme 1/sem → 2 semaines < 3 → alerte.
        self._item(hook_id='H1')
        self._item(hook_id='H2')
        self.assertTrue(backlog.is_backlog_low(self.company, today=TODAY))
        alert = backlog.backlog_alert(self.company, today=TODAY)
        self.assertTrue(alert['should_alert'])
        self.assertTrue(alert['backlog_low'])
        self.assertIn('Backlog bas', alert['message'])

    def test_healthy_backlog_no_low_alert(self):
        # 6 accroches distinctes, 6 items → runway 6 sem, diversité OK.
        for i in range(6):
            self._item(hook_id=f'H{i}')
        self.assertFalse(backlog.is_backlog_low(self.company, today=TODAY))
        alert = backlog.backlog_alert(self.company, today=TODAY)
        self.assertFalse(alert['should_alert'])

    def test_diversity_floor_false_diversity_single_hook(self):
        # 12 items MAIS une seule accroche → fausse diversité (1 < 4).
        for _ in range(12):
            self._item(hook_id='H_SAME')
        self.assertEqual(backlog.hook_diversity(self.company, today=TODAY), 1)
        self.assertFalse(
            backlog.meets_diversity_floor(self.company, today=TODAY))

    def test_diversity_floor_met_with_four_distinct_hooks(self):
        for i in range(4):
            self._item(hook_id=f'H{i}')
        self.assertEqual(backlog.hook_diversity(self.company, today=TODAY), 4)
        self.assertTrue(
            backlog.meets_diversity_floor(self.company, today=TODAY))

    def test_queue_for_campaign_ordered_by_earliest_then_seasonal(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1')
        self._item(hook_id='A', earliest=datetime.date(2026, 8, 1),
                   campaign=camp, seasonal='ete')
        self._item(hook_id='B', earliest=datetime.date(2026, 7, 1),
                   campaign=camp, seasonal='rentree')
        queue = backlog.queue_for_campaign(self.company, camp, today=TODAY)
        self.assertEqual(len(queue), 2)
        # Le plus tôt (2026-07-01) d'abord.
        self.assertEqual(queue[0].earliest_date, datetime.date(2026, 7, 1))

    def test_ready_count_ready_only_excludes_unvalidated(self):
        self._item(hook_id='H1', passed=True)
        self._item(hook_id='H2', passed=False)
        self.assertEqual(
            backlog.ready_count(self.company, today=TODAY), 2)
        self.assertEqual(
            backlog.ready_count(self.company, today=TODAY, ready_only=True), 1)
