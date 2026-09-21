# -*- coding: utf-8 -*-
"""CALX179 — le ratio de performance au sens de la norme IEC 61724-1.

Aucune base, aucun réseau : trois heures (une d'hiver, une d'été, une de
nuit) suffisent à vérifier que le PR se referme sur l'énergie publiée, que
la période voyage avec lui, et que la variante corrigée en température se
TAIT quand la fiche ne permet rien.

Run :
    python manage.py test apps.calepinage.tests.test_calx179_pr
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import performance
from apps.calepinage.services.performance import bloc_performance

KWC = 10.0

#: Une heure d'hiver, une heure d'été, une heure de nuit. L'énergie est
#: DÉCLARÉE côté alternatif : un PR se calcule sur ce qui est livré.
POINTS = [
    {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12, 'p_ac_kw': 3.0,
     'gi_w_m2': 400.0, 't_cell_c': 30.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 13, 'p_ac_kw': 7.2,
     'gi_w_m2': 900.0, 't_cell_c': 52.0},
    {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 3, 'p_ac_kw': 0.0,
     'gi_w_m2': 0.0, 't_cell_c': 12.0},
]
SERIE = {'pas_minutes': 60, 'colonne_energie': 'p_ac_kw', 'points': POINTS}

FICHE = {'temp_coeff_pmax_pct_c': -0.34}

ENERGIE_KWH = 10.2
IRRADIATION_KWH_M2 = 1.3


def serie_sans(colonne):
    """La même série, une colonne retirée de chaque point."""
    points = [{cle: valeur for cle, valeur in point.items() if cle != colonne}
              for point in POINTS]
    return dict(SERIE, points=points)


class ProprieteTest(unittest.TestCase):
    """``pr × irradiation × kWc`` redonne l'énergie publiée."""

    def test_le_pr_se_referme_sur_l_energie_a_un_demi_pour_cent(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        reconstituee = (bloc['pr'] * bloc['irradiation_plan_kwh_m2'] * KWC)
        self.assertLessEqual(
            abs(reconstituee - ENERGIE_KWH) / ENERGIE_KWH, 0.005,
            f'{reconstituee} kWh reconstitués contre {ENERGIE_KWH} publiés.')

    def test_l_irradiation_publiee_est_celle_de_la_serie(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertAlmostEqual(bloc['irradiation_plan_kwh_m2'],
                               IRRADIATION_KWH_M2, places=6)

    def test_le_pr_vaut_le_rendement_final_sur_le_rendement_de_reference(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        attendu = (ENERGIE_KWH / KWC) / IRRADIATION_KWH_M2
        self.assertAlmostEqual(bloc['pr'], round(attendu, 4), places=4)

    def test_la_colonne_d_energie_lue_est_publiee(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertEqual(bloc['colonne_energie'], 'p_ac_kw')


class ReferenceTest(unittest.TestCase):
    """La chaîne de référence de la norme est publiée TELLE QUELLE."""

    def test_la_reference_est_publiee_mot_pour_mot(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertEqual(bloc['pr_reference'], performance.REFERENCE_IEC)

    def test_la_reference_nomme_la_norme_et_son_denominateur(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertIn('IEC 61724-1', bloc['pr_reference'])
        self.assertIn('1 000 W/m²', bloc['pr_reference'])

    def test_la_methode_est_nommee_et_non_sous_entendue(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertEqual(bloc['pr_methode'], 'iec_61724_1')
        self.assertEqual(bloc['pr_methode'], performance.METHODE)

    def test_sans_pr_ni_methode_ni_reference_ne_sont_publiees(self):
        bloc = bloc_performance(SERIE, kwc=None, fiche_module=FICHE)
        self.assertIsNone(bloc['pr'])
        self.assertIsNone(bloc['pr_methode'])
        self.assertIsNone(bloc['pr_reference'])


class PeriodeTest(unittest.TestCase):
    """Une période non annuelle est EXPLICITE."""

    def test_deux_mois_donnent_une_periode_partielle_nommee(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertIn('partielle', bloc['periode'])
        self.assertIn('janvier', bloc['periode'])
        self.assertIn('juillet', bloc['periode'])

    def test_douze_mois_sur_une_annee_sont_annuels(self):
        points = [{'annee': 2020, 'mois': mois, 'jour': 15, 'heure': 12,
                   'p_ac_kw': 5.0, 'gi_w_m2': 700.0, 't_cell_c': 40.0}
                  for mois in range(1, 13)]
        bloc = bloc_performance(dict(SERIE, points=points), kwc=KWC,
                                fiche_module=FICHE)
        self.assertEqual(bloc['periode'], performance.PERIODE_ANNUELLE)

    def test_douze_mois_sur_deux_annees_portent_leur_fenetre(self):
        points = []
        for annee in (2020, 2021):
            for mois in range(1, 13):
                points.append({'annee': annee, 'mois': mois, 'jour': 15,
                               'heure': 12, 'p_ac_kw': 5.0,
                               'gi_w_m2': 700.0, 't_cell_c': 40.0})
        bloc = bloc_performance(dict(SERIE, points=points), kwc=KWC,
                                fiche_module=FICHE)
        self.assertIn('pluriannuelle', bloc['periode'])
        self.assertIn('2020-2021', bloc['periode'])

    def test_une_serie_sans_mois_n_invente_aucune_periode(self):
        bloc = bloc_performance(serie_sans('mois'), kwc=KWC,
                                fiche_module=FICHE)
        self.assertIsNone(bloc['periode'])


class CorrectionTemperatureTest(unittest.TestCase):
    """Publiée SEULEMENT si l'étape thermique a tourné — sinon absente."""

    def test_le_pr_corrige_est_publie_quand_tout_est_la(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertIn('pr_corrige_temperature', bloc)
        self.assertGreater(bloc['pr_corrige_temperature'], bloc['pr'])
        self.assertEqual(bloc['motif_pr_corrige_temperature'], '')

    def test_la_temperature_moyenne_est_ponderee_par_l_irradiance(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        attendu = (30.0 * 400.0 + 52.0 * 900.0) / 1300.0
        self.assertAlmostEqual(bloc['t_cell_moyenne_ponderee_c'],
                               round(attendu, 2), places=2)

    def test_une_fiche_sans_coefficient_omet_la_cle_avec_sa_raison(self):
        bloc = bloc_performance(SERIE, kwc=KWC, fiche_module={})
        self.assertNotIn('pr_corrige_temperature', bloc)
        self.assertNotIn('t_cell_moyenne_ponderee_c', bloc)
        self.assertIn('temp_coeff_pmax_pct_c',
                      bloc['motif_pr_corrige_temperature'])
        self.assertIsNotNone(bloc['pr'])

    def test_une_fiche_absente_omet_la_cle_elle_aussi(self):
        bloc = bloc_performance(SERIE, kwc=KWC)
        self.assertNotIn('pr_corrige_temperature', bloc)
        self.assertTrue(bloc['motif_pr_corrige_temperature'])

    def test_sans_etape_thermique_la_cle_est_absente_et_nomme_la_colonne(self):
        bloc = bloc_performance(serie_sans('t_cell_c'), kwc=KWC,
                                fiche_module=FICHE)
        self.assertNotIn('pr_corrige_temperature', bloc)
        self.assertIn('t_cell_c', bloc['motif_pr_corrige_temperature'])
        self.assertIsNotNone(bloc['pr'])

    def test_une_seule_heure_sans_temperature_suffit_a_se_taire(self):
        points = [dict(point) for point in POINTS]
        points[1].pop('t_cell_c')
        bloc = bloc_performance(dict(SERIE, points=points), kwc=KWC,
                                fiche_module=FICHE)
        self.assertNotIn('pr_corrige_temperature', bloc)
        self.assertIn('1 heure(s)', bloc['motif_pr_corrige_temperature'])

    def test_une_heure_de_nuit_sans_temperature_ne_gene_pas(self):
        points = [dict(point) for point in POINTS]
        points[2].pop('t_cell_c')
        bloc = bloc_performance(dict(SERIE, points=points), kwc=KWC,
                                fiche_module=FICHE)
        self.assertIn('pr_corrige_temperature', bloc)


class SilenceTest(unittest.TestCase):
    """Rien d'inventé : un PR incalculable reste NUL, motivé."""

    def test_une_serie_vide_ne_publie_aucun_ratio(self):
        bloc = bloc_performance({'points': []}, kwc=KWC, fiche_module=FICHE)
        self.assertIsNone(bloc['pr'])
        self.assertTrue(bloc['motif'])
        self.assertNotIn('pr_corrige_temperature', bloc)

    def test_une_serie_sans_irradiance_nomme_la_colonne(self):
        bloc = bloc_performance(serie_sans('gi_w_m2'), kwc=KWC,
                                fiche_module=FICHE)
        self.assertIsNone(bloc['pr'])
        self.assertIn('gi_w_m2', bloc['motif'])

    def test_une_serie_sans_colonne_d_energie_reste_nulle_jamais_zero(self):
        points = [{'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12,
                   'gi_w_m2': 400.0}]
        bloc = bloc_performance(dict(SERIE, colonne_energie=None,
                                     points=points),
                                kwc=KWC, fiche_module=FICHE)
        self.assertIsNone(bloc['pr'])
        self.assertIsNone(bloc['colonne_energie'])
        self.assertTrue(bloc['motif'])

    def test_sans_puissance_cretes_le_ratio_se_tait_en_le_disant(self):
        bloc = bloc_performance(SERIE, kwc=0.0, fiche_module=FICHE)
        self.assertIsNone(bloc['pr'])
        self.assertIn('puissance crête', bloc['motif'])

    def test_la_serie_d_entree_n_est_jamais_modifiee(self):
        avant = [dict(point) for point in POINTS]
        bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        self.assertEqual(SERIE['points'], avant)

    def test_le_bloc_porte_toujours_les_cles_du_contrat(self):
        for bloc in (bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE),
                     bloc_performance({'points': []}, kwc=None)):
            with self.subTest(pr=bloc['pr']):
                for cle in ('pr', 'pr_methode', 'pr_reference',
                            'irradiation_plan_kwh_m2', 'periode'):
                    self.assertIn(cle, bloc)


class PasDeTempsTest(unittest.TestCase):
    """Le pas de la série entre dans les deux termes, jamais dans un seul."""

    def test_un_pas_de_quinze_minutes_ne_change_pas_le_ratio(self):
        horaire = bloc_performance(SERIE, kwc=KWC, fiche_module=FICHE)
        quart = bloc_performance(dict(SERIE, pas_minutes=15), kwc=KWC,
                                 fiche_module=FICHE)
        self.assertAlmostEqual(horaire['pr'], quart['pr'], places=4)
        self.assertAlmostEqual(
            quart['irradiation_plan_kwh_m2'],
            round(IRRADIATION_KWH_M2 / 4.0, 3), places=6)
