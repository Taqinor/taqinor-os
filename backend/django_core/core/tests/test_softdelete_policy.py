"""YDATA17 — behavioural tests for the shared soft-delete base.

The trash suite (``test_trash.py``) covers the mixin *structure* and the
``core.trash`` service. This module adds the *behavioural* contract required by
YDATA17 — the default manager hides deleted rows, ``all_objects`` shows them,
and ``soft_delete``/``restore`` flip the flag/timestamp — WITHOUT creating a
real table (``isolate_apps`` registers a concrete subclass, and we assert on
the compiled query SQL / in-memory field state, never a DB round-trip, to keep
the fast test tier fast — same discipline as ``test_trash.py``).
"""
from unittest import mock

from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from core.models import SoftDeleteManager, SoftDeleteModel


def _make_concrete():
    """A concrete ``SoftDeleteModel`` subclass registered in an isolated app."""
    class Widget(SoftDeleteModel):
        name = models.CharField(max_length=20)

        class Meta:
            app_label = 'core'

    return Widget


class SoftDeleteManagerBehaviourTests(SimpleTestCase):
    @isolate_apps('core')
    def test_default_manager_filters_deleted(self):
        Widget = _make_concrete()
        self.assertIsInstance(Widget.objects, SoftDeleteManager)
        # The default manager's queryset carries the is_deleted=False filter.
        sql = str(Widget.objects.all().query).lower()
        self.assertIn('is_deleted', sql)

    @isolate_apps('core')
    def test_all_objects_is_unfiltered_manager(self):
        Widget = _make_concrete()
        # all_objects is a plain Manager (no soft-delete filtering layer).
        self.assertIs(type(Widget.all_objects), models.Manager)
        self.assertNotIsInstance(Widget.all_objects, SoftDeleteManager)


class SoftDeleteMethodBehaviourTests(SimpleTestCase):
    @isolate_apps('core')
    def test_soft_delete_sets_flag_and_timestamp(self):
        Widget = _make_concrete()
        w = Widget(name='x')
        saved = {}
        # Bypass the DB: record the save instead of hitting Postgres.
        w.save = lambda *a, **k: saved.update(update_fields=k.get('update_fields'))
        w.soft_delete(user=None, record=False)
        self.assertTrue(w.is_deleted)
        self.assertIsNotNone(w.deleted_at)
        self.assertEqual(
            set(saved['update_fields']),
            {'is_deleted', 'deleted_at', 'deleted_by'})

    @isolate_apps('core')
    def test_soft_delete_is_idempotent(self):
        Widget = _make_concrete()
        w = Widget(name='x')
        w.save = lambda *a, **k: None
        w.soft_delete(record=False)
        first = w.deleted_at
        w.soft_delete(record=False)  # second call is a no-op
        self.assertEqual(w.deleted_at, first)

    @isolate_apps('core')
    def test_restore_clears_flag(self):
        Widget = _make_concrete()
        w = Widget(name='x')
        w.save = lambda *a, **k: None
        w.soft_delete(record=False)
        # restore() closes the DeletionRecord journal (DB) — mock it out so
        # this stays a DB-free SimpleTestCase; we only assert the flag reset.
        with mock.patch('core.models.ContentType'), \
                mock.patch('core.models.DeletionRecord'):
            w.restore()
        self.assertFalse(w.is_deleted)
        self.assertIsNone(w.deleted_at)
