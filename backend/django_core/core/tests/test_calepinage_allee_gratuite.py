# -*- coding: utf-8 -*-
"""AOF50 — la plus grande allée à compte constant (bâtiment C : 1,90 m offerts)."""

import unittest

from core.calepinage.allee_gratuite import chercher_allee_gratuite
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.robustesse import valider_marges
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import KIT_AO_PORTRAIT, Marges, Parametres, Rives
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)


def _ecole():
    return SurfaceRectangle(repere="BAT_C_ECOLE", longueur_m=51.10,
                            largeur_m=25.62, rives=RIVES_AO)


def _parametres(allee=0.60):
    return Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO, allee_m=allee,
                      pas_recherche_m=0.01)


class LeBatimentCOffre190(unittest.TestCase):
    def setUp(self):
        self.resultat = chercher_allee_gratuite(
            _ecole(), _parametres(), appliquer_regles(ECOLE_OBSTACLES))

    def test_le_compte_de_reference_est_314(self):
        self.assertEqual(self.resultat.compte_reference, 314)

    def test_l_intervalle_gratuit_part_de_060(self):
        self.assertAlmostEqual(self.resultat.allee_min_m, 0.60)

    def test_l_intervalle_gratuit_couvre_au_moins_194(self):
        """L'audit adversarial du 27/07 annonçait 1,94 — le moteur trouve plus."""
        self.assertGreaterEqual(self.resultat.allee_max_m, 1.94)
        self.assertTrue(self.resultat.gratuite)

    def test_la_valeur_publiable_est_190(self):
        self.assertAlmostEqual(self.resultat.allee_publiable_m, 1.90, delta=1e-9)

    def test_le_compte_ne_bouge_pas_a_l_allee_publiee(self):
        self.assertEqual(self.resultat.compte_publiable, 314)

    def test_on_offre_130_m_d_allee_de_maintenance(self):
        self.assertAlmostEqual(self.resultat.gain_m, 1.30, delta=1e-9)

    def test_la_bascule_est_verifiee_et_non_supposee(self):
        self.assertTrue(self.resultat.bascule_verifiee)

    def test_le_plan_a_allee_large_repasse_tous_les_garde_fous(self):
        self.assertTrue(self.resultat.valide, self.resultat.motifs)
        self.assertEqual(self.resultat.motifs, ())
        troncon_cm, bande_cm = self.resultat.marges_cm
        ok, motifs = valider_marges(Marges(troncon_min_m=troncon_cm / 100.0,
                                           bande_min_m=bande_cm / 100.0))
        self.assertTrue(ok, motifs)

    def test_les_rangees_publiees_sont_espacees_de_l_allee_publiable(self):
        rangees = self.resultat.rangees
        self.assertEqual(len(rangees), 4)
        emprise = KIT_AO_PORTRAIT.emprise_transversale_m
        for gauche, droite in zip(rangees, rangees[1:]):
            self.assertGreaterEqual(droite[0] - (gauche[0] + emprise),
                                    self.resultat.allee_publiable_m - 1e-9)


class QuandRienNEstGratuit(unittest.TestCase):
    def test_une_surface_juste_a_la_bonne_taille_n_offre_rien(self):
        # deux rangées exactement : 0,35 + 4,70 + 0,60 + 4,70 + 0,35 = 10,70
        surface = SurfaceRectangle(repere="SERRE", longueur_m=20.0,
                                   largeur_m=10.70, rives=RIVES_AO)
        resultat = chercher_allee_gratuite(surface, _parametres())
        self.assertAlmostEqual(resultat.allee_publiable_m, 0.60, delta=1e-9)
        self.assertAlmostEqual(resultat.gain_m, 0.0, delta=1e-9)

    def test_une_surface_sans_contrainte_haute_reste_bornee(self):
        surface = SurfaceRectangle(repere="VASTE", longueur_m=20.0,
                                   largeur_m=10.70, rives=RIVES_AO)
        resultat = chercher_allee_gratuite(surface, _parametres(),
                                           allee_max_m=0.61)
        self.assertLessEqual(resultat.allee_max_m, 0.61)


class SeuilsDeMargesPersonnalises(unittest.TestCase):
    def test_des_seuils_severes_refusent_l_allee_large(self):
        resultat = chercher_allee_gratuite(
            _ecole(), _parametres(), appliquer_regles(ECOLE_OBSTACLES),
            seuils_marges=(1.0, 1.0))
        self.assertFalse(resultat.valide)
        self.assertTrue(resultat.motifs)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
