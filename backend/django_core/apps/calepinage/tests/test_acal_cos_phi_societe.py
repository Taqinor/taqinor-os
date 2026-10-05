# -*- coding: utf-8 -*-
"""ACAL175 — le réglage société ``cos_phi_par_defaut`` : repli SOURCÉ du
verdict « puissance souscrite », jamais de l'écrêtage.

Tests PURS : conception calculée par le service réel sur des fiches en
mémoire, aucune base.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import TemperaturesSite
from apps.calepinage.services.etapes import ecretage
from apps.calepinage.services.raccordement import verdicts_raccordement

LAYOUT = {'zones': [{'id': 'a', 'label': 'PAN-A', 'result': {'count': 12},
                     'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0}]}
MODULE = {'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59, 'imp_a': 17.59,
          'pmax_wc': 710.0}
#: Un onduleur SANS ``s_max_kva`` : la puissance apparente passe par un cos φ.
ONDULEUR = {'n_mppt': 2, 'mppt_v_min': 160.0, 'mppt_v_max': 950.0,
            'v_max_abs': 1100.0, 'i_max_mppt_a': 26.0, 'ac_kw': 9.0,
            'phases': 3}
REGLAGES = {'cos_phi_par_defaut': {'valeur': 0.9, 'source': 'societe'}}


def _conception():
    temperatures = TemperaturesSite(froid_c=-5.0, chaud_c=70.0,
                                    source='saisie', detail='saisie')
    return concevoir_par_pan(LAYOUT, module_specs=MODULE,
                             onduleur_specs=ONDULEUR,
                             temperatures=temperatures, phases=3)


class CosPhiSociete(unittest.TestCase):

    def test_repli_societe_source_nommee(self):
        bloc = verdicts_raccordement(_conception(), {}, REGLAGES)
        self.assertAlmostEqual(bloc['puissance_injectee_kva'], 10.0)
        self.assertIn('réglage société — cos_phi_par_defaut',
                      bloc['source_puissance'])

    def test_sans_reglage_motif_inchange(self):
        bloc = verdicts_raccordement(
            _conception(), {'puissance_souscrite_kva': 12.0}, {})
        self.assertIsNone(bloc['puissance_injectee_kva'])
        souscrite = bloc['verdicts'][0]
        self.assertIn("Aucun cos φ n'est supposé", souscrite.libelle)

    def test_site_prime_sur_societe(self):
        saisie = {'cos_phi_impose': 0.8, 'source_cos_phi': 'contrat'}
        bloc = verdicts_raccordement(_conception(), saisie, REGLAGES)
        self.assertAlmostEqual(bloc['puissance_injectee_kva'], 11.25)
        self.assertIn('cos_phi_impose', bloc['source_puissance'])

    def test_ecretage_ignore_le_reglage_societe(self):
        contexte = {'electrique_societe': REGLAGES, 'raccordement': {}}
        self.assertEqual(ecretage._cos_phi_impose(contexte), (None, ''))
