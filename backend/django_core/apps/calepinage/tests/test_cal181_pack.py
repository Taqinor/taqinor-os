"""CAL181 — le dossier technique : une pièce manquante est SIGNALÉE.

Deux niveaux d'essais, et ce qu'ils prouvent :

1. PURS (ici, exécutables sans base) — le comptage de pages se fait sur de
   VRAIS PDF construits par PyMuPDF, la somme des pages des pièces est celle
   qu'annonce le pack, une pièce obligatoire qui ne se rend pas fait ÉCHOUER
   le pack en la nommant, et une pièce facultative absente sort en SIGNALEMENT.
2. ORCHESTRATION (base) — le pack dépose chaque pièce en GED puis appelle
   ``fusionner_pdf`` avec TOUTES les pièces, dans l'ordre : aucune n'est
   silencieusement perdue en chemin. La fusion elle-même est la primitive
   plateforme XGED10, qui a ses propres essais ; on ne la re-teste pas, on
   vérifie qu'on l'appelle correctement.

Run :
    python manage.py test apps.calepinage.tests.test_cal181_pack -v2
"""
from unittest import mock, skipUnless

from django.test import SimpleTestCase

from apps.calepinage.services.pack_technique import (
    SPEC_PIECES, PackRefuse, compter_pages, construire_pack, rendre_pieces,
)

try:
    import fitz
    _FITZ = True
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None
    _FITZ = False


def pdf_de(pages):
    """Un VRAI PDF de ``pages`` pages — pas un octet inventé."""
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    octets = document.tobytes()
    document.close()
    return octets


class FauxCalepinage:
    pk = 41
    titre = 'Toiture atelier'
    layout_hash = 'a' * 64
    company = 'societe-essai'

    def __str__(self):
        return self.titre


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class ComptagePagesTest(SimpleTestCase):
    def test_compte_les_pages_d_un_vrai_pdf(self):
        self.assertEqual(compter_pages(pdf_de(3)), 3)

    def test_un_document_illisible_ne_compte_aucune_page(self):
        # Zéro page plutôt qu'une exception : c'est le CONTRÔLE de somme qui
        # doit signaler le défaut, pas une pile d'appels.
        self.assertEqual(compter_pages(b'ceci n est pas un pdf'), 0)
        self.assertEqual(compter_pages(b''), 0)


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class RenduDesPiecesTest(SimpleTestCase):
    def setUp(self):
        self.calepinage = FauxCalepinage()
        self.rendus = {'planche': lambda: pdf_de(1),
                       'note_calcul': lambda: pdf_de(2)}

    def test_les_pieces_obligatoires_sont_rendues_et_comptees(self):
        pieces, _signalements = rendre_pieces(self.calepinage,
                                              company='societe-essai',
                                              rendus=self.rendus)
        self.assertEqual([(code, pages) for code, _l, _o, pages in pieces],
                         [('planche', 1), ('note_calcul', 2)])

    def test_une_piece_facultative_absente_est_signalee_jamais_sautee(self):
        _pieces, signalements = rendre_pieces(self.calepinage,
                                              company='societe-essai',
                                              rendus=self.rendus)
        facultatives = [libelle for _c, libelle, obligatoire in SPEC_PIECES
                        if not obligatoire]
        self.assertTrue(facultatives)
        for libelle in facultatives:
            self.assertTrue(
                any(libelle in signalement for signalement in signalements),
                'pièce facultative « %s » sautée en silence' % libelle)

    def test_une_piece_obligatoire_qui_echoue_refuse_le_pack(self):
        def casse():
            raise ValueError('aucune conception enregistrée')

        with self.assertRaises(PackRefuse) as capture:
            rendre_pieces(self.calepinage, company='societe-essai',
                          rendus=dict(self.rendus, planche=casse))
        self.assertEqual(capture.exception.piece, 'planche')
        self.assertIn('aucune conception', str(capture.exception))

    def test_une_piece_obligatoire_vide_refuse_le_pack(self):
        # Un PDF vide dans un dossier remis est un défaut INVISIBLE.
        with self.assertRaises(PackRefuse) as capture:
            rendre_pieces(self.calepinage, company='societe-essai',
                          rendus=dict(self.rendus,
                                      note_calcul=lambda: b''))
        self.assertEqual(capture.exception.piece, 'note_calcul')


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class OrchestrationDuPackTest(SimpleTestCase):
    """Le pack appelle la GED — il ne fusionne rien lui-même."""

    def setUp(self):
        self.calepinage = FauxCalepinage()
        self.rendus = {'planche': lambda: pdf_de(1),
                       'note_calcul': lambda: pdf_de(2)}

    def _construire(self):
        self.deposes = []

        def deposer(**kwargs):
            self.deposes.append(kwargs)
            return ('document-%s' % kwargs['source_type'], True)

        with mock.patch('apps.ged.services.deposit_document',
                        side_effect=deposer), \
                mock.patch('apps.ged.services.fusionner_pdf',
                           return_value='pack') as fusion:
            resultat = construire_pack(self.calepinage,
                                       company='societe-essai',
                                       rendus=self.rendus)
        self.fusion = fusion
        return resultat

    def test_toutes_les_pieces_entrent_dans_la_fusion_dans_l_ordre(self):
        resultat = self._construire()
        self.assertEqual(resultat['document'], 'pack')
        self.assertEqual(
            self.fusion.call_args.args[0],
            ['document-calepinage.planche',
             'document-calepinage.note_calcul'])

    def test_le_nombre_de_pages_annonce_est_la_somme_des_pieces(self):
        resultat = self._construire()
        self.assertEqual(resultat['pages_attendues'], 3)
        self.assertEqual(
            resultat['pages_attendues'],
            sum(pages for _c, _l, pages in resultat['pieces']))

    def test_l_idempotence_est_ancree_sur_l_empreinte_du_layout(self):
        # Ancrer sur le seul identifiant du calepinage aurait rendu un pack
        # PÉRIMÉ en silence après modification de la conception.
        self._construire()
        ancres = [depose['source_id'] for depose in self.deposes]
        for ancre in ancres:
            self.assertIn('aaaaaaaaaaaa', ancre)
            self.assertTrue(ancre.startswith('41:'))

    def test_la_societe_est_celle_du_serveur_et_le_rangement_est_dedie(self):
        self._construire()
        for depose in self.deposes:
            self.assertEqual(depose['company'], 'societe-essai')
            self.assertEqual(depose['cabinet_nom'], 'Calepinage')
            self.assertEqual(depose['folder_nom'], 'Dossiers techniques')

    def test_sans_societe_le_pack_refuse(self):
        calepinage = FauxCalepinage()
        calepinage.company = None
        with self.assertRaises(PackRefuse) as capture:
            construire_pack(calepinage, rendus=self.rendus)
        self.assertEqual(capture.exception.piece, 'company')
