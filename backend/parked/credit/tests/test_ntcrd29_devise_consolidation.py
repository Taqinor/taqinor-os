"""NTCRD29 — réglage devise de consolidation : défaut MAD (comportement actuel
inchangé), modifiable par le Directeur."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import ReglageCredit

User = get_user_model()


def make_company(slug='ntcrd29-co', nom='NTCRD29 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD29DeviseConsolidationTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd29_admin', password='x', role_legacy='admin',
            company=self.company)

    def test_default_is_mad(self):
        reglage = ReglageCredit.get_or_default(self.company)
        self.assertEqual(reglage.devise_consolidation, 'MAD')

    def test_admin_can_change_devise(self):
        r = auth(self.admin).patch(
            '/api/django/credit/reglage/', {'devise_consolidation': 'EUR'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            ReglageCredit.objects.get(company=self.company).devise_consolidation,
            'EUR')
