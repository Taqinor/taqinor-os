# -*- coding: utf-8 -*-
"""CAL88 — la surface AU SOL : conformité, entraxe, taux d'occupation.

Ce qui est prouvé ici :

* ``SurfaceSol`` passe la SUITE DE CONFORMITÉ du protocole ``Surface``
  (``ConformiteSurface``, AOF38) — le DP, le poseur et les garde-fous n'ont
  donc rien à savoir d'un terrain ;
* l'entraxe SAISI est appliqué tel quel ; l'entraxe ABSENT est CALCULÉ à la
  latitude du site (CAL167) et un terrain sans entraxe NI latitude est REFUSÉ
  en nommant le champ — le noyau ne devine jamais un lieu ;
* le taux d'occupation est une SORTIE mesurée sur le plan posé, jamais une
  entrée ;
* une surface au sol produit un PLAN réel : le moteur d'optimum la calcule
  comme n'importe quelle autre surface ;
* les surfaces de TOITURE sont inchangées : le sol n'est pas sérialisable dans
  le contrat v1 et la sérialisation le REFUSE explicitement, au lieu de le
  dégrader en « polygone » en perdant son entraxe.

Aucune base de données, aucune dépendance : ``unittest`` pur.
"""

import unittest

from core.calepinage.politique_pas import (
    AlleeFixe, AntiOmbrage, position_solaire_solstice,
)
from core.calepinage.serialisation import SchemaIncompatible, surface_vers_dict
from core.calepinage.surfaces.sol import SurfaceSol
from core.calepinage.types import KIT_AO_PORTRAIT, Parametres, Rives

from core.tests.test_calepinage_surfaces import ConformiteSurface

#: Un terrain rectangulaire de 120 m (le long des rangées) × 60 m.
TERRAIN = ((0.0, 0.0), (120.0, 0.0), (120.0, 60.0), (0.0, 60.0))
#: Agadir (30,4°) et Tanger (35,8°) : les deux latitudes que CAL167 oppose.
AGADIR = 30.4
TANGER = 35.8


def _terrain(**champs):
    base = dict(repere='TERRAIN', contour=TERRAIN,
                rives=Rives(laterale_m=2.0, extremite_m=2.0))
    base.update(champs)
    return SurfaceSol(**base)


class SolEstConforme(ConformiteSurface, unittest.TestCase):
    """Le protocole ``Surface`` tient sur un terrain comme sur un toit."""

    def surface(self):
        return _terrain(pas_inter_rangee_m=8.0)

    def y_valide(self):
        return 2.0


class LEntraxeEstSaisiOuCalculeJamaisDevine(unittest.TestCase):

    def test_l_entraxe_saisi_est_applique_tel_quel(self):
        sol = _terrain(pas_inter_rangee_m=8.0)
        self.assertAlmostEqual(sol.entraxe_m(KIT_AO_PORTRAIT), 8.0, places=9)

    def test_l_entraxe_saisi_donne_une_allee_fixe(self):
        sol = _terrain(pas_inter_rangee_m=8.0)
        politique = sol.politique_pas(KIT_AO_PORTRAIT)
        self.assertIsInstance(politique, AlleeFixe)
        self.assertAlmostEqual(
            politique.allee_m,
            8.0 - KIT_AO_PORTRAIT.emprise_transversale_m, places=9)

    def test_sans_entraxe_la_latitude_calcule_le_pas(self):
        sol = _terrain(latitude_deg=AGADIR)
        politique = sol.politique_pas(KIT_AO_PORTRAIT)
        self.assertIsInstance(politique, AntiOmbrage)
        self.assertEqual(politique.latitude_deg, AGADIR)

    def test_agadir_et_tanger_ne_sont_pas_espaces_pareil(self):
        """Le sud monte plus haut : l'ombre est plus courte, le pas plus serré."""
        agadir = _terrain(latitude_deg=AGADIR).entraxe_m(KIT_AO_PORTRAIT)
        tanger = _terrain(latitude_deg=TANGER).entraxe_m(KIT_AO_PORTRAIT)
        self.assertLess(agadir, tanger)
        # Et la cause est bien l'élévation solaire du LIEU, pas un hasard.
        self.assertGreater(position_solaire_solstice(AGADIR)[0],
                           position_solaire_solstice(TANGER)[0])

    def test_sans_entraxe_ni_latitude_le_refus_nomme_le_champ(self):
        sol = _terrain()
        with self.assertRaises(ValueError) as refus:
            sol.politique_pas(KIT_AO_PORTRAIT)
        self.assertIn('latitude_deg', str(refus.exception))

    def test_un_entraxe_plus_court_que_la_table_est_refuse(self):
        sol = _terrain(pas_inter_rangee_m=1.0)
        with self.assertRaises(ValueError) as refus:
            sol.politique_pas(KIT_AO_PORTRAIT)
        self.assertIn('pas_inter_rangee_m', str(refus.exception))

    def test_un_entraxe_negatif_est_refuse_a_la_construction(self):
        with self.assertRaises(ValueError):
            _terrain(pas_inter_rangee_m=-1.0)

    def test_une_latitude_hors_bornes_est_refusee(self):
        with self.assertRaises(ValueError) as refus:
            _terrain(latitude_deg=120.0)
        self.assertIn('latitude_deg', str(refus.exception))

    def test_un_contour_de_deux_sommets_est_refuse(self):
        with self.assertRaises(ValueError):
            SurfaceSol(repere='T', contour=((0.0, 0.0), (1.0, 0.0)))


class LeTauxDOccupationEstUneSortie(unittest.TestCase):

    def test_il_se_mesure_sur_le_plan_pose(self):
        sol = _terrain(pas_inter_rangee_m=8.0)
        aire_module = (KIT_AO_PORTRAIT.module_long_m
                       * KIT_AO_PORTRAIT.module_court_m)
        self.assertAlmostEqual(sol.taux_occupation(KIT_AO_PORTRAIT, 100),
                               100 * aire_module / (120.0 * 60.0), places=9)

    def test_un_plan_vide_rend_un_zero_mesure(self):
        sol = _terrain(pas_inter_rangee_m=8.0)
        self.assertEqual(sol.taux_occupation(KIT_AO_PORTRAIT, 0), 0.0)

    def test_il_croit_quand_on_serre_les_rangees(self):
        serre = _terrain(pas_inter_rangee_m=6.0)
        large = _terrain(pas_inter_rangee_m=12.0)
        self.assertGreater(
            serre.taux_occupation_theorique(KIT_AO_PORTRAIT),
            large.taux_occupation_theorique(KIT_AO_PORTRAIT))

    def test_le_taux_theorique_est_dans_zero_un(self):
        sol = _terrain(pas_inter_rangee_m=8.0)
        taux = sol.taux_occupation_theorique(KIT_AO_PORTRAIT)
        self.assertGreater(taux, 0.0)
        self.assertLess(taux, 1.0)

    def test_le_nombre_de_rangees_tient_dans_la_largeur_utile(self):
        sol = _terrain(pas_inter_rangee_m=8.0)
        rangees = sol.rangees_theoriques(KIT_AO_PORTRAIT)
        self.assertGreaterEqual(rangees, 1)
        etendue = ((rangees - 1) * 8.0
                   + KIT_AO_PORTRAIT.emprise_transversale_m)
        ymin, ymax = sol.bornes_transversales_utiles()
        self.assertLessEqual(etendue, ymax - ymin + 1e-9)


class LeTerrainProduitUnPlanCommeUneToiture(unittest.TestCase):

    def test_le_moteur_pose_des_rangees_sur_un_terrain(self):
        from core.calepinage.optimum import calculer as calculer_optimum

        sol = _terrain(pas_inter_rangee_m=8.0)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,),
                                rives=sol.rives,
                                axe_rangee=sol.axe_rangee)
        resultat = calculer_optimum(sol, parametres, (), (),
                                    sol.politique_pas(KIT_AO_PORTRAIT))
        self.assertGreater(resultat.modules, 0)
        self.assertGreater(len(resultat.rangees), 1)
        # Le taux d'occupation du plan RÉELLEMENT posé est cohérent.
        taux = sol.taux_occupation(KIT_AO_PORTRAIT, resultat.modules)
        self.assertGreater(taux, 0.0)
        self.assertLess(taux, 1.0)


class LeSolNeContaminePasLesToitures(unittest.TestCase):

    def test_le_contrat_v1_refuse_le_sol_explicitement(self):
        """Refusé EN NOMMANT le problème — jamais dégradé en « polygone »."""
        with self.assertRaises(SchemaIncompatible) as refus:
            surface_vers_dict(_terrain(pas_inter_rangee_m=8.0))
        self.assertIn('SurfaceSol', str(refus.exception))

    def test_le_polygone_de_toiture_se_serialise_toujours(self):
        from core.calepinage.surfaces.polygone import SurfacePolygone

        document = surface_vers_dict(
            SurfacePolygone(repere='PAN', contour=TERRAIN))
        self.assertEqual(document['type'], 'polygone')

    def test_le_sol_n_est_pas_un_polygone(self):
        from core.calepinage.surfaces.polygone import SurfacePolygone

        self.assertNotIsInstance(_terrain(pas_inter_rangee_m=8.0),
                                 SurfacePolygone)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
