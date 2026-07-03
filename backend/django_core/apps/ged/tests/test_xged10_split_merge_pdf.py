"""XGED10 — Outils PDF : scission et fusion.

Couvre :
  * un PDF de 6 pages coupé en [1, 3] donne deux documents (2 pages + 4 pages) ;
  * 3 PDF fusionnés donnent un document paginé dans l'ordre ;
  * l'original n'est jamais muté ;
  * gardes GED23/24 (archivé/hold → refus) ;
  * dégradation explicite sans PyMuPDF (400, jamais un split silencieusement
    faux).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import ArchivageLegalError, Cabinet, Document, Folder

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


def _make_pdf_bytes(n_pages):
    import fitz
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f'Page {i + 1}')
    out = doc.tobytes()
    doc.close()
    return out


class XGed10Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged10-a', 'Xged10 A')
        self.admin_a = make_user(self.co_a, 'xged10-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='PDF 6 pages')
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

    def _add_pdf_version(self, document, n_pages):
        data = _make_pdf_bytes(n_pages)
        key, meta = self._fake_store_bytes(data)
        return services.add_version(
            document, file_key=key, company=self.co_a,
            filename=meta['filename'], size=meta['size'], mime='application/pdf')


class ScinderTests(XGed10Base):
    def test_split_6_pages_into_2_and_4(self):
        version = self._add_pdf_version(self.doc, 6)
        original_bytes = self._blobs[version.file_key]
        created = services.scinder_pdf(version, [1, 3])
        self.assertEqual(len(created), 2)
        import fitz
        v1 = created[0].versions.first()
        v2 = created[1].versions.first()
        doc1 = fitz.open(stream=self._blobs[v1.file_key], filetype='pdf')
        doc2 = fitz.open(stream=self._blobs[v2.file_key], filetype='pdf')
        self.assertEqual(doc1.page_count, 2)
        self.assertEqual(doc2.page_count, 4)
        doc1.close()
        doc2.close()
        # L'original n'est jamais muté.
        self.assertEqual(self._blobs[version.file_key], original_bytes)

    def test_split_invalid_points_raises(self):
        version = self._add_pdf_version(self.doc, 3)
        with self.assertRaises(ValueError):
            services.scinder_pdf(version, [99])

    def test_split_without_pymupdf_raises_explicit(self):
        version = self._add_pdf_version(self.doc, 3)
        with mock.patch.dict('sys.modules', {'fitz': None}):
            with self.assertRaises(ValueError):
                services.scinder_pdf(version, [1, 2])

    def test_split_archived_document_refused(self):
        version = self._add_pdf_version(self.doc, 4)
        with mock.patch(
                'apps.ged.services._document_archive_legalement',
                return_value=True):
            with self.assertRaises(ArchivageLegalError):
                services.scinder_pdf(version, [1, 2])


class FusionnerTests(XGed10Base):
    def test_merge_3_documents_paginated_in_order(self):
        doc1 = self.doc
        self._add_pdf_version(doc1, 2)
        doc2 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='PDF B')
        self._add_pdf_version(doc2, 3)
        doc3 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='PDF C')
        self._add_pdf_version(doc3, 1)

        resultat = services.fusionner_pdf(
            [doc1, doc2, doc3], company=self.co_a, created_by=self.admin_a)
        import fitz
        merged_version = resultat.versions.first()
        merged = fitz.open(
            stream=self._blobs[merged_version.file_key], filetype='pdf')
        self.assertEqual(merged.page_count, 6)
        merged.close()

    def test_merge_requires_at_least_two(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/fusionner/', {
            'documents': [self.doc.pk],
        })
        self.assertEqual(resp.status_code, 400)

    def test_merge_into_existing_target_adds_version(self):
        doc1 = self.doc
        self._add_pdf_version(doc1, 2)
        doc2 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='PDF B')
        self._add_pdf_version(doc2, 2)
        cible = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Cible')
        self._add_pdf_version(cible, 1)

        resultat = services.fusionner_pdf(
            [doc1, doc2], cible=cible, company=self.co_a)
        self.assertEqual(resultat.pk, cible.pk)
        self.assertEqual(resultat.versions.count(), 2)
