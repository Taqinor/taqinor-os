"""NTPRO10 — Budget de charges par bâtiment.

Couvre : un budget est créé par bâtiment+exercice+poste, la contrainte
d'unicité (batiment, exercice, poste) évite les doublons, isolation tenant,
filtres `?batiment=&exercice=`.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import Batiment, BudgetCharges, Site

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


class Ntpro10BudgetChargesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-bc-a', 'Immo BC A')
        self.co_b = make_company('immo-bc-b', 'Immo BC B')
        self.admin_a = make_user(self.co_a, 'immo-bc-admin-a')
        self.admin_b = make_user(self.co_b, 'immo-bc-admin-b')
        self.site_a = Site.objects.create(company=self.co_a, nom='Résidence')
        self.batiment_a = Batiment.objects.create(
            company=self.co_a, site=self.site_a, nom='Bât A')
        site_b = Site.objects.create(company=self.co_b, nom='Résidence B')
        self.batiment_b = Batiment.objects.create(
            company=self.co_b, site=site_b, nom='Bât B')

    def test_creer_budget_force_company_serveur(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/budgets-charges/', {
            'batiment': self.batiment_a.id, 'exercice': 2026,
            'poste': BudgetCharges.Poste.ASCENSEUR,
            'montant_budgete_annuel': '12000.00',
            'company': self.co_b.id,  # tentative d'injection — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        budget = BudgetCharges.objects.get(id=resp.data['id'])
        self.assertEqual(budget.company_id, self.co_a.id)

    def test_unique_together_batiment_exercice_poste(self):
        BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2026,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('5000.00'))
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/budgets-charges/', {
            'batiment': self.batiment_a.id, 'exercice': 2026,
            'poste': BudgetCharges.Poste.NETTOYAGE,
            'montant_budgete_annuel': '6000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_meme_poste_annees_differentes_autorise(self):
        BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2025,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('5000.00'))
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/budgets-charges/', {
            'batiment': self.batiment_a.id, 'exercice': 2026,
            'poste': BudgetCharges.Poste.NETTOYAGE,
            'montant_budgete_annuel': '6000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_filtre_batiment_et_exercice(self):
        BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2026,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('5000.00'))
        BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment_a, exercice=2025,
            poste=BudgetCharges.Poste.GARDIENNAGE,
            montant_budgete_annuel=Decimal('8000.00'))
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/budgets-charges/'
            f'?batiment={self.batiment_a.id}&exercice=2026')
        postes = [r['poste'] for r in rows(resp)]
        self.assertEqual(postes, ['nettoyage'])

    def test_isolation_tenant(self):
        BudgetCharges.objects.create(
            company=self.co_b, batiment=self.batiment_b, exercice=2026,
            poste=BudgetCharges.Poste.ASCENSEUR,
            montant_budgete_annuel=Decimal('3000.00'))
        resp = auth(self.admin_a).get('/api/django/immobilier/budgets-charges/')
        self.assertEqual(rows(resp), [])

    def test_batiment_dune_autre_societe_refuse(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/budgets-charges/', {
            'batiment': self.batiment_b.id, 'exercice': 2026,
            'poste': BudgetCharges.Poste.ASCENSEUR,
            'montant_budgete_annuel': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
