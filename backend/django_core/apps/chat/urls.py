from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet, MessageViewSet, UserChatStatusViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet,
                basename='chat-conversation')
router.register(r'messages', MessageViewSet, basename='chat-message')
router.register(r'status', UserChatStatusViewSet, basename='chat-status')

urlpatterns = router.urls
