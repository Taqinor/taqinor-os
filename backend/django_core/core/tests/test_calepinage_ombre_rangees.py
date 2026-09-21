# -*- coding: utf-8 -*-
"""CALX159 — la fraction ombrée entre rangées, prouvée par sa géométrie.

Aucune base, aucun réseau, aucun Django : ``unittest`` pur sur le noyau
``core/calepinage/ombre_rangees.py``.

Ce que ces essais démontrent, dans l'ordre :

1. **Un cas calculable À LA MAIN.** Table de côté ``L = √2`` inclinée à 45° :
   sa hauteur et son empreinte valent 1 m chacune. Avec un pas de 2 m, le jeu
   libre vaut 1 m ; à un angle de profil dont la tangente vaut 0,5, la
   longueur ombrée vaut ``(1 − 1×0,5) / (sin45° + 0,5·cos45°) = 0,5 / 1,06066``
   soit ``0,4714 m``, c'est-à-dire EXACTEMENT un tiers de la table. Aucun
   arrondi n'est toléré au-delà de la précision flottante.
2. **La décroissance monotone** de la fraction quand le soleil monte, sur
   toute la plage diurne et pour plusieurs azimuts.
3. **Le raccord avec ``politique_pas.AntiOmbrage``** : le pas que la politique
   anti-ombrage POSE (marge nulle) rend une élévation critique égale à son
   élévation de dimensionnement, et la fraction s'annule au-dessus. Le
   raccord est CALCULÉ des deux côtés — aucune constante n'est recopiée.
4. **Les deux extensions** : châssis est-ouest (deux plans opposés, matin et
   après-midi symétriques) et pose sans relief (fraction nulle par
   géométrie).

Run :
    python manage.py test core.tests.test_calepinage_ombre_rangees
"""

import math
import unittest

from core.calepinage.ombre_rangees import (
    AZIMUT_PLAN_EST_DEG, TableInclinee, angle_profil_deg,
    elevation_critique_deg, empreinte_table_m, fraction_ombree,
    fraction_ombree_est_ouest, hauteur_table_m, jeu_libre_m)
from core.calepinage.politique_pas import (
    ELEVATION_DIMENSIONNEMENT_DEG, AntiOmbrage)

#: Le cas à la main : côté √2 à 45° ⇒ hauteur 1 m, empreinte 1 m.
COTE_UNITAIRE_M = math.sqrt(2.0)
INCLINAISON_UNITAIRE_DEG = 45.0

#: Une table de villa réelle (kit 2 modules paysage du catalogue) à 30°.
COTE_VILLA_M = 1.134
INCLINAISON_VILLA_DEG = 30.0


class GeometrieDeLaTable(unittest.TestCase):
    """Hauteur, empreinte et jeu libre — les trois grandeurs de base."""

    def test_hauteur_et_empreinte_du_cas_unitaire(self):
        self.assertAlmostEqual(
            hauteur_table_m(COTE_UNITAIRE_M, INCLINAISON_UNITAIRE_DEG), 1.0)
        self.assertAlmostEqual(
            empreinte_table_m(COTE_UNITAIRE_M, INCLINAISON_UNITAIRE_DEG), 1.0)

    def test_la_table_delegue_a_politique_pas(self):
        """Les deux grandeurs viennent de ``AntiOmbrage``, pas d'un doublon."""
        table = TableInclinee(COTE_VILLA_M, INCLINAISON_VILLA_DEG)
        politique = AntiOmbrage()
        self.assertEqual(table.hauteur_m,
                         politique.hauteur_module_m(table))
        self.assertEqual(table.emprise_transversale_m,
                         politique.empreinte_pan_m(table))

    def test_jeu_libre_negatif_quand_les_rangees_se_chevauchent(self):
        self.assertLess(
            jeu_libre_m(0.5, COTE_UNITAIRE_M, INCLINAISON_UNITAIRE_DEG), 0.0)


class AngleDeProfil(unittest.TestCase):
    """``tan α_p = tan α / cos(γ_soleil − γ_plan)``."""

    def test_soleil_dans_le_plan_de_profil_rend_l_elevation(self):
        self.assertAlmostEqual(angle_profil_deg(30.0, 0.0, 0.0), 30.0)

    def test_soleil_de_biais_releve_l_angle_de_profil(self):
        profil = angle_profil_deg(30.0, -45.0, 0.0)
        attendu = math.degrees(math.atan(
            math.tan(math.radians(30.0)) / math.cos(math.radians(45.0))))
        self.assertAlmostEqual(profil, attendu)
        self.assertGreater(profil, 30.0)

    def test_soleil_derriere_le_plan_ou_sous_l_horizon_rend_none(self):
        self.assertIsNone(angle_profil_deg(30.0, 180.0, 0.0))
        self.assertIsNone(angle_profil_deg(-1.0, 0.0, 0.0))
        self.assertIsNone(angle_profil_deg(30.0, 90.0, 0.0))


class FractionOmbree(unittest.TestCase):
    """Le cœur : la part de la table aval à l'ombre de la table amont."""

    def test_cas_calculable_a_la_main_un_tiers(self):
        """h = g = 1 m, tan α_p = 0,5 ⇒ exactement un tiers de la table."""
        elevation = math.degrees(math.atan(0.5))
        fraction = fraction_ombree(
            2.0, COTE_UNITAIRE_M, INCLINAISON_UNITAIRE_DEG, 0.0,
            elevation, 0.0)
        self.assertAlmostEqual(fraction, 1.0 / 3.0, places=12)

    def test_decroissance_monotone_avec_l_elevation(self):
        """Propriété : plus le soleil monte, moins la rangée est ombrée."""
        for azimut in (-60.0, -30.0, 0.0, 30.0, 60.0):
            precedente = 1.0 + 1e-9
            for dixiemes in range(1, 900):
                fraction = fraction_ombree(
                    1.5, COTE_VILLA_M, INCLINAISON_VILLA_DEG, 0.0,
                    dixiemes / 10.0, azimut)
                self.assertLessEqual(
                    fraction, precedente + 1e-12,
                    'fraction remontée à %.1f° (azimut %.0f°)'
                    % (dixiemes / 10.0, azimut))
                precedente = fraction

    def test_l_arete_haute_n_est_jamais_ombree_par_une_rangee_identique(self):
        """Propriété : l'arête haute aval est à la MÊME hauteur que l'arête
        haute amont ; le rayon qui rase la seconde ne peut donc pas passer
        au-dessus de la première. La fraction reste strictement < 1 pour
        tout pas positif, même quand les rangées se chevauchent."""
        for pas in (0.05, 0.25, 0.5, 1.0, 1.5):
            for elevation in (1.0, 5.0, 20.0):
                fraction = fraction_ombree(
                    pas, COTE_UNITAIRE_M, INCLINAISON_UNITAIRE_DEG, 0.0,
                    elevation, 0.0)
                self.assertLess(fraction, 1.0,
                                'pas %.2f m, élévation %.0f°'
                                % (pas, elevation))

    def test_l_ombre_grandit_quand_le_pas_se_resserre(self):
        precedente = 0.0
        for pas in (2.0, 1.5, 1.0, 0.5, 0.05):
            fraction = fraction_ombree(
                pas, COTE_UNITAIRE_M, INCLINAISON_UNITAIRE_DEG, 0.0, 5.0, 0.0)
            self.assertGreater(fraction, precedente)
            precedente = fraction
        self.assertGreater(precedente, 0.9)

    def test_bornee_entre_zero_et_un_sur_toute_la_plage(self):
        for elevation in range(0, 91):
            for azimut in range(-180, 181, 15):
                fraction = fraction_ombree(
                    1.4, COTE_VILLA_M, INCLINAISON_VILLA_DEG, 0.0,
                    float(elevation), float(azimut))
                self.assertGreaterEqual(fraction, 0.0)
                self.assertLessEqual(fraction, 1.0)


class RaccordAvecLaPolitiqueDePas(unittest.TestCase):
    """Le seuil de non-ombrage est CELUI que ``AntiOmbrage`` vise."""

    def _pas_anti_ombrage(self, table, elevation_deg):
        """Le pas que la politique POSE pour cette table, marge nulle."""
        return AntiOmbrage(elevation_deg=elevation_deg,
                           marge_m=0.0).pas_de_rangee_m(table)

    def test_elevation_critique_egale_l_elevation_de_dimensionnement(self):
        table = TableInclinee(COTE_VILLA_M, INCLINAISON_VILLA_DEG)
        pas = self._pas_anti_ombrage(table, ELEVATION_DIMENSIONNEMENT_DEG)
        self.assertAlmostEqual(
            elevation_critique_deg(pas, COTE_VILLA_M, INCLINAISON_VILLA_DEG),
            ELEVATION_DIMENSIONNEMENT_DEG, places=9)

    def test_fraction_nulle_au_dessus_du_seuil_non_nulle_en_dessous(self):
        for elevation_de_design in (15.0, 21.0, 30.0):
            for inclinaison in (10.0, 20.0, 30.0):
                table = TableInclinee(COTE_VILLA_M, inclinaison)
                pas = self._pas_anti_ombrage(table, elevation_de_design)
                seuil = elevation_critique_deg(pas, COTE_VILLA_M, inclinaison)
                self.assertAlmostEqual(seuil, elevation_de_design, places=9)
                self.assertEqual(
                    fraction_ombree(pas, COTE_VILLA_M, inclinaison, 0.0,
                                    seuil + 0.5, 0.0),
                    0.0)
                self.assertGreater(
                    fraction_ombree(pas, COTE_VILLA_M, inclinaison, 0.0,
                                    seuil - 0.5, 0.0),
                    0.0)

    def test_un_pas_plus_grand_ombre_moins(self):
        table = TableInclinee(COTE_VILLA_M, INCLINAISON_VILLA_DEG)
        serre = self._pas_anti_ombrage(table, 40.0)
        large = self._pas_anti_ombrage(table, 15.0)
        self.assertGreater(large, serre)
        self.assertGreater(
            fraction_ombree(serre, COTE_VILLA_M, INCLINAISON_VILLA_DEG, 0.0,
                            12.0, 0.0),
            fraction_ombree(large, COTE_VILLA_M, INCLINAISON_VILLA_DEG, 0.0,
                            12.0, 0.0))


class ChassisEstOuest(unittest.TestCase):
    """Deux plans opposés : le matin ombre l'est, l'après-midi l'ouest."""

    def _couple(self, azimut_soleil_deg):
        return fraction_ombree_est_ouest(
            1.3, COTE_VILLA_M, 15.0, 25.0, azimut_soleil_deg)

    def test_le_matin_seul_le_pan_est_est_ombre(self):
        est, ouest = self._couple(-75.0)
        self.assertGreater(est, 0.0)
        self.assertEqual(ouest, 0.0)

    def test_l_apres_midi_seul_le_pan_ouest_est_ombre(self):
        est, ouest = self._couple(75.0)
        self.assertEqual(est, 0.0)
        self.assertGreater(ouest, 0.0)

    def test_symetrie_matin_apres_midi(self):
        matin_est, _ = self._couple(-60.0)
        _, apres_midi_ouest = self._couple(60.0)
        self.assertAlmostEqual(matin_est, apres_midi_ouest, places=12)

    def test_le_pan_est_suit_la_meme_formule_que_le_plein_sud(self):
        """Le faîte voisin est à ``pas − L·cos β`` : même jeu, même calcul."""
        est, _ = self._couple(-75.0)
        self.assertAlmostEqual(
            est,
            fraction_ombree(1.3, COTE_VILLA_M, 15.0, AZIMUT_PLAN_EST_DEG,
                            25.0, -75.0),
            places=12)


class PoseSansRelief(unittest.TestCase):
    """Pose affleurante / au sol sans inclinaison : rien ne s'ombre."""

    def test_inclinaison_nulle_rend_zero(self):
        self.assertEqual(
            fraction_ombree(1.0, COTE_VILLA_M, 0.0, 0.0, 10.0, 0.0), 0.0)
        self.assertEqual(
            elevation_critique_deg(1.0, COTE_VILLA_M, 0.0), 0.0)

    def test_table_de_longueur_nulle_rend_zero(self):
        self.assertEqual(fraction_ombree(2.0, 0.0, 30.0, 0.0, 10.0, 0.0), 0.0)
