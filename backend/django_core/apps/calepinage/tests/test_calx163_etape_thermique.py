"""CALX163 — l'étape « thermique » chauffe par type de POSE, heure par heure.

Aucune base, aucun réseau : une série de quatre heures, une fiche produit et
une table société en dur dans le fichier — exactement ce que la chaîne verra.

Run :
    python manage.py test apps.calepinage.tests.test_calx163_etape_thermique
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    CLES_ETAPE_PUBLIEE, appliquer_chaine)
from apps.calepinage.services.etapes import thermique as etape_thermique
from apps.calepinage.services.thermique import perte_thermique

GAMMA = -0.35

#: Quatre heures de juillet : une nuit et trois heures ensoleillées.
POINTS = [
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 3, 'p_w': 0.0,
     'gi_w_m2': 0.0, 't2m_c': 21.0, 'ws10m': 1.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 10, 'p_w': 3000.0,
     'gi_w_m2': 700.0, 't2m_c': 30.0, 'ws10m': 2.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 12, 'p_w': 4000.0,
     'gi_w_m2': 950.0, 't2m_c': 35.0, 'ws10m': 1.5},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 16, 'p_w': 2000.0,
     'gi_w_m2': 450.0, 't2m_c': 33.0, 'ws10m': 3.0},
]
SERIE = {'pas_minutes': 60, 'points': POINTS}

FICHE_COMPLETE = {
    'temp_coeff_pmax_pct_c': GAMMA,
    'uc_w_m2k': 29.0,
    'uv_w_m3sk': 0.0,
    'noct_c': 45.0,
}
FICHE_NOCT_SEULE = {'temp_coeff_pmax_pct_c': GAMMA, 'noct_c': 45.0}


def reglage_pose(table):
    """La section « simulation » telle que CALX145 la persiste."""
    return {'thermique_par_pose': {'valeur': table, 'source': 'societe',
                                   'reference': 'Table société'}}


TABLE_SOCIETE = {
    # Une toiture intégrée non ventilée échange MOINS bien : Uc plus faible,
    # donc cellule plus chaude que le même pan relevé sur châssis.
    'integre': {'uc_w_m2k': 20.0, 'uv_w_m3sk': 0.0, 'source': 'texte',
                'reference': 'PV*SOL — Module temperature'},
    'chassis': {'uc_w_m2k': 29.0, 'uv_w_m3sk': 1.2, 'source': 'texte',
                'reference': 'PVsyst — Array thermal losses'},
}


def contexte_de(*, fiche=None, table=None, plans=None):
    contexte = {'fiche_module': dict(fiche or {})}
    if table is not None:
        contexte['reglages_simulation'] = reglage_pose(table)
    if plans is not None:
        contexte['plans'] = plans
    return contexte


def plan(cle='A', **extra):
    base = {'cle': cle, 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0}
    base.update(extra)
    return base


class OmissionTest(unittest.TestCase):
    """Fiche nue, société muette : l'étape se TAIT, et dit quoi saisir."""

    def test_fiche_nue_et_societe_muette_omettent_l_etape(self):
        _, etape = etape_thermique.appliquer(SERIE, contexte_de())
        self.assertTrue(etape['motif_omission'])
        self.assertIn('thermique', etape['motif_omission'])
        self.assertIsNone(etape['source'])

    def test_la_serie_ressort_intacte_quand_l_etape_s_omet(self):
        rendue, etape = etape_thermique.appliquer(SERIE, contexte_de())
        self.assertTrue(etape['motif_omission'])
        self.assertIs(rendue, SERIE)
        self.assertEqual(etapes.energie_kwh(rendue), 9.0)

    def test_le_motif_de_thermique_py_est_publie_tel_quel(self):
        _, etape = etape_thermique.appliquer(SERIE, contexte_de())
        attendu = perte_thermique({}, POINTS)['motif']
        self.assertTrue(etape['motif_omission'].startswith(attendu),
                        etape['motif_omission'])

    def test_le_coefficient_de_puissance_manquant_est_nomme(self):
        _, etape = etape_thermique.appliquer(
            SERIE, contexte_de(fiche={'uc_w_m2k': 29.0}))
        self.assertIn('temp_coeff_pmax_pct_c', etape['motif_omission'])

    def test_sans_uc_ni_noct_les_trois_entrees_possibles_sont_nommees(self):
        _, etape = etape_thermique.appliquer(
            SERIE, contexte_de(fiche={'temp_coeff_pmax_pct_c': GAMMA}))
        self.assertIn('thermique_par_pose', etape['motif_omission'])
        self.assertIn('uc_w_m2k', etape['motif_omission'])
        self.assertIn('noct_c', etape['motif_omission'])

    def test_une_etape_omise_ne_publie_aucun_chiffre(self):
        _, etape = etape_thermique.appliquer(SERIE, contexte_de())
        self.assertIsNone(etape['entree'])
        self.assertIsNone(etape['reference'])
        self.assertFalse(etape['gain'])

    def test_le_module_n_emploie_jamais_de_forfait(self):
        with open(etape_thermique.__file__, encoding='utf-8') as fichier:
            code = fichier.read()
        self.assertNotIn("get('forfait_pct')", code)
        self.assertNotIn('forfait_pct=', code)


class ProvenanceTest(unittest.TestCase):
    """Trois provenances, trois mentions — et elles voyagent dans l'entrée."""

    def test_la_table_societe_prime_et_se_dit_societe(self):
        contexte = contexte_de(fiche=FICHE_COMPLETE, table=TABLE_SOCIETE,
                               plans=[plan(type_pose='intégré')])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['provenance'], 'societe')
        self.assertEqual(etape['source'], 'societe')
        self.assertEqual(etape['entree']['parametres']['uc_w_m2k'], 20.0)
        self.assertEqual(etape['entree']['reglage_societe']['source'],
                         'texte')

    def test_sans_table_le_uc_de_la_fiche_est_applique_et_annonce(self):
        contexte = contexte_de(fiche=FICHE_COMPLETE, plans=[plan()])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['provenance'], 'fiche')
        self.assertIn('pose non caractérisée', etape['entree']['mention'])

    def test_sans_uc_la_noct_est_employee_avec_son_avertissement(self):
        contexte = contexte_de(fiche=FICHE_NOCT_SEULE, plans=[plan()])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['provenance'], 'noct')
        self.assertIn('open-rack', etape['entree']['mention'])
        self.assertIn('sous-estimée', etape['entree']['mention'])

    def test_une_ligne_societe_sans_source_est_ecartee_en_le_disant(self):
        table = {'integre': {'uc_w_m2k': 20.0}}
        contexte = contexte_de(fiche=FICHE_COMPLETE, table=table,
                               plans=[plan(type_pose='integre')])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['provenance'], 'fiche')
        self.assertIn('ne porte pas sa source', etape['entree']['mention'])

    def test_un_type_de_pose_absent_de_la_table_est_dit(self):
        contexte = contexte_de(fiche=FICHE_COMPLETE, table=TABLE_SOCIETE,
                               plans=[plan(type_pose='ombriere')])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['provenance'], 'fiche')
        self.assertIn('ombriere', etape['entree']['mention'])

    def test_la_reference_cite_les_deux_textes_du_marche(self):
        contexte = contexte_de(fiche=FICHE_COMPLETE, plans=[plan()])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertIn('PVsyst', etape['reference'])
        self.assertIn('PV*SOL', etape['reference'])


class TypeDePoseTest(unittest.TestCase):
    """Le document porte la pose ; `flush` suffit à distinguer deux poses."""

    def _temperature_max(self, pan):
        contexte = contexte_de(fiche=FICHE_COMPLETE, table=TABLE_SOCIETE,
                               plans=[pan])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        return etape

    def test_un_pan_flush_chauffe_plus_que_le_meme_pan_en_chassis(self):
        integre = self._temperature_max(plan(flush=True))
        chassis = self._temperature_max(plan(flush=False))
        self.assertEqual(integre['entree']['type_pose'], 'integre')
        self.assertEqual(chassis['entree']['type_pose'], 'chassis')
        self.assertGreater(
            integre['entree']['temperature_cellule_max_c'],
            chassis['entree']['temperature_cellule_max_c'],
            'une pose intégrée non ventilée doit sortir PLUS chaude.')

    def test_flush_se_lit_aussi_dans_la_geometrie_du_plan(self):
        etape = self._temperature_max(plan(geometry={'flush': True}))
        self.assertEqual(etape['entree']['type_pose'], 'integre')
        self.assertEqual(etape['entree']['champ_type_pose'], 'plans[].flush')

    def test_le_type_saisi_prime_sur_le_booleen(self):
        etape = self._temperature_max(plan(type_pose='chassis', flush=True))
        self.assertEqual(etape['entree']['type_pose'], 'chassis')
        self.assertEqual(etape['entree']['champ_type_pose'],
                         'plans[].type_pose')

    def test_les_types_lus_sont_tous_publies(self):
        contexte = contexte_de(fiche=FICHE_COMPLETE, table=TABLE_SOCIETE,
                               plans=[plan('A', type_pose='integre'),
                                      plan('B', type_pose='chassis')])
        _, etape = etape_thermique.appliquer(SERIE, contexte)
        self.assertEqual(etape['entree']['types_pose_lus'],
                         ['integre', 'chassis'])


class HeureParHeureTest(unittest.TestCase):
    """La dérate est horaire, et la température reste sur la série."""

    def setUp(self):
        self.contexte = contexte_de(fiche=FICHE_COMPLETE, plans=[plan()])
        self.rendue, self.etape = etape_thermique.appliquer(
            SERIE, self.contexte)

    def test_t_cell_c_est_ecrit_sur_chaque_point(self):
        for point in self.rendue['points']:
            self.assertIn('t_cell_c', point, point)

    def test_la_nuit_la_cellule_est_a_la_temperature_de_l_air(self):
        nuit = self.rendue['points'][0]
        self.assertEqual(nuit['t_cell_c'], 21.0)

    def test_la_moyenne_ponderee_egale_la_perte_de_thermique_py(self):
        somme, poids = 0.0, 0.0
        for point in self.rendue['points']:
            irradiance = point['gi_w_m2']
            if irradiance <= 0:
                continue
            derate = -GAMMA * (point['t_cell_c'] - 25.0)
            somme += derate * irradiance
            poids += irradiance
        attendu = perte_thermique(FICHE_COMPLETE, POINTS)['pct']
        self.assertAlmostEqual(somme / poids, attendu, delta=0.01)

    def test_la_serie_d_entree_n_est_jamais_modifiee_sur_place(self):
        self.assertNotIn('t_cell_c', POINTS[1])
        self.assertEqual(POINTS[1]['p_w'], 3000.0)

    def test_une_heure_chaude_perd_de_l_energie(self):
        midi = self.rendue['points'][2]
        self.assertLess(midi['p_w'], 4000.0)
        self.assertLess(etapes.energie_kwh(self.rendue), 9.0)

    def test_une_heure_sans_temperature_d_air_reste_intacte_et_comptee(self):
        points = list(POINTS) + [
            {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 17,
             'p_w': 1000.0, 'gi_w_m2': 200.0}]
        rendue, etape = etape_thermique.appliquer(
            {'pas_minutes': 60, 'points': points}, self.contexte)
        self.assertEqual(etape['entree']['heures_sans_temperature'], 1)
        self.assertNotIn('t_cell_c', rendue['points'][-1])
        self.assertEqual(rendue['points'][-1]['p_w'], 1000.0)

    def test_un_site_froid_produit_un_gain_declare(self):
        froid = {'pas_minutes': 60, 'points': [
            {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12,
             'p_w': 1000.0, 'gi_w_m2': 300.0, 't2m_c': 2.0, 'ws10m': 1.0}]}
        rendue, etape = etape_thermique.appliquer(froid, self.contexte)
        self.assertTrue(etape['gain'],
                        'une cellule sous 25 °C produit PLUS : le gain est '
                        'déclaré, pas effacé.')
        self.assertGreater(etapes.energie_kwh(rendue), 1.0)


class DansLaChaineTest(unittest.TestCase):
    """L'étape passe par l'ordonnanceur sans rien lui devoir."""

    def setUp(self):
        contexte = contexte_de(fiche=FICHE_COMPLETE, table=TABLE_SOCIETE,
                               plans=[plan(type_pose='integre')])
        self.serie, self.cascade = appliquer_chaine(SERIE, contexte)
        self.etape = next(e for e in self.cascade['etapes']
                          if e['etape'] == 'thermique')

    def test_l_etape_est_appliquee_et_mesuree(self):
        self.assertEqual(self.etape['motif_omission'], '')
        self.assertEqual(self.etape['kwh_avant'], 9.0)
        self.assertGreater(self.etape['perte_pct'], 0.0)

    def test_les_douze_champs_du_contrat_sont_publies(self):
        self.assertEqual(sorted(self.etape), sorted(CLES_ETAPE_PUBLIEE))

    def test_la_provenance_et_la_mention_voyagent_dans_l_entree(self):
        self.assertEqual(self.etape['entree']['provenance'], 'societe')
        self.assertIn('mention', self.etape['entree'])

    def test_la_temperature_reste_disponible_pour_les_etapes_aval(self):
        self.assertTrue(all('t_cell_c' in point
                            for point in self.serie['points']))

    def test_une_chaine_sans_reglage_ni_fiche_omet_l_etape(self):
        _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'thermique')
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])


if __name__ == '__main__':
    unittest.main()
