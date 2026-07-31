"""NTAPI43 — Rejouer un import/export échoué + reprise sur curseur
`POST /api/public/jobs/<id>/relancer/`.

Couvre : un job EN ÉCHEC reprend au dernier `cursor` traité (idempotent — ne
re-traite jamais une ligne déjà appliquée, aucun doublon, aucun saut) ; un job
`termine`/`en_file` ne peut PAS être relancé.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

from . import bulk
from .constants import SCOPE_WRITE_LEADS
from .models import ApiKey, BulkJob


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key(company, scopes):
    return ApiKey.issue(company=company, label='k', scopes=scopes)


def _client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class _MinioMixin:
    def _mock_minio(self):
        import io as _io
        from apps.records import storage
        self._store = {}

        def _upload(fileobj, bucket, key, ExtraArgs=None):
            self._store[key] = fileobj.read()

        def _get_object(Bucket, Key):
            return {'Body': _io.BytesIO(self._store[Key])}

        client = mock.Mock()
        client.upload_fileobj.side_effect = _upload
        client.get_object.side_effect = _get_object
        p1 = mock.patch.object(storage, 'get_minio_client', return_value=client)
        p2 = mock.patch.object(storage, 'ensure_uploads_bucket')
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return client


class Ntapi43RelancerGuardTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi43', 'NTAPI43')
        self.api_key, _raw = _key(self.co, [SCOPE_WRITE_LEADS])

    def test_relancer_refuses_termine_job(self):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={}, statut=BulkJob.STATUT_TERMINE)
        with self.assertRaises(bulk.BulkJobError):
            bulk.relancer_job(job)

    def test_relancer_refuses_en_file_job(self):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={}, statut=BulkJob.STATUT_EN_FILE)
        with self.assertRaises(bulk.BulkJobError):
            bulk.relancer_job(job)

    def test_relancer_accepts_echec_job(self):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={}, statut=BulkJob.STATUT_ECHEC,
            message_erreur='panne réseau')
        with mock.patch.object(bulk, '_dispatch_import'):
            resumed = bulk.relancer_job(job)
        self.assertEqual(resumed.statut, BulkJob.STATUT_EN_FILE)
        self.assertEqual(resumed.message_erreur, '')


class Ntapi43RelancerEndpointTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi43b', 'NTAPI43B')
        self.api_key, self.raw = _key(self.co, [SCOPE_WRITE_LEADS])

    def test_relancer_termine_job_is_400(self):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={}, statut=BulkJob.STATUT_TERMINE)
        resp = _client(self.raw).post(f'/api/public/jobs/{job.id}/relancer/')
        self.assertEqual(resp.status_code, 400)

    def test_relancer_echec_job_is_200(self):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={}, statut=BulkJob.STATUT_ECHEC)
        with mock.patch.object(bulk, '_dispatch_import'):
            resp = _client(self.raw).post(f'/api/public/jobs/{job.id}/relancer/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], BulkJob.STATUT_EN_FILE)


class Ntapi43ResumeInterruptedImportTests(_MinioMixin, TestCase):
    """« Un import interrompu à la ligne 3000 relancé reprend à 3000 sans
    doublon ni saut » — vérifié ici à petite échelle (curseur explicite)."""

    def setUp(self):
        self.co = _company('ntapi43c', 'NTAPI43C')
        self.api_key, self.raw = _key(self.co, [SCOPE_WRITE_LEADS])
        self._mock_minio()

    def _make_job_with_cursor(self, csv_bytes, cursor, *, succes=0):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={'mode': 'create', 'format': 'csv'},
            cursor=cursor, succes=succes, statut=BulkJob.STATUT_ECHEC)
        source_key = bulk._store_import_source(
            csv_bytes, company_id=self.co.id, job_id=job.id, ext='csv')
        job.params['source_file_key'] = source_key
        job.save(update_fields=['params'])
        return job

    def test_resume_continues_from_cursor_without_reprocessing(self):
        rows = '\n'.join(f'Lead {i},lead{i}@example.com' for i in range(1, 6))
        csv_bytes = ('nom,email\n' + rows + '\n').encode()

        # Simule : les 2 premières lignes ont DÉJÀ été appliquées avant la
        # panne (curseur=2, 2 leads déjà créés manuellement — comme l'aurait
        # fait le premier passage de `run_import_job`).
        job = self._make_job_with_cursor(csv_bytes, cursor=2, succes=2)
        Lead.objects.create(company=self.co, nom='Lead 1', email='lead1@example.com')
        Lead.objects.create(company=self.co, nom='Lead 2', email='lead2@example.com')

        bulk.run_import_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        # 5 lignes au total, 2 déjà faites + 3 reprises = 5 leads, JAMAIS 7.
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 5)
        self.assertEqual(job.succes, 5)
        self.assertEqual(job.cursor, 5)

    def test_relancer_view_resumes_synchronously_when_broker_unreachable(self):
        # `_dispatch_import` retombe en traitement INLINE si Celery est
        # injoignable (comportement réel en environnement sans broker) —
        # vérifie que l'appel HTTP `relancer` fait progresser le job.
        csv_bytes = b'nom,email\nSeul,seul@example.com\n'
        job = self._make_job_with_cursor(csv_bytes, cursor=0, succes=0)

        with mock.patch('apps.publicapi.tasks.process_bulk_import_job.delay',
                        side_effect=RuntimeError('broker down')):
            resp = _client(self.raw).post(
                f'/api/public/jobs/{job.id}/relancer/')

        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 1)
