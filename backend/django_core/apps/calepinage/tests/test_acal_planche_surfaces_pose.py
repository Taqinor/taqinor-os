"""ACAL260 — les surfaces de pose ont leur feuille dédiée sur les livrables.

Constat C-ACAL-035 (S1) : un document ``{version: 2, pin, poseSurfaces:
[{kind: 'sol', contourM, engine}], panelWatt}`` sans zone était REFUSÉ par
``geometrie_de_planche`` (« Aucune géométrie enregistrée ») — planche, plan
de pose, DXF, tableur et plan de câblage tombaient tous ; un site mixte
perdait le champ en silence. Désormais chaque surface est dessinée sur une
FEUILLE DÉDIÉE, dans le repère local du moteur (m), cotée ; le total des
modules de la planche (toit + surfaces) égale celui de ``pans_du_document``.

Essais PURS sur les vraies fonctions (aucune base, aucun mock).

Run :
    python manage.py test apps.calepinage.tests.test_acal_planche_surfaces_pose -v2
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.services.documents.plan_cablage import (
    _plan_de_cablage, _svg_de_plan_cablage,
)
from apps.calepinage.services.export_tableur import (
    FEUILLE_SURFACES, _tables_du_resultat,
)
from apps.calepinage.services.planche import (
    CONTENU_POSE, DEBUT_FEUILLE, MENTION_REPERE_LOCAL, geometrie_de_planche,
    html_de_planche, svg_de_planche, texte_de_longueur,
)
from apps.ventes.services import pans_du_document

SURFACE_SOL = {
    'id': 'sol-1', 'kind': 'sol', 'label': 'Champ nord',
    'contourM': [[0, 0], [20, 0], [20, 10], [0, 10]],
    'moduleWc': 550,
    'engine': {'modules': 24, 'tables': [
        {'x0': 1, 'y0': 1, 'x1': 19, 'y1': 3},
        {'x0': 1, 'y0': 5, 'x1': 19, 'y1': 7},
    ]},
}

CHAMP_SEUL = {
    'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
    'poseSurfaces': [SURFACE_SOL], 'panelWatt': 550,
}

#: Un toit d'un pan, deux modules posés (centres relevés), + le champ.
SITE_MIXTE = {
    'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
    'panelWatt': 550,
    'zones': [{
        'id': 'a', 'label': 'PAN-A',
        'vertices': [[-7.5898, 33.5731], [-7.5897, 33.5731],
                     [-7.5897, 33.5732], [-7.5898, 33.5732]],
        'geometry': {'origin': [-7.5898, 33.5731], 'azimuthDeg': 180,
                     'tiltDeg': 15,
                     'panels': [{'cx': 1.0, 'cy': 1.0},
                                {'cx': 3.0, 'cy': 1.0}]},
    }],
    'poseSurfaces': [SURFACE_SOL],
}


def _total_planche(geometrie):
    return (sum(len(pan['modules']) for pan in geometrie['pans'])
            + sum(surface['modules'] or 0
                  for surface in geometrie['surfaces_de_pose']))


class ChampSeulTest(SimpleTestCase):
    def setUp(self):
        self.geometrie = geometrie_de_planche(copy.deepcopy(CHAMP_SEUL))

    def test_champ_seul_rend_une_feuille(self):
        self.assertIsNone(self.geometrie['etendue'])
        [surface] = self.geometrie['surfaces_de_pose']
        self.assertEqual(surface['modules'], 24)
        self.assertEqual(len(surface['tables']), 2)
        svg = svg_de_planche(self.geometrie, titre='Champ')
        self.assertNotIn(DEBUT_FEUILLE, svg)  # UNE feuille, A3
        self.assertIn(MENTION_REPERE_LOCAL, svg)
        self.assertIn('Modules posés (moteur) : 24', svg)
        # Cotée : l'encombrement du champ en mètres.
        self.assertIn(texte_de_longueur(20.0), svg)
        self.assertIn(texte_de_longueur(10.0), svg)
        # Le plan de pose sort lui aussi.
        self.assertIn('<svg', svg_de_planche(self.geometrie,
                                             contenu=CONTENU_POSE))

    def test_tableur_porte_la_feuille_des_surfaces(self):
        tables = {titre: (entetes, lignes) for titre, entetes, lignes
                  in _tables_du_resultat(self.geometrie, {})}
        _entetes, lignes = tables[FEUILLE_SURFACES]
        self.assertEqual(lignes[0][0], 'Champ nord')
        self.assertEqual(lignes[0][2], 24)

    def test_plan_de_cablage_ne_refuse_plus_le_champ(self):
        plan = _plan_de_cablage(copy.deepcopy(CHAMP_SEUL), [
            {'module': 'sol-1:1', 'chaine': 1, 'onduleur': 1, 'mppt': 1}])
        svg = _svg_de_plan_cablage(plan, titre='Câblage')
        self.assertIn(MENTION_REPERE_LOCAL, svg)

    def test_dxf_porte_le_calque_des_surfaces(self):
        try:
            import ezdxf  # noqa: F401
        except ImportError:  # pragma: no cover - dépend de l'environnement
            self.skipTest('ezdxf indisponible')
        from apps.calepinage.services.export_dxf import octets_dxf

        octets = octets_dxf(self.geometrie)
        self.assertIn(b'SURFACES_POSE', octets)


class SiteMixteTest(SimpleTestCase):
    def setUp(self):
        self.geometrie = geometrie_de_planche(copy.deepcopy(SITE_MIXTE))

    def test_site_mixte_total_modules(self):
        attendu = sum(pan['modules']
                      for pan in pans_du_document(copy.deepcopy(SITE_MIXTE)))
        self.assertEqual(attendu, 26)
        self.assertEqual(_total_planche(self.geometrie), attendu)

    def test_site_mixte_feuille_du_toit_puis_feuille_du_champ(self):
        svg = svg_de_planche(self.geometrie, titre='Site')
        self.assertEqual(svg.count(DEBUT_FEUILLE), 2)
        html = html_de_planche(svg)
        self.assertEqual(html.count('class="feuille"'), 2)
        self.assertIn(MENTION_REPERE_LOCAL, html)
