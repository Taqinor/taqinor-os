"""ACAL59 (C-ACAL-035, C-ACAL-118, D-ACAL-5) — ``pans_du_document`` : un site
toit + champ au sol / ombrière est chiffré sur la SOMME des modules posés,
une surface sans puissance module est refusée en la nommant, un pan non pavé
ne compte jamais, et le ``result`` racine n'est jamais additionné aux zones.

Lecture PURE (``SimpleTestCase``) + le refus tel que le pré-vol le prononce.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_pans_du_document"
"""
import copy

from django.test import SimpleTestCase

from apps.ventes.domain.geometrie import (
    lire_layout, pans_du_document, refus_des_pans,
    validate_composition_for_layout)
from apps.ventes.domain.taille import AutoDevisError

MIXTE = {
    'zones': [{'id': 'zA', 'label': 'Toit', 'geometry': {
        'count': 10, 'kwc': 7.2, 'azimuthDeg': 180, 'tiltDeg': 30,
        'panels': [{'cx': i, 'cy': 0} for i in range(10)]}}],
    'result': {'panels': 10, 'kwc': 7.2},
    'poseSurfaces': [{'id': 's1', 'kind': 'ombriere', 'label': 'Carport',
                      'moduleWc': 620, 'tiltDeg': 10, 'rowAzimuthDeg': 90,
                      'engine': {'modules': 60}}],
}


class PansDuDocument(SimpleTestCase):

    def test_site_mixte_somme(self):
        lecture = lire_layout(MIXTE)
        self.assertEqual(lecture.compte, 70)
        self.assertAlmostEqual(lecture.kwc, 7.2 + 60 * 0.620)
        toit, ombriere = lecture.pans
        self.assertEqual((toit['kind'], toit['modules']), ('toit', 10))
        self.assertEqual((ombriere['kind'], ombriere['modules']),
                         ('ombriere', 60))
        self.assertAlmostEqual(ombriere['kwc'], 37.2)
        # Azimut de FACE = rowAzimuthDeg + 90 (défaut gravé du contrat).
        self.assertEqual(ombriere['azimut_deg'], 180.0)
        self.assertEqual(toit['source'], 'geometry.panels')

    def test_surface_sans_puissance_refusee(self):
        sans = copy.deepcopy(MIXTE)
        del sans['poseSurfaces'][0]['moduleWc']
        refus = refus_des_pans(pans_du_document(sans))
        self.assertEqual(len(refus), 1)
        self.assertIn('Carport', refus[0])
        with self.assertRaises(AutoDevisError) as leve:
            validate_composition_for_layout(sans, None)
        self.assertEqual(leve.exception.field, 'poseSurfaces.0.moduleWc')
        self.assertIn('Carport', leve.exception.message)

    def test_pan_non_pave_ne_compte_pas(self):
        layout = {'zones': [{'id': 'zB', 'label': 'Annexe',
                             'geometry': {'count': 0},
                             'neededPanels': 12}]}
        pan, = pans_du_document(layout)
        self.assertEqual(pan['modules'], 0)
        self.assertIn('pan Annexe non pavé — non chiffré',
                      pan['avertissement'])
        self.assertEqual(lire_layout(layout).compte, 0)

    def test_zone_auto_devis_compte(self):
        # La zone SYNTHÉTIQUE de l'auto-devis ne porte que ``result`` (et
        # ``neededPanels``, jamais lu comme compte posé).
        layout = {'zones': [{'id': 'auto', 'label': 'Toit du client',
                             'neededPanels': 14,
                             'result': {'count': 14, 'kwc': 9.94}}],
                  'result': {'panels': 14, 'kwc': 9.94}}
        pan, = pans_du_document(layout)
        self.assertEqual((pan['modules'], pan['source']), (14, 'result.count'))
        self.assertEqual(lire_layout(layout).compte, 14)

    def test_result_racine_jamais_double(self):
        for panels in (10, 25, 0):
            with self.subTest(result_panels=panels):
                layout = copy.deepcopy(MIXTE)
                layout['result'] = {'panels': panels, 'kwc': 99.0}
                self.assertEqual(lire_layout(layout).compte, 70)
        # Sans aucune géométrie de zone, le result racine est le toit.
        self.assertEqual(lire_layout({'result': {'panels': 12}}).compte, 12)
