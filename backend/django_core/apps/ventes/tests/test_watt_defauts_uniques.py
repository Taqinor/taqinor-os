# -*- coding: utf-8 -*-
"""QJR608 — deux wattages de repli NOMMÉS, un propriétaire chacun.

* ``domain.lignes.LAYOUT_WATT_REPLI = 550`` — le repli d'un layout (ou d'une
  composition) qui ne dit aucun wattage ;
* ``domain.taille._AUTO_PANEL_WATT = 710`` — le panneau catalogue par défaut.

Les deux valeurs ne sont PAS unifiées (entrées différentes). La garde AST :
dans ``apps/ventes/{domain,views}``, chaque littéral n'apparaît qu'UNE fois —
sa définition.

Run :
    python manage.py test apps.ventes.tests.test_watt_defauts_uniques -v 2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

VENTES = Path(__file__).resolve().parents[1]


def _occurrences(valeur):
    trouves = []
    for dossier in ('domain', 'views'):
        for fichier in sorted((VENTES / dossier).rglob('*.py')):
            arbre = ast.parse(fichier.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, ast.Constant)
                        and not isinstance(noeud.value, bool)
                        and noeud.value in (valeur, float(valeur),
                                            str(valeur))):
                    trouves.append('%s:%s' % (
                        fichier.relative_to(VENTES).as_posix(), noeud.lineno))
    return trouves


class DeuxWattagesNommes(SimpleTestCase):

    def test_550_defini_une_fois_dans_lignes(self):
        occ = _occurrences(550)
        self.assertEqual(len(occ), 1, occ)
        self.assertTrue(occ[0].startswith('domain/lignes.py:'), occ)

    def test_710_defini_une_fois_dans_taille(self):
        occ = _occurrences(710)
        self.assertEqual(len(occ), 1, occ)
        self.assertTrue(occ[0].startswith('domain/taille.py:'), occ)

    def test_valeurs_inchangees(self):
        from apps.ventes.domain.lignes import (
            CIBLE_WATT_DEFAUT, LAYOUT_WATT_REPLI)
        from apps.ventes.domain.taille import _AUTO_PANEL_WATT
        self.assertEqual(LAYOUT_WATT_REPLI, 550)
        self.assertEqual(CIBLE_WATT_DEFAUT, LAYOUT_WATT_REPLI)
        self.assertEqual(_AUTO_PANEL_WATT, 710)
