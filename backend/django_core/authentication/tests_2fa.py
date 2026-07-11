"""Tests double authentification TOTP (2FA) — opt-in par utilisateur (N96).

Garantie centrale : le 2FA est STRICTEMENT optionnel. Un compte sans 2FA se
connecte exactement comme avant (aucun verrouillage possible). Une fois activé,
la connexion exige un code TOTP valide ; la désactivation le retire.

Les codes valides sont produits avec ``pyotp.TOTP(secret).now()`` — jamais en
dur — pour rester robustes à l'horloge.
"""
import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()

# Le throttle de connexion (/token/) s'appuie sur le cache. En test on le
# bascule sur un cache local en mémoire — pas de dépendance Redis — et on le
# vide avant chaque test pour que les multiples connexions d'un même cas ne
# heurtent pas la limite 5/min (le comportement réel du throttle est couvert
# ailleurs ; ici on teste le 2FA).
_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}


@override_settings(CACHES=_LOCMEM_CACHE)
class TestTwoFactorLogin(TestCase):
    """Le 2FA n'affecte que les comptes qui l'ont activé."""

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='2FA Co', slug='fa-co')
        self.user = User.objects.create_user(
            username='alice', password='motdepasse1', company=self.company,
        )
        self.api = APIClient()

    def _login(self, **extra):
        body = {'username': 'alice', 'password': 'motdepasse1'}
        body.update(extra)
        return self.api.post('/api/django/token/', body, format='json')

    # ── Compte SANS 2FA : connexion inchangée ───────────────────────────
    def test_login_without_2fa_works_as_before(self):
        """Un utilisateur sans 2FA se connecte sans aucun code (comme avant)."""
        resp = self._login()
        self.assertEqual(resp.status_code, 200, resp.data)
        # Les cookies httpOnly sont posés (access/refresh sortis du corps).
        self.assertIn('access_token', resp.cookies)

    def test_login_without_2fa_ignores_stray_otp(self):
        """Un otp parasite n'empêche pas un compte sans 2FA de se connecter."""
        resp = self._login(otp='000000')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_wrong_password_still_fails_without_revealing_2fa(self):
        resp = self._login(password='faux')
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn('otp_required', resp.data)


@override_settings(CACHES=_LOCMEM_CACHE)
class TestTwoFactorSetupEnableDisable(TestCase):
    """Cycle complet : setup → enable (code requis) → login → disable."""

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='2FA Co2', slug='fa-co2')
        self.user = User.objects.create_user(
            username='bob', password='motdepasse2', company=self.company,
        )
        self.auth = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.auth.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.anon = APIClient()

    def _login(self, **extra):
        body = {'username': 'bob', 'password': 'motdepasse2'}
        body.update(extra)
        return self.anon.post('/api/django/token/', body, format='json')

    def test_setup_returns_secret_and_uri_without_enabling(self):
        resp = self.auth.post('/api/django/auth/2fa/setup/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('secret', resp.data)
        self.assertIn('otpauth_uri', resp.data)
        self.assertTrue(resp.data['otpauth_uri'].startswith('otpauth://totp/'))
        self.user.refresh_from_db()
        # Le secret est posé mais le 2FA n'est PAS encore actif.
        self.assertTrue(self.user.totp_secret)
        self.assertFalse(self.user.totp_enabled)
        # Tant que non activé, la connexion reste libre.
        self.assertEqual(self._login().status_code, 200)

    def test_setup_returns_qr_as_inline_svg_never_a_third_party_url(self):
        """VX120 — le QR est un SVG rendu par NOTRE serveur (réutilise le
        générateur QR maison de `apps.stock.labels`), jamais une URL vers un
        service tiers (qui exfiltrerait la graine TOTP contenue dans
        `otpauth_uri` à un domaine non contrôlé)."""
        resp = self.auth.post('/api/django/auth/2fa/setup/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('qr_svg', resp.data)
        svg = resp.data['qr_svg']
        self.assertTrue(svg.strip().startswith('<svg'))
        # Pas de script ni de référence à un service tiers dans le SVG
        # lui-même (le seul "http://" légitime est le namespace XML du <svg>).
        self.assertNotIn('<script', svg)
        self.assertNotIn('qrserver.com', svg)

    def test_enable_requires_valid_code(self):
        setup = self.auth.post('/api/django/auth/2fa/setup/', {}, format='json')
        secret = setup.data['secret']

        # Code invalide → refus, 2FA toujours désactivé.
        bad = self.auth.post(
            '/api/django/auth/2fa/enable/', {'code': '000000'}, format='json')
        self.assertEqual(bad.status_code, 400, bad.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.totp_enabled)

        # Code valide → activation + codes de secours renvoyés une fois.
        good = self.auth.post(
            '/api/django/auth/2fa/enable/',
            {'code': pyotp.TOTP(secret).now()}, format='json')
        self.assertEqual(good.status_code, 200, good.data)
        self.assertIn('recovery_codes', good.data)
        self.assertTrue(len(good.data['recovery_codes']) >= 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.totp_enabled)

    def _enable_2fa(self):
        setup = self.auth.post('/api/django/auth/2fa/setup/', {}, format='json')
        secret = setup.data['secret']
        enable = self.auth.post(
            '/api/django/auth/2fa/enable/',
            {'code': pyotp.TOTP(secret).now()}, format='json')
        self.assertEqual(enable.status_code, 200, enable.data)
        return secret, enable.data['recovery_codes']

    def test_login_after_enable_requires_code(self):
        secret, _ = self._enable_2fa()

        # Sans code → bloqué avec un signal otp_required clair (401).
        missing = self._login()
        self.assertEqual(missing.status_code, 401, missing.data)
        self.assertTrue(missing.data.get('otp_required'))

        # Code faux → bloqué.
        wrong = self._login(otp='123456')
        self.assertEqual(wrong.status_code, 401, wrong.data)

        # Code valide → connexion OK.
        ok = self._login(otp=pyotp.TOTP(secret).now())
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertIn('access_token', ok.cookies)

    def test_recovery_code_logs_in_and_is_single_use(self):
        secret, codes = self._enable_2fa()
        code = codes[0]
        # Un code de secours permet la connexion.
        first = self._login(otp=code)
        self.assertEqual(first.status_code, 200, first.data)
        # Le même code de secours ne fonctionne plus (usage unique).
        second = self._login(otp=code)
        self.assertEqual(second.status_code, 401, second.data)
        # Mais le TOTP normal marche toujours.
        ok = self._login(otp=pyotp.TOTP(secret).now())
        self.assertEqual(ok.status_code, 200, ok.data)

    def test_disable_with_code_clears_2fa(self):
        secret, _ = self._enable_2fa()
        resp = self.auth.post(
            '/api/django/auth/2fa/disable/',
            {'code': pyotp.TOTP(secret).now()}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.totp_enabled)
        self.assertFalse(self.user.totp_secret)
        # Connexion redevient libre, comme avant 2FA.
        self.assertEqual(self._login().status_code, 200)

    def test_disable_with_password_clears_2fa(self):
        self._enable_2fa()
        resp = self.auth.post(
            '/api/django/auth/2fa/disable/',
            {'password': 'motdepasse2'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.totp_enabled)

    def test_disable_rejects_bad_verification(self):
        self._enable_2fa()
        resp = self.auth.post(
            '/api/django/auth/2fa/disable/',
            {'code': '000000'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.totp_enabled)

    def test_status_reflects_state(self):
        before = self.auth.get('/api/django/auth/2fa/status/')
        self.assertEqual(before.status_code, 200)
        self.assertFalse(before.data['enabled'])
        self._enable_2fa()
        after = self.auth.get('/api/django/auth/2fa/status/')
        self.assertTrue(after.data['enabled'])
        self.assertTrue(after.data['recovery_codes_remaining'] >= 1)
