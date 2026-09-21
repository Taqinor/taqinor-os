"""NTCRD27 — limite suggérée : règle documentée (2× encours arrondi millier),
toujours modifiable, cohérente."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd27-co', nom='NTCRD27 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD27LimiteSuggereeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd27_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd27@example.com')

    def test_suggestion_zero_without_encours(self):
        from apps.credit.selectors import limite_suggeree
        self.assertEqual(limite_suggeree(self.client_obj)['suggestion'], Decimal('0'))

    def test_suggestion_double_encours_rounded(self):
        from apps.credit.selectors import limite_suggeree
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N27001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('12500'), created_by=self.user)
        # encours 12500 → arrondi 13000 → ×2 = 26000
        self.assertEqual(
            limite_suggeree(self.client_obj)['suggestion'], Decimal('26000'))

    def test_endpoint(self):
        r = self.api.get(
            f'/api/django/credit/clients/{self.client_obj.id}/limite-suggeree/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('suggestion', r.data)
        self.assertIn('regle', r.data)
