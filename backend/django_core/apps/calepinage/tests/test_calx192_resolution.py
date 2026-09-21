"""CALX192 — dire la vérité sur la résolution : PVGIS est HORAIRE.

`services/pvgis_serie.py:347-358` lit une ligne par heure et
`services/production.py:110` compte « 1 point = 1 heure ⇒ W = Wh » ;
`services/consommation.py:447-461` ramène de son côté toute courbe de charge
importée au pas horaire, quel que soit son pas d'origine. Personne ne DISAIT
rien de tout cela dans le résultat.

HelioScope assume une simulation horaire sur 8 760 pas — ce qui lui interdit de
modéliser un dépassement de puissance onduleur de moins d'une heure
(https://help-center.helioscope.com/hc/en-us/articles/8536640508307-Inverter-Focus-Nominal-and-Apparent-Power) ;
PVsyst n'autorise un pas infra-horaire que si les données météo le permettent
(https://www.pvsyst.com/help/project-design/simulation/index.html). Les nôtres
ne le permettent pas : la météo reste horaire, en ESCALIER, jamais lissée.

Aucune base, aucun réseau : les points viennent de la réponse enregistrée
`tests/fixtures_pvgis/seriescalc_casablanca_sud.json`.

Run :
    python manage.py test apps.calepinage.tests.test_calx192_resolution
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.chaine_pertes import (
    CLE_CHARGE, CLE_METEO_AU_PAS, MOTIF_RESOLUTION_DIVERGENTE,
    PAS_METEO_ATTENDU_MINUTES, appliquer_chaine,
)
from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
POSTES_ESSAI = [{'poste': 'shading', 'pct': 3.5, 'source': 'mesure'}]


class TransportEnregistre:
    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def points_reels():
    charge = json.loads(
        (FIXTURES / 'seriescalc_casablanca_sud.json').read_text(
            encoding='utf-8'))
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    return client.serie_horaire(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        politique=politique_de_pertes(POSTES_ESSAI),
        annee_debut=2020, annee_fin=2020)['points']


POINTS = points_reels()


def serie_meteo():
    return {'pas_minutes': 60, 'colonne_energie': 'p_w',
            'points': [dict(point) for point in POINTS]}


def charge_au_quart_d_heure():
    """Une courbe de charge d'ESSAI au pas de 15 min — 96 pas d'une journée."""
    return {'pas_minutes': 15,
            'points': [{'charge_kwh': 0.25} for _ in range(96)]}


def simuler(*, charge=None, resolution=None):
    reglages = {'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
                'fenetre_annees': {'valeur': '2020-2020',
                                   'source': 'societe'}}
    if resolution is not None:
        reglages['resolution_minutes'] = {'valeur': resolution,
                                          'source': 'societe'}
    contexte = {
        'site': {'lat': 33.5, 'lon': -7.6},
        'plans': [],
        'reglages_simulation': reglages,
    }
    if charge is not None:
        contexte[CLE_CHARGE] = charge
    resultat = {}
    serie, _ = appliquer_chaine(serie_meteo(), contexte, resultat=resultat)
    return resultat, contexte, serie


class DeuxPasPubliesSeparementTest(unittest.TestCase):
    """Le pas de la météo et celui de la charge ne se mélangent pas."""

    def test_la_meteo_reste_horaire_meme_avec_une_charge_au_quart_d_heure(self):
        resultat, _, _ = simuler(charge=charge_au_quart_d_heure())
        self.assertEqual(resultat['meteo']['pas_minutes'],
                         PAS_METEO_ATTENDU_MINUTES)

    def test_les_deux_pas_sont_publies_cote_a_cote(self):
        resultat, _, _ = simuler(charge=charge_au_quart_d_heure())
        meteo = resultat['meteo']
        self.assertEqual(meteo['pas_minutes'], 60)
        self.assertEqual(meteo['pas_charge_minutes'], 15)
        self.assertNotEqual(meteo['pas_minutes'], meteo['pas_charge_minutes'])

    def test_sans_courbe_de_charge_le_pas_de_charge_reste_nul(self):
        resultat, _, _ = simuler()
        self.assertIsNone(resultat['meteo']['pas_charge_minutes'])

    def test_le_pas_publie_est_MESURE_et_non_recopie_du_declare(self):
        # La série déclare 60 min ; on la ment à 15 pour vérifier que c'est
        # bien l'horodatage qui fait foi.
        contexte = {'site': {}, 'plans': [],
                    'reglages_simulation': {
                        'mode_meteo': {'valeur': 'tmy', 'source': 'societe'}}}
        serie = dict(serie_meteo(), pas_minutes=15)
        resultat = {}
        appliquer_chaine(serie, contexte, resultat=resultat)
        self.assertEqual(resultat['meteo']['pas_minutes'], 60)

    def test_le_reglage_divergent_est_dit_et_le_mesure_fait_foi(self):
        resultat, _, _ = simuler(resolution=15)
        self.assertEqual(resultat['meteo']['resolution_minutes'], 15)
        self.assertEqual(resultat['meteo']['pas_minutes'], 60)
        self.assertIn(
            MOTIF_RESOLUTION_DIVERGENTE.format(reglage=15, mesure=60),
            resultat['avertissements'])


class AucuneInterpolationTest(unittest.TestCase):
    """L'irradiance n'est JAMAIS lissée entre deux heures."""

    def test_la_serie_meteo_n_est_pas_rechantillonnee(self):
        avant = [point['gi_w_m2'] for point in POINTS]
        _, _, serie = simuler(charge=charge_au_quart_d_heure())
        self.assertEqual([point['gi_w_m2'] for point in serie['points']],
                         avant,
                         'Un point ajouté entre deux heures serait une '
                         'irradiance que personne n’a mesurée.')

    def test_quatre_pas_d_une_meme_heure_portent_la_meme_valeur(self):
        _, contexte, _ = simuler(charge=charge_au_quart_d_heure())
        escalier = contexte[CLE_METEO_AU_PAS](15)
        self.assertTrue(escalier['escalier'])
        self.assertEqual(escalier['pas_minutes'], 15)
        self.assertEqual(len(escalier['points']), len(POINTS) * 4)
        for depart in range(0, 4 * 24, 4):
            quatre = escalier['points'][depart:depart + 4]
            valeurs = {point['gi_w_m2'] for point in quatre}
            self.assertEqual(len(valeurs), 1,
                             f'pas {depart} : la valeur a bougé DANS l’heure.')
            self.assertEqual({point['heure'] for point in quatre},
                             {quatre[0]['heure']})

    def test_l_escalier_refuse_un_pas_qui_ne_divise_pas_l_heure(self):
        _, contexte, _ = simuler()
        rendu = contexte[CLE_METEO_AU_PAS](7)
        self.assertFalse(rendu['escalier'])
        self.assertEqual(rendu['pas_minutes'], 60)
        self.assertTrue(rendu['motif'].strip())

    def test_un_pas_plus_grossier_n_est_pas_agrege_non_plus(self):
        _, contexte, _ = simuler()
        rendu = contexte[CLE_METEO_AU_PAS](120)
        self.assertFalse(rendu['escalier'])
        self.assertEqual(len(rendu['points']), len(POINTS))


class NoteDeResolutionTest(unittest.TestCase):
    """La chose est DITE, en français, dans les avertissements."""

    def test_la_note_figure_dans_les_avertissements(self):
        resultat, _, _ = simuler(charge=charge_au_quart_d_heure())
        note = resultat['meteo']['note_resolution']
        self.assertIn(note, resultat['avertissements'])

    def test_la_note_dit_l_escalier_quand_la_charge_est_plus_fine(self):
        resultat, _, _ = simuler(charge=charge_au_quart_d_heure())
        note = resultat['meteo']['note_resolution']
        self.assertIn('ESCALIER', note)
        self.assertIn('15 min', note)
        self.assertIn('60 min', note)

    def test_la_note_dit_deja_l_absence_d_interpolation_sans_charge(self):
        resultat, _, _ = simuler()
        note = resultat['meteo']['note_resolution']
        self.assertIn('interpolation', note)
        self.assertFalse(resultat['meteo']['interpolation'])

    def test_la_note_n_est_pas_dupliquee(self):
        resultat, _, _ = simuler()
        note = resultat['meteo']['note_resolution']
        self.assertEqual(resultat['avertissements'].count(note), 1)


if __name__ == '__main__':
    unittest.main()
