"""NTCRD16/17 — police d'assurance-crédit (registre déclaratif, aucun appel
externe) + encours garantis par police/client (liste filtrable)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import EncoursGarantiClient, PoliceAssuranceCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd16-co', nom='NTCRD16 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD16And17Tests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='ntcrd16_com', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd16@example.com')

    def test_admin_creates_police(self):
        r = auth(self.admin).post('/api/django/credit/polices-assurance/', {
            'assureur': 'Allianz Trade', 'numero_police': 'AT-2026-001',
            'taux_couverture_pct': '90', 'plafond_global': '1000000',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        p = PoliceAssuranceCredit.objects.get(numero_police='AT-2026-001')
        self.assertEqual(p.company_id, self.company.id)

    def test_commercial_cannot_create_police(self):
        r = auth(self.commercial).post('/api/django/credit/polices-assurance/', {
            'assureur': 'Coface',
        }, format='json')
        self.assertEqual(r.status_code, 403)

    def test_encours_garanti_list_filter_by_client(self):
        police = PoliceAssuranceCredit.objects.create(
            company=self.company, assureur='Atradius')
        EncoursGarantiClient.objects.create(
            company=self.company, police=police, client=self.client_obj,
            montant_garanti=Decimal('50000'),
            statut_agrement=EncoursGarantiClient.StatutAgrement.ACCORDE)
        r = auth(self.admin).get(
            f'/api/django/credit/encours-garantis/?client={self.client_obj.id}')
        self.assertEqual(r.status_code, 200, r.data)
        results = r.data.get('results', r.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(Decimal(str(results[0]['montant_garanti'])), Decimal('50000'))
