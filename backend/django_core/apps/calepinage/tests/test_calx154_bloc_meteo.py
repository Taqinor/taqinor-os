"""CALX154 — `resultat['meteo']` : d'où sort le chiffre de production.

`services/production.py` ne publiait que trois clés sous `production.base`, et
`services/electrique.py` écrivait un `production.base` tout à `None` : ni
l'altitude, ni la base météo, ni l'origine de l'horizon, ni l'URL réellement
appelée n'atteignaient jamais le résultat — pourtant toutes rendues par
`pvgis_serie._provenance` et `horizon.lire_profil`. PVsyst imprime les
paramètres de la source météo employée
(https://www.pvsyst.com/help/project-design/results/index.html) : ce bloc fait
la même chose, en UN endroit.

Les valeurs sont DÉRIVÉES de la réponse PVGIS enregistrée
`tests/fixtures_pvgis/seriescalc_casablanca_sud_irradiance.json` — rejouée par
le client, jamais appelée sur le réseau. Aucune base de données.

Run :
    python manage.py test apps.calepinage.tests.test_calx154_bloc_meteo
"""
from __future__ import annotations

import copy
import json
import pathlib
import unittest

from apps.calepinage.services.chaine_pertes import (
    ALBEDO_FACE_AVANT, CLES_METEO_PUBLIEES, SOUS_BLOCS_METEO, MeteoIndecise,
    appliquer_chaine,
)
from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache

RACINE = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLONS = RACINE / 'contract_samples'
FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_meteo.json').read_text(encoding='utf-8'))


class TransportEnregistre:
    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def charge_irradiance():
    return json.loads(
        (FIXTURES / 'seriescalc_casablanca_sud_irradiance.json')
        .read_text(encoding='utf-8'))


def rendu_du_client(charge):
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    return client.serie_irradiance(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        annee_debut=2020, annee_fin=2020, obtenue_le='2026-09-21T10:14:00Z')


def reglages(**valeurs):
    return {cle: {'valeur': valeur, 'source': 'societe', 'reference': 'essai'}
            for cle, valeur in valeurs.items()}


def contexte_de(rendu, **reglages_supplementaires):
    return {
        'meteo': copy.deepcopy(rendu['meteo']),
        'site': {'lat': 33.5, 'lon': -7.6},
        'reglages_simulation': reglages(mode_meteo='tmy',
                                        **reglages_supplementaires),
    }


def simuler(charge=None, **reglages_supplementaires):
    """Une simulation complète sur la fixture : rend ``(resultat, rendu)``."""
    rendu = rendu_du_client(charge if charge is not None
                            else charge_irradiance())
    contexte = contexte_de(rendu, **reglages_supplementaires)
    contexte['reglages_simulation'].update(
        reglages(mode_meteo='pluriannuel', fenetre_annees='2020-2020'))
    serie = {'pas_minutes': 60, 'points': rendu['points'],
             'colonne_energie': 'p_w'}
    for point in serie['points']:
        point.setdefault('p_w', 0.0)
    resultat = {}
    appliquer_chaine(serie, contexte, resultat=resultat)
    return resultat, rendu


class BlocPublieTest(unittest.TestCase):
    """Le bloc a la FORME du contrat, et rien de plus."""

    def setUp(self):
        self.resultat, self.rendu = simuler()
        self.bloc = self.resultat['meteo']

    def test_le_bloc_est_ecrit_par_la_chaine(self):
        self.assertIn('meteo', self.resultat)

    def test_les_clefs_sont_celles_du_contrat_committe(self):
        # ACAL744 / ACAL746 — ``comparaison_base`` et ``comparaison_nasa_power``
        # sont posées APRÈS la chaîne par ``simuler_calepinage``
        # (meteo_comparee), pas par elle.
        attendues = set(CONTRAT['exemple']['meteo']) - {
            'comparaison_base', 'comparaison_nasa_power'}
        self.assertTrue(
            attendues.issubset(set(self.bloc)),
            'une clé du contrat CALX143 manque au bloc publié : '
            f'{sorted(attendues - set(self.bloc))}')
        for nom, champs in SOUS_BLOCS_METEO.items():
            self.assertEqual(sorted(self.bloc[nom]), sorted(champs), nom)

    def test_station_reste_absente_quand_la_reponse_ne_la_porte_pas(self):
        self.assertNotIn(
            'station', self.bloc,
            'PVGIS `seriescalc` ne nomme aucune station : la clé est '
            'ABSENTE, jamais remplie de la ville la plus proche.')

    def test_les_seuls_ajouts_sont_ceux_de_l_ordonnanceur(self):
        # Le compteur d'appels (CALX155) et les cinq clés de résolution
        # (CALX192) : rien d'autre ne s'ajoute au contrat CALX143.
        surplus = set(self.bloc) - set(CLES_METEO_PUBLIEES)
        self.assertEqual(surplus, {
            'appels_pvgis', 'pas_minutes', 'resolution_minutes',
            'pas_charge_minutes', 'interpolation', 'note_resolution'})


class SixValeursVerifiablesTest(unittest.TestCase):
    """Les six clés que la fixture permet de VÉRIFIER, une à une."""

    def setUp(self):
        self.charge = charge_irradiance()
        self.resultat, self.rendu = simuler(self.charge)
        self.bloc = self.resultat['meteo']
        self.entrees = self.charge['inputs']

    def test_base_rayonnement(self):
        self.assertEqual(self.bloc['base_rayonnement'],
                         self.entrees['meteo_data']['radiation_db'])

    def test_base_meteo(self):
        self.assertEqual(self.bloc['base_meteo'],
                         self.entrees['meteo_data']['meteo_db'])

    def test_mode(self):
        self.assertEqual(self.bloc['mode'], 'pluriannuel')

    def test_fenetre_annees(self):
        self.assertEqual(self.bloc['fenetre_annees'], '2020-2020')

    def test_point_altitude_m(self):
        self.assertEqual(self.bloc['point']['altitude_m'],
                         self.entrees['location']['elevation'])

    def test_horizon_origine(self):
        self.assertEqual(self.bloc['horizon']['origine'], 'dem_pvgis')

    def test_l_url_reellement_appelee_atteint_le_resultat(self):
        self.assertEqual(self.bloc['url'], self.rendu['url'])
        self.assertIn('pvcalculation=0', self.bloc['url'])


class AucuneValeurPlausibleTest(unittest.TestCase):
    """Ce que la réponse ne porte pas reste NUL — jamais 0, jamais plausible."""

    def test_une_reponse_sans_elevation_ne_rend_pas_zero(self):
        charge = charge_irradiance()
        charge['inputs']['location'].pop('elevation')
        resultat, _ = simuler(charge)
        self.assertIsNone(
            resultat['meteo']['point']['altitude_m'],
            "Une altitude absente vaut « non publiée » : un 0 se lirait "
            '« site au niveau de la mer, mesuré ».')

    def test_l_albedo_reste_nul_avec_son_motif_tant_qu_il_n_est_pas_saisi(self):
        resultat, _ = simuler()
        albedo = resultat['meteo']['albedo_face_avant']
        self.assertIsNone(albedo['valeur'])
        self.assertEqual(albedo['motif'], ALBEDO_FACE_AVANT['motif'])

    def test_un_albedo_saisi_et_source_remplit_la_cle(self):
        resultat, _ = simuler(albedo_mensuel=[0.2] * 12)
        albedo = resultat['meteo']['albedo_face_avant']
        self.assertEqual(albedo['valeur'], [0.2] * 12)
        self.assertIn('societe', albedo['motif'])

    def test_un_contexte_sans_meteo_publie_des_nuls_et_pas_des_zeros(self):
        resultat = {}
        appliquer_chaine(
            {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]},
            {'reglages_simulation': reglages(mode_meteo='tmy')},
            resultat=resultat)
        bloc = resultat['meteo']
        for cle in ('service', 'base_rayonnement', 'base_meteo',
                    'fenetre_annees', 'url', 'obtenue_le', 'depuis_cache',
                    'convention_azimut'):
            self.assertIsNone(bloc[cle], cle)
        self.assertEqual(bloc['annees'], [])
        self.assertEqual(bloc['heure']['decalage_minutes'], [])


class ModeEtCompteurTest(unittest.TestCase):
    """Le mode REFUSE la publication quand il n'est pas saisi (CALX153)."""

    def test_sans_mode_saisi_la_publication_est_refusee(self):
        rendu = rendu_du_client(charge_irradiance())
        contexte = {'meteo': copy.deepcopy(rendu['meteo'])}
        with self.assertRaises(MeteoIndecise) as capture:
            appliquer_chaine({'pas_minutes': 60, 'points': [{'p_w': 1.0}]},
                             contexte, resultat={})
        self.assertIn('mode_meteo', capture.exception.champ)

    def test_sans_resultat_la_chaine_ne_publie_rien_et_ne_refuse_rien(self):
        _, cascade = appliquer_chaine(
            {'pas_minutes': 60, 'points': [{'p_w': 1.0}]}, {})
        self.assertTrue(cascade['etapes'])

    def test_le_compteur_d_appels_pvgis_est_publie(self):
        resultat, _ = simuler()
        self.assertEqual(resultat['meteo']['appels_pvgis'], 0)

    def test_en_mode_tmy_aucune_annee_observee_n_est_publiee(self):
        rendu = rendu_du_client(charge_irradiance())
        contexte = contexte_de(rendu)
        resultat = {}
        appliquer_chaine({'pas_minutes': 60, 'points': rendu['points']},
                         contexte, resultat=resultat)
        self.assertEqual(resultat['meteo']['mode'], 'tmy')
        self.assertEqual(resultat['meteo']['annees'], [])


class ProductionBaseIntacteTest(unittest.TestCase):
    """Les lecteurs d'aujourd'hui gardent `production.base` tel quel."""

    def test_le_bloc_production_deja_ecrit_n_est_pas_touche(self):
        rendu = rendu_du_client(charge_irradiance())
        contexte = contexte_de(rendu)
        base = {'source': 'pvgis', 'base_rayonnement': 'PVGIS-SARAH3',
                'fenetre_annees': '2020-2020', 'loss_passee_pct': 7.25,
                'commentaire': 'essai'}
        resultat = {'production': {'base': dict(base)}}
        appliquer_chaine({'pas_minutes': 60, 'points': rendu['points']},
                         contexte, resultat=resultat)
        self.assertEqual(resultat['production']['base'], base)


def _reponse_mensuelle(watts_par_mois, annees=(2019, 2020)):
    """Une heure par mois et par année, ``gi_w_m2`` connu (jeu d'essai)."""
    return {'serie_horaire': {'pas_minutes': 60}, 'depuis_cache': False,
            'points': [{'annee': annee, 'mois': mois, 'jour': 15, 'heure': 12,
                        'gi_w_m2': watts_par_mois[mois - 1]}
                       for annee in annees for mois in range(1, 13)]}


class ComparaisonDeBasesTest(unittest.TestCase):
    """ACAL744 — l'irradiation de la base utilisée face à l'AUTRE base."""

    PRINCIPALE = [100.0 * mois for mois in range(1, 13)]
    COMPAREE = [90.0] + [110.0 * mois for mois in range(2, 13)]

    def _comparer(self, principale, comparee, **options):
        from apps.calepinage.services.meteo_comparee import _bloc_comparaison

        return _bloc_comparaison(principale, comparee,
                                 base_principale='PVGIS-SARAH3',
                                 base_comparee='PVGIS-ERA5', **options)

    def test_ecart_annuel_et_mensuel_calcule_a_la_main(self):
        bloc = self._comparer(_reponse_mensuelle(self.PRINCIPALE),
                              _reponse_mensuelle(self.COMPAREE))
        # Par année : Σ W/m² × 1 h ÷ 1000, moyenne des deux années identiques.
        principale = sum(self.PRINCIPALE) / 1000.0
        comparee = sum(self.COMPAREE) / 1000.0
        self.assertEqual(bloc['ecart_pct'],
                         round((comparee - principale) / principale * 100, 2))
        self.assertEqual(bloc['irradiation_kwh_m2'],
                         {'principale': round(principale, 1),
                          'comparee': round(comparee, 1)})
        self.assertEqual(len(bloc['mensuel']), 12)
        self.assertEqual(bloc['mensuel'][0]['ecart_pct'], -10.0)
        self.assertEqual(bloc['mensuel'][5]['ecart_pct'], 10.0)
        self.assertEqual(bloc['motif'], '')
        self.assertEqual((bloc['base_principale'], bloc['base_comparee']),
                         ('PVGIS-SARAH3', 'PVGIS-ERA5'))

    def test_annees_differentes_motif_sans_ecart(self):
        from apps.calepinage.services.meteo_comparee import MOTIF_ANNEES

        bloc = self._comparer(_reponse_mensuelle(self.PRINCIPALE),
                              _reponse_mensuelle(self.COMPAREE,
                                                 annees=(2020, 2021)))
        self.assertIsNone(bloc['ecart_pct'])
        self.assertEqual(bloc['motif'], MOTIF_ANNEES)

    def test_autre_base_indisponible_motif_et_appel_compte(self):
        from apps.calepinage.services.meteo_comparee import comparer_bases
        from apps.calepinage.services.pvgis_serie import PvgisIndisponible

        class Client:
            def __init__(self, refuse):
                self.refuse, self.bases = refuse, []

            def serie_irradiance(self, *, base, **_demande):
                self.bases.append(base)
                if self.refuse and base == 'PVGIS-ERA5':
                    raise PvgisIndisponible('PVGIS ne répond pas.')
                return _reponse_mensuelle(
                    ComparaisonDeBasesTest.PRINCIPALE if base == 'PVGIS-SARAH3'
                    else ComparaisonDeBasesTest.COMPAREE)

        plan = {'lat': 33.57, 'lon': -7.59, 'inclinaison_deg': 30,
                'azimut_pvgis_deg': 0}
        decision = {'fenetre_annees': (2019, 2020)}
        compteur = {'appels': 0}
        refus = comparer_bases(Client(True), plan, decision, {}, None, compteur)
        self.assertIsNone(refus['ecart_pct'])
        self.assertIn('PVGIS ne répond pas', refus['motif'])
        client = Client(False)
        bloc = comparer_bases(client, plan, decision, {}, None, compteur)
        self.assertEqual(client.bases, ['PVGIS-SARAH3', 'PVGIS-ERA5'])
        self.assertIsNotNone(bloc['ecart_pct'])
        self.assertEqual(compteur['appels'], 2)
        fichier = comparer_bases(client, plan, decision, {},
                                 {'identite': {}}, compteur)
        self.assertIsNone(fichier['ecart_pct'])
        self.assertTrue(fichier['motif'])

    def test_contrat_porte_le_bloc(self):
        contrat = json.loads((ECHANTILLONS / 'calepinage_meteo.json')
                             .read_text(encoding='utf-8'))
        servi = self._comparer(_reponse_mensuelle(self.PRINCIPALE),
                               _reponse_mensuelle(self.COMPAREE))
        self.assertEqual(contrat['exemple']['meteo']['comparaison_base'],
                         servi)
        self.assertIsNone(contrat['exemple_vide']['meteo']['comparaison_base'])
        sans = contrat['exemple_comparaison_sans_ecart']['meteo'][
            'comparaison_base']
        self.assertEqual(sorted(sans), sorted(servi))
        self.assertIsNone(sans['ecart_pct'])
        self.assertTrue(sans['motif'])


# ═══ ACAL746 (D-ACAL-81) — NASA POWER : seconde source météo, en comparaison seulement ═══
# La référence est une réponse RÉELLE de l'API horaire de NASA POWER, enregistrée le
# 23/11/2026 (point générique 33,5° N / 7,6° O, 21-22 juin 2023, 48 heures,
# ``time-standard=UTC``). AUCUN appel réseau : le transport est simulé.
FIXTURE_NASA = (pathlib.Path(__file__).resolve().parent / 'fixtures_nasa_power'
                / 'hourly_point_33.5_-7.6_20230621_20230622_utc.json')


def _reponse_nasa():
    return json.loads(FIXTURE_NASA.read_text(encoding='utf-8'))


class _TransportNasa:
    def __init__(self, charge=None, statut=200, erreur=None):
        self.charge, self.statut, self.erreur, self.urls = charge, statut, erreur, []

    def __call__(self, url, timeout_s):
        self.urls.append((url, timeout_s))
        if self.erreur is not None:
            raise self.erreur
        return self.statut, json.dumps(self.charge)


def _client_nasa(transport):
    from apps.calepinage.services.nasa_power import ClientNasaPower
    return ClientNasaPower(transport, cache=_Cache())


class NasaPowerSerieHorizontaleTest(unittest.TestCase):

    def test_la_reponse_enregistree_donne_la_serie_horizontale(self):
        from apps.calepinage.services.nasa_power import PARAMETRES
        charge = _reponse_nasa()
        transport = _TransportNasa(charge)
        serie = _client_nasa(transport).serie_horizontale(33.5, -7.6, 2023, 2023, obtenue_le='2026-11-23T10:00:00Z')
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
        from apps.calepinage.services.nasa_power import NasaPowerIndisponible
        charge = _reponse_nasa()
        charge['properties']['parameter']['ALLSKY_SFC_SW_DNI']['2023062112'] = charge['header']['fill_value']
        with self.assertRaises(NasaPowerIndisponible) as refus:
            _client_nasa(_TransportNasa(charge)).serie_horizontale(33.5, -7.6, 2023, 2023)
        self.assertIn('2023-06-21 à 12 h UTC', refus.exception.motif)
        self.assertEqual(refus.exception.champ, 'meteo.nasa_power.ALLSKY_SFC_SW_DNI')

    def test_une_panne_reseau_refuse_sans_serie_partielle(self):
        import urllib.error

        from apps.calepinage.services.nasa_power import NasaPowerIndisponible
        transport = _TransportNasa(erreur=urllib.error.URLError('hors ligne'))
        with self.assertRaises(NasaPowerIndisponible) as refus:
            _client_nasa(transport).serie_horizontale(33.5, -7.6, 2023, 2023)
        self.assertIn('injoignable', refus.exception.motif)

    def test_aucune_cle_lue_et_coordonnee_arrondie(self):
        import os
        from unittest import mock
        transport = _TransportNasa(_reponse_nasa())
        with mock.patch.dict(os.environ, {'NASA_POWER_API_KEY': 'secret', 'NASA_API_KEY': 'secret'}):
            _client_nasa(transport).serie_horizontale(33.56789, -7.61234, 2023, 2023)
        url = transport.urls[0][0]
        self.assertNotIn('secret', url)
        self.assertNotIn('key', url.lower())
        self.assertIn('latitude=33.57', url)
        self.assertIn('longitude=-7.61', url)
        self.assertNotIn('33.56789', url)


class NasaPowerComparaisonTest(unittest.TestCase):
    """PVGIS reste la source du chiffre ; NASA POWER est affiché à côté, jamais à la place."""

    @staticmethod
    def _annee_synthetique(ghi_w_m2):
        """Une année COMPLÈTE synthétique (même forme que la réponse réelle)."""
        import datetime

        from apps.calepinage.services.nasa_power import PARAMETRES
        charge = _reponse_nasa()
        heures, instant = [], datetime.datetime(2023, 1, 1)
        while instant.year == 2023:
            heures.append(instant.strftime('%Y%m%d%H'))
            instant += datetime.timedelta(hours=1)
        charge['properties']['parameter'] = {
            nom: {h: (ghi_w_m2 if nom == 'ALLSKY_SFC_SW_DWN' else 1.0) for h in heures} for nom in PARAMETRES}
        return charge

    def test_l_ecart_est_calcule_a_cote_de_pvgis(self):
        ghi = 200.0
        nasa_attendu = round(ghi * 8760 / 1000.0, 1)
        pvgis = nasa_attendu / 1.05
        bloc = _client_nasa(_TransportNasa(self._annee_synthetique(ghi))).comparaison_horizontale(
            lat=33.5, lon=-7.6, annee_debut=2023, annee_fin=2023, ghi_pvgis_kwh_m2=pvgis)
        self.assertEqual(bloc['source_du_chiffre'], 'pvgis')
        self.assertEqual(bloc['irradiation_horizontale_kwh_m2'], {'pvgis': pvgis, 'nasa_power': nasa_attendu})
        self.assertAlmostEqual(bloc['ecart_pct'], round((nasa_attendu - pvgis) / pvgis * 100.0, 2))
        self.assertEqual(bloc['annees'], [2023])
        self.assertEqual(bloc['motif'], '')

    def test_service_muet_repli_silencieux_avec_motif(self):
        bloc = _client_nasa(_TransportNasa(erreur=TimeoutError())).comparaison_horizontale(
            lat=33.5, lon=-7.6, annee_debut=2023, annee_fin=2023, ghi_pvgis_kwh_m2=1900.0)
        self.assertIsNone(bloc['irradiation_horizontale_kwh_m2']['nasa_power'])
        self.assertIsNone(bloc['ecart_pct'])
        self.assertIn('injoignable', bloc['motif'])

    def test_annee_incomplete_aucune_moyenne(self):
        bloc = _client_nasa(_TransportNasa(copy.deepcopy(_reponse_nasa()))).comparaison_horizontale(
            lat=33.5, lon=-7.6, annee_debut=2023, annee_fin=2023, ghi_pvgis_kwh_m2=1900.0)
        self.assertIsNone(bloc['ecart_pct'])
        self.assertIn('2023', bloc['motif'])


class NasaPowerDansLaSimulationTest(unittest.TestCase):
    """ACAL746 — ``meteo.comparaison_nasa_power`` posé par la simulation (``meteo_comparee``),
    au contrat du bloc météo ; jamais un appel réseau en test, jamais une simulation arrêtée."""

    PLAN = {'lat': 33.57, 'lon': -7.59}
    DECISION = {'fenetre_annees': (2019, 2020)}
    GAIN = {'ghi_annuel_kwh_m2': 1850.0}

    @staticmethod
    def _deux_annees(ghi_w_m2):
        import datetime

        from apps.calepinage.services.nasa_power import PARAMETRES
        charge = _reponse_nasa()
        heures, instant = [], datetime.datetime(2019, 1, 1)
        while instant.year <= 2020:
            heures.append(instant.strftime('%Y%m%d%H'))
            instant += datetime.timedelta(hours=1)
        charge['properties']['parameter'] = {
            nom: {h: (ghi_w_m2 if nom == 'ALLSKY_SFC_SW_DWN' else 1.0) for h in heures} for nom in PARAMETRES}
        return charge

    def _comparer(self, client, *, fichier=None, decision=None):
        from apps.calepinage.services.meteo_comparee import comparer_nasa_power
        return comparer_nasa_power(client, self.PLAN, decision or self.DECISION, fichier, self.GAIN)

    @staticmethod
    def _client_pvgis(**attributs):
        return type('ClientPvgisEssai', (), attributs)()

    def test_le_bloc_servi_est_celui_du_contrat(self):
        contrat = json.loads((ECHANTILLONS / 'calepinage_meteo.json').read_text(encoding='utf-8'))
        transport = _TransportNasa(self._deux_annees(210.0))
        servi = self._comparer(self._client_pvgis(client_nasa_power=_client_nasa(transport)))
        attendu = copy.deepcopy(contrat['exemple']['meteo']['comparaison_nasa_power'])
        servi['meteo']['obtenue_le'] = attendu['meteo']['obtenue_le']  # l'horloge du jour
        self.assertEqual(servi, attendu)
        self.assertEqual(servi['source_du_chiffre'], 'pvgis')
        self.assertEqual(len(transport.urls), 1)
        self.assertIsNone(contrat['exemple_vide']['meteo']['comparaison_nasa_power'])

    def test_un_transport_de_test_ne_recoit_jamais_d_url_nasa(self):
        contrat = json.loads((ECHANTILLONS / 'calepinage_meteo.json').read_text(encoding='utf-8'))
        transport = _TransportNasa(self._deux_annees(210.0))
        servi = self._comparer(self._client_pvgis(transport=transport))
        self.assertEqual(transport.urls, [])
        self.assertEqual(servi, contrat['exemple_comparaison_sans_ecart']['meteo']['comparaison_nasa_power'])

    def test_le_transport_reseau_de_pvgis_sert_aussi_nasa_power(self):
        from unittest import mock

        from apps.calepinage.services import nasa_power, pvgis_serie
        sonde = _TransportNasa(self._deux_annees(210.0))
        with mock.patch.object(pvgis_serie, '_transport_urllib', sonde):
            with mock.patch.object(nasa_power, '_CACHE_PARTAGE', pvgis_serie._Cache()):
                servi = self._comparer(self._client_pvgis(transport=pvgis_serie._transport_urllib))
        self.assertEqual(len(sonde.urls), 1)
        self.assertIn('power.larc.nasa.gov', sonde.urls[0][0])
        self.assertEqual(servi['irradiation_horizontale_kwh_m2']['nasa_power'], 1842.1)

    def test_aucune_panne_ne_fait_echouer_la_simulation(self):
        from apps.calepinage.services.meteo_comparee import MOTIF_NASA_ECHEC

        class Casse:
            def comparaison_horizontale(self, **_demande):
                raise AssertionError('transport inattendu')

        servi = self._comparer(self._client_pvgis(client_nasa_power=Casse()))
        self.assertEqual(servi['motif'], MOTIF_NASA_ECHEC)
        self.assertIsNone(servi['ecart_pct'])
        self.assertEqual(servi['irradiation_horizontale_kwh_m2']['pvgis'], 1850.0)

    def test_fichier_depose_ou_annee_type_aucune_comparaison(self):
        from apps.calepinage.services.meteo_comparee import MOTIF_NASA_FENETRE, MOTIF_NASA_FICHIER
        transport = _TransportNasa(self._deux_annees(210.0))
        client = self._client_pvgis(client_nasa_power=_client_nasa(transport))
        self.assertEqual(self._comparer(client, fichier={'identite': {}})['motif'], MOTIF_NASA_FICHIER)
        self.assertEqual(self._comparer(client, decision={'fenetre_annees': None})['motif'], MOTIF_NASA_FENETRE)
        self.assertEqual(transport.urls, [])


if __name__ == '__main__':
    unittest.main()
