"""ACAL281 — UNE projection lat/lng → mètres et UNE paire boussole ↔ aspect.

Constat C-ACAL-144 : le même rectangle à Casablanca mesurait 278,04 m²
(``zones.projeteur_local``, constantes 111 320 / 110 540), 276,82 m²
(``repere.js``, ellipsoïde) et 278,77 m² (``calepinage_options.anneau_enu``,
sphère) ; le Nord valait −180 dans ``geometrie._azimut_boussole_vers_aspect``
et +180 dans ``pvgis_serie.azimut_pvgis``. ``core/calepinage/geo.py`` est
désormais la source unique (sphère R = 6 378 137 m) ; les autres délèguent.

Test-du-test : remettre ``110540`` dans ``zones.projeteur_local`` ⇒
``test_meme_aire_partout`` (et la longueur de tronçon) rougissent.
"""
from __future__ import annotations

import math

from django.test import SimpleTestCase

from apps.calepinage.services import horizon, pvgis_serie, zones
from apps.calepinage.services.lidar_ign import _ajuster_plan
from apps.calepinage.services.troncons import _longueur_polyligne
from apps.ventes import calepinage_options
from apps.ventes import services as ventes_services
from apps.ventes.domain.geometrie import _aspect_vers_azimut_boussole
from core.calepinage import geo

LAT0, LNG0 = 33.5731, -7.5898
DLAT, DLNG = 0.00015, 0.00018
CONTOUR = [[LNG0, LAT0], [LNG0 + DLNG, LAT0],
           [LNG0 + DLNG, LAT0 + DLAT], [LNG0, LAT0 + DLAT]]

#: Oracle INDÉPENDANT : la sphère de rayon 6 378 137 m, écrite en clair.
_R = 6378137.0
_M_PAR_DEG = math.pi / 180.0 * _R
AIRE_SPHERE = (DLNG * _M_PAR_DEG * math.cos(math.radians(LAT0))
               * DLAT * _M_PAR_DEG)

AZIMUTS = [0.0, 90.0, 180.0, 270.0, 359.9]
ASPECTS_ATTENDUS = [180.0, -90.0, 0.0, 90.0, 179.9]
ASPECTS = [-180.0, -90.0, 0.0, 12.345, 90.0]
AZIMUTS_ATTENDUS = [0.0, 90.0, 180.0, 192.345, 270.0]


def _lacet(anneau):
    total = 0.0
    for i, (ax, ay) in enumerate(anneau):
        bx, by = anneau[(i + 1) % len(anneau)]
        total += ax * by - bx * ay
    return abs(total) / 2.0


class MemeAirePartoutTest(SimpleTestCase):

    def test_meme_aire_partout(self):
        projeter = zones.projeteur_local((LNG0, LAT0))
        aires = {
            'core.geo': geo.aire_contour_m2(CONTOUR),
            'ventes.aire_contour_m2': ventes_services.aire_contour_m2(CONTOUR),
            'ventes.aire_du_pan': ventes_services.aire_du_pan(
                {'vertices': CONTOUR}),
            'calepinage_options.anneau_enu': _lacet(
                calepinage_options.anneau_enu(CONTOUR, CONTOUR[0])),
            'zones.projeteur_local': _lacet([projeter(p) for p in CONTOUR]),
        }
        for source, aire in aires.items():
            with self.subTest(source=source):
                self.assertAlmostEqual(aire, AIRE_SPHERE, delta=0.01)
        self.assertAlmostEqual(AIRE_SPHERE, 278.77, places=2)

    def test_deprojeteur_inverse_exact(self):
        origine = (LNG0, LAT0)
        point = (LNG0 + DLNG, LAT0 + DLAT)
        retour = zones.deprojeteur_local(origine)(
            zones.projeteur_local(origine)(point))
        self.assertAlmostEqual(retour[0], point[0], places=12)
        self.assertAlmostEqual(retour[1], point[1], places=12)

    def test_longueur_de_troncon_sur_la_meme_sphere(self):
        longueur = _longueur_polyligne(
            [(LNG0, LAT0, None), (LNG0, LAT0 + 0.001, None)])
        self.assertAlmostEqual(longueur, 0.001 * _M_PAR_DEG, places=6)

    def test_pente_lidar_sur_la_meme_sphere(self):
        # Plan qui monte vers le Nord de 0,5 m/m (atan 0,5 = 26,57°), écrit
        # en mètres de la sphère : l'ajustement doit relire 26,6°.
        mesures = []
        for i in range(3):
            for j in range(3):
                lat = LAT0 + j * DLAT
                lon = LNG0 + i * DLNG
                mesures.append((lon, lat, 0.5 * (lat - LAT0) * _M_PAR_DEG))
        pente, azimut = _ajuster_plan(mesures)
        self.assertEqual(pente, 26.6)
        self.assertEqual(azimut, 180.0)


class MemeConversionPartoutTest(SimpleTestCase):

    def test_meme_conversion_partout(self):
        for azimut, attendu in zip(AZIMUTS, ASPECTS_ATTENDUS):
            valeurs = {
                'core.geo': geo.boussole_vers_aspect(azimut),
                'ventes._azimut_boussole_vers_aspect':
                    ventes_services._azimut_boussole_vers_aspect(azimut),
                'pvgis_serie.azimut_pvgis': pvgis_serie.azimut_pvgis(azimut),
                'horizon.profil_saisi': horizon.profil_saisi(
                    [{'azimut_face_deg': azimut, 'hauteur_deg': 1.0}]
                )['points'][0]['azimut_pvgis_deg'],
            }
            with self.subTest(azimut=azimut):
                self.assertEqual(len(set(valeurs.values())), 1, valeurs)
                self.assertAlmostEqual(valeurs['core.geo'], attendu,
                                       places=9)

        for aspect, attendu in zip(ASPECTS, AZIMUTS_ATTENDUS):
            valeurs = {
                'core.geo': geo.aspect_vers_boussole(aspect),
                'ventes._aspect_vers_azimut_boussole':
                    _aspect_vers_azimut_boussole(aspect),
                'horizon.azimut_de_face': horizon.azimut_de_face(aspect),
            }
            with self.subTest(aspect=aspect):
                self.assertEqual(len(set(valeurs.values())), 1, valeurs)
                self.assertAlmostEqual(valeurs['core.geo'], attendu,
                                       places=9)

    def test_nord_vaut_plus_180_partout(self):
        for azimut in (0.0, 360.0):
            with self.subTest(azimut=azimut):
                self.assertEqual(geo.boussole_vers_aspect(azimut), 180.0)
                self.assertEqual(
                    ventes_services._azimut_boussole_vers_aspect(azimut),
                    180.0)
                self.assertEqual(pvgis_serie.azimut_pvgis(azimut), 180.0)

    def test_valeur_illisible(self):
        self.assertIsNone(geo.boussole_vers_aspect(None))
        self.assertIsNone(geo.aspect_vers_boussole('abc'))
        self.assertIsNone(
            ventes_services._azimut_boussole_vers_aspect(float('nan')))
