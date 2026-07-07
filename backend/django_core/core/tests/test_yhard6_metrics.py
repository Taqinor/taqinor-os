"""Tests YHARD6 — métriques Prometheus + santé Celery/beat.

Couvre : garde d'accès de /metrics (admin OU IP allowlist, jamais public),
collecteurs custom (compteurs succès/échec, âge du heartbeat du beat, beat
arrêté → dégradé dans check_services()), et rendu texte toujours disponible
même sans ``django-prometheus`` installé.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from authentication.models import Company
from core import health, metrics
from core.views import metrics_view

User = get_user_model()


class MetricsRenderTests(TestCase):
    def setUp(self):
        cache.delete(metrics.BEAT_HEARTBEAT_CACHE_KEY)
        with metrics._lock:
            metrics._task_counters['success'] = 0
            metrics._task_counters['failure'] = 0

    def test_render_includes_up_and_counters(self):
        metrics.record_task_success()
        metrics.record_task_success()
        metrics.record_task_failure()
        text = metrics.render_prometheus_text()
        self.assertIn('taqinor_up 1', text)
        self.assertIn('taqinor_celery_tasks_total{status="success"} 2', text)
        self.assertIn('taqinor_celery_tasks_total{status="failure"} 1', text)

    def test_beat_heartbeat_age_none_when_never_recorded(self):
        self.assertIsNone(metrics.beat_heartbeat_age_seconds())
        self.assertTrue(metrics.beat_is_stale())

    def test_beat_heartbeat_recent_not_stale(self):
        metrics.mark_beat_heartbeat()
        age = metrics.beat_heartbeat_age_seconds()
        self.assertIsNotNone(age)
        self.assertLess(age, 5)
        self.assertFalse(metrics.beat_is_stale())

    def test_render_never_raises_without_redis_queue(self):
        with mock.patch.object(metrics, 'redis_queue_length', return_value=None):
            text = metrics.render_prometheus_text()
        self.assertNotIn('taqinor_broker_queue_length', text)


class HealthBeatQueueTests(TestCase):
    def setUp(self):
        cache.delete(metrics.BEAT_HEARTBEAT_CACHE_KEY)

    def test_check_services_includes_beat_and_queue(self):
        services = health.check_services()
        names = {s['name'] for s in services}
        self.assertIn('beat', names)
        self.assertIn('queue', names)

    def test_beat_unknown_when_never_ticked(self):
        result = health._check_beat()
        self.assertEqual(result['status'], health.STATUS_UNKNOWN)

    def test_beat_ok_when_recently_ticked(self):
        metrics.mark_beat_heartbeat()
        result = health._check_beat()
        self.assertEqual(result['status'], health.STATUS_OK)

    def test_beat_degraded_when_stale(self):
        with mock.patch.object(
                metrics, 'beat_heartbeat_age_seconds',
                return_value=metrics.BEAT_HEARTBEAT_STALE_SECONDS + 1):
            result = health._check_beat()
        self.assertEqual(result['status'], health.STATUS_DEGRADED)

    def test_overall_status_degraded_when_beat_down(self):
        services = [
            {'name': 'database', 'status': health.STATUS_OK, 'detail': ''},
            {'name': 'cache', 'status': health.STATUS_OK, 'detail': ''},
            {'name': 'beat', 'status': health.STATUS_DEGRADED, 'detail': 'x'},
        ]
        self.assertEqual(health.overall_status(services), health.STATUS_DEGRADED)


class MetricsEndpointAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD6 Co')
        cls.admin = User.objects.create_user(
            username='yhard6_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.plain = User.objects.create_user(
            username='yhard6_plain', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_anonymous_without_allowlist_forbidden(self):
        req = self.factory.get('/metrics/')
        resp = metrics_view(req)
        self.assertEqual(resp.status_code, 403)

    @override_settings(METRICS_ALLOWED_IPS=['203.0.113.5'])
    def test_allowlisted_ip_allowed(self):
        req = self.factory.get('/metrics/', REMOTE_ADDR='203.0.113.5')
        resp = metrics_view(req)
        self.assertEqual(resp.status_code, 200)

    @override_settings(METRICS_ALLOWED_IPS=['203.0.113.5'])
    def test_non_allowlisted_ip_without_auth_forbidden(self):
        req = self.factory.get('/metrics/', REMOTE_ADDR='10.0.0.9')
        resp = metrics_view(req)
        self.assertEqual(resp.status_code, 403)

    def test_admin_cookie_jwt_allowed(self):
        from rest_framework_simplejwt.tokens import AccessToken
        token = str(AccessToken.for_user(self.admin))
        req = self.factory.get('/metrics/')
        req.COOKIES['access_token'] = token
        resp = metrics_view(req)
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_cookie_jwt_forbidden(self):
        from rest_framework_simplejwt.tokens import AccessToken
        token = str(AccessToken.for_user(self.plain))
        req = self.factory.get('/metrics/')
        req.COOKIES['access_token'] = token
        resp = metrics_view(req)
        self.assertEqual(resp.status_code, 403)
