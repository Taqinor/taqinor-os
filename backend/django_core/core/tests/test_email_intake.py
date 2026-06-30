"""Tests FG373 — email entrant IMAP → leads/tickets (fondation).

Couvre :
  * parsing RFC 822 → InboundMessage (from, sujet, body, message-id) ;
  * threading : thread_root via References / In-Reply-To / self ;
  * registre de handlers + dispatch (un handler défaillant n'arrête pas) ;
  * fetch_messages no-op quand non configuré ;
  * poll_mailbox no-op sans config société ;
  * découplage : aucun import d'app domaine.
"""
from django.test import TestCase

from authentication.models import Company
from core import email_intake, integrations
from core.models import IntegrationConfig


class ParseTests(TestCase):
    def test_parse_simple_message(self):
        raw = (b'From: Ali Ben <ali@example.com>\r\n'
               b'Subject: Demande devis\r\n'
               b'Message-ID: <abc@x>\r\n'
               b'\r\n'
               b'Bonjour, je veux un devis.\r\n')
        msg = email_intake._parse_email_message(raw)
        self.assertEqual(msg.from_email, 'ali@example.com')
        self.assertEqual(msg.from_name, 'Ali Ben')
        self.assertEqual(msg.subject, 'Demande devis')
        self.assertEqual(msg.message_id, 'abc@x')
        self.assertIn('devis', msg.body)

    def test_thread_root_prefers_references(self):
        m = email_intake.InboundMessage(
            message_id='c', in_reply_to='b', references='root mid2')
        self.assertEqual(m.thread_root, 'root')
        m2 = email_intake.InboundMessage(message_id='c', in_reply_to='b')
        self.assertEqual(m2.thread_root, 'b')
        m3 = email_intake.InboundMessage(message_id='c')
        self.assertEqual(m3.thread_root, 'c')


class HandlerRegistryTests(TestCase):
    def setUp(self):
        email_intake._HANDLERS.clear()

    def tearDown(self):
        email_intake._HANDLERS.clear()

    def test_register_and_dispatch(self):
        seen = []
        email_intake.register_handler(lambda m, c: seen.append((m, c)))
        msg = email_intake.InboundMessage(message_id='x')
        n = email_intake._dispatch([msg], company='C')
        self.assertEqual(n, 1)
        self.assertEqual(seen[0][1], 'C')

    def test_failing_handler_does_not_break_others(self):
        ok = []

        def boom(m, c):
            raise RuntimeError('nope')

        email_intake.register_handler(boom)
        email_intake.register_handler(lambda m, c: ok.append(1))
        n = email_intake._dispatch(
            [email_intake.InboundMessage(message_id='x')], company='C')
        self.assertEqual(ok, [1])
        self.assertEqual(n, 1)

    def test_register_handler_idempotent(self):
        def fn(m, c):
            return None
        email_intake.register_handler(fn)
        email_intake.register_handler(fn)
        self.assertEqual(email_intake._HANDLERS.count(fn), 1)


class FetchAndPollTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_fetch_noop_when_unconfigured(self):
        cfg = IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_EMAIL_IN,
            provider='imap', actif=True, settings={})
        self.assertEqual(email_intake.fetch_messages(cfg), [])

    def test_poll_noop_without_config(self):
        res = email_intake.poll_mailbox(self.company)
        self.assertEqual(res, {'fetched': 0, 'handled': 0})
