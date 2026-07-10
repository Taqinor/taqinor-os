from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TiersViewSet

router = DefaultRouter()
router.register(r'tiers', TiersViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
