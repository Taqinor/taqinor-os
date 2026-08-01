# -*- coding: utf-8 -*-
"""AOF43 — le poseur, et l'invariant commercial ``2 × len(tables) == compte``.

Les 3 jeux : école (rectangle), aile en L (polygone), arc (courbe). Le test
importe les DEUX chemins — c'est son rôle ; le code de production, lui, ne les
laisse jamais se voir.
"""

import ast
import os
import unittest

from core.calepinage.moteur import compter_plan
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.poseur import obstacles_dilates, poser_plan, poser_rangee
from core.calepinage.surfaces.arc import arc_frdisi
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    NatureZone,
    Obstacle,
    Provenance,
    Rives,
    Zone,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES, ECOLE_RANGEES

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)
CONTOUR_L = ((10.76, 0.0), (10.76, 47.08), (0.0, 47.08),
             (0.0, 11.2), (-29.74, 11.2), (-29.74, 0.0))
RANGEES_L = (0.35, 5.65, 12.80, 20.65, 25.95, 31.25, 36.55, 41.85)
RANGEES_ARC = (0.80, 5.20, 8.30)


class DessineEgaleCompte(unittest.TestCase):
    """L'invariant, sur les TROIS géométries du dossier FRDISI."""

    def _verifier(self, surface, rangees, obstacles=(), zones=()):
        obs = appliquer_regles(obstacles)
        plan = compter_plan(surface, rangees, obs, zones)
        tables = poser_plan(surface, rangees, obs, zones)
        self.assertEqual(2 * len(tables), plan.modules)
        return plan.modules

    def test_ecole_rectangle(self):
        surface = SurfaceRectangle(repere="BAT_C_ECOLE", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        total = self._verifier(surface,
                               tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
                               ECOLE_OBSTACLES)
        self.assertEqual(total, 314)

    def test_aile_l_polygone(self):
        surface = SurfacePolygone(repere="BAT_A_AILE_L", contour=CONTOUR_L,
                                  rives=RIVES_AO)
        obstacles = (
            Obstacle(repere="CAGE", x0=6.13, x1=10.76, y0=12.23, y1=14.70,
                     provenance=Provenance.RELEVE, degagement_m=0.30),
            Obstacle(repere="C1", x0=3.77, x1=4.92, y0=3.39, y1=4.70,
                     provenance=Provenance.RELEVE, degagement_m=0.30),
            Obstacle(repere="GRECT", x0=-1.70, x1=-0.40, y0=4.95, y1=7.16,
                     provenance=Provenance.DEVINE),
        )
        self._verifier(surface, tuple((y, KIT_AO_PORTRAIT) for y in RANGEES_L),
                       obstacles)

    def test_arc(self):
        surface = arc_frdisi(rives=RIVES_AO)
        obstacles = (
            Obstacle(repere="K1", x0=27.28, x1=28.28, y0=6.23, y1=7.13,
                     provenance=Provenance.RELEVE, degagement_m=0.35),
            Obstacle(repere="K3", x0=29.18, x1=30.43, y0=3.50, y1=4.30,
                     provenance=Provenance.RELEVE, degagement_m=0.35),
        )
        self._verifier(surface, tuple((y, KIT_AO_PAYSAGE) for y in RANGEES_ARC),
                       obstacles)

    def test_avec_une_zone_interdite(self):
        surface = SurfaceRectangle(repere="R", longueur_m=40.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        zone = Zone(repere="SERVITUDE", nature=NatureZone.INTERDITE,
                    sommets=((15.0, 0.0), (20.0, 0.0), (20.0, 12.0), (15.0, 12.0)))
        self._verifier(surface, ((0.35, KIT_AO_PORTRAIT), (5.65, KIT_AO_PORTRAIT)),
                       (), (zone,))

    def test_sans_obstacle_du_tout(self):
        surface = SurfaceRectangle(repere="R", longueur_m=40.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        self._verifier(surface, ((0.35, KIT_AO_PAYSAGE),))


class GeometrieDesTables(unittest.TestCase):
    def test_une_table_plane_est_un_rectangle_de_la_taille_du_kit(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=10.0,
                                   rives=RIVES_AO)
        tables = poser_rangee(surface, 0.35, KIT_AO_PORTRAIT)
        self.assertTrue(tables)
        table = tables[0]
        self.assertAlmostEqual(table.x1 - table.x0, 1.134, delta=1e-9)
        self.assertAlmostEqual(table.y1 - table.y0,
                               KIT_AO_PORTRAIT.emprise_transversale_m, delta=1e-9)
        self.assertEqual(len(table.polygone), 4)

    def test_les_tables_ne_se_chevauchent_pas_en_abscisse(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=10.0,
                                   rives=RIVES_AO)
        tables = poser_rangee(surface, 0.35, KIT_AO_PORTRAIT)
        for gauche, droite in zip(tables, tables[1:]):
            self.assertLessEqual(gauche.x1, droite.x0 + 1e-9)

    def test_sur_l_arc_la_table_est_un_polygone_rigide(self):
        surface = arc_frdisi(rives=RIVES_AO)
        tables = poser_rangee(surface, 0.80, KIT_AO_PAYSAGE)
        self.assertTrue(tables)
        self.assertEqual(len(tables[0].polygone), 4)
        # l'emprise ANGULAIRE d'une table vaut le pas, plus large que la table
        self.assertGreater(tables[0].pas_m, KIT_AO_PAYSAGE.cote_le_long_rangee_m)

    def test_une_table_ne_compte_jamais(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=10.0,
                                   rives=RIVES_AO)
        self.assertIsNone(poser_rangee(surface, 0.35, KIT_AO_PORTRAIT)[0].modules)

    def test_degagement_non_derive_leve(self):
        with self.assertRaises(ValueError):
            obstacles_dilates((Obstacle(repere="X", x0=0, x1=1, y0=0, y1=1),))

    def test_obstacle_ecarte_ne_bloque_pas_la_pose(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=10.0,
                                   rives=RIVES_AO)
        obs = appliquer_regles((
            Obstacle(repere="S1", x0=5.0, x1=6.0, y0=0.0, y1=10.0,
                     provenance=Provenance.ECARTE),))
        sans = poser_rangee(surface, 0.35, KIT_AO_PORTRAIT)
        avec = poser_rangee(surface, 0.35, KIT_AO_PORTRAIT, obs)
        self.assertEqual(len(sans), len(avec))


class LePoseurNeCompteRien(unittest.TestCase):
    """Test EXIGÉ : ``poseur`` n'importe JAMAIS ``moteur``."""

    def test_poseur_n_importe_pas_moteur(self):
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "calepinage", "poseur.py")
        with open(chemin, "r", encoding="utf-8") as fh:
            arbre = ast.parse(fh.read(), filename=chemin)
        for noeud in ast.walk(arbre):
            noms = []
            if isinstance(noeud, ast.Import):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                noms = [noeud.module or ""]
            for nom in noms:
                self.assertNotIn("moteur", nom,
                                 "poseur.py ne doit JAMAIS importer moteur")

    def test_le_poseur_ne_rend_aucun_total(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=10.0,
                                   rives=RIVES_AO)
        sortie = poser_plan(surface, ((0.35, KIT_AO_PORTRAIT),))
        self.assertIsInstance(sortie, tuple)
        self.assertTrue(all(hasattr(t, "polygone") for t in sortie))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
