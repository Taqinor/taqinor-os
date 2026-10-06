"""ADOC142 — l'export « mes données » sert le même contenu que « Télécharger ».

Constat (C-ADOC-045, plausible — oracle = ce test) : ``exporter_mes_donnees``
écrivait dans le zip les octets BRUTS de la version (``fetch_attachment``),
alors que « Télécharger » applique le filigrane GED21 quand
``watermark_diffusion`` est posé : le client récupérait par l'export
l'original non filigrané. Correctif : ``contenu_diffusable(doc, company)``
sert les deux chemins.

Seul ``apps.records.storage.fetch_attachment`` (MinIO) est remplacé : il rend
le PDF de test ; le filigrane (``ged.services.apply_watermark``) est réel.

Run :
    python manage.py test apps.portail.tests.test_adoc_export_filigrane -v2
"""
import io
import itertools
import re
import zipfile
from unittest.mock import patch

import pymupdf  # PyMuPDF — dépendance dure (requirements.txt)
from django.test import TestCase
from rest_framework.test import APIClient
from testkit.time import frozen

from apps.crm.models import Client
from apps.ged.models import AclGed, Cabinet, Document, DocumentVersion, Folder
from apps.portail.services import provisionner_compte_portail_client
from authentication.models import Company

_seq = itertools.count(1)


def _pdf_une_page():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), 'Facture ONEE')
    return pdf.tobytes()


ORIGINAL = _pdf_une_page()

#: PyMuPDF régénère l'identifiant de fichier (``/ID [<…><…>]`` du trailer) à
#: CHAQUE sérialisation : deux rendus du même filigrane ne diffèrent QUE par
#: lui. On le neutralise pour comparer le contenu octet par octet.
_ID_PDF = re.compile(rb'/ID\s*\[\s*<[0-9A-Fa-f]*>\s*<[0-9A-Fa-f]*>\s*\]')


def _sans_id(octets):
    return _ID_PDF.sub(b'', octets)


class ExportFiligraneTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc142-{n}', defaults={'nom': f'ADOC142 {n}'})
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client', prenom=f'ADOC142-{n}',
            email=f'adoc142-{n}@example.invalid')
        admin, _ = provisionner_compte_portail_client(
            self.co, self.client_crm.id)
        admin.must_change_password = False
        admin.save(update_fields=['must_change_password'])
        cabinet = Cabinet.objects.create(company=self.co, nom=f'Cab-{n}')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cabinet, nom=f'Dossier-{n}')
        self.api = APIClient()
        self.api.force_authenticate(user=admin)

    def _document(self, nom, filigrane):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom=nom,
            watermark_diffusion=filigrane)
        DocumentVersion.objects.create(
            company=self.co, document=doc, version=1,
            file_key=f'ged/{self.co.id}/{doc.id}.pdf', filename=nom,
            size=len(ORIGINAL), mime='application/pdf')
        AclGed.objects.create(
            company=self.co, document=doc, client=self.client_crm)
        return doc

    def _telecharger_et_exporter(self, doc, nom):
        # Horloge gelée : l'étiquette du filigrane porte la date du jour.
        with frozen('2026-10-06 10:00:00'), patch(
                'apps.records.storage.fetch_attachment',
                return_value=(ORIGINAL, None)):
            telecharge = self.api.get(
                f'/api/django/portail/mes-documents/{doc.id}/telecharger/')
            export = self.api.get(
                '/api/django/portail/client/mes-donnees/export/')
        self.assertEqual(telecharge.status_code, 200, telecharge.content)
        self.assertEqual(export.status_code, 200, export.content)
        with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
            dans_zip = archive.read(f'documents/{nom}')
        return telecharge.content, dans_zip

    def test_export_egal_telechargement(self):
        nom = 'facture-filigranee.pdf'
        doc = self._document(nom, filigrane=True)
        telecharge, dans_zip = self._telecharger_et_exporter(doc, nom)
        self.assertNotEqual(_sans_id(telecharge), _sans_id(ORIGINAL),
                            'le téléchargement doit être filigrané')
        self.assertIn('CONFIDENTIEL', pymupdf.open(
            stream=telecharge, filetype='pdf')[0].get_text())
        self.assertEqual(_sans_id(dans_zip), _sans_id(telecharge))
        self.assertNotEqual(_sans_id(dans_zip), _sans_id(ORIGINAL))

    def test_sans_filigrane_identique_a_l_original(self):
        nom = 'plan.pdf'
        doc = self._document(nom, filigrane=False)
        telecharge, dans_zip = self._telecharger_et_exporter(doc, nom)
        self.assertEqual(telecharge, ORIGINAL)
        self.assertEqual(dans_zip, ORIGINAL)
