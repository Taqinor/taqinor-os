"""ADSENG15 — Tests de l'évaluateur de règles du Gardien.

Prouve : les cadences beat sont enregistrées ET routées vers ``scheduled`` ;
le chemin auto vs propose est correct (capacité ENG8) ; la simulation ne joue
JAMAIS rien (propose + [Simulation], aucune alerte) ; l'idempotence dédupe un
beat rejoué (jamais d'action auto en double) ; ``last_result`` est écrit à
chaque évaluation ; une branche insufficient_data alerte toujours ; et le filtre
de cadence isole la boucle critique de la boucle quotidienne.
"""
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import rules_engine
from apps.adsengine.rule_templates import CADENCE_CRITICAL, CADENCE_DAILY
from apps.adsengine.models import (
    AdSetMirror, EngineAction, EngineAlert, GuardrailConfig, InsightSnapshot,
    RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)


class FakeClient:
    """Client Meta factice : create_ad renvoie un id (jamais d'appel réseau)."""

    def __init__(self):
        self.calls = []

    def create_ad(self, **kwargs):
        self.calls.append(('create_ad', kwargs))
        return {'id': 'ad_fake', 'status': 'PAUSED'}


def _seed_frequency(company, adset, *, freq, days):
    ct = ContentType.objects.get_for_model(AdSetMirror)
    for i in range(days):
        InsightSnapshot.objects.create(
            company=company, content_type=ct, object_id=adset.pk,
            date=TODAY - datetime.timedelta(days=i),
            spend='10.00', results=1, frequency=str(freq))


class BeatRegistrationTests(SimpleTestCase):
    def test_guardian_beats_registered_and_routed(self):
        from erp_agentique.celery import app
        beat_tasks = {e['task'] for e in app.conf.beat_schedule.values()}
        for name in ('adsengine.evaluate_guardrails',
                     'adsengine.evaluate_optimization_rules'):
            self.assertIn(name, beat_tasks, f'{name} absent du beat')
            self.assertEqual(
                settings.CELERY_TASK_ROUTES[name]['queue'], 'scheduled')


class FrequencyRuleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RE Co', slug='re-co')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='AS', status='PAUSED')

    def _rule(self, **kw):
        defaults = dict(company=self.company, template_key='frequency_high',
                        enabled=True)
        defaults.update(kw)
        return RulePolicy.objects.create(**defaults)

    def test_dry_run_proposes_with_simulation_prefix_and_no_alert(self):
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        self._rule(dry_run=True)
        rules_engine.evaluate_company(self.company, now=TODAY)
        actions = EngineAction.objects.filter(company=self.company)
        self.assertEqual(actions.count(), 1)
        action = actions.first()
        self.assertFalse(action.auto)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertTrue(action.reason_fr.startswith('[Simulation] '))
        # Simulation → aucune alerte (visible in-app via le journal seulement).
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 0)

    def test_propose_mode_creates_proposal_and_alert(self):
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        self._rule(dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        action = EngineAction.objects.get(company=self.company)
        self.assertFalse(action.auto)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company).exists())

    def test_auto_mode_capability_off_only_proposes(self):
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=False)
        self._rule(dry_run=False, mode=RulePolicy.Mode.AUTO)
        rules_engine.evaluate_company(self.company, now=TODAY)
        action = EngineAction.objects.get(company=self.company)
        self.assertFalse(action.auto)  # capacité OFF → proposition, jamais auto
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_auto_mode_capability_on_applies_once(self):
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        config = GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=True)
        self._rule(dry_run=False, mode=RulePolicy.Mode.AUTO)
        client = FakeClient()
        rules_engine.evaluate_company(
            self.company, now=TODAY, client=client, config=config)
        action = EngineAction.objects.get(company=self.company)
        self.assertTrue(action.auto)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertEqual(len(client.calls), 1)

    def test_idempotent_double_beat_no_duplicate_auto_action(self):
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        config = GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=True)
        self._rule(dry_run=False, mode=RulePolicy.Mode.AUTO)
        client = FakeClient()
        # Deux beats rejoués coup sur coup : une SEULE action auto (dédup).
        rules_engine.evaluate_company(
            self.company, now=TODAY, client=client, config=config)
        rules_engine.evaluate_company(
            self.company, now=TODAY, client=client, config=config)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 1)

    def test_insufficient_data_always_alerts_no_action(self):
        # Un seul snapshot (< min_samples=3) → insufficient_data → alerte, jamais
        # d'action (jamais un skip muet — piège Madgicx).
        _seed_frequency(self.company, self.adset, freq=4.0, days=1)
        self._rule(dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company).exists())

    def test_last_result_written_even_when_not_fired(self):
        _seed_frequency(self.company, self.adset, freq=2.0, days=4)  # < seuil
        rule = self._rule(dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        rule.refresh_from_db()
        self.assertTrue(rule.last_result.get('evaluated'))
        self.assertFalse(rule.last_result.get('fired'))
        self.assertIsNotNone(rule.last_evaluated_at)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_cadence_filter_skips_wrong_cadence(self):
        # frequency_high est une règle QUOTIDIENNE : la boucle CRITIQUE ne
        # l'évalue pas (ne touche même pas last_result).
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        rule = self._rule(dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(
            self.company, cadences=frozenset({CADENCE_CRITICAL}), now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        rule.refresh_from_db()
        self.assertIsNone(rule.last_evaluated_at)
        # Mais la cadence QUOTIDIENNE l'évalue bien.
        rules_engine.evaluate_company(
            self.company, cadences=frozenset({CADENCE_DAILY}), now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 1)

    def test_disabled_rule_never_evaluated(self):
        _seed_frequency(self.company, self.adset, freq=4.0, days=4)
        rule = self._rule(enabled=False, dry_run=False)
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        rule.refresh_from_db()
        self.assertIsNone(rule.last_evaluated_at)
