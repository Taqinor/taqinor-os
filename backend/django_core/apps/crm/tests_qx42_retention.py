"""QX42 — PII retention for the raw intake copies.

Covers:
  - CrmConfig.ready() registers both CRM retention policies in the shared
    core.retention registry (it was empty before — no app registered);
  - purge_website_lead_payloads: processed + old payloads are purged;
    unprocessed/error payloads are EXEMPT (QX16 replay surface needs them);
    dry-run (apply_=False) never deletes, only counts;
  - purge_stale_chat_sessions: old, lead-less sessions are purged; a session
    already linked to a Lead is kept; a recently active session is kept.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import ChatSessionPublique, Lead, WebsiteLeadPayload
from apps.crm.services import (
    purge_stale_chat_sessions, purge_website_lead_payloads,
)
from core import retention


class RetentionRegistrationTests(TestCase):
    def test_both_crm_policies_registered(self):
        # CrmConfig.ready() a déjà tourné au démarrage de l'app Django — le
        # registre partagé doit contenir les deux politiques CRM.
        names = retention.list_retention_policies()
        self.assertIn('crm_website_lead_payloads', names)
        self.assertIn('crm_chat_sessions_publiques', names)


class PurgeWebsiteLeadPayloadsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX42', slug='taqinor-qx42')

    def _old_payload(self, **extra):
        payload = WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, **extra)
        WebsiteLeadPayload.objects.filter(pk=payload.pk).update(
            received_at=timezone.now() - datetime.timedelta(days=200))
        payload.refresh_from_db()
        return payload

    def test_old_processed_payload_purged(self):
        old = self._old_payload(processed=True)
        now = timezone.now()
        count = purge_website_lead_payloads(now, apply_=True)
        self.assertEqual(count, 1)
        self.assertFalse(WebsiteLeadPayload.objects.filter(pk=old.pk).exists())

    def test_dry_run_never_deletes(self):
        old = self._old_payload(processed=True)
        now = timezone.now()
        count = purge_website_lead_payloads(now, apply_=False)
        self.assertEqual(count, 1)
        self.assertTrue(WebsiteLeadPayload.objects.filter(pk=old.pk).exists())

    def test_unprocessed_payload_exempt(self):
        old = self._old_payload(processed=False)
        now = timezone.now()
        count = purge_website_lead_payloads(now, apply_=True)
        self.assertEqual(count, 0)
        self.assertTrue(WebsiteLeadPayload.objects.filter(pk=old.pk).exists())

    def test_error_payload_exempt_even_if_processed(self):
        old = self._old_payload(processed=True, error='ValueError: broken')
        now = timezone.now()
        count = purge_website_lead_payloads(now, apply_=True)
        self.assertEqual(count, 0)
        self.assertTrue(WebsiteLeadPayload.objects.filter(pk=old.pk).exists())

    def test_recent_payload_not_purged(self):
        recent = WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, processed=True)
        now = timezone.now()
        count = purge_website_lead_payloads(now, apply_=True)
        self.assertEqual(count, 0)
        self.assertTrue(WebsiteLeadPayload.objects.filter(pk=recent.pk).exists())

    def test_disabled_via_zero_days_setting(self):
        from django.test import override_settings
        old = self._old_payload(processed=True)
        now = timezone.now()
        with override_settings(WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS=0):
            count = purge_website_lead_payloads(now, apply_=True)
        self.assertEqual(count, 0)
        self.assertTrue(WebsiteLeadPayload.objects.filter(pk=old.pk).exists())

    def test_founder_configurable_shorter_window(self):
        payload = WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, processed=True)
        WebsiteLeadPayload.objects.filter(pk=payload.pk).update(
            received_at=timezone.now() - datetime.timedelta(days=10))
        from django.test import override_settings
        now = timezone.now()
        with override_settings(WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS=5):
            count = purge_website_lead_payloads(now, apply_=True)
        self.assertEqual(count, 1)


class PurgeStaleChatSessionsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX42 Chat', slug='taqinor-qx42-chat')

    def _old_session(self, **extra):
        session = ChatSessionPublique.objects.create(company=self.company, **extra)
        ChatSessionPublique.objects.filter(pk=session.pk).update(
            last_message_at=timezone.now() - datetime.timedelta(days=200))
        session.refresh_from_db()
        return session

    def test_old_session_without_lead_purged(self):
        old = self._old_session()
        now = timezone.now()
        count = purge_stale_chat_sessions(now, apply_=True)
        self.assertEqual(count, 1)
        self.assertFalse(ChatSessionPublique.objects.filter(pk=old.pk).exists())

    def test_old_session_with_lead_kept(self):
        lead = Lead.objects.create(company=self.company, nom='Lead Chat')
        old = self._old_session(lead=lead)
        now = timezone.now()
        count = purge_stale_chat_sessions(now, apply_=True)
        self.assertEqual(count, 0)
        self.assertTrue(ChatSessionPublique.objects.filter(pk=old.pk).exists())

    def test_recent_session_kept(self):
        recent = ChatSessionPublique.objects.create(company=self.company)
        now = timezone.now()
        count = purge_stale_chat_sessions(now, apply_=True)
        self.assertEqual(count, 0)
        self.assertTrue(ChatSessionPublique.objects.filter(pk=recent.pk).exists())

    def test_dry_run_never_deletes(self):
        old = self._old_session()
        now = timezone.now()
        count = purge_stale_chat_sessions(now, apply_=False)
        self.assertEqual(count, 1)
        self.assertTrue(ChatSessionPublique.objects.filter(pk=old.pk).exists())
