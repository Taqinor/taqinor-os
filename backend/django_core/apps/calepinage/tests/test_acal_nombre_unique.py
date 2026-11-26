# -*- coding: utf-8 -*-
"""ACAL323 — UNE lecture tolérante des nombres : ``services/valeurs.nombre``.

LE CONSTAT (C-ACAL-142)
-----------------------
51 copies privées ``_nombre(valeur)`` et 4 ``_flottant(valeur)`` lisaient
« un nombre » chacune à sa façon : ``agregation_electrique`` laissait passer
``nan``/``inf``, ``fixation`` refusait ``'3.5'``, ``production`` rendait
``1.0`` pour ``True``. Toutes délèguent désormais à ``valeurs.nombre`` ; les
variantes d'un AUTRE sens (``sld._nombre_planche`` rend une chaîne,
``modules_stock._cote_positive`` exige > 0, les validateurs à plusieurs
arguments) sont renommées, pas fusionnées.

Ce qui est prouvé ici :

* la table ``[True, False, '3.5', ' 4 ', nan, inf, -1, 0, None, 'abc']`` est
  rendue À L'IDENTIQUE par le ``_nombre``/``_flottant`` de chaque module qui
  en porte un ;
* garde AST : aucune définition ``_nombre`` ou ``_flottant`` à un argument ne
  subsiste (ni ne revient) dans ``apps/calepinage`` hors tests.

Run :
    python manage.py test apps.calepinage.tests.test_acal_nombre_unique
"""
from __future__ import annotations

import ast
import importlib
import math
import pathlib
import unittest

from apps.calepinage.services.valeurs import nombre, pente_du_pan

APP = pathlib.Path(__file__).resolve().parents[1]
NOMS = ('_nombre', '_flottant')

TABLE = [True, False, '3.5', ' 4 ', math.nan, math.inf, -1, 0, None, 'abc']
ATTENDU = [None, None, 3.5, 4.0, None, None, -1.0, 0.0, None, None]


def _sources():
    for chemin in sorted(APP.rglob('*.py')):
        morceaux = chemin.relative_to(APP).parts
        if morceaux[0] in ('tests', 'migrations'):
            continue
        yield chemin


def _module(chemin):
    morceaux = chemin.relative_to(APP.parent).with_suffix('').parts
    return 'apps.' + '.'.join(morceaux)


def _modules_porteurs():
    """``(module, nom)`` de chaque alias ``_nombre``/``_flottant`` du module."""
    porteurs = []
    for chemin in _sources():
        texte = chemin.read_text(encoding='utf-8')
        if 'import nombre as _' not in texte:
            continue
        for nom in NOMS:
            if 'nombre as %s' % nom in texte:
                porteurs.append((_module(chemin), nom))
    return porteurs


class NombreUniqueTest(unittest.TestCase):

    def test_le_survivant_rend_la_table(self):
        self.assertEqual([nombre(v) for v in TABLE], ATTENDU)

    def test_table_identique_partout(self):
        porteurs = _modules_porteurs()
        self.assertGreaterEqual(len(porteurs), 50)
        for module, nom in porteurs:
            with self.subTest(module=module, nom=nom):
                lecteur = getattr(importlib.import_module(module), nom)
                self.assertIs(lecteur, nombre)
                self.assertEqual([lecteur(v) for v in TABLE], ATTENDU)

    def test_aucune_nouvelle_copie(self):
        copies = []
        for chemin in _sources():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and noeud.name in NOMS
                        and len(noeud.args.args) + len(noeud.args.kwonlyargs)
                        + len(noeud.args.posonlyargs) == 1
                        and not noeud.args.vararg and not noeud.args.kwarg):
                    copies.append('%s:%d' % (
                        chemin.relative_to(APP).as_posix(), noeud.lineno))
        self.assertEqual(copies, [], 'une copie privée de la lecture des '
                         'nombres est revenue : appelez services/valeurs.nombre')

    def test_pente_du_pan_plat_vaut_zero(self):
        """ACAL1923 — un toit plat qui porte la valeur du curseur (22) se lit 0,
        exactement comme un toit plat à 0 ; un toit en pente garde sa pente."""
        self.assertEqual(pente_du_pan({'roofType': 'flat', 'pitchDeg': 22}), 0.0)
        self.assertEqual(pente_du_pan({'roofType': 'flat', 'pitchDeg': 0}), 0.0)
        self.assertEqual(pente_du_pan({'roofType': 'flat'}), 0.0)
        self.assertEqual(pente_du_pan({'roofType': 'pitched', 'pitchDeg': 22}), 22.0)
        self.assertEqual(pente_du_pan({'pitchDeg': '15'}), 15.0)
        self.assertIsNone(pente_du_pan({'roofType': 'pitched'}))
        self.assertIsNone(pente_du_pan(None))

    def test_pente_du_pan_est_la_regle_du_noyau(self):
        """D-ACAL-149 — ``apps.ventes`` lit la MÊME règle par
        ``core.calepinage.geo`` : la table des nombres rend à l'identique sur
        un pan en pente, et un toit plat vaut 0 quelle que soit sa saisie."""
        from core.calepinage.geo import pente_effective_du_pan

        for valeur in TABLE + [10 ** 400]:
            with self.subTest(valeur=valeur):
                pan = {'roofType': 'pitched', 'pitchDeg': valeur}
                self.assertEqual(pente_effective_du_pan(pan), nombre(valeur))
                self.assertEqual(pente_du_pan(pan), nombre(valeur))
                self.assertEqual(pente_effective_du_pan(
                    {'roofType': 'flat', 'pitchDeg': valeur}), 0.0)
