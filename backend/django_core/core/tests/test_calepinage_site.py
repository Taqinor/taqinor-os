# -*- coding: utf-8 -*-
"""AOF41 — multi-niveaux (aucune table à cheval) + agrégation de SITE calculée."""

import unittest

from core.calepinage.site import (
    AgregatSite,
    CompteSurface,
    Deport,
    Site,
    agreger,
)
from core.calepinage.surfaces.multi import Palier, SurfaceMultiNiveaux
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import Rives
from core.tests.test_calepinage_surfaces import ConformiteSurface

RIVES = Rives(laterale_m=0.35, extremite_m=0.35)


def _ecole():
    """Bâtiment C : 51,10 le long des rangées, ligne interne à 31,74."""
    return SurfaceMultiNiveaux(
        repere="ECOLE", largeur_m=25.62, rives=RIVES,
        paliers=(Palier(repere="BAS", x0=0.0, x1=31.74, niveau=0),
                 Palier(repere="HAUT", x0=31.74, x1=51.10, niveau=1)))


class MultiNiveauxEstConforme(ConformiteSurface, unittest.TestCase):
    def surface(self):
        return _ecole()

    def y_valide(self):
        return 0.35


class AucuneTableACheval(unittest.TestCase):
    def test_l_ecole_a_deux_niveaux_et_une_coupure(self):
        s = _ecole()
        self.assertEqual(s.niveaux, (0, 1))
        self.assertEqual(len(s.coupures()), 1)
        self.assertAlmostEqual(s.coupures()[0].position, 31.74, delta=1e-9)

    def test_une_table_a_cheval_sur_la_coupure_est_refusee(self):
        s = _ecole()
        self.assertTrue(s.table_a_cheval(31.20, 32.34))
        self.assertFalse(s.table_a_cheval(30.00, 31.13))
        self.assertFalse(s.table_a_cheval(31.74, 32.87))

    def test_une_table_hors_surface_est_refusee(self):
        s = _ecole()
        self.assertTrue(s.table_a_cheval(50.60, 52.00))

    def test_palier_de(self):
        s = _ecole()
        self.assertEqual(s.palier_de(10.0).repere, "BAS")
        self.assertEqual(s.palier_de(40.0).repere, "HAUT")
        self.assertIsNone(s.palier_de(100.0))

    def test_deux_paliers_de_meme_niveau_ne_creent_pas_de_coupure(self):
        s = SurfaceMultiNiveaux(
            repere="PLAT", largeur_m=10.0,
            paliers=(Palier(repere="A", x0=0.0, x1=10.0, niveau=0),
                     Palier(repere="B", x0=10.0, x1=20.0, niveau=0)))
        self.assertEqual(s.coupures(), ())
        self.assertFalse(s.table_a_cheval(9.5, 10.5))

    def test_paliers_qui_se_chevauchent_refuses(self):
        with self.assertRaises(ValueError):
            SurfaceMultiNiveaux(
                repere="X", largeur_m=10.0,
                paliers=(Palier(repere="A", x0=0.0, x1=10.0),
                         Palier(repere="B", x0=5.0, x1=20.0, niveau=1)))

    def test_surface_sans_palier_refusee(self):
        with self.assertRaises(ValueError):
            SurfaceMultiNiveaux(repere="X", largeur_m=10.0, paliers=())

    def test_aire_multi_niveaux(self):
        self.assertAlmostEqual(_ecole().aire_m2, 51.10 * 25.62, delta=1e-6)

    def test_palier_invalide(self):
        with self.assertRaises(ValueError):
            Palier(repere="X", x0=5.0, x1=5.0)


class TotalDuSiteCalcule(unittest.TestCase):
    """FRDISI : 152 + 120 + 288 = 560."""

    def _comptes(self):
        return (CompteSurface(repere="BAT_A", modules=152),
                CompteSurface(repere="BAT_B", modules=120),
                CompteSurface(repere="BAT_C", modules=288))

    def test_somme_des_batiments_egale_le_total(self):
        site = Site(repere="FRDISI", engagement_modules=560)
        agregat = agreger(site, self._comptes())
        self.assertEqual(agregat.modules, 560)
        self.assertEqual(agregat.modules,
                         sum(c.modules for c in agregat.comptes))
        self.assertTrue(agregat.tenu)

    def test_le_total_n_est_jamais_recopie(self):
        """``modules`` est une PROPRIÉTÉ : impossible de la figer à la main."""
        self.assertFalse(hasattr(AgregatSite("S", ()), "__dict__")
                         and "modules" in AgregatSite("S", ()).__dict__)
        with self.assertRaises(AttributeError):
            AgregatSite("S", ()).modules = 999

    def test_kwc_calcule(self):
        agregat = agreger(Site(repere="FRDISI"), self._comptes())
        self.assertAlmostEqual(agregat.kwc, 560 * 0.625, delta=1e-9)

    def test_engagement_non_tenu(self):
        site = Site(repere="FRDISI", engagement_modules=600)
        self.assertFalse(agreger(site, self._comptes()).tenu)

    def test_reperes_dupliques_refuses(self):
        with self.assertRaises(ValueError):
            agreger(Site(repere="S"), (CompteSurface("A", 10),
                                       CompteSurface("A", 20)))

    def test_compte_par_repere(self):
        agregat = agreger(Site(repere="S"), self._comptes())
        self.assertEqual(agregat.compte("BAT_B").modules, 120)
        with self.assertRaises(KeyError):
            agregat.compte("BAT_Z")

    def test_une_surface_non_engageable_contamine_le_site(self):
        agregat = agreger(Site(repere="S"), (
            CompteSurface(repere="A", modules=10),
            CompteSurface(repere="B", modules=10, engageable=False,
                          motifs=("PAN — emprise issue du PLAN",)),
        ))
        self.assertFalse(agregat.engageable)


class ContraintesInterSurfaces(unittest.TestCase):
    def test_un_plafond_kwc_ampute_la_surface_avec_un_motif_nomme(self):
        site = Site(repere="FRDISI", plafond_kwc_par_surface=60.0)
        agregat = agreger(site, (CompteSurface(repere="BAT_B", modules=120),))
        self.assertEqual(agregat.compte("BAT_B").modules, 96)   # 60 kWc
        self.assertTrue(agregat.motifs)
        self.assertIn("BAT_B", agregat.motifs[0])
        self.assertFalse(agregat.engageable)

    def test_le_deport_conserve_le_total_du_site(self):
        site = Site(repere="FRDISI",
                    deports=(Deport(depuis="BAT_B", vers="BAT_A", modules=24,
                                    motif="onduleur ≤ 60 kWc"),))
        agregat = agreger(site, (CompteSurface(repere="BAT_A", modules=152),
                                 CompteSurface(repere="BAT_B", modules=120)))
        self.assertEqual(agregat.compte("BAT_A").modules, 176)
        self.assertEqual(agregat.compte("BAT_B").modules, 96)
        self.assertEqual(agregat.modules, 272)

    def test_deport_impossible_leve(self):
        site = Site(repere="S", deports=(Deport(depuis="A", vers="B",
                                                modules=500),))
        with self.assertRaises(ValueError):
            agreger(site, (CompteSurface("A", 10), CompteSurface("B", 10)))

    def test_deport_vers_batiment_inconnu_leve(self):
        site = Site(repere="S", deports=(Deport(depuis="A", vers="Z",
                                                modules=1),))
        with self.assertRaises(KeyError):
            agreger(site, (CompteSurface("A", 10),))

    def test_deport_degenere_refuse(self):
        with self.assertRaises(ValueError):
            Deport(depuis="A", vers="A", modules=1)
        with self.assertRaises(ValueError):
            Deport(depuis="A", vers="B", modules=0)

    def test_site_expose_les_reperes_de_ses_surfaces(self):
        site = Site(repere="S", surfaces=(
            SurfaceRectangle(repere="R1", longueur_m=10.0, largeur_m=5.0),))
        self.assertEqual(site.reperes, ("R1",))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
