"""Durcissement auth (ERR45, ERR87, ERR88, ERR92).

Couvre :
- ERR45 : les cookies d'authentification restent SameSite=Strict (verrou anti
  relâchement silencieux) et httpOnly.
- ERR87 : le jeton d'accès est court ; le flux de refresh par cookie marche.
- ERR88 : ``seed_demo`` refuse de tourner hors DEBUG sans --force.
- ERR92 : sur un login réussi, l'audit normalise actor_username depuis le
  compte résolu (et non la chaîne brute de la requête).
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company

User = get_user_model()


class TestAuthCookieCsrfStrategy(TestCase):
    """ERR45 — les cookies JWT sont posés httpOnly + SameSite=Strict. C'est la
    barrière CSRF : ce test échoue si quelqu'un relâche SameSite en silence."""

    def setUp(self):
        self.company = Company.objects.create(nom='Cookie Co', slug='cookie-co')
        self.user = User.objects.create_user(
            username='cookie_user', password='secretpass1',
            role_legacy='admin', company=self.company)

    def test_auth_cookies_are_samesite_strict_and_httponly(self):
        api = APIClient()
        resp = api.post('/api/django/token/', {
            'username': 'cookie_user', 'password': 'secretpass1'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        for name in ('access_token', 'refresh_token'):
            self.assertIn(name, resp.cookies)
            cookie = resp.cookies[name]
            self.assertEqual(cookie['samesite'], 'Strict')
            self.assertTrue(cookie['httponly'])

    def test_refresh_flow_still_works(self):
        # ERR87 — le jeton d'accès est court, mais le refresh par cookie
        # renouvelle la session sans relogin.
        api = APIClient()
        login = api.post('/api/django/token/', {
            'username': 'cookie_user', 'password': 'secretpass1'},
            format='json')
        self.assertEqual(login.status_code, 200)
        # Le client APIClient conserve les cookies posés par la réponse.
        # CookieTokenRefreshView lit le refresh depuis le cookie (corps vide).
        refresh = api.post('/api/django/auth/token/refresh/')
        self.assertEqual(refresh.status_code, 200, refresh.data)
        self.assertIn('access_token', refresh.cookies)


class TestAccessTokenLifetime(TestCase):
    """ERR87 — la durée de vie du jeton d'accès est bornée à une valeur courte
    (≤ 30 min) pour limiter la fenêtre d'un access volé non révocable."""

    def test_access_token_lifetime_is_short(self):
        self.assertLessEqual(
            settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
            timedelta(minutes=30))


class TestSeedDemoProdGuard(TestCase):
    """ERR88 — seed_demo refuse de tourner hors DEBUG sans --force, pour ne
    jamais semer demo_admin/demo_resp (mot de passe connu) en production."""

    @override_settings(DEBUG=False)
    def test_seed_demo_refused_in_prod(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo')
        self.assertFalse(
            User.objects.filter(username='demo_admin').exists())

    @override_settings(DEBUG=False)
    def test_seed_demo_force_overrides(self):
        # --force permet de passer outre (environnement de démo explicite).
        # On vérifie seulement qu'aucun CommandError de garde n'est levé.
        try:
            call_command('seed_demo', force=True)
        except CommandError as exc:
            self.fail(f'--force ne devrait pas être bloqué : {exc}')


class TestLoginAuditActorNormalization(TestCase):
    """ERR92 — sur un login réussi, actor_username vient du compte résolu, pas
    de la chaîne brute (casse différente) fournie par le client."""

    def setUp(self):
        self.company = Company.objects.create(nom='Audit Co', slug='audit-co')
        self.user = User.objects.create_user(
            username='AuditUser', password='secretpass1',
            role_legacy='admin', company=self.company)

    def test_actor_username_comes_from_resolved_user(self):
        try:
            from apps.audit.models import AuditLog
        except Exception:
            self.skipTest('app audit indisponible')
        api = APIClient()
        resp = api.post('/api/django/token/', {
            'username': 'AuditUser', 'password': 'secretpass1'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN).order_by('-id').first()
        self.assertIsNotNone(row)
        # actor_username + FK user sont tous deux issus du compte résolu
        # (autorité), cohérents entre eux.
        self.assertEqual(row.user_id, self.user.id)
        self.assertEqual(row.actor_username, self.user.username)

    def test_failed_login_records_no_authoritative_actor(self):
        try:
            from apps.audit.models import AuditLog
        except Exception:
            self.skipTest('app audit indisponible')
        api = APIClient()
        before = AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN).count()
        resp = api.post('/api/django/token/', {
            'username': 'AuditUser', 'password': 'wrongpass'},
            format='json')
        self.assertEqual(resp.status_code, 401)
        # Un échec ne produit aucune ligne LOGIN (l'audit n'est écrit que sur
        # le chemin 200), donc pas d'actor truqué non plus.
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.LOGIN).count(),
            before)
