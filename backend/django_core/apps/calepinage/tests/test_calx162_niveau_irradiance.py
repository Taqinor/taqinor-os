"""CALX162 — l'étape « niveau d'irradiance » lit la courbe, ou se tait.

Aucune base de données, aucun réseau : une série de quatre heures, un
contexte minimal, et la vraie chaîne (``appliquer_chaine``) — c'est ce que
la simulation verra en production.

Run :
    python manage.py test apps.calepinage.tests.test_calx162_niveau_irradiance
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import niveau_irradiance

ETAPE = 'niveau_irradiance'

#: Quatre heures, quatre niveaux d'éclairement : 100, 400, 800 et 1200 W/m².
#: La dernière est VOLONTAIREMENT au-delà du dernier point des courbes
#: d'essai — c'est le cas « pas d'extrapolation » de la tâche.
SERIE = {
    'pas_minutes': 60,
    'points': [
        {'heure': 7, 'gi_w_m2': 100.0, 'p_w': 500.0},
        {'heure': 10, 'gi_w_m2': 400.0, 'p_w': 2000.0},
        {'heure': 13, 'gi_w_m2': 800.0, 'p_w': 4000.0},
        {'heure': 16, 'gi_w_m2': 1200.0, 'p_w': 6000.0},
    ],
}

#: Une courbe plate : 100 % du rendement STC à tous les niveaux publiés.
COURBE_PLATE = [
    {'w_m2': 100, 'rendement_relatif_pct': 100.0},
    {'w_m2': 500, 'rendement_relatif_pct': 100.0},
    {'w_m2': 1000, 'rendement_relatif_pct': 100.0},
]

#: Une courbe décroissante vers le bas de l'échelle, comme les fiches en
#: publient : le module rend moins sous faible éclairement.
COURBE_REELLE = [
    {'w_m2': 200, 'rendement_relatif_pct': 96.0},
    {'w_m2': 600, 'rendement_relatif_pct': 99.0},
    {'w_m2': 1000, 'rendement_relatif_pct': 100.0},
]


def cascade(contexte, serie=None):
    """L'étape TELLE QUE LA CHAÎNE la publie, douze champs compris."""
    _, bloc = appliquer_chaine(serie or SERIE, contexte)
    return next(e for e in bloc['etapes'] if e['etape'] == ETAPE)


def contexte_avec(courbe, produit='Module PV 550 Wc'):
    return {'fiche_module': {'rendement_par_irradiance': courbe},
            'designations': {'module': produit}}


class CourbeAbsenteTest(unittest.TestCase):
    """Sans courbe publiée, l'étape se TAIT — en nommant quoi saisir."""

    def test_le_motif_nomme_le_champ_et_le_produit(self):
        etape = cascade(contexte_avec(None))
        self.assertIn('FicheTechnique.rendement_par_irradiance',
                      etape['motif_omission'])
        self.assertIn('Module PV 550 Wc', etape['motif_omission'])

    def test_aucun_chiffre_n_est_publie(self):
        etape = cascade(contexte_avec(None))
        for champ in ('kwh_apres', 'perte_kwh', 'perte_pct', 'source',
                      'entree', 'reference'):
            self.assertIsNone(etape[champ], champ)

    def test_une_fiche_vide_nomme_le_module_retenu(self):
        etape = cascade({'fiche_module': {}})
        self.assertIn('le module retenu', etape['motif_omission'])
        self.assertIn('FicheTechnique.rendement_par_irradiance',
                      etape['motif_omission'])

    def test_un_contexte_sans_fiche_omet_aussi(self):
        self.assertIn('rendement_par_irradiance',
                      cascade({})['motif_omission'])

    def test_la_serie_ressort_inchangee(self):
        serie, _ = appliquer_chaine(SERIE, contexte_avec(None))
        self.assertEqual(etapes.energie_kwh(serie),
                         etapes.energie_kwh(SERIE))


class CourbePlateTest(unittest.TestCase):
    """Test de PROPRIÉTÉ : 100 % partout ⇒ exactement 0,0 % de perte."""

    def setUp(self):
        self.etape = cascade(contexte_avec(COURBE_PLATE))

    def test_l_etape_s_applique_et_nomme_sa_source(self):
        self.assertEqual(self.etape['motif_omission'], '')
        self.assertEqual(self.etape['source'], 'fiche')
        self.assertEqual(self.etape['entree'], 'rendement_par_irradiance')

    def test_la_perte_est_exactement_nulle(self):
        self.assertEqual(self.etape['perte_pct'], 0.0)
        self.assertEqual(self.etape['perte_kwh'], 0.0)
        self.assertEqual(self.etape['kwh_apres'], self.etape['kwh_avant'])

    def test_elle_ne_se_declare_pas_en_gain(self):
        self.assertFalse(self.etape['gain'])


class InterpolationTest(unittest.TestCase):
    """Entre deux points publiés, une droite — et rien d'autre."""

    def test_un_point_entre_deux_points_est_interpole(self):
        serie = {'pas_minutes': 60,
                 'points': [{'gi_w_m2': 400.0, 'p_w': 1000.0}]}
        suite, _ = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        # 400 W/m² : à mi-chemin de 200 (96 %) et 600 (99 %) ⇒ 97,5 %.
        self.assertAlmostEqual(etapes.energie_kwh(suite), 0.975, places=6)

    def test_un_point_publie_rend_sa_valeur_exacte(self):
        serie = {'pas_minutes': 60,
                 'points': [{'gi_w_m2': 600.0, 'p_w': 1000.0}]}
        suite, _ = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        self.assertAlmostEqual(etapes.energie_kwh(suite), 0.99, places=6)

    def test_la_serie_d_entree_n_est_jamais_modifiee_sur_place(self):
        avant = etapes.energie_kwh(SERIE)
        appliquer_chaine(SERIE, contexte_avec(COURBE_REELLE))
        self.assertEqual(etapes.energie_kwh(SERIE), avant)


class AucuneExtrapolationTest(unittest.TestCase):
    """Au-delà du dernier point, la dernière valeur — et l'étape le DIT."""

    def test_au_dela_du_dernier_point_la_derniere_valeur_est_retenue(self):
        serie = {'pas_minutes': 60,
                 'points': [{'gi_w_m2': 5000.0, 'p_w': 1000.0}]}
        suite, _ = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        # 100 % au dernier point publié (1000 W/m²) : la pente n'est PAS
        # prolongée au-delà de 100 %.
        self.assertAlmostEqual(etapes.energie_kwh(suite), 1.0, places=6)

    def test_en_deca_du_premier_point_la_premiere_valeur_est_retenue(self):
        serie = {'pas_minutes': 60,
                 'points': [{'gi_w_m2': 5.0, 'p_w': 1000.0}]}
        suite, _ = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        self.assertAlmostEqual(etapes.energie_kwh(suite), 0.96, places=6)

    def test_la_reference_dit_qu_aucune_extrapolation_n_a_eu_lieu(self):
        etape = cascade(contexte_avec(COURBE_REELLE))
        self.assertIn('Aucune extrapolation', etape['reference'])

    def test_la_reference_compte_les_heures_retenues_aux_bornes(self):
        etape = cascade(contexte_avec(COURBE_REELLE))
        # SERIE : 100 W/m² sous la borne basse, 1200 W/m² au-delà de la
        # borne haute — une heure de chaque côté, nommée.
        self.assertIn('1 heure(s) sous 200 W/m²', etape['reference'])
        self.assertIn('1 heure(s) au-delà de 1000 W/m²', etape['reference'])
        self.assertIn('96 %', etape['reference'])
        self.assertIn('100 %', etape['reference'])

    def test_la_reference_cite_pvsyst_sans_en_reprendre_le_modele(self):
        etape = cascade(contexte_avec(COURBE_REELLE))
        self.assertIn('PVsyst', etape['reference'])
        self.assertIn('pvsyst.com', etape['reference'])


class IrradianceIllisibleTest(unittest.TestCase):
    """Sans irradiance dans la série, la courbe ne se lit nulle part."""

    def test_aucune_irradiance_omet_l_etape_en_nommant_la_colonne(self):
        serie = {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]}
        _, bloc = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        etape = next(e for e in bloc['etapes'] if e['etape'] == ETAPE)
        self.assertIn('gi_w_m2', etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])

    def test_une_heure_sans_irradiance_ressort_inchangee_et_comptee(self):
        serie = {'pas_minutes': 60,
                 'points': [{'gi_w_m2': 1000.0, 'p_w': 1000.0},
                            {'p_w': 1000.0}]}
        suite, bloc = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        etape = next(e for e in bloc['etapes'] if e['etape'] == ETAPE)
        self.assertAlmostEqual(etapes.energie_kwh(suite), 2.0, places=6)
        self.assertIn('1 heure(s) sans irradiance lisible',
                      etape['reference'])

    def test_aucune_colonne_d_energie_omet_l_etape(self):
        serie = {'pas_minutes': 60, 'points': [{'gi_w_m2': 900.0}]}
        _, bloc = appliquer_chaine(serie, contexte_avec(COURBE_REELLE))
        etape = next(e for e in bloc['etapes'] if e['etape'] == ETAPE)
        self.assertIn('p_w', etape['motif_omission'])


class CourbeIllisibleTest(unittest.TestCase):
    """Une courbe qu'on ne sait pas lire n'est jamais rafistolée."""

    def test_un_point_sans_ses_deux_cles_nomme_son_rang(self):
        courbe = [{'w_m2': 200, 'rendement_relatif_pct': 96.0},
                  {'w_m2': 600}]
        etape = cascade(contexte_avec(courbe))
        self.assertIn('rang 1', etape['motif_omission'])
        self.assertIn('rendement_relatif_pct', etape['motif_omission'])

    def test_une_abscisse_non_croissante_nomme_son_rang(self):
        courbe = [{'w_m2': 600, 'rendement_relatif_pct': 99.0},
                  {'w_m2': 200, 'rendement_relatif_pct': 96.0}]
        etape = cascade(contexte_avec(courbe))
        self.assertIn('rang 1', etape['motif_omission'])
        self.assertIn('croissante', etape['motif_omission'])

    def test_une_courbe_vide_se_lit_comme_une_courbe_absente(self):
        self.assertIn('Aucune courbe',
                      cascade(contexte_avec([]))['motif_omission'])


class LectureDeLaFicheTest(unittest.TestCase):
    """La fiche se lit sous le nom que ``specs_for_produit`` publie."""

    def test_un_dict_de_specs_est_lu(self):
        self.assertEqual(
            niveau_irradiance._courbe_publiee(
                {'rendement_par_irradiance': COURBE_PLATE}),
            COURBE_PLATE)

    def test_un_objet_porteur_est_lu_aussi(self):
        class _Fiche:
            rendement_par_irradiance = COURBE_PLATE

        self.assertEqual(niveau_irradiance._courbe_publiee(_Fiche()),
                         COURBE_PLATE)

    def test_le_champ_lu_est_celui_que_calx60_publie(self):
        self.assertEqual(niveau_irradiance.CHAMP_COURBE,
                         'rendement_par_irradiance')


if __name__ == '__main__':
    unittest.main()
