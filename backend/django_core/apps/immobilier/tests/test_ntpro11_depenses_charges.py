"""NTPRO11 — Dépenses réelles de charges.

Couvre : le cumul des dépenses par poste s'affiche en face du budget avec un
écart % (`consommation`), isolation tenant, garde cross-tenant sur
`budget_charges`.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import Batiment, BudgetCharges, DepenseCharges, Site
from apps.immobilier.selectors import consommation_budget

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class Ntpro11DepensesChargesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-dc-a', 'Immo DC A')
        self.co_b = make_company('immo-dc-b', 'Immo DC B')
        self.admin_a = make_user(self.co_a, 'immo-dc-admin-a')
        site_a = Site.objects.create(company=self.co_a, nom='Résidence')
        self.batiment_a = Batiment.objects.create(
            company=self.co_a, site=site_a, nom='Bât A')
        self.budget_a = BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2026,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('10000.00'))

        site_b = Site.objects.create(company=self.co_b, nom='Résidence B')
        batiment_b = Batiment.objects.create(
            company=self.co_b, site=site_b, nom='Bât B')
        self.budget_b = BudgetCharges.objects.create(
            company=self.co_b, batiment=batiment_b, exercice=2026,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('5000.00'))

    def test_creer_depense_force_company_serveur(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/depenses-charges/', {
            'budget_charges': self.budget_a.id, 'date': '2026-03-15',
            'montant_reel': '2500.00',
            'company': self.co_b.id,  # tentative d'injection — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        depense = DepenseCharges.objects.get(id=resp.data['id'])
        self.assertEqual(depense.company_id, self.co_a.id)

    def test_budget_dune_autre_societe_refuse(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/depenses-charges/', {
            'budget_charges': self.budget_b.id, 'date': '2026-03-15',
            'montant_reel': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_consommation_budget_cumul_et_ecart_pct(self):
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=self.budget_a,
            date='2026-01-15', montant_reel=Decimal('3000.00'))
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=self.budget_a,
            date='2026-02-15', montant_reel=Decimal('2000.00'))
        data = consommation_budget(self.budget_a)
        self.assertEqual(data['total_reel'], Decimal('5000.00'))
        self.assertEqual(data['montant_budgete_annuel'], Decimal('10000.00'))
        self.assertEqual(data['ecart'], Decimal('-5000.00'))
        self.assertEqual(data['ecart_pct'], Decimal('-50.00'))

    def test_consommation_sans_depense_reste_a_zero(self):
        data = consommation_budget(self.budget_a)
        self.assertEqual(data['total_reel'], Decimal('0'))
        self.assertEqual(data['ecart_pct'], Decimal('-100.00'))

    def test_consommation_budget_nul_pas_de_division_par_zero(self):
        budget_nul = BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2027,
            poste=BudgetCharges.Poste.AUTRE, montant_budgete_annuel=Decimal('0'))
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=budget_nul,
            date='2027-01-15', montant_reel=Decimal('100.00'))
        data = consommation_budget(budget_nul)
        self.assertIsNone(data['ecart_pct'])

    def test_api_consommation_endpoint(self):
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=self.budget_a,
            date='2026-01-15', montant_reel=Decimal('1000.00'))
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/budgets-charges/{self.budget_a.id}/'
            'consommation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_reel'], '1000.00')

    def test_filtre_par_budget(self):
        d1 = DepenseCharges.objects.create(
            company=self.co_a, budget_charges=self.budget_a,
            date='2026-01-15', montant_reel=Decimal('1000.00'))
        autre_budget = BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2026,
            poste=BudgetCharges.Poste.GARDIENNAGE,
            montant_budgete_annuel=Decimal('3000.00'))
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=autre_budget,
            date='2026-01-20', montant_reel=Decimal('500.00'))
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/depenses-charges/'
            f'?budget_charges={self.budget_a.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [d1.id])
