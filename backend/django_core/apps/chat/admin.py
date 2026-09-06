from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    Conversation, ConversationMember, Message, MessageAttachment,
    MessageReaction, MessageMention,
)


# ── AUD417 — scope société de TOUTE l'administration de ce module ───────────
# Extension du mixin AUD185 (`core/admin_scoping.py`), déjà appliqué à
# ventes/compta : aucun `ModelAdmin` de ce fichier ne bornait sa liste à
# `request.user.company`, alors que ses modèles portent un FK `company`. Un
# superutilisateur RATTACHÉ À UNE SOCIÉTÉ y voyait — et cherchait par nom —
# les lignes de TOUTES les sociétés clientes simultanément. Le mixin est
# défensif : modèle sans FK `company`, ou compte sans société (opérateur
# plateforme), ⇒ aucun filtre, comportement historique inchangé.
class CompanyScopedAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    """`ModelAdmin` dont la liste est bornée à `request.user.company`."""


@admin.register(Conversation)
class ConversationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'kind', 'name', 'company', 'is_archived',
                    'created_at')
    list_filter = ('kind', 'is_archived')
    search_fields = ('name',)
    raw_id_fields = ('company', 'created_by')


@admin.register(ConversationMember)
class ConversationMemberAdmin(CompanyScopedAdmin):
    list_display = ('id', 'conversation', 'user', 'role', 'is_muted',
                    'last_read_at')
    list_filter = ('role', 'is_muted')
    raw_id_fields = ('conversation', 'user')


@admin.register(Message)
class MessageAdmin(CompanyScopedAdmin):
    list_display = ('id', 'conversation', 'sender', 'kind', 'created_at',
                    'deleted_at', 'pinned_at')
    list_filter = ('kind',)
    search_fields = ('body', 'shared_label')
    raw_id_fields = ('company', 'conversation', 'sender', 'reply_to',
                     'pinned_by', 'shared_content_type')


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(CompanyScopedAdmin):
    list_display = ('id', 'message', 'kind', 'filename', 'mime', 'size',
                    'transcript_status')
    list_filter = ('kind', 'transcript_status')
    raw_id_fields = ('message',)


@admin.register(MessageReaction)
class MessageReactionAdmin(CompanyScopedAdmin):
    list_display = ('id', 'message', 'user', 'emoji', 'created_at')
    raw_id_fields = ('message', 'user')


@admin.register(MessageMention)
class MessageMentionAdmin(CompanyScopedAdmin):
    list_display = ('id', 'message', 'mentioned_user', 'created_at')
    raw_id_fields = ('message', 'mentioned_user')
