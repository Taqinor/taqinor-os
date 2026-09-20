"""NTWFL15 — deep-link « un clic » ``/approbations/:source/:id``.

XKB1 (backend) + FE-XKB1-3/ZCTR7-9 livrent déjà la liste d'approbations
mobile ; ce ticket ajoute la couche manquante côté notification : cliquer
sur une notification de relance/escalade d'approbation doit atterrir
DIRECTEMENT sur la carte de décision, pas sur la liste générique.

Couverture (dans ce lot, backend uniquement — la carte mobile/swipe est
FE-XKB1-3/ZCTR7-9, hors périmètre de cette lane) :
  - une relance/escalade d'approbation ``automation`` porte un lien
    ``/approbations/automation/<id>`` (pas la query-string générique
    ``?source=automation`` d'avant) et un ``approval_action`` exploitable
    par le push (NTMOB7 : jetons Approuver/Refuser).
  - une relance d'étape BPM (NTWFL5) porte ``/approbations/workflow/<id>``.
  - la demande d'approbation compta (page de config dédiée, pas la liste
    unifiée) n'est PAS concernée : son lien reste inchangé.
"""
import datetime
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import workflow
from core.models import WorkflowDefinition, WorkflowStepDefinition

from .models import EventType, Notification

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


class AutomationApprovalDeepLinkTests(TestCase):
    def setUp(self):
        self.company = _company('ntwfl15-auto')
        self.approver = _admin(self.company, 'ntwfl15-auto-approver')
        self.requester = User.objects.create_user(
            username='ntwfl15-auto-requester', password='x',
            company=self.company, role_legacy='normal')

    def _pending_approval(self, days_old):
        from apps.automation.models import (
            ActionType, AutomationApproval, AutomationRule, TriggerType,
        )
        rule = AutomationRule.objects.create(
            company=self.company, nom='Règle NTWFL15',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL, requires_approval=True)
        approval = AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action en attente',
            requested_by=self.requester)
        approval.date_creation = timezone.now() - timedelta(days=days_old)
        approval.save(update_fields=['date_creation'])
        return approval

    def test_relance_porte_le_deeplink_un_clic(self):
        from .services import sweep_approval_reminders
        approval = self._pending_approval(days_old=5)
        sweep_approval_reminders(self.company)
        notif = Notification.objects.get(
            recipient=self.approver, event_type=EventType.APPROVAL_REMINDER)
        self.assertEqual(notif.link, f'/approbations/automation/{approval.pk}')

    def test_escalade_porte_le_deeplink_un_clic(self):
        from .services import sweep_approval_reminders
        approval = self._pending_approval(days_old=10)
        sweep_approval_reminders(self.company)
        notif = Notification.objects.get(
            recipient=self.approver, event_type=EventType.APPROVAL_ESCALATED)
        self.assertEqual(notif.link, f'/approbations/automation/{approval.pk}')


class ComptaApprovalLinkUnchangedTests(TestCase):
    """La demande d'approbation compta pointe une page de config dédiée
    (pas la liste unifiée des 5 sources ``reporting.approbations``) : son
    lien n'est PAS transformé en deep-link ``/approbations/:source/:id``."""

    def setUp(self):
        self.company = _company('ntwfl15-compta')
        self.approver = _admin(self.company, 'ntwfl15-compta-approver')
        self.requester = User.objects.create_user(
            username='ntwfl15-compta-requester', password='x',
            company=self.company, role_legacy='normal')

    def test_lien_compta_reste_la_page_de_config(self):
        from apps.compta.models import DemandeApprobationConfig
        from .services import sweep_approval_reminders
        demande = DemandeApprobationConfig.objects.create(
            company=self.company, devis_reference='DV-NTWFL15-1',
            motif='motif test', demandeur=self.requester)
        demande.date_creation = timezone.now() - timedelta(days=5)
        demande.save(update_fields=['date_creation'])
        sweep_approval_reminders(self.company)
        notif = Notification.objects.get(
            recipient=self.approver, event_type=EventType.APPROVAL_REMINDER)
        self.assertEqual(notif.link, '/comptabilite/approbations-config')


class WorkflowStepReminderDeepLinkTests(TestCase):
    def setUp(self):
        self.company = _company('ntwfl15-wf')
        self.admin = _admin(self.company, 'ntwfl15-wf-admin')

    def test_relance_etape_porte_le_deeplink_un_clic(self):
        from .services import sweep_workflow_step_reminders
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl15-wf', nom='NTWFL15 workflow')
        step_def = WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape', sla_heures=48)
        started = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0))
        instance = workflow.demarrer_workflow(
            wf, self.company, self.company, now=started)
        mi_sla = started + datetime.timedelta(hours=30)  # > 50% du SLA

        sweep_workflow_step_reminders(self.company, now=mi_sla)

        step = instance.step_instances.get(step_def=step_def)
        notif = Notification.objects.get(
            recipient=self.admin, event_type=EventType.APPROVAL_REMINDER)
        self.assertEqual(notif.link, f'/approbations/workflow/{step.pk}')
