"""DC12 — profil site/énergie réutilisable par client (SiteProfile).

Source unique du profil site/énergie/toiture : saisi une fois par client, le
générateur de devis le pré-remplit ensuite (y compris pour les devis sans lead).
Multi-tenant : société forcée côté serveur, jamais lue du corps de requête.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, SiteProfile
from apps.crm import selectors

User = get_user_model()


class TestSiteProfile(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='sp-co', defaults={'nom': 'SP Co'})[0]
        self.other = Company.objects.create(slug='sp-other', nom='Autre')
        self.user = User.objects.create_user(
            username='sp_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')

    def test_create_forces_company_server_side(self):
        # company envoyée dans le corps doit être ignorée (multi-tenant).
        r = self.api.post('/api/django/crm/site-profiles/', {
            'client': self.client_obj.id,
            'company': self.other.id,
            'facture_hiver': '1200',
            'type_installation': 'residentiel',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        sp = SiteProfile.objects.get(id=r.data['id'])
        self.assertEqual(sp.company_id, self.company.id)
        self.assertEqual(sp.created_by_id, self.user.id)
        self.assertEqual(sp.facture_hiver, Decimal('1200'))

    def test_client_must_be_same_company(self):
        foreign = Client.objects.create(company=self.other, nom='X')
        r = self.api.post('/api/django/crm/site-profiles/', {
            'client': foreign.id, 'facture_hiver': '900'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_list_scoped_to_company(self):
        SiteProfile.objects.create(
            company=self.company, client=self.client_obj)
        other_client = Client.objects.create(company=self.other, nom='Y')
        SiteProfile.objects.create(company=self.other, client=other_client)
        r = self.api.get('/api/django/crm/site-profiles/')
        self.assertEqual(r.status_code, 200)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), 1)

    def test_one_profile_per_client(self):
        SiteProfile.objects.create(
            company=self.company, client=self.client_obj)
        # OneToOne : un 2e profil pour le même client est rejeté.
        r = self.api.post('/api/django/crm/site-profiles/', {
            'client': self.client_obj.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_selector_returns_profile_dict(self):
        SiteProfile.objects.create(
            company=self.company, client=self.client_obj,
            facture_hiver=Decimal('1500'), conso_mensuelle_kwh=Decimal('800'),
            type_toiture='tuiles', orientation='sud')
        data = selectors.site_profile_for_client(
            self.client_obj.id, company=self.company)
        self.assertIsNotNone(data)
        self.assertEqual(data['facture_hiver'], Decimal('1500'))
        self.assertEqual(data['conso_mensuelle_kwh'], Decimal('800'))
        self.assertEqual(data['type_toiture'], 'tuiles')
        self.assertEqual(data['orientation'], 'sud')

    def test_selector_none_when_absent_or_cross_tenant(self):
        # Aucun profil → None.
        self.assertIsNone(
            selectors.site_profile_for_client(
                self.client_obj.id, company=self.company))
        # Profil d'une autre société jamais renvoyé.
        other_client = Client.objects.create(company=self.other, nom='Z')
        SiteProfile.objects.create(company=self.other, client=other_client)
        self.assertIsNone(
            selectors.site_profile_for_client(
                other_client.id, company=self.company))
