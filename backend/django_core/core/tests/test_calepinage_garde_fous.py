# -*- coding: utf-8 -*-
"""AOF51 — la PORTE : ``valider(plan)`` refuse tout ce qui n'est pas publiable."""

import unittest

from core.calepinage.exceptions import CalepinageIncoherent, ErreurCalepinage
from core.calepinage.garde_fous import (
    CONTROLES,
    polygones_se_chevauchent,
    valider,
)
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.poseur import poser_plan
from core.calepinage.surfaces.multi import Palier, SurfaceMultiNiveaux
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Axe,
    MethodePreuve,
    Obstacle,
    Parametres,
    Preuve,
    Provenance,
    Rives,
    Table,
    remplacer,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES, ECOLE_RANGEES
from core.tests.test_calepinage_pose_uniforme import (
    ARC_RANGEES,
    obstacles_arc,
    segment_arc,
)

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)


def _ecole():
    return SurfaceRectangle(repere="BAT_C_ECOLE", longueur_m=51.10,
                            largeur_m=25.62, rives=RIVES_AO)


def _parametres(kits=(KIT_AO_PORTRAIT,)):
    return Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                      pas_recherche_m=0.01)


def _rangees_ecole():
    return tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES)


class UnPlanValidePasse(unittest.TestCase):
    def test_l_ecole_passe_les_dix_controles(self):
        rapport = valider(_ecole(), _parametres(), _rangees_ecole(),
                          appliquer_regles(ECOLE_OBSTACLES))
        self.assertTrue(rapport.ok, rapport.echecs)
        for controle in ("orientation", "dessine_egale_compte",
                         "non_chevauchement", "rive_laterale",
                         "rive_extremite", "degagement_obstacle", "coupure",
                         "hors_developpe"):
            self.assertIn(controle, rapport.controles_passes)

    def test_l_arc_passe_avec_ses_tables_rigides(self):
        surface = segment_arc("S2", RIVES_AO)
        rapport = valider(surface, _parametres((KIT_AO_PAYSAGE,)),
                          tuple((y, KIT_AO_PAYSAGE)
                                for y in ARC_RANGEES["S2"]),
                          obstacles_arc("S2"))
        self.assertTrue(rapport.ok, rapport.echecs)

    def test_la_liste_des_controles_est_publiee(self):
        self.assertIn("non_chevauchement", CONTROLES)
        self.assertEqual(len(CONTROLES), 10)


class LeSATAttrapeUnDecalageDUnCentimetre(unittest.TestCase):
    """Exigence dure : 1 cm de décalage sur une table fait échouer le SAT."""

    def test_decalage_d_un_centimetre(self):
        surface, obstacles = _ecole(), appliquer_regles(ECOLE_OBSTACLES)
        tables = list(poser_plan(surface, _rangees_ecole(), obstacles))
        premiere = tables[0]
        tables[1] = Table(x0=tables[1].x0 - 0.01, x1=tables[1].x1 - 0.01,
                          y0=tables[1].y0, y1=tables[1].y1,
                          kit_code=tables[1].kit_code,
                          surface_repere=tables[1].surface_repere,
                          polygone=((tables[1].x0 - 0.01, tables[1].y0),
                                    (tables[1].x1 - 0.01, tables[1].y0),
                                    (tables[1].x1 - 0.01, tables[1].y1),
                                    (tables[1].x0 - 0.01, tables[1].y1)),
                          pas_m=tables[1].pas_m)
        self.assertIsNotNone(premiere)
        with self.assertRaises(CalepinageIncoherent) as ctx:
            valider(surface, _parametres(), _rangees_ecole(), obstacles,
                    tables=tuple(tables))
        self.assertEqual(ctx.exception.controle, "non_chevauchement")

    def test_le_sat_sur_deux_rectangles(self):
        a = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        b = ((0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5))
        loin = ((2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 3.0))
        self.assertTrue(polygones_se_chevauchent(a, b))
        self.assertFalse(polygones_se_chevauchent(a, loin))

    def test_le_sat_sur_deux_rectangles_jointifs(self):
        a = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        colle = ((1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0))
        self.assertFalse(polygones_se_chevauchent(a, colle))

    def test_le_sat_sur_deux_polygones_tournes(self):
        """Le cas de l'arc : deux repères tangents différents."""
        a = ((0.0, 0.0), (1.0, 0.1), (0.9, 1.1), (-0.1, 1.0))
        b = ((0.8, 0.0), (1.8, 0.2), (1.6, 1.2), (0.6, 1.0))
        self.assertTrue(polygones_se_chevauchent(a, b))

    def test_polygone_degenere(self):
        self.assertFalse(polygones_se_chevauchent(((0.0, 0.0),), ((1.0, 1.0),)))


class LesControlesNommes(unittest.TestCase):
    def test_retirer_le_degagement_d_un_obstacle_fait_echouer_le_controle(self):
        surface = _ecole()
        obstacles = appliquer_regles(ECOLE_OBSTACLES)
        tables = poser_plan(surface, _rangees_ecole(), obstacles)
        # on rejoue la validation avec un obstacle GONFLÉ : le plan posé sans
        # ce dégagement viole désormais le contrôle NOMMÉ
        gonfles = appliquer_regles(tuple(
            remplacer(o, degagement_m=1.50) for o in ECOLE_OBSTACLES))
        rapport = valider(surface, _parametres(), _rangees_ecole(), gonfles,
                          tables=tables, strict=False)
        self.assertFalse(rapport.ok)
        fautifs = [e for e in rapport.echecs
                   if e.controle == "degagement_obstacle"]
        self.assertTrue(fautifs, rapport.echecs)
        self.assertTrue(fautifs[0].repere)
        self.assertIn("dégagement", fautifs[0].message)

    def test_une_orientation_inconstructible_est_refusee(self):
        parametres = remplacer(_parametres(), axe_rangee=Axe.EST_OUEST)
        with self.assertRaises(CalepinageIncoherent) as ctx:
            valider(_ecole(), parametres, _rangees_ecole(),
                    appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(ctx.exception.controle, "orientation")

    def test_une_preuve_qui_ment_est_refusee(self):
        preuve = Preuve(methode=MethodePreuve.DP_EXACT_1CM,
                        pas_recherche_m=0.01, compte_retenu=999,
                        compte_optimal=999)
        with self.assertRaises(CalepinageIncoherent) as ctx:
            valider(_ecole(), _parametres(), _rangees_ecole(),
                    appliquer_regles(ECOLE_OBSTACLES), preuve=preuve)
        self.assertEqual(ctx.exception.controle, "compte_annonce")

    def test_une_table_a_cheval_sur_un_niveau_est_refusee(self):
        surface = SurfaceMultiNiveaux(
            repere="ECOLE", largeur_m=25.62, rives=RIVES_AO,
            paliers=(Palier(repere="BAS", x0=0.0, x1=25.0, niveau=0),
                     Palier(repere="HAUT", x0=25.0, x1=51.10, niveau=1)))
        rapport = valider(
            surface, _parametres(), ((0.35, KIT_AO_PORTRAIT),),
            tables=(Table(x0=24.50, x1=25.634, y0=0.35, y1=5.05,
                          kit_code="AO_PORTRAIT"),), strict=False)
        self.assertFalse(rapport.ok)
        self.assertIn("coupure", [e.controle for e in rapport.echecs])

    def test_une_table_hors_developpe_est_refusee(self):
        with self.assertRaises(CalepinageIncoherent) as ctx:
            valider(_ecole(), _parametres(), ((0.35, KIT_AO_PORTRAIT),),
                    tables=(Table(x0=60.0, x1=61.134, y0=0.35, y1=5.05,
                                  kit_code="AO_PORTRAIT"),))
        self.assertIn(ctx.exception.controle,
                      ("rive_extremite", "dessine_egale_compte"))

    def test_une_table_hors_rive_laterale_est_refusee(self):
        with self.assertRaises(CalepinageIncoherent) as ctx:
            valider(_ecole(), _parametres(), ((0.35, KIT_AO_PORTRAIT),),
                    tables=(Table(x0=1.0, x1=2.134, y0=0.05, y1=4.75,
                                  kit_code="AO_PORTRAIT"),))
        self.assertIn(ctx.exception.controle,
                      ("rive_laterale", "dessine_egale_compte"))


class ProvenanceEtEngagement(unittest.TestCase):
    def test_une_emprise_devinee_interdit_un_compte_engage(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        obstacles = appliquer_regles((
            Obstacle(repere="GRECT", x0=8.0, x1=9.0, y0=0.0, y1=1.0,
                     provenance=Provenance.DEVINE),))
        rapport = valider(surface, _parametres(), ((0.35, KIT_AO_PORTRAIT),),
                          obstacles, engage=False)
        self.assertTrue(rapport.ok, rapport.echecs)
        with self.assertRaises(CalepinageIncoherent) as ctx:
            valider(surface, _parametres(), ((0.35, KIT_AO_PORTRAIT),),
                    obstacles, engage=True)
        self.assertEqual(ctx.exception.controle, "provenance_engageable")

    def test_le_mode_non_strict_rend_tous_les_echecs(self):
        parametres = remplacer(_parametres(), axe_rangee=Axe.EST_OUEST)
        rapport = valider(_ecole(), parametres, _rangees_ecole(),
                          appliquer_regles(ECOLE_OBSTACLES), strict=False)
        self.assertFalse(rapport.ok)
        self.assertEqual(rapport.premier().controle, "orientation")

    def test_l_exception_est_une_erreur_de_calepinage(self):
        self.assertTrue(issubclass(CalepinageIncoherent, ErreurCalepinage))
        erreur = CalepinageIncoherent("coupure", "T1", "à cheval")
        self.assertIn("coupure", str(erreur))
        self.assertIn("T1", str(erreur))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
