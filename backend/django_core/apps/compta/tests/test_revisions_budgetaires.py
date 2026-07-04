"""Tests XACC22 — Révisions & scénarios budgétaires.

Couvre : réviser un budget conserve la V1 en lecture seule, le rapport
budget-vs-réel permet de choisir la version/le scénario, et la répartition
saisonnière somme exactement au montant annuel.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Budget, BudgetLigne, CentreCout


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class RevisionBudgetTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc22-rev', 'XACC22 Rev')
        self.compte = services._assurer_compte(self.co, '6111')
        self.budget_v1 = Budget.objects.create(
            company=self.co, annee=2026, libelle='Budget annuel')
        BudgetLigne.objects.create(
            company=self.co, budget=self.budget_v1, compte=self.compte,
            m01=Decimal('1000'), m02=Decimal('1000'), m03=Decimal('1000'),
            m04=Decimal('1000'), m05=Decimal('1000'), m06=Decimal('1000'),
            m07=Decimal('1000'), m08=Decimal('1000'), m09=Decimal('1000'),
            m10=Decimal('1000'), m11=Decimal('1000'), m12=Decimal('1000'),
        )

    def test_reviser_conserve_v1_en_lecture_seule(self):
        v2 = services.reviser_budget(self.budget_v1)
        self.budget_v1.refresh_from_db()
        self.assertTrue(self.budget_v1.figee)
        self.assertEqual(v2.version, 2)
        self.assertFalse(v2.figee)
        self.assertEqual(v2.budget_parent_id, self.budget_v1.id)
        # V1 figée refuse une modification directe.
        self.budget_v1.libelle = 'Modif interdite'
        with self.assertRaises(ValidationError):
            self.budget_v1.save()

    def test_v2_copie_les_lignes_de_v1(self):
        v2 = services.reviser_budget(self.budget_v1)
        self.assertEqual(v2.lignes.count(), 1)
        ligne_v2 = v2.lignes.first()
        self.assertEqual(ligne_v2.montant_annuel, Decimal('12000'))

    def test_double_revision_chaine_correctement(self):
        v2 = services.reviser_budget(self.budget_v1)
        v3 = services.reviser_budget(v2)
        self.assertEqual(v3.version, 3)
        self.assertEqual(v3.budget_parent_id, v2.id)

    def test_reviser_deux_fois_meme_version_refuse(self):
        services.reviser_budget(self.budget_v1)
        self.budget_v1.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.reviser_budget(self.budget_v1)


class ScenarioWhatIfTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc22-scenario', 'XACC22 Scenario')
        self.compte = services._assurer_compte(self.co, '6111')
        self.budget_engage = Budget.objects.create(
            company=self.co, annee=2026, libelle='Budget officiel')
        BudgetLigne.objects.create(
            company=self.co, budget=self.budget_engage, compte=self.compte,
            m01=Decimal('1000'), m02=Decimal('1000'), m03=Decimal('1000'),
            m04=Decimal('1000'), m05=Decimal('1000'), m06=Decimal('1000'),
            m07=Decimal('1000'), m08=Decimal('1000'), m09=Decimal('1000'),
            m10=Decimal('1000'), m11=Decimal('1000'), m12=Decimal('1000'),
        )

    def test_rapport_budget_vs_reel_choix_version_scenario(self):
        v2 = services.reviser_budget(self.budget_engage)
        scenario_opt = services.creer_scenario_what_if(
            self.budget_engage, scenario=Budget.Scenario.OPTIMISTE)
        rapport_v1 = selectors.budget_vs_realise(self.co, self.budget_engage)
        rapport_v2 = selectors.budget_vs_realise(self.co, v2)
        rapport_opt = selectors.budget_vs_realise(self.co, scenario_opt)
        self.assertEqual(rapport_v1['total_budget'], Decimal('12000'))
        self.assertEqual(rapport_v2['total_budget'], Decimal('12000'))
        self.assertEqual(rapport_opt['total_budget'], Decimal('12000'))

    def test_scenario_engage_refuse_comme_what_if(self):
        with self.assertRaises(ValidationError):
            services.creer_scenario_what_if(
                self.budget_engage, scenario=Budget.Scenario.ENGAGE)


class RepartitionCourbeTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc22-courbe', 'XACC22 Courbe')
        self.compte = services._assurer_compte(self.co, '6111')
        self.budget = Budget.objects.create(
            company=self.co, annee=2026, libelle='Budget courbe')

    def test_courbe_egale_somme_exacte(self):
        montants = services.repartir_montant_annuel(
            Decimal('12000'), courbe='egale')
        self.assertEqual(sum(montants, Decimal('0')), Decimal('12000.00'))
        self.assertTrue(all(m == Decimal('1000.00') for m in montants))

    def test_courbe_saisonniere_somme_exacte(self):
        montants = services.repartir_montant_annuel(
            Decimal('100000'), courbe='saisonniere')
        self.assertEqual(sum(montants, Decimal('0')), Decimal('100000.00'))

    def test_courbe_pourcentage_personnalisee(self):
        poids = [Decimal('10')] * 10 + [Decimal('0')] * 2
        montants = services.repartir_montant_annuel(
            Decimal('10000'), courbe='pourcentage', poids=poids)
        self.assertEqual(sum(montants, Decimal('0')), Decimal('10000.00'))

    def test_courbe_pourcentage_refuse_si_total_different_100(self):
        poids = [Decimal('10')] * 12  # somme 120.
        with self.assertRaises(ValidationError):
            services.repartir_montant_annuel(
                Decimal('10000'), courbe='pourcentage', poids=poids)

    def test_generer_ligne_budget_repartie(self):
        centre = CentreCout.objects.create(
            company=self.co, code='CH-1', libelle='Chantier')
        ligne = services.generer_ligne_budget_repartie(
            self.budget, compte=self.compte, montant_annuel=Decimal('12000'),
            centre_cout=centre, courbe='saisonniere')
        self.assertEqual(ligne.montant_annuel, Decimal('12000.00'))
