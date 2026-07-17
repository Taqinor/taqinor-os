"""ADSDEEP50/51/52 — Actions sur les posts de Page (édition / création / boost).

Prouve, mock (aucun réseau) :
  * ADSDEEP50 EDIT_POST — édite le ``message`` SEUL (jamais de ``status``), refuse
    proprement un post NON créé par l'app, double avertissement si le post est
    adossé à une pub, cycle complet propose→approuve→applique ;
  * ADSDEEP51 CREATE_POST — 3 modes (publié / dark / programmé, fenêtre 10 min-30 j
    validée) + 3 médias (photo / multi-photos / vidéo, borne 1,75 Go) ;
  * ADSDEEP52 BOOST_POST — adcreative ``object_story_id`` (JAMAIS object_story_spec,
    preuve sociale préservée) → ad née PAUSED (invariant permanent règle #3).
"""
import json
import time
from unittest.mock import Mock
from urllib.parse import parse_qs

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import AdSetMirror, EngineAction, PagePostMirror

User = get_user_model()

TOKEN = 'tok-post'


def make_client(handler, *, page_id='page-1', **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', page_id=page_id,
        http_client=http_client, max_retries=0, backoff_base=0, **kwargs)


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


# ── ADSDEEP50 — édition (client) ─────────────────────────────────────────────
class EditPagePostClientTests(SimpleTestCase):
    def test_edit_sends_only_message_never_status(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'post-1'})

        client = make_client(handler)
        result = client.edit_page_post(post_id='post-1', message='Nouveau texte')
        self.assertEqual(result, {'id': 'post-1'})
        req = captured['request']
        form = body_of(req)
        self.assertEqual(form['message'], ['Nouveau texte'])
        self.assertNotIn('status', form)
        self.assertTrue(str(req.url).endswith('/post-1'))

    def test_status_kwarg_raises_and_smuggled_stripped(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={})

        client = make_client(handler)
        with self.assertRaises(TypeError):
            client.edit_page_post(
                post_id='p', message='X', status='ACTIVE')
        client.edit_page_post(
            post_id='p', message='X', extra_fields={'status': 'ACTIVE'})
        raw = captured['request'].content.decode('utf-8')
        self.assertNotIn('ACTIVE', raw)
        self.assertNotIn('status', body_of(captured['request']))


# ── ADSDEEP51 — création (client) ────────────────────────────────────────────
class CreatePagePostClientTests(SimpleTestCase):
    def test_published_mode(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'p_1'})

        make_client(handler).create_page_post(
            message='Bonjour', link='https://taqinor.ma')
        form = body_of(captured['request'])
        self.assertEqual(form['published'], ['true'])
        self.assertEqual(form['message'], ['Bonjour'])
        self.assertTrue(str(captured['request'].url).endswith('/page-1/feed'))

    def test_dark_mode(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'p_2'})

        make_client(handler).create_page_post(message='Dark', published=False)
        form = body_of(captured['request'])
        self.assertEqual(form['published'], ['false'])
        self.assertNotIn('scheduled_publish_time', form)

    def test_scheduled_mode_within_window(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'p_3'})

        when = int(time.time()) + 3600  # +1 h → dans la fenêtre 10 min-30 j
        make_client(handler).create_page_post(
            message='Programmé', scheduled_publish_time=when)
        form = body_of(captured['request'])
        self.assertEqual(form['published'], ['false'])  # forcé non publié
        self.assertEqual(form['scheduled_publish_time'], [str(when)])

    def test_scheduled_out_of_window_raises(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        with self.assertRaises(mc.MetaError):
            client.create_page_post(
                scheduled_publish_time=int(time.time()) + 60)  # < 10 min
        with self.assertRaises(mc.MetaError):
            client.create_page_post(
                scheduled_publish_time=int(time.time()) + 40 * 24 * 3600)  # >30j

    def test_photo_upload(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'photo-1'})

        make_client(handler).upload_page_photo(
            image_url='https://img/1.jpg', published=True, caption='Légende')
        self.assertTrue(str(captured['request'].url).endswith('/page-1/photos'))
        form = body_of(captured['request'])
        self.assertEqual(form['url'], ['https://img/1.jpg'])
        self.assertEqual(form['published'], ['true'])

    def test_multi_photo_post_attaches_media_fbids(self):
        calls = []

        def handler(request):
            calls.append(request)
            if str(request.url).endswith('/page-1/photos'):
                return httpx.Response(200, json={'id': f'ph-{len(calls)}'})
            return httpx.Response(200, json={'id': 'post-multi'})

        make_client(handler).create_multi_photo_post(
            message='Album', image_urls=['a.jpg', 'b.jpg'])
        # 2 uploads photo (published=false) + 1 feed.
        self.assertEqual(len(calls), 3)
        self.assertTrue(str(calls[0].url).endswith('/page-1/photos'))
        self.assertEqual(body_of(calls[0])['published'], ['false'])
        feed = body_of(calls[2])
        self.assertEqual(json.loads(feed['attached_media[0]'][0]),
                         {'media_fbid': 'ph-1'})
        self.assertEqual(json.loads(feed['attached_media[1]'][0]),
                         {'media_fbid': 'ph-2'})

    def test_video_upload_and_size_guard(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'vid-1'})

        client = make_client(handler)
        client.upload_page_video(
            file_url='https://v/clip.mp4', message='Vidéo',
            file_size=100 * 1024 * 1024)
        self.assertTrue(str(captured['request'].url).endswith('/page-1/videos'))
        self.assertEqual(body_of(captured['request'])['file_url'],
                         ['https://v/clip.mp4'])
        # Au-delà de 1,75 Go → refus fail-fast.
        with self.assertRaises(mc.MetaError):
            client.upload_page_video(
                file_url='x', file_size=2 * 1024 * 1024 * 1024)


# ── ADSDEEP52 — boost (client) ───────────────────────────────────────────────
class BoostPagePostClientTests(SimpleTestCase):
    def test_boost_uses_object_story_id_and_ad_born_paused(self):
        calls = []

        def handler(request):
            calls.append(request)
            if str(request.url).endswith('/act_1/adcreatives'):
                return httpx.Response(200, json={'id': 'cr-boost'})
            return httpx.Response(200, json={'id': 'ad-boost'})

        client = make_client(handler)
        result = client.boost_page_post(
            post_id='post-9', adset_id='as-1', name='Boost')

        self.assertEqual(result['creative'], {'id': 'cr-boost'})
        self.assertEqual(result['ad'], {'id': 'ad-boost'})
        # 1er appel = créatif object_story_id ; 2e = ad.
        cr_body = body_of(calls[0])
        self.assertEqual(cr_body['object_story_id'], ['post-9'])
        # JAMAIS object_story_spec (preuve sociale préservée).
        self.assertNotIn('object_story_spec', calls[0].content.decode('utf-8'))
        self.assertNotIn('object_story_spec', cr_body)
        # L'ad est née PAUSED (invariant règle #3) et porte le nouveau créatif.
        ad_body = body_of(calls[1])
        self.assertEqual(ad_body['status'], ['PAUSED'])
        self.assertNotIn('ACTIVE', calls[1].content.decode('utf-8'))
        self.assertEqual(json.loads(ad_body['creative'][0]),
                         {'creative_id': 'cr-boost'})

    def test_boost_raises_without_post_id(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        with self.assertRaises(mc.MetaError):
            client.boost_page_post(post_id='', adset_id='as-1', name='X')


# ── Cycles services (propose→approuve→applique) ──────────────────────────────
class PostActionServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Post Co', slug='post-co')
        self.user = User.objects.create_user(
            username='post-approver', password='x', company=self.company)
        self.app_post = PagePostMirror.objects.create(
            company=self.company, meta_id='post-app', message='Ancien',
            created_by_app=True)
        self.foreign_post = PagePostMirror.objects.create(
            company=self.company, meta_id='post-foreign', created_by_app=False)
        self.ad_linked_post = PagePostMirror.objects.create(
            company=self.company, meta_id='post-ad', created_by_app=True,
            ad_linked=True)
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='AdSet')

    def _cycle(self, action, client):
        services.approve_action(action, user=self.user)
        services.apply_action(action, client=client)
        action.refresh_from_db()
        return action

    # ADSDEEP50
    def test_edit_post_refuses_non_app_post(self):
        with self.assertRaises(ValueError):
            services.propose_edit_post(
                self.company, post=self.foreign_post, message='X')
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_edit_post_single_warning_when_not_ad_linked(self):
        action = services.propose_edit_post(
            self.company, post=self.app_post, message='Nouveau')
        warns = action.payload['warnings']
        self.assertIn(services.WARN_POST_MESSAGE_ONLY, warns)
        self.assertNotIn(services.WARN_POST_AD_LINKED, warns)

    def test_edit_post_double_warning_when_ad_linked_then_cycle(self):
        action = services.propose_edit_post(
            self.company, post=self.ad_linked_post, message='Nouveau')
        warns = action.payload['warnings']
        self.assertIn(services.WARN_POST_MESSAGE_ONLY, warns)
        self.assertIn(services.WARN_POST_AD_LINKED, warns)

        client = Mock()
        client.edit_page_post.return_value = {'id': 'post-ad'}
        action = self._cycle(action, client)
        client.edit_page_post.assert_called_once_with(
            post_id='post-ad', message='Nouveau', extra_fields=None)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    # ADSDEEP51
    def test_create_post_scheduled_requires_time(self):
        with self.assertRaises(ValueError):
            services.propose_create_post(self.company, mode='scheduled')

    def test_create_post_cycle_routes_dark_mode(self):
        action = services.propose_create_post(
            self.company, message='Dark', mode='dark')
        client = Mock()
        client.create_page_post.return_value = {'id': 'p-dark'}
        action = self._cycle(action, client)
        client.create_page_post.assert_called_once_with(
            message='Dark', link='', published=False,
            scheduled_publish_time=None)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_create_post_cycle_routes_photo_media(self):
        action = services.propose_create_post(
            self.company, message='Photo', media={
                'kind': 'photo', 'image_url': 'https://img/x.jpg'})
        client = Mock()
        client.upload_page_photo.return_value = {'id': 'ph-1'}
        action = self._cycle(action, client)
        client.upload_page_photo.assert_called_once_with(
            image_url='https://img/x.jpg', published=True, caption='Photo')
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    # ADSDEEP52 — cycle complet avec un VRAI client mock-transport : prouve que
    # l'ad boostée naît PAUSED de bout en bout (pas seulement en unit du client).
    def test_boost_post_cycle_ad_born_paused_end_to_end(self):
        action = services.propose_boost_post(
            self.company, post=self.app_post, adset=self.adset)
        self.assertEqual(action.kind, services.KIND_BOOST_POST)
        services.approve_action(action, user=self.user)

        captured = []

        def handler(request):
            captured.append(request)
            if str(request.url).endswith('/act_1/adcreatives'):
                return httpx.Response(200, json={'id': 'cr-1'})
            return httpx.Response(200, json={'id': 'ad-1'})

        client = make_client(handler)
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        # L'ad créée (2e appel) est née PAUSED, jamais ACTIVE.
        ad_body = body_of(captured[1])
        self.assertEqual(ad_body['status'], ['PAUSED'])
        self.assertNotIn('ACTIVE', captured[1].content.decode('utf-8'))
        self.assertEqual(body_of(captured[0])['object_story_id'], ['post-app'])
