"""Tests YOPSB8 — réglages Celery de production durcis (time limits +
reject_on_worker_lost + acks_late + prefetch équitable)."""
from django.conf import settings
from django.test import SimpleTestCase


class CeleryHardeningTests(SimpleTestCase):
    def test_soft_time_limit_configured(self):
        self.assertEqual(settings.CELERY_TASK_SOFT_TIME_LIMIT, 120)

    def test_hard_time_limit_configured_and_greater_than_soft(self):
        self.assertEqual(settings.CELERY_TASK_TIME_LIMIT, 180)
        self.assertGreater(settings.CELERY_TASK_TIME_LIMIT,
                           settings.CELERY_TASK_SOFT_TIME_LIMIT)

    def test_acks_late_enabled(self):
        self.assertTrue(settings.CELERY_TASK_ACKS_LATE)

    def test_reject_on_worker_lost_enabled(self):
        self.assertTrue(settings.CELERY_TASK_REJECT_ON_WORKER_LOST)

    def test_worker_prefetch_multiplier_is_one(self):
        self.assertEqual(settings.CELERY_WORKER_PREFETCH_MULTIPLIER, 1)


class TransportRedisInstalleTests(SimpleTestCase):
    """ERR-CELERY-KOMBU-REDIS — le transport kombu installé accepte le redis-py épinglé : sinon
    `VersionMismatch` au démarrage (worker et beat en boucle, chaque `.delay()` bloque gunicorn).
    Test-du-test : kombu 5.7 (redis-py >= 6.1 exigé) avec redis==5.2.1 fait lever ce test."""

    def test_kombu_accepte_le_redis_installe(self):
        from types import SimpleNamespace
        from kombu.transport.redis import Channel

        Channel._get_client(SimpleNamespace(global_keyprefix=None))
