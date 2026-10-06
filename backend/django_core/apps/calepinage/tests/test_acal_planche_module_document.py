"""ACAL263 - la planche et ses sorties cotent chaque pan avec SON module.

``modules[]`` (schema CALX82) est resolu par ``geometry.moduleId`` via
``io_layout.module_du_pan`` ; le kit moteur par puissance (``panelWatt``)
n'est plus qu'un repli quand le pan ne designe aucun modele du catalogue.
Essais purs (aucune base).
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.services.export_dxf import document_dxf
from apps.calepinage.services.io_layout import module_du_pan
from apps.calepinage.services.planche import (
    dimensions_module, geometrie_de_planche, svg_de_planche,
)

from .test_cal171_planche import LAYOUT

CATALOGUE = [
    {'id': 'produit-9', 'longueurMm': 2278, 'largeurMm': 1134, 'pmaxWc': 580},
    {'id': 'produit-7', 'longueurMm': 2172, 'largeurMm': 1303, 'pmaxWc': 720},
]


def layout_a_deux_pans():
    layout = copy.deepcopy(LAYOUT)
    layout['modules'] = copy.deepcopy(CATALOGUE)
    layout['zones'][0]['geometry']['moduleId'] = 'produit-9'
    second = copy.deepcopy(layout['zones'][0])
    second['id'] = 'z2'
    second['geometry']['moduleId'] = 'produit-7'
    second['geometry']['panels'] = [{'cx': 8.0, 'cy': 1.0}]
    layout['zones'].append(second)
    return layout


class ModuleDuPanTest(SimpleTestCase):
    def test_resout_le_renvoi_moduleid_dans_le_catalogue(self):
        layout = layout_a_deux_pans()
        self.assertEqual(module_du_pan(layout, layout['zones'][0])['pmaxWc'], 580)
        self.assertEqual(module_du_pan(layout, layout['zones'][1])['pmaxWc'], 720)

    def test_sans_renvoi_ou_modele_absent_rend_none(self):
        layout = layout_a_deux_pans()
        layout['zones'][0]['geometry'].pop('moduleId')
        self.assertIsNone(module_du_pan(layout, layout['zones'][0]))
        layout['zones'][1]['geometry']['moduleId'] = 'inconnu'
        self.assertIsNone(module_du_pan(layout, layout['zones'][1]))
        self.assertIsNone(module_du_pan(None, {}))


class CotesDuModuleDuPanTest(SimpleTestCase):
    def test_cotes_du_module_du_pan(self):
        geometrie = geometrie_de_planche(layout_a_deux_pans())
        pans = geometrie['pans']
        self.assertEqual(pans[0]['module_m'], (2.278, 1.134))
        self.assertEqual(pans[1]['module_m'], (2.172, 1.303))

    def test_repli_sur_le_kit_sans_catalogue(self):
        # panelWatt 720 sans modules[] : le kit declare (2,384 x 1,303).
        geometrie = geometrie_de_planche(LAYOUT)
        self.assertEqual(geometrie['pans'][0]['module_m'], (2.384, 1.303))
        self.assertEqual(dimensions_module({'panelWatt': 720}), (2.384, 1.303))

    def test_un_pan_sans_renvoi_retombe_sur_le_kit_les_autres_gardent_leur_module(self):
        layout = layout_a_deux_pans()
        layout['zones'][0]['geometry'].pop('moduleId')
        pans = geometrie_de_planche(layout)['pans']
        self.assertEqual(pans[0]['module_m'], (2.384, 1.303))
        self.assertEqual(pans[1]['module_m'], (2.172, 1.303))

    def test_la_planche_dessine_des_rectangles_pas_des_points(self):
        geometrie = geometrie_de_planche(layout_a_deux_pans())
        svg = svg_de_planche(geometrie, titre='t', sous_titre='s', pied='p')
        self.assertIn('<polygon', svg)
        self.assertNotIn('r="0.7"', svg)

    def test_le_dxf_cote_chaque_pan_avec_son_module(self):
        document = document_dxf(geometrie_de_planche(layout_a_deux_pans()))
        polylignes = list(document.modelspace().query(
            'LWPOLYLINE[layer=="MODULES"]'))
        largeurs = sorted(round(max(p[0] for p in e.get_points())
                                - min(p[0] for p in e.get_points()), 3)
                          for e in polylignes)
        self.assertEqual(largeurs, [2.172, 2.278, 2.278])
