# -*- coding: utf-8 -*-
"""QJR139 — la puissance souscrite recommandée cesse d'être ~30× trop grande.

``etude.py`` passait à ``solar_design.optimize_subscribed_power`` les 288
points « 12 mois × jour type » où chaque case porte l'ÉNERGIE de tout le mois à
cette heure-là, alors que la fonction les lit comme des PUISSANCES
instantanées. Pour un foyer à 12 000 kWh/an, la case du soir vaut ≈ 92 « kW »
au lieu de ≈ 3,3 kW réels : ``recommended_subscribed`` et ``peak_pre_pv_kw``
étaient absurdes (seul le ratio ``peak_reduction_pct`` survivait). Le bloc
n'atteint pas le client (``public_views`` retire ``simulation``) mais s'affiche
au VENDEUR, qui peut le répéter de vive voix.

Deux corrections, deux familles de tests :
* la conversion en kW avant l'appel (``courbe_mensuelle_en_kw``) ;
* la GARDE D'UNITÉ côté ``solar_design`` : une courbe dont l'unité n'est pas
  déclarée est REFUSÉE — toutes les grandeurs absentes plutôt qu'une pointe
  plausible et fausse.

Tests purs — aucune base, aucun réseau.
"""
from django.test import SimpleTestCase

from apps.parametres.pvgis_profils import JOURS_PAR_MOIS
from apps.ventes import solar_design as sd
from apps.ventes.etude import (
    _tiled_load_curve,
    courbe_mensuelle_en_kw,
    production_horaire_zone,
)

#: La fixture du constat : 12 000 kWh/an, profil résidentiel.
_CONSO_ANNUELLE_KWH = 12000.0
_PRODUCTION_ANNUELLE_KWH = 15000.0


def _courbes():
    load = _tiled_load_curve(_CONSO_ANNUELLE_KWH / 365.0, 'residential')
    prod = production_horaire_zone(
        {'base_production_kwh': _PRODUCTION_ANNUELLE_KWH})
    return load, prod


class ConversionEnKilowattsTests(SimpleTestCase):
    """``courbe_mensuelle_en_kw`` : de l'énergie du mois à la puissance."""

    def test_la_grille_reste_de_288_points(self):
        load, _prod = _courbes()
        self.assertEqual(len(courbe_mensuelle_en_kw(load)), 288)

    def test_chaque_case_est_divisee_par_les_jours_de_SON_mois(self):
        load, _prod = _courbes()
        kw = courbe_mensuelle_en_kw(load)
        for m in range(12):
            for h in (0, 12, 20):
                i = m * 24 + h
                self.assertAlmostEqual(
                    kw[i], load[i] / JOURS_PAR_MOIS[m], places=9,
                    msg='mois %d, heure %d' % (m + 1, h))

    def test_la_pointe_du_soir_redevient_une_puissance_plausible(self):
        """Le chiffre du constat : ≈ 92 « kW » → ≈ 3,3 kW pour 12 000 kWh/an."""
        load, _prod = _courbes()
        kw = courbe_mensuelle_en_kw(load)
        self.assertGreater(max(load), 50.0)     # l'ancienne lecture, absurde
        self.assertLess(max(kw), 10.0)          # une pointe de foyer réelle
        self.assertGreater(max(kw), 1.0)

    def test_une_grille_qui_n_est_pas_celle_du_module_est_refusee(self):
        """Longueur ≠ 288 ⇒ unité NON établie : ``None``, jamais une supposition."""
        for mauvais in (None, [], [1.0] * 24, [1.0] * 287, [1.0] * 8760):
            self.assertIsNone(courbe_mensuelle_en_kw(mauvais),
                              msg='longueur %s' % (
                                  len(mauvais) if mauvais else mauvais))

    def test_valeurs_illisibles_ne_levent_jamais(self):
        kw = courbe_mensuelle_en_kw(['x'] * 288)
        self.assertEqual(kw, [0.0] * 288)


class PuissanceRecommandeeTests(SimpleTestCase):
    """La recommandation est enfin cohérente avec la pointe RÉELLE."""

    def _resultat(self, curve_unit=sd.SUBSCRIBED_CURVE_UNIT_KW):
        load, prod = _courbes()
        return sd.optimize_subscribed_power(
            load_curve=courbe_mensuelle_en_kw(load),
            production_curve=courbe_mensuelle_en_kw(prod),
            curve_unit=curve_unit, current_subscribed_kva=10)

    def test_la_pointe_pre_pv_est_celle_du_foyer(self):
        res = self._resultat()
        self.assertLess(res['peak_pre_pv_kw'], 10.0)
        self.assertGreater(res['peak_pre_pv_kw'], 1.0)

    def test_la_recommandation_reste_sous_la_souscription_actuelle(self):
        res = self._resultat()
        self.assertIsNotNone(res['recommended_subscribed'])
        self.assertLess(res['recommended_subscribed'], 10)
        self.assertGreater(res['recommended_subscribed'], 0)

    def test_l_ancienne_lecture_ne_recommandait_jamais_rien(self):
        """Régression : 92 « kW » × marge dépassait TOUJOURS la souscription,
        donc la fonction rendait « aucune réduction » sur un foyer que le PV
        écrête pourtant."""
        load, prod = _courbes()
        ancien = sd.optimize_subscribed_power(
            load_curve=load, production_curve=prod,
            curve_unit=sd.SUBSCRIBED_CURVE_UNIT_KW, current_subscribed_kva=10)
        self.assertGreater(ancien['peak_pre_pv_kw'], 50.0)
        self.assertEqual(ancien['recommended_subscribed'], 10)
        # Le nouveau, lui, recommande une VRAIE réduction.
        self.assertLess(self._resultat()['recommended_subscribed'], 10)

    def test_seul_le_ratio_survivait_a_l_ancienne_lecture(self):
        """Le ratio est invariant d'échelle — c'est pourquoi il ne trahissait
        rien, et pourquoi il ne prouvait rien non plus."""
        load, prod = _courbes()
        ancien = sd.optimize_subscribed_power(
            load_curve=load, production_curve=prod,
            curve_unit=sd.SUBSCRIBED_CURVE_UNIT_KW, current_subscribed_kva=10)
        self.assertAlmostEqual(ancien['peak_reduction_pct'],
                               self._resultat()['peak_reduction_pct'],
                               places=1)


class GardeUniteTests(SimpleTestCase):
    """« faire REFUSER une courbe dont l'unité n'est pas déclarée »."""

    LOAD = [5.0] * 24
    PROD = [1.0] * 24

    def _appel(self, **kwargs):
        return sd.optimize_subscribed_power(
            load_curve=self.LOAD, production_curve=self.PROD,
            current_subscribed_kva=10, **kwargs)

    def test_une_unite_non_declaree_est_refusee(self):
        for unite in (None, '', 'kwh', 'kwh_mois', 'kWh/mois', 42, object()):
            res = self._appel(curve_unit=unite)
            self.assertIsNone(res['peak_pre_pv_kw'], msg=repr(unite))
            self.assertIsNone(res['recommended_subscribed'], msg=repr(unite))
            self.assertIsNone(res['annual_saving'], msg=repr(unite))
            self.assertTrue(res['warnings'])

    def test_le_refus_nomme_l_unite_recue(self):
        res = self._appel(curve_unit='kwh_mois')
        self.assertIn('kwh_mois', res['warnings'][0])
        self.assertIn('PUISSANCES', res['warnings'][0])

    def test_le_refus_rend_le_MEME_jeu_de_cles(self):
        """Omettre les VALEURS, jamais les clés : l'appelant ne casse pas."""
        ok = self._appel(curve_unit=sd.SUBSCRIBED_CURVE_UNIT_KW)
        ko = self._appel(curve_unit=None)
        self.assertEqual(set(ok), set(ko))

    def test_l_unite_declaree_est_tolerante_a_la_casse(self):
        res = self._appel(curve_unit='  KW ')
        self.assertIsNotNone(res['peak_pre_pv_kw'])

    def test_le_defaut_reste_l_unite_documentee_du_module(self):
        """Le module PUR déclare des kW dans sa signature — comportement
        historique inchangé pour ses appelants existants."""
        res = self._appel()
        self.assertEqual(res['peak_pre_pv_kw'], 5.0)
