"""AMOT29 (C-AMOT-030) — UN payback publié (le cashflow 25 ans du document,
avec « jamais remboursé ») pour les cartes Éco/Max, l'échelle de paliers
batterie et le curseur ; le ratio simple ne sert plus qu'au tri interne.

Cas chiffrés : prix 90 000 / économie 6 500 / onduleur 15 000 (carte : 13,85 ;
définition du PDF : cashflow) et prix 120 000 / 4 000 (carte : 30,0 ; PDF :
jamais remboursé).

Test-du-test : remettre ``return round(cout / economie, 2)`` comme valeur
publiée (``_publier_payback``) ⇒ ``test_carte_publie_le_cashflow`` échoue.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import offres_tailles as OT
from apps.ventes.quote_engine.pricing import (
    compute_cashflow_payback, payback_publiable)


class PaybackPubliableTests(SimpleTestCase):
    def test_egal_au_cashflow_du_document(self):
        pub = payback_publiable(90000, 6500, cout_onduleur_ttc=15000)
        cf = compute_cashflow_payback(90000, 6500, inverter_replace_cost=15000)
        self.assertEqual(pub['annees'], cf['payback_years'])
        self.assertFalse(pub['jamais_rembourse'])
        self.assertNotAlmostEqual(pub['annees'], 90000 / 6500, places=1)

    def test_jamais_rembourse_publie_comme_tel(self):
        pub = payback_publiable(120000, 4000)
        self.assertTrue(pub['jamais_rembourse'])

    def test_non_chiffrable(self):
        self.assertIsNone(payback_publiable(0, 4000))
        self.assertIsNone(payback_publiable(90000, None))

    def test_carte_publie_le_cashflow(self):
        carte = {}
        OT._publier_payback(carte, SimpleNamespace(regles_calcul=2),
                            90000, 6500, cout_onduleur_ttc=15000)
        cf = compute_cashflow_payback(90000, 6500, inverter_replace_cost=15000)
        self.assertEqual(carte['payback_annees'], round(cf['payback_years'], 2))

    def test_carte_jamais_rembourse(self):
        carte = {}
        OT._publier_payback(carte, SimpleNamespace(regles_calcul=2),
                            120000, 4000)
        self.assertNotIn('payback_annees', carte)
        self.assertTrue(carte['payback_jamais_rembourse'])

    def test_regles_d_origine_ratio_d_hier(self):
        carte = {}
        OT._publier_payback(carte, SimpleNamespace(regles_calcul=1),
                            90000, 6500)
        self.assertEqual(carte['payback_annees'], round(90000 / 6500, 2))

    def test_cle_derivee_refusee_en_ecriture(self):
        self.assertIn('payback_jamais_rembourse', OT.CHAMPS_DERIVES)
