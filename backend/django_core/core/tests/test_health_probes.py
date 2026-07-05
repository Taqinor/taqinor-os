"""Tests YOPSB14 — endpoints readiness/liveness + limites d'upload Django.

Couvre :
  * /health/live/ répond toujours 200 SANS authentification, sans toucher la
    DB (mockée en échec, répond quand même 200) ;
  * /health/ready/ répond 200 quand la DB est OK, 503 quand elle est down
    (mockée en échec) ;
  * aucune donnée société ne fuit sur ces routes (payload minimal) ;
  * DATA_UPLOAD_MAX_MEMORY_SIZE / FILE_UPLOAD_MAX_MEMORY_SIZE /
    DATA_UPLOAD_MAX_NUMBER_FIELDS sont posés et cohérents avec le
    client_max_body_size 15m de nginx.conf.
"""
from unittest import mock

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient


class HealthProbesTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_live_always_returns_200_without_auth(self):
        resp = self.client.get('/api/django/core/health/live/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'live')

    def test_live_view_never_calls_health_check_db(self):
        """La vue health_live n'appelle JAMAIS core.health.check_db (contrat :
        elle répond même si Postgres est down)."""
        from core import health
        with mock.patch.object(
                health, 'check_db',
                side_effect=AssertionError('health_live ne doit jamais '
                                           'appeler check_db')):
            resp = self.client.get('/api/django/core/health/live/')
        self.assertEqual(resp.status_code, 200)

    def test_ready_returns_200_when_db_ok(self):
        resp = self.client.get('/api/django/core/health/ready/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ready')

    def test_ready_returns_503_when_db_down(self):
        from core import health
        fake_down = {
            'name': 'database', 'status': health.STATUS_DOWN,
            'detail': 'connection refused',
        }
        with mock.patch.object(health, 'check_db', return_value=fake_down):
            resp = self.client.get('/api/django/core/health/ready/')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['status'], 'not-ready')

    def test_no_company_data_leaks_on_probes(self):
        resp = self.client.get('/api/django/core/health/ready/')
        self.assertNotIn('company', str(resp.data).lower())
        self.assertNotIn('société', str(resp.data).lower())

    def test_probes_require_no_authentication_header(self):
        """Un client SANS jeton du tout doit quand même obtenir 200/503,
        jamais 401/403 (probes non authentifiées par design)."""
        resp_live = self.client.get('/api/django/core/health/live/')
        resp_ready = self.client.get('/api/django/core/health/ready/')
        self.assertNotEqual(resp_live.status_code, 401)
        self.assertNotEqual(resp_live.status_code, 403)
        self.assertNotEqual(resp_ready.status_code, 401)
        self.assertNotEqual(resp_ready.status_code, 403)


class UploadLimitSettingsTests(TestCase):
    def test_data_upload_max_memory_size_matches_nginx_15mb(self):
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 15 * 1024 * 1024)

    def test_file_upload_max_memory_size_matches_nginx_15mb(self):
        self.assertEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 15 * 1024 * 1024)

    def test_data_upload_max_number_fields_is_set(self):
        self.assertIsNotNone(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        self.assertGreater(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS, 0)

    def test_oversized_body_is_rejected_before_full_buffering(self):
        """Un corps dépassant DATA_UPLOAD_MAX_MEMORY_SIZE doit être rejeté
        (RequestDataTooBig -> 400) plutôt que bufferisé intégralement."""
        from django.core.exceptions import RequestDataTooBig
        from django.test import RequestFactory

        factory = RequestFactory()
        oversized = b'x' * (settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1024)
        request = factory.post(
            '/api/django/core/sauvegardes/', data=oversized,
            content_type='application/x-www-form-urlencoded')
        with self.assertRaises(RequestDataTooBig):
            request.POST  # noqa: B018 — l'accès déclenche le parsing/la garde
