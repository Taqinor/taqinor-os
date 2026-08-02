# -*- coding: utf-8 -*-
"""AOF52 — batterie de sensibilités, plancher publié, verdict GÉNÉRÉ."""

import ast
import os
import unittest
from dataclasses import replace
from functools import lru_cache

from core.calepinage.sensibilites import batterie, raccourcir
from core.calepinage.surfaces.arc import arc_frdisi
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Parametres,
    Rives,
)
from core.tests.test_calepinage_optimum import (
    RIVES_AO,
    obstacles_aile_l,
    surface_aile_l,
)

#: valeurs RÉCONCILIÉES sur le jeu FRDISI du bâtiment A (référence 148)
ATTENDUS_AILE_L = (
    ("DEGAGEMENT_MAX", 136),
    ("ALLEE_100", 144),
    ("ALLEE_120", 104),
    ("ALLEE_190", 102),
    ("NON_COTES_ABSENTS", 172),
    ("NON_COTES_INCONNUS", 148),
    ("LONGUEUR_COURTE", 148),
    ("RIVES_MAJOREES", 148),
)


def _parametres(kits=(KIT_AO_PORTRAIT,), engagement=152):
    return Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                      pas_recherche_m=0.01, engagement_modules=engagement)


@lru_cache(maxsize=4)
def _batterie(kits=(KIT_AO_PORTRAIT,), engagement=152):
    """Batterie MÉMOÏSÉE : elle rejoue 8 DP, on ne la relance pas par test."""
    return batterie(surface_aile_l(), _parametres(kits, engagement),
                    obstacles_aile_l())


class LAileLRedonneSesSensibilites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batterie = _batterie()

    def test_la_reference_est_celle_du_script_temoin(self):
        self.assertEqual(self.batterie.reference, 148)

    def test_chaque_sensibilite_redonne_son_compte_a_l_unite_pres(self):
        obtenus = {s.code: s.modules for s in self.batterie.sensibilites}
        for code, attendu in ATTENDUS_AILE_L:
            self.assertIn(code, obtenus)
            self.assertEqual(obtenus[code], attendu, "sensibilité %s" % code)

    def test_le_plancher_est_un_champ_du_resultat(self):
        self.assertEqual(self.batterie.plancher, 102)
        self.assertLessEqual(self.batterie.plancher, self.batterie.reference)

    def test_les_deltas_sont_signes(self):
        deltas = {s.code: s.delta for s in self.batterie.sensibilites}
        self.assertEqual(deltas["ALLEE_190"], 102 - 148)
        self.assertEqual(deltas["NON_COTES_ABSENTS"], 172 - 148)

    def test_un_impact_nul_s_annonce_en_modules_pas_en_adjectif(self):
        nulle = [s for s in self.batterie.sensibilites if s.delta == 0][0]
        self.assertIn("impact chiffré de +0 module", nulle.libelle)
        self.assertNotIn("négligeable", nulle.libelle)

    def test_le_verdict_porte_les_nombres_calcules(self):
        verdict = self.batterie.verdict()
        self.assertIn("102", verdict)
        self.assertIn("152", verdict)

    def test_le_verdict_change_avec_l_engagement(self):
        souple = replace(self.batterie, engagement=100)
        self.assertIn("tenu partout", souple.verdict())
        self.assertNotEqual(souple.verdict(), self.batterie.verdict())

    def test_sans_engagement_le_verdict_le_dit(self):
        sans = replace(self.batterie, engagement=None)
        self.assertIn("aucun engagement déclaré", sans.verdict())


class AucuneChaineDeVerdictEnDur(unittest.TestCase):
    """Test EXIGÉ : aucune phrase de verdict figée dans le code."""

    def _constantes(self, nom_module):
        """Chaînes du module, DOCSTRINGS EXCLUES (elles expliquent la règle)."""
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "calepinage", nom_module)
        with open(chemin, "r", encoding="utf-8") as fh:
            arbre = ast.parse(fh.read(), filename=chemin)
        docs = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                corps = getattr(noeud, "body", None)
                if corps and isinstance(corps[0], ast.Expr) \
                        and isinstance(corps[0].value, ast.Constant) \
                        and isinstance(corps[0].value.value, str):
                    docs.add(id(corps[0].value))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant)
                    and isinstance(noeud.value, str)
                    and id(noeud) not in docs):
                yield noeud.value

    def test_toute_phrase_de_verdict_porte_un_nombre_calcule(self):
        vues = 0
        for texte in self._constantes("sensibilites.py"):
            minuscule = texte.lower()
            if "tenu" in minuscule or "engagement" in minuscule:
                vues += 1
                self.assertIn("%", texte,
                              "phrase de verdict figée : %r" % (texte,))
        self.assertGreater(vues, 0, "aucune phrase de verdict analysée")

    def test_le_libelle_d_une_sensibilite_porte_son_delta(self):
        for sensibilite in _batterie().sensibilites:
            self.assertIn("impact chiffré", sensibilite.libelle)


class KitUniqueEtMultiKits(unittest.TestCase):
    def test_le_kit_unique_est_une_sensibilite_quand_le_jeu_est_mixte(self):
        resultat = _batterie((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE))
        codes = [s.code for s in resultat.sensibilites]
        self.assertIn("KIT_UNIQUE_AO_PORTRAIT", codes)
        self.assertIn("KIT_UNIQUE_AO_PAYSAGE", codes)

    def test_le_kit_unique_ne_bat_jamais_le_mixte(self):
        resultat = _batterie((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE))
        for sensibilite in resultat.sensibilites:
            if sensibilite.code.startswith("KIT_UNIQUE"):
                self.assertLessEqual(sensibilite.modules, resultat.reference)


class Raccourcissement(unittest.TestCase):
    def test_un_rectangle_se_raccourcit(self):
        surface = SurfaceRectangle(repere="R", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        self.assertAlmostEqual(raccourcir(surface, 0.10).longueur_m, 51.00,
                               delta=1e-9)

    def test_un_arc_se_raccourcit_sur_son_developpe(self):
        self.assertAlmostEqual(raccourcir(arc_frdisi(), 0.10).developpe_m,
                               67.95, delta=1e-9)

    def test_un_polygone_se_raccourcit_par_ecretage(self):
        courte = raccourcir(surface_aile_l(), 0.10)
        self.assertIsNotNone(courte)
        self.assertAlmostEqual(max(p[0] for p in courte.contour), 10.66,
                               delta=1e-9)

    def test_un_raccourcissement_impossible_rend_none(self):
        surface = SurfaceRectangle(repere="R", longueur_m=0.05,
                                   largeur_m=25.62, rives=Rives())
        self.assertIsNone(raccourcir(surface, 0.10))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
