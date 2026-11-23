# -*- coding: utf-8 -*-
"""ACAL746 (D-ACAL-81) — le client NASA POWER : série horizontale, comparaison à PVGIS.

Nouveau fichier car : client externe neuf, aucun module de test existant ne porte un
client réseau hors PVGIS (clause « Test rouge d'abord » de la tâche).

La référence est une réponse RÉELLE de l'API horaire de NASA POWER, enregistrée le
23/11/2026 (point générique 33,5° N / 7,6° O, 21-22 juin 2023, 48 heures,
``time-standard=UTC``) : ``fixtures_nasa_power/``. AUCUN appel réseau ici : le
transport est simulé.

Run :
    python manage.py test apps.calepinage.tests.test_nasa_power_client
"""
from __future__ import annotations

import copy
import datetime
import json
import os
import pathlib
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.nasa_power import (
    PARAMETRES, ClientNasaPower, NasaPowerIndisponible)
from apps.calepinage.services.pvgis_serie import _Cache

FIXTURE = (pathlib.Path(__file__).resolve().parent / 'fixtures_nasa_power'
           / 'hourly_point_33.5_-7.6_20230621_20230622_utc.json')


def _reponse():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class _Transport:
    def __init__(self, charge=None, statut=200, erreur=None):
        self.charge, self.statut, self.erreur, self.urls = charge, statut, erreur, []

    def __call__(self, url, timeout_s):
        self.urls.append((url, timeout_s))
        if self.erreur is not None:
            raise self.erreur
        return self.statut, json.dumps(self.charge)


def _client(transport):
    return ClientNasaPower(transport, cache=_Cache())


class SerieHorizontaleTest(SimpleTestCase):

    def test_la_reponse_enregistree_donne_la_serie_horizontale(self):
        charge = _reponse()
        transport = _Transport(charge)
        serie = _client(transport).serie_horizontale(33.5, -7.6, 2023, 2023, obtenue_le='2026-11-23T10:00:00Z')
        valeurs = charge['properties']['parameter']
        self.assertEqual(len(serie['points']), len(valeurs['ALLSKY_SFC_SW_DWN']))
        self.assertEqual(serie['plan_des_donnees'], 'horizontal')
        midi = next(p for p in serie['points'] if (p['jour'], p['heure']) == (21, 12))
        self.assertEqual(sorted(midi), sorted(['annee', 'mois', 'jour', 'heure', *PARAMETRES.values()]))
        for parametre, colonne in PARAMETRES.items():
            self.assertEqual(midi[colonne], valeurs[parametre]['2023062112'])
        meteo = serie['meteo']
        self.assertEqual(meteo['service'], 'nasa_power')
        self.assertEqual(meteo['obtenue_le'], '2026-11-23T10:00:00Z')
        self.assertEqual(meteo['point'], {'lat': 33.5, 'lon': -7.6, 'altitude_m': charge['geometry']['coordinates'][2]})
        self.assertIn('time-standard=UTC', meteo['url'])
        self.assertEqual(transport.urls[0][1], 10)

    def test_une_valeur_de_remplissage_refuse_en_nommant_l_heure(self):
        charge = _reponse()
        charge['properties']['parameter']['ALLSKY_SFC_SW_DNI']['2023062112'] = charge['header']['fill_value']
        with self.assertRaises(NasaPowerIndisponible) as refus:
            _client(_Transport(charge)).serie_horizontale(33.5, -7.6, 2023, 2023)
        self.assertIn('2023-06-21 à 12 h UTC', refus.exception.motif)
        self.assertEqual(refus.exception.champ, 'meteo.nasa_power.ALLSKY_SFC_SW_DNI')

    def test_une_panne_reseau_refuse_sans_serie_partielle(self):
        transport = _Transport(erreur=urllib.error.URLError('hors ligne'))
        with self.assertRaises(NasaPowerIndisponible) as refus:
            _client(transport).serie_horizontale(33.5, -7.6, 2023, 2023)
        self.assertIn('injoignable', refus.exception.motif)

    def test_aucune_cle_lue_et_coordonnee_arrondie(self):
        transport = _Transport(_reponse())
        with mock.patch.dict(os.environ, {'NASA_POWER_API_KEY': 'secret', 'NASA_API_KEY': 'secret'}):
            _client(transport).serie_horizontale(33.56789, -7.61234, 2023, 2023)
        url = transport.urls[0][0]
        self.assertNotIn('secret', url)
        self.assertNotIn('key', url.lower())
        self.assertIn('latitude=33.57', url)
        self.assertIn('longitude=-7.61', url)
        self.assertNotIn('33.56789', url)


class ComparaisonHorizontaleTest(SimpleTestCase):
    """PVGIS reste la source du chiffre ; NASA POWER est affiché à côté, jamais à la place."""

    @staticmethod
    def _annee_synthetique(ghi_w_m2):
        """Une année COMPLÈTE synthétique (même forme que la réponse réelle)."""
        charge = _reponse()
        heures = []
        jour = datetime.datetime(2023, 1, 1)
        while jour.year == 2023:
            heures.append(jour.strftime('%Y%m%d%H'))
            jour += datetime.timedelta(hours=1)
        charge['properties']['parameter'] = {
            nom: {h: (ghi_w_m2 if nom == 'ALLSKY_SFC_SW_DWN' else 1.0) for h in heures} for nom in PARAMETRES}
        return charge

    def test_l_ecart_est_calcule_a_cote_de_pvgis(self):
        ghi = 200.0
        nasa_attendu = round(ghi * 8760 / 1000.0, 1)
        pvgis = nasa_attendu / 1.05
        bloc = _client(_Transport(self._annee_synthetique(ghi))).comparaison_horizontale(
            lat=33.5, lon=-7.6, annee_debut=2023, annee_fin=2023, ghi_pvgis_kwh_m2=pvgis)
        self.assertEqual(bloc['source_du_chiffre'], 'pvgis')
        self.assertEqual(bloc['irradiation_horizontale_kwh_m2'], {'pvgis': pvgis, 'nasa_power': nasa_attendu})
        self.assertAlmostEqual(bloc['ecart_pct'], round((nasa_attendu - pvgis) / pvgis * 100.0, 2))
        self.assertEqual(bloc['annees'], [2023])
        self.assertEqual(bloc['motif'], '')

    def test_service_muet_repli_silencieux_avec_motif(self):
        bloc = _client(_Transport(erreur=TimeoutError())).comparaison_horizontale(
            lat=33.5, lon=-7.6, annee_debut=2023, annee_fin=2023, ghi_pvgis_kwh_m2=1900.0)
        self.assertIsNone(bloc['irradiation_horizontale_kwh_m2']['nasa_power'])
        self.assertIsNone(bloc['ecart_pct'])
        self.assertIn('injoignable', bloc['motif'])

    def test_annee_incomplete_aucune_moyenne(self):
        bloc = _client(_Transport(copy.deepcopy(_reponse()))).comparaison_horizontale(
            lat=33.5, lon=-7.6, annee_debut=2023, annee_fin=2023, ghi_pvgis_kwh_m2=1900.0)
        self.assertIsNone(bloc['ecart_pct'])
        self.assertIn('2023', bloc['motif'])
