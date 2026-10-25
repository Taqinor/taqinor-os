from django.urls import include, path
from rest_framework.routers import DefaultRouter

from authentication.corps_requetes import exiger_corps

from .views import (
    ActivityTypeViewSet, ActivityViewSet, AttachmentViewSet,
    CommentViewSet, FollowerViewSet, TaggedItemViewSet, TagViewSet,
    attachments_all, attachments_count,
)

# api-fuzz-full 25/10 — le corps de création n'a plus de champ requis (type facultatif) :
# il est publié OBLIGATOIRE, comme la vue le contrôle (« Corps JSON obligatoire. »).
exiger_corps(ActivityViewSet.create)

router = DefaultRouter()
router.register(r'activity-types', ActivityTypeViewSet, basename='activity-type')
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'attachments', AttachmentViewSet, basename='attachment')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'tagged-items', TaggedItemViewSet, basename='tagged-item')
router.register(r'followers', FollowerViewSet, basename='follower')

urlpatterns = [
    # FG10 — Centre de pièces jointes de la société (toutes, paginées).
    path('attachments/all/', attachments_all, name='attachments-all'),
    path('attachments-count/', attachments_count, name='attachments-count'),
    path('', include(router.urls)),
]
