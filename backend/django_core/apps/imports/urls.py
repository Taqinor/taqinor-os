from django.urls import path

from . import views

urlpatterns = [
    path('specs/', views.import_specs, name='import-specs'),
    path('preview/', views.import_preview, name='import-preview'),
    path('confirm/', views.import_confirm, name='import-confirm'),
]
