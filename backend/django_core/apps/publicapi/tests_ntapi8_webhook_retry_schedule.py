"""NTAPI8 — reprises programmées à backoff long (1m/5m/30m/2h/6h, max 6).

Teste `retry.py` en isolation (jamais de dépendance au minutage Celery réel
— cf. `tests_yapic8_delivery.py` pour les reprises Celery immédiates) :
programmation de la première reprise, cascade multi-échecs avec délais
croissants, succès final SANS doublon métier, abandon définitif après
6 tentatives, et non-interférence entre sociétés/webhooks.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from . import delivery
from .constants import EVENT_LEAD_CREATED
from .models import Webhook, WebhookDelivery, WebhookDeliveryAttempt
from .retry import RETRY_DELAYS_SECONDS, MAX_ATTEMPTS, schedule_first_retry, run_due_retries


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


class Ntapi8RetryScheduleTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi8', 'NTAPI8')
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/hook',
            secret='s3cr3t', events=[EVENT_LEAD_CREATED], enabled=True)
        p = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        p.start()
        self.addCleanup(p.stop)

    def _failed_delivery(self, event_id='fixed-id'):
        return WebhookDelivery.objects.create(
            company=self.co, webhook=self.hook, event=EVENT_LEAD_CREATED,
            event_id=event_id, payload={'id': 1, 'event_id': event_id},
            status=WebhookDelivery.Statut.FAILED, response_status=500,
            error='HTTP 500')

    def test_schedule_first_retry_creates_attempt_2_at_60s(self):
        wh_delivery = self._failed_delivery()
        now = timezone.now()
        attempt = schedule_first_retry(wh_delivery, now=now)
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.numero_tentative, 2)
        self.assertEqual(attempt.company_id, self.co.id)
        expected = now + timedelta(seconds=RETRY_DELAYS_SECONDS[0])
        self.assertLess(abs((attempt.prochain_essai_at - expected).total_seconds()), 1)

    def test_schedule_first_retry_is_idempotent(self):
        wh_delivery = self._failed_delivery()
        schedule_first_retry(wh_delivery)
        schedule_first_retry(wh_delivery)  # rejoué — no-op
        self.assertEqual(
            WebhookDeliveryAttempt.objects.filter(delivery=wh_delivery).count(), 1)

    def test_schedule_first_retry_noop_on_success(self):
        wh_delivery = self._failed_delivery()
        wh_delivery.status = WebhookDelivery.Statut.SUCCESS
        wh_delivery.save(update_fields=['status'])
        self.assertIsNone(schedule_first_retry(wh_delivery))
        self.assertFalse(
            WebhookDeliveryAttempt.objects.filter(delivery=wh_delivery).exists())

    def _run_with_status(self, status_code):
        fake_resp = mock.Mock(status_code=status_code)
        with mock.patch.object(delivery.httpx, 'post', return_value=fake_resp):
            return run_due_retries(now=timezone.now() + timedelta(days=1))

    def test_two_failures_then_success_ends_success_no_duplicate(self):
        wh_delivery = self._failed_delivery(event_id='stable-id')
        attempt = schedule_first_retry(wh_delivery, now=timezone.now() - timedelta(days=1))

        # Tentative 2 échoue → programme la tentative 3 (délai suivant).
        self._run_with_status(500)
        attempt.refresh_from_db()
        self.assertEqual(attempt.statut, WebhookDeliveryAttempt.Statut.ECHEC)
        attempt3 = WebhookDeliveryAttempt.objects.get(
            delivery=wh_delivery, numero_tentative=3)
        self.assertEqual(attempt3.statut, WebhookDeliveryAttempt.Statut.EN_ATTENTE)
        wh_delivery.refresh_from_db()
        self.assertEqual(wh_delivery.status, WebhookDelivery.Statut.FAILED)

        # Force l'échéance de la tentative 3 dans le passé puis fait réussir
        # la cible (statut 200) : la livraison ORIGINALE (une seule ligne)
        # finit SUCCESS — aucun doublon métier créé.
        attempt3.prochain_essai_at = timezone.now() - timedelta(minutes=1)
        attempt3.save(update_fields=['prochain_essai_at'])
        self._run_with_status(200)

        wh_delivery.refresh_from_db()
        self.assertEqual(wh_delivery.status, WebhookDelivery.Statut.SUCCESS)
        attempt3.refresh_from_db()
        self.assertEqual(attempt3.statut, WebhookDeliveryAttempt.Statut.SUCCES)
        self.assertEqual(WebhookDelivery.objects.filter(webhook=self.hook).count(), 1)
        self.assertFalse(
            WebhookDeliveryAttempt.objects.filter(
                delivery=wh_delivery, statut=WebhookDeliveryAttempt.Statut.EN_ATTENTE
            ).exists())

    def test_delivery_attempt_header_sent_on_retry(self):
        wh_delivery = self._failed_delivery()
        schedule_first_retry(wh_delivery, now=timezone.now() - timedelta(days=1))
        captured = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            captured['headers'] = headers
            return mock.Mock(status_code=200)

        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            run_due_retries(now=timezone.now())
        self.assertEqual(
            captured['headers'][delivery.DELIVERY_ATTEMPT_HEADER], '2')

    def test_dead_target_gives_up_after_max_attempts_and_marks_en_echec(self):
        wh_delivery = self._failed_delivery()
        attempt = schedule_first_retry(
            wh_delivery, now=timezone.now() - timedelta(days=1))
        # Fait avancer la cascade jusqu'à épuisement (toujours 500).
        while attempt.numero_tentative < MAX_ATTEMPTS:
            attempt.prochain_essai_at = timezone.now() - timedelta(minutes=1)
            attempt.save(update_fields=['prochain_essai_at'])
            self._run_with_status(500)
            attempt = WebhookDeliveryAttempt.objects.filter(
                delivery=wh_delivery).order_by('-numero_tentative').first()
        # Dernière tentative (numero_tentative == MAX_ATTEMPTS) échoue aussi.
        attempt.prochain_essai_at = timezone.now() - timedelta(minutes=1)
        attempt.save(update_fields=['prochain_essai_at'])
        self._run_with_status(500)

        wh_delivery.refresh_from_db()
        self.assertEqual(wh_delivery.status, WebhookDelivery.Statut.EN_ECHEC)
        self.assertEqual(
            WebhookDeliveryAttempt.objects.filter(delivery=wh_delivery).count(),
            MAX_ATTEMPTS - 1)
        self.assertFalse(
            WebhookDeliveryAttempt.objects.filter(
                delivery=wh_delivery, statut=WebhookDeliveryAttempt.Statut.EN_ATTENTE
            ).exists())

    def test_run_due_retries_ignores_not_yet_due_attempts(self):
        wh_delivery = self._failed_delivery()
        schedule_first_retry(wh_delivery)  # échéance dans le futur (+60s)
        processed = run_due_retries(now=timezone.now())
        self.assertEqual(processed, [])

    def test_disabled_webhook_mid_cascade_ends_echec_without_crash(self):
        wh_delivery = self._failed_delivery()
        schedule_first_retry(wh_delivery, now=timezone.now() - timedelta(days=1))
        self.hook.enabled = False
        self.hook.save(update_fields=['enabled'])
        processed = run_due_retries(now=timezone.now())
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].statut, WebhookDeliveryAttempt.Statut.ECHEC)

    def test_attempts_scoped_to_own_company_no_cross_tenant_mixing(self):
        other_co = _company('ntapi8-b', 'NTAPI8 B')
        other_hook = Webhook.objects.create(
            company=other_co, target_url='https://example.test/other',
            secret='s3cr3t2', events=[EVENT_LEAD_CREATED], enabled=True)
        wh_delivery = self._failed_delivery()
        other_delivery = WebhookDelivery.objects.create(
            company=other_co, webhook=other_hook, event=EVENT_LEAD_CREATED,
            event_id='other-id', payload={'event_id': 'other-id'},
            status=WebhookDelivery.Statut.FAILED, response_status=500, error='x')
        schedule_first_retry(wh_delivery)
        schedule_first_retry(other_delivery)
        mine = WebhookDeliveryAttempt.objects.get(delivery=wh_delivery)
        theirs = WebhookDeliveryAttempt.objects.get(delivery=other_delivery)
        self.assertEqual(mine.company_id, self.co.id)
        self.assertEqual(theirs.company_id, other_co.id)
        self.assertNotEqual(mine.company_id, theirs.company_id)
