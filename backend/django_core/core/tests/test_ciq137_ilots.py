"""CIQ137 — îlots bornés avec allées coupe-feu, respectés par la pose, le
comptage ET la contenance du devis (même grille).

Python pur : ``python -m unittest core.tests.test_ciq137_ilots``.
"""
import unittest

from core.calepinage.ilots import (
    bandes_allees, lire_contraintes, module_hors_allees, regle_ilots,
    zones_allees,
)
from core.calepinage.optimum import calculer
from core.calepinage.politique_pas import Affleurant
from core.calepinage.poseur import poser_plan
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    Kit, OrientationModule, Parametres, Rives,
)

KIT = Kit(code='M', libelle='Module', module_long_m=2.278,
          module_court_m=1.134, puissance_module_wc=720.0,
          inclinaison_deg=5.0, orientation=OrientationModule.PORTRAIT,
          modules_par_table=1)
CONTRAINTES_FM = {'ilot_max_m': {'longueur': 46.0, 'largeur': 46.0},
                  'allee_ilot_m': 1.2,
                  'source': {'document': 'FM Global DS 1-15',
                             'reference': '§2.1.1.4'}}


def _poser(zones=()):
    rives = Rives(laterale_m=0.5, extremite_m=0.5)
    surface = SurfaceRectangle(repere='PAN', longueur_m=100.0, largeur_m=20.0,
                               rives=rives)
    parametres = Parametres(kits=(KIT,), rives=rives)
    resultat = calculer(surface, parametres, zones=zones,
                        politique=Affleurant())
    rangees = tuple((y0, parametres.kit(code))
                    for y0, code in resultat.rangees)
    return resultat.modules, poser_plan(surface, rangees, (), zones)


class IlotsTests(unittest.TestCase):
    def test_pan_100_x_20_deux_allees_transversales_vides(self):
        longueur, largeur, allee, _c = lire_contraintes(CONTRAINTES_FM)
        bandes = bandes_allees(0.0, 100.0, longueur, allee)
        self.assertEqual(len(bandes), 2)
        self.assertAlmostEqual(bandes[0][0], 46.0)
        self.assertAlmostEqual(bandes[1][0], 93.2)
        zones = zones_allees('PAN', (0.0, 100.0, 0.0, 20.0), longueur,
                             largeur, allee)
        modules, tables = _poser(zones)
        self.assertGreater(modules, 0)
        for a, b in bandes:
            for table in tables:
                self.assertFalse(table.x0 < b - 1e-9 and table.x1 > a + 1e-9,
                                 (table, a, b))

    def test_contenance_meme_grille_jamais_plus_que_le_moteur(self):
        """La contenance du devis (filtre sur la pose existante) lit la MÊME
        grille d'îlots que le moteur : elle ne promet JAMAIS plus de modules
        que le calepinage n'en pose (le moteur, lui, re-pave chaque îlot)."""
        longueur, largeur, allee, _c = lire_contraintes(CONTRAINTES_FM)
        bornes = (0.0, 100.0, 0.0, 20.0)
        _sans, tables_sans = _poser()
        modules, _tables = _poser(zones_allees('PAN', bornes, longueur,
                                               largeur, allee))
        gardees = [t for t in tables_sans if module_hors_allees(
            (t.x0, t.x1, t.y0, t.y1), bornes, longueur, largeur, allee)]
        self.assertLessEqual(len(gardees), modules)
        self.assertGreater(len(gardees), 0)
        for t in gardees:
            for a, b in bandes_allees(0.0, 100.0, longueur, allee):
                self.assertFalse(t.x0 < b - 1e-9 and t.x1 > a + 1e-9)

    def test_sans_contrainte_rien_ne_change(self):
        self.assertIsNone(lire_contraintes({}))
        self.assertIsNone(lire_contraintes(None))
        self.assertEqual(zones_allees('PAN', (0, 100, 0, 20), 46, 46, 0), ())
        modules_a, _ = _poser()
        modules_b, _ = _poser(())
        self.assertEqual(modules_a, modules_b)

    def test_regle_publiee_avec_la_source(self):
        longueur, largeur, allee, citation = lire_contraintes(CONTRAINTES_FM)
        phrase = regle_ilots(longueur, largeur, allee, citation)
        self.assertIn('46.0 × 46.0', phrase)
        self.assertIn('DS 1-15', phrase)


if __name__ == '__main__':
    unittest.main()
