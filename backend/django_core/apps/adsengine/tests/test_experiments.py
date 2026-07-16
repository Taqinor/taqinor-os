"""ADSENG3 — Tests des modèles d'expérimentation.

Prouve : l'upsert quotidien est idempotent (une re-synchro du même jour écrase,
jamais de doublon), le CRUD des expériences/bras est company-scopé (isolation
multi-tenant, FK cross-société refusée), et le journal de décision est en
lecture seule côté API.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.adsengine.models import (
    ArmDailyStat, DecisionLog, EngineAction, Experiment, ExperimentArm,
)

User = get_user_model()


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ArmDailyStatUpsertTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Exp Co', slug='exp-co')
        self.exp = Experiment.objects.create(
            company=self.company, name='Test Hooks',
            tested_variable=Experiment.Variable.HOOK)
        self.arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.exp, label='Bras A',
            ad_id='ad_1')

    def test_upsert_is_idempotent(self):
        day = datetime.date(2026, 7, 15)
        stat1, created1 = ArmDailyStat.upsert(
            arm=self.arm, date=day, impressions=1000, clicks=30,
            conversations=5, spend=Decimal('20.00'))
        self.assertTrue(created1)
        # Re-synchro du MÊME jour : écrase, jamais de doublon.
        stat2, created2 = ArmDailyStat.upsert(
            arm=self.arm, date=day, impressions=1200, clicks=36,
            conversations=6, spend=Decimal('24.00'))
        self.assertFalse(created2)
        self.assertEqual(stat1.pk, stat2.pk)
        self.assertEqual(
            ArmDailyStat.objects.filter(arm=self.arm, date=day).count(), 1)
        stat2.refresh_from_db()
        self.assertEqual(stat2.impressions, 1200)
        self.assertEqual(stat2.conversations, 6)
        self.assertEqual(stat2.spend, Decimal('24.00'))

    def test_upsert_derives_company_from_arm(self):
        stat, _ = ArmDailyStat.upsert(
            arm=self.arm, date=datetime.date(2026, 7, 16), impressions=100)
        self.assertEqual(stat.company_id, self.company.id)

    def test_distinct_days_are_separate_rows(self):
        ArmDailyStat.upsert(arm=self.arm, date=datetime.date(2026, 7, 15))
        ArmDailyStat.upsert(arm=self.arm, date=datetime.date(2026, 7, 16))
        self.assertEqual(ArmDailyStat.objects.filter(arm=self.arm).count(), 2)


class ExperimentCrudTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Crud Co', slug='crud-co')
        self.manager = make_user(
            self.company, 'mgr', ['adsengine_view', 'adsengine_manage'])

    def test_create_experiment_forces_company(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/experiences/',
            {'name': 'Exp API', 'tested_variable': 'visuel'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        exp = Experiment.objects.get(pk=resp.data['id'])
        self.assertEqual(exp.company_id, self.company.id)

    def test_list_scoped_to_company(self):
        Experiment.objects.create(company=self.company, name='Mine')
        other = Company.objects.create(nom='Other', slug='other-crud')
        Experiment.objects.create(company=other, name='Theirs')
        resp = auth(self.manager).get('/api/django/adsengine/experiences/')
        self.assertEqual(resp.status_code, 200)
        names = [r['name'] for r in resp.data['results']] if isinstance(
            resp.data, dict) and 'results' in resp.data else [
            r['name'] for r in resp.data]
        self.assertIn('Mine', names)
        self.assertNotIn('Theirs', names)

    def test_arm_rejects_cross_company_experiment(self):
        other = Company.objects.create(nom='Other2', slug='other2-crud')
        foreign_exp = Experiment.objects.create(company=other, name='Foreign')
        resp = auth(self.manager).post(
            '/api/django/adsengine/bras/',
            {'experiment': foreign_exp.id, 'label': 'X'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_manage_permission_required_to_create(self):
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        resp = auth(viewer).post(
            '/api/django/adsengine/experiences/',
            {'name': 'Nope'}, format='json')
        self.assertEqual(resp.status_code, 403)


class DecisionLogReadOnlyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Dec Co', slug='dec-co')
        self.manager = make_user(
            self.company, 'decmgr', ['adsengine_view', 'adsengine_manage'])
        self.exp = Experiment.objects.create(
            company=self.company, name='Dec Exp')

    def test_decision_log_links_action_nullable(self):
        action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.REBALANCE_BUDGET,
            reason_fr='Rééquilibrage proposé par la science.')
        log = DecisionLog.objects.create(
            company=self.company, experiment=self.exp,
            inputs={'arms': 2}, posteriors={'a': 0.6, 'b': 0.4},
            action=action)
        self.assertEqual(log.action_id, action.id)
        # Sans action liée (nullable).
        log2 = DecisionLog.objects.create(
            company=self.company, experiment=self.exp)
        self.assertIsNone(log2.action_id)

    def test_decision_log_is_read_only_via_api(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/decisions/',
            {'experiment': self.exp.id}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_decision_log_list_scoped(self):
        DecisionLog.objects.create(company=self.company, experiment=self.exp)
        resp = auth(self.manager).get('/api/django/adsengine/decisions/')
        self.assertEqual(resp.status_code, 200)
