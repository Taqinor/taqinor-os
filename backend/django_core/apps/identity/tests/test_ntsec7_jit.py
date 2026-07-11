"""NTSEC7 — Just-in-time provisioning depuis les groupes SSO (SAML/OIDC → rôle).

Vérifie qu'un utilisateur SSO dont le claim « groupes » est mappé arrive avec le
bon rôle sans SCIM ; qu'un claim inconnu retombe sur ``default_role`` ; que le
rôle est réappliqué à CHAQUE connexion (source de vérité = l'IdP) ; et que le
JIT ne s'applique pas sans ``auto_provision``.
"""
from django.test import TestCase

from apps.identity.models import IdentityProvider, ScimGroupMapping
from apps.identity.services import (
    apply_sso_groups, resolve_or_provision_user,
)
from apps.roles.models import Role

from .helpers import make_company, make_user


def _idp(company, **kwargs):
    defaults = dict(
        protocol=IdentityProvider.PROTOCOL_SAML, nom='IdP', actif=True,
        auto_provision=True,
        attribute_map={'email': 'mail', 'groupes': 'memberOf'})
    defaults.update(kwargs)
    return IdentityProvider.objects.create(company=company, **defaults)


class JitProvisioningTests(TestCase):
    def setUp(self):
        self.company = make_company('acme', 'ACME')
        self.sales = Role.objects.create(company=self.company, nom='Commercial')
        self.default_role = Role.objects.create(
            company=self.company, nom='Viewer')

    def test_mapped_group_applies_role_on_provision(self):
        ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Sales', role=self.sales)
        idp = _idp(self.company, default_role=self.default_role)
        user, created = resolve_or_provision_user(
            idp, email='new@acme.ma', groups=['Sales'])
        self.assertTrue(created)
        self.assertEqual(user.role_id, self.sales.id)

    def test_unknown_group_falls_back_to_default_role(self):
        idp = _idp(self.company, default_role=self.default_role)
        user, _ = resolve_or_provision_user(
            idp, email='new@acme.ma', groups=['UnknownGroup'])
        self.assertEqual(user.role_id, self.default_role.id)

    def test_role_reapplied_each_login_source_of_truth_idp(self):
        ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Sales', role=self.sales)
        idp = _idp(self.company, default_role=self.default_role)
        user = make_user(self.company, 'existing@acme.ma', role='normal')
        user.email = 'existing@acme.ma'
        user.role = self.default_role
        user.save()
        # L'IdP place l'utilisateur dans « Sales » à cette connexion.
        apply_sso_groups(idp, user, ['Sales'])
        user.refresh_from_db()
        self.assertEqual(user.role_id, self.sales.id)

    def test_no_autoprovision_no_jit(self):
        ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Sales', role=self.sales)
        idp = _idp(self.company, auto_provision=False,
                   default_role=self.default_role)
        user = make_user(self.company, 'existing@acme.ma', role='normal')
        user.role = None
        user.save(update_fields=['role'])
        apply_sso_groups(idp, user, ['Sales'])
        user.refresh_from_db()
        # Sans auto_provision, le JIT ne touche pas le rôle.
        self.assertIsNone(user.role_id)

    def test_empty_groups_uses_default(self):
        idp = _idp(self.company, default_role=self.default_role)
        user, _ = resolve_or_provision_user(
            idp, email='new@acme.ma', groups=[])
        self.assertEqual(user.role_id, self.default_role.id)

    def test_first_matched_group_wins(self):
        eng = Role.objects.create(company=self.company, nom='Technicien')
        ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Sales', role=self.sales)
        ScimGroupMapping.objects.create(
            company=self.company, scim_group_name='Eng', role=eng)
        idp = _idp(self.company, default_role=self.default_role)
        user, _ = resolve_or_provision_user(
            idp, email='new@acme.ma', groups=['Sales', 'Eng'])
        self.assertEqual(user.role_id, self.sales.id)
