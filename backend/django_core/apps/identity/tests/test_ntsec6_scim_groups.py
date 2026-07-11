"""NTSEC6 — Provisioning SCIM 2.0 — Groups → rôles.

Couvre : le service ``roles.services`` (assign/revoke + garde multi-tenant),
l'application/retrait automatique du rôle quand un membre est ajouté/retiré d'un
groupe SCIM mappé, la gestion des mappings réservée Directeur, et le scope
société.
"""
import json

from django.test import TestCase

from apps.identity.models import ScimGroupMapping, ScimToken
from apps.roles import services as role_services
from apps.roles.models import Role

from .helpers import auth_client, make_company, make_user


class RoleServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.other = make_company('other', 'Other')
        self.role = Role.objects.create(company=self.company, nom='Commercial')
        self.user = make_user(self.company, 'alice', role='normal')

    def test_assign_role_sets_fk(self):
        changed = role_services.assign_role(self.user, self.role)
        self.assertTrue(changed)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role_id, self.role.id)

    def test_assign_role_cross_tenant_refused(self):
        foreign_role = Role.objects.create(company=self.other, nom='X')
        changed = role_services.assign_role(self.user, foreign_role)
        self.assertFalse(changed)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.role_id)

    def test_revoke_only_if_currently_held(self):
        role_services.assign_role(self.user, self.role)
        other_role = Role.objects.create(company=self.company, nom='Autre')
        # Retirer un rôle non porté = no-op (jamais toucher un rôle posé
        # ailleurs).
        self.assertFalse(role_services.revoke_role(self.user, other_role))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role_id, self.role.id)
        # Retirer le rôle porté le remet à None.
        self.assertTrue(role_services.revoke_role(self.user, self.role))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.role_id)

    def test_role_for_scim_group(self):
        ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Sales', role=self.role)
        found = role_services.role_for_scim_group(self.company, 'Sales')
        self.assertEqual(found.id, self.role.id)
        self.assertIsNone(
            role_services.role_for_scim_group(self.company, 'Unknown'))


class ScimGroupsApiTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.role = Role.objects.create(company=self.company, nom='Commercial')
        self.mapping = ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Sales', role=self.role)
        self.user = make_user(self.company, 'alice', role='normal')
        _, self.raw = ScimToken.issue(company=self.company)
        self.base = '/api/django/identity/scim/v2/acme/Groups'

    def _hdr(self):
        return {'HTTP_AUTHORIZATION': f'Bearer {self.raw}'}

    def test_list_groups(self):
        resp = self.client.get(self.base, **self._hdr())
        self.assertEqual(resp.status_code, 200)
        names = {g['displayName'] for g in resp.data['Resources']}
        self.assertIn('Sales', names)

    def test_add_member_applies_role(self):
        payload = {
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
            'displayName': 'Sales',
            'members': [{'value': str(self.user.id)}],
        }
        resp = self.client.post(
            self.base, data=json.dumps(payload),
            content_type='application/scim+json', **self._hdr())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role_id, self.role.id)

    def test_patch_remove_member_revokes_role(self):
        role_services.assign_role(self.user, self.role)
        payload = {
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [{
                'op': 'remove', 'path': 'members',
                'value': [{'value': str(self.user.id)}]}],
        }
        resp = self.client.patch(
            f'{self.base}/{self.mapping.id}', data=json.dumps(payload),
            content_type='application/scim+json', **self._hdr())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.role_id)

    def test_unmapped_group_404(self):
        payload = {'displayName': 'Nope', 'members': []}
        resp = self.client.post(
            self.base, data=json.dumps(payload),
            content_type='application/scim+json', **self._hdr())
        self.assertEqual(resp.status_code, 404)

    def test_group_scoped_by_token_company(self):
        other = make_company('other', 'Other')
        _, other_raw = ScimToken.issue(company=other)
        resp = self.client.get(
            self.base, HTTP_AUTHORIZATION=f'Bearer {other_raw}')
        # Le jeton d'une autre société ne peut pas lister les groupes d'acme.
        self.assertEqual(resp.status_code, 401)


class ScimGroupMappingAdminTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.admin = make_user(self.company, 'admin', role='admin')
        self.role = Role.objects.create(company=self.company, nom='Commercial')

    def test_admin_creates_mapping(self):
        resp = auth_client(self.admin).post(
            '/api/django/identity/scim-group-mappings/',
            {'scim_group_name': 'Sales', 'role': self.role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        m = ScimGroupMapping.objects.get(pk=resp.data['id'])
        self.assertEqual(m.company_id, self.company.id)

    def test_non_admin_forbidden(self):
        normal = make_user(self.company, 'bob', role='normal')
        resp = auth_client(normal).get(
            '/api/django/identity/scim-group-mappings/')
        self.assertEqual(resp.status_code, 403)

    def test_foreign_role_rejected(self):
        other = make_company('other', 'Other')
        foreign_role = Role.objects.create(company=other, nom='X')
        resp = auth_client(self.admin).post(
            '/api/django/identity/scim-group-mappings/',
            {'scim_group_name': 'Sales', 'role': foreign_role.id},
            format='json')
        self.assertEqual(resp.status_code, 400)
