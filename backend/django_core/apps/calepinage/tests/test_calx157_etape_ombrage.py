# -*- coding: utf-8 -*-
"""CALX157 — la matrice 12×24 s'applique HEURE PAR HEURE, ou pas du tout.

CE QUI EST PROUVÉ ICI
---------------------
1. **Une matrice pleine de 1 ne coûte RIEN** : 0,0 % exactement, sur une
   réponse PVGIS réelle.
2. **Une ombre de nuit ne coûte rien non plus** : mettre à 0 les heures où
   le direct est nul ne retire pas un watt — c'est la preuve que la matrice
   est lue HEURE PAR HEURE et non moyennée sur l'année.
3. **Une matrice de mauvaise forme est refusée EN BLOC**, en nommant la
   forme (11 lignes) ou la case fautive — jamais complétée, jamais réparée.
4. **Matrice absente ⇒ étape omise**, jamais un facteur 1 supposé.
5. **L'exclusivité D-CALX 16 tient** : une lecture d'accès solaire module
   par module écarte la matrice, sans quoi l'ombre serait comptée deux fois.
6. **Le diffus et le réfléchi ne sont pas masqués** : une cellule à l'ombre
   d'un obstacle proche voit encore le ciel.

Aucune base de données, aucun réseau : ``SimpleTestCase`` et la réponse
PVGIS v5_3 RÉELLE enregistrée le 21/09/2026.

Run :
    python manage.py test apps.calepinage.tests.test_calx157_etape_ombrage
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import LIBELLES, appliquer_chaine
from apps.calepinage.services.etapes import ombrage_proche
from apps.calepinage.services.pvgis_serie import (
    MOTIF_COMPOSANTES_ABSENTES, ClientPvgis, _Cache)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
AVEC_COMPOSANTES = 'seriescalc_casablanca_sud_composantes.json'
SANS_COMPOSANTES = 'seriescalc_casablanca_sud_irradiance.json'

#: Les heures où la fixture ne porte AUCUN direct, tous mois confondus
#: (mesuré sur la réponse : le direct maximal y vaut 0,0 W/m²).
HEURES_DE_NUIT = tuple(range(0, 6)) + tuple(range(19, 24))


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


def matrice(facteur=1.0):
    return [[facteur] * 24 for _mois in range(12)]


def contexte_de(brute, cle='shading12x24'):
    return {'ombrage': {cle: brute}} if brute is not None else {'ombrage': {}}


def somme(serie, colonne):
    return sum(point[colonne] or 0.0 for point in serie['points'])


class MatriceNeutreTest(SimpleTestCase):
    """Plein soleil partout : 0,0 %, pas « presque 0 »."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_une_matrice_pleine_de_un_ne_coute_rien(self):
        rendue, etape = ombrage_proche.appliquer(
            self.serie, contexte_de(matrice(1.0)))
        self.assertEqual(etape['motif_omission'], '')
        for colonne in ('gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2', 'gi_w_m2'):
            self.assertAlmostEqual(somme(rendue, colonne),
                                   somme(self.serie, colonne), places=6,
                                   msg=colonne)
        self.assertEqual(etape['entree']['cases_ombrees'], 0)
        self.assertEqual(etape['entree']['heures_ombrees'], 0)

    def test_une_ombre_de_nuit_ne_coute_rien(self):
        nuit = matrice(1.0)
        for ligne in nuit:
            for heure in HEURES_DE_NUIT:
                ligne[heure] = 0.0
        rendue, etape = ombrage_proche.appliquer(
            self.serie, contexte_de(nuit))
        self.assertEqual(etape['motif_omission'], '')
        self.assertAlmostEqual(somme(rendue, 'gb_i_w_m2'),
                               somme(self.serie, 'gb_i_w_m2'), places=9)
        self.assertEqual(etape['entree']['heures_ombrees'], 0,
                         'aucune heure ensoleillée n’est ombrée : la '
                         'matrice est bien lue heure par heure.')
        self.assertEqual(etape['entree']['cases_ombrees'],
                         12 * len(HEURES_DE_NUIT))

    def test_la_serie_d_entree_n_est_jamais_modifiee(self):
        empreinte = json.dumps(self.serie, sort_keys=True)
        ombrage_proche.appliquer(self.serie, contexte_de(matrice(0.4)))
        self.assertEqual(json.dumps(self.serie, sort_keys=True), empreinte,
                         'une étape est PURE : elle copie, elle ne mute pas.')

    def test_le_libelle_est_celui_que_l_ordre_declare(self):
        _rendue, etape = ombrage_proche.appliquer(
            self.serie, contexte_de(matrice(1.0)))
        self.assertEqual(etape['libelle'], LIBELLES['ombrage_proche'])


class OmbreAppliqueeTest(SimpleTestCase):
    """L'ombre porte sur le DIRECT de son heure, et sur lui seul."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_un_demi_facteur_partout_coupe_la_moitie_du_direct(self):
        rendue, _etape = ombrage_proche.appliquer(
            self.serie, contexte_de(matrice(0.5)))
        self.assertAlmostEqual(somme(rendue, 'gb_i_w_m2'),
                               somme(self.serie, 'gb_i_w_m2') / 2.0,
                               places=6)

    def test_le_diffus_et_le_reflechi_ne_sont_pas_masques(self):
        rendue, _etape = ombrage_proche.appliquer(
            self.serie, contexte_de(matrice(0.0)))
        for colonne in ('gd_i_w_m2', 'gr_i_w_m2'):
            self.assertAlmostEqual(somme(rendue, colonne),
                                   somme(self.serie, colonne), places=6,
                                   msg=colonne)
        self.assertEqual(somme(rendue, 'gb_i_w_m2'), 0.0)

    def test_une_ombre_de_janvier_ne_touche_pas_juillet(self):
        janvier = matrice(1.0)
        janvier[0] = [0.0] * 24
        rendue, _etape = ombrage_proche.appliquer(
            self.serie, contexte_de(janvier))
        par_mois = {}
        for avant, apres in zip(self.serie['points'], rendue['points']):
            par_mois.setdefault(avant['mois'], [0.0, 0.0])
            par_mois[avant['mois']][0] += avant['gb_i_w_m2']
            par_mois[avant['mois']][1] += apres['gb_i_w_m2']
        self.assertEqual(par_mois[1][1], 0.0)
        for mois in range(2, 13):
            self.assertAlmostEqual(par_mois[mois][1], par_mois[mois][0],
                                   places=9, msg=f'mois {mois}')

    def test_les_deux_autres_ecritures_de_la_matrice_sont_lues(self):
        for cle in ('matrice_12x24', 'matrice'):
            _rendue, etape = ombrage_proche.appliquer(
                self.serie, contexte_de(matrice(0.8), cle=cle))
            self.assertEqual(etape['motif_omission'], '', cle)


class MatriceRefuseeTest(SimpleTestCase):
    """Une matrice à moitié fausse est refusée EN BLOC, et nommée."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def _refus(self, brute):
        rendue, etape = ombrage_proche.appliquer(
            self.serie, contexte_de(brute))
        self.assertIs(rendue, self.serie)
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['source'])
        return etape['motif_omission']

    def test_onze_lignes_sont_refusees_en_nommant_la_forme(self):
        motif = self._refus(matrice(1.0)[:11])
        self.assertIn('11 ligne(s)', motif)
        self.assertIn('12 mois', motif)
        self.assertIn('refusée en bloc', motif)

    def test_une_ligne_de_vingt_trois_heures_est_nommee(self):
        brute = matrice(1.0)
        brute[4] = [1.0] * 23
        motif = self._refus(brute)
        self.assertIn('ligne n°5', motif)
        self.assertIn('23 heure(s)', motif)

    def test_une_case_hors_de_zero_un_est_nommee(self):
        brute = matrice(1.0)
        brute[2][15] = 1.4
        motif = self._refus(brute)
        self.assertIn('mois 3, heure 15', motif)

    def test_une_case_illisible_est_nommee(self):
        brute = matrice(1.0)
        brute[11][0] = 'plein soleil'
        motif = self._refus(brute)
        self.assertIn('mois 12, heure 0', motif)

    def test_une_matrice_qui_n_est_pas_une_liste_est_refusee(self):
        motif = self._refus({'janvier': [1.0] * 24})
        self.assertIn('refusée en bloc', motif)


class EntreeManquanteTest(SimpleTestCase):
    """Chaque absence est NOMMÉE — jamais un facteur 1 supposé."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_sans_matrice_l_etape_nomme_le_champ(self):
        rendue, etape = ombrage_proche.appliquer(self.serie, {'ombrage': {}})
        self.assertIs(rendue, self.serie)
        self.assertIn('ombrage.shading12x24', etape['motif_omission'])
        self.assertIn('aucune ombre, vérifié', etape['motif_omission'])

    def test_sans_composantes_le_motif_est_celui_de_calx152(self):
        serie = serie_de(SANS_COMPOSANTES, composantes=False)
        _rendue, etape = ombrage_proche.appliquer(
            serie, contexte_de(matrice(0.5)))
        self.assertEqual(etape['motif_omission'], MOTIF_COMPOSANTES_ABSENTES)

    def test_une_serie_sans_mois_ni_heure_est_nommee(self):
        serie = {'pas_minutes': 60,
                 'points': [{'gb_i_w_m2': 100.0, 'gd_i_w_m2': 10.0,
                             'gr_i_w_m2': 5.0, 'gi_w_m2': 115.0}]}
        _rendue, etape = ombrage_proche.appliquer(
            serie, contexte_de(matrice(0.5)))
        self.assertIn('serie.points[].heure', etape['motif_omission'])

    def test_l_acces_par_module_ecarte_la_matrice(self):
        contexte = contexte_de(matrice(0.2))
        contexte['ombrage']['solar_access'] = {'values': [0.9]}
        rendue, etape = ombrage_proche.appliquer(self.serie, contexte)
        self.assertIs(rendue, self.serie)
        self.assertIn('module par module', etape['motif_omission'].lower())


class DansLaChaineTest(SimpleTestCase):
    """Vue par l'ordonnanceur : le contrat cascade tient."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_l_etape_appliquee_porte_les_douze_champs(self):
        _rendue, cascade = appliquer_chaine(self.serie,
                                            contexte_de(matrice(0.6)))
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'ombrage_proche')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['etape'], 'ombrage_proche')
        self.assertEqual(etape['libelle'], LIBELLES['ombrage_proche'])
        self.assertEqual(etape['source'], 'document')
        self.assertFalse(etape['gain'])

    def test_l_exclusivite_de_l_ordonnanceur_prime(self):
        contexte = contexte_de(matrice(0.6))
        contexte['ombrage']['solar_access'] = {'values': [0.5]}
        _rendue, cascade = appliquer_chaine(self.serie, contexte)
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'ombrage_proche')
        self.assertIn('module par module', etape['motif_omission'].lower())
        self.assertIsNone(etape['perte_pct'])


class ColonneEnergieTest(SimpleTestCase):
    """Quand la série porte déjà une puissance, elle suit le même rapport."""

    def test_la_puissance_suit_l_irradiance_heure_par_heure(self):
        serie = {
            'pas_minutes': 60,
            'points': [
                {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
                 'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
                 'gi_w_m2': 1000.0, 'p_w': 1000.0},
            ],
        }
        brute = matrice(1.0)
        brute[5][12] = 0.5
        rendue, etape = ombrage_proche.appliquer(serie, contexte_de(brute))
        self.assertEqual(etape['motif_omission'], '')
        point = rendue['points'][0]
        self.assertEqual(point['gb_i_w_m2'], 400.0)
        self.assertEqual(point['gi_w_m2'], 600.0)
        self.assertEqual(point['p_w'], 600.0)
        self.assertEqual(etapes.energie_kwh(rendue), 0.6)
