"""NTSEC23 — Tests permissions au niveau champ (field-level masking).

Garanties : sans règle la sérialisation est inchangée ; « masque » retire le
champ de la réponse ; « lecture » interdit l'écriture ; super-admin non
restreint ; scope société respecté.
"""
from types import SimpleNamespace

from django.test import TestCase
from rest_framework import serializers

from apps.roles.models import Role
from authentication.models import CustomUser
from core.field_permissions import FieldPermissionMixin, FieldPermissionRule
from testkit.factories import CompanyFactory, UserFactory


class _UserFP(FieldPermissionMixin, serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name']


class FieldPermissionTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.role = Role.objects.create(company=self.company, nom='Limite')
        self.caller = UserFactory(
            company=self.company, username='caller', role=self.role)
        self.subject = UserFactory(
            company=self.company, username='subject', email='s@x.com')

    def _ctx(self, user=None):
        return {'request': SimpleNamespace(user=user or self.caller)}

    def _rule(self, field, acces, company=None, role_id=None):
        from django.contrib.contenttypes.models import ContentType
        FieldPermissionRule.objects.create(
            company=company or self.company,
            content_type=ContentType.objects.get_for_model(CustomUser),
            field_name=field, role_id=str(role_id or self.role.id),
            acces=acces)

    def test_no_rule_unchanged(self):
        data = _UserFP(self.subject, context=self._ctx()).data
        self.assertIn('email', data)

    def test_masque_hides_field(self):
        self._rule('email', 'masque')
        data = _UserFP(self.subject, context=self._ctx()).data
        self.assertNotIn('email', data)
        self.assertIn('username', data)

    def test_lecture_blocks_write(self):
        self._rule('email', 'lecture')
        ser = _UserFP(
            self.subject, data={'username': 'subject', 'email': 'new@x.com'},
            context=self._ctx(), partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        # Le champ « lecture » est retiré du validated_data (jamais écrit).
        self.assertNotIn('email', ser.validated_data)

    def test_ecriture_allows_write(self):
        self._rule('email', 'ecriture')
        ser = _UserFP(
            self.subject, data={'email': 'new@x.com'},
            context=self._ctx(), partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data.get('email'), 'new@x.com')

    def test_superuser_not_restricted(self):
        self._rule('email', 'masque')
        su = UserFactory(
            company=self.company, username='su', is_superuser=True,
            role=self.role)
        data = _UserFP(self.subject, context=self._ctx(su)).data
        self.assertIn('email', data)

    def test_rule_scoped_to_company(self):
        other = CompanyFactory()
        self._rule('email', 'masque', company=other)
        # La règle est dans une autre société → n'affecte pas cet appelant.
        data = _UserFP(self.subject, context=self._ctx()).data
        self.assertIn('email', data)

    def test_rule_scoped_to_role(self):
        other_role = Role.objects.create(company=self.company, nom='Autre')
        self._rule('email', 'masque', role_id=other_role.id)
        # Règle ciblant un AUTRE rôle → pas d'effet pour cet appelant.
        data = _UserFP(self.subject, context=self._ctx()).data
        self.assertIn('email', data)
