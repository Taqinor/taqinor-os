"""Tests YHARD2 — journal des actions IA confirmées + rollback.

Couvre : journalisation à la confirmation (scopée société), refus
d'annulation d'une action irréversible / déjà annulée / sans handler,
annulation réussie via un handler enregistré, isolation multi-tenant de
l'endpoint de lecture + de l'endpoint d'annulation.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from apps.agent import services
from apps.agent.models import AgentActionLog
from apps.agent.views import AgentActionLogView, AgentActionUndoView

User = get_user_model()


class LogConfirmedActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD2 Co')
        cls.other = Company.objects.create(nom='YHARD2 Autre')
        cls.user = User.objects.create_user(
            username='yhard2_user', password='x', company=cls.company)

    def test_log_creates_entry_scoped_to_company(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='devis.envoyer',
            risk_level=AgentActionLog.RiskLevel.OUTWARD, inputs={'devis_id': 1})
        self.assertEqual(log.company_id, self.company.id)
        self.assertEqual(log.action_key, 'devis.envoyer')
        self.assertIsNotNone(log.executed_at)
        self.assertIsNone(log.undone_at)

    def test_log_derives_content_type_from_resulted_object(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='crm.creer_client',
            risk_level=AgentActionLog.RiskLevel.INTERNAL,
            resulted_object=self.company)
        self.assertIsNotNone(log.content_type)
        self.assertEqual(log.object_id, str(self.company.pk))


class AnnulerActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD2 Undo Co')
        cls.user = User.objects.create_user(
            username='yhard2_undo', password='x', company=cls.company)

    def setUp(self):
        self._calls = []
        services.register_undo_handler('test.reversible', self._fake_handler)

    def _fake_handler(self, log):
        self._calls.append(log.pk)
        return 'annule (test)'

    def test_irreversible_action_cannot_be_undone(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.reversible',
            risk_level=AgentActionLog.RiskLevel.IRREVERSIBLE)
        with self.assertRaises(services.ActionNotUndoableError):
            services.annuler_action(log)
        self.assertEqual(self._calls, [])

    def test_no_handler_registered_refuses(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.no_handler',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        with self.assertRaises(services.ActionNotUndoableError):
            services.annuler_action(log)

    def test_reversible_action_undo_calls_handler_and_marks_undone(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.reversible',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        result = services.annuler_action(log)
        self.assertEqual(self._calls, [log.pk])
        self.assertIsNotNone(result.undone_at)
        self.assertEqual(result.undo_detail, 'annule (test)')

    def test_already_undone_action_cannot_be_undone_again(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.reversible',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        services.annuler_action(log)
        with self.assertRaises(services.ActionNotUndoableError):
            services.annuler_action(log)
        self.assertEqual(len(self._calls), 1)


class AgentActionLogEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD2 EP Co')
        cls.other = Company.objects.create(nom='YHARD2 EP Autre')
        cls.admin = User.objects.create_user(
            username='yhard2_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.plain = User.objects.create_user(
            username='yhard2_plain', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_list_scoped_to_company(self):
        services.log_confirmed_action(
            company=self.company, user=self.admin, action_key='a',
            risk_level=AgentActionLog.RiskLevel.INTERNAL)
        services.log_confirmed_action(
            company=self.other, user=self.admin, action_key='b',
            risk_level=AgentActionLog.RiskLevel.INTERNAL)
        req = self.factory.get('/logs/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionLogView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_non_admin_forbidden(self):
        req = self.factory.get('/logs/')
        force_authenticate(req, user=self.plain)
        resp = AgentActionLogView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_undo_endpoint_scoped_to_company_404_for_other(self):
        services.register_undo_handler('test.endpoint', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.other, user=self.admin, action_key='test.endpoint',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        req = self.factory.post(f'/logs/{log.pk}/annuler/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionUndoView.as_view()(req, pk=log.pk)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_undo_endpoint_success(self):
        services.register_undo_handler('test.endpoint2', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.company, user=self.admin, action_key='test.endpoint2',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        req = self.factory.post(f'/logs/{log.pk}/annuler/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionUndoView.as_view()(req, pk=log.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        log.refresh_from_db()
        self.assertIsNotNone(log.undone_at)

    def test_undo_endpoint_irreversible_conflict(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.admin, action_key='test.irrev',
            risk_level=AgentActionLog.RiskLevel.IRREVERSIBLE)
        req = self.factory.post(f'/logs/{log.pk}/annuler/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionUndoView.as_view()(req, pk=log.pk)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
