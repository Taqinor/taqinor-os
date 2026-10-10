"""ACAL276 — l'aire d'un pan DESSINÉ se calcule de ses sommets (aire projetée).

Constat C-ACAL-125 : une zone tracée dans l'atelier mais sans bloc ``result``
sortait de ``extract_roof_config`` avec ``surface_m2 = 0.0`` et la feuille de
masse (``lestage.masse_du_layout``) ne publiait aucune masse par m² (surface
``None``). Les deux lisent désormais ``apps.ventes.services.aire_du_pan`` :
``result.areaM2`` s'il est porté, sinon l'aire PROJETÉE des ``vertices``
(sphère R = 6 378 137 m, même reprojection ENU que l'écran).

Test-du-test : remettre la seule lecture ``result.areaM2`` (dans
``aire_du_pan`` ou dans ``extract_roof_config``) ⇒
``test_zone_dessinee_aire_projetee`` rougit (0.0 / None).
"""
from __future__ import annotations

import math

from django.test import SimpleTestCase

from apps.calepinage.services.lestage import _masse_du_layout
from apps.ventes.services import aire_du_pan, extract_roof_config

#: Un rectangle à Casablanca : 0,00018° de longitude × 0,00015° de latitude.
LAT0, LNG0 = 33.5731, -7.5898
DLAT, DLNG = 0.00015, 0.00018
SOMMETS = [[LNG0, LAT0], [LNG0 + DLNG, LAT0],
           [LNG0 + DLNG, LAT0 + DLAT], [LNG0, LAT0 + DLAT]]

#: Oracle INDÉPENDANT (forme close d'un rectangle sur la sphère WGS84 projetée
#: localement autour de son coin) — pas une relecture du code testé.
_R = 6378137.0
AIRE_ATTENDUE = ((math.radians(DLNG) * _R * math.cos(math.radians(LAT0)))
                 * (math.radians(DLAT) * _R))


class AireDuPanTest(SimpleTestCase):

    def test_oracle_est_le_rectangle_de_l_audit(self):
        # La sonde de l'audit mesurait 278,77 m² pour ce tracé.
        self.assertAlmostEqual(AIRE_ATTENDUE, 278.77, places=2)

    def test_zone_dessinee_aire_projetee(self):
        zone = {'id': 'z1', 'label': 'Toit plat', 'vertices': SOMMETS,
                'geometry': {'count': 10}}
        self.assertAlmostEqual(aire_du_pan(zone), AIRE_ATTENDUE, places=4)

        cfg = extract_roof_config({'version': 2, 'zones': [zone]})
        self.assertAlmostEqual(cfg['surface_m2'], 278.77, places=2)
        self.assertAlmostEqual(cfg['pans'][0]['surface_m2'], 278.77,
                               places=2)

        masse = _masse_du_layout({'version': 2, 'zones': [zone]},
                                 poids_module_kg=22.0, section={})
        pan = masse['pans'][0]
        self.assertAlmostEqual(pan['surface_pan_m2'], AIRE_ATTENDUE, places=4)
        self.assertAlmostEqual(pan['masse_par_m2_kg'], 220.0 / AIRE_ATTENDUE,
                               places=6)

    def test_result_area_prime_sur_les_sommets(self):
        zone = {'vertices': SOMMETS, 'result': {'count': 4, 'areaM2': 12.5}}
        self.assertEqual(aire_du_pan(zone), 12.5)
        cfg = extract_roof_config({'zones': [zone]})
        self.assertEqual(cfg['surface_m2'], 12.5)

    def test_sommets_objets_lat_lng(self):
        zone = {'vertices': [{'lat': lat, 'lng': lng}
                             for lng, lat in SOMMETS]}
        self.assertAlmostEqual(aire_du_pan(zone), AIRE_ATTENDUE, places=4)

    def test_sans_aire_ni_contour_aucune_surface_inventee(self):
        self.assertIsNone(aire_du_pan({'result': {'count': 3}}))
        self.assertIsNone(aire_du_pan({'vertices': SOMMETS[:2]}))
        self.assertIsNone(aire_du_pan({'result': {'areaM2': 0}}))
        self.assertIsNone(aire_du_pan(None))
