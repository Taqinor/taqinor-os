"""T5 — recherche globale + notifications in-app (multi-tenant, lecture seule)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Facture
from authentication.models import Company

User = get_user_model()


class TestGlobalSearch(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='search-co', defaults={'nom': 'Search Co'})[0]
        self.other = Company.objects.create(slug='search-other', nom='Autre')
        self.user = User.objects.create_user(
            username='search_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_search_finds_lead_and_is_scoped(self):
        Lead.objects.create(company=self.company, nom='Bennani', prenom='Salma')
        Lead.objects.create(company=self.other, nom='Bennani', prenom='Autre')
        resp = self.api.get('/api/django/reporting/search/?q=Bennani')
        self.assertEqual(resp.status_code, 200)
        lead_group = next(
            (g for g in resp.data['groups'] if g['type'] == 'lead'), None)
        self.assertIsNotNone(lead_group)
        # Seul le lead de NOTRE société est renvoyé (multi-tenant).
        self.assertEqual(len(lead_group['results']), 1)
        self.assertIn('Bennani', lead_group['results'][0]['label'])

    def test_short_query_returns_nothing(self):
        resp = self.api.get('/api/django/reporting/search/?q=a')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['groups'], [])


class TestNotifications(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='notif-co', defaults={'nom': 'Notif Co'})[0]
        self.user = User.objects.create_user(
            username='notif_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_overdue_invoice_flagged(self):
        client = Client.objects.create(company=self.company, nom='C')
        Facture.objects.create(
            company=self.company, reference='FAC-NOTIF-1', client=client,
            statut=Facture.Statut.EN_RETARD,
            date_echeance=date.today() - timedelta(days=10),
            taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['total'], 1)
        fac = resp.data['factures_impayees']
        self.assertEqual(len(fac), 1)
        self.assertTrue(fac[0]['overdue'])

    def test_structure_keys_present(self):
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        for key in ('total', 'activites_en_retard', 'garanties_expirantes',
                    'factures_impayees'):
            self.assertIn(key, resp.data)
