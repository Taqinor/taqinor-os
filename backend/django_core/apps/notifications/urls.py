from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    HolidayViewSet, NotificationPreferenceViewSet, NotificationRoutingRuleViewSet,
    NotificationViewSet, WorkingHoursConfigViewSet,
    calendar_check, push_subscribe, push_unsubscribe, vapid_public_key,
)
from .views_whatsapp_bsp import WhatsAppBspWebhookView

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(
    r'preferences', NotificationPreferenceViewSet, basename='notification-preference')
router.register(
    r'routing-rules', NotificationRoutingRuleViewSet, basename='notification-routing-rule')
# FG5 — Calendrier ouvré.
router.register(
    r'working-hours', WorkingHoursConfigViewSet, basename='notification-working-hours')
router.register(
    r'holidays', HolidayViewSet, basename='notification-holiday')

urlpatterns = [
    path('', include(router.urls)),
    # N92 — Web push (PWA) : clé publique VAPID + opt-in/opt-out par appareil.
    path('push/vapid-public-key/', vapid_public_key, name='push-vapid-public-key'),
    path('push/subscribe/', push_subscribe, name='push-subscribe'),
    path('push/unsubscribe/', push_unsubscribe, name='push-unsubscribe'),
    # QJ23 — WhatsApp BSP webhook (Meta verify handshake + statut callbacks).
    # Public (pas de JWT) ; securise par verify_token (GET) et signature HMAC (POST).
    path(
        'whatsapp/webhook/',
        WhatsAppBspWebhookView.as_view(),
        name='whatsapp-bsp-webhook',
    ),
    # FG5 — Diagnostic calendrier ouvré.
    path('calendar/check/', calendar_check, name='notification-calendar-check'),
]
