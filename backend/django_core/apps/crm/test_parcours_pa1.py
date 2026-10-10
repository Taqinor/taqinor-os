"""AMET18 — garde statique de la table de parcours PA1 « Contact -> visite ».

``apps/crm/parcours/PA1.json`` décrit formulaire / ``/crm/leads`` ->
qualification -> cadence de contact -> visite -> ``/visites/revue``. Cette
garde la confronte au CODE par analyse AST, sans base de données : chaque
``declencheur.source``, ``fonction_entree``, ``checkpoint.persistance`` et
``regles_aval[].source`` désigne un symbole qui existe ; ``portes[]`` liste les
13 portes de création de lead ; ``provenance.ecrivains_auto`` nomme les
écrivains automatiques de chaque champ saisi.

Lancer : ``python -m unittest apps.crm.test_parcours_pa1`` (depuis
``backend/django_core``).
"""
import ast
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]  # backend/django_core
TABLE = json.loads(
    (Path(__file__).resolve().parent / 'parcours' / 'PA1.json')
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


class ParcoursPA1Tests(unittest.TestCase):

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

    def test_les_treize_portes_de_creation_de_lead_resolvent(self):
        portes = TABLE['portes']
        self.assertEqual(len(portes), 13)
        self.assertEqual(len({p['id'] for p in portes}), 13)
        for porte in portes:
            self.assertTrue(porte['description'].strip(), porte['id'])
            self.assertTrue(_symbole_existe(porte['source']),
                            f'{porte["id"]} : porte introuvable '
                            f'{porte["source"]}')

    def test_les_ecrivains_automatiques_des_champs_resolvent(self):
        ecrivains = TABLE['provenance']['ecrivains_auto']
        champs = {e['champ'] for e in ecrivains}
        # Meta, placement et fusion sont les trois écrivains nommés au constat.
        self.assertTrue({'meta_ad_id', 'placement_relances',
                         'champs_fusionnes'} <= champs)
        for entree in ecrivains:
            self.assertTrue(entree['ecrivains'], entree['champ'])
            for ecrivain in entree['ecrivains']:
                self.assertTrue(ecrivain['regle'].strip(), entree['champ'])
                self.assertTrue(
                    _symbole_existe(ecrivain['source']),
                    f'{entree["champ"]} : écrivain introuvable '
                    f'{ecrivain["source"]}')

    def test_les_references_pointent_des_fichiers_existants(self):
        self.assertTrue(TABLE['references'])
        for chemin in TABLE['references']:
            self.assertTrue((RACINE / chemin).is_file(), chemin)


if __name__ == '__main__':
    unittest.main()
