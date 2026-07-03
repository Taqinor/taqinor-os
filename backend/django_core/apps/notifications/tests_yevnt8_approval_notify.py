"""YEVNT8 — les demandes d'approbation notifient l'approbateur, puis le
demandeur à la décision. Couvre les DEUX moteurs d'approbation :
  - ``automation.AutomationApproval`` (N73) ;
  - ``compta.DemandeApprobationConfig`` (FG213).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from .models import EventType, Notification

User = get_user_model()


def _make_company(name='ApprovalNotifyCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class AutomationApprovalNotifyTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.approver = _make_user(self.company, 'approver1', role_legacy='admin')
        self.requester = _make_user(self.company, 'requester1')

    def _make_rule(self):
        from apps.automation.models import ActionType, AutomationRule, TriggerType
        return AutomationRule.objects.create(
            company=self.company, nom='Règle test',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL,
            requires_approval=True)

    def test_pending_approval_creation_notifies_approver(self):
        from apps.automation.models import AutomationApproval
        rule = self._make_rule()
        AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action à valider',
            requested_by=self.requester)
        notifs = Notification.objects.filter(
            recipient=self.approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notifs.count(), 1)

    def test_approval_decision_notifies_requester(self):
        from apps.automation.models import AutomationApproval
        rule = self._make_rule()
        approval = AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action à valider',
            requested_by=self.requester)
        Notification.objects.all().delete()

        approval.status = AutomationApproval.Status.APPROVED
        approval.decided_by = self.approver
        approval.save()

        notifs = Notification.objects.filter(
            recipient=self.requester, event_type=EventType.APPROVAL_DECIDED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('approuvée', notifs.first().body)

    def test_rejection_notifies_requester_with_motif_in_description(self):
        from apps.automation.models import AutomationApproval
        rule = self._make_rule()
        approval = AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Remise 40%',
            requested_by=self.requester)
        Notification.objects.all().delete()

        approval.status = AutomationApproval.Status.REJECTED
        approval.save()

        notifs = Notification.objects.filter(
            recipient=self.requester, event_type=EventType.APPROVAL_DECIDED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('rejetée', notifs.first().body)

    def test_resave_while_still_pending_does_not_reemit(self):
        from apps.automation.models import AutomationApproval
        rule = self._make_rule()
        approval = AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action à valider',
            requested_by=self.requester)
        Notification.objects.all().delete()
        approval.save()  # re-save, toujours PENDING
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.APPROVAL_DECIDED).count(), 0)


class DemandeApprobationConfigNotifyTests(TestCase):

    def setUp(self):
        self.company = _make_company('ComptaApprovalCo')
        self.approver = _make_user(self.company, 'compta_approver', role_legacy='admin')
        self.requester = _make_user(self.company, 'compta_requester')

    def test_pending_demande_notifies_approver(self):
        from apps.compta.models import DemandeApprobationConfig
        DemandeApprobationConfig.objects.create(
            company=self.company, devis_reference='DV-YEVNT8-1',
            motif='kWc/onduleur incohérents', demandeur=self.requester)
        notifs = Notification.objects.filter(
            recipient=self.approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notifs.count(), 1)

    def test_decision_notifies_demandeur_with_motif(self):
        from apps.compta import services as compta_services
        from apps.compta.models import DemandeApprobationConfig
        demande = DemandeApprobationConfig.objects.create(
            company=self.company, devis_reference='DV-YEVNT8-2',
            motif='kWc/onduleur incohérents', demandeur=self.requester)
        Notification.objects.all().delete()

        compta_services.decider_approbation_config(
            demande, approuver=False, user=self.approver,
            commentaire='Composition non conforme au catalogue.')

        notifs = Notification.objects.filter(
            recipient=self.requester, event_type=EventType.APPROVAL_DECIDED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('refusée', notifs.first().body)
        self.assertIn('Composition non conforme', notifs.first().body)

    def test_idempotent_decision_does_not_reemit(self):
        """`decider_approbation_config` est déjà idempotent (ne redécide pas
        une demande déjà tranchée) -> pas de second envoi."""
        from apps.compta import services as compta_services
        from apps.compta.models import DemandeApprobationConfig
        demande = DemandeApprobationConfig.objects.create(
            company=self.company, devis_reference='DV-YEVNT8-3',
            motif='motif', demandeur=self.requester)
        compta_services.decider_approbation_config(
            demande, approuver=True, user=self.approver)
        Notification.objects.all().delete()
        compta_services.decider_approbation_config(
            demande, approuver=True, user=self.approver)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.APPROVAL_DECIDED).count(), 0)
