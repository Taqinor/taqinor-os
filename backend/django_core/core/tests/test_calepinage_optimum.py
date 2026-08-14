# -*- coding: utf-8 -*-
"""AOF44 — le DP exact multi-kits et le vocabulaire VERROUILLÉ de la preuve.

Jeu de référence : bâtiment A (aile en L) du relevé FRDISI 27/07/2026, avec
ses 30 emprises (28 relevées + GRECT deviné + PAN venu du plan). Le script
témoin ``vue_bat_A_v2.py`` publie **148** modules sur ses 8 rangées explicites
en kit portrait unique ; le moteur les redonne exactement, puis le DP montre ce
que les kits mixtes rapportent.
"""

import unittest

from core.calepinage.exceptions import EntreeInvalide
from core.calepinage.moteur import compter_plan
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.optimum import (
    borne_superieure_kit,
    calculer,
    evaluer_plan_impose,
    optimiser,
    positions_grille,
)
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    MethodePreuve,
    ModePose,
    Obstacle,
    Parametres,
    Preuve,
    Provenance,
    Rives,
)

RIVE = 0.35
RIVES_AO = Rives(laterale_m=RIVE, extremite_m=RIVE)
BARRE, W_B, LEG_W, LEG_S = 47.08, 10.76, 11.2, 29.74

#: contour (x nord-sud, y est-ouest) — la rive de l'aile est DÉDUITE du contour
#: (le script d'origine la portait dans sa constante ``X_LEG_E = 10,85``)
CONTOUR_AILE_L = ((W_B, 0.0), (W_B, BARRE), (0.0, BARRE),
                  (0.0, LEG_W - RIVE), (-LEG_S, LEG_W - RIVE), (-LEG_S, 0.0))

#: (x0, x1, y0, y1, douteux) des caissons de la BARRE, repère moteur
_BARRE = (
    (3.77, 4.92, 3.39, 4.70, False), (3.84, 4.98, 11.17, 12.50, False),
    (3.33, 4.34, 19.05, 20.35, False), (5.91, 7.02, 3.16, 4.27, False),
    (6.08, 7.38, 8.03, 9.14, False), (8.43, 9.06, 16.52, 17.32, True),
    (6.02, 7.46, 18.92, 20.35, False), (6.82, 7.46, 24.86, 26.41, True),
    (6.53, 7.08, 27.06, 27.92, False), (6.14, 6.98, 32.53, 33.03, False),
    (6.41, 6.88, 33.68, 34.63, True), (6.61, 7.07, 39.50, 40.48, True),
    (6.18, 7.05, 43.975, 44.515, False), (3.74, 4.73, 32.18, 32.88, False),
    (3.75, 4.65, 39.31, 40.72, False), (3.75, 4.81, 45.68, 46.98, False),
)
#: caissons de l'AILE : ``s`` = distance sous le bord sud de la barre
_AILE = (
    (25.01, 26.36, 3.78, 4.93, False), (17.12, 18.47, 3.78, 4.93, False),
    (25.01, 26.36, 6.33, 7.48, False), (16.99, 18.34, 6.33, 7.48, False),
    (9.24, 10.45, 3.78, 4.85, True), (1.45, 1.87, 3.72, 4.82, False),
    (9.63, 10.26, 6.40, 7.20, True), (9.70, 10.40, 7.35, 7.75, True),
)


def obstacles_aile_l():
    """Les 30 emprises : 28 relevées + GRECT (deviné) + PAN (venu du plan)."""
    obs = []
    for i, (x0, x1, y0, y1, douteux) in enumerate(_BARRE):
        obs.append(Obstacle(
            repere="BAR%d" % (i + 1), x0=x0, x1=x1, y0=y0, y1=y1,
            provenance=(Provenance.RELEVE_DOUTEUX if douteux
                        else Provenance.RELEVE),
            degagement_m=0.50 if douteux else 0.30))
    for repere, (a0, a1, b0, b1), degagement in (
            ("CAGE", (12.23, 14.70, 6.13, 10.76), 0.30),
            ("DECN", (14.70, 17.47, 9.61, 10.76), 0.30),
            ("NOTCH", (31.28, 32.82, 0.0, 0.74), RIVE),
            ("EDIC", (30.21, 31.13, 0.0, 0.74), 0.30)):
        obs.append(Obstacle(repere=repere, x0=b0, x1=b1, y0=a0, y1=a1,
                            provenance=Provenance.RELEVE,
                            degagement_m=degagement))
    for i, (s0, s1, y0, y1, douteux) in enumerate(_AILE):
        obs.append(Obstacle(
            repere="LEG%d" % (i + 1), x0=-s1, x1=-s0, y0=y0, y1=y1,
            provenance=(Provenance.RELEVE_DOUTEUX if douteux
                        else Provenance.RELEVE),
            degagement_m=0.50 if douteux else 0.30))
    obs.append(Obstacle(repere="GRECT", x0=-1.70, x1=-0.40, y0=4.95, y1=7.16,
                        provenance=Provenance.DEVINE, degagement_m=0.50))
    obs.append(Obstacle(repere="PAN", x0=-LEG_S, x1=-(LEG_S - 4.04),
                        y0=LEG_W - 2.18, y1=LEG_W,
                        provenance=Provenance.PLAN, degagement_m=RIVE))
    return appliquer_regles(tuple(obs))


def surface_aile_l():
    return SurfacePolygone(repere="BAT_A_AILE_L", contour=CONTOUR_AILE_L,
                           rives=RIVES_AO)


#: les 8 rangées explicites du script témoin (kit portrait unique)
RANGEES_TEMOIN = (0.35, 5.65, 12.80, 20.65, 25.95, 31.25, 36.55, 41.85)
#: comptes par rangée publiés par le script témoin
DETAIL_TEMOIN = (42, 46, 8, 14, 12, 8, 10, 8)
COMPTE_TEMOIN = 148


class LeTemoinEstReproduit(unittest.TestCase):
    """Ancrage : sans lui, le DP « prouverait » un chiffre faux."""

    def test_les_rangees_du_script_redonnent_148(self):
        plan = compter_plan(surface_aile_l(),
                            tuple((y, KIT_AO_PORTRAIT) for y in RANGEES_TEMOIN),
                            obstacles_aile_l())
        self.assertEqual(plan.modules, COMPTE_TEMOIN)
        self.assertEqual(tuple(r.modules for r in plan.rangees), DETAIL_TEMOIN)


class DPExactMultiKits(unittest.TestCase):
    def setUp(self):
        self.surface = surface_aile_l()
        self.obstacles = obstacles_aile_l()

    def _parametres(self, kits):
        return Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                          pas_recherche_m=0.01, engagement_modules=152)

    def test_kit_unique_ne_bat_jamais_le_mixte(self):
        seul = optimiser(self.surface, self._parametres((KIT_AO_PORTRAIT,)),
                         self.obstacles)
        mixte = optimiser(self.surface,
                          self._parametres((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)),
                          self.obstacles)
        self.assertLessEqual(seul.modules, mixte.modules)
        self.assertGreaterEqual(mixte.modules, COMPTE_TEMOIN)

    def test_l_optimum_mixte_est_prouve(self):
        resultat = optimiser(self.surface,
                             self._parametres((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)),
                             self.obstacles)
        self.assertEqual(resultat.modules, 172)
        self.assertTrue(resultat.optimal)
        self.assertIs(resultat.preuve.methode, MethodePreuve.DP_EXACT_1CM)
        self.assertIn("prouvé", resultat.preuve.libelle)
        self.assertEqual(resultat.ecart_a_l_optimum, 0)

    def test_le_plan_retenu_respecte_rives_et_allees(self):
        resultat = optimiser(self.surface,
                             self._parametres((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)),
                             self.obstacles)
        ymin, ymax = self.surface.bornes_transversales_utiles()
        precedent = None
        for y0, code in resultat.rangees:
            kit = (KIT_AO_PORTRAIT if code == "AO_PORTRAIT" else KIT_AO_PAYSAGE)
            self.assertGreaterEqual(y0, ymin - 1e-9)
            self.assertLessEqual(y0 + kit.emprise_transversale_m, ymax + 1e-9)
            if precedent is not None:
                self.assertGreaterEqual(y0 - precedent, 0.60 - 1e-9)
            precedent = y0 + kit.emprise_transversale_m

    def test_le_nombre_de_plans_optimaux_est_publie(self):
        resultat = optimiser(self.surface,
                             self._parametres((KIT_AO_PORTRAIT,)),
                             self.obstacles)
        self.assertGreaterEqual(resultat.preuve.nb_plans_optimaux, 1)

    def test_un_plan_impose_inferieur_donne_l_ecart(self):
        parametres = self._parametres((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE))
        impose = evaluer_plan_impose(
            self.surface, parametres,
            tuple((y, KIT_AO_PORTRAIT) for y in RANGEES_TEMOIN),
            self.obstacles, compte_optimal=172)
        self.assertEqual(impose.modules, COMPTE_TEMOIN)
        self.assertFalse(impose.optimal)
        self.assertEqual(impose.ecart_a_l_optimum, 172 - COMPTE_TEMOIN)
        self.assertNotIn("prouvé", impose.preuve.libelle)


class VocabulaireVerrouille(unittest.TestCase):
    """« prouvé » est INACCESSIBLE hors méthode exacte — test dédié."""

    def test_heuristique_bornee_ne_peut_jamais_dire_prouve(self):
        preuve = Preuve(methode=MethodePreuve.HEURISTIQUE_BORNEE,
                        pas_recherche_m=0.05, compte_retenu=200,
                        compte_optimal=200, borne_superieure=200)
        self.assertFalse(preuve.optimal)
        self.assertNotIn("prouvé", preuve.libelle)
        self.assertIn("borne supérieure", preuve.libelle)

    def test_impose_utilisateur_non_plus(self):
        preuve = Preuve(methode=MethodePreuve.IMPOSE_UTILISATEUR,
                        pas_recherche_m=0.01, compte_retenu=148,
                        compte_optimal=148)
        self.assertFalse(preuve.optimal)
        self.assertNotIn("prouvé", preuve.libelle)

    def test_exhaustif_par_segment_est_exact(self):
        self.assertTrue(MethodePreuve.EXHAUSTIF_PAR_SEGMENT.exacte)
        self.assertFalse(MethodePreuve.HEURISTIQUE_BORNEE.exacte)


class GrilleEtBornes(unittest.TestCase):
    def test_positions_grille(self):
        self.assertEqual(positions_grille(0.0, 0.05, 0.01)[-1], 0.05)
        self.assertEqual(len(positions_grille(0.0, 0.05, 0.01)), 6)
        with self.assertRaises(ValueError):
            positions_grille(0.0, 1.0, 0.0)

    def test_le_dp_sur_un_rectangle_simple(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60, pas_recherche_m=0.01)
        resultat = optimiser(surface, parametres)
        # 12,00 - 0,70 = 11,30 utiles ; 2 rangées (4,70 + 0,60 + 4,70 = 10,00)
        # chacune : 19,30 / 1,134 = 17 pas = 34 modules
        self.assertEqual(len(resultat.rangees), 2)
        self.assertEqual(resultat.modules, 68)
        self.assertTrue(resultat.optimal)

    def test_borne_superieure_kit_borne_bien(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60, pas_recherche_m=0.01)
        borne = borne_superieure_kit(surface, KIT_AO_PORTRAIT,
                                     pas_recherche=0.05)
        self.assertGreaterEqual(borne, optimiser(surface, parametres).modules)


class ModeRangeesImposees(unittest.TestCase):
    """PV29 — le dessinateur impose ses rangées ; le moteur les COMPTE.

    Le point sensible n'est pas le compte : c'est que ce mode ne puisse
    JAMAIS produire la phrase « optimum prouvé », même quand le plan imposé
    égale le DP. La méthode reste ``IMPOSE_UTILISATEUR``, donc non exacte.
    """

    def setUp(self):
        self.surface = SurfaceRectangle(repere="R", longueur_m=20.0,
                                        largeur_m=12.0, rives=RIVES_AO)

    def _parametres(self, rangees_imposees):
        return Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                          allee_m=0.60, pas_recherche_m=0.01,
                          mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR,
                          rangees_imposees=rangees_imposees)

    def test_le_plan_impose_est_compte_et_situe_face_au_dp(self):
        resultat = calculer(self.surface,
                            self._parametres(((0.35, "AO_PORTRAIT"),)))
        self.assertEqual(resultat.modules, 34)
        self.assertEqual(resultat.rangees, ((0.35, "AO_PORTRAIT"),))
        self.assertEqual(resultat.ecart_a_l_optimum, 68 - 34)
        self.assertIs(resultat.preuve.methode,
                      MethodePreuve.IMPOSE_UTILISATEUR)
        self.assertEqual(resultat.preuve.compte_optimal, 68)

    def test_meme_egal_a_l_optimum_il_ne_dit_jamais_prouve(self):
        resultat = calculer(self.surface, self._parametres(
            ((0.35, "AO_PORTRAIT"), (5.65, "AO_PORTRAIT"))))
        self.assertEqual(resultat.modules, 68)
        self.assertEqual(resultat.ecart_a_l_optimum, 0)
        self.assertFalse(resultat.optimal)
        self.assertNotIn("prouvé", resultat.preuve.libelle)
        self.assertIn("meilleur plan trouvé", resultat.preuve.libelle)

    def test_sans_rangees_le_mode_refuse_au_lieu_de_se_replier_sur_le_dp(self):
        for vide in (None, ()):
            with self.subTest(vide=vide):
                with self.assertRaises(EntreeInvalide) as capture:
                    calculer(self.surface, self._parametres(vide))
                self.assertIn("rangees_imposees", str(capture.exception))

    def test_un_kit_non_declare_est_refuse_par_son_nom(self):
        with self.assertRaises(EntreeInvalide) as capture:
            calculer(self.surface, self._parametres(((0.35, "INCONNU"),)))
        self.assertIn("INCONNU", str(capture.exception))

    def test_un_couple_malforme_est_refuse_par_son_rang(self):
        with self.assertRaises(EntreeInvalide) as capture:
            calculer(self.surface, self._parametres((0.35,)))
        self.assertIn("n°1", str(capture.exception))

    def test_le_mode_impose_reste_un_value_error_pour_les_appelants(self):
        """``EntreeInvalide`` hérite de ``ValueError`` : les rattrapages
        historiques (le service AO) continuent de fonctionner."""
        with self.assertRaises(ValueError):
            calculer(self.surface, self._parametres(()))


class SerialisationDuPlanImpose(unittest.TestCase):
    """PV29 — le plan imposé fait l'aller-retour JSON sans rien perdre."""

    def _entree(self, rangees_imposees):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0,
                                   largeur_m=12.0, rives=RIVES_AO)
        parametres = Parametres(
            kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO, allee_m=0.60,
            pas_recherche_m=0.01,
            mode_pose=(ModePose.RANGEES_IMPOSEES_UTILISATEUR
                       if rangees_imposees
                       else ModePose.RANGEES_EXPLICITES_DP),
            rangees_imposees=rangees_imposees)
        return EntreeCalepinage(repere="PV29", surfaces=(surface,),
                                kits=(KIT_AO_PORTRAIT,), parametres=parametres)

    def test_l_aller_retour_rend_le_meme_plan_impose(self):
        entree = self._entree(((0.35, "AO_PORTRAIT"), (5.65, "AO_PORTRAIT")))
        refaite = EntreeCalepinage.depuis_json(entree.vers_json())
        self.assertEqual(refaite.parametres.rangees_imposees,
                         entree.parametres.rangees_imposees)
        self.assertIs(refaite.parametres.mode_pose,
                      ModePose.RANGEES_IMPOSEES_UTILISATEUR)
        self.assertEqual(refaite.hash_entree, entree.hash_entree)

    def test_sans_plan_impose_la_cle_n_apparait_pas_dans_le_document(self):
        """Sinon l'empreinte FIGÉE des golden bougerait sans qu'aucun relevé
        n'ait changé : le champ absent vaut ``None``."""
        entree = self._entree(None)
        self.assertNotIn("rangees_imposees",
                         entree.vers_dict()["parametres"])
        refaite = EntreeCalepinage.depuis_json(entree.vers_json())
        self.assertIsNone(refaite.parametres.rangees_imposees)
        self.assertEqual(refaite.hash_entree, entree.hash_entree)

    def test_deux_plans_imposes_differents_ont_deux_empreintes(self):
        un = self._entree(((0.35, "AO_PORTRAIT"),))
        autre = self._entree(((0.36, "AO_PORTRAIT"),))
        self.assertNotEqual(un.hash_entree, autre.hash_entree)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
