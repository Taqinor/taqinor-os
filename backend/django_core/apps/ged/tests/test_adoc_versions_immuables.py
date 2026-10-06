"""ADOC17 — historique des versions immuable, check-out respecté, comparateur
honnête.

Constats #17/#18/#20 de l'audit documents (2026-10-05) : PATCH d'une version
→ 200 ; restaurer malgré le check-out d'autrui → 201 ; comparer → diff_texte
[] avec texte_disponible=True (le texte OCR est celui du DOCUMENT).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _pdf():
    import fitz
    doc = fitz.open()
    doc.new_page()
    out = doc.tobytes()
    doc.close()
    return out


class VersionsImmuablesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc17', defaults={'nom': 'ADOC17'})[0]
        self.u1 = User.objects.create_user(
            username='adoc17-u1', password='x', company=self.co,
            role_legacy='responsable')
        self.u2 = User.objects.create_user(
            username='adoc17-u2', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='D',
            texte_ocr='Ligne 1\nLigne 2')
        self.v1 = services.add_version(
            self.doc, file_key='attachments/d1.pdf', company=self.co,
            filename='d1.pdf', uploaded_by=self.u1)
        self.v2 = services.add_version(
            self.doc, file_key='attachments/d2.pdf', company=self.co,
            filename='d2.pdf', uploaded_by=self.u1)
        self.autre = Document.objects.create(
            company=self.co, folder=self.folder, nom='Autre')

    def test_patch_version_405(self):
        api = auth(self.u2)
        url = f'{BASE}versions/{self.v1.pk}/'
        for corps in ({'file_key': 'attachments/x.pdf'},
                      {'document': self.autre.pk}):
            self.assertEqual(api.patch(url, corps, format='json').status_code,
                             405)
        self.assertEqual(api.put(url, {
            'document': self.doc.pk, 'file_key': 'attachments/x.pdf'},
            format='json').status_code, 405)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.file_key, 'attachments/d1.pdf')
        self.assertEqual(self.v1.document_id, self.doc.pk)

    def test_restaurer_respecte_checkout_409(self):
        services.checkout_document(self.doc, self.u1)
        resp = auth(self.u2).post(
            f'{BASE}documents/{self.doc.pk}/restaurer/',
            {'version': self.v1.pk}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(self.doc.versions.count(), 2)
        # Le détenteur du verrou restaure toujours.
        resp = auth(self.u1).post(
            f'{BASE}documents/{self.doc.pk}/restaurer/',
            {'version': self.v1.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_fusion_cible_respecte_checkout_409(self):
        a = Document.objects.create(company=self.co, folder=self.folder,
                                    nom='A')
        b = Document.objects.create(company=self.co, folder=self.folder,
                                    nom='B')
        for doc in (a, b):
            services.add_version(doc, file_key=f'attachments/{doc.nom}.pdf',
                                 company=self.co, uploaded_by=self.u2)
        services.checkout_document(self.doc, self.u1)
        octets = _pdf()
        with mock.patch('apps.ged.services._fetch_version_bytes',
                        return_value=(octets, None)), \
                mock.patch('apps.ged.services._store_bytes',
                           return_value=('attachments/f.pdf',
                                         {'filename': 'f.pdf',
                                          'size': len(octets),
                                          'mime': 'application/pdf'})):
            resp = auth(self.u2).post(f'{BASE}documents/fusionner/', {
                'documents': [a.pk, b.pk], 'cible': self.doc.pk},
                format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(self.doc.versions.count(), 2)

    def test_comparateur_honnete(self):
        resp = auth(self.u2).get(
            f'{BASE}documents/{self.doc.pk}/comparer/'
            f'?v1={self.v1.pk}&v2={self.v2.pk}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['texte_disponible'])
        self.assertNotIn('custom_data', resp.data['metadonnees'])
        self.assertIn('filename', resp.data['metadonnees'])
        self.assertEqual(
            DocumentVersion.objects.filter(document=self.doc).count(), 2)
