"""APAR17 — décision d'approbation VERROUILLÉE.

Constat C-APAR-023 : ``services.decider_approval`` (et les actions
``approve``/``reject`` de la vue, copie divergente) testaient ``status`` sur
l'instance EN MÉMOIRE : deux décisions lues avant la première (approuver puis
refuser) passaient toutes les deux — action exécutée ET statut final
``rejected``.

Test-du-test : retirer ``select_for_update``/la relecture PENDING de
``decider_approval`` ⇒ ``test_deux_decisions_concurrentes`` rouge.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation import engine, services
from apps.automation.models import (
    ActionType, AutomationApproval, AutomationRule, TriggerType,
)
from authentication.models import Company

User = get_user_model()


class DecisionVerrouTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar17-co', defaults={'nom': 'APAR17'})
        self.resp1 = User.objects.create_user(
            username='apar17-r1', password='x', company=self.co,
            role_legacy='responsable')
        self.resp2 = User.objects.create_user(
            username='apar17-r2', password='x', company=self.co,
            role_legacy='admin')
        self.regle = AutomationRule.objects.create(
            company=self.co, nom='Différée', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.WAIT, action_config={},
            requires_approval=True)
        self.demande = AutomationApproval.objects.create(
            company=self.co, rule=self.regle, description='x',
            status=AutomationApproval.Status.PENDING)

    def test_deux_decisions_concurrentes(self):
        lue_a = AutomationApproval.objects.get(pk=self.demande.pk)
        lue_b = AutomationApproval.objects.get(pk=self.demande.pk)
        with mock.patch.object(engine, 'run_approved',
                               wraps=engine.run_approved) as espion:
            with self.captureOnCommitCallbacks(execute=True):
                services.decider_approval(lue_a, approve=True, user=self.resp1)
            with self.assertRaisesMessage(
                    services.DecisionError, 'Décision déjà prise'):
                with self.captureOnCommitCallbacks(execute=True):
                    services.decider_approval(
                        lue_b, approve=False, user=self.resp2)
        self.assertEqual(espion.call_count, 1)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.status,
                         AutomationApproval.Status.APPROVED)
        self.assertEqual(self.demande.decided_by_id, self.resp1.pk)

    def test_vue_seconde_decision_400(self):
        url = f'/api/django/automation/approvals/{self.demande.pk}/'
        api1, api2 = APIClient(), APIClient()
        api1.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp1)}')
        api2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp2)}')
        with self.captureOnCommitCallbacks(execute=True):
            r1 = api1.post(url + 'approve/')
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = api2.post(url + 'reject/')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn('Décision déjà prise', r2.data['detail'])
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.status,
                         AutomationApproval.Status.APPROVED)
        self.assertEqual(self.demande.decided_by_id, self.resp1.pk)
