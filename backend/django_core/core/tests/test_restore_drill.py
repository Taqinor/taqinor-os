"""Tests YOPSB2 — drill de restauration testé + garde base de production.

``pg_restore``/``createdb``/``dropdb``/MinIO/psycopg2 sont mockés. Couvre :
  * garde dure : refuse d'écrire si la base cible == la base de production ;
  * aucun dump disponible → échec propre (pas d'exception) ;
  * succès : restaure, compte, DROP la base scratch, journalise ;
  * pg_restore en échec → statut echec, la base scratch est quand même DROP.
"""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core import backup
from core.models import BackupRun


def _completed(returncode=0, stderr=b''):
    c = mock.Mock()
    c.returncode = returncode
    c.stderr = stderr
    return c


class RestoreDrillGuardTests(TestCase):
    @override_settings(DATABASES={'default': {
        'NAME': 'erp_db', 'HOST': 'db', 'PORT': '5432', 'USER': 'erp_user',
        'PASSWORD': 'x'}})
    def test_refuses_when_drill_db_equals_prod_db(self):
        run = BackupRun.objects.create(kind=BackupRun.KIND_RESTORE_DRILL,
                                       company=None)
        with mock.patch.dict('os.environ', {'BACKUP_RESTORE_DRILL_DB':
                                            'erp_db'}):
            result = backup.restore_drill(run)
        self.assertEqual(result.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('production', result.detail['message'])


class RestoreDrillTests(TestCase):
    def _make_source_dump(self):
        return BackupRun.objects.create(
            kind=BackupRun.KIND_DB_DUMP, statut=BackupRun.STATUT_TERMINE,
            object_key='pg_dumps/20260101-000000.dump', company=None)

    def test_no_dump_available_fails_cleanly(self):
        run = BackupRun.objects.create(kind=BackupRun.KIND_RESTORE_DRILL,
                                       company=None)
        result = backup.restore_drill(run)
        self.assertEqual(result.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('Aucun', result.detail['message'])

    def test_success_restores_counts_and_drops_scratch_db(self):
        self._make_source_dump()
        run = BackupRun.objects.create(kind=BackupRun.KIND_RESTORE_DRILL,
                                       company=None)
        fake_client = mock.Mock()
        fake_cursor = mock.MagicMock()
        fake_cursor.__enter__.return_value = fake_cursor
        fake_cursor.fetchone.return_value = (42,)
        fake_conn = mock.Mock()
        fake_conn.cursor.return_value = fake_cursor

        with mock.patch.object(backup, '_minio_client',
                               return_value=fake_client), \
                mock.patch('subprocess.run',
                           return_value=_completed(returncode=0)) as run_mock, \
                mock.patch('psycopg2.connect', return_value=fake_conn):
            result = backup.restore_drill(run)

        self.assertEqual(result.statut, BackupRun.STATUT_TERMINE)
        self.assertEqual(result.detail['comptages'],
                         {t: 42 for t in backup.RESTORE_DRILL_TABLES})
        fake_client.download_file.assert_called_once()
        # dropdb called at least twice (pré-nettoyage + nettoyage final).
        dropdb_calls = [c for c in run_mock.call_args_list
                        if c.args and c.args[0][0] == 'dropdb']
        self.assertGreaterEqual(len(dropdb_calls), 2)

    def test_pg_restore_failure_marks_echec_and_still_drops(self):
        self._make_source_dump()
        run = BackupRun.objects.create(kind=BackupRun.KIND_RESTORE_DRILL,
                                       company=None)
        fake_client = mock.Mock()

        def fake_run(args, **kwargs):
            if args[0] == 'createdb':
                return _completed(returncode=0)
            if args[0] == 'pg_restore':
                return _completed(returncode=1, stderr=b'corrupt dump')
            return _completed(returncode=0)

        with mock.patch.object(backup, '_minio_client',
                               return_value=fake_client), \
                mock.patch('subprocess.run', side_effect=fake_run) as run_mock:
            result = backup.restore_drill(run)

        self.assertEqual(result.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('pg_restore', result.detail['message'])
        dropdb_calls = [c for c in run_mock.call_args_list
                        if c.args and c.args[0][0] == 'dropdb']
        self.assertGreaterEqual(len(dropdb_calls), 2)

    def test_management_command_failure_exits_nonzero(self):
        with self.assertRaises(CommandError):
            call_command('restore_drill')
        run = BackupRun.objects.get(kind=BackupRun.KIND_RESTORE_DRILL)
        self.assertEqual(run.statut, BackupRun.STATUT_ECHEC)

    def test_management_command_success(self):
        self._make_source_dump()
        fake_client = mock.Mock()
        fake_cursor = mock.MagicMock()
        fake_cursor.__enter__.return_value = fake_cursor
        fake_cursor.fetchone.return_value = (1,)
        fake_conn = mock.Mock()
        fake_conn.cursor.return_value = fake_cursor

        with mock.patch.object(backup, '_minio_client',
                               return_value=fake_client), \
                mock.patch('subprocess.run',
                           return_value=_completed(returncode=0)), \
                mock.patch('psycopg2.connect', return_value=fake_conn):
            out = StringIO()
            call_command('restore_drill', stdout=out)

        self.assertIn('OK', out.getvalue())
