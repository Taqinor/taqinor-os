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
#: selectors*/services*)`` — valeurs mesurées sur la branche de la vague 1
#: (origin/main 3cd507aa4 : 18/1 et 38/5), à ne faire que BAISSER.
#: Hors portes aujourd'hui : ventes/dsr_provider.py ; calepinage/services/
#: {autoconsommation,batterie,consommation,profils_types}.py, views/pompage.py.
PLAFONDS = {
    ('ventes', 'calepinage'): (18, 1),
    # ACAL997 : +1 — ``selectors_devis.py`` (module frère des sélecteurs lus
    # par ventes) relit ``ventes.selectors``/``selectors_calepinage`` pour la
    # fraîcheur de la conception, comme ``selectors.ombrage_servi``.
    ('calepinage', 'ventes'): (41, 5),
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


def depassements(app, cible, importent, hors, plafond, plafond_hors):
    """Les messages d'échec (vide = sous les plafonds), fichiers nommés."""
    messages = []
    for liste, borne, quoi in (
            (importent, plafond, 'importent'),
            (hors, plafond_hors,
             'importent un module hors selectors*/services* de')):
        if len(liste) > borne:
            messages.append(
                f'{len(liste)} fichiers de apps/{app} {quoi} apps.{cible} '
                f'(plafond {borne}) — passez par les selectors/services de '
                f'apps/{cible}. Fichiers : {liste}')
    return messages


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
            self.assertTrue(importent, 'lecture vide : la garde ne garde rien')
            self.assertEqual(depassements(app, cible, importent, hors,
                                          plafond, plafond_hors), [])
            if (len(importent), len(hors)) < (plafond, plafond_hors):
                print(f'ACAL1009 : apps/{app} -> apps.{cible} est descendu à '
                      f'{len(importent)}/{len(hors)} : baissez le plafond.')

    def test_plafond_moins_un_echoue_en_nommant_le_fichier(self):
        importent, hors = mesurer('ventes', 'calepinage')
        plafond, plafond_hors = PLAFONDS[('ventes', 'calepinage')]
        messages = depassements('ventes', 'calepinage', importent, hors,
                                plafond - 1, plafond_hors)
        self.assertEqual(len(messages), 1)
        self.assertIn(importent[0], messages[0])

    def test_import_de_coherence_registre_ajoute_echoue(self):
        importent, hors = mesurer('calepinage', 'ventes')
        plafond, plafond_hors = PLAFONDS[('calepinage', 'ventes')]
        neuf = 'calepinage/services/nouveau.py'
        source = 'from apps.ventes.coherence.registre import TOLERANCES\n'
        self.assertTrue(hors_portes(modules_importes(source, 'ventes')))
        messages = depassements('calepinage', 'ventes', importent + [neuf],
                                hors + [neuf], plafond, plafond_hors)
        self.assertEqual(len(messages), 2)
        self.assertIn(neuf, messages[1])
