"""ACAL230 - UNE definition ORIENTEE de la rangee (plan, classeur, fixation).

Un pan de 3 rangees x 5 modules, tourne de 172, 188, 135 ou 200 degres : les
modules d'une meme rangee physique ne partagent plus la meme ordonnee Nord, et
le groupement par ordonnee seule en faisait 15 rangees (15 reperes ``R`` sans
fleche). Essais PURS - calcul sur la geometrie.

Run :
    python manage.py test apps.calepinage.tests.test_acal_rangees_orientees
"""
import math

from django.test import SimpleTestCase

from apps.calepinage.services import fixation
from apps.calepinage.services.export_tableur import table_modules
from apps.calepinage.services.planche import (
    CONTENU_POSE, geometrie_de_planche, svg_de_planche,
)
from apps.calepinage.services.rangees import (
    positions_par_rangee, rangees_du_pan,
)

from .test_calx359_bom_fixation import layout

PAS_RANGEE = 1.2   # entre modules d'une meme rangee (metres)
PAS_PENTE = 2.0    # entre deux rangees (metres)


def pan_tourne(azimut, rangees=3, par_rangee=5, origine=(5.0, 5.0)):
    """Centres (est, nord) d'un pan regulier tourne de ``azimut`` degres."""
    a = math.radians(azimut)
    pente = (math.sin(a), math.cos(a))      # sens de la plus grande pente
    rang = (math.cos(a), -math.sin(a))      # le long de la rangee
    return [(origine[0] + k * PAS_RANGEE * rang[0] + r * PAS_PENTE * pente[0],
             origine[1] + k * PAS_RANGEE * rang[1] + r * PAS_PENTE * pente[1])
            for r in range(rangees) for k in range(par_rangee)]


class RangeesOrienteesTest(SimpleTestCase):
    def test_trois_rangees_pour_azimuts_non_cardinaux(self):
        for azimut in (172, 188, 135, 200, 5):
            with self.subTest(azimut=azimut):
                modules = pan_tourne(azimut)
                rangees = rangees_du_pan(modules, azimut)
                self.assertEqual(len(set(rangees.values())), 3)
                self.assertEqual(sorted(set(rangees.values())), [1, 2, 3])

    def test_sans_azimut_le_regroupement_par_ordonnee_est_conserve(self):
        modules = [(1.0, 1.0), (2.2, 1.0), (1.0, 3.0), (2.2, 3.004),
                   (3.4, 5.0)]
        rangees = rangees_du_pan(modules)
        self.assertEqual(rangees[(1.0, 1.0)], 1)
        self.assertEqual(rangees[(2.2, 3.004)], rangees[(1.0, 3.0)])
        self.assertEqual(rangees[(3.4, 5.0)], 3)

    def test_plein_sud_numerote_comme_avant_de_l_egout_vers_le_faite(self):
        modules = [(1.0, 1.0), (1.0, 3.0), (1.0, 5.0)]
        rangees = rangees_du_pan(modules, 180.0)
        self.assertEqual([rangees[m] for m in modules], [1, 2, 3])

    def test_plan_de_pose_porte_trois_reperes_et_trois_fleches_a_172(self):
        document = layout(pan_tourne(172), azimut=172.0)
        svg = svg_de_planche(geometrie_de_planche(document),
                             contenu=CONTENU_POSE)
        for numero in (1, 2, 3):
            self.assertEqual(svg.count('>R%d</text>' % numero), 1)
        self.assertNotIn('>R4</text>', svg)
        self.assertEqual(svg.count('stroke-dasharray="1 0.8"'), 3)

    def test_classeur_et_bom_fixation_comptent_les_memes_rangees(self):
        document = layout(pan_tourne(172), azimut=172.0)
        geometrie = geometrie_de_planche(document)
        _entetes, lignes = table_modules(geometrie, None)
        rangees_du_classeur = {ligne[2] for ligne in lignes}
        valeurs = fixation._grandeurs_du_document(document)['valeurs']
        self.assertEqual(rangees_du_classeur, {1, 2, 3})
        self.assertEqual(valeurs['rangees'], len(rangees_du_classeur))

    def test_positions_par_rangee_sont_triees_le_long_de_la_rangee(self):
        for positions in positions_par_rangee(pan_tourne(172), 172):
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(len(positions), 5)
