"""ADSDEEP49 — Miroir des posts organiques de Page (PagePostMirror + sync).

Couvre : les LECTURES du client (``get_page_posts`` demande les bons champs et
suit la pagination ; ``get_ads_posts_ids`` renvoie l'ensemble des ids ad-linked),
et la SYNCHRO (``sync.sync_page_posts`` peuple le miroir avec ``created_by_app``
vrai UNIQUEMENT quand l'``application.id`` matche l'``app_id``, et ``ad_linked``
vrai UNIQUEMENT pour les posts figurant dans ``ads_posts``). Idempotence prouvée.
"""
import httpx
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import meta_client as mc
from apps.adsengine import sync
from apps.adsengine.models import PagePostMirror

TOKEN = 'tok-pp'


def make_client(handler, *, page_id='page-1', **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', page_id=page_id,
        http_client=http_client, max_retries=0, backoff_base=0, **kwargs)


class PagePostReadsTests(SimpleTestCase):
    def test_get_page_posts_requests_expected_fields(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'data': []})

        make_client(handler).get_page_posts()
        req = captured['request']
        self.assertTrue(str(req.url).split('?')[0].endswith('/page-1/posts'))
        fields = (req.url.params.get('fields') or '').split(',')
        for f in ('id', 'message', 'created_time', 'permalink_url',
                  'is_published', 'scheduled_publish_time', 'application'):
            self.assertIn(f, fields)

    def test_get_page_posts_follows_pagination(self):
        def handler(request):
            after = request.url.params.get('after')
            if not after:
                return httpx.Response(200, json={
                    'data': [{'id': 'p1'}],
                    'paging': {'cursors': {'after': 'C2'}, 'next': 'more'}})
            return httpx.Response(200, json={
                'data': [{'id': 'p2'}], 'paging': {'cursors': {'after': 'C3'}}})

        rows = make_client(handler).get_page_posts()
        self.assertEqual([r['id'] for r in rows], ['p1', 'p2'])

    def test_get_ads_posts_ids_returns_set(self):
        def handler(request):
            self.assertTrue(str(request.url).split('?')[0]
                            .endswith('/page-1/ads_posts'))
            return httpx.Response(200, json={
                'data': [{'id': 'p1'}, {'id': 'p3'}, {'id': ''}]})

        ids = make_client(handler).get_ads_posts_ids()
        self.assertEqual(ids, {'p1', 'p3'})

    def test_page_edge_raises_without_page_id(self):
        client = make_client(
            lambda r: httpx.Response(200, json={'data': []}), page_id='')
        with self.assertRaises(mc.MetaError):
            client.get_page_posts()


class SyncPagePostsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PP Co', slug='pp-co')

    def _posts(self):
        return [
            {'id': 'p1', 'message': 'Nôtre solaire',
             'permalink_url': 'https://fb/p1', 'is_published': True,
             'created_time': '2026-01-02T10:00:00+0000',
             'application': {'id': 'app-42'}},
            {'id': 'p2', 'message': 'Programmé', 'is_published': False,
             'scheduled_publish_time': 1893456000,
             'application': {'id': 'other-app'}},
            {'id': '', 'message': 'ignoré'},  # sans id → ignoré
        ]

    def test_sync_sets_created_by_app_and_ad_linked_flags(self):
        mirrors = sync.sync_page_posts(
            self.company, self._posts(),
            ad_linked_ids={'p1'}, app_id='app-42')
        self.assertEqual(len(mirrors), 2)  # le post sans id est ignoré

        p1 = PagePostMirror.objects.get(company=self.company, meta_id='p1')
        # created_by_app vrai : application.id matche app_id.
        self.assertTrue(p1.created_by_app)
        self.assertTrue(p1.is_editable_by_app)
        # ad_linked vrai : p1 figure dans ads_posts.
        self.assertTrue(p1.ad_linked)
        self.assertTrue(p1.is_published)
        self.assertEqual(p1.message, 'Nôtre solaire')
        self.assertIsNotNone(p1.created_time)

        p2 = PagePostMirror.objects.get(company=self.company, meta_id='p2')
        # application.id NE matche PAS → non éditable par l'app.
        self.assertFalse(p2.created_by_app)
        self.assertFalse(p2.ad_linked)
        self.assertFalse(p2.is_published)
        self.assertIsNotNone(p2.scheduled_publish_time)

    def test_created_by_app_false_when_no_app_id_known(self):
        sync.sync_page_posts(self.company, self._posts(), app_id='')
        self.assertFalse(
            PagePostMirror.objects.get(meta_id='p1').created_by_app)

    def test_sync_is_idempotent(self):
        sync.sync_page_posts(
            self.company, self._posts(), ad_linked_ids={'p1'}, app_id='app-42')
        sync.sync_page_posts(
            self.company, self._posts(), ad_linked_ids=set(), app_id='app-42')
        self.assertEqual(
            PagePostMirror.objects.filter(company=self.company).count(), 2)
        # Re-synchro sans ad_linked_ids : le flag repasse à False (Meta = vérité).
        self.assertFalse(
            PagePostMirror.objects.get(meta_id='p1').ad_linked)
