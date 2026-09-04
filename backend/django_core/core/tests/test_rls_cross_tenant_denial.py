"""AUD422 — DÉNI CROSS-TENANT ASVS 4.2.3 sur les CINQ TABLES ARGENT.

LE GAP RÉELLEMENT PROUVÉ PAR L'AUDIT. Toute la mécanique RLS existait
(``core/tenant_context.py`` NTPLT1, ``core/rls.py`` NTPLT2,
``backend/db/rls_roles.sql`` NTPLT3, la bascule de rôle NTPLT3 dans
``settings/base.py``) et deux suites la testaient — mais
``core/tests/test_rls_command.py`` ne teste que la GÉNÉRATION SQL et
``test_rls_roles.py`` que le CHOIX DU RÔLE. ``core/tests/test_rls.py`` joue bien
le sceau, mais sur UNE table (``authentication_customuser``) qu'il équipe
lui-même : AUCUN test n'exécutait le scénario de déni cross-tenant sur les
tables où vit l'ARGENT, ni sur des policies posées par le SCHÉMA.

CE QUE CETTE SUITE PROUVE, table par table, sur PostgreSQL réel :

  1. les 5 tables argent portent bien ``ENABLE`` + ``FORCE ROW LEVEL
     SECURITY`` et leur policy ``rls_company_<table>`` — donc les migrations
     AUD422 (compta 0126, ventes 0111, facturation 0007) ont réellement mordu ;
  2. sous le rôle applicatif NON-superuser, GUC posé sur la société A, un
     SELECT brut sur les lignes de B renvoie 0 ligne ;
  3. un UPDATE et un DELETE bruts visant les lignes de B n'affectent 0 ligne —
     et les lignes de B existent toujours, vérifié sous le rôle propriétaire ;
  4. LE TEST ROUGE : sans la policy, la même requête FUIT — la protection est
     bien la policy, pas un artefact du montage.

Le filtrage APPLICATIF (``company=`` sur les querysets) reste en place et n'est
JAMAIS retiré : RLS est un filet SOUS lui, jamais un remplacement.

Opt-in comme ``test_rls.py`` : toute la suite est SAUTÉE si
``POSTGRES_RLS_ENABLED`` ≠ 1 (défaut), donc elle n'entre jamais dans le gate
``backend-tests`` requis. Le job CI facultatif ``rls-tests`` la lance flag ON.
"""
import os
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase

from authentication.models import Company
from core import rls
from core.test_utils import WideTeardownTimeoutMixin

_RLS_ON = os.environ.get('POSTGRES_RLS_ENABLED', '0') == '1'

#: Rôle applicatif NON-superuser dédié à cette suite (miroir de `app_rls`).
_APP_ROLE = 'rls_argent_test_app'


def _is_postgres():
    return connection.vendor == 'postgresql'


class RlsArgentCrossTenantDenialTests(WideTeardownTimeoutMixin,
                                      TransactionTestCase):
    """Déni cross-tenant sur les 5 tables argent — opt-in (sauté flag OFF)."""

    reset_sequences = True

    def setUp(self):
        if not _RLS_ON:
            self.skipTest('POSTGRES_RLS_ENABLED != 1 — suite RLS sautée.')
        if not _is_postgres():
            self.skipTest('RLS testé uniquement sur PostgreSQL.')

        self.entries = rls.tables_for_labels(rls.TABLES_ARGENT)
        self.tables = [e.table for e in self.entries]
        self.assertEqual(len(self.entries), 5, self.tables)

        self.company_a = Company.objects.create(
            nom='Argent A', slug='rls-argent-a')
        self.company_b = Company.objects.create(
            nom='Argent B', slug='rls-argent-b')
        self._peupler(self.company_a, 'A')
        self._peupler(self.company_b, 'B')

        with connection.cursor() as cursor:
            cursor.execute(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=%s) "
                "THEN CREATE ROLE " + _APP_ROLE + " NOSUPERUSER NOBYPASSRLS; "
                "END IF; END $$;", [_APP_ROLE])
            for entry in self.entries:
                cursor.execute(
                    f'GRANT SELECT, UPDATE, DELETE ON "{entry.table}" '
                    f'TO {_APP_ROLE}')
                # Idempotent : les policies viennent des migrations AUD422, on
                # les REPOSE pour que la suite reste vraie même sur une base
                # restaurée d'un dump antérieur à ces migrations.
                for stmt in rls.enable_sql(entry):
                    cursor.execute(stmt)

    def tearDown(self):
        if not (_RLS_ON and _is_postgres()):
            return
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
        # Les policies NE SONT PAS révoquées : elles appartiennent désormais au
        # schéma (migrations AUD422), les défaire laisserait la base de test
        # dans un état que la migration dit avoir posé.

    # ── Fixture ────────────────────────────────────────────────────────────
    def _peupler(self, company, marque):
        """Une ligne RÉELLE dans chacune des 5 tables argent, pour ``company``.

        Les modèles sont résolus par CHAÎNE via le registre Django, jamais
        importés : ``core`` est une couche FONDATION (contrat import-linter
        ``core-foundation-is-a-base-layer``) et un ``from apps.compta.models
        import …`` ici ouvrirait, en transitif, une dizaine d'arêtes interdites
        (compta.models → crm.models → crm.services → notifications/ventes…).
        Le code de production d'AUD422 suit exactement la même règle : il ne
        cite que des chaînes (``core.rls.TABLES_ARGENT``).
        """
        from django.apps import apps as registre

        Client = registre.get_model('crm', 'Client')
        Devis = registre.get_model('ventes', 'Devis')
        Facture = registre.get_model('facturation', 'Facture')
        Paiement = registre.get_model('facturation', 'Paiement')
        PlanComptable = registre.get_model('compta', 'PlanComptable')
        CompteComptable = registre.get_model('compta', 'CompteComptable')
        Journal = registre.get_model('compta', 'Journal')
        EcritureComptable = registre.get_model('compta', 'EcritureComptable')
        LigneEcriture = registre.get_model('compta', 'LigneEcriture')

        client = Client.objects.create(
            company=company, nom=f'Client {marque}',
            email=f'client-{marque.lower()}@example.com')
        Devis.objects.create(
            company=company, client=client,
            reference=f'DEV-RLS-{marque}-0001')
        facture = Facture.objects.create(
            company=company, client=client,
            reference=f'FAC-RLS-{marque}-0001')
        Paiement.objects.create(
            company=company, facture=facture, montant=Decimal('100.00'),
            date_paiement=date(2026, 1, 15))

        plan = PlanComptable.objects.create(company=company)
        compte = CompteComptable.objects.create(
            company=company, plan=plan, numero=f'512{marque}',
            intitule=f'Banque {marque}', classe=5)
        journal = Journal.objects.create(
            company=company, code=f'BNK{marque}', libelle=f'Banque {marque}',
            type_journal=Journal.Type.BANQUE)
        ecriture = EcritureComptable.objects.create(
            company=company, journal=journal, date_ecriture=date(2026, 1, 15),
            libelle=f'Encaissement {marque}')
        LigneEcriture.objects.create(
            company=company, ecriture=ecriture, compte=compte,
            debit=Decimal('100.00'), credit=Decimal('0'))

    # ── Outils ─────────────────────────────────────────────────────────────
    def _sous_role_applicatif(self, cursor, company_id):
        cursor.execute(f'SET ROLE {_APP_ROLE}')
        cursor.execute(
            "SELECT set_config('app.current_company', %s, false)",
            [str(company_id)])

    def _compter_owner(self, table, company_id):
        """Compte les lignes SOUS LE RÔLE PROPRIÉTAIRE (superuser : hors RLS)."""
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE company_id = %s',
                [company_id])
            return cursor.fetchone()[0]

    # ── 1. Les migrations ont réellement posé les policies ────────────────
    def test_les_cinq_tables_argent_portent_la_policy(self):
        with connection.cursor() as cursor:
            for entry in self.entries:
                cursor.execute(
                    'SELECT relrowsecurity, relforcerowsecurity '
                    'FROM pg_class WHERE relname = %s', [entry.table])
                ligne = cursor.fetchone()
                self.assertIsNotNone(ligne, entry.table)
                self.assertTrue(ligne[0], f'{entry.table}: RLS non activé')
                self.assertTrue(ligne[1], f'{entry.table}: FORCE absent')
                cursor.execute(
                    'SELECT COUNT(*) FROM pg_policies '
                    'WHERE tablename = %s AND policyname = %s',
                    [entry.table, entry.policy_name])
                self.assertEqual(
                    cursor.fetchone()[0], 1,
                    f'{entry.table}: policy {entry.policy_name} absente')

    # ── 2. La fixture est réelle des deux côtés (non-vacuité) ─────────────
    def test_les_deux_societes_ont_bien_des_lignes_dans_les_cinq_tables(self):
        for table in self.tables:
            with self.subTest(table=table):
                self.assertEqual(self._compter_owner(table, self.company_a.pk), 1)
                self.assertEqual(self._compter_owner(table, self.company_b.pk), 1)

    # ── 3. SELECT cross-société : 0 ligne ─────────────────────────────────
    def test_select_cross_societe_ne_voit_rien(self):
        for table in self.tables:
            with self.subTest(table=table):
                with connection.cursor() as cursor:
                    self._sous_role_applicatif(cursor, self.company_a.pk)
                    try:
                        cursor.execute(
                            f'SELECT COUNT(*) FROM "{table}" '
                            'WHERE company_id = %s', [self.company_b.pk])
                        self.assertEqual(
                            cursor.fetchone()[0], 0,
                            f'{table}: les lignes de B sont VISIBLES sous GUC A')
                        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                        self.assertEqual(
                            cursor.fetchone()[0], 1,
                            f'{table}: la société A doit voir SA ligne, une seule')
                    finally:
                        cursor.execute('RESET ROLE')

    # ── 4. UPDATE cross-société : 0 ligne affectée ────────────────────────
    def test_update_cross_societe_naffecte_aucune_ligne(self):
        for entry in self.entries:
            with self.subTest(table=entry.table):
                with connection.cursor() as cursor:
                    self._sous_role_applicatif(cursor, self.company_a.pk)
                    try:
                        cursor.execute(
                            f'UPDATE "{entry.table}" SET company_id = company_id '
                            'WHERE company_id = %s', [self.company_b.pk])
                        self.assertEqual(
                            cursor.rowcount, 0,
                            f'{entry.table}: UPDATE a touché des lignes de B')
                    finally:
                        cursor.execute('RESET ROLE')

    # ── 5. DELETE cross-société : 0 ligne, et B est intacte ───────────────
    def test_delete_cross_societe_naffecte_aucune_ligne(self):
        for table in self.tables:
            with self.subTest(table=table):
                with connection.cursor() as cursor:
                    self._sous_role_applicatif(cursor, self.company_a.pk)
                    try:
                        cursor.execute(
                            f'DELETE FROM "{table}" WHERE company_id = %s',
                            [self.company_b.pk])
                        self.assertEqual(
                            cursor.rowcount, 0,
                            f'{table}: DELETE a touché des lignes de B')
                    finally:
                        cursor.execute('RESET ROLE')
                self.assertEqual(
                    self._compter_owner(table, self.company_b.pk), 1,
                    f'{table}: une ligne de B a disparu')

    # ── 6. LE TEST ROUGE — sans policy, la fuite est réelle ───────────────
    def test_sans_policy_la_fuite_cross_societe_est_reelle(self):
        """Prouve que c'est bien la POLICY qui scelle, pas le montage.

        On retire la policy d'UNE table (``ventes_devis``), on constate la
        fuite sous le même rôle et le même GUC, puis on la repose.
        """
        entry = next(e for e in self.entries if e.table == 'ventes_devis')
        with connection.cursor() as cursor:
            for stmt in rls.revert_sql(entry):
                cursor.execute(stmt)
        try:
            with connection.cursor() as cursor:
                self._sous_role_applicatif(cursor, self.company_a.pk)
                try:
                    cursor.execute(
                        f'SELECT COUNT(*) FROM "{entry.table}" '
                        'WHERE company_id = %s', [self.company_b.pk])
                    self.assertEqual(
                        cursor.fetchone()[0], 1,
                        'sans policy, les lignes de B devraient être visibles '
                        '— si elles ne le sont pas, ce test ne prouve rien.')
                finally:
                    cursor.execute('RESET ROLE')
        finally:
            with connection.cursor() as cursor:
                for stmt in rls.enable_sql(entry):
                    cursor.execute(stmt)
        # Policy reposée : le sceau est de nouveau en place.
        with connection.cursor() as cursor:
            self._sous_role_applicatif(cursor, self.company_a.pk)
            try:
                cursor.execute(
                    f'SELECT COUNT(*) FROM "{entry.table}" '
                    'WHERE company_id = %s', [self.company_b.pk])
                self.assertEqual(cursor.fetchone()[0], 0)
            finally:
                cursor.execute('RESET ROLE')
