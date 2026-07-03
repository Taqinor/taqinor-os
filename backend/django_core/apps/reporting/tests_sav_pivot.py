"""ZSAV7 — pivot tickets SAV (technicien×statut) + coûts gated + export xlsx."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.roles.models import Role
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()


class SavPivotBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='zsav7-pivot-co', defaults={'nom': 'ZSAV7 Pivot Co'})[0]
        self.user = User.objects.create_user(
            username='zsav7_pivot_u', password='x', role_legacy='responsable',
            company=self.company)
        self.tech = User.objects.create_user(
            username='zsav7_pivot_tech', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientPivot')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestSavTicketsPivot(SavPivotBase):
    def test_pivot_technicien_statut(self):
        Ticket.objects.create(
            company=self.company, reference='ZP-1', client=self.client_obj,
            technicien_responsable=self.tech, statut=Ticket.Statut.NOUVEAU)
        Ticket.objects.create(
            company=self.company, reference='ZP-2', client=self.client_obj,
            technicien_responsable=self.tech, statut=Ticket.Statut.NOUVEAU)
        Ticket.objects.create(
            company=self.company, reference='ZP-3', client=self.client_obj,
            technicien_responsable=self.tech, statut=Ticket.Statut.CLOTURE)
        resp = self.api.get('/api/django/reporting/insights/sav-tickets-pivot/')
        self.assertEqual(resp.status_code, 200)
        cells = resp.data['cells']
        tech_key = self.tech.username
        self.assertEqual(cells[tech_key]['nouveau'], 2)
        self.assertEqual(cells[tech_key]['cloture'], 1)

    def test_export_xlsx(self):
        Ticket.objects.create(
            company=self.company, reference='ZP-4', client=self.client_obj,
            technicien_responsable=self.tech)
        resp = self.api.get(
            '/api/django/reporting/insights/sav-tickets-pivot/?export=xlsx')
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_gated_to_responsable_or_admin(self):
        limited = User.objects.create_user(
            username='zsav7_limited', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limited)}')
        resp = api.get('/api/django/reporting/insights/sav-tickets-pivot/')
        self.assertEqual(resp.status_code, 403)


class TestSavTicketsCoutGating(SavPivotBase):
    def test_cout_visible_for_legacy_account_without_role(self):
        """Compte hérité sans rôle fin -> comportement historique (accès)."""
        Ticket.objects.create(
            company=self.company, reference='ZP-5', client=self.client_obj,
            technicien_responsable=self.tech, cout=Decimal('200'))
        resp = self.api.get(
            '/api/django/reporting/insights/sav-tickets-cout-moyen/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('rows', resp.data)

    def test_cout_hidden_without_permission(self):
        # Une permission d'écriture (pour passer IsResponsableOrAdmin) SANS
        # prix_achat_voir -> can_view_buy_prices doit rester False.
        role = Role.objects.create(
            company=self.company, nom='SansPrixAchat',
            permissions=['tickets_gerer'])
        restricted = User.objects.create_user(
            username='zsav7_restricted', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(restricted)}')
        resp = api.get(
            '/api/django/reporting/insights/sav-tickets-cout-moyen/')
        self.assertEqual(resp.status_code, 403)

    def test_cout_visible_with_permission(self):
        role = Role.objects.create(
            company=self.company, nom='AvecPrixAchat',
            permissions=['tickets_gerer', 'prix_achat_voir'])
        allowed = User.objects.create_user(
            username='zsav7_allowed', password='x', company=self.company,
            role=role)
        Ticket.objects.create(
            company=self.company, reference='ZP-6', client=self.client_obj,
            technicien_responsable=self.tech, cout=Decimal('300'))
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(allowed)}')
        resp = api.get(
            '/api/django/reporting/insights/sav-tickets-cout-moyen/')
        self.assertEqual(resp.status_code, 200)
