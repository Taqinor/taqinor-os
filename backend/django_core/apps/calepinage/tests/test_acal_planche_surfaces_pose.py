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
import importlib
import copy
import math

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

from .acal_livrables_helpers import texte_des_lignes_svg  # T4-V1-006

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
        self.assertIn(MENTION_REPERE_LOCAL, texte_des_lignes_svg(svg))
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
        self.assertIn(MENTION_REPERE_LOCAL, texte_des_lignes_svg(svg))

    def test_dxf_porte_le_calque_des_surfaces(self):
        try:
            importlib.import_module('ezdxf')
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
        self.assertIn(MENTION_REPERE_LOCAL, texte_des_lignes_svg(html))


def ombriere(**appuis):
    """ACAL580 — une ombrière 10 × 6 m, une table, ``appuis`` tels que saisis."""
    return {'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898}, 'panelWatt': 550,
            'poseSurfaces': [{'id': 'omb-1', 'kind': 'ombriere', 'label': 'Ombrière parking',
                              'contourM': [[0, 0], [10, 0], [10, 6], [0, 6]], 'appuis': appuis,
                              'engine': {'modules': 8, 'tables': [{'x0': 1, 'y0': 1, 'x1': 9, 'y1': 5}]}}]}


class PoteauxDOmbriereTest(SimpleTestCase):
    """ACAL580 — les poteaux d'ombrière repérés P1…Pn sur le plan de pose."""

    def svg(self, document):
        return svg_de_planche(geometrie_de_planche(document), contenu=CONTENU_POSE)

    def test_entraxe_deux_et_demi_treize_poteaux_reperes(self):
        svg = self.svg(ombriere(pasM=2.5, sectionM=0.2))
        self.assertIn('Poteaux : 13 (entraxe saisi 2,5 m, section 0,20 m)', texte_des_lignes_svg(svg))
        # Mutant « numéroter P0… » : P0 présent et P13 absent ⇒ échec.
        for numero in range(1, 14):
            self.assertIn('>P%d</text>' % numero, svg)
        self.assertNotIn('>P0</text>', svg)
        self.assertNotIn('>P14</text>', svg)

    def test_repere_de_poteau_lisible_et_pose_sur_son_symbole(self):
        """ACAL1718 — chaque poteau : un disque, un repère de 9 pt au moins (3,175 mm), décalé du disque
        vers l'extérieur ; mutant « remettre 7 pt / pas de disque » ⇒ échec."""
        import re

        svg = self.svg(ombriere(pasM=2.5, sectionM=0.2))
        textes = re.findall(r'<text x="([\d.-]+)" y="([\d.-]+)" font-size="([\d.]+)"[^>]*>P(\d+)</text>', svg)
        disques = re.findall(r'<circle cx="([\d.-]+)" cy="([\d.-]+)" r="1"', svg)
        self.assertEqual(len(textes), 13)
        self.assertEqual(len(disques), 13)
        for x, y, corps, _numero in textes:
            self.assertGreaterEqual(float(corps) * 72 / 25.4, 9.0)
        # le repère n'est jamais posé AU centre du disque : décalé d'au moins 1,5 mm
        for (x, y, _c, _n), (cx, cy) in zip(textes, disques):
            self.assertGreaterEqual(math.hypot(float(x) - float(cx), float(y) - float(cy)), 1.5)

    def test_entraxe_absent_non_decrits_sans_repere(self):
        svg = self.svg(ombriere(sectionM=0.2))
        self.assertIn('Poteaux : non décrits (entraxe des appuis non renseigné)', texte_des_lignes_svg(svg))
        self.assertNotIn('>P1</text>', svg)

    def test_un_champ_au_sol_ne_parle_pas_de_poteaux(self):
        self.assertNotIn('Poteaux :', svg_de_planche(
            geometrie_de_planche(copy.deepcopy(CHAMP_SEUL)), contenu=CONTENU_POSE))
