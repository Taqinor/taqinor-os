from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CorbeilleViewSet

router = DefaultRouter()
router.register(r'corbeille', CorbeilleViewSet, basename='corbeille')

urlpatterns = [
    path('', include(router.urls)),
]
