"""Sérialiseurs de la messagerie interne.

La société est TOUJOURS forcée côté serveur (jamais lue du corps de requête) —
voir les viewsets. Les sérialiseurs n'exposent jamais `company` en écriture.
"""
from rest_framework import serializers

from .models import (
    Conversation, ConversationMember, Message, MessageAttachment,
    MessageReaction, MessageMention,
)


class UserMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(required=False, default='')
    full_name = serializers.SerializerMethodField()
    email = serializers.CharField(required=False, default='')

    def get_full_name(self, obj):
        fn = getattr(obj, 'get_full_name', None)
        return fn() if callable(fn) else ''


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'message', 'file_key', 'filename', 'mime', 'size', 'kind',
            'duration_s', 'transcript', 'transcript_lang', 'transcript_status',
            'created_at',
        ]
        read_only_fields = fields


class MessageReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageReaction
        fields = ['id', 'message', 'user', 'emoji', 'created_at']
        read_only_fields = ['id', 'message', 'user', 'created_at']


class MessageMentionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageMention
        fields = ['id', 'message', 'mentioned_user', 'created_at']
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    reactions = MessageReactionSerializer(many=True, read_only=True)
    sender_detail = serializers.SerializerMethodField()
    shared_url = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_detail', 'body', 'kind',
            'reply_to', 'created_at', 'edited_at', 'deleted_at',
            'pinned_at', 'pinned_by', 'is_pinned',
            'shared_object_id', 'shared_label', 'shared_url',
            'attachments', 'reactions', 'reply_count',
        ]
        # `conversation` est fourni par l'URL/le contexte, pas par le corps.
        read_only_fields = [
            'id', 'sender', 'kind', 'created_at', 'edited_at', 'deleted_at',
            'pinned_at', 'pinned_by', 'shared_object_id', 'shared_label',
            'attachments', 'reactions', 'reply_count',
        ]

    def get_reply_count(self, obj):
        # XKB24 — compteur de réponses sous le message parent (fil).
        from .services import thread_reply_count
        return thread_reply_count(obj)

    def get_sender_detail(self, obj):
        if obj.sender_id is None:
            return None
        return UserMiniSerializer(obj.sender).data

    def get_is_pinned(self, obj):
        return obj.pinned_at is not None

    def get_shared_url(self, obj):
        # L'URL n'est PAS stockée (le snapshot l'est) ; on la recalcule à la
        # volée par société via les sélecteurs cibles, en lecture seule.
        if not obj.shared_object_id or obj.shared_content_type_id is None:
            return ''
        try:
            ct = obj.shared_content_type
            from .services import _record_card
            rt = {'lead': 'lead', 'devis': 'devis',
                  'installation': 'chantier'}.get(ct.model)
            if not rt:
                return ''
            card = _record_card(rt, obj.shared_object_id, obj.company)
            return (card or {}).get('url', '') if card else ''
        except Exception:
            return ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.deleted_at is not None:
            # Message supprimé : on masque le corps/les pièces jointes.
            data['body'] = ''
            data['attachments'] = []
            data['shared_label'] = ''
        return data


class ConversationMemberSerializer(serializers.ModelSerializer):
    user_detail = serializers.SerializerMethodField()

    class Meta:
        model = ConversationMember
        fields = [
            'id', 'conversation', 'user', 'user_detail', 'role',
            'last_read_at', 'is_muted', 'notification_level', 'joined_at',
        ]
        read_only_fields = ['id', 'conversation', 'joined_at']

    def get_user_detail(self, obj):
        if obj.user_id is None:
            return None
        return UserMiniSerializer(obj.user).data


class ConversationSerializer(serializers.ModelSerializer):
    members = ConversationMemberSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    # Écriture seule : liste d'IDs d'utilisateurs à ajouter à la création.
    member_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Conversation
        fields = [
            'id', 'kind', 'name', 'created_by', 'is_archived',
            'created_at', 'updated_at', 'members', 'member_ids',
            'last_message', 'unread_count',
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at', 'members',
        ]

    def get_last_message(self, obj):
        msg = (obj.messages.filter(deleted_at__isnull=True)
               .order_by('-created_at', '-id').first())
        if msg is None:
            return None
        from .services import _preview
        return {
            'id': msg.id,
            'preview': _preview(msg),
            'kind': msg.kind,
            'created_at': msg.created_at,
            'sender': msg.sender_id,
        }

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request is None:
            return 0
        member = obj.members.filter(user=request.user).first()
        if member is None:
            return 0
        from .services import unread_count
        return unread_count(obj, member)
