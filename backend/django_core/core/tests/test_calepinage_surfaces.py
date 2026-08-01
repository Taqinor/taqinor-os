# -*- coding: utf-8 -*-
"""AOF38 — protocole ``Surface`` + SUITE DE CONFORMITÉ réutilisable.

``ConformiteSurface`` est un MIXIN (volontairement pas un ``TestCase`` : la
découverte ne doit pas l'exécuter seul). Toute surface future — polygone, arc,
multi-niveaux, adaptateur villa — hérite de ce mixin dans SON fichier de test
et hérite du coup de tous les contrôles du protocole.
"""

import unittest

from core.calepinage.surfaces.base import CONFORMITE_METHODES, Coupure, Surface
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import KIT_AO_PORTRAIT, Axe, Rives


class ConformiteSurface(object):
    """Suite de conformité : à hériter avec ``unittest.TestCase``.

    La sous-classe fournit ``surface()`` et ``y_valide()``.
    """

    def surface(self):                       # pragma: no cover - contrat
        raise NotImplementedError

    def y_valide(self):                      # pragma: no cover - contrat
        raise NotImplementedError

    def kit(self):
        return KIT_AO_PORTRAIT

    # --------------------------------------------------------------- contrôles
    def test_conformite_expose_les_six_methodes(self):
        s = self.surface()
        for nom in CONFORMITE_METHODES:
            self.assertTrue(callable(getattr(s, nom, None)),
                            "méthode de protocole absente : %s" % nom)

    def test_conformite_axe_progression_est_un_axe(self):
        self.assertIsInstance(self.surface().axe_progression(), Axe)

    def test_conformite_bande_est_ordonnee(self):
        s = self.surface()
        bornes = s.bande(self.y_valide(), self.kit().emprise_transversale_m)
        self.assertIsNotNone(bornes, "la bande de référence doit exister")
        self.assertLess(bornes[0], bornes[1])

    def test_conformite_bande_hors_surface_rend_none(self):
        s = self.surface()
        ymin, ymax = s.bornes_transversales()
        self.assertIsNone(s.bande(ymax + 100.0,
                                  self.kit().emprise_transversale_m))

    def test_conformite_longueur_utile_est_positive_et_bornee(self):
        s = self.surface()
        y0 = self.y_valide()
        emprise = self.kit().emprise_transversale_m
        bornes = s.bande(y0, emprise)
        utile = s.longueur_utile(y0, emprise)
        self.assertGreaterEqual(utile, 0.0)
        self.assertLessEqual(utile, bornes[1] - bornes[0] + 1e-9)

    def test_conformite_pas_de_pose_couvre_la_table(self):
        s = self.surface()
        pas = s.pas_de_pose(self.kit(), self.y_valide())
        self.assertGreater(pas, 0.0)
        self.assertGreaterEqual(pas, self.kit().cote_le_long_rangee_m - 1e-9)

    def test_conformite_vers_feuille_rend_un_couple(self):
        point = self.surface().vers_feuille((1.0, 2.0))
        self.assertEqual(len(point), 2)
        self.assertIsInstance(point[0], float)
        self.assertIsInstance(point[1], float)

    def test_conformite_vers_feuille_est_injective(self):
        s = self.surface()
        self.assertNotEqual(s.vers_feuille((1.0, 2.0)), s.vers_feuille((3.0, 2.0)))

    def test_conformite_coupures_est_un_tuple(self):
        self.assertIsInstance(self.surface().coupures(), tuple)

    def test_conformite_bornes_utiles_retirent_les_rives(self):
        s = self.surface()
        ymin, ymax = s.bornes_transversales()
        umin, umax = s.bornes_transversales_utiles()
        self.assertGreaterEqual(umin, ymin - 1e-9)
        self.assertLessEqual(umax, ymax + 1e-9)


class RectangleEstConforme(ConformiteSurface, unittest.TestCase):
    """Le bâtiment C de FRDISI : 51,10 le long des rangées × 25,62 transversal."""

    def surface(self):
        return SurfaceRectangle(repere="ECOLE", longueur_m=51.10,
                                largeur_m=25.62,
                                rives=Rives(laterale_m=0.35, extremite_m=0.35))

    def y_valide(self):
        return 0.35


class RectangleGeometrie(unittest.TestCase):
    def test_bande_couvre_toute_la_longueur(self):
        s = SurfaceRectangle(repere="R", longueur_m=51.10, largeur_m=25.62,
                             rives=Rives(laterale_m=0.35, extremite_m=0.35))
        self.assertEqual(s.bande(0.35, 4.70), (0.0, 51.10))
        self.assertAlmostEqual(s.longueur_utile(0.35, 4.70), 50.40)

    def test_rangee_qui_deborde_lateralement_est_refusee(self):
        s = SurfaceRectangle(repere="R", longueur_m=10.0, largeur_m=5.0,
                             rives=Rives(laterale_m=0.35, extremite_m=0.35))
        self.assertIsNone(s.bande(4.50, 4.70))
        self.assertIsNone(s.bande(0.10, 4.70))

    def test_aire(self):
        self.assertAlmostEqual(
            SurfaceRectangle(repere="R", longueur_m=4.0, largeur_m=3.0).aire_m2,
            12.0)

    def test_dimensions_invalides(self):
        with self.assertRaises(ValueError):
            SurfaceRectangle(repere="R", longueur_m=0.0, largeur_m=3.0)


class CoupuresDuProtocole(unittest.TestCase):
    def test_troncons_entre_coupures(self):
        s = SurfaceRectangle(
            repere="ARC", longueur_m=68.05, largeur_m=10.90,
            coupures_declarees=(Coupure(repere="J1", axe="x", position=20.775,
                                        epaisseur_m=0.45),
                                Coupure(repere="J2", axe="x", position=44.225,
                                        epaisseur_m=0.45)))
        morceaux = s.troncons_entre_coupures((0.0, 68.05))
        self.assertEqual(len(morceaux), 3)
        self.assertAlmostEqual(morceaux[0][1] - morceaux[0][0], 20.55, delta=1e-9)
        self.assertAlmostEqual(morceaux[1][1] - morceaux[1][0], 23.00, delta=1e-9)
        self.assertAlmostEqual(morceaux[2][1] - morceaux[2][0], 23.60, delta=1e-9)

    def test_une_table_a_cheval_est_detectee(self):
        s = SurfaceRectangle(
            repere="ECOLE", longueur_m=51.10, largeur_m=25.62,
            coupures_declarees=(Coupure(repere="NIVEAU", axe="x",
                                        position=31.74),))
        self.assertTrue(s.enjambe_une_coupure(31.0, 32.0))
        self.assertFalse(s.enjambe_une_coupure(29.0, 30.0))

    def test_axe_de_coupure_invalide(self):
        with self.assertRaises(ValueError):
            Coupure(repere="X", axe="z", position=1.0)


class ProtocoleAbstrait(unittest.TestCase):
    def test_surface_de_base_n_est_pas_utilisable_telle_quelle(self):
        s = Surface(repere="ABSTRAITE")
        with self.assertRaises(NotImplementedError):
            s.bornes_transversales()
        with self.assertRaises(NotImplementedError):
            s.bande(0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
