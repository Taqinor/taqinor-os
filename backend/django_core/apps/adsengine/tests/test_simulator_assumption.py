"""ASG7 — Tests du harnais de simulation de l'ORDONNANCEUR de l'arbre.

Prouve, de façon DÉTERMINISTE (seed figé), les quatre comportements-clés de
l'arbre vivant (dd-assumption-engine §3.2/§3.3/§3.5, §1 correction n°1) contre une
vérité terrain CONNUE, SANS aucun test calendaire ni contact Meta :

  * ``peremption_retest_auto``  → un nœud validé s'oublie, son incertitude regonfle
    et il RE-SURFACE en tête de file par U seul (jamais de retest calendaire) ;
  * ``saison_revient``          → un nœud saisonnier n'est jamais oublié (posterior
    in-saison préservé), alors qu'un frère non saisonnier s'oublie ;
  * ``cascade_invalidation``    → la bascule d'un parent périme ses dépendants en
    cascade, AUCUN re-testé automatiquement ;
  * ``famine_testabilite``      → une file 100 % intestable (T≈0) est PROPOSÉE à un
    humain, le slot n'est jamais brûlé.
"""
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import simulator
from apps.adsengine.models import (
    AssumptionNode, EngineAlert, Experiment,
)


class AssumptionSchedulerBase(TestCase):
    def setUp(self):
        cache.clear()
        self._n = 0

    def tearDown(self):
        cache.clear()

    def _company(self):
        self._n += 1
        return Company.objects.create(
            nom=f'ASG7 Co {self._n}', slug=f'asg7-co-{self._n}')

    def _run(self, scenario, seed=42):
        return simulator.simulate_assumption_scheduler(
            self._company(), scenario=scenario, seed=seed)


class GoldenAssumptionScenarioTests(AssumptionSchedulerBase):
    def test_peremption_resurfaces_by_uncertainty_alone(self):
        rep = self._run('peremption_retest_auto')
        self.assertEqual(rep['verdict'], 'resurfaced', rep)
        self.assertEqual(rep['expected_verdict'], 'resurfaced')
        # L'incertitude a REGONFLÉ avec l'oubli (§3.3).
        self.assertGreater(rep['u_after'], rep['u_before'])
        # AUCUN retest calendaire n'a été déclenché (re-surface ≠ test lancé).
        self.assertFalse(rep['retest_triggered'])

    def test_saison_posterior_preserved(self):
        company = self._company()
        rep = simulator.simulate_assumption_scheduler(
            company, scenario='saison_revient', seed=42)
        self.assertEqual(rep['verdict'], 'season_preserved', rep)
        # Le nœud saisonnier n'est jamais éligible à l'oubli hebdomadaire.
        self.assertFalse(rep['seasonal_eligible'])
        # Son posterior in-saison est resté INTACT.
        self.assertEqual(rep['seasonal_posterior'], [40.0, 8.0])
        # Le frère non saisonnier, lui, s'est bien oublié (posterior déplacé).
        self.assertNotEqual(rep['ordinary_posterior'], [40.0, 8.0])

    def test_cascade_marks_dependents_stale_without_retest(self):
        company = self._company()
        rep = simulator.simulate_assumption_scheduler(
            company, scenario='cascade_invalidation', seed=42)
        self.assertEqual(rep['verdict'], 'cascade_stale', rep)
        # 2 enfants hiérarchiques + 1 lien DAG = 3 dépendants périmés.
        self.assertEqual(len(rep['invalidated']), 3)
        self.assertEqual(rep['alerts'], 3)
        self.assertFalse(rep['retest_triggered'])
        # Réel côté base : les dépendants sont STALE, aucun Experiment ouvert.
        self.assertEqual(
            AssumptionNode.objects.filter(
                company=company,
                statut=AssumptionNode.Statut.STALE).count(), 4)  # parent + 3
        self.assertFalse(Experiment.objects.filter(company=company).exists())
        # Trois alertes INFO 🔵 (une par dépendant périmé).
        self.assertEqual(
            EngineAlert.objects.filter(
                company=company,
                severity=EngineAlert.Severity.INFO).count(), 3)

    def test_famine_proposes_to_human_without_burning_slot(self):
        company = self._company()
        rep = simulator.simulate_assumption_scheduler(
            company, scenario='famine_testabilite', seed=42)
        self.assertEqual(rep['verdict'], 'proposed_to_human', rep)
        # Le barreau le plus à enjeu est bien intestable (T≈0).
        self.assertLess(rep['top_testability'], 0.05)
        # Le slot n'a JAMAIS été brûlé (aucun test ouvert).
        self.assertFalse(rep['slot_burned'])
        self.assertFalse(Experiment.objects.filter(company=company).exists())
        # Une alerte « proposé à un humain » existe.
        self.assertTrue(EngineAlert.objects.filter(
            company=company,
            detail__proposed_to_human=True).exists())


class AssumptionSchedulerContractTests(AssumptionSchedulerBase):
    def test_unknown_scenario_refused(self):
        with self.assertRaises(ValueError):
            simulator.simulate_assumption_scheduler(
                self._company(), scenario='pas_un_scenario')

    def test_report_carries_scenario_and_expected(self):
        rep = self._run('peremption_retest_auto', seed=7)
        self.assertEqual(rep['scenario'], 'peremption_retest_auto')
        self.assertEqual(rep['seed'], 7)
        self.assertIn('summary_fr', rep)
        self.assertTrue(rep['summary_fr'])


class AssumptionDeterminismTests(AssumptionSchedulerBase):
    def test_same_seed_same_verdict_and_uncertainty(self):
        first = simulator.simulate_assumption_scheduler(
            self._company(), scenario='peremption_retest_auto', seed=123)
        second = simulator.simulate_assumption_scheduler(
            self._company(), scenario='peremption_retest_auto', seed=123)
        self.assertEqual(first['verdict'], second['verdict'])
        self.assertEqual(first['u_before'], second['u_before'])
        self.assertEqual(first['u_after'], second['u_after'])
        self.assertEqual(first['winner_node_id'] is not None,
                         second['winner_node_id'] is not None)

    def test_all_four_scenarios_reach_expected_verdict(self):
        for scenario, expected in (
                simulator.ASSUMPTION_EXPECTED_VERDICT.items()):
            rep = self._run(scenario)
            self.assertEqual(rep['verdict'], expected, (scenario, rep))
