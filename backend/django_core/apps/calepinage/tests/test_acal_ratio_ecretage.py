"""ACAL141 — le ratio DC/AC publie l'écrêtage de la simulation FRAÎCHE.

Constat C-ACAL-083 : ``ratio_dc_ac.ecretage_pct`` relisait une colonne
``p_dc_kw`` de la série persistée — qu'AUCUNE étape n'écrit : il valait
``null`` sur tout calepinage réellement simulé.

Désormais il est lu sur l'étape « ecretage » de la cascade SERVIE (fraîche),
calculée heure par heure dans la chaîne (phase ONDULEUR sur la somme DC,
ACAL53). Périmé ou jamais simulé ⇒ ``null`` avec le motif inchangé.

Chaîne RÉELLE : onduleur et écrêtage appliqués par la simulation (client
rejoué) ; aucune colonne écrite à la main.

Run :
    python manage.py test apps.calepinage.tests.test_acal_ratio_ecretage -v2
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    METHODE_ECRETAGE_SERIE, MOTIF_ECRETAGE_SANS_SERIE, resultat_calepinage,
)
from apps.calepinage.services.simulation import simuler_calepinage

from .test_acal_multi_pans import _ClientParOrientation
from .test_calx5_simulation import LAYOUT, MATERIEL, REGLAGES, _Calepinage


def _materiel(ac_kw):
    materiel = copy.deepcopy(MATERIEL)
    materiel['onduleur']['ac_kw'] = ac_kw
    return materiel


def _simule(materiel):
    pivot = _Calepinage(layout=copy.deepcopy(LAYOUT))
    simuler_calepinage(pivot, client=_ClientParOrientation(1000.0),
                       materiel=materiel, reglages=REGLAGES,
                       enregistrer=True)
    return pivot


class RatioEcretageTest(SimpleTestCase):

    def test_ecretage_lu_dans_la_cascade_fraiche(self):
        materiel = _materiel(5.0)
        pivot = _simule(materiel)
        etape = next(e for e in pivot.resultat['cascade']['etapes']
                     if e['etape'] == 'ecretage')
        self.assertEqual(etape['motif_omission'], '')

        servi = resultat_calepinage(pivot, materiel=materiel,
                                    reglages=REGLAGES)

        self.assertFalse(servi['simulation_perimee'])
        self.assertEqual(servi['ratio_dc_ac']['ecretage_pct'],
                         etape['entree']['ecretage_pct'])
        self.assertGreater(servi['ratio_dc_ac']['ecretage_pct'], 0.0)
        self.assertEqual(servi['ratio_dc_ac']['ecretage_methode'],
                         METHODE_ECRETAGE_SERIE)

    def test_perime_rend_null_et_le_motif(self):
        materiel = _materiel(5.0)
        pivot = _simule(materiel)
        pivot.roof_layout = copy.deepcopy(pivot.roof_layout)
        pivot.roof_layout['zones'][0]['geometry']['count'] = 9

        servi = resultat_calepinage(pivot, materiel=materiel,
                                    reglages=REGLAGES)

        self.assertTrue(servi['simulation_perimee'])
        self.assertIsNone(servi['ratio_dc_ac']['ecretage_pct'])
        self.assertEqual(servi['ratio_dc_ac']['ecretage_methode'],
                         MOTIF_ECRETAGE_SANS_SERIE)

    def test_jamais_simule_rend_null_et_le_motif(self):
        materiel = _materiel(5.0)
        servi = resultat_calepinage(_Calepinage(), materiel=materiel,
                                    reglages=REGLAGES)
        self.assertIsNone(servi['ratio_dc_ac']['ecretage_pct'])
        self.assertEqual(servi['ratio_dc_ac']['ecretage_methode'],
                         MOTIF_ECRETAGE_SANS_SERIE)
