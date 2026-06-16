from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_profile),
    path('update/', views.update_profile),
    path('upload-logo/', views.upload_logo),
    path('upload-signature/', views.upload_signature),
    path('delete-logo/', views.delete_logo),
    path('delete-signature/', views.delete_signature),
    # Modèles de message WhatsApp (FR + Darija) éditables.
    path('messages/', views.messages_endpoint),
    # Journal d'audit des changements de paramètres (admin, lecture seule).
    path('audit/', views.settings_audit_log),
]
