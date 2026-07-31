"""NTAPI14 — Export bulk asynchrone `POST /api/public/exports/`.

Couvre : création d'un `BulkJob` (statut initial `en_file`), scope requis
DÉPENDANT de l'entité (jamais un scope fixe), traitement synchrone
(`bulk.run_export_job`) produisant un CSV/JSONL complet déposé en MinIO
(mocké — aucun conteneur), jamais de `prix_achat`, et cross-tenant impossible.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

from . import bulk
from .constants import SCOPE_READ_LEADS, SCOPE_READ_STOCK
from .models import ApiKey, BulkJob


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key(company, scopes):
    instance, raw = ApiKey.issue(company=company, label='k', scopes=scopes)
    return instance, raw


def _client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class _MinioMixin:
    def _mock_minio(self):
        # `apps.records.storage.store_export_result`/`fetch_attachment` sont
        # importées PARESSEUSEMENT dans `bulk.py` (dans chaque fonction) : on
        # mocke le CLIENT MinIO résolu à l'exécution (même motif que
        # `tests_ntplt30_async_export.py`), jamais de conteneur nécessaire.
        from apps.records import storage
        client = mock.Mock()
        client.generate_presigned_url.return_value = 'https://minio/exports/x'
        p1 = mock.patch.object(storage, 'get_minio_client', return_value=client)
        p2 = mock.patch.object(storage, 'ensure_uploads_bucket')
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return client


class Ntapi14CreateExportJobTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi14', 'NTAPI14')
        self._mock_minio()

    def test_create_export_job_starts_en_file(self):
        api_key, _raw = _key(self.co, [SCOPE_READ_LEADS])
        with mock.patch.object(bulk, '_dispatch_export'):
            created = bulk.create_export_job(
                company=self.co, api_key=api_key, entite='leads')
        self.assertEqual(created.statut, BulkJob.STATUT_EN_FILE)
        self.assertEqual(created.type, BulkJob.TYPE_EXPORT)
        self.assertEqual(created.company_id, self.co.id)

    def test_unknown_entity_rejected(self):
        api_key, _raw = _key(self.co, [SCOPE_READ_LEADS])
        with self.assertRaises(bulk.BulkJobError):
            bulk.create_export_job(
                company=self.co, api_key=api_key, entite='inconnue')

    def test_unknown_format_rejected(self):
        api_key, _raw = _key(self.co, [SCOPE_READ_LEADS])
        with self.assertRaises(bulk.BulkJobError):
            bulk.create_export_job(
                company=self.co, api_key=api_key, entite='leads', fmt='xml')


class Ntapi14ExportEndpointTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi14b', 'NTAPI14B')
        self._mock_minio()

    def test_post_without_scope_is_403(self):
        _api_key, raw = _key(self.co, [])  # aucun scope
        resp = _client(raw).post(
            '/api/public/exports/', {'entite': 'leads'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_post_with_scope_returns_202_and_job(self):
        _api_key, raw = _key(self.co, [SCOPE_READ_LEADS])
        with mock.patch.object(bulk, '_dispatch_export'):
            resp = _client(raw).post(
                '/api/public/exports/', {'entite': 'leads'}, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['statut'], BulkJob.STATUT_EN_FILE)
        self.assertEqual(BulkJob.objects.filter(company=self.co).count(), 1)

    def test_wrong_entity_scope_is_403(self):
        # Une clé `read:leads` ne peut PAS exporter les produits (scope
        # read:stock requis) — jamais un scope bulk générique qui court-circuite.
        _api_key, raw = _key(self.co, [SCOPE_READ_LEADS])
        resp = _client(raw).post(
            '/api/public/exports/', {'entite': 'produits'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_produits_scope_can_export_produits(self):
        _api_key, raw = _key(self.co, [SCOPE_READ_STOCK])
        with mock.patch.object(bulk, '_dispatch_export'):
            resp = _client(raw).post(
                '/api/public/exports/', {'entite': 'produits'}, format='json')
        self.assertEqual(resp.status_code, 202)


class Ntapi14RunExportJobTests(_MinioMixin, TestCase):
    def setUp(self):
        self.co = _company('ntapi14c', 'NTAPI14C')
        self.other_co = _company('ntapi14c-other', 'Autre société')
        self.client_minio = self._mock_minio()

    def test_run_export_job_completes_and_stores_csv(self):
        for i in range(3):
            Lead.objects.create(company=self.co, nom=f'Lead {i}')
        # Un lead d'une AUTRE société ne doit jamais fuiter dans l'export.
        Lead.objects.create(company=self.other_co, nom='Autre société lead')

        api_key, _raw = _key(self.co, [SCOPE_READ_LEADS])
        job = BulkJob.objects.create(
            company=self.co, api_key=api_key, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={'format': 'csv', 'filtres': {}})

        bulk.run_export_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(job.total, 3)
        self.assertEqual(job.succes, 3)
        self.assertTrue(job.resultat_file_key.startswith(f'exports/{self.co.id}/'))
        self.assertTrue(self.client_minio.upload_fileobj.called)
        # Le CSV uploadé ne contient jamais prix_achat/marge (le serializer
        # public ne les expose jamais de toute façon — garde structurelle).
        uploaded_bytes = self.client_minio.upload_fileobj.call_args[0][0].read()
        self.assertNotIn(b'prix_achat', uploaded_bytes)

    def test_run_export_job_jsonl_format(self):
        Lead.objects.create(company=self.co, nom='Lead JSONL')
        api_key, _raw = _key(self.co, [SCOPE_READ_LEADS])
        job = BulkJob.objects.create(
            company=self.co, api_key=api_key, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={'format': 'jsonl', 'filtres': {}})

        bulk.run_export_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertTrue(job.resultat_file_key.endswith('.jsonl'))

    def test_run_export_job_unknown_job_is_noop(self):
        bulk.run_export_job(999999)  # ne lève jamais

    # Le suivi cross-tenant (`GET /api/public/jobs/<id>/`) est couvert par
    # `tests_ntapi16_job_tracking.py` (NTAPI16 — endpoint pas encore monté
    # dans cette tâche NTAPI14).
