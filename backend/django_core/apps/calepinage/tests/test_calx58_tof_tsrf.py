# -*- coding: utf-8 -*-
"""CALX58 — TOF et TSRF par pan, à côté de l'accès solaire.

CE QUI EST PROUVÉ ICI
---------------------
1. **Le plan optimal coûte UN appel, et c'est bien ``PVcalc``** avec
   ``optimalangles=1`` (``seriescalc`` n'a pas ce paramètre). Le second pan
   du même site est servi par le CACHE du client : une seule requête part.
2. **Un pan posé aux angles optimaux rend ``tof == 1,0``** à 0,5 % près, sur
   la réponse PVcalc RÉELLE enregistrée
   (``fixtures_pvgis/pvcalc_optimalangles_casablanca.json``). Un pan moins
   bien orienté rend un TOF strictement inférieur.
3. **TSRF = accès solaire × TOF** (HelioScope), et un pan SANS ``solarAccess``
   publie ``tsrf: null`` AVEC son motif — jamais un accès supposé à 100 %.
4. **Rien n'est supposé quand PVGIS manque** : sans client, ou sur un refus
   de PVGIS, ``tof`` et ``tsrf`` valent ``null`` avec leur motif. Jamais 1,0.
5. **La chaîne publie les clés du contrat** : les cinq colonnes
   d'orientation sur ``production.par_pan[]`` et le bloc
   ``resultat['ombrage']`` (``par_pan`` + ``methode``), tels que
   ``contract_samples/calepinage_simulation.json`` les décrit.

AUCUN RÉSEAU : le transport du client est injecté et rejoue la réponse
enregistrée. ``SimpleTestCase`` : aucune base de données.

Run :
    python manage.py test apps.calepinage.tests.test_calx58_tof_tsrf
"""
from __future__ import annotations

import json
import pathlib
import urllib.parse

from django.test import SimpleTestCase

from apps.calepinage.services import orientation
from apps.calepinage.services.chaine_pertes import (
    CLE_CLIENT_PVGIS, CLE_SORTIES_PAR_PAN, appliquer_chaine,
)
from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache

RACINE = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
CONTRAT = json.loads(
    (RACINE / 'contract_samples' / 'calepinage_simulation.json')
    .read_text(encoding='utf-8'))

PVCALC = json.loads(
    (FIXTURES / 'pvcalc_optimalangles_casablanca.json')
    .read_text(encoding='utf-8'))

#: Ce que la réponse ENREGISTRÉE porte — lu ici, jamais recopié en constante
#: dans le code produit.
H_OPTIMALE = PVCALC['outputs']['totals']['fixed']['H(i)_y']
INCLINAISON_OPTIMALE = PVCALC['inputs']['mounting_system']['fixed'][
    'slope']['value']
AZIMUT_OPTIMAL_PVGIS = PVCALC['inputs']['mounting_system']['fixed'][
    'azimuth']['value']

SITE = {'lat': 33.5, 'lon': -7.6, 'fuseau': 'Africa/Casablanca'}


class TransportEnregistre:
    """Rejoue la réponse enregistrée et COMPTE ce qui part sur le réseau."""

    def __init__(self, charge=None, statut=200):
        self.charge = charge if charge is not None else PVCALC
        self.statut = statut
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return self.statut, json.dumps(self.charge)


def client(transport=None):
    """Un client au cache PRIVÉ (un test ne pollue jamais un autre)."""
    return ClientPvgis(transport or TransportEnregistre(), cache=_Cache(),
                       dormir=lambda _s: None)


def serie_de(irradiation_kwh_m2, *, annees=(2020,), points_par_an=365):
    """Une série dont l'irradiation ANNUELLE vaut exactement la valeur dite.

    Le test fabrique SON entrée (c'est le propre d'un test de propriété) :
    la somme des ``gi_w_m2`` au pas horaire vaut, par an, l'irradiation
    demandée.
    """
    par_point = irradiation_kwh_m2 * 1000.0 / points_par_an
    points = [{'annee': annee, 'mois': 1 + rang % 12, 'jour': 1, 'heure': 12,
               'gi_w_m2': par_point, 'p_w': 1000.0}
              for annee in annees for rang in range(points_par_an)]
    return {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': points}


def requete(url):
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


class PlanOptimalTest(SimpleTestCase):
    """L'appel PVcalc : ce qui part, ce qui revient, ce qu'il coûte."""

    def setUp(self):
        self.transport = TransportEnregistre()
        self.optimal = orientation.plan_optimal(33.5, -7.6,
                                                client=client(self.transport))

    def test_le_service_appele_est_pvcalc(self):
        self.assertIn('/PVcalc?', self.transport.appels[0])

    def test_les_angles_sont_demandes_optimaux(self):
        params = requete(self.transport.appels[0])
        self.assertEqual(params['optimalangles'], ['1'])
        # Les angles ne sont PAS imposés : c'est PVGIS qui les trouve.
        self.assertNotIn('angle', params)
        self.assertNotIn('aspect', params)

    def test_l_irradiation_optimale_est_celle_de_la_reponse(self):
        self.assertEqual(self.optimal['irradiation_kwh_m2'],
                         round(H_OPTIMALE, 2))
        self.assertEqual(self.optimal['source'], orientation.SOURCE_PVGIS)
        self.assertEqual(self.optimal['motif_omission'], '')

    def test_les_deux_angles_optimaux_sont_publies(self):
        self.assertEqual(self.optimal['inclinaison_deg'],
                         float(INCLINAISON_OPTIMALE))
        self.assertEqual(self.optimal['azimut_pvgis_deg'],
                         float(AZIMUT_OPTIMAL_PVGIS))

    def test_l_azimut_optimal_est_republie_en_azimut_de_face(self):
        # PVGIS compte depuis le Sud (0), le document de toiture en azimut de
        # FACE (180 = Sud) : publier la mauvaise convention ferait lire un
        # écart qui n'existe pas.
        self.assertEqual(self.optimal['azimut_deg'],
                         round((AZIMUT_OPTIMAL_PVGIS + 180.0) % 360.0, 1))

    def test_le_second_appel_du_meme_site_vient_du_cache(self):
        cli = client(self.transport)
        premier = orientation.plan_optimal(33.5, -7.6, client=cli)
        second = orientation.plan_optimal(33.5, -7.6, client=cli)
        self.assertEqual(premier['irradiation_kwh_m2'],
                         second['irradiation_kwh_m2'])
        self.assertTrue(second['depuis_cache'])

    def test_sans_client_le_plan_optimal_est_omis_et_le_dit(self):
        omis = orientation.plan_optimal(33.5, -7.6, client=None)
        self.assertIsNone(omis['irradiation_kwh_m2'])
        self.assertEqual(omis['motif_omission'], orientation.MOTIF_SANS_CLIENT)

    def test_un_site_sans_coordonnees_est_omis_et_le_dit(self):
        omis = orientation.plan_optimal(None, None, client=client())
        self.assertEqual(omis['motif_omission'], orientation.MOTIF_SANS_SITE)

    def test_un_refus_de_pvgis_ne_leve_pas_et_porte_son_motif(self):
        transport = TransportEnregistre(statut=500)
        omis = orientation.plan_optimal(33.5, -7.6, client=client(transport))
        self.assertIsNone(omis['irradiation_kwh_m2'])
        self.assertIn('500', omis['motif_omission'])


class TofDuPanTest(SimpleTestCase):
    """Le rapport lui-même : mesuré, ou omis en nommant ce qui manque."""

    def bloc(self, serie, **extra):
        return orientation.tof_du_pan(
            33.5, -7.6, INCLINAISON_OPTIMALE, AZIMUT_OPTIMAL_PVGIS,
            client=client(), serie=serie, **extra)

    def test_un_pan_aux_angles_optimaux_rend_un_tof_de_un(self):
        bloc = self.bloc(serie_de(H_OPTIMALE))
        self.assertAlmostEqual(bloc['tof'], 1.0, delta=0.005)
        self.assertEqual(bloc['source'], orientation.SOURCE_PVGIS)

    def test_le_tof_d_un_pan_moins_bien_oriente_est_plus_faible(self):
        bloc = self.bloc(serie_de(H_OPTIMALE * 0.82))
        self.assertLess(bloc['tof'], 1.0)
        self.assertAlmostEqual(bloc['tof'], 0.82, delta=0.005)

    def test_une_fenetre_pluriannuelle_ne_double_pas_le_numerateur(self):
        deux_ans = serie_de(H_OPTIMALE, annees=(2019, 2020))
        bloc = self.bloc(deux_ans)
        self.assertEqual(bloc['annees_serie'], 2)
        self.assertAlmostEqual(bloc['tof'], 1.0, delta=0.005)

    def test_le_tsrf_est_l_acces_solaire_multiplie_par_le_tof(self):
        bloc = self.bloc(serie_de(H_OPTIMALE), acces_solaire_pct=96.5)
        self.assertAlmostEqual(bloc['tsrf'], bloc['tof'] * 0.965, places=4)
        self.assertEqual(bloc['acces_solaire_moyen_pct'], 96.5)
        self.assertEqual(bloc['motif_omission'], '')

    def test_sans_acces_solaire_le_tsrf_est_omis_et_le_tof_reste(self):
        bloc = self.bloc(serie_de(H_OPTIMALE))
        self.assertIsNotNone(bloc['tof'])
        self.assertIsNone(bloc['tsrf'])
        self.assertEqual(bloc['motif_omission'],
                         orientation.MOTIF_SANS_ACCES_SOLAIRE)

    def test_sans_serie_le_tof_est_omis_et_le_dit(self):
        bloc = self.bloc(None)
        self.assertIsNone(bloc['tof'])
        self.assertIsNone(bloc['tsrf'])
        self.assertEqual(bloc['motif_omission'], orientation.MOTIF_SANS_SERIE)

    def test_une_serie_sans_irradiance_est_omise_et_le_dit(self):
        muette = {'pas_minutes': 60, 'colonne_energie': 'p_w',
                  'points': [{'annee': 2020, 'p_w': 1000.0}]}
        bloc = self.bloc(muette)
        self.assertIsNone(bloc['tof'])
        self.assertEqual(bloc['motif_omission'],
                         orientation.MOTIF_SERIE_SANS_IRRADIANCE)

    def test_sans_client_aucun_tof_n_est_suppose_a_un(self):
        bloc = orientation.tof_du_pan(
            33.5, -7.6, 15.0, 0.0, client=None, serie=serie_de(H_OPTIMALE),
            acces_solaire_pct=96.5)
        self.assertIsNone(bloc['tof'])
        self.assertIsNone(bloc['tsrf'])
        self.assertEqual(bloc['motif_omission'], orientation.MOTIF_SANS_CLIENT)

    def test_le_bloc_porte_ce_qui_a_servi_au_calcul(self):
        bloc = self.bloc(serie_de(H_OPTIMALE))
        self.assertEqual(sorted(bloc), sorted(orientation.CLES_ORIENTATION))
        self.assertEqual(bloc['irradiation_optimale_kwh_m2'],
                         round(H_OPTIMALE, 2))
        self.assertAlmostEqual(bloc['irradiation_reelle_kwh_m2'],
                               H_OPTIMALE, delta=0.05)


class AccesSolaireMoyenTest(SimpleTestCase):
    """La moyenne ne porte QUE sur les modules CALCULÉS (contrat v2)."""

    def test_la_moyenne_exclut_les_modules_non_calcules(self):
        pct, motif = orientation.acces_solaire_moyen_pct(
            {'solar_access': {'values': [1.0, 0.8, None]}})
        self.assertEqual(pct, 90.0)
        self.assertEqual(motif, '')

    def test_une_valeur_hors_bornes_est_non_calculee(self):
        pct, _motif = orientation.acces_solaire_moyen_pct(
            {'solar_access': {'values': [1.0, 4.2]}})
        self.assertEqual(pct, 100.0)

    def test_aucun_module_calcule_est_omis_avec_son_motif(self):
        pct, motif = orientation.acces_solaire_moyen_pct(
            {'solar_access': {'values': [None, None]}})
        self.assertIsNone(pct)
        self.assertEqual(motif, orientation.MOTIF_SANS_ACCES_SOLAIRE)

    def test_le_document_est_relu_pan_par_pan(self):
        layout = {'zones': [
            {'label': 'PAN-A',
             'geometry': {'solarAccess': {'values': [0.9, 1.0]}}},
            {'label': 'PAN-B',
             'geometry': {'solarAccess': {'values': [0.5, 0.5]}}}]}
        ombrage = {'solar_access': {'method': {'horizon': False}}}
        pan_a, _ = orientation.acces_solaire_moyen_pct(
            ombrage, {'cle': 'A', 'pan': 'PAN-A'}, layout=layout)
        pan_b, _ = orientation.acces_solaire_moyen_pct(
            ombrage, {'cle': 'B', 'pan': 'PAN-B'}, layout=layout)
        self.assertEqual(pan_a, 95.0)
        self.assertEqual(pan_b, 50.0)


def plans():
    return [
        {'cle': 'A', 'pan': 'PAN-A', 'modules': 8, 'kwc': 4.0,
         'azimut_deg': 185.0, 'inclinaison_deg': INCLINAISON_OPTIMALE,
         'azimut_pvgis_deg': AZIMUT_OPTIMAL_PVGIS},
        {'cle': 'B', 'pan': 'PAN-B', 'modules': 6, 'kwc': 3.0,
         'azimut_deg': 90.0, 'inclinaison_deg': 20.0,
         'azimut_pvgis_deg': -90.0},
    ]


def simuler(*, avec_client=True, ombrage=None):
    contexte = {
        'site': dict(SITE),
        'meteo': {'heure': {'base': 'utc'}},
        'plans': plans(),
        'reglages_simulation': {
            'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
            'fenetre_annees': {'valeur': '2020-2020', 'source': 'societe'}},
        CLE_SORTIES_PAR_PAN: {'A': serie_de(H_OPTIMALE),
                              'B': serie_de(H_OPTIMALE * 0.75)},
    }
    if ombrage is not None:
        contexte['ombrage'] = ombrage
    if avec_client:
        contexte[CLE_CLIENT_PVGIS] = client()
    resultat = {}
    appliquer_chaine(serie_de(H_OPTIMALE), contexte, resultat)
    return resultat


class PublieParLaChaineTest(SimpleTestCase):
    """Les deux endroits où le contrat CALX4 attend TOF et TSRF."""

    def setUp(self):
        self.resultat = simuler(ombrage={'solar_access': {
            'par_pan': {'PAN-A': [1.0, 0.93], 'PAN-B': [0.8, 0.8]}}})

    def test_les_cinq_colonnes_d_orientation_sont_sur_chaque_pan(self):
        modele = [ligne for ligne
                  in CONTRAT['exemple']['production']['par_pan']][0]
        for ligne in self.resultat['production']['par_pan']:
            for cle in ('tof', 'tsrf', 'inclinaison_optimale_deg',
                        'azimut_optimal_deg', 'source'):
                self.assertIn(cle, ligne, cle)
                self.assertIn(cle, modele, cle)

    def test_le_pan_aux_angles_optimaux_publie_un_tof_de_un(self):
        pan_a = self.resultat['production']['par_pan'][0]
        self.assertAlmostEqual(pan_a['tof'], 1.0, delta=0.005)
        self.assertEqual(pan_a['source'], orientation.SOURCE_PVGIS)
        self.assertEqual(pan_a['inclinaison_optimale_deg'],
                         float(INCLINAISON_OPTIMALE))

    def test_le_bloc_ombrage_a_les_cles_de_l_echantillon(self):
        bloc = self.resultat['ombrage']
        self.assertEqual(sorted(bloc),
                         sorted(CONTRAT['exemple']['ombrage']))
        modele = CONTRAT['exemple']['ombrage']['par_pan'][0]
        for ligne in bloc['par_pan']:
            self.assertEqual(sorted(ligne), sorted(modele))

    def test_la_methode_publiee_est_celle_du_contrat(self):
        self.assertEqual(self.resultat['ombrage']['methode'],
                         CONTRAT['exemple']['ombrage']['methode'])

    def test_le_tsrf_du_pan_reprend_son_acces_solaire(self):
        pan_a = self.resultat['ombrage']['par_pan'][0]
        self.assertEqual(pan_a['acces_solaire_moyen_pct'], 96.5)
        self.assertAlmostEqual(pan_a['tsrf'], pan_a['tof'] * 0.965, places=4)


class SansClientNiAccesTest(SimpleTestCase):
    """Sans PVGIS, la chaîne publie des ``null`` motivés — jamais un 1,0."""

    def setUp(self):
        self.resultat = simuler(avec_client=False)

    def test_les_colonnes_restent_nulles(self):
        for ligne in self.resultat['production']['par_pan']:
            self.assertIsNone(ligne['tof'], ligne['pan'])
            self.assertIsNone(ligne['tsrf'], ligne['pan'])
            self.assertIsNone(ligne['source'], ligne['pan'])

    def test_chaque_pan_porte_son_motif(self):
        for ligne in self.resultat['ombrage']['par_pan']:
            self.assertEqual(ligne['motif_omission'],
                             orientation.MOTIF_SANS_CLIENT)

    def test_la_methode_n_est_pas_annoncee_sans_mesure(self):
        # ``exemple_vide`` du contrat : ``methode`` vaut ``null`` tant que
        # rien n'a été mesuré.
        self.assertIsNone(self.resultat['ombrage']['methode'])
        self.assertIsNone(CONTRAT['exemple_vide']['ombrage']['methode'])

    def test_un_seul_appel_pvgis_pour_tout_le_site(self):
        transport = TransportEnregistre()
        contexte = {
            'site': dict(SITE),
            'meteo': {'heure': {'base': 'utc'}},
            'plans': plans(),
            'reglages_simulation': {
                'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
                'fenetre_annees': {'valeur': '2020-2020',
                                   'source': 'societe'}},
            CLE_SORTIES_PAR_PAN: {'A': serie_de(H_OPTIMALE),
                                  'B': serie_de(H_OPTIMALE)},
            CLE_CLIENT_PVGIS: client(transport),
        }
        appliquer_chaine(serie_de(H_OPTIMALE), contexte, {})
        self.assertEqual(len(transport.appels), 1, transport.appels)
