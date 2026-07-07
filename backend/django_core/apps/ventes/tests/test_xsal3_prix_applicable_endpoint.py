"""XSAL3 — GET /api/django/ventes/prix-applicable/?produit=&client=&quantite=

Câble la tarification XSAL1/XSAL2 dans un endpoint lecture seule, company-
scoped, consommé par le générateur de devis (partie frontend hors lane :
frontend/src/pages/ventes/DevisGenerator.jsx).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal3_prix_applicable_endpoint -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import CustomUser
from apps.ventes.models import ListePrix, LignePrixListe
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory, UserFactory, another_tenant


class TestPrixApplicableEndpoint(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'),
            prix_achat=Decimal('500.00'))
        self.liste = ListePrix.objects.create(company=self.company, nom='Rev')
        self.client_rev = ClientFactory(
            company=self.company, liste_prix=self.liste)
        LignePrixListe.objects.create(
            liste=self.liste, produit=self.produit,
            prix_unitaire=Decimal('880.00'))
        self.api = APIClient()
        token = AccessToken.for_user(self.user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_resolves_client_liste_price(self):
        resp = self.api.get(
            '/api/django/ventes/prix-applicable/',
            {'produit': self.produit.id, 'client': self.client_rev.id,
             'quantite': 1})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['prix'], '880.00')
        self.assertEqual(resp.data['source'], 'liste')
        self.assertEqual(resp.data['liste_nom'], 'Rev')

    def test_no_client_returns_standard_price(self):
        resp = self.api.get(
            '/api/django/ventes/prix-applicable/',
            {'produit': self.produit.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['prix'], '1000.00')
        self.assertEqual(resp.data['source'], 'standard')

    def test_missing_produit_param_is_rejected(self):
        resp = self.api.get('/api/django/ventes/prix-applicable/')
        self.assertEqual(resp.status_code, 400)

    def test_response_never_leaks_prix_achat(self):
        resp = self.api.get(
            '/api/django/ventes/prix-applicable/',
            {'produit': self.produit.id})
        self.assertNotIn('prix_achat', resp.data)
        self.assertNotIn('500.00', str(resp.data))

    def test_cross_tenant_produit_404(self):
        _other_company, other_user = another_tenant()
        api = APIClient()
        token = AccessToken.for_user(other_user)
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = api.get(
            '/api/django/ventes/prix-applicable/', {'produit': self.produit.id})
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_client_404(self):
        resp = self.api.get(
            '/api/django/ventes/prix-applicable/',
            {'produit': self.produit.id, 'client': 999999})
        self.assertEqual(resp.status_code, 404)
