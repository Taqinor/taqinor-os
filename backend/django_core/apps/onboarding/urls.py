from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    OnboardingItemsMasquesViewSet, OnboardingProgressViewSet,
    ProductTourViewSet,
)

router = DefaultRouter()
router.register(r'progress', OnboardingProgressViewSet, basename='onboarding-progress')
router.register(r'tours', ProductTourViewSet, basename='onboarding-tours')
# NTDMO28 — masquage par société d'items du catalogue (Paramètres).
router.register(r'items-masques', OnboardingItemsMasquesViewSet, basename='onboarding-items-masques')

urlpatterns = [
    path('', include(router.urls)),
]
