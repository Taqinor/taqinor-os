"""NTOBS24 — purge planifiée des vieux incidents/exports/buckets d'uptime."""
import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from django.apps import apps as django_apps
from authentication.models import Company
from core.export_registry import ExportReversibiliteRun
from core.tasks import purger_donnees_fiabilite_task

# Pas d'import statique d'une app domaine sous core (contrat import-linter M3)
IncidentPublic = django_apps.get_model('statuspage', 'IncidentPublic')
UptimeDayBucket = django_apps.get_model('statuspage', 'UptimeDayBucket')


class PurgerIncidentsResolusTest(TestCase):
    def test_old_resolved_incident_is_deleted(self):
        vieux = timezone.now() - datetime.timedelta(days=800)
        incident = IncidentPublic.objects.create(
            titre='Vieille panne', company=None, debute_le=vieux,
            statut=IncidentPublic.Statut.RESOLVED, resolu_le=vieux)
        purger_donnees_fiabilite_task()
        self.assertFalse(
            IncidentPublic.objects.filter(pk=incident.pk).exists())

    def test_recent_resolved_incident_is_kept(self):
        recent = timezone.now() - datetime.timedelta(days=10)
        incident = IncidentPublic.objects.create(
            titre='Panne récente', company=None, debute_le=recent,
            statut=IncidentPublic.Statut.RESOLVED, resolu_le=recent)
        purger_donnees_fiabilite_task()
        self.assertTrue(
            IncidentPublic.objects.filter(pk=incident.pk).exists())

    def test_old_unresolved_incident_is_kept(self):
        """Jamais un incident encore ouvert, même ancien."""
        vieux = timezone.now() - datetime.timedelta(days=800)
        incident = IncidentPublic.objects.create(
            titre='Toujours ouverte', company=None, debute_le=vieux)
        purger_donnees_fiabilite_task()
        self.assertTrue(
            IncidentPublic.objects.filter(pk=incident.pk).exists())


class PurgerExportsReversibiliteTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs24-acme')

    def test_expired_export_is_deleted_and_minio_key_removed(self):
        run = ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.EXPIRE,
            fichier_key='acme/export-old.zip',
            expire_le=timezone.now() - datetime.timedelta(days=45))
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            purger_donnees_fiabilite_task()
        self.assertFalse(
            ExportReversibiliteRun.objects.filter(pk=run.pk).exists())
        self.assertTrue(fake_client.delete_object.called)

    def test_recently_expired_export_is_kept(self):
        run = ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.EXPIRE,
            fichier_key='acme/export-recent.zip',
            expire_le=timezone.now() - datetime.timedelta(days=5))
        purger_donnees_fiabilite_task()
        self.assertTrue(
            ExportReversibiliteRun.objects.filter(pk=run.pk).exists())

    def test_minio_failure_never_blocks_db_row_deletion(self):
        run = ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.EXPIRE,
            fichier_key='acme/export-old2.zip',
            expire_le=timezone.now() - datetime.timedelta(days=45))
        with mock.patch(
                'core.backup._minio_client', side_effect=RuntimeError('boom')):
            purger_donnees_fiabilite_task()
        self.assertFalse(
            ExportReversibiliteRun.objects.filter(pk=run.pk).exists())


class PurgerUptimeBucketsTest(TestCase):
    def test_old_bucket_is_deleted(self):
        vieux = timezone.now().date() - datetime.timedelta(days=450)
        bucket = UptimeDayBucket.objects.create(
            company=None, composant='API', region='EU-West/Hetzner',
            date=vieux, statut_pire_du_jour='operational')
        purger_donnees_fiabilite_task()
        self.assertFalse(
            UptimeDayBucket.objects.filter(pk=bucket.pk).exists())

    def test_bucket_within_13_months_is_kept(self):
        recent = timezone.now().date() - datetime.timedelta(days=200)
        bucket = UptimeDayBucket.objects.create(
            company=None, composant='API', region='EU-West/Hetzner',
            date=recent, statut_pire_du_jour='operational')
        purger_donnees_fiabilite_task()
        self.assertTrue(
            UptimeDayBucket.objects.filter(pk=bucket.pk).exists())


class PurgerDonneesFiabiliteIdempotenceTest(TestCase):
    def test_running_twice_deletes_nothing_the_second_time(self):
        vieux = timezone.now() - datetime.timedelta(days=800)
        IncidentPublic.objects.create(
            titre='Vieille panne', company=None, debute_le=vieux,
            statut=IncidentPublic.Statut.RESOLVED, resolu_le=vieux)
        r1 = purger_donnees_fiabilite_task()
        r2 = purger_donnees_fiabilite_task()
        self.assertEqual(r1['incidents'], 1)
        self.assertEqual(r2['incidents'], 0)
