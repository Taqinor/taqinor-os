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

    def test_index_class_gin_pour_le_plein_texte(self):
        """NTPLT32 — même pose concurrente pour un index GIN (search_vector) ;
        sans ``index_class``, l'index reste un B-tree (inchangé)."""
        from django.contrib.postgres.indexes import GinIndex
        from django.db import models
        gin = concurrent_index_migration(
            app_label='crm', dependencies=[('crm', '0158_ntplt32_search_vector')],
            model_name='lead', fields=['search_vector'],
            index_name='crm_lead_fts_gin', index_class=GinIndex)
        self.assertFalse(gin.atomic)
        self.assertIsInstance(gin.operations[0].index, GinIndex)
        self.assertEqual(gin.operations[0].index.fields, ['search_vector'])
        self.assertIs(type(self._build().operations[0].index), models.Index)
        # NTPLT33 — index PARTIEL des lignes non indexées (même pose).
        from django.db.models import Q
        from core.champs_plateforme import index_fts_attente
        partiel = concurrent_index_migration(
            app_label='crm', dependencies=[('crm', '0161_ntplt34_trgm_lead_client')],
            model_name='lead', fields=['id'], index_name='crm_lead_fts_null',
            condition=Q(search_vector__isnull=True)).operations[0].index
        self.assertEqual(partiel, index_fts_attente('crm_lead_fts_null'))
        self.assertIsNone(self._build().operations[0].index.condition)


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


class TrigramIndexMigrationTests(SimpleTestCase):
    """NTPLT34 — index trigramme : jamais d'échec de ``migrate``, index posé
    concurremment seulement si pg_trgm est là, lock_timeout toujours remis."""

    CIBLES = [('lead', 'nom', 'crm_lead_nom_trgm')]

    class _Editeur(_FauxSchemaEditor):
        def __init__(self, refuse_extension=False, index_casse=False):
            super().__init__()
            self.refuse_extension, self.index_casse = refuse_extension, index_casse
            self.index_poses = []

        def execute(self, sql, params=()):
            if self.refuse_extension and 'EXTENSION' in str(sql):
                raise RuntimeError('permission denied to create extension')
            super().execute(sql, params)

        def add_index(self, model, index, concurrently=False):
            if self.index_casse:
                raise RuntimeError('verrou tenu')
            self.index_poses.append((index.name, list(index.opclasses), concurrently))

    def _jouer(self, editeur, presente=True, existe=False):
        from core import migrations_utils as mu
        apps = mock.Mock()
        apps.get_model.return_value._meta.db_table = 'crm_lead'
        migration = mu.trigram_index_migration(
            'crm', [('crm', '0160_ntplt32_client_fts_gin')], self.CIBLES)
        self.assertFalse(migration.atomic)
        with mock.patch.object(mu, '_extension_trgm_presente', return_value=presente), \
                mock.patch.object(mu, '_index_existe', return_value=existe):
            migration.operations[0].code(apps, editeur)

    def test_pose_concurrente_avec_opclass_et_lock_timeout_remis(self):
        editeur = self._Editeur()
        self._jouer(editeur)
        self.assertEqual(editeur.index_poses,
                         [('crm_lead_nom_trgm', ['gin_trgm_ops'], True)])
        self.assertEqual(editeur.sql[-1], 'RESET lock_timeout;')

    def test_extension_refusee_ou_absente_ne_fait_jamais_echouer(self):
        editeur = self._Editeur(refuse_extension=True)
        self._jouer(editeur, presente=False)
        self.assertEqual(editeur.index_poses, [])
        casse = self._Editeur(index_casse=True)
        self._jouer(casse)  # l'échec de l'index est journalisé, jamais levé
        self.assertEqual(casse.sql[-1], 'RESET lock_timeout;')

    def test_index_existant_ignore(self):
        editeur = self._Editeur()
        self._jouer(editeur, existe=True)
        self.assertEqual(editeur.index_poses, [])
