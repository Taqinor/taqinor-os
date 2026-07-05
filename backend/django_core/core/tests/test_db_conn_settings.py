"""Tests YOPSB7 — CONN_MAX_AGE + CONN_HEALTH_CHECKS posés et pilotables."""
from django.conf import settings
from django.test import SimpleTestCase


class DbConnSettingsTests(SimpleTestCase):
    def test_conn_max_age_is_set_and_positive(self):
        conn_max_age = settings.DATABASES['default'].get('CONN_MAX_AGE')
        self.assertIsNotNone(conn_max_age)
        self.assertIsInstance(conn_max_age, int)
        self.assertGreaterEqual(conn_max_age, 0)

    def test_conn_health_checks_enabled(self):
        self.assertTrue(
            settings.DATABASES['default'].get('CONN_HEALTH_CHECKS'))
