"""Tests YOPSB3 — rétention GFS + purge automatique des sauvegardes.

Couvre : schéma GFS réduit un jeu de dumps datés au nombre attendu (horloge
simulée), rien n'est supprimé en dry-run (défaut), la purge (apply_=True)
retire l'objet MinIO + soft-delete le BackupRun, les runs déjà purgés sont
ignorés à l'exécution suivante."""
import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from core import backup
from core.models import BackupRun


def _make_run(termine_le):
    return BackupRun.objects.create(
        kind=BackupRun.KIND_DB_DUMP, statut=BackupRun.STATUT_TERMINE,
        company=None, termine_le=termine_le,
        object_key=f'pg_dumps/{termine_le:%Y%m%d-%H%M%S}.dump')


class PurgeBackupsGfsTests(TestCase):
    def test_dry_run_deletes_nothing(self):
        now = timezone.now()
        for i in range(20):
            _make_run(now - datetime.timedelta(days=i))

        result = backup.purger_backups(now=now, apply_=False)

        self.assertTrue(result['dry_run'])
        self.assertEqual(
            BackupRun.objects.filter(purge_is_deleted=True).count(), 0)
        self.assertGreater(result['supprimes'], 0)

    @mock.patch.dict('os.environ', {
        'BACKUP_RETENTION_DAILY': '7',
        'BACKUP_RETENTION_WEEKLY': '4',
        'BACKUP_RETENTION_MONTHLY': '12',
    })
    def test_gfs_scheme_reduces_to_expected_set(self):
        now = timezone.now()
        # Un dump par jour sur 400 jours (largement > 12 mois).
        for i in range(400):
            _make_run(now - datetime.timedelta(days=i))

        fake_client = mock.Mock()
        with mock.patch.object(backup, '_minio_client',
                               return_value=fake_client):
            result = backup.purger_backups(now=now, apply_=True)

        self.assertFalse(result['dry_run'])
        restants = BackupRun.objects.filter(purge_is_deleted=False).count()
        self.assertEqual(restants, result['conserves'])
        # Borne large : le schéma GFS doit réduire drastiquement 400 → une
        # poignée (7 quotidiens + ≤4 hebdo + ≤12 mensuels, chevauchements
        # possibles mais jamais > 23).
        self.assertLessEqual(restants, 23)
        self.assertGreater(restants, 0)
        self.assertEqual(
            BackupRun.objects.filter(purge_is_deleted=True).count(),
            result['supprimes'])
        self.assertTrue(fake_client.delete_object.called)

    def test_apply_true_soft_deletes_and_removes_minio_object(self):
        now = timezone.now()
        old_run = _make_run(now - datetime.timedelta(days=400))
        recent_run = _make_run(now)

        fake_client = mock.Mock()
        with mock.patch.object(backup, '_minio_client',
                               return_value=fake_client):
            backup.purger_backups(now=now, apply_=True)

        old_run.refresh_from_db()
        recent_run.refresh_from_db()
        self.assertTrue(old_run.purge_is_deleted)
        self.assertIsNotNone(old_run.purge_deleted_at)
        self.assertFalse(recent_run.purge_is_deleted)
        fake_client.delete_object.assert_any_call(
            Bucket=backup.BACKUP_BUCKET, Key=old_run.object_key)

    def test_already_purged_runs_are_excluded_from_next_pass(self):
        now = timezone.now()
        old_run = _make_run(now - datetime.timedelta(days=400))
        old_run.purge_is_deleted = True
        old_run.purge_deleted_at = now
        old_run.save(update_fields=['purge_is_deleted', 'purge_deleted_at'])

        fake_client = mock.Mock()
        with mock.patch.object(backup, '_minio_client',
                               return_value=fake_client):
            result = backup.purger_backups(now=now, apply_=True)

        self.assertEqual(result['supprimes'], 0)
        fake_client.delete_object.assert_not_called()
