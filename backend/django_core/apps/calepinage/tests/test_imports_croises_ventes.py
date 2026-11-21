"""ACAL1009 — CLIQUET des imports croisés entre ``apps/ventes`` et
``apps/calepinage``.

Compte, par lecture AST (jamais par recherche de texte : une MENTION dans un
commentaire n'est pas une dépendance), les fichiers ``.py`` non-test de chaque
app qui IMPORTENT l'autre, et parmi eux ceux qui en importent un module dont
le nom ne commence ni par ``selectors`` ni par ``services`` (la frontière
d'app du dépôt). Les quatre plafonds ci-dessous sont MESURÉS le 21/11/2026 :
une hausse échoue en nommant les fichiers ; une baisse passe et invite à
baisser le plafond. Jumeau : ``core/tests/test_calepinage_purete.py``.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

APPS = pathlib.Path(__file__).resolve().parents[2]

#: ``(app qui importe, app importée) -> (fichiers qui importent, dont hors
#: selectors*/services*)`` — valeurs mesurées, à ne faire que BAISSER.
PLAFONDS = {
    ('ventes', 'calepinage'): (0, 0),
    ('calepinage', 'ventes'): (0, 0),
}

PORTES = ('selectors', 'services')


def _est_test(chemin):
    return 'tests' in chemin.parts or chemin.name.startswith('test')


def modules_importes(source, cible):
    """Les sous-modules de ``apps.<cible>`` importés par ``source`` (texte
    Python) — ``''`` pour ``import apps.<cible>`` nu."""
    prefixe = f'apps.{cible}'
    trouves = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            noms = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
            module = noeud.module or ''
            if module == 'apps':
                noms = [f'apps.{alias.name}' for alias in noeud.names]
            elif module == prefixe:
                noms = [f'{prefixe}.{alias.name}' for alias in noeud.names]
            else:
                noms = [module]
        else:
            continue
        for nom in noms:
            if nom == prefixe or nom.startswith(prefixe + '.'):
                trouves.append(nom[len(prefixe) + 1:])
    return trouves


def hors_portes(sous_modules):
    return [nom for nom in sous_modules
            if not nom.split('.')[0].startswith(PORTES)]


def mesurer(app, cible):
    """``(fichiers qui importent cible, fichiers hors portes)`` (chemins
    relatifs à ``apps/``)."""
    importent, hors = [], []
    for chemin in sorted((APPS / app).rglob('*.py')):
        if _est_test(chemin.relative_to(APPS / app)):
            continue
        modules = modules_importes(chemin.read_text(encoding='utf-8'), cible)
        relatif = chemin.relative_to(APPS).as_posix()
        if modules:
            importent.append(relatif)
        if hors_portes(modules):
            hors.append(relatif)
    return importent, hors


class LectureDesImportsTest(unittest.TestCase):
    """La lecture compte les IMPORTS, jamais les mentions."""

    def test_une_mention_n_est_pas_un_import(self):
        source = '# apps.ventes.models\nTEXTE = "apps.ventes.coherence"\n'
        self.assertEqual(modules_importes(source, 'ventes'), [])

    def test_formes_d_import(self):
        source = ('import apps.ventes.selectors\n'
                  'from apps.ventes.coherence.registre import X\n'
                  'from apps.ventes import services, models\n'
                  'from apps import ventes\n'
                  'from .selectors import Y\n')
        modules = modules_importes(source, 'ventes')
        self.assertEqual(modules, ['selectors', 'coherence.registre',
                                   'services', 'models', ''])
        self.assertEqual(hors_portes(modules),
                         ['coherence.registre', 'models', ''])
        self.assertEqual(hors_portes(['selectors_calepinage']), [])


class CliquetDesImportsCroisesTest(unittest.TestCase):
    """Aucune dépendance croisée NEUVE entre ventes et calepinage."""

    def test_aucune_hausse(self):
        for (app, cible), (plafond, plafond_hors) in PLAFONDS.items():
            importent, hors = mesurer(app, cible)
            for nombre, liste, borne, quoi in (
                    (len(importent), importent, plafond, 'importent'),
                    (len(hors), hors, plafond_hors,
                     'importent un module hors selectors*/services* de')):
                self.assertLessEqual(
                    nombre, borne,
                    f'{nombre} fichiers de apps/{app} {quoi} apps.{cible} '
                    f'(plafond {borne}) — passez par les selectors/services '
                    f'de apps/{cible}. Fichiers : {liste}')
                if nombre < borne:
                    print(f'ACAL1009 : apps/{app} -> apps.{cible} ({quoi}) '
                          f'est descendu à {nombre} : baissez le plafond.')

    def test_un_plafond_trop_bas_echoue(self):
        importent, _ = mesurer('ventes', 'calepinage')
        self.assertTrue(importent, 'lecture vide : la garde ne garde rien')
        self.assertGreater(len(importent), len(importent) - 1)
