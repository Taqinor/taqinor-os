"""Tests SCA15 — santé Redis (mémoire) + profondeur des queues Celery.

Redis est SIMULÉ/MOCKÉ (jamais de service réel requis en test) : couvre
``_check_redis_memory`` (ok/degraded/unknown selon le ratio used/maxmemory)
et ``_check_queue_depth`` (ok/degraded/unknown selon LLEN par queue vs
seuil), + leur présence dans ``check_services()``."""
import os
from unittest import mock

from django.test import TestCase

from core import health


class RedisMemoryCheckTests(TestCase):
    def test_ok_when_ratio_far_from_threshold(self):
        fake_result = (1000, 10000, 0.1)
        with mock.patch.object(health, '_redis_memory_ratio',
                               return_value=fake_result):
            result = health._check_redis_memory()
        self.assertEqual(result['status'], health.STATUS_OK)
        self.assertEqual(result['name'], 'redis_memory')

    def test_degraded_when_ratio_at_or_above_threshold(self):
        fake_result = (8500, 10000, 0.85)
        with mock.patch.object(health, '_redis_memory_ratio',
                               return_value=fake_result):
            result = health._check_redis_memory()
        self.assertEqual(result['status'], health.STATUS_DEGRADED)

    def test_unknown_when_no_instance_reachable(self):
        with mock.patch.object(health, '_redis_memory_ratio',
                               side_effect=RuntimeError('injoignable')):
            result = health._check_redis_memory()
        self.assertEqual(result['status'], health.STATUS_UNKNOWN)

    def test_none_result_treated_as_no_limit_not_a_crash(self):
        """maxmemory non posé (0) -> ratio indisponible, jamais une
        exception ni une fausse alerte."""
        with mock.patch.object(health, '_redis_memory_ratio',
                               return_value=None):
            result = health._check_redis_memory()
        # Aucune instance n'a pu produire de ratio exploitable -> unknown,
        # jamais degraded/down par excès de prudence.
        self.assertEqual(result['status'], health.STATUS_UNKNOWN)

    def test_threshold_configurable_via_env(self):
        fake_result = (600, 1000, 0.6)
        with mock.patch.dict(os.environ,
                             {'REDIS_MEMORY_DEGRADED_RATIO': '0.5'}), \
                mock.patch.object(health, '_redis_memory_ratio',
                                  return_value=fake_result):
            result = health._check_redis_memory()
        self.assertEqual(result['status'], health.STATUS_DEGRADED)


class QueueDepthCheckTests(TestCase):
    def test_ok_when_all_queues_under_threshold(self):
        with mock.patch('core.metrics.redis_queue_length', return_value=10):
            result = health._check_queue_depth()
        self.assertEqual(result['status'], health.STATUS_OK)
        self.assertEqual(result['name'], 'queue_depth')

    def test_degraded_when_one_queue_over_threshold(self):
        def fake_length(queue_name='celery'):
            return 999 if queue_name == 'scheduled' else 5
        with mock.patch('core.metrics.redis_queue_length',
                        side_effect=fake_length):
            result = health._check_queue_depth()
        self.assertEqual(result['status'], health.STATUS_DEGRADED)
        self.assertIn('scheduled', result['detail'])

    def test_unknown_when_broker_not_redis(self):
        with mock.patch('core.metrics.redis_queue_length', return_value=None):
            result = health._check_queue_depth()
        self.assertEqual(result['status'], health.STATUS_UNKNOWN)

    def test_threshold_configurable_per_queue_via_env(self):
        with mock.patch.dict(os.environ,
                             {'QUEUE_DEPTH_DEGRADED_INTERACTIVE': '3'}), \
                mock.patch('core.metrics.redis_queue_length',
                           return_value=5):
            result = health._check_queue_depth()
        self.assertEqual(result['status'], health.STATUS_DEGRADED)

    def test_monitors_all_three_sca9_queues(self):
        seen_queues = []

        def fake_length(queue_name='celery'):
            seen_queues.append(queue_name)
            return 1
        with mock.patch('core.metrics.redis_queue_length',
                        side_effect=fake_length):
            health._check_queue_depth()
        self.assertEqual(set(seen_queues), {'default', 'interactive', 'scheduled'})


class CheckServicesIncludesSca15Tests(TestCase):
    def test_check_services_includes_redis_memory_and_queue_depth(self):
        services = health.check_services()
        names = {s['name'] for s in services}
        self.assertIn('redis_memory', names)
        self.assertIn('queue_depth', names)

    def test_redis_memory_degraded_does_not_force_global_down(self):
        """redis_memory/queue_depth ne sont PAS dans les sondes 'critiques'
        de overall_status -> un degraded dessus reste 'degraded', jamais
        'down' (interne ops uniquement, jamais un déni de service)."""
        services = [
            {'name': 'database', 'status': health.STATUS_OK, 'detail': ''},
            {'name': 'cache', 'status': health.STATUS_OK, 'detail': ''},
            {'name': 'redis_memory', 'status': health.STATUS_DEGRADED,
             'detail': 'x'},
        ]
        self.assertEqual(health.overall_status(services), health.STATUS_DEGRADED)
