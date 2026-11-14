"""WIR50 — les trois commandes périodiques de sécurité/gouvernance sont
PLANIFIÉES au Celery Beat, et leurs enveloppes ``@shared_task`` délèguent bien.

Jobs bâtis mais jamais planifiés (donc jamais exécutés en prod — mode de
défaillance dominant du dépôt) :
  * ``identity.revoke_expired_break_glass`` (toutes les ~10 min) — un octroi
    break-glass échu conservait sinon le rôle Administrateur (élévation de
    privilège persistante) ;
  * ``authentication.desactiver_comptes_dormants`` (quotidien) — un compte
    inactif au-delà du seuil société restait actif ;
  * ``core.escalate_workflow_sla`` (horaire) — une étape de workflow au SLA
    dépassé n'escaladait jamais.

Frontière import-linter : ce module (paquet ``core``) ne doit PAS importer
``apps.identity.tasks`` (qui atteint transitivement stock/ventes). La preuve
d'enregistrement + d'exécution de la tâche identity vit donc dans
``apps/identity/tests/test_wir50_break_glass_beat.py`` (import intra-app légal).
``authentication`` et ``core`` sont des apps fondation : leur import depuis
``core`` est autorisé.
"""
from io import StringIO
from unittest.mock import patch

from django.test import TestCase

from erp_agentique.celery import app

EXPECTED_TASKS = {
    'identity.revoke_expired_break_glass',
    'authentication.desactiver_comptes_dormants',
    'core.escalate_workflow_sla',
}


class Wir50SecurityBeatTests(TestCase):
    def _scheduled_task_names(self):
        return {entry['task'] for entry in app.conf.beat_schedule.values()}

    def test_three_security_tasks_are_scheduled(self):
        scheduled = self._scheduled_task_names()
        for name in EXPECTED_TASKS:
            self.assertIn(name, scheduled, name)

    def test_schedule_cadences(self):
        # Chaque entrée est joignable et porte une cadence (crontab).
        by_task = {e['task']: e for e in app.conf.beat_schedule.values()}
        for name in EXPECTED_TASKS:
            self.assertIn('schedule', by_task[name], name)

    def test_auth_and_core_tasks_registered_with_expected_names(self):
        # authentication + core = apps fondation (import légal depuis core) ;
        # identity est vérifié dans apps/identity/tests (frontière M3).
        from authentication.tasks import desactiver_comptes_dormants_task
        from core.tasks import escalate_workflow_sla_task
        self.assertEqual(
            desactiver_comptes_dormants_task.name,
            'authentication.desactiver_comptes_dormants')
        self.assertEqual(
            escalate_workflow_sla_task.name, 'core.escalate_workflow_sla')

    def test_dormant_task_delegates_to_command(self):
        from authentication.tasks import desactiver_comptes_dormants_task
        with patch('django.core.management.call_command') as mock_cc:
            result = desactiver_comptes_dormants_task()
        mock_cc.assert_called_once_with('desactiver_comptes_dormants')
        self.assertEqual(result, {'ok': True})

    def test_escalate_task_delegates_to_command(self):
        from core.tasks import escalate_workflow_sla_task
        with patch('django.core.management.call_command') as mock_cc:
            result = escalate_workflow_sla_task()
        mock_cc.assert_called_once_with('escalate_workflow_sla')
        self.assertEqual(result, {'ok': True})

    def test_escalade_ignore_les_societes_suspendues(self):
        """ACEL89 — le passage horaire n'escalade que les sociétés actives :
        l'étape au délai dépassé d'une société suspendue garde son statut."""
        import datetime

        from django.core.management import call_command
        from django.utils import timezone

        from authentication.models import Company
        from core import workflow
        from core.models import (
            WorkflowDefinition, WorkflowStepDefinition, WorkflowStepInstance,
        )
        active = Company.objects.create(nom='Active ACEL89')
        suspendue = Company.objects.create(
            nom='Suspendue ACEL89', statut=Company.STATUT_SUSPENDU)
        debut = timezone.make_aware(datetime.datetime(2026, 6, 28, 8, 0, 0))
        etapes = {}
        for societe in (active, suspendue):
            wf = WorkflowDefinition.objects.create(
                company=societe, code='acel89', nom='SLA ACEL89')
            WorkflowStepDefinition.objects.create(
                definition=wf, ordre=1, nom='M', sla_heures=1)
            workflow.demarrer_workflow(wf, societe, societe, now=debut)
            etapes[societe.pk] = WorkflowStepInstance.objects.get(
                company=societe, ordre=1)
        call_command('escalate_workflow_sla', now='2026-06-28T12:00:00',
                     stdout=StringIO())
        for etape in etapes.values():
            etape.refresh_from_db()
        self.assertEqual(etapes[active.pk].statut,
                         WorkflowStepInstance.STATUT_ESCALADE)
        self.assertEqual(etapes[suspendue.pk].statut,
                         WorkflowStepInstance.STATUT_EN_ATTENTE)
