from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityTypeViewSet, ActivityViewSet, AttachmentViewSet,
    CommentViewSet, attachments_count,
)

router = DefaultRouter()
router.register(r'activity-types', ActivityTypeViewSet, basename='activity-type')
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'attachments', AttachmentViewSet, basename='attachment')
router.register(r'comments', CommentViewSet, basename='comment')

urlpatterns = [
    path('attachments-count/', attachments_count, name='attachments-count'),
    path('', include(router.urls)),
]
