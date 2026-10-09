"""Garde statique de la table PA7 « Monitoring et abonnement » (AMET24, METHODE v3 §D.1).

Sans base : AST et texte, via l'unique résolveur ``core.parcours``.
"""
import copy
import unittest
from pathlib import Path

from core import parcours

TABLE = Path(__file__).resolve().parent / 'parcours' / 'PA7.json'
SANS_EMETTEUR = ('equipement_remplace', 'abonnement_monitoring_resilie')


class ParcoursPA7Tests(unittest.TestCase):
    def setUp(self):
        self.table = parcours.charger_table(TABLE)

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertEqual(parcours.problemes_de_la_table(self.table), [])

    def test_mutant_fonction_entree_cassee_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        mutant['etapes'][0]['fonction_entree'] += '_inexistante'
        problemes = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any('fonction_entree' in p for p in problemes), problemes)

    def test_abonnes_sans_emetteur_sont_des_manques_jamais_des_etapes(self):
        manquantes = {m['signal']: m for m in self.table['etapes_manquantes'] if 'signal' in m}
        for signal in SANS_EMETTEUR:
            self.assertIn(signal, manquantes)
            self.assertTrue(manquantes[signal]['negatif'])
            self.assertEqual(parcours.resoudre_symbole(manquantes[signal]['abonne_sans_emetteur']), (True, ''))
            for etape in parcours.etapes(self.table):
                self.assertNotIn(signal, str(etape.get('declencheur')))


if __name__ == '__main__':
    unittest.main()
