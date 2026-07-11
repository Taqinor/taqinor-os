"""NTSEC2 — Connexion SSO SAML 2.0 par tenant.

Le wheel ``python3-saml`` (onelogin) exige xmlsec/libxml2 natifs et n'est pas
présent dans l'environnement de test ; on couvre donc :
* la DÉGRADATION propre (501 sans lib, 404 sans IdP actif) — comportement réel
  actuel, login local intact ;
* le service de finalisation (résolution/provisioning, cookies JWT, UserSession,
  audit) indépendant de la lib ;
* l'anti-rejeu (ConsumedAssertion unique par société) ;
* le mapping d'attributs ;
* le flux ACS complet quand la lib est disponible, via un ``OneLogin`` mocké
  (signature validée = is_authenticated True), pour couvrir la résolution
  utilisateur + l'émission de session sans dépendre du wheel natif.
"""
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.identity import saml as saml_mod
from apps.identity import views_saml
from apps.identity.models import ConsumedAssertion, IdentityProvider
from apps.identity.services import (
    finalize_sso_login, resolve_or_provision_user,
)

from .helpers import make_company, make_user


def _make_idp(company, **kwargs):
    defaults = dict(
        protocol=IdentityProvider.PROTOCOL_SAML, nom='IdP', actif=True,
        entity_id='https://idp.example/meta', sso_url='https://idp.example/sso',
        x509_cert='CERT',
        attribute_map={'email': 'mail', 'prenom': 'givenName',
                       'nom': 'sn', 'groupes': 'memberOf'},
    )
    defaults.update(kwargs)
    return IdentityProvider.objects.create(company=company, **defaults)


class SamlEndpointDegradationTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')

    def test_no_idp_returns_404(self):
        resp = self.client.get('/api/django/identity/saml/acme/login/')
        self.assertEqual(resp.status_code, 404)

    def test_unknown_company_404(self):
        resp = self.client.get('/api/django/identity/saml/nope/login/')
        self.assertEqual(resp.status_code, 404)

    def test_login_without_lib_returns_501(self):
        _make_idp(self.company)
        with mock.patch.object(saml_mod, 'saml_available', return_value=False):
            resp = self.client.get('/api/django/identity/saml/acme/login/')
        self.assertEqual(resp.status_code, 501)

    def test_acs_without_lib_returns_501(self):
        _make_idp(self.company)
        with mock.patch.object(saml_mod, 'saml_available', return_value=False):
            resp = self.client.post('/api/django/identity/saml/acme/acs/', {})
        self.assertEqual(resp.status_code, 501)

    def test_metadata_without_lib_returns_501(self):
        _make_idp(self.company)
        with mock.patch.object(saml_mod, 'saml_available', return_value=False):
            resp = self.client.get('/api/django/identity/saml/acme/metadata/')
        self.assertEqual(resp.status_code, 501)

    def test_inactive_idp_treated_as_no_idp(self):
        _make_idp(self.company, actif=False)
        resp = self.client.get('/api/django/identity/saml/acme/login/')
        self.assertEqual(resp.status_code, 404)


class ResolveProvisionTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')

    def test_existing_user_matched_by_email(self):
        u = make_user(self.company, 'alice', role='normal')
        u.email = 'alice@acme.ma'
        u.save()
        idp = _make_idp(self.company, auto_provision=False)
        user, created = resolve_or_provision_user(idp, email='ALICE@acme.ma')
        self.assertEqual(user.pk, u.pk)
        self.assertFalse(created)

    def test_absent_user_without_autoprovision_is_none(self):
        idp = _make_idp(self.company, auto_provision=False)
        user, created = resolve_or_provision_user(idp, email='new@acme.ma')
        self.assertIsNone(user)
        self.assertFalse(created)

    def test_autoprovision_creates_scoped_user(self):
        from apps.roles.models import Role
        role = Role.objects.create(company=self.company, nom='SSO Base')
        idp = _make_idp(self.company, auto_provision=True, default_role=role)
        user, created = resolve_or_provision_user(
            idp, email='new@acme.ma', first_name='New', last_name='User')
        self.assertTrue(created)
        self.assertEqual(user.company_id, self.company.id)
        self.assertEqual(user.email, 'new@acme.ma')
        self.assertEqual(user.role_id, role.id)
        # Mot de passe inutilisable : l'accès passe strictement par le SSO.
        self.assertFalse(user.has_usable_password())

    def test_empty_email_rejected(self):
        idp = _make_idp(self.company, auto_provision=True)
        user, created = resolve_or_provision_user(idp, email='')
        self.assertIsNone(user)


class FinalizeSsoLoginTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.idp = _make_idp(self.company)
        self.user = make_user(self.company, 'alice', role='normal')

    def test_finalize_sets_cookies_and_session(self):
        from django.test import RequestFactory

        from authentication.models import UserSession
        req = RequestFactory().post('/api/django/identity/saml/acme/acs/')
        resp = finalize_sso_login(req, self.idp, self.user)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access_token', resp.cookies)
        self.assertIn('refresh_token', resp.cookies)
        self.assertTrue(
            UserSession.objects.filter(user=self.user).exists())

    def test_finalize_records_sso_audit(self):
        from django.test import RequestFactory

        from apps.audit.models import AuditLog
        req = RequestFactory().post('/api/django/identity/saml/acme/acs/')
        finalize_sso_login(req, self.idp, self.user)
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action__in=[getattr(AuditLog.Action, 'SSO_LOGIN', 'login'),
                            'login']).exists())


class AntiReplayTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')

    def test_assertion_unique_per_company(self):
        ConsumedAssertion.objects.create(
            company=self.company, assertion_id='aid-1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConsumedAssertion.objects.create(
                    company=self.company, assertion_id='aid-1')

    def test_same_assertion_id_across_companies_allowed(self):
        other = make_company('other', 'Other')
        ConsumedAssertion.objects.create(
            company=self.company, assertion_id='aid-1')
        ConsumedAssertion.objects.create(company=other, assertion_id='aid-1')
        self.assertEqual(ConsumedAssertion.objects.count(), 2)


class AttributeMappingTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.idp = _make_idp(self.company)

    def test_first_attr_maps_and_takes_first(self):
        attrs = {'mail': ['a@acme.ma', 'b@acme.ma'], 'givenName': ['Al']}
        self.assertEqual(
            views_saml._first_attr(attrs, self.idp, 'email'), 'a@acme.ma')
        self.assertEqual(
            views_saml._first_attr(attrs, self.idp, 'prenom'), 'Al')

    def test_first_attr_missing_key_empty(self):
        self.assertEqual(views_saml._first_attr({}, self.idp, 'email'), '')

    def test_list_attr_returns_all(self):
        attrs = {'memberOf': ['g1', 'g2']}
        self.assertEqual(
            views_saml._list_attr(attrs, self.idp, 'groupes'), ['g1', 'g2'])


class SamlAcsMockedLibTests(TestCase):
    """Flux ACS complet avec ``OneLogin`` mocké (couvre la branche lib-présente
    sans dépendre du wheel natif)."""

    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.idp = _make_idp(self.company, auto_provision=True)

    def _fake_auth(self, authenticated=True, assertion_id='aid-xyz',
                   attrs=None):
        fake = mock.Mock()
        fake.process_response.return_value = None
        fake.get_errors.return_value = []
        fake.is_authenticated.return_value = authenticated
        fake.get_last_assertion_id.return_value = assertion_id
        fake.get_session_expiration.return_value = None
        fake.get_attributes.return_value = attrs or {
            'mail': ['sso@acme.ma'], 'givenName': ['SSO'], 'sn': ['User']}
        fake.get_nameid.return_value = 'sso@acme.ma'
        return fake

    def test_valid_assertion_logs_in_and_provisions(self):
        with mock.patch.object(saml_mod, 'saml_available', return_value=True), \
             mock.patch.object(saml_mod, 'build_auth',
                               return_value=self._fake_auth()):
            resp = self.client.post('/api/django/identity/saml/acme/acs/', {})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('access_token', resp.cookies)
        from authentication.models import CustomUser
        self.assertTrue(
            CustomUser.objects.filter(
                company=self.company, email='sso@acme.ma').exists())

    def test_replayed_assertion_refused(self):
        ConsumedAssertion.objects.create(
            company=self.company, assertion_id='aid-xyz')
        with mock.patch.object(saml_mod, 'saml_available', return_value=True), \
             mock.patch.object(saml_mod, 'build_auth',
                               return_value=self._fake_auth()):
            resp = self.client.post('/api/django/identity/saml/acme/acs/', {})
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_assertion_refused(self):
        with mock.patch.object(saml_mod, 'saml_available', return_value=True), \
             mock.patch.object(
                 saml_mod, 'build_auth',
                 return_value=self._fake_auth(authenticated=False)):
            resp = self.client.post('/api/django/identity/saml/acme/acs/', {})
        self.assertEqual(resp.status_code, 401)

    def test_unknown_user_without_autoprovision_forbidden(self):
        self.idp.auto_provision = False
        self.idp.save()
        with mock.patch.object(saml_mod, 'saml_available', return_value=True), \
             mock.patch.object(saml_mod, 'build_auth',
                               return_value=self._fake_auth()):
            resp = self.client.post('/api/django/identity/saml/acme/acs/', {})
        self.assertEqual(resp.status_code, 403)
