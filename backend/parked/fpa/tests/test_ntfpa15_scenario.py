"""NTFPA15 — ScenarioBudgetaire : un scénario ne touche AUCUNE ligne du budget
de base ; il calcule un total dérivé à la volée (deltas en lecture)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
    LigneScenario, ScenarioBudgetaire,
)
from apps.fpa.selectors import budget_total_annuel, total_scenario


class TestScenarioBudgetaire(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa15-co', defaults={'nom': 'NTFPA15 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='CO', nom='Commercial')
        # Ventes (marketing) 100000, masse salariale 50000.
        LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('100000'))
        LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MASSE_SALARIALE, mois=1, montant_prevu=Decimal('50000'))

    def test_scenario_ne_modifie_pas_le_budget_de_base(self):
        base_avant = budget_total_annuel(self.company, self.cycle.pk)
        scenario = ScenarioBudgetaire.objects.create(
            company=self.company, cycle=self.cycle,
            nom='-10% marketing / +5% masse salariale')
        LigneScenario.objects.create(
            company=self.company, scenario=scenario,
            categorie=Categorie.MARKETING, delta_pct=Decimal('-10'))
        LigneScenario.objects.create(
            company=self.company, scenario=scenario,
            categorie=Categorie.MASSE_SALARIALE, delta_pct=Decimal('5'))

        # Le total de base est INCHANGÉ (aucune ligne du cycle touchée).
        self.assertEqual(budget_total_annuel(self.company, self.cycle.pk), base_avant)

        # Le total dérivé applique les deltas : 90000 + 52500 = 142500.
        total = total_scenario(self.company, scenario)
        self.assertEqual(total, Decimal('142500'))

    def test_un_seul_scenario_base_par_cycle(self):
        ScenarioBudgetaire.objects.create(
            company=self.company, cycle=self.cycle, nom='Base A',
            est_scenario_base=True)
        with self.assertRaises(Exception):
            ScenarioBudgetaire.objects.create(
                company=self.company, cycle=self.cycle, nom='Base B',
                est_scenario_base=True)
