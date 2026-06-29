"""Tests FG362 — score de probabilité de gain (win-probability).

Couvre la fonction pure :func:`core.win_probability.win_probability` :
  * monotonicité d'étape : une étape plus avancée → probabilité de base >= ;
  * repli propre : sans feature exploitable, le score = base d'étape statique ;
  * cas terminaux : ``perdu`` → 0.0, ``SIGNED`` → 1.0 (aucun ajustement) ;
  * ajustements continus : fraîcheur, priorité, canal, relances ;
  * bornage strict à ``[0, 1]`` et robustesse aux entrées invalides.

Aucune dépendance à Django/DB — fonction pure (``SimpleTestCase``).
"""
from django.test import SimpleTestCase

from core import win_probability as wp
from core.win_probability import (
    DEFAULT_BASE,
    STAGE_BASE_PROBABILITY,
    WinProbabilityResult,
    base_probability_for_stage,
    win_probability,
)


class BaseProbabilityTests(SimpleTestCase):
    def test_known_stage_keys_match_static_table(self):
        for key, expected in STAGE_BASE_PROBABILITY.items():
            self.assertEqual(base_probability_for_stage(key), expected)

    def test_unknown_stage_falls_back_to_default(self):
        self.assertEqual(base_probability_for_stage('???'), DEFAULT_BASE)
        self.assertEqual(base_probability_for_stage(None), DEFAULT_BASE)

    def test_stage_base_is_monotonic_through_funnel(self):
        # NEW < CONTACTED < QUOTE_SENT < FOLLOW_UP < SIGNED (ordre du funnel).
        order = ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED']
        bases = [base_probability_for_stage(k) for k in order]
        self.assertEqual(bases, sorted(bases))
        # Strictement croissant.
        for a, b in zip(bases, bases[1:]):
            self.assertLess(a, b)


class FallbackTests(SimpleTestCase):
    def test_stage_only_equals_static_base(self):
        for key, expected in STAGE_BASE_PROBABILITY.items():
            if key == 'SIGNED':
                continue  # cas terminal, testé ailleurs
            res = win_probability({'stage': key})
            self.assertIsInstance(res, WinProbabilityResult)
            self.assertTrue(res.used_fallback)
            self.assertAlmostEqual(res.probability, expected, places=4)

    def test_empty_features_uses_default_base(self):
        res = win_probability({})
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.probability, DEFAULT_BASE, places=4)

    def test_none_features_does_not_crash(self):
        res = win_probability(None)
        self.assertAlmostEqual(res.probability, DEFAULT_BASE, places=4)

    def test_non_dict_features_treated_as_empty(self):
        res = win_probability(['not', 'a', 'dict'])
        self.assertAlmostEqual(res.probability, DEFAULT_BASE, places=4)

    def test_unrecognized_feature_values_ignored_keeps_base(self):
        # Priorité/canal inconnus, age absent → aucun ajustement appliqué.
        res = win_probability({
            'stage': 'CONTACTED',
            'priorite': 'inconnue',
            'canal': 'mystere',
        })
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.probability, 0.20, places=4)


class TerminalCaseTests(SimpleTestCase):
    def test_signed_is_one_regardless_of_features(self):
        res = win_probability({
            'stage': 'SIGNED', 'priorite': 'basse', 'canal': 'ads',
            'age_days': 999,
        })
        self.assertEqual(res.probability, 1.0)
        self.assertFalse(res.used_fallback)

    def test_perdu_forces_zero(self):
        res = win_probability({
            'stage': 'FOLLOW_UP', 'perdu': True, 'priorite': 'haute',
        })
        self.assertEqual(res.probability, 0.0)

    def test_perdu_beats_signed_stage(self):
        # Un lead marqué perdu est à 0 même si l'étape est SIGNED — perdu d'abord.
        res = win_probability({'stage': 'SIGNED', 'perdu': True})
        self.assertEqual(res.probability, 0.0)


class FeatureAdjustmentTests(SimpleTestCase):
    def test_high_priority_raises_above_base(self):
        base = win_probability({'stage': 'CONTACTED'}).probability
        raised = win_probability(
            {'stage': 'CONTACTED', 'priorite': 'haute'}).probability
        self.assertGreater(raised, base)

    def test_low_priority_lowers_below_base(self):
        base = win_probability({'stage': 'CONTACTED'}).probability
        lowered = win_probability(
            {'stage': 'CONTACTED', 'priorite': 'basse'}).probability
        self.assertLess(lowered, base)

    def test_referral_canal_beats_cold_purchase_canal(self):
        reco = win_probability(
            {'stage': 'QUOTE_SENT', 'canal': 'recommandation'}).probability
        achat = win_probability(
            {'stage': 'QUOTE_SENT', 'canal': 'achat'}).probability
        self.assertGreater(reco, achat)

    def test_fresh_lead_beats_stale_lead(self):
        fresh = win_probability(
            {'stage': 'FOLLOW_UP', 'age_days': 0}).probability
        stale = win_probability(
            {'stage': 'FOLLOW_UP', 'age_days': 120}).probability
        self.assertGreater(fresh, stale)

    def test_recency_floor_not_breached(self):
        # Même très périmé, la recency ne tombe pas sous le plancher × base.
        res = win_probability({'stage': 'QUOTE_SENT', 'age_days': 10000})
        floor = 0.40 * wp._RECENCY_FLOOR
        self.assertGreaterEqual(res.probability, round(floor, 4) - 1e-9)

    def test_relances_add_capped_bonus(self):
        base = win_probability({'stage': 'CONTACTED'}).probability
        one = win_probability(
            {'stage': 'CONTACTED', 'relances': 1}).probability
        many = win_probability(
            {'stage': 'CONTACTED', 'relances': 50}).probability
        self.assertGreater(one, base)
        self.assertGreater(many, one)
        # Bonus plafonné : 50 relances n'ajoutent pas plus que le cap.
        self.assertLessEqual(many - base, wp._RELANCE_BONUS_CAP + 1e-9)

    def test_marks_used_fallback_false_when_feature_applied(self):
        res = win_probability({'stage': 'NEW', 'priorite': 'haute'})
        self.assertFalse(res.used_fallback)
        self.assertIn('priorite', res.factors)


class ClampAndRobustnessTests(SimpleTestCase):
    def test_probability_never_exceeds_one(self):
        res = win_probability({
            'stage': 'FOLLOW_UP', 'priorite': 'haute',
            'canal': 'recommandation', 'relances': 100, 'age_days': 0,
        })
        self.assertLessEqual(res.probability, 1.0)

    def test_probability_never_below_zero(self):
        res = win_probability({
            'stage': 'COLD', 'priorite': 'basse', 'canal': 'achat',
            'age_days': 365,
        })
        self.assertGreaterEqual(res.probability, 0.0)

    def test_invalid_numeric_features_ignored(self):
        res = win_probability({
            'stage': 'CONTACTED', 'age_days': 'pas-un-nombre',
            'relances': None,
        })
        # age_days illisible → recency ignorée ; relances absent → pas de bonus.
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.probability, 0.20, places=4)

    def test_negative_age_days_ignored(self):
        res = win_probability({'stage': 'CONTACTED', 'age_days': -5})
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.probability, 0.20, places=4)

    def test_priority_case_insensitive(self):
        upper = win_probability(
            {'stage': 'NEW', 'priorite': 'HAUTE'}).probability
        lower = win_probability(
            {'stage': 'NEW', 'priorite': 'haute'}).probability
        self.assertEqual(upper, lower)
