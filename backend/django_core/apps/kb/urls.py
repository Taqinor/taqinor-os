from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    KbArticleAclViewSet,
    KbArticleLienViewSet,
    KbArticleVersionViewSet,
    KbArticleViewSet,
    KbLectureObligatoireViewSet,
)

router = DefaultRouter()
router.register(r'articles', KbArticleViewSet)
router.register(r'versions', KbArticleVersionViewSet)
router.register(r'article-liens', KbArticleLienViewSet)
router.register(r'article-acls', KbArticleAclViewSet)
router.register(r'lectures-obligatoires', KbLectureObligatoireViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
