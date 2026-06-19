from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views_statuses import StatutConfigViewSet

# N58 — configuration d'affichage des statuts métier (chantier/SAV/BC).
# Routeur isolé (registre dédié) pour ne pas perturber les vues fonctions.
statuts_router = DefaultRouter()
statuts_router.register(r'statuts', StatutConfigViewSet,
                        basename='statut-config')

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
    # D2/N60/N67/N26/N59 — modèles de documents éditables (textes du devis).
    path('document-templates/', views.get_document_templates),
    path('document-templates/update/', views.update_document_templates),
    # N64/N65 — tarification ONEE + hypothèses ROI/productible éditables.
    path('tarification/', views.get_tariff_settings),
    path('tarification/update/', views.update_tariff_settings),
    path('tarification/roi/', views.compute_roi),
    path('tarification/productible/', views.get_productible),
    # N58 — statuts configurables (libellé/ordre/visibilité), couche affichage.
    path('', include(statuts_router.urls)),
]
