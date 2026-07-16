"""ADSENG36 — Tests du harnais de simulation (4 scénarios dorés).

Prouve, de façon DÉTERMINISTE (seed figé), que le moteur rejoué sur les comptes
synthétiques ADSENG7 produit le BON comportement :

  * ``clear_winner``      → converge sur le vrai gagnant ;
  * ``noisy_tie``         → ne conclut PAS (aucun signal) ;
  * ``mid_flight_drift``  → détecte la bascule de gagnant à mi-vol ;
  * ``delivery_collapse`` → le gardien propose une pause + alerte.
"""
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import simulator
from apps.adsengine.models import EngineAction


class SimulatorBase(TestCase):
    def setUp(self):
        cache.clear()
        self._n = 0

    def tearDown(self):
        cache.clear()

    def _company(self):
        self._n += 1
        return Company.objects.create(
            nom=f'Sim Co {self._n}', slug=f'sim-co-{self._n}')

    def _run(self, scenario, seed=42, months=2):
        return simulator.simulate(
            self._company(), scenario=scenario, seed=seed, months=months)


class GoldenScenarioTests(SimulatorBase):
    def test_clear_winner_converges_on_true_winner(self):
        rep = self._run('clear_winner')
        self.assertEqual(rep['verdict'], 'converged', rep)
        self.assertTrue(rep['converged'])
        self.assertEqual(rep['winner'], 'Bras A')  # le vrai gagnant (A)
        self.assertEqual(rep['expected_verdict'], 'converged')

    def test_noisy_tie_does_not_conclude(self):
        rep = self._run('noisy_tie')
        self.assertEqual(rep['verdict'], 'no_signal', rep)
        self.assertFalse(rep['converged'])

    def test_mid_flight_drift_is_detected(self):
        rep = self._run('mid_flight_drift')
        self.assertEqual(rep['verdict'], 'drift_detected', rep)
        self.assertTrue(rep['leader_changed'])

    def test_delivery_collapse_triggers_guardian_pause(self):
        company = self._company()
        rep = simulator.simulate(
            company, scenario='delivery_collapse', seed=42, months=2)
        self.assertEqual(rep['verdict'], 'collapse_handled', rep)
        self.assertTrue(rep['collapse_detected'])
        self.assertGreaterEqual(rep['guardian_pauses'], 1)
        # Le gardien a proposé une pause (propose-only, jamais appliquée).
        pauses = EngineAction.objects.filter(
            company=company, kind=EngineAction.Kind.PAUSE,
            status=EngineAction.Statut.PROPOSEE,
            payload__delivery_collapse=True)
        self.assertTrue(pauses.exists())


class SimulatorReportTests(SimulatorBase):
    def test_report_is_readable_and_structured(self):
        rep = self._run('clear_winner')
        self.assertIn('timeline', rep)
        self.assertTrue(rep['timeline'])
        for step in rep['timeline']:
            self.assertIn('as_of', step)
            self.assertIn('prob_best', step)
            self.assertIn('leader', step)
        self.assertIn('summary_fr', rep)
        self.assertTrue(rep['summary_fr'])

    def test_unknown_scenario_refused(self):
        with self.assertRaises(ValueError):
            simulator.simulate(self._company(), scenario='pas_un_scenario')


class DeterminismTests(SimulatorBase):
    def test_same_seed_same_verdict_and_beliefs(self):
        first = simulator.simulate(
            self._company(), scenario='clear_winner', seed=99, months=2)
        second = simulator.simulate(
            self._company(), scenario='clear_winner', seed=99, months=2)
        self.assertEqual(first['verdict'], second['verdict'])
        self.assertEqual(first['winner'], second['winner'])
        self.assertEqual(first['max_prob_best'], second['max_prob_best'])
        self.assertEqual(
            [s['leader'] for s in first['timeline']],
            [s['leader'] for s in second['timeline']])
