"""WIR50 — la tâche beat ``identity.revoke_expired_break_glass`` est
enregistrée sous le bon nom et s'exécute (balayage global, no-op sans octroi
break-glass échu).

Placé dans l'app ``identity`` : l'import de ``apps.identity.tasks`` y est
intra-app. La frontière import-linter (M3) interdit à ``core`` de l'importer
(``identity.tasks`` atteint transitivement stock/ventes), d'où ce fichier
distinct du test de planification beat côté ``core``.
"""
from django.test import TestCase

from apps.identity.tasks import revoke_expired_break_glass_task


class Wir50BreakGlassBeatTests(TestCase):
    def test_task_registered_with_expected_name(self):
        self.assertEqual(
            revoke_expired_break_glass_task.name,
            'identity.revoke_expired_break_glass')

    def test_task_runs_and_sweeps(self):
        # Balayage global (toutes sociétés) ; sans octroi échu, zéro révocation.
        self.assertEqual(revoke_expired_break_glass_task(), {'revoques': 0})
