"""NTCRD40 — export CSV des dérogations : 10 dérogations → 10 lignes + en-tête,
UTF-8 avec BOM (Excel FR)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import DerogationCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd40-co', nom='NTCRD40 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD40ExportCsvTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd40_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd40@example.com')
        for _ in range(10):
            DerogationCredit.objects.create(
                company=self.company, client=self.client_obj,
                montant_demande=Decimal('1000'))

    def test_csv_export_bom_and_rows(self):
        r = self.api.get(
            f'/api/django/credit/rapport-derogations/'
            f'?export=csv&client={self.client_obj.id}')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith('﻿'.encode('utf-8')))
        text = r.content.decode('utf-8-sig')
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 11)  # header + 10
