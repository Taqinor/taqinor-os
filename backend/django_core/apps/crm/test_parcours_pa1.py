"""Garde statique de la table PA1 « Contact → visite » (AMET18, METHODE v3 §D.1).

Sans base : AST et texte, via l'unique résolveur ``core.parcours``. La cadence de
suivi a sa propre sous-table (``parcours_suivi.json``), référencée et jamais recopiée.
"""
import copy
import unittest
from pathlib import Path

from core import parcours

TABLE = Path(__file__).resolve().parent / 'parcours' / 'PA1.json'


class ParcoursPA1Tests(unittest.TestCase):
    def setUp(self):
        self.table = parcours.charger_table(TABLE)

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertEqual(parcours.problemes_de_la_table(self.table), [])

    def test_treize_portes_resolues_et_sous_table_referencee(self):
        self.assertEqual(len(self.table['portes']), 13)
        for porte in self.table['portes'] + self.table['sous_tables']:
            self.assertEqual(parcours.resoudre_symbole(porte), (True, ''), porte)
        for etape in parcours.etapes(self.table):
            self.assertTrue(etape['provenance']['ecrivains_auto'], etape['id'])

    def test_mutant_fonction_entree_cassee_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        mutant['etapes'][0]['fonction_entree'] += '_inexistante'
        problemes = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any('fonction_entree' in p for p in problemes), problemes)


if __name__ == '__main__':
    unittest.main()
