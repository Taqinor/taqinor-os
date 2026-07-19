from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views_statuses import StatutConfigViewSet
from .views_email import EmailTemplateViewSet
from .views_approvals import ApprovalPolicyViewSet
from .views_translations import TranslationOverrideViewSet
from .views_referentiels import (
    ConditionPaiementViewSet,
    TauxTVAViewSet,
    UniteMesureViewSet,
)

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

# N94 — surcharges de traduction de l'interface (par langue/clé). Routeur isolé.
translations_router = DefaultRouter()
translations_router.register(r'traductions', TranslationOverrideViewSet,
                             basename='translation-override')

# WIR66 — référentiels société (TVA / conditions de paiement / unités de
# mesure), seedés au signup mais sans API jusqu'ici. Routeur isolé.
referentiels_router = DefaultRouter()
referentiels_router.register(r'taux-tva', TauxTVAViewSet,
                             basename='taux-tva')
referentiels_router.register(r'conditions-paiement', ConditionPaiementViewSet,
                             basename='condition-paiement')
referentiels_router.register(r'unites-mesure', UniteMesureViewSet,
                             basename='unite-mesure')

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
    # FG26 — purge RGPD du journal d'audit selon la fenêtre de rétention.
    path('audit/purge/', views.purge_audit_retention),
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
    # N94 — surcharges de traduction de l'interface (CRUD + bulk + effective).
    path('', include(translations_router.urls)),
    # WIR66 — référentiels société : taux de TVA, conditions de paiement,
    # unités de mesure (lecture tout rôle, écriture admin/responsable).
    path('', include(referentiels_router.urls)),
]
