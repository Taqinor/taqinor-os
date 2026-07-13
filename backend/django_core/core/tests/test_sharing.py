"""NTSEC21 — Tests du partage niveau enregistrement (record-level sharing).

Garanties : sans règle la visibilité est vide (historique intact) ; un objet
partagé devient visible/éditable pour le bénéficiaire selon le niveau ;
l'expiration retire l'accès ; jamais cross-tenant.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.roles.models import Role
from core.sharing import (
    SharingRule, can_write, share_object, visible_ids,
)
from testkit.factories import ClientFactory, CompanyFactory, UserFactory


class SharingTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.owner = UserFactory(company=self.company, username='owner')
        self.colleague = UserFactory(company=self.company, username='colleague')
        self.obj = ClientFactory(company=self.company)

    def test_no_rule_empty_visibility(self):
        self.assertEqual(visible_ids(self.colleague, type(self.obj)), set())
        self.assertFalse(can_write(self.colleague, self.obj))

    def test_share_to_user_grants_read(self):
        share_object(self.obj, principal_type='user',
                     principal_id=self.colleague.pk, niveau='lecture')
        ids = visible_ids(self.colleague, type(self.obj))
        self.assertIn(str(self.obj.pk), ids)
        # En lecture seule : pas d'écriture.
        self.assertFalse(can_write(self.colleague, self.obj))

    def test_share_write_grants_write(self):
        share_object(self.obj, principal_type='user',
                     principal_id=self.colleague.pk, niveau='ecriture')
        self.assertTrue(can_write(self.colleague, self.obj))
        self.assertIn(
            str(self.obj.pk),
            visible_ids(self.colleague, type(self.obj), write=True))

    def test_share_to_role(self):
        role = Role.objects.create(company=self.company, nom='Equipe')
        member = UserFactory(
            company=self.company, username='rolemember', role=role)
        share_object(self.obj, principal_type='role', principal_id=role.id)
        self.assertIn(
            str(self.obj.pk), visible_ids(member, type(self.obj)))
        # Un utilisateur sans ce rôle ne voit rien.
        self.assertNotIn(
            str(self.obj.pk), visible_ids(self.colleague, type(self.obj)))

    def test_expired_rule_removes_access(self):
        rule = share_object(
            self.obj, principal_type='user', principal_id=self.colleague.pk)
        SharingRule.objects.filter(pk=rule.pk).update(
            expire_le=timezone.now() - timedelta(hours=1))
        self.assertEqual(visible_ids(self.colleague, type(self.obj)), set())

    def test_never_cross_tenant(self):
        other_company = CompanyFactory()
        stranger = UserFactory(company=other_company, username='stranger')
        share_object(self.obj, principal_type='user',
                     principal_id=stranger.pk)
        # Le bénéficiaire est dans une autre société : aucune fuite.
        self.assertEqual(visible_ids(stranger, type(self.obj)), set())
