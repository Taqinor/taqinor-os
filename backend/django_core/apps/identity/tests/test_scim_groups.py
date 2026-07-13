"""NTSEC6 — Tests SCIM Groups → rôles (attribution/révocation auto).

Garanties : ajouter un membre à un groupe SCIM mappé lui attribue le rôle, le
retrait le révoque, un rôle d'une autre société n'est jamais appliqué, et
l'écriture du rôle passe par ``apps.roles.services``.
"""
from django.test import TestCase

from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.roles.services import apply_role_to_user, remove_role_from_user
from testkit.factories import CompanyFactory, UserFactory

from apps.identity.models import ScimGroupMapping, ScimToken


class RolesServiceTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other = CompanyFactory()
        self.role = Role.objects.create(company=self.company, nom='Compta')
        self.foreign = Role.objects.create(company=self.other, nom='X')
        self.user = UserFactory(company=self.company, username='u1')

    def test_apply_and_remove(self):
        self.assertTrue(apply_role_to_user(self.user, self.role.id))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role_id, self.role.id)
        self.assertTrue(remove_role_from_user(self.user, self.role.id))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.role_id)

    def test_foreign_company_role_never_applied(self):
        self.assertFalse(apply_role_to_user(self.user, self.foreign.id))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.role_id)

    def test_remove_only_if_current(self):
        other_role = Role.objects.create(company=self.company, nom='Autre')
        apply_role_to_user(self.user, other_role.id)
        # Retirer un rôle qu'il ne porte pas : no-op.
        self.assertFalse(remove_role_from_user(self.user, self.role.id))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role_id, other_role.id)


class ScimGroupsTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.role = Role.objects.create(company=self.company, nom='Compta')
        self.user = UserFactory(company=self.company, username='member1')
        _, self.raw = ScimToken.issue(company=self.company)
        self.slug = self.company.slug
        self.base = f'/api/django/identity/scim/v2/{self.slug}/Groups'

    def _client(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {self.raw}')
        return c

    def test_no_token_rejected(self):
        r = APIClient().get(self.base)
        self.assertEqual(r.status_code, 401)

    def test_create_group_mapping(self):
        r = self._client().post(self.base, {
            'displayName': 'Comptables', 'roleId': str(self.role.id)},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(ScimGroupMapping.objects.filter(
            company=self.company, scim_group_name='Comptables').exists())

    def test_patch_add_member_applies_role(self):
        mapping = ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='G',
            role_id=str(self.role.id))
        r = self._client().patch(f'{self.base}/{mapping.pk}', {
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'add', 'path': 'members',
                 'value': [{'value': str(self.user.pk)}]},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role_id, self.role.id)

    def test_patch_remove_member_revokes_role(self):
        self.user.role = self.role
        self.user.save()
        mapping = ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='G',
            role_id=str(self.role.id))
        r = self._client().patch(f'{self.base}/{mapping.pk}', {
            'Operations': [
                {'op': 'remove', 'path': 'members',
                 'value': [{'value': str(self.user.pk)}]},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.role_id)

    def test_membership_scoped_to_company(self):
        # Un compte d'une autre société n'est jamais affecté par le mapping.
        other = CompanyFactory()
        stranger = UserFactory(company=other, username='stranger')
        mapping = ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='G',
            role_id=str(self.role.id))
        self._client().patch(f'{self.base}/{mapping.pk}', {
            'Operations': [
                {'op': 'add', 'path': 'members',
                 'value': [{'value': str(stranger.pk)}]},
            ],
        }, format='json')
        stranger.refresh_from_db()
        self.assertIsNone(stranger.role_id)
