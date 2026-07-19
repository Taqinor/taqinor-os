"""PUB17 — Câblage RÉEL de l'ordonnanceur VoI dans ``FlightRunner.advance_phase``.

Avant : flag ON ⇒ ``advance_phase`` loggait-et-return, ``voi.schedule_next``
n'était JAMAIS appelé. Après : flag ON + expérience + contexte MDE ⇒ la phase
suivante = sortie de ``voi.schedule_next`` (argmax VoI + DecisionLog obligatoire).
Golden : flag OFF ⇒ comportement calendaire BYTE-IDENTIQUE (kwargs VoI ignorés).
"""
import datetime

from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import voi
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.models import (
    AssumptionNode, DecisionLog, Experiment, FlightPlan,
)

TODAY = datetime.date(2026, 1, 1)
TESTABLE = dict(delta_plausible=0.5, p=0.02, n=25200, cost=1.0)


class VoISchedulerWiringTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='VoI Co', slug='voi-co')
        self.plan = FlightPlan.objects.create(
            company=self.company, name='Plan', status=FlightPlan.Statut.ACTIF)

    def tearDown(self):
        cache.clear()

    def _node(self, **kw):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Hypothèse.', enjeux_s=0.5, pertinence_r=0.5,
            alpha=2.0, beta=2.0, alpha0=1.0, beta0=1.0, demi_vie_semaines=8)
        defaults.update(kw)
        return AssumptionNode.objects.create(**defaults)

    def _experiment(self):
        return Experiment.objects.create(
            company=self.company, name='Slot',
            status=Experiment.Statut.EN_COURS)

    # ── Flag OFF : byte-identique (golden) ───────────────────────────────────
    def test_flag_off_calendar_behaviour_unchanged(self):
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(today=TODAY)
        self.assertNotIn('voi_mode', result)
        self.assertEqual(result.get('reason'), 'aucune phase')

    def test_flag_off_ignores_voi_kwargs(self):
        # Même avec les nouveaux kwargs, OFF reste calendaire (byte-identique).
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(
            today=TODAY, voi_params={1: TESTABLE})
        self.assertNotIn('voi_mode', result)
        self.assertEqual(result.get('reason'), 'aucune phase')

    # ── Flag ON : schedule_next RÉELLEMENT appelé ────────────────────────────
    def test_flag_on_next_phase_is_schedule_next_output(self):
        voi.set_voi_scheduler_active(self.company, True)
        node = self._node()
        self._experiment()
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(
            today=TODAY, voi_params={node.pk: TESTABLE})
        self.assertTrue(result['voi_mode'])
        self.assertTrue(result['advanced'])
        # La « phase suivante » = le nœud argmax VoI choisi par schedule_next.
        self.assertEqual(result['voi_node_id'], node.pk)
        # Sélection TRACÉE (DecisionLog obligatoire ASG3).
        self.assertIsNotNone(result['decision_log_id'])
        self.assertTrue(
            DecisionLog.objects.filter(id=result['decision_log_id']).exists())

    def test_flag_on_without_params_forces_no_selection(self):
        # Flag ON mais aucun contexte MDE → aucune sélection fabriquée.
        voi.set_voi_scheduler_active(self.company, True)
        self._node()
        self._experiment()
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(today=TODAY)
        self.assertTrue(result['voi_mode'])
        self.assertFalse(result['advanced'])
        self.assertIsNone(result['voi_node_id'])

    def test_flag_on_without_experiment_no_crash(self):
        voi.set_voi_scheduler_active(self.company, True)
        node = self._node()
        runner = FlightRunner(self.plan)
        result = runner.advance_phase(
            today=TODAY, voi_params={node.pk: TESTABLE})
        # Aucune expérience EN_COURS → pas de slot forcé, jamais un crash.
        self.assertTrue(result['voi_mode'])
        self.assertFalse(result['advanced'])
