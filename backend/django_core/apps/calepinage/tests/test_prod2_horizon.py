"""CAL92 — le profil d'horizon du site, obtenu et servi (ou dit absent).

Les réponses rejouées ici sont des réponses PVGIS ``printhorizon`` **RÉELLES**,
enregistrées le 20/09/2026 depuis cette machine pour DEUX villes de test
(``fixtures_pvgis/printhorizon_casablanca.json`` et
``…_marrakech.json``, chacune portant son bloc ``_provenance`` avec l'URL
exacte). Aucun degré n'a été fabriqué à la main.

Ce qui est tenu :

* le profil est obtenu et MIS EN CACHE (deux appels pour le même site ne
  paient qu'une requête) ;
* PVGIS indisponible ⇒ champ VIDE et mention explicite, JAMAIS un horizon
  plat inventé ;
* le profil est corrigeable à la main, et la source le dit.
"""
from __future__ import annotations

import json
import pathlib
import unittest
import urllib.error

from apps.calepinage.services.horizon import (
    ClientHorizon, azimut_de_face, lire_profil, profil_saisi,
)
from apps.calepinage.services.pvgis_serie import (
    _Cache, EntreeInvalide, PvgisIndisponible,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

VILLES = {
    'casablanca': (33.5731, -7.5898, 'printhorizon_casablanca.json'),
    'marrakech': (31.6295, -7.9811, 'printhorizon_marrakech.json'),
}


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    """Rejoue une réponse ENREGISTRÉE — jamais le réseau."""

    def __init__(self, charge=None, statut=200, erreur=None):
        self.charge = charge
        self.statut = statut
        self.erreur = erreur
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        if self.erreur is not None:
            raise self.erreur
        return self.statut, json.dumps(self.charge or {})


def client(transport):
    return ClientHorizon(transport, cache=_Cache(), dormir=lambda _s: None)


class DeuxVillesTest(unittest.TestCase):
    """« Profil obtenu et mis en cache pour deux villes de test »."""

    def test_le_profil_est_obtenu_pour_les_deux_villes(self):
        for ville, (lat, lon, fixture) in VILLES.items():
            with self.subTest(ville=ville):
                transport = TransportEnregistre(charger(fixture))
                resultat = client(transport).profil_horizon(lat=lat, lon=lon)
                self.assertEqual(resultat['source'], 'pvgis')
                self.assertEqual(len(resultat['points']), 49)
                self.assertEqual(resultat['base_horizon'], 'DEM-calculated')
                self.assertIsNotNone(resultat['altitude_m'])
                self.assertGreaterEqual(resultat['hauteur_max_deg'], 0.0)

    def test_le_second_appel_du_meme_site_est_servi_par_le_cache(self):
        lat, lon, fixture = VILLES['casablanca']
        transport = TransportEnregistre(charger(fixture))
        cli = client(transport)
        premier = cli.profil_horizon(lat=lat, lon=lon)
        second = cli.profil_horizon(lat=lat, lon=lon)
        self.assertFalse(premier['depuis_cache'])
        self.assertTrue(second['depuis_cache'])
        self.assertEqual(len(transport.appels), 1)
        self.assertEqual(premier['points'], second['points'])

    def test_deux_villes_differentes_sont_deux_appels(self):
        transport = TransportEnregistre(
            charger(VILLES['casablanca'][2]))
        cli = client(transport)
        cli.profil_horizon(lat=33.5731, lon=-7.5898)
        cli.profil_horizon(lat=31.6295, lon=-7.9811)
        self.assertEqual(len(transport.appels), 2)

    def test_l_url_appelee_est_bien_printhorizon_sans_perte(self):
        transport = TransportEnregistre(charger(VILLES['marrakech'][2]))
        resultat = client(transport).profil_horizon(lat=31.6295, lon=-7.9811)
        self.assertIn('printhorizon', resultat['url'])
        # ``printhorizon`` est une GÉOMÉTRIE : aucun paramètre de pertes n'y
        # a de sens, et n'en fabriquer aucun n'est pas une entorse à CAL238.
        self.assertNotIn('loss=', resultat['url'])


class ConventionAzimutTest(unittest.TestCase):

    def test_l_azimut_de_face_est_republie_a_cote_de_celui_de_pvgis(self):
        profil = lire_profil(charger(VILLES['casablanca'][2]))
        sud = [p for p in profil['points']
               if p['azimut_pvgis_deg'] == 0.0][0]
        self.assertEqual(sud['azimut_face_deg'], 180.0)

    def test_la_conversion_est_l_inverse_exacte_de_celle_du_client(self):
        from apps.calepinage.services.pvgis_serie import azimut_pvgis

        for face in (0.0, 90.0, 180.0, 270.0, 315.0):
            with self.subTest(face=face):
                self.assertAlmostEqual(
                    azimut_de_face(azimut_pvgis(face)) % 360.0, face % 360.0,
                    places=6)


class PvgisIndisponibleTest(unittest.TestCase):
    """« PVGIS indisponible → champ vide, jamais un horizon plat inventé »."""

    def test_reseau_coupe_aucun_horizon_publie(self):
        transport = TransportEnregistre(
            erreur=urllib.error.URLError('coupé'))
        with self.assertRaises(PvgisIndisponible) as refus:
            client(transport).profil_horizon(lat=33.5, lon=-7.6)
        self.assertIn('injoignable', str(refus.exception))

    def test_refus_http_aucun_horizon_publie(self):
        transport = TransportEnregistre({}, statut=400)
        with self.assertRaises(PvgisIndisponible):
            client(transport).profil_horizon(lat=33.5, lon=-7.6)

    def test_reponse_sans_profil_est_refusee_en_le_disant(self):
        with self.assertRaises(PvgisIndisponible) as refus:
            lire_profil({'outputs': {}})
        self.assertIn('VIDE', str(refus.exception))
        self.assertIn('plat', str(refus.exception))

    def test_coordonnee_illisible_refusee_en_nommant_le_champ(self):
        transport = TransportEnregistre(charger(VILLES['casablanca'][2]))
        with self.assertRaises(EntreeInvalide) as refus:
            client(transport).profil_horizon(lat='ici', lon=-7.6)
        self.assertEqual(refus.exception.champ, 'lat')
        self.assertEqual(transport.appels, [])


class ProfilSaisiTest(unittest.TestCase):
    """Le profil se CORRIGE à la main — et la source change avec lui."""

    def test_un_profil_saisi_porte_la_source_saisie(self):
        profil = profil_saisi([
            {'azimut_face_deg': 90.0, 'hauteur_deg': 12.0},
            {'azimut_face_deg': 180.0, 'hauteur_deg': 3.0},
        ], note='relevé au clinomètre, 20/09')
        self.assertEqual(profil['source'], 'saisie')
        self.assertEqual(profil['hauteur_max_deg'], 12.0)
        self.assertIn('clinomètre', profil['note'])

    def test_les_deux_conventions_d_azimut_sont_publiees(self):
        profil = profil_saisi([{'azimut_face_deg': 180.0,
                                'hauteur_deg': 3.0}])
        self.assertEqual(profil['points'][0]['azimut_pvgis_deg'], 0.0)

    def test_un_profil_saisi_vide_est_refuse(self):
        with self.assertRaises(EntreeInvalide) as refus:
            profil_saisi([])
        self.assertEqual(refus.exception.champ, 'horizon')
        self.assertIn('plat', str(refus.exception))

    def test_un_point_hors_bornes_nomme_son_rang(self):
        with self.assertRaises(EntreeInvalide) as refus:
            profil_saisi([{'azimut_face_deg': 400.0, 'hauteur_deg': 3.0}])
        self.assertEqual(refus.exception.champ, 'horizon[0].azimut_face_deg')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
