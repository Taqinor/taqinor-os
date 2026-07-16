"""ENG5 — Tests de la synchro idempotente des miroirs + InsightSnapshot.

Prouve : deux exécutions sur les mêmes payloads = même état (aucun doublon),
``created_via_engine`` préservé au re-sync, résolution des FK parent, upsert
d'insight idempotent (même jour = 1 ligne mise à jour) et isolation multi-tenant.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, InsightSnapshot,
)

CAMPAIGNS = [
    {'id': 'c1', 'name': 'Camp 1', 'status': 'PAUSED',
     'objective': 'OUTCOME_LEADS', 'daily_budget': '5000'},
    {'id': 'c2', 'name': 'Camp 2', 'status': 'PAUSED', 'daily_budget': '3000'},
]


class SyncIdempotencyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sync Co', slug='sync-co')

    def _snapshot(self):
        return sorted(
            (m.meta_id, m.name, m.status, str(m.budget), m.created_via_engine)
            for m in AdCampaignMirror.objects.filter(company=self.company))

    def test_campaigns_two_runs_same_state(self):
        sync.sync_campaigns(self.company, CAMPAIGNS)
        state1 = self._snapshot()
        count1 = AdCampaignMirror.objects.count()
        # Deuxième exécution : mêmes payloads → état byte-identique, 0 doublon.
        sync.sync_campaigns(self.company, CAMPAIGNS)
        self.assertEqual(AdCampaignMirror.objects.count(), count1)
        self.assertEqual(self._snapshot(), state1)
        c1 = AdCampaignMirror.objects.get(company=self.company, meta_id='c1')
        self.assertEqual(c1.budget, Decimal('5000'))
        self.assertEqual(c1.objective, 'OUTCOME_LEADS')

    def test_created_via_engine_preserved_on_resync(self):
        sync.sync_campaigns(
            self.company, [{'id': 'c9', 'name': 'Engine', 'status': 'PAUSED'}],
            created_via_engine=True)
        # Re-sync depuis Meta (created_via_engine défaut False) : le flag NE doit
        # PAS être écrasé, mais les métadonnées SONT rafraîchies.
        sync.sync_campaigns(
            self.company,
            [{'id': 'c9', 'name': 'Engine renommée', 'status': 'ACTIVE'}])
        c9 = AdCampaignMirror.objects.get(company=self.company, meta_id='c9')
        self.assertTrue(c9.created_via_engine)
        self.assertEqual(c9.name, 'Engine renommée')
        self.assertEqual(c9.status, 'ACTIVE')

    def test_adset_and_ad_resolve_parent_fk(self):
        sync.sync_campaigns(self.company, [{'id': 'c1', 'name': 'C'}])
        sync.sync_adsets(
            self.company,
            [{'id': 'as1', 'campaign_id': 'c1', 'name': 'AS', 'status': 'PAUSED'}])
        sync.sync_ads(
            self.company,
            [{'id': 'ad1', 'adset_id': 'as1', 'name': 'AD', 'status': 'PAUSED'}])
        as1 = AdSetMirror.objects.get(company=self.company, meta_id='as1')
        ad1 = AdMirror.objects.get(company=self.company, meta_id='ad1')
        self.assertEqual(as1.campaign.meta_id, 'c1')
        self.assertEqual(ad1.adset.meta_id, 'as1')

    def test_adset_orphan_parent_stays_null(self):
        # Ad set synchronisé AVANT son parent → FK nulle, pas d'erreur.
        sync.sync_adsets(
            self.company, [{'id': 'as9', 'campaign_id': 'cX', 'name': 'AS'}])
        as9 = AdSetMirror.objects.get(company=self.company, meta_id='as9')
        self.assertIsNone(as9.campaign)

    def test_insight_upsert_idempotent(self):
        camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]
        day = datetime.date(2026, 7, 16)
        sync.upsert_insight(
            self.company, camp, date=day, spend='12.50', results=3,
            frequency='1.4', cpl='4.17')
        sync.upsert_insight(
            self.company, camp, date=day, spend='20.00', results=5,
            frequency='1.6', cpl='4.00')
        snaps = InsightSnapshot.objects.filter(company=self.company)
        self.assertEqual(snaps.count(), 1)  # même clé (jour) → 1 ligne
        snap = snaps.get()
        self.assertEqual(snap.spend, Decimal('20.00'))
        self.assertEqual(snap.results, 5)
        self.assertEqual(snap.content_object, camp)  # FK générique résout

    def test_tenant_isolation_same_meta_id(self):
        other = Company.objects.create(nom='Sync B', slug='sync-b')
        sync.sync_campaigns(self.company, [{'id': 'c1', 'name': 'A'}])
        sync.sync_campaigns(other, [{'id': 'c1', 'name': 'B'}])
        # Même meta_id, sociétés différentes → deux miroirs distincts.
        self.assertEqual(AdCampaignMirror.objects.filter(meta_id='c1').count(), 2)
        self.assertEqual(
            AdCampaignMirror.objects.get(company=self.company, meta_id='c1').name,
            'A')
