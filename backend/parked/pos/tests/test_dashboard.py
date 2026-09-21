"""XPOS11 — Reporting ventes comptoir (dashboard 6 axes + drill-down).

Couvre : le dashboard rend les 6 axes, la marge est invisible sans la
permission ``prix_achat_voir``, export xlsx.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import selectors, services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit

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


class DashboardSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos11', 'XPOS11 Co')
        self.user = make_user(self.co, 'caissier-xpos11')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur', prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'), quantite_stock=20, categorie=categorie)

        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-DASH-1', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation='Onduleur',
            quantite=1, prix_unitaire_ttc=Decimal('1000'))
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '1000'}],
            user=self.user)

    def test_dashboard_data_axes(self):
        data = selectors.dashboard_data(company=self.co)
        self.assertEqual(data['nb_ventes'], 1)
        self.assertIn('par_jour', data)
        self.assertIn('par_session', data)
        self.assertIn('par_caissier', data)
        self.assertIn('par_mode_paiement', data)
        self.assertIn('par_produit', data)
        self.assertIn('par_categorie', data)

    def test_marge_absent_without_include_marge(self):
        data = selectors.dashboard_data(company=self.co, include_marge=False)
        for row in data['par_produit'].values():
            self.assertNotIn('marge', row)

    def test_marge_present_with_include_marge(self):
        data = selectors.dashboard_data(company=self.co, include_marge=True)
        row = data['par_produit']['Onduleur']
        self.assertIn('marge', row)
        self.assertEqual(Decimal(row['marge']), Decimal('400.00'))

    def test_export_xlsx_never_contains_prix_achat(self):
        response = selectors.export_dashboard_xlsx(company=self.co)
        content = response.content
        self.assertNotIn(b'prix_achat', content)
        self.assertNotIn(b'600', content)


class DashboardApiTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos11-api', 'XPOS11 API Co')
        self.admin = make_user(self.co, 'admin-xpos11', role='admin')

    def test_dashboard_endpoint(self):
        api = auth(self.admin)
        resp = api.get('/api/django/pos/ventes/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('nb_ventes', resp.data)

    def test_dashboard_export_endpoint(self):
        api = auth(self.admin)
        resp = api.get('/api/django/pos/ventes/dashboard-export/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet')
