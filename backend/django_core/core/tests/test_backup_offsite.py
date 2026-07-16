"""Tests SCA13 — copie de sauvegarde hors-boîte (key-gated OFF par défaut).

``pg_dump``/MinIO/S3 hors-boîte sont TOUS mockés (pas de binaire ni de
service réel en test) : couvre le no-op silencieux sans les 4 variables
``BACKUP_OFFSITE_*``, le push réussi avec les 4 variables posées, l'échec du
push hors-boîte qui NE FAIT JAMAIS échouer le ``BackupRun`` (le backup local
MinIO reste la source de vérité du statut), et la rétention simple (N
derniers dumps hors-boîte)."""
import os
from unittest import mock

from django.test import TestCase

from core import backup
from core.models import BackupRun

_OFFSITE_ENV = {
    'BACKUP_OFFSITE_ENDPOINT': 'https://offsite.example.com',
    'BACKUP_OFFSITE_BUCKET': 'taqinor-offsite',
    'BACKUP_OFFSITE_ACCESS_KEY': 'fake-access-key',
    'BACKUP_OFFSITE_SECRET_KEY': 'fake-secret-key',
}


def _fake_completed_process(returncode=0, stderr=b''):
    completed = mock.Mock()
    completed.returncode = returncode
    completed.stderr = stderr
    return completed


class OffsiteConfigTests(TestCase):
    def test_not_configured_without_any_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in _OFFSITE_ENV:
                os.environ.pop(key, None)
            self.assertFalse(backup._offsite_configured())

    def test_not_configured_with_partial_env(self):
        """OFF tant que les 4 variables ne sont PAS TOUTES posées — un
        sous-ensemble partiel reste désactivé (jamais un push à moitié
        configuré)."""
        partial = dict(_OFFSITE_ENV)
        partial.pop('BACKUP_OFFSITE_SECRET_KEY')
        with mock.patch.dict(os.environ, partial, clear=False):
            os.environ.pop('BACKUP_OFFSITE_SECRET_KEY', None)
            self.assertFalse(backup._offsite_configured())

    def test_configured_with_all_four_env(self):
        with mock.patch.dict(os.environ, _OFFSITE_ENV, clear=False):
            self.assertTrue(backup._offsite_configured())

    def test_retain_last_defaults_to_seven(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('BACKUP_OFFSITE_RETAIN_LAST', None)
            cfg = backup._offsite_settings()
        self.assertEqual(cfg['retain_last'], 7)


class DumpDatabaseOffsiteTests(TestCase):
    """Couvre dump_database() de bout en bout avec le hors-boîte OFF/ON."""

    def _make_run(self):
        return BackupRun.objects.create(
            kind=BackupRun.KIND_DB_DUMP, mode=BackupRun.MODE_MANUEL,
            company=None)

    def _fake_write(self, *args, **kwargs):
        kwargs['stdout'].write(b'fake-dump-bytes')
        return _fake_completed_process(returncode=0)

    def test_dump_without_offsite_env_is_silent_noop(self):
        """Sans BACKUP_OFFSITE_* posé : comportement byte-identique à avant
        SCA13 — le run termine, AUCUN appel au client hors-boîte."""
        run = self._make_run()
        fake_minio = mock.Mock()

        with mock.patch.dict(os.environ, {}, clear=False):
            for key in _OFFSITE_ENV:
                os.environ.pop(key, None)
            with mock.patch('subprocess.run', side_effect=self._fake_write), \
                    mock.patch.object(backup, '_minio_client',
                                      return_value=fake_minio), \
                    mock.patch.object(backup, '_offsite_client') as offsite_client:
                result = backup.dump_database(run)

        self.assertEqual(result.statut, BackupRun.STATUT_TERMINE)
        offsite_client.assert_not_called()
        self.assertEqual(result.detail['offsite']['status'], 'off')
        self.assertFalse(result.detail['offsite']['configured'])

    def test_dump_with_offsite_env_pushes_and_stays_termine(self):
        run = self._make_run()
        fake_minio = mock.Mock()
        fake_offsite = mock.Mock()
        fake_offsite.list_objects_v2.return_value = {'Contents': []}

        with mock.patch.dict(os.environ, _OFFSITE_ENV, clear=False), \
                mock.patch('subprocess.run', side_effect=self._fake_write), \
                mock.patch.object(backup, '_minio_client',
                                  return_value=fake_minio), \
                mock.patch.object(backup, '_offsite_client',
                                  return_value=fake_offsite):
            result = backup.dump_database(run)

        self.assertEqual(result.statut, BackupRun.STATUT_TERMINE)
        fake_offsite.upload_file.assert_called_once()
        self.assertEqual(result.detail['offsite']['status'], 'ok')
        self.assertTrue(result.detail['offsite']['configured'])

    def test_offsite_push_failure_does_not_fail_the_run(self):
        """Le backup local (MinIO) a déjà réussi à ce stade — un échec du
        push hors-boîte reste TRACÉ mais ne fait JAMAIS échouer le
        BackupRun (la couche offsite est une résilience additionnelle,
        jamais un nouveau point de défaillance pour le backup principal)."""
        run = self._make_run()
        fake_minio = mock.Mock()

        with mock.patch.dict(os.environ, _OFFSITE_ENV, clear=False), \
                mock.patch('subprocess.run', side_effect=self._fake_write), \
                mock.patch.object(backup, '_minio_client',
                                  return_value=fake_minio), \
                mock.patch.object(backup, '_offsite_client',
                                  side_effect=RuntimeError('offsite injoignable')):
            result = backup.dump_database(run)

        self.assertEqual(result.statut, BackupRun.STATUT_TERMINE)
        self.assertEqual(result.detail['offsite']['status'], 'echec')
        self.assertIn('offsite injoignable', result.detail['offsite']['message'])


class OffsiteRetentionTests(TestCase):
    def test_retention_keeps_last_n_and_deletes_rest(self):
        fake_client = mock.Mock()
        fake_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'pg_dumps/20260101-000000.dump'},
                {'Key': 'pg_dumps/20260102-000000.dump'},
                {'Key': 'pg_dumps/20260103-000000.dump'},
            ]
        }
        cfg = {'bucket': 'taqinor-offsite', 'retain_last': 2}

        result = backup._purge_offsite_retention(fake_client, cfg)

        self.assertEqual(result['conserves'], 2)
        self.assertEqual(result['supprimes'], 1)
        fake_client.delete_object.assert_called_once_with(
            Bucket='taqinor-offsite', Key='pg_dumps/20260101-000000.dump')

    def test_retention_failure_is_best_effort(self):
        fake_client = mock.Mock()
        fake_client.list_objects_v2.side_effect = RuntimeError('list failed')
        cfg = {'bucket': 'taqinor-offsite', 'retain_last': 7}

        result = backup._purge_offsite_retention(fake_client, cfg)

        self.assertIn('erreur', result)
