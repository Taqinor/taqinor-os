"""AMOT35 (C-AMOT-045) — ``bankable.bankable_imprimable`` (fonction pure,
tolérances ``TOLERANCE_KWC_SIMULATION`` / ``TOLERANCE_PRODUCTION_PAGE``) est
LA règle du legacy ET de la page finance industrielle : une P50/P90 n'est
imprimée que si la simulation décrit le champ vendu et reste cohérente avec
la production imprimée.

Fonctions réelles, aucun mock. Test-du-test : retirer l'appel
``bankable_imprimable`` de ``industriel.finance._p90_bancable`` ⇒
``test_finance_industrielle_p90_perimee_omise`` échoue (987 654 imprimé).
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.bankable import (
    TOLERANCE_KWC_SIMULATION, TOLERANCE_PRODUCTION_PAGE, bankable_imprimable,
)
from apps.ventes.quote_engine.industriel import finance


def _bank(kwc, p50, p90):
    return {'zones': [{'kwc': kwc}],
            'pr': {'p50_kwh': p50, 'p90_kwh': p90}}


class P90BancableTests(SimpleTestCase):
    def test_constantes_partagees(self):
        self.assertEqual(G.TOLERANCE_KWC_SIMULATION, TOLERANCE_KWC_SIMULATION)
        self.assertEqual(G.TOLERANCE_PRODUCTION_PAGE,
                         TOLERANCE_PRODUCTION_PAGE)

    def test_pur_coherente(self):
        ok, motif = bankable_imprimable(_bank(49.7, 79500, 72000), 49.7, 79482)
        self.assertTrue(ok)
        self.assertIsNone(motif)

    def test_pur_champ_perime(self):
        ok, motif = bankable_imprimable(_bank(120.0, 990000, 987654), 49.7,
                                        79482)
        self.assertFalse(ok)
        self.assertIn('ne décrit pas le champ', motif)

    def test_pur_production_contredite(self):
        ok, motif = bankable_imprimable(_bank(49.7, 99000, 90000), 49.7, 79482)
        self.assertFalse(ok)
        self.assertIn('production', motif)

    def test_pur_tolerances(self):
        self.assertTrue(bankable_imprimable(
            _bank(49.7 * 1.019, 79482 * 1.009, 1), 49.7, 79482)[0])
        self.assertFalse(bankable_imprimable(
            _bank(49.7 * 1.03, 79482, 1), 49.7, 79482)[0])

    def test_finance_industrielle_p90_perimee_omise(self):
        d = {'ind_kwc': 49.7, 'ind_prod': 79482,
             'etude': {'bankable': _bank(120.0, 990000, 987654)},
             'avertissements_internes': []}
        self.assertIsNone(finance._p90_bancable(d))
        self.assertTrue(any('périmée' in a
                            for a in d['avertissements_internes']))

    def test_finance_industrielle_p90_coherente_imprimee(self):
        d = {'ind_kwc': 49.7, 'ind_prod': 79482,
             'etude': {'bankable': _bank(49.7, 79500, 72000)}}
        self.assertEqual(finance._p90_bancable(d), 72000)

    def test_legacy_meme_regle(self):
        with G._RENDER_LOCK:
            anciens = (G.KWC, G.PUISSANCE_INCONNUE, G.__dict__.get('ETUDE'))
            try:
                G.KWC, G.PUISSANCE_INCONNUE = 49.7, False
                G.ETUDE = {'production_annuelle': 79482}
                self.assertEqual(
                    G._bankable_block_html(_bank(120.0, 990000, 987654)), '')
                self.assertIn('72', G._bankable_block_html(
                    _bank(49.7, 79500, 72000)))
            finally:
                G.KWC, G.PUISSANCE_INCONNUE = anciens[0], anciens[1]
                if anciens[2] is None:
                    G.__dict__.pop('ETUDE', None)
                else:
                    G.ETUDE = anciens[2]
