from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import VoteIdeeViewSet

router = DefaultRouter()
router.register(r'votes', VoteIdeeViewSet, basename='vote-idee')

urlpatterns = [
    path('', include(router.urls)),
]
