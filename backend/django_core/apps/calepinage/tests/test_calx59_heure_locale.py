"""CALX59 — la série météo alignée sur l'heure LÉGALE du site.

`services/autoconsommation.py:168` et `services/batterie.py:239` croisent index
à index une courbe de charge SAISIE en heure locale avec une série météo qui ne
l'est pas : un cran d'écart déplace toute l'autoconsommation d'un créneau, et
rien ne le montre — les deux courbes ont la même forme. `services/site.py:442`
savait déjà calculer le décalage et n'était appelé par aucune de ces chaînes.

Le décalage n'est JAMAIS une constante : il est lu dans `zoneinfo` à la DATE de
chaque point, si bien que l'heure d'été et le retour marocain à UTC+0 pendant
le Ramadan sont portés par la base de fuseaux (tzdata 2026.4, épinglée dans
`requirements.txt`) — jamais par un chiffre écrit dans le module.

Les valeurs viennent de la réponse PVGIS enregistrée
`tests/fixtures_pvgis/seriescalc_casablanca_sud.json` (appel SANS `localtime`,
donc indexée en UTC — c'est ce que son `_provenance` montre dans l'URL
committée). Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx59_heure_locale
"""
from __future__ import annotations

import collections
import datetime
import json
import pathlib
import unittest
import zoneinfo

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    BLOCS_HORAIRES_OMIS, CLE_CROISEMENT_HORAIRE, MOTIF_BASE_HORAIRE_INCONNUE,
    MOTIF_FUSEAU_ABSENT, appliquer_chaine,
)
from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import (
    BASE_HEURE_LOCALE_LEGALE, BASE_HEURE_LOCALE_STANDARD, BASE_HEURE_UTC,
    ClientPvgis, _Cache,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
FUSEAU = 'Africa/Casablanca'
POSTES_ESSAI = [{'poste': 'shading', 'pct': 3.5, 'source': 'mesure'}]


class TransportEnregistre:
    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def points_utc():
    """Les points de la réponse RÉELLE, indexés en UTC (aucun `localtime`)."""
    charge = json.loads(
        (FIXTURES / 'seriescalc_casablanca_sud.json').read_text(
            encoding='utf-8'))
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    return client.serie_horaire(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        politique=politique_de_pertes(POSTES_ESSAI),
        annee_debut=2020, annee_fin=2020)['points']


def serie_de(points):
    return {'pas_minutes': 60, 'colonne_energie': 'p_w',
            'points': [dict(point) for point in points]}


def contexte_de(base, *, fuseau=FUSEAU):
    site = {'lat': 33.5, 'lon': -7.6}
    if fuseau:
        site['fuseau'] = fuseau
    return {'site': site, 'meteo': {'heure': {'base': base}}}


def heure_du_maximum(points):
    """``{(mois, jour): heure du maximum de gi_w_m2}`` — un jour, un pic."""
    par_jour = collections.defaultdict(list)
    for point in points:
        irradiance = point.get('gi_w_m2')
        if irradiance is not None:
            par_jour[(point['mois'], point['jour'])].append(
                (irradiance, point['heure']))
    return {jour: max(valeurs)[1] for jour, valeurs in par_jour.items()}


def decalage_reel(mois, jour):
    """Le décalage UTC→Casablanca à cette date, lu dans la base de fuseaux."""
    moment = datetime.datetime(2020, mois, jour, 12)
    return int(moment.replace(
        tzinfo=zoneinfo.ZoneInfo(FUSEAU)).utcoffset().total_seconds() // 60)


class MidiTombeAMidiTest(unittest.TestCase):
    """Le pic quotidien passe de l'heure UTC à l'heure LÉGALE du site."""

    def setUp(self):
        self.points = points_utc()
        self.avant = heure_du_maximum(self.points)
        serie, _ = appliquer_chaine(serie_de(self.points),
                                    contexte_de(BASE_HEURE_UTC))
        self.apres = heure_du_maximum(serie['points'])

    def test_le_15_juillet_passe_de_13h_utc_a_14h_locales(self):
        self.assertEqual(self.avant[(7, 15)], 13)
        self.assertEqual(self.apres[(7, 15)], 14)

    def test_les_jours_de_beau_temps_passent_de_11_13_utc_a_12_14_locales(self):
        vus = 0
        for jour, heure_avant in self.avant.items():
            if heure_avant not in (11, 12, 13):
                # Un jour dont le pic n'est PAS autour du midi solaire est un
                # jour couvert : la propriété porte sur l'INDEX, pas la météo.
                continue
            vus += 1
            self.assertIn(
                self.apres[jour], (12, 13, 14),
                f'{jour} : pic à {heure_avant} h UTC → {self.apres[jour]} h '
                'locales, hors du créneau de midi.')
        self.assertGreaterEqual(vus, 10)

    def test_chaque_jour_est_decale_du_decalage_lu_dans_la_base(self):
        for (mois, jour), heure_avant in self.avant.items():
            attendu = (heure_avant + decalage_reel(mois, jour) // 60) % 24
            self.assertEqual(self.apres[(mois, jour)], attendu,
                             f'{mois}/{jour} : décalage inattendu.')


class RamadanTest(unittest.TestCase):
    """Le Maroc repasse à UTC+0 pendant le Ramadan : une heure de MOINS."""

    def test_une_date_de_ramadan_decale_d_une_heure_de_moins_qu_en_juillet(self):
        # Ramadan 2020 : du 24 avril au 23 mai — le 15 mai tombe dedans.
        ramadan = decalage_reel(5, 15)
        juillet = decalage_reel(7, 15)
        self.assertEqual(juillet - ramadan, 60)

        points = points_utc()
        serie, _ = appliquer_chaine(serie_de(points),
                                    contexte_de(BASE_HEURE_UTC))
        avant = heure_du_maximum(points)
        apres = heure_du_maximum(serie['points'])
        self.assertEqual(apres[(5, 15)] - avant[(5, 15)], ramadan // 60)
        self.assertEqual(apres[(7, 15)] - avant[(7, 15)], juillet // 60)

    def test_les_deux_decalages_sont_publies_sur_la_fenetre(self):
        contexte = contexte_de(BASE_HEURE_UTC)
        appliquer_chaine(serie_de(points_utc()), contexte)
        self.assertEqual(contexte['meteo']['heure']['decalage_minutes'],
                         [0, 60],
                         'Un fuseau qui change au cours de la fenêtre publie '
                         'TOUS ses décalages, pas le premier.')


class BaseDeclareeTest(unittest.TestCase):
    """Une série déjà décalée ne se décale pas deux fois."""

    def test_locale_standard_n_applique_que_la_part_saisonniere(self):
        points = points_utc()
        serie, _ = appliquer_chaine(
            serie_de(points), contexte_de(BASE_HEURE_LOCALE_STANDARD))
        avant = heure_du_maximum(points)
        apres = heure_du_maximum(serie['points'])
        # Hors Ramadan, la part saisonnière marocaine est nulle : PVGIS a
        # déjà appliqué l'écart standard sous `localtime=1`.
        self.assertEqual(apres[(7, 15)], avant[(7, 15)])
        # Pendant le Ramadan, la base de fuseaux décrit un décalage
        # saisonnier NÉGATIF : une heure de moins.
        self.assertEqual(apres[(5, 15)], avant[(5, 15)] - 1)

    def test_une_base_non_declaree_ne_decale_rien_et_le_dit(self):
        contexte = contexte_de(None)
        serie, _ = appliquer_chaine(serie_de(points_utc()), contexte)
        self.assertEqual(contexte['meteo']['heure']['motif'],
                         MOTIF_BASE_HORAIRE_INCONNUE)
        self.assertFalse(contexte[CLE_CROISEMENT_HORAIRE]['possible'])
        self.assertEqual(contexte[CLE_CROISEMENT_HORAIRE]['champ'],
                         'meteo.heure.base')

    def test_la_base_publiee_apres_re_indexation_est_l_heure_legale(self):
        contexte = contexte_de(BASE_HEURE_UTC)
        appliquer_chaine(serie_de(points_utc()), contexte)
        self.assertEqual(contexte['meteo']['heure']['base'],
                         BASE_HEURE_LOCALE_LEGALE)
        self.assertEqual(contexte['meteo']['heure']['fuseau_site'], FUSEAU)
        self.assertEqual(contexte['meteo']['heure']['motif'], '')
        self.assertTrue(contexte[CLE_CROISEMENT_HORAIRE]['possible'])
        self.assertEqual(contexte[CLE_CROISEMENT_HORAIRE]['blocs_omis'], [])


class SansFuseauTest(unittest.TestCase):
    """D-CALX 15 — sans fuseau saisi, rien n'est décalé EN SILENCE."""

    def setUp(self):
        self.points = points_utc()
        self.contexte = contexte_de(BASE_HEURE_UTC, fuseau=None)
        self.serie, _ = appliquer_chaine(serie_de(self.points), self.contexte)

    def test_la_serie_reste_indexee_telle_quelle(self):
        self.assertEqual(heure_du_maximum(self.serie['points']),
                         heure_du_maximum(self.points))

    def test_les_blocs_horaires_sont_omis_en_nommant_le_champ(self):
        verdict = self.contexte[CLE_CROISEMENT_HORAIRE]
        self.assertFalse(verdict['possible'])
        self.assertEqual(verdict['motif'], MOTIF_FUSEAU_ABSENT)
        self.assertEqual(verdict['champ'], 'site.fuseau')
        self.assertEqual(verdict['blocs_omis'], list(BLOCS_HORAIRES_OMIS))
        for bloc in ('autoconsommation', 'batterie', 'hors_reseau'):
            self.assertIn(bloc, verdict['blocs_omis'])

    def test_le_bloc_heure_publie_le_motif(self):
        self.assertEqual(self.contexte['meteo']['heure']['motif'],
                         MOTIF_FUSEAU_ABSENT)
        self.assertIsNone(self.contexte['meteo']['heure']['fuseau_site'])
        self.assertEqual(self.contexte['meteo']['heure']['decalage_minutes'],
                         [])

    def test_la_simulation_tourne_quand_meme(self):
        _, cascade = appliquer_chaine(serie_de(self.points), self.contexte)
        self.assertTrue(cascade['etapes'],
                        'La production ne dépend pas du fuseau : seule la '
                        'lecture horaire de la charge en dépend.')


class ReetiquetageSeulTest(unittest.TestCase):
    """Ré-indexer change l'ÉTIQUETTE d'une heure, jamais sa mesure."""

    def test_aucune_valeur_mesuree_n_est_touchee(self):
        points = points_utc()
        serie, _ = appliquer_chaine(serie_de(points),
                                    contexte_de(BASE_HEURE_UTC))
        avant = sorted(round(p['gi_w_m2'], 6) for p in points
                       if p['gi_w_m2'] is not None)
        apres = sorted(round(p['gi_w_m2'], 6) for p in serie['points']
                       if p['gi_w_m2'] is not None)
        self.assertEqual(avant, apres)

    def test_l_energie_de_la_serie_est_inchangee(self):
        points = points_utc()
        depart = serie_de(points)
        serie, _ = appliquer_chaine(depart, contexte_de(BASE_HEURE_UTC))
        self.assertAlmostEqual(etapes.energie_kwh(serie),
                               etapes.energie_kwh(depart), places=6)

    def test_la_serie_recue_n_est_pas_modifiee_sur_place(self):
        depart = serie_de(points_utc())
        temoin = [dict(point) for point in depart['points']]
        appliquer_chaine(depart, contexte_de(BASE_HEURE_UTC))
        self.assertEqual(depart['points'], temoin)


if __name__ == '__main__':
    unittest.main()
