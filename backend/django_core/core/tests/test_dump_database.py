"""Tests YOPSB1 — pg_dump réel planifié vers MinIO.

``pg_dump``/MinIO sont mockés (pas de binaire ni de service réel en test) :
couvre le succès (BackupRun termine, object_key/bytes_taille posés), l'échec
pg_dump (code retour non nul → statut echec, exit non nul de la commande de
gestion), et l'échec d'upload MinIO."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import backup
from core.models import BackupRun


def _fake_completed_process(returncode=0, stderr=b''):
    completed = mock.Mock()
    completed.returncode = returncode
    completed.stderr = stderr
    return completed


class DumpDatabaseTests(TestCase):
    def _make_run(self):
        return BackupRun.objects.create(
            kind=BackupRun.KIND_DB_DUMP, mode=BackupRun.MODE_MANUEL,
            company=None)

    def test_dump_success_uploads_and_marks_termine(self):
        run = self._make_run()
        fake_client = mock.Mock()

        def fake_write(*args, **kwargs):
            # args[0] is the pg_dump argv list; stdout kwarg is the open file
            kwargs['stdout'].write(b'fake-dump-bytes')
            return _fake_completed_process(returncode=0)

        with mock.patch('subprocess.run', side_effect=fake_write), \
                mock.patch.object(backup, '_minio_client',
                                  return_value=fake_client):
            result = backup.dump_database(run)

        self.assertEqual(result.statut, BackupRun.STATUT_TERMINE)
        self.assertTrue(result.object_key.startswith('pg_dumps/'))
        self.assertEqual(result.bytes_taille, len(b'fake-dump-bytes'))
        self.assertTrue(result.artifact_ref.startswith('minio://erp-backups/'))
        fake_client.upload_file.assert_called_once()

    def test_dump_pg_dump_failure_marks_echec(self):
        run = self._make_run()
        with mock.patch('subprocess.run',
                        return_value=_fake_completed_process(
                            returncode=1, stderr=b'connection refused')):
            result = backup.dump_database(run)

        self.assertEqual(result.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('connection refused', result.detail.get('stderr', ''))

    def test_dump_upload_failure_marks_echec(self):
        run = self._make_run()
        fake_client = mock.Mock()
        fake_client.upload_file.side_effect = RuntimeError('minio down')

        def fake_write(*args, **kwargs):
            kwargs['stdout'].write(b'x')
            return _fake_completed_process(returncode=0)

        with mock.patch('subprocess.run', side_effect=fake_write), \
                mock.patch.object(backup, '_minio_client',
                                  return_value=fake_client):
            result = backup.dump_database(run)

        self.assertEqual(result.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('minio down', result.detail.get('message', ''))

    def test_management_command_success(self):
        fake_client = mock.Mock()

        def fake_write(*args, **kwargs):
            kwargs['stdout'].write(b'ok')
            return _fake_completed_process(returncode=0)

        with mock.patch('subprocess.run', side_effect=fake_write), \
                mock.patch.object(backup, '_minio_client',
                                  return_value=fake_client):
            out = StringIO()
            call_command('dump_database', stdout=out)

        self.assertIn('OK', out.getvalue())
        run = BackupRun.objects.get(kind=BackupRun.KIND_DB_DUMP)
        self.assertEqual(run.statut, BackupRun.STATUT_TERMINE)

    def test_management_command_failure_exits_nonzero(self):
        with mock.patch('subprocess.run',
                        return_value=_fake_completed_process(returncode=1)):
            with self.assertRaises(CommandError):
                call_command('dump_database')

        run = BackupRun.objects.get(kind=BackupRun.KIND_DB_DUMP)
        self.assertEqual(run.statut, BackupRun.STATUT_ECHEC)
