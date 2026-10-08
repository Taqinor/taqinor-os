"""AMOT35 (C-AMOT-045) — ``bankable_imprimable(bank, kwc_devis,
production_servie)`` (fonction pure) appelée par le legacy ET la page finance
industrielle : une P50/P90 n'est imprimée que si la simulation décrit le champ
vendu et reste cohérente avec la production imprimée.

Rejoue VC ci1 (devis industriel 49,7 kWc / 79 482 kWh portant une simulation
périmée : « P90) : 987654 kWh/an » imprimé).

Test-du-test : retirer l'appel dans ``_p90_bancable`` ⇒
``test_finance_omet_la_p90_perimee`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import bankable as B
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.industriel import finance

PERIMEE = {'zones': [{'kwc': 12.0}], 'pr': {'p50_kwh': 1000000,
                                            'p90_kwh': 987654}}
COHERENTE = {'zones': [{'kwc': 30.0}, {'kwc': 19.7}],
             'pr': {'p50_kwh': 79482 * 1.005, 'p90_kwh': 72000}}


class P90BancableTests(SimpleTestCase):
    def test_pure(self):
        self.assertEqual(B.bankable_imprimable(PERIMEE, 49.7, 79482),
                         (False, B.MOTIF_CHAMP))
        self.assertEqual(B.bankable_imprimable(COHERENTE, 49.7, 79482),
                         (True, None))
        mauvaise_p50 = {'zones': [{'kwc': 49.7}],
                        'pr': {'p50_kwh': 90000, 'p90_kwh': 80000}}
        self.assertEqual(B.bankable_imprimable(mauvaise_p50, 49.7, 79482),
                         (False, B.MOTIF_PRODUCTION))
        self.assertEqual(B.bankable_imprimable(COHERENTE, None, 79482)[0],
                         False)

    def test_finance_omet_la_p90_perimee(self):
        d = {'etude': {'bankable': PERIMEE}, 'ind_kwc': 49.7,
             'ind_prod': 79482}
        self.assertIsNone(finance._p90_bancable(d))

    def test_finance_garde_la_p90_coherente(self):
        d = {'etude': {'bankable': COHERENTE}, 'ind_kwc': 49.7,
             'ind_prod': 79482}
        self.assertEqual(finance._p90_bancable(d), 72000)

    def test_regles_d_origine(self):
        d = {'etude': {'bankable': PERIMEE}, 'ind_kwc': 49.7,
             'ind_prod': 79482, 'regles_calcul_origine': True}
        self.assertEqual(finance._p90_bancable(d), 987654)

    def test_legacy_delegue_a_la_meme_regle(self):
        self.assertIs(G.TOLERANCE_PRODUCTION_PAGE,
                      B.TOLERANCE_PRODUCTION_PAGE)
        sauve = (G.KWC, G.PUISSANCE_INCONNUE)
        G.KWC, G.PUISSANCE_INCONNUE = 49.7, False
        try:
            self.assertFalse(G._bankable_decrit_ce_champ(PERIMEE))
            self.assertTrue(G._bankable_decrit_ce_champ(COHERENTE))
        finally:
            G.KWC, G.PUISSANCE_INCONNUE = sauve
