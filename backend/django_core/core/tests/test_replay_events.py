"""NTPLT13 — rejeu ciblé support : garde-fou rejouable + re-exécution réelle."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import events
from core.models import OutboxEvent, ProcessedEvent


class ReplayEventsCommandTests(TestCase):
    def setUp(self):
        # NTPLT11 — on RESTAURE les handlers des apps (webhooks publicapi,
        # notifications) au lieu de vider le registre pour la suite du
        # processus de test.
        self.addCleanup(events.restore_durable_handlers,
                        events.snapshot_durable_handlers())
        events.clear_durable_handlers()
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


class EnqueueDurableTests(TestCase):
    """NTPLT11 — ``enqueue_durable`` : effet confié à l'outbox, tentative
    immédiate, rejeu par le worker sans perte ni doublon."""

    EFFET = 'test.ntplt11'

    def setUp(self):
        self.addCleanup(events.restore_durable_handlers,
                        events.snapshot_durable_handlers())
        self.effets = []
        self.panne = True

        def handler(evt):
            if self.panne:
                raise ConnectionError('Redis indisponible')
            self.effets.append(evt.payload['n'])

        events.subscribe_durable(self.EFFET, handler, handler_name='h11')

    def _plus_tard(self):
        from datetime import timedelta
        from django.utils import timezone
        return timezone.now() + timedelta(hours=2)

    def test_panne_a_l_emission_puis_rejeu_unique(self):
        from core import dispatch_outbox
        ligne = events.enqueue_durable(
            self.EFFET, {'n': 1}, immediat=events.IMMEDIAT_TRANSACTION)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, OutboxEvent.STATUT_FAILED)
        self.assertEqual(self.effets, [])
        self.panne = False
        dispatch_outbox.dispatch_pending(now=self._plus_tard())
        dispatch_outbox.dispatch_pending(now=self._plus_tard())
        self.assertEqual(self.effets, [1])
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, OutboxEvent.STATUT_DELIVERED)

    def test_succes_immediat_au_commit(self):
        self.panne = False
        with self.captureOnCommitCallbacks(execute=False) as rappels:
            ligne = events.enqueue_durable(self.EFFET, {'n': 2})
            self.assertEqual(self.effets, [])  # rien avant le commit
        for rappel in rappels:
            rappel()
        self.assertEqual(self.effets, [2])
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, OutboxEvent.STATUT_DELIVERED)

    def test_rollback_de_l_emetteur_annule_l_effet(self):
        from django.db import transaction
        self.panne = False
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    events.enqueue_durable(self.EFFET, {'n': 3})
                    raise RuntimeError('geste annulé')
        self.assertEqual(self.effets, [])
        self.assertFalse(OutboxEvent.objects.filter(
            event_name=self.EFFET).exists())

    def test_effets_partiels_gardent_les_marques(self):
        from core import dispatch_outbox
        faits = []

        def partiel(evt):
            for cle in ('a', 'b'):
                if dispatch_outbox.effet_deja_applique(evt, cle):
                    continue
                if cle == 'b' and self.panne:
                    raise dispatch_outbox.EffetsPartiels('b en panne')
                faits.append(cle)
                dispatch_outbox.marquer_effet_applique(evt, cle)

        events.subscribe_durable('test.partiel', partiel,
                                 handler_name='h_partiel')
        ligne = events.enqueue_durable(
            'test.partiel', {}, immediat=events.IMMEDIAT_TRANSACTION)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, OutboxEvent.STATUT_FAILED)
        self.assertEqual(faits, ['a'])
        self.panne = False
        dispatch_outbox.dispatch_pending(now=self._plus_tard())
        self.assertEqual(faits, ['a', 'b'])  # « a » jamais refait
