"""AMET11 (C-AMET-025) — garde statique de la table PA2 « Conception ».

Sans base ni Django : la table ``apps/calepinage/parcours/PA2.json`` est lue
et chaque référence ``fichier::Symbole`` résolue par AST avec LE résolveur du
dépôt (``core/parcours.py``, METHODE v3 §D.1) — aucune seconde implémentation.

Run :
    python -m unittest apps.calepinage.tests.test_parcours_pa2
"""
import copy
import pathlib
import unittest

from core import parcours

TABLE = pathlib.Path(__file__).resolve().parents[1] / 'parcours' / 'PA2.json'


def _references(noeud):
    """Toutes les chaînes ``fichier[::Symbole]`` de la table (portes, tests,
    contrats, écrivains automatiques, composants d'écran…)."""
    if isinstance(noeud, dict):
        for valeur in noeud.values():
            yield from _references(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from _references(valeur)
    elif parcours.est_une_reference(noeud):
        yield noeud


class ParcoursPA2Tests(unittest.TestCase):
    def setUp(self):
        self.table = parcours.charger_table(TABLE)

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertEqual(parcours.problemes_de_la_table(self.table), [])
        self.assertEqual(self.table['id'], 'PA2')
        ids = [etape['id'] for etape in parcours.etapes(self.table)]
        suites = {etape.get('suite') for etape in parcours.etapes(self.table)}
        self.assertLessEqual(suites - {'fin'}, set(ids), 'suite vers une étape absente')
        for porte in self.table['portes']:
            self.assertEqual(parcours.resoudre_symbole(porte['ref']), (True, ''), porte)
        for etape in parcours.etapes(self.table):
            self.assertTrue(parcours.est_une_reference(etape['test_nomme']), etape['id'])
        motifs = [f'{ref} — {motif}' for ref in _references(self.table)
                  for ok, motif in [parcours.resoudre_symbole(ref)] if not ok]
        self.assertEqual(motifs, [])

    def test_une_fonction_d_entree_cassee_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        etape = mutant['etapes'][0]
        etape['fonction_entree'] += '_casse'
        erreurs = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any(e.startswith(f"{etape['id']} : fonction_entree") for e in erreurs), erreurs)
