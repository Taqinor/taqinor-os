# -*- coding: utf-8 -*-
"""ACAL269 — le classeur, le plan de pose et le plan de câblage impriment les
numéros STABLES des modules (``panels[].n``) et les étiquettes de rangée.

LE CONSTAT (C-ACAL-051) : un module retiré (trou en 3) renumérotait 1, 2, 3
dans les livrables alors que l'atelier, le rapport d'ombrage et l'affectation
le nomment 4 : l'équipe de pose et le bureau d'études ne parlaient plus du
même panneau. Sans ``n`` (document ancien), l'index reste le repli.
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services.documents.plan_cablage import _modules_du_plan
from apps.calepinage.services.export_tableur import table_modules
from apps.calepinage.services.planche import (
    _reperes_de_pose, geometrie_de_planche,
)

from .test_cal171_planche import LAYOUT as LAYOUT_PLANCHE


def _layout(numerotes=True):
    layout = copy.deepcopy(LAYOUT_PLANCHE)
    panneaux = [{'cx': 1.0 + 2.0 * i, 'cy': 1.0} for i in range(3)]
    if numerotes:
        for panneau, numero in zip(panneaux, (1, 2, 4)):
            panneau.update(n=numero, rangee='R1')
    layout['zones'][0]['geometry'].update(count=3, panels=panneaux)
    layout['zones'][0].pop('obstacles', None)
    return layout


class NumerosStablesTest(SimpleTestCase):

    def test_module_1_2_4(self):
        layout = _layout()
        geometrie = geometrie_de_planche(layout)
        resultat = {'electrique': {'affectation': [
            {'module': 'z1#4', 'pan': 'Pan Sud', 'chaine': 2, 'mppt': 1,
             'onduleur': 1}]}}

        entetes, lignes = table_modules(geometrie, resultat)

        module = entetes.index('Module')
        self.assertEqual([ligne[module] for ligne in lignes], [1, 2, 4])
        self.assertEqual([ligne[entetes.index('Rangée')] for ligne in lignes],
                         ['R1', 'R1', 'R1'])
        # L'affectation se joint par la clé du module, pas par la position.
        chaine = entetes.index('Chaîne')
        self.assertEqual([ligne[chaine] for ligne in lignes], [None, None, 2])
        # Le plan de câblage nomme les mêmes modules.
        self.assertEqual([m['module'] for m in
                          _modules_du_plan(layout, geometrie)],
                         ['z1#1', 'z1#2', 'z1#4'])
        # Le plan de pose imprime l'étiquette de rangée du document.
        svg = ''.join(_reperes_de_pose(geometrie['pans'][0],
                                       lambda point: point))
        self.assertIn('>R1</text>', svg)

    def test_sans_numero_l_index_reste_le_repli(self):
        layout = _layout(numerotes=False)
        geometrie = geometrie_de_planche(layout)

        entetes, lignes = table_modules(geometrie)

        self.assertEqual([ligne[entetes.index('Module')] for ligne in lignes],
                         [1, 2, 3])
        self.assertEqual([m['module'] for m in
                          _modules_du_plan(layout, geometrie)],
                         ['z1#1', 'z1#2', 'z1#3'])
