"""ADOC8 — un fichier GED importé n'est jamais servi en HTML inline.

Rejoue les sondes #14/#54 de l'audit documents (2026-10-05) : un ZIP
contenant `p.html` (avec un script) importé en masse donnait une version
mime=text/html servie `inline` sans CSP — y compris par le lien public.
"""
import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'
HTML = b'<html><body><script>alert("j6")</script></body></html>'
PDF = b'%PDF-1.4\n%%EOF'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for nom, octets in entries.items():
            zf.writestr(nom, octets)
    return buf.getvalue()


def _minio():
    """Seul le stockage objet est simulé (aucun MinIO en test)."""
    client = mock.MagicMock()
    return mock.patch.multiple(
        'apps.ventes.utils.minio_client',
        get_minio_client=mock.MagicMock(return_value=client),
        ensure_uploads_bucket=mock.MagicMock())


class HtmlInlineTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc8', defaults={'nom': 'ADOC8'})[0]
        self.admin = User.objects.create_user(
            username='adoc8-admin', password='x', company=self.co,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')

    def _importer_html(self):
        with _minio():
            res = services.importer_en_masse(
                company=self.co, folder=self.folder,
                lignes=[{'nom': 'X', 'fichier': 'p.html'}],
                zip_bytes=_zip({'p.html': HTML}), created_by=self.admin)
        self.assertEqual(res['crees'], 1, res['erreurs'])
        return DocumentVersion.objects.get(document=res['documents'][0])

    def _assert_jamais_inline(self, resp):
        self.assertTrue(resp['Content-Disposition'].startswith('attachment'))
        self.assertEqual(resp['Content-Security-Policy'], 'sandbox')
        self.assertEqual(resp['X-Content-Type-Options'], 'nosniff')

    def test_import_masse_html_jamais_inline(self):
        version = self._importer_html()
        version.refresh_from_db()
        self.assertEqual(version.mime, 'application/octet-stream')
        api = auth(self.admin)
        for _ in range(2):
            with mock.patch('apps.ged.views.fetch_attachment',
                            return_value=(HTML, None)):
                resp = api.get(f'{BASE}versions/{version.pk}/apercu/')
            self.assertEqual(resp.status_code, 200)
            self._assert_jamais_inline(resp)
        # Une version HÉRITÉE déjà stockée en text/html n'est plus inline.
        DocumentVersion.objects.filter(pk=version.pk).update(mime='text/html')
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(HTML, None)):
            resp = api.get(f'{BASE}versions/{version.pk}/apercu/')
        self._assert_jamais_inline(resp)

    def test_lien_public_html_attachment(self):
        version = self._importer_html()
        DocumentVersion.objects.filter(pk=version.pk).update(mime='text/html')
        partage = services.create_partage(
            document=version.document, company=self.co, created_by=self.admin)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(HTML, None)):
            resp = APIClient().get(f'{BASE}public/{partage.token}/')
        self.assertEqual(resp.status_code, 200)
        self._assert_jamais_inline(resp)

    @override_settings(GED_OFFICE_URL='https://office.example.test')
    def test_office_mime_detecte(self):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='edit')
        upload = SimpleUploadedFile('p.html', HTML, content_type='text/html')
        with _minio():
            resp = auth(self.admin).post(
                f'{BASE}documents/{doc.pk}/office-sauvegarder/',
                {'file': upload}, format='multipart')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        version = DocumentVersion.objects.filter(document=doc).get()
        self.assertEqual(version.mime, 'application/octet-stream')
        # PATCH du mime ignoré (lecture seule).
        auth(self.admin).patch(f'{BASE}versions/{version.pk}/',
                               {'mime': 'text/html'}, format='json')
        version.refresh_from_db()
        self.assertEqual(version.mime, 'application/octet-stream')

    def test_pdf_reste_inline_avec_csp(self):
        with _minio():
            res = services.importer_en_masse(
                company=self.co, folder=self.folder,
                lignes=[{'nom': 'P', 'fichier': 'p.pdf'}],
                zip_bytes=_zip({'p.pdf': PDF}), created_by=self.admin)
        version = DocumentVersion.objects.get(document=res['documents'][0])
        self.assertEqual(version.mime, 'application/pdf')
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(PDF, None)):
            resp = auth(self.admin).get(f'{BASE}versions/{version.pk}/apercu/')
        self.assertTrue(resp['Content-Disposition'].startswith('inline'))
        self.assertEqual(resp['Content-Security-Policy'], 'sandbox')
