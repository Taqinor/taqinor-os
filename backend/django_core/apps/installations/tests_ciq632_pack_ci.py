"""CIQ632 — pack de remise C&I : as-built réel (révisé APRÈS la pose),
pièces C&I, certificat d'organisme agréé et assurance exigés en accord de
raccordement (décret 2.25.100 art. 15), phrase « arrêt sur coupure ».
"""
import datetime
from unittest.mock import patch

from django.test import TestCase

from apps.installations.models import (
    DocumentProjet, Installation, RevisionDocument,
)
from apps.installations.services import (
    PHRASE_ARRET_COUPURE, assemble_handover_pieces,
)
from authentication.models import Company

POSE = datetime.date(2026, 9, 1)


class PackRemiseCITests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ632', slug='ciq632-co')
        self._n = 0

    def _chantier(self, regime='declaration_bt', type_installation='industriel',
                  bom=None):
        self._n += 10
        return Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ632-{self._n}',
            type_installation=type_installation, regime_8221=regime,
            date_pose_reelle=POSE, bom=bom or [])

    def _doc(self, chantier, type_doc, revision=None):
        doc = DocumentProjet.objects.create(
            company=self.company, installation=chantier, type_doc=type_doc,
            titre=type_doc)
        if revision is not None:
            RevisionDocument.objects.create(
                company=self.company, document=doc, date_revision=revision)
        return doc

    def _piece(self, chantier, code):
        pieces = assemble_handover_pieces(chantier)['pieces']
        return next(p for p in pieces if p['type'] == code)

    def test_pointeur_du_devis_seul_as_built_absent(self):
        chantier = self._chantier()
        self._doc(chantier, 'schema_unifilaire')  # pointeur, sans révision
        self.assertFalse(self._piece(chantier, 'as_built')['present'])

    def test_revision_avant_la_pose_ne_compte_pas(self):
        chantier = self._chantier()
        self._doc(chantier, 'schema_unifilaire',
                  revision=POSE - datetime.timedelta(days=3))
        self.assertFalse(self._piece(chantier, 'as_built')['present'])

    def test_schema_depose_apres_la_pose_present(self):
        chantier = self._chantier()
        self._doc(chantier, 'plan_chaines',
                  revision=POSE + datetime.timedelta(days=2))
        self.assertTrue(self._piece(chantier, 'as_built')['present'])

    def test_accord_sans_assurance_pack_incomplet(self):
        chantier = self._chantier(regime='accord_raccordement')
        self._doc(chantier, 'certificat_organisme_agree')
        piece = self._piece(chantier, 'attestation_assurance')
        self.assertTrue(piece['obligatoire'])
        self.assertFalse(piece['present'])
        self.assertIn('art. 15', piece['source'])
        self.assertFalse(assemble_handover_pieces(chantier)['complet'])

    def test_accord_sans_certificat_pack_incomplet(self):
        chantier = self._chantier(regime='accord_raccordement')
        self._doc(chantier, 'attestation_assurance')
        piece = self._piece(chantier, 'certificat_organisme_agree')
        self.assertTrue(piece['obligatoire'])
        self.assertFalse(piece['present'])

    def test_declaration_pieces_exploitation_facultatives(self):
        chantier = self._chantier(regime='declaration_bt')
        self.assertFalse(
            self._piece(chantier, 'attestation_assurance')['obligatoire'])
        self.assertFalse(self._piece(chantier, 'manuel_om')['obligatoire'])

    def test_residentiel_inchange(self):
        chantier = self._chantier(type_installation='residentiel')
        self._doc(chantier, 'schema_unifilaire')
        pieces = assemble_handover_pieces(chantier)['pieces']
        self.assertTrue(self._piece(chantier, 'as_built')['present'])
        self.assertNotIn('manuel_om', [p['type'] for p in pieces])


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class PhraseArretCoupureTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ632b', slug='ciq632-b')

    def _html(self, mock_pdf, chantier):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        builders.generate_dossier_remise(chantier)
        return mock_pdf.call_args[0][0]

    def _chantier(self, ref, bom, type_installation='industriel'):
        return Installation.objects.create(
            company=self.company, reference=ref,
            type_installation=type_installation,
            regime_8221='declaration_bt', bom=bom)

    def test_phrase_presente_sans_batterie(self, mock_pdf, _dl):
        chantier = self._chantier('CHT-CIQ632-B1', [
            {'designation': 'Onduleur réseau 50 kW', 'quantite': 1}])
        html = self._html(mock_pdf, chantier)
        self.assertIn(PHRASE_ARRET_COUPURE.replace("'", '&#x27;'), html)

    def test_phrase_absente_avec_batterie(self, mock_pdf, _dl):
        chantier = self._chantier('CHT-CIQ632-B2', [
            {'designation': 'Batterie lithium 10 kWh', 'quantite': 2}])
        html = self._html(mock_pdf, chantier)
        self.assertNotIn('coupure du réseau', html)

    def test_phrase_absente_en_residentiel(self, mock_pdf, _dl):
        chantier = self._chantier('CHT-CIQ632-B3', [],
                                  type_installation='residentiel')
        html = self._html(mock_pdf, chantier)
        self.assertNotIn('coupure du réseau', html)
