"""ACAL270 — un seul productible de repli « PVGIS indisponible / ville
inconnue » : celui du devis (D-ACAL, défaut gravé « productible de repli =
celui du devis partout »).

``solar_design`` retombait sur un 1600.0 brut quand un scénario ne portait pas
de ``productible_kwh_kwc`` ; le moteur du devis, lui, applique
``productible_for_city('')`` (DEFAULT_PRODUCTIBLE = 1651) × PRODUCTION_DERATE
(≈ 0,9302) ≈ 1 536 kWh/kWc. Les deux doivent rendre le MÊME chiffre.

Test-du-test : remettre l'ancien repli brut (1600.0, ou 1500) dans
``solar_design._scenario_annual_production`` ⇒ ``test_solar_design_egal_au_devis``
échoue. Calcul pur (SimpleTestCase, aucune base).
"""
from django.test import SimpleTestCase

from apps.ventes import solar_design as sd
from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
from apps.ventes.quote_engine.productible import (
    DEFAULT_PRODUCTIBLE, productible_for_city,
)


class ProductibleRepliUniqueTests(SimpleTestCase):

    def test_solar_design_egal_au_devis(self):
        attendu_kwh_kwc = productible_for_city('') * PRODUCTION_DERATE
        # Sanité des sources réelles (vivantes, jamais mockées).
        self.assertEqual(productible_for_city(''), float(DEFAULT_PRODUCTIBLE))
        self.assertAlmostEqual(attendu_kwh_kwc, 1536, delta=1.0)

        # Scénario SANS productible (ville inconnue) : 10 kWc.
        prod = sd._scenario_annual_production({'kwc': 10})
        self.assertAlmostEqual(prod, round(10 * attendu_kwh_kwc, 1), places=1)
        self.assertNotAlmostEqual(prod, 16000.0, delta=1.0)

    def test_le_comparateur_rend_le_meme_repli(self):
        attendu = round(4 * productible_for_city('') * PRODUCTION_DERATE, 1)
        res = sd.compare_scenarios([{'kwc': 4, 'annual_savings': 1}])
        self.assertAlmostEqual(
            res['scenarios'][0]['annual_production_kwh'], attendu, places=1)

    def test_un_productible_illisible_retombe_sur_le_meme_repli(self):
        attendu = round(2 * productible_for_city('') * PRODUCTION_DERATE, 1)
        prod = sd._scenario_annual_production(
            {'kwc': 2, 'productible_kwh_kwc': 'x'})
        self.assertAlmostEqual(prod, attendu, places=1)

    def test_un_productible_fourni_prime_toujours(self):
        prod = sd._scenario_annual_production(
            {'kwc': 5, 'productible_kwh_kwc': 1700})
        self.assertEqual(prod, 8500.0)

    def test_solar_design_n_a_plus_de_repli_brut(self):
        # Jumeau supprimé : plus aucun repli 1600.0 codé en dur.
        import inspect
        source = inspect.getsource(sd._scenario_annual_production)
        self.assertNotIn('1600', source)
