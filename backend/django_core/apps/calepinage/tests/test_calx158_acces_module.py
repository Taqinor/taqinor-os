# -*- coding: utf-8 -*-
"""CALX158 — l'accès solaire se lit MODULE PAR MODULE, et se dit.

CE QUI EST PROUVÉ ICI
---------------------
1. **Sans ``solarAccess``, l'étape s'omet** avec le motif que
   ``ombrage_chaines.MOTIF_SANS_ACCES`` publie déjà — une seule formulation
   dans tout le dépôt.
2. **Un module ``null`` ne tire pas la moyenne vers 1** : il est publié dans
   ``modules_sans_acces`` et EXCLU du calcul. Le contrat v2 l'interdit
   explicitement, et c'est le piège que cette étape existe pour éviter.
3. **Propriété** : deux modules à 1,0 et 0,5 sur un plan de deux modules
   rendent exactement 25 % de perte sur le direct.
4. **La méthode doit se déclarer** : sans ``horizon`` ni ``rangees``, la
   lecture n'est pas comparable et l'étape s'omet en NOMMANT la clé ; une
   méthode qui inclut l'horizon lointain est refusée (double comptage avec
   CALX156).
5. **La résolution est dite, pas surjouée** : un facteur par module n'est
   pas une courbe horaire, et l'étape le publie.
6. ``acces_par_module`` est RÉUTILISÉ : un document de toiture v2 est lu par
   le service qui connaît déjà l'ordre des modules d'un pan.

Aucune base de données, aucun réseau : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx158_acces_module
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import LIBELLES, appliquer_chaine
from apps.calepinage.services.etapes import acces_module
from apps.calepinage.services.ombrage_chaines import MOTIF_SANS_ACCES
from apps.calepinage.services.pvgis_serie import (
    MOTIF_COMPOSANTES_ABSENTES, ClientPvgis, _Cache)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
AVEC_COMPOSANTES = 'seriescalc_casablanca_sud_composantes.json'
SANS_COMPOSANTES = 'seriescalc_casablanca_sud_irradiance.json'

#: Une méthode COMPLÈTE : elle répond aux deux questions que la tâche pose.
METHODE = {'horizon': False, 'rangees': False,
           'nom': 'shadingEngine roofPro11'}

#: Deux heures ensoleillées, composantes séparées — le minimum pour lire
#: une perte de direct sans rien deviner.
SERIE = {
    'pas_minutes': 60,
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
         'gb_i_w_m2': 400.0, 'gd_i_w_m2': 100.0, 'gr_i_w_m2': 0.0,
         'gi_w_m2': 500.0},
    ],
}


class TransportEnregistre:
    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def serie_de(fixture, *, composantes):
    charge = json.loads((FIXTURES / fixture).read_text(encoding='utf-8'))
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    resultat = client.serie_irradiance(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        annee_debut=2020, annee_fin=2020, composantes=composantes,
        obtenue_le='2026-09-21T09:00:00Z')
    return resultat['serie_horaire']


def contexte_de(values, *, methode=None, **extra):
    acces = {'values': values, 'method': dict(METHODE if methode is None
                                              else methode)}
    contexte = {'ombrage': {'solarAccess': acces}}
    contexte['ombrage'].update(extra)
    return contexte


def somme(serie, colonne):
    return sum(point[colonne] or 0.0 for point in serie['points'])


class ProprieteTest(SimpleTestCase):
    """La perte de direct suit la moyenne des modules CALCULÉS."""

    def test_un_et_un_demi_font_vingt_cinq_pour_cent(self):
        rendue, etape = acces_module.appliquer(
            SERIE, contexte_de([1.0, 0.5]))
        self.assertEqual(etape['motif_omission'], '')
        avant = somme(SERIE, 'gb_i_w_m2')
        apres = somme(rendue, 'gb_i_w_m2')
        self.assertAlmostEqual(100.0 * (1.0 - apres / avant), 25.0, places=9)
        self.assertEqual(etape['entree']['facteur_moyen'], 0.75)

    def test_un_module_null_ne_tire_pas_la_moyenne_vers_un(self):
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_de([0.5, None]))
        self.assertEqual(etape['entree']['facteur_moyen'], 0.5,
                         'un « null » complété à 1 donnerait 0,75 : le '
                         'contrat v2 l’interdit explicitement.')
        self.assertEqual(etape['entree']['modules_sans_acces'], [1])
        self.assertEqual(etape['entree']['modules_calcules'], 1)
        self.assertEqual(etape['entree']['modules_lus'], 2)

    def test_une_valeur_hors_bornes_compte_comme_non_calculee(self):
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_de([0.4, 1.8]))
        self.assertEqual(etape['entree']['facteur_moyen'], 0.4)
        self.assertEqual(etape['entree']['modules_sans_acces'], [1])

    def test_le_diffus_et_le_reflechi_ne_sont_pas_masques(self):
        rendue, _etape = acces_module.appliquer(
            SERIE, contexte_de([0.0, 0.0]))
        for colonne in ('gd_i_w_m2', 'gr_i_w_m2'):
            self.assertAlmostEqual(somme(rendue, colonne),
                                   somme(SERIE, colonne), places=9,
                                   msg=colonne)
        self.assertEqual(somme(rendue, 'gb_i_w_m2'), 0.0)

    def test_la_serie_d_entree_n_est_jamais_modifiee(self):
        empreinte = json.dumps(SERIE, sort_keys=True)
        acces_module.appliquer(SERIE, contexte_de([0.3, 0.6]))
        self.assertEqual(json.dumps(SERIE, sort_keys=True), empreinte,
                         'une étape est PURE : elle copie, elle ne mute pas.')

    def test_le_libelle_est_celui_que_l_ordre_declare(self):
        _rendue, etape = acces_module.appliquer(SERIE, contexte_de([1.0]))
        self.assertEqual(etape['libelle'], LIBELLES['acces_module'])


class MethodeDeclareeTest(SimpleTestCase):
    """Deux tracés différents ne sont pas comparables : la méthode le dit."""

    def _omise(self, contexte):
        rendue, etape = acces_module.appliquer(SERIE, contexte)
        self.assertIs(rendue, SERIE)
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['source'])
        return etape['motif_omission']

    def test_sans_horizon_la_cle_est_nommee(self):
        motif = self._omise(contexte_de([0.9], methode={'rangees': False}))
        self.assertIn('solarAccess.method.horizon', motif)

    def test_sans_rangees_la_cle_est_nommee(self):
        motif = self._omise(contexte_de([0.9], methode={'horizon': False}))
        self.assertIn('solarAccess.method.rangees', motif)

    def test_une_methode_en_texte_ne_declare_rien(self):
        contexte = {'ombrage': {'solarAccess': {'values': [0.9],
                                                'method': 'placeholder'}}}
        motif = self._omise(contexte)
        self.assertIn('solarAccess.method.horizon', motif)

    def test_une_methode_qui_inclut_l_horizon_est_refusee(self):
        motif = self._omise(contexte_de(
            [0.9], methode={'horizon': True, 'rangees': False}))
        self.assertIn('CALX156', motif)
        self.assertIn('deux fois', motif)

    def test_rangees_vrai_ne_bloque_pas_cette_etape(self):
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_de([0.9],
                               methode={'horizon': False, 'rangees': True}))
        self.assertEqual(etape['motif_omission'], '',
                         '« rangees » pilote l’exclusivité d’inter_rangees '
                         'chez l’ordonnanceur, pas celle-ci.')


class ResolutionTest(SimpleTestCase):
    """Un facteur par module n'est pas une courbe horaire — et le dit."""

    def test_par_defaut_la_resolution_annuelle_est_publiee(self):
        _rendue, etape = acces_module.appliquer(SERIE, contexte_de([0.8]))
        self.assertEqual(etape['entree']['resolution'], 'annuelle')
        self.assertIn('CONSTANT', etape['entree']['avertissement'])
        self.assertIn('facteur constant', etape['entree']['application'])

    def test_une_methode_horaire_declaree_est_republiee(self):
        methode = dict(METHODE, resolution='horaire')
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_de([0.8], methode=methode))
        self.assertEqual(etape['entree']['resolution'], 'horaire')
        self.assertNotIn('avertissement', etape['entree'])


class EntreeManquanteTest(SimpleTestCase):
    """Chaque absence est NOMMÉE — jamais un module supposé à 100 %."""

    def test_sans_acces_le_motif_est_celui_du_service(self):
        rendue, etape = acces_module.appliquer(SERIE, {'ombrage': {}})
        self.assertIs(rendue, SERIE)
        self.assertIn(MOTIF_SANS_ACCES, etape['motif_omission'])
        self.assertIn('ombrage.solarAccess', etape['motif_omission'])

    def test_tous_les_modules_null_omettent_l_etape(self):
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_de([None, None]))
        self.assertIn('AUCUN module', etape['motif_omission'])

    def test_sans_composantes_le_motif_est_celui_de_calx152(self):
        serie = serie_de(SANS_COMPOSANTES, composantes=False)
        _rendue, etape = acces_module.appliquer(serie, contexte_de([0.7]))
        self.assertEqual(etape['motif_omission'], MOTIF_COMPOSANTES_ABSENTES)


class LectureDuDocumentTest(SimpleTestCase):
    """``acces_par_module`` est réutilisé, pas réécrit."""

    LAYOUT = {
        'version': 2,
        'zones': [
            {'label': 'PAN-SUD',
             'geometry': {'solarAccess': {'values': [1.0, 0.5]}}},
            {'label': 'PAN-NORD',
             'geometry': {'solarAccess': {'values': [0.2, None]}}},
        ],
    }

    def test_le_document_de_toiture_est_lu_par_le_service(self):
        contexte = {'ombrage': {'solarAccess': {'method': dict(METHODE)},
                                'layout': self.LAYOUT}}
        _rendue, etape = acces_module.appliquer(SERIE, contexte)
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['modules_lus'], 4)
        self.assertEqual(etape['entree']['modules_calcules'], 3)

    def test_le_pan_nomme_restreint_la_moyenne_a_ses_modules(self):
        contexte = {'ombrage': {'solarAccess': {'method': dict(METHODE)},
                                'layout': self.LAYOUT},
                    'plan': {'cle': 'PAN-SUD'}}
        _rendue, etape = acces_module.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['modules_lus'], 2)
        self.assertEqual(etape['entree']['facteur_moyen'], 0.75)

    def test_une_table_par_pan_du_contexte_est_lue(self):
        contexte = {'ombrage': {'solarAccess': {
            'method': dict(METHODE),
            'par_pan': {'PAN-SUD': [0.6, 0.4]}}}}
        _rendue, etape = acces_module.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['facteur_moyen'], 0.5)


class DansLaChaineTest(SimpleTestCase):
    """Vue par l'ordonnanceur, et lisible par la simulation par module."""

    def test_l_etape_appliquee_porte_les_douze_champs(self):
        serie, cascade = appliquer_chaine(SERIE, contexte_de([1.0, 0.5]))
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'acces_module')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['libelle'], LIBELLES['acces_module'])
        self.assertEqual(etape['source'], 'document')
        self.assertFalse(etape['gain'])
        self.assertIn('HelioScope', etape['reference'])
        self.assertEqual(serie['acces_module']['facteurs'], [1.0, 0.5])
        self.assertEqual(serie['acces_module']['modules_sans_acces'], [])

    def test_la_matrice_12x24_est_ecartee_au_profit_de_cette_lecture(self):
        contexte = contexte_de([0.9])
        contexte['ombrage']['shading12x24'] = [[0.5] * 24 for _m in range(12)]
        _serie, cascade = appliquer_chaine(SERIE, contexte)
        par_nom = {e['etape']: e for e in cascade['etapes']}
        self.assertIn('module par module',
                      par_nom['ombrage_proche']['motif_omission'].lower())
        self.assertEqual(par_nom['acces_module']['motif_omission'], '')

    def test_sur_la_fixture_reelle_la_perte_de_direct_est_lisible(self):
        serie = serie_de(AVEC_COMPOSANTES, composantes=True)
        rendue, etape = acces_module.appliquer(serie, contexte_de([0.8, 0.6]))
        self.assertEqual(etape['motif_omission'], '')
        self.assertAlmostEqual(somme(rendue, 'gb_i_w_m2'),
                               somme(serie, 'gb_i_w_m2') * 0.7, places=6)
