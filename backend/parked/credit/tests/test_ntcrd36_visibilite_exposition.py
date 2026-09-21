"""NTCRD36 — visibilité restreinte du rapport d'exposition : un Commercial ne
voit que ses clients (via les documents qu'il a créés) ; le Directeur voit
tout le portefeuille société."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.roles.models import Role
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd36-co', nom='NTCRD36 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD36VisibiliteExpositionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.directeur = User.objects.create_user(
            username='ntcrd36_dir', password='x', role_legacy='admin',
            company=self.company)
        role_com = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'records_scope_equipe'])
        self.com = User.objects.create_user(
            username='ntcrd36_com', password='x', role_legacy='normal',
            company=self.company, role=role_com)
        self.mine = Client.objects.create(
            company=self.company, nom='Mine', email='mine36@example.com')
        self.other = Client.objects.create(
            company=self.company, nom='Other', email='other36@example.com')
        # Facture créée par le commercial → rattache "mine" à sa portée.
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N36001',
            client=self.mine, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), created_by=self.com)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N36002',
            client=self.other, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('7000'), created_by=self.directeur)

    def test_directeur_sees_all(self):
        r = auth(self.directeur).get('/api/django/credit/exposition/')
        self.assertEqual(r.status_code, 200, r.data)
        ids = {ligne['client_id'] for ligne in r.data['resultats']}
        self.assertIn(self.mine.id, ids)
        self.assertIn(self.other.id, ids)

    def test_commercial_sees_only_own(self):
        r = auth(self.com).get('/api/django/credit/exposition/')
        self.assertEqual(r.status_code, 200, r.data)
        ids = {ligne['client_id'] for ligne in r.data['resultats']}
        self.assertIn(self.mine.id, ids)
        self.assertNotIn(self.other.id, ids)
