"""ADSDEEP1 — Tests : un payload insights réel remplit toutes les colonnes
typées ; le parsing d'``actions[]``/AdsActionStats est correct ; les anciens
rows (upsert 4-args) restent intacts.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import InsightSnapshot
from apps.adsengine.platforms.base import normalize_insight_row

# Payload insights RÉEL (forme Graph v25) : campagne CTWA avec conversations,
# leads, clics sur lien et métriques vidéo (AdsActionStats).
REAL_ROW = {
    'date_start': '2026-07-16',
    'spend': '123.45',
    'impressions': '10000',
    'reach': '8000',
    'clicks': '250',
    'frequency': '1.25',
    'inline_link_clicks': '180',
    'results': '12',
    'actions': [
        {'action_type': 'link_click', 'value': '180'},
        {'action_type': 'lead', 'value': '9'},
        {'action_type':
         'onsite_conversion.messaging_conversation_started_7d',
         'value': '12'},
        {'action_type': 'post_engagement', 'value': '500'},
    ],
    'video_p25_watched_actions': [{'action_type': 'video_view', 'value': '400'}],
    'video_p50_watched_actions': [{'action_type': 'video_view', 'value': '300'}],
    'video_p75_watched_actions': [{'action_type': 'video_view', 'value': '200'}],
    'video_p95_watched_actions': [{'action_type': 'video_view', 'value': '150'}],
    'video_p100_watched_actions': [{'action_type': 'video_view', 'value': '120'}],
    'video_play_actions': [{'action_type': 'video_view', 'value': '900'}],
    'video_6_sec_watched_actions': [{'action_type': 'video_view', 'value': '500'}],
    'video_15_sec_watched_actions': [{'action_type': 'video_view', 'value': '350'}],
    'video_30_sec_watched_actions': [{'action_type': 'video_view', 'value': '250'}],
    'video_thruplay_watched_actions': [{'action_type': 'video_view', 'value': '450'}],
    'video_avg_time_watched_actions': [{'action_type': 'video_view', 'value': '7'}],
}


class NormalizeInsightRowTests(TestCase):
    def test_all_columns_extracted_from_real_payload(self):
        norm = normalize_insight_row(REAL_ROW)
        self.assertEqual(norm['impressions'], 10000.0)
        self.assertEqual(norm['reach'], 8000.0)
        self.assertEqual(norm['clicks'], 250.0)
        self.assertEqual(norm['link_clicks'], 180.0)
        self.assertEqual(norm['conversations'], 12.0)
        self.assertEqual(norm['leads_count'], 9.0)
        vm = norm['video_metrics']
        self.assertEqual(vm['p25'], 400.0)
        self.assertEqual(vm['p100'], 120.0)
        self.assertEqual(vm['plays'], 900.0)
        self.assertEqual(vm['s6'], 500.0)
        self.assertEqual(vm['thruplay'], 450.0)
        self.assertEqual(vm['avg_time'], 7.0)

    def test_link_clicks_falls_back_to_action_when_no_scalar(self):
        row = dict(REAL_ROW)
        row.pop('inline_link_clicks')
        norm = normalize_insight_row(row)
        self.assertEqual(norm['link_clicks'], 180.0)  # depuis action link_click

    def test_static_ad_has_empty_video_metrics_and_null_conversions(self):
        norm = normalize_insight_row(
            {'spend': '5', 'impressions': '100', 'clicks': '3'})
        self.assertEqual(norm['video_metrics'], {})
        self.assertIsNone(norm['conversations'])
        self.assertIsNone(norm['leads_count'])

    def test_no_three_second_video_field(self):
        # Meta n'a pas de champ « 3 s » : un tel champ ne doit rien produire.
        from apps.adsengine.platforms import base
        self.assertNotIn('s3', base._VIDEO_FIELDS)
        self.assertNotIn('video_3_sec_watched_actions',
                         base._VIDEO_FIELDS.values())


class UpsertInsightColumnsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADSDEEP1 Co', slug='ad1')
        self.camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]

    def test_upsert_stores_all_columns(self):
        norm = normalize_insight_row(REAL_ROW)
        snap = sync.upsert_insight(
            self.company, self.camp, date=datetime.date(2026, 7, 16),
            spend=norm['spend'], results=norm['results'],
            frequency=norm['frequency'], cpl=norm['cpl'],
            impressions=norm['impressions'], reach=norm['reach'],
            clicks=norm['clicks'], link_clicks=norm['link_clicks'],
            conversations=norm['conversations'], leads_count=norm['leads_count'],
            video_metrics=norm['video_metrics'])
        snap.refresh_from_db()
        self.assertEqual(snap.impressions, 10000)
        self.assertEqual(snap.reach, 8000)
        self.assertEqual(snap.clicks, 250)
        self.assertEqual(snap.link_clicks, 180)
        self.assertEqual(snap.conversations, 12)
        self.assertEqual(snap.leads_count, 9)
        self.assertEqual(snap.video_metrics['plays'], 900.0)

    def test_legacy_upsert_leaves_new_columns_null(self):
        # Appel « ancien » (4 args) : les colonnes ADSDEEP1 restent NULL.
        snap = sync.upsert_insight(
            self.company, self.camp, date=datetime.date(2026, 7, 15),
            spend='10', results=2, frequency='1.1', cpl='5')
        snap.refresh_from_db()
        self.assertIsNone(snap.impressions)
        self.assertIsNone(snap.conversations)
        self.assertEqual(snap.video_metrics, {})

    def test_partial_resync_does_not_null_existing(self):
        day = datetime.date(2026, 7, 16)
        sync.upsert_insight(
            self.company, self.camp, date=day, spend='10',
            conversations=5, impressions=100)
        # Re-sync partiel SANS conversations : ne doit pas remettre à NULL.
        sync.upsert_insight(
            self.company, self.camp, date=day, spend='20')
        snap = InsightSnapshot.objects.get(
            company=self.company, object_id=self.camp.pk, date=day)
        self.assertEqual(snap.conversations, 5)
        self.assertEqual(snap.impressions, 100)
