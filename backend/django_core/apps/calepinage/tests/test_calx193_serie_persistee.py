"""CALX193 — la série horaire que l'export attend depuis toujours.

`views/export_csv.py:59-62` lit `resultat['serie_horaire']` et le service
derrière refuse proprement quand elle est vide — mais AUCUN code du dépôt
n'écrivait cette clé : l'export « horaire » était structurellement vide.
PVsyst exporte la série au pas de simulation, ce qui permet à un tiers de
refaire le calcul
(https://www.pvsyst.com/help/project-design/simulation/create-a-csv-file-of-hourly-daily-values.html).

Un SEUL écrivain : `services/chaine_pertes.py`. Et la clé n'est PAS recopiée
par `GET resultat/` (CALX70, volume) : elle reste servie par `export-csv`.

Aucune base, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx193_serie_persistee
"""
from __future__ import annotations

import datetime
import json
import pathlib
import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    COLONNES_SERIE_PERSISTEE, JOURS_MAX_SERIE_PERSISTEE,
    PAS_JOURNALIER_MINUTES, appliquer_chaine,
)
from apps.calepinage.services.electrique import BLOCS_SIMULATION
from apps.calepinage.services.export_csv import export_csv
from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache

RACINE = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
CONTRAT = json.loads(
    (RACINE / 'contract_samples' / 'calepinage_serie_horaire.json')
    .read_text(encoding='utf-8'))

POSTES_ESSAI = [{'poste': 'shading', 'pct': 3.5, 'source': 'mesure'}]

#: Les SEPT colonnes historiques que `services/export_csv.py` lit depuis
#: CAL144 — elles ne bougent ni de nom, ni d'unité, ni de nature.
SEPT_HISTORIQUES = ('annee', 'mois', 'jour', 'heure', 'p_w', 'gi_w_m2',
                    't2m_c')


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


def reglages():
    return {'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
            'fenetre_annees': {'valeur': '2020-2020', 'source': 'societe'}}


def simuler(points=None, *, colonne='p_w'):
    serie = {'pas_minutes': 60, 'colonne_energie': colonne,
             'points': [dict(point) for point in (points or POINTS)]}
    contexte = {'site': {'lat': 33.5, 'lon': -7.6}, 'plans': [],
                'reglages_simulation': reglages()}
    resultat = {}
    appliquer_chaine(serie, contexte, resultat=resultat)
    return resultat


def serie_longue(nombre):
    """``nombre`` points horaires consécutifs, à partir du 01/01/2020."""
    depart = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    points = []
    for rang in range(nombre):
        moment = depart + datetime.timedelta(hours=rang)
        points.append({'annee': moment.year, 'mois': moment.month,
                       'jour': moment.day, 'heure': moment.hour,
                       'p_w': 1000.0, 'gi_w_m2': 800.0, 't2m_c': 20.0})
    return points


class BlocEcritTest(unittest.TestCase):
    """La clé est enfin écrite, au format du contrat CALX142."""

    def setUp(self):
        self.bloc = simuler()['serie_horaire']

    def test_les_quatre_cles_du_contrat_sont_la(self):
        modele = CONTRAT['exemple']['serie_horaire']
        for cle in modele:
            self.assertIn(cle, self.bloc, cle)

    def test_les_points_sont_ceux_de_la_serie(self):
        self.assertEqual(len(self.bloc['points']), len(POINTS))
        self.assertFalse(self.bloc['tronquee'])
        self.assertEqual(self.bloc['pas_minutes'], 60)

    def test_chaque_point_porte_les_vingt_colonnes(self):
        for point in self.bloc['points']:
            self.assertEqual(sorted(point),
                             sorted(COLONNES_SERIE_PERSISTEE))

    def test_une_colonne_non_produite_vaut_null_jamais_zero(self):
        point = self.bloc['points'][0]
        for colonne in ('charge_kwh', 'batterie_soc_pct', 'reseau_import_kwh',
                        'reseau_export_kwh', 't_cell_c'):
            self.assertIsNone(point[colonne], colonne)

    def test_colonnes_enumere_ce_qui_porte_vraiment_une_valeur(self):
        for colonne in SEPT_HISTORIQUES:
            self.assertIn(colonne, self.bloc['colonnes'], colonne)
        self.assertNotIn('charge_kwh', self.bloc['colonnes'])
        self.assertEqual(self.bloc['colonnes'],
                         [colonne for colonne in COLONNES_SERIE_PERSISTEE
                          if colonne in self.bloc['colonnes']],
                         "l'ordre du contrat n'est pas respecté.")

    def test_p_w_vaut_bien_mille_fois_p_ac_kw(self):
        points = [dict(point, p_ac_kw=2.5) for point in POINTS[:24]]
        bloc = simuler(points, colonne='p_ac_kw')['serie_horaire']
        for point in bloc['points']:
            self.assertEqual(point['p_w'], 2500.0)
            self.assertEqual(point['p_ac_kw'], 2.5)


class ExportHoraireEnfinRempliTest(unittest.TestCase):
    """L'export horaire produit un fichier non vide aux sept colonnes."""

    def test_le_fichier_porte_les_sept_colonnes_historiques(self):
        resultat = simuler()
        document = {
            'production': resultat['production'],
            'pertes': [], 'version_moteur': 'essai',
            'points': resultat['serie_horaire']['points'],
            'shading12x24': None,
        }
        texte = export_csv(document, quoi='horaire')
        self.assertIn('annee;mois;jour;heure;production_kw;'
                      'irradiance_plan_w_m2;temperature_air_c', texte)
        lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
        self.assertGreater(len(lignes), len(POINTS),
                           'le fichier doit porter ses points, pas seulement '
                           'son en-tête.')


class BorneDeVolumeTest(unittest.TestCase):
    """Au-delà de la borne, la série est AGRÉGÉE — jamais coupée en silence."""

    def setUp(self):
        self.plafond = JOURS_MAX_SERIE_PERSISTEE * 24
        self.bloc = simuler(serie_longue(self.plafond + 1))['serie_horaire']

    def test_la_borne_est_declaree(self):
        self.assertEqual(self.bloc['plafond_points'], self.plafond)

    def test_la_serie_est_marquee_tronquee_avec_sa_raison(self):
        self.assertTrue(self.bloc['tronquee'])
        self.assertTrue(self.bloc['motif_troncature'].strip())
        self.assertIn(str(self.plafond), self.bloc['motif_troncature'])

    def test_elle_est_agregee_au_jour_et_non_coupee(self):
        self.assertEqual(self.bloc['pas_minutes'], PAS_JOURNALIER_MINUTES)
        # 8 785 points horaires couvrent 366 jours + 1 heure = 367 jours.
        self.assertEqual(len(self.bloc['points']), 367)
        for point in self.bloc['points']:
            self.assertIsNone(point['heure'],
                              "un jour n'a pas d'heure : la colonne reste "
                              'nulle plutôt que de désigner une heure au '
                              'hasard.')

    def test_l_agregation_conserve_l_energie(self):
        points = serie_longue(self.plafond + 1)
        horaire = {'pas_minutes': 60, 'colonne_energie': 'p_w',
                   'points': points}
        journaliere = {'pas_minutes': self.bloc['pas_minutes'],
                       'colonne_energie': 'p_w',
                       'points': self.bloc['points']}
        self.assertAlmostEqual(etapes.energie_kwh(journaliere),
                               etapes.energie_kwh(horaire), places=3)

    def test_une_serie_sous_la_borne_n_est_pas_touchee(self):
        bloc = simuler(serie_longue(self.plafond))['serie_horaire']
        self.assertFalse(bloc['tronquee'])
        self.assertEqual(bloc['motif_troncature'], '')
        self.assertEqual(len(bloc['points']), self.plafond)


class UnSeulEcrivainTest(unittest.TestCase):
    """La clé n'est écrite que par la chaîne, et pas servie par `resultat/`."""

    def test_sans_resultat_rien_n_est_ecrit(self):
        contexte = {'reglages_simulation': reglages()}
        serie, _ = appliquer_chaine(
            {'pas_minutes': 60, 'points': list(POINTS)}, contexte)
        self.assertNotIn('serie_horaire', contexte)

    def test_get_resultat_ne_recopie_pas_la_serie(self):
        self.assertNotIn(
            'serie_horaire', BLOCS_SIMULATION,
            'CALX70/D-CALX 14 : la série ne part pas dans `GET resultat/` — '
            'elle reste servie par `export-csv` et le panneau Séries.')


if __name__ == '__main__':
    unittest.main()
