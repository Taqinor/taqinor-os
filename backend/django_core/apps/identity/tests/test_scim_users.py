"""NTSEC5 — Tests du provisioning SCIM 2.0 Users.

Garanties : jeton requis (401), scope société strict (slug≠société → 404),
création scopée société, désactivation (DELETE/active=false) qui révoque les
sessions, jamais d'accès cross-tenant.
"""
from django.test import TestCase

from rest_framework.test import APIClient

from authentication.models import CustomUser, UserSession
from testkit.factories import CompanyFactory, UserFactory

from apps.identity.models import ScimToken


class ScimUsersTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other = CompanyFactory()
        self.token_obj, self.raw = ScimToken.issue(
            company=self.company, label='okta')
        self.slug = self.company.slug
        self.base = f'/api/django/identity/scim/v2/{self.slug}/Users'

    def _client(self, raw=None):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {raw or self.raw}')
        return c

    def test_no_token_rejected(self):
        r = APIClient().get(self.base)
        self.assertEqual(r.status_code, 401)

    def test_invalid_token_rejected(self):
        r = self._client(raw='wrong').get(self.base)
        self.assertEqual(r.status_code, 401)

    def test_inactive_token_rejected(self):
        self.token_obj.actif = False
        self.token_obj.save()
        r = self._client().get(self.base)
        self.assertEqual(r.status_code, 401)

    def test_slug_mismatch_is_404(self):
        base = f'/api/django/identity/scim/v2/{self.other.slug}/Users'
        r = self._client().get(base)
        self.assertEqual(r.status_code, 404)

    def test_create_user_scoped_to_token_company(self):
        r = self._client().post(self.base, {
            'userName': 'jdoe',
            'emails': [{'value': 'jdoe@corp.com', 'primary': True}],
            'name': {'givenName': 'John', 'familyName': 'Doe'},
            'active': True,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        u = CustomUser.objects.get(username='jdoe')
        self.assertEqual(u.company_id, self.company.id)
        self.assertTrue(u.is_active)
        self.assertFalse(u.has_usable_password())
        self.assertEqual(r.json()['userName'], 'jdoe')

    def test_list_only_shows_own_company(self):
        UserFactory(company=self.company, username='mine')
        UserFactory(company=self.other, username='theirs')
        r = self._client().get(self.base)
        self.assertEqual(r.status_code, 200)
        names = {res['userName'] for res in r.json()['Resources']}
        self.assertIn('mine', names)
        self.assertNotIn('theirs', names)

    def test_filter_by_username(self):
        UserFactory(company=self.company, username='alpha')
        UserFactory(company=self.company, username='beta')
        r = self._client().get(self.base + '?filter=userName eq "alpha"')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['totalResults'], 1)

    def test_delete_deactivates_and_revokes_sessions(self):
        u = UserFactory(company=self.company, username='togo')
        UserSession.objects.create(
            company=self.company, user=u, jti='abc', revoked=False)
        r = self._client().delete(f'{self.base}/{u.pk}')
        self.assertEqual(r.status_code, 204)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertFalse(
            UserSession.objects.filter(user=u, revoked=False).exists())

    def test_cannot_touch_other_company_user(self):
        theirs = UserFactory(company=self.other, username='theirs2')
        r = self._client().get(f'{self.base}/{theirs.pk}')
        self.assertEqual(r.status_code, 404)

    def test_patch_active_false_revokes(self):
        u = UserFactory(company=self.company, username='patchme')
        UserSession.objects.create(
            company=self.company, user=u, jti='xyz', revoked=False)
        r = self._client().patch(
            f'{self.base}/{u.pk}', {'active': False}, format='json')
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertFalse(
            UserSession.objects.filter(user=u, revoked=False).exists())
