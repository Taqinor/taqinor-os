"""NTCRD22 — historique des changements de limite : chaque modification laisse
une trace horodatée consultable via l'endpoint historique."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd22-co', nom='NTCRD22 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD22HistoriqueTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd22_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd22@example.com')
        self.limite = LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'))

    def test_limit_change_is_logged(self):
        r = self.api.patch(
            f'/api/django/credit/limites/{self.limite.id}/',
            {'montant_limite': '25000'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        h = self.api.get(
            f'/api/django/credit/limites/{self.limite.id}/historique/')
        self.assertEqual(h.status_code, 200, h.data)
        self.assertGreaterEqual(h.data['count'], 1)
        entry = h.data['entries'][0]
        self.assertEqual(entry['field'], 'montant_limite')
        self.assertEqual(entry['acteur'], 'ntcrd22_admin')

    def test_no_change_no_log(self):
        r = self.api.patch(
            f'/api/django/credit/limites/{self.limite.id}/',
            {'montant_limite': '10000'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        h = self.api.get(
            f'/api/django/credit/limites/{self.limite.id}/historique/')
        self.assertEqual(h.data['count'], 0)
