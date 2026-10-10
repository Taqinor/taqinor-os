"""AMET8 — garde statique de la table de parcours PA4 « Argent » (METHODE §D.1).

Sans base : la table `apps/facturation/parcours/PA4.json` est lue, ses ancres
`fichier::symbole` sont résolues par AST (Python) ou par recherche du mot
(JS), et `portes` est comparé au balayage réel des créateurs
`Facture.objects.create` / `Paiement.objects.create`.
"""
import ast
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = DJANGO_ROOT.parents[1]
TABLE = DJANGO_ROOT / 'apps' / 'facturation' / 'parcours' / 'PA4.json'
ANCRE = re.compile(r'((?:backend|frontend)/[\w/.\[\]-]+\.(?:py|jsx?|ts))::([\w.]+)')
REGLES = {'recalcul', 'preserve_manuel', 'fige', 'reference', 'choix_explicite',
          'refus_409', 'ecrase', 'non_propage'}


def _ancres(valeur, acc):
    if isinstance(valeur, dict):
        for v in valeur.values():
            _ancres(v, acc)
    elif isinstance(valeur, list):
        for v in valeur:
            _ancres(v, acc)
    elif isinstance(valeur, str):
        acc.update(ANCRE.findall(valeur))
    return acc


def _resout(chemin, symbole):
    fichier = REPO_ROOT / chemin
    if not fichier.is_file():
        return False
    source = fichier.read_text(encoding='utf-8')
    if not chemin.endswith('.py'):
        return re.search(r'\b%s\b' % re.escape(symbole.split('.')[-1]), source) is not None
    noeud = ast.parse(source)
    for i, segment in enumerate(symbole.split('.')):
        # 1er segment : niveau module ; suivants : n'importe où dans le corps
        # (les fonctions imbriquées `_create` vivent dans un try/with).
        candidats = ast.iter_child_nodes(noeud) if i == 0 else ast.walk(noeud)
        trouve = None
        for ch in candidats:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ch.name == segment:
                trouve = ch
                break
            if i == 0 and isinstance(ch, (ast.Assign, ast.AnnAssign)):
                cibles = ch.targets if isinstance(ch, ast.Assign) else [ch.target]
                if any(isinstance(t, ast.Name) and t.id == segment for t in cibles):
                    trouve = ch
                    break
        if trouve is None:
            return False
        noeud = trouve
    return True


def _createurs():
    """{(modele, 'apps/ventes/x.py::symbole')} réellement présents hors tests."""
    trouves = set()
    for p in (DJANGO_ROOT / 'apps').rglob('*.py'):
        rel = p.relative_to(DJANGO_ROOT).as_posix()
        if '/tests' in rel or '/migrations/' in rel or p.name.startswith('test'):
            continue
        try:
            arbre = ast.parse(p.read_text(encoding='utf-8'))
        except SyntaxError:
            continue

        def marche(n, pile):
            for c in ast.iter_child_nodes(n):
                st = pile
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    st = pile + [c.name]
                if (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                        and c.func.attr == 'create'
                        and isinstance(c.func.value, ast.Attribute)
                        and c.func.value.attr == 'objects'
                        and isinstance(c.func.value.value, ast.Name)
                        and c.func.value.value.id in ('Facture', 'Paiement')):
                    trouves.add((c.func.value.value.id,
                                 'backend/django_core/%s::%s' % (rel, '.'.join(pile))))
                marche(c, st)
        marche(arbre, [])
    return trouves


class ParcoursPA4Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.table = json.loads(TABLE.read_text(encoding='utf-8'))

    def test_chaque_etape_est_complete_et_resolue(self):
        etapes = self.table['etapes']
        self.assertTrue(etapes)
        ids = [e['id'] for e in etapes]
        self.assertEqual(len(ids), len(set(ids)))
        for e in etapes:
            i = e['id']
            self.assertEqual(sorted(e['declencheur']), ['source', 'type'], i)
            self.assertIn(e['declencheur']['type'], {'clic', 'evenement', 'beat', 'manuel'}, i)
            self.assertIsInstance(e['fonction_entree'], str, i)
            self.assertEqual(len(ANCRE.findall(e['fonction_entree'])), 1, i)
            self.assertIn('persistance', e['checkpoint'], i)
            self.assertIn('modifiable', e['checkpoint'], i)
            self.assertGreaterEqual(len(e['regle_aval']), 1, i)
            for r in e['regle_aval']:
                self.assertIn(r['type'], REGLES, i)
            self.assertTrue(e['suite'] == 'fin' or e['suite'] in ids, i)
            for chemin, symbole in sorted(_ancres(
                    [e['declencheur'], e['fonction_entree'], e['checkpoint']['persistance']], set())):
                self.assertTrue(_resout(chemin, symbole), '%s : %s::%s introuvable' % (i, chemin, symbole))
            for cle in ('declencheur', 'fonction_entree', 'checkpoint'):
                self.assertTrue(_ancres(e[cle] if cle != 'checkpoint' else e[cle]['persistance'], set()),
                                '%s : %s sans ancre fichier::symbole' % (i, cle))

    def test_portes_listent_tous_les_createurs(self):
        etapes = {e['id'] for e in self.table['etapes']}
        declares = set()
        for modele, portes in self.table['portes'].items():
            for p in portes:
                self.assertIn(p['etape'], etapes, p['source'])
                self.assertTrue(_ancres(p['source'], set()), p['source'])
                declares.add((modele, p['source']))
        self.assertEqual(declares, _createurs())
