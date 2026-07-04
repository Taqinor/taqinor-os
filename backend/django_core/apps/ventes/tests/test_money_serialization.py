"""Test-garde YDATA9 — DRF sérialise les `Decimal` en STRING (jamais en float
JSON, qui perdrait la précision à la frontière API). `COERCE_DECIMAL_TO_STRING`
est désormais posé EXPLICITEMENT dans `REST_FRAMEWORK` (erp_agentique/settings/
base.py) : ce test verrouille le comportement — l'inverser fait échouer ce
test."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()


def make_company(slug='ydata9-co', nom='YDATA9 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestMoneySerializedAsString(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ydata9_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='D9',
            email='ydata9@example.com', telephone='+212600000014')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YDATA9',
            prix_vente=Decimal('1234.56'), quantite_stock=10,
            tva=Decimal('0'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YDATA9-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('0.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1234.56'),
            taux_tva=Decimal('0.00'))

    def test_money_serialized_as_string(self):
        r = self.api.get(f'/api/django/ventes/factures/{self.facture.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        # r.data is DRF's parsed representation (post-serializer, pre-JSON
        # render) — total_ttc must already be a str, not a float, confirming
        # the serializer field itself round-trips as a string end-to-end.
        self.assertIsInstance(r.data['total_ttc'], str)
        self.assertEqual(r.data['total_ttc'], '1234.56')
        # Round-trip through the actual rendered JSON bytes too, to prove the
        # wire format is genuinely a JSON string, never a bare float.
        raw = r.content.decode('utf-8')
        self.assertIn('"total_ttc":"1234.56"', raw.replace(' ', ''))

    def test_coerce_decimal_to_string_setting_is_explicit(self):
        from django.conf import settings
        self.assertTrue(
            settings.REST_FRAMEWORK.get('COERCE_DECIMAL_TO_STRING'))
