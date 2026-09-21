"""CALX169 — la perte ohmique DC se calcule en R·I², heure par heure.

Aucune base, aucun réseau : un métré de câble comme ``services/cables.py`` le
publie, un chaînage comme ``services/chaines.py`` le publie, et quatre heures
de production.

Run :
    python manage.py test apps.calepinage.tests.test_calx169_ohmique_dc
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import ohmique_dc
from apps.calepinage.services.norme import norme_applicable

SERIE = {
    'pas_minutes': 60,
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 9, 'p_w': 1000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 10, 'p_w': 2000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11, 'p_w': 3000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12, 'p_w': 4000.0},
    ],
}

#: Un câble DC tel que ``cables_du_calepinage`` le publie (chiffres d'essai).
CABLE_W1 = {
    'repere': 'W1',
    'designation': "Câble solaire H1Z2Z2-K (essai)",
    'section_mm2': 6.0,
    'nb_conducteurs': 2,
    'longueur_m': 50.0,
    'longueur_origine': 'plan et saisie',
    'chute_tension_pct': 1.9,
}

CHAINAGE = {
    'modules': 20,
    'modules_par_chaine': 10,
    'chaines': 2,
    'reste': 0,
    'puissance_module_wc': 500.0,
}

NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'}})


def contexte(**extras):
    base = {
        'norme': NORME_FR,
        'cables': {'cables': [dict(CABLE_W1)],
                   'longueurs': {'dc': None, 'ac': None},
                   'omissions': []},
        'electrique': {'chainage': dict(CHAINAGE)},
        'fiche_module': {'vmp_v': 40.0, 'pmax_wc': 500.0},
        'reglages_simulation': {},
        'postes_saisis': [],
    }
    base.update(extras)
    return base


class CalculHoraireTest(unittest.TestCase):

    def setUp(self):
        self.serie, self.etape = ohmique_dc.appliquer(SERIE, contexte())
        self.entree = self.etape['entree']

    def test_l_etape_s_applique_et_nomme_sa_source(self):
        self.assertEqual(self.etape['motif_omission'], '')
        self.assertEqual(self.etape['source'], 'plan et saisie')
        self.assertIn('PVsyst', self.etape['reference'])

    def test_la_resistance_vient_de_la_section_et_de_la_longueur(self):
        self.assertAlmostEqual(self.entree['resistance_ohm'],
                               2 * 0.01851 * 50.0 / 6.0, places=6)

    def test_la_perte_ponderee_est_strictement_inferieure_a_celle_du_stc(self):
        """Propriété : la perte est quadratique en courant, l'énergie est
        linéaire — le STC est le pire point, jamais la moyenne."""
        self.assertGreater(self.entree['perte_stc_pct'], 0.0)
        self.assertLess(self.entree['perte_ponderee_pct'],
                        self.entree['perte_stc_pct'])

    def test_l_energie_baisse_de_la_fraction_ponderee(self):
        attendue = 10.0 * (1.0 - self.entree['perte_ponderee_pct'] / 100.0)
        self.assertAlmostEqual(etapes.energie_kwh(self.serie), attendue,
                               places=4)

    def test_chaque_heure_perd_sa_propre_fraction(self):
        """L'heure la plus chargée perd relativement PLUS que la plus faible."""
        avant = [p['p_w'] for p in SERIE['points']]
        apres = [p['p_w'] for p in self.serie['points']]
        fractions = [1.0 - a / b for a, b in zip(apres, avant)]
        self.assertEqual(fractions, sorted(fractions))
        self.assertLess(fractions[0], fractions[-1])

    def test_la_serie_d_entree_n_est_pas_modifiee(self):
        self.assertEqual(etapes.energie_kwh(SERIE), 10.0)


class ArbitrageAvecLePosteSaisiTest(unittest.TestCase):
    """Le poste saisi est ÉCARTÉ, jamais soustrait une seconde fois."""

    def setUp(self):
        self.contexte = contexte(postes_saisis=[
            {'poste': 'ohmique_dc', 'pct': 1.5, 'source': 'societe',
             'libelle': 'Pertes ohmiques DC'}])
        _, self.cascade = appliquer_chaine(SERIE, self.contexte)
        self.ligne = _ligne(self.cascade, 'ohmique_dc')

    def test_la_saisie_apparait_ecartee(self):
        ecartee = self.ligne['entree']['saisie_ecartee']
        self.assertEqual(ecartee['poste'], 'ohmique_dc')
        self.assertEqual(ecartee['pct'], 1.5)
        self.assertTrue(ecartee['motif'])

    def test_la_perte_publiee_est_celle_du_calcul_et_pas_1_5(self):
        calculee = self.ligne['entree']['champ']['perte_ponderee_pct']
        self.assertAlmostEqual(self.ligne['perte_pct'], calculee, places=2)
        self.assertNotAlmostEqual(self.ligne['perte_pct'], 1.5, places=2)


class NormeNonApplicableTest(unittest.TestCase):
    """``pays=ma`` sans norme choisie : le motif de norme.py, tel quel."""

    def setUp(self):
        self.serie, self.etape = ohmique_dc.appliquer(
            SERIE, contexte(norme=NORME_MA))

    def test_omise_avec_le_motif_de_la_norme(self):
        self.assertFalse(NORME_MA['applicable'])
        self.assertEqual(self.etape['motif_omission'], NORME_MA['motif'])

    def test_energie_intacte(self):
        self.assertEqual(etapes.energie_kwh(self.serie), 10.0)


class OmissionsNommeesTest(unittest.TestCase):

    def test_sans_cable_dc_l_etape_nomme_le_metre(self):
        vide = {'cables': [], 'longueurs': {'dc': None, 'ac': None},
                'omissions': ['descente verticale non saisie (m)']}
        serie, etape = ohmique_dc.appliquer(SERIE, contexte(cables=vide))
        self.assertIn('W1', etape['motif_omission'])
        self.assertIn('descente verticale', etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 10.0)

    def test_sans_vmp_l_etape_nomme_le_champ(self):
        _, etape = ohmique_dc.appliquer(SERIE, contexte(fiche_module={}))
        self.assertIn('vmp_v', etape['motif_omission'])

    def test_micro_onduleur_sans_longueur_saisie_est_omis(self):
        _, etape = ohmique_dc.appliquer(
            SERIE,
            contexte(**{ohmique_dc.CLE_SUIVI_MPP:
                        ohmique_dc.SUIVI_MICRO_ONDULEUR}))
        self.assertIn('micro-onduleur', etape['motif_omission'])
        self.assertIn(ohmique_dc.CHAMP_MICRO_LONGUEUR,
                      etape['motif_omission'])

    def test_micro_onduleur_avec_saisie_porte_sur_le_seul_cable_module(self):
        """Repère de test cité : OpenSolar publie 0,1 % pour cette
        configuration — la valeur du module reste CALCULÉE, jamais forfaitée."""
        _, etape = ohmique_dc.appliquer(
            SERIE,
            contexte(cheminement={'module_vers_micro_onduleur_m': 2.0,
                                  'module_vers_micro_onduleur_mm2': 4.0},
                     **{ohmique_dc.CLE_SUIVI_MPP:
                        ohmique_dc.SUIVI_MICRO_ONDULEUR}))
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['liaison'],
                         'module → micro-onduleur')
        self.assertEqual(etape['entree']['branches_paralleles'], 20.0)

    def test_serie_sans_colonne_d_energie_est_omise(self):
        _, etape = ohmique_dc.appliquer({'points': [{'t2m_c': 21.0}]},
                                        contexte())
        self.assertTrue(etape['motif_omission'])


def _ligne(cascade, nom):
    for etape in cascade['etapes']:
        if etape['etape'] == nom:
            return etape
    raise AssertionError('étape « %s » absente de la cascade' % nom)
