"""PUB92 — Golden tests des DEUX règles d'arrêt côte à côte (purs, SimpleTestCase).

Prouve : (1) ``challenger_phase_complete`` reste BYTE-IDENTIQUE (son contrat
P≥80 % OU cap 4 sem est inchangé) ; (2) la NOUVELLE règle à perte espérée
``expected_loss_stop`` arrête tôt une victoire nette et continue sur une vraie
égalité mince ; (3) les deux règles DIVERGENT là où c'est la valeur ajoutée (au
plafond de 4 sem sur une égalité, l'ancienne stoppe, la nouvelle attend).
"""
from django.test import SimpleTestCase

from apps.adsengine import allocation, bandit


def _arm(impressions, conversions):
    return {'impressions': impressions, 'conversions': conversions}


class ChallengerPhaseCompleteUnchangedTests(SimpleTestCase):
    """L'existante reste byte-identique — on ré-affirme son contrat exact."""

    def test_stops_at_80_percent_probability(self):
        self.assertTrue(allocation.challenger_phase_complete(0.80, 0))
        self.assertTrue(allocation.challenger_phase_complete(0.95, 1))

    def test_does_not_stop_below_threshold_before_cap(self):
        self.assertFalse(allocation.challenger_phase_complete(0.79, 0))
        self.assertFalse(allocation.challenger_phase_complete(0.50, 3))

    def test_stops_at_week_cap_regardless_of_probability(self):
        self.assertTrue(allocation.challenger_phase_complete(0.50, 4))
        self.assertTrue(allocation.challenger_phase_complete(0.10, 5))


class ExpectedLossStopGoldenTests(SimpleTestCase):
    def test_clear_winner_stops_early_even_on_thin_data(self):
        # 20 impressions/bras seulement, mais B écrase A → perte espérée quasi
        # nulle → on arrête (stop tôt sur une victoire nette).
        post = bandit.posteriors([_arm(20, 1), _arm(20, 15)])
        res = allocation.expected_loss_stop(post, 100.0, threshold_mad=5.0)
        self.assertTrue(res['should_stop'])
        self.assertLess(res['expected_loss_mad'], 5.0)

    def test_true_tie_on_thin_data_keeps_going(self):
        # Deux bras identiques sur peu de données → postérieurs larges → perte
        # espérée élevée → on CONTINUE (ne stoppe pas une vraie égalité incertaine).
        post = bandit.posteriors([_arm(20, 6), _arm(20, 6)])
        res = allocation.expected_loss_stop(post, 100.0, threshold_mad=5.0)
        self.assertFalse(res['should_stop'])
        self.assertGreater(res['expected_loss_mad'], 5.0)

    def test_single_arm_trivially_stops(self):
        post = bandit.posteriors([_arm(100, 20)])
        res = allocation.expected_loss_stop(post, 100.0)
        self.assertTrue(res['should_stop'])
        self.assertEqual(res['expected_loss_mad'], 0.0)

    def test_winner_has_lower_expected_loss_than_tie(self):
        winner = bandit.posteriors([_arm(20, 1), _arm(20, 15)])
        tie = bandit.posteriors([_arm(20, 6), _arm(20, 6)])
        self.assertLess(
            allocation.expected_loss_mad(winner, 100.0),
            allocation.expected_loss_mad(tie, 100.0))

    def test_higher_threshold_more_likely_to_stop(self):
        tie = bandit.posteriors([_arm(20, 6), _arm(20, 6)])
        self.assertFalse(
            allocation.expected_loss_stop(tie, 100.0, threshold_mad=5.0)[
                'should_stop'])
        self.assertTrue(
            allocation.expected_loss_stop(tie, 100.0, threshold_mad=100.0)[
                'should_stop'])

    def test_deterministic_under_seed(self):
        post = bandit.posteriors([_arm(50, 10), _arm(50, 14)])
        a = allocation.expected_loss_stop(post, 100.0, seed=7)
        b = allocation.expected_loss_stop(post, 100.0, seed=7)
        self.assertEqual(a['expected_loss_mad'], b['expected_loss_mad'])


class TwoRulesSideBySideTests(SimpleTestCase):
    """La valeur ajoutée : sur une VRAIE ÉGALITÉ au plafond de 4 semaines,
    l'ancienne règle stoppe (cap) tandis que la nouvelle attend encore."""

    def test_rules_diverge_on_tie_at_week_cap(self):
        tie = bandit.posteriors([_arm(20, 6), _arm(20, 6)])
        # Ancienne : plafond 4 sem atteint (P au plus 0,5) → stop forcé.
        self.assertTrue(allocation.challenger_phase_complete(0.5, 4))
        # Nouvelle : perte espérée toujours élevée sur une égalité mince → attend.
        self.assertFalse(
            allocation.expected_loss_stop(tie, 100.0, threshold_mad=5.0)[
                'should_stop'])

    def test_rules_agree_on_clear_winner(self):
        winner = bandit.posteriors([_arm(200, 10), _arm(200, 120)])
        p_best = float(bandit.prob_best(winner)[1])
        self.assertTrue(allocation.challenger_phase_complete(p_best, 1))
        self.assertTrue(
            allocation.expected_loss_stop(winner, 100.0)['should_stop'])
