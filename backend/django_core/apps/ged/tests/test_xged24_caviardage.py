"""XGED24 — Outil de caviardage (redaction).

Couvre :
  * la copie caviardée ne contient plus le texte masqué (extraction vide sur
    la zone) ;
  * l'original reste inchangé (byte-identique) ;
  * sans PyMuPDF → 400 explicite (ValueError) ;
  * la copie devient un nouveau document lié à l'original (custom_data) ;
  * document-lien (XGED18) refuse le caviardage.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _make_pdf_with_text(text, at=(72, 200)):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(at, text, fontsize=24)
    out = doc.tobytes()
    doc.close()
    return out


class XGed24Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged24-a', 'Xged24 A')
        self.admin_a = make_user(self.co_a, 'xged24-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Fiche paie')
        self._store_patch = mock.patch(
            'apps.ged.services._store_bytes',
            side_effect=self._fake_store_bytes)
        self._store_patch.start()
        self._fetch_patch = mock.patch(
            'apps.ged.services._fetch_version_bytes',
            side_effect=self._fake_fetch_bytes)
        self._fetch_patch.start()
        self._blobs = {}
        self.addCleanup(self._store_patch.stop)
        self.addCleanup(self._fetch_patch.stop)

    def _fake_store_bytes(self, data, *, mime='application/pdf'):
        import uuid
        key = f'attachments/{uuid.uuid4().hex}.pdf'
        self._blobs[key] = data
        return key, {'filename': key, 'size': len(data), 'mime': mime}

    def _fake_fetch_bytes(self, version):
        return self._blobs.get(version.file_key, b''), None

    def _add_pdf_version(self, document, text):
        data = _make_pdf_with_text(text)
        key, meta = self._fake_store_bytes(data)
        return services.add_version(
            document, file_key=key, company=self.co_a,
            filename=meta['filename'], size=meta['size'], mime='application/pdf')


class CaviarderServiceTests(XGed24Base):
    def test_zone_caviardee_supprime_le_texte(self):
        version = self._add_pdf_version(self.doc, 'CIN AB123456')
        original_bytes = self._blobs[version.file_key]
        # Zone couvrant toute la page (0-100%) — le texte doit disparaître.
        new_doc = services.caviarder_document(
            version, [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 100, 'y1': 100}],
            created_by=self.admin_a)
        import fitz
        new_version = new_doc.versions.first()
        redacted = fitz.open(
            stream=self._blobs[new_version.file_key], filetype='pdf')
        texte = redacted[0].get_text()
        redacted.close()
        self.assertNotIn('AB123456', texte)
        # L'original n'est jamais muté.
        self.assertEqual(self._blobs[version.file_key], original_bytes)

    def test_original_document_intact(self):
        version = self._add_pdf_version(self.doc, 'RIB 001234567890')
        new_doc = services.caviarder_document(
            version, [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 100, 'y1': 100}],
            created_by=self.admin_a)
        self.assertNotEqual(new_doc.pk, self.doc.pk)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.nom, 'Fiche paie')

    def test_copie_liee_a_original_via_custom_data(self):
        version = self._add_pdf_version(self.doc, 'secret')
        new_doc = services.caviarder_document(
            version, [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 100, 'y1': 100}],
            created_by=self.admin_a)
        self.assertEqual(new_doc.custom_data.get('caviarde_depuis'), self.doc.pk)

    def test_sans_zones_leve(self):
        version = self._add_pdf_version(self.doc, 'texte')
        with self.assertRaises(ValueError):
            services.caviarder_document(version, [], created_by=self.admin_a)

    def test_sans_pymupdf_leve_explicite(self):
        version = self._add_pdf_version(self.doc, 'texte')
        with mock.patch.dict('sys.modules', {'fitz': None}):
            with self.assertRaises(ValueError):
                services.caviarder_document(
                    version, [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 50, 'y1': 50}],
                    created_by=self.admin_a)

    def test_document_lien_refuse(self):
        lien = services.creer_document_lien(
            company=self.co_a, folder=self.folder_a, nom='Lien externe',
            url_externe='https://example.com/doc')
        with self.assertRaises(ValueError):
            services.caviarder_document(
                mock.Mock(document=lien),
                [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 50, 'y1': 50}],
                created_by=self.admin_a)


class CaviarderViewTests(XGed24Base):
    def test_endpoint_caviarder(self):
        version = self._add_pdf_version(self.doc, 'ABCDEF secret')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/caviarder/', {
                'version': version.pk,
                'zones': [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 100, 'y1': 100}],
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['id'], self.doc.pk)

    def test_endpoint_sans_pymupdf_400(self):
        version = self._add_pdf_version(self.doc, 'ABCDEF secret')
        api = auth(self.admin_a)
        with mock.patch.dict('sys.modules', {'fitz': None}):
            resp = api.post(
                f'/api/django/ged/documents/{self.doc.pk}/caviarder/', {
                    'version': version.pk,
                    'zones': [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 50,
                               'y1': 50}],
                }, format='json')
        self.assertEqual(resp.status_code, 400)
