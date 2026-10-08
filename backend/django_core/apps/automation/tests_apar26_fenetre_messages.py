"""APAR26 — les envois d'automatisation respectent la fenêtre des messages.

Constat C-APAR-034 : à 23:30 (Africa/Casablanca, fenêtre fermée), une règle
``send_email`` sur LEAD_STAGE_CHANGE envoyait immédiatement au client. Hors
fenêtre, l'envoi est désormais REPORTÉ au prochain créneau par une
``AutomationScheduledStep`` (mécanique NTEXT7) que le beat reprend.

Heure injectée : ``frozen`` prend une heure UTC — 22:30 UTC = 23:30 au Maroc.

Test-du-test : retirer l'appel à ``reporter_hors_fenetre`` de
``actions._send_email`` ⇒ ``test_23h30_rien_avant_l_ouverture`` rouge.
"""
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.automation.beat_tasks import process_due_automation_steps
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationScheduledStep,
    TriggerType,
)
from apps.crm.models import Lead
from apps.crm.stages import CONTACTED, NEW
from authentication.models import Company
from testkit.time import frozen

NUIT = '2026-01-05 22:30:00'      # lundi 23:30 au Maroc
LENDEMAIN = '2026-01-06 09:00:00'  # mardi 10:00 au Maroc


@override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
class FenetreMessagesTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar26-co', defaults={'nom': 'APAR26'})
        self.regle = AutomationRule.objects.create(
            company=self.co, nom='E-mail étape', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'Suivi', 'body': 'Bonjour'})
        self.lead = Lead.objects.create(
            company=self.co, nom='Client APAR26', stage=NEW,
            email='apar26@example.invalid')
        mail.outbox = []

    def test_23h30_rien_avant_l_ouverture(self):
        with frozen(NUIT):
            with self.captureOnCommitCallbacks(execute=True):
                self.lead.stage = CONTACTED
                self.lead.save()
            maintenant = timezone.now()
        self.assertEqual(len(mail.outbox), 0)
        echeance = AutomationScheduledStep.objects.get(
            company=self.co, rule=self.regle)
        self.assertGreater(echeance.run_at, maintenant)
        ouverture = timezone.localtime(echeance.run_at)
        self.assertGreaterEqual((ouverture.hour, ouverture.minute), (8, 30))

        # Le beat avant l'ouverture ne fait rien.
        with frozen(NUIT):
            with self.captureOnCommitCallbacks(execute=True):
                process_due_automation_steps()
        self.assertEqual(len(mail.outbox), 0)

        # À l'ouverture, le beat envoie UNE fois.
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                process_due_automation_steps()
                process_due_automation_steps()
        self.assertEqual(len(mail.outbox), 1)
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut, AutomationScheduledStep.Statut.REPRISE)
        self.assertTrue(AutomationRun.objects.filter(
            rule=self.regle, status=AutomationRun.Status.SUCCESS).exists())

    def test_en_journee_l_envoi_part_tout_de_suite(self):
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                self.lead.stage = CONTACTED
                self.lead.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(AutomationScheduledStep.objects.filter(
            rule=self.regle).exists())
