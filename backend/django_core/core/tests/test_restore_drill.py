"""Tests YOPSB2 — drill de restauration testé + garde base de production.

``pg_restore``/``createdb``/``dropdb``/MinIO/psycopg2 sont mockés. Couvre :
  * garde dure : refuse d'écrire si la base cible == la base de production ;
  * aucun dump disponible → échec propre (pas d'exception) ;
  * succès : restaure, compte, DROP la base scratch, journalise ;
  * pg_restore en échec → statut echec, la base scratch est quand même DROP.
"""
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
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

    def test_limite_de_temps_pendant_pg_restore_finit_en_echec(self):
        """ADCG35 — une SoftTimeLimitExceeded remonte, le run finit `echec`."""
        from celery.exceptions import SoftTimeLimitExceeded
        self._make_source_dump()
        run = BackupRun.objects.create(kind=BackupRun.KIND_RESTORE_DRILL,
                                       company=None)

        def fake_run(args, **kwargs):
            if args[0] == 'pg_restore':
                raise SoftTimeLimitExceeded()
            return _completed(returncode=0)

        with mock.patch.object(backup, '_minio_client', return_value=mock.Mock()), \
                mock.patch('subprocess.run', side_effect=fake_run) as run_mock:
            with self.assertRaises(SoftTimeLimitExceeded):
                backup.restore_drill(run)

        run.refresh_from_db()
        self.assertEqual(run.statut, BackupRun.STATUT_ECHEC)
        self.assertEqual(run.detail['message'],
                         'Exercice de restauration interrompu : SoftTimeLimitExceeded')
        dropdb_calls = [c for c in run_mock.call_args_list
                        if c.args and c.args[0][0] == 'dropdb']
        self.assertGreaterEqual(len(dropdb_calls), 2)

    def _drill_avec(self, restaure_n, lignes_societe):
        """ADCG38 — live : 5 lignes par table clé, société 1 = 1640 lignes."""
        self._make_source_dump()
        run = BackupRun.objects.create(kind=BackupRun.KIND_RESTORE_DRILL, company=None)
        fake_cursor = mock.MagicMock()
        fake_cursor.__enter__.return_value = fake_cursor
        fake_cursor.fetchone.return_value = (restaure_n,)
        fake_cursor.fetchall.return_value = lignes_societe
        fake_conn = mock.Mock()
        fake_conn.cursor.return_value = fake_cursor
        live = {t: 5 for t in backup.RESTORE_DRILL_TABLES}
        with mock.patch.object(backup, '_minio_client', return_value=mock.Mock()), \
                mock.patch('subprocess.run', return_value=_completed(returncode=0)), \
                mock.patch('psycopg2.connect', return_value=fake_conn), \
                mock.patch.object(backup, '_comptages_live', return_value=live), \
                mock.patch.object(backup, '_top_tenants_live', return_value={1: 1640}):
            backup.restore_drill(run)
        run.refresh_from_db()
        return run

    def test_restauration_vide_ou_societe_perdue_echec(self):
        vide = self._drill_avec(0, [])
        self.assertEqual(vide.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('Base restaurée incomplète : ', vide.detail['message'])
        self.assertIn('ventes_devis 0 ligne (live 5)', vide.detail['message'])
        self.assertEqual(vide.detail['comptages']['ventes_devis'], 0)

        perdue = self._drill_avec(3, [])
        self.assertEqual(perdue.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('société 1 sans données restaurées', perdue.detail['message'])
        self.assertEqual(perdue.detail['ecarts_tenant'], ['1'])

        complete = self._drill_avec(3, [(1, 1600)])  # restauré < live : normal
        self.assertEqual(complete.statut, BackupRun.STATUT_TERMINE)

    def test_taches_sauvegarde_limites_propres(self):
        """ADCG35 — dump et exercice ont leur limite, au-dessus des 3600 s."""
        from core.tasks import dump_database_task, restore_drill_task
        for tache in (dump_database_task, restore_drill_task):
            self.assertGreater(tache.soft_time_limit, 3600)
            self.assertGreater(tache.time_limit, tache.soft_time_limit)

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


class RestaurerSauvegardeTests(TestCase):
    """ADCG37 — restauration RÉELLE : propriétaires, droits, rôles, fichiers."""

    def _roles_sql(self):
        dossier = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, dossier, True)
        chemin = dossier / 'rls_roles.sql'
        chemin.write_text("ALTER ROLE erp_user BYPASSRLS;\n"
                          "GRANT CONNECT ON DATABASE erp_db TO app_rls;\n", encoding='utf-8')
        return str(chemin)

    def _minio(self):
        client = mock.Mock()

        def lister(Bucket, Prefix='', **_kw):
            if Bucket != backup.BACKUP_BUCKET:
                return {'Contents': []}
            return {'Contents': [{'Key': Prefix + 'ged/1/a.pdf', 'Size': 3, 'ETag': 'e'}]}
        client.list_objects_v2.side_effect = lister
        return client

    def test_restaure_avec_proprietaires_roles_et_fichiers(self):
        appels = []

        def fake_run(args, **kwargs):
            appels.append((args, kwargs))
            return _completed(returncode=0)

        client = self._minio()
        fake_cursor = mock.MagicMock()
        fake_cursor.__enter__.return_value = fake_cursor
        fake_cursor.fetchone.return_value = (7,)
        fake_conn = mock.Mock()
        fake_conn.cursor.return_value = fake_cursor
        out = StringIO()
        with mock.patch.object(backup, '_minio_client', return_value=client), \
                mock.patch('subprocess.run', side_effect=fake_run), \
                mock.patch('psycopg2.connect', return_value=fake_conn):
            call_command('restaurer_sauvegarde', '--dump', 'pg_dumps/20261110-030000.dump',
                         '--base', 'erp_restaure', '--suffixe-buckets', '-restaure',
                         '--roles-sql', self._roles_sql(), stdout=out)

        noms = [a[0] for a, _k in appels]
        self.assertNotIn('dropdb', noms)  # la base restaurée est CONSERVÉE
        restore = next(a for a, _k in appels if a[0] == 'pg_restore')
        self.assertNotIn('--no-owner', restore)
        self.assertNotIn('--no-privileges', restore)
        self.assertIn('erp_restaure', restore)
        psql = [(a, k) for a, k in appels if a[0] == 'psql']
        self.assertEqual(len(psql), 2)  # rôles avant ET après pg_restore
        self.assertLess(noms.index('psql'), noms.index('pg_restore'))
        self.assertIn('-f', psql[0][0])
        self.assertIn('DATABASE "erp_restaure"', psql[0][1]['input'].decode('utf-8'))
        cibles = sorted(c.kwargs['Bucket'] for c in client.copy_object.call_args_list)
        self.assertEqual(cibles, ['erp-pdf-restaure', 'erp-uploads-restaure'])
        run = BackupRun.objects.get(kind=BackupRun.KIND_RESTORE)
        self.assertEqual(run.statut, BackupRun.STATUT_TERMINE)
        self.assertEqual(run.detail['comptages'], {t: 7 for t in backup.RESTORE_DRILL_TABLES})
        self.assertIn('OK', out.getvalue())

    def test_refuse_la_base_de_production_sans_confirmation(self):
        prod = settings.DATABASES['default']['NAME']
        with mock.patch('subprocess.run') as run_mock:
            with self.assertRaises(CommandError):
                call_command('restaurer_sauvegarde', '--dump', 'pg_dumps/x.dump', '--base', prod)
        run_mock.assert_not_called()
        self.assertFalse(BackupRun.objects.filter(kind=BackupRun.KIND_RESTORE).exists())
        backup.verifier_cible_restauration(prod, prod)  # confirmée : pas de refus
        with self.assertRaises(backup.RestoreDrillGuardError):
            backup.verifier_cible_restauration('erp; DROP', None)
