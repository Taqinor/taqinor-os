"""YEVNT9 — relance/escalade des approbations en attente au-delà d'un seuil,
pour les DEUX moteurs (automation.AutomationApproval + compta.DemandeApprobationConfig).

Couverture :
  - avant le seuil de relance -> rien.
  - au-delà du seuil de relance -> une notification APPROVAL_REMINDER à
    l'approbateur, palier 1, jamais deux fois.
  - au-delà du seuil d'escalade -> APPROVAL_ESCALATED vers l'admin, palier 2,
    jamais deux fois, et ne re-déclenche pas la relance palier 1.
  - seuils configurables (ApprovalReminderConfig).
  - idempotent sur ré-exécution le même jour.
  - les deux moteurs sont couverts indépendamment.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .models import ApprovalReminderConfig, EventType, Notification

User = get_user_model()


def _make_company(name='ApprovalReminderCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


def timezone_ago(days):
    return timezone.now() - timedelta(days=days)


class AutomationApprovalReminderTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.approver = _make_user(self.company, 'auto_approver', role_legacy='admin')
        self.requester = _make_user(self.company, 'auto_requester')

    def _make_pending_approval(self, days_old):
        from apps.automation.models import (
            ActionType, AutomationApproval, AutomationRule, TriggerType,
        )
        rule = AutomationRule.objects.create(
            company=self.company, nom='Règle relance test',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL, requires_approval=True)
        approval = AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action en attente',
            requested_by=self.requester)
        approval.date_creation = timezone_ago(days_old)
        approval.save(update_fields=['date_creation'])
        return approval

    def test_no_reminder_before_threshold(self):
        from .services import sweep_approval_reminders
        self._make_pending_approval(days_old=0)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 0)

    def test_reminder_sent_after_threshold(self):
        from .services import sweep_approval_reminders
        self._make_pending_approval(days_old=5)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.approver,
            event_type=EventType.APPROVAL_REMINDER).exists())

    def test_reminder_not_resent_same_day(self):
        from .services import sweep_approval_reminders
        self._make_pending_approval(days_old=5)
        first = sweep_approval_reminders(self.company)
        second = sweep_approval_reminders(self.company)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_escalation_after_second_threshold(self):
        from .services import sweep_approval_reminders
        self._make_pending_approval(days_old=10)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.approver,
            event_type=EventType.APPROVAL_ESCALATED).exists())
        # L'escalade ne doit PAS aussi déclencher une relance palier 1
        # (un seul palier signalé par exécution).
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.APPROVAL_REMINDER).exists())

    def test_configurable_thresholds(self):
        from .services import sweep_approval_reminders
        ApprovalReminderConfig.objects.create(
            company=self.company, relance_days=10, escalade_days=20)
        self._make_pending_approval(days_old=5)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 0)  # 5 jours < seuil configuré (10)

    def test_selector_escalade_state_pour_reflects_palier(self):
        """VX218 — `selectors.escalade_state_pour` (lecture cross-app pour
        `reporting/approbations.py`) reflète le palier YEVNT9 sans jamais
        rien fabriquer pour une approbation jamais balayée."""
        from .selectors import escalade_state_pour
        from .services import sweep_approval_reminders

        approval = self._make_pending_approval(days_old=0)
        label, when = escalade_state_pour(approval)
        self.assertIsNone(label)
        self.assertIsNone(when)

        approval2 = self._make_pending_approval(days_old=5)
        sweep_approval_reminders(self.company)
        label2, when2 = escalade_state_pour(approval2)
        self.assertEqual(label2, 'relance')
        self.assertIsNotNone(when2)


class ComptaDemandeReminderTests(TestCase):

    def setUp(self):
        self.company = _make_company('ComptaReminderCo')
        self.approver = _make_user(self.company, 'compta_r_approver', role_legacy='admin')
        self.requester = _make_user(self.company, 'compta_r_requester')

    def _make_pending_demande(self, days_old):
        from apps.compta.models import DemandeApprobationConfig
        demande = DemandeApprobationConfig.objects.create(
            company=self.company, devis_reference='DV-Y9-1',
            motif='motif test', demandeur=self.requester)
        demande.date_creation = timezone_ago(days_old)
        demande.save(update_fields=['date_creation'])
        return demande

    def test_no_reminder_before_threshold(self):
        from .services import sweep_approval_reminders
        self._make_pending_demande(days_old=0)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 0)

    def test_reminder_then_escalation_over_time(self):
        from .services import sweep_approval_reminders
        demande = self._make_pending_demande(days_old=5)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.approver,
            event_type=EventType.APPROVAL_REMINDER).exists())

        # Le temps passe : la demande dépasse maintenant le seuil d'escalade.
        demande.date_creation = timezone_ago(10)
        demande.save(update_fields=['date_creation'])
        count2 = sweep_approval_reminders(self.company)
        self.assertEqual(count2, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.approver,
            event_type=EventType.APPROVAL_ESCALATED).exists())

    def test_decided_demande_not_relanced(self):
        """Une demande déjà décidée n'apparaît plus dans les en-attente ->
        aucune relance."""
        from apps.compta import services as compta_services
        from .services import sweep_approval_reminders
        demande = self._make_pending_demande(days_old=5)
        compta_services.decider_approbation_config(
            demande, approuver=True, user=self.approver)
        count = sweep_approval_reminders(self.company)
        self.assertEqual(count, 0)
