"""CALX161 — la salissure garde ses douze mois jusqu'au bout.

Aucune base, aucun réseau : une série de deux mois très inégaux, et une
saisie société en dur — c'est tout ce qu'il faut pour voir la saisonnalité
survivre (ou non) au calcul.

Run :
    python manage.py test apps.calepinage.tests.test_calx161_salissure
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import salissure

#: Janvier pèse peu, juillet pèse gros : une salissure d'été ne coûte pas la
#: même chose qu'une salissure d'hiver.
POINTS = [
    {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12, 'p_w': 1000.0,
     'gi_w_m2': 400.0, 'gb_i_w_m2': 300.0, 'gd_i_w_m2': 80.0,
     'gr_i_w_m2': 20.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 12, 'p_w': 4000.0,
     'gi_w_m2': 1000.0, 'gb_i_w_m2': 850.0, 'gd_i_w_m2': 120.0,
     'gr_i_w_m2': 30.0},
]
SERIE = {'pas_minutes': 60, 'points': POINTS}

#: Douze mois non constants : sale l'été, rincé l'hiver.
ETE_SALE = [1.0, 1.0, 2.0, 3.0, 5.0, 7.0, 9.0, 9.0, 6.0, 2.0, 1.0, 1.0]
MOYENNE_PLATE = [sum(ETE_SALE) / 12.0] * 12


def contexte_de(valeur, *, source='societe'):
    return {'reglages_simulation': {
        'salissure_mensuelle_pct': {
            'valeur': valeur, 'source': source,
            'reference': 'Relevé de rinçage du site'}}}


class OmissionTest(unittest.TestCase):
    """Rien de saisi, rien d'inventé — et le champ est nommé."""

    def test_aucune_saisie_omet_l_etape_en_nommant_la_cle(self):
        rendue, etape = salissure.appliquer(SERIE, {})
        self.assertIn('salissure_mensuelle_pct', etape['motif_omission'])
        self.assertIs(rendue, SERIE)
        self.assertIsNone(etape['source'])

    def test_une_saisie_sans_source_ne_vaut_pas_saisie(self):
        contexte = {'reglages_simulation': {
            'salissure_mensuelle_pct': {'valeur': 3.0, 'source': ''}}}
        _, etape = salissure.appliquer(SERIE, contexte)
        self.assertTrue(etape['motif_omission'])

    def test_douze_valeurs_dont_une_manque_sont_refusees_en_nommant_le_mois(
            self):
        incomplete = list(ETE_SALE)
        incomplete[6] = None
        _, etape = salissure.appliquer(SERIE, contexte_de(incomplete))
        self.assertIn('juillet', etape['motif_omission'])
        self.assertIn('comblé', etape['motif_omission'])

    def test_deux_mois_manquants_sont_tous_les_deux_nommes(self):
        incomplete = list(ETE_SALE)
        incomplete[0] = None
        incomplete[11] = ''
        _, etape = salissure.appliquer(SERIE, contexte_de(incomplete))
        self.assertIn('janvier', etape['motif_omission'])
        self.assertIn('décembre', etape['motif_omission'])

    def test_onze_valeurs_sont_refusees_comme_annee_incomplete(self):
        _, etape = salissure.appliquer(SERIE, contexte_de(ETE_SALE[:11]))
        self.assertIn('12 valeurs', etape['motif_omission'])

    def test_une_valeur_hors_bornes_est_nommee_par_son_mois(self):
        hors = list(ETE_SALE)
        hors[3] = 140.0
        _, etape = salissure.appliquer(SERIE, contexte_de(hors))
        self.assertIn('avril', etape['motif_omission'])

    def test_une_serie_sans_mois_omet_l_etape_en_nommant_la_colonne(self):
        serie = {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]}
        rendue, etape = salissure.appliquer(serie, contexte_de(ETE_SALE))
        self.assertIn('serie_horaire.mois', etape['motif_omission'])
        self.assertIs(rendue, serie)


class SaisonnaliteTest(unittest.TestCase):
    """La saisonnalité CHANGE le résultat — c'est tout l'objet de la tâche."""

    def _energie(self, valeurs):
        rendue, etape = salissure.appliquer(SERIE, contexte_de(valeurs))
        self.assertEqual(etape['motif_omission'], '')
        return etapes.energie_kwh(rendue)

    def test_une_saisie_mensuelle_differe_de_sa_moyenne_plate(self):
        self.assertNotAlmostEqual(self._energie(ETE_SALE),
                                  self._energie(MOYENNE_PLATE), places=4)

    def test_le_mois_le_plus_lourd_pese_le_plus(self):
        # Le profil retourné a la MÊME moyenne, mais juillet — le mois
        # qui pèse le plus ici — y est moins sale : le toit produit PLUS.
        hiver_sale = list(reversed(ETE_SALE))
        self.assertGreater(self._energie(hiver_sale),
                           self._energie(ETE_SALE))

    def test_une_valeur_unique_egale_douze_valeurs_egales(self):
        self.assertEqual(self._energie(4.0), self._energie([4.0] * 12))

    def test_le_mode_de_saisie_est_dit(self):
        _, unique = salissure.appliquer(SERIE, contexte_de(4.0))
        _, douze = salissure.appliquer(SERIE, contexte_de(ETE_SALE))
        self.assertEqual(unique['entree']['mode'], 'annuelle')
        self.assertEqual(douze['entree']['mode'], 'mensuelle')

    def test_la_moyenne_annuelle_est_une_sortie_pas_une_entree(self):
        _, etape = salissure.appliquer(SERIE, contexte_de(ETE_SALE))
        self.assertAlmostEqual(etape['entree']['moyenne_pct'],
                               sum(ETE_SALE) / 12.0, places=3)
        self.assertEqual(etape['entree']['valeurs_pct'], ETE_SALE)


class ApplicationTest(unittest.TestCase):
    """L'irradiance de l'heure, et ses composantes, suivent le même facteur."""

    def setUp(self):
        self.rendue, self.etape = salissure.appliquer(
            SERIE, contexte_de(ETE_SALE))

    def test_l_irradiance_du_mois_porte_le_facteur_du_mois(self):
        janvier, juillet = self.rendue['points']
        self.assertAlmostEqual(janvier['gi_w_m2'], 400.0 * (1 - 0.01), 6)
        self.assertAlmostEqual(juillet['gi_w_m2'], 1000.0 * (1 - 0.09), 6)

    def test_les_composantes_suivent_pour_que_la_somme_reste_vraie(self):
        for point in self.rendue['points']:
            somme = (point['gb_i_w_m2'] + point['gd_i_w_m2']
                     + point['gr_i_w_m2'])
            self.assertAlmostEqual(point['gi_w_m2'], somme, places=6)

    def test_la_serie_d_entree_n_est_jamais_modifiee_sur_place(self):
        self.assertEqual(POINTS[1]['gi_w_m2'], 1000.0)
        self.assertEqual(POINTS[1]['p_w'], 4000.0)

    def test_les_colonnes_touchees_sont_publiees(self):
        self.assertEqual(self.etape['entree']['colonnes_appliquees'],
                         ['p_w', 'gi_w_m2', 'gb_i_w_m2', 'gd_i_w_m2',
                          'gr_i_w_m2'])

    def test_la_reference_cite_pvsyst_et_aurora(self):
        self.assertIn('PVsyst', self.etape['reference'])
        self.assertIn('Aurora', self.etape['reference'])


class MachineriePartageeTest(unittest.TestCase):
    """`valeurs_mensuelles` est la machinerie que `neige` réemploiera."""

    def test_un_nombre_unique_devient_douze_valeurs_egales(self):
        valeurs, mode, motif = salissure.valeurs_mensuelles(
            2.5, champ='essai')
        self.assertEqual(valeurs, [2.5] * 12)
        self.assertEqual(mode, 'annuelle')
        self.assertEqual(motif, '')

    def test_une_saisie_illisible_est_refusee_en_nommant_le_champ(self):
        valeurs, _, motif = salissure.valeurs_mensuelles(
            'beaucoup', champ='simulation.neige_mensuelle_pct')
        self.assertIsNone(valeurs)
        self.assertIn('simulation.neige_mensuelle_pct', motif)


class DansLaChaineTest(unittest.TestCase):
    """L'étape passe par l'ordonnanceur sans rien lui devoir."""

    def test_l_etape_est_appliquee_et_mesuree(self):
        _, cascade = appliquer_chaine(SERIE, contexte_de(ETE_SALE))
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'salissure')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['kwh_avant'], 5.0)
        self.assertGreater(etape['perte_pct'], 0.0)
        self.assertLess(etape['perte_pct'], 100.0)

    def test_une_chaine_sans_reglage_omet_l_etape(self):
        _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'salissure')
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])


if __name__ == '__main__':
    unittest.main()
