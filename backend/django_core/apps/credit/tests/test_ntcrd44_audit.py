"""NTCRD44 — actions sensibles crédit tracées dans audit.AuditLog :
modification de limite + décision de dérogation."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.audit.models import AuditLog
from apps.credit.models import DerogationCredit, LimiteCredit
from apps.credit.services import approuver_derogation
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd44-co', nom='NTCRD44 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD44AuditTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd44_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd44@example.com')

    def test_limit_change_audited(self):
        limite = LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'))
        before = AuditLog.objects.count()
        auth(self.admin).patch(
            f'/api/django/credit/limites/{limite.id}/',
            {'montant_limite': '25000'}, format='json')
        self.assertGreater(AuditLog.objects.count(), before)

    def test_derogation_decision_audited(self):
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        before = AuditLog.objects.count()
        approuver_derogation(d, self.admin)
        self.assertGreater(AuditLog.objects.count(), before)
