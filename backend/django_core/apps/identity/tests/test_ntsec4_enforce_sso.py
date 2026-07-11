"""NTSEC4 — Enforce-SSO : interdire le login local quand ``enforce_sso`` actif.

Vérifie que : avec un IdP actif ``enforce_sso=True`` un membre ne peut plus se
connecter par mot de passe (403 sso_required) ; un super-admin le peut toujours ;
un compte break-glass le peut ; les sociétés sans IdP (ou IdP non-enforce) sont
strictement inchangées ; fail-open.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.identity.models import IdentityProvider

from .helpers import make_company, make_user

User = get_user_model()


def _login(username, password='x'):
    return APIClient().post(
        '/api/django/token/',
        {'username': username, 'password': password}, format='json')


class EnforceSsoTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.user = make_user(self.company, 'alice', role='normal')

    def test_no_idp_login_unchanged(self):
        resp = _login('alice')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_inactive_idp_login_unchanged(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='X', actif=False,
            enforce_sso=True)
        resp = _login('alice')
        self.assertEqual(resp.status_code, 200)

    def test_active_idp_without_enforce_login_unchanged(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='X', actif=True,
            enforce_sso=False)
        resp = _login('alice')
        self.assertEqual(resp.status_code, 200)

    def test_enforce_sso_blocks_local_login(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='X', actif=True,
            enforce_sso=True)
        resp = _login('alice')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertTrue(resp.data.get('sso_required'))

    def test_superuser_bypasses_enforce(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='X', actif=True,
            enforce_sso=True)
        su = User.objects.create_superuser(
            username='root', password='x', company=self.company)
        su.company = self.company
        su.save(update_fields=['company'])
        resp = _login('root')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_break_glass_bypasses_enforce(self):
        from unittest import mock
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='X', actif=True,
            enforce_sso=True)
        # NTSEC22 pas encore branché : on simule un octroi break-glass actif.
        with mock.patch('apps.identity.selectors.is_break_glass',
                        return_value=True):
            resp = _login('alice')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_wrong_password_still_401_not_sso(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='X', actif=True,
            enforce_sso=True)
        resp = _login('alice', password='WRONG')
        # Identifiants invalides : jamais révéler l'état SSO avant le mot de
        # passe prouvé — l'erreur d'identifiants (401) prime.
        self.assertEqual(resp.status_code, 401)
