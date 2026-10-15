"""ACAL69 — le serveur pose le contour d'un plan calé autour de l'épingle.

Un VRAI DXF fabriqué par ``ezdxf`` (comme ``test_calx39_import_plan``) passe
par la porte ``importer-plan/`` avec un ``calage`` : la réponse porte
``contour_lnglat``, reprojeté par ``zones.projeteur_local`` (l'inverse de
``deprojeteur_local``) et les distances sont conservées à 1 cm. Sans épingle :
409 nommant ``pin``. Sans base de données.

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

    def test_sans_epingle_409_pin(self):
        # ERR-ENF11-FUZZ-CALEPINAGE (w4) : un calage de forme CONFORME que le
        # calepinage ne permet pas est un refus d'ÉTAT (409), pas de forme.
        reponse = _appeler(calque=CALQUE, calage=_calage())
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(list(reponse.data), ['pin'])

    def test_epingle_illisible_ou_hors_bornes_409_jamais_500(self):
        for pin in ({'lat': 'x', 'lng': 1}, {'lat': 95, 'lng': 0},
                    {'lat': 0, 'lng': -181}, {'lat': 1e999, 'lng': 0}):
            calepinage = CalepinageEpingle()
            calepinage.roof_layout = {'pin': pin}
            reponse = _appeler(vue=FausseVue(calepinage), calque=CALQUE,
                               calage=_calage())
            self.assertEqual(reponse.status_code, 409, pin)
            self.assertEqual(list(reponse.data), ['pin'])

    def test_calage_a_egal_b_409_les_formes_fautives_400(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                           calque=CALQUE,
                           calage=_calage(pointB=[0, 0]))
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(list(reponse.data), ['calage'])
        fautifs = (
            _calage(pointA=['0', 0]), _calage(pointA=[0]),
            _calage(pointB=[True, 1]), _calage(distanceM=0),
            _calage(distanceM=-3), _calage(distanceM=1e-9),
            _calage(distanceM=2e7), _calage(distanceM='60'),
            _calage(rotationDeg='90'), _calage(rotationDeg=2e4),
            _calage(pointA=[1e8, 0]), '{}', '[]', 'null', '',
            'pas du json', json.dumps({'pointA': [0, 0]}))
        for calage in fautifs:
            reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                               calque=CALQUE, calage=calage)
            self.assertEqual(reponse.status_code, 400, calage)
            self.assertEqual(list(reponse.data), ['calage'], calage)

    def test_calage_forme_fautive_400_meme_sans_calque(self):
        # La forme se juge avant le contenu : un calage mal formé n'est jamais
        # « ignoré faute de calque » (et un calage vide n'est pas « absent »).
        for calage in (_calage(distanceM=0), ''):
            reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                               calage=calage)
            self.assertEqual(reponse.status_code, 400, calage)
            self.assertEqual(list(reponse.data), ['calage'], calage)

    def test_calage_sans_calque_refuse_409(self):
        reponse = _appeler(vue=FausseVue(CalepinageEpingle()),
                           calage=_calage())
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(list(reponse.data), ['calque'])

    def test_echelle_hors_des_nombres_representables_409_jamais_500(self):
        # A et B quasi confondus, distance démesurée : l'échelle déborde.
        reponse = _appeler(
            vue=FausseVue(CalepinageEpingle()), calque=CALQUE,
            calage=_calage(pointA=[0, 0], pointB=[1e-300, 0],
                           distanceM=1e7))
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(list(reponse.data), ['calage'])


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
