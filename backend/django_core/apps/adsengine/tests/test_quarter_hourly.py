"""ADSDEEP42 — Tests de la cadence QUART-HORAIRE (15 min) opt-in + budgeteur.

Prouve : la boucle quart-horaire n'évalue QUE les règles ayant opté
(``cadence_minutes>0``) et ignore les autres ; et le beat SAUTE une société dont
le compte Meta est en throttle (budgeteur de rate-limit ADSDEEP5 — jamais un 613).
"""
import datetime
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.adsengine import rules_engine, tasks
from apps.adsengine.models import MetaConnection, RulePolicy

TODAY = datetime.date(2026, 7, 16)


class QuarterHourlySelectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QH Co', slug='qh-co', actif=True)

    def test_opt_in_rule_is_evaluated_quarter_hourly(self):
        policy = RulePolicy.objects.create(
            company=self.company, template_key='frequency_high', enabled=True,
            dry_run=True, mode=RulePolicy.Mode.PROPOSE, cadence_minutes=15)
        n = rules_engine.evaluate_company(
            self.company, now=TODAY, quarter_hourly=True)
        self.assertEqual(n, 1)
        policy.refresh_from_db()
        self.assertTrue(policy.last_result.get('evaluated'))

    def test_non_opt_in_rule_skipped_quarter_hourly(self):
        RulePolicy.objects.create(
            company=self.company, template_key='frequency_high', enabled=True,
            dry_run=True, mode=RulePolicy.Mode.PROPOSE)  # cadence_minutes=0
        n = rules_engine.evaluate_company(
            self.company, now=TODAY, quarter_hourly=True)
        self.assertEqual(n, 0)


class QuarterHourlyBeatBudgeterTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QB Co', slug='qb-co', actif=True)
        RulePolicy.objects.create(
            company=self.company, template_key='frequency_high', enabled=True,
            dry_run=True, mode=RulePolicy.Mode.PROPOSE, cadence_minutes=15)

    def test_beat_skips_throttled_company(self):
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1')
        with mock.patch('apps.adsengine.meta_client.rate_limit_status',
                        return_value={'throttled': True, 'usage_pct': 95.0}):
            result = tasks.evaluate_quarter_hourly()
        self.assertEqual(result['throttled_skipped'], 1)
        self.assertEqual(result['evaluated'], 0)

    def test_beat_evaluates_when_not_throttled(self):
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1')
        with mock.patch('apps.adsengine.meta_client.rate_limit_status',
                        return_value={'throttled': False, 'usage_pct': 10.0}):
            result = tasks.evaluate_quarter_hourly()
        self.assertEqual(result['throttled_skipped'], 0)
        self.assertEqual(result['evaluated'], 1)
