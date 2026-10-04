"""CIQ415 — réglage « responsable des leads commerciaux et industriels »."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()
URL = '/api/django/parametres/update/'


class TestResponsableLeadsPro(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ciq415-co', defaults={'nom': 'CIQ415 Co'})[0]
        self.other = Company.objects.get_or_create(
            slug='ciq415-other', defaults={'nom': 'CIQ415 Other'})[0]
        self.admin = User.objects.create_user(
            username='ciq415_admin', password='x', role_legacy='admin',
            company=self.company)
        self.mate = User.objects.create_user(
            username='ciq415_mate', password='x', role_legacy='admin',
            company=self.company)
        self.stranger = User.objects.create_user(
            username='ciq415_stranger', password='x', role_legacy='admin',
            company=self.other)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_other_company_user_rejected_naming_field(self):
        resp = self.api.patch(
            URL, {'responsable_leads_pro': self.stranger.pk}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('responsable_leads_pro', resp.data)

    def test_patch_then_get_identical(self):
        resp = self.api.patch(
            URL, {'responsable_leads_pro': self.mate.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['responsable_leads_pro'], self.mate.pk)
        got = self.api.get('/api/django/parametres/')
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.data['responsable_leads_pro'], self.mate.pk)

    def test_unset_by_default(self):
        got = self.api.get('/api/django/parametres/')
        self.assertEqual(got.status_code, 200)
        self.assertIsNone(got.data['responsable_leads_pro'])
