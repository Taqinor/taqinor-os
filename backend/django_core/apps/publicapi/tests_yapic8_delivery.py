"""YAPIC8 — livraison webhook fiable : signature horodatée, event_id stable,
retries Celery bornés.

Le broker Redis existe en CI mais aucun worker ne tourne : on exécute les
tâches EN LIGNE (eager) pour exercer la livraison réelle dans le processus de
test. La résolution SSRF est neutralisée (hôte de test non résolvable).
"""
import hashlib
import hmac
import json
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from . import delivery
from .constants import EVENT_LEAD_CREATED
from .models import Webhook, WebhookDelivery
from .tasks import deliver_webhook


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


class Yapic8DeliveryTests(TestCase):
    def setUp(self):
        self.co = _company('yapic8', 'YAPIC8')
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/hook',
            secret='s3cr3t', events=[EVENT_LEAD_CREATED], enabled=True)
        p = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        p.start()
        self.addCleanup(p.stop)
        from erp_agentique.celery import app as celery_app
        prev = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = False
        self.addCleanup(
            lambda: setattr(celery_app.conf, 'task_always_eager', prev))

    def _capture_post(self, status_code=200):
        captured = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            captured['headers'] = headers
            captured['content'] = content
            return mock.Mock(status_code=status_code)

        return captured, fake_post

    def test_signature_covers_timestamp(self):
        captured, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED, {'id': 1})
        ts = captured['headers'][delivery.TIMESTAMP_HEADER]
        body = captured['content']
        good = hmac.new(b's3cr3t', f'{ts}.'.encode('utf-8') + body,
                        hashlib.sha256).hexdigest()
        self.assertEqual(captured['headers'][delivery.SIGNATURE_HEADER], good)
        # A different timestamp yields a different signature (anti-replay): the
        # receiver rejecting an out-of-tolerance timestamp is therefore safe.
        other = hmac.new(b's3cr3t', b'0.' + body, hashlib.sha256).hexdigest()
        self.assertNotEqual(good, other)

    def test_event_id_injected_into_payload_and_recorded(self):
        captured, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED, {'id': 1})
        sent = json.loads(captured['content'].decode('utf-8'))
        self.assertTrue(sent.get('event_id'))
        d = WebhookDelivery.objects.get()
        self.assertEqual(d.event_id, sent['event_id'])

    def test_event_id_stable_across_attempts(self):
        # First (automatic) delivery, then a replay reusing the same payload:
        # both attempts carry the SAME stable event_id.
        _c, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED, {'id': 1})
        first = WebhookDelivery.objects.get()
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery._deliver_one(self.hook, first.event, first.payload)
        ids = list(WebhookDelivery.objects.values_list('event_id', flat=True))
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0], ids[1])
        self.assertTrue(ids[0])

    def test_failed_delivery_retries_and_ends_failed(self):
        # A 500 endpoint is retried, then the terminal attempt stays FAILED.
        # Patch retry to raise MaxRetriesExceededError deterministically (no
        # eager-loop timing dependence); the task must catch it and record.
        _c, fake_post = self._capture_post(500)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post), \
                mock.patch.object(
                    deliver_webhook, 'retry',
                    side_effect=deliver_webhook.MaxRetriesExceededError):
            deliver_webhook.apply(
                args=[self.hook.id, EVENT_LEAD_CREATED,
                      {'id': 1, 'event_id': 'fixed-id'}])
        deliveries = WebhookDelivery.objects.all()
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(deliveries[0].status, WebhookDelivery.Statut.FAILED)
        self.assertEqual(deliveries[0].event_id, 'fixed-id')

    def test_ssrf_target_blocked_no_retry(self):
        from .validators import UnsafeWebhookURL
        with mock.patch(
                'apps.publicapi.delivery.validate_webhook_target_url',
                side_effect=UnsafeWebhookURL('interne')), \
                mock.patch.object(deliver_webhook, 'retry') as retry_mock:
            deliver_webhook.apply(
                args=[self.hook.id, EVENT_LEAD_CREATED, {'event_id': 'x'}])
        # SSRF is permanent — recorded FAILED, never retried.
        d = WebhookDelivery.objects.get()
        self.assertEqual(d.status, WebhookDelivery.Statut.FAILED)
        retry_mock.assert_not_called()
