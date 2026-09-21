"""CALX143 — l'énoncé de source météo est DÉRIVÉ d'une réponse réelle.

Un contrat de provenance qui inventerait ses propres valeurs serait un comble.
Ce fichier construit donc le bloc `resultat['meteo']` depuis la réponse PVGIS
enregistrée `tests/fixtures_pvgis/seriescalc_casablanca_sud.json` — rejouée
par le client, jamais appelée sur le réseau — et compare, clé par clé, ce que
le producteur publie à ce que l'exemple committé promet.

UN SEUL POINT, UNE SEULE RÉPONSE. La fixture d'horizon décrit un AUTRE point
(33,5731 / −7,5898) que la fixture de série (33,5 / −7,6) : elle n'est donc
pas mélangée à l'exemple. Elle sert uniquement à prouver que
`services/horizon.py::lire_profil` publie bien les trois noms de champs que le
bloc consomme (`base_horizon`, `hauteur_max_deg`, `altitude_m`).

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx143_contrat_meteo
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.horizon import lire_profil
from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import (
    ClientPvgis, _Cache, azimut_pvgis,
)

RACINE = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLONS = RACINE / 'contract_samples'
FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Postes d'ESSAI : la mécanique de l'appel, pas des pertes réelles.
POSTES_ESSAI = [{'poste': 'shading', 'pct': 3.5, 'source': 'mesure'}]


def charger(chemin):
    return json.loads(chemin.read_text(encoding='utf-8'))


METEO = charger(ECHANTILLONS / 'calepinage_meteo.json')
SIMULATION = charger(ECHANTILLONS / 'calepinage_simulation.json')


class TransportEnregistre:
    """Rejoue une réponse enregistrée — le réseau n'est jamais touché."""

    def __init__(self, charge):
        self.charge = charge
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return 200, json.dumps(self.charge)


def serie_de_la_fixture():
    """La réponse `seriescalc` réelle, passée par le client du module."""
    charge = charger(FIXTURES / 'seriescalc_casablanca_sud.json')
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    return charge, client.serie_horaire(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        politique=politique_de_pertes(POSTES_ESSAI),
        annee_debut=2020, annee_fin=2020)


class EnveloppeTest(unittest.TestCase):
    """L'échantillon se relit, et ses deux états portent les mêmes clés."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, METEO)
        self.assertIn('resultat/', METEO['endpoint'])

    def test_memes_clefs_que_le_bloc_meteo_de_calx4(self):
        for etat in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(METEO[etat]['meteo']),
                             sorted(SIMULATION[etat]['meteo']),
                             f'{etat} : les clés du bloc ont divergé de '
                             'calepinage_simulation.json (CALX4).')
            for sous_bloc in ('point', 'horizon', 'heure',
                              'albedo_face_avant'):
                self.assertEqual(
                    sorted(METEO[etat]['meteo'][sous_bloc]),
                    sorted(SIMULATION[etat]['meteo'][sous_bloc]),
                    f'{etat}.{sous_bloc} : clés divergentes de CALX4.')

    def test_vide_ne_publie_aucun_zero(self):
        bloc = METEO['exemple_vide']['meteo']
        for cle in ('service', 'base_rayonnement', 'base_meteo', 'mode',
                    'fenetre_annees', 'url', 'obtenue_le', 'depuis_cache',
                    'convention_azimut'):
            self.assertIsNone(bloc[cle], cle)
        self.assertEqual(bloc['annees'], [])
        self.assertEqual(bloc['heure']['decalage_minutes'], [])
        self.assertTrue(bloc['albedo_face_avant']['motif'].strip())


class DeriveDeLaFixtureTest(unittest.TestCase):
    """Les valeurs du contrat sortent de la réponse PVGIS, pas d'une idée."""

    def setUp(self):
        self.charge, self.serie = serie_de_la_fixture()
        self.entrees = self.charge['inputs']
        self.attendu = METEO['exemple']['meteo']

    def test_les_trois_valeurs_exigees_par_le_plan(self):
        self.assertEqual(self.serie['base'], 'PVGIS-SARAH3')
        self.assertEqual(self.serie['base_meteo'], 'ERA5')
        self.assertEqual(self.serie['fenetre_annees'], '2020-2020')

    def test_le_bloc_committe_reprend_la_reponse_cle_par_cle(self):
        self.assertEqual(self.attendu['service'], self.serie['service'])
        self.assertEqual(self.attendu['base_rayonnement'], self.serie['base'])
        self.assertEqual(self.attendu['base_meteo'], self.serie['base_meteo'])
        self.assertEqual(self.attendu['fenetre_annees'],
                         self.serie['fenetre_annees'])
        self.assertEqual(self.attendu['depuis_cache'],
                         self.serie['depuis_cache'])
        self.assertEqual(self.attendu['point']['lat'],
                         self.entrees['location']['latitude'])
        self.assertEqual(self.attendu['point']['lon'],
                         self.entrees['location']['longitude'])
        self.assertEqual(self.attendu['point']['altitude_m'],
                         self.entrees['location']['elevation'])

    def test_les_annees_sont_celles_des_points_servis(self):
        annees = sorted({point['annee'] for point in self.serie['points']})
        self.assertEqual(self.attendu['annees'], annees)

    def test_l_horizon_dit_ce_que_la_reponse_dit_et_rien_de_plus(self):
        meteo_data = self.entrees['meteo_data']
        self.assertTrue(meteo_data['use_horizon'])
        self.assertEqual(self.attendu['horizon']['base_horizon'],
                         meteo_data['horizon_data'])
        self.assertEqual(self.attendu['horizon']['origine'], 'dem_pvgis')
        self.assertIsNone(
            self.attendu['horizon']['hauteur_max_deg'],
            "`seriescalc` ne publie AUCUN profil d'horizon : la hauteur "
            'maximale reste nulle plutôt que de valoir 0° — un horizon plat '
            "et un horizon non publié ne se lisent pas pareil.")

    def test_l_url_committee_est_bien_celle_du_service(self):
        self.assertTrue(self.serie['url'].startswith(self.attendu['url']))


class ProducteurDuProfilDHorizonTest(unittest.TestCase):
    """`lire_profil` publie les trois noms de champs que le bloc consomme."""

    def test_les_trois_champs_existent_chez_le_producteur(self):
        profil = lire_profil(charger(FIXTURES / 'printhorizon_casablanca.json'))
        for champ in ('base_horizon', 'hauteur_max_deg', 'altitude_m'):
            self.assertIn(champ, profil)
            self.assertIsNotNone(profil[champ])
        # Le profil décrit un AUTRE point que la série : il ne rejoint donc
        # pas l'exemple committé, il prouve seulement le vocabulaire.
        self.assertEqual(profil['source'], 'pvgis')


class ConventionsDeclareesTest(unittest.TestCase):
    """La convention d'azimut et la clé conditionnelle `station`."""

    def test_la_convention_d_azimut_est_celle_du_convertisseur(self):
        self.assertEqual(METEO['exemple']['meteo']['convention_azimut'],
                         'pvgis_sud_0_est_-90')
        self.assertEqual(azimut_pvgis(180.0), 0.0)      # face Sud
        self.assertEqual(azimut_pvgis(90.0), -90.0)     # face Est
        self.assertEqual(azimut_pvgis(270.0), 90.0)     # face Ouest

    def test_station_reste_absente_tant_que_la_reponse_ne_la_porte_pas(self):
        for etat in ('exemple', 'exemple_vide'):
            self.assertNotIn(
                'station', METEO[etat]['meteo'],
                "PVGIS `seriescalc` ne nomme aucune station : la clé est "
                'ABSENTE, jamais remplie de la ville la plus proche.')

    def test_l_albedo_reste_nul_avec_son_motif(self):
        albedo = METEO['exemple']['meteo']['albedo_face_avant']
        self.assertIsNone(albedo['valeur'])
        self.assertTrue(albedo['motif'].strip(),
                        'Une valeur absente se dit ; elle ne se devine pas.')


if __name__ == '__main__':
    unittest.main()
