"""AMET13 — garde statique de la table de parcours PA6 « Approvisionnement ».

Sans base : la table ``parcours/PA6.json`` est lue et ses symboles sont résolus par AST
avec le résolveur unique ``core.parcours`` (aucune seconde implémentation).
"""
import copy
import os
import unittest
from pathlib import Path

from core import parcours

TABLE = Path(__file__).resolve().parent / 'parcours' / 'PA6.json'
PORTES_ATTENDUES = {'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7'}


class ParcoursPA6Tests(unittest.TestCase):
    def setUp(self):
        self.table = parcours.charger_table(TABLE)

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertEqual(parcours.problemes_de_la_table(self.table), [])
        for etape in parcours.etapes(self.table):
            self.assertTrue(parcours.est_une_reference(etape['fonction_entree']), etape['id'])
            persistance = etape['checkpoint']['persistance']
            self.assertTrue(parcours.est_une_reference(persistance) or persistance.startswith('n/a'), etape['id'])
            test = etape['test_nomme']
            if not test.startswith('aucun'):
                racine = parcours.RACINE_DJANGO
                self.assertTrue(os.path.isfile(racine / test), f"{etape['id']} : test_nomme introuvable ({test})")

    def test_casser_une_fonction_entree_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        mutant['etapes'][0]['fonction_entree'] = 'apps/stock/services.py::symbole_qui_n_existe_pas'
        problemes = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any('fonction_entree' in p for p in problemes), problemes)

    def test_portes_listent_les_sept_sorties_de_stock(self):
        portes = self.table['portes']
        self.assertEqual({p['id'] for p in portes}, PORTES_ATTENDUES)
        for porte in portes:
            ok, motif = parcours.resoudre_symbole(porte['source'])
            self.assertTrue(ok, f"{porte['id']} : {motif}")
        self.assertTrue(self.table['liens_manquants'], 'les liens manquants sont déclarés, jamais inventés résolus')


if __name__ == '__main__':
    unittest.main()
