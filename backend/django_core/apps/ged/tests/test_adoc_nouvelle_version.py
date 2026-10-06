"""ADOC18 — geste « Nouvelle version » (multipart) dans la GED (D-ADOC-2).

Rejoue la sonde #12 de l'audit documents (2026-10-05) : POST /ged/versions/
multipart {document, file} → 400 {'file_key': obligatoire}, versions=1 —
aucun geste écran ne permettait d'ajouter une version.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder
from authentication.models import Company

User = get_user_model()
PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _store(file, company=None, **kwargs):
    return ({'file_key': f'attachments/{company.pk}/v.pdf',
             'filename': file.name, 'size': file.size,
             'mime': 'application/pdf'}, None)


class NouvelleVersionTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc18', defaults={'nom': 'ADOC18'})[0]
        self.resp = User.objects.create_user(
            username='adoc18-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.autre = User.objects.create_user(
            username='adoc18-autre', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=folder, nom='D')
        self.v1 = services.add_version(
            self.doc, file_key='attachments/d1.pdf', company=self.co,
            filename='d1.pdf', uploaded_by=self.resp)
        self.url = f'/api/django/ged/documents/{self.doc.pk}/nouvelle-version/'

    def _post(self, user):
        upload = SimpleUploadedFile('d-v2.pdf', PDF,
                                    content_type='application/pdf')
        with mock.patch('apps.ged.views.store_attachment', side_effect=_store):
            return auth(user).post(self.url, {'file': upload},
                                   format='multipart')

    def test_multipart_cree_v2(self):
        resp = self._post(self.resp)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['version'], 2)
        v2 = DocumentVersion.objects.get(pk=resp.data['id'])
        self.assertEqual(v2.uploaded_by_id, self.resp.pk)
        self.assertEqual(v2.size, len(PDF))
        self.assertEqual(v2.checksum, services.compute_checksum(PDF))
        liste = auth(self.resp).get(
            f'/api/django/ged/versions/?document={self.doc.pk}')
        data = liste.data['results'] if isinstance(liste.data, dict) \
            else liste.data
        self.assertEqual(sorted(v['version'] for v in data), [1, 2])

    def test_checkout_409(self):
        services.checkout_document(self.doc, self.resp)
        resp = self._post(self.autre)
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(self.doc.versions.count(), 1)

    def test_archive_403(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            services.archiver_legalement(self.doc, user=self.resp)
        resp = self._post(self.resp)
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(self.doc.versions.count(), 1)
