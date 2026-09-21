"""NTCRD5 — sélecteur ``disponible_credit`` : limite - encours, None si
illimité, 85% utilisé => depasse=False, pct_utilise=0.85."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd5-co', nom='NTCRD5 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD5DisponibleCreditTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd5_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd5@example.com')

    def test_no_limite_is_unlimited(self):
        from apps.credit.selectors import disponible_credit
        result = disponible_credit(self.client_obj)
        self.assertIsNone(result['limite'])
        self.assertIsNone(result['disponible'])
        self.assertFalse(result['depasse'])

    def test_85_percent_utilise_not_depasse(self):
        from apps.credit.selectors import disponible_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'))
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N5001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('85000'), created_by=self.user)
        result = disponible_credit(self.client_obj)
        self.assertEqual(result['pct_utilise'], 0.85)
        self.assertFalse(result['depasse'])
        self.assertEqual(result['disponible'], Decimal('15000'))

    def test_depasse_when_over_limit(self):
        from apps.credit.selectors import disponible_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'))
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N5002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('15000'), created_by=self.user)
        result = disponible_credit(self.client_obj)
        self.assertTrue(result['depasse'])
        self.assertEqual(result['disponible'], Decimal('-5000'))
