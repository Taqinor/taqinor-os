"""ADOC10 — POST /ged/versions/ ajoute TOUJOURS la version au document demandé.

Rejoue la sonde #19 de l'audit documents (2026-10-05) : POST /versions/
{document: B, checksum de A (coffre d'autrui)} répondait 200 avec la version
de A (et sa file_key) ; les versions de B restaient à 1.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, Coffre, Document, DocumentVersion, Folder,
)
from authentication.models import Company

User = get_user_model()
URL = '/api/django/ged/versions/'


def _octets(contenu):
    return b'%PDF-1.4 ' + contenu


def _empreinte(contenu):
    return services.compute_checksum(_octets(contenu))


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VersionsDedupTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc10', defaults={'nom': 'ADOC10'})[0]
        self.u1 = User.objects.create_user(
            username='adoc10-u1', password='x', company=self.co,
            role_legacy='responsable')
        self.u2 = User.objects.create_user(
            username='adoc10-u2', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        coffre = Coffre.objects.create(
            company=self.co, nom='Coffre U1', proprietaire=self.u1)
        self.doc_a = Document.objects.create(
            company=self.co, folder=folder, coffre=coffre, nom='A')
        # ASEC37 — l'empreinte est calculée par le serveur sur les octets
        # téléversés : les versions de référence portent l'empreinte RÉELLE
        # de contenus connus.
        self.va = services.add_version(
            self.doc_a, file_key='attachments/secret-a.pdf', company=self.co,
            checksum=_empreinte(b'C'), uploaded_by=self.u1)
        self.doc_b = Document.objects.create(
            company=self.co, folder=folder, nom='B')
        services.add_version(
            self.doc_b, file_key='attachments/b1.pdf', company=self.co,
            checksum=_empreinte(b'C1'), uploaded_by=self.u2)
        services.add_version(
            self.doc_b, file_key='attachments/b2.pdf', company=self.co,
            checksum=_empreinte(b'C2'), uploaded_by=self.u2)

    def _versions_b(self):
        return DocumentVersion.objects.filter(document=self.doc_b).count()

    def _post(self, nom, contenu):
        # ASEC37 — la version arrive comme fichier téléversé (multipart).
        return auth(self.u2).post(URL, {
            'document': self.doc_b.pk,
            'file': SimpleUploadedFile(
                nom, _octets(contenu), content_type='application/pdf')},
            format='multipart')

    def test_checksum_autre_document_cree_version(self):
        self.assertEqual(self._versions_b(), 2)
        resp = self._post('k2.pdf', b'C')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['document'], self.doc_b.pk)
        self.assertNotEqual(resp.data['id'], self.va.pk)
        self.assertNotIn('secret-a', str(resp.content))
        self.assertEqual(self._versions_b(), 3)
        self.assertEqual(
            DocumentVersion.objects.filter(document=self.doc_a).count(), 1)

    def test_retour_arriere_cree_version(self):
        resp = self._post('k3.pdf', b'C1')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['version'], 3)
        self.assertEqual(self._versions_b(), 3)

    def test_doublon_derniere_version_200(self):
        resp = self._post('k4.pdf', b'C2')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['version'], 2)
        self.assertEqual(resp.data['document'], self.doc_b.pk)
        self.assertEqual(self._versions_b(), 2)
