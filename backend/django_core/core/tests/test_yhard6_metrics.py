"""Tests YHARD6 — métriques Prometheus + santé Celery/beat.

Couvre : garde d'accès de /metrics (admin OU IP allowlist, jamais public),
collecteurs custom (compteurs succès/échec, âge du heartbeat du beat, beat
arrêté → dégradé dans check_services()), et rendu texte toujours disponible
même sans ``django-prometheus`` installé.
"""
import importlib
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
        cache.delete_many(metrics.cles_compteurs_taches())

    def test_render_includes_up_and_counters(self):
        metrics.record_task_success()
        metrics.record_task_success()
        metrics.record_task_failure()
        text = metrics.render_prometheus_text()
        self.assertIn('taqinor_up 1', text)
        self.assertIn('taqinor_celery_tasks_total{status="success"} 2', text)
        self.assertIn('taqinor_celery_tasks_total{status="failure"} 1', text)

    def test_compteurs_celery_survivent_a_un_autre_processus(self):
        """ACEL14 — le worker incrémente, gunicorn lit : les compteurs
        vivent dans le cache partagé, pas dans le processus."""
        metrics.record_task_failure()
        metrics.record_task_success()
        metrics.record_task_success()
        metrics.record_task_queue('scheduled', ok=False)
        importlib.reload(metrics)  # nouveau processus : état du module neuf
        text = metrics.render_prometheus_text()
        self.assertIn('taqinor_celery_tasks_total{status="failure"} 1', text)
        self.assertIn('taqinor_celery_tasks_total{status="success"} 2', text)
        self.assertIn('taqinor_celery_queue_tasks_total'
                      '{queue="scheduled",status="failure"} 1', text)

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

    def _get(self, user, **extra):
        from rest_framework_simplejwt.tokens import AccessToken
        req = self.factory.get('/metrics/', **extra)
        if user is not None:
            req.COOKIES['access_token'] = str(AccessToken.for_user(user))
        return metrics_view(req)

    def test_admin_cookie_jwt_allowed(self):
        # APUB48 — /metrics expose TOUTE la plateforme : superutilisateur seul ;
        # l'administrateur d'une société (role_legacy='admin') reçoit 403.
        su = User.objects.create_superuser(
            username='yhard6_su', password='x', company=self.company)
        self.assertEqual(self._get(su).status_code, 200)
        self.assertEqual(self._get(self.admin).status_code, 403)

    def test_directeur_de_societe_403(self):
        """APUB48 — le Directeur LIVRÉ d'une société B ne lit pas les compteurs
        de la société A ; superutilisateur et IP autorisée gardent 200."""
        from importlib import import_module
        from django.apps import apps as django_apps
        Role = django_apps.get_model('roles', 'Role')  # ENF20 : aucune arête core -> apps.roles
        DIRECTEUR_PERMISSIONS = import_module(
            'apps.roles.permissions_registre').DIRECTEUR_PERMISSIONS
        autre = Company.objects.create(nom='APUB48 B')
        metrics.record_http_request(self.company.pk, 200, 10)
        role = Role.objects.create(
            company=autre, nom='Directeur', permissions=DIRECTEUR_PERMISSIONS)
        directeur = User.objects.create_user(
            username='apub48_dir', password='x', company=autre, role=role)
        resp = self._get(directeur)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['detail'], 'Accès /metrics non autorisé.')
        su = User.objects.create_superuser(
            username='apub48_su', password='x', company=autre)
        self.assertEqual(self._get(su).status_code, 200)
        with self.settings(METRICS_ALLOWED_IPS=['203.0.113.9']):
            self.assertEqual(
                self._get(None, REMOTE_ADDR='203.0.113.9').status_code, 200)

    def test_non_admin_cookie_jwt_forbidden(self):
        from rest_framework_simplejwt.tokens import AccessToken
        token = str(AccessToken.for_user(self.plain))
        req = self.factory.get('/metrics/')
        req.COOKIES['access_token'] = token
        resp = metrics_view(req)
        self.assertEqual(resp.status_code, 403)
