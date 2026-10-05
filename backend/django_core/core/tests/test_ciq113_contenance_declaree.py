"""CIQ113 — contenance estimée d'une surface DÉCLARÉE par le vrai moteur.

Python pur (aucune base) : ``python -m unittest
core.tests.test_ciq113_contenance_declaree``.
"""
import ast
import os
import re
import unittest

from core.calepinage.contenance_declaree import contenance_surface_declaree

CHEMIN = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                      'calepinage', 'contenance_declaree.py')
MODULE = (2.384, 1.303)


def _f(surface=300, mode='bac_acier', cotes=MODULE, incl=5.0, lat=33.6):
    return contenance_surface_declaree(
        surface, mode_pose=mode, cotes_module_m=cotes, inclinaison_deg=incl,
        latitude_deg=lat, puissance_module_wc=720)


class ContenanceTests(unittest.TestCase):
    def test_bac_acier_borne_par_l_aire(self):
        r = _f()
        self.assertIsNone(r['motif'])
        self.assertGreater(r['nb_modules'], 0)
        self.assertLessEqual(r['nb_modules'],
                             int(300 // (MODULE[0] * MODULE[1])))
        self.assertAlmostEqual(r['kwc'], r['nb_modules'] * 0.72, places=3)
        cles = {h['cle'] for h in r['hypotheses']}
        self.assertIn('forme', cles)
        self.assertIn('obstacles', cles)

    def test_toit_plat_leste_moins_qu_affleurant(self):
        affleurant = _f(mode='bac_acier', incl=13.0)
        leste = _f(mode='toit_plat_leste', incl=13.0, lat=33.6)
        self.assertLess(leste['nb_modules'], affleurant['nb_modules'])

    def test_sol_et_ombriere_none_avec_motif(self):
        for mode in ('sol', 'ombriere'):
            r = _f(mode=mode)
            self.assertIsNone(r['nb_modules'])
            self.assertIn('sol / ombrière', r['motif'])

    def test_fiche_sans_dimensions_none_avec_motif(self):
        for cotes in (None, (None, 1.3), ()):
            r = _f(cotes=cotes)
            self.assertIsNone(r['nb_modules'])
            self.assertIn('dimensions du module', r['motif'])

    def test_aucune_constante_surfacique(self):
        texte = open(CHEMIN, encoding='utf-8').read()
        self.assertIsNone(re.search(r'm²\s*/\s*kWc|m2_par_kwc|M2_PAR_KWC',
                                    texte))
        self.assertNotIn('6.0', texte)

    def test_module_pur(self):
        arbre = ast.parse(open(CHEMIN, encoding='utf-8').read())
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                self.assertTrue((noeud.module or '').startswith(
                    'core.calepinage'), noeud.module)
            elif isinstance(noeud, ast.Import):
                self.assertEqual(noeud.names[0].name, 'math')


if __name__ == '__main__':
    unittest.main()
