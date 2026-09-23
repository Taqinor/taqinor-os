"""CALX326 — le rapport d'étude, le plan de câblage et le rapport d'ombrage
ENTRENT dans le dossier technique.

Le Constat était vérifié : ``SPEC_PIECES`` figeait quatre pièces
(``services/pack_technique.py:50-55``) et le dossier réglementaire trois
(``services/reglementaire.py:348-352``) — le rapport d'étude (CALX297), le
plan de câblage (CALX310) et le rapport d'ombrage (CALX317), une fois
construits, restaient hors de TOUT dossier.

Deux niveaux d'essais, comme CAL181 (``test_cal181_pack.py``) et CALX309
(``test_calx309_pack_plans.py``) :

1. PUR, verrouille le CÂBLAGE — ``_rendus`` (fonction privée) doit déclarer
   un rendu pour CHACUN des SEPT codes de ``SPEC_PIECES``, en particulier les
   trois neufs.
2. PUR mais RÉEL sur le contrôle de pages — ``rendre_pieces`` avec un
   ``rendus`` EXPLICITE (mêmes fabriques PyMuPDF que CAL181) : un calepinage
   « simulé » (les trois rendus neufs sont disponibles) voit ses SEPT pièces
   entrer, la somme de pages étant celle que ``compter_pages`` annonce ; un
   calepinage « non simulé » (aucun des trois rendus neufs, exactement comme
   un refus de ``RapportRefuse``/``PlanCablageRefuse``/
   ``RapportOmbrageRefuse`` amont) produit EXACTEMENT le dossier d'avant la
   tâche, les trois pièces neuves sortant en SIGNALEMENT — jamais sautées en
   silence.

Run :
    python manage.py test apps.calepinage.tests.test_calx326_pack_etendu -v2
"""
from unittest import skipUnless

from django.test import SimpleTestCase

from apps.calepinage.services import pack_technique
from apps.calepinage.services.pack_technique import SPEC_PIECES, rendre_pieces

try:
    import fitz  # PyMuPDF
    _FITZ = True
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None
    _FITZ = False


def pdf_de(pages):
    """Un VRAI PDF de ``pages`` pages — même fabrique que CAL181/CALX309."""
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


PIECES_NEUVES = ('rapport_etude', 'plan_cablage', 'rapport_ombrage')
PIECES_D_AVANT = ('planche', 'note_calcul', 'plan_toiture', 'plan_masse')


class SpecPiecesEtenduesTest(SimpleTestCase):
    """``SPEC_PIECES`` déclare les trois pièces neuves, FACULTATIVES, sans
    perdre les quatre d'avant la tâche."""

    def test_les_trois_pieces_neuves_sont_declarees_facultatives(self):
        obligatoire_par_code = {code: obligatoire
                                for code, _l, obligatoire in SPEC_PIECES}
        for code in PIECES_NEUVES:
            self.assertIn(code, obligatoire_par_code)
            self.assertFalse(obligatoire_par_code[code],
                             '« %s » doit être facultative' % code)

    def test_les_quatre_pieces_d_avant_la_tache_restent_declarees(self):
        codes = {code for code, _l, _o in SPEC_PIECES}
        for code in PIECES_D_AVANT:
            self.assertIn(code, codes)

    def test_sept_pieces_au_total_aucune_perdue_aucune_dupliquee(self):
        codes = [code for code, _l, _o in SPEC_PIECES]
        self.assertEqual(len(codes), 7)
        self.assertEqual(len(set(codes)), 7)


class RendusDeclareLesSeptPiecesTest(SimpleTestCase):
    """Comme CALX309 (``RendusDeclareLesQuatrePiecesTest``) : ``_rendus``
    doit déclarer un rendu pour CHAQUE code de ``SPEC_PIECES`` — un écart y
    ramènerait la MÊME fuite silencieuse que le Constat de CALX309/CALX326
    documentait (une pièce déclarée sans rendu branché)."""

    def test_les_sept_codes_de_spec_pieces_ont_tous_un_rendu(self):
        rendus = pack_technique._rendus(FauxCalepinage(), 'societe-essai')
        codes_declares = {code for code, _l, _o in SPEC_PIECES}
        self.assertEqual(set(rendus), codes_declares)

    def test_les_trois_pieces_neuves_sont_branchees(self):
        rendus = pack_technique._rendus(FauxCalepinage(), 'societe-essai')
        for code in PIECES_NEUVES:
            self.assertIn(code, rendus)


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class DossierEtenduSimuleOuPasTest(SimpleTestCase):
    """``rendre_pieces`` avec un ``rendus`` EXPLICITE — MÊME mécanique que
    CAL181 (contrôle de pages par ``compter_pages``), aucune base."""

    def setUp(self):
        self.calepinage = FauxCalepinage()
        # Les quatre pièces D'AVANT la tâche — toujours disponibles.
        self.rendus_avant = {
            'planche': lambda: pdf_de(1),
            'note_calcul': lambda: pdf_de(2),
            'plan_toiture': lambda: pdf_de(1),
            'plan_masse': lambda: pdf_de(1),
        }

    def test_calepinage_simule_les_trois_pieces_neuves_entrent(self):
        rendus = dict(self.rendus_avant,
                      rapport_etude=lambda: pdf_de(3),
                      plan_cablage=lambda: pdf_de(1),
                      rapport_ombrage=lambda: pdf_de(2))
        pieces, signalements = rendre_pieces(self.calepinage,
                                             company='societe-essai',
                                             rendus=rendus)
        self.assertEqual(
            [code for code, _l, _o, _p in pieces],
            ['planche', 'note_calcul', 'plan_toiture', 'plan_masse',
             'rapport_etude', 'plan_cablage', 'rapport_ombrage'])
        # `pages` (posé par `rendre_pieces` via `compter_pages`, ARC11) doit
        # correspondre au VRAI comptage des octets rendus.
        for _code, _libelle, octets, pages in pieces:
            self.assertEqual(pack_technique.compter_pages(octets), pages)
        self.assertEqual(sum(pages for _c, _l, _o, pages in pieces), 11)
        self.assertEqual(signalements, [])

    def test_calepinage_non_simule_produit_le_dossier_d_avant_la_tache(self):
        # Aucun rendu pour les trois pièces neuves : la MÊME issue qu'un
        # calepinage sans résultat de moteur / sans chaîne publiée / sans
        # matrice d'ombrage — un refus amont AVALÉ en signalement, puisque
        # les trois sont FACULTATIVES.
        pieces, signalements = rendre_pieces(self.calepinage,
                                             company='societe-essai',
                                             rendus=self.rendus_avant)
        self.assertEqual([code for code, _l, _o, _p in pieces],
                         list(PIECES_D_AVANT))
        self.assertEqual(sum(pages for _c, _l, _o, pages in pieces), 5)
        libelles_neufs = [libelle for code, libelle, _o in SPEC_PIECES
                          if code in PIECES_NEUVES]
        self.assertEqual(len(signalements), 3)
        for libelle in libelles_neufs:
            self.assertTrue(
                any(libelle in signalement for signalement in signalements),
                'pièce neuve « %s » sautée en silence' % libelle)
