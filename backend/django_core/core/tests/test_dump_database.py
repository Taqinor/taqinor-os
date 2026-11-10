"""Tests YOPSB1 — pg_dump réel planifié vers MinIO.

``pg_dump``/MinIO sont mockés (pas de binaire ni de service réel en test) :
couvre le succès (BackupRun termine, object_key/bytes_taille posés), l'échec
pg_dump (code retour non nul → statut echec, exit non nul de la commande de
gestion), et l'échec d'upload MinIO."""
from io import BytesIO, StringIO
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


class _FauxS3:
    """ADCG30 — double S3 minimal : ``{bucket: {clé: (octets, etag)}}``."""

    def __init__(self, contenu=None):
        self.store = {b: dict(objs) for b, objs in (contenu or {}).items()}
        self.upload_file = mock.Mock()

    def list_objects_v2(self, Bucket, Prefix='', **_kw):
        objs = self.store.get(Bucket, {})
        return {'Contents': [{'Key': k, 'Size': len(v[0]), 'ETag': v[1]}
                             for k, v in sorted(objs.items()) if k.startswith(Prefix)]}

    def copy_object(self, Bucket, Key, CopySource):
        src = self.store[CopySource['Bucket']][CopySource['Key']]
        self.store.setdefault(Bucket, {})[Key] = src

    def get_object(self, Bucket, Key):
        return {'Body': BytesIO(self.store[Bucket][Key][0])}

    def upload_fileobj(self, corps, Bucket, Key):
        self.store.setdefault(Bucket, {})[Key] = (corps.read(), 'distant')


_DISTANT_ENV = {
    'BACKUP_OFFSITE_ENDPOINT': 'https://offsite.example.com',
    'BACKUP_OFFSITE_BUCKET': 'taqinor-offsite',
    'BACKUP_OFFSITE_ACCESS_KEY': 'fake-access-key',
    'BACKUP_OFFSITE_SECRET_KEY': 'fake-secret-key',
}


def _ecrire_dump(*args, **kwargs):
    kwargs['stdout'].write(b'dump')
    return _fake_completed_process(returncode=0)


class DumpDatabaseTests(TestCase):
    def _make_run(self):
        return BackupRun.objects.create(
            kind=BackupRun.KIND_DB_DUMP, mode=BackupRun.MODE_MANUEL,
            company=None)

    def test_dump_success_uploads_and_marks_termine(self):
        run = self._make_run()
        fake_client = mock.Mock()
        fake_client.list_objects_v2.return_value = {'Contents': []}  # ADCG30 : buckets vides

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
        fake_client.list_objects_v2.return_value = {'Contents': []}  # ADCG30 : buckets vides

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

    def _dump_avec(self, client, env=None):
        cles = {k: '' for k in _DISTANT_ENV}
        cles.update(env or {})
        with mock.patch.dict('os.environ', cles), \
                mock.patch('subprocess.run', side_effect=_ecrire_dump), \
                mock.patch.object(backup, '_minio_client', return_value=client):
            return backup.dump_database(self._make_run())

    def test_dump_copie_les_buckets_metier(self):
        """ADCG30 — les fichiers métier suivent le dump ; jamais de suppression."""
        client = _FauxS3({
            'erp-uploads': {'ged/1/a.pdf': (b'aaa', 'e1'), 'ged/1/b.pdf': (b'bb', 'e2')},
            'erp-pdf': {'devis/1.pdf': (b'p', 'e3')},
        })
        run = self._dump_avec(client)
        self.assertEqual(run.statut, BackupRun.STATUT_TERMINE)
        run.refresh_from_db()
        self.assertEqual(run.detail['fichiers'], {
            'erp-uploads': {'objets': 2, 'octets': 5},
            'erp-pdf': {'objets': 1, 'octets': 1},
        })
        copies = sorted(k for k in client.store['erp-backups'] if k.startswith('fichiers/'))
        self.assertEqual(copies, ['fichiers/erp-pdf/devis/1.pdf', 'fichiers/erp-uploads/ged/1/a.pdf',
                                  'fichiers/erp-uploads/ged/1/b.pdf'])
        del client.store['erp-uploads']['ged/1/a.pdf']
        run2 = self._dump_avec(client)
        self.assertEqual(run2.statut, BackupRun.STATUT_TERMINE)
        self.assertIn('fichiers/erp-uploads/ged/1/a.pdf', client.store['erp-backups'])
        self.assertEqual(run2.detail['fichiers']['erp-uploads']['objets'], 1)

    def test_dump_echec_copie_fichiers_nomme_le_bucket(self):
        client = _FauxS3({'erp-uploads': {'a': (b'a', 'e')}})
        client.copy_object = mock.Mock(side_effect=RuntimeError('disque plein'))
        run = self._dump_avec(client)
        self.assertEqual(run.statut, BackupRun.STATUT_ECHEC)
        self.assertIn('erp-uploads', run.detail['message'])
        self.assertIn('disque plein', run.detail['message'])

    def test_dump_pousse_les_fichiers_vers_la_cible_distante(self):
        client = _FauxS3({'erp-pdf': {'devis/1.pdf': (b'p', 'e3')}})
        distant = _FauxS3()
        with mock.patch.object(backup, '_offsite_client', return_value=distant):
            run = self._dump_avec(client, _DISTANT_ENV)
        self.assertEqual(run.statut, BackupRun.STATUT_TERMINE)
        self.assertEqual(run.detail['fichiers']['erp-pdf']['offsite'], 'ok')
        bucket = _DISTANT_ENV['BACKUP_OFFSITE_BUCKET']
        self.assertIn('fichiers/erp-pdf/devis/1.pdf', distant.store[bucket])
