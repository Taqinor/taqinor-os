"""ASG3 — Tests dorés du scoreur VoI + ordonnanceur (dd-assumption-engine §3.3).

Invariants prouvés (déterministes sous seed) :
  * ``U = 1 − |2·P(meilleur) − 1|`` : max quand P=0.5, nul quand P∈{0,1} ;
  * un nœud PÉRIMÉ re-surface par U SEUL (S/R/T/C égaux, seul le posterior oublié
    diffère → il gagne la file) ;
  * un nœud INTESTABLE (T≈0, MDE infaisable) ne gagne JAMAIS la file, même à
    S/U/R maximaux ;
  * ``schedule_next`` écrit TOUJOURS un ``DecisionLog`` (ASG3 obligatoire) ;
  * le flag ``voi_scheduler_active`` (OFF par défaut) désactive la transition de
    phase calendaire fixe du FlightRunner.
"""
import datetime

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import voi
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.models import (
    AssumptionNode, DecisionLog, Experiment, FlightPlan,
)


class VoIMathTests(SimpleTestCase):
    """Cœur pur — déterministe sous seed."""

    def test_uncertainty_maximal_when_indistinguishable(self):
        # Posterior == champion (mêmes Beta) ⇒ P≈0.5 ⇒ U≈1.
        u = voi.uncertainty(2.0, 2.0, 2.0, 2.0, seed=0)
        self.assertGreater(u, 0.95)

    def test_uncertainty_low_when_sharp_winner(self):
        # Posterior net et fort vs prior faible ⇒ P proche de 1 ⇒ U bas.
        u = voi.uncertainty(90.0, 10.0, 1.0, 1.0, seed=0)
        self.assertLess(u, 0.3)

    def test_uncertainty_in_unit_interval(self):
        for a, b in [(1, 1), (50, 10), (3, 7), (100, 100)]:
            u = voi.uncertainty(a, b, 1.0, 1.0, seed=0)
            self.assertGreaterEqual(u, 0.0)
            self.assertLessEqual(u, 1.0)

    def test_testability_full_when_effect_above_mde(self):
        # Gros volume (n élevé) ⇒ MDE petit ⇒ effet plausible >> MDE ⇒ T=1.
        t = voi.testability(0.5, 0.02, 25200)
        self.assertEqual(t, 1.0)

    def test_testability_near_zero_when_untestable(self):
        # Barreau signature : p bas, n minuscule ⇒ MDE énorme ⇒ T≈0.
        t = voi.testability(0.05, 0.06, 6)
        self.assertLess(t, 0.15)

    def test_testability_zero_on_nonpositive(self):
        self.assertEqual(voi.testability(0.5, 0.02, 0), 0.0)
        self.assertEqual(voi.testability(0.0, 0.02, 1000), 0.0)

    def test_voi_score_formula(self):
        self.assertAlmostEqual(
            voi.voi_score(0.5, 0.8, 0.6, 0.9, 2.0),
            (0.5 * 0.8 * 0.6 * 0.9) / 2.0, places=12)

    def test_voi_score_rejects_nonpositive_cost(self):
        with self.assertRaises(ValueError):
            voi.voi_score(0.5, 0.5, 0.5, 0.5, 0.0)


class VoISchedulerTests(TestCase):
    """Ordonnanceur : re-surface par U, intestable écarté, DecisionLog obligé."""

    def setUp(self):
        self.company = Company.objects.create(nom='ASG VoI', slug='asg-voi')
        cache.clear()

    def _node(self, **kw):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Hypothèse.', enjeux_s=0.5, pertinence_r=0.5,
            alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0, demi_vie_semaines=8)
        defaults.update(kw)
        return AssumptionNode.objects.create(**defaults)

    def _experiment(self):
        return Experiment.objects.create(company=self.company, name='Slot')

    # Contexte MDE/coût pleinement testable (T=1) — commun aux nœuds testables.
    TESTABLE = dict(delta_plausible=0.5, p=0.02, n=25200, cost=1.0)
    # Contexte intestable (barreau signature : MDE infaisable) — T≈0.03.
    UNTESTABLE = dict(delta_plausible=0.02, p=0.06, n=2, cost=1.0)

    def test_stale_node_resurfaces_by_uncertainty_alone(self):
        # Deux nœuds S/R/T/C IDENTIQUES ; seul le posterior diffère.
        fresh = self._node(alpha=50.0, beta=10.0)   # net ⇒ U bas
        stale = self._node(alpha=2.0, beta=2.0)     # oublié/large ⇒ U haut
        params = {fresh.pk: self.TESTABLE, stale.pk: self.TESTABLE}

        ranking = voi.rank_candidates(self.company, params, seed=0)
        winner = ranking[0][0]

        self.assertEqual(winner.pk, stale.pk)
        # Le SEUL discriminant est U (S,R,T,C égaux).
        self.assertGreater(ranking[0][1]['U'], ranking[1][1]['U'])

    def test_untestable_node_never_wins(self):
        # Nœud intestable dopé à fond (S,R max) — mais T≈0 l'écrase.
        untestable = self._node(
            enjeux_s=1.0, pertinence_r=1.0, alpha=2.0, beta=2.0)
        testable = self._node(
            enjeux_s=0.5, pertinence_r=0.5, alpha=2.0, beta=2.0)
        params = {untestable.pk: self.UNTESTABLE,
                  testable.pk: self.TESTABLE}

        result = voi.schedule_next(
            self.company, experiment=self._experiment(), params=params, seed=0)

        self.assertEqual(result['winner'].pk, testable.pk)
        # T du nœud intestable doit être ~0.
        by_node = {n.pk: s for n, s in result['ranking']}
        self.assertLess(by_node[untestable.pk]['T'], 0.15)

    def test_schedule_next_writes_decisionlog(self):
        node = self._node(alpha=2.0, beta=2.0)
        exp = self._experiment()
        result = voi.schedule_next(
            self.company, experiment=exp, params={node.pk: self.TESTABLE},
            seed=0)

        self.assertIsNotNone(result['log'])
        self.assertEqual(DecisionLog.objects.filter(experiment=exp).count(), 1)
        log = DecisionLog.objects.get(experiment=exp)
        self.assertEqual(log.company_id, self.company.id)
        self.assertEqual(log.allocations['winner_node_id'], node.pk)

    def test_schedule_next_logs_even_when_queue_empty(self):
        exp = self._experiment()
        result = voi.schedule_next(
            self.company, experiment=exp, params={}, seed=0)

        self.assertIsNone(result['winner'])
        self.assertEqual(DecisionLog.objects.filter(experiment=exp).count(), 1)

    def test_retired_node_excluded(self):
        active = self._node(alpha=2.0, beta=2.0)
        retired = self._node(
            alpha=2.0, beta=2.0, statut=AssumptionNode.Statut.RETIRED)
        params = {active.pk: self.TESTABLE, retired.pk: self.TESTABLE}
        ranking = voi.rank_candidates(self.company, params, seed=0)
        self.assertEqual([n.pk for n, _ in ranking], [active.pk])

    def test_scheduler_is_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='autre-voi')
        mine = self._node(alpha=2.0, beta=2.0)
        theirs = AssumptionNode.objects.create(
            company=other, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='X', enjeux_s=0.9, pertinence_r=0.9,
            alpha=2.0, beta=2.0, alpha0=1.0, beta0=1.0, demi_vie_semaines=8)
        params = {mine.pk: self.TESTABLE, theirs.pk: self.TESTABLE}

        ranking = voi.rank_candidates(self.company, params, seed=0)

        self.assertEqual([n.pk for n, _ in ranking], [mine.pk])

    def test_schedule_next_rejects_foreign_experiment(self):
        other = Company.objects.create(nom='Autre2', slug='autre2-voi')
        foreign_exp = Experiment.objects.create(company=other, name='X')
        with self.assertRaises(ValueError):
            voi.schedule_next(
                self.company, experiment=foreign_exp, params={}, seed=0)


class VoIFlagFlightRunnerTests(TestCase):
    """Le flag OFF/ON gouverne la transition de phase du FlightRunner."""

    def setUp(self):
        self.company = Company.objects.create(nom='ASG Flag', slug='asg-flag')
        cache.clear()
        self.plan = FlightPlan.objects.create(
            company=self.company, name='Plan', status=FlightPlan.Statut.ACTIF)

    def test_flag_off_by_default(self):
        self.assertFalse(voi.voi_scheduler_active(self.company))

    def test_flag_off_uses_calendar_transition(self):
        # Sans flag et sans phase → comportement calendaire historique.
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(today=datetime.date(2026, 1, 1))
        self.assertNotIn('voi_mode', result)
        self.assertEqual(result.get('reason'), 'aucune phase')

    def test_flag_on_disables_calendar_transition(self):
        voi.set_voi_scheduler_active(self.company, True)
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(today=datetime.date(2026, 1, 1))
        self.assertTrue(result.get('voi_mode'))
        self.assertFalse(result.get('advanced'))

    def test_flag_toggle_off(self):
        voi.set_voi_scheduler_active(self.company, True)
        voi.set_voi_scheduler_active(self.company, False)
        self.assertFalse(voi.voi_scheduler_active(self.company))
