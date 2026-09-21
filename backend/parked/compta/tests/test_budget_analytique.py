"""Tests FG149 (budget-vs-réalisé), FG150 (analytique), FG151 (pilotage).

Couvre : la variance budget-vs-réalisé lue du grand livre, le résultat ventilé
par centre de coût (axe analytique posé sur la ligne d'écriture), le cockpit
directeur (résultat, trésorerie, marge brute %, DSO/DPO), la pose ``company``
côté serveur, l'isolation multi-société et le gate de rôle. Tout se déduit du
grand livre de la compta.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Budget, CentreCout, Journal

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _od(company, lignes_par_numero, *, jour, centre=None):
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = []
    for numero, debit, credit in lignes_par_numero:
        lignes.append({
            'compte': services.get_compte(company, numero),
            'debit': Decimal(debit), 'credit': Decimal(credit),
            'centre_cout': centre,
        })
    return services.creer_ecriture(
        company, journal, jour, 'Test', lignes,
        statut='validee')


class BudgetVsRealiseTests(TestCase):
    def setUp(self):
        self.co = make_company('fg149', 'FG149 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'fg149-user')

    def test_variance_budget_vs_realise(self):
        compte = services.get_compte(self.co, '6111')  # achats (charge).
        budget = services.creer_budget(
            self.co, annee=2026, libelle='B2026',
            lignes=[{'compte': compte, 'm01': '10000', 'm02': '10000'}],
            user=self.user)
        # Réalisé : 15 000 d'achats en 2026 (charge, débit).
        _od(self.co, [('6111', '15000', '0'), ('5141', '0', '15000')],
            jour=date(2026, 1, 15))
        data = selectors.budget_vs_realise(self.co, budget)
        self.assertEqual(data['total_budget'], Decimal('20000'))
        self.assertEqual(data['total_realise'], Decimal('15000'))
        self.assertEqual(data['total_variance'], Decimal('-5000'))

    def test_create_budget_api_pose_company(self):
        compte = services.get_compte(self.co, '6111')
        resp = auth(self.user).post(
            '/api/django/compta/budgets/',
            {'annee': 2026, 'libelle': 'API',
             'lignes': [{'compte': compte.id, 'm01': '1000'}]},
            format='json')
        self.assertEqual(resp.status_code, 201)
        b = Budget.objects.get(id=resp.data['id'])
        self.assertEqual(b.company_id, self.co.id)
        self.assertEqual(b.lignes.count(), 1)


class AnalytiqueTests(TestCase):
    def setUp(self):
        self.co = make_company('fg150', 'FG150 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'fg150-user')

    def test_resultat_par_centre_cout(self):
        chantier = services.creer_centre_cout(
            self.co, code='CH-01', libelle='Chantier 1')
        # Produit 100 000 et charge 60 000 imputés au chantier.
        _od(self.co, [('5141', '100000', '0'), ('7121', '0', '100000')],
            jour=date(2026, 2, 1), centre=chantier)
        _od(self.co, [('6111', '60000', '0'), ('5141', '0', '60000')],
            jour=date(2026, 2, 2), centre=chantier)
        data = selectors.resultat_analytique(self.co)
        self.assertEqual(len(data['centres']), 1)
        cc = data['centres'][0]
        self.assertEqual(cc['code'], 'CH-01')
        self.assertEqual(cc['produits'], Decimal('100000'))
        self.assertEqual(cc['charges'], Decimal('60000'))
        self.assertEqual(cc['resultat'], Decimal('40000'))

    def test_centre_cout_api_create_isole(self):
        resp = auth(self.user).post(
            '/api/django/compta/centres-cout/',
            {'code': 'AG-01', 'libelle': 'Agence', 'axe': 'agence'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        cc = CentreCout.objects.get(id=resp.data['id'])
        self.assertEqual(cc.company_id, self.co.id)

    def test_refuse_role_normal(self):
        normal = make_user(self.co, 'fg150-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/centres-cout/',
            {'code': 'X', 'libelle': 'Y'}, format='json')
        self.assertEqual(resp.status_code, 403)


class PilotageTests(TestCase):
    def setUp(self):
        self.co = make_company('fg151', 'FG151 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'fg151-user')

    def test_cockpit_indicateurs(self):
        # CA 200 000, charges 120 000 → marge 80 000 (40 %).
        _od(self.co, [('3421', '200000', '0'), ('7121', '0', '200000')],
            jour=date(2026, 1, 10))
        _od(self.co, [('6111', '120000', '0'), ('5141', '0', '120000')],
            jour=date(2026, 1, 11))
        data = selectors.pilotage_financier(
            self.co, date_debut='2026-01-01', date_fin='2026-12-31')
        self.assertEqual(data['chiffre_affaires'], Decimal('200000'))
        self.assertEqual(data['marge_brute'], Decimal('80000'))
        self.assertEqual(data['marge_brute_pct'], Decimal('40.00'))
        self.assertEqual(data['encours_clients'], Decimal('200000'))

    def test_cockpit_api(self):
        resp = auth(self.user).get(
            '/api/django/compta/pilotage/cockpit/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-12-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('marge_brute_pct', resp.data)

    def test_refuse_role_normal(self):
        normal = make_user(self.co, 'fg151-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/pilotage/cockpit/')
        self.assertEqual(resp.status_code, 403)
