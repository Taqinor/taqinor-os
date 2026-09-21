# -*- coding: utf-8 -*-
"""CALX164 — le vent arrive enfin jusqu'au modèle thermique, ou il est DIT.

CE QUI EST PROUVÉ ICI
---------------------
1. **Le vent traverse** : ``WS10m`` de la réponse PVGIS enregistrée est lu par
   les DEUX portes du client (``serie_irradiance``, CALX150, et le chemin
   d'aujourd'hui ``serie_horaire``), et il arrive tel quel sur chaque point
   que ``services/thermique.py::perte_thermique`` consomme.
2. **Il refroidit vraiment** (test de propriété) : avec une fiche portant
   ``uv_w_m3sk``, la température de cellule calculée sur les vents RÉELS de la
   fixture est STRICTEMENT inférieure à celle calculée sur la même série vent
   retiré. C'était l'anomalie : Faiman tournait toujours à vent nul.
3. **Les deux silences ne se confondent pas** : la fiche muette sur Uv et la
   série muette sur le vent portent des motifs DISTINCTS, tous deux publiés
   (``hypotheses`` et ``motif``), et l'étape CALX163 les fait voyager dans
   ``cascade[].entree``.
4. **Rien n'est supposé** : une fiche qui donne ``uv_w_m3sk = 0`` ne publie
   aucune hypothèse (elle DIT que le vent ne compte pas), et aucune vitesse de
   vent n'est jamais fabriquée (D-CALX 7).

Parité : PVsyst — Array thermal losses, ``U = Uc + Uv × v``
(https://www.pvsyst.com/help/project-design/array-and-system-losses/
array-thermal-losses/index.html).

AUCUN RÉSEAU, AUCUNE BASE : le transport est injecté et rejoue la réponse
enregistrée ``tests/fixtures_pvgis/seriescalc_casablanca_sud.json``.
``SimpleTestCase`` : aucune base de données.

Run :
    python manage.py test apps.calepinage.tests.test_calx164_vent
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.etapes import thermique as etape_thermique
from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache
from apps.calepinage.services.thermique import (
    COLONNE_VENT, GABARIT_VENT_PARTIEL, HYPOTHESE_UV_ABSENT_DE_LA_FICHE,
    HYPOTHESE_VENT_ABSENT_DE_LA_SERIE, MODELE_FAIMAN, perte_thermique,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Postes d'ESSAI — la mécanique de ``serie_horaire``, pas des pertes réelles.
POSTES_ESSAI = [{'poste': 'shading', 'pct': 3.5, 'source': 'mesure'}]

#: Fiche d'ESSAI portant le couple complet Uc/Uv (les noms sont ceux de
#: ``apps.stock.selectors.specs_for_produit``, champs CAL111). Ces valeurs
#: servent la MÉCANIQUE du modèle, elles ne chiffrent aucune installation.
FICHE_AVEC_UV = {
    'uc_w_m2k': 25.0, 'uv_w_m3sk': 1.2, 'temp_coeff_pmax_pct_c': -0.35,
}
#: La MÊME fiche, sans Uv : le fabricant n'a rien dit du vent.
FICHE_SANS_UV = {'uc_w_m2k': 25.0, 'temp_coeff_pmax_pct_c': -0.35}
#: Une fiche qui DIT que le vent ne compte pas — ce n'est pas une hypothèse.
FICHE_UV_NUL = dict(FICHE_AVEC_UV, uv_w_m3sk=0.0)


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    """Transport INJECTÉ : rejoue une réponse enregistrée, jamais le réseau."""

    def __init__(self, charge):
        self.charge = charge
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return 200, json.dumps(self.charge)


def client(charge):
    return ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                       dormir=lambda _s: None)


def points_du_chemin_rapide():
    """Les points de ``serie_horaire`` — le chemin du constructeur 3D."""
    return client(charger('seriescalc_casablanca_sud.json')).serie_horaire(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        politique=politique_de_pertes(POSTES_ESSAI),
        annee_debut=2020, annee_fin=2020)['points']


def points_de_l_irradiance_nue():
    """Les points de ``serie_irradiance`` — ceux de la chaîne de pertes."""
    return client(
        charger('seriescalc_casablanca_sud_irradiance.json')
    ).serie_irradiance(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        annee_debut=2020, annee_fin=2020,
        obtenue_le='2026-09-21T09:00:00Z')['points']


def sans_vent(points):
    """La MÊME série, vent retiré — rien d'autre ne change."""
    return [{cle: valeur for cle, valeur in point.items()
             if cle != COLONNE_VENT} for point in points]


class LeVentTraverseLeClientTest(SimpleTestCase):
    """``WS10m`` est lu par les deux portes, et vaut celui de la réponse."""

    def test_serie_horaire_publie_enfin_le_vent(self):
        points = points_du_chemin_rapide()
        self.assertTrue(points)
        manquants = [p for p in points if p.get(COLONNE_VENT) is None]
        self.assertEqual(manquants, [])

    def test_serie_irradiance_publie_le_vent(self):
        points = points_de_l_irradiance_nue()
        self.assertTrue(points)
        manquants = [p for p in points if p.get(COLONNE_VENT) is None]
        self.assertEqual(manquants, [])

    def test_la_vitesse_est_celle_de_la_reponse_enregistree(self):
        lignes = charger('seriescalc_casablanca_sud.json')['outputs']['hourly']
        attendu = lignes[0]['WS10m']
        self.assertEqual(points_du_chemin_rapide()[0][COLONNE_VENT], attendu)

    def test_aucune_vitesse_de_vent_n_est_fabriquee(self):
        """Une réponse sans ``WS10m`` rend ``None``, jamais un zéro."""
        charge = charger('seriescalc_casablanca_sud.json')
        for ligne in charge['outputs']['hourly']:
            ligne.pop('WS10m', None)
        points = client(charge).serie_horaire(
            lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
            politique=politique_de_pertes(POSTES_ESSAI),
            annee_debut=2020, annee_fin=2020)['points']
        self.assertTrue(points)
        for point in points:
            self.assertIsNone(point[COLONNE_VENT])


class LeVentRefroiditLaCelluleTest(SimpleTestCase):
    """Test de PROPRIÉTÉ : avec Uv, la série ventée chauffe moins."""

    def setUp(self):
        self.points = points_du_chemin_rapide()
        self.avec = perte_thermique(FICHE_AVEC_UV, self.points)
        self.sans = perte_thermique(FICHE_AVEC_UV, sans_vent(self.points))

    def test_les_deux_calculs_sont_comparables(self):
        for mesure in (self.avec, self.sans):
            self.assertTrue(mesure['calculable'], mesure['motif'])
            self.assertEqual(mesure['modele'], MODELE_FAIMAN)
        self.assertEqual(self.avec['heures_retenues'],
                         self.sans['heures_retenues'])

    def test_la_temperature_moyenne_est_strictement_plus_basse(self):
        self.assertLess(self.avec['temperature_cellule_moyenne_c'],
                        self.sans['temperature_cellule_moyenne_c'])

    def test_la_temperature_maximale_est_strictement_plus_basse(self):
        self.assertLess(self.avec['temperature_cellule_max_c'],
                        self.sans['temperature_cellule_max_c'])

    def test_donc_la_perte_thermique_est_strictement_plus_faible(self):
        self.assertLess(self.avec['pct'], self.sans['pct'])

    def test_les_heures_ventees_sont_comptees(self):
        self.assertEqual(self.avec['heures_avec_vent'],
                         self.avec['heures_retenues'])
        self.assertEqual(self.sans['heures_avec_vent'], 0)

    def test_sans_uv_le_vent_ne_change_rien(self):
        """Sans Uv sur la fiche, le terme de vent n'existe pas du tout."""
        avec = perte_thermique(FICHE_SANS_UV, self.points)
        sans = perte_thermique(FICHE_SANS_UV, sans_vent(self.points))
        self.assertEqual(avec['pct'], sans['pct'])


class LesDeuxSilencesSontDistinctsTest(SimpleTestCase):
    """Fiche muette ≠ série muette : deux motifs, deux interlocuteurs."""

    def setUp(self):
        self.points = points_du_chemin_rapide()

    def test_les_deux_motifs_ne_se_confondent_pas(self):
        self.assertNotEqual(HYPOTHESE_UV_ABSENT_DE_LA_FICHE,
                            HYPOTHESE_VENT_ABSENT_DE_LA_SERIE)

    def test_fiche_muette_sur_uv_le_dit(self):
        mesure = perte_thermique(FICHE_SANS_UV, self.points)
        self.assertEqual(mesure['hypotheses'],
                         [HYPOTHESE_UV_ABSENT_DE_LA_FICHE])
        self.assertIn(HYPOTHESE_UV_ABSENT_DE_LA_FICHE, mesure['motif'])
        self.assertNotIn(HYPOTHESE_VENT_ABSENT_DE_LA_SERIE, mesure['motif'])

    def test_serie_muette_sur_le_vent_le_dit_AUTREMENT(self):
        mesure = perte_thermique(FICHE_AVEC_UV, sans_vent(self.points))
        self.assertEqual(mesure['hypotheses'],
                         [HYPOTHESE_VENT_ABSENT_DE_LA_SERIE])
        self.assertIn(HYPOTHESE_VENT_ABSENT_DE_LA_SERIE, mesure['motif'])
        self.assertNotIn(HYPOTHESE_UV_ABSENT_DE_LA_FICHE, mesure['motif'])

    def test_serie_ventee_et_fiche_complete_ne_supposent_rien(self):
        mesure = perte_thermique(FICHE_AVEC_UV, self.points)
        self.assertEqual(mesure['hypotheses'], [])

    def test_une_fiche_qui_dit_uv_nul_n_est_pas_une_hypothese(self):
        mesure = perte_thermique(FICHE_UV_NUL, sans_vent(self.points))
        self.assertEqual(mesure['hypotheses'], [])

    def test_un_vent_partiel_est_dit_avec_ses_deux_nombres(self):
        ventes = list(self.points)
        muettes = sans_vent(ventes[: len(ventes) // 2])
        mesure = perte_thermique(FICHE_AVEC_UV,
                                 muettes + ventes[len(ventes) // 2:])
        self.assertEqual(len(mesure['hypotheses']), 1)
        self.assertEqual(
            mesure['hypotheses'][0],
            GABARIT_VENT_PARTIEL.format(avec=mesure['heures_avec_vent'],
                                        total=mesure['heures_retenues']))
        self.assertLess(mesure['heures_avec_vent'],
                        mesure['heures_retenues'])

    def test_la_serie_sans_soleil_ne_publie_aucune_hypothese(self):
        mesure = perte_thermique(FICHE_AVEC_UV, [])
        self.assertFalse(mesure['calculable'])
        self.assertEqual(mesure['hypotheses'], [])
        self.assertEqual(mesure['heures_avec_vent'], 0)


class LEtapePublieLHypotheseTest(SimpleTestCase):
    """CALX163 fait voyager l'hypothèse dans ``cascade[].entree``."""

    def serie(self, points):
        return {'points': points, 'colonne_energie': 'p_w'}

    def contexte(self):
        return {'fiche_module': dict(FICHE_AVEC_UV), 'plans': [],
                'reglages_simulation': {}}

    def test_l_etape_publie_les_heures_ventees_et_l_hypothese(self):
        points = [dict(point, p_w=1000.0)
                  for point in points_du_chemin_rapide()]
        _serie, etape = etape_thermique.appliquer(
            self.serie(points), self.contexte())
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['hypotheses'], [])
        self.assertEqual(etape['entree']['heures_avec_vent'],
                         etape['entree']['heures_retenues'])

    def test_serie_sans_vent_l_etape_nomme_le_silence_de_la_meteo(self):
        points = [dict(point, p_w=1000.0)
                  for point in sans_vent(points_du_chemin_rapide())]
        _serie, etape = etape_thermique.appliquer(
            self.serie(points), self.contexte())
        self.assertEqual(etape['entree']['hypotheses'],
                         [HYPOTHESE_VENT_ABSENT_DE_LA_SERIE])
        self.assertEqual(etape['entree']['heures_avec_vent'], 0)

    def test_l_etape_garde_les_six_cles_du_contrat(self):
        points = [dict(point, p_w=1000.0)
                  for point in points_du_chemin_rapide()]
        _serie, etape = etape_thermique.appliquer(
            self.serie(points), self.contexte())
        for cle in _etapes.CLES_ETAPE:
            self.assertIn(cle, etape, cle)
