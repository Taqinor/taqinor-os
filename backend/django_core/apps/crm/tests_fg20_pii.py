"""FG20 — masquage des données sensibles (PII client/lead, marge).

Un rôle SANS ``client_pii_voir`` ne voit pas les coordonnées personnelles ;
un rôle SANS ``marge_voir`` ne voit pas l'indicateur de marge produit. Repli
historique : un compte légacy (sans rôle fin) garde l'accès complet."""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.roles.models import Role

User = get_user_model()


def _company(slug='fg20-co', nom='FG20 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG20ClientPiiTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.role_no_pii = Role.objects.create(
            company=self.company, nom='Lecture sans PII',
            permissions=['crm_voir', 'parametres_voir'])
        self.role_pii = Role.objects.create(
            company=self.company, nom='Lecture avec PII',
            permissions=['crm_voir', 'client_pii_voir', 'parametres_voir'])
        self.client_obj = Client.objects.create(
            company=self.company, nom='Test SARL',
            email='client@example.com', telephone='0612345678',
            adresse='12 rue du Soleil')

    def _api(self, role):
        u = User.objects.create_user(
            username=f'u_{role.id}', password='pw',
            role_legacy='utilisateur', role=role, company=self.company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(u)}')
        return api

    def test_pii_masked_without_permission(self):
        api = self._api(self.role_no_pii)
        r = api.get(f'/api/django/crm/clients/{self.client_obj.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.data['email'])
        self.assertIsNone(r.data['telephone'])
        self.assertIsNone(r.data['adresse'])
        # Le nom (non-PII) reste visible.
        self.assertEqual(r.data['nom'], 'Test SARL')

    def test_pii_visible_with_permission(self):
        api = self._api(self.role_pii)
        r = api.get(f'/api/django/crm/clients/{self.client_obj.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['email'], 'client@example.com')
        self.assertEqual(r.data['telephone'], '0612345678')

    def test_legacy_account_keeps_pii(self):
        u = User.objects.create_user(
            username='legacy', password='pw', role_legacy='admin',
            company=self.company)  # pas de rôle fin → repli historique
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(u)}')
        r = api.get(f'/api/django/crm/clients/{self.client_obj.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['email'], 'client@example.com')


class FG20MargePermissionTest(TestCase):
    """L'indicateur de marge produit dépend de ``marge_voir``."""

    def test_can_view_marge_helper(self):
        company = _company(slug='fg20-marge', nom='FG20 Marge')
        role_no = Role.objects.create(
            company=company, nom='Sans marge', permissions=['stock_voir'])
        role_yes = Role.objects.create(
            company=company, nom='Avec marge',
            permissions=['stock_voir', 'marge_voir'])
        u_no = User.objects.create_user(
            username='m_no', password='pw', role=role_no, company=company)
        u_yes = User.objects.create_user(
            username='m_yes', password='pw', role=role_yes, company=company)
        u_legacy = User.objects.create_user(
            username='m_legacy', password='pw', company=company)
        self.assertFalse(u_no.can_view_marge)
        self.assertTrue(u_yes.can_view_marge)
        self.assertTrue(u_legacy.can_view_marge)  # repli historique

    def test_marge_pct_value(self):
        from apps.stock.serializers import ProduitSerializer
        from apps.stock.models import Produit
        p = Produit(prix_achat=Decimal('80'), prix_vente=Decimal('100'))
        ser = ProduitSerializer()
        self.assertEqual(ser.get_marge_pct(p), '20.0')
        p2 = Produit(prix_achat=Decimal('0'), prix_vente=Decimal('100'))
        self.assertIsNone(ser.get_marge_pct(p2))
