from django.contrib import admin

from .models import (
    Conversation, ConversationMember, Message, MessageAttachment,
    MessageReaction, MessageMention,
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'name', 'company', 'is_archived',
                    'created_at')
    list_filter = ('kind', 'is_archived')
    search_fields = ('name',)
    raw_id_fields = ('company', 'created_by')


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'role', 'is_muted',
                    'last_read_at')
    list_filter = ('role', 'is_muted')
    raw_id_fields = ('conversation', 'user')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'kind', 'created_at',
                    'deleted_at', 'pinned_at')
    list_filter = ('kind',)
    search_fields = ('body', 'shared_label')
    raw_id_fields = ('company', 'conversation', 'sender', 'reply_to',
                     'pinned_by', 'shared_content_type')


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'kind', 'filename', 'mime', 'size',
                    'transcript_status')
    list_filter = ('kind', 'transcript_status')
    raw_id_fields = ('message',)


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'user', 'emoji', 'created_at')
    raw_id_fields = ('message', 'user')


@admin.register(MessageMention)
class MessageMentionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'mentioned_user', 'created_at')
    raw_id_fields = ('message', 'mentioned_user')
