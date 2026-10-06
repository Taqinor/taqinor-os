"""ADOC61 — D-ADOC-2 : un document client régénéré = NOUVELLE VERSION du même
Document GED (historique gardé), via ``services.versionner_si_modifie``.

Source réelle : l'événement ``core.events.document_produit`` (émis en prod par
``ventes/utils/pdf.py``) est envoyé tel quel ; le récepteur GED réel route le
fichier ; stockage MinIO de test réel (``records.storage.store_attachment``),
aucun mock de source interne.
"""
import hashlib
import json
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.management.commands import publier_documents_meryem as cmd
from apps.ged.models import (
    Cabinet, Document, DocumentVersion, LegalHold, RoutageDocumentaire,
)
from core.events import document_produit

User = get_user_model()

OCTETS_A = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n' + b'A' * 200
OCTETS_B = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n' + b'B' * 200


def _fichier(octets, name='FAC-1.pdf'):
    buf = BytesIO(octets)
    buf.name = name
    buf.size = len(octets)
    buf.seek(0)
    return buf


def _sha(octets):
    return hashlib.sha256(octets).hexdigest()


class RoutageVersionneBase(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc61-a', defaults={'nom': 'Adoc61 A'})
        self.admin = User.objects.create_user(
            username='adoc61-admin', password='x', company=self.co_a,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co_a, nom='Ventes')
        RoutageDocumentaire.objects.create(
            company=self.co_a, source='ventes_facture',
            cabinet_cible=self.cab, dossier_cible='Factures/{{ annee }}')

    def _emettre(self, octets, reference='FAC-1'):
        document_produit.send(
            sender=None, source='ventes_facture', company=self.co_a,
            file=_fichier(octets), filename='FAC-1.pdf', reference=reference,
            contexte={'annee': 2026}, uploaded_by=self.admin)

    def _docs(self):
        return Document.objects.filter(
            company=self.co_a, custom_data__routage_reference='FAC-1')

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        return api


class RoutageVersionneTests(RoutageVersionneBase):
    def test_regeneration_contenu_different_ajoute_une_version(self):
        self._emettre(OCTETS_A)
        self._emettre(OCTETS_B)
        self._emettre(OCTETS_A)

        self.assertEqual(self._docs().count(), 1)
        document = self._docs().get()
        versions = list(document.versions.order_by('version'))
        self.assertEqual([v.version for v in versions], [1, 2, 3])
        # Checksum renseigné dès la version 1.
        self.assertEqual(versions[0].checksum, _sha(OCTETS_A))
        self.assertEqual(versions[1].checksum, _sha(OCTETS_B))
        en_vigueur = document.versions.order_by('-version').first()
        self.assertEqual(en_vigueur.checksum, _sha(OCTETS_A))

        # Persistance relue par l'API : 3 versions, la v3 en vigueur.
        api = self._api()
        resp = api.get(f'/api/django/ged/documents/{document.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['version_count'], 3)
        self.assertEqual(resp.data['derniere_version'], 3)
        # Rouvrir = même version en vigueur.
        resp2 = api.get(f'/api/django/ged/documents/{document.pk}/')
        self.assertEqual(resp2.data['derniere_version'], 3)

    def test_regeneration_identique_ne_cree_rien(self):
        self._emettre(OCTETS_A)
        self._emettre(OCTETS_B)
        self._emettre(OCTETS_B)
        document = self._docs().get()
        self.assertEqual(document.versions.count(), 2)
        self.assertEqual(
            document.versions.order_by('-version').first().checksum,
            _sha(OCTETS_B))

    def test_document_en_corbeille_jamais_versionne(self):
        self._emettre(OCTETS_A)
        premier = self._docs().get()
        services.mettre_en_corbeille(premier, self.admin)
        self._emettre(OCTETS_B)

        premier.refresh_from_db()
        self.assertIsNotNone(premier.supprime_le)
        self.assertEqual(premier.versions.count(), 1)
        visibles = self._docs().filter(supprime_le__isnull=True)
        self.assertEqual(visibles.count(), 1)
        nouveau = visibles.get()
        self.assertNotEqual(nouveau.pk, premier.pk)
        self.assertEqual(
            nouveau.versions.get().checksum, _sha(OCTETS_B))

    def test_legal_hold_refuse_sans_500(self):
        self._emettre(OCTETS_A)
        document = self._docs().get()
        LegalHold.objects.create(
            company=self.co_a, document=document, motif='litige')
        # Ne lève jamais (receveur best-effort) ; aucune version ajoutée.
        version, cree = services.versionner_si_modifie(document, OCTETS_B)
        self.assertIsNone(version)
        self.assertFalse(cree)
        self._emettre(OCTETS_B)
        self.assertEqual(document.versions.count(), 1)

    def test_deposit_document_versionner_opt_in(self):
        doc, cree = services.deposit_document(
            company=self.co_a, nom='Pack', source_type='adoc61.pack',
            source_id=1, contenu_bytes=OCTETS_A, mime='application/pdf',
            versionner_si_modifie=True)
        self.assertTrue(cree)
        doc2, cree2 = services.deposit_document(
            company=self.co_a, nom='Pack', source_type='adoc61.pack',
            source_id=1, contenu_bytes=OCTETS_B, mime='application/pdf',
            versionner_si_modifie=True)
        self.assertFalse(cree2)
        self.assertEqual(doc.pk, doc2.pk)
        self.assertEqual(doc.versions.count(), 2)
        # Défaut inchangé : idempotent sans nouvelle version.
        services.deposit_document(
            company=self.co_a, nom='Pack', source_type='adoc61.pack',
            source_id=1, contenu_bytes=OCTETS_A, mime='application/pdf')
        self.assertEqual(doc.versions.count(), 2)


class MeryemCorbeilleTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='adoc61-meryem', defaults={'nom': 'Adoc61 Meryem'})
        self.admin = User.objects.create_user(
            username='adoc61-meryem-admin', password='x',
            company=self.company, role_legacy='admin')
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        patcher = mock.patch.object(cmd, 'MERYEM_DOCS_DIR', self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _ecrire(self, contenu):
        (self.dir / cmd.MANIFEST_NOM).write_text(json.dumps([
            {'fichier': 'guide.pdf', 'titre': 'Guide ADOC61',
             'version': '1', 'description': ''}]), encoding='utf-8')
        (self.dir / 'guide.pdf').write_bytes(contenu)

    def test_meryem_ignore_un_document_en_corbeille(self):
        self._ecrire(b'%PDF-1.4 guide v1')
        cmd.publier_documents(self.company, stdout=StringIO())
        premier = Document.objects.get(
            company=self.company, nom='Guide ADOC61')
        services.mettre_en_corbeille(premier, self.admin)

        self._ecrire(b'%PDF-1.4 guide v2')
        cmd.publier_documents(self.company, stdout=StringIO())

        premier.refresh_from_db()
        self.assertEqual(premier.versions.count(), 1)
        visibles = Document.objects.filter(
            company=self.company, nom='Guide ADOC61',
            supprime_le__isnull=True)
        self.assertEqual(visibles.count(), 1)
        self.assertNotEqual(visibles.get().pk, premier.pk)
        self.assertEqual(
            DocumentVersion.objects.filter(document=visibles.get()).get()
            .checksum, _sha(b'%PDF-1.4 guide v2'))
