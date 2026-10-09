"""ADOC74 — l'avoir, la note de débit et le bordereau de remise émettent
``core.events.document_produit`` après le stockage de leur PDF, comme la
facture (WIR165) : un ``RoutageDocumentaire`` configuré les classe en GED.

Oracle de la sonde COUTURE #79 : avant le correctif, « facture(témoin)=1,
avoir=0, note_debit=0, remise=0 ; événements émis = ['ventes_facture'] ».

Source réelle : générateurs ``apps.ventes.utils.pdf`` (rendu WeasyPrint
réel), événement ``core.events.document_produit`` réel, receveur GED réel
(``apps/ged/receivers.py``) et stockage ``records.storage`` réel. Seul
l'upload MinIO du PDF métier (``_upload_pdf``) et le téléchargement du logo
sont neutralisés, comme dans ``test_aud156_cle_pdf_scopee``.
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ged.models import Cabinet, Document, DocumentVersion, RoutageDocumentaire
from apps.ventes.models import Avoir, Facture, NoteDebit, RemiseEncaissement
from authentication.models import Company
from core.events import document_produit

User = get_user_model()

SOURCES = {
    'ventes_facture': 'Factures',
    'ventes_avoir': 'Avoirs',
    'ventes_note_debit': 'Notes de debit',
    'ventes_remise': 'Remises',
}


@patch('apps.ventes.utils.pdf._upload_pdf')
@patch('apps.ventes.utils.pdf._download', return_value=None)
class AdocDocumentProduitTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='adoc74-a', defaults={'nom': 'Adoc74 A'})
        self.user = User.objects.create_user(
            username='adoc74-admin', password='x', company=self.co,
            role_legacy='admin')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Bennani', prenom='Sara',
            telephone='+212600000074')
        self.facture = Facture.objects.create(
            company=self.co, client=self.client_obj,
            reference='FAC-202610-0001', statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), created_by=self.user)
        self.avoir = Avoir.objects.create(
            company=self.co, client=self.client_obj, facture=self.facture,
            reference='AV-202610-0001', taux_tva=Decimal('20'),
            created_by=self.user)
        self.note = NoteDebit.objects.create(
            company=self.co, client=self.client_obj, facture=self.facture,
            reference='ND-202610-0001', taux_tva=Decimal('20'),
            created_by=self.user)
        self.remise = RemiseEncaissement.objects.create(
            company=self.co, technicien=self.user, reference='REM-202610-0001',
            date_collecte=datetime.date(2026, 10, 8),
            montant_declare=Decimal('0'), created_by=self.user)
        self.emis = []
        document_produit.connect(self._capter, dispatch_uid='adoc74-capte')
        self.addCleanup(
            document_produit.disconnect, dispatch_uid='adoc74-capte')

    def _capter(self, sender, **kwargs):
        self.emis.append((kwargs.get('source'), kwargs.get('reference')))

    def _router(self):
        cab = Cabinet.objects.create(company=self.co, nom='Ventes')
        for source, dossier in SOURCES.items():
            RoutageDocumentaire.objects.update_or_create(
                company=self.co, source=source,
                defaults={'cabinet_cible': cab,
                          'dossier_cible': dossier + '/{{ annee }}'})

    def _docs(self, reference):
        return Document.objects.filter(
            company=self.co, custom_data__routage_reference=reference)

    def _generer_tout(self):
        from apps.ventes.utils.pdf import (
            generate_avoir_pdf, generate_bordereau_remise_pdf,
            generate_facture_pdf, generate_note_debit_pdf,
        )
        generate_facture_pdf(self.facture.id)
        generate_avoir_pdf(self.avoir.id)
        generate_note_debit_pdf(self.note.id)
        generate_bordereau_remise_pdf(self.remise.id)

    def test_avoir_note_debit_remise_archives_en_ged(self, _dl, _up):
        self._router()
        self._generer_tout()

        self.assertIn(('ventes_facture', 'FAC-202610-0001'), self.emis)
        # Une assertion par source : retirer l'émission d'un seul générateur
        # fait échouer la sienne.
        self.assertIn(('ventes_avoir', 'AV-202610-0001'), self.emis)
        self.assertIn(('ventes_note_debit', 'ND-202610-0001'), self.emis)
        self.assertIn(('ventes_remise', 'REM-202610-0001'), self.emis)

        self.assertEqual(self._docs('FAC-202610-0001').count(), 1)
        self.assertEqual(self._docs('AV-202610-0001').count(), 1)
        self.assertEqual(self._docs('ND-202610-0001').count(), 1)
        self.assertEqual(self._docs('REM-202610-0001').count(), 1)

        # Persistance : fichier_pdf des pièces inchangé (clé métier).
        self.avoir.refresh_from_db()
        self.note.refresh_from_db()
        self.remise.refresh_from_db()
        self.assertEqual(
            self.avoir.fichier_pdf, f'avoirs/{self.co.id}/AV-202610-0001.pdf')
        self.assertEqual(
            self.note.fichier_pdf,
            f'notes-debit/{self.co.id}/ND-202610-0001.pdf')
        self.assertEqual(
            self.remise.fichier_pdf,
            f'remises-encaissement/{self.co.id}/REM-202610-0001.pdf')

    def test_regeneration_avoir_ajoute_une_version(self, _dl, _up):
        from apps.ventes.utils.pdf import generate_avoir_pdf
        self._router()
        generate_avoir_pdf(self.avoir.id)
        Avoir.objects.filter(pk=self.avoir.pk).update(
            motif='Remise commerciale accordée')
        generate_avoir_pdf(self.avoir.id)

        docs = self._docs('AV-202610-0001')
        self.assertEqual(docs.count(), 1)
        self.assertEqual(
            DocumentVersion.objects.filter(document=docs.get()).count(), 2)

    def test_sans_routage_no_op(self, _dl, _up):
        # ADOC75 : routages par défaut semés à la création de la société.
        RoutageDocumentaire.objects.filter(company=self.co).delete()
        self._generer_tout()
        self.assertFalse(Document.objects.filter(company=self.co).exists())
        self.avoir.refresh_from_db()
        self.assertTrue(self.avoir.fichier_pdf)

    def test_emission_best_effort(self, _dl, _up):
        """Une exception à l'émission est journalisée ; le PDF reste stocké."""
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        self._router()
        with patch('core.events.document_produit.send',
                   side_effect=RuntimeError('boom')):
            with self.assertLogs('apps.ventes.utils.pdf', level='ERROR'):
                cle = generate_note_debit_pdf(self.note.id)
        self.note.refresh_from_db()
        self.assertEqual(self.note.fichier_pdf, cle)
