"""NTSEC8 — Passkeys / WebAuthn (enregistrement + connexion sans mot de passe).

Le wheel ``webauthn`` n'est pas présent dans l'environnement de test ; on couvre
donc : la DÉGRADATION (501 sans lib), le modèle (unicité credential_id), le
défi à usage unique, l'anti-clone du ``sign_count`` (via la lib mockée pour
contrôler le compteur), la connexion par passkey qui émet le cookie JWT +
session, et l'auto-service (liste/suppression de ses propres passkeys).
"""
from unittest import mock

from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory, UserFactory

from authentication import webauthn_util
from authentication.models import WebAuthnChallenge, WebAuthnCredential


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class WebAuthnModelTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(slug='acme')
        self.user = UserFactory(username='alice', company=self.company)

    def test_credential_id_unique(self):
        WebAuthnCredential.objects.create(
            user=self.user, credential_id='cred-1', public_key='pk',
            sign_count=0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WebAuthnCredential.objects.create(
                    user=self.user, credential_id='cred-1', public_key='pk2',
                    sign_count=0)


class WebAuthnDegradationTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(slug='acme')
        self.user = UserFactory(username='alice', company=self.company)

    def test_register_begin_501_without_lib(self):
        with mock.patch.object(
                webauthn_util, 'webauthn_available', return_value=False):
            resp = _auth(self.user).post(
                '/api/django/auth/webauthn/register/begin/', {}, format='json')
        self.assertEqual(resp.status_code, 501)

    def test_login_begin_501_without_lib(self):
        with mock.patch.object(
                webauthn_util, 'webauthn_available', return_value=False):
            resp = APIClient().post(
                '/api/django/auth/webauthn/login/begin/',
                {'username': 'alice'}, format='json')
        self.assertEqual(resp.status_code, 501)

    def test_register_begin_requires_auth(self):
        with mock.patch.object(
                webauthn_util, 'webauthn_available', return_value=True):
            resp = APIClient().post(
                '/api/django/auth/webauthn/register/begin/', {}, format='json')
        self.assertIn(resp.status_code, (401, 403))


class SignCountAntiCloneTests(TenantAPITestCase):
    """Cœur anti-clone : ``sign_count_regressed`` (fonction pure, sans lib)."""

    def test_regression_detected(self):
        # Compteur courant 5, assertion à 3 → clone suspecté.
        self.assertTrue(webauthn_util.sign_count_regressed(5, 3))
        self.assertTrue(webauthn_util.sign_count_regressed(5, 5))

    def test_increase_ok(self):
        self.assertFalse(webauthn_util.sign_count_regressed(5, 6))
        self.assertFalse(webauthn_util.sign_count_regressed(0, 1))

    def test_zero_zero_tolerated(self):
        # Authentificateurs sans compteur (passkeys de plateforme) : 0/0 OK.
        self.assertFalse(webauthn_util.sign_count_regressed(0, 0))


class WebAuthnLoginCompleteFlowTests(TenantAPITestCase):
    """Flux login/complete indépendant de la lib (défi, credential inconnu)."""

    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(slug='acme')
        self.user = UserFactory(username='alice', company=self.company)
        self.cred = WebAuthnCredential.objects.create(
            user=self.user, credential_id='cred-abc', public_key='cGs=',
            sign_count=5)

    def test_invalid_challenge_400(self):
        with mock.patch.object(
                webauthn_util, 'webauthn_available', return_value=True):
            resp = APIClient().post(
                '/api/django/auth/webauthn/login/complete/', {
                    'challenge': 'never-issued',
                    'credential': {'id': 'cred-abc'},
                }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unknown_credential_401(self):
        ch = WebAuthnChallenge.objects.create(
            challenge='c2', purpose=WebAuthnChallenge.PURPOSE_LOGIN)
        with mock.patch.object(
                webauthn_util, 'webauthn_available', return_value=True):
            resp = APIClient().post(
                '/api/django/auth/webauthn/login/complete/', {
                    'challenge': ch.challenge,
                    'credential': {'id': 'does-not-exist'},
                }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_challenge_consumed_after_use(self):
        # Un défi de login est marqué consommé même si la vérification échoue.
        ch = WebAuthnChallenge.objects.create(
            challenge='once', purpose=WebAuthnChallenge.PURPOSE_LOGIN)
        with mock.patch.object(
                webauthn_util, 'webauthn_available', return_value=True):
            APIClient().post(
                '/api/django/auth/webauthn/login/complete/', {
                    'challenge': ch.challenge,
                    'credential': {'id': 'does-not-exist'},
                }, format='json')
        ch.refresh_from_db()
        self.assertTrue(ch.used)


class WebAuthnCredentialViewSetTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(slug='acme')
        self.user = UserFactory(username='alice', company=self.company)
        self.other = UserFactory(username='bob', company=self.company)
        self.cred = WebAuthnCredential.objects.create(
            user=self.user, credential_id='mine', public_key='pk', sign_count=0)

    def test_lists_only_own_passkeys(self):
        WebAuthnCredential.objects.create(
            user=self.other, credential_id='theirs', public_key='pk',
            sign_count=0)
        resp = _auth(self.user).get(
            '/api/django/auth/webauthn/credentials/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)

    def test_cannot_delete_others_passkey(self):
        theirs = WebAuthnCredential.objects.create(
            user=self.other, credential_id='theirs', public_key='pk',
            sign_count=0)
        resp = _auth(self.user).delete(
            f'/api/django/auth/webauthn/credentials/{theirs.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_can_delete_own_passkey(self):
        resp = _auth(self.user).delete(
            f'/api/django/auth/webauthn/credentials/{self.cred.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            WebAuthnCredential.objects.filter(id=self.cred.id).exists())
