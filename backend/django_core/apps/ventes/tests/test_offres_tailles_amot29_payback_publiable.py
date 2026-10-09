"""AMOT29 (C-AMOT-030) — UN payback publié (le cashflow 25 ans du document,
avec « jamais remboursé ») pour les cartes Éco/Max, l'échelle de paliers
batterie et le repli de la carte Recommandé : ``pricing.payback_publiable``.
Le ratio simple ``coût ÷ économie`` ne sert plus qu'au tri interne.

Moteur réel (``compute_cashflow_payback``), aucun mock. Test-du-test :
remettre ``return round(cout / economie, 2)`` comme valeur publiée
(``offres_tailles._payback_publie``) ⇒ ``test_carte_eco_max_definition_pdf``
échoue (13,85 au lieu de 16,8).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import offres_tailles as ot
from apps.ventes.domain.dimensionnement_devis import _payback_publie_palier
from apps.ventes.quote_engine.pricing import (
    compute_cashflow_payback, payback_publiable,
)


class PaybackPubliableTests(SimpleTestCase):
    def test_definition_du_document(self):
        attendu = compute_cashflow_payback(
            90000, 6500, inverter_replace_cost=15000)['payback_years']
        res = payback_publiable(90000, 6500, cout_onduleur_ttc=15000)
        self.assertEqual(res['payback_annees'], round(attendu, 2))
        self.assertFalse(res['jamais_rembourse'])
        self.assertNotAlmostEqual(res['payback_annees'], 90000 / 6500,
                                  delta=0.5)

    def test_jamais_rembourse_publie_comme_tel(self):
        res = payback_publiable(120000, 4000)
        self.assertTrue(res['jamais_rembourse'])
        self.assertIsNone(res['payback_annees'])

    def test_non_chiffrable(self):
        for prix, eco in ((0, 100), (100, 0), (None, None)):
            self.assertIsNone(payback_publiable(prix, eco)['payback_annees'])

    def test_carte_eco_max_definition_pdf(self):
        publie = ot._payback_publie(90000.0, 6500.0, cout_onduleur_ttc=15000)
        self.assertEqual(publie, payback_publiable(
            90000, 6500, cout_onduleur_ttc=15000)['payback_annees'])
        self.assertNotEqual(publie, round(90000 / 6500, 2))
        self.assertIsNone(ot._payback_publie(120000.0, 4000.0))

    def test_carte_recommande_repli(self):
        """Sans ``roi_*`` servi, la carte Recommandé publie la définition du
        document, jamais le ratio simple."""
        from apps.ventes.tests.test_offres_tailles import _contexte_factice
        data = {'nb_panneaux_sans': 22, 'puissance_kwc_sans': 12.1,
                'totaux_sans': {'ttc': 90000.0}, 'eco_s_ann': 6500.0}
        contexte = _contexte_factice(SimpleNamespace(
            etude_params={}, reference='DEV-AMOT29'))
        carte = ot._carte_du_devis(contexte, data, 'sans')
        self.assertEqual(carte['payback_annees'], payback_publiable(
            90000, 6500)['payback_annees'])
        self.assertNotEqual(carte['payback_annees'], round(90000 / 6500, 2))

    def test_echelle_paliers(self):
        lignes = [{'role': 'onduleur_hybride', 'quantite': 1,
                   'prix_unitaire_ht': 12500.0},
                  {'role': 'batterie', 'quantite': 1,
                   'prix_unitaire_ht': 20000.0}]
        publie = _payback_publie_palier(90000.0, 6500.0, lignes, 0.9)
        attendu = compute_cashflow_payback(
            90000.0, 6500.0, battery=True,
            inverter_replace_cost=round(12500 * 1.2 * 0.9, 2))
        self.assertEqual(publie, round(attendu['payback_years'], 2))
        self.assertIsNone(_payback_publie_palier(120000.0, 4000.0, [], 1.0))
