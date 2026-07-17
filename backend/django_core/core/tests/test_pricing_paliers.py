"""Tests NTSUB3 — ``core.pricing_paliers`` (calcul de prix par paliers, pur)."""
from decimal import Decimal

from django.test import SimpleTestCase

from core.pricing_paliers import (
    MODE_GRADUATED,
    MODE_VOLUME,
    calculer_prix_paliers,
)

PALIERS = [
    {'seuil_min': 0, 'seuil_max': 100, 'prix_unitaire': 2},
    {'seuil_min': 100, 'seuil_max': None, 'prix_unitaire': 1.5},
]


class CalculerPrixPaliersTests(SimpleTestCase):
    def test_absence_de_palier_renvoie_none(self):
        # Rétrocompatibilité XCTR16 : aucun palier configuré = None (jamais 0).
        self.assertIsNone(calculer_prix_paliers(150, [], MODE_VOLUME))
        self.assertIsNone(calculer_prix_paliers(150, None, MODE_VOLUME))

    def test_usage_nul_ou_negatif_renvoie_zero(self):
        self.assertEqual(
            calculer_prix_paliers(0, PALIERS, MODE_VOLUME), Decimal('0.00'))
        self.assertEqual(
            calculer_prix_paliers(-10, PALIERS, MODE_VOLUME), Decimal('0.00'))

    def test_mode_volume_dernier_palier_atteint(self):
        # 150 unités >= seuil du 2e palier (100) -> TOUT au tarif 1.5.
        self.assertEqual(
            calculer_prix_paliers(150, PALIERS, MODE_VOLUME),
            Decimal('225.00'))

    def test_mode_volume_premier_palier_seulement(self):
        # 50 unités < 100 -> reste dans le 1er palier, tout à 2.
        self.assertEqual(
            calculer_prix_paliers(50, PALIERS, MODE_VOLUME),
            Decimal('100.00'))

    def test_mode_graduated_par_tranche(self):
        # 150 = (100 x 2) + (50 x 1.5) = 200 + 75 = 275.
        self.assertEqual(
            calculer_prix_paliers(150, PALIERS, MODE_GRADUATED),
            Decimal('275.00'))

    def test_mode_graduated_dans_premiere_tranche(self):
        # 50 unités entièrement dans la 1re tranche -> 50 x 2 = 100.
        self.assertEqual(
            calculer_prix_paliers(50, PALIERS, MODE_GRADUATED),
            Decimal('100.00'))

    def test_mode_graduated_exactement_au_seuil(self):
        # 100 unités pile au seuil -> entièrement dans la 1re tranche.
        self.assertEqual(
            calculer_prix_paliers(100, PALIERS, MODE_GRADUATED),
            Decimal('200.00'))

    def test_accepte_des_tuples(self):
        paliers_tuples = [(0, 100, 2), (100, None, 1.5)]
        self.assertEqual(
            calculer_prix_paliers(150, paliers_tuples, MODE_VOLUME),
            Decimal('225.00'))

    def test_paliers_non_tries_en_entree(self):
        # L'ordre d'entrée ne doit pas influencer le résultat (tri interne).
        desordonne = [
            {'seuil_min': 100, 'seuil_max': None, 'prix_unitaire': 1.5},
            {'seuil_min': 0, 'seuil_max': 100, 'prix_unitaire': 2},
        ]
        self.assertEqual(
            calculer_prix_paliers(150, desordonne, MODE_GRADUATED),
            Decimal('275.00'))

    def test_objet_avec_attributs(self):
        class FakePalier:
            def __init__(self, seuil_min, seuil_max, prix_unitaire):
                self.seuil_min = seuil_min
                self.seuil_max = seuil_max
                self.prix_unitaire = prix_unitaire

        objets = [
            FakePalier(0, 100, 2), FakePalier(100, None, Decimal('1.5'))]
        self.assertEqual(
            calculer_prix_paliers(150, objets, MODE_VOLUME),
            Decimal('225.00'))
