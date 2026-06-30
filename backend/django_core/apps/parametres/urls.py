from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views_statuses import StatutConfigViewSet
from .views_email import EmailTemplateViewSet
from .views_approvals import ApprovalPolicyViewSet

# N58 — configuration d'affichage des statuts métier (chantier/SAV/BC).
# Routeur isolé (registre dédié) pour ne pas perturber les vues fonctions.
statuts_router = DefaultRouter()
statuts_router.register(r'statuts', StatutConfigViewSet,
                        basename='statut-config')

# FG17 — modèles d'e-mail éditables (parité WhatsApp). Routeur isolé pour ne pas
# perturber les vues fonctions.
emails_router = DefaultRouter()
emails_router.register(r'email-templates', EmailTemplateViewSet,
                       basename='email-template')

# FG25 — politiques d'approbation configurables. Routeur isolé.
approvals_router = DefaultRouter()
approvals_router.register(r'approbations', ApprovalPolicyViewSet,
                          basename='approval-policy')

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
    # FG18 — sections connues du journal d'audit (filtre UI).
    path('audit/sections/', views.settings_audit_sections),
    # FG24 — export/import de la configuration entre sociétés (admin).
    path('config-export/', views.config_export),
    path('config-import/', views.config_import),
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
    # FG17 — modèles d'e-mail éditables (sujet + corps), par société/clé.
    path('', include(emails_router.urls)),
    # FG25 — politiques d'approbation configurables (CRUD).
    path('', include(approvals_router.urls)),
]
