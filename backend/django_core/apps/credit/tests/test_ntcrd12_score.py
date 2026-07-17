"""NTCRD12 — endpoint score crédit : lettre A-E cohérente avec
``comportement_paiement`` + position vs limite + recommandation."""
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


def make_company(slug='ntcrd12-co', nom='NTCRD12 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD12ScoreTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd12_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd12@example.com')

    def _url(self, client_id=None):
        return f'/api/django/credit/clients/{client_id or self.client_obj.id}/score/'

    def test_score_matches_comportement_paiement(self):
        from apps.ventes.selectors import comportement_paiement
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['lettre'], comportement_paiement(self.client_obj)['lettre'])

    def test_recommandation_when_over_limit(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'))
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N12001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), created_by=self.user)
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['depasse'])
        self.assertIn('dérogation', r.data['recommandation'].lower())

    def test_cross_company_404(self):
        other_co, _ = Company.objects.get_or_create(
            slug='ntcrd12-other', defaults={'nom': 'Autre'})
        other_client = Client.objects.create(
            company=other_co, nom='Autre', email='o12@example.com')
        r = self.api.get(self._url(other_client.id))
        self.assertEqual(r.status_code, 404)
