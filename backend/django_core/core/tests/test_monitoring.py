"""Tests FG396 — monitoring d'erreurs (Sentry), gardé par DSN.

Couvre :
  * sans DSN → désactivé, init no-op (renvoie False) ;
  * avec DSN mais sentry-sdk absent → no-op silencieux (jamais d'exception) ;
  * is_enabled reflète le DSN.
"""
from unittest import mock

from django.test import SimpleTestCase

from core import monitoring


class MonitoringTests(SimpleTestCase):
    def setUp(self):
        # Réinitialise le drapeau idempotent pour chaque test.
        monitoring._INITIALISE = False

    def test_disabled_without_dsn(self):
        with mock.patch.dict('os.environ', {'SENTRY_DSN': ''}, clear=False):
            self.assertFalse(monitoring.is_enabled())
            self.assertFalse(monitoring.init_sentry())

    def test_init_noop_when_sdk_missing(self):
        # DSN présent mais import sentry_sdk échoue → no-op (False), pas d'erreur.
        with mock.patch.dict('os.environ',
                             {'SENTRY_DSN': 'https://x@example/1'},
                             clear=False):
            self.assertTrue(monitoring.is_enabled())
            with mock.patch.dict('sys.modules', {'sentry_sdk': None}):
                self.assertFalse(monitoring.init_sentry())

    def test_init_runs_with_fake_sdk(self):
        fake = mock.MagicMock()
        with mock.patch.dict('os.environ',
                             {'SENTRY_DSN': 'https://x@example/1'},
                             clear=False):
            with mock.patch.dict('sys.modules', {'sentry_sdk': fake}):
                self.assertTrue(monitoring.init_sentry())
                fake.init.assert_called_once()

    def test_init_passes_release_from_env(self):
        # BPQ9 — `release` = sha déployé (SENTRY_RELEASE), pour que Sentry
        # distingue « régressé après tel déploiement » de « jamais corrigé ».
        fake = mock.MagicMock()
        with mock.patch.dict('os.environ',
                             {'SENTRY_DSN': 'https://x@example/1',
                              'SENTRY_RELEASE': 'abc1234'},
                             clear=False):
            with mock.patch.dict('sys.modules', {'sentry_sdk': fake}):
                self.assertTrue(monitoring.init_sentry())
                self.assertEqual(fake.init.call_args.kwargs['release'], 'abc1234')

    def test_init_without_release_env_passes_none(self):
        fake = mock.MagicMock()
        env = {'SENTRY_DSN': 'https://x@example/1', 'SENTRY_RELEASE': ''}
        with mock.patch.dict('os.environ', env, clear=False):
            with mock.patch.dict('sys.modules', {'sentry_sdk': fake}):
                self.assertTrue(monitoring.init_sentry())
                self.assertIsNone(fake.init.call_args.kwargs['release'])
