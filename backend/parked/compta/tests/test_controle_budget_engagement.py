"""Tests XACC21 — Contrôle du budget COMPTABLE à l'engagement (warning/blocage).

Couvre : un engagement qui dépasse le budget restant du centre reçoit le
warning avec les montants (le contrôle projet FG313 reste intact, non
dupliqué ici), en mode bloquant un non-responsable est refusé et l'override
responsable passe, et budget non défini = aucun contrôle.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Budget, BudgetLigne, CentreCout


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BudgetRestantTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc21-svc', 'XACC21 Svc')
        self.cc = CentreCout.objects.create(
            company=self.co, code='CH-1', libelle='Chantier 1')
        self.compte = services._assurer_compte(self.co, '6111')

    def _make_budget(self, controle=Budget.Controle.WARNING, montant_annuel=Decimal('12000')):
        budget = Budget.objects.create(
            company=self.co, annee=2026, libelle='Budget 2026', controle=controle)
        BudgetLigne.objects.create(
            company=self.co, budget=budget, compte=self.compte,
            centre_cout=self.cc,
            m01=montant_annuel / 12, m02=montant_annuel / 12,
            m03=montant_annuel / 12, m04=montant_annuel / 12,
            m05=montant_annuel / 12, m06=montant_annuel / 12,
            m07=montant_annuel / 12, m08=montant_annuel / 12,
            m09=montant_annuel / 12, m10=montant_annuel / 12,
            m11=montant_annuel / 12, m12=montant_annuel / 12,
        )
        return budget

    def test_budget_non_defini_aucun_controle(self):
        resultat = services.verifier_engagement_budgetaire(
            self.co, montant_engage=Decimal('5000'),
            periode=date(2026, 3, 1), centre_cout=self.cc)
        self.assertTrue(resultat['autorise'])
        self.assertIsNone(resultat['warning'])
        self.assertIsNone(resultat['budget_restant'])

    def test_depassement_mode_warning_autorise_avec_message(self):
        self._make_budget(controle=Budget.Controle.WARNING,
                          montant_annuel=Decimal('1200'))
        resultat = services.verifier_engagement_budgetaire(
            self.co, montant_engage=Decimal('5000'),
            periode=date(2026, 3, 1), centre_cout=self.cc)
        self.assertTrue(resultat['autorise'])
        self.assertIsNotNone(resultat['warning'])
        self.assertIn('5000', resultat['warning'])

    def test_depassement_mode_bloquant_refuse_non_responsable(self):
        self._make_budget(controle=Budget.Controle.BLOQUANT,
                          montant_annuel=Decimal('1200'))
        resultat = services.verifier_engagement_budgetaire(
            self.co, montant_engage=Decimal('5000'),
            periode=date(2026, 3, 1), centre_cout=self.cc,
            est_responsable=False)
        self.assertFalse(resultat['autorise'])

    def test_depassement_mode_bloquant_override_responsable_passe(self):
        self._make_budget(controle=Budget.Controle.BLOQUANT,
                          montant_annuel=Decimal('1200'))
        resultat = services.verifier_engagement_budgetaire(
            self.co, montant_engage=Decimal('5000'),
            periode=date(2026, 3, 1), centre_cout=self.cc,
            est_responsable=True)
        self.assertTrue(resultat['autorise'])
        self.assertIn('override', resultat['warning'])

    def test_pas_de_depassement_aucun_warning(self):
        self._make_budget(controle=Budget.Controle.WARNING,
                          montant_annuel=Decimal('12000'))
        resultat = services.verifier_engagement_budgetaire(
            self.co, montant_engage=Decimal('500'),
            periode=date(2026, 3, 1), centre_cout=self.cc)
        self.assertTrue(resultat['autorise'])
        self.assertIsNone(resultat['warning'])

    def test_selector_budget_restant_direct(self):
        self._make_budget(montant_annuel=Decimal('1200'))
        info = selectors.budget_restant(
            self.co, centre_cout=self.cc, periode=date(2026, 6, 1))
        self.assertEqual(info['montant_budgete'], Decimal('1200'))
        self.assertEqual(info['restant'], Decimal('1200'))

    def test_defaut_controle_warning(self):
        budget = self._make_budget()
        self.assertEqual(budget.controle, Budget.Controle.WARNING)
