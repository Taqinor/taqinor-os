"""SIG2 — Tests du quadrant de garde-fous DURS (Layer 0, fa-signals §2.3).

Deux volets : (1) chaque garde-fou se déclenche/ne se déclenche pas correctement ;
(2) l'INVARIANT DUR « freiner SEULEMENT » — aucun garde-fou ne peut, sous AUCUNE
entrée, émettre une action d'accélération. Module pur → ``SimpleTestCase``.
"""
import inspect
import itertools
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.adsengine import allocation, bandit, rewards, signal_guards as sg


class FrequencyGuardTests(SimpleTestCase):
    def test_fires_above_cap_and_rotates(self):
        v = sg.frequency_guard({'frequency': 4.2})
        self.assertTrue(v.triggered)
        self.assertEqual(v.action, sg.GUARD_ACTION_ROTATE)

    def test_silent_at_or_below_cap(self):
        self.assertFalse(sg.frequency_guard({'frequency': 3.0}).triggered)
        self.assertFalse(sg.frequency_guard({'frequency': 1.0}).triggered)

    def test_missing_frequency_is_silent(self):
        self.assertFalse(sg.frequency_guard({}).triggered)

    def test_config_field_overrides_default_cap(self):
        cfg = SimpleNamespace(frequency_cap=6)
        self.assertFalse(sg.frequency_guard({'frequency': 4.5}, cfg).triggered)


class QualityRankingGuardTests(SimpleTestCase):
    def test_below_average_with_enough_impressions_pauses(self):
        v = sg.quality_ranking_guard(
            {'quality_ranking': 'below_average', 'impressions': 800})
        self.assertTrue(v.triggered)
        self.assertEqual(v.action, sg.GUARD_ACTION_PAUSE)

    def test_below_but_under_500_impressions_is_silent(self):
        # Diagnostic n'apparaît qu'après ~500 impr : absence de donnée ≠ mauvais.
        v = sg.quality_ranking_guard(
            {'quality_ranking': 'below', 'impressions': 120})
        self.assertFalse(v.triggered)

    def test_average_or_above_is_silent(self):
        self.assertFalse(sg.quality_ranking_guard(
            {'quality_ranking': 'average', 'impressions': 900}).triggered)
        self.assertFalse(sg.quality_ranking_guard(
            {'quality_ranking': 'above', 'impressions': 900}).triggered)

    def test_missing_ranking_is_silent(self):
        self.assertFalse(sg.quality_ranking_guard(
            {'impressions': 900}).triggered)


class CplGuardTests(SimpleTestCase):
    def test_over_ceiling_on_mature_cohort_reduces_budget(self):
        v = sg.cpl_guard(
            {'cpl': 200, 'cpl_target': 100, 'cohort_age_days': 20})
        self.assertTrue(v.triggered)
        self.assertEqual(v.action, sg.GUARD_ACTION_REDUCE)

    def test_immature_cohort_never_fires_even_if_cpl_high(self):
        # Filigrane de cohorte (SIG3) : une cohorte <14 j est ignorée — jamais
        # de frein sur un CPL pas encore fiable.
        v = sg.cpl_guard(
            {'cpl': 500, 'cpl_target': 100, 'cohort_age_days': 5})
        self.assertFalse(v.triggered)

    def test_within_ceiling_is_silent(self):
        v = sg.cpl_guard(
            {'cpl': 120, 'cpl_target': 100, 'cohort_age_days': 30})
        self.assertFalse(v.triggered)

    def test_missing_target_is_silent(self):
        self.assertFalse(sg.cpl_guard(
            {'cpl': 300, 'cohort_age_days': 30}).triggered)


class AccountQualityGuardTests(SimpleTestCase):
    def test_drop_pauses(self):
        v = sg.account_quality_guard({'account_quality_dropped': True})
        self.assertTrue(v.triggered)
        self.assertEqual(v.action, sg.GUARD_ACTION_PAUSE)

    def test_no_drop_is_silent(self):
        self.assertFalse(
            sg.account_quality_guard({'account_quality_dropped': False}).triggered)
        self.assertFalse(sg.account_quality_guard({}).triggered)


class EvaluateGuardsTests(SimpleTestCase):
    def test_returns_only_triggered_verdicts(self):
        verdicts = sg.evaluate_guards({
            'frequency': 5, 'cpl': 300, 'cpl_target': 100,
            'cohort_age_days': 30, 'account_quality_dropped': False,
        })
        guards = {v.guard for v in verdicts}
        self.assertEqual(guards, {'frequency', 'cpl'})

    def test_empty_signals_returns_nothing(self):
        self.assertEqual(sg.evaluate_guards({}), [])
        self.assertEqual(sg.evaluate_guards(None), [])


class BrakeOnlyInvariantTests(SimpleTestCase):
    """INVARIANT DUR : aucun garde-fou ne peut émettre une action d'accélération.
    Prouvé structurellement (ensemble exhaustif) ET par balayage exhaustif des
    entrées."""

    def test_declared_action_set_is_subset_of_brake_actions(self):
        self.assertTrue(sg.all_guard_actions().issubset(sg.BRAKE_ACTIONS))

    def test_no_declared_action_is_an_accelerate_action(self):
        self.assertEqual(
            sg.all_guard_actions() & sg.FORBIDDEN_ACCELERATE_ACTIONS, set())
        self.assertEqual(
            sg.BRAKE_ACTIONS & sg.FORBIDDEN_ACCELERATE_ACTIONS, set())

    def test_every_emitted_action_across_input_sweep_is_brake_only(self):
        # Balayage large : quelle que soit l'entrée, une action émise est
        # TOUJOURS un frein — jamais une accélération.
        freqs = [None, 0.5, 3.0, 3.1, 99]
        rankings = [None, 'above', 'average', 'below']
        impressions = [None, 100, 500, 5000]
        cpls = [None, 50, 300]
        targets = [None, 0, 100]
        ages = [None, 5, 14, 90]
        drops = [None, False, True]
        emitted = set()
        for combo in itertools.product(
                freqs, rankings, impressions, cpls, targets, ages, drops):
            f, r, im, c, t, a, d = combo
            verdicts = sg.evaluate_guards({
                'frequency': f, 'quality_ranking': r, 'impressions': im,
                'cpl': c, 'cpl_target': t, 'cohort_age_days': a,
                'account_quality_dropped': d,
            })
            for v in verdicts:
                self.assertTrue(v.triggered)
                emitted.add(v.action)
                self.assertIn(v.action, sg.BRAKE_ACTIONS)
                self.assertNotIn(v.action, sg.FORBIDDEN_ACCELERATE_ACTIONS)
        # On a bien exercé au moins une action de frein réelle.
        self.assertTrue(emitted)
        self.assertTrue(emitted.issubset(sg.BRAKE_ACTIONS))

    def test_emitted_actions_name_no_accelerate_verb(self):
        # L'ensemble d'actions émises ne contient aucun verbe d'accélération
        # (garde négative — documentation vivante de ce que SIG2 ne fera JAMAIS).
        self.assertFalse(
            sg.all_guard_actions() & sg.FORBIDDEN_ACCELERATE_ACTIONS)
        self.assertFalse(
            {v.action for v in sg.evaluate_guards({'frequency': 9})}
            & sg.FORBIDDEN_ACCELERATE_ACTIONS)


class SignalGuardsNeverConsumedByBanditTests(SimpleTestCase):
    """Comme SIG1 : un garde-fou est FREIN/alerte — jamais une récompense lue
    par le bandit/l'allocation. Vérifié structurellement (pas d'import croisé)."""

    def test_bandit_paths_never_import_signal_guards(self):
        for module in (bandit, rewards, allocation):
            source = inspect.getsource(module)
            self.assertNotIn('signal_guards', source)

    def test_module_is_pure_no_model_io(self):
        source = inspect.getsource(sg)
        self.assertNotIn('from .models import', source)
        self.assertNotIn('from django.db import models', source)
