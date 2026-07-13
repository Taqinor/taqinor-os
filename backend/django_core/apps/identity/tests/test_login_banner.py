"""NTSEC28 — Tests de la bannière de connexion configurable.

Avec un texte configuré : la bannière est renvoyée et l'accusé est journalisé
(scopé société). Sans texte : réponse vide et aucun accusé (écran inchangé).
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.parametres.models_company import CompanyProfile
from authentication.models import Company, CustomUser


class LoginBannerTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.company = Company.objects.create(nom='Banner Co', slug='banner-co')
        self.user = CustomUser.objects.create_user(
            username='hank', password='x', company=self.company)

    def _profile(self, text):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'login_banner_text': text})

    # ── GET ────────────────────────────────────────────────────────────────
    def test_get_returns_configured_banner(self):
        self._profile('Accès autorisé uniquement.')
        resp = self.api.get(
            '/api/django/identity/login-banner/', {'username': 'hank'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data['login_banner_text'], 'Accès autorisé uniquement.')

    def test_get_without_config_returns_empty(self):
        self._profile('')
        resp = self.api.get(
            '/api/django/identity/login-banner/', {'username': 'hank'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['login_banner_text'], '')

    def test_get_unknown_username_still_200(self):
        resp = self.api.get(
            '/api/django/identity/login-banner/', {'username': 'ghost'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('login_banner_text', resp.data)

    # ── POST (accusé) ────────────────────────────────────────────────────────
    def test_ack_logged_when_banner_configured(self):
        self._profile('Accès autorisé uniquement.')
        before = AuditLog.objects.count()
        resp = self.api.post(
            '/api/django/identity/login-banner/',
            {'username': 'hank'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['acknowledged'])
        self.assertEqual(AuditLog.objects.count(), before + 1)
        row = AuditLog.objects.latest('id')
        self.assertEqual(row.company_id, self.company.id)
        self.assertEqual(row.action, AuditLog.Action.SECURITY_ALERT)

    def test_ack_noop_without_banner(self):
        self._profile('')
        before = AuditLog.objects.count()
        resp = self.api.post(
            '/api/django/identity/login-banner/',
            {'username': 'hank'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['acknowledged'])
        self.assertEqual(AuditLog.objects.count(), before)
