from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, stats, meta, security_events
from .analytics import audit_analytics

router = DefaultRouter()
router.register(r'entries', AuditLogViewSet, basename='audit-entries')

urlpatterns = [
    path('stats/', stats, name='audit-stats'),
    path('meta/', meta, name='audit-meta'),
    # FG23 — onglet « Sécurité » : évènements de sécurité (connexion/échec/alerte)
    path('security/', security_events, name='audit-security'),
    # FG97 — rollups analytiques du journal (utilisateurs, mix actions, churn)
    path('analytics/', audit_analytics, name='audit-analytics'),
    path('', include(router.urls)),
]
