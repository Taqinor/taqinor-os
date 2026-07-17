"""NTCRD26 — rapport « Dérogations crédit » périodique : total approuvées =
DerogationCredit.statut='approuvee' de la période, company-scopé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import DerogationCredit
from apps.credit.services import approuver_derogation
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd26-co', nom='NTCRD26 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD26RapportDerogationsTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd26_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd26@example.com')

    def test_total_approved_matches(self):
        d1 = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('3000'))
        approuver_derogation(d1, self.admin)
        r = self.api.get('/api/django/credit/rapport-derogations/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_approuvees'], 1)
        self.assertEqual(len(r.data['lignes']), 2)
        expected = DerogationCredit.objects.filter(
            company=self.company,
            statut=DerogationCredit.Statut.APPROUVEE).count()
        self.assertEqual(r.data['nb_approuvees'], expected)

    def test_xlsx_export(self):
        DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        r = self.api.get('/api/django/credit/rapport-derogations/?format=xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content[:2] == b'PK')

    def test_company_scoped(self):
        other_co, _ = Company.objects.get_or_create(
            slug='ntcrd26-other', defaults={'nom': 'Autre'})
        other_client = Client.objects.create(
            company=other_co, nom='Autre', email='o26@example.com')
        DerogationCredit.objects.create(
            company=other_co, client=other_client,
            montant_demande=Decimal('9000'))
        r = self.api.get('/api/django/credit/rapport-derogations/')
        self.assertEqual(len(r.data['lignes']), 0)
