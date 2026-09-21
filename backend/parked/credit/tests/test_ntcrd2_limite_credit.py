"""NTCRD2 — modèle ``LimiteCredit`` : company FK, client unique par société,
montant nullable (null = pas de limite = comportement actuel inchangé)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd2-co', nom='NTCRD2 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD2LimiteCreditTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd2@example.com')

    def test_client_without_limite_credit_is_unaffected(self):
        """Aucune LimiteCredit pour ce client => comportement actuel inchangé."""
        self.assertFalse(
            LimiteCredit.objects.filter(client=self.client_obj).exists())

    def test_create_limite_via_api(self):
        r = self.api.post('/api/django/credit/limites/', {
            'client': self.client_obj.id, 'montant_limite': '50000',
            'mode_hold': 'avertissement',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        limite = LimiteCredit.objects.get(client=self.client_obj)
        self.assertEqual(limite.company_id, self.company.id)
        self.assertEqual(limite.cree_par_id, self.admin.id)
        self.assertEqual(limite.montant_limite, Decimal('50000'))

    def test_montant_limite_nullable(self):
        limite = LimiteCredit.objects.create(
            company=self.company, client=self.client_obj, montant_limite=None,
            motif_null='Client historique, pas de limite définie.')
        self.assertIsNone(limite.montant_limite)

    def test_unique_together_company_client(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LimiteCredit.objects.create(
                    company=self.company, client=self.client_obj,
                    montant_limite=Decimal('20000'))

    def test_cross_company_isolation(self):
        other_co, _ = Company.objects.get_or_create(
            slug='ntcrd2-other', defaults={'nom': 'Autre'})
        other_client = Client.objects.create(
            company=other_co, nom='Autre client', email='other@example.com')
        LimiteCredit.objects.create(
            company=other_co, client=other_client, montant_limite=Decimal('1'))
        r = self.api.get('/api/django/credit/limites/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data.get('results', r.data)), 0)
