"""ADSDEEP5 — Tests du budgeteur de rate-limit : parsing des en-têtes Meta,
backoff préventif quand l'usage franchit le seuil, exposition du % dans le
statut lisible par wiring-health.
"""
import json
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token='tok', ad_account_id='act_5', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


class ParseUsageHeadersTests(SimpleTestCase):
    def test_max_pct_across_headers(self):
        headers = {
            'X-FB-Ads-Insights-Throttle': json.dumps({
                'app_id_util_pct': 40.0, 'acc_id_util_pct': 95.0,
                'ads_api_access_tier': 'standard_access'}),
            'X-Ad-Account-Usage': json.dumps({'acc_id_util_pct': 12.0}),
            'X-Business-Use-Case-Usage': json.dumps({
                'act_5': [{'type': 'ads_insights', 'call_count': 30,
                           'total_cputime': 10, 'total_time': 20}]}),
        }
        state = mc.parse_usage_headers(headers)
        self.assertEqual(state['usage_pct'], 95.0)
        self.assertEqual(state['tier'], 'standard_access')

    def test_missing_headers_returns_none_pct(self):
        state = mc.parse_usage_headers({})
        self.assertIsNone(state['usage_pct'])

    def test_bad_json_ignored(self):
        state = mc.parse_usage_headers(
            {'X-FB-Ads-Insights-Throttle': 'not-json'})
        self.assertIsNone(state['usage_pct'])


class ThrottleBackoffTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_high_usage_triggers_slowdown_on_next_request(self):
        # 1re réponse renvoie 95 % d'usage → la 2e requête doit dormir.
        def handler(request):
            return httpx.Response(
                200, json={'data': []},
                headers={'X-FB-Ads-Insights-Throttle': json.dumps(
                    {'app_id_util_pct': 95.0})})

        client = make_client(handler)
        with patch('apps.adsengine.meta_client.time.sleep') as mock_sleep:
            client._request('GET', 'act_5/insights')  # observe 95 %
            self.assertFalse(mock_sleep.called)  # 1re requête : pas de sleep
            client._request('GET', 'act_5/insights')  # doit ralentir
            mock_sleep.assert_called_with(mc.THROTTLE_SLEEP_SECONDS)
        self.assertEqual(client.usage_state['usage_pct'], 95.0)

    def test_low_usage_no_slowdown(self):
        def handler(request):
            return httpx.Response(
                200, json={'data': []},
                headers={'X-FB-Ads-Insights-Throttle': json.dumps(
                    {'app_id_util_pct': 10.0})})

        client = make_client(handler)
        with patch('apps.adsengine.meta_client.time.sleep') as mock_sleep:
            client._request('GET', 'act_5/insights')
            client._request('GET', 'act_5/insights')
            self.assertFalse(mock_sleep.called)


class RateLimitStatusTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_status_reflects_cached_usage(self):
        def handler(request):
            return httpx.Response(
                200, json={'data': []},
                headers={'X-FB-Ads-Insights-Throttle': json.dumps(
                    {'app_id_util_pct': 95.0,
                     'ads_api_access_tier': 'standard_access'})})

        client = make_client(handler)
        client._request('GET', 'act_5/insights')
        status = mc.rate_limit_status('act_5')
        self.assertIsNotNone(status)
        self.assertEqual(status['usage_pct'], 95.0)
        self.assertTrue(status['throttled'])
        self.assertEqual(status['tier'], 'standard_access')

    def test_status_none_without_observation(self):
        self.assertIsNone(mc.rate_limit_status('act_unknown'))
