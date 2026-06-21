"""Vues de la messagerie interne (« Discuss »).

MULTI-TENANT STRICT : tout queryset est filtré à `request.user.company` ET aux
conversations dont l'utilisateur est membre. Cross-tenant → 404 (jamais révélé) ;
non-membre d'une conversation de sa société → 403.
"""
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.records.storage import (
    fetch_attachment, store_attachment,
)

from . import services
from .models import (
    Conversation, ConversationMember, Message, MessageAttachment,
    MessageReaction,
)
from .permissions import IsConversationMember, is_member
from .selectors import member_conversation_ids, search_messages
from .serializers import (
    ConversationSerializer, MessageSerializer,
)


def _company(request):
    return request.user.company if request.user.company_id else None


def _transcription_enabled():
    from django.conf import settings
    return bool(getattr(settings, 'CHAT_TRANSCRIPTION_ENABLED', False))


class ConversationViewSet(viewsets.ModelViewSet):
    """Conversations de l'utilisateur (DM + canaux) — scopées société +
    appartenance."""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = _company(self.request)
        if company is None:
            return Conversation.objects.none()
        ids = member_conversation_ids(self.request.user, company)
        qs = Conversation.objects.filter(company=company, id__in=ids)
        if self.request.query_params.get('archived') == '1':
            qs = qs.filter(is_archived=True)
        else:
            qs = qs.filter(is_archived=False)
        return qs.prefetch_related('members', 'members__user').distinct()

    def perform_create(self, serializer):
        company = _company(self.request)
        member_ids = serializer.validated_data.pop('member_ids', [])
        conv = serializer.save(
            company=company, created_by=self.request.user)
        # Le créateur est toujours membre admin.
        ConversationMember.objects.get_or_create(
            conversation=conv, user=self.request.user,
            defaults={'role': ConversationMember.Role.ADMIN})
        # Ajoute les membres demandés — UNIQUEMENT de la même société.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for uid in member_ids:
            u = User.objects.filter(pk=uid, company=company).first()
            if u is not None and u.pk != self.request.user.pk:
                ConversationMember.objects.get_or_create(
                    conversation=conv, user=u)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        conv = self.get_object()
        conv.is_archived = True
        conv.save(update_fields=['is_archived'])
        return Response(self.get_serializer(conv).data)

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        """S4 — avance last_read_at à maintenant pour le membre courant."""
        conv = self.get_object()
        services.mark_read(conv, request.user)
        return Response({'status': 'ok'})

    @action(detail=False, methods=['get'], url_path='unread')
    def unread(self, request):
        """S4 — compteurs de non-lus par conversation + total (badge)."""
        company = _company(request)
        return Response(services.unread_summary(request.user, company))

    # ── S9 — sourdine par conversation ────────────────────────────────
    @action(detail=True, methods=['post'], url_path='mute')
    def mute(self, request, pk=None):
        """Active/désactive la sourdine de la conversation pour le membre
        courant. Body : {muted: bool}. Scopé société + appartenance."""
        conv = self.get_object()  # déjà scopé société (cross-tenant → 404)
        member = ConversationMember.objects.filter(
            conversation=conv, user=request.user).first()
        if member is None:
            return Response(
                {'detail': "Vous n'êtes pas membre de cette conversation."},
                status=status.HTTP_403_FORBIDDEN)
        muted = request.data.get('muted')
        member.is_muted = bool(muted) if muted is not None else True
        member.save(update_fields=['is_muted'])
        return Response(self.get_serializer(conv).data)

    # ── S20 — gestion des membres d'un canal ──────────────────────────
    def _require_admin(self, conv):
        """Retourne le membre admin courant, ou None si non-admin/non-membre."""
        return ConversationMember.objects.filter(
            conversation=conv, user=self.request.user,
            role=ConversationMember.Role.ADMIN).first()

    @action(detail=True, methods=['post'], url_path='members')
    def add_members(self, request, pk=None):
        """Ajoute des membres au canal (admin seulement, même société)."""
        conv = self.get_object()
        if self._require_admin(conv) is None:
            return Response(
                {'detail': 'Action réservée aux administrateurs du canal.'},
                status=status.HTTP_403_FORBIDDEN)
        company = _company(request)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        member_ids = request.data.get('member_ids') or []
        for uid in member_ids:
            u = User.objects.filter(pk=uid, company=company).first()
            if u is not None:
                ConversationMember.objects.get_or_create(
                    conversation=conv, user=u)
        return Response(self.get_serializer(conv).data)

    @action(detail=True, methods=['delete'],
            url_path='members/(?P<user_id>[0-9]+)')
    def remove_member(self, request, pk=None, user_id=None):
        """Retire un membre du canal (admin seulement)."""
        conv = self.get_object()
        if self._require_admin(conv) is None:
            return Response(
                {'detail': 'Action réservée aux administrateurs du canal.'},
                status=status.HTTP_403_FORBIDDEN)
        ConversationMember.objects.filter(
            conversation=conv, user_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='leave')
    def leave(self, request, pk=None):
        """Le membre courant quitte la conversation."""
        conv = self.get_object()
        ConversationMember.objects.filter(
            conversation=conv, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """S5 — recherche scopée société + appartenance."""
        company = _company(request)
        q = request.query_params.get('q', '')
        rows = search_messages(request.user, company, q)
        out = []
        for m in rows:
            body = m.body or ''
            idx = body.lower().find(q.lower()) if q else -1
            if idx >= 0:
                start = max(0, idx - 30)
                snippet = ('…' if start > 0 else '') + body[start:idx + 60]
            else:
                snippet = body[:90]
            out.append({
                'message_id': m.id,
                'conversation': m.conversation_id,
                'conversation_name': (m.conversation.name
                                      or f'Conversation {m.conversation_id}'),
                'sender': m.sender_id,
                'snippet': snippet,
                'created_at': m.created_at,
            })
        return Response(out)


class MessageViewSet(viewsets.ModelViewSet):
    """Messages d'une conversation — listés newest-first, paginés.

    L'appartenance est vérifiée pour CHAQUE action : un non-membre est 403, une
    conversation cross-tenant est 404."""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]

    def _conversation(self):
        """Conversation cible scopée société, ou None (→ 404)."""
        company = _company(self.request)
        if company is None:
            return None
        cid = (self.request.query_params.get('conversation')
               or self.request.data.get('conversation'))
        if not cid:
            return None
        return Conversation.objects.filter(pk=cid, company=company).first()

    def get_queryset(self):
        company = _company(self.request)
        if company is None:
            return Message.objects.none()
        ids = member_conversation_ids(self.request.user, company)
        qs = Message.objects.filter(
            company=company, conversation_id__in=ids
        ).select_related('sender', 'conversation', 'pinned_by').prefetch_related(
            'attachments', 'reactions')
        cid = self.request.query_params.get('conversation')
        if cid:
            qs = qs.filter(conversation_id=cid)
        if self.request.query_params.get('pinned') == '1':
            qs = qs.filter(pinned_at__isnull=False)
        return qs.order_by('-created_at', '-id')

    def create(self, request, *args, **kwargs):
        company = _company(request)
        conv = self._conversation()
        if conv is None:
            return Response({'detail': 'Conversation introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if not is_member(request.user, conv):
            return Response(
                {'detail': "Vous n'êtes pas membre de cette conversation."},
                status=status.HTTP_403_FORBIDDEN)
        reply_to = None
        rid = request.data.get('reply_to')
        if rid:
            reply_to = Message.objects.filter(
                pk=rid, conversation=conv).first()
        try:
            msg = services.create_message(
                conversation=conv, sender=request.user, company=company,
                body=request.data.get('body', ''),
                reply_to=reply_to,
                record_type=request.data.get('record_type'),
                record_id=request.data.get('record_id'),
                mention_ids=request.data.get('mentions'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(msg).data,
                        status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        msg = self.get_object()
        if msg.sender_id != request.user.pk:
            return Response(
                {'detail': 'Vous ne pouvez modifier que vos messages.'},
                status=status.HTTP_403_FORBIDDEN)
        if msg.deleted_at is not None:
            return Response({'detail': 'Message supprimé.'},
                            status=status.HTTP_400_BAD_REQUEST)
        body = request.data.get('body')
        if body is not None:
            msg.body = body
            msg.edited_at = timezone.now()
            msg.save(update_fields=['body', 'edited_at'])
        return Response(self.get_serializer(msg).data)

    def destroy(self, request, *args, **kwargs):
        msg = self.get_object()
        if msg.sender_id != request.user.pk:
            return Response(
                {'detail': 'Vous ne pouvez supprimer que vos messages.'},
                status=status.HTTP_403_FORBIDDEN)
        msg.deleted_at = timezone.now()
        msg.save(update_fields=['deleted_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── S6 — pièces jointes & mémos vocaux ────────────────────────────
    @action(detail=False, methods=['post'], url_path='upload',
            parser_classes=[MultiPartParser])
    def upload(self, request):
        """Téléverse une pièce jointe (image/fichier/voix) et crée un message la
        portant. Réutilise `records.storage.store_attachment` (10 Mo, types
        validés). Voix → kind=voice, transcript_status=pending (ou disabled)."""
        company = _company(request)
        conv = self._conversation()
        if conv is None:
            return Response({'detail': 'Conversation introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if not is_member(request.user, conv):
            return Response(
                {'detail': "Vous n'êtes pas membre de cette conversation."},
                status=status.HTTP_403_FORBIDDEN)
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        is_voice = (request.data.get('kind') == 'voice'
                    or request.data.get('voice') in ('1', 'true', 'True'))
        meta, err = store_attachment(f, audio=is_voice)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)

        if is_voice:
            att_kind = MessageAttachment.Kind.VOICE
        elif (meta.get('mime') or '').startswith('image/'):
            att_kind = MessageAttachment.Kind.IMAGE
        else:
            att_kind = MessageAttachment.Kind.FILE

        msg_kind = (Message.Kind.VOICE if is_voice else Message.Kind.TEXT)
        msg = services.create_message(
            conversation=conv, sender=request.user, company=company,
            body=request.data.get('body', ''), kind=msg_kind)

        ts = ''
        if is_voice:
            ts = (MessageAttachment.TranscriptStatus.PENDING
                  if _transcription_enabled()
                  else MessageAttachment.TranscriptStatus.DISABLED)
        duration = request.data.get('duration_s')
        MessageAttachment.objects.create(
            message=msg, kind=att_kind, transcript_status=ts,
            duration_s=(int(duration) if duration else None), **meta)
        return Response(self.get_serializer(msg).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'],
            url_path='attachments/(?P<att_id>[0-9]+)/download')
    def download_attachment(self, request, pk=None, att_id=None):
        """Proxy même-origine pour servir une pièce jointe (comme records)."""
        msg = self.get_object()  # déjà scopé société + appartenance
        att = MessageAttachment.objects.filter(
            pk=att_id, message=msg).first()
        if att is None:
            return Response({'detail': 'Pièce jointe introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        data, err = fetch_attachment(att.file_key)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(
            data, content_type=att.mime or 'application/octet-stream')
        safe = (att.filename or 'fichier').replace('"', '')
        resp['Content-Disposition'] = f'inline; filename="{safe}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

    # ── S7 — réactions & épingles ─────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='react')
    def react(self, request, pk=None):
        """Toggle d'une réaction emoji (unique par user+emoji)."""
        msg = self.get_object()
        emoji = (request.data.get('emoji') or '').strip()
        if not emoji:
            return Response({'detail': 'Emoji requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        existing = MessageReaction.objects.filter(
            message=msg, user=request.user, emoji=emoji).first()
        if existing is not None:
            existing.delete()
            toggled = 'removed'
        else:
            MessageReaction.objects.create(
                message=msg, user=request.user, emoji=emoji)
            toggled = 'added'
        return Response({'status': toggled,
                         'message': self.get_serializer(msg).data})

    @action(detail=True, methods=['post'], url_path='pin')
    def pin(self, request, pk=None):
        """Épingle un message (member-can-pin v1)."""
        msg = self.get_object()
        if msg.pinned_at is None:
            msg.pinned_at = timezone.now()
            msg.pinned_by = request.user
            msg.save(update_fields=['pinned_at', 'pinned_by'])
        return Response(self.get_serializer(msg).data)

    @action(detail=True, methods=['post'], url_path='unpin')
    def unpin(self, request, pk=None):
        msg = self.get_object()
        if msg.pinned_at is not None:
            msg.pinned_at = None
            msg.pinned_by = None
            msg.save(update_fields=['pinned_at', 'pinned_by'])
        return Response(self.get_serializer(msg).data)

    def get_permissions(self):
        # Les actions au niveau objet exigent l'appartenance.
        if self.action in ('partial_update', 'update', 'destroy', 'react',
                           'pin', 'unpin', 'download_attachment', 'retrieve'):
            return [IsAuthenticated(), IsConversationMember()]
        return [IsAuthenticated()]
