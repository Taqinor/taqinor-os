"""ADSENG5 — Tests créa + vol.

Prouve : les composants créatifs sont stockés sur CreativeAsset, l'approbation
d'un lot est BATCH-level (un seul geste), le backlog refuse une FK cross-société,
les bornes de phase de vol (2-4 bras, 1-8 semaines) sont validées, et la
réconciliation est en lecture seule.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, CreativeGenerationBatch, FlightPlan,
    ReconciliationSnapshot,
)

User = get_user_model()


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CreativeComponentFieldsTests(TestCase):
    def test_component_fields_store(self):
        company = Company.objects.create(nom='CC Co', slug='cc-co')
        asset = CreativeAsset.objects.create(
            company=company, asset_type=CreativeAsset.AssetType.STATIC,
            hook_id='H03', hook_text='Économisez 40% sur votre facture',
            primary_text='Passez au solaire.', visual_asset_key='co/vis.jpg',
            cta='LEARN_MORE')
        asset.refresh_from_db()
        self.assertEqual(asset.hook_id, 'H03')
        self.assertEqual(asset.cta, 'LEARN_MORE')
        self.assertEqual(asset.visual_asset_key, 'co/vis.jpg')


class CreativeBatchApprovalTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Batch Co', slug='batch-co')
        self.manager = make_user(
            self.company, 'bmgr', ['adsengine_view', 'adsengine_manage'])

    def test_batch_default_pending(self):
        batch = CreativeGenerationBatch.objects.create(company=self.company)
        self.assertEqual(
            batch.status, CreativeGenerationBatch.Statut.EN_ATTENTE)

    def test_approve_is_batch_level_single_action(self):
        batch = CreativeGenerationBatch.objects.create(
            company=self.company, visual_ids=['V1', 'V2'])
        resp = auth(self.manager).post(
            f'/api/django/adsengine/lots-creatifs/{batch.id}/approve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        batch.refresh_from_db()
        self.assertEqual(
            batch.status, CreativeGenerationBatch.Statut.APPROUVEE)
        self.assertEqual(batch.approved_by_id, self.manager.id)
        self.assertIsNotNone(batch.approved_at)

    def test_reject_sets_status(self):
        batch = CreativeGenerationBatch.objects.create(company=self.company)
        resp = auth(self.manager).post(
            f'/api/django/adsengine/lots-creatifs/{batch.id}/reject/')
        self.assertEqual(resp.status_code, 200, resp.data)
        batch.refresh_from_db()
        self.assertEqual(
            batch.status, CreativeGenerationBatch.Statut.REJETEE)


class BacklogAndFlightTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fl Co', slug='fl-co')
        self.manager = make_user(
            self.company, 'flmgr', ['adsengine_view', 'adsengine_manage'])

    def test_backlog_rejects_cross_company_asset(self):
        other = Company.objects.create(nom='Other', slug='other-fl')
        foreign_asset = CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC)
        resp = auth(self.manager).post(
            '/api/django/adsengine/backlog-creatif/',
            {'asset': foreign_asset.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_backlog_create_ok(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        resp = auth(self.manager).post(
            '/api/django/adsengine/backlog-creatif/',
            {'asset': asset.id, 'seasonal_tag': 'ete'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        item = CreativeBacklogItem.objects.get(pk=resp.data['id'])
        self.assertEqual(item.company_id, self.company.id)

    def test_flight_phase_rejects_bad_num_arms(self):
        plan = FlightPlan.objects.create(company=self.company, name='Plan A')
        resp = auth(self.manager).post(
            '/api/django/adsengine/phases-vol/',
            {'plan': plan.id, 'name': 'Phase 1', 'num_arms': 5},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_flight_phase_rejects_bad_week_span(self):
        plan = FlightPlan.objects.create(company=self.company, name='Plan B')
        resp = auth(self.manager).post(
            '/api/django/adsengine/phases-vol/',
            {'plan': plan.id, 'name': 'Phase 1', 'week_span': 0},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_flight_phase_valid_range(self):
        plan = FlightPlan.objects.create(company=self.company, name='Plan C')
        resp = auth(self.manager).post(
            '/api/django/adsengine/phases-vol/',
            {'plan': plan.id, 'name': 'Phase 1', 'num_arms': 3,
             'week_span': 4}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class ReconciliationReadOnlyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Rc Co', slug='rc-co')
        self.manager = make_user(
            self.company, 'rcmgr', ['adsengine_view', 'adsengine_manage'])

    def test_reconciliation_read_only(self):
        ReconciliationSnapshot.objects.create(
            company=self.company, date=datetime.date(2026, 7, 15),
            meta_leads=10, erp_leads=8, delta_leads=2,
            status=ReconciliationSnapshot.Statut.ECART)
        # Lecture OK.
        resp = auth(self.manager).get(
            '/api/django/adsengine/reconciliations/')
        self.assertEqual(resp.status_code, 200)
        # Écriture interdite (GET-only).
        resp2 = auth(self.manager).post(
            '/api/django/adsengine/reconciliations/',
            {'date': '2026-07-16'}, format='json')
        self.assertEqual(resp2.status_code, 405)
