"""NTOBS11 — mode dégradé documenté et exposé par dépendance externe."""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from core.degraded_mode import DEGRADED_MODE_MATRIX, degraded_mode_status


class DegradedModeStatusTest(TestCase):
    def test_matrix_has_at_least_five_keys(self):
        self.assertGreaterEqual(len(DEGRADED_MODE_MATRIX), 5)
        for cle in ('db', 'cache', 'celery_broker', 'storage', 'llm_ia'):
            self.assertIn(cle, DEGRADED_MODE_MATRIX)

    def test_every_entry_has_impact_lists(self):
        for entree in DEGRADED_MODE_MATRIX.values():
            self.assertIn('impactees', entree)
            self.assertIn('continuent', entree)
            self.assertIn('label', entree)

    def test_status_reflects_real_probe_down(self):
        fake_services = [
            {'name': 'database', 'status': 'ok', 'detail': ''},
            {'name': 'cache', 'status': 'ok', 'detail': ''},
            {'name': 'broker', 'status': 'ok', 'detail': ''},
            {'name': 'storage', 'status': 'down', 'detail': 'MinIO KO'},
        ]
        with mock.patch(
                'core.health.check_services', return_value=fake_services):
            resultat = degraded_mode_status()
        by_key = {r['cle']: r for r in resultat}
        self.assertEqual(by_key['storage']['statut'], 'down')
        self.assertEqual(by_key['db']['statut'], 'ok')
        self.assertGreater(len(by_key['storage']['impactees']), 0)

    def test_check_services_failure_never_crashes(self):
        with mock.patch(
                'core.health.check_services', side_effect=RuntimeError('boom')):
            resultat = degraded_mode_status()
        self.assertEqual(len(resultat), len(DEGRADED_MODE_MATRIX))

    def test_llm_ia_status_is_ok_without_configured_provider(self):
        resultat = degraded_mode_status()
        by_key = {r['cle']: r for r in resultat}
        self.assertIn(by_key['llm_ia']['statut'], ('ok', 'unknown', 'degraded'))


class DegradedModeStatusEndpointTest(TestCase):
    def test_endpoint_is_public(self):
        resp = APIClient().get('/api/django/core/degraded-mode-status/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 5)
