"""CALX319 — le dossier de fin de chantier du calepinage.

Le Constat était vérifié : le pack de remise au CHANTIER existe déjà
(``apps.installations.services.assemble_handover_pieces`` : as-built/schéma,
fiches, garanties, recette IEC 62446-1, dossier 82-21, monitoring) et le pack
as-built de VENTES ne stocke que des RÉFÉRENCES
(``apps.ventes.models_commissioning.AsBuiltPack.pieces``, JSON) — mais AUCUNE
pièce PRODUITE PAR LE CALEPINAGE n'était fusionnée en un seul document.

Trois niveaux d'essais, comme CAL181 (``test_cal181_pack.py``) :

1. PUR — ``rendre_pieces`` avec ``spec=DOSSIER_FIN_CHANTIER`` et un
   ``rendus`` EXPLICITE (mêmes fabriques PyMuPDF que CAL181) : les cinq
   pièces se rendent et se comptent (``compter_pages``) ; une pièce
   facultative absente sort en SIGNALEMENT, jamais sautée en silence.
2. PUR — ``_rendus_dossier_fin_chantier`` déclare un rendu pour CHACUN des
   cinq codes de ``DOSSIER_FIN_CHANTIER`` (même garde que CALX309/CALX326
   pour ``_rendus``).
3. ORCHESTRATION (GED mockée, comme CAL181) — ``construire_dossier_fin_
   chantier`` dépose et fusionne LA MÊME mécanique que ``construire_pack``,
   dans un dossier GED DISTINCT, avec une ancre préfixée qui ne collisionne
   jamais avec le dossier technique ; ``MENTION_RECETTE_GARANTIES`` est
   TOUJOURS présente dans ``signalements`` — la recette et les garanties
   restent produites par le chantier, ce dossier ne les fabrique pas et le
   DIT plutôt que de le taire.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx319_dossier_fin_chantier -v2
"""
from unittest import mock, skipUnless

from django.test import SimpleTestCase

from apps.calepinage.services import pack_technique
from apps.calepinage.services.pack_technique import (
    CABINET, DOSSIER, DOSSIER_CHANTIER_GED, DOSSIER_FIN_CHANTIER,
    MENTION_RECETTE_GARANTIES, PackRefuse, construire_dossier_fin_chantier,
    rendre_pieces,
)

try:
    import fitz  # PyMuPDF
    _FITZ = True
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None
    _FITZ = False


def pdf_de(pages):
    """Un VRAI PDF de ``pages`` pages — même fabrique que CAL181."""
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    octets = document.tobytes()
    document.close()
    return octets


class FauxCalepinage:
    pk = 57
    titre = 'Ferme solaire — remise'
    layout_hash = 'b' * 64
    company = 'societe-essai'

    def __str__(self):
        return self.titre


CODES_DOSSIER_CHANTIER = ('plan_pose', 'document_asbuilt', 'plan_cablage',
                          'nomenclature', 'manuel_proprietaire')


class SpecDossierFinChantierTest(SimpleTestCase):
    """``DOSSIER_FIN_CHANTIER`` déclare les cinq pièces, TOUTES facultatives
    — la recette et les garanties ne conditionnent aucune d'entre elles."""

    def test_cinq_pieces_declarees_dans_l_ordre(self):
        self.assertEqual([code for code, _l, _o in DOSSIER_FIN_CHANTIER],
                         list(CODES_DOSSIER_CHANTIER))

    def test_les_cinq_pieces_sont_facultatives(self):
        for code, libelle, obligatoire in DOSSIER_FIN_CHANTIER:
            self.assertFalse(obligatoire,
                             '« %s » doit être facultative' % libelle)

    def test_le_dossier_ged_est_distinct_du_dossier_technique(self):
        self.assertNotEqual(DOSSIER_CHANTIER_GED, DOSSIER)


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class RenduDesCinqPiecesTest(SimpleTestCase):
    """``rendre_pieces`` sur ``spec=DOSSIER_FIN_CHANTIER`` — MÊME mécanique
    de contrôle de pages que CAL181, avec un ``rendus`` explicite."""

    def setUp(self):
        self.calepinage = FauxCalepinage()
        self.rendus = {
            'plan_pose': lambda: pdf_de(2),
            'document_asbuilt': lambda: pdf_de(1),
            'plan_cablage': lambda: pdf_de(1),
            'nomenclature': lambda: pdf_de(1),
            'manuel_proprietaire': lambda: pdf_de(3),
        }

    def test_les_cinq_pieces_sont_rendues_et_comptees(self):
        pieces, signalements = rendre_pieces(self.calepinage,
                                             company='societe-essai',
                                             rendus=self.rendus,
                                             spec=DOSSIER_FIN_CHANTIER)
        self.assertEqual([code for code, _l, _o, _p in pieces],
                         list(CODES_DOSSIER_CHANTIER))
        for _code, _libelle, octets, pages in pieces:
            self.assertEqual(pack_technique.compter_pages(octets), pages)
        self.assertEqual(sum(pages for _c, _l, _o, pages in pieces), 8)
        self.assertEqual(signalements, [])

    def test_une_piece_facultative_absente_est_signalee_jamais_sautee(self):
        rendus = dict(self.rendus)
        del rendus['document_asbuilt']
        pieces, signalements = rendre_pieces(self.calepinage,
                                             company='societe-essai',
                                             rendus=rendus,
                                             spec=DOSSIER_FIN_CHANTIER)
        self.assertEqual(
            [code for code, _l, _o, _p in pieces],
            ['plan_pose', 'plan_cablage', 'nomenclature',
             'manuel_proprietaire'])
        self.assertEqual(len(signalements), 1)
        self.assertIn('Document as-built', signalements[0])


class RendusDossierFinChantierDeclareLesCinqPiecesTest(SimpleTestCase):
    """Comme CALX309/CALX326 pour ``_rendus`` : ``_rendus_dossier_fin_
    chantier`` doit déclarer un rendu pour CHAQUE code de
    ``DOSSIER_FIN_CHANTIER`` — un écart y ramènerait la MÊME fuite
    silencieuse (une pièce déclarée sans rendu branché)."""

    def test_les_cinq_codes_ont_tous_un_rendu(self):
        rendus = pack_technique._rendus_dossier_fin_chantier(
            FauxCalepinage(), 'societe-essai')
        self.assertEqual(set(rendus), set(CODES_DOSSIER_CHANTIER))


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class OrchestrationDossierFinChantierTest(SimpleTestCase):
    """La GED est appelée — LA MÊME mécanique que ``construire_pack``
    (CAL181), un dossier GED distinct."""

    def setUp(self):
        self.calepinage = FauxCalepinage()
        self.rendus = {
            'plan_pose': lambda: pdf_de(2),
            'document_asbuilt': lambda: pdf_de(1),
            'plan_cablage': lambda: pdf_de(1),
            'nomenclature': lambda: pdf_de(1),
            'manuel_proprietaire': lambda: pdf_de(3),
        }

    def _construire(self, *, rendus=None):
        self.deposes = []

        def deposer(**depot):
            self.deposes.append(depot)
            return ('document-%s' % depot['source_type'], True)

        with mock.patch('apps.ged.services.deposit_document',
                        side_effect=deposer), \
                mock.patch('apps.ged.services.fusionner_pdf',
                           return_value='dossier-chantier') as fusion:
            resultat = construire_dossier_fin_chantier(
                self.calepinage, company='societe-essai',
                rendus=rendus if rendus is not None else self.rendus)
        self.fusion = fusion
        return resultat

    def test_toutes_les_pieces_entrent_dans_la_fusion_dans_l_ordre(self):
        resultat = self._construire()
        self.assertEqual(resultat['document'], 'dossier-chantier')
        self.assertEqual(
            self.fusion.call_args.args[0],
            ['document-calepinage.dossier_fin_chantier.plan_pose',
             'document-calepinage.dossier_fin_chantier.document_asbuilt',
             'document-calepinage.dossier_fin_chantier.plan_cablage',
             'document-calepinage.dossier_fin_chantier.nomenclature',
             'document-calepinage.dossier_fin_chantier.manuel_proprietaire'])

    def test_le_nombre_de_pages_annonce_est_la_somme_des_pieces(self):
        resultat = self._construire()
        self.assertEqual(resultat['pages_attendues'], 8)
        self.assertEqual(
            resultat['pages_attendues'],
            sum(pages for _c, _l, pages in resultat['pieces']))

    def test_la_mention_recette_garanties_est_toujours_presente(self):
        resultat = self._construire()
        self.assertIn(MENTION_RECETTE_GARANTIES, resultat['signalements'])

    def test_une_piece_absente_ajoute_son_signalement_en_plus_de_la_mention(
            self):
        rendus = dict(self.rendus)
        del rendus['nomenclature']
        resultat = self._construire(rendus=rendus)
        self.assertEqual(len(resultat['pieces']), 4)
        self.assertEqual(len(resultat['signalements']), 2)
        self.assertIn(MENTION_RECETTE_GARANTIES, resultat['signalements'])
        self.assertTrue(any('Nomenclature' in s
                            for s in resultat['signalements']))

    def test_le_rangement_ged_est_dedie_et_distinct_du_dossier_technique(
            self):
        self._construire()
        for depose in self.deposes:
            self.assertEqual(depose['company'], 'societe-essai')
            self.assertEqual(depose['cabinet_nom'], CABINET)
            self.assertEqual(depose['folder_nom'], DOSSIER_CHANTIER_GED)
            self.assertNotEqual(depose['folder_nom'], DOSSIER)

    def test_l_ancre_est_prefixee_distincte_du_dossier_technique(self):
        self._construire()
        for depose in self.deposes:
            self.assertTrue(
                depose['source_id'].startswith('dossier-fin-chantier:'))
            self.assertIn('57:', depose['source_id'])

    def test_sans_societe_le_dossier_refuse(self):
        calepinage = FauxCalepinage()
        calepinage.company = None
        with self.assertRaises(PackRefuse) as capture:
            construire_dossier_fin_chantier(calepinage, rendus=self.rendus)
        self.assertEqual(capture.exception.piece, 'company')
