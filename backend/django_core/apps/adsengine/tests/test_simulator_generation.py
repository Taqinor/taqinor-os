"""AGEN10 — Tests du harnais de simulation de la PIPELINE de génération.

Prouve, de façon DÉTERMINISTE, les trois comportements-clés de la pile de
sécurité de la génération créative (dd-assumption-engine §10.1/§10.2) contre une
vérité terrain CONNUE, SANS aucun appel réseau :

  * ``faux_chiffre_bloque``  → un lot dont une variante porte un chiffre HORS
    table est bloqué par le vérificateur numérique dur (AGEN3) ; l'ancrée passe ;
  * ``gabarit_gradue``       → un gabarit propre N semaines gradue en Palier A
    (tout-vert + gradué → backlog direct, AGEN6) ;
  * ``desapprobation_rayon`` → une désapprobation Meta déclenche l'auto-pause
    maison (AGEN8) dans un seul cycle de polling.
"""
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import simulator
from apps.adsengine.models import (
    CreativeAsset, EngineAction, EngineAlert, ExperimentArm,
)


class GenerationSimulatorBase(TestCase):
    def setUp(self):
        cache.clear()
        self._n = 0

    def tearDown(self):
        cache.clear()

    def _company(self):
        self._n += 1
        return Company.objects.create(
            nom=f'AGEN10 Co {self._n}', slug=f'agen10-co-{self._n}')

    def _run(self, scenario, seed=42):
        return simulator.simulate_generation(
            self._company(), scenario=scenario, seed=seed)


class GoldenGenerationScenarioTests(GenerationSimulatorBase):
    def test_false_number_batch_is_blocked(self):
        rep = self._run('faux_chiffre_bloque')
        self.assertEqual(rep['verdict'], 'blocked', rep)
        self.assertEqual(rep['expected_verdict'], 'blocked')
        # Exactement une variante bloquée (le faux chiffre), l'ancrée passe.
        self.assertEqual(rep['blocked_count'], 1)
        self.assertEqual(rep['passed_count'], 1)
        self.assertIn('99 999', rep['blocked_numbers'])

    def test_clean_template_graduates_to_tier_a(self):
        rep = self._run('gabarit_gradue')
        self.assertEqual(rep['verdict'], 'graduated', rep)
        self.assertEqual(rep['tier_before'], 'B')  # non gradué au départ
        self.assertEqual(rep['tier_after'], 'A')   # gradué → backlog direct
        # Le compteur a bien atteint le seuil.
        self.assertEqual(rep['clean_weeks'][-1], rep['threshold'])

    def test_disapproval_triggers_blast_radius_autopause(self):
        company = self._company()
        rep = simulator.simulate_generation(
            company, scenario='desapprobation_rayon', seed=42)
        self.assertEqual(rep['verdict'], 'auto_paused', rep)
        self.assertEqual(rep['poll_result'],
                         {'polled': 1, 'paused': 1, 'alerted': 1})
        self.assertFalse(rep['arm_active'])
        # Réel côté base : bras retiré, EngineAction auto d'audit, alerte 🔴.
        self.assertFalse(
            ExperimentArm.objects.get(company=company).is_active)
        act = EngineAction.objects.get(
            company=company, kind=EngineAction.Kind.PAUSE)
        self.assertTrue(act.auto)
        self.assertEqual(act.status, EngineAction.Statut.APPROUVEE)
        self.assertTrue(EngineAlert.objects.filter(
            company=company,
            severity=EngineAlert.Severity.CRITIQUE).exists())
        # Le créatif généré existe toujours (jamais supprimé, juste borné).
        self.assertTrue(CreativeAsset.objects.filter(company=company).exists())


class GenerationSimulatorContractTests(GenerationSimulatorBase):
    def test_unknown_scenario_refused(self):
        with self.assertRaises(ValueError):
            simulator.simulate_generation(
                self._company(), scenario='pas_un_scenario')

    def test_report_carries_scenario_and_expected(self):
        rep = self._run('faux_chiffre_bloque', seed=5)
        self.assertEqual(rep['scenario'], 'faux_chiffre_bloque')
        self.assertEqual(rep['seed'], 5)
        self.assertIn('summary_fr', rep)
        self.assertTrue(rep['summary_fr'])


class GenerationDeterminismTests(GenerationSimulatorBase):
    def test_all_three_scenarios_reach_expected_verdict(self):
        for scenario, expected in (
                simulator.GENERATION_EXPECTED_VERDICT.items()):
            rep = self._run(scenario)
            self.assertEqual(rep['verdict'], expected, (scenario, rep))

    def test_same_scenario_same_result_across_seeds(self):
        # Règle-à-règle : le verdict ne dépend pas du seed.
        first = simulator.simulate_generation(
            self._company(), scenario='faux_chiffre_bloque', seed=1)
        second = simulator.simulate_generation(
            self._company(), scenario='faux_chiffre_bloque', seed=999)
        self.assertEqual(first['verdict'], second['verdict'])
        self.assertEqual(first['blocked_count'], second['blocked_count'])
