from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, stats, meta

router = DefaultRouter()
router.register(r'entries', AuditLogViewSet, basename='audit-entries')

urlpatterns = [
    path('stats/', stats, name='audit-stats'),
    path('meta/', meta, name='audit-meta'),
    path('', include(router.urls)),
]
