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
        # ACAL744 — ``comparaison_base`` est posée APRÈS la chaîne par
        # ``simuler_calepinage`` (meteo_comparee.comparer_bases), pas par elle.
        attendues = set(CONTRAT['exemple']['meteo']) - {'comparaison_base'}
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


if __name__ == '__main__':
    unittest.main()
