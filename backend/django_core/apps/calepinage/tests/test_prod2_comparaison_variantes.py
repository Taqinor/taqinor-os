"""CAL145 — le comparatif de variantes se joue sur la PRODUCTION.

Ce qui est tenu ici :

* les colonnes de production du contrat (``variantes_comparer.json``) sont
  RÉELLEMENT remplies, depuis la forme imbriquée du module (CAL138/CAL142)
  comme depuis la forme plate du parcours devis ;
* le comparatif est recalculé À LA LECTURE : une conception modifiée depuis la
  dernière simulation rend la variante « non simulée », jamais un chiffre qui
  décrit un autre toit ;
* une variante non simulée porte ``None`` partout — jamais ``0``.

Tests PURS sur le service de lecture : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.comparaison import (
    CLES_PRODUCTION, MOTIF_NON_SIMULEE, MOTIF_PERIMEE, colonnes_production,
)

EMPREINTE = 'a' * 64
AUTRE_EMPREINTE = 'b' * 64

#: La forme IMBRIQUÉE que produit le module (CAL138 + CAL142).
RESULTAT_MODULE = {
    'layout_hash': EMPREINTE,
    'production': {
        'total': {'kwc': 8.64, 'p50_kwh': 13000.0, 'p75_kwh': 12400.0,
                  'p90_kwh': 11900.0, 'performance_ratio': 0.8,
                  'specific_yield_kwh_kwc': 1504.6},
    },
    'pertes': [
        {'poste': 'thermique', 'pct': 7.4, 'source': 'fiche'},
        {'poste': 'salissure', 'pct': 3.1, 'source': 'societe'},
        {'poste': 'onduleur', 'pct': 2.5, 'source': 'fiche'},
        {'poste': 'mismatch', 'pct': 2.0, 'source': None},
    ],
    'autoconsommation': {'self_consumption_rate': 0.62},
}

#: La forme PLATE des résultats venus du parcours devis.
RESULTAT_DEVIS = {
    'production': {
        'p50_kwh': 10400.0, 'p75_kwh': 9900.0, 'p90_kwh': 9500.0,
        'performance_ratio': 0.81, 'specific_yield_kwh_kwc': 1444.4,
        'self_consumption': {'self_consumption_rate': 0.66},
        'loss_breakdown': {'temperature': {'pct': 8.0},
                           'soiling': {'pct': 3.0},
                           'inverter': {'pct': 2.5},
                           'mismatch': {'pct': 2.0}},
    },
}


class FormeImbriqueeTest(unittest.TestCase):

    def test_les_colonnes_du_contrat_sont_remplies(self):
        simulee, production, motif = colonnes_production(
            RESULTAT_MODULE, layout_hash=EMPREINTE)
        self.assertTrue(simulee)
        self.assertEqual(motif, '')
        self.assertEqual(production['p50_kwh'], 13000.0)
        self.assertEqual(production['p90_kwh'], 11900.0)
        self.assertEqual(production['performance_ratio'], 0.8)
        self.assertEqual(production['self_consumption_rate'], 0.62)

    def test_les_pertes_dominantes_sont_les_plus_lourdes_avec_leur_source(self):
        _, production, _ = colonnes_production(RESULTAT_MODULE,
                                               layout_hash=EMPREINTE)
        dominantes = production['pertes_dominantes']
        self.assertEqual([poste['poste'] for poste in dominantes],
                         ['thermique', 'salissure', 'onduleur'])
        self.assertEqual(dominantes[0]['source'], 'fiche')

    def test_un_poste_non_source_reste_non_source(self):
        resultat = dict(RESULTAT_MODULE, pertes=[
            {'poste': 'mismatch', 'pct': 9.0, 'source': None}])
        _, production, _ = colonnes_production(resultat,
                                               layout_hash=EMPREINTE)
        self.assertIsNone(production['pertes_dominantes'][0]['source'])


class FormePlateTest(unittest.TestCase):

    def test_la_forme_du_parcours_devis_est_lue_a_l_identique(self):
        simulee, production, _ = colonnes_production(RESULTAT_DEVIS)
        self.assertTrue(simulee)
        self.assertEqual(production['p50_kwh'], 10400.0)
        self.assertEqual(production['self_consumption_rate'], 0.66)

    def test_le_loss_breakdown_donne_des_postes_SANS_source(self):
        _, production, _ = colonnes_production(RESULTAT_DEVIS)
        dominantes = production['pertes_dominantes']
        self.assertEqual(dominantes[0]['poste'], 'temperature')
        self.assertIsNone(dominantes[0]['source'])
        self.assertEqual(len(dominantes), 3)


class NonSimuleeTest(unittest.TestCase):

    def test_sans_resultat_tout_est_none_et_jamais_zero(self):
        simulee, production, motif = colonnes_production(None)
        self.assertFalse(simulee)
        self.assertEqual(motif, MOTIF_NON_SIMULEE)
        for cle in CLES_PRODUCTION:
            self.assertIsNone(production[cle], cle)
        self.assertEqual(production['pertes_dominantes'], [])

    def test_un_bloc_production_vide_n_est_pas_une_simulation(self):
        simulee, _, motif = colonnes_production(
            {'production': {'total': {'kwc': 8.64}}})
        self.assertFalse(simulee)
        self.assertEqual(motif, MOTIF_NON_SIMULEE)

    def test_une_conception_modifiee_perime_la_production(self):
        simulee, production, motif = colonnes_production(
            RESULTAT_MODULE, layout_hash=AUTRE_EMPREINTE)
        self.assertFalse(simulee)
        self.assertEqual(motif, MOTIF_PERIMEE)
        self.assertIsNone(production['p50_kwh'])

    def test_un_resultat_sans_empreinte_n_est_pas_declare_perime(self):
        """Un doute ne rougit jamais : sans empreinte, on ne peut rien dire."""
        sans_empreinte = {cle: valeur
                          for cle, valeur in RESULTAT_MODULE.items()
                          if cle != 'layout_hash'}
        simulee, _, _ = colonnes_production(sans_empreinte,
                                            layout_hash=AUTRE_EMPREINTE)
        self.assertTrue(simulee)

    def test_rien_n_est_ecrit_dans_le_resultat_lu(self):
        """Le comparatif CALCULE à la lecture : il ne touche pas sa source."""
        avant = repr(RESULTAT_MODULE)
        colonnes_production(RESULTAT_MODULE, layout_hash=EMPREINTE)
        self.assertEqual(repr(RESULTAT_MODULE), avant)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
