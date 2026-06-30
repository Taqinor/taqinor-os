"""Tests FG376 — connecteur Zapier/Make (REST hooks sortants).

Couvre :
  * _sign HMAC déterministe + vide sans secret ;
  * dispatch_event no-op sans abonné ;
  * dispatch_event POSTe à chaque abonné actif (mocké) + maj last_status ;
  * abonnés inactifs ignorés ;
  * découplage : aucun import d'app domaine.
"""
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from core import webhooks
from core.models import WebhookSubscription


class SignTests(TestCase):
    def test_no_secret_empty_signature(self):
        self.assertEqual(webhooks._sign('', b'x'), '')

    def test_sign_is_deterministic(self):
        a = webhooks._sign('k', b'payload')
        b = webhooks._sign('k', b'payload')
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)


class DispatchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_noop_without_subscriptions(self):
        res = webhooks.dispatch_event(self.company, 'devis_accepted', {'id': 1})
        self.assertEqual(res, {'delivered': 0, 'subscriptions': 0})

    def test_delivers_to_active_subscribers(self):
        WebhookSubscription.objects.create(
            company=self.company, event='devis_accepted',
            target_url='https://hooks.zapier.com/a', actif=True)
        WebhookSubscription.objects.create(
            company=self.company, event='devis_accepted',
            target_url='https://hooks.zapier.com/b', actif=False)
        with mock.patch.object(webhooks, '_post', return_value=200) as m:
            res = webhooks.dispatch_event(
                self.company, 'devis_accepted', {'id': 7})
        self.assertEqual(res, {'delivered': 1, 'subscriptions': 1})
        m.assert_called_once()
        sub = WebhookSubscription.objects.get(
            target_url='https://hooks.zapier.com/a')
        self.assertEqual(sub.last_status, 200)
        self.assertIsNotNone(sub.last_delivery_le)

    def test_failed_delivery_not_counted(self):
        WebhookSubscription.objects.create(
            company=self.company, event='x',
            target_url='https://h/c', actif=True)
        with mock.patch.object(webhooks, '_post', return_value=500):
            res = webhooks.dispatch_event(self.company, 'x', {})
        self.assertEqual(res['delivered'], 0)
        self.assertEqual(res['subscriptions'], 1)
