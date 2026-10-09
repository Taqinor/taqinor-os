"""APDF27 (C-APDF-009) — l'avoir et la note de débit impriment le bloc
client entreprise de la facture (raison sociale + ICE, IF, RC quand
renseignés ; rien pour un particulier sans identifiant).

Rejoue la sonde PFAC-2 (AVOIR et NOTE DEBIT : ICE/IF/RC absents, facture
présents). Vrais ``generate_avoir_pdf`` / ``generate_note_debit_pdf`` (rendu
réel) ; seul l'upload MinIO est neutralisé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_client_entreprise_rectificatifs"
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class ClientEntrepriseRectificatifsTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(nom='APDF27', slug='apdf27-co')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _client(self, **kw):
        from apps.crm.models import Client
        return Client.objects.create(
            company=self.company, email=f'apdf27-{_nxt()}@example.invalid',
            **kw)

    def _facture(self, client):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-APDF27-{_nxt()}',
            client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))

    def _avoir_pdf(self, client):
        from apps.ventes.models import Avoir, LigneAvoir
        from apps.ventes.utils.pdf import generate_avoir_pdf
        facture = self._facture(client)
        avoir = Avoir.objects.create(
            company=self.company, reference=f'AVO-APDF27-{_nxt()}',
            facture=facture, client=client, statut=Avoir.Statut.EMISE,
            taux_tva=Decimal('20'))
        LigneAvoir.objects.create(
            avoir=avoir, designation='Geste', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), remise=Decimal('0'))
        return _texte(self.objets[generate_avoir_pdf(avoir.id)])

    def _nd_pdf(self, client):
        from apps.ventes.models import LigneNoteDebit, NoteDebit
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        facture = self._facture(client)
        nd = NoteDebit.objects.create(
            company=self.company, reference=f'ND-APDF27-{_nxt()}',
            facture=facture, client=client, statut=NoteDebit.Statut.EMISE,
            taux_tva=Decimal('20'))
        LigneNoteDebit.objects.create(
            note_debit=nd, designation='Complément', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), taux_tva=Decimal('20'))
        return _texte(self.objets[generate_note_debit_pdf(nd.id)])

    def _entreprise(self):
        return self._client(
            nom='Atlas Agro SARL', type_client='entreprise',
            ice='ICECLI000777', if_fiscal='IFCLI55', rc='RCCLI99')

    def test_avoir_ice_if_rc(self):
        texte = self._avoir_pdf(self._entreprise())
        for valeur in ('ICECLI000777', 'IFCLI55', 'RCCLI99'):
            self.assertIn(valeur, texte)

    def test_nd_ice_if_rc(self):
        texte = self._nd_pdf(self._entreprise())
        for valeur in ('ICECLI000777', 'IFCLI55', 'RCCLI99'):
            self.assertIn(valeur, texte)

    def test_particulier_rien(self):
        particulier = self._client(
            nom='Alaoui', prenom='Sara', type_client='particulier')
        for texte in (self._avoir_pdf(particulier),
                      self._nd_pdf(particulier)):
            for libelle in ('ICE :', 'IF :', 'RC :'):
                self.assertNotIn(libelle, texte)
