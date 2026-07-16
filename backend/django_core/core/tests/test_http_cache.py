"""NTPLT23/25 — compteur de version + ETag/304 + Cache-Control (fondation)."""
from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from core import http_cache


class _FakeQueryParams(dict):
    def getlist(self, k):
        v = self.get(k)
        return [v] if v is not None else []


class VersionCounterTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_bump_increments_per_tenant_model(self):
        self.assertEqual(http_cache.get_version('crm.lead', 1), 0)
        http_cache.bump_version('crm.lead', 1)
        self.assertEqual(http_cache.get_version('crm.lead', 1), 1)
        # Autre société : compteur indépendant.
        self.assertEqual(http_cache.get_version('crm.lead', 2), 0)

    def test_etag_changes_after_write(self):
        e1 = http_cache.compute_list_etag('crm.lead', 1, _FakeQueryParams())
        http_cache.bump_version('crm.lead', 1)
        e2 = http_cache.compute_list_etag('crm.lead', 1, _FakeQueryParams())
        self.assertNotEqual(e1, e2)

    def test_etag_varies_with_query_params(self):
        a = http_cache.compute_list_etag('crm.lead', 1, _FakeQueryParams(q='x'))
        b = http_cache.compute_list_etag('crm.lead', 1, _FakeQueryParams(q='y'))
        self.assertNotEqual(a, b)


class _DummyBaseViewSet:
    """Simule le comportement DRF de list() (retourne une Response 200)."""

    def get_queryset(self):
        return SimpleNamespace(model=SimpleNamespace(
            _meta=SimpleNamespace(label_lower='crm.lead')))

    def list(self, request, *args, **kwargs):
        return Response([{'id': 1}], status=200)


class _EtagViewSet(http_cache.ETagListMixin, _DummyBaseViewSet):
    etag_model_label = 'crm.lead'


class ETagListMixinTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.rf = APIRequestFactory()

    def test_200_then_304_then_200_after_write(self):
        vs = _EtagViewSet()
        # 1) premier appel → 200 + ETag.
        r1 = vs.list(self.rf.get('/leads/'))
        self.assertEqual(r1.status_code, 200)
        etag = r1['ETag']
        # 2) même ETag renvoyé → 304 sans corps.
        r2 = vs.list(self.rf.get('/leads/', HTTP_IF_NONE_MATCH=etag))
        self.assertEqual(r2.status_code, 304)
        # 3) après écriture (bump), le même If-None-Match ne matche plus → 200.
        http_cache.bump_version('crm.lead', None)
        r3 = vs.list(self.rf.get('/leads/', HTTP_IF_NONE_MATCH=etag))
        self.assertEqual(r3.status_code, 200)

    def test_cache_control_mixin_sets_header(self):
        class _CC(http_cache.CacheControlMixin, _DummyBaseViewSet):
            cache_control_max_age = 300
        r = _CC().list(self.rf.get('/marques/'))
        self.assertEqual(r['Cache-Control'], 'private, max-age=300')
