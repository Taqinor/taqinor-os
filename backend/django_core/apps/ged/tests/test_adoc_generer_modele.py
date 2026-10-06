"""ADOC13 — générer depuis un modèle rend le contexte saisi (D-ADOC-2).

Rejoue la sonde #9 de l'audit documents (2026-10-05) : ALPHA puis BRAVO
donnaient le MÊME document (created=False au 2e), une seule version, et le
PDF disait « Attestation ALPHA » pour BRAVO.
"""
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged.models import Document, DocumentVersion, ModeleDocument
from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class GenererModeleTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc13', defaults={'nom': 'ADOC13'})[0]
        self.admin = User.objects.create_user(
            username='adoc13-admin', password='x', company=self.co,
            role_legacy='admin')
        self.modele = ModeleDocument.objects.create(
            company=self.co, nom='Attestation',
            corps_html='<p>Attestation {{ nom }}</p>')
        self._blobs = {}
        patcher = mock.patch('apps.ged.services._store_bytes',
                             side_effect=self._store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.url = f'/api/django/ged/modeles-document/{self.modele.pk}/generer/'

    def _store(self, data, *, mime='application/pdf'):
        key = f'attachments/{uuid.uuid4().hex}.pdf'
        self._blobs[key] = data
        return key, {'filename': key, 'size': len(data),
                     'mime': 'application/pdf'}

    def _texte(self, document):
        import fitz
        version = document.versions.order_by('-version').first()
        pdf = fitz.open(stream=self._blobs[version.file_key], filetype='pdf')
        try:
            return ' '.join(page.get_text() for page in pdf)
        finally:
            pdf.close()

    def _generer(self, nom):
        resp = auth(self.admin).post(
            self.url, {'contexte': {'nom': nom}}, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        return resp

    def test_contextes_differents_deux_documents(self):
        r1 = self._generer('ALPHA')
        r2 = self._generer('BRAVO')
        self.assertTrue(r1.data['created'])
        self.assertTrue(r2.data['created'])
        self.assertNotEqual(r1.data['document'], r2.data['document'])
        alpha = Document.objects.get(pk=r1.data['document'])
        bravo = Document.objects.get(pk=r2.data['document'])
        self.assertIn('Attestation ALPHA', self._texte(alpha))
        self.assertIn('Attestation BRAVO', self._texte(bravo))
        # Même contexte, modèle inchangé : même document, aucune version.
        r3 = self._generer('ALPHA')
        self.assertFalse(r3.data['created'])
        self.assertEqual(r3.data['document'], alpha.pk)
        self.assertEqual(alpha.versions.count(), 1)

    def test_modele_corrige_nouvelle_version(self):
        r1 = self._generer('ALPHA')
        self.modele.corps_html = '<p>Attestation corrigée {{ nom }}</p>'
        self.modele.save()
        r2 = self._generer('ALPHA')
        self.assertFalse(r2.data['created'])
        self.assertEqual(r2.data['document'], r1.data['document'])
        alpha = Document.objects.get(pk=r1.data['document'])
        self.assertEqual(
            sorted(DocumentVersion.objects.filter(document=alpha)
                   .values_list('version', flat=True)), [1, 2])
        self.assertIn('corrigée ALPHA', self._texte(alpha))
        self.assertEqual(
            Document.objects.filter(
                custom_data__contains={'source_type': 'ged.modeledocument'}
            ).count(), 1)
