from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ConversationViewSet, MessageViewSet, UserChatStatusViewSet,
    ScheduledMessageViewSet, CannedResponseViewSet, RetentionPolicyViewSet,
    MessageReminderViewSet, inbound_email_webhook,
)

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet,
                basename='chat-conversation')
router.register(r'messages', MessageViewSet, basename='chat-message')
router.register(r'status', UserChatStatusViewSet, basename='chat-status')
router.register(r'scheduled-messages', ScheduledMessageViewSet,
                basename='chat-scheduled-message')
router.register(r'canned-responses', CannedResponseViewSet,
                basename='chat-canned-response')
router.register(r'retention-policies', RetentionPolicyViewSet,
                basename='chat-retention-policy')
# AUDV28 — lecture + annulation d'un rappel, creator-only (la création reste
# messages/<id>/remind-me/).
router.register(r'reminders', MessageReminderViewSet,
                basename='chat-message-reminder')

from .views_transcription import transcrire  # noqa: E402  (NTMOB30)

urlpatterns = router.urls + [
    path('inbound-email/', inbound_email_webhook,
         name='chat-inbound-email-webhook'),
    # NTMOB30 — transcription vocale synchrone et générique (notes terrain).
    path('transcrire/', transcrire, name='chat-transcrire'),
]
