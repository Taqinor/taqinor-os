# -*- coding: utf-8 -*-
"""ACAL285 — la teinte de chaque chaîne et de chaque entrée MPPT, SERVIE.

``electrique.affectation[]`` porte ``couleur_chaine`` et ``couleur_mppt``
(source unique ``services/chaines.py::PALETTE_CHAINES``), par ordre de
première apparition, recalculées après l'affectation manuelle ; le plan de
câblage garde EXACTEMENT ses teintes. Conception réelle (service), aucun mock.
"""
from __future__ import annotations

import copy
import unittest

from apps.calepinage.services.chaines import (
    COULEUR_NON_AFFECTE, PALETTE_CHAINES, affectation, concevoir_par_pan,
    normaliser_affectation_imposee,
)
from apps.calepinage.services.documents.plan_cablage import (
    plan_de_cablage, svg_de_plan_cablage,
)
from apps.calepinage.services.electrique import TemperaturesSite

from .test_calx310_plan_cablage import AFFECTATION, LAYOUT as LAYOUT_PLAN

#: Deux pans, un onduleur à 2 MPPT : trois chaînes réparties sur deux MPPT,
#: et la réserve d'appoint d'un pan reste non affectée.
LAYOUT = {'zones': [
    {'id': 'a', 'label': 'PAN-A', 'result': {'count': 17},
     'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0},
    {'id': 'b', 'label': 'PAN-B', 'result': {'count': 8},
     'facingAzimuthDeg': 90.0, 'pitchDeg': 15.0},
]}
MODULE = {'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59, 'imp_a': 17.59,
          'pmax_wc': 710.0}
ONDULEUR = {'n_mppt': 2, 'mppt_v_min': 120.0, 'mppt_v_max': 500.0,
            'v_max_abs': 600.0, 'i_max_mppt_a': 40.0, 'ac_kw': 15.0,
            'phases': 3}


def _conception():
    temperatures = TemperaturesSite(froid_c=-5.0, chaud_c=70.0,
                                    source='saisie', detail='saisie')
    return concevoir_par_pan(LAYOUT, module_specs=MODULE,
                             onduleur_specs=ONDULEUR,
                             temperatures=temperatures, phases=3)


def _premieres(lignes, cle, couleur):
    vus = {}
    for ligne in lignes:
        if ligne[cle] is not None and ligne[cle] not in vus:
            vus[ligne[cle]] = ligne[couleur]
    return vus


class AffectationCouleurs(unittest.TestCase):

    def test_lignes_portent_couleur_chaine_et_mppt_dans_l_ordre_de_premiere_apparition(self):  # noqa: E501
        lignes = affectation(_conception())
        self.assertGreaterEqual(len({ligne['chaine'] for ligne in lignes
                                     if ligne['chaine'] is not None}), 2)
        par_chaine = _premieres(lignes, 'chaine', 'couleur_chaine')
        self.assertEqual(list(par_chaine.values()),
                         list(PALETTE_CHAINES[:len(par_chaine)]))
        par_mppt = _premieres(lignes, 'mppt', 'couleur_mppt')
        self.assertEqual(list(par_mppt.values()),
                         list(PALETTE_CHAINES[:len(par_mppt)]))
        for ligne in lignes:
            self.assertTrue(ligne['couleur_chaine'].startswith('rgb('))
            self.assertTrue(ligne['couleur_mppt'].startswith('rgb('))

    def test_module_non_affecte_est_gris(self):
        lignes = affectation(_conception())
        libres = [ligne for ligne in lignes if ligne['chaine'] is None]
        self.assertTrue(libres, 'aucun module de réserve dans le cas')
        for ligne in libres:
            self.assertEqual(ligne['couleur_chaine'], COULEUR_NON_AFFECTE)
            self.assertEqual(ligne['couleur_mppt'], COULEUR_NON_AFFECTE)

    def test_affectation_manuelle_recolore(self):
        conception = _conception()
        auto = affectation(conception)
        libre = next(ligne for ligne in auto if ligne['chaine'] is None)
        imposee = normaliser_affectation_imposee([
            {'module': libre['module'], 'chaine': 99, 'mppt': 2,
             'onduleur': 1}])
        manuelle = affectation(conception, imposee=imposee)
        ligne = next(item for item in manuelle
                     if item['module'] == libre['module'])
        self.assertIn(ligne['couleur_chaine'], PALETTE_CHAINES)
        self.assertNotEqual(ligne['couleur_chaine'], COULEUR_NON_AFFECTE)

    def test_svg_plan_cablage_inchange(self):
        sans = copy.deepcopy(AFFECTATION)
        avec = copy.deepcopy(AFFECTATION)
        for ligne in avec:
            ligne['couleur_chaine'] = 'rgb(1, 2, 3)'
            ligne['couleur_mppt'] = 'rgb(4, 5, 6)'
        self.assertEqual(
            svg_de_plan_cablage(plan_de_cablage(LAYOUT_PLAN, sans)),
            svg_de_plan_cablage(plan_de_cablage(LAYOUT_PLAN, avec)))
        self.assertIn(PALETTE_CHAINES[0],
                      svg_de_plan_cablage(plan_de_cablage(LAYOUT_PLAN, sans)))
