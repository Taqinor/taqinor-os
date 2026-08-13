"""NTEXT7 — étape « Attendre » (WAIT) : suspension puis reprise d'une séquence.

Une étape ``WAIT`` ne bloque aucun thread : elle écrit une échéance
(``AutomationScheduledStep``, contexte gelé) et rend la main. La tâche beat
``process_due_automation_steps`` reprend, à date, la séquence là où elle s'est
arrêtée — et sans beat déployé, la séquence reste simplement suspendue.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord

from apps.automation import engine
from apps.automation.beat_tasks import process_due_automation_steps
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationScheduledStep,
    AutomationStep, TriggerType,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class WaitStepTests(TestCase):
    def setUp(self):
        self.co = make_company('ntext7-a', 'NTEXT7 A')
        self.objet = CustomObjectDef.objects.create(
            company=self.co, code='suivi', libelle='Suivi')
        CustomFieldDef.objects.create(
            company=self.co, module='custom:suivi', code='titre',
            libelle='Titre', type='text', obligatoire=True)
        self.lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        self.rule = AutomationRule.objects.create(
            company=self.co, nom='Suivi J+7',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config={})

    def _sequence(self, delai_minutes=7 * 24 * 60):
        AutomationStep.objects.create(
            rule=self.rule, ordre=1, action_type=ActionType.WAIT,
            action_config={'delai_minutes': delai_minutes})
        AutomationStep.objects.create(
            rule=self.rule, ordre=2,
            action_type=ActionType.CREATE_CUSTOM_RECORD,
            action_config={'object_code': 'suivi',
                           'data': {'titre': 'Relance {reference}'}})

    def test_wait_suspends_sequence_and_schedules_resume(self):
        self._sequence()
        status, message = engine.run_action(
            self.rule, self.lead, self.co, context={'reference': 'DV-1'})
        self.assertEqual(status, AutomationRun.Status.NOOP)
        self.assertIn('suspendue', message)
        echeance = AutomationScheduledStep.objects.get(company=self.co)
        self.assertEqual(echeance.statut,
                         AutomationScheduledStep.Statut.EN_ATTENTE)
        self.assertEqual(echeance.next_step_index, 1)
        self.assertEqual(echeance.context['reference'], 'DV-1')
        self.assertEqual(echeance.target_model, 'crm.lead')
        self.assertEqual(echeance.target_id, self.lead.pk)
        # La suite de la séquence n'a PAS été exécutée.
        self.assertEqual(CustomRecord.objects.count(), 0)
        # Échéance dans le futur : le beat ne la reprend pas encore.
        self.assertEqual(process_due_automation_steps(), 0)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_beat_resumes_due_sequence_from_next_step(self):
        self._sequence()
        engine.run_action(self.rule, self.lead, self.co,
                          context={'reference': 'DV-2'})
        echeance = AutomationScheduledStep.objects.get(company=self.co)
        echeance.run_at = timezone.now() - timedelta(minutes=1)
        echeance.save(update_fields=['run_at'])

        self.assertEqual(process_due_automation_steps(), 1)
        record = CustomRecord.objects.get(company=self.co)
        self.assertEqual(record.data['titre'], 'Relance DV-2')
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut,
                         AutomationScheduledStep.Statut.REPRISE)

    def test_resume_is_idempotent(self):
        self._sequence()
        engine.run_action(self.rule, self.lead, self.co,
                          context={'reference': 'DV-3'})
        echeance = AutomationScheduledStep.objects.get(company=self.co)
        echeance.run_at = timezone.now() - timedelta(minutes=1)
        echeance.save(update_fields=['run_at'])
        process_due_automation_steps()
        # Deuxième passage : l'échéance n'est plus due, rien n'est refait.
        self.assertEqual(process_due_automation_steps(), 0)
        self.assertEqual(CustomRecord.objects.count(), 1)
        echeance.refresh_from_db()
        status, _msg = engine.resume_scheduled_step(echeance)
        self.assertEqual(status, AutomationRun.Status.SKIPPED)
        self.assertEqual(CustomRecord.objects.count(), 1)

    def test_disabled_rule_is_not_resumed(self):
        self._sequence()
        engine.run_action(self.rule, self.lead, self.co, context={})
        self.rule.enabled = False
        self.rule.save(update_fields=['enabled'])
        echeance = AutomationScheduledStep.objects.get(company=self.co)
        echeance.run_at = timezone.now() - timedelta(minutes=1)
        echeance.save(update_fields=['run_at'])
        process_due_automation_steps()
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_wait_alone_without_sequence_is_noop(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Attente seule',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.WAIT,
            action_config={'delai_minutes': 60})
        status, _message = engine.run_action(rule, self.lead, self.co)
        self.assertEqual(status, AutomationRun.Status.NOOP)
        self.assertEqual(AutomationScheduledStep.objects.count(), 0)

    def test_resume_target_is_company_scoped(self):
        self._sequence()
        engine.run_action(self.rule, self.lead, self.co, context={})
        autre = make_company('ntext7-b', 'NTEXT7 B')
        echeance = AutomationScheduledStep.objects.get()
        # Cible d'une AUTRE société : elle ne doit jamais être résolue.
        lead_autre = Lead.objects.create(company=autre, nom='X', stage='NEW')
        echeance.target_id = lead_autre.pk
        echeance.run_at = timezone.now() - timedelta(minutes=1)
        echeance.save(update_fields=['target_id', 'run_at'])
        self.assertIsNone(engine._resolve_target(
            'crm.lead', lead_autre.pk, self.co))
        process_due_automation_steps()
        # La séquence reprend quand même (l'action ne dépend pas de la cible
        # ici) mais l'objet d'une autre société n'a jamais été touché.
        lead_autre.refresh_from_db()
        self.assertEqual(lead_autre.stage, 'NEW')
