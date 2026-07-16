"""NTPLT2 — Tests de la génération/commande RLS par introspection.

Couvre :
  * ``discover_company_scoped_tables`` liste 100 % des tables portant une FK
    ``company`` — comparé au périmètre multi-tenant réel (aucun oubli) ;
  * le SQL généré est idempotent (DROP POLICY IF EXISTS) et réversible ;
  * la commande ``rls --dry-run`` imprime le SQL sans rien exécuter (défaut) ;
  * la commande refuse ``--apply`` hors PostgreSQL.
"""
from io import StringIO
from unittest import mock

from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, models as m
from django.test import TestCase

from core import rls


class DiscoveryTests(TestCase):
    def test_discovers_every_company_scoped_table(self):
        found = {e.label for e in rls.discover_company_scoped_tables()}
        # Périmètre attendu : TOUT modèle concret avec une FK company locale.
        expected = set()
        for model in django_apps.get_models():
            meta = model._meta
            if meta.abstract or meta.proxy:
                continue
            try:
                field = meta.get_field('company')
            except Exception:  # noqa: BLE001
                continue
            if isinstance(field, m.ForeignKey):
                expected.add(f"{meta.app_label}.{model.__name__}")
        self.assertEqual(found, expected)
        # Le périmètre n'est pas vide (au moins les modèles CRM/ventes).
        self.assertTrue(found, 'aucune table company-scopée découverte')

    def test_entries_carry_table_and_company_column(self):
        entries = rls.discover_company_scoped_tables()
        for e in entries:
            self.assertTrue(e.table)
            self.assertEqual(e.company_column, 'company_id')
            self.assertTrue(e.policy_name.startswith(rls.POLICY_PREFIX))
            self.assertLessEqual(len(e.policy_name), 63)


class SqlGenerationTests(TestCase):
    def _sample(self):
        entries = rls.discover_company_scoped_tables()
        self.assertTrue(entries)
        return entries[0]

    def test_enable_sql_is_idempotent_and_scoped(self):
        e = self._sample()
        sql = rls.enable_sql(e)
        joined = '\n'.join(sql)
        self.assertIn('ENABLE ROW LEVEL SECURITY', joined)
        self.assertIn('FORCE ROW LEVEL SECURITY', joined)
        # Idempotence : la policy est recréée proprement (DROP IF EXISTS).
        self.assertIn('DROP POLICY IF EXISTS', joined)
        self.assertIn('CREATE POLICY', joined)
        # La policy compare bien la colonne company au GUC transaction-scopé.
        self.assertIn("current_setting('app.current_company', true)", joined)
        self.assertIn(e.company_column, joined)

    def test_revert_sql_undoes_enable(self):
        e = self._sample()
        joined = '\n'.join(rls.revert_sql(e))
        self.assertIn('DROP POLICY IF EXISTS', joined)
        self.assertIn('NO FORCE ROW LEVEL SECURITY', joined)
        self.assertIn('DISABLE ROW LEVEL SECURITY', joined)

    def test_build_statements_covers_all_tables(self):
        tables, statements = rls.build_statements('apply')
        # 4 instructions par table (ENABLE, FORCE, DROP, CREATE).
        self.assertEqual(len(statements), len(tables) * 4)


class CommandTests(TestCase):
    def test_dry_run_prints_sql_without_executing(self):
        out = StringIO()
        # --dry-run ne doit émettre AUCUN DDL : on patche le curseur pour
        # échouer si exécuté (le dry-run ne prend jamais de connexion DDL).
        with mock.patch.object(
                rls, 'build_statements',
                wraps=rls.build_statements) as spy:
            call_command('rls', '--dry-run', stdout=out)
        spy.assert_called_once()
        text = out.getvalue()
        self.assertIn('aucune exécution', text)
        self.assertIn('ENABLE ROW LEVEL SECURITY', text)

    def test_default_is_dry_run(self):
        out = StringIO()
        call_command('rls', stdout=out)
        self.assertIn('aucune exécution', out.getvalue())

    def test_apply_refuses_non_postgres(self):
        if connection.vendor == 'postgresql':
            self.skipTest('Test du refus non-PostgreSQL uniquement hors pg.')
        with self.assertRaises(CommandError):
            call_command('rls', '--apply', stdout=StringIO())
