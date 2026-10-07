"""CAL138 — la production se calcule PAR PAN, jamais sur un azimut moyen.

Les trois séries rejouées (sud, est, ouest) sont des réponses PVGIS RÉELLES
enregistrées le 20/09/2026 au même point, même pente, même fenêtre : seul
l'azimut change. C'est ce qui permet de comparer honnêtement « deux pans
opposés » à « leur moyenne » sans fabriquer une seule irradiation.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.production import _pans_du_layout

#: Azimuts de FACE du document de toiture (0 = Nord, 180 = Sud).
SUD, EST, OUEST = 180.0, 90.0, 270.0


class LecturePansTest(unittest.TestCase):
    """La lecture du document ne suppose rien qu'il ne dise pas."""

    def test_la_geometrie_posee_prime_sur_le_resultat_decran(self):
        pans = _pans_du_layout({'zones': [{
            'id': 'z1', 'label': 'Pan Sud', 'pitchDeg': 20.0,
            'facingAzimuthDeg': 170.0,
            'result': {'count': 4, 'kwc': 2.88},
            'geometry': {'count': 12, 'kwc': 8.64, 'azimuthDeg': 180.0,
                         'tiltDeg': 15.0},
        }]})
        self.assertEqual(pans, [{
            # ACAL265 — la clé STABLE du pan, à part de son libellé.
            'cle': 'z1',
            'pan': 'Pan Sud', 'modules': 12, 'kwc': 8.64,
            'azimut_deg': 180.0, 'inclinaison_deg': 15.0}])

    def test_document_sans_zone_ne_rend_aucun_pan(self):
        self.assertEqual(_pans_du_layout({}), [])
        self.assertEqual(_pans_du_layout(None), [])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
