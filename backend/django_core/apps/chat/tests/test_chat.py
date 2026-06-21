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
    MessageReaction, MessageMention,
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
