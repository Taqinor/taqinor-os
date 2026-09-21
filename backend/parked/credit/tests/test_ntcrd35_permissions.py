"""NTCRD35 — un Commercial reçoit 403 en modification de limite mais 200 sur
la fiche (lecture) ; réglages/écriture restent Directeur+."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.roles.models import Role

User = get_user_model()


def make_company(slug='ntcrd35-co', nom='NTCRD35 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD35PermissionsTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd35_admin', password='x', role_legacy='admin',
            company=self.company)
        role_com = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.commercial = User.objects.create_user(
            username='ntcrd35_com', password='x', role_legacy='normal',
            company=self.company, role=role_com)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd35@example.com')
        self.limite = LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'))

    def test_commercial_cannot_modify_limite(self):
        r = auth(self.commercial).patch(
            f'/api/django/credit/limites/{self.limite.id}/',
            {'montant_limite': '99999'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_commercial_can_read_fiche(self):
        r = auth(self.commercial).get(
            f'/api/django/credit/clients/{self.client_obj.id}/fiche/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_commercial_cannot_configure_reglages(self):
        r = auth(self.commercial).patch(
            '/api/django/credit/reglage/', {'mode_hold_defaut': 'blocage'},
            format='json')
        self.assertEqual(r.status_code, 403)

    def test_admin_can_modify_limite(self):
        r = auth(self.admin).patch(
            f'/api/django/credit/limites/{self.limite.id}/',
            {'montant_limite': '99999'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
