# -*- coding: utf-8 -*-
"""CALX150 — l'irradiance NUE demandée à PVGIS, jamais sa production.

CE QUI EST PROUVÉ ICI
---------------------
1. **L'URL ne porte plus le modèle PV de PVGIS** : ni ``loss``, ni
   ``peakpower``, ni ``mountingplace``, ni ``pvtechchoice``, et
   ``pvcalculation=0``. Le double comptage thermique tranché par D-CALX 4 ne
   peut donc plus se produire : la chaîne de pertes du module possède chaque
   poste.
2. **Le chemin d'aujourd'hui est INTACT** : ``serie_horaire`` (l'estimation
   rapide du constructeur de toiture) continue d'envoyer ``pvcalculation=1``
   et la somme des postes en ``loss``. Les deux portes coexistent.
3. **Les colonnes promises sont là** : ``ws10m`` et ``h_sun_deg`` sur CHAQUE
   point, et AUCUN ``p_w`` inventé — la puissance appartient à la chaîne.
4. **Rien n'est replié** : une réponse sans ``G(i)`` exploitable lève
   ``PvgisIndisponible`` avec son motif, jamais une série de zéros.
5. **La borne de volume de CALX142** : sur une fenêtre RÉELLEMENT
   pluriannuelle, la série persistée ne garde qu'une année et ``tronquee``
   vaut vrai.

AUCUN RÉSEAU, AUCUNE BASE
-------------------------
Les réponses rejouées sont des réponses PVGIS v5_3 **RÉELLES**, enregistrées
le 21/09/2026 depuis cette machine pour le point public 33,5 / −7,6 (chacune
porte son bloc ``_provenance`` : l'URL exacte, la date, et les lignes
retirées). ``SimpleTestCase`` : aucune base de données.

Run :
    python manage.py test apps.calepinage.tests.test_calx150_irradiance_nue
"""
from __future__ import annotations

import json
import pathlib
import urllib.parse

from django.test import SimpleTestCase

from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import (
    COLONNES_IRRADIANCE, ClientPvgis, EntreeInvalide, PvgisIndisponible,
    _Cache, _Limiteur,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Postes d'ESSAI — la mécanique de ``serie_horaire``, pas des pertes réelles.
POSTES_ESSAI = [
    {'poste': 'shading', 'pct': 3.5, 'source': 'mesure'},
    {'poste': 'soiling', 'pct': 2.25, 'source': 'societe'},
]

#: Horodatage FIGÉ : un test ne dépend jamais de l'horloge murale.
OBTENUE_LE = '2026-09-21T09:00:00Z'


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    """Transport INJECTÉ : rejoue une réponse enregistrée, jamais le réseau."""

    def __init__(self, charge=None, statut=200):
        self.charge = charge
        self.statut = statut
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return self.statut, json.dumps(self.charge or {})


def client(transport, **kwargs):
    """Un client au cache PRIVÉ (un test ne pollue jamais un autre)."""
    kwargs.setdefault('cache', _Cache())
    kwargs.setdefault('dormir', lambda _s: None)
    return ClientPvgis(transport, **kwargs)


def appel(cli, **extra):
    params = dict(lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
                  annee_debut=2020, annee_fin=2020, obtenue_le=OBTENUE_LE)
    params.update(extra)
    return cli.serie_irradiance(**params)


def requete(url):
    """Les paramètres de l'URL, décodés — jamais un ``in`` sur du texte."""
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


class ParametresEnvoyes(SimpleTestCase):
    """Ce qui PART vers PVGIS : l'irradiance nue, et rien d'autre."""

    def setUp(self):
        self.transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud_irradiance.json'))
        self.resultat = appel(client(self.transport))
        self.params = requete(self.transport.appels[0])

    def test_aucun_modele_pv_ne_tourne_cote_pvgis(self):
        for absent in ('loss', 'peakpower', 'mountingplace', 'pvtechchoice'):
            self.assertNotIn(absent, self.params,
                             'CALX150 : « %s » ne doit plus partir.' % absent)
        self.assertEqual(self.params['pvcalculation'], ['0'])

    def test_les_parametres_attendus_sont_la_et_lisibles(self):
        self.assertEqual(self.params['lat'], ['33.5'])
        self.assertEqual(self.params['lon'], ['-7.6'])
        self.assertEqual(self.params['angle'], ['15.0'])
        self.assertEqual(self.params['aspect'], ['0.0'])
        self.assertEqual(self.params['startyear'], ['2020'])
        self.assertEqual(self.params['endyear'], ['2020'])
        self.assertEqual(self.params['raddatabase'], ['PVGIS-SARAH3'])
        self.assertEqual(self.params['outputformat'], ['json'])
        # CALX59 : l'heure locale est DEMANDÉE ici ; la ré-indexation sur le
        # fuseau saisi du site appartient à la chaîne.
        self.assertEqual(self.params['localtime'], ['1'])

    def test_lurl_publiee_est_celle_qui_a_ete_appelee(self):
        self.assertEqual(self.resultat['url'], self.transport.appels[0])
        self.assertEqual(self.resultat['meteo']['url'],
                         self.transport.appels[0])

    def test_une_base_inconnue_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(EntreeInvalide) as leve:
            appel(client(TransportEnregistre({})), base='PVGIS-INEXISTANTE')
        self.assertEqual(leve.exception.champ, 'base')

    def test_une_fenetre_a_lenvers_est_refusee_sans_appeler_pvgis(self):
        transport = TransportEnregistre({})
        with self.assertRaises(EntreeInvalide) as leve:
            appel(client(transport), annee_debut=2021, annee_fin=2019)
        self.assertEqual(leve.exception.champ, 'annee_fin')
        self.assertEqual(transport.appels, [])


class CheminDaujourdhuiIntact(SimpleTestCase):
    """``serie_horaire`` — l'estimation rapide du builder — ne bouge PAS."""

    def test_serie_horaire_envoie_toujours_son_modele_pv_et_sa_perte(self):
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        resultat = client(transport).serie_horaire(
            lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
            politique=politique_de_pertes(POSTES_ESSAI),
            annee_debut=2020, annee_fin=2020)
        params = requete(transport.appels[0])
        self.assertEqual(params['pvcalculation'], ['1'])
        self.assertEqual(params['loss'], ['5.75'])
        self.assertEqual(params['mountingplace'], ['building'])
        self.assertEqual(params['pvtechchoice'], ['crystSi'])
        # Et sa provenance garde SES noms : ``production.py`` les lit.
        self.assertEqual(resultat['base'], 'PVGIS-SARAH3')
        self.assertIn('p_w', resultat['points'][0])


class SerieRendue(SimpleTestCase):
    """Ce qui REVIENT : les colonnes promises, aucune puissance inventée."""

    def setUp(self):
        self.resultat = appel(client(TransportEnregistre(
            charger('seriescalc_casablanca_sud_irradiance.json'))))

    def test_toute_la_fenetre_est_lue(self):
        self.assertEqual(len(self.resultat['points']), 288)
        self.assertEqual(
            sorted({p['mois'] for p in self.resultat['points']}),
            list(range(1, 13)))
        self.assertEqual(self.resultat['annees'], [2020])
        self.assertEqual(self.resultat['service'], 'seriescalc')

    def test_ws10m_et_h_sun_deg_sont_sur_chaque_point(self):
        manquants = [p for p in self.resultat['points']
                     if p['ws10m'] is None or p['h_sun_deg'] is None]
        self.assertEqual(manquants, [])

    def test_aucune_puissance_nest_publiee(self):
        for point in self.resultat['points']:
            self.assertNotIn('p_w', point)
            self.assertNotIn('p_dc_kw', point)
            self.assertNotIn('p_ac_kw', point)

    def test_les_valeurs_sont_celles_de_la_reponse_enregistree(self):
        ligne = charger(
            'seriescalc_casablanca_sud_irradiance.json')['outputs']['hourly']
        midi = [x for x in ligne if x['time'] == '20200115:1209'][0]
        point = [p for p in self.resultat['points']
                 if (p['mois'], p['jour'], p['heure']) == (1, 15, 12)][0]
        self.assertEqual(point['gi_w_m2'], midi['G(i)'])
        self.assertEqual(point['t2m_c'], midi['T2m'])
        self.assertEqual(point['ws10m'], midi['WS10m'])
        self.assertEqual(point['h_sun_deg'], midi['H_sun'])

    def test_le_bloc_serie_declare_son_pas_mesure_et_ses_colonnes(self):
        serie = self.resultat['serie_horaire']
        self.assertEqual(serie['pas_minutes'], 60)
        self.assertEqual(serie['colonnes'], list(COLONNES_IRRADIANCE))
        self.assertEqual(serie['annee_retenue'], 2020)
        self.assertFalse(serie['tronquee'])
        self.assertEqual(len(serie['points']), 288)


class ProvenanceMeteo(SimpleTestCase):
    """Le bloc ``meteo`` de CALX143, aux noms EXACTS du contrat."""

    def setUp(self):
        self.meteo = appel(client(TransportEnregistre(
            charger('seriescalc_casablanca_sud_irradiance.json')
        )))['meteo']

    def test_les_cles_du_contrat_sont_toutes_presentes(self):
        self.assertEqual(
            sorted(self.meteo),
            ['annees', 'base_demandee', 'base_meteo', 'base_rayonnement',
             'convention_azimut', 'depuis_cache', 'fenetre_annees', 'heure',
             'horizon', 'mode', 'obtenue_le', 'point', 'service', 'url'])
        # ``station`` est la SEULE clé conditionnelle du contrat : seriescalc
        # ne nomme aucune station, elle reste donc ABSENTE (jamais nulle).
        self.assertNotIn('station', self.meteo)

    def test_les_valeurs_sortent_de_la_reponse_enregistree(self):
        self.assertEqual(self.meteo['base_rayonnement'], 'PVGIS-SARAH3')
        self.assertEqual(self.meteo['base_meteo'], 'ERA5')
        self.assertEqual(self.meteo['fenetre_annees'], '2020-2020')
        self.assertEqual(self.meteo['annees'], [2020])
        self.assertEqual(self.meteo['point'],
                         {'lat': 33.5, 'lon': -7.6, 'altitude_m': 139.0})
        self.assertEqual(self.meteo['horizon'],
                         {'origine': 'dem_pvgis', 'hauteur_max_deg': None,
                          'base_horizon': 'DEM-calculated'})
        self.assertEqual(self.meteo['convention_azimut'],
                         'pvgis_sud_0_est_-90')
        self.assertEqual(self.meteo['heure']['base'], 'locale_standard')

    def test_ce_qui_appartient_a_la_chaine_reste_nul_et_nest_pas_devine(self):
        self.assertIsNone(self.meteo['mode'])
        self.assertIsNone(self.meteo['heure']['fuseau_site'])
        self.assertEqual(self.meteo['heure']['decalage_minutes'], [])


class RefusNet(SimpleTestCase):
    """Sans irradiance exploitable, RIEN n'est publié — pas des zéros."""

    def test_une_reponse_sans_serie_est_refusee(self):
        with self.assertRaises(PvgisIndisponible) as leve:
            appel(client(TransportEnregistre({'outputs': {'hourly': []}})))
        self.assertEqual(leve.exception.champ, 'meteo')

    def test_une_reponse_sans_g_i_est_refusee_en_le_disant(self):
        charge = charger('seriescalc_casablanca_sud_irradiance.json')
        for ligne in charge['outputs']['hourly']:
            ligne.pop('G(i)')
        with self.assertRaises(PvgisIndisponible) as leve:
            appel(client(TransportEnregistre(charge)))
        self.assertIn('G(i)', leve.exception.motif)
        self.assertEqual(leve.exception.champ, 'meteo')

    def test_des_horodatages_illisibles_sont_refuses(self):
        charge = charger('seriescalc_casablanca_sud_irradiance.json')
        for ligne in charge['outputs']['hourly']:
            ligne['time'] = 'jamais'
        with self.assertRaises(PvgisIndisponible):
            appel(client(TransportEnregistre(charge)))


class FenetrePluriannuelle(SimpleTestCase):
    """CALX142 — une seule année persistée, et la troncature le DIT."""

    def setUp(self):
        self.resultat = appel(
            client(TransportEnregistre(
                charger('seriescalc_casablanca_sud_deux_annees.json'))),
            annee_debut=2019, annee_fin=2020)

    def test_les_deux_annees_sont_lues_et_enumerees(self):
        self.assertEqual(self.resultat['annees'], [2019, 2020])
        self.assertEqual(self.resultat['meteo']['annees'], [2019, 2020])
        self.assertEqual(self.resultat['meteo']['fenetre_annees'],
                         '2019-2020')
        self.assertEqual(len(self.resultat['points']), 96)

    def test_la_serie_persistee_ne_garde_que_lannee_la_plus_recente(self):
        serie = self.resultat['serie_horaire']
        self.assertEqual(serie['annee_retenue'], 2020)
        self.assertTrue(serie['tronquee'])
        self.assertEqual(len(serie['points']), 48)
        self.assertEqual({p['annee'] for p in serie['points']}, {2020})

    def test_lannee_retenue_se_choisit_et_le_choix_est_republie(self):
        resultat = appel(
            client(TransportEnregistre(
                charger('seriescalc_casablanca_sud_deux_annees.json'))),
            annee_debut=2019, annee_fin=2020, annee_retenue=2019)
        self.assertEqual(resultat['serie_horaire']['annee_retenue'], 2019)
        self.assertEqual({p['annee']
                          for p in resultat['serie_horaire']['points']},
                         {2019})

    def test_une_annee_retenue_hors_serie_est_refusee_en_la_nommant(self):
        with self.assertRaises(EntreeInvalide) as leve:
            appel(client(TransportEnregistre(
                charger('seriescalc_casablanca_sud_deux_annees.json'))),
                annee_debut=2019, annee_fin=2020, annee_retenue=2017)
        self.assertEqual(leve.exception.champ, 'annee_retenue')


class CadenceEtCache(SimpleTestCase):
    """Le limiteur et le cache de CAL135 servent aussi cette porte."""

    def test_deux_appels_identiques_ne_paient_quun_aller_reseau(self):
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud_irradiance.json'))
        cli = client(transport)
        premier = appel(cli)
        second = appel(cli)
        self.assertEqual(len(transport.appels), 1)
        self.assertFalse(premier['depuis_cache'])
        self.assertTrue(second['depuis_cache'])
        # L'horodatage REPUBLIÉ est celui de la réponse mise en cache, jamais
        # celui de la relecture (CALX143).
        self.assertEqual(second['meteo']['obtenue_le'],
                         premier['meteo']['obtenue_le'])

    def test_le_limiteur_est_consulte_a_chaque_aller_reseau(self):
        vus = []

        class LimiteurTemoin(_Limiteur):
            def attendre_son_tour(self):
                vus.append(1)

        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud_irradiance.json'))
        appel(client(transport, limiteur=LimiteurTemoin()))
        self.assertEqual(len(vus), 1)
