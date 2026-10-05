"""ACAL290 - la planche cite la source de chaque zone reglementaire.

Essais PURS sur le SVG rendu (la legende est la meme dans le PDF servi, qui
n'est que ce SVG encapsule). La route HTTP planche.pdf est couverte par
``test_cal174_endpoints_planche.py``.
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.services.planche import (
    geometrie_de_planche, rendre_planche_svg,
)

from .test_cal171_planche import LAYOUT
from .test_cal173_empreinte import MOMENT, FauxCalepinage

SOURCE = 'Arrêté X — bande coupe-feu 1,5 m'
SOMMETS = [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]]


def calepinage(**zone):
    layout = copy.deepcopy(LAYOUT)
    layout['exclusionZones'] = [dict(
        {'id': 'zx-1', 'nature': 'INTERDITE', 'vertices': SOMMETS}, **zone)]
    return FauxCalepinage(roof_layout=layout)


class SourceDeZoneTest(SimpleTestCase):
    def test_la_legende_cite_la_source_de_la_zone(self):
        svg = rendre_planche_svg(calepinage(source=SOURCE), moment=MOMENT)
        self.assertIn('Zone interdite ou réservée — ' + 'Arrêté X', svg)
        self.assertIn('bande coupe-feu', svg)

    def test_zone_sans_source_sans_citation(self):
        svg = rendre_planche_svg(calepinage(), moment=MOMENT)
        self.assertIn('Zone interdite ou réservée', svg)
        self.assertNotIn('Zone interdite ou réservée —', svg)

    def test_la_source_survit_dans_la_geometrie(self):
        geometrie = geometrie_de_planche(calepinage(source=SOURCE).roof_layout)
        self.assertEqual(geometrie['zones_interdites'][0]['source'], SOURCE)
