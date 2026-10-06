"""ADOC25 — le post-dépôt (règles de dossier + demandes de pièces) tourne
sur TOUTES les routes de dépôt, pas seulement `televerser`.

Constat #34 de l'audit documents (2026-10-05) : scan-lot, import-masse et
dépôt public ne posaient aucun tag et ne journalisaient aucune
ExecutionRegleDossier.
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
    Cabinet, DemandeDocument, Document, DocumentTag, ExecutionRegleDossier,
    Folder, RegleDossier,
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
    return ({'file_key': f'attachments/{file.name}', 'filename': file.name,
             'size': file.size, 'mime': 'application/pdf'}, None)


class ApresDepotTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc25', defaults={'nom': 'ADOC25'})[0]
        self.resp = User.objects.create_user(
            username='adoc25-resp', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='F')
        self.tag = DocumentTag.objects.create(
            company=self.co, nom='Facture', slug='facture')
        RegleDossier.objects.create(
            company=self.co, folder=self.folder, nom='Tout → Facture',
            condition_group={'op': 'and', 'conditions': [
                {'field': 'nom', 'operator': 'contains', 'value': 'scan'}]},
            actions=[{'type': 'tag', 'params': {'tag': 'facture'}}])

    def _assert_regle_appliquee(self, document):
        self.assertTrue(document.tag_assignments.filter(tag=self.tag).exists())
        self.assertTrue(ExecutionRegleDossier.objects.filter(
            document=document, declenchee=True).exists())

    def test_scan_lot_applique_regles(self):
        demande = services.creer_demande_document(
            folder=self.folder, company=self.co, libelle='scan',
            created_by=self.resp)
        upload = SimpleUploadedFile('scan-1.pdf', PDF,
                                    content_type='application/pdf')
        with mock.patch('apps.ged.views.store_attachment', side_effect=_store):
            resp = auth(self.resp).post(
                f'{BASE}documents/scan-lot/',
                {'folder': self.folder.pk, 'files': [upload]},
                format='multipart')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        document = Document.objects.get(folder=self.folder, nom__icontains='scan')
        self._assert_regle_appliquee(document)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'soldee')
        self.assertEqual(demande.document_id, document.pk)

    def test_import_masse_applique_regles(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('p.pdf', PDF)
        with mock.patch('apps.ged.services._store_bytes',
                        return_value=('attachments/p.pdf',
                                      {'filename': 'p.pdf', 'size': len(PDF),
                                       'mime': 'application/pdf'})):
            res = services.importer_en_masse(
                company=self.co, folder=self.folder,
                lignes=[{'nom': 'scan importé', 'fichier': 'p.pdf'}],
                zip_bytes=buf.getvalue(), created_by=self.resp)
        self.assertEqual(res['crees'], 1, res['erreurs'])
        self._assert_regle_appliquee(res['documents'][0])

    def test_depot_public_applique_regles(self):
        depot = services.create_depot_public(
            folder=self.folder, company=self.co)
        document = services.deposer_via_lien_public(
            depot, file_key='attachments/x.pdf', filename='scan-public.pdf',
            size=len(PDF), mime='application/pdf')
        self._assert_regle_appliquee(document)
        self.assertFalse(DemandeDocument.objects.exists())
