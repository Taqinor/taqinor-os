from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AuditLogViewSet, stats, meta, security_events, security_events_export,
    object_as_of, object_history,
)
from .analytics import audit_analytics

router = DefaultRouter()
router.register(r'entries', AuditLogViewSet, basename='audit-entries')

urlpatterns = [
    path('stats/', stats, name='audit-stats'),
    path('meta/', meta, name='audit-meta'),
    # FG23 — onglet « Sécurité » : évènements de sécurité (connexion/échec/alerte)
    path('security/', security_events, name='audit-security'),
    # NTSEC15 — export CSV des évènements de sécurité (Directeur only).
    path('security/export/', security_events_export,
         name='audit-security-export'),
    # FG97 — rollups analytiques du journal (utilisateurs, mix actions, churn)
    path('analytics/', audit_analytics, name='audit-analytics'),
    # YHARD3 — reconstruction as-of générique (content_type = "app_label.model")
    path('objets/<str:content_type>/<str:object_id>/as-of/',
         object_as_of, name='audit-object-as-of'),
    # VX243(b) — historique record-scopé d'UN objet (propriétaire OU Journal).
    path('objets/<str:content_type>/<str:object_id>/history/',
         object_history, name='audit-object-history'),
    path('', include(router.urls)),
]
