from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    OnboardingItemsMasquesViewSet, OnboardingProgressViewSet,
    OnboardingTextesExportView, OnboardingTextesImportView, ProductTourViewSet,
)

router = DefaultRouter()
router.register(r'progress', OnboardingProgressViewSet, basename='onboarding-progress')
router.register(r'tours', ProductTourViewSet, basename='onboarding-tours')
# NTDMO28 — masquage par société d'items du catalogue (Paramètres).
router.register(r'items-masques', OnboardingItemsMasquesViewSet, basename='onboarding-items-masques')

urlpatterns = [
    # NTDMO36 — textes FR (tours + checklist) : export/réimport CSV, admin.
    path('export-textes.csv', OnboardingTextesExportView.as_view(),
         name='onboarding-export-textes'),
    path('import-textes.csv', OnboardingTextesImportView.as_view(),
         name='onboarding-import-textes'),
    path('', include(router.urls)),
]
