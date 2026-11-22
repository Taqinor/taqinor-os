# -*- coding: utf-8 -*-
"""ACAL722 — l'étape « diodes » : la dispersion d'ombrage affinée par bande.

Toutes les valeurs attendues sont RECALCULÉES À LA MAIN (jamais copiées de la
sortie du code) à partir de la règle :
    linéaire par bande = Σ bandes / n ; série = nb_bandes × min / n ;
    dérivation = max(Σ bandes ≥ seuil / n ; série) ;
    affiné = linéaire_chaîne × dérivation / linéaire_bandes, BORNÉ entre le
    courant série et la dérivation de la chaîne (bornes d'ACAL711).

Aucune base de données : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_etape_diodes
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import (
    EXCLUSIVITES, TOUJOURS_OMISES, appliquer_chaine,
    completude_de_la_chaine,
)
from apps.calepinage.services.etapes import diodes, mismatch_ombrage

METHODE = {'horizon': False, 'rangees': False, 'nom': 'shadingEngine roofPro11'}
SERIE = {
    'pas_minutes': 60, 'colonne_energie': 'p_w',
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0, 'p_w': 4000.0},
    ],
}
SEUIL = {'valeur': 0.6, 'source': 'societe', 'reference': 'Réglage d\'essai'}


def moyenne(bandes):
    return sum(bandes) / len(bandes)


def contexte_de(bandes_par_module, *, n=3, seuil=SEUIL, valeurs=None,
                avec_bandes=True):
    """Une chaîne de modules ; l'accès par module = moyenne de ses bandes,
    sauf ``valeurs`` donné."""
    valeurs = valeurs or [moyenne(b) for b in bandes_par_module]
    acces = {'values': list(valeurs), 'method': dict(METHODE)}
    if avec_bandes:
        acces['bandes'] = [list(b) for b in bandes_par_module]
    return {
        'affectation': [
            {'module': 'PAN-A#%d' % rang, 'pan': 'PAN-A', 'chaine': 1,
             'onduleur': 1, 'mppt': 1, 'source': 'automatique'}
            for rang in range(1, len(bandes_par_module) + 1)],
        'ombrage': {'layout': {'zones': [{
            'id': 'PAN-A', 'label': 'PAN-A',
            'geometry': {'solarAccess': acces}}]}},
        'reglages_simulation': ({} if seuil is None
                                else {mismatch_ombrage.CLE_REGLAGE: seuil}),
        'fiche_module': ({} if n is None
                         else {'sous_chaines_par_module': n}),
    }


class ChaineAffineeParBande(SimpleTestCase):
    def test_exemple_a_trois_bandes_rend_9_09_pour_cent(self):
        # 5,5/3 = 1,8333 linéaire ; dérivation max(5/3 ; 6 × 0,5/3 = 1,0) =
        # 1,6667 ; borne haute (courant série) 2 × 0,8333 = 1,6667 ;
        # excédent = (1,8333 − 1,6667) / 1,8333 = 9,0909 %.
        serie, etape = diodes.appliquer(
            SERIE, contexte_de([[1, 1, 1], [1, 1, 0.5]]))
        self.assertEqual(etape['motif_omission'], '')
        entree = etape['entree']
        self.assertEqual(entree['granularite'], 'bande')
        self.assertEqual(entree['sous_chaines_par_module'], 3)
        self.assertAlmostEqual(entree['excedent_par_bande_pct'], 9.0909, 3)
        self.assertAlmostEqual(entree['bornes']['basse']['excedent_pct'], 0.0)
        self.assertAlmostEqual(entree['bornes']['haute']['excedent_pct'],
                               9.0909, 3)
        self.assertAlmostEqual(entree['facteur_applique'], 0.909091, 5)
        self.assertEqual(etape['source'], 'fiche')
        self.assertTrue(etape['reference'])
        self.assertAlmostEqual(serie['points'][0]['p_w'], 4000 * 10 / 11, 2)

    def test_bande_a_0_9_ne_coute_rien(self):
        # 5,9/3 = 1,9667 linéaire ; série 6 × 0,9/3 = 1,8 ; dérivation
        # max(1,9667 ; 1,8) = 1,9667 : excédent nul.
        serie, etape = diodes.appliquer(
            SERIE, contexte_de([[1, 1, 1], [1, 1, 0.9]]))
        self.assertEqual(etape['motif_omission'], '')
        self.assertAlmostEqual(etape['entree']['excedent_par_bande_pct'], 0.0)
        self.assertAlmostEqual(serie['points'][0]['p_w'], 4000.0)

    def test_deux_bandes_sous_le_seuil(self):
        # bandes 1,1,1 / 0,5,0,5,1 : linéaire 5/3 ; série 6 × 0,5/3 = 1,0 ;
        # dérivation max(4/3 ; 1,0) = 1,3333 ; chaîne : linéaire 1,6667,
        # courant série 2 × 0,6667 = 1,3333 ⇒ affiné 1,3333 (= borne haute),
        # excédent 20 %.
        _, etape = diodes.appliquer(
            SERIE, contexte_de([[1, 1, 1], [0.5, 0.5, 1]]))
        self.assertAlmostEqual(etape['entree']['excedent_par_bande_pct'], 20.0)
        self.assertAlmostEqual(
            etape['entree']['bornes']['haute']['excedent_pct'], 20.0)

    def test_jamais_au_dela_de_la_borne_haute(self):
        # Le document dit accès 1,0 / 1,0 par module (bornes à 0 %), alors
        # que les bandes diraient 9,09 % : le résultat est BORNÉ à 0 %.
        serie, etape = diodes.appliquer(SERIE, contexte_de(
            [[1, 1, 1], [1, 1, 0.5]], valeurs=[1.0, 1.0]))
        self.assertEqual(etape['motif_omission'], '')
        self.assertAlmostEqual(etape['entree']['excedent_par_bande_pct'], 0.0)
        self.assertTrue(etape['entree']['chaines'][0]['bornee'])
        self.assertAlmostEqual(serie['points'][0]['p_w'], 4000.0)

    def test_nombre_de_bandes_different_de_la_fiche_n_est_pas_affine(self):
        _, etape = diodes.appliquer(
            SERIE, contexte_de([[1, 1, 1], [1, 1, 0.5]], n=2))
        self.assertIn(diodes.MOTIF_AUCUNE_CHAINE_AFFINEE,
                      etape['motif_omission'])
        self.assertIsNone(etape['source'])


class SansDonnees(SimpleTestCase):
    def test_sans_fiche_ou_sans_bandes_omise_et_non_comptee(self):
        cas = {
            'sans sous-chaînes': contexte_de([[1, 1, 1], [1, 1, 0.5]], n=None),
            'sans bandes': contexte_de([[1, 1, 1], [1, 1, 0.5]],
                                       avec_bandes=False),
        }
        for nom, contexte in cas.items():
            with self.subTest(nom):
                self.assertTrue(diodes.sans_donnees(contexte))
                _, cascade = appliquer_chaine(SERIE, contexte)
                etape = next(e for e in cascade['etapes']
                             if e['etape'] == 'diodes')
                self.assertEqual(etape['motif_omission'],
                                 EXCLUSIVITES['diodes'][1])
                self.assertIsNone(etape['perte_pct'])
                completude = completude_de_la_chaine(cascade, contexte)
                self.assertNotIn('diodes', completude['non_renseignees'])

    def test_diodes_n_est_plus_toujours_omise(self):
        self.assertNotIn('diodes', TOUJOURS_OMISES)

    def test_sans_seuil_omise_en_le_nommant_et_comptee(self):
        contexte = contexte_de([[1, 1, 1], [1, 1, 0.5]], seuil=None)
        _, etape = diodes.appliquer(SERIE, contexte)
        self.assertIn('seuil_derivation_acces', etape['motif_omission'])
        _, cascade = appliquer_chaine(SERIE, contexte)
        self.assertIn('diodes', completude_de_la_chaine(
            cascade, contexte)['non_renseignees'])

    def test_dans_la_cascade_la_perte_est_celle_de_l_exemple(self):
        contexte = contexte_de([[1, 1, 1], [1, 1, 0.5]])
        _, cascade = appliquer_chaine(SERIE, contexte)
        etape = next(e for e in cascade['etapes'] if e['etape'] == 'diodes')
        self.assertEqual(etape['motif_omission'], '')
        self.assertAlmostEqual(etape['perte_pct'], 9.09, 1)
