from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityTypeViewSet, ActivityViewSet, AttachmentViewSet,
    CommentViewSet, TaggedItemViewSet, TagViewSet,
    attachments_all, attachments_count,
)

router = DefaultRouter()
router.register(r'activity-types', ActivityTypeViewSet, basename='activity-type')
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'attachments', AttachmentViewSet, basename='attachment')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'tagged-items', TaggedItemViewSet, basename='tagged-item')

urlpatterns = [
    # FG10 — Centre de pièces jointes de la société (toutes, paginées).
    path('attachments/all/', attachments_all, name='attachments-all'),
    path('attachments-count/', attachments_count, name='attachments-count'),
    path('', include(router.urls)),
]
