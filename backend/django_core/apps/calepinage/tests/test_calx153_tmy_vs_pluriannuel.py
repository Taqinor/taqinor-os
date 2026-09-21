"""CALX153 — année météo TYPE ou fenêtre PLURIANNUELLE : un CHOIX, jamais un défaut.

`services/pvgis_serie.py::ClientPvgis.tmy` existait, complet, et n'était
appelé par aucune production : la simulation ne connaissait que la fenêtre
d'années. Le mode est désormais un réglage société (CALX145) SANS valeur par
défaut — absent, la simulation est REFUSÉE en nommant le réglage — et il tire
ses conséquences : une année météo type est l'assemblage du mois le plus
représentatif de jusqu'à trente années (HelioScope,
https://help-center.helioscope.com/hc/en-us/articles/8316899662099-TMY-Weather-File-Primer),
donc UNE année par construction, sur laquelle aucune variabilité
interannuelle ne se MESURE.

Aucune base de données, aucun réseau : les réglages sont des dicts, la réponse
`tmy` est la fixture enregistrée `tests/fixtures_pvgis/tmy_casablanca.json`.

Run :
    python manage.py test apps.calepinage.tests.test_calx153_tmy_vs_pluriannuel
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.chaine_pertes import (
    CLE_REGLAGE_FENETRE_ANNEES, CLE_REGLAGE_MODE_METEO, MODES_METEO,
    PLAFOND_FENETRE_ANNEES, MeteoIndecise, appliquer_chaine, decision_meteo,
)
from apps.calepinage.services.incertitude import ORIGINE_MESUREE
from apps.calepinage.services.p50p90 import bankable
from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    """Rejoue une réponse enregistrée — le réseau n'est jamais touché."""

    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def reglages(**valeurs):
    """Des réglages société SOURCÉS, à la forme de CALX145."""
    return {'reglages_simulation': {
        cle: {'valeur': valeur, 'source': 'societe', 'reference': 'essai'}
        for cle, valeur in valeurs.items()}}


class ModeAbsentTest(unittest.TestCase):
    """Sans mode saisi, la simulation est REFUSÉE — et le réglage est nommé."""

    def test_le_refus_nomme_le_reglage_a_saisir(self):
        with self.assertRaises(MeteoIndecise) as capture:
            decision_meteo({})
        self.assertEqual(capture.exception.champ, CLE_REGLAGE_MODE_METEO)
        self.assertIn(CLE_REGLAGE_MODE_METEO, capture.exception.motif)
        for mode in MODES_METEO:
            self.assertIn(mode, capture.exception.motif)

    def test_un_reglage_sans_source_ne_vaut_pas_saisi(self):
        contexte = {'reglages_simulation': {'mode_meteo': {'valeur': 'tmy'}}}
        with self.assertRaises(MeteoIndecise) as capture:
            decision_meteo(contexte)
        self.assertEqual(capture.exception.champ, CLE_REGLAGE_MODE_METEO)

    def test_un_mode_inconnu_est_refuse_en_listant_les_deux_modes(self):
        with self.assertRaises(MeteoIndecise) as capture:
            decision_meteo(reglages(mode_meteo='annee_moyenne'))
        self.assertEqual(capture.exception.champ, CLE_REGLAGE_MODE_METEO)
        for mode in MODES_METEO:
            self.assertIn(mode, capture.exception.motif)


class ModeTmyTest(unittest.TestCase):
    """En `tmy`, aucune fenêtre, aucune année observée, aucun σ mesuré."""

    def setUp(self):
        self.decision = decision_meteo(reglages(mode_meteo='tmy'))

    def test_le_mode_est_publie_avec_sa_provenance(self):
        self.assertEqual(self.decision['mode'], 'tmy')
        self.assertEqual(self.decision['source'], 'societe')

    def test_aucune_fenetre_d_annees_n_est_appliquee(self):
        self.assertIsNone(self.decision['fenetre_annees'])
        self.assertTrue(self.decision['motif_fenetre'].strip())

    def test_une_fenetre_saisie_ne_reveille_pas_le_mode_pluriannuel(self):
        decision = decision_meteo(
            reglages(mode_meteo='tmy', fenetre_annees='2015-2024'))
        self.assertIsNone(decision['fenetre_annees'])

    def test_la_reponse_tmy_ne_declare_aucune_annee_observee(self):
        client = ClientPvgis(TransportEnregistre(charger('tmy_casablanca.json')),
                             cache=_Cache(), dormir=lambda _s: None)
        rendu = client.tmy(lat=33.5, lon=-7.6)
        self.assertEqual(rendu['mode'], 'tmy')
        self.assertEqual(
            rendu['annees'], [],
            "Une année météo TYPE n'est l'observation d'aucune année réelle : "
            'elle ne peut pas alimenter une variabilité interannuelle.')

    def test_sigma_meteo_n_est_jamais_mesure_en_mode_tmy(self):
        client = ClientPvgis(TransportEnregistre(charger('tmy_casablanca.json')),
                             cache=_Cache(), dormir=lambda _s: None)
        rendu = client.tmy(lat=33.5, lon=-7.6)
        # Les totaux annuels que la cascade pourrait publier en mode `tmy` :
        # il n'y en a aucun, donc σ ne peut pas se dire « mesuré ».
        totaux = {annee: 1000.0 for annee in rendu['annees']}
        quantiles = bankable(1000.0, totaux_par_annee=totaux, kwc=1.0)
        self.assertNotEqual(quantiles['sigma_source'], ORIGINE_MESUREE)


class ModePluriannuelTest(unittest.TestCase):
    """En `pluriannuel`, la fenêtre est SAISIE, sourcée, et bornée."""

    def test_la_fenetre_saisie_est_reprise_telle_quelle(self):
        decision = decision_meteo(
            reglages(mode_meteo='pluriannuel', fenetre_annees='2018-2024'))
        self.assertEqual(decision['fenetre_annees'], (2018, 2024))
        self.assertEqual(decision['fenetre_source'], 'societe')
        self.assertEqual(decision['motif_fenetre'], '')

    def test_une_fenetre_en_liste_est_acceptee(self):
        decision = decision_meteo(
            reglages(mode_meteo='pluriannuel', fenetre_annees=[2020, 2022]))
        self.assertEqual(decision['fenetre_annees'], (2020, 2022))

    def test_la_fenetre_absente_refuse_la_simulation_en_la_nommant(self):
        with self.assertRaises(MeteoIndecise) as capture:
            decision_meteo(reglages(mode_meteo='pluriannuel'))
        self.assertEqual(capture.exception.champ, CLE_REGLAGE_FENETRE_ANNEES)

    def test_une_fenetre_illisible_est_refusee_en_la_nommant(self):
        with self.assertRaises(MeteoIndecise) as capture:
            decision_meteo(
                reglages(mode_meteo='pluriannuel', fenetre_annees='depuis 2015'))
        self.assertEqual(capture.exception.champ, CLE_REGLAGE_FENETRE_ANNEES)

    def test_le_plafond_garde_les_annees_les_plus_recentes_et_le_dit(self):
        decision = decision_meteo(
            reglages(mode_meteo='pluriannuel', fenetre_annees='2005-2024'))
        debut, fin = decision['fenetre_annees']
        self.assertEqual(fin, 2024)
        self.assertEqual(fin - debut + 1, PLAFOND_FENETRE_ANNEES)
        self.assertTrue(decision['motif_fenetre'].strip(),
                        'Une fenêtre bornée se DIT : sinon la société croit '
                        'simuler vingt ans.')
        self.assertEqual(decision['plafond_annees'], PLAFOND_FENETRE_ANNEES)


class IrradianceHorizontaleRefuseeTest(unittest.TestCase):
    """Le TMY sert du GLOBAL HORIZONTAL : la chaîne refuse d'y démarrer."""

    def test_une_serie_sans_irradiance_de_plan_est_refusee(self):
        client = ClientPvgis(TransportEnregistre(charger('tmy_casablanca.json')),
                             cache=_Cache(), dormir=lambda _s: None)
        rendu = client.tmy(lat=33.5, lon=-7.6)
        serie = {'pas_minutes': 60, 'points': rendu['points']}
        with self.assertRaises(MeteoIndecise) as capture:
            appliquer_chaine(serie, {})
        self.assertIn('gh_w_m2', capture.exception.motif)
        self.assertIn('gi_w_m2', capture.exception.motif)

    def test_le_client_publie_le_meme_motif_avec_sa_reponse(self):
        client = ClientPvgis(TransportEnregistre(charger('tmy_casablanca.json')),
                             cache=_Cache(), dormir=lambda _s: None)
        rendu = client.tmy(lat=33.5, lon=-7.6)
        self.assertIn('gh_w_m2', rendu['motif_irradiance_de_plan'])

    def test_une_serie_de_plan_passe_sans_encombre(self):
        serie = {'pas_minutes': 60,
                 'points': [{'annee': 2020, 'mois': 6, 'jour': 21,
                             'heure': 12, 'gi_w_m2': 800.0, 'p_w': 1000.0}]}
        _, cascade = appliquer_chaine(serie, {})
        self.assertTrue(cascade['etapes'])


if __name__ == '__main__':
    unittest.main()
