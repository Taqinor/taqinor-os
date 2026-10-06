"""ACAL61 — le compte des surfaces de pose, partout le même.

Constat : ``chaines.pans_poses`` et ``production.pans_du_layout`` relisaient
chacun ``zones[]`` à leur façon — un champ au sol (``poseSurfaces``) y valait
0 module (la chaîne électrique, la bloc de pose et les livrables l'ignoraient)
et le compte d'un pan non pavé pouvait diverger d'un lecteur à l'autre.

Ils sont désormais deux adaptateurs MINCES de
``apps.ventes.services.pans_du_document`` (LA primitive, D-ACAL-5) : un champ
au sol de 340 modules vaut 340 partout, un pan non pavé vaut 0 partout.

Run :
    python manage.py test apps.calepinage.tests.test_acal_compte_surfaces_pose_partout -v2
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.services.chaines import pans_poses
from apps.calepinage.services.production import pans_du_layout
from apps.ventes.services import pans_du_document

SOL_340 = {
    'version': 2,
    'zones': [],
    'poseSurfaces': [{
        'id': 'champ-1', 'kind': 'sol', 'label': 'Champ sud',
        'moduleWc': 550, 'tiltDeg': 20, 'rowAzimuthDeg': 90,
        'engine': {'modules': 340},
    }],
}

PAN_NON_PAVE = {
    'version': 2,
    'zones': [{'id': 'z1', 'label': 'Pan sud', 'neededPanels': 12,
               'pitchDeg': 30, 'facingAzimuthDeg': 180}],
}


class CompteSurfacesPosePartoutTest(SimpleTestCase):

    def test_sol_seul_340_partout(self):
        primitive = pans_du_document(SOL_340)
        self.assertEqual([p['modules'] for p in primitive], [340])

        chaines = pans_poses(SOL_340)
        self.assertEqual(len(chaines), 1)
        self.assertEqual(chaines[0].modules, 340)
        self.assertEqual(chaines[0].label, 'Champ sud')
        # Azimut de FACE = rangée + 90 (défaut gravé du contrat).
        self.assertEqual(chaines[0].azimut_deg, 180.0)
        self.assertEqual(chaines[0].inclinaison_deg, 20.0)
        self.assertEqual(chaines[0].source_orientation, 'geometrie')

        production = pans_du_layout(SOL_340)
        self.assertEqual(sum(p['modules'] for p in production), 340)
        self.assertEqual(production[0]['kwc'], 187.0)
        self.assertEqual(production[0]['azimut_deg'], 180.0)

        # Le même compte que la primitive, à l'unité près, des deux côtés.
        self.assertEqual(sum(p.modules for p in chaines),
                         sum(p['modules'] for p in primitive))

    def test_pan_non_pave_zero_partout(self):
        primitive = pans_du_document(PAN_NON_PAVE)
        self.assertEqual([p['modules'] for p in primitive], [0])

        # neededPanels n'est JAMAIS un compte posé : rien à chaîner.
        self.assertEqual(pans_poses(PAN_NON_PAVE), ())

        production = pans_du_layout(PAN_NON_PAVE)
        self.assertEqual([p['modules'] for p in production], [0])
        self.assertIsNone(production[0]['kwc'])

    def test_orientation_saisie_du_toit(self):
        layout = {'version': 2, 'zones': [{
            'id': 'z1', 'label': 'Pan est', 'pitchDeg': 15,
            'facingAzimuthDeg': 90, 'geometry': {'count': 8}}]}

        pan, = pans_poses(layout)

        self.assertEqual(pan.modules, 8)
        self.assertEqual(pan.azimut_deg, 90.0)
        self.assertEqual(pan.source_orientation, 'saisie')
