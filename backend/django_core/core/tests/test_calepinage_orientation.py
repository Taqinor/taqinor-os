# -*- coding: utf-8 -*-
"""AOF45 — le moteur refuse une orientation inconstructible, sur TOUS les chemins."""

import unittest

from core.calepinage.orientation import (
    ErreurOrientation,
    axe_rangee_impose,
    motif_orientation,
    parametres_avec_axe_derive,
    verifier,
    verifier_kit,
)
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    KIT_VILLA_720,
    Axe,
    Parametres,
    Rives,
)

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)


class AxeImposeParLeKit(unittest.TestCase):
    def test_une_table_dos_a_dos_impose_des_rangees_nord_sud(self):
        self.assertIs(axe_rangee_impose(KIT_AO_PORTRAIT), Axe.NORD_SUD)
        self.assertIs(axe_rangee_impose(KIT_AO_PAYSAGE), Axe.NORD_SUD)

    def test_un_module_unique_plein_sud_impose_des_rangees_est_ouest(self):
        self.assertIs(axe_rangee_impose(KIT_VILLA_720, 180.0), Axe.EST_OUEST)
        self.assertIs(axe_rangee_impose(KIT_VILLA_720, 0.0), Axe.EST_OUEST)

    def test_un_module_unique_plein_est_impose_des_rangees_nord_sud(self):
        self.assertIs(axe_rangee_impose(KIT_VILLA_720, 90.0), Axe.NORD_SUD)
        self.assertIs(axe_rangee_impose(KIT_VILLA_720, 270.0), Axe.NORD_SUD)


class LeCasHistoriqueDeLaBarreA(unittest.TestCase):
    """La v1 avait calepiné la barre en rangées E-O : modules face NORD."""

    def test_rangees_est_ouest_avec_une_table_dos_a_dos_levent(self):
        with self.assertRaises(ErreurOrientation) as ctx:
            verifier_kit(KIT_AO_PORTRAIT, Axe.EST_OUEST)
        message = str(ctx.exception)
        self.assertIn("dos-à-dos", message)
        self.assertIn("NORD_SUD", message)
        self.assertIn("inconstructible", message)

    def test_rangees_nord_sud_passent(self):
        self.assertIs(verifier_kit(KIT_AO_PORTRAIT, Axe.NORD_SUD), Axe.NORD_SUD)

    def test_le_motif_est_genere_et_nomme_le_kit(self):
        motif = motif_orientation(KIT_AO_PAYSAGE, Axe.EST_OUEST)
        self.assertIn("AO_PAYSAGE", motif)


class LAoEtLaVillaPassentLaMemePorte(unittest.TestCase):
    def test_l_ao_est_verifie_avant_tout_calcul(self):
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                axe_rangee=Axe.EST_OUEST)
        with self.assertRaises(ErreurOrientation):
            verifier(parametres)

    def test_la_villa_est_verifiee_par_la_meme_fonction(self):
        parametres = Parametres(kits=(KIT_VILLA_720,), rives=RIVES_AO,
                                axe_rangee=Axe.NORD_SUD)
        surface = SurfaceRectangle(repere="VILLA", longueur_m=12.0,
                                   largeur_m=8.0, rives=RIVES_AO,
                                   axe_rangee=Axe.NORD_SUD, azimut_deg=180.0)
        with self.assertRaises(ErreurOrientation):
            verifier(parametres, (surface,))

    def test_la_villa_plein_sud_en_rangees_est_ouest_passe(self):
        parametres = Parametres(kits=(KIT_VILLA_720,), rives=RIVES_AO,
                                axe_rangee=Axe.EST_OUEST)
        surface = SurfaceRectangle(repere="VILLA", longueur_m=12.0,
                                   largeur_m=8.0, rives=RIVES_AO,
                                   axe_rangee=Axe.EST_OUEST, azimut_deg=180.0)
        self.assertTrue(verifier(parametres, (surface,)))

    def test_une_surface_d_axe_divergent_leve(self):
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                axe_rangee=Axe.NORD_SUD)
        surface = SurfaceRectangle(repere="BARRE", longueur_m=47.08,
                                   largeur_m=10.76, rives=RIVES_AO,
                                   axe_rangee=Axe.EST_OUEST)
        with self.assertRaises(ErreurOrientation) as ctx:
            verifier(parametres, (surface,))
        self.assertIn("BARRE", str(ctx.exception))


class AxeDerive(unittest.TestCase):
    def test_l_axe_est_derive_des_kits(self):
        parametres = Parametres(kits=(KIT_AO_PORTRAIT, KIT_AO_PAYSAGE),
                                rives=RIVES_AO, axe_rangee=Axe.EST_OUEST)
        corrige = parametres_avec_axe_derive(parametres)
        self.assertIs(corrige.axe_rangee, Axe.NORD_SUD)
        self.assertTrue(verifier(corrige))

    def test_kits_d_axes_incompatibles_levent(self):
        parametres = Parametres(kits=(KIT_AO_PORTRAIT, KIT_VILLA_720),
                                rives=RIVES_AO)
        with self.assertRaises(ErreurOrientation):
            parametres_avec_axe_derive(parametres, azimut_deg=180.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
