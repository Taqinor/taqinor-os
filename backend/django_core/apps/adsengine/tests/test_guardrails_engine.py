"""ENG9 — Tests du moteur de garde-fous (checks pré-apply + détecteur d'anomalie).

Invariants prouvés :
  * chaque check pré-apply bloque une violation ET une règle inopérante (entrée
    manquante) lève ``GuardrailInoperative`` — jamais un skip silencieux ;
  * le détecteur d'anomalie (dépense > 0, 0 résultat) crée UNE proposition de
    pause (jamais appliquée) + une alerte, dédupe les runs, et tourne dégradé
    (fenêtre par défaut) sans config au lieu de skipper en silence.
"""
import datetime
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import guardrails
from apps.adsengine.models import (
    AdCampaignMirror, EngineAction, GuardrailConfig, InsightSnapshot,
)


class PreApplyPureChecksTests(SimpleTestCase):
    """Checks purs (statut) — aucune base de données."""

    def test_never_activate_raises(self):
        with self.assertRaises(guardrails.GuardrailViolation):
            guardrails.enforce_never_activate('ACTIVE')

    def test_paused_only_allows_paused_and_empty(self):
        self.assertTrue(guardrails.enforce_paused_only('PAUSED'))
        self.assertTrue(guardrails.enforce_paused_only(''))

    def test_paused_only_rejects_any_other_status(self):
        for bad in ('ACTIVE', 'ARCHIVED', 'DELETED'):
            with self.assertRaises(guardrails.GuardrailViolation):
                guardrails.enforce_paused_only(bad)


class BudgetChecksTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BC Co', slug='bc-co')
        self.config = GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=100,
            weekly_change_pct_max=20)

    def test_daily_ceiling_ok(self):
        self.assertTrue(guardrails.check_daily_ceiling(self.config, 90))

    def test_daily_ceiling_violation(self):
        with self.assertRaises(guardrails.GuardrailViolation):
            guardrails.check_daily_ceiling(self.config, 150)

    def test_daily_ceiling_inoperative_without_config(self):
        with self.assertRaises(guardrails.GuardrailInoperative):
            guardrails.check_daily_ceiling(None, 50)

    def test_daily_ceiling_inoperative_bad_budget(self):
        with self.assertRaises(guardrails.GuardrailInoperative):
            guardrails.check_daily_ceiling(self.config, 'abc')

    def test_weekly_change_ok(self):
        self.assertTrue(guardrails.check_weekly_change(
            self.config, current_budget=100, new_budget=110))

    def test_weekly_change_violation(self):
        with self.assertRaises(guardrails.GuardrailViolation):
            guardrails.check_weekly_change(
                self.config, current_budget=100, new_budget=200)

    def test_weekly_change_inoperative_without_current(self):
        # Budget courant nul → aucune base de comparaison → règle inopérante.
        with self.assertRaises(guardrails.GuardrailInoperative):
            guardrails.check_weekly_change(
                self.config, current_budget=0, new_budget=50)

    def test_inoperative_emits_alert(self):
        with patch.object(guardrails, 'emit_alert') as mock_alert:
            with self.assertRaises(guardrails.GuardrailInoperative):
                guardrails.check_daily_ceiling(
                    None, 50, company=self.company)
            mock_alert.assert_called_once()
            self.assertEqual(
                mock_alert.call_args.kwargs['alert_type'],
                guardrails.ALERT_INOPERATIVE)


class AnomalyDetectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='An Co', slug='an-co')
        self.config = GuardrailConfig.objects.create(
            company=self.company, anomaly_window_hours=48)
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.today = datetime.date(2026, 7, 16)

    def _insight(self, *, spend, results, date=None):
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.camp.pk,
            date=date or self.today, spend=spend, results=results)

    def test_spend_without_results_proposes_pause_and_alerts(self):
        self._insight(spend='30.00', results=0)
        with patch.object(guardrails, 'emit_alert') as mock_alert:
            created = guardrails.detect_anomalies(
                self.company, now=self.today, config=self.config)
        self.assertEqual(len(created), 1)
        action = created[0]
        self.assertEqual(action.kind, EngineAction.Kind.PAUSE)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.payload['target_meta_id'], 'c1')
        # Une alerte anomalie est émise, jamais une application silencieuse.
        anomaly_calls = [
            c for c in mock_alert.call_args_list
            if c.kwargs.get('alert_type') == guardrails.ALERT_ANOMALY]
        self.assertEqual(len(anomaly_calls), 1)

    def test_no_anomaly_when_results_present(self):
        self._insight(spend='30.00', results=5)
        created = guardrails.detect_anomalies(
            self.company, now=self.today, config=self.config)
        self.assertEqual(created, [])
        self.assertFalse(EngineAction.objects.filter(
            kind=EngineAction.Kind.PAUSE).exists())

    def test_no_anomaly_when_no_spend(self):
        self._insight(spend='0.00', results=0)
        created = guardrails.detect_anomalies(
            self.company, now=self.today, config=self.config)
        self.assertEqual(created, [])

    def test_second_run_does_not_duplicate_proposal(self):
        self._insight(spend='30.00', results=0)
        first = guardrails.detect_anomalies(
            self.company, now=self.today, config=self.config)
        second = guardrails.detect_anomalies(
            self.company, now=self.today, config=self.config)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(EngineAction.objects.filter(
            kind=EngineAction.Kind.PAUSE).count(), 1)

    def test_out_of_window_snapshot_ignored(self):
        self._insight(spend='30.00', results=0,
                      date=self.today - datetime.timedelta(days=10))
        created = guardrails.detect_anomalies(
            self.company, now=self.today, config=self.config)
        self.assertEqual(created, [])

    def test_degraded_without_config_alerts_and_still_runs(self):
        self._insight(spend='30.00', results=0)
        with patch.object(guardrails, 'emit_alert') as mock_alert:
            created = guardrails.detect_anomalies(
                self.company, now=self.today, config=None)
        # Sans config : tourne en dégradé (fenêtre 48 h) + alerte inopérante.
        self.assertEqual(len(created), 1)
        inop_calls = [
            c for c in mock_alert.call_args_list
            if c.kwargs.get('alert_type') == guardrails.ALERT_INOPERATIVE]
        self.assertEqual(len(inop_calls), 1)


class EmitAlertHookTests(SimpleTestCase):
    def test_emit_alert_is_log_only_at_eng9(self):
        # HOOK ENG9 : log-only, renvoie None (ENG13 branchera EngineAlert).
        result = guardrails.emit_alert(
            None, alert_type=guardrails.ALERT_ANOMALY, message='x')
        self.assertIsNone(result)
