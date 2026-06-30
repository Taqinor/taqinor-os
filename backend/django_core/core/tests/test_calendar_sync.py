"""Tests FG374 — sync calendrier 2-way (fondation branchable).

Couvre :
  * event_hash stable/déterministe ;
  * push_events crée des mappings (dry-run sans connecteur) ;
  * push_events idempotent : ré-exécution = tout skipped ;
  * changement d'événement → updated ;
  * événement sans kind/id → skipped ;
  * découplage : aucun import d'app domaine (events = dicts purs).
"""
from django.test import TestCase

from authentication.models import Company
from core import calendar_sync
from core.models import CalendarSyncMapping


class EventHashTests(TestCase):
    def test_hash_is_stable_and_order_independent(self):
        a = {'id': 1, 'title': 'x', 'kind': 'pose'}
        b = {'kind': 'pose', 'title': 'x', 'id': 1}
        self.assertEqual(calendar_sync.event_hash(a),
                         calendar_sync.event_hash(b))

    def test_hash_changes_on_change(self):
        a = {'id': 1, 'title': 'x'}
        b = {'id': 1, 'title': 'y'}
        self.assertNotEqual(calendar_sync.event_hash(a),
                            calendar_sync.event_hash(b))


class PushEventsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_create_then_idempotent(self):
        events = [
            {'kind': 'intervention', 'id': '10', 'title': 'Pose A'},
            {'kind': 'visite', 'id': '11', 'title': 'Visite B'},
        ]
        res = calendar_sync.push_events(self.company, events)
        self.assertEqual(res['created'], 2)
        self.assertEqual(CalendarSyncMapping.objects.count(), 2)
        # Re-run identique : tout skipped.
        res2 = calendar_sync.push_events(self.company, events)
        self.assertEqual(res2['created'], 0)
        self.assertEqual(res2['skipped'], 2)

    def test_change_triggers_update(self):
        calendar_sync.push_events(
            self.company, [{'kind': 'pose', 'id': '1', 'title': 'A'}])
        res = calendar_sync.push_events(
            self.company, [{'kind': 'pose', 'id': '1', 'title': 'A modifié'}])
        self.assertEqual(res['updated'], 1)

    def test_event_without_identity_is_skipped(self):
        res = calendar_sync.push_events(self.company, [{'title': 'orphan'}])
        self.assertEqual(res['skipped'], 1)
        self.assertEqual(CalendarSyncMapping.objects.count(), 0)
