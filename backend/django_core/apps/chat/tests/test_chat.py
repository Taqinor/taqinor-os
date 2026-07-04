"""Tests Group S — messagerie interne (« Discuss »).

Couvre :
  * S1 — aller-retour Conversation + Message scopé société ;
  * S2 — pièce jointe/réaction/mention attachées à un Message ;
  * S3 — sérialiseurs/viewsets/permissions : membre liste/poste, non-membre 403,
    cross-tenant 404, company forcée ;
  * S4 — lecture / non-lus ;
  * S5 — recherche scopée société + appartenance (jamais cross-tenant) ;
  * S6 — upload pièce jointe/voix + proxy de téléchargement ;
  * S7 — réactions (toggle) + épingles ;
  * S8 — partage d'un devis/lead (carte + lien), rejet d'un record étranger ;
  * S9 — notifications (in-app) aux membres non en sourdine, mention plus forte.
"""
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.chat.models import (
    Conversation, ConversationMember, Message, MessageAttachment,
    MessageReaction, MessageMention, ThreadFollow,
)
from apps.chat import services

User = get_user_model()


def make_company(slug='chat-co', nom='Chat Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, **kw):
    return User.objects.create_user(
        username=username, password='x', company=company, **kw)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_channel(company, creator, name='general', members=()):
    conv = Conversation.objects.create(
        company=company, kind=Conversation.Kind.CHANNEL, name=name,
        created_by=creator)
    ConversationMember.objects.create(
        conversation=conv, user=creator,
        role=ConversationMember.Role.ADMIN)
    for u in members:
        ConversationMember.objects.create(conversation=conv, user=u)
    return conv


class S1CoreTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')

    def test_conversation_message_roundtrip(self):
        conv = make_channel(self.company, self.alice)
        msg = Message.objects.create(
            company=self.company, conversation=conv, sender=self.alice,
            body='Bonjour équipe')
        self.assertEqual(conv.messages.count(), 1)
        self.assertEqual(msg.company, self.company)
        self.assertEqual(msg.kind, Message.Kind.TEXT)

    def test_company_scoped(self):
        other = make_company(slug='other', nom='Other')
        bob = make_user(other, 'bob')
        make_channel(self.company, self.alice)
        make_channel(other, bob, name='theirs')
        self.assertEqual(
            Conversation.objects.filter(company=self.company).count(), 1)


class S2ExtraModelsTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])
        self.msg = Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            body='@bob regarde')

    def test_attachment_reaction_mention(self):
        att = MessageAttachment.objects.create(
            message=self.msg, kind=MessageAttachment.Kind.VOICE,
            file_key='attachments/x.webm', filename='x.webm',
            mime='audio/webm', size=10,
            transcript_status=MessageAttachment.TranscriptStatus.PENDING)
        rx = MessageReaction.objects.create(
            message=self.msg, user=self.bob, emoji='👍')
        mn = MessageMention.objects.create(
            message=self.msg, mentioned_user=self.bob)
        self.assertEqual(self.msg.attachments.count(), 1)
        self.assertEqual(self.msg.reactions.count(), 1)
        self.assertEqual(self.msg.mentions.count(), 1)
        self.assertEqual(att.transcript_status, 'pending')
        self.assertEqual(rx.emoji, '👍')
        self.assertEqual(mn.mentioned_user, self.bob)


class S3ApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')        # member
        self.carol = make_user(self.company, 'carol')    # non-member
        self.other_co = make_company(slug='other', nom='Other')
        self.evil = make_user(self.other_co, 'evil')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def _post_msg(self, api, conv, body='hi'):
        return api.post(
            f'/api/django/chat/messages/?conversation={conv.id}',
            {'conversation': conv.id, 'body': body}, format='json')

    def test_member_can_list_and_post(self):
        api = auth(self.bob)
        r = self._post_msg(api, self.conv, 'salut')
        self.assertEqual(r.status_code, 201, r.data)
        rl = api.get(f'/api/django/chat/messages/?conversation={self.conv.id}')
        self.assertEqual(rl.status_code, 200)

    def test_non_member_post_403(self):
        api = auth(self.carol)
        r = self._post_msg(api, self.conv)
        self.assertEqual(r.status_code, 403, r.data)

    def test_non_member_list_empty(self):
        api = auth(self.carol)
        rl = api.get(f'/api/django/chat/messages/?conversation={self.conv.id}')
        self.assertEqual(rl.status_code, 200)
        rows = rl.data['results'] if isinstance(rl.data, dict) else rl.data
        self.assertEqual(len(rows), 0)

    def test_cross_tenant_404(self):
        api = auth(self.evil)
        r = self._post_msg(api, self.conv)
        self.assertEqual(r.status_code, 404, r.data)

    def test_create_conversation_forces_company(self):
        api = auth(self.alice)
        r = api.post('/api/django/chat/conversations/', {
            'kind': 'channel', 'name': 'projets',
            'company': self.other_co.id,  # doit être IGNORÉ
            'member_ids': [self.bob.id],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        conv = Conversation.objects.get(pk=r.data['id'])
        self.assertEqual(conv.company, self.company)
        self.assertTrue(conv.members.filter(user=self.alice).exists())
        self.assertTrue(conv.members.filter(user=self.bob).exists())

    def test_edit_own_only(self):
        api = auth(self.bob)
        r = self._post_msg(api, self.conv, 'oops')
        mid = r.data['id']
        # Bob édite le sien : OK
        re = api.patch(f'/api/django/chat/messages/{mid}/',
                       {'body': 'corrigé'}, format='json')
        self.assertEqual(re.status_code, 200, re.data)
        self.assertEqual(re.data['body'], 'corrigé')
        self.assertIsNotNone(re.data['edited_at'])
        # Alice ne peut pas éditer celui de Bob
        ra = auth(self.alice).patch(
            f'/api/django/chat/messages/{mid}/',
            {'body': 'pirate'}, format='json')
        self.assertEqual(ra.status_code, 403)

    def test_soft_delete_own(self):
        api = auth(self.bob)
        mid = self._post_msg(api, self.conv, 'à effacer').data['id']
        rd = api.delete(f'/api/django/chat/messages/{mid}/')
        self.assertEqual(rd.status_code, 204)
        msg = Message.objects.get(pk=mid)
        self.assertIsNotNone(msg.deleted_at)


class S4ReadStateTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def test_unread_and_mark_read(self):
        for i in range(3):
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body=f'm{i}')
        api = auth(self.bob)
        r = api.get('/api/django/chat/conversations/unread/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['total'], 3)
        self.assertEqual(r.data['per_conversation'][str(self.conv.id)]
                         if str(self.conv.id) in r.data['per_conversation']
                         else r.data['per_conversation'][self.conv.id], 3)
        # marque lu → 0
        rm = api.post(f'/api/django/chat/conversations/{self.conv.id}/read/')
        self.assertEqual(rm.status_code, 200)
        r2 = api.get('/api/django/chat/conversations/unread/')
        self.assertEqual(r2.data['total'], 0)


class S5SearchTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.other_co = make_company(slug='other', nom='Other')
        self.evil = make_user(self.other_co, 'evil')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])
        self.foreign = make_channel(self.other_co, self.evil, name='x')
        Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            body='le panneau solaire est arrivé')
        Message.objects.create(
            company=self.other_co, conversation=self.foreign, sender=self.evil,
            body='panneau secret étranger')

    def test_search_scoped(self):
        api = auth(self.bob)
        r = api.get('/api/django/chat/conversations/search/?q=panneau')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertIn('panneau', r.data[0]['snippet'])

    def test_search_never_cross_tenant(self):
        # Bob ne voit jamais le message de l'autre société, même même mot-clé.
        api = auth(self.bob)
        r = api.get('/api/django/chat/conversations/search/?q=secret')
        self.assertEqual(len(r.data), 0)

    def test_search_voice_transcript(self):
        msg = Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            kind=Message.Kind.VOICE)
        MessageAttachment.objects.create(
            message=msg, kind=MessageAttachment.Kind.VOICE,
            file_key='a/v.webm', mime='audio/webm', size=5,
            transcript='rendez-vous demain matin',
            transcript_status='done')
        api = auth(self.bob)
        r = api.get('/api/django/chat/conversations/search/?q=rendez-vous')
        self.assertEqual(len(r.data), 1)


class S6UploadTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.conv = make_channel(self.company, self.alice)

    def _png(self):
        data = (b'\x89PNG\r\n\x1a\n' + b'0' * 32)
        f = io.BytesIO(data)
        f.name = 'pic.png'
        return f

    @patch('apps.chat.views.store_attachment')
    def test_upload_image(self, mock_store):
        mock_store.return_value = ({
            'file_key': 'attachments/abc.png', 'filename': 'pic.png',
            'mime': 'image/png', 'size': 40}, None)
        api = auth(self.alice)
        r = api.post(
            f'/api/django/chat/messages/upload/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'file': self._png()},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        att = r.data['attachments'][0]
        self.assertEqual(att['kind'], 'image')

    @patch('apps.chat.views.store_attachment')
    def test_upload_rejects_bad_type(self, mock_store):
        mock_store.return_value = (None, 'Format non supporté')
        api = auth(self.alice)
        f = io.BytesIO(b'nope')
        f.name = 'x.exe'
        r = api.post(
            f'/api/django/chat/messages/upload/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'file': f}, format='multipart')
        self.assertEqual(r.status_code, 400)

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=False)
    @patch('apps.chat.views.store_attachment')
    def test_voice_disabled_when_off(self, mock_store):
        mock_store.return_value = ({
            'file_key': 'attachments/v.webm', 'filename': 'v.webm',
            'mime': 'audio/webm', 'size': 20}, None)
        api = auth(self.alice)
        f = io.BytesIO(b'\x1aE\xdf\xa3xxxx')
        f.name = 'v.webm'
        r = api.post(
            f'/api/django/chat/messages/upload/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'file': f, 'kind': 'voice'},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        att = MessageAttachment.objects.get(message_id=r.data['id'])
        self.assertEqual(att.kind, 'voice')
        self.assertEqual(att.transcript_status, 'disabled')

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.views.store_attachment')
    def test_voice_pending_when_on(self, mock_store):
        mock_store.return_value = ({
            'file_key': 'attachments/v2.webm', 'filename': 'v2.webm',
            'mime': 'audio/webm', 'size': 20}, None)
        api = auth(self.alice)
        f = io.BytesIO(b'\x1aE\xdf\xa3xxxx')
        f.name = 'v2.webm'
        r = api.post(
            f'/api/django/chat/messages/upload/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'file': f, 'kind': 'voice'},
            format='multipart')
        att = MessageAttachment.objects.get(message_id=r.data['id'])
        self.assertEqual(att.transcript_status, 'pending')

    @patch('apps.chat.views.fetch_attachment')
    @patch('apps.chat.views.store_attachment')
    def test_download_proxy(self, mock_store, mock_fetch):
        mock_store.return_value = ({
            'file_key': 'attachments/abc.png', 'filename': 'pic.png',
            'mime': 'image/png', 'size': 40}, None)
        mock_fetch.return_value = (b'PNGDATA', None)
        api = auth(self.alice)
        up = api.post(
            f'/api/django/chat/messages/upload/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'file': self._png()},
            format='multipart')
        mid = up.data['id']
        aid = up.data['attachments'][0]['id']
        r = api.get(
            f'/api/django/chat/messages/{mid}/attachments/{aid}/download/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'PNGDATA')


class S7ReactionPinTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])
        self.msg = Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            body='important')

    def test_reaction_toggle(self):
        api = auth(self.bob)
        url = f'/api/django/chat/messages/{self.msg.id}/react/'
        r1 = api.post(url, {'emoji': '👍'}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data['status'], 'added')
        self.assertEqual(MessageReaction.objects.filter(
            message=self.msg).count(), 1)
        # idempotent toggle off
        r2 = api.post(url, {'emoji': '👍'}, format='json')
        self.assertEqual(r2.data['status'], 'removed')
        self.assertEqual(MessageReaction.objects.filter(
            message=self.msg).count(), 0)

    def test_pin_unpin(self):
        api = auth(self.bob)
        rp = api.post(f'/api/django/chat/messages/{self.msg.id}/pin/')
        self.assertEqual(rp.status_code, 200)
        self.msg.refresh_from_db()
        self.assertIsNotNone(self.msg.pinned_at)
        # list pinned
        rl = api.get(
            f'/api/django/chat/messages/?conversation={self.conv.id}&pinned=1')
        rows = rl.data['results'] if isinstance(rl.data, dict) else rl.data
        self.assertEqual(len(rows), 1)
        api.post(f'/api/django/chat/messages/{self.msg.id}/unpin/')
        self.msg.refresh_from_db()
        self.assertIsNone(self.msg.pinned_at)

    def test_non_member_cannot_react(self):
        carol = make_user(self.company, 'carol')
        r = auth(carol).post(
            f'/api/django/chat/messages/{self.msg.id}/react/',
            {'emoji': '👍'}, format='json')
        # non-membre de la conversation → message non visible (404) ou 403
        self.assertIn(r.status_code, (403, 404))


class S8ShareRecordTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.conv = make_channel(self.company, self.alice)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ACME', email='acme@example.invalid')
        self.devis = Devis.objects.create(
            company=self.company, reference='DV-1', client=self.client_obj)
        self.lead = Lead.objects.create(company=self.company, nom='Prospect')
        # record d'une autre société
        self.other_co = make_company(slug='other', nom='Other')
        oclient = Client.objects.create(
            company=self.other_co, nom='Foreign',
            email='f@example.invalid')
        self.foreign_devis = Devis.objects.create(
            company=self.other_co, reference='DV-X', client=oclient)

    def test_share_devis(self):
        api = auth(self.alice)
        r = api.post(
            f'/api/django/chat/messages/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'record_type': 'devis',
             'record_id': self.devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn('DV-1', r.data['shared_label'])
        self.assertEqual(r.data['shared_url'], f'/devis/{self.devis.id}')
        msg = Message.objects.get(pk=r.data['id'])
        self.assertEqual(msg.kind, Message.Kind.RECORD)
        self.assertEqual(msg.shared_object_id, self.devis.id)

    def test_share_lead(self):
        api = auth(self.alice)
        r = api.post(
            f'/api/django/chat/messages/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'record_type': 'lead',
             'record_id': self.lead.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn('Prospect', r.data['shared_label'])

    def test_foreign_record_rejected(self):
        api = auth(self.alice)
        r = api.post(
            f'/api/django/chat/messages/?conversation={self.conv.id}',
            {'conversation': self.conv.id, 'record_type': 'devis',
             'record_id': self.foreign_devis.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)


class S9NotificationTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.carol = make_user(self.company, 'carol')
        self.conv = make_channel(
            self.company, self.alice, members=[self.bob, self.carol])

    def _notifs(self, user, event=None):
        from apps.notifications.models import Notification
        qs = Notification.objects.filter(recipient=user)
        if event:
            qs = qs.filter(event_type=event)
        return qs

    def test_message_notifies_other_members(self):
        with patch('apps.notifications.services._dispatch_webpush'), \
                self.captureOnCommitCallbacks(execute=True):
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='bonjour à tous')
        # alice (sender) non notifiée ; bob + carol oui
        self.assertEqual(self._notifs(self.alice).count(), 0)
        self.assertEqual(self._notifs(
            self.bob, 'chat_message').count(), 1)
        self.assertEqual(self._notifs(
            self.carol, 'chat_message').count(), 1)

    def test_mute_suppresses(self):
        ConversationMember.objects.filter(
            conversation=self.conv, user=self.carol).update(is_muted=True)
        with patch('apps.notifications.services._dispatch_webpush'), \
                self.captureOnCommitCallbacks(execute=True):
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='salut')
        self.assertEqual(self._notifs(self.bob).count(), 1)
        self.assertEqual(self._notifs(self.carol).count(), 0)

    def test_mention_fires_chat_mention(self):
        with patch('apps.notifications.services._dispatch_webpush'), \
                self.captureOnCommitCallbacks(execute=True):
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='@bob peux-tu vérifier ?')
        self.assertEqual(
            self._notifs(self.bob, 'chat_mention').count(), 1)
        # carol (non mentionnée) reçoit un chat_message normal
        self.assertEqual(
            self._notifs(self.carol, 'chat_message').count(), 1)
        self.assertTrue(MessageMention.objects.filter(
            mentioned_user=self.bob).exists())

    def test_mention_ids_persist_and_fire(self):
        """S16 — les @mentions explicites (liste d'ids) persistent et déclenchent
        un CHAT_MENTION, en plus de l'analyse du texte."""
        with patch('apps.notifications.services._dispatch_webpush'), \
                self.captureOnCommitCallbacks(execute=True):
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='coucou',
                mention_ids=[self.bob.id])
        self.assertTrue(MessageMention.objects.filter(
            mentioned_user=self.bob).exists())
        self.assertEqual(
            self._notifs(self.bob, 'chat_mention').count(), 1)

    def test_mention_ids_via_api(self):
        api = auth(self.alice)
        with patch('apps.notifications.services._dispatch_webpush'), \
                self.captureOnCommitCallbacks(execute=True):
            r = api.post(
                f'/api/django/chat/messages/?conversation={self.conv.id}',
                {'conversation': self.conv.id, 'body': 'hello',
                 'mentions': [self.bob.id]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(MessageMention.objects.filter(
            message_id=r.data['id'], mentioned_user=self.bob).exists())

    def test_mention_ids_filtered_to_members(self):
        """Un id hors conversation est ignoré (jamais de mention fantôme)."""
        outsider = make_user(self.company, 'dave')
        services.create_message(
            conversation=self.conv, sender=self.alice,
            company=self.company, body='salut',
            mention_ids=[outsider.id])
        self.assertFalse(MessageMention.objects.filter(
            mentioned_user=outsider).exists())


class S9MuteEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.carol = make_user(self.company, 'carol')  # non-membre
        self.other_co = make_company(slug='other', nom='Other')
        self.evil = make_user(self.other_co, 'evil')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def test_mute_sets_member_flag(self):
        api = auth(self.bob)
        r = api.post(f'/api/django/chat/conversations/{self.conv.id}/mute/',
                     {'muted': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        self.assertTrue(member.is_muted)
        # unmute
        r2 = api.post(f'/api/django/chat/conversations/{self.conv.id}/mute/',
                      {'muted': False}, format='json')
        self.assertEqual(r2.status_code, 200)
        member.refresh_from_db()
        self.assertFalse(member.is_muted)

    def test_mute_non_member_404(self):
        # carol n'est pas membre → la conversation n'est pas dans son queryset.
        api = auth(self.carol)
        r = api.post(f'/api/django/chat/conversations/{self.conv.id}/mute/',
                     {'muted': True}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_mute_cross_tenant_404(self):
        api = auth(self.evil)
        r = api.post(f'/api/django/chat/conversations/{self.conv.id}/mute/',
                     {'muted': True}, format='json')
        self.assertEqual(r.status_code, 404)


class S20MemberManagementTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')   # admin (créateur)
        self.bob = make_user(self.company, 'bob')       # membre
        self.dave = make_user(self.company, 'dave')     # à ajouter
        self.other_co = make_company(slug='other', nom='Other')
        self.evil = make_user(self.other_co, 'evil')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def test_admin_adds_members_same_company_only(self):
        api = auth(self.alice)
        r = api.post(
            f'/api/django/chat/conversations/{self.conv.id}/members/',
            {'member_ids': [self.dave.id, self.evil.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(ConversationMember.objects.filter(
            conversation=self.conv, user=self.dave).exists())
        # evil (autre société) ignoré
        self.assertFalse(ConversationMember.objects.filter(
            conversation=self.conv, user=self.evil).exists())

    def test_non_admin_cannot_add(self):
        api = auth(self.bob)
        r = api.post(
            f'/api/django/chat/conversations/{self.conv.id}/members/',
            {'member_ids': [self.dave.id]}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_admin_removes_member(self):
        api = auth(self.alice)
        r = api.delete(
            f'/api/django/chat/conversations/{self.conv.id}'
            f'/members/{self.bob.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(ConversationMember.objects.filter(
            conversation=self.conv, user=self.bob).exists())

    def test_non_admin_cannot_remove(self):
        api = auth(self.bob)
        r = api.delete(
            f'/api/django/chat/conversations/{self.conv.id}'
            f'/members/{self.alice.id}/')
        self.assertEqual(r.status_code, 403)

    def test_member_can_leave(self):
        api = auth(self.bob)
        r = api.post(
            f'/api/django/chat/conversations/{self.conv.id}/leave/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(ConversationMember.objects.filter(
            conversation=self.conv, user=self.bob).exists())

    def test_leave_non_member_404(self):
        carol = make_user(self.company, 'carol')
        api = auth(carol)
        r = api.post(
            f'/api/django/chat/conversations/{self.conv.id}/leave/')
        self.assertEqual(r.status_code, 404)


class XKB24ThreadTests(TestCase):
    """XKB24 — fils de discussion : réponses groupées, suivi, notifications
    ciblées aux suiveurs (jamais tout le canal), boîte Fils."""

    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')   # racine
        self.bob = make_user(self.company, 'bob')        # répondant
        self.carol = make_user(self.company, 'carol')    # membre, ne répond pas
        self.conv = make_channel(
            self.company, self.alice, members=[self.bob, self.carol])
        self.root = Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            body='Message racine')

    def test_reply_groups_under_root_and_counts(self):
        api = auth(self.bob)
        r = api.post(
            f'/api/django/chat/messages/{self.root.id}/reply/',
            {'body': 'Réponse de bob'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.root.replies.count(), 1)

        thread = api.get(f'/api/django/chat/messages/{self.root.id}/thread/')
        self.assertEqual(thread.status_code, 200)
        self.assertEqual(len(thread.data), 1)

        detail = api.get(f'/api/django/chat/messages/{self.root.id}/')
        self.assertEqual(detail.data['reply_count'], 1)

    def test_reply_auto_follows_root_author_and_replier(self):
        services.reply_in_thread(
            root_message=self.root, sender=self.bob, company=self.company,
            body='hop')
        self.assertTrue(ThreadFollow.objects.filter(
            root_message=self.root, user=self.alice).exists())
        self.assertTrue(ThreadFollow.objects.filter(
            root_message=self.root, user=self.bob).exists())

    @patch('apps.notifications.services.notify')
    def test_only_thread_followers_notified_not_whole_channel(self, mock_notify):
        services.reply_in_thread(
            root_message=self.root, sender=self.bob, company=self.company,
            body='réponse')
        notified_users = {call.args[0] for call in mock_notify.call_args_list}
        # alice (racine, auto-suivie) est notifiée ; carol (membre du canal,
        # pas du fil) ne l'est PAS ; bob (auteur) ne se notifie pas lui-même.
        self.assertIn(self.alice, notified_users)
        self.assertNotIn(self.carol, notified_users)
        self.assertNotIn(self.bob, notified_users)

    def test_followed_threads_box_lists_unread(self):
        services.reply_in_thread(
            root_message=self.root, sender=self.bob, company=self.company,
            body='une réponse')
        api = auth(self.alice)
        r = api.get('/api/django/chat/messages/threads/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['root_message_id'], self.root.id)
        self.assertEqual(r.data[0]['unread'], 1)

        api.post(f'/api/django/chat/messages/{self.root.id}/thread-read/')
        r2 = api.get('/api/django/chat/messages/threads/')
        self.assertEqual(r2.data[0]['unread'], 0)

    def test_manual_follow_unfollow(self):
        carol_api = auth(self.carol)
        carol_api.post(
            f'/api/django/chat/messages/{self.root.id}/thread-follow/')
        self.assertTrue(ThreadFollow.objects.filter(
            root_message=self.root, user=self.carol).exists())
        carol_api.post(
            f'/api/django/chat/messages/{self.root.id}/thread-unfollow/')
        self.assertFalse(ThreadFollow.objects.filter(
            root_message=self.root, user=self.carol).exists())

    def test_reply_non_member_403(self):
        other_co = make_company(slug='xkb24-other', nom='Other')
        evil = make_user(other_co, 'evil-xkb24')
        api = auth(evil)
        r = api.post(
            f'/api/django/chat/messages/{self.root.id}/reply/',
            {'body': 'intrus'}, format='json')
        self.assertEqual(r.status_code, 404)


class XKB25NotificationLevelTests(TestCase):
    """XKB25 — niveau de notification à 3 valeurs par conversation."""

    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def test_default_level_is_all_preserves_existing_behavior(self):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        self.assertEqual(member.notification_level, 'all')
        self.assertFalse(member.is_muted)

    def test_set_level_muted_syncs_is_muted(self):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        services.set_notification_level(member, 'muted')
        member.refresh_from_db()
        self.assertEqual(member.notification_level, 'muted')
        self.assertTrue(member.is_muted)

    def test_set_level_all_unsyncs_is_muted(self):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        services.set_notification_level(member, 'muted')
        services.set_notification_level(member, 'all')
        member.refresh_from_db()
        self.assertFalse(member.is_muted)

    def test_invalid_level_rejected(self):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        with self.assertRaises(ValueError):
            services.set_notification_level(member, 'bogus')

    @patch('apps.notifications.services.notify')
    def test_mentions_only_level_filters_plain_messages(self, mock_notify):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        services.set_notification_level(member, 'mentions')
        services.create_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='message ordinaire, pas de mention')
        notified = {call.args[0] for call in mock_notify.call_args_list}
        self.assertNotIn(self.bob, notified)

    @patch('apps.notifications.services.notify')
    def test_mentions_only_level_lets_mention_through(self, mock_notify):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        services.set_notification_level(member, 'mentions')
        services.create_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='@bob regarde ça')
        notified = {call.args[0] for call in mock_notify.call_args_list}
        self.assertIn(self.bob, notified)

    @patch('apps.notifications.services.notify')
    def test_muted_level_blocks_everything_including_mentions(self, mock_notify):
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        services.set_notification_level(member, 'muted')
        services.create_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='@bob urgent')
        notified = {call.args[0] for call in mock_notify.call_args_list}
        self.assertNotIn(self.bob, notified)

    def test_api_notification_level_endpoint(self):
        api = auth(self.bob)
        r = api.post(
            f'/api/django/chat/conversations/{self.conv.id}'
            f'/notification-level/', {'level': 'mentions'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        self.assertEqual(member.notification_level, 'mentions')

    def test_api_notification_level_invalid_rejected(self):
        api = auth(self.bob)
        r = api.post(
            f'/api/django/chat/conversations/{self.conv.id}'
            f'/notification-level/', {'level': 'bogus'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_mute_endpoint_still_syncs_level(self):
        api = auth(self.bob)
        r = api.post(f'/api/django/chat/conversations/{self.conv.id}/mute/',
                     {'muted': True}, format='json')
        self.assertEqual(r.status_code, 200)
        member = ConversationMember.objects.get(
            conversation=self.conv, user=self.bob)
        self.assertEqual(member.notification_level, 'muted')


class XKB26StatusDndTests(TestCase):
    """XKB26 — statut personnalisé + Ne pas déranger."""

    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def test_set_status_visible_to_colleagues(self):
        api = auth(self.bob)
        r = api.post('/api/django/chat/status/me/',
                     {'status_text': 'En déplacement chantier',
                      'status_emoji': '🚗'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

        colleague_api = auth(self.alice)
        r2 = colleague_api.get('/api/django/chat/status/colleagues/')
        self.assertEqual(r2.status_code, 200)
        entry = next(e for e in r2.data if e['user_id'] == self.bob.id)
        self.assertEqual(entry['status_text'], 'En déplacement chantier')
        self.assertEqual(entry['status_emoji'], '🚗')

    def test_dnd_suppresses_push_during_window(self):
        from django.utils import timezone
        from datetime import timedelta
        services.set_dnd(
            self.bob, self.company,
            start=timezone.now() - timedelta(minutes=5),
            end=timezone.now() + timedelta(hours=1))
        with patch('apps.notifications.services.notify') as mock_notify:
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='Bonjour')
            notified = {call.args[0] for call in mock_notify.call_args_list}
            self.assertNotIn(self.bob, notified)

    def test_dnd_lifted_after_window_restores_push(self):
        from django.utils import timezone
        from datetime import timedelta
        services.set_dnd(
            self.bob, self.company,
            start=timezone.now() - timedelta(hours=2),
            end=timezone.now() - timedelta(hours=1))
        with patch('apps.notifications.services.notify') as mock_notify:
            services.create_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='Bonjour')
            notified = {call.args[0] for call in mock_notify.call_args_list}
            self.assertIn(self.bob, notified)

    def test_dnd_invalid_window_rejected(self):
        from django.utils import timezone
        from datetime import timedelta
        with self.assertRaises(ValueError):
            services.set_dnd(
                self.bob, self.company,
                start=timezone.now(),
                end=timezone.now() - timedelta(hours=1))

    def test_api_dnd_roundtrip(self):
        api = auth(self.bob)
        r = api.post('/api/django/chat/status/dnd/', {
            'start': '2026-01-01T22:00:00Z',
            'end': '2026-01-02T06:00:00Z',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNotNone(r.data['dnd_start'])
        # Clear DND.
        r2 = api.post('/api/django/chat/status/dnd/',
                      {'start': None, 'end': None}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertIsNone(r2.data['dnd_start'])

    def test_last_seen_updated_via_polling_endpoint(self):
        api = auth(self.bob)
        r = api.post('/api/django/chat/status/seen/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data['last_seen_at'])

    def test_clear_status(self):
        services.set_status(self.bob, self.company, status_text='Occupé',
                            status_emoji='⛔')
        services.clear_status(self.bob, self.company)
        st = services.get_or_create_status(self.bob, self.company)
        self.assertEqual(st.status_text, '')
        self.assertEqual(st.status_emoji, '')


class XKB27ScheduledRemindersBookmarksTests(TestCase):
    """XKB27 — messages programmés, rappels & signets."""

    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])
        self.msg = Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            body='Message à enregistrer')

    def test_schedule_message_not_sent_before_time(self):
        from django.utils import timezone
        from datetime import timedelta
        future = timezone.now() + timedelta(hours=1)
        sched = services.schedule_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='Plus tard', scheduled_at=future)
        sent = services.sweep_scheduled_messages(now=timezone.now())
        self.assertEqual(sent, 0)
        sched.refresh_from_db()
        self.assertEqual(sched.status, 'pending')
        self.assertEqual(
            self.conv.messages.filter(body='Plus tard').count(), 0)

    def test_schedule_message_sent_at_due_time(self):
        from django.utils import timezone
        from datetime import timedelta
        future = timezone.now() + timedelta(minutes=1)
        sched = services.schedule_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='Plus tard', scheduled_at=future)
        sent = services.sweep_scheduled_messages(
            now=future + timedelta(seconds=1))
        self.assertEqual(sent, 1)
        sched.refresh_from_db()
        self.assertEqual(sched.status, 'sent')
        self.assertIsNotNone(sched.sent_message)
        self.assertEqual(sched.sent_message.body, 'Plus tard')

    def test_schedule_rejects_past_time(self):
        from django.utils import timezone
        from datetime import timedelta
        with self.assertRaises(ValueError):
            services.schedule_message(
                conversation=self.conv, sender=self.alice,
                company=self.company, body='x',
                scheduled_at=timezone.now() - timedelta(hours=1))

    def test_cancel_scheduled_message_before_time(self):
        from django.utils import timezone
        from datetime import timedelta
        future = timezone.now() + timedelta(hours=1)
        sched = services.schedule_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='Annule-moi', scheduled_at=future)
        services.cancel_scheduled_message(sched, self.alice)
        sched.refresh_from_db()
        self.assertEqual(sched.status, 'cancelled')
        sent = services.sweep_scheduled_messages(
            now=future + timedelta(seconds=1))
        self.assertEqual(sent, 0)

    def test_cancel_scheduled_message_wrong_user_forbidden(self):
        from django.utils import timezone
        from datetime import timedelta
        sched = services.schedule_message(
            conversation=self.conv, sender=self.alice, company=self.company,
            body='x', scheduled_at=timezone.now() + timedelta(hours=1))
        with self.assertRaises(PermissionError):
            services.cancel_scheduled_message(sched, self.bob)

    def test_api_scheduled_message_create_and_cancel(self):
        api = auth(self.alice)
        r = api.post('/api/django/chat/scheduled-messages/', {
            'conversation': self.conv.id,
            'body': 'via API',
            'scheduled_at': '2099-01-01T10:00:00Z',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        sched_id = r.data['id']
        r2 = api.delete(f'/api/django/chat/scheduled-messages/{sched_id}/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['status'], 'cancelled')

    @patch('apps.notifications.services.notify')
    def test_reminder_notifies_at_due_time_not_before(self, mock_notify):
        from django.utils import timezone
        from datetime import timedelta
        future = timezone.now() + timedelta(minutes=30)
        services.remind_me(self.msg, self.bob, future)
        sent = services.sweep_reminders(now=timezone.now())
        self.assertEqual(sent, 0)
        mock_notify.assert_not_called()

        sent2 = services.sweep_reminders(now=future + timedelta(seconds=1))
        self.assertEqual(sent2, 1)
        mock_notify.assert_called_once()

    def test_reminder_rejects_past_time(self):
        from django.utils import timezone
        from datetime import timedelta
        with self.assertRaises(ValueError):
            services.remind_me(
                self.msg, self.bob, timezone.now() - timedelta(hours=1))

    def test_bookmark_toggle_list_remove(self):
        api = auth(self.bob)
        r = api.post(f'/api/django/chat/messages/{self.msg.id}/bookmark/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'added')

        r2 = api.get('/api/django/chat/messages/bookmarks/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(r2.data), 1)
        self.assertEqual(r2.data[0]['message'], self.msg.id)

        r3 = api.post(f'/api/django/chat/messages/{self.msg.id}/bookmark/')
        self.assertEqual(r3.data['status'], 'removed')
        r4 = api.get('/api/django/chat/messages/bookmarks/')
        self.assertEqual(len(r4.data), 0)


class XKB28CannedResponseTests(TestCase):
    """XKB28 — réponses enregistrées (snippets) : personnelles privées,
    société partagées."""

    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.other_co = make_company(slug='xkb28-other', nom='Other')
        self.evil = make_user(self.other_co, 'evil-xkb28')

    def test_create_personal_snippet_private_to_owner(self):
        api = auth(self.alice)
        r = api.post('/api/django/chat/canned-responses/', {
            'shortcut': 'salut', 'body': 'Bonjour, comment puis-je aider ?',
            'scope': 'personal',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)

        bob_api = auth(self.bob)
        listing = bob_api.get('/api/django/chat/canned-responses/')
        shortcuts = [c['shortcut'] for c in listing.data]
        self.assertNotIn('salut', shortcuts)

    def test_company_snippet_shared_across_users(self):
        api = auth(self.alice)
        api.post('/api/django/chat/canned-responses/', {
            'shortcut': 'devis', 'body': 'Voici votre devis en pièce jointe.',
            'scope': 'company',
        }, format='json')
        bob_api = auth(self.bob)
        listing = bob_api.get('/api/django/chat/canned-responses/')
        shortcuts = [c['shortcut'] for c in listing.data]
        self.assertIn('devis', shortcuts)

    def test_prefix_autocomplete(self):
        services.create_canned_response(
            self.alice, self.company, shortcut='bonjour', body='Salut',
            scope='personal')
        services.create_canned_response(
            self.alice, self.company, shortcut='byebye', body='Au revoir',
            scope='personal')
        rows = services.visible_canned_responses(
            self.alice, self.company, prefix='bon')
        self.assertEqual([r.shortcut for r in rows], ['bonjour'])

    def test_duplicate_shortcut_same_scope_rejected(self):
        services.create_canned_response(
            self.alice, self.company, shortcut='dup', body='a',
            scope='personal')
        with self.assertRaises(ValueError):
            services.create_canned_response(
                self.alice, self.company, shortcut='dup', body='b',
                scope='personal')

    def test_cross_tenant_never_visible(self):
        services.create_canned_response(
            self.alice, self.company, shortcut='interne', body='x',
            scope='company')
        rows = services.visible_canned_responses(self.evil, self.other_co)
        self.assertEqual(rows, [])

    def test_personal_snippet_delete_owner_only(self):
        canned = services.create_canned_response(
            self.alice, self.company, shortcut='del', body='x',
            scope='personal')
        with self.assertRaises(PermissionError):
            services.delete_canned_response(canned, self.bob)
        services.delete_canned_response(canned, self.alice)  # ne lève pas

    def test_company_snippet_deletable_by_any_member(self):
        canned = services.create_canned_response(
            self.alice, self.company, shortcut='partage', body='x',
            scope='company')
        services.delete_canned_response(canned, self.bob)  # ne lève pas


class XKB30PollTests(TestCase):
    """XKB30 — sondages dans les canaux : créer/voter/clôturer, anonyme
    masque les votants, non-membre 403."""

    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'alice')
        self.bob = make_user(self.company, 'bob')
        self.carol = make_user(self.company, 'carol')  # non-membre
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def test_create_vote_close_flow(self):
        api = auth(self.alice)
        r = api.post('/api/django/chat/messages/poll/', {
            'conversation': self.conv.id,
            'question': 'Date de pose ?',
            'options': ['Lundi', 'Mardi', 'Mercredi'],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        msg_id = r.data['id']
        poll = Message.objects.get(pk=msg_id).poll
        opt_lundi = poll.options.get(label='Lundi')

        bob_api = auth(self.bob)
        r2 = bob_api.post(
            f'/api/django/chat/messages/{msg_id}/poll-vote/',
            {'option_ids': [opt_lundi.id]}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['options'][0]['vote_count'], 1)

        r3 = api.post(f'/api/django/chat/messages/{msg_id}/poll-close/')
        self.assertEqual(r3.status_code, 200)
        poll.refresh_from_db()
        self.assertIsNotNone(poll.closed_at)

        # Vote refusé après clôture.
        r4 = bob_api.post(
            f'/api/django/chat/messages/{msg_id}/poll-vote/',
            {'option_ids': [opt_lundi.id]}, format='json')
        self.assertEqual(r4.status_code, 400)

    def test_anonymous_poll_hides_voters(self):
        poll = services.create_poll(
            conversation=self.conv, sender=self.alice, company=self.company,
            question='Anonyme ?', options=['Oui', 'Non'], is_anonymous=True)
        opt = poll.options.first()
        services.vote_poll(poll, self.bob, [opt.id])
        results = services.poll_results(poll, self.alice)
        self.assertNotIn('voter_ids', results['options'][0])
        self.assertEqual(results['options'][0]['vote_count'], 1)

    def test_non_anonymous_poll_shows_voters(self):
        poll = services.create_poll(
            conversation=self.conv, sender=self.alice, company=self.company,
            question='Public ?', options=['Oui', 'Non'], is_anonymous=False)
        opt = poll.options.first()
        services.vote_poll(poll, self.bob, [opt.id])
        results = services.poll_results(poll, self.alice)
        self.assertIn(self.bob.id, results['options'][0]['voter_ids'])

    def test_non_member_403(self):
        api = auth(self.carol)
        r = api.post('/api/django/chat/messages/poll/', {
            'conversation': self.conv.id,
            'question': 'Q ?', 'options': ['a', 'b'],
        }, format='json')
        self.assertEqual(r.status_code, 403)

    def test_single_choice_rejects_multiple_options(self):
        poll = services.create_poll(
            conversation=self.conv, sender=self.alice, company=self.company,
            question='Un seul ?', options=['A', 'B'], allow_multiple=False)
        opts = list(poll.options.all())
        with self.assertRaises(ValueError):
            services.vote_poll(poll, self.bob, [o.id for o in opts])

    def test_multiple_choice_allows_several(self):
        poll = services.create_poll(
            conversation=self.conv, sender=self.alice, company=self.company,
            question='Plusieurs ?', options=['A', 'B', 'C'],
            allow_multiple=True)
        opts = list(poll.options.all())
        services.vote_poll(poll, self.bob, [opts[0].id, opts[1].id])
        results = services.poll_results(poll)
        counted = sum(o['vote_count'] for o in results['options'])
        self.assertEqual(counted, 2)

    def test_close_poll_non_author_forbidden(self):
        poll = services.create_poll(
            conversation=self.conv, sender=self.alice, company=self.company,
            question='Q ?', options=['a', 'b'])
        with self.assertRaises(PermissionError):
            services.close_poll(poll, self.bob)

    def test_requires_at_least_two_options(self):
        with self.assertRaises(ValueError):
            services.create_poll(
                conversation=self.conv, sender=self.alice,
                company=self.company, question='Q ?', options=['juste une'])
