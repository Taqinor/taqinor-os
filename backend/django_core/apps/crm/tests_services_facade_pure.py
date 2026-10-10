"""SPL26 — garde « façade pure » de `crm/services.py` (fichier SÉPARÉ : le
golden SPL1, `tests_services_split_golden.py`, n'est jamais édité).

Après la scission SPL3-SPL25, `services.py` ne contient plus que son
docstring, `logger`, le bloc de réexport T-TRACE (`from .visites import`) et
les lignes de façade `from .<module> import (...)  # noqa: F401 — façade`
gardées pour les appelants d'un AUTRE propriétaire. Surface append-only
(`docs/ownership.yml`) : on y ajoute une ligne de façade, jamais un corps.

Lecture AST uniquement (aucune regex sur le code, aucun mock) : DB-free.
"""
import ast

from django.test import SimpleTestCase

from apps.crm.tests_services_split_golden import (
    EXCEPTIONS_NOMS, _fichiers_backend, _ICI, _paquet_du_fichier,
    charger_golden, references,
)

_SERVICES = _ICI / 'services.py'
_MODULE = 'apps.crm.services'


def _source():
    return _SERVICES.read_text(encoding='utf-8')


def _imports_relatifs(arbre):
    return [n for n in arbre.body
            if isinstance(n, ast.ImportFrom) and n.level == 1]


def reexports():
    """{nom réexporté: module source} — hors bloc T-TRACE (`.visites`)."""
    out = {}
    for n in _imports_relatifs(ast.parse(_source())):
        if n.module == 'visites':
            continue
        for a in n.names:
            out[a.asname or a.name] = n.module
    return out


def noms_t_trace():
    return sorted(a.name for n in _imports_relatifs(ast.parse(_source()))
                  if n.module == 'visites' for a in n.names)


def noms_lus_via_services():
    """{nom: [fichiers]} lus via `apps.crm.services` (import, attribut, patch)
    par tout fichier du backend autre que services.py lui-même."""
    cibles = {_MODULE: set()}
    lus = {}
    for p in _fichiers_backend():
        if p.resolve() == _SERVICES.resolve():
            continue
        try:
            src = p.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if 'services' not in src:
            continue
        try:
            refs = references(src, _paquet_du_fichier(p), cibles)
        except SyntaxError:
            continue
        for _mod, nom, _genre in refs:
            lus.setdefault(nom, set()).add(p.name)
    return lus


class FacadePureTests(SimpleTestCase):

    def test_aucune_definition_hors_logger(self):
        arbre = ast.parse(_source())
        intrus = []
        for i, n in enumerate(arbre.body):
            if i == 0 and isinstance(n, ast.Expr) \
                    and isinstance(n.value, ast.Constant):
                continue  # docstring
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(n, ast.Assign) and [
                    getattr(t, 'id', None) for t in n.targets] == ['logger']:
                continue
            intrus.append(f'l.{n.lineno} {type(n).__name__}')
        self.assertEqual(intrus, [])

    def test_seul_import_absolu_logging(self):
        arbre = ast.parse(_source())
        absolus = [ast.unparse(n) for n in arbre.body
                   if isinstance(n, ast.Import)
                   or (isinstance(n, ast.ImportFrom) and n.level == 0)]
        self.assertEqual(absolus, ['import logging'])

    def test_chaque_import_relatif_nomme_un_module_et_porte_noqa_motif(self):
        lignes = _source().splitlines()
        fautes = []
        for n in _imports_relatifs(ast.parse(_source())):
            if not n.module:
                fautes.append(f'l.{n.lineno} : « from . import » (nommer le module)')
                continue
            texte = ' '.join(lignes[n.lineno - 1:n.end_lineno])
            if '# noqa: F401' not in texte:
                fautes.append(f'l.{n.lineno} : sans « # noqa: F401 »')
                continue
            motif = texte.split('# noqa: F401', 1)[1].split(')')[0].strip(' —-')
            if not motif:
                fautes.append(f'l.{n.lineno} : # noqa: F401 sans motif')
        self.assertEqual(fautes, [])

    def test_t_trace_identique_au_golden(self):
        self.assertEqual(noms_t_trace(), sorted(charger_golden()['t_trace']))

    def test_la_facade_du_golden_reste_exposee(self):
        golden = charger_golden()
        exposes = set(reexports()) | set(noms_t_trace())
        self.assertEqual(sorted(set(golden['facade']) - exposes), [])

    def test_chaque_nom_lu_via_services_est_reexporte(self):
        exposes = set(reexports()) | set(noms_t_trace())
        lus = noms_lus_via_services()
        hors = {nom: sorted(f) for nom, f in lus.items()
                if nom not in exposes and nom not in EXCEPTIONS_NOMS
                and not (nom.startswith('__') and nom.endswith('__'))}
        self.assertEqual(hors, {})

    def test_aucune_ligne_de_facade_morte(self):
        golden = set(charger_golden()['facade'])
        lus = noms_lus_via_services()
        morts = sorted(nom for nom in reexports()
                       if nom not in lus and nom not in golden)
        self.assertEqual(morts, [])
