from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OnboardingProgressViewSet

router = DefaultRouter()
router.register(r'progress', OnboardingProgressViewSet, basename='onboarding-progress')

urlpatterns = [
    path('', include(router.urls)),
]
