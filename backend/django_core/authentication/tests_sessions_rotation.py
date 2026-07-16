"""Tests sessions actives + rotation forcée du mot de passe (N96).

Garanties centrales (additif, opt-in) :
  • Une connexion réussie crée UNE session traçable (appareil/IP), scopée à
    l'utilisateur ET à sa société. Un utilisateur ne voit JAMAIS les sessions
    d'un autre (multi-tenant).
  • Révoquer une session la retire de la liste et blackliste son jeton de
    rafraîchissement.
  • ``must_change_password`` défaut False : aucun compte existant n'est forcé.
    Un admin peut le passer à True ; le frontend le lit dans /auth/me/. Le
    changement de mot de passe efface le drapeau et horodate
    ``password_changed_at``.

Le throttle de connexion s'appuie sur le cache : on le bascule sur un cache
local en mémoire (pas de Redis) et on le vide avant chaque test.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company, UserSession

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}


@override_settings(CACHES=_LOCMEM_CACHE)
class TestActiveSessions(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Sess Co', slug='sess-co')
        self.other_company = Company.objects.create(
            nom='Autre Co', slug='autre-co')
        self.user = User.objects.create_user(
            username='alice', password='motdepasse1', company=self.company)
        self.api = APIClient()

    def _login(self, user='alice', pwd='motdepasse1'):
        return self.api.post(
            '/api/django/token/',
            {'username': user, 'password': pwd}, format='json')

    def test_login_creates_session_row(self):
        """Une connexion réussie crée une ligne UserSession scopée."""
        self.assertEqual(UserSession.objects.count(), 0)
        resp = self._login()
        self.assertEqual(resp.status_code, 200, resp.data)
        sessions = UserSession.objects.filter(user=self.user)
        self.assertEqual(sessions.count(), 1)
        s = sessions.first()
        self.assertEqual(s.company_id, self.company.id)
        self.assertFalse(s.revoked)
        self.assertTrue(s.jti)

    def test_session_list_marks_current_device(self):
        """La liste renvoie la session courante marquée ``is_current``."""
        self._login()
        resp = self.api.get('/api/django/auth/sessions/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertTrue(resp.data[0]['is_current'])
        # Le jti ne doit jamais être exposé.
        self.assertNotIn('jti', resp.data[0])

    def test_sessions_are_tenant_scoped(self):
        """Un utilisateur ne voit jamais les sessions d'un autre tenant."""
        self._login()
        # Session d'un utilisateur d'une AUTRE société.
        other = User.objects.create_user(
            username='bob', password='motdepasse2',
            company=self.other_company)
        UserSession.objects.create(
            user=other, company=self.other_company, jti='other-jti')
        resp = self.api.get('/api/django/auth/sessions/')
        self.assertEqual(len(resp.data), 1)
        self.assertNotIn(
            'other-jti',
            [UserSession.objects.get(pk=r['id']).jti for r in resp.data])

    def test_revoke_session_marks_revoked_and_hides_it(self):
        """Révoquer une session la marque ``revoked`` et la retire de la liste."""
        self._login()
        sid = UserSession.objects.get(user=self.user).id
        resp = self.api.post(
            f'/api/django/auth/sessions/{sid}/revoke/')
        self.assertEqual(resp.status_code, 200, resp.data)
        UserSession.objects.get(pk=sid)
        self.assertTrue(UserSession.objects.get(pk=sid).revoked)
        # Plus listée.
        listing = self.api.get('/api/django/auth/sessions/')
        self.assertEqual(len(listing.data), 0)

    def test_cannot_revoke_other_users_session(self):
        """Révoquer la session d'un autre utilisateur → 404 (jamais autorisé)."""
        self._login()
        other = User.objects.create_user(
            username='bob', password='motdepasse2', company=self.company)
        other_session = UserSession.objects.create(
            user=other, company=self.company, jti='bob-jti')
        resp = self.api.post(
            f'/api/django/auth/sessions/{other_session.id}/revoke/')
        self.assertEqual(resp.status_code, 404)
        other_session.refresh_from_db()
        self.assertFalse(other_session.revoked)

    def test_sessions_endpoint_requires_auth(self):
        """Non authentifié → 401/403."""
        resp = self.api.get('/api/django/auth/sessions/')
        self.assertIn(resp.status_code, (401, 403))


@override_settings(CACHES=_LOCMEM_CACHE)
class TestForcedRotation(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Rot Co', slug='rot-co')
        self.user = User.objects.create_user(
            username='carol', password='ancienMotDePasse1',
            company=self.company)
        self.api = APIClient()

    def _login(self, pwd='ancienMotDePasse1'):
        return self.api.post(
            '/api/django/token/',
            {'username': 'carol', 'password': pwd}, format='json')

    def test_default_must_change_password_is_false(self):
        """Aucun compte n'est forcé par défaut (pas de verrouillage)."""
        self.assertFalse(self.user.must_change_password)
        self.assertIsNone(self.user.password_changed_at)

    def test_me_exposes_must_change_password(self):
        """/auth/me/ expose ``must_change_password`` pour le frontend."""
        self._login()
        resp = self.api.get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('must_change_password', resp.data)
        self.assertFalse(resp.data['must_change_password'])

    def test_change_password_clears_flag_and_stamps(self):
        """Le changement efface le drapeau et horodate password_changed_at."""
        self.user.must_change_password = True
        self.user.save(update_fields=['must_change_password'])
        self._login()
        resp = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'ancienMotDePasse1',
            'new_password': 'nouveauMotDePasse2',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertIsNotNone(self.user.password_changed_at)
        self.assertTrue(self.user.check_password('nouveauMotDePasse2'))

    def test_change_password_rejects_wrong_current(self):
        """Mauvais mot de passe actuel → 400, aucun changement."""
        self._login()
        resp = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'faux',
            'new_password': 'nouveauMotDePasse2',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ancienMotDePasse1'))

    # ── VX242 : le changement de mot de passe révoque les AUTRES sessions ──
    def test_change_password_revokes_other_sessions_but_not_current(self):
        """2 connexions actives ; on change le mot de passe depuis la 1re
        (cookies encore posés par ce client) : la 2e session doit être
        blacklistée/révoquée, la session courante doit rester active."""
        self._login()
        current_session = UserSession.objects.get(user=self.user)
        # Simule une 2e session active (autre appareil) sans passer par ce
        # client (qui écraserait les cookies de la session courante).
        other_session = UserSession.objects.create(
            user=self.user, company=self.company, jti='other-device-jti')

        resp = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'ancienMotDePasse1',
            'new_password': 'nouveauMotDePasse2',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data.get('sessions_revoked'), 1)

        other_session.refresh_from_db()
        self.assertTrue(other_session.revoked)
        current_session.refresh_from_db()
        self.assertFalse(current_session.revoked)

    def test_change_password_blacklists_other_session_refresh_token(self):
        """La révocation blackliste aussi le jeton de rafraîchissement (pas
        seulement le flag `revoked`) : réutiliser ROTATE_REFRESH_TOKENS doit
        être bloqué. On vérifie via BlacklistedToken sur un OutstandingToken
        réel émis pour ce jti."""
        from django.utils import timezone
        from rest_framework_simplejwt.token_blacklist.models import (
            OutstandingToken, BlacklistedToken,
        )
        self._login()
        outstanding = OutstandingToken.objects.create(
            user=self.user, jti='blacklist-me-jti',
            token='fake-token-value',
            created_at=timezone.now(), expires_at=timezone.now(),
        )
        UserSession.objects.create(
            user=self.user, company=self.company, jti='blacklist-me-jti')

        resp = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'ancienMotDePasse1',
            'new_password': 'nouveauMotDePasse2',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            BlacklistedToken.objects.filter(token=outstanding).exists())

    def test_change_password_no_other_sessions_reports_zero(self):
        """Une seule session active (la courante) : sessions_revoked=0, aucun
        message additionnel n'est nécessaire."""
        self._login()
        resp = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'ancienMotDePasse1',
            'new_password': 'nouveauMotDePasse2',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data.get('sessions_revoked'), 0)

    def test_admin_can_force_rotation_via_user_endpoint(self):
        """Un admin peut poser must_change_password sur un compte de sa société."""
        from apps.roles.models import Role
        admin_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=['users_voir', 'roles_gerer'], est_systeme=True)
        admin = User.objects.create_user(
            username='admin', password='adminpass1',
            company=self.company, role=admin_role, role_legacy='admin')
        self.api.force_authenticate(user=admin)
        resp = self.api.patch(
            f'/api/django/users/{self.user.id}/',
            {'must_change_password': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)
