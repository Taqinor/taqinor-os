"""CAL92/93 — l'action ``horizon`` (contrat CAL92).

Ce qui est prouvé ici :

* la FORME pure de ``profil_horizon_pour`` (SimpleTestCase, réseau injecté
  par une réponse PVGIS ENREGISTRÉE — jamais le réseau) : points republiés en
  azimut de FACE (0=Nord), ``source``/``source_url``/``obtenu_le`` renseignés ;
* sans épingle posée, ``points`` reste ``[]``, ``source`` vaut ``None`` et
  ``detail`` NOMME la raison — jamais un horizon plat inventé ;
* PVGIS injoignable ⇒ même discipline (``points: []``, ``detail`` explicite) ;
* la ROUTE (APITestCase) : 200 avec droit de lecture, 403 sans droit, 404
  pour un calepinage d'une autre société.

Run :
    python manage.py test apps.calepinage.tests.test_api_horizon -v2
"""
from __future__ import annotations

import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.horizon import ClientHorizon
from apps.calepinage.services.pvgis_serie import PvgisIndisponible, _Cache
from apps.calepinage.views.horizon import profil_horizon_pour

from .test_api_liste import BaseApiCalepinage, url_detail

FIXTURES = (pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis')


def url_horizon(pk):
    return f'{url_detail(pk)}horizon/'


def _charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    """Rejoue une réponse ENREGISTRÉE — jamais le réseau (même patron que
    ``tests/test_prod2_horizon.py``)."""

    def __init__(self, charge=None, erreur=None):
        self.charge = charge
        self.erreur = erreur

    def __call__(self, url, timeout_s):
        if self.erreur is not None:
            raise self.erreur
        return 200, json.dumps(self.charge or {})


def _client_horizon(transport):
    return ClientHorizon(transport, cache=_Cache(), dormir=lambda _s: None)


class ObjetFactice:
    """Un calepinage minimal pour la fonction PURE — pas de base de données."""

    def __init__(self, pk, *, roof_layout=None):
        self.pk = pk
        self.roof_layout = roof_layout
        self.lead_id = None
        self.client_id = None
        self.company_id = 1


# ── La forme PURE (SimpleTestCase, aucune base de données) ──────────────────
class ProfilHorizonPourTest(SimpleTestCase):
    def test_avec_pin_republie_les_points_en_azimut_de_face(self):
        calepinage = ObjetFactice(
            1, roof_layout={'pin': {'lat': 33.5731, 'lng': -7.5898}})
        transport = TransportEnregistre(
            _charger('printhorizon_casablanca.json'))
        resultat = profil_horizon_pour(
            calepinage, client=_client_horizon(transport))

        self.assertEqual(resultat['calepinage'], 1)
        self.assertEqual(resultat['source'], 'pvgis')
        self.assertEqual(len(resultat['points']), 49)
        # A=0 (Sud, PVGIS) doit devenir azimuthDeg=180 (Sud, repère FACE).
        sud = [p for p in resultat['points'] if p['heightDeg'] == 1.5][0]
        self.assertIn('azimuthDeg', sud)
        self.assertEqual(resultat['baseHorizon'], 'DEM-calculated')
        self.assertIsNotNone(resultat['altitudeM'])
        self.assertIn('printhorizon', resultat['source_url'])
        self.assertIsNotNone(resultat['obtenu_le'])
        self.assertIsNone(resultat['detail'])

    def test_sans_pin_points_vides_et_detail_explicite(self):
        calepinage = ObjetFactice(2, roof_layout=None)
        resultat = profil_horizon_pour(calepinage)

        self.assertEqual(resultat['points'], [])
        self.assertIsNone(resultat['source'])
        self.assertIsNone(resultat['hauteurMaxDeg'])
        self.assertIsNone(resultat['source_url'])
        self.assertTrue(resultat['detail'])

    def test_pvgis_injoignable_points_vides_jamais_un_horizon_plat(self):
        calepinage = ObjetFactice(
            3, roof_layout={'pin': {'lat': 33.5731, 'lng': -7.5898}})
        transport = TransportEnregistre(
            erreur=PvgisIndisponible('PVGIS a refusé la requête.'))
        resultat = profil_horizon_pour(
            calepinage, client=_client_horizon(transport))

        self.assertEqual(resultat['points'], [])
        self.assertIsNone(resultat['source'])
        self.assertTrue(resultat['detail'])


# ── La ROUTE (APITestCase, base de données + droits) ─────────────────────────
class ActionHorizonRouteTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout={'pin': {'lat': 33.5731, 'lng': -7.5898}})

    def test_avec_pin_200_et_points_pvgis(self):
        transport = TransportEnregistre(
            _charger('printhorizon_casablanca.json'))
        with mock.patch(
                'apps.calepinage.views.horizon.ClientHorizon',
                return_value=_client_horizon(transport)):
            reponse = self.api.get(url_horizon(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['source'], 'pvgis')
        self.assertEqual(len(reponse.data['points']), 49)

    def test_sans_pin_200_points_vides(self):
        sans_pin = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans repère')
        reponse = self.api.get(url_horizon(sans_pin.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['points'], [])
        self.assertIsNone(reponse.data['source'])
        self.assertTrue(reponse.data['detail'])

    def test_sans_droit_lecture_403(self):
        reponse = self.api_sans.get(url_horizon(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 403)

    def test_calepinage_d_une_autre_societe_404(self):
        etranger = Calepinage.objects.create(
            company=self.autre, lead_id=1, titre='Chez la voisine')
        reponse = self.api.get(url_horizon(etranger.pk))
        self.assertEqual(reponse.status_code, 404)
