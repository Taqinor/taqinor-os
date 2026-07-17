"""ADSDEEP3 — Tests du backfill : un compte avec 4 mois d'historique se remplit
(async report_run_id + polling), re-run sans doublons, repli mois-par-mois sur
« Job Failed ». Aucun réseau (client mocké).
"""
import datetime
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import InsightSnapshot, MetaConnection

# 4 mois d'historique, une ligne par mois pour l'ad 'ad1'.
HISTORY_ROWS = [
    {'ad_id': 'ad1', 'date_start': '2026-04-10', 'spend': '10',
     'impressions': '100'},
    {'ad_id': 'ad1', 'date_start': '2026-05-10', 'spend': '20',
     'impressions': '200'},
    {'ad_id': 'ad1', 'date_start': '2026-06-10', 'spend': '30',
     'impressions': '300'},
    {'ad_id': 'ad1', 'date_start': '2026-07-10', 'spend': '40',
     'impressions': '400',
     'actions': [{'action_type': 'lead', 'value': '5'}]},
]


class AsyncFakeClient:
    """Client mocké : cycle async report_run_id → Completed → data."""

    def __init__(self, *, fail=False):
        self.fail = fail
        self.ad_account_id = 'act_1'

    def _request(self, method, path, *, params=None, data=None):
        if method == 'POST' and path.endswith('/insights'):
            return {'report_run_id': 'run-1'}
        if method == 'GET' and path == 'run-1':
            return {'async_status': 'Job Failed' if self.fail
                    else 'Job Completed', 'async_percent_completion': 100}
        return {}

    def get_insights(self, meta_id, *, fields=None, params=None):
        if meta_id == 'run-1':
            return list(HISTORY_ROWS)
        # repli mensuel : filtre par time_range
        tr = (params or {}).get('time_range') or {}
        since = tr.get('since')
        until = tr.get('until')
        if since and until:
            return [r for r in HISTORY_ROWS if since <= r['date_start'] <= until]
        return list(HISTORY_ROWS)


class BackfillTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BF Co', slug='bf')
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        # Le miroir d'ad doit exister pour rattacher les snapshots.
        sync.sync_ads(self.company, [{'id': 'ad1', 'name': 'AD'}])

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_four_months_history_filled(self, mock_cls):
        mock_cls.from_connection.return_value = AsyncFakeClient()
        call_command('insights_backfill', '--poll-interval', '0')
        snaps = InsightSnapshot.objects.filter(company=self.company)
        self.assertEqual(snaps.count(), 4)  # une par mois
        # La ligne de juillet porte les leads parsés depuis actions[].
        july = snaps.get(date=datetime.date(2026, 7, 10))
        self.assertEqual(july.leads_count, 5)
        self.assertEqual(float(july.spend), 40.0)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_rerun_no_duplicates(self, mock_cls):
        mock_cls.from_connection.return_value = AsyncFakeClient()
        call_command('insights_backfill', '--poll-interval', '0')
        call_command('insights_backfill', '--poll-interval', '0')
        self.assertEqual(
            InsightSnapshot.objects.filter(company=self.company).count(), 4)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_job_failed_falls_back_to_monthly(self, mock_cls):
        mock_cls.from_connection.return_value = AsyncFakeClient(fail=True)
        call_command('insights_backfill', '--poll-interval', '0')
        # Le repli mensuel remplit quand même l'historique, sans doublon.
        self.assertEqual(
            InsightSnapshot.objects.filter(company=self.company).count(), 4)

    def test_noop_without_connection(self):
        MetaConnection.objects.filter(company=self.company).delete()
        # Aucune exception, aucun snapshot.
        call_command('insights_backfill', '--poll-interval', '0')
        self.assertEqual(
            InsightSnapshot.objects.filter(company=self.company).count(), 0)
