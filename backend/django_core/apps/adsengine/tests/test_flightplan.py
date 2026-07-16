"""ADSENG28 — Tests du plan de vol + préflight.

Prouve : un plan invalide (backlog/diversité/garde-fous/alertes/MDE manquants)
est REFUSÉ avec des raisons FR ; un plan valide se matérialise en phases
planifiées ordonnées (une variable par phase, dates séquentielles).
"""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.adsengine import flightplan
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, FlightPhase, FlightPlan,
    GuardrailConfig, RulePolicy,
)

TODAY = datetime.date(2026, 7, 13)


class FlightPlanPreflightTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fp Co', slug='fp-co')

    # ── Helpers de fixture ───────────────────────────────────────────────────
    def _seed_backlog(self, *, count=12, distinct_hooks=4):
        for i in range(count):
            asset = CreativeAsset.objects.create(
                company=self.company,
                asset_type=CreativeAsset.AssetType.STATIC,
                hook_id=f'H{i % distinct_hooks}',
                policy_stamp={'passed': True})
            CreativeBacklogItem.objects.create(
                company=self.company, asset=asset,
                status=CreativeBacklogItem.Statut.EN_FILE)

    def _seed_guardrails_and_alerts(self):
        GuardrailConfig.objects.create(company=self.company)
        RulePolicy.objects.create(
            company=self.company, template_key='zero_results', enabled=True)

    def _valid_plan(self):
        self._seed_backlog()
        self._seed_guardrails_and_alerts()
        return FlightPlan.objects.create(
            company=self.company, name='Plan 6 mois', start_date=TODAY)

    # ── Refus ────────────────────────────────────────────────────────────────
    def test_empty_context_plan_is_refused_with_fr_reasons(self):
        plan = FlightPlan.objects.create(
            company=self.company, name='Vide', start_date=TODAY)
        result = flightplan.preflight(
            self.company, flightplan.default_phase_specs(), today=TODAY)
        self.assertFalse(result.ok)
        joined = ' '.join(result.reasons_fr)
        self.assertIn('Backlog insuffisant', joined)
        self.assertIn('Diversité insuffisante', joined)
        self.assertIn('Garde-fous non configurés', joined)
        self.assertIn('Alertes non câblées', joined)
        # materialize() refuse le plan.
        with self.assertRaises(ValueError):
            flightplan.materialize(
                plan, flightplan.default_phase_specs(), today=TODAY)
        self.assertEqual(FlightPhase.objects.count(), 0)

    def test_low_diversity_alone_refuses(self):
        # Volume OK (12) mais une seule accroche → diversité 1 < 4.
        self._seed_backlog(count=12, distinct_hooks=1)
        self._seed_guardrails_and_alerts()
        result = flightplan.preflight(
            self.company, flightplan.default_phase_specs(), today=TODAY)
        self.assertFalse(result.ok)
        self.assertTrue(
            any('Diversité insuffisante' in r for r in result.reasons_fr))

    def test_bad_phase_bounds_refused(self):
        self._valid_plan()
        bad = [{'name': 'X', 'tested_variable': 'hook', 'num_arms': 5,
                'week_span': 1}]
        result = flightplan.preflight(self.company, bad, today=TODAY)
        self.assertFalse(result.ok)
        joined = ' '.join(result.reasons_fr)
        self.assertIn('bras hors bornes', joined)
        self.assertIn('semaine(s) hors bornes', joined)

    def test_mde_check_can_veto_a_phase(self):
        self._valid_plan()

        def veto(company, spec):
            return False, 'volume trop faible'

        result = flightplan.preflight(
            self.company, flightplan.default_phase_specs(), today=TODAY,
            mde_check=veto)
        self.assertFalse(result.ok)
        self.assertTrue(
            any('sanité MDE' in r for r in result.reasons_fr))

    # ── Succès + matérialisation ─────────────────────────────────────────────
    def test_valid_plan_materializes_planned_phases(self):
        plan = self._valid_plan()
        result = flightplan.preflight(
            self.company, flightplan.default_phase_specs(), today=TODAY)
        self.assertTrue(result.ok, result.reasons_fr)

        phases = flightplan.materialize(
            plan, flightplan.default_phase_specs(), today=TODAY)
        self.assertEqual(len(phases), len(flightplan.PHASE_SEQUENCE))
        # Ordonnées, une variable par phase, dates séquentielles.
        self.assertEqual([p.tested_variable for p in phases],
                         list(flightplan.PHASE_SEQUENCE))
        self.assertEqual([p.order for p in phases], [0, 1, 2, 3, 4])
        for earlier, later in zip(phases, phases[1:]):
            self.assertEqual(earlier.end_date, later.start_date)
        plan.refresh_from_db()
        self.assertEqual(plan.status, FlightPlan.Statut.ACTIF)
        self.assertEqual(plan.end_date, phases[-1].end_date)

    def test_default_phase_specs_are_all_valid(self):
        for spec in flightplan.default_phase_specs():
            self.assertEqual(flightplan.validate_phase_spec(spec), [])
