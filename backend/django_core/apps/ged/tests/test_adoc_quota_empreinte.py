"""ADOC23 — empreinte et taille réelles à chaque dépôt ; quota appliqué par
add_version sur toutes les routes ; dépôt public contrôlé AVANT stockage.

Constats #21/#22/#66 de l'audit documents (2026-10-05) : televerser
enregistrait checksum='' ; import-masse passait (201) au-delà du quota ; le
dépôt public stockait puis créait (201) alors que l'upload interne → 403.
"""
import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, DocumentVersion, Folder, QuotaStockage,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'
PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _store(file, company=None, **kwargs):
    return ({'file_key': 'attachments/x.pdf', 'filename': file.name,
             'size': 1, 'mime': 'application/pdf'}, None)


class QuotaEmpreinteTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc23', defaults={'nom': 'ADOC23'})[0]
        self.resp = User.objects.create_user(
            username='adoc23-resp', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        self.existant = Document.objects.create(
            company=self.co, folder=self.folder, nom='existant')
        DocumentVersion.objects.create(
            company=self.co, document=self.existant, version=1,
            file_key='attachments/e.pdf', size=10)

    def test_televerser_checksum_64hex(self):
        upload = SimpleUploadedFile('a.pdf', PDF,
                                    content_type='application/pdf')
        with mock.patch('apps.ged.views.store_attachment', side_effect=_store):
            resp = auth(self.resp).post(
                f'{BASE}documents/televerser/',
                {'folder': self.folder.pk, 'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.content)
        version = DocumentVersion.objects.get(document_id=resp.data['id'])
        self.assertEqual(len(version.checksum), 64)
        self.assertEqual(version.checksum, services.compute_checksum(PDF))
        self.assertEqual(version.size, len(PDF))

    def test_import_masse_quota_403(self):
        QuotaStockage.objects.create(company=self.co, quota_octets=1)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('p.pdf', PDF)
        csv = SimpleUploadedFile('m.csv', b'nom,fichier\nX,p.pdf\n',
                                 content_type='text/csv')
        zip_file = SimpleUploadedFile('l.zip', buf.getvalue(),
                                      content_type='application/zip')
        avant = Document.objects.count()
        with mock.patch('apps.ged.services._store_bytes',
                        return_value=('attachments/p.pdf',
                                      {'filename': 'p.pdf', 'size': len(PDF),
                                       'mime': 'application/pdf'})):
            resp = auth(self.resp).post(
                f'{BASE}documents/import-masse/',
                {'folder': self.folder.pk, 'csv': csv, 'zip': zip_file},
                format='multipart')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(Document.objects.count(), avant)
        # POST /versions/ (fichier téléversé, ASEC37) : même garde.
        fichier = SimpleUploadedFile('k.pdf', PDF,
                                     content_type='application/pdf')
        resp = auth(self.resp).post(
            f'{BASE}versions/',
            {'document': self.existant.pk, 'file': fichier},
            format='multipart')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(self.existant.versions.count(), 1)

    def test_depot_public_quota_avant_stockage(self):
        QuotaStockage.objects.create(company=self.co, quota_octets=1)
        depot = services.create_depot_public(
            folder=self.folder, company=self.co)
        upload = SimpleUploadedFile('p.pdf', PDF,
                                    content_type='application/pdf')
        avant = Document.objects.count()
        with mock.patch('apps.ged.views.store_attachment',
                        side_effect=_store) as stockage:
            resp = APIClient().post(f'{BASE}depot/{depot.token}/',
                                    {'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn('Quota', resp.data['detail'])
        self.assertEqual(stockage.call_count, 0)
        self.assertEqual(Document.objects.count(), avant)
