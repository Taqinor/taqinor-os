"""ACAL69 — le serveur pose le contour d'un plan calé autour de l'épingle.

Un VRAI DXF fabriqué par ``ezdxf`` (comme ``test_calx39_import_plan``) passe
par la porte ``importer-plan/`` avec un ``calage`` : la réponse porte
``contour_lnglat``, reprojeté par ``zones.projeteur_local`` (l'inverse de
``deprojeteur_local``) et les distances sont conservées à 1 cm. Sans épingle :
400 nommant ``pin``. Sans base de données.

Run ::

    python manage.py test apps.calepinage.tests.test_acal_plan_vers_pan -v 2
"""
from __future__ import annotations

import json
import math

from django.test import SimpleTestCase

from apps.calepinage.tests.test_calx39_import_plan import (
    CALQUE,
    FausseVue,
    _appeler,
)

PIN = {'lat': 33.5, 'lng': -7.6}


class CalepinageEpingle:
    """Un calepinage NU dont le document porte une épingle."""

    pk = 1
    company = None
    roof_layout = {'pin': PIN}


def _distance_m(p, q, pin=PIN):
    from apps.calepinage.services.zones import projeteur_local

    projeter = projeteur_local((pin['lng'], pin['lat']))
    (x1, y1), (x2, y2) = projeter(p), projeter(q)
    return math.hypot(x2 - x1, y2 - y1)


def _calage(**surcharges):
    calage = {'pointA': [0, 0], 'pointB': [30, 0], 'distanceM': 60.0,
              'rotationDeg': 0}
    calage.update(surcharges)
    return json.dumps(calage)


class ContourLnglatTest(SimpleTestCase):

    def test_contour_lnglat_autour_de_l_epingle_distances_conservees(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                           calque=CALQUE, calage=_calage())
        self.assertEqual(reponse.status_code, 200)
        geo = reponse.data['contour_lnglat']
        self.assertEqual(len(geo), 4)
        # 30 x 18 dans le fichier, 2 m réels par unité : 60 x 36 m.
        self.assertAlmostEqual(_distance_m(geo[0], geo[1]), 60.0, delta=0.01)
        self.assertAlmostEqual(_distance_m(geo[1], geo[2]), 36.0, delta=0.01)
        # Centré sur l'épingle (pas au « golfe de Guinée » : lng/lat sont
        # des degrés voisins de l'épingle, pas des mètres).
        lng_moy = sum(p[0] for p in geo) / 4
        lat_moy = sum(p[1] for p in geo) / 4
        self.assertAlmostEqual(lng_moy, PIN['lng'], places=6)
        self.assertAlmostEqual(lat_moy, PIN['lat'], places=6)
        self.assertFalse(reponse.data['enregistre'])

    def test_la_rotation_conserve_les_distances(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                           calque=CALQUE, calage=_calage(rotationDeg=90))
        geo = reponse.data['contour_lnglat']
        self.assertAlmostEqual(_distance_m(geo[0], geo[1]), 60.0, delta=0.01)
        # Tourné de 90 degres : le premier côté (60 m) devient vertical.
        self.assertAlmostEqual(geo[0][0], geo[1][0], places=7)

    def test_sans_calage_pas_de_contour_lnglat(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()), calque=CALQUE)
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.data['contour_lnglat'])

    def test_sans_epingle_400_pin(self):
        reponse = _appeler(calque=CALQUE, calage=_calage())
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data), ['pin'])

    def test_calage_a_egal_b_refuse(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                           calque=CALQUE,
                           calage=_calage(pointB=[0, 0]))
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data), ['calage'])

    def test_calage_sans_calque_refuse(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                           calage=_calage())
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data), ['calque'])


class DeprojeteurTest(SimpleTestCase):

    def test_deprojeter_est_l_inverse_de_projeter(self):
        from apps.calepinage.services.zones import (
            deprojeteur_local,
            projeteur_local,
        )

        origine = (-7.6, 33.5)
        point = (-7.5987, 33.5013)
        retour = deprojeteur_local(origine)(projeteur_local(origine)(point))
        self.assertAlmostEqual(retour[0], point[0], places=10)
        self.assertAlmostEqual(retour[1], point[1], places=10)
