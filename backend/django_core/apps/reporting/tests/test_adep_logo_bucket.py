"""ADEP40 — le logo des rapports PDF est lu là où Paramètres l'écrit.

`parametres/views_uploads.py` téléverse le logo dans
``settings.MINIO_BUCKET_UPLOADS`` ; `report_pdf._logo_data_uri` le cherchait
dans un bucket ``erp-media`` que rien ne crée (NoSuchBucket → logo absent).
Client MinIO simulé à la frontière S3 : le logo n'existe QUE dans le bucket
d'upload ; le vrai `_logo_data_uri` est exercé.

Test-du-test : remettre ``'erp-media'`` dans `_logo_data_uri` ⇒ rouge.
"""
import base64
import io
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.reporting import report_pdf

LOGO_KEY = 'logos/1/logo.png'
LOGO_BYTES = b'\x89PNG\r\n\x1a\nfaux-logo'


class _NoSuchBucket(Exception):
    pass


class _FakeS3:
    """Seul le bucket d'upload contient le logo, comme en prod."""

    def __init__(self, buckets):
        self.buckets = buckets
        self.calls = []

    def get_object(self, Bucket, Key):
        self.calls.append(Bucket)
        if Bucket not in self.buckets:
            raise _NoSuchBucket(f'NoSuchBucket: {Bucket}')
        return {'Body': io.BytesIO(self.buckets[Bucket][Key])}


@override_settings(MINIO_BUCKET_UPLOADS='erp-uploads')
class LogoBucketTests(SimpleTestCase):
    def _client(self):
        return _FakeS3({'erp-uploads': {LOGO_KEY: LOGO_BYTES}})

    def test_logo_lu_dans_le_bucket_d_upload(self):
        fake = self._client()
        with mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                        return_value=fake):
            uri = report_pdf._logo_data_uri(LOGO_KEY)
        self.assertEqual(fake.calls, ['erp-uploads'])
        self.assertEqual(
            uri, 'data:image/png;base64,' + base64.b64encode(LOGO_BYTES).decode())

    def test_reexport_garde_le_logo(self):
        # CLAUSE PERSISTANCE : ré-exporter le même rapport → logo présent.
        fake = self._client()
        with mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                        return_value=fake):
            premier = report_pdf._logo_data_uri(LOGO_KEY)
            second = report_pdf._logo_data_uri(LOGO_KEY)
        self.assertIsNotNone(premier)
        self.assertEqual(premier, second)
