# -*- coding: utf-8 -*-
"""AOF68 — le bloc de notes se replie seul, ou il refuse. Rien ne sort du cadre.

Deux preuves exigées :

1. un texte trop long échoue avec « notes illisibles : alléger le texte » AU
   LIEU de rendre une planche illisible en silence ;
2. aucun élément ne dépasse le cadre — test GÉOMÉTRIQUE sur les boîtes
   englobantes de tous les artistes de la figure.
"""

import unittest

from core.calepinage.rendu import couleurs as C
from core.calepinage.rendu import notes as N
from core.calepinage.rendu.feuille import Feuille

#: Les notas réels du bas de la planche 05H.
NOTES_05H = (
    "Relevé contradictoire du 27/07/2026 : terrasse COMPLÈTE (bord bas = mur "
    "sud) — un seul calepinage sur 51,1 m. Aucune table à cheval sur la ligne "
    "interne.",
    "OUVRAGE BAS (angle SE) : 4,78 × ≈1,0 — muret h≈0,5, nature à confirmer à "
    "l'exécution — dégagement 0,50 · aucune souche relevée sur la terrasse.",
    "Aucun équipement de climatisation présent sur la terrasse au relevé ; une "
    "installation ultérieure sera coordonnée avec le champ PV à l'exécution.",
)

#: Haut du bloc et haut du cartouche, en fraction de figure (planches remises).
HAUT = 0.30
HAUT_DU_CARTOUCHE = 0.135
LARGEUR_COLONNE = 0.32


def feuille_temoin():
    return Feuille("IMPLANTATION PHOTOVOLTAÏQUE", "relevé du 27/07/2026",
                   (0, 30), (0, 55))


class RepliAutomatique(unittest.TestCase):
    def test_le_texte_est_replie_a_la_largeur_de_colonne(self):
        lignes = N.replier(NOTES_05H, 60)
        self.assertGreater(len(lignes), len(NOTES_05H))
        for ligne in lignes:
            self.assertLessEqual(len(ligne), 60, ligne)

    def test_aucun_mot_n_est_perdu_au_repli(self):
        mots_avant = " ".join(NOTES_05H).split()
        mots_apres = " ".join(N.replier(NOTES_05H, 48)).split()
        self.assertEqual(mots_apres, mots_avant)

    def test_une_note_vide_reste_une_respiration(self):
        self.assertEqual(N.replier(("", "  "), 40), ("", ""))

    def test_la_largeur_de_colonne_depend_de_la_taille(self):
        large = N.caracteres_par_ligne(0.32, 16.54, 5.0)
        etroite = N.caracteres_par_ligne(0.32, 16.54, 7.0)
        self.assertGreater(large, etroite)
        self.assertGreaterEqual(etroite, 1)


class MiseEnPageCalculee(unittest.TestCase):
    def _calculer(self, textes, hauteur=HAUT - HAUT_DU_CARTOUCHE):
        return N.calculer_mise_en_page(textes, LARGEUR_COLONNE, hauteur,
                                       16.54, 11.69)

    def test_les_notas_reels_tiennent_a_taille_maximale(self):
        mise = self._calculer(NOTES_05H)
        self.assertEqual(mise.taille, N.TAILLE_MAXIMALE)
        self.assertLessEqual(mise.hauteur, HAUT - HAUT_DU_CARTOUCHE + 1e-12)

    def test_le_bloc_s_arrete_AU_DESSUS_du_cartouche(self):
        mise = self._calculer(NOTES_05H)
        bas_atteint = HAUT - mise.hauteur
        self.assertGreaterEqual(bas_atteint, HAUT_DU_CARTOUCHE - 1e-12)

    def test_un_texte_plus_long_fait_baisser_la_taille_avant_de_refuser(self):
        allonge = NOTES_05H * 3
        mise = self._calculer(allonge)
        self.assertLess(mise.taille, N.TAILLE_MAXIMALE)
        self.assertGreaterEqual(mise.taille, N.TAILLE_MINIMALE)
        self.assertLessEqual(mise.hauteur, HAUT - HAUT_DU_CARTOUCHE + 1e-12)

    def test_un_texte_trop_long_ECHOUE_avec_le_message_exact(self):
        with self.assertRaises(N.NotesIllisibles) as capture:
            self._calculer(NOTES_05H * 40)
        self.assertEqual(str(capture.exception),
                         "notes illisibles : alléger le texte")

    def test_une_hauteur_disponible_nulle_ou_negative_echoue_de_meme(self):
        for hauteur in (0.0, -0.05):
            with self.assertRaises(N.NotesIllisibles) as capture:
                self._calculer(NOTES_05H, hauteur=hauteur)
            self.assertEqual(str(capture.exception), N.MESSAGE_ILLISIBLE)

    def test_jamais_en_dessous_du_seuil_de_lisibilite(self):
        for repetitions in range(1, 12):
            try:
                mise = self._calculer(NOTES_05H * repetitions)
            except N.NotesIllisibles:
                continue
            self.assertGreaterEqual(mise.taille, N.TAILLE_MINIMALE)

    def test_le_calcul_est_reproductible(self):
        premier = self._calculer(NOTES_05H * 3)
        second = self._calculer(NOTES_05H * 3)
        self.assertEqual(premier, second)


class DessinDuBloc(unittest.TestCase):
    def test_une_ligne_de_figure_par_ligne_repliee(self):
        with feuille_temoin() as feuille:
            avant = len(feuille.figure.texts)
            mise = N.dessiner_notes(feuille, NOTES_05H, C.TEXTE_SECONDAIRE,
                                    0.015, HAUT, HAUT_DU_CARTOUCHE,
                                    LARGEUR_COLONNE)
            poses = len(feuille.figure.texts) - avant
            hauteurs = [t.get_position()[1] for t in feuille.figure.texts]
        self.assertEqual(poses, len([ligne for ligne in mise.lignes if ligne]))
        self.assertEqual(hauteurs, sorted(hauteurs, reverse=True))

    def test_le_bloc_refuse_plutot_que_de_deborder_sur_le_cartouche(self):
        with feuille_temoin() as feuille:
            avant = len(feuille.figure.texts)
            with self.assertRaises(N.NotesIllisibles):
                N.dessiner_notes(feuille, NOTES_05H * 40, C.TEXTE_SECONDAIRE,
                                 0.015, HAUT, HAUT_DU_CARTOUCHE,
                                 LARGEUR_COLONNE)
            self.assertEqual(len(feuille.figure.texts), avant)


class RienHorsCadre(unittest.TestCase):
    def test_une_planche_bien_cadree_passe(self):
        with feuille_temoin() as feuille:
            feuille.rectangle(1, 1, 20, 40, contour=C.NOIR_GEOMETRIE)
            feuille.cote((1, 45), (21, 45), C.BLEU_MESURE, off=0.5,
                         contenu="20,00")
            N.dessiner_notes(feuille, NOTES_05H, C.TEXTE_SECONDAIRE, 0.015,
                             HAUT, HAUT_DU_CARTOUCHE, LARGEUR_COLONNE)
            self.assertTrue(N.verifier_dans_le_cadre(feuille))

    def test_un_element_hors_cadre_est_DETECTE_et_NOMME(self):
        with feuille_temoin() as feuille:
            feuille.texte(-4000, 25, "cote égarée", C.BLEU_MESURE)
            with self.assertRaises(N.ElementHorsCadre) as capture:
                N.verifier_dans_le_cadre(feuille)
        self.assertIn("cote égarée", str(capture.exception))

    def test_un_patch_hors_cadre_est_detecte_par_son_type(self):
        with feuille_temoin() as feuille:
            feuille.rectangle(-5000, -5000, 10, 10, contour=C.NOIR_GEOMETRIE)
            with self.assertRaises(N.ElementHorsCadre) as capture:
                N.verifier_dans_le_cadre(feuille)
        self.assertIn("Rectangle", str(capture.exception))

    def test_la_garde_couvre_les_artistes_de_la_FIGURE_aussi(self):
        with feuille_temoin() as feuille:
            feuille.texte_figure(0.015, 4.0, "note hors feuille",
                                 C.TEXTE_SECONDAIRE)
            with self.assertRaises(N.ElementHorsCadre) as capture:
                N.verifier_dans_le_cadre(feuille)
        self.assertIn("note hors feuille", str(capture.exception))

    def test_un_element_invisible_ne_declenche_rien(self):
        with feuille_temoin() as feuille:
            egare = feuille.texte(-4000, 25, "masqué", C.BLEU_MESURE)
            egare.set_visible(False)
            self.assertTrue(N.verifier_dans_le_cadre(feuille))


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
