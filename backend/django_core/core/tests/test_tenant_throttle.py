"""NTPLT42 — throttle applicatif par tenant."""
from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase

from core.throttling import TenantRateThrottle


def _req(company_id=None, authed=True):
    company = SimpleNamespace(pk=company_id) if company_id is not None else None
    user = SimpleNamespace(is_authenticated=authed, company=company)
    return SimpleNamespace(user=user)


class TenantThrottleKeyTests(SimpleTestCase):
    def test_anonymous_not_throttled(self):
        t = TenantRateThrottle()
        self.assertIsNone(t.get_cache_key(_req(authed=False), None))

    def test_authed_without_company_not_throttled(self):
        t = TenantRateThrottle()
        self.assertIsNone(t.get_cache_key(_req(company_id=None), None))

    def test_company_scoped_key(self):
        t = TenantRateThrottle()
        self.assertEqual(t.get_cache_key(_req(company_id=9), None),
                         'throttle_tenant_9')

    def test_two_companies_have_separate_buckets(self):
        cache.clear()
        t = TenantRateThrottle()
        t.rate = '2/min'
        t.num_requests, t.duration = t.parse_rate('2/min')
        # Société 1 épuise son budget.
        self.assertTrue(t.allow_request(_req(company_id=1), None))
        self.assertTrue(t.allow_request(_req(company_id=1), None))
        self.assertFalse(t.allow_request(_req(company_id=1), None))
        # Société 2 démarre intacte : l'isolation est réelle.
        self.assertTrue(t.allow_request(_req(company_id=2), None))
