# -*- coding: utf-8 -*-
"""AOF67 — le bandeau d'engagement est GÉNÉRÉ, jamais rédigé.

Les preuves exigées : les trois cas (marge positive, nulle, négative) ; la 4e
ligne apparaît exactement quand N < E ; aucun verdict écrit à la main.

Ce fichier porte en outre la vérification de la SEULE arithmétique métier
tolérée dans ``rendu/`` (``bandeau.ecart``, allowlist de
``test_calepinage_planche.py``) : son corps doit être exactement la
soustraction des deux entrées du bandeau — rien d'autre ne peut se glisser
sous cette tolérance.
"""

import ast
import os
import re
import unittest

from core.calepinage.rendu import bandeau as B
from core.calepinage.rendu import couleurs as C
from core.calepinage.rendu.feuille import Feuille

CHEMIN_BANDEAU = os.path.abspath(B.__file__)

#: Un verdict FIGÉ : « marge +26 », « écart −26 ». Le gabarit « marge +{} » ne
#: l'est pas — il dérive de la donnée à chaque rendu.
VERDICT_CHIFFRE = re.compile(r"(marge\s*\+|écart\s*[−-])\s*\d")


def _arbre_bandeau():
    with open(CHEMIN_BANDEAU, "r", encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=CHEMIN_BANDEAU)


def _reperes_de_docstrings(arbre):
    """Les docstrings DÉCRIVENT la formulation ; elles ne la figent pas."""
    reperes = set()
    for noeud in ast.walk(arbre):
        corps = getattr(noeud, "body", None)
        if not isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            continue
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            reperes.add(id(corps[0].value))
    return reperes


PARAMS = ("terrasse complète 51,1 m (allées de maintenance 1,90 / rives 0,35 / "
          "dégagt 0,30) : 314 mod. = 196,25 kWc")
VARIANTE = "variante conservatrice 1,50/0,50/0,50 : 268"


def engagement(capacite, engage=288):
    return B.Engagement(capacite_demontree=capacite, engagement_marche=engage,
                        parametres=PARAMS, variante_conservatrice=VARIANTE)


class LesTroisCasDeMarge(unittest.TestCase):
    def test_marge_positive(self):
        eng = engagement(314)
        self.assertEqual(eng.ecart, 26)
        self.assertTrue(eng.tenu)
        self.assertEqual(eng.mention_ecart, "marge +26")
        self.assertEqual(eng.couleur_verdict, C.VERT_VERDICT)
        self.assertEqual(
            eng.ligne_capacite().texte,
            "Capacité démontrée sur le relevé : 314 modules — "
            "ENGAGÉ AU MARCHÉ : 288 modules (marge +26)")

    def test_marge_nulle(self):
        eng = engagement(288)
        self.assertEqual(eng.ecart, 0)
        self.assertTrue(eng.tenu)
        self.assertEqual(eng.mention_ecart, "marge +0")
        self.assertEqual(eng.couleur_verdict, C.VERT_VERDICT)

    def test_marge_negative(self):
        eng = engagement(262)
        self.assertEqual(eng.ecart, -26)
        self.assertFalse(eng.tenu)
        self.assertEqual(eng.mention_ecart, "écart −26")
        self.assertEqual(eng.couleur_verdict, C.ORANGE_VERDICT_TENDU)
        self.assertEqual(
            eng.ligne_capacite().texte,
            "Capacité démontrée sur le relevé : 262 modules — "
            "ENGAGÉ AU MARCHÉ : 288 modules (écart −26)")

    def test_le_moins_est_typographique_pas_un_trait_d_union(self):
        self.assertEqual(B.MOINS, "−")
        self.assertNotIn("-", engagement(262).mention_ecart)


class LaQuatriemeLigne(unittest.TestCase):
    """« la 4e ligne apparaît exactement quand N < E »."""

    def test_absente_tant_que_la_capacite_couvre_l_engagement(self):
        for capacite in (289, 288, 400):
            with self.subTest(capacite=capacite):
                eng = engagement(capacite)
                self.assertIsNone(eng.ligne_repartition())
                self.assertEqual(len(eng.lignes()), 3)
                self.assertNotIn(B.LIGNE_REPARTITION, eng.textes())

    def test_presente_des_que_la_capacite_est_inferieure(self):
        for capacite in (287, 262, 0):
            with self.subTest(capacite=capacite):
                eng = engagement(capacite)
                self.assertIsNotNone(eng.ligne_repartition())
                self.assertEqual(len(eng.lignes()), 4)
                self.assertEqual(eng.textes()[3], B.LIGNE_REPARTITION)

    def test_elle_est_orange_tendu_jamais_rouge_d_echec(self):
        ligne = engagement(262).ligne_repartition()
        self.assertEqual(ligne.couleur, C.ORANGE_VERDICT_TENDU)

    def test_son_texte_est_la_clause_qui_rend_un_batiment_tendu_non_bloquant(self):
        self.assertEqual(
            B.LIGNE_REPARTITION,
            "Répartition des modules entre bâtiments ajustable à l'exécution "
            "dans le cadre du marché à prix unitaires")

    def test_la_bascule_est_exactement_a_l_egalite(self):
        avec = [c for c in range(280, 296)
                if engagement(c).ligne_repartition() is not None]
        self.assertEqual(avec, list(range(280, 288)))


class LesLignesFixes(unittest.TestCase):
    def test_la_ligne_de_marche_est_invariable(self):
        self.assertEqual(
            B.LIGNE_MARCHE,
            "Implantation définitive arrêtée après relevé d'exécution — "
            "marché à prix unitaires")
        for capacite in (262, 288, 314):
            self.assertEqual(engagement(capacite).textes()[1], B.LIGNE_MARCHE)

    def test_la_ligne_de_parametres_porte_les_deux_parties(self):
        texte = engagement(314).ligne_parametres().texte
        self.assertTrue(texte.startswith(PARAMS))
        self.assertTrue(texte.endswith(VARIANTE))

    def test_sans_variante_la_ligne_reste_celle_des_parametres(self):
        eng = B.Engagement(capacite_demontree=314, engagement_marche=288,
                           parametres=PARAMS)
        self.assertEqual(eng.ligne_parametres().texte, PARAMS)

    def test_un_bandeau_sans_parametres_est_refuse(self):
        with self.assertRaises(ValueError):
            B.Engagement(capacite_demontree=314, engagement_marche=288,
                         parametres="  ")

    def test_les_comptes_doivent_etre_des_entiers_positifs(self):
        with self.assertRaises(TypeError):
            B.Engagement(capacite_demontree=314.0, engagement_marche=288,
                         parametres=PARAMS)
        with self.assertRaises(TypeError):
            B.Engagement(capacite_demontree=True, engagement_marche=288,
                         parametres=PARAMS)
        with self.assertRaises(ValueError):
            B.Engagement(capacite_demontree=-1, engagement_marche=288,
                         parametres=PARAMS)


class AucunVerdictRedigeALaMain(unittest.TestCase):
    def test_aucun_verdict_chiffre_ecrit_en_dur(self):
        """Un « marge +26 » figé survivrait à la donnée qui l'a produit."""
        arbre = _arbre_bandeau()
        docstrings = _reperes_de_docstrings(arbre)
        fautifs = []
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant)
                    and isinstance(noeud.value, str)
                    and id(noeud) not in docstrings
                    and VERDICT_CHIFFRE.search(noeud.value)):
                fautifs.append((noeud.lineno, noeud.value))
        self.assertEqual(fautifs, [],
                         "verdict chiffré écrit en dur dans le bandeau")

    def test_le_detecteur_de_verdict_fige_voit_reellement_une_faute(self):
        self.assertTrue(VERDICT_CHIFFRE.search("(marge +26)"))
        self.assertTrue(VERDICT_CHIFFRE.search("(écart −26)"))
        self.assertIsNone(VERDICT_CHIFFRE.search("(marge +{})"))

    def test_la_soustraction_toleree_est_exactement_celle_annoncee(self):
        """La tolérance d'AOF66 ne doit pas devenir une porte dérobée."""
        arbre = _arbre_bandeau()
        corps = None
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef) and noeud.name == "ecart":
                corps = [n for n in noeud.body
                         if not (isinstance(n, ast.Expr)
                                 and isinstance(n.value, ast.Constant))]
        self.assertIsNotNone(corps, "bandeau.ecart introuvable")
        self.assertEqual(len(corps), 1)
        retour = corps[0]
        self.assertIsInstance(retour, ast.Return)
        self.assertIsInstance(retour.value, ast.BinOp)
        self.assertIsInstance(retour.value.op, ast.Sub)
        self.assertEqual(retour.value.left.attr, "capacite_demontree")
        self.assertEqual(retour.value.right.attr, "engagement_marche")

    def test_le_verdict_suit_la_donnee_quand_elle_change(self):
        avant = engagement(314)
        apres = engagement(262)
        self.assertNotEqual(avant.mention_ecart, apres.mention_ecart)
        self.assertNotEqual(avant.couleur_verdict, apres.couleur_verdict)
        self.assertNotEqual(len(avant.lignes()), len(apres.lignes()))


class DessinDuBandeau(unittest.TestCase):
    def test_les_lignes_sont_empilees_de_haut_en_bas(self):
        eng = engagement(262)
        with Feuille("T", "s", (0, 30), (50, 60)) as feuille:
            lignes = B.dessiner_bandeau(feuille, eng, 13.1, 57.05, pas=0.85)
            poses = list(feuille.axe.texts)
            hauteurs = [t.get_position()[1] for t in poses]
            textes = [t.get_text() for t in poses]
            couleurs = [t.get_color() for t in poses]
        self.assertEqual(len(poses), 4)
        self.assertEqual(textes, list(eng.textes()))
        self.assertEqual(hauteurs, sorted(hauteurs, reverse=True))
        self.assertEqual(couleurs[0], C.ORANGE_VERDICT_TENDU)
        self.assertEqual(lignes[0].taille, 9.5)

    def test_la_premiere_ligne_est_verte_quand_l_engagement_est_tenu(self):
        with Feuille("T", "s", (0, 30), (50, 60)) as feuille:
            B.dessiner_bandeau(feuille, engagement(314), 13.1, 57.05)
            couleur = feuille.axe.texts[0].get_color()
            nombre = len(feuille.axe.texts)
        self.assertEqual(couleur, C.VERT_VERDICT)
        self.assertEqual(nombre, 3)


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
