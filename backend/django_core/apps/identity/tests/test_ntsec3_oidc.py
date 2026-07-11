"""NTSEC3 — Connexion SSO OIDC (Authorization Code + PKCE) par tenant.

``requests`` et ``PyJWT`` sont présents, on couvre donc le flow COMPLET :
login (état PKCE créé), puis callback avec un ``id_token`` RS256 réellement
signé (via ``cryptography``) — validation de signature, nonce, aud, exp — et
émission de la session. On couvre aussi les refus (id_token invalide, nonce
faux, état rejoué) et la dégradation (501 sans socle, 404 sans IdP).
"""
import time
from unittest import mock

from django.test import TestCase

from apps.identity import oidc as oidc_mod
from apps.identity.models import IdentityProvider, OidcAuthState

from .helpers import make_company


def _self_signed_cert(key):
    """Certificat PEM auto-signé portant la clé publique (validation locale)."""
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, 'idp')])
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow()
                             + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _sign_id_token(priv_pem, *, aud, iss, nonce, email='u@acme.ma',
                   given='G', family='F', exp_delta=300):
    import jwt
    now = int(time.time())
    payload = {
        'iss': iss, 'aud': aud, 'sub': 'subject-1', 'nonce': nonce,
        'email': email, 'given_name': given, 'family_name': family,
        'iat': now, 'exp': now + exp_delta,
    }
    return jwt.encode(payload, priv_pem, algorithm='RS256')


def _make_oidc_idp(company, pubkey_cert_pem='', **kwargs):
    defaults = dict(
        protocol=IdentityProvider.PROTOCOL_OIDC, nom='OIDC', actif=True,
        entity_id='https://idp.example', sso_url='https://idp.example/auth',
        client_id='client-123', client_secret='shh',
        auto_provision=True,
        attribute_map={'email': 'email', 'prenom': 'given_name',
                       'nom': 'family_name', 'groupes': 'groups'},
        x509_cert=pubkey_cert_pem,
    )
    defaults.update(kwargs)
    return IdentityProvider.objects.create(company=company, **defaults)


class OidcHelperTests(TestCase):
    def test_pkce_pair_is_s256(self):
        import base64
        import hashlib
        verifier, challenge = oidc_mod.gen_pkce_pair()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(challenge, expected)

    def test_authorization_url_carries_pkce_and_state(self):
        company = make_company('acme', 'ACME')
        idp = _make_oidc_idp(company)
        conf = {'authorization_endpoint': 'https://idp.example/auth'}
        url = oidc_mod.build_authorization_url(
            idp, conf, redirect_uri='https://erp/cb', state='ST',
            nonce='NO', code_challenge='CH')
        self.assertIn('code_challenge=CH', url)
        self.assertIn('code_challenge_method=S256', url)
        self.assertIn('state=ST', url)
        self.assertIn('response_type=code', url)


class OidcDegradationTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')

    def test_login_no_idp_404(self):
        resp = self.client.get('/api/django/identity/oidc/acme/login/')
        self.assertEqual(resp.status_code, 404)

    def test_login_unavailable_501(self):
        _make_oidc_idp(self.company)
        with mock.patch.object(oidc_mod, 'oidc_available', return_value=False):
            resp = self.client.get('/api/django/identity/oidc/acme/login/')
        self.assertEqual(resp.status_code, 501)

    def test_callback_missing_params_400(self):
        _make_oidc_idp(self.company)
        resp = self.client.get('/api/django/identity/oidc/acme/callback/')
        self.assertEqual(resp.status_code, 400)


class OidcLoginTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.idp = _make_oidc_idp(self.company)

    def test_login_creates_state_and_returns_redirect(self):
        with mock.patch.object(oidc_mod, 'discover', return_value={
                'authorization_endpoint': 'https://idp.example/auth',
                'token_endpoint': 'https://idp.example/token',
                'jwks_uri': '', 'issuer': 'https://idp.example'}):
            resp = self.client.get('/api/django/identity/oidc/acme/login/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('redirect', resp.data)
        self.assertEqual(OidcAuthState.objects.filter(used=False).count(), 1)


class OidcCallbackTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        # Certificat PEM auto-signé pour la vérification de signature (pas de
        # JWKS réseau) — la clé privée signe l'id_token de test.
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.priv_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        cert_pem = _self_signed_cert(key)
        self.idp = _make_oidc_idp(self.company, pubkey_cert_pem=cert_pem)

    def _start_login(self):
        with mock.patch.object(oidc_mod, 'discover', return_value={
                'authorization_endpoint': 'https://idp.example/auth',
                'token_endpoint': 'https://idp.example/token',
                'jwks_uri': '', 'issuer': 'https://idp.example'}):
            self.client.get('/api/django/identity/oidc/acme/login/')
        return OidcAuthState.objects.get(used=False)

    def _conf(self):
        return {
            'authorization_endpoint': 'https://idp.example/auth',
            'token_endpoint': 'https://idp.example/token',
            'jwks_uri': '', 'issuer': 'https://idp.example'}

    def test_full_callback_logs_in_and_provisions(self):
        state = self._start_login()
        id_token = _sign_id_token(
            self.priv_pem, aud='client-123', iss='https://idp.example',
            nonce=state.nonce, email='sso@acme.ma')
        with mock.patch.object(oidc_mod, 'discover', return_value=self._conf()), \
             mock.patch.object(oidc_mod, 'exchange_code',
                               return_value={'id_token': id_token}):
            resp = self.client.get(
                f'/api/django/identity/oidc/acme/callback/'
                f'?code=abc&state={state.state}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('access_token', resp.cookies)
        from authentication.models import CustomUser
        self.assertTrue(CustomUser.objects.filter(
            company=self.company, email='sso@acme.ma').exists())

    def test_wrong_nonce_rejected(self):
        state = self._start_login()
        id_token = _sign_id_token(
            self.priv_pem, aud='client-123', iss='https://idp.example',
            nonce='WRONG')
        with mock.patch.object(oidc_mod, 'discover', return_value=self._conf()), \
             mock.patch.object(oidc_mod, 'exchange_code',
                               return_value={'id_token': id_token}):
            resp = self.client.get(
                f'/api/django/identity/oidc/acme/callback/'
                f'?code=abc&state={state.state}')
        self.assertEqual(resp.status_code, 401)

    def test_wrong_audience_rejected(self):
        state = self._start_login()
        id_token = _sign_id_token(
            self.priv_pem, aud='someone-else', iss='https://idp.example',
            nonce=state.nonce)
        with mock.patch.object(oidc_mod, 'discover', return_value=self._conf()), \
             mock.patch.object(oidc_mod, 'exchange_code',
                               return_value={'id_token': id_token}):
            resp = self.client.get(
                f'/api/django/identity/oidc/acme/callback/'
                f'?code=abc&state={state.state}')
        self.assertEqual(resp.status_code, 401)

    def test_expired_id_token_rejected(self):
        state = self._start_login()
        id_token = _sign_id_token(
            self.priv_pem, aud='client-123', iss='https://idp.example',
            nonce=state.nonce, exp_delta=-10)
        with mock.patch.object(oidc_mod, 'discover', return_value=self._conf()), \
             mock.patch.object(oidc_mod, 'exchange_code',
                               return_value={'id_token': id_token}):
            resp = self.client.get(
                f'/api/django/identity/oidc/acme/callback/'
                f'?code=abc&state={state.state}')
        self.assertEqual(resp.status_code, 401)

    def test_replayed_state_rejected(self):
        state = self._start_login()
        state.used = True
        state.save(update_fields=['used'])
        resp = self.client.get(
            f'/api/django/identity/oidc/acme/callback/'
            f'?code=abc&state={state.state}')
        self.assertEqual(resp.status_code, 401)
