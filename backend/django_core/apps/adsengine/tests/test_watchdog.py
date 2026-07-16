"""ADSENG17 — Tests du watchdog de l'évaluateur.

Prouve : le heartbeat se pose et se lit ; un évaluateur « tué » (heartbeat
absent/périmé) déclenche une alerte 🔴 dédiée (dédupliquée) ; une règle qui lève
déclenche une alerte 🔴 dédiée ; la santé est exposée à l'endpoint ENG12
(wiring-health) ; et ``evaluate_company`` pose bien un heartbeat.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rules_engine, watchdog
from apps.adsengine.models import EngineAlert
from apps.adsengine.rules import SEVERITY_CRITICAL

User = get_user_model()
WIRING = '/api/django/adsengine/wiring-health/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class HeartbeatTests(TestCase):
    def setUp(self):
        cache.clear()  # LocMem par process — jamais de fuite entre tests
        self.company = Company.objects.create(nom='WD Co', slug='wd-co')

    def test_record_and_read_heartbeat(self):
        self.assertIsNone(watchdog.last_heartbeat(self.company))
        watchdog.record_heartbeat(self.company)
        self.assertIsNotNone(watchdog.last_heartbeat(self.company))
        self.assertFalse(watchdog.is_stale(self.company))

    def test_no_heartbeat_is_stale(self):
        self.assertTrue(watchdog.is_stale(self.company))

    def test_old_heartbeat_is_stale(self):
        old = timezone.now() - datetime.timedelta(hours=48)
        watchdog.record_heartbeat(self.company, now=old)
        self.assertTrue(watchdog.is_stale(self.company, max_age_hours=24))

    def test_health_shape(self):
        h = watchdog.health(self.company)
        self.assertFalse(h['healthy'])
        self.assertTrue(h['stale'])
        self.assertIsNone(h['evaluator_last_run'])
        watchdog.record_heartbeat(self.company)
        h2 = watchdog.health(self.company)
        self.assertTrue(h2['healthy'])
        self.assertFalse(h2['stale'])
        self.assertIsNotNone(h2['evaluator_last_run'])


class WatchdogAlertTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='WA Co', slug='wa-co')

    def test_killed_evaluator_raises_watchdog_alert(self):
        # Évaluateur « tué » : aucun heartbeat → alerte 🔴 dédiée.
        alert = watchdog.check_and_alert(self.company)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, SEVERITY_CRITICAL)
        self.assertEqual(alert.alert_type, EngineAlert.Type.REGLE_INOPERANTE)
        self.assertEqual(alert.entity_key, 'watchdog:evaluator')
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 1)

    def test_fresh_heartbeat_no_alert(self):
        watchdog.record_heartbeat(self.company)
        self.assertIsNone(watchdog.check_and_alert(self.company))
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 0)

    def test_check_and_alert_dedups_within_cooldown(self):
        watchdog.check_and_alert(self.company)
        watchdog.check_and_alert(self.company)  # rejoué
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company, entity_key='watchdog:evaluator').count(), 1)

    def test_report_rule_failure_dedicated_critical_alert(self):
        watchdog.report_rule_failure(
            self.company, template_key='frequency_high', error='boom')
        alert = EngineAlert.objects.get(company=self.company)
        self.assertEqual(alert.severity, SEVERITY_CRITICAL)
        self.assertEqual(alert.alert_type, EngineAlert.Type.REGLE_INOPERANTE)
        self.assertIn('frequency_high', alert.entity_key)
        # Dédup : un 2e signalement dans le cooldown n'ajoute pas de doublon.
        watchdog.report_rule_failure(
            self.company, template_key='frequency_high', error='boom')
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 1)


class WatchdogEngineIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='WE Co', slug='we-co')

    def test_evaluate_company_records_heartbeat(self):
        self.assertTrue(watchdog.is_stale(self.company))
        rules_engine.evaluate_company(self.company)
        self.assertFalse(watchdog.is_stale(self.company))
        self.assertTrue(watchdog.health(self.company)['healthy'])


class WiringHealthGuardianTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='WH Co', slug='wh-co')
        self.viewer = make_user(self.company, 'whv', ['adsengine_view'])

    def test_wiring_health_exposes_guardian_block(self):
        resp = auth(self.viewer).get(WIRING)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('guardian', resp.data)
        self.assertIn('healthy', resp.data['guardian'])
        # Sans passage de l'évaluateur, le Gardien est signalé non sain (jamais
        # un « OK » fabriqué).
        self.assertFalse(resp.data['guardian']['healthy'])
