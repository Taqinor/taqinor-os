"""ADSENG7 — Tests du générateur de compte synthétique (4 scénarios dorés).

Prouve : les 4 scénarios existent, la génération est DÉTERMINISTE (même seed ⇒
mêmes données), et chaque scénario produit sa vérité terrain attendue (gagnant
net, égalité, dérive mi-vol, effondrement de delivery). Un test vérifie aussi que
les leads synthétiques sont attribuables par variante (ADSENG6).
"""
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import attribution
from apps.adsengine.models import ArmDailyStat, Experiment
from apps.adsengine.management.commands.seed_synthetic_account import (
    SCENARIOS, generate_synthetic_account,
)


class SyntheticScenariosTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Synth Co', slug='synth-co')

    def _gen(self, scenario, months=1, seed=42, create_leads=False):
        return generate_synthetic_account(
            company=self.company, scenario=scenario, months=months,
            seed=seed, create_leads=create_leads)

    def test_four_golden_scenarios_documented(self):
        self.assertEqual(
            set(SCENARIOS),
            {'clear_winner', 'noisy_tie', 'mid_flight_drift',
             'delivery_collapse'})

    def test_deterministic_same_seed(self):
        first = self._gen('clear_winner', seed=7)
        second = self._gen('clear_winner', seed=7)
        # Recréation → mêmes totaux exacts sous le même seed.
        f_arms = {a['label']: a['total_conversations'] for a in first['arms']}
        s_arms = {a['label']: a['total_conversations'] for a in second['arms']}
        self.assertEqual(f_arms, s_arms)
        f_imp = {a['label']: a['total_impressions'] for a in first['arms']}
        s_imp = {a['label']: a['total_impressions'] for a in second['arms']}
        self.assertEqual(f_imp, s_imp)

    def test_recreate_does_not_duplicate(self):
        self._gen('clear_winner')
        self._gen('clear_winner')
        exps = Experiment.objects.filter(
            company=self.company, name='[SYNTH:clear_winner]')
        self.assertEqual(exps.count(), 1)

    def test_clear_winner_has_highest_conversions(self):
        res = self._gen('clear_winner')
        self.assertEqual(res['winning_arm'], 'A')
        by_conv = {a['label']: a['total_conversations'] for a in res['arms']}
        winner = max(by_conv, key=by_conv.get)
        self.assertEqual(winner, 'A')
        self.assertGreater(by_conv['A'], by_conv['B'])
        self.assertGreater(by_conv['A'], by_conv['C'])

    def test_noisy_tie_has_no_declared_winner(self):
        res = self._gen('noisy_tie')
        self.assertIsNone(res['winning_arm'])

    def test_mid_flight_drift_reverses_leader(self):
        res = self._gen('mid_flight_drift', months=2)
        arms = {a['label']: a for a in res['arms']}
        # A domine la 1re moitié, B la 2e (le gagnant change à mi-vol).
        self.assertGreater(
            arms['A']['first_half_conversations'],
            arms['A']['second_half_conversations'])
        self.assertGreater(
            arms['B']['second_half_conversations'],
            arms['B']['first_half_conversations'])

    def test_delivery_collapse_kills_late_delivery(self):
        res = self._gen('delivery_collapse', months=2)
        arms = {a['label']: a for a in res['arms']}
        # Le bras A (effondrement) délivre quasi 0 en fin de vol vs B qui tient.
        self.assertLess(
            arms['A']['last_quarter_impressions'],
            arms['B']['last_quarter_impressions'] * 0.2)

    def test_arm_daily_stats_written(self):
        self._gen('clear_winner')
        # 30 jours × 3 bras = 90 lignes de stats quotidiennes.
        self.assertEqual(
            ArmDailyStat.objects.filter(company=self.company).count(), 90)

    def test_synthetic_leads_are_attributable(self):
        self._gen('clear_winner', months=1, create_leads=True)
        variant = attribution.variant_attribution(self.company)
        by_meta = {v['meta_id']: v for v in variant['variants']}
        winner_ad = 'synth-clear_winner-A-ad'
        # Le bras gagnant porte le plus de leads attribués (∝ conversions).
        self.assertGreater(by_meta[winner_ad]['leads'], 0)
        loser_ad = 'synth-clear_winner-C-ad'
        self.assertGreaterEqual(
            by_meta[winner_ad]['leads'], by_meta[loser_ad]['leads'])
