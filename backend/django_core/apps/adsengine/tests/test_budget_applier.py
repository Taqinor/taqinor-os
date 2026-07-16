"""ADSENG21 — Tests de l'applicateur de budgets ABO (dd-treasury §b).

Prouve : un pas quotidien > 15 % est STRUCTURELLEMENT impossible (``cap_daily_
step`` + ``assert_step_within_cap``) ; les plafonds quotidiens sont inviolables
(bornage à la proposition) ; un budget n'est jamais appliqué à un ad set hors
des miroirs de la société (validation de propriété) ; CBO est refusé sous L'UN
OU L'AUTRE plancher Madgicx (< 8 ad sets OU < 2 semaines de spend consistant) ;
et toutes les propositions restent propose-only (statut ``proposee``).
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import budget_applier, pacing
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, GuardrailConfig,
    InsightSnapshot,
)


class CapDailyStepTests(TestCase):
    def test_step_over_15pct_is_impossible(self):
        # Cible 500 depuis 100 → borné à +15 % = 115 (jamais 500).
        self.assertAlmostEqual(budget_applier.cap_daily_step(100, 500), 115.0)
        # Cible 10 depuis 100 → borné à −15 % = 85.
        self.assertAlmostEqual(budget_applier.cap_daily_step(100, 10), 85.0)

    def test_within_band_target_is_unchanged(self):
        self.assertAlmostEqual(budget_applier.cap_daily_step(100, 110), 110.0)

    def test_zero_current_yields_no_move(self):
        self.assertEqual(budget_applier.cap_daily_step(0, 200), 0)


class StepGuardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='St', slug='st')

    def test_over_cap_raises_step_violation(self):
        with self.assertRaises(budget_applier.BudgetStepViolation):
            budget_applier.assert_step_within_cap(
                100, 130, company=self.company)

    def test_within_cap_passes(self):
        self.assertTrue(budget_applier.assert_step_within_cap(100, 112))

    def test_missing_current_is_inoperative(self):
        with self.assertRaises(budget_applier.guardrails.GuardrailInoperative):
            budget_applier.assert_step_within_cap(None, 100)


class MirrorOwnershipTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Mo', slug='mo')
        self.other = Company.objects.create(nom='Ot', slug='ot')
        AdSetMirror.objects.create(company=self.company, meta_id='as-owned')
        AdSetMirror.objects.create(company=self.other, meta_id='as-foreign')

    def test_owned_adset_passes(self):
        self.assertTrue(
            budget_applier.validate_adset_target(
                self.company, {'adset_id': 'as-owned'}))

    def test_foreign_adset_is_refused(self):
        # L'ad set existe mais appartient à une AUTRE société → refus.
        with self.assertRaises(budget_applier.MirrorOwnershipViolation):
            budget_applier.validate_adset_target(
                self.company, {'adset_id': 'as-foreign'})

    def test_unknown_adset_is_refused(self):
        with self.assertRaises(budget_applier.MirrorOwnershipViolation):
            budget_applier.validate_adset_target(
                self.company, {'adset_id': 'nope'})

    def test_empty_adset_is_refused(self):
        with self.assertRaises(budget_applier.MirrorOwnershipViolation):
            budget_applier.validate_adset_target(self.company, {})


class ProposeBudgetChangeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pb', slug='pb')
        self.cfg = GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=200)
        AdSetMirror.objects.create(company=self.company, meta_id='as1')

    def test_rebalance_caps_step_and_is_propose_only(self):
        action = budget_applier.propose_rebalance_adset_budget(
            self.company, adset_meta_id='as1',
            current_daily_budget_mad=100, target_daily_budget_mad=500,
            reason_fr='Bandit : ensemble A gagnant.', config=self.cfg)
        self.assertEqual(action.kind, pacing.KIND_REBALANCE_ADSET_BUDGET)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        # Borné à +15 % = 115 (< plafond 200) → 11500 centimes.
        self.assertAlmostEqual(action.payload['new_daily_budget_mad'], 115.0)
        self.assertEqual(action.payload['daily_budget'], 11500)

    def test_ceiling_clamps_below_the_step_cap(self):
        # Plafond 108 < pas +15 % (115) → borné au plafond (inviolable).
        cfg = GuardrailConfig.objects.filter(company=self.company).first()
        cfg.daily_budget_ceiling_mad = 108
        cfg.save(update_fields=['daily_budget_ceiling_mad'])
        action = budget_applier.propose_rebalance_adset_budget(
            self.company, adset_meta_id='as1',
            current_daily_budget_mad=100, target_daily_budget_mad=500,
            reason_fr='Bandit.', config=cfg)
        self.assertAlmostEqual(action.payload['new_daily_budget_mad'], 108.0)

    def test_increase_pace_bumps_within_cap(self):
        action = budget_applier.propose_increase_pace(
            self.company, adset_meta_id='as1',
            current_daily_budget_mad=100,
            reason_fr='Sous-rythme : coup de pouce.', config=self.cfg)
        self.assertEqual(action.kind, pacing.KIND_INCREASE_PACE)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        # Défaut = +15 % = 115.
        self.assertAlmostEqual(action.payload['new_daily_budget_mad'], 115.0)

    def test_foreign_target_never_proposed(self):
        with self.assertRaises(budget_applier.MirrorOwnershipViolation):
            budget_applier.propose_rebalance_adset_budget(
                self.company, adset_meta_id='ghost',
                current_daily_budget_mad=100, target_daily_budget_mad=110,
                reason_fr='x', config=self.cfg)


class CboFloorTests(TestCase):
    AS_OF = datetime.date(2026, 7, 20)

    def setUp(self):
        self.company = Company.objects.create(nom='Cbo', slug='cbo')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='camp1')

    def _adset(self, meta_id, *, consistent=False):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id=meta_id, campaign=self.campaign)
        if consistent:
            ct = ContentType.objects.get_for_model(AdSetMirror)
            for i in range(10):  # 10 jours distincts sur les 14 derniers
                InsightSnapshot.objects.create(
                    company=self.company, content_type=ct,
                    object_id=adset.pk,
                    date=self.AS_OF - datetime.timedelta(days=i),
                    spend=Decimal('20'))
        return adset

    def test_below_adset_count_floor_is_refused(self):
        for i in range(5):  # 5 < 8
            self._adset(f'as{i}', consistent=True)
        reason = budget_applier.cbo_floor_reason(
            self.company, 'camp1', as_of=self.AS_OF)
        self.assertIsNotNone(reason)
        self.assertIn('< plancher 8', reason)
        with self.assertRaises(budget_applier.CboFloorViolation):
            budget_applier.assert_cbo_allowed(
                self.company, 'camp1', as_of=self.AS_OF)

    def test_enough_adsets_but_not_consistent_is_refused(self):
        for i in range(8):  # 8 ad sets mais AUCUN spend consistant
            self._adset(f'as{i}', consistent=False)
        reason = budget_applier.cbo_floor_reason(
            self.company, 'camp1', as_of=self.AS_OF)
        self.assertIsNotNone(reason)
        self.assertIn('spend consistant', reason)

    def test_floor_met_allows_and_proposes_only(self):
        for i in range(8):
            self._adset(f'as{i}', consistent=True)
        self.assertIsNone(
            budget_applier.cbo_floor_reason(
                self.company, 'camp1', as_of=self.AS_OF))
        action = budget_applier.propose_enable_cbo(
            self.company, campaign_meta_id='camp1',
            reason_fr='8 ad sets consistants : CBO éligible.',
            as_of=self.AS_OF)
        self.assertEqual(action.kind, pacing.KIND_ENABLE_CBO)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_enable_cbo_below_floor_never_reaches_inbox(self):
        self._adset('as0', consistent=True)  # 1 seul ad set
        with self.assertRaises(budget_applier.CboFloorViolation):
            budget_applier.propose_enable_cbo(
                self.company, campaign_meta_id='camp1',
                reason_fr='x', as_of=self.AS_OF)
        # Aucune action n'a été créée.
        self.assertFalse(
            EngineAction.objects.filter(
                company=self.company, kind=pacing.KIND_ENABLE_CBO).exists())
