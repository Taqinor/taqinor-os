"""ADSDEEP2 — Tests : la synchro peuple des snapshots niveau ad ET adset
(edge compte, level=…), avec des spends NON NULS lisibles par le reporting
per-ad. Idempotent. Les rows sans miroir sont ignorés.
"""
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine.models import (
    AdMirror, AdSetMirror, InsightSnapshot, MetaConnection,
)
from apps.adsengine.tasks import sync_insights_daily


class LevelAwareFakeClient:
    """Client Meta mocké qui renvoie des lignes ad/adset selon ``level``."""

    def get_account(self, **kw):
        return {'currency': 'MAD'}

    def get_campaigns(self, **kw):
        return [{'id': 'c1', 'name': 'Camp', 'status': 'PAUSED'}]

    def get_adsets(self, **kw):
        return [{'id': 'as1', 'campaign_id': 'c1', 'name': 'AS',
                 'status': 'PAUSED'}]

    def get_ads(self, **kw):
        return [{'id': 'ad1', 'adset_id': 'as1', 'name': 'AD',
                 'status': 'PAUSED'}]

    def get_insights(self, meta_id, *, fields=None, params=None):
        level = (params or {}).get('level')
        if level == 'ad':
            return [{
                'date_start': '2026-07-16', 'ad_id': 'ad1',
                'spend': '42.00', 'impressions': '5000', 'reach': '4000',
                'clicks': '120', 'inline_link_clicks': '80',
                'actions': [
                    {'action_type': 'lead', 'value': '4'},
                    {'action_type':
                     'onsite_conversion.messaging_conversation_started_7d',
                     'value': '6'},
                ],
                'video_play_actions': [
                    {'action_type': 'video_view', 'value': '300'}],
            }]
        if level == 'adset':
            return [{
                'date_start': '2026-07-16', 'adset_id': 'as1',
                'spend': '84.00', 'impressions': '9000',
            }]
        # campagne (edge objet, date_preset=maximum)
        return [{'date_start': '2026-07-16', 'spend': '84.00', 'results': 6}]


class AdLevelSyncTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AdLvl Co', slug='adlvl')
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok-2'}, ad_account_id='act_9')

    def _snap_for(self, mirror):
        ct = ContentType.objects.get_for_model(mirror)
        return InsightSnapshot.objects.filter(
            company=self.company, content_type=ct, object_id=mirror.pk).first()

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_ad_and_adset_snapshots_populated(self, mock_cls):
        mock_cls.from_connection.return_value = LevelAwareFakeClient()
        sync_insights_daily()

        ad = AdMirror.objects.get(company=self.company, meta_id='ad1')
        adset = AdSetMirror.objects.get(company=self.company, meta_id='as1')
        ad_snap = self._snap_for(ad)
        adset_snap = self._snap_for(adset)

        self.assertIsNotNone(ad_snap)
        self.assertEqual(float(ad_snap.spend), 42.0)  # spend NON nul par ad
        self.assertEqual(ad_snap.impressions, 5000)
        self.assertEqual(ad_snap.link_clicks, 80)
        self.assertEqual(ad_snap.leads_count, 4)
        self.assertEqual(ad_snap.conversations, 6)
        self.assertEqual(ad_snap.video_metrics['plays'], 300.0)

        self.assertIsNotNone(adset_snap)
        self.assertEqual(float(adset_snap.spend), 84.0)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_idempotent(self, mock_cls):
        mock_cls.from_connection.return_value = LevelAwareFakeClient()
        sync_insights_daily()
        count = InsightSnapshot.objects.count()
        sync_insights_daily()
        self.assertEqual(InsightSnapshot.objects.count(), count)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_row_without_mirror_is_ignored(self, mock_cls):
        class Orphan(LevelAwareFakeClient):
            def get_ads(self, **kw):
                return []  # aucun miroir ad → la ligne ad_id=ad1 est ignorée

        mock_cls.from_connection.return_value = Orphan()
        sync_insights_daily()
        # Aucun snapshot d'ad (pas de miroir) — pas d'erreur non plus.
        self.assertFalse(AdMirror.objects.filter(company=self.company).exists())
