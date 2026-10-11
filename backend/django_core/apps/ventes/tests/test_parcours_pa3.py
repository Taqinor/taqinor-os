"""AMET10 (C-AMET-025) — garde statique de la table PA3 « Devis → signature ».

Sans base ni Django : ``apps/ventes/parcours/PA3.json`` est lue et chaque
référence ``fichier::Symbole`` résolue par AST avec LE résolveur du dépôt
(``core/parcours.py``, METHODE v3 §D.1) — aucune seconde implémentation.

Run :
    python -m unittest apps.ventes.tests.test_parcours_pa3
"""
import copy
import pathlib
import unittest

from core import parcours

TABLE = pathlib.Path(__file__).resolve().parents[1] / 'parcours' / 'PA3.json'
STATUTS_8221 = ('en_constitution', 'depose', 'en_instruction', 'complement_demande',
                'approuve', 'refuse', 'comptage_pose')


def _references(noeud):
    if isinstance(noeud, dict):
        for valeur in noeud.values():
            yield from _references(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from _references(valeur)
    elif parcours.est_une_reference(noeud):
        yield noeud


class ParcoursPA3Tests(unittest.TestCase):
    def setUp(self):
        self.table = parcours.charger_table(TABLE)

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertEqual(parcours.problemes_de_la_table(self.table), [])
        self.assertEqual(self.table['id'], 'PA3')
        ids = [etape['id'] for etape in parcours.etapes(self.table)]
        suites = {etape['suite'] for etape in parcours.etapes(self.table)}
        self.assertLessEqual(suites - {'fin'}, set(ids), 'suite vers une étape absente')
        motifs = [f'{ref} — {motif}' for ref in _references(self.table)
                  for ok, motif in [parcours.resoudre_symbole(ref)] if not ok]
        self.assertEqual(motifs, [])

    def test_portes_trois_acceptations_sept_creations(self):
        portes = self.table['portes']
        self.assertEqual(len([p for p in portes if p['type'] == 'acceptation']), 3)
        self.assertEqual(len([p for p in portes if p['type'] == 'creation']), 7)
        accept = [e for e in parcours.etapes(self.table) if e['fonction_entree'].endswith('::accept_devis')]
        self.assertEqual(len(accept), 3)

    def test_82_21_et_moteur_qui_ne_fait_que_rendre(self):
        etapes = {e['id']: e for e in parcours.etapes(self.table)}
        for statut in STATUTS_8221:
            self.assertIn(statut, etapes['PA3-09']['provenance']['marqueur'])
        rendu = etapes['PA3-03']
        self.assertIn('quote_engine/', rendu['fonction_entree'])
        self.assertTrue(rendu['checkpoint']['persistance'].startswith('n/a'))

    def test_une_fonction_d_entree_cassee_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        etape = mutant['etapes'][0]
        etape['fonction_entree'] += '_casse'
        erreurs = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any(e.startswith(f"{etape['id']} : fonction_entree") for e in erreurs), erreurs)
