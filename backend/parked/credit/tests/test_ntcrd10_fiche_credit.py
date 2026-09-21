"""NTCRD10 — endpoint « fiche crédit client » : limite, encours, disponible,
pct utilisé, lettre de score, mode de hold, dérogations. Company-scopé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import DerogationCredit, LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd10-co', nom='NTCRD10 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD10FicheCreditTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd10_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd10@example.com')

    def _url(self, client_id=None):
        return f'/api/django/credit/clients/{client_id or self.client_obj.id}/fiche/'

    def test_fiche_consolidates_data(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N10001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('25000'), created_by=self.user)
        DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data['limite'])), Decimal('100000'))
        self.assertEqual(Decimal(str(r.data['encours'])), Decimal('25000'))
        self.assertEqual(Decimal(str(r.data['disponible'])), Decimal('75000'))
        self.assertEqual(r.data['mode_hold'], 'blocage')
        self.assertIn(r.data['lettre_score'], list('ABCDE'))
        self.assertEqual(len(r.data['derogations']), 1)

    def test_fiche_no_limite_is_unlimited(self):
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['limite'])
        self.assertIsNone(r.data['disponible'])
        self.assertFalse(r.data['depasse'])

    def test_cross_company_404(self):
        other_co, _ = Company.objects.get_or_create(
            slug='ntcrd10-other', defaults={'nom': 'Autre'})
        other_client = Client.objects.create(
            company=other_co, nom='Autre', email='o10@example.com')
        r = self.api.get(self._url(other_client.id))
        self.assertEqual(r.status_code, 404)
