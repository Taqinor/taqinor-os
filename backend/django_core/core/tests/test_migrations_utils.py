"""Tests YOPSB6 — helper d'index concurrent + lock_timeout (migrations_utils).

Couvre : la classe produite est bien ``atomic = False``, ses ``operations``
sont dans l'ordre attendu (``RunSQL lock_timeout`` puis
``AddIndexConcurrently``), ``dependencies`` est posé tel que fourni, et
l'index/modèle/nom sont corrects. Pas de DB réelle nécessaire : on inspecte
la classe générée (pas d'exécution de migration)."""
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations
from django.test import SimpleTestCase

from core.migrations_utils import concurrent_index_migration


class ConcurrentIndexMigrationTests(SimpleTestCase):
    def _build(self):
        return concurrent_index_migration(
            app_label='crm',
            dependencies=[('crm', '0030_pointcontact')],
            model_name='lead',
            fields=['statut'],
            index_name='crm_lead_statut_idx',
        )

    def test_migration_is_non_atomic(self):
        Migration = self._build()
        self.assertFalse(Migration.atomic)

    def test_dependencies_are_set_as_provided(self):
        Migration = self._build()
        self.assertEqual(Migration.dependencies, [('crm', '0030_pointcontact')])

    def test_operations_order_lock_timeout_then_index(self):
        Migration = self._build()
        ops = Migration.operations
        self.assertEqual(len(ops), 2)
        self.assertIsInstance(ops[0], migrations.RunSQL)
        self.assertIn('lock_timeout', ops[0].sql)
        self.assertIsInstance(ops[1], AddIndexConcurrently)

    def test_index_targets_correct_model_and_fields(self):
        Migration = self._build()
        add_index_op = Migration.operations[1]
        self.assertEqual(add_index_op.model_name, 'lead')
        self.assertEqual(add_index_op.index.fields, ['statut'])
        self.assertEqual(add_index_op.index.name, 'crm_lead_statut_idx')

    def test_reverse_sql_is_noop(self):
        Migration = self._build()
        lock_timeout_op = Migration.operations[0]
        self.assertEqual(lock_timeout_op.reverse_sql, migrations.RunSQL.noop)

    def test_returns_a_fresh_class_each_call(self):
        """Deux appels ne doivent PAS partager la même classe/état mutable
        (chaque migration appelante obtient sa propre classe)."""
        m1 = self._build()
        m2 = concurrent_index_migration(
            app_label='ventes',
            dependencies=[('ventes', '0001_initial')],
            model_name='devis',
            fields=['created_at'],
            index_name='ventes_devis_created_idx',
        )
        self.assertIsNot(m1, m2)
        self.assertEqual(m2.operations[1].model_name, 'devis')
