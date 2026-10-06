"""ADOC11 — caviarder refuse les zones hors page / vides et la copie ne fuit
ni le texte masqué ni les métadonnées d'origine.

Rejoue la sonde #7 de l'audit documents (2026-10-05) : une zone page=9 sur un
PDF de 2 pages → 201, copie « (caviardé) » au texte intact ; zone vide → 201.
"""
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder
from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _pdf_deux_pages():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 200), 'SECRET-J6', fontsize=24)
    doc.new_page()
    doc.set_metadata({'author': 'Auteur Origine', 'title': 'Titre Origine'})
    out = doc.tobytes()
    doc.close()
    return out


class CaviardageTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc11', defaults={'nom': 'ADOC11'})[0]
        self.admin = User.objects.create_user(
            username='adoc11-admin', password='x', company=self.co,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=folder, nom='a-caviarder')
        self._blobs = {}
        p1 = mock.patch('apps.ged.services._store_bytes',
                        side_effect=self._store)
        p2 = mock.patch('apps.ged.services._fetch_version_bytes',
                        side_effect=lambda v: (self._blobs.get(v.file_key, b''),
                                               None))
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        key, _ = self._store(_pdf_deux_pages())
        self.version = services.add_version(
            self.doc, file_key=key, company=self.co, filename='a.pdf',
            mime='application/pdf')
        self.url = f'/api/django/ged/documents/{self.doc.pk}/caviarder/'

    def _store(self, data, *, mime='application/pdf'):
        key = f'attachments/{uuid.uuid4().hex}.pdf'
        self._blobs[key] = data
        return key, {'filename': key, 'size': len(data), 'mime': mime}

    def test_zone_hors_page_400(self):
        avant = Document.objects.count()
        resp = auth(self.admin).post(self.url, {'zones': [
            {'page': 9, 'x0': 0, 'y0': 0, 'x1': 100, 'y1': 100}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('hors page (page 9 / 2 pages)', resp.data['detail'])
        self.assertEqual(Document.objects.count(), avant)

    def test_zone_vide_400(self):
        avant = Document.objects.count()
        resp = auth(self.admin).post(self.url, {'zones': [
            {'page': 0, 'x0': 0, 'y0': 0, 'x1': 0, 'y1': 0}]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('vide', resp.data['detail'])
        self.assertEqual(Document.objects.count(), avant)

    def test_texte_retire(self):
        import fitz
        resp = auth(self.admin).post(self.url, {'zones': [
            {'page': 0, 'x0': 0, 'y0': 0, 'x1': 100, 'y1': 100}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        copie = Document.objects.get(pk=resp.data['id'])
        self.assertEqual(copie.nom, 'a-caviarder (caviardé)')
        octets = self._blobs[copie.versions.first().file_key]
        self.assertNotIn(b'SECRET-J6', octets)
        lu = fitz.open(stream=octets, filetype='pdf')
        try:
            self.assertNotIn('SECRET-J6', lu[0].get_text())
            meta = lu.metadata or {}
            self.assertFalse(meta.get('author'))
            self.assertFalse(meta.get('title'))
        finally:
            lu.close()

    def test_nombre_de_pages(self):
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(self._blobs[self.version.file_key],
                                      None)):
            resp = auth(self.admin).get(
                f'/api/django/ged/versions/{self.version.pk}/pages/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['pages'], 2)
