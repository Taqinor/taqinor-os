"""ADOC134 — « Mes documents » sert la version en vigueur et sa date.

Constat (C-ADOC-050) : la ligne portail ne disait ni quelle version le client
téléchargeait ni de quand elle datait (D-ADOC-2 : un document régénéré est
une NOUVELLE VERSION du même document, le portail montre celle en vigueur).
Contrat : ``mes_documents.json`` (ADOC111).

Run :
    python manage.py test apps.portail.tests.test_adoc_mes_documents_version -v2
"""
import itertools
import json
import pathlib

from django.test import TestCase
from rest_framework.test import APIClient
from testkit.time import frozen

from apps.crm.models import Client
from apps.ged.models import AclGed, Cabinet, Document, DocumentVersion, Folder
from apps.portail.services import provisionner_compte_portail_client
from authentication.models import Company

_seq = itertools.count(1)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'mes_documents.json')
    .read_text(encoding='utf-8'))

RACINE = '/api/django/portail/mes-documents/'


class MesDocumentsVersionTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc134-{n}', defaults={'nom': f'ADOC134 {n}'})
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client', prenom=f'ADOC134-{n}',
            email=f'adoc134-{n}@example.invalid')
        admin, _ = provisionner_compte_portail_client(
            self.co, self.client_crm.id)
        admin.must_change_password = False
        admin.save(update_fields=['must_change_password'])
        cabinet = Cabinet.objects.create(company=self.co, nom=f'Cab-{n}')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cabinet, nom=f'Dossier-{n}')
        with frozen('2026-08-15 08:00:00'):
            self.doc = Document.objects.create(
                company=self.co, folder=self.folder, nom='Facture ONEE')
        AclGed.objects.create(
            company=self.co, document=self.doc, client=self.client_crm)
        self._version(1, '2026-09-01 10:00:00')
        self.v2 = self._version(2, '2026-09-20 11:20:00')
        self.api = APIClient()
        self.api.force_authenticate(user=admin)

    def _version(self, numero, quand, document=None):
        document = document or self.doc
        with frozen(quand):
            return DocumentVersion.objects.create(
                company=self.co, document=document, version=numero,
                file_key=f'ged/{self.co.id}/{document.id}-v{numero}.pdf',
                filename=f'v{numero}.pdf', size=100 * numero,
                mime='application/pdf')

    def test_ligne_conforme_contrat(self):
        self.assertEqual(CONTRAT['forme_serveur'], 'complete')
        cles = set(CONTRAT['exemple']['results'][0])
        liste = self.api.get(RACINE)
        self.assertEqual(liste.status_code, 200, liste.content)
        ligne = liste.json()['results'][0]
        self.assertEqual(set(ligne), cles)
        self.assertEqual(ligne['version_numero'], 2)
        self.assertEqual(ligne['version_date'], self.v2.created_at.isoformat())
        # La date de la VERSION, jamais celle du document.
        self.assertNotEqual(ligne['version_date'], ligne['date_creation'])
        self.assertEqual(ligne['taille'], 200)

        detail = self.api.get(f'{RACINE}{self.doc.id}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(set(detail.json()), cles)
        self.assertEqual(detail.json()['version_numero'], 2)

        # Persistance : une v3 côté GED, relue au portail.
        v3 = self._version(3, '2026-10-01 09:00:00')
        ligne = self.api.get(RACINE).json()['results'][0]
        self.assertEqual(ligne['version_numero'], 3)
        self.assertEqual(ligne['version_date'], v3.created_at.isoformat())

    def test_document_sans_version_null(self):
        nu = Document.objects.create(
            company=self.co, folder=self.folder, nom='Plan de toiture')
        AclGed.objects.create(
            company=self.co, document=nu, client=self.client_crm)
        res = self.api.get(f'{RACINE}{nu.id}/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(set(res.json()),
                         set(CONTRAT['exemple_sans_version']['results'][0]))
        self.assertIsNone(res.json()['version_numero'])
        self.assertIsNone(res.json()['version_date'])
