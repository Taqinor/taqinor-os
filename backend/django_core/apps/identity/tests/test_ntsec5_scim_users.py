"""NTSEC5 — Provisioning SCIM 2.0 — Users.

Couvre : auth par jeton SCIM (valide/invalide/inactif → 401), création scopée
société, list+filter userName, désactivation (DELETE et active=false) +
révocation des sessions, isolation multi-tenant, gestion des jetons réservée
Directeur.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.identity.models import ScimToken
from authentication.models import UserSession

from .helpers import auth_client, make_company, make_user

User = get_user_model()


class ScimTokenIssueTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.admin = make_user(self.company, 'admin', role='admin')

    def test_issue_returns_secret_once(self):
        token, raw = ScimToken.issue(company=self.company, label='idp')
        self.assertTrue(raw.startswith('scim_'))
        self.assertNotEqual(token.token_hash, raw)
        from apps.identity.models import hash_scim_token
        self.assertEqual(token.token_hash, hash_scim_token(raw))

    def test_token_endpoint_admin_only(self):
        normal = make_user(self.company, 'bob', role='normal')
        resp = auth_client(normal).get('/api/django/identity/scim-tokens/')
        self.assertEqual(resp.status_code, 403)

    def test_token_creation_returns_raw(self):
        resp = auth_client(self.admin).post(
            '/api/django/identity/scim-tokens/', {'label': 'idp'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn('token', resp.data)
        self.assertTrue(resp.data['token'].startswith('scim_'))

    def test_token_list_never_exposes_secret(self):
        ScimToken.issue(company=self.company, label='x')
        resp = auth_client(self.admin).get('/api/django/identity/scim-tokens/')
        self.assertEqual(resp.status_code, 200)
        body = json.dumps(resp.data)
        self.assertNotIn('token_hash', body)


class ScimUsersApiTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.other = make_company('other', 'Other')
        self.token_obj, self.raw = ScimToken.issue(company=self.company)
        self.base = '/api/django/identity/scim/v2/acme/Users'

    def _hdr(self, raw=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {raw or self.raw}'}

    def test_invalid_token_401(self):
        resp = self.client.get(self.base, **self._hdr('scim_wrong'))
        self.assertEqual(resp.status_code, 401)

    def test_missing_token_401(self):
        resp = self.client.get(self.base)
        self.assertEqual(resp.status_code, 401)

    def test_inactive_token_401(self):
        self.token_obj.actif = False
        self.token_obj.save(update_fields=['actif'])
        resp = self.client.get(self.base, **self._hdr())
        self.assertEqual(resp.status_code, 401)

    def test_unknown_company_404(self):
        resp = self.client.get(
            '/api/django/identity/scim/v2/nope/Users', **self._hdr())
        self.assertEqual(resp.status_code, 404)

    def test_create_user_scoped(self):
        payload = {
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
            'userName': 'newbie@acme.ma',
            'name': {'givenName': 'New', 'familyName': 'Bie'},
            'emails': [{'value': 'newbie@acme.ma', 'primary': True}],
            'active': True,
        }
        resp = self.client.post(
            self.base, data=json.dumps(payload),
            content_type='application/scim+json', **self._hdr())
        self.assertEqual(resp.status_code, 201, resp.content)
        u = User.objects.get(username='newbie@acme.ma')
        self.assertEqual(u.company_id, self.company.id)
        self.assertEqual(u.first_name, 'New')
        self.assertFalse(u.has_usable_password())
        self.assertEqual(resp.data['userName'], 'newbie@acme.ma')

    def test_list_and_filter(self):
        make_user(self.company, 'alice@acme.ma')
        make_user(self.company, 'bob@acme.ma')
        make_user(self.other, 'foreign@other.ma')
        resp = self.client.get(self.base, **self._hdr())
        self.assertEqual(resp.status_code, 200)
        usernames = {r['userName'] for r in resp.data['Resources']}
        self.assertIn('alice@acme.ma', usernames)
        self.assertNotIn('foreign@other.ma', usernames)  # jamais cross-tenant
        # Filtre userName eq
        resp2 = self.client.get(
            self.base + '?filter=userName eq "alice@acme.ma"', **self._hdr())
        self.assertEqual(len(resp2.data['Resources']), 1)

    def test_delete_deactivates_and_revokes_sessions(self):
        u = make_user(self.company, 'todel@acme.ma')
        UserSession.objects.create(
            user=u, company=self.company, jti='j1', revoked=False)
        resp = self.client.delete(
            f'{self.base}/{u.id}', **self._hdr())
        self.assertEqual(resp.status_code, 204)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertFalse(
            UserSession.objects.filter(user=u, revoked=False).exists())

    def test_patch_active_false_deactivates(self):
        u = make_user(self.company, 'p@acme.ma')
        UserSession.objects.create(
            user=u, company=self.company, jti='j2', revoked=False)
        payload = {
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [{'op': 'replace', 'path': 'active', 'value': False}],
        }
        resp = self.client.patch(
            f'{self.base}/{u.id}', data=json.dumps(payload),
            content_type='application/scim+json', **self._hdr())
        self.assertEqual(resp.status_code, 200, resp.content)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertFalse(
            UserSession.objects.filter(user=u, revoked=False).exists())

    def test_cannot_touch_foreign_user(self):
        foreign = make_user(self.other, 'x@other.ma')
        resp = self.client.get(f'{self.base}/{foreign.id}', **self._hdr())
        self.assertEqual(resp.status_code, 404)

    def test_token_of_other_company_rejected(self):
        _, other_raw = ScimToken.issue(company=self.other)
        # Le jeton de « other » ne peut pas piloter les Users de « acme ».
        resp = self.client.get(self.base, **self._hdr(other_raw))
        self.assertEqual(resp.status_code, 401)
