"""PUB101 — Tests de la santé du compte lue au sync (jamais devinée).

Prouve : ``get_account_health`` traduit les codes Meta en libellés FR + statut
sain/anormal (dégradation propre si champ absent) ; ``check_account_health``
lève une alerte typée liée au playbook FR sur un statut ≠ actif (CRITICAL pour
désactivé/fermé, WARNING pour revue/grâce), dédupliquée et résolue au retour à
l'actif ; scoping société.
"""
from django.test import TestCase

from authentication.models import Company

from apps.adsengine.models import EngineAlert, MetaConnection
from apps.adsengine.rules import SEVERITY_CRITICAL, SEVERITY_WARNING
from apps.adsengine.tasks import check_account_health


class _FakeHealthClient:
    def __init__(self, health):
        self._health = health

    def get_account_health(self):
        return self._health


def _health(status, reason=0):
    from apps.adsengine.meta_client import MetaClient
    return {
        'account_status': status,
        'account_status_label': MetaClient.ACCOUNT_STATUS_FR.get(status, ''),
        'disable_reason': reason,
        'disable_reason_label': MetaClient.DISABLE_REASON_FR.get(reason, ''),
        'is_healthy': status in MetaClient.ACCOUNT_STATUS_HEALTHY,
        'name': 'Compte test',
    }


class AccountHealthMappingTests(TestCase):
    def test_active_is_healthy(self):
        from apps.adsengine.meta_client import MetaClient
        h = _health(1)
        self.assertTrue(h['is_healthy'])
        self.assertEqual(
            MetaClient.ACCOUNT_STATUS_FR[2], 'Désactivé')

    def test_disabled_not_healthy(self):
        self.assertFalse(_health(2, 1)['is_healthy'])


class CheckAccountHealthTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Health Co', slug='health-co')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 't'}, ad_account_id='act_1')

    def test_disabled_emits_critical_alert(self):
        alert = check_account_health(
            self.company, self.conn, _FakeHealthClient(_health(2, 1)))
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, SEVERITY_CRITICAL)
        self.assertEqual(alert.entity_key, 'account_status')
        self.assertEqual(alert.alert_type, EngineAlert.Type.GARDE_FOU)
        self.assertIn('compte-restreint.md', alert.detail['playbook'])

    def test_risk_review_emits_warning(self):
        alert = check_account_health(
            self.company, self.conn, _FakeHealthClient(_health(7)))
        self.assertEqual(alert.severity, SEVERITY_WARNING)

    def test_active_resolves_open_alert(self):
        check_account_health(
            self.company, self.conn, _FakeHealthClient(_health(2, 1)))
        self.assertEqual(EngineAlert.objects.filter(
            entity_key='account_status', resolved=False).count(), 1)
        check_account_health(
            self.company, self.conn, _FakeHealthClient(_health(1)))
        self.assertEqual(EngineAlert.objects.filter(
            entity_key='account_status', resolved=False).count(), 0)

    def test_healthy_no_alert(self):
        alert = check_account_health(
            self.company, self.conn, _FakeHealthClient(_health(1)))
        self.assertIsNone(alert)
        self.assertEqual(EngineAlert.objects.count(), 0)

    def test_no_double_alert(self):
        client = _FakeHealthClient(_health(2, 1))
        check_account_health(self.company, self.conn, client)
        check_account_health(self.company, self.conn, client)
        self.assertEqual(EngineAlert.objects.filter(
            entity_key='account_status').count(), 1)

    def test_degradation_when_status_absent(self):
        # account_status None (API sans le champ) → is_healthy True → aucune alarme.
        client = _FakeHealthClient({
            'account_status': None, 'account_status_label': '',
            'disable_reason': None, 'disable_reason_label': '',
            'is_healthy': True, 'name': ''})
        alert = check_account_health(self.company, self.conn, client)
        self.assertIsNone(alert)
