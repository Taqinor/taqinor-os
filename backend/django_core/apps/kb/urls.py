from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import KbArticleViewSet

router = DefaultRouter()
router.register(r'articles', KbArticleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
