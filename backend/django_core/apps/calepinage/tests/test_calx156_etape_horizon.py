# -*- coding: utf-8 -*-
"""CALX156 — l'étape « horizon » masque le direct, et ne le masque qu'une fois.

CE QUI EST PROUVÉ ICI
---------------------
1. **Un horizon plat à 0° ne coûte RIEN** : 0,0 % exactement, sur une réponse
   PVGIS réelle. Un masquage qui grignoterait quelques watts sur un site
   parfaitement dégagé serait une perte inventée.
2. **Un mur de 90° tout autour coupe TOUT le direct** — propriété, pas
   valeur : la perte de direct égale exactement la part directe de
   l'irradiation de la fixture (66,8 % de l'irradiation de plan).
3. **Le double masquage est impossible** : masque déjà retranché par PVGIS
   (modèle de terrain OU notre propre profil envoyé en ``userhorizon``,
   CALX151) ⇒ étape omise, motif publié, série INCHANGÉE.
4. **Rien n'est supposé** : profil absent, composantes absentes (CALX152),
   site sans coordonnées, base de temps non déclarée ⇒ étape omise en
   NOMMANT le champ qui manque.
5. **L'atténuation du diffus et du réfléchi se désactive** par le réglage
   société sourcé ``simulation.attenuation_horizon``.

Aucune base de données, aucun réseau : ``SimpleTestCase`` et la réponse PVGIS
v5_3 RÉELLE enregistrée le 21/09/2026.

Run :
    python manage.py test apps.calepinage.tests.test_calx156_etape_horizon
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import LIBELLES, appliquer_chaine
from apps.calepinage.services.etapes import horizon as etape_horizon
from apps.calepinage.services.pvgis_serie import (
    MOTIF_COMPOSANTES_ABSENTES, ClientPvgis, _Cache)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
AVEC_COMPOSANTES = 'seriescalc_casablanca_sud_composantes.json'
SANS_COMPOSANTES = 'seriescalc_casablanca_sud_irradiance.json'

#: Le site de la fixture, et le seul que ces essais emploient.
SITE = {'lat': 33.5, 'lon': -7.6, 'altitude_m': 139.0}

#: La série de la fixture est horodatée en heure locale standard ; les
#: essais la déclarent en UTC, ce que la position du soleil vérifiée par
#: CALX152 confirme sur cette réponse (écart max 0,4335° sur H_sun).
METEO_UTC = {'heure': {'base': 'utc', 'fuseau_site': 'UTC',
                       'decalage_minutes': 0},
             'horizon': {'origine': 'aucun'}}


class TransportEnregistre:
    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def serie_de(fixture, *, composantes):
    """La série horaire CALX142 d'une réponse PVGIS enregistrée."""
    charge = json.loads((FIXTURES / fixture).read_text(encoding='utf-8'))
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    resultat = client.serie_irradiance(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        annee_debut=2020, annee_fin=2020, composantes=composantes,
        obtenue_le='2026-09-21T09:00:00Z')
    return resultat['serie_horaire']


def profil_plat(hauteur_deg, *, directions=24, source='pvgis'):
    """Un profil d'horizon à hauteur CONSTANTE, sur tout le tour."""
    pas = 360.0 / directions
    return {
        'source': source,
        'hauteur_max_deg': hauteur_deg,
        'points': [{'azimut_face_deg': rang * pas,
                    'hauteur_deg': hauteur_deg}
                   for rang in range(directions)],
    }


def contexte_de(profil, **extra):
    contexte = {'site': dict(SITE), 'meteo': json.loads(json.dumps(METEO_UTC))}
    if profil is not None:
        contexte['horizon'] = profil
    contexte.update(extra)
    return contexte


def somme(serie, colonne):
    return sum(point[colonne] or 0.0 for point in serie['points'])


class HorizonPlatTest(SimpleTestCase):
    """Un site dégagé ne perd rien — 0,0 %, pas « presque 0 »."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_un_horizon_plat_a_zero_ne_coute_rien(self):
        rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(0.0)))
        self.assertEqual(etape['motif_omission'], '')
        for colonne in ('gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2', 'gi_w_m2'):
            self.assertAlmostEqual(somme(rendue, colonne),
                                   somme(self.serie, colonne), places=6,
                                   msg=colonne)
        self.assertEqual(etape['entree']['heures_masquees'], 0)
        self.assertEqual(etape['entree']['fraction_ciel_visible'], 1.0)
        self.assertEqual(etape['entree']['facteur_reflechi'], 1.0)

    def test_la_serie_d_entree_n_est_jamais_modifiee(self):
        empreinte = json.dumps(self.serie, sort_keys=True)
        etape_horizon.appliquer(self.serie, contexte_de(profil_plat(30.0)))
        self.assertEqual(json.dumps(self.serie, sort_keys=True), empreinte,
                         'une étape est PURE : elle copie, elle ne mute pas.')

    def test_le_libelle_est_celui_que_l_ordre_declare(self):
        _rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(0.0)))
        self.assertEqual(etape['libelle'], LIBELLES['horizon'])


class MurDeQuatreVingtDixTest(SimpleTestCase):
    """Un mur tout autour : le direct disparaît, exactement lui."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_toutes_les_heures_perdent_leur_direct(self):
        rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(90.0)))
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(somme(rendue, 'gb_i_w_m2'), 0.0)
        ensoleillees = sum(1 for point in self.serie['points']
                           if point['gb_i_w_m2'] > 0.0)
        self.assertEqual(etape['entree']['heures_masquees'], ensoleillees)

    def test_la_perte_de_direct_egale_la_part_directe_de_la_fixture(self):
        rendue, _etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(90.0)))
        directe = somme(self.serie, 'gb_i_w_m2')
        globale = somme(self.serie, 'gi_w_m2')
        perte = directe - somme(rendue, 'gb_i_w_m2')
        self.assertAlmostEqual(perte, directe, places=9)
        self.assertGreater(perte / globale, 0.6,
                           'la fixture porte bien une part directe majeure.')

    def test_un_mur_plus_haut_ne_perd_jamais_moins(self):
        restes = []
        for hauteur in (0.0, 5.0, 15.0, 30.0, 60.0, 90.0):
            rendue, _etape = etape_horizon.appliquer(
                self.serie, contexte_de(profil_plat(hauteur)))
            restes.append(somme(rendue, 'gi_w_m2'))
        self.assertEqual(restes, sorted(restes, reverse=True),
                         'un horizon plus haut ne peut pas laisser passer '
                         'plus de lumière.')


class DoubleMasquageTest(SimpleTestCase):
    """Le masque ne se retranche jamais deux fois."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def _omise_pour(self, origine):
        contexte = contexte_de(profil_plat(40.0))
        contexte['meteo']['horizon']['origine'] = origine
        rendue, etape = etape_horizon.appliquer(self.serie, contexte)
        self.assertIs(rendue, self.serie,
                      'une étape omise laisse la série INCHANGÉE.')
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['source'])
        return etape

    def test_le_modele_de_terrain_de_pvgis_omet_l_etape(self):
        etape = self._omise_pour('dem_pvgis')
        self.assertIn('modèle de terrain', etape['motif_omission'])

    def test_notre_profil_envoye_en_userhorizon_omet_l_etape(self):
        for origine in ('profil_mesure', 'saisie'):
            etape = self._omise_pour(origine)
            self.assertIn('userhorizon', etape['motif_omission'], origine)
            self.assertIn('21/09/2026', etape['motif_omission'], origine)

    def test_sans_masque_amont_l_etape_s_applique(self):
        _rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(40.0)))
        self.assertEqual(etape['motif_omission'], '')


class EntreeManquanteTest(SimpleTestCase):
    """Chaque absence est NOMMÉE — jamais un horizon plat de repli."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_sans_profil_l_etape_nomme_le_champ(self):
        _rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(None))
        self.assertIn('horizon.points', etape['motif_omission'])
        self.assertIn('dégagé', etape['motif_omission'])

    def test_le_profil_se_lit_aussi_dans_le_repere_de_pvgis(self):
        depuis_le_sud = {
            'source': 'pvgis',
            'points': [{'azimut_pvgis_deg': rang * 30.0 - 180.0,
                        'hauteur_deg': 12.0} for rang in range(12)],
        }
        _rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(depuis_le_sud))
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['profil']['directions'], 12)
        self.assertEqual(etape['entree']['profil']['hauteur_max_deg'], 12.0)

    def test_un_profil_trop_court_ne_fait_pas_le_tour(self):
        profil = profil_plat(20.0)
        profil['points'] = profil['points'][:1]
        _rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil))
        self.assertIn('horizon.points', etape['motif_omission'])

    def test_sans_composantes_le_motif_est_celui_de_calx152(self):
        serie = serie_de(SANS_COMPOSANTES, composantes=False)
        _rendue, etape = etape_horizon.appliquer(
            serie, contexte_de(profil_plat(30.0)))
        self.assertEqual(etape['motif_omission'], MOTIF_COMPOSANTES_ABSENTES)

    def test_sans_coordonnees_le_site_est_nomme(self):
        contexte = contexte_de(profil_plat(30.0))
        contexte['site'] = {'lon': -7.6}
        _rendue, etape = etape_horizon.appliquer(self.serie, contexte)
        self.assertIn('site.lat', etape['motif_omission'])

    def test_sans_base_de_temps_le_champ_est_nomme(self):
        contexte = contexte_de(profil_plat(30.0))
        contexte['meteo']['heure'] = {'base': 'locale_standard',
                                      'fuseau_site': None,
                                      'decalage_minutes': []}
        _rendue, etape = etape_horizon.appliquer(self.serie, contexte)
        self.assertIn('meteo.heure.decalage_minutes',
                      etape['motif_omission'])

    def test_un_decalage_unique_suffit(self):
        contexte = contexte_de(profil_plat(0.0))
        contexte['meteo']['heure'] = {'base': 'locale_standard',
                                      'decalage_minutes': [60, 60]}
        _rendue, etape = etape_horizon.appliquer(self.serie, contexte)
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['decalage_minutes'], 60.0)


class AttenuationTest(SimpleTestCase):
    """Le diffus et le réfléchi : conventions citées, ou rien."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_par_defaut_les_deux_conventions_sont_citees(self):
        rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(18.0)))
        self.assertEqual(etape['entree']['attenuation'], 'conventions_citees')
        self.assertIn('PVsyst', etape['reference'])
        self.assertAlmostEqual(etape['entree']['fraction_ciel_visible'],
                               1.0 - 18.0 / 90.0, places=6)
        self.assertAlmostEqual(etape['entree']['facteur_reflechi'],
                               1.0 - 18.0 / 20.0, places=6)
        self.assertLess(somme(rendue, 'gd_i_w_m2'),
                        somme(self.serie, 'gd_i_w_m2'))

    def test_au_dela_de_vingt_degres_le_reflechi_est_nul(self):
        _rendue, etape = etape_horizon.appliquer(
            self.serie, contexte_de(profil_plat(25.0)))
        self.assertEqual(etape['entree']['facteur_reflechi'], 0.0)

    def test_le_reglage_societe_source_la_desactive(self):
        contexte = contexte_de(
            profil_plat(30.0),
            reglages_simulation={'attenuation_horizon': {
                'valeur': 'aucune', 'source': 'societe',
                'reference': 'décision de la société'}})
        rendue, etape = etape_horizon.appliquer(self.serie, contexte)
        self.assertEqual(etape['entree']['attenuation'], 'desactivee')
        self.assertEqual(etape['entree']['attenuation_source'], 'societe')
        self.assertAlmostEqual(somme(rendue, 'gd_i_w_m2'),
                               somme(self.serie, 'gd_i_w_m2'), places=6)
        self.assertLess(somme(rendue, 'gb_i_w_m2'),
                        somme(self.serie, 'gb_i_w_m2'),
                        'le direct reste masqué : c’est de la géométrie.')

    def test_un_reglage_sans_source_ne_s_applique_pas(self):
        contexte = contexte_de(
            profil_plat(30.0),
            reglages_simulation={'attenuation_horizon': {'valeur': 'aucune'}})
        _rendue, etape = etape_horizon.appliquer(self.serie, contexte)
        self.assertEqual(etape['entree']['attenuation'], 'conventions_citees')


class DansLaChaineTest(SimpleTestCase):
    """Vue par l'ordonnanceur : le contrat cascade tient."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def _etape(self, contexte):
        _rendue, cascade = appliquer_chaine(self.serie, contexte)
        return next(e for e in cascade['etapes'] if e['etape'] == 'horizon')

    def test_l_etape_appliquee_porte_les_douze_champs(self):
        etape = self._etape(contexte_de(profil_plat(40.0)))
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['rang'], 1)
        self.assertEqual(etape['libelle'], LIBELLES['horizon'])
        self.assertTrue(etape['source'])
        self.assertFalse(etape['gain'])

    def test_l_exclusivite_de_l_ordonnanceur_prime(self):
        contexte = contexte_de(profil_plat(40.0))
        contexte['meteo']['horizon']['origine'] = 'dem_pvgis'
        etape = self._etape(contexte)
        self.assertIn('PVGIS', etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])

    def test_une_serie_sans_horodatage_ne_fait_pas_tomber_la_chaine(self):
        serie = {'pas_minutes': 60,
                 'points': [{'p_w': 1000.0}, {'p_w': 2000.0}]}
        _rendue, cascade = appliquer_chaine(serie, contexte_de(
            profil_plat(30.0)))
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'horizon')
        self.assertEqual(etape['motif_omission'], MOTIF_COMPOSANTES_ABSENTES)


class ColonneEnergieTest(SimpleTestCase):
    """Quand la série porte déjà une puissance, elle suit le même rapport."""

    def test_la_puissance_suit_l_irradiance_heure_par_heure(self):
        serie = {
            'pas_minutes': 60,
            'points': [
                {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
                 'h_sun_deg': 70.0, 'gb_i_w_m2': 800.0, 'gd_i_w_m2': 100.0,
                 'gr_i_w_m2': 100.0, 'gi_w_m2': 1000.0, 'p_w': 1000.0},
            ],
        }
        contexte = contexte_de(
            profil_plat(90.0),
            reglages_simulation={'attenuation_horizon': {
                'valeur': 'aucune', 'source': 'societe'}})
        rendue, etape = etape_horizon.appliquer(serie, contexte)
        self.assertEqual(etape['motif_omission'], '')
        point = rendue['points'][0]
        self.assertEqual(point['gb_i_w_m2'], 0.0)
        self.assertEqual(point['gi_w_m2'], 200.0)
        self.assertEqual(point['p_w'], 200.0)
        self.assertEqual(etapes.energie_kwh(rendue), 0.2)
