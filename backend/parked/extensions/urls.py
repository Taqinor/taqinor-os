from django.urls import path

from .views import (
    ExtensionPackageCatalogueView,
    JournalPlateformeView,
    StatistiquesPlateformeView,
)

urlpatterns = [
    path('catalogue/', ExtensionPackageCatalogueView.as_view(),
         name='extension-package-catalogue'),
    # NTEXT25 — journal unifié des exécutions de la plateforme (admin).
    path('journal/', JournalPlateformeView.as_view(),
         name='extension-journal'),
    # NTEXT40 — statistiques d'usage de la plateforme (cockpit admin).
    path('statistiques/', StatistiquesPlateformeView.as_view(),
         name='extension-statistiques'),
]
