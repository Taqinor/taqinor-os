"""AGEN8 — Tests du rayon d'explosion (budget test + auto-pause maison).

Prouve (dd-assumption-engine §10.2 point 5) :
  * le budget test est PUR : sous le budget → hors bandit ; budget purgé +
    approuvé → éligible ; budget purgé mais REFUSÉ → hors bandit ; statut inconnu
    → hors bandit (jamais « OK » assumé) ;
  * ``poll_and_autopause`` : une désapprobation simulée → PAUSE (client gardé
    PAUSED-only) + bras retiré + EngineAction auto + alerte 🔴, dans UN cycle ;
  * un statut OK ne déclenche jamais de pause ;
  * sans client, le bras est quand même retiré + alerte (jamais d'échec muet).
"""
import os
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import blast_radius as br
from apps.adsengine.models import (
    AdMirror, ArmDailyStat, CreativeAsset, EngineAction, EngineAlert,
    Experiment, ExperimentArm,
)


class TestBudgetPureTests(SimpleTestCase):
    def test_under_budget_not_cleared(self):
        self.assertFalse(br.has_cleared_test_budget(10, budget_mad=30))

    def test_at_budget_cleared(self):
        self.assertTrue(br.has_cleared_test_budget(30, budget_mad=30))

    def test_can_enter_requires_budget_and_approval(self):
        # Budget purgé + statut actif → éligible.
        self.assertTrue(br.can_enter_bandit(50, status='ACTIVE', budget_mad=30))
        # Sous budget → jamais, même si actif.
        self.assertFalse(br.can_enter_bandit(5, status='ACTIVE', budget_mad=30))
        # Budget purgé mais REFUSÉ → hors bandit.
        self.assertFalse(
            br.can_enter_bandit(50, status='DISAPPROVED', budget_mad=30))
        # Statut inconnu → jamais « OK » assumé.
        self.assertFalse(br.can_enter_bandit(50, status='', budget_mad=30))

    def test_budget_from_env(self):
        with patch.dict(os.environ, {'ADSENGINE_TEST_BUDGET_MAD': '50'}):
            self.assertEqual(br.test_budget_mad(), Decimal('50'))
        with patch.dict(os.environ, {'ADSENGINE_TEST_BUDGET_MAD': 'oops'}):
            self.assertEqual(br.test_budget_mad(), br.DEFAULT_TEST_BUDGET_MAD)


class AutoPauseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='B Co', slug='b-co')
        self.asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.EXPLAINER, policy_stamp={})
        self.exp = Experiment.objects.create(company=self.company, name='E')
        self.arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.exp,
            creative_asset=self.asset, label='A', ad_id='ad-7', is_active=True)

    def _lookup(self, status, reason=''):
        return lambda ad_id: (status, reason)

    def test_disapproval_pauses_within_one_cycle(self):
        client = Mock()
        result = br.poll_and_autopause(
            self.company, client=client,
            status_lookup=self._lookup('DISAPPROVED', 'texte non conforme'))
        self.assertEqual(result, {'polled': 1, 'paused': 1, 'alerted': 1})
        # PAUSE réelle, gardée PAUSED-only.
        client.update_status_paused.assert_called_once_with(
            object_id='ad-7', level='ad')
        # Bras retiré du bandit.
        self.arm.refresh_from_db()
        self.assertFalse(self.arm.is_active)
        # EngineAction auto + alerte 🔴.
        act = EngineAction.objects.get(kind=EngineAction.Kind.PAUSE)
        self.assertTrue(act.auto)
        self.assertEqual(act.status, EngineAction.Statut.APPROUVEE)
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company, severity='critical').exists())

    def test_ok_status_never_pauses(self):
        client = Mock()
        result = br.poll_and_autopause(
            self.company, client=client, status_lookup=self._lookup('ACTIVE'))
        self.assertEqual(result, {'polled': 1, 'paused': 0, 'alerted': 0})
        client.update_status_paused.assert_not_called()
        self.arm.refresh_from_db()
        self.assertTrue(self.arm.is_active)

    def test_unknown_status_never_pauses(self):
        # Statut vide/inconnu → jamais de pause spéculative.
        result = br.poll_and_autopause(
            self.company, client=Mock(), status_lookup=self._lookup(''))
        self.assertEqual(result['paused'], 0)
        self.assertEqual(result['alerted'], 0)

    def test_without_client_still_deactivates_and_alerts(self):
        result = br.poll_and_autopause(
            self.company, client=None,
            status_lookup=self._lookup('WITH_ISSUES'))
        self.assertEqual(result['alerted'], 1)
        self.assertEqual(result['paused'], 0)  # pas de client → pas d'appel réel
        self.arm.refresh_from_db()
        self.assertFalse(self.arm.is_active)

    def test_default_lookup_reads_admirror(self):
        AdMirror.objects.create(
            company=self.company, meta_id='ad-7', status='REJECTED')
        result = br.poll_and_autopause(self.company, client=Mock())
        self.assertEqual(result['alerted'], 1)


class EligibilityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EL Co', slug='el-co')
        self.asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.EXPLAINER, policy_stamp={})
        self.exp = Experiment.objects.create(company=self.company, name='E')
        self.arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.exp,
            creative_asset=self.asset, label='A', ad_id='ad-3', is_active=True)

    def test_arm_spend_sums_daily_stats(self):
        import datetime
        ArmDailyStat.objects.create(
            company=self.company, arm=self.arm,
            date=datetime.date(2026, 1, 1), spend=Decimal('12'))
        ArmDailyStat.objects.create(
            company=self.company, arm=self.arm,
            date=datetime.date(2026, 1, 2), spend=Decimal('20'))
        self.assertEqual(br.arm_spend_mad(self.company, self.arm), Decimal('32'))

    def test_eligible_only_after_budget_and_approval(self):
        import datetime
        # Sous budget → non éligible.
        ArmDailyStat.objects.create(
            company=self.company, arm=self.arm,
            date=datetime.date(2026, 1, 1), spend=Decimal('5'))
        lookup = lambda ad_id: ('ACTIVE', '')  # noqa: E731
        self.assertEqual(
            br.eligible_arms_for_bandit(self.company, status_lookup=lookup), [])
        # Budget purgé + actif → éligible.
        ArmDailyStat.objects.create(
            company=self.company, arm=self.arm,
            date=datetime.date(2026, 1, 2), spend=Decimal('40'))
        self.assertEqual(
            br.eligible_arms_for_bandit(self.company, status_lookup=lookup),
            [self.arm])
