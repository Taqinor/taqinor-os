# -*- coding: utf-8 -*-
"""AOF47 — mode « rangées uniformes à phase balayée » : marche A = 112, école 314.

Ce fichier porte AUSSI le jeu de données de l'ARC (bâtiment B) : les 22
emprises relevées, les 3 segments séparés par leurs murets et les rangées
explicites de la planche V2. AOF53 et AOF184 le réutilisent.
"""

import unittest

from core.calepinage.exceptions import EntreeInvalide
from core.calepinage.moteur import compter_plan
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.optimum import calculer, optimiser
from core.calepinage.pose_uniforme import (
    balayer_phase,
    compter_uniforme,
    jeu_de_rangees,
    jeu_maximal,
    nb_rangees,
    phases_a_evaluer,
)
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.surfaces.arc import SurfaceArc
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    MethodePreuve,
    ModePose,
    Obstacle,
    Parametres,
    Provenance,
    Rives,
    remplacer,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES, ECOLE_RANGEES

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)
#: rives du moteur v1 : latérale 0,35 mais rive d'EXTRÉMITÉ 0,50
RIVES_V1 = Rives(laterale_m=0.35, extremite_m=0.50)

# ====================================================== bâtiment B (arc)
R_EXT, LARGEUR = 274.0, 10.90
S1_LEN, S2_LEN, S3_LEN, MURET = 20.55, 23.00, 23.60, 0.45
OFF2 = S1_LEN + MURET
OFF3 = OFF2 + S2_LEN + MURET
DEVELOPPE = OFF3 + S3_LEN

#: (repère, s0, s1, y0, y1) en abscisse LOCALE du segment, y depuis le bord INT
ARC_S1 = (
    ("C1", 3.27, 4.63, LARGEUR - 4.72, LARGEUR - 3.82),
    ("C2", 15.54, 17.09, 4.80, 5.76),
    ("C3", 12.78, 14.14, 4.20, 5.15),
)
ARC_S2 = (
    ("cage", 0.00, 4.98, LARGEUR - 5.93, LARGEUR),
    ("K1", 6.28, 7.28, LARGEUR - 4.67, LARGEUR - 3.77),
    ("K2", 8.58, 9.78, LARGEUR - 4.20, LARGEUR - 3.40),
    ("K3", 8.18, 9.43, 3.50, 4.30),
    ("K4", 15.97, 17.42, 3.85, 4.75),
    ("K5", 11.34, 13.14, LARGEUR - 3.00, LARGEUR - 2.00),
    ("K6", 20.00, 21.50, LARGEUR - 4.68, LARGEUR - 3.78),
    ("K7", 20.10, 21.60, 3.86, 4.72),
)
ARC_S3 = (
    ("A", 3.30, 4.57, LARGEUR - 4.19, LARGEUR - 3.61),
    ("B", 2.50, 3.55, 3.70, 5.33),
    ("X", 4.62, 5.32, 4.20, 5.30),
    ("N1", 4.92, 8.15, LARGEUR - 1.70, LARGEUR),
    ("N2", 8.15, 10.72, LARGEUR - 3.15, LARGEUR),
    ("C", 9.05, 10.59, 3.681, 4.701),
    ("D", 9.60, 10.44, LARGEUR - 4.70, LARGEUR - 3.93),
    ("E", 10.72, 12.52, LARGEUR - 4.84, LARGEUR - 3.74),
    ("G", 10.90, 12.43, 3.77, 4.67),
    ("F", 19.05, 20.27, LARGEUR - 4.69, LARGEUR - 3.85),
    ("H", 18.99, 20.34, 3.83, 4.69),
)
#: éléments NON COTÉS du segment 3 (comptes AVEC et SANS, pour arbitrage client)
ARC_NON_COTES = ("X", "N1", "N2")
#: rangées explicites retenues par la planche V2, segment par segment
ARC_RANGEES = {"S1": (0.55, 5.85), "S2": (0.80, 5.20, 8.30),
               "S3": (1.00, 5.10, 8.30)}
ARC_LONGUEURS = {"S1": S1_LEN, "S2": S2_LEN, "S3": S3_LEN}
ARC_KITS = {"S1": KIT_AO_PORTRAIT, "S2": KIT_AO_PAYSAGE, "S3": KIT_AO_PAYSAGE}


def obstacles_arc(segment, degagement=0.35):
    """Obstacles LOCAUX d'un segment, dégagement en abscisse développée."""
    table = {"S1": ARC_S1, "S2": ARC_S2, "S3": ARC_S3}[segment]
    return appliquer_regles(tuple(
        Obstacle(repere=repere, x0=s0, x1=s1, y0=y0, y1=y1,
                 provenance=Provenance.RELEVE, degagement_m=degagement)
        for repere, s0, s1, y0, y1 in table))


def segment_plat(segment, rives=RIVES_AO):
    """Le segment vu par l'ANCIEN modèle : tables jointives en abscisse."""
    return SurfaceRectangle(repere=segment, longueur_m=ARC_LONGUEURS[segment],
                            largeur_m=LARGEUR, rives=rives)


def segment_arc(segment, rives=RIVES_AO):
    """Le segment vu par le modèle CORRIGÉ : pas ``mod_l × R_ext / R_int``."""
    return SurfaceArc(repere=segment, rayon_ext_m=R_EXT, largeur_m=LARGEUR,
                      developpe_m=ARC_LONGUEURS[segment], rives=rives)


class JeuUniforme(unittest.TestCase):
    def test_nb_rangees_reproduit_rows_for(self):
        # école : (25,62 - 0,70 + 0,60) // (4,70 + 0,60) = 4 rangées
        self.assertEqual(nb_rangees(0.35, 25.27, 4.70, 0.60), 4)
        # arc : (10,90 - 0,70 + 1,20) // (2,25 + 1,20) = 3 rangées
        self.assertEqual(nb_rangees(0.35, 10.55, 2.25, 1.20), 3)

    def test_jeu_de_rangees_et_phase(self):
        surface = SurfaceRectangle(repere="R", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        rangees = jeu_de_rangees(surface, KIT_AO_PORTRAIT, 0.60)
        self.assertEqual(len(rangees), 4)
        self.assertAlmostEqual(rangees[0], 0.35, delta=1e-9)
        self.assertAlmostEqual(rangees[1] - rangees[0],
                               KIT_AO_PORTRAIT.emprise_transversale_m + 0.60,
                               delta=1e-9)
        decale = jeu_de_rangees(surface, KIT_AO_PORTRAIT, 0.60, phase=1.00)
        self.assertAlmostEqual(decale[0], 1.35, delta=1e-9)

    def test_jeu_maximal_est_le_slack_du_moteur_v1(self):
        surface = SurfaceRectangle(repere="R", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        self.assertAlmostEqual(jeu_maximal(surface, KIT_AO_PORTRAIT, 0.60),
                               4.32, delta=0.01)

    def test_pas_de_balayage_invalide(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO)
        with self.assertRaises(ValueError):
            balayer_phase(surface, parametres, pas_phase=0.0)


class LEcoleRedonneSaVarianteUniforme(unittest.TestCase):
    """``best_phase(51,10 ; 25,62 ; allée 0,60 ; rive 0,35) = 314``."""

    def test_variante_uniforme_060(self):
        surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60)
        resultat = balayer_phase(surface, parametres,
                                 appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(resultat.modules, 314)

    def test_la_variante_uniforme_egale_les_rangees_explicites(self):
        surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        explicites = compter_plan(
            surface, tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
            appliquer_regles(ECOLE_OBSTACLES))
        self.assertEqual(explicites.modules, 314)


class LaMarcheADeLArcRedonne112(unittest.TestCase):
    """Le moteur v1 tel quel : uniforme 1,20 / rive 0,35 / dégagement 0,30 /
    rive d'extrémité 0,50, tables paysage, SANS correction d'arc."""

    def _marche_a(self):
        parametres = Parametres(kits=(KIT_AO_PAYSAGE,), rives=RIVES_V1,
                                allee_m=1.20)
        total = 0
        for segment in ("S1", "S2", "S3"):
            surface = segment_plat(segment, RIVES_V1)
            total += balayer_phase(surface, parametres,
                                   obstacles_arc(segment, 0.30)).modules
        return total

    def test_marche_a(self):
        self.assertEqual(self._marche_a(), 112)

    def test_la_correction_d_arc_est_la_marche_suivante(self):
        """Marche B : même jeu, pas de pose corrigé — 112 -> 108."""
        parametres = Parametres(kits=(KIT_AO_PAYSAGE,), rives=RIVES_V1,
                                allee_m=1.20)
        total = 0
        for segment in ("S1", "S2", "S3"):
            total += balayer_phase(segment_arc(segment, RIVES_V1), parametres,
                                   obstacles_arc(segment, 0.30)).modules
        self.assertEqual(total, 108)
        self.assertLess(total, self._marche_a())


class LesRangeesExplicitesDeLArc(unittest.TestCase):
    """La planche V2 publie 120 : S1 = 48 (portrait), S2 = 34, S3 = 38."""

    def _compte(self, segment):
        surface = segment_arc(segment, RIVES_AO)
        kit = ARC_KITS[segment]
        return compter_plan(surface,
                            tuple((y, kit) for y in ARC_RANGEES[segment]),
                            obstacles_arc(segment)).modules

    def test_par_segment(self):
        self.assertEqual(self._compte("S1"), 48)
        self.assertEqual(self._compte("S2"), 34)
        self.assertEqual(self._compte("S3"), 38)

    def test_total_de_l_arc(self):
        total = sum(self._compte(s) for s in ("S1", "S2", "S3"))
        self.assertEqual(total, 120)


class LeModeUniformeNeBatJamaisLeDP(unittest.TestCase):
    """Test de MONOTONIE : le DP explore un sur-ensemble strict."""

    def test_monotonie_sur_l_ecole(self):
        surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60, pas_recherche_m=0.01)
        obstacles = appliquer_regles(ECOLE_OBSTACLES)
        uniforme = balayer_phase(surface, parametres, obstacles)
        dp = optimiser(surface, parametres, obstacles)
        self.assertLessEqual(uniforme.modules, dp.modules)

    def test_monotonie_sur_un_segment_d_arc(self):
        surface = segment_arc("S2", RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PAYSAGE,), rives=RIVES_AO,
                                allee_m=0.60, pas_recherche_m=0.01)
        obstacles = obstacles_arc("S2")
        self.assertLessEqual(balayer_phase(surface, parametres, obstacles).modules,
                             optimiser(surface, parametres, obstacles).modules)


class VocabulaireDuModeUniforme(unittest.TestCase):
    def test_le_mode_uniforme_est_une_heuristique_bornee(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60)
        resultat = balayer_phase(surface, parametres, borne_superieure=99)
        self.assertIs(resultat.preuve.methode, MethodePreuve.HEURISTIQUE_BORNEE)
        self.assertFalse(resultat.optimal)
        self.assertNotIn("prouvé", resultat.preuve.libelle)
        self.assertIn("borne supérieure", resultat.preuve.libelle)

    def test_le_mode_de_pose_des_parametres_pilote_le_calcul(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60, pas_recherche_m=0.01)
        dp = calculer(surface, parametres)
        uniforme = calculer(surface, remplacer(
            parametres, mode_pose=ModePose.RANGEES_UNIFORMES_PHASE))
        self.assertIs(dp.preuve.methode, MethodePreuve.DP_EXACT_1CM)
        self.assertIs(uniforme.preuve.methode, MethodePreuve.HEURISTIQUE_BORNEE)
        self.assertLessEqual(uniforme.modules, dp.modules)
        self.assertEqual(uniforme.preuve.borne_superieure, dp.modules)

    def test_les_deux_modes_partagent_le_compteur(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        rangees = jeu_de_rangees(surface, KIT_AO_PORTRAIT, 0.60)
        direct = compter_plan(surface, tuple((y, KIT_AO_PORTRAIT)
                                             for y in rangees))
        self.assertEqual(
            compter_uniforme(surface, KIT_AO_PORTRAIT, allee=0.60).modules,
            direct.modules)


class LaPhaseForcee(unittest.TestCase):
    """PV52 — republier une pose EXISTANTE : sa phase est une donnée du
    terrain, pas un paramètre à ré-optimiser."""

    def setUp(self):
        self.surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                        largeur_m=25.62, rives=RIVES_AO)
        self.obstacles = appliquer_regles(ECOLE_OBSTACLES)
        self.parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                     allee_m=0.60)

    def _forcee(self, phase):
        return remplacer(self.parametres, phase_forcee_m=phase)

    def test_la_phase_forcee_rend_exactement_cette_phase_la(self):
        for phase in (0.0, 1.00, 2.50):
            with self.subTest(phase=phase):
                resultat = balayer_phase(self.surface, self._forcee(phase),
                                         self.obstacles)
                attendu = compter_uniforme(self.surface, KIT_AO_PORTRAIT,
                                           self.obstacles, allee=0.60,
                                           phase=phase)
                self.assertEqual(resultat.modules, attendu.modules)
                self.assertAlmostEqual(resultat.rangees[0][0],
                                       attendu.rangees[0].y0, delta=1e-9)

    def test_une_phase_forcee_mediocre_n_est_pas_corrigee_en_douce(self):
        """Le balayage libre trouve 314 ; la phase 0 en rend moins et le
        moteur PUBLIE ce moins — sinon « phase forcée » ne voudrait rien dire."""
        libre = balayer_phase(self.surface, self.parametres, self.obstacles)
        forcee = balayer_phase(self.surface, self._forcee(0.0), self.obstacles)
        self.assertEqual(libre.modules, 314)
        self.assertLessEqual(forcee.modules, libre.modules)
        self.assertEqual(
            forcee.modules,
            compter_uniforme(self.surface, KIT_AO_PORTRAIT, self.obstacles,
                             allee=0.60, phase=0.0).modules)

    def test_sans_phase_forcee_le_balayage_est_inchange(self):
        self.assertIsNone(self.parametres.phase_forcee_m)
        self.assertEqual(
            balayer_phase(self.surface, self.parametres, self.obstacles).modules,
            314)

    def test_les_phases_a_evaluer_sont_le_balayage_ou_le_singleton(self):
        balayage = phases_a_evaluer(self.surface, KIT_AO_PORTRAIT, 0.60, 0.05)
        self.assertGreater(len(balayage), 1)
        self.assertAlmostEqual(balayage[0], 0.0, delta=1e-9)
        unique = phases_a_evaluer(self.surface, KIT_AO_PORTRAIT, 0.60, 0.05,
                                  phase_forcee=1.00)
        self.assertEqual(len(unique), 1)
        self.assertAlmostEqual(unique[0], 1.00, delta=1e-9)

    def test_une_phase_hors_du_jeu_maximal_est_refusee_poliment(self):
        maximal = jeu_maximal(self.surface, KIT_AO_PORTRAIT, 0.60)
        with self.assertRaises(EntreeInvalide) as capture:
            balayer_phase(self.surface, self._forcee(maximal + 1.0),
                          self.obstacles)
        self.assertIn("jeu maximal", str(capture.exception))
        self.assertIn("AO_PORTRAIT", str(capture.exception))

    def test_une_phase_negative_est_refusee(self):
        with self.assertRaises(EntreeInvalide):
            balayer_phase(self.surface, self._forcee(-0.10), self.obstacles)

    def test_le_mode_de_pose_porte_la_phase_forcee_de_bout_en_bout(self):
        parametres = remplacer(self.parametres,
                               mode_pose=ModePose.RANGEES_UNIFORMES_PHASE,
                               pas_recherche_m=0.01, phase_forcee_m=1.00)
        resultat = calculer(self.surface, parametres, self.obstacles)
        self.assertIs(resultat.preuve.methode, MethodePreuve.HEURISTIQUE_BORNEE)
        self.assertEqual(
            resultat.modules,
            compter_uniforme(self.surface, KIT_AO_PORTRAIT, self.obstacles,
                             allee=0.60, phase=1.00).modules)

    def test_l_aller_retour_json_conserve_la_phase_et_l_omet_sinon(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        avec = EntreeCalepinage(
            repere="PV52", surfaces=(surface,), kits=(KIT_AO_PORTRAIT,),
            parametres=remplacer(self.parametres, phase_forcee_m=1.25))
        refaite = EntreeCalepinage.depuis_json(avec.vers_json())
        self.assertAlmostEqual(refaite.parametres.phase_forcee_m, 1.25,
                               delta=1e-9)
        self.assertEqual(refaite.hash_entree, avec.hash_entree)
        sans = EntreeCalepinage(repere="PV52", surfaces=(surface,),
                                kits=(KIT_AO_PORTRAIT,),
                                parametres=self.parametres)
        self.assertNotIn("phase_forcee_m", sans.vers_dict()["parametres"])
        self.assertIsNone(
            EntreeCalepinage.depuis_json(sans.vers_json())
            .parametres.phase_forcee_m)
        self.assertNotEqual(sans.hash_entree, avec.hash_entree)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
