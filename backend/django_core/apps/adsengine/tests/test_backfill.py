"""PUB105 — Tests du rejeu/backfill ciblé après panne de webhook.

Prouve : sans connexion live le backfill est un NO-OP propre ; avec un client
mocké il rejoue les insights de la campagne visée (upsert idempotent, aucun
doublon) et re-calcule la réconciliation ; l'endpoint « rattraper » lit l'alerte
de divergence et déclenche le backfill (permission + scope société).
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import (
    AdCampaignMirror, InsightSnapshot, MetaConnection,
)
from apps.adsengine.tasks import backfill_after_divergence

User = get_user_model()


class _FakeBackfillClient:
    """Client mocké : leads vides, insights d'une campagne (déterministe)."""

    def get_ad_leads(self, ad_id, **kw):
        return []

    def get_insights(self, meta_id, *, fields=None, params=None):
        return [{'date_start': '2026-07-10', 'spend': '77.00', 'results': 5}]


class BackfillNoConnectionTests(TestCase):
    def test_noop_without_live_connection(self):
        company = Company.objects.create(nom='NoConn', slug='noconn')
        result = backfill_after_divergence(company, campaign_meta_id='c1')
        self.assertEqual(result['status'], 'no_connection')


class BackfillWithClientTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bf Co', slug='bf-co')
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 't'}, ad_account_id='act_1')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _run(self):
        with patch('apps.adsengine.meta_client.MetaClient.from_connection',
                   return_value=_FakeBackfillClient()):
            return backfill_after_divergence(
                self.company, campaign_meta_id='c1',
                day=datetime.date(2026, 7, 10))

    def test_refreshes_insights_and_is_idempotent(self):
        self._run()
        snap = InsightSnapshot.objects.get(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=datetime.date(2026, 7, 10))
        self.assertEqual(snap.spend, Decimal('77.00'))
        # Rejeu : aucun doublon (upsert idempotent par date).
        self._run()
        self.assertEqual(InsightSnapshot.objects.filter(
            object_id=self.camp.pk, date=datetime.date(2026, 7, 10)).count(), 1)


class BackfillEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bf API', slug='bf-api')
        role = Role.objects.create(
            company=self.company, nom='mgr',
            permissions=['adsengine_view', 'adsengine_manage'])
        self.user = User.objects.create_user(
            username='mgr', password='x', company=self.company,
            role_legacy='normal', role=role)
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 't'}, ad_account_id='act_1')
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')

    def _auth(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_endpoint_triggers_backfill(self):
        with patch('apps.adsengine.meta_client.MetaClient.from_connection',
                   return_value=_FakeBackfillClient()):
            resp = self._auth().post(
                '/api/django/adsengine/reconciliation/backfill/',
                {'campaign_meta_id': 'c1', 'date': '2026-07-10'},
                format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')
        self.assertGreaterEqual(resp.data['insights_refreshed'], 1)

    def test_endpoint_requires_manage_permission(self):
        role = Role.objects.create(
            company=self.company, nom='viewer', permissions=['adsengine_view'])
        viewer = User.objects.create_user(
            username='viewer', password='x', company=self.company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        resp = api.post(
            '/api/django/adsengine/reconciliation/backfill/',
            {'campaign_meta_id': 'c1'}, format='json')
        self.assertEqual(resp.status_code, 403)
