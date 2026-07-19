"""AGEN1 — Tests de ``FactTable``/``FactEntry`` (versionnage) + CRUD API +
seed idempotent ``seed_fact_table``.

Prouve : la version est TOUJOURS calculée côté serveur (jamais un
``count()+1``), une seule table publiée par société à la fois (publier
supersède), CRUD company-scopé, et le seed additif-seulement (double-run =
même état ; aucune entrée existante n'est jamais écrasée).
"""
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import CreativeGenerationBatch, FactEntry, FactTable

TABLE_BASE = '/api/django/adsengine/table-faits/'
ENTRY_BASE = '/api/django/adsengine/faits/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FactTableVersioningTests(TestCase):
    """Versionnage au niveau modèle."""

    def setUp(self):
        self.company = Company.objects.create(nom='AGEN Co', slug='agen-co')

    def test_create_draft_starts_at_version_1(self):
        table = FactTable.create_draft(self.company)
        self.assertEqual(table.version, 1)
        self.assertEqual(table.statut, FactTable.Statut.BROUILLON)

    def test_create_draft_never_reuses_a_deleted_version(self):
        # Jamais un count()+1 (CLAUDE.md — ça a collisionné en prod ailleurs).
        t1 = FactTable.create_draft(self.company)  # v1
        t2 = FactTable.create_draft(self.company)  # v2
        self.assertEqual(t1.version, 1)
        self.assertEqual(t2.version, 2)
        t1.delete()  # une seule ligne reste (v2) → count() vaudrait 1
        t3 = FactTable.create_draft(self.company)
        # Plus-haute-utilisée (v2, la ligne restante) + 1 = 3. Un count()+1
        # aurait donné 2 : COLLISION avec t2 (déjà version 2).
        self.assertEqual(t3.version, 3)

    def test_publish_supersedes_prior_published(self):
        t1 = FactTable.create_draft(self.company)
        t1.publish()
        self.assertEqual(FactTable.published_for(self.company).id, t1.id)
        t2 = FactTable.create_draft(self.company)
        t2.publish()
        t1.refresh_from_db()
        self.assertEqual(t1.statut, FactTable.Statut.BROUILLON)
        self.assertEqual(FactTable.published_for(self.company).id, t2.id)

    def test_published_for_returns_none_when_no_table(self):
        self.assertIsNone(FactTable.published_for(self.company))

    def test_only_one_published_table_at_db_level(self):
        # Le garde-fou DB (index partiel) refuse une 2e ligne 'publiee' posée
        # hors du chemin publish() (ex. un accès direct au modèle).
        t1 = FactTable.create_draft(self.company)
        t1.publish()
        t2 = FactTable.objects.create(
            company=self.company, version=99, statut=FactTable.Statut.BROUILLON)
        t2.statut = FactTable.Statut.PUBLIEE
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                t2.save(update_fields=['statut'])

    def test_fact_entry_unique_per_table_and_cle(self):
        table = FactTable.create_draft(self.company)
        FactEntry.objects.create(
            company=self.company, table=table, cle='fda_taux_pct',
            valeur='30', unite='%', source='FDA', verifie_le='2026-07-19')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactEntry.objects.create(
                    company=self.company, table=table, cle='fda_taux_pct',
                    valeur='25', unite='%', source='FDA (doublon)',
                    verifie_le='2026-07-19')


class FactTableApiTests(TestCase):
    """CRUD company-scopé + action ``publish``."""

    def setUp(self):
        self.company_a = Company.objects.create(nom='AGEN A', slug='agen-a')
        self.company_b = Company.objects.create(nom='AGEN B', slug='agen-b')
        self.user_a = make_user(
            self.company_a, 'agen-user-a',
            ['adsengine_view', 'adsengine_manage'])
        self.user_b = make_user(
            self.company_b, 'agen-user-b',
            ['adsengine_view', 'adsengine_manage'])

    def test_post_creates_draft_with_server_computed_version(self):
        api = auth(self.user_a)
        resp = api.post(TABLE_BASE, {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['version'], 1)
        self.assertEqual(resp.data['statut'], FactTable.Statut.BROUILLON)

    def test_client_supplied_version_is_ignored(self):
        api = auth(self.user_a)
        resp = api.post(TABLE_BASE, {'version': 999}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['version'], 1)

    def test_publish_action_activates_table(self):
        api = auth(self.user_a)
        created = api.post(TABLE_BASE, {}, format='json').data
        resp = api.post(f"{TABLE_BASE}{created['id']}/publish/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], FactTable.Statut.PUBLIEE)

    def test_direct_status_patch_is_ignored(self):
        # `statut` en lecture seule : pas de bascule hors de l'action publish.
        api = auth(self.user_a)
        created = api.post(TABLE_BASE, {}, format='json').data
        resp = api.patch(
            f"{TABLE_BASE}{created['id']}/",
            {'statut': FactTable.Statut.PUBLIEE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], FactTable.Statut.BROUILLON)

    def test_list_never_leaks_other_company_tables(self):
        api_a = auth(self.user_a)
        api_b = auth(self.user_b)
        api_a.post(TABLE_BASE, {}, format='json')
        api_b.post(TABLE_BASE, {}, format='json')
        resp = api_a.get(TABLE_BASE)
        results = resp.data['results'] if 'results' in resp.data \
            else resp.data
        self.assertEqual(len(results), 1)

    def test_fact_entry_table_rejects_cross_company_reference(self):
        api_b = auth(self.user_b)
        foreign_table = api_b.post(TABLE_BASE, {}, format='json').data
        api_a = auth(self.user_a)
        resp = api_a.post(
            ENTRY_BASE,
            {'table': foreign_table['id'], 'cle': 'x', 'valeur': '1',
             'verifie_le': '2026-07-19'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_fact_entry_crud_happy_path(self):
        api = auth(self.user_a)
        table = api.post(TABLE_BASE, {}, format='json').data
        resp = api.post(
            ENTRY_BASE,
            {'table': table['id'], 'cle': 'fda_taux_pct', 'valeur': '30',
             'unite': '%', 'source': 'FDA', 'verifie_le': '2026-07-19'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['cle'], 'fda_taux_pct')


class SeedFactTableTests(TestCase):
    """Seed idempotent additif."""

    def setUp(self):
        self.company = Company.objects.create(nom='Seed Co', slug='seed-co')

    def _run(self):
        call_command('seed_fact_table', stdout=StringIO())

    def test_seeds_published_table_and_entries(self):
        self._run()
        table = FactTable.published_for(self.company)
        self.assertIsNotNone(table)
        self.assertGreater(table.entries.count(), 0)
        self.assertTrue(
            table.entries.filter(cle='fda_taux_subvention_pompage_pct')
            .exists())

    def test_fda_fact_value(self):
        self._run()
        table = FactTable.published_for(self.company)
        fda = table.entries.get(cle='fda_taux_subvention_pompage_pct')
        self.assertEqual(fda.valeur, '30')
        self.assertIn('SANS plafond', fda.source)

    def test_double_run_is_idempotent(self):
        self._run()
        first_count = FactEntry.objects.filter(company=self.company).count()
        first_table_count = FactTable.objects.filter(
            company=self.company).count()
        self._run()
        self.assertEqual(
            FactEntry.objects.filter(company=self.company).count(),
            first_count)
        self.assertEqual(
            FactTable.objects.filter(company=self.company).count(),
            first_table_count)

    def test_seed_never_overwrites_existing_entry_value(self):
        self._run()
        table = FactTable.published_for(self.company)
        entry = table.entries.get(cle='fda_taux_subvention_pompage_pct')
        entry.valeur = '99'
        entry.save(update_fields=['valeur'])
        self._run()
        entry.refresh_from_db()
        self.assertEqual(entry.valeur, '99')


class CreativeGenerationBatchAuditFieldsTests(TestCase):
    """AGEN1 — Champs d'audit ajoutés au lot de génération créative."""

    def setUp(self):
        self.company = Company.objects.create(nom='Audit Co', slug='audit-co')

    def test_audit_fields_default_safe(self):
        batch = CreativeGenerationBatch.objects.create(company=self.company)
        self.assertIsNone(batch.fact_table_version)
        self.assertEqual(batch.claim_verdicts, {})
        self.assertFalse(batch.template_quarantined)
