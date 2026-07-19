"""PUB93 — Golden tests de la variante bandit à décote exponentielle.

Prouve : (1) flag OFF ⇒ postérieurs **byte-identiques** à ``posteriors`` sur les
totaux cumulés (aucune régression du bandit existant) ; (2) flag ON ⇒ les périodes
RÉCENTES dominent (un bras fatigué récemment perd, même s'il fut bon il y a 6
semaines) ; (3) ``ρ`` respecte la demi-vie ; (4) déterminisme sous graine.
"""
from django.test import SimpleTestCase

from apps.adsengine import bandit


def _bucket(impressions, conversions):
    return {'impressions': impressions, 'conversions': conversions}


def _sum_arm(buckets):
    return {'impressions': sum(b['impressions'] for b in buckets),
            'conversions': sum(b['conversions'] for b in buckets)}


# Deux bras aux MÊMES totaux mais aux dynamiques OPPOSÉES dans le temps :
#  A — excellent tôt, effondré récemment (fatigue) ;
#  B — faible tôt, excellent récemment (montée).
A_SERIES = [_bucket(1000, 80), _bucket(1000, 80),
            _bucket(1000, 10), _bucket(1000, 10)]
B_SERIES = [_bucket(1000, 10), _bucket(1000, 10),
            _bucket(1000, 80), _bucket(1000, 80)]


def _mean(post):
    a, b = post
    return a / (a + b)


class DecayOffByteIdenticalTests(SimpleTestCase):
    def test_off_equals_plain_posteriors_on_totals(self):
        series = [A_SERIES, B_SERIES]
        decayed = bandit.decayed_posteriors(series, decay=False)
        plain = bandit.posteriors([_sum_arm(A_SERIES), _sum_arm(B_SERIES)])
        # Égalité EXACTE (byte-identique) — mêmes flottants, pas d'approximation.
        self.assertEqual(decayed, plain)

    def test_off_two_equal_total_arms_are_equal(self):
        decayed = bandit.decayed_posteriors([A_SERIES, B_SERIES], decay=False)
        self.assertEqual(decayed[0], decayed[1])

    def test_off_matches_posteriors_for_arbitrary_series(self):
        series = [[_bucket(500, 12), _bucket(300, 40), _bucket(700, 3)]]
        decayed = bandit.decayed_posteriors(series, decay=False)
        plain = bandit.posteriors([_sum_arm(series[0])])
        self.assertEqual(decayed, plain)


class DecayOnRecentDominatesTests(SimpleTestCase):
    def test_on_recent_periods_dominate(self):
        series = [A_SERIES, B_SERIES]
        decayed = bandit.decayed_posteriors(
            series, decay=True, half_life_periods=1.0)
        # B (fort récemment) doit dépasser A (fort anciennement) sous décote,
        # alors que leurs totaux sont identiques.
        self.assertGreater(_mean(decayed[1]), _mean(decayed[0]))

    def test_on_probability_best_favours_recent_winner(self):
        series = [A_SERIES, B_SERIES]
        w = bandit.decayed_probability_best(
            series, decay=True, half_life_periods=1.0)
        self.assertGreater(w[1], w[0])

    def test_off_probability_best_is_a_tie(self):
        # Totaux égaux + pas de décote → ~50/50 (le passé lointain compte autant).
        w = bandit.decayed_probability_best([A_SERIES, B_SERIES], decay=False)
        self.assertAlmostEqual(w[0], 0.5, delta=0.06)
        self.assertAlmostEqual(w[1], 0.5, delta=0.06)


class DecayMechanicsTests(SimpleTestCase):
    def test_rho_respects_half_life(self):
        rho = bandit._decay_rho(3.0)
        self.assertAlmostEqual(rho ** 3, 0.5, places=9)

    def test_rho_rejects_non_positive_half_life(self):
        with self.assertRaises(ValueError):
            bandit._decay_rho(0)

    def test_deterministic_under_seed(self):
        series = [A_SERIES, B_SERIES]
        a = bandit.decayed_probability_best(series, decay=True, seed=7)
        b = bandit.decayed_probability_best(series, decay=True, seed=7)
        self.assertEqual(list(a), list(b))
