"""YHARD9 — fondation analytique : réplica de lecture optionnel + routeur.

Ces tests n'importent AUCUNE app métier et n'exigent PAS de seconde base
physique. Ils prouvent le point critique de sécurité : sans réplica configuré
(le cas de TOUS les tests), ``analytics_queryset`` est un no-op STRICT — il
renvoie le queryset inchangé, n'ouvre jamais de connexion ``replica`` et laisse
tout sur ``default`` (comportement octet-identique à l'existant).
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, override_settings

from core.analytics_db import (
    ANALYTICS_DB_ALIAS,
    AnalyticsRouter,
    analytics_queryset,
)


class _FakeQS:
    """Faux queryset : n'expose que ``using`` pour tracer l'appel de routage."""

    def __init__(self):
        self.used_alias = None

    def using(self, alias):
        self.used_alias = alias
        return ('routed', alias)


class AnalyticsQuerysetNoReplicaTests(SimpleTestCase):
    """Sans réplica configuré : no-op strict, tout reste sur ``default``."""

    def test_no_replica_alias_configured_by_default(self):
        # Aucun test ne pose DB_REPLICA_HOST → pas d'alias 'replica' du tout.
        self.assertNotIn(ANALYTICS_DB_ALIAS, settings.DATABASES)
        self.assertIn('default', settings.DATABASES)

    def test_helper_returns_queryset_unchanged_and_on_default(self):
        # Queryset réel (modèle framework, pas une app métier) : sans réplica,
        # le helper renvoie le MÊME objet, toujours routé sur 'default'.
        qs = ContentType.objects.all()
        routed = analytics_queryset(qs)
        self.assertIs(routed, qs)
        self.assertEqual(routed.db, 'default')

    def test_helper_never_calls_using_when_unconfigured(self):
        fake = _FakeQS()
        result = analytics_queryset(fake)
        self.assertIs(result, fake)
        self.assertIsNone(fake.used_alias)


class AnalyticsQuerysetWithReplicaTests(SimpleTestCase):
    """Avec un alias ``replica`` présent : le helper route bien dessus."""

    @override_settings(DATABASES={
        **settings.DATABASES,
        'replica': dict(settings.DATABASES['default']),
    })
    def test_helper_routes_to_replica_when_configured(self):
        fake = _FakeQS()
        result = analytics_queryset(fake)
        self.assertEqual(fake.used_alias, ANALYTICS_DB_ALIAS)
        self.assertEqual(result, ('routed', ANALYTICS_DB_ALIAS))


class AnalyticsRouterInstalledTests(SimpleTestCase):
    def test_router_is_installed(self):
        self.assertIn(
            'core.analytics_db.AnalyticsRouter', settings.DATABASE_ROUTERS)


class AnalyticsRouterBehaviourTests(SimpleTestCase):
    """Le réplica est LECTURE SEULE : aucune écriture ni migration dessus."""

    def setUp(self):
        self.router = AnalyticsRouter()

    def test_reads_are_not_globally_hijacked(self):
        # db_for_read → None : le routage analytique reste EXPLICITE.
        self.assertIsNone(self.router.db_for_read(ContentType))

    def test_writes_always_go_to_default(self):
        self.assertEqual(self.router.db_for_write(ContentType), 'default')

    def test_migrations_never_on_replica(self):
        self.assertIs(
            self.router.allow_migrate(ANALYTICS_DB_ALIAS, 'reporting'), False)

    def test_migrations_neutral_on_default(self):
        self.assertIsNone(self.router.allow_migrate('default', 'reporting'))
