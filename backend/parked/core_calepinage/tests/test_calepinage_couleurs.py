# -*- coding: utf-8 -*-
"""AOF65 — le statut porte la couleur, la donnée porte la section et la légende.

Les trois preuves exigées :

1. une cote ``A_CONFIRMER`` absente de la section générée est ROUGE ;
2. changer une couleur ne se fait qu'à UN endroit — test statique sur tout le
   sous-paquet ``rendu/`` ;
3. la légende re-déclare les statuts PRÉSENTS et seulement ceux-là.
"""

import ast
import os
import re
import unittest
from dataclasses import dataclass

from core.calepinage.rendu import couleurs as C
from core.calepinage.rendu.feuille import Feuille

DOSSIER_RENDU = os.path.dirname(os.path.abspath(C.__file__))
FICHIER_PALETTE = os.path.basename(C.__file__)
HEXA = re.compile(r"^#[0-9a-fA-F]{3,8}$")


@dataclass(frozen=True)
class CoteTemoin:
    """Le minimum qu'une cote doit porter pour être colorée et annoncée."""

    texte: str
    statut: C.StatutCote
    mention: str = ""


#: Les cotes réelles de la planche 05H (bâtiment C, école SUPTECH).
COTES_05H = (
    CoteTemoin("13,18", C.StatutCote.MESURE),
    CoteTemoin("0,91", C.StatutCote.MESURE),
    CoteTemoin("4,11 (déduit)", C.StatutCote.DEDUIT_PLAN),
    CoteTemoin("7,92", C.StatutCote.MESURE),
    CoteTemoin("≈8,82", C.StatutCote.A_CONFIRMER,
               mention="profondeur de la cage ≈8,82, déduite de la fermeture 51,1"),
    CoteTemoin("≈1,0", C.StatutCote.A_CONFIRMER,
               mention="ouvrage bas de l'angle SE : profondeur ≈1,0 · muret h≈0,5"),
    CoteTemoin("13,5", C.StatutCote.A_CONFIRMER,
               mention="mur de référence de la cote 13,5 (sud)"),
)


class CouleurDeduiteDuStatut(unittest.TestCase):
    def test_les_trois_statuts_et_leurs_couleurs(self):
        self.assertEqual(C.couleur_du_statut(C.StatutCote.MESURE), "#1d4ed8")
        self.assertEqual(C.couleur_du_statut(C.StatutCote.A_CONFIRMER), "#d97706")
        self.assertEqual(C.couleur_du_statut(C.StatutCote.DEDUIT_PLAN), "#64748b")

    def test_la_palette_de_geometrie_de_tables_et_de_verdict(self):
        self.assertEqual(C.NOIR_GEOMETRIE, "#111111")
        self.assertEqual(C.VERT_TABLE_FOND, "#bbf7d0")
        self.assertEqual(C.VERT_TABLE_CONTOUR, "#15803d")
        self.assertEqual(C.couleur_du_verdict(True), "#15803d")
        self.assertEqual(C.couleur_du_verdict(False), "#c2410c")

    def test_une_couleur_ne_se_demande_pas_avec_autre_chose_qu_un_statut(self):
        with self.assertRaises(TypeError):
            C.couleur_du_statut("orange")
        with self.assertRaises(TypeError):
            C.couleur_du_statut(None)

    def test_un_caisson_incertain_est_orange_et_tirete(self):
        contour, tirete = C.style_caisson(C.StatutCote.A_CONFIRMER)
        self.assertEqual(contour, C.ORANGE_A_CONFIRMER)
        self.assertTrue(tirete)
        for statut in (C.StatutCote.MESURE, C.StatutCote.DEDUIT_PLAN):
            _contour, tirete = C.style_caisson(statut)
            self.assertFalse(tirete)

    def test_le_caisson_incertain_est_reellement_dessine_tirete(self):
        contour, tirete = C.style_caisson(C.StatutCote.A_CONFIRMER)
        with Feuille("T", "s", (0, 30), (0, 30)) as feuille:
            feuille.caisson(14.09, 22.92, 4.11, 8.82, contour=contour,
                            remplissage=C.FOND_CAISSON, incertain=tirete)
            rectangle = feuille.axe.patches[0]
        self.assertEqual(rectangle.get_linestyle(), "--")
        self.assertEqual(rectangle.get_edgecolor()[:3],
                         (0xd9 / 255, 0x77 / 255, 0x06 / 255))


class SectionAConfirmerGenereeDepuisLaDonnee(unittest.TestCase):
    def test_chaque_cote_orange_produit_sa_ligne(self):
        lignes = C.section_a_confirmer(COTES_05H)
        self.assertEqual(len(lignes), 3)
        for cote in COTES_05H:
            if cote.statut is C.StatutCote.A_CONFIRMER:
                self.assertIn(cote.mention, lignes)

    def test_aucune_cote_bleue_ni_grise_dans_la_section(self):
        lignes = " | ".join(C.section_a_confirmer(COTES_05H))
        self.assertNotIn("13,18", lignes)
        self.assertNotIn("4,11 (déduit)", lignes)

    def test_une_cote_a_confirmer_absente_de_la_section_est_ROUGE(self):
        """LE cas de la tâche : la section n'est jamais retapée à la main."""
        complete = C.section_a_confirmer(COTES_05H)
        ampute = complete[:-1]
        with self.assertRaises(C.SectionIncomplete) as capture:
            C.verifier_section_complete(COTES_05H, ampute)
        self.assertIn(complete[-1], str(capture.exception))

    def test_la_section_complete_passe(self):
        complete = C.section_a_confirmer(COTES_05H)
        self.assertEqual(C.verifier_section_complete(COTES_05H, complete),
                         complete)

    def test_une_cote_orange_sans_mention_retombe_sur_son_texte(self):
        cotes = (CoteTemoin("Δ 0,58 de largeur", C.StatutCote.A_CONFIRMER),)
        self.assertEqual(C.section_a_confirmer(cotes), ("Δ 0,58 de largeur",))

    def test_une_cote_orange_totalement_muette_est_refusee(self):
        cotes = (CoteTemoin("", C.StatutCote.A_CONFIRMER),)
        with self.assertRaises(C.SectionIncomplete):
            C.section_a_confirmer(cotes)

    def test_les_doublons_ne_sont_annonces_qu_une_fois(self):
        cotes = (CoteTemoin("a", C.StatutCote.A_CONFIRMER, mention="même point"),
                 CoteTemoin("b", C.StatutCote.A_CONFIRMER, mention="même point"))
        self.assertEqual(C.section_a_confirmer(cotes), ("même point",))

    def test_le_titre_de_section_est_celui_des_planches_remises(self):
        self.assertEqual(C.TITRE_SECTION_A_CONFIRMER,
                         "À CONFIRMER À L'EXÉCUTION (orange)")


class LegendeDesStatutsPresents(unittest.TestCase):
    def test_les_trois_statuts_presents_sont_declares_dans_l_ordre(self):
        legende = C.legende_des_statuts(COTES_05H)
        self.assertEqual([statut for statut, _ in legende],
                         [C.StatutCote.MESURE, C.StatutCote.A_CONFIRMER,
                          C.StatutCote.DEDUIT_PLAN])

    def test_un_statut_absent_n_est_PAS_declare(self):
        sans_orange = tuple(c for c in COTES_05H
                            if c.statut is not C.StatutCote.A_CONFIRMER)
        statuts = [statut for statut, _ in C.legende_des_statuts(sans_orange)]
        self.assertNotIn(C.StatutCote.A_CONFIRMER, statuts)
        self.assertEqual(statuts, [C.StatutCote.MESURE,
                                   C.StatutCote.DEDUIT_PLAN])

    def test_une_planche_toute_bleue_ne_declare_qu_un_statut(self):
        toutes_bleues = (CoteTemoin("10,87", C.StatutCote.MESURE),)
        self.assertEqual(len(C.legende_des_statuts(toutes_bleues)), 1)

    def test_aucune_cote_aucune_legende(self):
        self.assertEqual(C.legende_des_statuts(()), ())
        self.assertEqual(C.section_a_confirmer(()), ())

    def test_les_entrees_se_dessinent_dans_la_couleur_de_leur_statut(self):
        entrees = C.entrees_de_legende(COTES_05H)
        self.assertEqual(len(entrees), 3)
        with Feuille("T", "s", (0, 30), (0, 30)) as feuille:
            feuille.legende(2.0, 20.0, entrees, couleur_texte=C.TEXTE_PANNEAU)
            couleurs = [p.get_edgecolor()[:3] for p in feuille.axe.patches]
            rendus = [t.get_text() for t in feuille.axe.texts]
        self.assertEqual(couleurs[0], (0x1d / 255, 0x4e / 255, 0xd8 / 255))
        self.assertEqual(couleurs[1], (0xd9 / 255, 0x77 / 255, 0x06 / 255))
        self.assertEqual(couleurs[2], (0x64 / 255, 0x74 / 255, 0x8b / 255))
        self.assertEqual(rendus, [libelle for _e, libelle in entrees])


class UnSeulProprietaireDeLaPalette(unittest.TestCase):
    """« changer une couleur ne se fait qu'à un seul endroit »."""

    def _modules_de_rendu(self):
        for nom in sorted(os.listdir(DOSSIER_RENDU)):
            if nom.endswith(".py") and nom != FICHIER_PALETTE:
                yield nom, os.path.join(DOSSIER_RENDU, nom)

    def test_aucune_valeur_hexadecimale_hors_du_module_de_palette(self):
        fautifs = []
        for nom, chemin in self._modules_de_rendu():
            with open(chemin, "r", encoding="utf-8") as fh:
                arbre = ast.parse(fh.read(), filename=chemin)
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, ast.Constant)
                        and isinstance(noeud.value, str)
                        and HEXA.match(noeud.value)):
                    fautifs.append((nom, noeud.lineno, noeud.value))
        self.assertEqual(
            fautifs, [],
            "couleur codée hors de rendu/couleurs.py — la palette a UN "
            "propriétaire : %r" % (fautifs,))

    def test_le_module_de_palette_couvre_bien_toute_la_planche(self):
        for nom in ("BLEU_MESURE", "ORANGE_A_CONFIRMER", "GRIS_DEDUIT",
                    "NOIR_GEOMETRIE", "FOND_CAISSON", "FOND_BLOC",
                    "VERT_TABLE_FOND", "VERT_TABLE_CONTOUR", "VERT_VERDICT",
                    "ORANGE_VERDICT_TENDU", "TEXTE_PANNEAU",
                    "TEXTE_SECONDAIRE", "TEXTE_ENGAGEMENT"):
            self.assertTrue(HEXA.match(getattr(C, nom)), nom)


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
