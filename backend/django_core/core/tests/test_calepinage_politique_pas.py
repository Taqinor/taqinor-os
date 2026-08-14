# -*- coding: utf-8 -*-
"""AOF46 — politique de pas injectable : non-régression AO + pas villa variable."""

import math
import unittest

from core.calepinage.optimum import optimiser
from core.calepinage.politique_pas import (
    ELEVATION_DIMENSIONNEMENT_DEG,
    ELEVATION_PLANCHER_DEG,
    Affleurant,
    AlleeFixe,
    AntiOmbrage,
    politique_par_defaut,
    position_solaire_solstice,
)
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PORTRAIT,
    KIT_VILLA_720,
    Axe,
    Parametres,
    Rives,
)
from core.calepinage.version import VERSION_MOTEUR, version_tuple

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)


class NonRegressionAO(unittest.TestCase):
    """L'AO redonne STRICTEMENT les mêmes comptes avec ``AlleeFixe``."""

    def _surface(self):
        return SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                largeur_m=25.62, rives=RIVES_AO)

    def _parametres(self):
        return Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                          allee_m=0.60, pas_recherche_m=0.01)

    def test_scalaire_et_politique_donnent_le_meme_compte(self):
        surface, parametres = self._surface(), self._parametres()
        sans = optimiser(surface, parametres)
        avec = optimiser(surface, parametres, politique=AlleeFixe(0.60))
        self.assertEqual(sans.modules, avec.modules)
        self.assertEqual(sans.rangees, avec.rangees)

    def test_la_politique_par_defaut_est_une_allee_fixe(self):
        politique = politique_par_defaut(self._parametres())
        self.assertIsInstance(politique, AlleeFixe)
        self.assertAlmostEqual(politique.allee_m, 0.60)
        self.assertAlmostEqual(
            politique.pas_apres_rangee(KIT_AO_PORTRAIT, 0.35), 0.60)

    def test_une_allee_plus_large_ne_peut_pas_gagner_de_rangee(self):
        surface, parametres = self._surface(), self._parametres()
        etroite = optimiser(surface, parametres, politique=AlleeFixe(0.60))
        large = optimiser(surface, parametres, politique=AlleeFixe(1.90))
        self.assertLessEqual(large.modules, etroite.modules)

    def test_allee_negative_refusee(self):
        with self.assertRaises(ValueError):
            AlleeFixe(-0.1)


class AntiOmbrageVilla(unittest.TestCase):
    """Le calcul de référence : profondeur projetée + ombre + marge."""

    def _reference(self, kit, elevation_deg, marge):
        cote = kit.cote_dans_la_pente_m
        inclinaison = math.radians(kit.inclinaison_deg)
        profondeur = cote * math.cos(inclinaison)
        hauteur = cote * math.sin(inclinaison)
        ombre = hauteur / math.tan(math.radians(elevation_deg))
        return profondeur + ombre + marge

    def test_le_pas_de_rangee_villa_suit_le_calcul_de_reference(self):
        politique = AntiOmbrage(elevation_deg=21.0, marge_m=0.05)
        attendu = self._reference(KIT_VILLA_720, 21.0, 0.05)
        self.assertAlmostEqual(politique.pas_de_rangee_m(KIT_VILLA_720),
                               attendu, delta=0.01)

    def test_le_pas_est_variable_et_non_une_allee_constante(self):
        politique = AntiOmbrage()
        villa = politique.pas_apres_rangee(KIT_VILLA_720, 0.0)
        ao = politique.pas_apres_rangee(KIT_AO_PORTRAIT, 0.0)
        self.assertNotAlmostEqual(villa, ao, places=2)
        self.assertGreater(villa, 0.60)

    def test_une_elevation_plus_basse_ecarte_les_rangees(self):
        basse = AntiOmbrage(elevation_deg=15.0)
        haute = AntiOmbrage(elevation_deg=30.0)
        self.assertGreater(basse.pas_apres_rangee(KIT_VILLA_720, 0.0),
                           haute.pas_apres_rangee(KIT_VILLA_720, 0.0))

    def test_hauteur_et_ombre_sont_publiables(self):
        politique = AntiOmbrage(elevation_deg=21.0)
        self.assertAlmostEqual(politique.hauteur_module_m(KIT_VILLA_720),
                               2.384 * math.sin(math.radians(13.0)),
                               delta=1e-9)
        self.assertGreater(politique.longueur_ombre_m(KIT_VILLA_720), 1.0)

    def test_une_allee_minimale_peut_etre_imposee(self):
        politique = AntiOmbrage(elevation_deg=80.0, marge_m=0.0,
                                allee_minimale_m=0.40)
        self.assertAlmostEqual(politique.pas_apres_rangee(KIT_VILLA_720, 0.0),
                               0.40)

    def test_parametres_hors_bornes_refuses(self):
        with self.assertRaises(ValueError):
            AntiOmbrage(elevation_deg=0.0)
        with self.assertRaises(ValueError):
            AntiOmbrage(marge_m=-0.1)

    def test_le_dp_villa_tourne_avec_la_politique_anti_ombrage(self):
        surface = SurfaceRectangle(repere="VILLA", longueur_m=14.0,
                                   largeur_m=12.0,
                                   rives=Rives(laterale_m=0.50, extremite_m=0.50),
                                   axe_rangee=Axe.EST_OUEST)
        parametres = Parametres(kits=(KIT_VILLA_720,),
                                rives=Rives(laterale_m=0.50, extremite_m=0.50),
                                axe_rangee=Axe.EST_OUEST, pas_recherche_m=0.01)
        resultat = optimiser(surface, parametres, politique=AntiOmbrage())
        self.assertGreater(resultat.modules, 0)
        politique = AntiOmbrage()
        for gauche, droite in zip(resultat.rangees, resultat.rangees[1:]):
            self.assertGreaterEqual(
                droite[0] - gauche[0],
                politique.pas_de_rangee_m(KIT_VILLA_720) - 0.02)


class LElevationVientDeLaLatitude(unittest.TestCase):
    """PV65 — le soleil de dimensionnement est celui du LIEU, s'il est déclaré.

    Le point sensible est le DÉFAUT : sans latitude, l'ombre doit rester
    identique au bit près, sinon toutes les études villa déjà publiées
    changeraient de compte sans que personne n'ait touché une toiture.
    """

    def _alpha_a_la_main(self, latitude_deg, heure=10.0):
        """La formule réécrite ICI, indépendamment du module testé."""
        phi = math.radians(latitude_deg)
        delta = math.radians(-23.44)
        h = math.radians(15.0 * (heure - 12.0))
        return math.degrees(math.asin(
            math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.cos(h)))

    def test_sans_latitude_l_elevation_reste_la_constante_historique(self):
        politique = AntiOmbrage()
        self.assertIsNone(politique.latitude_deg)
        self.assertEqual(politique.elevation_effective_deg(),
                         ELEVATION_DIMENSIONNEMENT_DEG)
        self.assertEqual(politique.elevation_effective_deg(), 21.0)

    def test_sans_latitude_l_ombre_est_identique_au_bit_pres(self):
        """Le chemin de non-régression : les golden villa en dépendent."""
        hauteur = (KIT_VILLA_720.cote_dans_la_pente_m
                   * math.sin(math.radians(KIT_VILLA_720.inclinaison_deg)))
        attendu = hauteur / math.tan(math.radians(21.0))
        self.assertEqual(AntiOmbrage().longueur_ombre_m(KIT_VILLA_720),
                         attendu)

    def test_la_formule_portee_redonne_les_valeurs_calculees_a_la_main(self):
        for latitude, attendu in ((30.4, 28.948492), (33.6, 26.210601),
                                  (35.8, 24.314703)):
            with self.subTest(latitude=latitude):
                elevation, _azimut = position_solaire_solstice(latitude)
                self.assertAlmostEqual(elevation, attendu, places=5)
                self.assertAlmostEqual(elevation,
                                       self._alpha_a_la_main(latitude),
                                       places=9)

    def test_a_midi_solaire_l_elevation_vaut_la_forme_fermee(self):
        """h = 0 -> α = 90 − |φ − δ| : contrôle indépendant de la formule."""
        for latitude in (0.0, 30.4, 35.8):
            with self.subTest(latitude=latitude):
                elevation, azimut = position_solaire_solstice(latitude, 12.0)
                self.assertAlmostEqual(elevation,
                                       90.0 - abs(latitude - (-23.44)),
                                       places=9)
                self.assertAlmostEqual(abs(azimut), 0.0, places=9)

    def test_agadir_recoit_un_soleil_plus_haut_que_tanger(self):
        agadir = AntiOmbrage(latitude_deg=30.4)
        tanger = AntiOmbrage(latitude_deg=35.8)
        self.assertGreater(agadir.elevation_effective_deg(),
                           tanger.elevation_effective_deg())
        # soleil plus haut -> ombre plus courte -> rangées plus serrées
        self.assertLess(agadir.longueur_ombre_m(KIT_VILLA_720),
                        tanger.longueur_ombre_m(KIT_VILLA_720))
        self.assertLess(agadir.pas_de_rangee_m(KIT_VILLA_720),
                        tanger.pas_de_rangee_m(KIT_VILLA_720))

    def test_le_plancher_de_5_degres_protege_des_latitudes_extremes(self):
        """Sans plancher, tan(α) tendrait vers 0 et le pas vers l'infini."""
        polaire = AntiOmbrage(latitude_deg=80.0)
        self.assertEqual(polaire.elevation_effective_deg(),
                         ELEVATION_PLANCHER_DEG)
        self.assertLess(polaire.pas_de_rangee_m(KIT_VILLA_720), 10.0)

    def test_une_latitude_ou_une_heure_hors_bornes_est_refusee(self):
        with self.assertRaises(ValueError):
            AntiOmbrage(latitude_deg=120.0)
        with self.assertRaises(ValueError):
            AntiOmbrage(latitude_deg=-91.0)
        with self.assertRaises(ValueError):
            AntiOmbrage(heure_solaire=25.0)

    def test_le_dp_villa_serre_les_rangees_quand_la_latitude_est_donnee(self):
        surface = SurfaceRectangle(repere="VILLA", longueur_m=14.0,
                                   largeur_m=20.0,
                                   rives=Rives(laterale_m=0.50,
                                               extremite_m=0.50),
                                   axe_rangee=Axe.EST_OUEST)
        parametres = Parametres(kits=(KIT_VILLA_720,),
                                rives=Rives(laterale_m=0.50, extremite_m=0.50),
                                axe_rangee=Axe.EST_OUEST, pas_recherche_m=0.01)
        national = optimiser(surface, parametres, politique=AntiOmbrage())
        agadir = optimiser(surface, parametres,
                           politique=AntiOmbrage(latitude_deg=30.4))
        self.assertGreaterEqual(len(agadir.rangees), len(national.rangees))
        self.assertGreaterEqual(agadir.modules, national.modules)

    def test_le_majeur_du_moteur_a_ete_incremente(self):
        """Un compte publiable peut changer à toiture identique : MAJEUR."""
        self.assertGreaterEqual(version_tuple(VERSION_MOTEUR)[0], 2)


class AffleurantEnPente(unittest.TestCase):
    def test_pose_jointive(self):
        self.assertAlmostEqual(
            Affleurant().pas_apres_rangee(KIT_VILLA_720, 0.0), 0.0)
        self.assertAlmostEqual(Affleurant(jeu_m=0.02).allee_minimale(), 0.02)

    def test_jeu_negatif_refuse(self):
        with self.assertRaises(ValueError):
            Affleurant(jeu_m=-0.01)

    def test_affleurant_place_plus_de_rangees_que_l_anti_ombrage(self):
        surface = SurfaceRectangle(repere="PENTE", longueur_m=14.0,
                                   largeur_m=12.0,
                                   rives=Rives(laterale_m=0.50, extremite_m=0.50),
                                   axe_rangee=Axe.EST_OUEST)
        parametres = Parametres(kits=(KIT_VILLA_720,),
                                rives=Rives(laterale_m=0.50, extremite_m=0.50),
                                axe_rangee=Axe.EST_OUEST, pas_recherche_m=0.01)
        jointif = optimiser(surface, parametres, politique=Affleurant())
        espace = optimiser(surface, parametres, politique=AntiOmbrage())
        self.assertGreater(len(jointif.rangees), len(espace.rangees))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
