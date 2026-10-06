"""ADOC3 — les objets rattachés à un document suivent SA visibilité.

Rejoue la sonde #2 de l'audit documents (2026-10-05) : un document du coffre
d'un collègue répondait 404 sur GET /documents/<id>/ mais sa version restait
listée (/versions/?document=) et son binaire servi (/versions/<id>/apercu/) ;
idem pour un document en corbeille et l'export annoté.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import (
    AnnotationDocument, Cabinet, Coffre, DemandeApprobation, Document,
    DocumentTag, DocumentTagAssignment, DocumentVersion, Folder,
    ValidationOcrDocument,
)

User = get_user_model()
BASE = '/api/django/ged/'
PDF = b'%PDF-1.4\n%%EOF'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def lignes(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class VersionsVisibiliteTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc3', defaults={'nom': 'ADOC3'})[0]
        self.admin = User.objects.create_user(
            username='adoc3-admin', password='x', company=self.co,
            role_legacy='admin')
        self.emp1 = User.objects.create_user(
            username='adoc3-emp1', password='x', company=self.co,
            role_legacy='normal')
        self.emp2 = User.objects.create_user(
            username='adoc3-emp2', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        coffre = Coffre.objects.create(
            company=self.co, nom='Coffre emp1', proprietaire=self.emp1)
        self.doc = Document.objects.create(
            company=self.co, folder=folder, coffre=coffre, nom='Paie emp1')
        self.version = DocumentVersion.objects.create(
            company=self.co, document=self.doc, version=1,
            file_key='attachments/paie.pdf', filename='paie.pdf',
            size=len(PDF), mime='application/pdf')
        AnnotationDocument.objects.create(
            company=self.co, version=self.version, type_annotation='note',
            contenu='note')
        ValidationOcrDocument.objects.create(
            company=self.co, document=self.doc, score_confiance=0.4)
        DemandeApprobation.objects.create(
            company=self.co, document=self.doc, demandeur=self.emp1)
        tag = DocumentTag.objects.create(company=self.co, nom='RH')
        DocumentTagAssignment.objects.create(
            company=self.co, document=self.doc, tag=tag)
        # Document T en corbeille.
        self.doc_t = Document.objects.create(
            company=self.co, folder=folder, nom='Jeté')
        self.version_t = DocumentVersion.objects.create(
            company=self.co, document=self.doc_t, version=1,
            file_key='attachments/t.pdf', filename='t.pdf', size=len(PDF),
            mime='application/pdf')
        from django.utils import timezone
        Document.objects.filter(pk=self.doc_t.pk).update(
            supprime_le=timezone.now())

    def _apercu(self, api, version):
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(PDF, None)):
            return api.get(f'{BASE}versions/{version.pk}/apercu/')

    def test_liste_versions_coffre_vide(self):
        api = auth(self.emp2)
        self.assertEqual(
            api.get(f'{BASE}documents/{self.doc.pk}/').status_code, 404)
        resp = api.get(f'{BASE}versions/?document={self.doc.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(lignes(resp)), 0)
        for url in (f'annotations/?version={self.version.pk}',
                    'validations-ocr/',
                    f'demandes-approbation/?document={self.doc.pk}',
                    f'liens/?document={self.doc.pk}',
                    f'tag-assignments/?document={self.doc.pk}'):
            resp = api.get(BASE + url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertEqual(len(lignes(resp)), 0, url)

    def test_apercu_coffre_404(self):
        self.assertEqual(self._apercu(auth(self.emp2), self.version).status_code,
                         404)

    def test_export_annote_coffre_404(self):
        with mock.patch('apps.ged.services._fetch_version_bytes',
                        return_value=(PDF, None)):
            # L'export est réservé aux responsables : un responsable SANS
            # accès au coffre d'emp1 doit recevoir 404 (pas le fichier).
            resp_user = User.objects.create_user(
                username='adoc3-resp', password='x', company=self.co,
                role_legacy='responsable')
            resp = auth(resp_user).get(
                f'{BASE}annotations/export-annote/?version={self.version.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_corbeille_404(self):
        api = auth(self.emp2)
        resp = api.get(f'{BASE}versions/?document={self.doc_t.pk}')
        self.assertEqual(len(lignes(resp)), 0)
        self.assertEqual(self._apercu(api, self.version_t).status_code, 404)

    def test_proprietaire_200(self):
        for user in (self.emp1, self.admin):
            api = auth(user)
            resp = api.get(f'{BASE}versions/?document={self.doc.pk}')
            self.assertEqual(len(lignes(resp)), 1, user.username)
            self.assertEqual(self._apercu(api, self.version).status_code, 200)
            resp = api.get(f'{BASE}annotations/?version={self.version.pk}')
            self.assertEqual(len(lignes(resp)), 1)
            resp = api.get(f'{BASE}validations-ocr/')
            self.assertEqual(len(lignes(resp)), 1)
