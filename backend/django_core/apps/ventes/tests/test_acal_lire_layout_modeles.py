"""ACAL62 (C-ACAL-042) — ``lire_layout`` expose les MODÈLES de module posés
(produit_id, watt, nombre), lus dans ``modules[]`` + ``zones[].geometry.
moduleId``, au lieu d'un seul entier ``panelWatt``.

Lecture PURE (``SimpleTestCase``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_lire_layout_modeles"
"""
from django.test import SimpleTestCase

from apps.ventes.domain.geometrie import (
    lire_layout, refus_des_pans, validate_composition_for_layout)
from apps.ventes.domain.taille import AutoDevisError


def _pan(identifiant, nombre, module_id):
    return {'id': identifiant, 'label': identifiant, 'geometry': {
        'moduleId': module_id, 'azimuthDeg': 180, 'tiltDeg': 20,
        'panels': [{'cx': i, 'cy': 0} for i in range(nombre)]}}


DEUX_MODELES = {
    'panelWatt': 440,
    'modules': [
        {'id': 'p440', 'libelle': 'Module 440', 'source': 'fiche',
         'produitId': 129, 'pmaxWc': 440},
        {'id': 'p550', 'libelle': 'Module 550', 'source': 'fiche',
         'produitId': 130, 'pmaxWc': 550},
    ],
    'zones': [_pan('A', 10, 'p440'), _pan('B', 8, 'p550')],
    'result': {'panels': 18, 'kwc': 8.8},
}


class LireLayoutModeles(SimpleTestCase):

    def test_deux_modeles(self):
        lecture = lire_layout(DEUX_MODELES)
        self.assertEqual(lecture.modeles, [
            {'produit_id': 129, 'watt': 440, 'count': 10},
            {'produit_id': 130, 'watt': 550, 'count': 8},
        ])
        self.assertEqual(lecture.compte, 18)
        self.assertAlmostEqual(lecture.kwc, 8.8)

    def test_sans_catalogue_inchange(self):
        layout = {'panelWatt': 550, 'result': {'panels': 12, 'kwc': 6.6}}
        lecture = lire_layout(layout)
        self.assertEqual(lecture.modeles, [
            {'produit_id': None, 'watt': 550, 'count': 12}])
        self.assertEqual((lecture.compte, lecture.watt), (12, 550))

    def test_surface_de_pose_comptee_dans_les_modeles(self):
        layout = dict(DEUX_MODELES, poseSurfaces=[
            {'id': 's1', 'kind': 'sol', 'moduleWc': 620,
             'engine': {'modules': 40}}])
        self.assertIn({'produit_id': None, 'watt': 620, 'count': 40},
                      lire_layout(layout).modeles)

    def test_module_inconnu_refuse_en_le_nommant(self):
        layout = dict(DEUX_MODELES,
                      zones=[_pan('A', 10, 'p440'), _pan('B', 8, 'p999')])
        refus = refus_des_pans(lire_layout(layout).pans)
        self.assertEqual(len(refus), 1)
        self.assertIn('p999', refus[0])
        with self.assertRaises(AutoDevisError) as leve:
            validate_composition_for_layout(layout, None)
        self.assertEqual(leve.exception.field, 'zones.1.geometry.moduleId')
