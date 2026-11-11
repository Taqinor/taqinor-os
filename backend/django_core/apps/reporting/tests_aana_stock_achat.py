"""AANA26 (C-AANA-017) — ``valorisation_achat`` du rapport stock n'est servie
qu'à ``can_view_buy_prices``.

Scénario R6 : le Commercial livré, dont le rôle ne porte PAS ``prix_achat_voir``.
Avant le correctif : 200 avec ``valorisation_achat='300.00'``.

Données RÉELLES en base, vraie propriété ``can_view_buy_prices`` (aucun mock).
Retirer la condition rougit ce test.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/reports/stock/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestValorisationAchatGatee(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana26-co', defaults={'nom': 'AANA26 Co'})[0]
        Produit.objects.create(
            company=self.company, nom='Panneau', sku='AANA26-P',
            prix_vente=Decimal('150'), prix_achat=Decimal('100'),
            quantite_stock=3)

    def test_valorisation_achat_gatee(self):
        # ATST12 — le Commercial LIVRÉ (registre), sans ``prix_achat_voir``.
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=dict(CANONICAL_SYSTEM_ROLES)['Commercial'])
        commercial = User.objects.create_user(
            username='aana26_resp', password='x', company=self.company,
            role=role)
        self.assertFalse(commercial.can_view_buy_prices)

        resp = _api(commercial).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('valorisation_achat', resp.data)
        self.assertEqual(resp.data['valorisation_vente'], '450.00')

    def test_admin_voit_valorisation_achat(self):
        admin = User.objects.create_user(
            username='aana26_admin', password='x', role_legacy='admin',
            company=self.company)
        resp = _api(admin).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['valorisation_achat'], '300.00')
