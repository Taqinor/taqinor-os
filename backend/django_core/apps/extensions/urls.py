from django.urls import path

from .views import ExtensionPackageCatalogueView, JournalPlateformeView

urlpatterns = [
    path('catalogue/', ExtensionPackageCatalogueView.as_view(),
         name='extension-package-catalogue'),
    # NTEXT25 — journal unifié des exécutions de la plateforme (admin).
    path('journal/', JournalPlateformeView.as_view(),
         name='extension-journal'),
]
