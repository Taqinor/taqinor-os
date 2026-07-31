"""NTAPI15 — Import bulk asynchrone `POST /api/public/imports/` (leads/activités).

Couvre : upload CSV/JSONL → `BulkJob` import, mode `create`/`upsert` (dédup
email/téléphone), un fichier MIXTE crée les lignes valides et liste
PRÉCISÉMENT les invalides (`erreurs_file_key`) sans bloquer les valides, un
rejeu upsert NE duplique jamais.
"""
import io
import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

from . import bulk
from .constants import SCOPE_WRITE_ACTIVITIES, SCOPE_WRITE_LEADS
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
        from apps.records import storage
        self._store = {}

        def _upload(fileobj, bucket, key, ExtraArgs=None):
            self._store[key] = fileobj.read()

        def _get_object(Bucket, Key):
            return {'Body': io.BytesIO(self._store[Key])}

        client = mock.Mock()
        client.upload_fileobj.side_effect = _upload
        client.get_object.side_effect = _get_object
        client.generate_presigned_url.return_value = 'https://minio/x'
        p1 = mock.patch.object(storage, 'get_minio_client', return_value=client)
        p2 = mock.patch.object(storage, 'ensure_uploads_bucket')
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return client


class Ntapi15CreateImportJobTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi15', 'NTAPI15')
        self._mock_minio()

    def test_upsert_without_dedup_key_rejected(self):
        api_key, _raw = _key(self.co, [SCOPE_WRITE_LEADS])
        with self.assertRaises(bulk.BulkJobError):
            bulk.create_import_job(
                company=self.co, api_key=api_key, entite='leads',
                mode='upsert', dedup_key=None, file_bytes=b'nom\nx\n')

    def test_empty_file_rejected(self):
        api_key, _raw = _key(self.co, [SCOPE_WRITE_LEADS])
        with self.assertRaises(bulk.BulkJobError):
            bulk.create_import_job(
                company=self.co, api_key=api_key, entite='leads',
                file_bytes=b'')


class Ntapi15ImportEndpointTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi15b', 'NTAPI15B')
        self._mock_minio()

    def test_post_without_scope_is_403(self):
        _api_key, raw = _key(self.co, [])
        upload = SimpleUploadedFile('l.csv', b'nom\nx\n', content_type='text/csv')
        resp = _client(raw).post(
            '/api/public/imports/',
            {'entite': 'leads', 'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 403)

    def test_post_with_scope_returns_202(self):
        _api_key, raw = _key(self.co, [SCOPE_WRITE_LEADS])
        upload = SimpleUploadedFile('l.csv', b'nom\nx\n', content_type='text/csv')
        with mock.patch.object(bulk, '_dispatch_import'):
            resp = _client(raw).post(
                '/api/public/imports/',
                {'entite': 'leads', 'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(BulkJob.objects.filter(company=self.co).count(), 1)


class Ntapi15RunImportJobTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi15c', 'NTAPI15C')
        self._mock_minio()

    def _make_job(self, csv_bytes, *, mode='create', dedup_key=None):
        api_key, _raw = _key(self.co, [SCOPE_WRITE_LEADS])
        job = BulkJob.objects.create(
            company=self.co, api_key=api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads',
            params={'mode': mode, 'dedup_key': dedup_key, 'format': 'csv'})
        source_key = bulk._store_import_source(
            csv_bytes, company_id=self.co.id, job_id=job.id, ext='csv')
        job.params['source_file_key'] = source_key
        job.save(update_fields=['params'])
        return job

    def test_mixed_file_creates_valid_and_lists_invalid(self):
        csv_bytes = (
            b'nom,email\n'
            b'Lead Un,un@example.com\n'
            b',invalide@example.com\n'  # nom manquant -> ValueError
            b'Lead Trois,trois@example.com\n'
        )
        job = self._make_job(csv_bytes)

        bulk.run_import_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(job.succes, 2)
        self.assertEqual(job.erreurs, 1)
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 2)
        self.assertTrue(job.erreurs_file_key)

        error_bytes = self._store[job.erreurs_file_key]
        error_rows = [json.loads(line) for line in error_bytes.decode().splitlines()]
        self.assertEqual(len(error_rows), 1)
        # 2e ligne de DONNÉES (le nom manque) — `csv.DictReader` numérote à
        # partir de 1 sur les lignes de données (en-tête déjà consommé).
        self.assertEqual(error_rows[0]['ligne'], 2)

    def test_upsert_replay_does_not_duplicate(self):
        csv_bytes = b'nom,email\nLead Un,un@example.com\n'
        job1 = self._make_job(csv_bytes, mode='upsert', dedup_key='email')
        bulk.run_import_job(job1.id)
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 1)

        # Rejeu du MÊME fichier en upsert : ne crée PAS un second lead.
        job2 = self._make_job(csv_bytes, mode='upsert', dedup_key='email')
        bulk.run_import_job(job2.id)
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 1)

    def test_create_mode_without_dedup_creates_new_each_time(self):
        csv_bytes = b'nom,email\nLead Un,un@example.com\n'
        job1 = self._make_job(csv_bytes, mode='create')
        bulk.run_import_job(job1.id)
        job2 = self._make_job(csv_bytes, mode='create')
        bulk.run_import_job(job2.id)
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 2)

    def test_unreadable_source_marks_job_echec(self):
        api_key, _raw = _key(self.co, [SCOPE_WRITE_LEADS])
        job = BulkJob.objects.create(
            company=self.co, api_key=api_key, type=BulkJob.TYPE_IMPORT,
            entite='leads',
            params={'mode': 'create', 'format': 'csv',
                    'source_file_key': 'imports/does-not-exist.csv'})
        bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_ECHEC)


class Ntapi15ActivitesImportTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi15d', 'NTAPI15D')
        self._mock_minio()

    def test_import_activites_requires_lead_id(self):
        lead = Lead.objects.create(company=self.co, nom='Lead cible')
        api_key, _raw = _key(self.co, [SCOPE_WRITE_ACTIVITIES])
        csv_bytes = (
            f'lead_id,body\n{lead.id},Note valide\n,Note orpheline\n'
        ).encode()
        job = BulkJob.objects.create(
            company=self.co, api_key=api_key, type=BulkJob.TYPE_IMPORT,
            entite='activites', params={'mode': 'create', 'format': 'csv'})
        source_key = bulk._store_import_source(
            csv_bytes, company_id=self.co.id, job_id=job.id, ext='csv')
        job.params['source_file_key'] = source_key
        job.save(update_fields=['params'])

        bulk.run_import_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.succes, 1)
        self.assertEqual(job.erreurs, 1)
