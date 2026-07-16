from django.urls import path

from .views import ExtensionPackageCatalogueView

urlpatterns = [
    path('catalogue/', ExtensionPackageCatalogueView.as_view(),
         name='extension-package-catalogue'),
]
