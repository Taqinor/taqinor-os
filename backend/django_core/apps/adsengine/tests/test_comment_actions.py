"""ADSDEEP53 — Boîte de réception des commentaires (posts + dark posts).

Prouve, mock (aucun réseau) :
  * client — lecture des commentaires (posts organiques ET dark posts, mêmes
    edges), masquage (``is_hidden`` SEUL, jamais de ``status``), read-back
    (``get_comment``), réponse, suppression, réponse privée ;
  * masquage AVEC READ-BACK : ``hidden_verified`` (badge « caché-vérifié ») ne
    passe VRAI que si le re-GET confirme l'état demandé ;
  * garde de réponse privée : UNE seule / commentaire, fenêtre 7 jours ;
  * moteur mot-clé en DRY-RUN (aucune action créée) puis mode PROPOSE.
"""
from unittest.mock import Mock

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import comments as comments_mod
from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import (
    AdCreativeMirror, AdMirror, CommentKeywordRule, CommentMirror, EngineAction,
    PagePostMirror)

User = get_user_model()

TOKEN = 'tok-comment'


def make_client(handler, *, page_id='page-1', **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', page_id=page_id,
        http_client=http_client, max_retries=0, backoff_base=0, **kwargs)


def body_of(request):
    from urllib.parse import parse_qs
    return parse_qs(request.content.decode('utf-8'))


# ── Client (mock-transport) ──────────────────────────────────────────────────
class CommentClientTests(SimpleTestCase):
    def test_get_object_comments_reads_toplevel(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'data': [{'id': 'c1'}], 'paging': {}})

        rows = make_client(handler).get_object_comments('post-1')
        self.assertEqual(rows, [{'id': 'c1'}])
        self.assertIn('filter=toplevel', str(captured['request'].url))
        self.assertTrue('/post-1/comments' in str(captured['request'].url))

    def test_hide_comment_sends_only_is_hidden_never_status(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        make_client(handler).hide_comment(comment_id='c-9', hidden=True)
        form = body_of(captured['request'])
        self.assertEqual(form['is_hidden'], ['true'])
        self.assertNotIn('status', form)
        self.assertNotIn('ACTIVE', captured['request'].content.decode('utf-8'))
        self.assertTrue(str(captured['request'].url).endswith('/c-9'))

    def test_get_comment_readback(self):
        def handler(request):
            return httpx.Response(200, json={'id': 'c-9', 'is_hidden': True})

        self.assertEqual(
            make_client(handler).get_comment('c-9'),
            {'id': 'c-9', 'is_hidden': True})

    def test_reply_delete_private_reply(self):
        seen = []

        def handler(request):
            seen.append((request.method, str(request.url)))
            return httpx.Response(200, json={'id': 'x'})

        client = make_client(handler)
        client.reply_to_comment(comment_id='c1', message='Merci')
        client.delete_comment(comment_id='c1')
        client.private_reply(comment_id='c1', message='Bonjour en privé')
        methods = [m for m, _ in seen]
        self.assertIn('DELETE', methods)
        self.assertTrue(any(u.endswith('/c1/comments') for _, u in seen))
        self.assertTrue(any(u.endswith('/c1/private_replies') for _, u in seen))


# ── Services : cycle propose→approuve→applique + read-back ───────────────────
class CommentServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cmt Co', slug='cmt-co')
        self.user = User.objects.create_user(
            username='cmt-approver', password='x', company=self.company)
        self.comment = CommentMirror.objects.create(
            company=self.company, meta_id='c-1', message='Bonjour',
            created_time=timezone.now())

    def _cycle(self, action, client):
        services.approve_action(action, user=self.user)
        services.apply_action(action, client=client)
        action.refresh_from_db()
        return action

    def test_hide_readback_confirms_sets_verified_badge(self):
        action = services.propose_hide_comment(
            self.company, comment=self.comment, hidden=True)
        self.assertEqual(action.kind, services.KIND_HIDE_COMMENT)
        self.assertIn(services.WARN_COMMENT_HIDE_READBACK,
                      action.payload['warnings'])

        client = Mock()
        client.hide_comment.return_value = {'success': True}
        # Read-back CONFIRME (is_hidden=True == demandé).
        client.get_comment.return_value = {'id': 'c-1', 'is_hidden': True}
        action = self._cycle(action, client)

        # Le read-back est fait AVANT de conclure : get_comment appelé.
        client.hide_comment.assert_called_once_with(comment_id='c-1', hidden=True)
        client.get_comment.assert_called_once_with('c-1')
        self.assertTrue(action.result['verified'])
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_hidden)
        self.assertTrue(self.comment.hidden_verified)  # badge « caché-vérifié »

    def test_hide_readback_mismatch_leaves_unverified(self):
        action = services.propose_hide_comment(
            self.company, comment=self.comment, hidden=True)
        client = Mock()
        client.hide_comment.return_value = {'success': True}
        # Meta a répondu OK au POST mais le re-GET montre TOUJOURS visible
        # (bug connu) → jamais un faux « vérifié ».
        client.get_comment.return_value = {'id': 'c-1', 'is_hidden': False}
        action = self._cycle(action, client)
        self.assertFalse(action.result['verified'])
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.hidden_verified)

    def test_reply_marks_answered(self):
        action = services.propose_reply_comment(
            self.company, comment=self.comment, message='Merci !')
        client = Mock()
        client.reply_to_comment.return_value = {'id': 'reply-1'}
        action = self._cycle(action, client)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.answered)

    def test_delete_removes_mirror(self):
        action = services.propose_delete_comment(
            self.company, comment=self.comment)
        client = Mock()
        client.delete_comment.return_value = {'success': True}
        self._cycle(action, client)
        self.assertFalse(
            CommentMirror.objects.filter(meta_id='c-1').exists())

    # ── Réponse privée : garde « une seule / 7 j » ──
    def test_private_reply_success_then_second_refused(self):
        action = services.propose_private_reply(
            self.company, comment=self.comment, message='DM')
        client = Mock()
        client.private_reply.return_value = {'id': 'pr-1'}
        self._cycle(action, client)
        self.comment.refresh_from_db()
        self.assertIsNotNone(self.comment.private_reply_sent_at)
        # 2e proposition REFUSÉE (aucune action créée).
        before = EngineAction.objects.count()
        with self.assertRaises(ValueError):
            services.propose_private_reply(
                self.company, comment=self.comment, message='Encore')
        self.assertEqual(EngineAction.objects.count(), before)

    def test_private_reply_window_expired_refused(self):
        import datetime
        old = CommentMirror.objects.create(
            company=self.company, meta_id='c-old', message='vieux',
            created_time=timezone.now() - datetime.timedelta(days=8))
        with self.assertRaises(ValueError):
            services.propose_private_reply(
                self.company, comment=old, message='trop tard')

    def test_empty_reply_refused(self):
        with self.assertRaises(ValueError):
            services.propose_reply_comment(
                self.company, comment=self.comment, message='   ')


# ── Moteur mot-clé : dry-run (aucune écriture) puis propose ──────────────────
class KeywordRuleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='KW Co', slug='kw-co')
        CommentKeywordRule.objects.create(
            company=self.company, keyword='arnaque', enabled=True, auto=False)
        self.spam = CommentMirror.objects.create(
            company=self.company, meta_id='c-spam',
            message='Quelle ARNAQUE ce produit')
        self.clean = CommentMirror.objects.create(
            company=self.company, meta_id='c-ok', message='Super installation')
        self.already_hidden = CommentMirror.objects.create(
            company=self.company, meta_id='c-h', message='arnaque bis',
            is_hidden=True)

    def test_dry_run_lists_matches_without_creating_actions(self):
        plan = comments_mod.plan_keyword_hides(self.company)
        ids = {p['comment_id'] for p in plan}
        # Le commentaire spam VISIBLE matche ; le propre non ; le déjà-masqué exclu.
        self.assertIn(self.spam.pk, ids)
        self.assertNotIn(self.clean.pk, ids)
        self.assertNotIn(self.already_hidden.pk, ids)
        # DRY-RUN : STRICTEMENT aucune action créée.
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_propose_creates_propose_mode_actions(self):
        actions = services.propose_keyword_hides(self.company)
        self.assertEqual(len(actions), 1)
        act = actions[0]
        self.assertEqual(act.kind, services.KIND_HIDE_COMMENT)
        self.assertEqual(act.status, EngineAction.Statut.PROPOSEE)
        # Règle en mode PROPOSE (auto=False) → action non-auto (approbation requise).
        self.assertFalse(act.auto)
        self.assertEqual(act.payload['comment_id'], 'c-spam')


# ── Synchro : upsert idempotent + préservation des drapeaux locaux ───────────
class SyncCommentsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sync Co', slug='sync-co')

    def test_sync_upserts_and_preserves_local_flags(self):
        rows = [{
            'id': 'c-1', 'message': 'v1', 'from': {'id': 'u1', 'name': 'Ali'},
            'created_time': '2026-07-10T10:00:00+0000', 'like_count': 2,
            'is_hidden': False, 'can_hide': True, 'can_remove': True,
            'permalink_url': 'https://fb/c1'}]
        mirrors = comments_mod.sync_comments(
            self.company, rows, object_meta_id='post-1', source='post')
        self.assertEqual(len(mirrors), 1)
        m = mirrors[0]
        # Pose un drapeau LOCAL (posé normalement par une action) puis re-synchro.
        m.hidden_verified = True
        m.private_reply_sent_at = timezone.now()
        m.answered = True
        m.save(update_fields=[
            'hidden_verified', 'private_reply_sent_at', 'answered'])

        rows[0]['message'] = 'v2-edited'
        comments_mod.sync_comments(
            self.company, rows, object_meta_id='post-1', source='post')
        m.refresh_from_db()
        # Champ LECTURE écrasé…
        self.assertEqual(m.message, 'v2-edited')
        # …mais les drapeaux LOCAUX intacts (la synchro ne les touche jamais).
        self.assertTrue(m.hidden_verified)
        self.assertIsNotNone(m.private_reply_sent_at)
        self.assertTrue(m.answered)
        self.assertEqual(CommentMirror.objects.count(), 1)  # idempotent

    def test_sync_for_company_covers_posts_and_dark_posts(self):
        from apps.adsengine.tasks import sync_comments_for_company

        PagePostMirror.objects.create(
            company=self.company, meta_id='post-A', created_by_app=True)
        ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-1', name='Ad')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id='cr-1',
            effective_object_story_id='page_dark-1')

        seen_objects = []

        client = Mock()

        def _comments(object_id, **kw):
            seen_objects.append(object_id)
            return [{'id': f'cm-{object_id}', 'message': 'hi'}]

        client.get_object_comments.side_effect = _comments
        total = sync_comments_for_company(self.company, client)
        self.assertEqual(total, 2)
        # A couvert le post organique ET le dark post (effective_object_story_id).
        self.assertIn('post-A', seen_objects)
        self.assertIn('page_dark-1', seen_objects)
