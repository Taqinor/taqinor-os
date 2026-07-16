"""NTPLT1 — Tests du contexte tenant par requête (fondation RLS).

Couvre :
  * défaut OFF : ``set_current_company`` est un no-op (ZÉRO requête SQL) sans
    le flag ``POSTGRES_RLS_ENABLED`` — le budget de requêtes prouve l'absence
    de coût ;
  * OFF : le middleware ne pose aucun GUC (no-op total) ;
  * helper : ``company_id`` None ⇒ no-op même flag ON ;
  * ON + PostgreSQL : le GUC ``app.current_company`` est réellement posé pour
    la transaction, et lisible via ``current_setting`` ;
  * ``rls_enabled`` suit strictement le flag d'environnement.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponse
from django.test import TestCase

from authentication.models import Company
from core import tenant_context

User = get_user_model()


def _env(enabled):
    """Contexte patch de l'environnement RLS (ON/OFF)."""
    return mock.patch.dict(
        'os.environ',
        {'POSTGRES_RLS_ENABLED': '1' if enabled else '0'},
        clear=False,
    )


class RlsFlagTests(TestCase):
    def test_flag_off_by_default(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            # Retire explicitement la variable pour prouver le défaut OFF.
            with mock.patch.dict('os.environ', {'POSTGRES_RLS_ENABLED': ''}):
                self.assertFalse(tenant_context.rls_enabled())

    def test_flag_on(self):
        with _env(True):
            self.assertTrue(tenant_context.rls_enabled())

    def test_flag_non_1_is_off(self):
        with mock.patch.dict('os.environ', {'POSTGRES_RLS_ENABLED': 'true'}):
            self.assertFalse(tenant_context.rls_enabled())


class SetCurrentCompanyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def test_noop_when_flag_off(self):
        # Défaut OFF : aucun GUC posé, ET aucune requête SQL émise (budget = 0).
        with _env(False):
            with self.assertNumQueries(0):
                posed = tenant_context.set_current_company(self.company.pk)
        self.assertFalse(posed)

    def test_noop_when_company_none(self):
        # Même flag ON, une société None est un no-op (jamais de GUC vide ici).
        with _env(True):
            with self.assertNumQueries(0):
                posed = tenant_context.set_current_company(None)
        self.assertFalse(posed)

    def test_sets_guc_when_on_postgres(self):
        if connection.vendor != 'postgresql':
            self.skipTest('GUC réel testé uniquement sur PostgreSQL.')
        with _env(True):
            posed = tenant_context.set_current_company(self.company.pk)
            self.assertTrue(posed)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.current_company', true)")
                value = cursor.fetchone()[0]
            self.assertEqual(value, str(self.company.pk))

    def test_clear_resets_guc_when_on_postgres(self):
        if connection.vendor != 'postgresql':
            self.skipTest('GUC réel testé uniquement sur PostgreSQL.')
        with _env(True):
            tenant_context.set_current_company(self.company.pk)
            tenant_context.clear_current_company()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.current_company', true)")
                value = cursor.fetchone()[0]
            self.assertEqual(value, '')


class TenantContextMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.user = User.objects.create_user(
            username='rls_user', password='x', role_legacy='normal',
            company=cls.company)

    def _mw(self):
        sentinel = HttpResponse('ok')
        return (tenant_context.TenantContextMiddleware(lambda req: sentinel),
                sentinel)

    def test_middleware_noop_when_flag_off(self):
        # Flag OFF : le middleware ne résout pas la société et n'émet aucune
        # requête (chemin par défaut byte-identique à l'absence du middleware).
        mw, sentinel = self._mw()
        request = mock.Mock()
        request.user = self.user
        with _env(False):
            with self.assertNumQueries(0):
                resp = mw(request)
        self.assertIs(resp, sentinel)

    def test_middleware_sets_guc_when_on_postgres(self):
        if connection.vendor != 'postgresql':
            self.skipTest('GUC réel testé uniquement sur PostgreSQL.')
        mw, sentinel = self._mw()
        request = mock.Mock()
        request.user = self.user
        with _env(True):
            resp = mw(request)
            self.assertIs(resp, sentinel)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.current_company', true)")
                value = cursor.fetchone()[0]
            self.assertEqual(value, str(self.company.pk))


class TenantTaskDecoratorTests(TestCase):
    """NTPLT4 — le décorateur tenant_task pose le GUC en tête d'une tâche."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def test_noop_passthrough_when_flag_off(self):
        seen = {}

        @tenant_context.tenant_task
        def task(*, company_id, x):
            seen['x'] = x
            return x * 2

        # Flag OFF : aucune transaction/GUC ajoutés, le corps s'exécute tel quel.
        with _env(False):
            with self.assertNumQueries(0):
                result = task(company_id=self.company.pk, x=21)
        self.assertEqual(result, 42)
        self.assertEqual(seen['x'], 21)

    def test_noop_when_company_id_none(self):
        # Tâche cross-company (company_id None) : jamais de GUC (tourne owner).
        @tenant_context.tenant_task
        def task(*, company_id=None):
            return 'ok'

        with _env(True):
            with self.assertNumQueries(0):
                self.assertEqual(task(company_id=None), 'ok')

    def test_sets_guc_when_on_postgres(self):
        if connection.vendor != 'postgresql':
            self.skipTest('GUC réel testé uniquement sur PostgreSQL.')
        captured = {}

        @tenant_context.tenant_task
        def task(*, company_id):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.current_company', true)")
                captured['value'] = cursor.fetchone()[0]
            return 'done'

        with _env(True):
            self.assertEqual(task(company_id=self.company.pk), 'done')
        # Le GUC était bien posé PENDANT l'exécution du corps.
        self.assertEqual(captured['value'], str(self.company.pk))
