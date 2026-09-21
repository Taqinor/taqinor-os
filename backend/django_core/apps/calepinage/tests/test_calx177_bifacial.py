# -*- coding: utf-8 -*-
"""CALX177 — le gain bifacial entre dans la chaîne, avec un albédo MENSUEL.

Aucune base, aucun réseau : deux mois très inégaux, une géométrie de pan et
une saisie société en dur — c'est tout ce qu'il faut pour voir la
saisonnalité de l'albédo survivre (ou non) au calcul.

Run :
    python manage.py test apps.calepinage.tests.test_calx177_bifacial
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.bifacial import PARAMETRES_REQUIS
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import bifacial

#: Janvier pèse peu, juillet pèse gros : un albédo d'hiver et un albédo
#: d'été ne valent pas la même énergie.
POINTS = [
    {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12, 'p_w': 1000.0,
     'gi_w_m2': 400.0, 'gb_i_w_m2': 300.0, 'gd_i_w_m2': 80.0,
     'gr_i_w_m2': 20.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 12, 'p_w': 4000.0,
     'gi_w_m2': 1000.0, 'gb_i_w_m2': 850.0, 'gd_i_w_m2': 120.0,
     'gr_i_w_m2': 30.0},
]
SERIE = {'pas_minutes': 60, 'points': POINTS}

#: Un pan complet : le moteur a MESURÉ le pas, la surface de pose porte sa
#: hauteur libre, et le côté de table dans la pente donne le GCR.
PLAN = {
    'cle': 'PAN-A',
    'clearHeightM': 1.0,
    'engine': {'rowPitchM': 3.4},
    'geometry': {'tiltDeg': 25.0, 'panelSlopeLenM': 1.7, 'kwc': 5.0,
                 'panels': [{'cx': 0.0, 'cy': 0.0},
                            {'cx': 1.2, 'cy': 0.0},
                            {'cx': 0.0, 'cy': 3.4}]},
}

FICHE_BIFACIALE = {'bifacialite_pct': 70.0}
FICHE_MONOFACIALE = {'puissance_wc': 500.0, 'temp_coeff_pmax_pct_c': -0.34}

#: Sol clair l'hiver, sol poussiéreux l'été — moyenne 0,3.
ALBEDO_SAISONNIER = [0.5] * 6 + [0.1] * 6
MOYENNE_PLATE = [sum(ALBEDO_SAISONNIER) / 12.0] * 12


def contexte_de(albedo, *, fiche=None, plans=None, mismatch=None,
                source='societe'):
    reglages = {}
    if albedo is not None:
        reglages[bifacial.CLE_ALBEDO] = {
            'valeur': albedo, 'source': source,
            'reference': 'Relevé du sol sous les rangées'}
    if mismatch is not None:
        reglages[bifacial.CLE_MISMATCH] = {
            'valeur': mismatch, 'source': 'societe',
            'reference': 'Retenu par la société'}
    return {
        'fiche_module': FICHE_BIFACIALE if fiche is None else fiche,
        'plans': [dict(PLAN)] if plans is None else plans,
        'reglages_simulation': reglages,
    }


def energie(serie):
    return etapes.energie_kwh(serie)


class MonofacialTest(unittest.TestCase):
    """Un module monofacial n'est pas une anomalie : le silence, sans champ."""

    def test_une_fiche_sans_bifacialite_omet_l_etape_sans_rien_reclamer(self):
        rendue, etape = bifacial.appliquer(
            SERIE, contexte_de(ALBEDO_SAISONNIER, fiche=FICHE_MONOFACIALE))
        self.assertTrue(etape['motif_omission'])
        self.assertIn('MONOFACIAL', etape['motif_omission'])
        self.assertNotIn('Champ manquant', etape['motif_omission'])
        self.assertIs(rendue, SERIE)
        self.assertIsNone(etape['source'])
        self.assertFalse(etape['gain'])

    def test_le_motif_monofacial_ne_reclame_aucune_geometrie(self):
        _, etape = bifacial.appliquer(
            SERIE, contexte_de(ALBEDO_SAISONNIER, fiche=FICHE_MONOFACIALE,
                               plans=[{}]))
        self.assertIn('MONOFACIAL', etape['motif_omission'])
        self.assertNotIn('hauteur de pose', etape['motif_omission'])


class ManquantsTest(unittest.TestCase):
    """Les cinq paramètres requis remontent NOMMÉMENT, un par un."""

    def test_les_cinq_manquants_sont_nommes_dans_le_motif(self):
        _, etape = bifacial.appliquer(SERIE, {'plans': [{}]})
        motif = etape['motif_omission']
        for _cle, libelle in PARAMETRES_REQUIS:
            with self.subTest(parametre=_cle):
                self.assertIn(libelle, motif)

    def test_l_inclinaison_absente_est_nommee_elle_aussi(self):
        _, etape = bifacial.appliquer(SERIE, {'plans': [{}]})
        self.assertIn("l'inclinaison du plan", etape['motif_omission'])

    def test_l_albedo_non_saisi_pointe_la_cle_de_reglage(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(None))
        self.assertIn(f'simulation.{bifacial.CLE_ALBEDO}',
                      etape['motif_omission'])

    def test_une_saisie_sans_source_ne_vaut_pas_saisie(self):
        contexte = contexte_de(0.2, source='')
        _, etape = bifacial.appliquer(SERIE, contexte)
        self.assertTrue(etape['motif_omission'])
        self.assertIn("l'albédo du sol (saisi)", etape['motif_omission'])

    def test_aucun_pan_omet_l_etape_en_le_disant(self):
        rendue, etape = bifacial.appliquer(
            SERIE, contexte_de(ALBEDO_SAISONNIER, plans=[]))
        self.assertIn('Aucun pan exploitable', etape['motif_omission'])
        self.assertIs(rendue, SERIE)

    def test_une_serie_sans_mois_refuse_un_albedo_mensuel(self):
        serie = {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]}
        rendue, etape = bifacial.appliquer(
            serie, contexte_de(ALBEDO_SAISONNIER))
        self.assertIn('serie_horaire.mois', etape['motif_omission'])
        self.assertIs(rendue, serie)

    def test_onze_valeurs_sont_refusees_comme_annee_incomplete(self):
        _, etape = bifacial.appliquer(
            SERIE, contexte_de(ALBEDO_SAISONNIER[:11]))
        self.assertTrue(etape['motif_omission'])


class SaisonnaliteTest(unittest.TestCase):
    """Douze albédos ne valent PAS douze fois leur moyenne."""

    def test_un_albedo_mensuel_ne_vaut_pas_sa_moyenne(self):
        saisonniere, etape_s = bifacial.appliquer(
            SERIE, contexte_de(ALBEDO_SAISONNIER))
        plate, etape_p = bifacial.appliquer(
            SERIE, contexte_de(MOYENNE_PLATE))
        self.assertFalse(etape_s['motif_omission'], etape_s['motif_omission'])
        self.assertFalse(etape_p['motif_omission'])
        self.assertNotAlmostEqual(energie(saisonniere), energie(plate),
                                  places=4)

    def test_le_gain_est_declare_comme_un_gain(self):
        rendue, etape = bifacial.appliquer(
            SERIE, contexte_de(ALBEDO_SAISONNIER))
        self.assertTrue(etape['gain'])
        self.assertGreater(energie(rendue), energie(SERIE))

    def test_un_albedo_unique_vaut_pour_les_douze_mois(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        self.assertEqual(etape['entree']['albedo_mode'], bifacial.MODE_UNIQUE)
        gains = {ligne['gain_pct']
                 for ligne in etape['entree']['gain_mensuel_pct']}
        self.assertEqual(len(gains), 1)

    def test_chaque_mois_publie_sa_valeur_et_sa_source(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(ALBEDO_SAISONNIER))
        mensuel = etape['entree']['albedo_mensuel']
        self.assertEqual(len(mensuel), 12)
        self.assertEqual(mensuel[0]['mois'], 'janvier')
        self.assertEqual(mensuel[0]['valeur'], 0.5)
        self.assertEqual(mensuel[6]['source'], 'societe')

    def test_une_source_par_mois_prime_sur_celle_du_reglage(self):
        douze = [{'valeur': 0.25, 'source': 'mesure'}] * 12
        _, etape = bifacial.appliquer(SERIE, contexte_de(douze))
        self.assertEqual(
            etape['entree']['albedo_mensuel'][0]['source'], 'mesure')

    def test_la_serie_d_entree_n_est_jamais_modifiee(self):
        avant = energie(SERIE)
        bifacial.appliquer(SERIE, contexte_de(ALBEDO_SAISONNIER))
        self.assertEqual(energie(SERIE), avant)


class MismatchArriereTest(unittest.TestCase):
    """Les 10 % de PVsyst sont CITÉS, jamais appliqués."""

    def test_sans_saisie_le_gain_sort_brut_et_le_dit(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        self.assertIsNone(etape['entree']['mismatch_arriere_pct'])
        self.assertTrue(any('BRUT' in hypothese
                            for hypothese in etape['entree']['hypotheses']))

    def test_une_saisie_reduit_le_gain(self):
        _, brut = bifacial.appliquer(SERIE, contexte_de(0.3))
        _, ampute = bifacial.appliquer(
            SERIE, contexte_de(0.3, mismatch=10.0))
        self.assertEqual(ampute['entree']['mismatch_arriere_pct'], 10.0)
        self.assertLess(ampute['entree']['gain_mensuel_pct'][0]['gain_pct'],
                        brut['entree']['gain_mensuel_pct'][0]['gain_pct'])

    def test_le_dix_pour_cent_de_pvsyst_est_cite_dans_la_reference(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        self.assertIn('10 %', etape['reference'])
        self.assertIn('jamais appliqué', etape['reference'])


class GeometrieTest(unittest.TestCase):
    """Le document d'abord, la société en repli NOMMÉ."""

    def test_un_pan_complet_declare_une_geometrie_de_document(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        self.assertEqual(etape['entree']['geometrie_source'],
                         bifacial.SOURCE_DOCUMENT)
        origines = etape['entree']['plans'][0]['origines']
        self.assertEqual(set(origines.values()), {bifacial.SOURCE_DOCUMENT})

    def test_le_gcr_se_derive_du_cote_de_table_et_du_pas(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        self.assertAlmostEqual(
            etape['entree']['plans'][0]['taux_occupation'], 0.5, places=6)

    def test_le_pas_se_mesure_sur_les_centres_quand_le_moteur_se_tait(self):
        plan = {'cle': 'PAN-B', 'clearHeightM': 1.0,
                'geometry': {'tiltDeg': 25.0, 'panelSlopeLenM': 1.7,
                             'kwc': 5.0,
                             'panels': [{'cx': 0.0, 'cy': 0.0},
                                        {'cx': 0.0, 'cy': 3.4}]}}
        _, etape = bifacial.appliquer(
            SERIE, contexte_de(0.3, plans=[plan]))
        self.assertAlmostEqual(
            etape['entree']['plans'][0]['pas_rangee_m'], 3.4, places=6)
        self.assertEqual(etape['entree']['geometrie_source'],
                         bifacial.SOURCE_DOCUMENT)

    def test_le_repli_societe_est_nomme_comme_tel(self):
        nu = {'cle': 'PAN-C', 'geometry': {'tiltDeg': 25.0, 'kwc': 5.0}}
        contexte = contexte_de(0.3, plans=[nu])
        contexte['reglages_simulation'].update({
            bifacial.CLE_PAS: {'valeur': 3.4, 'source': 'societe'},
            bifacial.CLE_HAUTEUR: {'valeur': 1.0, 'source': 'societe'},
            bifacial.CLE_OCCUPATION: {'valeur': 0.5, 'source': 'societe'},
        })
        _, etape = bifacial.appliquer(SERIE, contexte)
        self.assertFalse(etape['motif_omission'], etape['motif_omission'])
        self.assertEqual(etape['entree']['geometrie_source'],
                         bifacial.SOURCE_SOCIETE)

    def test_sans_document_ni_repli_la_hauteur_est_nommee(self):
        nu = {'cle': 'PAN-D',
              'geometry': {'tiltDeg': 25.0, 'kwc': 5.0, 'panelSlopeLenM': 1.7,
                           'rowPitchM': 3.4}}
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3, plans=[nu]))
        self.assertIn('la hauteur de pose (m)', etape['motif_omission'])
        self.assertIn('clearHeightM', etape['motif_omission'])


class RepereReflechiTest(unittest.TestCase):
    """``gr_i_w_m2`` est un REPÈRE de la face avant, jamais un facteur."""

    def test_la_part_reflechie_avant_est_publiee(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        repere = etape['entree']['repere_reflechi_avant']
        self.assertEqual(repere['heures_lues'], 2)
        self.assertAlmostEqual(repere['part_reflechie_avant_pct'],
                               round(100.0 * 50.0 / 1400.0, 3), places=3)

    def test_sans_composantes_le_repere_manque_mais_le_gain_reste(self):
        serie = {'pas_minutes': 60, 'composantes_disponibles': False,
                 'points': [dict(point, gr_i_w_m2=None) for point in POINTS]}
        rendue, etape = bifacial.appliquer(serie, contexte_de(0.3))
        self.assertFalse(etape['motif_omission'], etape['motif_omission'])
        self.assertIsNone(etape['entree']['repere_reflechi_avant'])
        self.assertTrue(etape['entree']['motif_repere_reflechi'])
        self.assertGreater(energie(rendue), energie(serie))


class DansLaChaineTest(unittest.TestCase):
    """L'étape passe par l'ordonnanceur et respecte le contrat cascade."""

    def test_la_cascade_publie_le_gain_juste_apres_l_auto_ombrage(self):
        _, cascade = appliquer_chaine(SERIE, contexte_de(ALBEDO_SAISONNIER))
        ordre = cascade['ordre']
        self.assertEqual(ordre[ordre.index('bifacial') - 1], 'inter_rangees')

    def test_l_ordonnanceur_accepte_le_gain_declare(self):
        _, cascade = appliquer_chaine(SERIE, contexte_de(ALBEDO_SAISONNIER))
        etape = next(ligne for ligne in cascade['etapes']
                     if ligne['etape'] == 'bifacial')
        self.assertFalse(etape['motif_omission'], etape['motif_omission'])
        self.assertTrue(etape['gain'])
        self.assertGreater(etape['kwh_apres'], etape['kwh_avant'])
        self.assertLess(etape['perte_kwh'], 0.0)
        self.assertEqual(etape['libelle'], bifacial.LIBELLE)

    def test_un_module_monofacial_reste_une_ligne_silencieuse(self):
        contexte = contexte_de(ALBEDO_SAISONNIER, fiche=FICHE_MONOFACIALE)
        _, cascade = appliquer_chaine(SERIE, contexte)
        etape = next(ligne for ligne in cascade['etapes']
                     if ligne['etape'] == 'bifacial')
        self.assertIn('MONOFACIAL', etape['motif_omission'])
        self.assertIsNone(etape['kwh_apres'])

    def test_l_etape_ne_publie_aucune_cle_de_l_ordonnanceur(self):
        _, etape = bifacial.appliquer(SERIE, contexte_de(0.3))
        self.assertEqual(set(etape), set(etapes.CLES_ETAPE))


class RegistreTest(unittest.TestCase):
    """Les quatre clés lues sont DÉCLARÉES au registre CALX145."""

    def test_les_quatre_cles_sont_au_registre(self):
        from apps.calepinage.services.parametres_cles import (
            SECTION_SIMULATION, registre)

        connues = registre(SECTION_SIMULATION)
        for cle in (bifacial.CLE_ALBEDO, bifacial.CLE_HAUTEUR,
                    bifacial.CLE_OCCUPATION, bifacial.CLE_PAS,
                    bifacial.CLE_MISMATCH):
            with self.subTest(cle=cle):
                self.assertIn(cle, connues)
