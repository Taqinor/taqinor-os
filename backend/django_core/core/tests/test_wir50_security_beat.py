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
"""
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

    def test_tasks_registered_with_expected_names(self):
        from apps.identity.tasks import revoke_expired_break_glass_task
        from authentication.tasks import desactiver_comptes_dormants_task
        from core.tasks import escalate_workflow_sla_task
        self.assertEqual(
            revoke_expired_break_glass_task.name,
            'identity.revoke_expired_break_glass')
        self.assertEqual(
            desactiver_comptes_dormants_task.name,
            'authentication.desactiver_comptes_dormants')
        self.assertEqual(
            escalate_workflow_sla_task.name, 'core.escalate_workflow_sla')

    def test_revoke_break_glass_task_runs_and_sweeps(self):
        # Balayage global (toutes sociétés) ; sans octroi échu, zéro révocation.
        from apps.identity.tasks import revoke_expired_break_glass_task
        self.assertEqual(revoke_expired_break_glass_task(), {'revoques': 0})

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
