"""NTPLT37 — plan de partitionnement (génération SQL testable sans base)."""
from datetime import date

from django.test import SimpleTestCase

from core.partition_tooling import PartitionPlan


class PartitionPlanTests(SimpleTestCase):
    def _plan(self):
        return PartitionPlan('audit_auditlog', 'created_at',
                             date(2026, 1, 15), date(2026, 3, 2))

    def test_monthly_partitions_cover_range(self):
        parts = self._plan().partitions()
        self.assertEqual([p['name'] for p in parts],
                         ['audit_auditlog_p202601', 'audit_auditlog_p202602',
                          'audit_auditlog_p202603'])
        # Bornes mensuelles [1er du mois, 1er du mois suivant).
        self.assertEqual(parts[0]['from'], '2026-01-01')
        self.assertEqual(parts[0]['to'], '2026-02-01')
        self.assertEqual(parts[2]['to'], '2026-04-01')

    def test_create_statements_partition_by_range(self):
        stmts = self._plan().create_statements()
        self.assertIn('PARTITION BY RANGE (created_at)', stmts[0])
        self.assertTrue(stmts[0].startswith(
            'CREATE TABLE audit_auditlog_part_new'))
        self.assertEqual(len(stmts), 1 + 3)  # shadow + 3 partitions

    def test_swap_is_atomic_and_keeps_old(self):
        plan = self._plan()
        swap = plan.swap_statements()
        self.assertEqual(swap[0], 'BEGIN;')
        self.assertEqual(swap[-1], 'COMMIT;')
        self.assertIn(f'RENAME TO {plan.old}', swap[1])
        self.assertEqual(plan.old, 'audit_auditlog_old')

    def test_revert_restores_from_old(self):
        plan = self._plan()
        revert = plan.revert_statements()
        self.assertTrue(any(f'{plan.old} RENAME TO {plan.table}' in s
                            for s in revert))

    def test_year_boundary_partitions(self):
        plan = PartitionPlan('t', 'd', date(2025, 12, 1), date(2026, 1, 20))
        names = [p['name'] for p in plan.partitions()]
        self.assertEqual(names, ['t_p202512', 't_p202601'])
