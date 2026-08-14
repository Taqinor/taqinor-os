from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OnboardingProgressViewSet, ProductTourViewSet

router = DefaultRouter()
router.register(r'progress', OnboardingProgressViewSet, basename='onboarding-progress')
router.register(r'tours', ProductTourViewSet, basename='onboarding-tours')

urlpatterns = [
    path('', include(router.urls)),
]
