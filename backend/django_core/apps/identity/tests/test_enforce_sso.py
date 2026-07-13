"""NTSEC4 — Enforce-SSO : interdire le login local quand un IdP l'exige.

Garanties : avec ``enforce_sso`` actif un membre ordinaire ne peut plus se
connecter par mot de passe (403), un super-admin le peut toujours, et une
société sans IdP est totalement inchangée (fail-open).
"""
from django.core.cache import cache
from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from testkit.factories import CompanyFactory, UserFactory

from apps.identity.models import IdentityProvider
from apps.identity.selectors import local_password_login_blocked

_LOCMEM = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=_LOCMEM)
class EnforceSsoSelectorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)

    def test_no_idp_never_blocks(self):
        self.assertFalse(local_password_login_blocked(self.user))

    def test_active_enforcing_idp_blocks_member(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta',
            actif=True, enforce_sso=True)
        self.assertTrue(local_password_login_blocked(self.user))

    def test_inactive_idp_does_not_block(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta',
            actif=False, enforce_sso=True)
        self.assertFalse(local_password_login_blocked(self.user))

    def test_active_idp_without_enforce_does_not_block(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta',
            actif=True, enforce_sso=False)
        self.assertFalse(local_password_login_blocked(self.user))

    def test_superuser_exempt(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta',
            actif=True, enforce_sso=True)
        su = UserFactory(company=self.company, is_superuser=True)
        self.assertFalse(local_password_login_blocked(su))

    def test_other_company_idp_does_not_block(self):
        other = CompanyFactory()
        IdentityProvider.objects.create(
            company=other, protocol='saml', nom='Okta',
            actif=True, enforce_sso=True)
        self.assertFalse(local_password_login_blocked(self.user))


@override_settings(CACHES=_LOCMEM)
class EnforceSsoLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, username='alice', password='correct-horse')

    def _login(self, pwd='correct-horse'):
        return APIClient().post(
            '/api/django/token/',
            {'username': 'alice', 'password': pwd}, format='json')

    def test_login_ok_without_idp(self):
        r = self._login()
        self.assertEqual(r.status_code, 200, r.content)

    def test_login_blocked_when_enforced(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta',
            actif=True, enforce_sso=True)
        r = self._login()
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json().get('sso_required'))
