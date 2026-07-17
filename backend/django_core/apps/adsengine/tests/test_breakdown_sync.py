"""ADSDEEP8 — Tests de la synchro des breakdowns : les 4 dimensions se peuplent
en mock ; les combos ILLÉGAUX (hourly + reach/frequency) ne sont jamais émis ;
idempotence.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import InsightBreakdown
from apps.adsengine.tasks import (
    BREAKDOWN_SPECS, sync_breakdowns_for_campaign,
)


class BreakdownFakeClient:
    """Renvoie une ligne ventilée selon la dimension demandée (breakdowns)."""

    def __init__(self):
        self.calls = []

    def get_insights(self, meta_id, *, fields=None, params=None):
        self.calls.append({'fields': fields, 'params': params})
        bd = (params or {}).get('breakdowns', '')
        if 'age' in bd:
            return [{'age': '25-34', 'gender': 'female', 'spend': '10',
                     'impressions': '100', 'clicks': '5'}]
        if 'publisher_platform' in bd:
            return [{'publisher_platform': 'instagram',
                     'platform_position': 'instagram_reels', 'spend': '8',
                     'impressions': '80'}]
        if 'region' in bd:
            return [{'region': 'Casablanca', 'spend': '6', 'impressions': '60'}]
        if 'hourly' in bd:
            return [{
                'hourly_stats_aggregated_by_advertiser_time_zone':
                '14:00:00 - 14:59:59', 'spend': '4', 'impressions': '40'}]
        return []


class BreakdownSpecsGuardTests(SimpleTestCase):
    def test_hourly_never_requests_reach_or_frequency(self):
        # Combo illégal : hourly + reach/frequency/unique_* → ne JAMAIS émettre.
        fields = BREAKDOWN_SPECS['hourly']['fields']
        self.assertNotIn('reach', fields)
        self.assertNotIn('frequency', fields)
        for f in fields:
            self.assertFalse(f.startswith('unique_'))

    def test_four_dimensions_declared(self):
        self.assertEqual(
            set(BREAKDOWN_SPECS), {'age_gender', 'platform', 'region', 'hourly'})


class BreakdownSyncTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BD Co', slug='bd')
        self.camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]

    def test_four_dimensions_populated(self):
        client = BreakdownFakeClient()
        written = sync_breakdowns_for_campaign(self.company, client, self.camp)
        self.assertEqual(written, 4)
        dims = set(InsightBreakdown.objects.filter(
            company=self.company).values_list('dimension', flat=True))
        self.assertEqual(dims, {'age_gender', 'platform', 'region', 'hourly'})
        # Les clés sont normalisées (dossier §2 exemples).
        keys = dict(InsightBreakdown.objects.filter(
            company=self.company).values_list('dimension', 'key'))
        self.assertEqual(keys['age_gender'], '25-34/f')
        self.assertEqual(keys['platform'], 'instagram/reels')
        self.assertEqual(keys['region'], 'Casablanca')
        self.assertEqual(keys['hourly'], '14')

    def test_no_illegal_field_emitted_for_hourly(self):
        client = BreakdownFakeClient()
        sync_breakdowns_for_campaign(self.company, client, self.camp)
        hourly_calls = [
            c for c in client.calls
            if 'hourly' in (c['params'] or {}).get('breakdowns', '')]
        self.assertTrue(hourly_calls)
        for call in hourly_calls:
            self.assertNotIn('reach', call['fields'])
            self.assertNotIn('frequency', call['fields'])

    def test_idempotent(self):
        client = BreakdownFakeClient()
        sync_breakdowns_for_campaign(self.company, client, self.camp)
        sync_breakdowns_for_campaign(self.company, client, self.camp)
        self.assertEqual(
            InsightBreakdown.objects.filter(company=self.company).count(), 4)
