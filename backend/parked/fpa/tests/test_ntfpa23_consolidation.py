"""NTFPA23 — consolidation_entreprise : la consolidation totale (dépenses)
égale exactement la somme des lignes département (aucun écart >1 MAD)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
)
from apps.fpa.selectors import consolidation_entreprise


class TestConsolidationEntreprise(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa23-co', defaults={'nom': 'NTFPA23 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.d1 = Departement.objects.create(
            company=self.company, code='IT', nom='IT')
        self.d2 = Departement.objects.create(
            company=self.company, code='MKT', nom='Marketing')
        for dept, cat, montant in [
            (self.d1, Categorie.IT, '3000'),
            (self.d1, Categorie.MASSE_SALARIALE, '5000'),
            (self.d2, Categorie.MARKETING, '2000'),
        ]:
            LigneBudgetDepartement.objects.create(
                company=self.company, cycle=self.cycle, departement=dept,
                categorie=cat, mois=1, montant_prevu=Decimal(montant))

    def test_total_depenses_egale_somme_lignes(self):
        result = consolidation_entreprise(self.company, self.cycle)
        somme_lignes = sum(
            (Decimal(str(li.montant_prevu)) for li in
             LigneBudgetDepartement.objects.filter(cycle=self.cycle)), Decimal('0'))
        self.assertEqual(result['total_depenses'], somme_lignes)
        self.assertEqual(result['total_depenses'], Decimal('10000'))

    def test_marge_brute_est_revenu_moins_depenses(self):
        result = consolidation_entreprise(self.company, self.cycle)
        attendu = result['revenu_previsionnel'] - result['total_depenses']
        self.assertEqual(result['marge_brute_previsionnelle'], attendu)
