"""LW28 — ``LeadActivity.pinned`` : la note épinglée.

Couvre : POST epingler/desepingler (permission crm_modifier, idempotents,
company-scopés — un ``activite_id`` d'un autre lead ou d'une autre société
renvoie 404, jamais une fuite), l'exposition de ``pinned`` sur
``LeadActivitySerializer``, le tri ``historique/`` en épingle-d'abord, et une
vérification de construction que la migration LW28 reste purement additive
(donc révertable via ``migrate crm <n-1>``, jamais exécutée ici — pas de DB
migrate/rollback dans un TestCase)."""
import importlib

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

User = get_user_model()


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChatterPinTests(TestCase):
    def setUp(self):
        self.company = _company('lw28-co', 'LW28 Co')
        self.user = User.objects.create_user(
            username='lw28_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='LW28 Lead')
        self.old_note = LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.user,
            kind=LeadActivity.Kind.NOTE, body='Ancienne note')
        self.recent_note = LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.user,
            kind=LeadActivity.Kind.NOTE, body='Note récente')
        self.api = _api(self.user)

    def _epingler_url(self, activite_id):
        return (f'/api/django/crm/leads/{self.lead.id}/activites/'
                f'{activite_id}/epingler/')

    def _desepingler_url(self, activite_id):
        return (f'/api/django/crm/leads/{self.lead.id}/activites/'
                f'{activite_id}/desepingler/')

    def _historique_url(self):
        return f'/api/django/crm/leads/{self.lead.id}/historique/'

    # ── Épingler / désépingler ───────────────────────────────────────────────

    def test_epingler_marks_pinned_true(self):
        resp = self.api.post(self._epingler_url(self.old_note.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['pinned'])
        self.old_note.refresh_from_db()
        self.assertTrue(self.old_note.pinned)

    def test_epingler_is_idempotent(self):
        self.api.post(self._epingler_url(self.old_note.id))
        resp = self.api.post(self._epingler_url(self.old_note.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['pinned'])

    def test_desepingler_reverts_pinned(self):
        self.api.post(self._epingler_url(self.old_note.id))
        resp = self.api.post(self._desepingler_url(self.old_note.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['pinned'])
        self.old_note.refresh_from_db()
        self.assertFalse(self.old_note.pinned)

    def test_historique_orders_pinned_first(self):
        # L'ancienne note épinglée doit remonter DEVANT la note récente
        # non-épinglée, malgré le tri par défaut -created_at.
        self.api.post(self._epingler_url(self.old_note.id))
        resp = self.api.get(self._historique_url())
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.data]
        self.assertEqual(ids[0], self.old_note.id)
        self.assertTrue(resp.data[0]['pinned'])

    # ── Garde 404 hors-tenant / hors-lead ────────────────────────────────────

    def test_epingler_cross_company_404(self):
        other_company = _company('lw28-co-b', 'LW28 Co B')
        other_user = User.objects.create_user(
            username='lw28_other', password='x', role_legacy='responsable',
            company=other_company)
        other_api = _api(other_user)
        resp = other_api.post(self._epingler_url(self.old_note.id))
        # Le lead lui-même est hors société → get_object() 404 en amont.
        self.assertEqual(resp.status_code, 404)
        self.old_note.refresh_from_db()
        self.assertFalse(self.old_note.pinned)

    def test_epingler_activite_of_another_lead_404(self):
        # Même société, mais l'activité appartient à un AUTRE lead.
        other_lead = Lead.objects.create(company=self.company, nom='Autre Lead')
        other_note = LeadActivity.objects.create(
            company=self.company, lead=other_lead, user=self.user,
            kind=LeadActivity.Kind.NOTE, body='Note autre lead')
        resp = self.api.post(self._epingler_url(other_note.id))
        self.assertEqual(resp.status_code, 404)

    def test_epingler_unknown_activite_id_404(self):
        resp = self.api.post(self._epingler_url(999999))
        self.assertEqual(resp.status_code, 404)

    # ── Permission crm_modifier ──────────────────────────────────────────────

    def test_epingler_requires_authentication(self):
        anon = APIClient()
        resp = anon.post(self._epingler_url(self.old_note.id))
        self.assertIn(resp.status_code, (401, 403))

    # ── Sanité de construction de la migration LW28 (additive, révertable) ──

    def test_lw28_migration_is_additive_and_reversible_by_construction(self):
        """La migration LW28 ne fait qu'AJOUTER un champ ``pinned`` — pas de
        ``RunPython`` ni de perte de données possible : Django génère le
        ``RemoveField`` inverse automatiquement (revert propre via ``manage.py
        migrate crm 0063``). Cette vérification statique n'exécute AUCUNE
        migration réelle (pas de DB migrate ici) — l'apply/rollback complet
        est validé par l'orchestrateur (gate CI/local)."""
        mod = importlib.import_module(
            'apps.crm.migrations.0064_lw28_leadactivity_pinned')
        migration = mod.Migration
        expected_dep = (
            'crm',
            '0063_forecastentry_plancompte_playbook_playbooketape_and_more',
        )
        self.assertEqual(migration.dependencies, [expected_dep])
        self.assertEqual(len(migration.operations), 1)
        op = migration.operations[0]
        self.assertIsInstance(op, migrations.AddField)
        self.assertEqual(op.model_name, 'leadactivity')
        self.assertEqual(op.name, 'pinned')
        # Défaut explicite (False) → applicable sur des lignes existantes
        # sans RunPython/backfill, donc trivialement réversible.
        self.assertTrue(op.field.has_default())
        self.assertIs(op.field.default, False)
