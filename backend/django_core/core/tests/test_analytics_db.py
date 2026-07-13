"""Tests YHARD9 — fondation analytique (réplica de lecture + routeur BI).

Sans réplica configuré (cas par défaut de la CI/tests), tout tourne sur
``default`` : ``replica`` en est un alias octet-identique. On prouve :

  * les settings exposent une base ``replica`` (aliasée sur ``default`` ici) et
    le routeur est bien branché ;
  * ``analytics_queryset(qs)`` marque le queryset pour l'alias ``replica`` ;
  * le routeur n'écrit ni ne migre JAMAIS vers le réplica, et autorise les
    relations default↔replica (mêmes données).

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_analytics_db -v 2
"""
from types import SimpleNamespace

from django.conf import settings
from django.test import TestCase

from core.analytics_db import (
    ANALYTICS_DB_ALIAS,
    AnalyticsRouter,
    analytics_queryset,
)
from core.models import DeletionRecord


def _obj_on(db):
    return SimpleNamespace(_state=SimpleNamespace(db=db))


class SettingsWiringTests(TestCase):
    def test_replica_alias_present(self):
        self.assertIn('replica', settings.DATABASES)

    def test_replica_aliases_default_without_host(self):
        # En CI/tests aucun DB_REPLICA_HOST n'est posé → replica == default
        # (même base, comportement inchangé).
        self.assertEqual(
            settings.DATABASES['replica']['NAME'],
            settings.DATABASES['default']['NAME'])
        self.assertEqual(
            settings.DATABASES['replica']['HOST'],
            settings.DATABASES['default']['HOST'])

    def test_router_installed(self):
        self.assertIn('core.analytics_db.AnalyticsRouter',
                      settings.DATABASE_ROUTERS)


class AnalyticsQuerysetTests(TestCase):
    databases = {'default', 'replica'}

    def test_marks_queryset_for_replica_alias(self):
        qs = analytics_queryset(DeletionRecord.objects.all())
        self.assertEqual(qs.db, ANALYTICS_DB_ALIAS)

    def test_default_queryset_uses_default(self):
        # Sans le helper, un queryset ordinaire reste sur `default` (le routeur
        # ne détourne pas les lectures globalement).
        self.assertEqual(DeletionRecord.objects.all().db, 'default')


class RouterTests(TestCase):
    def setUp(self):
        self.router = AnalyticsRouter()

    def test_reads_not_hijacked(self):
        self.assertIsNone(self.router.db_for_read(DeletionRecord))

    def test_writes_go_to_default(self):
        self.assertEqual(self.router.db_for_write(DeletionRecord), 'default')

    def test_never_migrate_replica(self):
        self.assertIs(self.router.allow_migrate('replica', 'core'), False)

    def test_migrate_default_deferred(self):
        self.assertIsNone(self.router.allow_migrate('default', 'core'))

    def test_relation_within_same_data_allowed(self):
        self.assertTrue(
            self.router.allow_relation(_obj_on('default'), _obj_on('replica')))

    def test_relation_foreign_db_deferred(self):
        self.assertIsNone(
            self.router.allow_relation(_obj_on('default'), _obj_on('other')))
