# -*- coding: utf-8 -*-
"""CALX159 — l'étape « inter-rangées » dans la chaîne de pertes.

CE QUI EST LU, ET POURQUOI JAMAIS LE TOTAL DE LA CHAÎNE
---------------------------------------------------------
Les essais passent par ``chaine_pertes.appliquer_chaine`` — le seul chemin que
la production emprunte, et celui qui impose les trois refus (une étape omise
laisse la série intacte, une étape qui gagne de l'énergie le déclare, une
étape appliquée nomme sa source) — mais ils lisent TOUJOURS l'entrée
``inter_rangees`` de la cascade, jamais l'énergie totale en sortie de chaîne.
La chaîne porte vingt-quatre étapes : dès qu'une lane voisine en livre une
(thermique, IAM, horizon…), elle réduit LÉGITIMEMENT la série, et un total
inchangé cesserait de prouver quoi que ce soit de CETTE étape-ci. Les douze
champs publiés par l'ordonnanceur (``kwh_avant``/``kwh_apres``, ``perte_pct``,
``source``, ``motif_omission``) sont mesurés AUTOUR de l'étape : eux seuls
sont stables.

L'intégrité de la série sur une omission (« une étape omise ne touche à
rien ») se vérifie donc par un appel DIRECT à
``etapes.inter_rangees.appliquer`` : c'est le seul endroit où l'on peut
attribuer la série rendue à cette étape et à elle seule.

AUCUNE BASE, AUCUN RÉSEAU — ``unittest`` pur. La série est une journée
d'hiver à Casablanca, en chiffres d'essai ASSUMÉS (ils ne sortent d'aucune
mesure : ce qui est prouvé ici est une géométrie, pas une production).

Run :
    python manage.py test apps.calepinage.tests.test_calx159_inter_rangees
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import inter_rangees
from apps.calepinage.services.etapes.inter_rangees import (
    CHAMP_KWC, CHAMP_PAS, SOURCE)
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES

ETAPE = 'inter_rangees'

#: Le site d'essai : Casablanca (le même point que les fixtures PVGIS).
LATITUDE = 33.5731
LONGITUDE = -7.5898

#: Une table de villa réelle (kit 2 modules paysage), inclinée à 30°.
COTE_TABLE_M = 1.134
INCLINAISON_DEG = 30.0


def point(heure, directe, diffuse, puissance_w):
    """Un point horaire d'essai — composantes séparées (CALX152)."""
    return {
        'annee': 2020, 'mois': 12, 'jour': 21, 'heure': heure,
        'gi_w_m2': (0.0 if directe is None else directe) + diffuse,
        't2m_c': 15.0,
        'gb_i_w_m2': directe, 'gd_i_w_m2': diffuse, 'gr_i_w_m2': 0.0,
        'ws10m': 2.0, 'h_sun_deg': None,
        'p_w': puissance_w,
    }


def serie(directe=True):
    """Une journée d'hiver de 8 h à 16 h, 1 kW par heure ensoleillée."""
    heures = (8, 9, 10, 11, 12, 13, 14, 15, 16)
    return {
        'pas_minutes': 60,
        'points': [point(heure, 600.0 if directe else None, 150.0, 1000.0)
                   for heure in heures],
    }


def plan(**surcharges):
    """Un pan plein sud de quatre rangées, resserrées à 1,5 m."""
    pan = {
        'cle': 'pan-sud',
        'inclinaison_deg': INCLINAISON_DEG,
        'azimut_pvgis_deg': 0.0,
        'pas_rangee_m': 1.5,
        'longueur_table_m': COTE_TABLE_M,
        'nombre_rangees': 4,
        'kwc': 6.0,
    }
    pan.update(surcharges)
    return {cle: valeur for cle, valeur in pan.items() if valeur is not None}


def contexte(plans=None, **surcharges):
    """Le contexte minimal que l'étape lit — rien de plus."""
    base = {
        'plans': plans if plans is not None else [plan()],
        'site': {'lat': LATITUDE, 'lon': LONGITUDE},
        'meteo': {'heure': {'base': 'utc', 'decalage_minutes': []}},
    }
    base.update(surcharges)
    return base


def etape_de(cascade):
    """L'étape « inter_rangees » telle que la cascade la publie."""
    for publiee in cascade['etapes']:
        if publiee['etape'] == ETAPE:
            return publiee
    raise AssertionError('« %s » absente de la cascade' % ETAPE)


class EtapeAppliquee(unittest.TestCase):
    """La géométrie du document donne une perte, sourcée et bornée."""

    def test_la_cascade_publie_une_perte_sourcee(self):
        _rendue, cascade = appliquer_chaine(serie(), contexte())
        etape = etape_de(cascade)
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['source'], SOURCE)
        self.assertEqual(etape['entree'], 'zones[].geometry')
        self.assertIn('plan de profil', etape['reference'])
        self.assertIn('pvsyst.com', etape['reference'])
        self.assertFalse(etape['gain'])
        self.assertGreater(etape['perte_pct'], 0.0)
        self.assertLess(etape['perte_pct'], 100.0)

    def test_la_perte_ne_touche_que_la_part_directe(self):
        """600 W directs sur 750 W : au plus 80 % de l'énergie est en jeu."""
        _rendue, cascade = appliquer_chaine(serie(), contexte())
        self.assertLessEqual(etape_de(cascade)['perte_pct'], 80.0)

    def test_l_etape_ne_gagne_jamais_d_energie(self):
        _rendue, cascade = appliquer_chaine(serie(), contexte())
        etape = etape_de(cascade)
        self.assertLessEqual(etape['kwh_apres'], etape['kwh_avant'])

    def test_un_pas_tres_large_ne_perd_rien(self):
        """Rangées espacées de 50 m : le soleil d'hiver passe au-dessus."""
        _rendue, cascade = appliquer_chaine(
            serie(), contexte([plan(pas_rangee_m=50.0)]))
        etape = etape_de(cascade)
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['perte_pct'], 0.0)

    def test_un_pas_plus_serre_perd_davantage(self):
        pertes = []
        for pas in (2.5, 2.0, 1.5, 1.2):
            _rendue, cascade = appliquer_chaine(
                serie(), contexte([plan(pas_rangee_m=pas)]))
            pertes.append(etape_de(cascade)['perte_pct'])
        self.assertEqual(pertes, sorted(pertes))
        self.assertGreater(pertes[-1], pertes[0])

    def test_la_geometrie_brute_du_document_est_lue(self):
        """Un pan qui porte ``zones[].geometry`` tel quel est compris."""
        brut = {
            'cle': 'pan-sud',
            'azimut_pvgis_deg': 0.0,
            'geometry': {
                'tiltDeg': INCLINAISON_DEG,
                'panelSlopeLenM': COTE_TABLE_M,
                'rowPitchM': 1.5,
                'rowCount': 4,
                'kwc': 6.0,
            },
        }
        _rendue, cascade = appliquer_chaine(serie(), contexte([brut]))
        etape = etape_de(cascade)
        self.assertEqual(etape['motif_omission'], '')
        self.assertGreater(etape['perte_pct'], 0.0)

    def test_le_pas_d_une_surface_au_sol_vient_du_moteur(self):
        """``engine.rowPitchM`` (CAL89) est le pas d'un champ au sol."""
        sol = {
            'cle': 'champ-sol',
            'azimut_pvgis_deg': 0.0,
            'tiltDeg': INCLINAISON_DEG,
            'longueur_table_m': COTE_TABLE_M,
            'nombre_rangees': 12,
            'kwc': 120.0,
            'engine': {'rowPitchM': 1.5},
        }
        _rendue, cascade = appliquer_chaine(serie(), contexte([sol]))
        self.assertGreater(etape_de(cascade)['perte_pct'], 0.0)


class PanARangeeUnique(unittest.TestCase):
    """Une seule rangée : aucune rangée amont, donc 0,0 % CALCULÉ."""

    def test_rend_zero_pour_cent_sans_reclamer_le_pas(self):
        unique = plan(nombre_rangees=1, pas_rangee_m=None)
        self.assertNotIn('pas_rangee_m', unique)
        contexte_ = contexte([unique])

        # Ce que la CASCADE publie pour cette étape : appliquée, 0,0 %.
        etape = etape_de(appliquer_chaine(serie(), contexte_)[1])
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['perte_pct'], 0.0)
        self.assertEqual(etape['perte_kwh'], 0.0)

        # Ce que l'ÉTAPE rend, elle seule : chaque heure intacte. Le total de
        # la chaîne, lui, porte les autres étapes et ne dirait rien d'elle.
        rendue, seule = inter_rangees.appliquer(serie(), contexte_)
        self.assertEqual(seule['motif_omission'], '')
        self.assertEqual([point['p_w'] for point in rendue['points']],
                         [point['p_w'] for point in serie()['points']])


class ChassisEstOuest(unittest.TestCase):
    """Deux plans opposés : la famille du document change le calcul."""

    def _pan(self, **surcharges):
        pan = plan(inclinaison_deg=15.0, azimut_pvgis_deg=-90.0,
                   pas_rangee_m=1.5)
        pan.update(surcharges)
        return pan

    def test_la_famille_est_ouest_est_appliquee(self):
        _rendue, cascade = appliquer_chaine(
            serie(), contexte([self._pan(famille='eastwest')]))
        etape = etape_de(cascade)
        self.assertEqual(etape['motif_omission'], '')
        self.assertGreater(etape['perte_pct'], 0.0)
        self.assertIn('parts égales', etape['reference'])

    def test_les_faces_posees_priment_sur_l_hypothese(self):
        pan = self._pan(famille='eastwest')
        pan['geometry'] = {'panels': [{'face': 'E'}, {'face': 'E'},
                                      {'face': 'W'}, {'face': 'W'}]}
        _rendue, cascade = appliquer_chaine(serie(), contexte([pan]))
        self.assertNotIn('parts égales', etape_de(cascade)['reference'])

    def test_un_chevron_ne_perd_pas_comme_un_plein_sud(self):
        _, cascade_ew = appliquer_chaine(
            serie(), contexte([self._pan(famille='eastwest')]))
        _, cascade_sud = appliquer_chaine(
            serie(), contexte([self._pan()]))
        self.assertNotEqual(etape_de(cascade_ew)['perte_pct'],
                            etape_de(cascade_sud)['perte_pct'])


class EtapeOmise(unittest.TestCase):
    """Chaque entrée absente OMET l'étape en nommant le champ à saisir."""

    def _omission(self, serie_, contexte_, *, par_le_module=True):
        """La cascade publie l'étape OMISE, et rend son motif.

        ``par_le_module`` dit qui omet. Quand c'est le MODULE (une entrée
        manque), on vérifie EN PLUS, par un appel direct, qu'il rend la série
        intacte : la chaîne complète porte d'autres étapes qui la réduisent
        légitimement, son total ne prouverait rien de celle-ci. Quand c'est
        l'ORDONNANCEUR (exclusivité D-CALX 16), le module n'est même pas
        appelé — il n'y a rien à lui demander.
        """
        if par_le_module:
            rendue, seule = inter_rangees.appliquer(serie_, contexte_)
            self.assertNotEqual(seule['motif_omission'], '')
            self.assertEqual(etapes.energie_kwh(rendue),
                             etapes.energie_kwh(serie_))
        etape = etape_de(appliquer_chaine(serie_, contexte_)[1])
        self.assertNotEqual(etape['motif_omission'], '')
        self.assertIsNone(etape['kwh_apres'])
        self.assertIsNone(etape['perte_pct'])
        self.assertIsNone(etape['source'])
        return etape['motif_omission']

    def test_inclinaison_absente(self):
        motif = self._omission(
            serie(), contexte([plan(inclinaison_deg=None)]))
        self.assertIn('zones[].geometry.tiltDeg', motif)

    def test_longueur_de_table_absente(self):
        motif = self._omission(
            serie(), contexte([plan(longueur_table_m=None)]))
        self.assertIn('zones[].geometry.panelSlopeLenM', motif)

    def test_pas_absent_avec_plusieurs_rangees(self):
        motif = self._omission(
            serie(), contexte([plan(pas_rangee_m=None)]))
        self.assertIn(CHAMP_PAS, motif)

    def test_pas_absent_et_nombre_de_rangees_inconnu(self):
        motif = self._omission(
            serie(),
            contexte([plan(pas_rangee_m=None, nombre_rangees=None)]))
        self.assertIn('rowPitchM', motif)

    def test_aucun_pan(self):
        motif = self._omission(serie(), contexte([]))
        self.assertIn('zones[].geometry', motif)

    def test_plusieurs_pans_sans_puissance_posee(self):
        motif = self._omission(
            serie(),
            contexte([plan(), plan(cle='pan-ouest', kwc=None)]))
        self.assertIn(CHAMP_KWC, motif)

    def test_composantes_absentes(self):
        motif = self._omission(serie(directe=False), contexte())
        self.assertEqual(motif, MOTIF_COMPOSANTES_ABSENTES)

    def test_site_sans_point(self):
        motif = self._omission(serie(), contexte(site={}))
        self.assertIn('site.lat', motif)

    def test_heure_locale_sans_decalage_publie(self):
        motif = self._omission(
            serie(),
            contexte(meteo={'heure': {'base': 'locale_standard',
                                      'decalage_minutes': []}}))
        self.assertIn('meteo.heure.decalage_minutes', motif)

    def test_base_horaire_inconnue(self):
        motif = self._omission(
            serie(), contexte(meteo={'heure': {'base': 'heure_d_ete'}}))
        self.assertIn('meteo.heure.base', motif)

    def test_acces_solaire_par_module_ecarte_l_etape(self):
        """D-CALX 16 : l'ordonnanceur écarte l'étape, pas le module."""
        motif = self._omission(
            serie(),
            contexte(ombrage={'solar_access': {'method': {'rangees': True}}}),
            par_le_module=False)
        self.assertIn('rangées entre elles', motif)


class HeureLocale(unittest.TestCase):
    """Le décalage UTC publié est APPLIQUÉ, jamais ignoré."""

    def _perte(self, meteo):
        # Appel DIRECT de l'étape : depuis CALX59, `appliquer_chaine` ré-indexe
        # la série sur le fuseau SAISI du site et réécrit `meteo.heure` — ici on
        # prouve que l'ÉTAPE applique le décalage qu'on lui publie, pas la chaîne.
        from ..services import etapes
        from ..services.etapes import inter_rangees
        source = serie()
        rendue, etape = inter_rangees.appliquer(source, contexte(meteo=meteo))
        self.assertEqual(etape['motif_omission'], '')
        return round(etapes.energie_kwh(source) - etapes.energie_kwh(rendue), 9)

    def test_un_decalage_publie_deplace_le_soleil(self):
        utc = self._perte({'heure': {'base': 'utc'}})
        locale = self._perte({'heure': {'base': 'locale_standard',
                                        'decalage_minutes': 60}})
        self.assertNotEqual(utc, locale)

    def test_un_decalage_par_point_est_accepte(self):
        decalages = [60] * len(serie()['points'])
        self.assertEqual(
            self._perte({'heure': {'base': 'locale_standard',
                                   'decalage_minutes': decalages}}),
            self._perte({'heure': {'base': 'locale_standard',
                                   'decalage_minutes': 60}}))
