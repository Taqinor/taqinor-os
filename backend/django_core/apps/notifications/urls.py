from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnonceViewSet, HolidayViewSet, NotificationPreferenceViewSet,
    NotificationRoutingRuleViewSet, NotificationViewSet, WhatsAppTemplateViewSet,
    WorkingHoursConfigViewSet,
    attention_summary,
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
# XMKT25 — Registre des gabarits WhatsApp BSP + cycle d'approbation Meta.
router.register(
    r'whatsapp-templates', WhatsAppTemplateViewSet, basename='notification-whatsapp-template')
# XKB5 — Annonces internes ciblées et programmées.
router.register(r'annonces', AnnonceViewSet, basename='notification-annonce')

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
    # VX207 — décompte canonique unique d'attention (cloche/badge sidebar/
    # en-tête Ma file consomment tous ce seul endpoint).
    path('attention-summary/', attention_summary, name='notification-attention-summary'),
]
