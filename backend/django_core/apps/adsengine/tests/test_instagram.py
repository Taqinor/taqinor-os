"""ADSDEEP55 — Instagram (compte Business relié).

Prouve, mock (aucun réseau) :
  * client — lecture médias/commentaires ; masquage/réponse/suppression de
    commentaire ; ``comment_enabled`` (SEUL champ écrivable d'un média) ; quota
    de publication ;
  * flux CONTAINER complet (create → poll FINISHED → publish) + garde de quota
    50/24 h + garde de statut ERROR/EXPIRED + borne de taille Reel 300 Mo ;
  * la CAPTION est posée à la création et AUCUNE méthode d'édition de légende
    n'existe (immuable, dossier §4) ;
  * services — cycle publish_ig de bout en bout (journal InstagramPublishJob +
    quota surfacé), actions commentaires ; synchro miroir.
"""
from unittest.mock import Mock

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import instagram as ig
from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import (
    EngineAction, InstagramCommentMirror, InstagramMediaMirror,
    InstagramPublishJob, MetaConnection)

User = get_user_model()

TOKEN = 'tok-ig'


def make_client(handler, *, ig_user_id='ig-1', page_id='page-1', **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', page_id=page_id,
        ig_user_id=ig_user_id, http_client=http_client, max_retries=0,
        backoff_base=0, **kwargs)


def body_of(request):
    from urllib.parse import parse_qs
    return parse_qs(request.content.decode('utf-8'))


# ── Client : commentaires + média writable field ─────────────────────────────
class IgCommentClientTests(SimpleTestCase):
    def test_hide_ig_comment_sends_hide_never_status(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        make_client(handler).hide_ig_comment(comment_id='igc-1', hidden=True)
        form = body_of(captured['request'])
        self.assertEqual(form['hide'], ['true'])
        self.assertNotIn('status', form)
        self.assertNotIn('ACTIVE', captured['request'].content.decode('utf-8'))

    def test_set_comment_enabled_only_writable_media_field(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        make_client(handler).set_ig_comment_enabled(media_id='m-1', enabled=False)
        form = body_of(captured['request'])
        self.assertEqual(form['comment_enabled'], ['false'])
        # JAMAIS de caption écrite (légende immuable).
        self.assertNotIn('caption', form)

    def test_reply_and_delete(self):
        seen = []

        def handler(request):
            seen.append((request.method, str(request.url)))
            return httpx.Response(200, json={'id': 'x'})

        client = make_client(handler)
        client.reply_ig_comment(comment_id='igc-1', message='Merci')
        client.delete_ig_comment(comment_id='igc-1')
        methods = [m for m, _ in seen]
        self.assertIn('DELETE', methods)
        self.assertTrue(any(u.endswith('/igc-1/replies') for _, u in seen))

    def test_no_caption_edit_method_exists(self):
        # Invariant : aucune édition de légende (immuable, comme aucune activation).
        client = make_client(lambda r: httpx.Response(200, json={}))
        self.assertFalse(hasattr(client, 'edit_ig_caption'))
        self.assertFalse(hasattr(client, 'update_ig_caption'))


# ── Client : quota + flux container ──────────────────────────────────────────
class IgPublishClientTests(SimpleTestCase):
    def test_publishing_limit_parses_quota(self):
        def handler(request):
            return httpx.Response(200, json={'data': [
                {'quota_usage': 3, 'config': {'quota_total': 50}}]})

        limit = make_client(handler).get_ig_publishing_limit()
        self.assertEqual(limit, {'used': 3, 'total': 50})

    def test_create_container_sets_caption_and_media_type(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'cont-1'})

        make_client(handler).create_ig_container(
            image_url='https://img/x.jpg', media_type='IMAGE',
            caption='Ma légende')
        form = body_of(captured['request'])
        self.assertEqual(form['caption'], ['Ma légende'])
        self.assertEqual(form['media_type'], ['IMAGE'])
        self.assertEqual(form['image_url'], ['https://img/x.jpg'])

    def test_reel_size_guard(self):
        client = make_client(lambda r: httpx.Response(200, json={'id': 'c'}))
        with self.assertRaises(mc.MetaError):
            client.create_ig_container(
                video_url='https://v/reel.mp4', media_type='REELS',
                file_size=301 * 1024 * 1024)  # > 300 Mo

    def test_full_container_flow_create_poll_publish(self):
        calls = []

        def handler(request):
            url = str(request.url)
            calls.append((request.method, url))
            if url.endswith('/content_publishing_limit'):
                return httpx.Response(200, json={'data': [
                    {'quota_usage': 1, 'config': {'quota_total': 50}}]})
            if url.endswith('/ig-1/media'):
                return httpx.Response(200, json={'id': 'cont-9'})
            if 'cont-9' in url:  # GET status
                return httpx.Response(200, json={'status_code': 'FINISHED'})
            if url.endswith('/media_publish'):
                return httpx.Response(200, json={'id': 'ig-media-9'})
            return httpx.Response(200, json={})

        result = make_client(handler).publish_ig_media(
            image_url='https://img/x.jpg', media_type='IMAGE',
            caption='Bonjour', poll_seconds=0)
        self.assertEqual(result['creation_id'], 'cont-9')
        self.assertEqual(result['media_id'], 'ig-media-9')
        self.assertEqual(result['quota'], {'used': 1, 'total': 50})
        # L'ordre : quota → media (create) → status → media_publish.
        urls = [u for _, u in calls]
        self.assertTrue(urls[0].endswith('/content_publishing_limit'))
        self.assertTrue(any(u.endswith('/ig-1/media') for u in urls))
        self.assertTrue(urls[-1].endswith('/media_publish'))

    def test_quota_exceeded_refuses_before_publish(self):
        calls = []

        def handler(request):
            url = str(request.url)
            calls.append(url)
            if url.endswith('/content_publishing_limit'):
                return httpx.Response(200, json={'data': [
                    {'quota_usage': 50, 'config': {'quota_total': 50}}]})
            return httpx.Response(200, json={'id': 'never'})

        with self.assertRaises(mc.MetaError):
            make_client(handler).publish_ig_media(
                image_url='https://img/x.jpg', media_type='IMAGE')
        # Aucune création de container n'a eu lieu (refus AVANT).
        self.assertFalse(any(u.endswith('/ig-1/media') for u in calls))

    def test_container_error_status_raises(self):
        def handler(request):
            url = str(request.url)
            if url.endswith('/content_publishing_limit'):
                return httpx.Response(200, json={'data': [
                    {'quota_usage': 0, 'config': {'quota_total': 50}}]})
            if url.endswith('/ig-1/media'):
                return httpx.Response(200, json={'id': 'cont-err'})
            if 'cont-err' in url:
                return httpx.Response(200, json={'status_code': 'ERROR'})
            return httpx.Response(200, json={})

        with self.assertRaises(mc.MetaError):
            make_client(handler).publish_ig_media(
                video_url='https://v/x.mp4', media_type='REELS', poll_seconds=0)


# ── Services : cycle publish + actions commentaires ──────────────────────────
class IgServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='IG Co', slug='ig-co')
        self.user = User.objects.create_user(
            username='ig-approver', password='x', company=self.company)

    def _cycle(self, action, client):
        services.approve_action(action, user=self.user)
        services.apply_action(action, client=client)
        action.refresh_from_db()
        return action

    def test_publish_ig_validation_and_warning(self):
        with self.assertRaises(ValueError):
            services.propose_publish_ig(self.company, media_type='NOPE')
        with self.assertRaises(ValueError):
            services.propose_publish_ig(
                self.company, media_type='REELS')  # video_url manquant
        action = services.propose_publish_ig(
            self.company, media_type='IMAGE', image_url='https://img/x.jpg',
            caption='Ma légende')
        self.assertIn(services.WARN_IG_CAPTION_IMMUTABLE,
                      action.payload['warnings'])

    def test_publish_ig_cycle_records_job_and_quota(self):
        action = services.propose_publish_ig(
            self.company, media_type='IMAGE', image_url='https://img/x.jpg',
            caption='Bonjour')

        def handler(request):
            url = str(request.url)
            if url.endswith('/content_publishing_limit'):
                return httpx.Response(200, json={'data': [
                    {'quota_usage': 4, 'config': {'quota_total': 50}}]})
            if url.endswith('/ig-1/media'):
                return httpx.Response(200, json={'id': 'cont-1'})
            if 'cont-1' in url:
                return httpx.Response(200, json={'status_code': 'FINISHED'})
            if url.endswith('/media_publish'):
                return httpx.Response(200, json={'id': 'pub-1'})
            return httpx.Response(200, json={})

        action = self._cycle(action, make_client(handler))
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        job = InstagramPublishJob.objects.get(company=self.company)
        self.assertEqual(job.status, InstagramPublishJob.Status.PUBLISHED)
        self.assertEqual(job.published_media_id, 'pub-1')
        self.assertEqual(job.creation_id, 'cont-1')
        # Quota SURFACÉ sur le job.
        self.assertEqual(job.quota_used, 4)
        self.assertEqual(job.quota_total, 50)

    def test_publish_ig_quota_full_marks_job_error(self):
        action = services.propose_publish_ig(
            self.company, media_type='IMAGE', image_url='https://img/x.jpg')

        def handler(request):
            if str(request.url).endswith('/content_publishing_limit'):
                return httpx.Response(200, json={'data': [
                    {'quota_usage': 50, 'config': {'quota_total': 50}}]})
            return httpx.Response(200, json={'id': 'never'})

        services.approve_action(action, user=self.user)
        with self.assertRaises(mc.MetaError):
            services.apply_action(action, client=make_client(handler))
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
        job = InstagramPublishJob.objects.get(company=self.company)
        self.assertEqual(job.status, InstagramPublishJob.Status.ERROR)

    def test_toggle_ig_comments_updates_mirror(self):
        media = InstagramMediaMirror.objects.create(
            company=self.company, meta_id='m-1', comment_enabled=True)
        action = services.propose_toggle_ig_comments(
            self.company, media=media, enabled=False)
        client = Mock()
        client.set_ig_comment_enabled.return_value = {'success': True}
        self._cycle(action, client)
        media.refresh_from_db()
        self.assertFalse(media.comment_enabled)

    def test_hide_ig_comment_cycle(self):
        comment = InstagramCommentMirror.objects.create(
            company=self.company, meta_id='igc-1', message='spam')
        action = services.propose_hide_ig_comment(
            self.company, comment=comment, hidden=True)
        client = Mock()
        client.hide_ig_comment.return_value = {'success': True}
        self._cycle(action, client)
        comment.refresh_from_db()
        self.assertTrue(comment.hidden)


# ── Synchro ──────────────────────────────────────────────────────────────────
class IgSyncTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='IG Sync', slug='ig-sync')

    def test_sync_media_mirrors_caption_readonly(self):
        rows = [{
            'id': 'm-1', 'caption': 'Ma légende', 'media_type': 'IMAGE',
            'permalink': 'https://ig/m1', 'like_count': 5, 'comments_count': 2,
            'is_comment_enabled': True, 'timestamp': '2026-07-10T10:00:00+0000'}]
        mirrors = ig.sync_ig_media(self.company, rows)
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(mirrors[0].caption, 'Ma légende')
        # Idempotent.
        ig.sync_ig_media(self.company, rows)
        self.assertEqual(InstagramMediaMirror.objects.count(), 1)

    def test_sync_for_company_resolves_ig_user_id_and_persists(self):
        from apps.adsengine.tasks import sync_instagram_for_company

        conn = MetaConnection.objects.create(
            company=self.company, enabled=True, page_id='page-1',
            ad_account_id='act_1')
        client = Mock()
        client.ig_user_id = None
        client.get_page_ig_account.return_value = 'ig-99'
        client.get_ig_media.return_value = [
            {'id': 'm-1', 'caption': 'x', 'media_type': 'IMAGE'}]
        client.get_ig_media_comments.return_value = [
            {'id': 'igc-1', 'text': 'hi', 'username': 'sara'}]
        total = sync_instagram_for_company(self.company, conn, client)
        self.assertEqual(total, 1)
        conn.refresh_from_db()
        # ig_user_id résolu ET persisté sur la connexion.
        self.assertEqual(conn.ig_user_id, 'ig-99')
        self.assertEqual(InstagramCommentMirror.objects.count(), 1)
