"""N98 — programme de parrainage (multi-tenant, récompense par défaut, stats)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Parrainage
from apps.parametres.models import CompanyProfile

User = get_user_model()


class TestParrainage(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='parr-co', defaults={'nom': 'Parr Co'})[0]
        self.other = Company.objects.create(slug='parr-other', nom='Autre')
        self.user = User.objects.create_user(
            username='parr_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.parrain = Client.objects.create(
            company=self.company, nom='Parrain')

    def test_create_prefills_reward_from_settings(self):
        prof = CompanyProfile.get(self.company)
        prof.referral_reward = Decimal('500')
        prof.save(update_fields=['referral_reward'])
        r = self.api.post('/api/django/crm/parrainages/', {
            'parrain': self.parrain.id, 'filleul_nom': 'Ami'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data['recompense']), Decimal('500'))

    def test_explicit_reward_respected(self):
        r = self.api.post('/api/django/crm/parrainages/', {
            'parrain': self.parrain.id, 'filleul_nom': 'Ami',
            'recompense': '750'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data['recompense']), Decimal('750'))

    def test_parrain_must_be_same_company(self):
        foreign = Client.objects.create(company=self.other, nom='X')
        r = self.api.post('/api/django/crm/parrainages/', {
            'parrain': foreign.id, 'filleul_nom': 'Ami'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_list_scoped_to_company(self):
        Parrainage.objects.create(company=self.company, parrain=self.parrain)
        Parrainage.objects.create(
            company=self.other,
            parrain=Client.objects.create(company=self.other, nom='P2'))
        r = self.api.get('/api/django/crm/parrainages/')
        self.assertEqual(r.status_code, 200)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), 1)

    def test_stats_endpoint(self):
        Parrainage.objects.create(
            company=self.company, parrain=self.parrain,
            statut=Parrainage.Statut.RECOMPENSE_VERSEE,
            recompense=Decimal('300'))
        r = self.api.get('/api/django/crm/parrainages/stats/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['total'], 1)
        self.assertEqual(Decimal(r.data['recompenses_versees']), Decimal('300'))
