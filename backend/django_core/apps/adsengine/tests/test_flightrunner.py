"""ADSENG35 — Tests de la machine à états ``FlightRunner``.

Prouve, état par état : DRAFT → matérialisation (structures PAUSED) → ACTIVE
(boucles quotidienne/hebdo) → COMPLETED ; l'interrupteur global (kill-switch) ;
l'idempotence des créations (G3) ; et l'INVARIANT PERMANENT re-testé ici — le
runner ne dé-pause JAMAIS rien par programme (règle #3).
"""
import datetime

from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import flightplan, flightrunner
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.management.commands.seed_synthetic_account import (
    generate_synthetic_account,
)
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, CreativeAsset, CreativeBacklogItem,
    DecisionLog, EngineAction, FlightPlan, GuardrailConfig, RulePolicy,
)

TODAY = datetime.date(2026, 7, 13)


class FakeMetaClient:
    """Faux client Meta : trace créations + pauses, n'expose AUCUNE activation.

    Les créations naissent toujours PAUSED (comme le vrai client force PAUSED) ;
    ``get_campaigns``/``get_adsets`` rendent l'inventaire vivant (support de la
    dédup G3). ``update_status_paused`` est la SEULE mutation de statut — il
    n'existe délibérément aucune méthode d'activation."""

    def __init__(self):
        self.campaigns = []
        self.adsets = []
        self.paused = []
        self._seq = 0

    def _next_id(self, prefix):
        self._seq += 1
        return f'{prefix}-{self._seq}'

    def get_campaigns(self, **kw):
        return list(self.campaigns)

    def get_adsets(self, **kw):
        return list(self.adsets)

    def create_campaign(self, *, name, objective, special_ad_categories=None,
                        extra_fields=None):
        cid = self._next_id('cmp')
        self.campaigns.append({'id': cid, 'name': name, 'status': 'PAUSED'})
        return {'id': cid}

    def create_adset(self, *, name, campaign_id, extra_fields=None):
        aid = self._next_id('ast')
        self.adsets.append({'id': aid, 'name': name, 'status': 'PAUSED'})
        return {'id': aid}

    def update_status_paused(self, *, object_id, level=None):
        self.paused.append(object_id)
        return {'success': True}


class FlightRunnerBase(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Runner Co', slug='runner-co')

    def tearDown(self):
        cache.clear()

    def _seed_valid_context(self):
        for i in range(12):
            asset = CreativeAsset.objects.create(
                company=self.company,
                asset_type=CreativeAsset.AssetType.STATIC,
                hook_id=f'H{i % 4}', policy_stamp={'passed': True})
            CreativeBacklogItem.objects.create(
                company=self.company, asset=asset,
                status=CreativeBacklogItem.Statut.EN_FILE)
        GuardrailConfig.objects.create(company=self.company)
        RulePolicy.objects.create(
            company=self.company, template_key='zero_results', enabled=True)

    def _valid_plan(self):
        self._seed_valid_context()
        return FlightPlan.objects.create(
            company=self.company, name='Plan 6 mois', start_date=TODAY)


class StateMachineTests(FlightRunnerBase):
    def test_draft_state_before_materialize(self):
        plan = self._valid_plan()
        runner = FlightRunner(plan, clock=lambda: TODAY)
        self.assertEqual(runner.state(), FlightRunner.STATE_DRAFT)

    def test_materialize_moves_to_active_and_creates_paused_structures(self):
        plan = self._valid_plan()
        client = FakeMetaClient()
        runner = FlightRunner(plan, client=client, clock=lambda: TODAY)

        report = runner.materialize()

        self.assertEqual(runner.state(), FlightRunner.STATE_ACTIVE)
        self.assertEqual(report['phases'], len(flightplan.PHASE_SEQUENCE))
        # Structures de la 1re phase créées PAUSED, marquées created_via_engine.
        camps = AdCampaignMirror.objects.filter(
            company=self.company, created_via_engine=True)
        self.assertEqual(camps.count(), 1)
        self.assertEqual(camps.first().status, 'PAUSED')
        self.assertTrue(AdSetMirror.objects.filter(
            company=self.company, created_via_engine=True,
            status='PAUSED').exists())
        # Actions-log : lignes de création écrites (auto=True, appliquées).
        creates = EngineAction.objects.filter(
            company=self.company, kind=EngineAction.Kind.CREATE_CAMPAIGN)
        self.assertTrue(creates.exists())
        self.assertTrue(all(a.auto for a in creates))

    def test_invalid_plan_refused_no_phase_created(self):
        # Contexte vide (pas de backlog/garde-fous) → préflight refuse.
        plan = FlightPlan.objects.create(
            company=self.company, name='Vide', start_date=TODAY)
        runner = FlightRunner(plan, client=FakeMetaClient(), clock=lambda: TODAY)
        with self.assertRaises(ValueError):
            runner.materialize()
        self.assertFalse(AdCampaignMirror.objects.filter(
            company=self.company).exists())

    def test_advance_phase_completes_plan_at_end(self):
        plan = self._valid_plan()
        client = FakeMetaClient()
        runner = FlightRunner(plan, client=client, clock=lambda: TODAY)
        runner.materialize()
        plan.refresh_from_db()
        # Avance bien APRÈS la fin de la dernière phase → COMPLETED + rapport.
        far_future = plan.end_date + datetime.timedelta(days=1)
        result = runner.advance_phase(today=far_future)
        self.assertTrue(result.get('completed'))
        self.assertEqual(runner.state(), FlightRunner.STATE_COMPLETED)
        self.assertIn('report', result)
        self.assertEqual(result['report']['plan_id'], plan.pk)


class DailyWeeklyLoopTests(FlightRunnerBase):
    def _synthetic(self, scenario='clear_winner'):
        return generate_synthetic_account(
            company=self.company, scenario=scenario, months=1, seed=7,
            create_leads=False)

    def test_run_daily_writes_a_decisionlog_per_experiment(self):
        self._valid_plan()
        self._synthetic()
        plan = FlightPlan.objects.get(company=self.company, name='Plan 6 mois')
        runner = FlightRunner(plan, clock=lambda: datetime.date(2026, 2, 15))

        before = DecisionLog.objects.filter(company=self.company).count()
        report = runner.run_daily(window_days=30)
        after = DecisionLog.objects.filter(company=self.company).count()

        self.assertGreaterEqual(report['decisions'], 1)
        self.assertGreater(after, before)

    def test_run_weekly_generates_brief_and_rotations(self):
        self._valid_plan()
        self._synthetic()
        plan = FlightPlan.objects.get(company=self.company, name='Plan 6 mois')
        runner = FlightRunner(plan, clock=lambda: datetime.date(2026, 2, 15))
        report = runner.run_weekly()
        self.assertIn('rotations', report)
        self.assertTrue(report['brief_generated'])


class KillSwitchTests(FlightRunnerBase):
    def test_kill_switch_pauses_engine_created_and_flags_state(self):
        self._valid_plan()
        generate_synthetic_account(
            company=self.company, scenario='clear_winner', months=1, seed=3,
            create_leads=False)
        plan = FlightPlan.objects.get(company=self.company, name='Plan 6 mois')
        client = FakeMetaClient()
        runner = FlightRunner(plan, client=client, clock=lambda: TODAY)

        self.assertFalse(runner.is_killed())
        result = runner.engage_kill_switch()

        self.assertTrue(runner.is_killed())
        self.assertEqual(runner.state(), FlightRunner.STATE_KILLED)
        # A mis en pause via le client (campagne + ad set créés par le moteur).
        self.assertGreaterEqual(result['paused'], 2)
        self.assertGreaterEqual(len(client.paused), 2)
        # Actions-log : lignes PAUSE écrites (marquées kill_switch).
        self.assertTrue(EngineAction.objects.filter(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            payload__kill_switch=True).exists())

    def test_loops_noop_when_killed(self):
        self._valid_plan()
        generate_synthetic_account(
            company=self.company, scenario='clear_winner', months=1, seed=3,
            create_leads=False)
        plan = FlightPlan.objects.get(company=self.company, name='Plan 6 mois')
        runner = FlightRunner(plan, client=FakeMetaClient(), clock=lambda: TODAY)
        runner.engage_kill_switch()

        daily = runner.run_daily()
        weekly = runner.run_weekly()
        self.assertEqual(daily.get('skipped'), 'kill_switch')
        self.assertEqual(weekly.get('skipped'), 'kill_switch')

    def test_release_kill_switch_never_unpauses(self):
        self._valid_plan()
        plan = FlightPlan.objects.get(company=self.company, name='Plan 6 mois')
        runner = FlightRunner(plan, client=FakeMetaClient(), clock=lambda: TODAY)
        runner.engage_kill_switch()
        out = runner.release_kill_switch()
        self.assertFalse(runner.is_killed())
        # Relâcher NE dé-pause RIEN (unpause humain requis).
        self.assertEqual(out['unpaused'], 0)


class NeverProgrammaticUnpauseTests(FlightRunnerBase):
    def test_runner_exposes_no_activation_method(self):
        plan = self._valid_plan()
        runner = FlightRunner(plan, clock=lambda: TODAY)
        for name in ('activate', 'unpause', 'resume', 'enable', 'go_live',
                     'unpause_all', 'reactivate', 'set_active'):
            self.assertFalse(
                hasattr(runner, name),
                f'FlightRunner ne doit exposer aucune méthode « {name} » — '
                'invariant #3 (jamais d\'unpause programmatique).')

    def test_client_only_ever_receives_paused_creations(self):
        # Une matérialisation complète : le faux client n'a reçu que des
        # créations PAUSED (aucune activation possible — le client n'en a pas).
        plan = self._valid_plan()
        client = FakeMetaClient()
        runner = FlightRunner(plan, client=client, clock=lambda: TODAY)
        runner.materialize()
        self.assertTrue(client.campaigns)
        self.assertTrue(all(c['status'] == 'PAUSED' for c in client.campaigns))
        self.assertTrue(all(a['status'] == 'PAUSED' for a in client.adsets))

    def test_autonomy_flag_off_by_default(self):
        self.assertFalse(flightrunner.is_autonomy_active(self.company))


class IdempotencyG3Tests(FlightRunnerBase):
    def test_materialize_twice_creates_no_duplicate_campaign(self):
        plan = self._valid_plan()
        client = FakeMetaClient()
        runner = FlightRunner(plan, client=client, clock=lambda: TODAY)
        runner.materialize()
        n_campaigns = len(client.campaigns)

        # Re-lancer la création de la 1re phase (retry après « réponse perdue ») :
        # la dédup par nom réutilise l'existant — aucun doublon POSTé.
        phase = plan.phases.order_by('order').first()
        out = runner._launch_phase(phase, client=client)

        self.assertTrue(out['campaign_reused'])
        self.assertEqual(len(client.campaigns), n_campaigns)
        self.assertEqual(
            AdCampaignMirror.objects.filter(
                company=self.company, created_via_engine=True).count(),
            n_campaigns)
