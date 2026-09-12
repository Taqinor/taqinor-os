"""Tests NTWFL5 — intégration bout en bout notifications <-> core.workflow.

Couvre :
- Démarrer un ``core.workflow`` notifie les managers de la société
  (``EventType.APPROVAL_REQUESTED``, comble YEVNT8 pour FG366).
- ``sweep_workflow_step_reminders`` relance UNE SEULE FOIS une étape après
  50% du SLA, jamais avant, jamais deux fois (marqueur ``dernier_rappel_le``).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import workflow
from core.models import WorkflowDefinition, WorkflowStepDefinition

from .models import EventType, Notification
from .services import sweep_workflow_step_reminders

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


class DemarrerWorkflowNotifieLesManagersTests(TestCase):
    def setUp(self):
        self.company = _company('ntwfl5-notify-a')
        self.admin = _admin(self.company, 'ntwfl5-admin-a')

    def test_demarrage_cree_une_notification_approval_requested(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl5-notify', nom='NTWFL5')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Validation')

        workflow.demarrer_workflow(wf, self.company, self.company)

        notifs = Notification.objects.filter(
            recipient=self.admin, event_type=EventType.APPROVAL_REQUESTED)
        self.assertTrue(notifs.exists())


class SweepWorkflowStepRemindersTests(TestCase):
    def setUp(self):
        self.company = _company('ntwfl5-notify-b')
        self.admin = _admin(self.company, 'ntwfl5-admin-b')

    def _instance(self, sla_heures, started):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code=f'ntwfl5-sweep-{sla_heures}',
            nom='NTWFL5 sweep')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape', sla_heures=sla_heures)
        return workflow.demarrer_workflow(
            wf, self.company, self.company, now=started)

    def test_relance_une_seule_fois_apres_mi_sla(self):
        started = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0))
        self._instance(48, started)
        mi_sla = started + datetime.timedelta(hours=30)  # > 50%

        count1 = sweep_workflow_step_reminders(self.company, now=mi_sla)
        self.assertEqual(count1, 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin,
                event_type=EventType.APPROVAL_REMINDER).exists())

        # Un second passage (même moment ou plus tard) ne relance plus.
        count2 = sweep_workflow_step_reminders(
            self.company, now=mi_sla + datetime.timedelta(hours=1))
        self.assertEqual(count2, 0)

    def test_aucun_rappel_avant_mi_sla(self):
        started = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0))
        self._instance(48, started)
        avant = started + datetime.timedelta(hours=5)
        count = sweep_workflow_step_reminders(self.company, now=avant)
        self.assertEqual(count, 0)
