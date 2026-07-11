"""NTPLT3 — Tests du choix de rôle DB (owner vs applicatif non-BYPASSRLS).

Couvre :
  * ``_running_owner_command`` reconnaît migrate/dump/seed/test comme des
    commandes OWNER (elles doivent voir tous les tenants — critère : migrate et
    core.dump_database passent flag ON) ;
  * un process runtime (gunicorn/celery, pas de manage.py) n'est PAS une
    commande owner → il prendra le rôle applicatif ;
  * le script de provisionnement backend/db/rls_roles.sql pose bien un rôle
    applicatif NON-BYPASSRLS et garde l'owner en BYPASSRLS.
"""
from pathlib import Path
from unittest import mock

from django.test import TestCase

from erp_agentique.settings import base as settings_base


class OwnerCommandDetectionTests(TestCase):
    def _argv(self, *args):
        return mock.patch.object(settings_base.sys, 'argv', list(args))

    def test_migrate_is_owner_command(self):
        with self._argv('manage.py', 'migrate'):
            self.assertTrue(settings_base._running_owner_command())

    def test_dump_database_is_owner_command(self):
        with self._argv('manage.py', 'dump_database'):
            self.assertTrue(settings_base._running_owner_command())

    def test_rls_command_itself_is_owner(self):
        # La commande rls pose le DDL/policies → doit tourner sous l'owner.
        with self._argv('manage.py', 'rls', '--apply'):
            self.assertTrue(settings_base._running_owner_command())

    def test_seed_commands_are_owner(self):
        with self._argv('manage.py', 'seed_catalogue'):
            self.assertTrue(settings_base._running_owner_command())

    def test_test_command_is_owner(self):
        with self._argv('manage.py', 'test', 'core'):
            self.assertTrue(settings_base._running_owner_command())

    def test_runtime_gunicorn_is_not_owner(self):
        # gunicorn : argv[0] n'est pas manage.py → runtime → PAS owner (le
        # service prendra le rôle applicatif quand le flag est ON).
        with self._argv('gunicorn', 'erp_agentique.wsgi:application'):
            self.assertFalse(settings_base._running_owner_command())

    def test_celery_is_not_owner(self):
        with self._argv('celery', '-A', 'erp_agentique', 'worker'):
            self.assertFalse(settings_base._running_owner_command())

    def test_runserver_is_not_owner_command(self):
        # runserver EST un runtime (sert des requêtes) → rôle applicatif.
        with self._argv('manage.py', 'runserver'):
            self.assertFalse(settings_base._running_owner_command())


class ProvisioningScriptTests(TestCase):
    def _sql(self):
        # backend/django_core/core/tests/ → remonter à backend/db/rls_roles.sql
        root = Path(settings_base.__file__).resolve()
        # .../backend/django_core/erp_agentique/settings/base.py
        backend = root.parents[3]  # .../backend
        path = backend / 'db' / 'rls_roles.sql'
        self.assertTrue(path.exists(), f'script introuvable : {path}')
        return path.read_text(encoding='utf-8')

    def test_creates_non_bypassrls_app_role(self):
        sql = self._sql()
        self.assertIn('app_rls', sql)
        self.assertIn('NOBYPASSRLS', sql)

    def test_owner_keeps_bypassrls_for_migrations_dumps(self):
        sql = self._sql()
        self.assertIn('BYPASSRLS', sql)
        # L'app role reçoit du DML mais AUCUN DDL (les migrations = owner).
        self.assertIn('GRANT SELECT, INSERT, UPDATE, DELETE', sql)

    def test_documents_revert(self):
        sql = self._sql()
        self.assertIn('DROP ROLE app_rls', sql)
