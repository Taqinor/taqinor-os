"""AMET11 (C-AMET-025, C15) — garde STATIQUE de la table du parcours PA2.

``apps/calepinage/parcours/PA2.json`` décrit le parcours « Conception »
(METHODE §D.1). Chaque ``declencheur.source``, ``fonction_entree``,
``checkpoint.persistance``, porte et écrivain automatique est un
``chemin::Symbole`` (relatif à ``backend/django_core``) résolu par AST — sans
base, sans import de Django. Chaque étape porte 1 déclencheur, 1 entrée,
1 checkpoint et ≥ 1 règle aval de la légende.

Run (sans base) :
    python -m unittest apps.calepinage.tests.test_parcours_pa2
"""
import ast
import json
import pathlib
import unittest

RACINE = pathlib.Path(__file__).resolve().parents[3]  # backend/django_core
TABLE = RACINE / 'apps' / 'calepinage' / 'parcours' / 'PA2.json'
TYPES_DECLENCHEUR = {'clic', 'evenement', 'beat', 'manuel'}
REGLES = {'recalcul', 'preserve_manuel', 'fige', 'reference',
          'choix_explicite', 'refus_409', 'ecrase', 'non_propage'}

_ARBRES = {}


def _noms_definis(corps):
    """``{nom: nœud}`` des fonctions, classes et affectations d'un corps."""
    noms = {}
    for noeud in corps:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms[noeud.name] = noeud
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    noms[cible.id] = noeud
        elif isinstance(noeud, ast.AnnAssign) and isinstance(
                noeud.target, ast.Name):
            noms[noeud.target.id] = noeud
    return noms


def resoudre(reference):
    """Message d'erreur si ``chemin::A.B`` ne résout pas, sinon ``None``."""
    if not isinstance(reference, str) or '::' not in reference:
        return f'référence mal formée : {reference!r}'
    chemin, symbole = reference.split('::', 1)
    fichier = RACINE / chemin
    if not fichier.is_file():
        return f'fichier absent : {chemin}'
    if chemin not in _ARBRES:
        _ARBRES[chemin] = ast.parse(fichier.read_text(encoding='utf-8'))
    corps = _ARBRES[chemin].body
    for partie in symbole.split('.'):
        noeud = _noms_definis(corps).get(partie)
        if noeud is None:
            return f'symbole introuvable : {reference}'
        corps = getattr(noeud, 'body', [])
    return None


def charger():
    return json.loads(TABLE.read_text(encoding='utf-8'))


class ParcoursPA2Tests(unittest.TestCase):
    def setUp(self):
        self.table = charger()

    def test_chaque_etape_est_complete_et_resolue(self):
        erreurs = []
        etapes = self.table['etapes']
        self.assertGreaterEqual(len(etapes), 10)
        ids = [e['id'] for e in etapes]
        self.assertEqual(len(ids), len(set(ids)), 'identifiant dupliqué')
        portes = {p['id'] for p in self.table['portes']}
        for etape in etapes:
            eid = etape['id']
            declencheur = etape.get('declencheur') or {}
            if declencheur.get('type') not in TYPES_DECLENCHEUR:
                erreurs.append(f'{eid} : type de déclencheur invalide')
            checkpoint = etape.get('checkpoint') or {}
            if not isinstance(checkpoint.get('modifiable'), bool):
                erreurs.append(f'{eid} : checkpoint.modifiable absent')
            for champ, ref in (
                    ('declencheur.source', declencheur.get('source')),
                    ('fonction_entree', etape.get('fonction_entree')),
                    ('checkpoint.persistance',
                     checkpoint.get('persistance'))):
                probleme = resoudre(ref)
                if probleme:
                    erreurs.append(f'{eid} {champ} : {probleme}')
            regles = etape.get('regle_aval') or []
            if not regles or set(regles) - REGLES:
                erreurs.append(f'{eid} : regle_aval vide ou hors légende')
            for ref in (etape.get('provenance') or {}).get(
                    'ecrivains_auto') or []:
                probleme = resoudre(ref)
                if probleme:
                    erreurs.append(f'{eid} ecrivain_auto : {probleme}')
            for porte in etape.get('portes') or []:
                if porte not in portes:
                    erreurs.append(f'{eid} : porte inconnue {porte}')
            suite = etape.get('suite')
            if suite is not None and suite not in ids:
                erreurs.append(f'{eid} : suite inconnue {suite}')
            for chemin in [etape.get('test_nomme')] + list(
                    etape.get('contrats') or []):
                if chemin and not (RACINE / chemin).is_file():
                    erreurs.append(f'{eid} : fichier absent {chemin}')
        self.assertEqual(erreurs, [])

    def test_portes_de_creation_resolues(self):
        portes = self.table['portes']
        sources = {p['source'] for p in portes}
        self.assertIn(
            'apps/calepinage/views/calepinages.py::CalepinageViewSet.create',
            sources)
        self.assertIn('apps/calepinage/views/depuis_lead.py::depuis_lead',
                      sources)
        self.assertEqual(
            [(p['id'], resoudre(p['source'])) for p in portes
             if resoudre(p['source'])], [])

    def test_le_resolveur_refuse_un_symbole_casse(self):
        """Test du test : un ``fonction_entree`` cassé est détecté."""
        self.assertIsNone(resoudre(
            'apps/calepinage/services/devis.py::generer_devis'))
        self.assertIsNotNone(resoudre(
            'apps/calepinage/services/devis.py::generer_devis_fantome'))
        self.assertIsNotNone(resoudre(
            'apps/calepinage/views/calepinages.py::'
            'CalepinageViewSet.inexistante'))
        self.assertIsNotNone(resoudre('apps/calepinage/absent.py::x'))


if __name__ == '__main__':
    unittest.main()
