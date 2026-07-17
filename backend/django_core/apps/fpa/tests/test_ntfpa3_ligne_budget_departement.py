"""NTFPA3 — LigneBudgetDepartement : saisie mensuelle par département/catégorie,
total annuel calculable côté selector."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement
from apps.fpa.selectors import budget_total_annuel

User = get_user_model()


class TestLigneBudgetDepartement(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa3-co', defaults={'nom': 'NTFPA3 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='IT', nom='IT')

    def test_saisie_mensuelle_et_total_annuel(self):
        for mois in range(1, 13):
            LigneBudgetDepartement.objects.create(
                company=self.company, cycle=self.cycle, departement=self.dept,
                categorie=Categorie.IT, mois=mois, montant_prevu=Decimal('1000'))
        total = budget_total_annuel(self.company, self.cycle.pk)
        self.assertEqual(total, Decimal('12000'))

    def test_contrainte_unique_cycle_departement_categorie_mois(self):
        LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.IT, mois=1, montant_prevu=Decimal('500'))
        with self.assertRaises(Exception):
            LigneBudgetDepartement.objects.create(
                company=self.company, cycle=self.cycle, departement=self.dept,
                categorie=Categorie.IT, mois=1, montant_prevu=Decimal('600'))
