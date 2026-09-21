"""CALX171 — la fenêtre MPPT compte les HEURES, pas les extrêmes.

Aucune base, aucun réseau. La colonne ``t_cell_c`` est posée à la main ici :
l'étape « thermique » (CALX163) l'écrit en production, et cette lane ne
dépend pas de son atterrissage pour être prouvée.

Run :
    python manage.py test apps.calepinage.tests.test_calx171_mppt
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import mppt

#: Cinq heures à 1 kW, avec leur température de cellule (chiffres d'essai).
#: Tension de chaîne : 10 modules × 40 V = 400 V au STC, dérive −0,40 %/°C.
#: T = 25 → 400 V ; 70 → 328 V ; 72 → 324,8 V ; 0 → 440 V ; 50 → 360 V.
SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_dc_kw',
    'points': [
        {'mois': 6, 'heure': 12, 'p_dc_kw': 1.0, 't_cell_c': 25.0},
        {'mois': 7, 'heure': 13, 'p_dc_kw': 1.0, 't_cell_c': 70.0},
        {'mois': 7, 'heure': 14, 'p_dc_kw': 1.0, 't_cell_c': 72.0},
        {'mois': 1, 'heure': 11, 'p_dc_kw': 1.0, 't_cell_c': 0.0},
        {'mois': 6, 'heure': 15, 'p_dc_kw': 1.0, 't_cell_c': 50.0},
    ],
}

FICHE_MODULE = {'vmp_v': 40.0, 'temp_coeff_pmax_pct_c': -0.40,
                'pmax_wc': 500.0}

#: Fenêtre ÉTROITE : deux heures chaudes sous la borne basse, une heure
#: froide au-dessus de la borne haute.
FENETRE_ETROITE = {'mppt_v_min': 350.0, 'mppt_v_max': 430.0,
                   'v_demarrage_v': 340.0}

#: Fenêtre LARGE : les cinq heures y tiennent.
FENETRE_LARGE = {'mppt_v_min': 300.0, 'mppt_v_max': 450.0,
                 'v_demarrage_v': 280.0}


def contexte(fenetre=None, fiche_module=None, **extras):
    base = {
        'fiche_module': dict(FICHE_MODULE if fiche_module is None
                             else fiche_module),
        'fiche_onduleur': dict(FENETRE_ETROITE if fenetre is None
                               else fenetre),
        'electrique': {'chainage': {'modules': 20,
                                    'modules_par_chaine': 10,
                                    'puissance_module_wc': 500.0}},
        'reglages_simulation': {},
        'postes_saisis': [],
    }
    base.update(extras)
    return base


class HeuresHorsPlageTest(unittest.TestCase):

    def setUp(self):
        self.serie, self.etape = mppt.appliquer(SERIE, contexte())
        self.entree = self.etape['entree']

    def test_l_etape_s_applique_et_cite_pvsol(self):
        self.assertEqual(self.etape['motif_omission'], '')
        self.assertEqual(self.etape['source'], 'fiche')
        self.assertIn('PV*SOL', self.etape['reference'])

    def test_les_trois_heures_hors_plage_sont_comptees(self):
        self.assertEqual(self.entree['heures_examinees'], 5)
        self.assertEqual(self.entree['heures_hors_plage'], 3)

    def test_les_heures_sous_le_demarrage_sont_comptees_a_part(self):
        self.assertEqual(self.entree['heures_sous_demarrage'], 2)

    def test_le_mois_le_plus_concerne_est_publie(self):
        self.assertEqual(self.entree['mois_le_plus_concerne'], 7)

    def test_l_energie_des_heures_hors_plage_est_retiree(self):
        self.assertEqual(etapes.energie_kwh(SERIE), 5.0)
        self.assertEqual(etapes.energie_kwh(self.serie), 2.0)

    def test_les_heures_dans_la_plage_sont_intactes(self):
        restantes = [p['p_dc_kw'] for p in self.serie['points']]
        self.assertEqual(restantes, [1.0, 0.0, 0.0, 0.0, 1.0])

    def test_les_tensions_extremes_sont_publiees(self):
        self.assertAlmostEqual(self.entree['tension_min_v'], 324.8, places=1)
        self.assertAlmostEqual(self.entree['tension_max_v'], 440.0, places=1)


class PlageElargieTest(unittest.TestCase):
    """Propriété : élargir la fenêtre ne peut que faire baisser le compte."""

    def test_le_compte_decroit_quand_la_plage_s_elargit(self):
        _, etroite = mppt.appliquer(SERIE, contexte())
        _, large = mppt.appliquer(SERIE, contexte(fenetre=FENETRE_LARGE))
        self.assertGreater(etroite['entree']['heures_hors_plage'],
                           large['entree']['heures_hors_plage'])
        self.assertEqual(large['entree']['heures_hors_plage'], 0)

    def test_une_chaine_entierement_dans_la_plage_rend_zero_pour_cent(self):
        _, cascade = appliquer_chaine(SERIE, contexte(fenetre=FENETRE_LARGE))
        ligne = _ligne(cascade, 'mppt')
        self.assertEqual(ligne['perte_pct'], 0.0)
        self.assertEqual(ligne['kwh_avant'], ligne['kwh_apres'])


class OmissionsNommeesTest(unittest.TestCase):

    def test_fiche_sans_coefficient_omet_l_etape_en_nommant_le_champ(self):
        """Le défaut −0,35 de la dataclass du noyau n'est PAS employé."""
        sans = {'vmp_v': 40.0, 'pmax_wc': 500.0}
        serie, etape = mppt.appliquer(SERIE,
                                      contexte(fiche_module=sans))
        self.assertIn(mppt.CHAMP_COEFFICIENT, etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 5.0)
        self.assertIsNone(etape['entree'])

    def test_serie_sans_temperature_omet_l_etape_en_nommant_la_colonne(self):
        nue = {'pas_minutes': 60, 'colonne_energie': 'p_dc_kw',
               'points': [{'mois': 6, 'heure': 12, 'p_dc_kw': 1.0}]}
        serie, etape = mppt.appliquer(nue, contexte())
        self.assertIn(mppt.COLONNE_TEMPERATURE, etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 1.0)

    def test_onduleur_sans_fenetre_omet_l_etape(self):
        _, etape = mppt.appliquer(
            SERIE, contexte(fenetre={'v_demarrage_v': 340.0}))
        self.assertIn('mppt_v_min', etape['motif_omission'])

    def test_sans_modules_par_chaine_l_etape_nomme_la_tension(self):
        _, etape = mppt.appliquer(
            SERIE, contexte(electrique={'chainage': {'modules': 20}}))
        self.assertIn('vmp_v', etape['motif_omission'])


def _ligne(cascade, nom):
    for etape in cascade['etapes']:
        if etape['etape'] == nom:
            return etape
    raise AssertionError('étape « %s » absente de la cascade' % nom)
