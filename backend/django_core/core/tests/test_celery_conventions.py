"""Tests YDATA13 — convention Celery : acks_late + time limits + visibility
timeout du broker sont bien chargés depuis les settings.

Réglages seulement (YOPSB8 posait déjà acks_late/time limits ; YDATA13
ajoute `CELERY_BROKER_TRANSPORT_OPTIONS`) — pas de comportement de tâche à
tester ici, juste que la config EST posée. `SimpleTestCase` : aucune DB
requise.
"""
from django.conf import settings
from django.test import SimpleTestCase


class CeleryConventionsTests(SimpleTestCase):

    def test_acks_late_is_enabled(self):
        self.assertTrue(settings.CELERY_TASK_ACKS_LATE)

    def test_time_limits_are_set_and_positive(self):
        self.assertGreater(settings.CELERY_TASK_SOFT_TIME_LIMIT, 0)
        self.assertGreater(settings.CELERY_TASK_TIME_LIMIT, 0)
        self.assertGreaterEqual(
            settings.CELERY_TASK_TIME_LIMIT,
            settings.CELERY_TASK_SOFT_TIME_LIMIT,
        )

    def test_reject_on_worker_lost_is_enabled(self):
        self.assertTrue(settings.CELERY_TASK_REJECT_ON_WORKER_LOST)

    def test_broker_visibility_timeout_exceeds_max_task_runtime(self):
        options = settings.CELERY_BROKER_TRANSPORT_OPTIONS
        self.assertIn('visibility_timeout', options)
        self.assertGreater(
            options['visibility_timeout'], settings.CELERY_TASK_TIME_LIMIT,
        )
