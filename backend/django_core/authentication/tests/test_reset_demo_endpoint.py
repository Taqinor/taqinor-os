"""Tests du endpoint reset-demo (NTDMO7) + drapeaux démo /auth/me."""
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser


@override_settings(DEBUG=True)
class ResetDemoEndpointTest(TestCase):
    SLUG = 'taqinor-demo-full'

    def setUp(self):
        call_command('seed_demo_company', verbosity=0)
        self.demo = Company.objects.get(slug=self.SLUG)
        self.admin = CustomUser.objects.get(username='demo_admin_full')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_reset_demo_on_demo_company_succeeds(self):
        resp = self.client.post(
            f'/api/django/companies/{self.demo.id}/reset-demo/')
        self.assertEqual(resp.status_code, 200)
        # La société existe toujours (re-peuplée).
        self.assertTrue(Company.objects.filter(slug=self.SLUG).exists())

    def test_reset_demo_forbidden_on_non_demo_company(self):
        real = Company.objects.create(nom='Réelle SARL', slug='reelle-sarl')
        resp = self.client.post(
            f'/api/django/companies/{real.id}/reset-demo/')
        self.assertEqual(resp.status_code, 403)

    def test_me_exposes_demo_flags(self):
        resp = self.client.get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['company_est_demo'])
        self.assertFalse(resp.data['company_mode_presentation_actif'])

    def test_est_demo_read_only_via_company_api(self):
        real = Company.objects.create(nom='Réelle 2', slug='reelle-2')
        self.client.patch(
            f'/api/django/companies/{real.id}/', {'est_demo': True},
            format='json')
        real.refresh_from_db()
        self.assertFalse(real.est_demo)  # jamais écrit via l'API

    def test_presentation_mode_toggle_on_demo_company(self):
        resp = self.client.patch(
            f'/api/django/companies/{self.demo.id}/',
            {'mode_presentation_actif': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.demo.refresh_from_db()
        self.assertTrue(self.demo.mode_presentation_actif)

    def test_presentation_mode_forbidden_on_non_demo(self):
        real = Company.objects.create(nom='Réelle 3', slug='reelle-3')
        resp = self.client.patch(
            f'/api/django/companies/{real.id}/',
            {'mode_presentation_actif': True}, format='json')
        self.assertEqual(resp.status_code, 403)
        real.refresh_from_db()
        self.assertFalse(real.mode_presentation_actif)
