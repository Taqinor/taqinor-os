"""NTPLT13 — rejeu ciblé support : garde-fou rejouable + re-exécution réelle."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import events
from core.models import OutboxEvent, ProcessedEvent


class ReplayEventsCommandTests(TestCase):
    def setUp(self):
        events.clear_durable_handlers()
        self.addCleanup(events.clear_durable_handlers)
        self.calls = []

    def _make_event(self, name='devis_accepted'):
        return OutboxEvent.objects.create(
            event_name=name, payload={'devis': 1},
            statut=OutboxEvent.STATUT_DELIVERED)

    def test_refuses_non_replayable_handler(self):
        events.subscribe_durable(
            'devis_accepted', lambda e: self.calls.append(e),
            rejouable=False, handler_name='h_off')
        self._make_event()
        with self.assertRaises(CommandError):
            call_command('replay_events', '--event', 'devis_accepted',
                         '--handler', 'h_off', stdout=StringIO())

    def test_refuses_unknown_handler(self):
        with self.assertRaises(CommandError):
            call_command('replay_events', '--event', 'devis_accepted',
                         '--handler', 'inconnu', stdout=StringIO())

    def test_dry_run_does_not_execute(self):
        events.subscribe_durable(
            'devis_accepted', lambda e: self.calls.append(e.event_id),
            rejouable=True, handler_name='h_ok')
        self._make_event()
        out = StringIO()
        call_command('replay_events', '--event', 'devis_accepted',
                     '--handler', 'h_ok', '--dry-run', stdout=out)
        self.assertEqual(self.calls, [])
        self.assertIn('dry-run', out.getvalue())

    def test_replays_and_reruns_handler_despite_prior_dedup(self):
        events.subscribe_durable(
            'devis_accepted', lambda e: self.calls.append(e.event_id),
            rejouable=True, handler_name='h_ok')
        ev = self._make_event()
        # Simule une livraison antérieure (ligne de dédup posée).
        ProcessedEvent.objects.create(
            event_id=ev.event_id, handler_name='h_ok')
        call_command('replay_events', '--event', 'devis_accepted',
                     '--handler', 'h_ok', stdout=StringIO())
        # Le handler a bien été RÉ-exécuté malgré la dédup préexistante.
        self.assertEqual(self.calls, [ev.event_id])
        self.assertTrue(ProcessedEvent.objects.filter(
            event_id=ev.event_id, handler_name='h_ok').exists())

    def test_only_targets_named_handler(self):
        other = []
        events.subscribe_durable(
            'devis_accepted', lambda e: self.calls.append(e.event_id),
            rejouable=True, handler_name='h_ok')
        events.subscribe_durable(
            'devis_accepted', lambda e: other.append(e.event_id),
            rejouable=True, handler_name='h_other')
        self._make_event()
        call_command('replay_events', '--event', 'devis_accepted',
                     '--handler', 'h_ok', stdout=StringIO())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(other, [])  # l'autre handler n'est jamais touché

    def test_company_filter(self):
        events.subscribe_durable(
            'devis_accepted', lambda e: self.calls.append(e.event_id),
            rejouable=True, handler_name='h_ok')
        self._make_event()  # company None
        call_command('replay_events', '--event', 'devis_accepted',
                     '--handler', 'h_ok', '--company', '999',
                     stdout=StringIO())
        self.assertEqual(self.calls, [])  # aucune ligne pour company 999
