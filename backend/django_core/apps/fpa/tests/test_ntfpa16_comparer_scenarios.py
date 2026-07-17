"""NTFPA16 — comparer_scenarios : tableau à N+1 colonnes (base + un total par
scénario) avec le delta total annuel par scénario vs base, en une requête."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
    LigneScenario, ScenarioBudgetaire,
)
from apps.fpa.selectors import comparer_scenarios


class TestComparerScenarios(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa16-co', defaults={'nom': 'NTFPA16 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='CO', nom='Commercial')
        LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('100000'))

    def _scenario(self, nom, delta_pct):
        s = ScenarioBudgetaire.objects.create(
            company=self.company, cycle=self.cycle, nom=nom)
        LigneScenario.objects.create(
            company=self.company, scenario=s, categorie=Categorie.MARKETING,
            delta_pct=Decimal(delta_pct))
        return s

    def test_comparaison_trois_scenarios(self):
        s1 = self._scenario('Pessimiste', '-10')
        s2 = self._scenario('Optimiste', '20')
        s3 = self._scenario('Neutre', '0')
        result = comparer_scenarios(
            self.company, self.cycle.pk, [s1.pk, s2.pk, s3.pk])
        self.assertEqual(result['base'], Decimal('100000'))
        self.assertEqual(len(result['scenarios']), 3)
        par_nom = {r['nom']: r for r in result['scenarios']}
        self.assertEqual(par_nom['Pessimiste']['ecart'], Decimal('-10000'))
        self.assertEqual(par_nom['Optimiste']['ecart'], Decimal('20000'))
        self.assertEqual(par_nom['Neutre']['ecart'], Decimal('0'))
