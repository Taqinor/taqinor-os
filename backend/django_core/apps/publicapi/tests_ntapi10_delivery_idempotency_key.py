"""NTAPI10 — `Idempotency-Key` sur toutes les livraisons webhook.

Une clé (`WebhookDelivery.idempotency_key`, = `event_id`) par ÉVÈNEMENT
SOURCE, partagée par TOUTES les tentatives (envoi original + reprise
programmée NTAPI8) — deux évènements distincts ont des clés distinctes.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from . import delivery
from .constants import EVENT_LEAD_CREATED
from .models import Webhook, WebhookDelivery
from .retry import schedule_first_retry, run_due_retries


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


class Ntapi10IdempotencyKeyTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi10', 'NTAPI10')
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/hook',
            secret='s3cr3t', events=[EVENT_LEAD_CREATED], enabled=True)
        p = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        p.start()
        self.addCleanup(p.stop)

    def _capture_post(self, status_code=200):
        captured = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            captured['headers'] = headers
            return mock.Mock(status_code=status_code)

        return captured, fake_post

    def test_idempotency_key_header_matches_event_id(self):
        captured, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery._deliver_one(
                self.hook, EVENT_LEAD_CREATED, {'id': 1, 'event_id': 'evt-fixed'})
        self.assertEqual(
            captured['headers'][delivery.IDEMPOTENCY_HEADER], 'evt-fixed')
        wh_delivery = WebhookDelivery.objects.get()
        self.assertEqual(wh_delivery.idempotency_key, 'evt-fixed')
        self.assertEqual(wh_delivery.idempotency_key, wh_delivery.event_id)

    def test_two_distinct_events_get_distinct_keys(self):
        _c, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery._deliver_one(self.hook, EVENT_LEAD_CREATED, {'id': 1})
            delivery._deliver_one(self.hook, EVENT_LEAD_CREATED, {'id': 2})
        keys = list(
            WebhookDelivery.objects.order_by('id')
            .values_list('idempotency_key', flat=True))
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])
        self.assertTrue(all(keys))

    def test_retry_attempt_reuses_same_idempotency_key(self):
        # L'envoi original échoue, la reprise programmée NTAPI8 rejoue le
        # MÊME évènement — l'en-tête d'idempotence envoyé au consommateur est
        # identique sur les deux tentatives.
        wh_delivery = WebhookDelivery.objects.create(
            company=self.co, webhook=self.hook, event=EVENT_LEAD_CREATED,
            event_id='evt-shared', idempotency_key='evt-shared',
            payload={'id': 1, 'event_id': 'evt-shared'},
            status=WebhookDelivery.Statut.FAILED, response_status=500,
            error='HTTP 500')
        schedule_first_retry(wh_delivery, now=timezone.now() - timedelta(days=1))

        captured, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            run_due_retries(now=timezone.now())

        self.assertEqual(
            captured['headers'][delivery.IDEMPOTENCY_HEADER], 'evt-shared')
        wh_delivery.refresh_from_db()
        self.assertEqual(wh_delivery.idempotency_key, 'evt-shared')
