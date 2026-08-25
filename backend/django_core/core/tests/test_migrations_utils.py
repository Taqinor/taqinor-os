"""Tests YOPSB6 — helper d'index concurrent + lock_timeout (migrations_utils).

Couvre : la classe produite est bien ``atomic = False``, elle porte UNE seule
opération (l'index concurrent, qui pose et REMET lui-même le ``lock_timeout``),
``dependencies`` est posé tel que fourni, et l'index/modèle/nom sont corrects.

Revue critique du 25/08/2026, finding #11 — le ``lock_timeout`` était posé par
un ``RunSQL`` séparé et n'était JAMAIS remis : en ``atomic=False`` (autocommit)
le réglage vaut pour toute la SESSION, donc pour la suite du plan de migration.
Les tests d'exécution ci-dessous épinglent le ``RESET``, y compris quand la
construction de l'index ÉCHOUE.

Pas de PostgreSQL réel : la construction de l'index est simulée, et
l'« éditeur de schéma » n'est qu'un enregistreur de SQL.
"""
from unittest import mock

from django.contrib.postgres.operations import AddIndexConcurrently
from django.test import SimpleTestCase

from core.migrations_utils import (
    LOCK_TIMEOUT_INDEX,
    concurrent_index_migration,
)


class _FausseConnexion:
    def __init__(self, vendor='postgresql'):
        self.vendor = vendor


class _FauxSchemaEditor:
    """Enregistre le SQL émis — aucune base derrière."""

    def __init__(self, vendor='postgresql'):
        self.connection = _FausseConnexion(vendor)
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append(str(sql))


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

    def test_une_seule_operation_lindex_concurrent(self):
        """Le ``lock_timeout`` n'est plus une opération séparée : il vit DANS
        l'opération d'index, seule façon de garantir sa remise (finding #11)."""
        ops = self._build().operations
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], AddIndexConcurrently)

    def test_index_targets_correct_model_and_fields(self):
        add_index_op = self._build().operations[0]
        self.assertEqual(add_index_op.model_name, 'lead')
        self.assertEqual(add_index_op.index.fields, ['statut'])
        self.assertEqual(add_index_op.index.name, 'crm_lead_statut_idx')

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
        self.assertEqual(m2.operations[0].model_name, 'devis')


class LockTimeoutRemisTests(SimpleTestCase):
    """Finding #11 — le réglage ne fuit plus sur la suite du plan."""

    def _operation(self):
        return concurrent_index_migration(
            app_label='crm', dependencies=[('crm', '0030_pointcontact')],
            model_name='lead', fields=['statut'],
            index_name='crm_lead_statut_idx').operations[0]

    def test_pose_puis_remet_le_lock_timeout(self):
        editeur = _FauxSchemaEditor()
        with mock.patch.object(AddIndexConcurrently, 'database_forwards'):
            self._operation().database_forwards('crm', editeur, None, None)
        self.assertEqual(editeur.sql, [
            f"SET lock_timeout = '{LOCK_TIMEOUT_INDEX}';",
            'RESET lock_timeout;',
        ])

    def test_remis_meme_si_la_construction_echoue(self):
        """C'EST LE CAS QUI COMPTE : un index qui échoue ne doit pas laisser la
        session à 3 s pour les migrations suivantes."""
        editeur = _FauxSchemaEditor()
        with mock.patch.object(AddIndexConcurrently, 'database_forwards',
                               side_effect=RuntimeError('verrou tenu')):
            with self.assertRaises(RuntimeError):
                self._operation().database_forwards(
                    'crm', editeur, None, None)
        self.assertEqual(editeur.sql[-1], 'RESET lock_timeout;')

    def test_aucun_sql_non_portable_hors_postgres(self):
        editeur = _FauxSchemaEditor(vendor='sqlite')
        with mock.patch.object(AddIndexConcurrently, 'database_forwards'):
            self._operation().database_forwards('crm', editeur, None, None)
        self.assertEqual(editeur.sql, [])

    def test_un_reset_qui_echoue_ne_masque_pas_lerreur_dorigine(self):
        class _EditeurCasse(_FauxSchemaEditor):
            def execute(self, sql, params=()):
                if 'RESET' in str(sql):
                    raise RuntimeError('connexion perdue')
                super().execute(sql, params)

        with mock.patch.object(AddIndexConcurrently, 'database_forwards',
                               side_effect=ValueError('cause reelle')):
            with self.assertRaises(ValueError):
                self._operation().database_forwards(
                    'crm', _EditeurCasse(), None, None)
