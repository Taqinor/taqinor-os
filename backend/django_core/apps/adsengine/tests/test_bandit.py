"""ADSENG8 — Tests du bandit beta-binomial (purs, sans base : SimpleTestCase).

Prouve les propriétés dont dépend le moteur de décision :
  * cas dorés : 2/3/4 bras, égalité, gagnant net — le classement de probabilité
    reflète le classement du taux de conversion ;
  * propriétés : les poids somment à 1, monotonie (plus de conversions ⇒ plus de
    probabilité d'être le meilleur) ;
  * déterminisme : mêmes données + même graine ⇒ vecteur identique (auditabilité).

Les valeurs numériques sont estimées Monte-Carlo (K=10 000) ; le ``Generator``
NumPy ne garantit pas un flux binaire identique entre versions, donc on ancre sur
la vraie probabilité analytique avec une tolérance large (≥ l'écart d'estimation
inter-version), jamais sur un flottant codé en dur.
"""
from django.test import SimpleTestCase

from apps.adsengine import bandit


def _arm(impressions, conversions):
    return {'impressions': impressions, 'conversions': conversions}


class PosteriorsTests(SimpleTestCase):
    def test_conjugate_update_beta_1_1_prior(self):
        post = bandit.posteriors([_arm(1000, 20), _arm(1000, 40)])
        # alpha = 1 + conversions ; beta = 1 + (impressions - conversions).
        self.assertEqual(post[0], (1.0 + 20, 1.0 + 980))
        self.assertEqual(post[1], (1.0 + 40, 1.0 + 960))

    def test_informative_prior_is_configurable(self):
        post = bandit.posteriors([_arm(100, 10)], alpha0=5.0, beta0=25.0)
        self.assertEqual(post[0], (5.0 + 10, 25.0 + 90))

    def test_failures_never_negative(self):
        # conversions > impressions (donnée corrompue) ⇒ β borné au prior.
        post = bandit.posteriors([_arm(0, 5)])
        self.assertEqual(post[0], (1.0 + 5, 1.0))

    def test_empty_arms(self):
        self.assertEqual(bandit.posteriors([]), [])


class ProbBestGoldenTests(SimpleTestCase):
    def test_two_arms_clear_winner(self):
        w = bandit.probability_best([_arm(1000, 20), _arm(1000, 40)])
        # Vraie P(bras B meilleur) ≈ 0.9956 (vérifiée K=400k).
        self.assertGreater(w[1], w[0])
        self.assertAlmostEqual(w[1], 0.9956, delta=0.03)

    def test_three_arms_monotone_ranking(self):
        w = bandit.probability_best(
            [_arm(1000, 20), _arm(1000, 30), _arm(1000, 40)])
        self.assertLess(w[0], w[1])
        self.assertLess(w[1], w[2])
        self.assertAlmostEqual(w[2], 0.885, delta=0.04)

    def test_four_arms_monotone_ranking(self):
        w = bandit.probability_best(
            [_arm(1000, 10), _arm(1000, 20), _arm(1000, 30), _arm(1000, 40)])
        self.assertLess(w[0], w[1])
        self.assertLess(w[1], w[2])
        self.assertLess(w[2], w[3])

    def test_tie_splits_evenly(self):
        w = bandit.probability_best([_arm(1000, 30), _arm(1000, 30)])
        self.assertAlmostEqual(w[0], 0.5, delta=0.05)
        self.assertAlmostEqual(w[1], 0.5, delta=0.05)

    def test_net_winner_dominates(self):
        w = bandit.probability_best([_arm(2000, 10), _arm(2000, 200)])
        self.assertAlmostEqual(w[1], 1.0, delta=0.01)


class ProbBestPropertyTests(SimpleTestCase):
    def test_weights_sum_to_one(self):
        for arms in (
            [_arm(1000, 20), _arm(1000, 40)],
            [_arm(500, 10), _arm(800, 30), _arm(1200, 25)],
            [_arm(100, 1), _arm(100, 2), _arm(100, 3), _arm(100, 4)],
        ):
            w = bandit.probability_best(arms)
            self.assertAlmostEqual(float(w.sum()), 1.0, places=9)
            self.assertTrue((w >= 0).all())

    def test_monotonicity_more_conversions_raises_prob_best(self):
        # À impressions égales, augmenter les conversions d'un bras ne peut
        # qu'augmenter sa probabilité d'être le meilleur.
        base = bandit.probability_best([_arm(1000, 20), _arm(1000, 30)])
        better = bandit.probability_best([_arm(1000, 20), _arm(1000, 45)])
        self.assertGreater(better[1], base[1])

    def test_single_arm_is_certain(self):
        w = bandit.probability_best([_arm(1000, 20)])
        self.assertEqual(list(w), [1.0])

    def test_empty_returns_empty(self):
        self.assertEqual(len(bandit.probability_best([])), 0)


class DeterminismTests(SimpleTestCase):
    def test_same_seed_same_result(self):
        arms = [_arm(1000, 20), _arm(1000, 30), _arm(1000, 40)]
        a = bandit.probability_best(arms, seed=7)
        b = bandit.probability_best(arms, seed=7)
        self.assertEqual(list(a), list(b))

    def test_different_seed_may_differ_but_stays_close(self):
        arms = [_arm(1000, 20), _arm(1000, 40)]
        a = bandit.probability_best(arms, seed=1)
        b = bandit.probability_best(arms, seed=2)
        # Estiment la même vraie probabilité : proches malgré des graines
        # différentes (bruit Monte-Carlo borné).
        self.assertAlmostEqual(a[1], b[1], delta=0.03)
