"""ACEL66 — l'export asynchrone s'arrête à la limite douce au lieu d'être
relancé (la limite douce globale hérite d'``Exception`` : elle était relancée
jusqu'à 3 fois sur la file interactive)."""
from unittest import mock

from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.ventes import tasks as tasks_mod

_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'acel66'}}


@override_settings(CACHES=_CACHE)
class ExportAsynchroneLimiteDouceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.token = 'jeton-acel66'
        self.ckey = tasks_mod.export_job_cache_key(self.token)
        cache.set(self.ckey, {'company_id': 7, 'status': 'pending'})
        self.minio = mock.Mock()

    def _lancer(self, erreur):
        with mock.patch('apps.ventes.exports.build_export_xlsx_bytes',
                        side_effect=erreur) as builder, \
                mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                           return_value=self.minio):
            res = tasks_mod.task_build_async_export.apply(
                args=(7, 'journal', '2026-01-01', '2026-01-31', self.token))
        return res, builder

    def test_limite_douce_marque_error_sans_relance(self):
        res, builder = self._lancer(SoftTimeLimitExceeded())
        self.assertTrue(res.failed())
        self.assertIsInstance(res.result, SoftTimeLimitExceeded)
        self.assertNotIsInstance(res.result, Retry)
        self.assertEqual(builder.call_count, 1)  # aucune relance
        self.assertEqual(cache.get(self.ckey)['status'], 'error')
        self.minio.put_object.assert_not_called()

    def test_autre_erreur_garde_la_relance(self):
        res, builder = self._lancer(ValueError('boom'))
        self.assertTrue(res.failed())
        self.assertGreater(builder.call_count, 1)  # relance conservée
        self.assertEqual(cache.get(self.ckey)['status'], 'error')
