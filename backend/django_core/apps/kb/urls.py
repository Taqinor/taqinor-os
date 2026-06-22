from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import KbArticleVersionViewSet, KbArticleViewSet

router = DefaultRouter()
router.register(r'articles', KbArticleViewSet)
router.register(r'versions', KbArticleVersionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
