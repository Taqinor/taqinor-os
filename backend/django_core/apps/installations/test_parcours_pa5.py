"""Garde statique de la table de parcours PA5 « Chantier -> SAV » (AMET15) — sans base."""
import copy
import unittest

from core import parcours

CHEMIN = parcours.RACINE_DJANGO / 'apps' / 'installations' / 'parcours' / 'PA5.json'


class ParcoursPA5Tests(unittest.TestCase):
    def test_chaque_etape_est_complete_et_resolue(self):
        table = parcours.charger_table(CHEMIN)
        self.assertEqual(parcours.problemes_de_la_table(table), [])
        self.assertEqual(len(parcours.etapes(table)), 7)
        for ref in table['portes']:
            self.assertEqual(parcours.resoudre_symbole(ref), (True, ''), ref)
        for etape in parcours.etapes(table):
            self.assertTrue(str(etape.get('compensation') or '').strip(), etape['id'])
        self.assertTrue(table['etapes_manquantes'])

    def test_mutant_fonction_entree_cassee_fait_echouer_la_garde(self):
        table = copy.deepcopy(parcours.charger_table(CHEMIN))
        table['etapes'][0]['fonction_entree'] = 'apps/installations/services.py::symbole_inexistant_xyz'
        self.assertTrue(parcours.problemes_de_la_table(table))
