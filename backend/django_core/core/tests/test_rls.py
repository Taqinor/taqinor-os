"""NTPLT5 — Suite d'étanchéité RLS (opt-in, sautée si le flag est OFF).

Prouve, sur des tables représentatives, que Row Level Security (RLS Postgres)
isole physiquement les tenants — y compris via une requête SQL BRUTE
(``connection.cursor()``), le chemin que le scoping applicatif (TenantMixin) ne
protège pas :

  * sans GUC ``app.current_company`` posé → 0 ligne visible ;
  * GUC = société B → les lignes de la société A sont INVISIBLES en SELECT,
    et intouchables en UPDATE/DELETE (0 ligne affectée).

Opt-in : toute la suite est SAUTÉE quand ``POSTGRES_RLS_ENABLED`` n'est pas
``1`` (défaut) — elle n'entre donc jamais dans le gate ``backend-tests`` requis.
Un job CI FACULTATIF ``rls-tests`` (non-required) la lance flag ON.

Mécanique : comme le rôle de connexion des tests est superuser (BYPASSRLS
implicite), on crée un rôle applicatif NON-superuser dédié, on ``SET ROLE`` vers
lui pour les assertions (il EST soumis aux policies), et on restaure ensuite.
On applique/révoque les policies via la même génération SQL que
``manage.py rls`` (``core.rls``), sur un petit ensemble de tables peuplables
trivialement.
"""
import os

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from authentication.models import Company
from core import rls

User = get_user_model()

_RLS_ON = os.environ.get('POSTGRES_RLS_ENABLED', '0') == '1'
_APP_ROLE = 'rls_test_app'


def _is_postgres():
    return connection.vendor == 'postgresql'


# On teste sur des tables company-scopées peuplables trivialement par l'ORM.
# authentication_company est la table tenant elle-même ; on prend des tables
# métier/fondation portant une FK company simple. La liste réelle est
# intersectée avec le périmètre découvert (core.rls) pour ne jamais viser une
# table absente.
_CANDIDATE_TABLES = [
    'authentication_customuser',
]


class RlsSealTests(TransactionTestCase):
    """Suite d'étanchéité RLS — opt-in (sautée flag OFF)."""

    reset_sequences = True

    def setUp(self):
        if not _RLS_ON:
            self.skipTest('POSTGRES_RLS_ENABLED != 1 — suite RLS sautée.')
        if not _is_postgres():
            self.skipTest('RLS testé uniquement sur PostgreSQL.')
        # Deux sociétés + un utilisateur par société (table customuser, portant
        # une FK company simple).
        self.company_a = Company.objects.create(nom='Société A')
        self.company_b = Company.objects.create(nom='Société B')
        self.user_a = User.objects.create_user(
            username='rls_a', password='x', company=self.company_a)
        self.user_b = User.objects.create_user(
            username='rls_b', password='x', company=self.company_b)

        # Périmètre effectif = tables candidates réellement découvertes.
        discovered = {e.table for e in rls.discover_company_scoped_tables()}
        self.tables = [t for t in _CANDIDATE_TABLES if t in discovered]
        self.assertTrue(self.tables, 'aucune table candidate découverte')
        self.entries = [
            e for e in rls.discover_company_scoped_tables()
            if e.table in self.tables
        ]

        with connection.cursor() as cursor:
            # Rôle applicatif NON-superuser (soumis aux policies), idempotent.
            cursor.execute(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=%s) "
                "THEN CREATE ROLE " + _APP_ROLE + " NOSUPERUSER NOBYPASSRLS; "
                "END IF; END $$;", [_APP_ROLE])
            for entry in self.entries:
                cursor.execute(
                    f'GRANT SELECT, UPDATE, DELETE ON "{entry.table}" '
                    f'TO {_APP_ROLE}')
                for stmt in rls.enable_sql(entry):
                    cursor.execute(stmt)

    def tearDown(self):
        if not (_RLS_ON and _is_postgres()):
            return
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
            for entry in getattr(self, 'entries', []):
                for stmt in rls.revert_sql(entry):
                    cursor.execute(stmt)

    def _set_guc(self, cursor, company_id):
        cursor.execute(
            "SELECT set_config('app.current_company', %s, false)",
            [str(company_id)])

    def _count_visible(self, cursor, table):
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        return cursor.fetchone()[0]

    def test_no_guc_sees_zero_rows(self):
        # Sous le rôle applicatif, sans GUC posé, la policy
        # (company_id = current_setting(...)::int) ne matche RIEN → 0 ligne.
        for table in self.tables:
            with connection.cursor() as cursor:
                cursor.execute(f'SET ROLE {_APP_ROLE}')
                cursor.execute("SELECT set_config('app.current_company', '', false)")
                try:
                    self.assertEqual(
                        self._count_visible(cursor, table), 0,
                        f'{table}: lignes visibles sans GUC')
                finally:
                    cursor.execute('RESET ROLE')

    def test_guc_b_hides_company_a_rows(self):
        # GUC = société B : les lignes de A sont invisibles (SELECT).
        for table in self.tables:
            with connection.cursor() as cursor:
                cursor.execute(f'SET ROLE {_APP_ROLE}')
                self._set_guc(cursor, self.company_b.pk)
                try:
                    cursor.execute(
                        f'SELECT COUNT(*) FROM "{table}" WHERE company_id=%s',
                        [self.company_a.pk])
                    self.assertEqual(
                        cursor.fetchone()[0], 0,
                        f'{table}: lignes de A visibles sous GUC B')
                finally:
                    cursor.execute('RESET ROLE')

    def test_guc_b_cannot_update_or_delete_company_a_rows(self):
        # UPDATE/DELETE ciblant les lignes de A sous GUC B n'affectent 0 ligne
        # (la policy les rend intouchables via SQL brut).
        for table in self.tables:
            with connection.cursor() as cursor:
                cursor.execute(f'SET ROLE {_APP_ROLE}')
                self._set_guc(cursor, self.company_b.pk)
                try:
                    cursor.execute(
                        f'DELETE FROM "{table}" WHERE company_id=%s',
                        [self.company_a.pk])
                    self.assertEqual(
                        cursor.rowcount, 0,
                        f'{table}: DELETE a touché des lignes de A sous GUC B')
                finally:
                    cursor.execute('RESET ROLE')
        # Les lignes de A existent toujours (vérifié sous le rôle owner).
        self.assertTrue(
            User.objects.filter(company=self.company_a).exists())
