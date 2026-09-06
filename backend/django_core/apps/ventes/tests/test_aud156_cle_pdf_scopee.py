"""AUD156 — clé MinIO des PDF facture/avoir/note de débit scopée SOCIÉTÉ.

``Facture.Meta`` déclare ``unique_together = [('company','reference')]`` et la
numérotation est PAR SOCIÉTÉ + période : deux sociétés produisent légitimement
la même référence ``FAC-YYYYMM-NNNN``. Or la clé de stockage ne contenait que
la référence pour les trois documents de facturation — le MÊME fichier corrige
pourtant explicitement ce défaut pour le devis (ERR75) et pour le bordereau.

Scénario : deux sociétés émettent ``FAC-202609-0001`` le même mois ; la seconde
écrase le PDF de la première, et le client de A télécharge la facture de B.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Avoir, Facture, NoteDebit
from authentication.models import Company

User = get_user_model()
_CTR = [0]
REFERENCE = 'FAC-202609-0001'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestClePdfScopeeSociete(TestCase):
    def setUp(self):
        self.a = Company.objects.create(
            nom='AUD156 A', slug=f'aud156a-{_nxt()}')
        self.b = Company.objects.create(
            nom='AUD156 B', slug=f'aud156b-{_nxt()}')
        self.client_a = Client.objects.create(
            company=self.a, nom='A', prenom='Client',
            telephone='+212600000156')
        self.client_b = Client.objects.create(
            company=self.b, nom='B', prenom='Client',
            telephone='+212600000157')

    def _facture(self, company, client_obj, reference=REFERENCE):
        return Facture.objects.create(
            company=company, client=client_obj, reference=reference,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_deux_societes_meme_reference_deux_objets_distincts(
            self, _dl, _up):
        """ROUGE avant le correctif : une seule et même clé pour les deux."""
        from apps.ventes.utils.pdf import generate_facture_pdf
        cle_a = generate_facture_pdf(
            self._facture(self.a, self.client_a).id)
        cle_b = generate_facture_pdf(
            self._facture(self.b, self.client_b).id)
        self.assertNotEqual(cle_a, cle_b)
        self.assertEqual(cle_a, f'factures/{self.a.id}/{REFERENCE}.pdf')
        self.assertEqual(cle_b, f'factures/{self.b.id}/{REFERENCE}.pdf')

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_avoir_scope_societe(self, _dl, _up):
        from apps.ventes.utils.pdf import generate_avoir_pdf
        facture = self._facture(self.a, self.client_a, 'FAC-202609-0009')
        avoir = Avoir.objects.create(
            company=self.a, client=self.client_a, facture=facture,
            reference='AV-202609-0001', taux_tva=Decimal('20'))
        cle = generate_avoir_pdf(avoir.id)
        self.assertEqual(cle, f'avoirs/{self.a.id}/AV-202609-0001.pdf')

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_note_debit_scope_societe(self, _dl, _up):
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        facture = self._facture(self.a, self.client_a, 'FAC-202609-0010')
        note = NoteDebit.objects.create(
            company=self.a, client=self.client_a, facture=facture,
            reference='ND-202609-0001', taux_tva=Decimal('20'))
        cle = generate_note_debit_pdf(note.id)
        self.assertEqual(cle, f'notes-debit/{self.a.id}/ND-202609-0001.pdf')

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_repli_lecture_ancienne_cle_puis_migration(self, _dl, _up):
        """Un PDF stocké sous l'ANCIENNE clé reste lisible tel quel, puis
        migre vers la clé scopée à la première régénération."""
        from apps.ventes.utils.pdf import (
            cle_facture_pdf_a_jour, empreinte_donnees_facture_pdf)
        facture = self._facture(self.a, self.client_a, 'FAC-202609-0011')
        ancienne = f'factures/{facture.reference}.pdf'
        facture.fichier_pdf = ancienne
        facture.pdf_render_meta = {
            'empreinte': empreinte_donnees_facture_pdf(facture)}
        facture.save(update_fields=['fichier_pdf', 'pdf_render_meta'])

        # Empreinte à jour → l'ancienne clé est servie telle quelle (repli).
        self.assertEqual(cle_facture_pdf_a_jour(facture), ancienne)

        # Les données changent → régénération sous la clé SCOPÉE.
        facture.taux_tva = Decimal('10')
        facture.save(update_fields=['taux_tva'])
        facture.refresh_from_db()
        nouvelle = cle_facture_pdf_a_jour(facture)
        self.assertEqual(
            nouvelle, f'factures/{self.a.id}/{facture.reference}.pdf')
