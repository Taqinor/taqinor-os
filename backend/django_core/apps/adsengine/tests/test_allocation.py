"""ADSENG10 — Tests politique d'allocation + kill/promote (purs : SimpleTestCase).

Chaque règle testée isolément (dd-science-core §2.4/§2.5) + propriétés + scénarios
composés :
  * plancher d'exploration = max(20 % budget, 20 MAD) ;
  * allocation MAD somme au budget et respecte le plancher ; cas pathologique
    (plancher inatteignable) ⇒ partage égal ;
  * porte de repondération « 100 impressions/bras » (tout-ou-rien) ;
  * burn-in (≥ 7 j ET ≥ 40 conv) ; kill = burn-in + P(best)<5 % tenu 3 jours ;
  * signal de promotion (P(best)≥80 % ou plafond 4 semaines).
"""
from django.test import SimpleTestCase

from apps.adsengine import allocation


class ExplorationFloorTests(SimpleTestCase):
    def test_percent_wins_on_large_budget(self):
        # 20 % de 500 = 100 > 20 MAD.
        self.assertEqual(allocation.exploration_floor(500), 100.0)

    def test_absolute_min_wins_on_small_budget(self):
        # 20 % de 100 = 20 == plancher dur ; 20 % de 50 = 10 < 20 ⇒ 20.
        self.assertEqual(allocation.exploration_floor(100), 20.0)
        self.assertEqual(allocation.exploration_floor(50), 20.0)

    def test_never_the_growthbook_1pct(self):
        # 1 % de 100 = 1 MAD serait sous le minimum de delivery Meta : le
        # plancher absolu garantit ≥ 20 MAD.
        self.assertGreaterEqual(allocation.exploration_floor(100), 20.0)


class AllocateBudgetTests(SimpleTestCase):
    def test_sums_to_budget_and_respects_floor(self):
        alloc = allocation.allocate_budget([0.1, 0.2, 0.7], 100)
        self.assertAlmostEqual(sum(alloc), 100.0, places=6)
        for a in alloc:
            self.assertGreaterEqual(a, 20.0 - 1e-9)
        # 3 bras à 100 MAD : 60 planchés, 40 répartis ⇒ 20 + 40·w.
        self.assertAlmostEqual(alloc[2], 20 + 40 * 0.7, places=6)

    def test_leader_gets_most(self):
        alloc = allocation.allocate_budget([0.1, 0.9], 100)
        self.assertGreater(alloc[1], alloc[0])

    def test_pathological_floor_even_split(self):
        # 6 bras à 100 MAD : 6·20 = 120 > 100 ⇒ plancher inatteignable ⇒ égal.
        alloc = allocation.allocate_budget([1 / 6] * 6, 100)
        self.assertAlmostEqual(sum(alloc), 100.0, places=6)
        for a in alloc:
            self.assertAlmostEqual(a, 100 / 6, places=6)

    def test_empty(self):
        self.assertEqual(allocation.allocate_budget([], 100), [])

    def test_scales_to_500(self):
        alloc = allocation.allocate_budget([0.5, 0.5], 500)
        self.assertAlmostEqual(sum(alloc), 500.0, places=6)
        # Plancher 20 % de 500 = 100 chacun ; free = 300 réparti 50/50.
        self.assertAlmostEqual(alloc[0], 100 + 150, places=6)


class ReweightGateTests(SimpleTestCase):
    def test_all_arms_above_gate(self):
        self.assertTrue(allocation.can_reweight([100, 250, 900]))

    def test_one_arm_below_blocks(self):
        self.assertFalse(allocation.can_reweight([100, 99, 900]))

    def test_empty_blocks(self):
        self.assertFalse(allocation.can_reweight([]))

    def test_allocate_daily_holds_even_split_before_gate(self):
        # Un bras sous 100 impressions ⇒ partage égal (on ne bouge pas les poids).
        alloc = allocation.allocate_daily([0.1, 0.9], [50, 200], 100)
        self.assertAlmostEqual(alloc[0], 50.0, places=6)
        self.assertAlmostEqual(alloc[1], 50.0, places=6)

    def test_allocate_daily_reweights_after_gate(self):
        alloc = allocation.allocate_daily([0.1, 0.9], [150, 200], 100)
        self.assertGreater(alloc[1], alloc[0])
        self.assertAlmostEqual(sum(alloc), 100.0, places=6)


class BurnInTests(SimpleTestCase):
    def test_needs_both_days_and_conversions(self):
        self.assertTrue(allocation.is_burned_in(7, 40))
        self.assertFalse(allocation.is_burned_in(6, 40))   # trop peu de jours
        self.assertFalse(allocation.is_burned_in(7, 39))   # trop peu de conv
        self.assertFalse(allocation.is_burned_in(30, 10))


class ConsecutiveBelowTests(SimpleTestCase):
    def test_trailing_streak(self):
        self.assertEqual(
            allocation.consecutive_below([0.5, 0.04, 0.03, 0.02], 0.05), 3)

    def test_broken_streak_counts_only_tail(self):
        self.assertEqual(
            allocation.consecutive_below([0.04, 0.5, 0.03], 0.05), 1)

    def test_no_streak(self):
        self.assertEqual(
            allocation.consecutive_below([0.5, 0.6], 0.05), 0)


class KillableTests(SimpleTestCase):
    def test_all_conditions_met(self):
        self.assertTrue(allocation.killable(7, 40, 0.02, 3))

    def test_before_burn_in_never_kills(self):
        # P(best) écrasé mais burn-in non atteint ⇒ jamais de kill.
        self.assertFalse(allocation.killable(6, 40, 0.001, 5))
        self.assertFalse(allocation.killable(7, 39, 0.001, 5))

    def test_prob_above_threshold_never_kills(self):
        self.assertFalse(allocation.killable(30, 200, 0.06, 5))

    def test_streak_too_short_never_kills(self):
        self.assertFalse(allocation.killable(30, 200, 0.02, 2))

    def test_composed_scenario_day_by_day(self):
        # Bras vivant 10 j, 60 conv, P(best) sous 5 % depuis 2 jours puis 3.
        self.assertFalse(allocation.killable(10, 60, 0.02, 2))
        self.assertTrue(allocation.killable(10, 60, 0.02, 3))


class ChallengerPhaseTests(SimpleTestCase):
    def test_advance_on_high_prob(self):
        self.assertTrue(allocation.challenger_phase_complete(0.85, 2))

    def test_advance_on_week_cap(self):
        self.assertTrue(allocation.challenger_phase_complete(0.4, 4))

    def test_hold_when_neither(self):
        self.assertFalse(allocation.challenger_phase_complete(0.5, 3))
