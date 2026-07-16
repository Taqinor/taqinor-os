"""ADSENG12 — Tests du hook DecisionLog systématique.

Invariant : AUCUNE décision (allocation) sans une ligne ``DecisionLog``.
``decide_and_log`` calcule ET journalise en un seul appel — la ligne est écrite
avant le retour, donc un appelant ne peut pas obtenir l'allocation sans le log.
Vérifie aussi : company forcée depuis l'expérience (multi-tenant), instantané des
entrées + postérieurs + allocation stockés, JSON sérialisable (pas de numpy),
déterminisme sous graine, lien EngineAction.
"""
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import decisionlog
from apps.adsengine.models import (
    DecisionLog, EngineAction, Experiment,
)


ARMS = [
    {'label': 'A', 'impressions': 1000, 'conversions': 40},
    {'label': 'B', 'impressions': 1000, 'conversions': 20},
]


class DecideAndLogTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Log Co', slug='log-co')
        self.exp = Experiment.objects.create(
            company=self.company, name='Reweight',
            status=Experiment.Statut.EN_COURS)

    def test_every_decision_writes_exactly_one_log(self):
        before = DecisionLog.objects.count()
        result, log = decisionlog.decide_and_log(self.exp, ARMS, 100)
        self.assertEqual(DecisionLog.objects.count(), before + 1)
        self.assertEqual(log.experiment, self.exp)
        # L'allocation retournée est EXACTEMENT celle qui a été journalisée.
        self.assertEqual(result['allocations'], log.allocations['budget_mad'])

    def test_company_forced_from_experiment(self):
        _, log = decisionlog.decide_and_log(self.exp, ARMS, 100)
        self.assertEqual(log.company, self.company)

    def test_snapshot_and_posteriors_stored(self):
        _, log = decisionlog.decide_and_log(self.exp, ARMS, 100)
        self.assertEqual(len(log.inputs['arms']), 2)
        self.assertEqual(log.inputs['arms'][0]['conversions'], 40)
        self.assertEqual(log.inputs['daily_budget_mad'], 100.0)
        # Postérieurs Beta(1+conv, 1+échecs).
        self.assertEqual(log.posteriors['alpha_beta'][0], [41.0, 961.0])
        self.assertIn('budget_mad', log.allocations)
        self.assertTrue(log.summary_fr)

    def test_allocation_sums_to_budget(self):
        _, log = decisionlog.decide_and_log(self.exp, ARMS, 100)
        self.assertAlmostEqual(
            sum(log.allocations['budget_mad'].values()), 100.0, places=3)

    def test_leader_gets_more_budget(self):
        result, _ = decisionlog.decide_and_log(self.exp, ARMS, 100)
        self.assertGreater(
            result['allocations']['A'], result['allocations']['B'])

    def test_deterministic_under_seed(self):
        r1, _ = decisionlog.decide_and_log(self.exp, ARMS, 100, seed=5)
        r2, _ = decisionlog.decide_and_log(self.exp, ARMS, 100, seed=5)
        self.assertEqual(r1['allocations'], r2['allocations'])
        self.assertEqual(r1['prob_best'], r2['prob_best'])

    def test_json_serialisable_no_numpy(self):
        # La (re)lecture depuis la base prouve la sérialisation JSON (aucune
        # valeur ndarray/np.float n'aurait pu être enregistrée).
        _, log = decisionlog.decide_and_log(self.exp, ARMS, 100)
        reloaded = DecisionLog.objects.get(pk=log.pk)
        for v in reloaded.allocations['budget_mad'].values():
            self.assertIsInstance(v, float)
        for v in reloaded.allocations['prob_best'].values():
            self.assertIsInstance(v, float)

    def test_below_reweight_gate_holds_even_split(self):
        thin = [
            {'label': 'A', 'impressions': 50, 'conversions': 5},
            {'label': 'B', 'impressions': 40, 'conversions': 1},
        ]
        result, log = decisionlog.decide_and_log(self.exp, thin, 100)
        self.assertFalse(result['reweighted'])
        self.assertAlmostEqual(result['allocations']['A'], 50.0, places=3)
        self.assertAlmostEqual(result['allocations']['B'], 50.0, places=3)

    def test_links_engine_action(self):
        action = EngineAction.objects.create(
            company=self.company,
            kind=EngineAction.Kind.REBALANCE_BUDGET,
            reason_fr="Rééquilibrage quotidien du bandit.",
            status=EngineAction.Statut.PROPOSEE, auto=False)
        _, log = decisionlog.decide_and_log(self.exp, ARMS, 100, action=action)
        self.assertEqual(log.action, action)


class LogDecisionTenancyTests(TestCase):
    def test_log_decision_forces_experiment_company(self):
        company = Company.objects.create(nom='T Co', slug='t-co')
        exp = Experiment.objects.create(
            company=company, name='X', status=Experiment.Statut.EN_COURS)
        log = decisionlog.log_decision(
            exp, inputs={'a': 1}, posteriors={'b': 2},
            allocations={'c': 3}, summary_fr='ok')
        self.assertEqual(log.company, company)
        self.assertEqual(log.experiment, exp)
