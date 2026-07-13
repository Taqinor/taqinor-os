"""NTSEC14 — Tests des appareils de confiance (skip MFA).

Prouve de bout en bout : un appareil marqué de confiance saute la MFA jusqu'à
expiration, la révocation reforce la MFA, et une société SANS opt-in exige
toujours la MFA (défaut inchangé). Couvre aussi ``TrustedDevice.is_trusted`` et
l'endpoint list/révoquer scopé à l'utilisateur.
"""
from datetime import timedelta

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.parametres.models_company import CompanyProfile
from authentication.models import Company

from apps.identity.models import TrustedDevice

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
}


@override_settings(CACHES=_LOCMEM_CACHE)
class TrustedDeviceLoginSkipTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='TD Co', slug='td-co')
        self.user = User.objects.create_user(
            username='bob', password='motdepasse1', company=self.company)
        # Active le 2FA TOTP.
        self.secret = pyotp.random_base32()
        self.user.totp_secret = self.secret
        self.user.totp_enabled = True
        self.user.save(update_fields=['totp_secret', 'totp_enabled'])
        self.api = APIClient()

    def _set_opt_in(self, value):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'allow_device_trust': value})

    def _trust(self, token='dev-token-abc', days=30):
        now = timezone.now()
        return TrustedDevice.objects.create(
            user=self.user, company=self.company, device_fingerprint=token,
            approuve_le=now, expire_le=now + timedelta(days=days),
            approuve_par=self.user)

    def _login(self, **extra):
        body = {'username': 'bob', 'password': 'motdepasse1'}
        body.update(extra)
        return self.api.post('/api/django/token/', body, format='json')

    def test_2fa_required_without_trusted_device(self):
        resp = self._login()
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(resp.data.get('otp_required'))

    def test_trusted_device_skips_mfa(self):
        self._set_opt_in(True)
        self._trust(token='dev-token-abc')
        self.api.cookies['device_trust_id'] = 'dev-token-abc'
        resp = self._login()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('access_token', resp.cookies)

    def test_revoked_device_reforces_mfa(self):
        self._set_opt_in(True)
        device = self._trust(token='dev-token-abc')
        device.revoque_le = timezone.now()
        device.save(update_fields=['revoque_le'])
        self.api.cookies['device_trust_id'] = 'dev-token-abc'
        resp = self._login()
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(resp.data.get('otp_required'))

    def test_expired_device_reforces_mfa(self):
        self._set_opt_in(True)
        self._trust(token='dev-token-abc', days=-1)  # déjà expiré
        self.api.cookies['device_trust_id'] = 'dev-token-abc'
        resp = self._login()
        self.assertEqual(resp.status_code, 401)

    def test_no_company_opt_in_always_requires_mfa(self):
        # Opt-in société False (défaut) : la confiance appareil est inerte.
        self._set_opt_in(False)
        self._trust(token='dev-token-abc')
        self.api.cookies['device_trust_id'] = 'dev-token-abc'
        resp = self._login()
        self.assertEqual(resp.status_code, 401)

    def test_login_with_trust_flag_mints_device_and_cookie(self):
        self._set_opt_in(True)
        resp = self._login(otp=pyotp.TOTP(self.secret).now(),
                           trust_device=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('device_trust_id', resp.cookies)
        self.assertTrue(
            TrustedDevice.objects.filter(user=self.user).exists())


class TrustedDeviceModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='M Co', slug='m-co')
        self.user = User.objects.create_user(
            username='carol', password='x', company=self.company)

    def _dev(self, **kw):
        now = timezone.now()
        defaults = dict(
            user=self.user, company=self.company,
            device_fingerprint='tok', approuve_le=now,
            expire_le=now + timedelta(days=10))
        defaults.update(kw)
        return TrustedDevice.objects.create(**defaults)

    def test_active_device_is_trusted(self):
        self._dev()
        self.assertTrue(TrustedDevice.is_trusted(self.user, 'tok'))

    def test_expired_not_trusted(self):
        self._dev(expire_le=timezone.now() - timedelta(days=1))
        self.assertFalse(TrustedDevice.is_trusted(self.user, 'tok'))

    def test_revoked_not_trusted(self):
        self._dev(revoque_le=timezone.now())
        self.assertFalse(TrustedDevice.is_trusted(self.user, 'tok'))

    def test_other_company_not_trusted(self):
        other_company = Company.objects.create(nom='Other', slug='other')
        other = User.objects.create_user(
            username='dave', password='x', company=other_company)
        self._dev()
        # dave (autre société) ne peut pas réutiliser le jeton de carol.
        self.assertFalse(TrustedDevice.is_trusted(other, 'tok'))

    def test_unknown_token_not_trusted(self):
        self._dev()
        self.assertFalse(TrustedDevice.is_trusted(self.user, 'wrong'))


class TrustedDeviceEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='E Co', slug='e-co')
        self.user = User.objects.create_user(
            username='erin', password='x', company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _dev(self, user=None):
        now = timezone.now()
        return TrustedDevice.objects.create(
            user=user or self.user, company=self.company,
            device_fingerprint='tok-%s' % now.timestamp(), approuve_le=now,
            expire_le=now + timedelta(days=10))

    def test_list_only_own_active_devices(self):
        self._dev()
        other = User.objects.create_user(
            username='frank', password='x', company=self.company)
        self._dev(user=other)  # ne doit pas apparaître
        resp = self.api.get('/api/django/identity/trusted-devices/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        self.assertEqual(len(data), 1)

    def test_revoke_soft_deletes(self):
        device = self._dev()
        resp = self.api.delete(
            '/api/django/identity/trusted-devices/%s/' % device.id)
        self.assertIn(resp.status_code, (200, 204))
        device.refresh_from_db()
        self.assertIsNotNone(device.revoque_le)

    def test_cannot_revoke_another_users_device(self):
        other = User.objects.create_user(
            username='gina', password='x', company=self.company)
        device = self._dev(user=other)
        resp = self.api.delete(
            '/api/django/identity/trusted-devices/%s/' % device.id)
        self.assertEqual(resp.status_code, 404)
        device.refresh_from_db()
        self.assertIsNone(device.revoque_le)
