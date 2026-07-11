"""NTSEC1 — Modèle ``IdentityProvider`` par société (fondation SSO).

Couvre : CRUD réservé Directeur/Admin, scope société strict (A ne voit jamais
B, company forcé côté serveur), unicité d'un seul IdP actif par (company,
protocol), et — critère clé — que l'existence d'un IdP ne change RIEN au login
local (selectors inertes tant que non actif).
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.identity import selectors
from apps.identity.models import IdentityProvider

from .helpers import auth_client, make_company, make_user


class IdentityProviderModelTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')

    def test_defaults_are_inert(self):
        """Un IdP créé est OFF par défaut : actif/enforce/auto_provision False."""
        idp = IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='Test')
        self.assertFalse(idp.actif)
        self.assertFalse(idp.enforce_sso)
        self.assertFalse(idp.auto_provision)
        self.assertEqual(idp.attribute_map, {})

    def test_one_active_idp_per_company_protocol(self):
        """Deux IdP SAML ACTIFS pour une même société sont interdits."""
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='A', actif=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IdentityProvider.objects.create(
                    company=self.company,
                    protocol=IdentityProvider.PROTOCOL_SAML,
                    nom='B', actif=True)

    def test_two_inactive_idp_allowed(self):
        """Plusieurs IdP INACTIFS (brouillons) coexistent sans contrainte."""
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='A', actif=False)
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='B', actif=False)
        self.assertEqual(IdentityProvider.objects.count(), 2)

    def test_active_saml_and_oidc_coexist(self):
        """Un SAML actif et un OIDC actif coexistent (protocoles distincts)."""
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='S', actif=True)
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_OIDC,
            nom='O', actif=True)
        self.assertEqual(IdentityProvider.objects.filter(actif=True).count(), 2)


class IdentitySelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')

    def test_no_provider_is_inert(self):
        """Sans IdP, les sélecteurs sont inertes (login local inchangé)."""
        self.assertIsNone(selectors.active_provider(self.company))
        self.assertFalse(selectors.enforce_sso_active(self.company))

    def test_inactive_provider_ignored(self):
        """Un IdP inactif n'est jamais renvoyé, même avec enforce_sso."""
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='X', actif=False, enforce_sso=True)
        self.assertIsNone(selectors.active_provider(self.company))
        self.assertFalse(selectors.enforce_sso_active(self.company))

    def test_active_provider_returned(self):
        idp = IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_OIDC,
            nom='X', actif=True)
        self.assertEqual(selectors.active_provider(self.company).pk, idp.pk)
        self.assertEqual(
            selectors.active_provider(self.company, protocol='oidc').pk, idp.pk)
        self.assertIsNone(
            selectors.active_provider(self.company, protocol='saml'))

    def test_enforce_sso_active(self):
        IdentityProvider.objects.create(
            company=self.company, protocol=IdentityProvider.PROTOCOL_SAML,
            nom='X', actif=True, enforce_sso=True)
        self.assertTrue(selectors.enforce_sso_active(self.company))

    def test_selectors_none_company_safe(self):
        self.assertIsNone(selectors.active_provider(None))
        self.assertFalse(selectors.enforce_sso_active(None))


class IdentityProviderApiTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.other = make_company('other', 'Other')
        self.admin = make_user(self.company, 'admin', role='admin')
        self.normal = make_user(self.company, 'bob', role='normal')

    def test_admin_can_create_provider(self):
        api = auth_client(self.admin)
        resp = api.post('/api/django/identity/providers/', {
            'protocol': 'saml', 'nom': 'Azure',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        idp = IdentityProvider.objects.get(pk=resp.data['id'])
        # Company FORCÉE côté serveur.
        self.assertEqual(idp.company_id, self.company.id)
        self.assertFalse(idp.actif)

    def test_company_never_taken_from_body(self):
        api = auth_client(self.admin)
        resp = api.post('/api/django/identity/providers/', {
            'protocol': 'oidc', 'nom': 'Evil', 'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        idp = IdentityProvider.objects.get(pk=resp.data['id'])
        self.assertEqual(idp.company_id, self.company.id)

    def test_can_activate_provider(self):
        api = auth_client(self.admin)
        idp = IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='A')
        resp = api.patch(
            f'/api/django/identity/providers/{idp.id}/',
            {'actif': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        idp.refresh_from_db()
        self.assertTrue(idp.actif)

    def test_queryset_scoped_to_company(self):
        IdentityProvider.objects.create(
            company=self.other, protocol='saml', nom='Foreign')
        api = auth_client(self.admin)
        resp = api.get('/api/django/identity/providers/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        self.assertEqual(len(results), 0)

    def test_cannot_access_foreign_provider(self):
        foreign = IdentityProvider.objects.create(
            company=self.other, protocol='saml', nom='Foreign')
        api = auth_client(self.admin)
        resp = api.get(f'/api/django/identity/providers/{foreign.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_non_admin_forbidden(self):
        api = auth_client(self.normal)
        resp = api.get('/api/django/identity/providers/')
        self.assertEqual(resp.status_code, 403)
        resp = api.post('/api/django/identity/providers/', {
            'protocol': 'saml', 'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_forbidden(self):
        from rest_framework.test import APIClient
        resp = APIClient().get('/api/django/identity/providers/')
        self.assertIn(resp.status_code, (401, 403))

    def test_client_secret_write_only(self):
        api = auth_client(self.admin)
        resp = api.post('/api/django/identity/providers/', {
            'protocol': 'oidc', 'nom': 'O', 'client_secret': 'topsecret',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertNotIn('client_secret', resp.data)
        idp = IdentityProvider.objects.get(pk=resp.data['id'])
        self.assertEqual(idp.client_secret, 'topsecret')
