"""PUB23 — Armer/désarmer une règle depuis la console (RulesScreen).

Prouve : le CRUD existant ``RulePolicyViewSet`` (``regles/``) suffit à armer
(créer OU PATCH ``enabled=True, dry_run=False``) et désarmer
(``enabled=False, dry_run=True``) une instance ``RulePolicy`` — AUCUNE route
nouvelle. Un basculement d'``enabled`` laisse une trace dans le journal
d'audit UNIFIÉ de l'ERP (``apps.audit.AuditLog``, ARC16), jamais un second
système ad hoc. Écriture réservée à ``adsengine_manage`` (permission déjà
portée par la base ``AdsengineViewSet``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import RulePolicy
from apps.audit.models import AuditLog

User = get_user_model()
REGLES_URL = '/api/django/adsengine/regles/'


def _make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ArmDisarmTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB23 Co', slug='pub23-co')
        self.manager = _make_user(
            self.company, 'pub23mgr', ['adsengine_view', 'adsengine_manage'])
        self.viewer = _make_user(
            self.company, 'pub23viewer', ['adsengine_view'])

    def test_arm_creates_policy_enabled_not_dry_run(self):
        resp = _auth(self.manager).post(
            REGLES_URL,
            {'template_key': 'zero_delivery', 'enabled': True, 'dry_run': False},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rule = RulePolicy.objects.get(pk=resp.data['id'])
        self.assertTrue(rule.enabled)
        self.assertFalse(rule.dry_run)

    def test_arm_then_disarm_existing_policy(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery')
        self.assertFalse(rule.enabled)

        resp = _auth(self.manager).patch(
            f'{REGLES_URL}{rule.id}/', {'enabled': True, 'dry_run': False},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        rule.refresh_from_db()
        self.assertTrue(rule.enabled)
        self.assertFalse(rule.dry_run)

        resp = _auth(self.manager).patch(
            f'{REGLES_URL}{rule.id}/', {'enabled': False, 'dry_run': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        rule.refresh_from_db()
        self.assertFalse(rule.enabled)
        self.assertTrue(rule.dry_run)

    def test_arm_toggle_leaves_audit_trail(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery')
        before = AuditLog.objects.filter(company=self.company).count()

        _auth(self.manager).patch(
            f'{REGLES_URL}{rule.id}/', {'enabled': True, 'dry_run': False},
            format='json')

        after = AuditLog.objects.filter(company=self.company).count()
        self.assertGreater(after, before)

    def test_no_op_update_does_not_duplicate_audit(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery',
            enabled=True, dry_run=False)
        before = AuditLog.objects.filter(company=self.company).count()

        # PATCH sans changer `enabled` : aucune écriture d'audit supplémentaire.
        _auth(self.manager).patch(
            f'{REGLES_URL}{rule.id}/', {'enabled': True}, format='json')

        after = AuditLog.objects.filter(company=self.company).count()
        self.assertEqual(after, before)

    def test_view_only_cannot_arm(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery')
        resp = _auth(self.viewer).patch(
            f'{REGLES_URL}{rule.id}/', {'enabled': True, 'dry_run': False},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        rule.refresh_from_db()
        self.assertFalse(rule.enabled)
