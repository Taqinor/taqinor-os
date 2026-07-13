"""NTPLT30 — Exports lourds asynchrones : brique de stockage/décision.

Couvre la primitive ajoutée à ``apps/records/storage.py`` : décision
sync-vs-async par seuil de lignes (env-pilotable, off-switch), clé MinIO du
livrable isolée PAR SOCIÉTÉ, dépôt + URL présignée courte durée. Le client
MinIO est mocké — aucun conteneur, aucune DB nécessaire (``SimpleTestCase``)."""
from unittest import mock

from django.test import SimpleTestCase

from apps.records import storage


class ExportThresholdTests(SimpleTestCase):
    def test_default_threshold_is_5000(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('NTPLT30_EXPORT_ROW_THRESHOLD', None)
            self.assertEqual(storage.export_row_threshold(), 5000)

    def test_env_override(self):
        with mock.patch.dict(
                'os.environ', {'NTPLT30_EXPORT_ROW_THRESHOLD': '100'}):
            self.assertEqual(storage.export_row_threshold(), 100)

    def test_illegible_env_falls_back_to_default(self):
        with mock.patch.dict(
                'os.environ', {'NTPLT30_EXPORT_ROW_THRESHOLD': 'abc'}):
            self.assertEqual(storage.export_row_threshold(), 5000)

    def test_should_async_over_threshold(self):
        self.assertTrue(storage.should_async_export(5001, threshold=5000))
        self.assertFalse(storage.should_async_export(5000, threshold=5000))
        self.assertFalse(storage.should_async_export(10, threshold=5000))

    def test_threshold_zero_disables_async(self):
        # 0 (ou négatif) = off-switch : jamais d'asynchrone.
        self.assertFalse(storage.should_async_export(10 ** 9, threshold=0))
        self.assertFalse(storage.should_async_export(10 ** 9, threshold=-1))

    def test_should_async_uses_env_when_threshold_none(self):
        with mock.patch.dict(
                'os.environ', {'NTPLT30_EXPORT_ROW_THRESHOLD': '3'}):
            self.assertTrue(storage.should_async_export(4))
            self.assertFalse(storage.should_async_export(3))


class ExportResultKeyTests(SimpleTestCase):
    def test_key_is_company_scoped(self):
        # Isolation multi-tenant : la clé porte l'id société.
        self.assertEqual(
            storage.export_result_key(42, 'job-7', ext='xlsx'),
            'exports/42/job-7.xlsx')

    def test_key_accepts_company_instance(self):
        company = mock.Mock(id=9)
        self.assertEqual(
            storage.export_result_key(company, 5, ext='csv'),
            'exports/9/5.csv')

    def test_key_without_company_falls_back_to_zero(self):
        self.assertEqual(
            storage.export_result_key(None, 'j', ext='.xlsx'),
            'exports/0/j.xlsx')


class ExportStorageTests(SimpleTestCase):
    def test_store_export_result_uploads_and_returns_key(self):
        client = mock.Mock()
        with mock.patch.object(storage, 'get_minio_client',
                               return_value=client), \
                mock.patch.object(storage, 'ensure_uploads_bucket') as ensure:
            key = storage.store_export_result(
                b'PK\x03\x04data', company_id=7, job_id='abc', ext='xlsx',
                content_type='application/vnd.ms-excel')
        self.assertEqual(key, 'exports/7/abc.xlsx')
        ensure.assert_called_once()
        self.assertTrue(client.upload_fileobj.called)
        # Le bucket uploads existant est réutilisé (aucune dépendance nouvelle).
        args, kwargs = client.upload_fileobj.call_args
        self.assertIn(storage.settings.MINIO_BUCKET_UPLOADS, args)
        self.assertIn(key, args)

    def test_presign_export_result(self):
        client = mock.Mock()
        client.generate_presigned_url.return_value = 'https://minio/exports/x'
        with mock.patch.object(storage, 'get_minio_client',
                               return_value=client):
            url = storage.presign_export_result('exports/7/abc.xlsx',
                                                expires=900)
        self.assertEqual(url, 'https://minio/exports/x')
        _, kwargs = client.generate_presigned_url.call_args
        self.assertEqual(kwargs['ExpiresIn'], 900)

    def test_presign_none_key_returns_none(self):
        self.assertIsNone(storage.presign_export_result(''))

    def test_presign_swallows_errors(self):
        client = mock.Mock()
        client.generate_presigned_url.side_effect = RuntimeError('minio down')
        with mock.patch.object(storage, 'get_minio_client',
                               return_value=client):
            self.assertIsNone(
                storage.presign_export_result('exports/7/abc.xlsx'))
