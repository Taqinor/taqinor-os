# -*- coding: utf-8 -*-
"""ACAL723 — l'étape « optimiseur » : le rendement de la fiche, sur les seuls
modules équipés.

Attendus recalculés À LA MAIN : perte = part d'énergie des modules équipés ×
(100 − rendement) ; part = Σ poids des équipés / Σ poids de tous, le poids
étant l'accès solaire quand il est lu pour tous les modules, sinon 1.

Aucune base de données : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_etape_optimiseur
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import (
    EXCLUSIVITES, appliquer_chaine, completude_de_la_chaine,
)
from apps.calepinage.services.etapes import optimiseur

SERIE = {
    'pas_minutes': 60, 'colonne_energie': 'p_w',
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0, 'p_w': 4000.0},
    ],
}
FICHE = {'rendement_pct': 99.0}


def contexte_de(equipes, *, acces=None, fiche=FICHE, global_=False):
    """Un pan, ses modules câblés, ``equipes`` = drapeau par module (True /
    False / None) ; ``acces`` = accès solaire par module (None = non lu)."""
    lignes = []
    for rang, drapeau in enumerate(equipes, start=1):
        ligne = {'module': 'PAN-A#%d' % rang, 'pan': 'PAN-A', 'chaine': 1,
                 'onduleur': 1, 'mppt': 1}
        if drapeau is not None:
            ligne['optimiseur'] = drapeau
        lignes.append(ligne)
    contexte = {'affectation': lignes}
    if fiche is not None:
        contexte['fiche_optimiseur'] = fiche if (global_ or fiche) else None
    if acces is not None:
        contexte['ombrage'] = {'layout': {'zones': [{
            'id': 'PAN-A', 'label': 'PAN-A', 'geometry': {
                'solarAccess': {'values': list(acces)}}}]}}
    return contexte


class PerteDesModulesEquipes(SimpleTestCase):
    def test_deux_modules_sur_dix_a_99_pour_cent_retirent_0_20(self):
        # 2/10 × (100 − 99) = 0,20 %.
        drapeaux = [True, True] + [False] * 8
        serie, etape = optimiseur.appliquer(
            SERIE, contexte_de(drapeaux, acces=[1.0] * 10))
        self.assertEqual(etape['motif_omission'], '')
        entree = etape['entree']
        self.assertEqual((entree['modules_equipes'], entree['modules']),
                         (2, 10))
        attendu_pct = 2 / 10 * (100 - 99.0)
        self.assertAlmostEqual(entree['perte_pct'], attendu_pct, 6)
        self.assertEqual(entree['ponderation'], 'accès solaire')
        self.assertEqual(entree['rendement_pct'], 99.0)
        self.assertEqual(etape['source'], 'fiche')
        self.assertAlmostEqual(serie['points'][0]['p_w'], 4000 * 0.998, 6)

    def test_ponderation_par_l_acces_solaire(self):
        # deux équipés à 0,5 et huit à 1,0 : 1,0 / (1,0 + 8,0) = 0,1111 ;
        # perte 0,1111 × 1,0 = 0,1111 %.
        drapeaux = [True, True] + [False] * 8
        _, etape = optimiseur.appliquer(
            SERIE, contexte_de(drapeaux, acces=[0.5, 0.5] + [1.0] * 8))
        self.assertAlmostEqual(etape['entree']['part_energie'], 1 / 9, 5)
        self.assertAlmostEqual(etape['entree']['perte_pct'], 0.1111, 4)

    def test_sans_acces_lu_les_effectifs_comptent(self):
        _, etape = optimiseur.appliquer(
            SERIE, contexte_de([True, False, False, False]))
        self.assertEqual(etape['entree']['ponderation'], 'effectifs')
        self.assertAlmostEqual(etape['entree']['perte_pct'], 0.25, 6)

    def test_produit_du_document_sans_drapeau_equipe_tous_les_modules(self):
        # 4 modules sans drapeau : 4/4 × 1,0 = 1,0 % ; l'un dit « false » :
        # 3/4 × 1,0 = 0,75 %.
        _, tous = optimiseur.appliquer(
            SERIE, contexte_de([None, None, None, None]))
        self.assertAlmostEqual(tous['entree']['perte_pct'], 1.0, 6)
        _, sauf_un = optimiseur.appliquer(
            SERIE, contexte_de([None, None, None, False]))
        self.assertAlmostEqual(sauf_un['entree']['perte_pct'], 0.75, 6)

    def test_le_rendement_ne_s_applique_pas_au_pan_entier(self):
        # mutant « appliquer le rendement à tous » : 1,0 % au lieu de 0,25 %.
        serie, _ = optimiseur.appliquer(
            SERIE, contexte_de([True, False, False, False]))
        self.assertGreater(serie['points'][0]['p_w'], 4000 * 0.995)


class Omissions(SimpleTestCase):
    def test_aucun_optimiseur_omis_et_non_compte(self):
        contexte = contexte_de([False, False], fiche=None)
        self.assertFalse(optimiseur.optimiseur_declare(contexte))
        _, cascade = appliquer_chaine(SERIE, contexte)
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'optimiseur')
        self.assertEqual(etape['motif_omission'],
                         EXCLUSIVITES['optimiseur'][1])
        self.assertIsNone(etape['perte_pct'])
        self.assertNotIn('optimiseur', completude_de_la_chaine(
            cascade, contexte)['non_renseignees'])

    def test_sans_rendement_omis_en_nommant_le_champ_et_compte(self):
        contexte = contexte_de([True, False], fiche={'rendement_pct': None},
                               global_=True)
        _, etape = optimiseur.appliquer(SERIE, contexte)
        self.assertIn('FicheTechnique.opt_rendement_pct',
                      etape['motif_omission'])
        _, cascade = appliquer_chaine(SERIE, contexte)
        self.assertIn('optimiseur', completude_de_la_chaine(
            cascade, contexte)['non_renseignees'])

    def test_marque_sans_produit_omis_en_nommant_le_rendement(self):
        _, etape = optimiseur.appliquer(
            SERIE, contexte_de([True, False], fiche=None))
        self.assertIn('FicheTechnique.opt_rendement_pct',
                      etape['motif_omission'])
