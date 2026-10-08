"""ADEP30 (C-ADEP-001) — le GUC tenant TIENT pendant toute la requête HTTP.

LE DÉFAUT. ``TenantContextMiddleware`` posait ``set_config('app.current_company',
…, true)`` — transaction-scopé (SCA14), donc effacé à la fin de SA transaction.
``ATOMIC_REQUESTS`` n'est pas activé : en autocommit, chaque statement ORM de la
vue tournait dans sa propre transaction implicite, SANS GUC. Sous un rôle
NOBYPASSRLS : 0 ligne visible, INSERT refusé (« new row violates row-level
security policy »).

POURQUOI ``TransactionTestCase`` EST OBLIGATOIRE. Un ``TestCase`` enveloppe tout
le test dans une transaction : le ``SET LOCAL`` y survit jusqu'à la fin, ce qui
MASQUE le défaut (c'est pourquoi les tests RLS existants étaient verts).

LE MONTAGE (aucun mock) : une table sonde équipée par ``core.rls.enable_sql``
(ENABLE + FORCE RLS + la vraie policy), un rôle NOSUPERUSER NOBYPASSRLS créé ici
et ``SET ROLE`` sur la connexion, des requêtes par le client de test à travers
la VRAIE pile de middlewares (dont ``TenantContextMiddleware``), flag
``POSTGRES_RLS_ENABLED=1`` posé le temps du test.

Test-du-test : retirer l'``execute_wrapper`` du middleware ⇒
``test_get_lit_sa_societe`` échoue (0 ligne) ; poser le GUC en session
(``is_local=false``) sans remise à zéro ⇒ ``test_aucune_fuite_entre_requetes``
échoue (connexion réutilisée).
"""
import os
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import JsonResponse
from django.test import TransactionTestCase, override_settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from authentication.models import Company
from core import checks, rls
from core.test_utils import WideTeardownTimeoutMixin

TABLE = 'adep30_sonde'
#: Rôle applicatif propre à CE process (les rôles sont globaux au cluster :
#: ``--parallel`` ne doit pas faire collisionner deux workers).
ROLE = f'adep30_app_{os.getpid()}'
LABEL_INSERT = 'adep30-insert'


# ── Vues de sonde (URLconf de ce module) ────────────────────────────────────
def _lire(request):
    with connection.cursor() as cursor:
        # Un premier statement sans rapport : le GUC doit tenir AUSSI pour les
        # statements suivants (le défaut le perdait dès le premier commit).
        cursor.execute('SELECT 1')
        cursor.execute(f'SELECT COUNT(*) FROM {TABLE}')
        total = cursor.fetchone()[0]
    return JsonResponse({'total': total})


@csrf_exempt
def _inserer(request):
    company_id = getattr(getattr(request.user, 'company', None), 'pk', None)
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.execute(
            f'INSERT INTO {TABLE} (company_id, label) VALUES (%s, %s)',
            [company_id, LABEL_INSERT])
    return JsonResponse({'ok': True}, status=201)


urlpatterns = [
    path('adep30/lire/', _lire),
    path('adep30/inserer/', _inserer),
]


@override_settings(ROOT_URLCONF=__name__)
class RlsGucRequeteTests(WideTeardownTimeoutMixin, TransactionTestCase):
    """Le GUC tient sur toute la requête HTTP, sous un rôle NOBYPASSRLS."""

    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('RLS testé uniquement sur PostgreSQL.')
        patcher = mock.patch.dict(os.environ, {'POSTGRES_RLS_ENABLED': '1'})
        patcher.start()
        self.addCleanup(patcher.stop)

        User = get_user_model()
        self.co1 = Company.objects.create(nom='ADEP30 Un', slug='adep30-un')
        self.co2 = Company.objects.create(nom='ADEP30 Deux', slug='adep30-deux')
        self.user1 = User.objects.create_user(
            username='adep30_u1', password='x', role_legacy='normal',
            company=self.co1)
        self.user2 = User.objects.create_user(
            username='adep30_u2', password='x', role_legacy='normal',
            company=self.co2)

        entree = rls.RlsTable(
            label='adep30.Sonde', table=TABLE, company_column='company_id')
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS {TABLE}')
            cursor.execute(
                f'CREATE TABLE {TABLE} (id serial PRIMARY KEY, '
                'company_id integer, label text)')
            cursor.execute(
                f'INSERT INTO {TABLE} (company_id, label) VALUES '
                '(%s, %s), (%s, %s), (%s, %s)',
                [self.co1.pk, 'a', self.co1.pk, 'b', self.co2.pk, 'c'])
            for stmt in rls.enable_sql(entree):
                cursor.execute(stmt)
            cursor.execute(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=%s) "
                "THEN CREATE ROLE " + ROLE + " NOSUPERUSER NOBYPASSRLS; "
                "END IF; END $$;", [ROLE])
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {ROLE}')
            # Toute la pile de middlewares (session, utilisateur, modules,
            # politique réseau…) lit sous ce rôle : DML sur tout le schéma,
            # AUCUN DDL — exactement le profil de backend/db/rls_roles.sql.
            cursor.execute(
                'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA '
                f'public TO {ROLE}')
            cursor.execute(
                f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE}')

    def tearDown(self):
        if connection.vendor != 'postgresql':
            return
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
            cursor.execute(f'DROP TABLE IF EXISTS {TABLE}')
            cursor.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", [ROLE])
            if cursor.fetchone():
                cursor.execute(f'DROP OWNED BY {ROLE}')
                cursor.execute(f'DROP ROLE {ROLE}')

    # ── Outils ─────────────────────────────────────────────────────────────
    def _sous_role(self):
        with connection.cursor() as cursor:
            cursor.execute(f'SET ROLE {ROLE}')

    def _owner(self):
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')

    def _total(self):
        response = self.client.get('/adep30/lire/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['total']

    # ── Tests ──────────────────────────────────────────────────────────────
    def test_get_lit_sa_societe(self):
        self.client.force_login(self.user1)
        self._sous_role()
        try:
            self.assertEqual(
                self._total(), 2,
                'sous un rôle NOBYPASSRLS, la société 1 doit lire SES 2 lignes '
                '— le GUC ne tient pas pendant la requête HTTP')
        finally:
            self._owner()

    def test_insert_passe(self):
        self.client.force_login(self.user1)
        self._sous_role()
        try:
            response = self.client.post('/adep30/inserer/')
            self.assertEqual(response.status_code, 201, response.content)
        finally:
            self._owner()
        # CLAUSE PERSISTANCE : relue par une NOUVELLE connexion (owner).
        connection.close()
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT company_id FROM {TABLE} WHERE label = %s',
                [LABEL_INSERT])
            lignes = cursor.fetchall()
        self.assertEqual(lignes, [(self.co1.pk,)])

    def test_aucune_fuite_entre_requetes(self):
        self.client.force_login(self.user1)
        self._sous_role()
        try:
            self.assertEqual(self._total(), 2)
        finally:
            self._owner()

        self.client.logout()
        self.client.force_login(self.user2)
        self._sous_role()
        try:
            self.assertEqual(
                self._total(), 1,
                'la société 2 ne doit voir que SA ligne — même connexion '
                'réutilisée après la requête de la société 1')
        finally:
            self._owner()

        self.client.logout()
        self._sous_role()
        try:
            self.assertEqual(
                self._total(), 0, 'une requête anonyme ne voit aucune ligne')
        finally:
            self._owner()

    def test_check_refuse_flag_sans_garantie(self):
        def ids(messages):
            return [m.id for m in messages]

        with override_settings(TESTING=False):
            # Rôle runtime NOBYPASSRLS + middleware présent : silencieux.
            with mock.patch.dict(os.environ, {'DB_APP_USER': ROLE}):
                self.assertNotIn(checks.ID_RLS, ids(checks.verifier_garantie_rls()))

            # Rôle runtime qui contourne RLS (le rôle propriétaire de la suite).
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT current_user, rolsuper, rolbypassrls FROM pg_roles '
                    'WHERE rolname = current_user')
                owner, est_super, contourne = cursor.fetchone()
            if est_super or contourne:
                with mock.patch.dict(os.environ, {'DB_APP_USER': owner}):
                    self.assertIn(
                        checks.ID_RLS, ids(checks.verifier_garantie_rls()))

            # Middleware retiré : la pose du GUC ne tient pas.
            sans_mw = [m for m in settings.MIDDLEWARE
                       if m != checks.MIDDLEWARE_TENANT]
            with override_settings(MIDDLEWARE=sans_mw), \
                    mock.patch.dict(os.environ, {'DB_APP_USER': ROLE}):
                self.assertIn(checks.ID_RLS, ids(checks.verifier_garantie_rls()))

        # Flag OFF : no-op total.
        with mock.patch.dict(os.environ, {'POSTGRES_RLS_ENABLED': '0'}):
            self.assertEqual(checks.verifier_garantie_rls(), [])
