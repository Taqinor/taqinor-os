"""ASEC52 — attribut ``Secure`` des cookies d'authentification décidé PAR
REQUÊTE, plus par ``not settings.DEBUG``.

La production tourne en ``settings.dev`` (``DEBUG=True``) derrière Caddy
(TLS) → nginx (HTTP) → Django : avant ASEC52 les cookies JWT y partaient
SANS ``Secure``. Désormais une requête arrivée en HTTPS au bord
(``X-Forwarded-Proto: https`` relayé par nginx, lu par
``SECURE_PROXY_SSL_HEADER`` posé dans ``settings/base.py``) reçoit des cookies
``Secure`` ; le développement HTTP local pur reste sans ``Secure``.

Run :
    python manage.py test authentication.tests_asec52_cookie_secure -v2
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from authentication.models import Company
from authentication.throttles import LoginRateThrottle

User = get_user_model()

_BON = 'Bon-mdp-123!'
_LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=_LOCMEM, DEBUG=True, AUTH_COOKIE_SECURE=None)
class CookieSecureTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch.object(
            LoginRateThrottle, 'allow_request', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.company = Company.objects.create(nom='ASEC52', slug='asec52')
        self.user = User.objects.create_user(
            username='asec52_u', password=_BON, company=self.company)

    def _login(self, https, **corps):
        extra = {'HTTP_X_FORWARDED_PROTO': 'https'} if https else {}
        corps.update({'username': 'asec52_u', 'password': _BON})
        r = APIClient().post('/api/django/token/', corps, format='json',
                             **extra)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r

    def test_proxy_ssl_header_declare_dans_base(self):
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER,
                         ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_debug_true_https_proxy_cookie_secure(self):
        r = self._login(https=True)
        for nom in ('access_token', 'refresh_token'):
            with self.subTest(cookie=nom):
                morsel = r.cookies[nom]
                self.assertTrue(morsel['secure'])
                self.assertTrue(morsel['httponly'])
                self.assertEqual(morsel['samesite'], 'Lax')

    def test_http_local_sans_secure(self):
        r = self._login(https=False)
        for nom in ('access_token', 'refresh_token'):
            with self.subTest(cookie=nom):
                self.assertFalse(r.cookies[nom]['secure'])

    def test_device_trust_secure(self):
        CompanyProfile.objects.create(
            company=self.company, allow_device_trust=True)
        r = self._login(https=True, trust_device=True)
        self.assertIn('device_trust_id', r.cookies)
        self.assertTrue(r.cookies['device_trust_id']['secure'])

    def test_refresh_https_cookie_secure(self):
        api = APIClient()
        api.post('/api/django/token/', {
            'username': 'asec52_u', 'password': _BON}, format='json',
            HTTP_X_FORWARDED_PROTO='https')
        with mock.patch('core.throttling.CookieRefreshThrottle.allow_request',
                        return_value=True):
            r = api.post('/api/django/auth/token/refresh/',
                         HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.cookies['access_token']['secure'])

    @override_settings(AUTH_COOKIE_SECURE=False)
    def test_reglage_explicite_l_emporte(self):
        r = self._login(https=True)
        self.assertFalse(r.cookies['access_token']['secure'])

    @override_settings(DEBUG=False)
    def test_debug_false_toujours_secure(self):
        r = self._login(https=False)
        self.assertTrue(r.cookies['access_token']['secure'])
