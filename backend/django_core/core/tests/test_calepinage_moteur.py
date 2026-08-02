# -*- coding: utf-8 -*-
"""AOF42 — le compteur générique, et la PREUVE qu'il ne pose rien.

Le jeu de référence est le bâtiment C (école SUPTECH) : mêmes cotes, mêmes
obstacles, mêmes rangées explicites que la planche définitive du 27/07/2026,
qui publie 314 modules.
"""

import ast
import os
import unittest

from core.calepinage.moteur import (
    capacite_theorique,
    compter_plan,
    compter_rangee,
    compter_troncon,
    segments_libres,
)
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.surfaces.arc import SurfaceArc, arc_frdisi
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Obstacle,
    Provenance,
    Rives,
    TypeObstacle,
)

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)

# ------------------------------------------------------ bâtiment C (école)
#: ``x`` = le long des rangées (51,10) · ``y`` = transversal (25,62)
ECOLE_OBSTACLES = (
    Obstacle(repere="NIVEAU", x0=31.74, x1=31.74, y0=0.0, y1=25.62,
             type_obstacle=TypeObstacle.JOINT_DILATATION,
             provenance=Provenance.RELEVE, degagement_m=0.30),
    Obstacle(repere="JOG", x0=31.29, x1=31.74, y0=13.18, y1=14.09,
             type_obstacle=TypeObstacle.ACROTERE,
             provenance=Provenance.RELEVE, degagement_m=0.30),
    Obstacle(repere="CAGE", x0=22.92, x1=31.74, y0=14.09, y1=18.20,
             type_obstacle=TypeObstacle.CAGE_ESCALIER,
             provenance=Provenance.RELEVE),
    Obstacle(repere="LOCAL", x0=10.50, x1=15.00, y0=13.95, y1=18.13,
             type_obstacle=TypeObstacle.EDICULE,
             provenance=Provenance.RELEVE),
    # gêne « clim probable » : emprise gonflée de 0,20 (dégagement 0,50 tenu)
    Obstacle(repere="GENE", x0=13.30, x1=14.70, y0=19.12, y1=24.30,
             type_obstacle=TypeObstacle.CLIMATISEUR,
             provenance=Provenance.DECLARE_CLIENT, degagement_m=0.30),
)
ECOLE_RANGEES = (0.35, 6.95, 13.55, 20.15)


def _ecole():
    return SurfaceRectangle(repere="BAT_C_ECOLE", longueur_m=51.10,
                            largeur_m=25.62, rives=RIVES_AO)


class LEcoleRedonne314(unittest.TestCase):
    """Compte IDENTIQUE au script d'origine (planche définitive : 314)."""

    def test_le_total_de_l_ecole(self):
        plan = compter_plan(_ecole(),
                            tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
                            appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(plan.modules, 314)

    def test_le_detail_par_rangee(self):
        surface, obs = _ecole(), appliquer_regles(ECOLE_OBSTACLES)
        attendus = (86, 86, 60, 82)
        for y0, attendu in zip(ECOLE_RANGEES, attendus):
            rangee = compter_rangee(surface, y0, KIT_AO_PORTRAIT, obs)
            self.assertEqual(rangee.modules, attendu,
                             "rangée %.2f" % y0)

    def test_la_coupure_de_niveau_scinde_la_rangee_en_deux_troncons(self):
        troncons = segments_libres(_ecole(), 0.35, KIT_AO_PORTRAIT,
                                   appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(len(troncons), 2)
        self.assertAlmostEqual(troncons[0][0], 0.35, delta=1e-9)
        self.assertAlmostEqual(troncons[0][1], 31.44, delta=1e-9)
        self.assertAlmostEqual(troncons[1][0], 32.04, delta=1e-9)
        self.assertAlmostEqual(troncons[1][1], 50.75, delta=1e-9)

    def test_la_rangee_porte_son_kit_et_sa_surface(self):
        rangee = compter_rangee(_ecole(), 0.35, KIT_AO_PORTRAIT,
                                appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(rangee.kit_code, "AO_PORTRAIT")
        self.assertEqual(rangee.surface_repere, "BAT_C_ECOLE")
        self.assertAlmostEqual(rangee.y1, 0.35 + KIT_AO_PORTRAIT.emprise_transversale_m)

    def test_retirer_la_gene_ne_peut_pas_faire_perdre(self):
        surface = _ecole()
        avec = compter_plan(surface,
                            tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
                            appliquer_regles(ECOLE_OBSTACLES)).modules
        sans = compter_plan(
            surface, tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
            appliquer_regles(tuple(o for o in ECOLE_OBSTACLES
                                   if o.repere != "GENE"))).modules
        self.assertGreaterEqual(sans, avec)


class CompteurGenerique(unittest.TestCase):
    def test_compter_troncon(self):
        self.assertEqual(compter_troncon(10.0, 1.134, 2), 16)
        self.assertEqual(compter_troncon(0.5, 1.134, 2), 0)

    def test_rangee_sans_obstacle(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=10.0,
                                   rives=RIVES_AO)
        rangee = compter_rangee(surface, 0.35, KIT_AO_PAYSAGE)
        # 20,00 - 2 × 0,35 = 19,30 ; 19,30 / 2,382 = 8 pas
        self.assertEqual(rangee.modules, 16)

    def test_rangee_hors_surface_rend_zero(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=5.0,
                                   rives=RIVES_AO)
        self.assertEqual(compter_rangee(surface, 4.0, KIT_AO_PORTRAIT).modules, 0)

    def test_le_moteur_marche_sur_un_polygone(self):
        contour = ((10.76, 0.0), (10.76, 47.08), (0.0, 47.08),
                   (0.0, 11.2), (-29.74, 11.2), (-29.74, 0.0))
        surface = SurfacePolygone(repere="AILE_L", contour=contour,
                                  rives=RIVES_AO)
        rangee = compter_rangee(surface, 0.35, KIT_AO_PORTRAIT)
        # rangée traversante : 40,50 - 0,70 = 39,80 ; 39,80 / 1,134 = 35 pas
        self.assertEqual(rangee.modules, 70)

    def test_le_moteur_marche_sur_l_arc_avec_le_pas_corrige(self):
        arc = arc_frdisi(rives=RIVES_AO)
        rangee = compter_rangee(arc, 0.80, KIT_AO_PAYSAGE)
        self.assertGreater(rangee.modules, 0)
        # 3 tronçons : les 2 murets coupent l'arc
        self.assertEqual(len(rangee.troncons), 3)

    def test_le_pas_corrige_de_l_arc_coute_des_modules(self):
        """Le recouvrement évité a un prix — assumé et VÉRIFIÉ.

        Sur une rangée d'un seul tenant (68,05 développés), la correction de
        pas coûte exactement un pas : 28 tables jointives en abscisse contre
        27 tables qui ne se recouvrent pas au rayon intérieur.
        """
        arc = SurfaceArc(repere="ARC_ENTIER", rives=RIVES_AO)
        plat = SurfaceRectangle(repere="PLAT", longueur_m=arc.developpe_m,
                                largeur_m=arc.largeur_m, rives=RIVES_AO)
        corrige = compter_rangee(arc, 0.80, KIT_AO_PAYSAGE).modules
        jointif = compter_rangee(plat, 0.80, KIT_AO_PAYSAGE).modules
        self.assertEqual((corrige, jointif), (54, 56))
        self.assertLess(corrige, jointif)

    def test_capacite_theorique_borne_par_le_haut(self):
        surface = _ecole()
        obs = appliquer_regles(ECOLE_OBSTACLES)
        plan = compter_plan(surface,
                            tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
                            obs)
        self.assertGreaterEqual(capacite_theorique(surface, KIT_AO_PORTRAIT, obs),
                                plan.modules)


class LeMoteurNePosePas(unittest.TestCase):
    """Test EXIGÉ : ``moteur`` n'importe JAMAIS ``poseur``."""

    def _imports(self, chemin):
        with open(chemin, "r", encoding="utf-8") as fh:
            arbre = ast.parse(fh.read(), filename=chemin)
        noms = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                noms.extend(a.name for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                noms.append(noeud.module or "")
        return noms

    def test_moteur_n_importe_pas_poseur(self):
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "calepinage", "moteur.py")
        for nom in self._imports(chemin):
            self.assertNotIn("poseur", nom,
                             "moteur.py ne doit JAMAIS importer poseur")

    def test_le_moteur_ne_rend_aucune_table(self):
        plan = compter_plan(_ecole(),
                            tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
                            appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(plan.tables, ())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
