"""NTCRD23 — badge crédit : un client en blocage + dépassement ressort en
'rouge' ; batch endpoint company-scopé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd23-co', nom='NTCRD23 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD23BadgeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd23_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.blocked = Client.objects.create(
            company=self.company, nom='Bloqué', email='blk23@example.com')
        self.ok = Client.objects.create(
            company=self.company, nom='OK', email='ok23@example.com')

    def test_blocked_client_is_red(self):
        from apps.credit.selectors import badge_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.blocked,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N23001',
            client=self.blocked, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), created_by=self.user)
        self.assertEqual(badge_credit(self.blocked), 'rouge')

    def test_client_without_limite_is_green(self):
        from apps.credit.selectors import badge_credit
        self.assertEqual(badge_credit(self.ok), 'vert')

    def test_batch_endpoint(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.blocked,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N23002',
            client=self.blocked, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), created_by=self.user)
        r = self.api.get(
            f'/api/django/credit/badges/?client_ids={self.blocked.id},{self.ok.id}')
        self.assertEqual(r.status_code, 200, r.data)
        data = r.json()
        self.assertEqual(data[str(self.blocked.id)], 'rouge')
        self.assertEqual(data[str(self.ok.id)], 'vert')
