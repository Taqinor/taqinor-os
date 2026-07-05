"""Tests ZACC2 — Colonne comparative N-1 sur bilan/CPC/balance/ESG.

Couvre : ``comparer=1`` renvoie chaque poste avec N, N-1 et écart %, un
exercice sans N-1 renvoie N-1=0 (jamais d'erreur), défaut sans paramètre =
réponse actuelle byte-identique.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services

User = get_user_model()


def make_company(slug='zacc2-co', nom='ZACC2 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        compte_clients = services.get_compte(self.company, '3421')
        compte_ventes = services.get_compte(self.company, '7121')
        journal_od = services._journal(
            self.company, services.Journal.Type.OPERATIONS_DIVERSES)
        # Exercice N (2026) : vente de 1000.
        services.creer_ecriture_od(
            self.company, '2026-03-10', 'Vente N',
            [
                {'compte': compte_clients, 'debit': Decimal('1000'),
                 'credit': Decimal('0')},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
            ], journal=journal_od)
        # Exercice N-1 (2025) : vente de 400.
        services.creer_ecriture_od(
            self.company, '2025-03-10', 'Vente N-1',
            [
                {'compte': compte_clients, 'debit': Decimal('400'),
                 'credit': Decimal('0')},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('400')},
            ], journal=journal_od)
        self.user = make_user(self.company, 'zacc2-admin')
        self.api = auth(self.user)


class TestSelectorsDefautInchange(_Base):
    """Sans ``comparer``, chaque selector renvoie EXACTEMENT son dict actuel."""

    def test_cpc_defaut_sans_champs_n1(self):
        data = selectors.cpc(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31')
        self.assertNotIn('montant_n1', data['produits'][0])
        self.assertNotIn('resultat_n1', data)

    def test_bilan_defaut_sans_champs_n1(self):
        data = selectors.bilan(self.company, date_fin='2026-12-31')
        self.assertNotIn('resultat_n1', data)
        for item in data['actif']:
            self.assertNotIn('montant_n1', item)

    def test_balance_defaut_sans_champs_n1(self):
        data = selectors.balance_generale(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31')
        self.assertNotIn('date_debut_n1', data)
        for li in data['lignes']:
            self.assertNotIn('solde_debiteur_n1', li)

    def test_esg_defaut_sans_champs_n1(self):
        data = selectors.esg(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31')
        self.assertNotIn('resultat_net_n1', data)
        for solde in data['soldes']:
            self.assertNotIn('montant_n1', solde)


class TestSelectorsComparatif(_Base):
    def test_cpc_comparatif_ecart(self):
        data = selectors.cpc(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31',
            comparer=True, date_debut_n1='2025-01-01',
            date_fin_n1='2025-12-31')
        self.assertEqual(data['resultat_n1'], Decimal('400'))
        self.assertEqual(data['resultat'], Decimal('1000'))
        self.assertEqual(data['resultat_ecart'], Decimal('600'))
        produit = next(
            p for p in data['produits'] if p['numero'] == '7121')
        self.assertEqual(produit['montant_n1'], Decimal('400'))
        self.assertEqual(produit['ecart'], Decimal('600'))
        self.assertEqual(produit['ecart_pct'], Decimal('150.00'))

    def test_bilan_comparatif(self):
        data = selectors.bilan(
            self.company, date_fin='2026-12-31', comparer=True,
            date_fin_n1='2025-12-31')
        self.assertIn('resultat_n1', data)
        self.assertEqual(data['resultat_n1'], Decimal('400'))

    def test_balance_comparatif(self):
        data = selectors.balance_generale(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31',
            comparer=True, date_debut_n1='2025-01-01',
            date_fin_n1='2025-12-31')
        ligne = next(li for li in data['lignes'] if li['numero'] == '3421')
        self.assertEqual(ligne['solde_debiteur_n1'], Decimal('400'))
        self.assertEqual(ligne['ecart_solde_debiteur'], Decimal('600'))

    def test_esg_comparatif(self):
        data = selectors.esg(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31',
            comparer=True, date_debut_n1='2025-01-01',
            date_fin_n1='2025-12-31')
        self.assertEqual(data['resultat_net_n1'], Decimal('400'))
        marge = next(s for s in data['soldes'] if s['code'] == 'MARGE')
        self.assertIn('montant_n1', marge)

    def test_exercice_sans_n1_renvoie_zero_jamais_erreur(self):
        """Un exercice trop ancien pour avoir un N-1 dans les données ->
        montant_n1 = 0, jamais d'exception."""
        data = selectors.cpc(
            self.company, date_debut='2020-01-01', date_fin='2020-12-31',
            comparer=True)
        self.assertEqual(data['resultat'], Decimal('0'))
        self.assertEqual(data['resultat_n1'], Decimal('0'))

    def test_comparer_sans_bornes_explicites_decale_un_an(self):
        """``comparer=True`` sans ``date_debut_n1``/``date_fin_n1`` déduit la
        période N-1 par décalage d'un an."""
        data = selectors.cpc(
            self.company, date_debut='2026-01-01', date_fin='2026-12-31',
            comparer=True)
        self.assertEqual(data['date_debut_n1'].year, 2025)
        self.assertEqual(data['resultat_n1'], Decimal('400'))


class TestEndpointComparatif(_Base):
    def test_cpc_endpoint_comparer_1(self):
        resp = self.api.get(
            '/api/django/compta/etats/cpc/?date_debut=2026-01-01'
            '&date_fin=2026-12-31&comparer=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('resultat_n1', resp.data)
        self.assertEqual(Decimal(str(resp.data['resultat_n1'])),
                         Decimal('400'))

    def test_cpc_endpoint_defaut_reponse_identique(self):
        resp_a = self.api.get(
            '/api/django/compta/etats/cpc/?date_debut=2026-01-01'
            '&date_fin=2026-12-31')
        resp_b = self.api.get(
            '/api/django/compta/etats/cpc/?date_debut=2026-01-01'
            '&date_fin=2026-12-31')
        self.assertEqual(resp_a.data, resp_b.data)
        self.assertNotIn('resultat_n1', resp_a.data)

    def test_bilan_endpoint_comparer_1(self):
        resp = self.api.get(
            '/api/django/compta/etats/bilan/?date_fin=2026-12-31&comparer=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('resultat_n1', resp.data)

    def test_balance_endpoint_comparer_1(self):
        resp = self.api.get(
            '/api/django/compta/etats/balance/?date_debut=2026-01-01'
            '&date_fin=2026-12-31&comparer=1')
        self.assertEqual(resp.status_code, 200)
        ligne = next(
            li for li in resp.data['lignes'] if li['numero'] == '3421')
        self.assertIn('solde_debiteur_n1', ligne)

    def test_esg_endpoint_comparer_1(self):
        resp = self.api.get(
            '/api/django/compta/etats/esg/?date_debut=2026-01-01'
            '&date_fin=2026-12-31&comparer=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('resultat_net_n1', resp.data)
