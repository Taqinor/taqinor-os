"""AMET15 — garde statique de la table de parcours PA5 « Chantier -> SAV ».

``apps/installations/parcours/PA5.json`` décrit la création du chantier depuis
le devis jusqu'au ticket SAV. Cette garde la confronte au CODE par analyse AST,
sans base de données : chaque ``declencheur.source``, ``fonction_entree``,
``checkpoint.persistance`` et ``regles_aval[].source`` désigne un symbole qui
existe, chaque étape porte 1 déclencheur, 1 entrée, 1 checkpoint, >= 1 règle
aval, et chaque effet automatique porte sa ``compensation`` (annulation,
réouverture).

Lancer : ``python -m unittest apps.installations.test_parcours_pa5`` (depuis
``backend/django_core``).
"""
import ast
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]  # backend/django_core
TABLE = json.loads(
    (Path(__file__).resolve().parent / 'parcours' / 'PA5.json')
    .read_text(encoding='utf-8'))
TYPES_DECLENCHEUR = {'signal', 'tache', 'http', 'manuel'}


def _symbole_existe(reference):
    """``chemin.py::Classe.methode`` ou ``chemin.py::fonction`` -> bool (AST)."""
    chemin, _, nom = reference.partition('::')
    fichier = RACINE / chemin
    if not nom or not fichier.is_file():
        return False
    portee = ast.parse(fichier.read_text(encoding='utf-8'))
    for morceau in nom.split('.'):
        for noeud in getattr(portee, 'body', []):
            if isinstance(noeud, (ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef)) \
                    and noeud.name == morceau:
                portee = noeud
                break
        else:
            return False
    return True


class ParcoursPA5Tests(unittest.TestCase):

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertTrue(TABLE['etapes'])
        ids = [e['id'] for e in TABLE['etapes']]
        self.assertEqual(len(ids), len(set(ids)), 'identifiants dupliqués')
        for etape in TABLE['etapes']:
            ident = etape['id']
            for cle in ('declencheur', 'fonction_entree', 'checkpoint',
                        'regles_aval'):
                self.assertIn(cle, etape, f'{ident} : « {cle} » absent')
            declencheur = etape['declencheur']
            self.assertIn(declencheur.get('type'), TYPES_DECLENCHEUR, ident)
            self.assertTrue(_symbole_existe(declencheur['source']),
                            f'{ident} : déclencheur introuvable '
                            f'{declencheur["source"]}')
            self.assertTrue(_symbole_existe(etape['fonction_entree']),
                            f'{ident} : fonction_entree introuvable '
                            f'{etape["fonction_entree"]}')
            persistance = etape['checkpoint']['persistance']
            self.assertTrue(_symbole_existe(persistance),
                            f'{ident} : persistance introuvable {persistance}')
            self.assertGreaterEqual(len(etape['regles_aval']), 1, ident)
            for regle in etape['regles_aval']:
                self.assertTrue(regle['regle'].strip(), ident)
                self.assertTrue(_symbole_existe(regle['source']),
                                f'{ident} : règle aval introuvable '
                                f'{regle["source"]}')

    def test_chaque_effet_automatique_porte_sa_compensation(self):
        automatiques = [e for e in TABLE['etapes'] if e['effet_automatique']]
        self.assertTrue(automatiques)
        for etape in automatiques:
            ident = etape['id']
            self.assertIn('compensation', etape, f'{ident} : compensation')
            self.assertTrue(etape['compensation']['regle'].strip(), ident)
            self.assertTrue(
                _symbole_existe(etape['compensation']['source']),
                f'{ident} : compensation introuvable '
                f'{etape["compensation"]["source"]}')
        for etape in TABLE['etapes']:
            if not etape['effet_automatique']:
                self.assertNotIn('compensation', etape, etape['id'])

    def test_les_references_pointent_des_fichiers_existants(self):
        self.assertTrue(TABLE['references'])
        for chemin in TABLE['references']:
            self.assertTrue((RACINE / chemin).is_file(), chemin)


if __name__ == '__main__':
    unittest.main()
