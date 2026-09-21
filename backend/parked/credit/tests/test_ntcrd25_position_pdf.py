"""NTCRD25 — rapport interne « Position crédit client » : le HTML porte le
filigrane USAGE INTERNE et ne fuit jamais de prix d'achat/marge."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.credit.services import _html_position_credit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd25-co', nom='NTCRD25 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD25PositionPdfTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd25_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd25@example.com')
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'))
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N25001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('25000'), created_by=self.user)

    def test_html_has_watermark_and_no_purchase_price(self):
        html = _html_position_credit(self.client_obj)
        self.assertIn('USAGE INTERNE', html)
        self.assertIn(f'FAC-{MONTH}-N25001', html)
        # Aucune fuite de prix d'achat / marge.
        self.assertNotIn('prix_achat', html)
        self.assertNotIn('marge', html.lower())

    def test_html_contains_position_figures(self):
        html = _html_position_credit(self.client_obj)
        self.assertIn('100000', html)
        self.assertIn('25000', html)
