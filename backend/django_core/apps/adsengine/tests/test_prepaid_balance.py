"""PUB97 — Tests de la surveillance du solde prépayé Meta (trésorerie).

Prouve : le détecteur PUR (solde bas → warning/critical, dégradation propre quand
le champ solde manque ou sans dépense), la conversion unités mineures→majeures du
client, et le câblage ``check_prepaid_balance`` (alerte typée à solde bas, résolue
à solde sain, alerte INFO de dégradation quand l'API n'expose pas le champ).
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import anomaly
from apps.adsengine.meta_client import MetaClient
from apps.adsengine.models import (
    AdCampaignMirror, EngineAlert, InsightSnapshot, MetaConnection,
)
from apps.adsengine.rules import SEVERITY_CRITICAL, SEVERITY_WARNING
from apps.adsengine.tasks import check_prepaid_balance


class _FakeBalanceClient:
    def __init__(self, info):
        self._info = info

    def get_account_balance(self):
        return self._info


class LowBalanceDetectorTests(TestCase):
    def test_warning_below_threshold(self):
        det = anomaly.detect_low_balance(200.0, 50.0, min_days_runway=5.0)
        self.assertTrue(det.fired)
        self.assertEqual(det.severity, SEVERITY_WARNING)
        self.assertEqual(det.computed['days_runway'], 4.0)

    def test_critical_below_half_threshold(self):
        det = anomaly.detect_low_balance(50.0, 50.0, min_days_runway=5.0)
        self.assertTrue(det.fired)
        self.assertEqual(det.severity, SEVERITY_CRITICAL)

    def test_healthy_balance_not_fired(self):
        det = anomaly.detect_low_balance(1000.0, 50.0, min_days_runway=5.0)
        self.assertFalse(det.fired)
        self.assertFalse(det.insufficient_data)

    def test_missing_field_degrades(self):
        det = anomaly.detect_low_balance(None, 50.0)
        self.assertFalse(det.fired)
        self.assertTrue(det.insufficient_data)

    def test_no_spend_no_alarm(self):
        det = anomaly.detect_low_balance(10.0, 0.0)
        self.assertFalse(det.fired)
        self.assertTrue(det.insufficient_data)


class MinorToMajorTests(TestCase):
    def test_cents_to_major(self):
        self.assertEqual(MetaClient._minor_to_major('12345'), Decimal('123.45'))

    def test_missing_is_none(self):
        self.assertIsNone(MetaClient._minor_to_major(None))
        self.assertIsNone(MetaClient._minor_to_major(''))
        self.assertIsNone(MetaClient._minor_to_major('abc'))


class CheckPrepaidBalanceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bal Co', slug='bal-co')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 't'}, ad_account_id='act_1',
            currency='MAD')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _spend(self, days_ago, amount):
        day = datetime.date.today() - datetime.timedelta(days=days_ago)
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=day, spend=Decimal(amount))

    def test_low_balance_emits_alert(self):
        for d in range(1, 4):
            self._spend(d, '100.00')  # ~100 MAD/j
        client = _FakeBalanceClient({
            'balance': Decimal('150.00'), 'currency': 'MAD',
            'has_balance_field': True})
        alert = check_prepaid_balance(self.company, self.conn, client)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.entity_key, 'prepaid_balance')
        self.assertFalse(alert.resolved)
        self.assertEqual(alert.detail['kind'], anomaly.KIND_LOW_BALANCE)

    def test_healthy_balance_resolves_open_alert(self):
        for d in range(1, 4):
            self._spend(d, '100.00')
        # d'abord bas → alerte ouverte
        check_prepaid_balance(self.company, self.conn,
                              _FakeBalanceClient({'balance': Decimal('120.00'),
                                                  'currency': 'MAD',
                                                  'has_balance_field': True}))
        self.assertEqual(EngineAlert.objects.filter(
            entity_key='prepaid_balance', resolved=False).count(), 1)
        # puis sain → résolue
        check_prepaid_balance(self.company, self.conn,
                              _FakeBalanceClient({'balance': Decimal('9999.00'),
                                                  'currency': 'MAD',
                                                  'has_balance_field': True}))
        self.assertEqual(EngineAlert.objects.filter(
            entity_key='prepaid_balance', resolved=False).count(), 0)

    def test_no_double_alert_on_persistent_low(self):
        for d in range(1, 4):
            self._spend(d, '100.00')
        client = _FakeBalanceClient({'balance': Decimal('120.00'),
                                     'currency': 'MAD',
                                     'has_balance_field': True})
        check_prepaid_balance(self.company, self.conn, client)
        check_prepaid_balance(self.company, self.conn, client)
        self.assertEqual(EngineAlert.objects.filter(
            entity_key='prepaid_balance').count(), 1)

    def test_missing_field_info_alert(self):
        for d in range(1, 4):
            self._spend(d, '100.00')
        client = _FakeBalanceClient({'balance': None, 'currency': 'MAD',
                                     'has_balance_field': False})
        alert = check_prepaid_balance(self.company, self.conn, client)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'info')
        self.assertFalse(alert.detail['has_balance_field'])
