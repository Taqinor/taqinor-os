"""ACAL237 — la pièce « Plan de pose » des dossiers est le plan de pose TERRAIN.

Constat C-ACAL-136 : la pièce ``plan_pose`` du dossier de fin de chantier
était rendue par ``rendre_planche_pdf`` (la planche cotée) — ni repères de
rangée, ni sens de pose, ni liste des chaînes ; le dossier technique n'avait
aucun plan de pose. Désormais les deux dossiers rendent
``planche.rendre_plan_pose_pdf`` (celui que sert ``plan-pose.pdf``) ; un plan
de pose refusé est SIGNALÉ (pièce facultative), jamais remplacé en silence
par la planche.

Le calepinage est simulé par les VRAIS écrivains (``calepinage_de_pose`` de
CAL211) ; WeasyPrint et PyMuPDF réels ; on compare le TEXTE extrait de la
pièce, jamais ses octets.

Run :
    python manage.py test apps.calepinage.tests.test_acal_plan_pose_dossier -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services import pack_technique
from apps.calepinage.services.pack_technique import (
    DOSSIER_FIN_CHANTIER, SPEC_PIECES, _rendre_pieces,
)

from .acal_livrables_helpers import exiger_bibliotheques_pdf, patch_materiel
from .test_cal173_empreinte import FauxCalepinage
from .test_cal211_plan_pose import calepinage_de_pose


def _texte(octets):
    import fitz

    document = fitz.open(stream=octets, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in document)
    finally:
        document.close()


class PlanDePoseDuDossierFinChantierTest(SimpleTestCase):
    def setUp(self):
        exiger_bibliotheques_pdf()
        self.calepinage = calepinage_de_pose()

    def test_piece_plan_pose_porte_les_reperes_de_rangee_et_les_chaines(self):
        rendus = pack_technique._rendus_dossier_fin_chantier(
            self.calepinage, None)
        with patch_materiel():
            texte = _texte(rendus['plan_pose']())
        self.assertIn('R1', texte)
        self.assertIn('Chaînes', texte)

    def test_plan_pose_refuse_devient_un_signalement(self):
        vide = FauxCalepinage(roof_layout={})
        rendus = pack_technique._rendus_dossier_fin_chantier(vide, None)
        with patch_materiel():
            pieces, signalements = _rendre_pieces(
                vide, company='societe-essai',
                rendus={'plan_pose': rendus['plan_pose']},
                spec=DOSSIER_FIN_CHANTIER)
        # Aucune planche substituée : la pièce manque, et le dossier le DIT.
        self.assertNotIn('plan_pose', [code for code, _l, _o, _p in pieces])
        signalement = next(s for s in signalements
                           if s.startswith('« Plan de pose »'))
        self.assertNotIn('aucun rendu disponible', signalement)


class PlanDePoseDuDossierTechniqueTest(SimpleTestCase):
    def test_dossier_technique_porte_le_plan_de_pose_terrain(self):
        exiger_bibliotheques_pdf()
        codes = [code for code, _l, _o in SPEC_PIECES]
        self.assertIn(('plan_pose', 'Plan de pose terrain', False),
                      SPEC_PIECES)
        # À sa place : après les plans dérivés, avant les rapports.
        self.assertEqual(codes.index('plan_pose'),
                         codes.index('plan_masse') + 1)
        calepinage = calepinage_de_pose()
        rendus = pack_technique._rendus(calepinage, None)
        with patch_materiel():
            texte = _texte(rendus['plan_pose']())
        self.assertIn('R1', texte)
        self.assertIn('Chaînes', texte)
