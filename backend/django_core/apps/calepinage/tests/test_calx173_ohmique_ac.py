"""CALX173 — la perte ohmique AC se calcule sur la longueur SAISIE.

Aucune base, aucun réseau : un câble AC comme ``services/cables.py`` le
publie, et deux heures de production alternative.

Run :
    python manage.py test apps.calepinage.tests.test_calx173_ohmique_ac
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.etapes import ohmique_ac
from apps.calepinage.services.norme import norme_applicable

SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_ac_kw',
    'points': [
        {'mois': 6, 'heure': 10, 'p_ac_kw': 1.0},
        {'mois': 6, 'heure': 12, 'p_ac_kw': 2.0},
    ],
}

CABLE_W2 = {
    'repere': 'W2',
    'designation': 'Câble AC U-1000 R2V (essai)',
    'section_mm2': 6.0,
    'nb_conducteurs': 3,
    'longueur_m': 20.0,
    'longueur_origine': 'saisie',
}

NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'}})


def contexte(phases=1, longueur_m=20.0, cable=True, **extras):
    cables = ([dict(CABLE_W2, longueur_m=longueur_m)] if cable else [])
    base = {
        'norme': NORME_FR,
        'cables': {'cables': cables,
                   'longueurs': {'dc': None, 'ac': None},
                   'omissions': []},
        'fiche_onduleur': {'phases': phases, 'ac_kw': 5.0},
        'cheminement': {},
        'reglages_simulation': {},
        'postes_saisis': [],
    }
    base.update(extras)
    return base


class CalculMonophaseTest(unittest.TestCase):

    def setUp(self):
        self.serie, self.etape = ohmique_ac.appliquer(SERIE, contexte())
        self.entree = self.etape['entree']

    def test_l_etape_s_applique_et_cite_pvsol(self):
        self.assertEqual(self.etape['motif_omission'], '')
        self.assertEqual(self.etape['source'], 'saisie')
        self.assertIn('PV*SOL', self.etape['reference'])

    def test_le_reseau_bt_vient_du_noyau(self):
        self.assertEqual(self.entree['tension_reseau_v'], 230.0)
        self.assertEqual(self.entree['facteur_phases'], 1.0)
        self.assertEqual(self.entree['conducteurs_actifs'], 2.0)

    def test_la_resistance_lineique_vient_du_metre(self):
        self.assertAlmostEqual(self.entree['resistance_lineique_ohm'],
                               0.01851 * 20.0 / 6.0, places=6)

    def test_l_energie_baisse_et_la_serie_d_entree_reste_intacte(self):
        self.assertLess(etapes.energie_kwh(self.serie), 3.0)
        self.assertEqual(etapes.energie_kwh(SERIE), 3.0)

    def test_l_heure_la_plus_chargee_perd_relativement_plus(self):
        avant = [p['p_ac_kw'] for p in SERIE['points']]
        apres = [p['p_ac_kw'] for p in self.serie['points']]
        fractions = [1.0 - a / b for a, b in zip(apres, avant)]
        self.assertLess(fractions[0], fractions[1])


class LongueurDoubleeTest(unittest.TestCase):
    """Propriété : doubler la longueur double la perte, à section et
    courant constants."""

    def test_la_perte_double(self):
        _, simple = ohmique_ac.appliquer(SERIE, contexte(longueur_m=20.0))
        _, double = ohmique_ac.appliquer(SERIE, contexte(longueur_m=40.0))
        self.assertAlmostEqual(double['entree']['perte_ponderee_pct'],
                               2.0 * simple['entree']['perte_ponderee_pct'],
                               places=6)


class TriphaseTest(unittest.TestCase):
    """Le même transit perd STRICTEMENT moins en triphasé."""

    def test_le_triphase_perd_moins_que_le_monophase(self):
        _, mono = ohmique_ac.appliquer(SERIE, contexte(phases=1))
        _, tri = ohmique_ac.appliquer(SERIE, contexte(phases=3))
        self.assertLess(tri['entree']['perte_ponderee_pct'],
                        mono['entree']['perte_ponderee_pct'])
        self.assertEqual(tri['entree']['tension_reseau_v'], 400.0)
        self.assertEqual(tri['entree']['conducteurs_actifs'], 3.0)


class OmissionsNommeesTest(unittest.TestCase):

    def test_longueur_ac_non_saisie_reprend_le_motif_existant(self):
        serie, etape = ohmique_ac.appliquer(SERIE, contexte(cable=False))
        attendu = 'liaison onduleur → TGBT non saisie (m)'
        self.assertIn(attendu, etape['motif_omission'])
        self.assertIn('onduleur_vers_tgbt_m', etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 3.0)

    def test_fiche_sans_phases_omet_en_nommant_le_champ(self):
        _, etape = ohmique_ac.appliquer(
            SERIE, contexte(fiche_onduleur={'ac_kw': 5.0}))
        self.assertIn('phases', etape['motif_omission'])

    def test_serie_encore_continue_est_omise(self):
        continue_ = {'pas_minutes': 60, 'colonne_energie': 'p_dc_kw',
                     'points': [{'p_dc_kw': 1.0}]}
        serie, etape = ohmique_ac.appliquer(continue_, contexte())
        self.assertIn('alternative', etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 1.0)

    def test_norme_non_applicable_reprend_le_motif_de_norme_py(self):
        _, etape = ohmique_ac.appliquer(SERIE, contexte(norme=NORME_MA))
        self.assertEqual(etape['motif_omission'], NORME_MA['motif'])
