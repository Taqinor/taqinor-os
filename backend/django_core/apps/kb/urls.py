from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    KbArticleLienViewSet,
    KbArticleVersionViewSet,
    KbArticleViewSet,
)

router = DefaultRouter()
router.register(r'articles', KbArticleViewSet)
router.register(r'versions', KbArticleVersionViewSet)
router.register(r'article-liens', KbArticleLienViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
