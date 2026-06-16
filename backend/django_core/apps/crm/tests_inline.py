"""T4 — édition en place : un PATCH d'UN SEUL champ valide côté serveur et
journalise dans l'Historique (leads). Confirme aussi le PATCH mono-champ produit."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead, LeadActivity
from authentication.models import Company

User = get_user_model()


class TestInlineLeadEdit(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='inline-co', defaults={'nom': 'Inline Co'})[0]
        self.user = User.objects.create_user(
            username='inline_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_single_field_patch_logs_historique(self):
        lead = Lead.objects.create(company=self.company, nom='Test', stage='NEW')
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/', {'priorite': 'haute'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'haute')
        # Une entrée de modification (non « en masse ») est tracée.
        act = LeadActivity.objects.filter(lead=lead, field='priorite').first()
        self.assertIsNotNone(act)
        self.assertFalse(act.bulk)

    def test_single_field_patch_does_not_touch_other_fields(self):
        lead = Lead.objects.create(
            company=self.company, nom='Garde', prenom='Sara', stage='NEW',
            ville='Casablanca')
        self.api.patch(f'/api/django/crm/leads/{lead.id}/',
                       {'relance_date': '2026-09-01'}, format='json')
        lead.refresh_from_db()
        self.assertEqual(str(lead.relance_date), '2026-09-01')
        # Les autres champs restent intacts.
        self.assertEqual(lead.prenom, 'Sara')
        self.assertEqual(lead.ville, 'Casablanca')


class TestInlineProduitEdit(TestCase):
    def setUp(self):
        from apps.stock.models import Produit
        self.company = Company.objects.get_or_create(
            slug='inline-stock-co', defaults={'nom': 'Inline Stock Co'})[0]
        self.user = User.objects.create_user(
            username='inline_stock', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='INL-1',
            prix_vente=Decimal('1000'), quantite_stock=5)

    def test_single_field_price_patch(self):
        resp = self.api.patch(
            f'/api/django/stock/produits/{self.produit.id}/',
            {'prix_vente': '1250'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.prix_vente, Decimal('1250'))
        self.assertEqual(self.produit.quantite_stock, 5)  # inchangé
