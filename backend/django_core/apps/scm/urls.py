"""Routes de planification supply chain (NTSCM), montées sous
``/api/django/scm/…`` via ``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClassificationABCViewSet, CyclePlanificationSOPViewSet, EvenementDemandeViewSet,
    PolitiqueStockViewSet, PrevisionDemandeViewSet,
    anomalies_demande_view, creer_brouillons_bcf_reappro_view,
    detecter_anomalies_demande_view, export_ecarts_prevision_view,
    parametres_sop_view, precision_previsions_view,
    proposer_allocation_penurie_view, simuler_rupture_view,
    suggestions_achat_groupe_view, suggestions_transfert_view,
    tableau_bord_executif_view, tableau_bord_reappro_view,
)

router = DefaultRouter()
router.register(
    r'previsions-demande', PrevisionDemandeViewSet, basename='scm-prevision-demande')
router.register(
    r'evenements-demande', EvenementDemandeViewSet, basename='scm-evenement-demande')
router.register(
    r'classification-abc', ClassificationABCViewSet, basename='scm-classification-abc')
router.register(
    r'politiques-stock', PolitiqueStockViewSet, basename='scm-politique-stock')
router.register(
    r'cycles-sop', CyclePlanificationSOPViewSet, basename='scm-cycle-sop')

urlpatterns = [
    # NTSCM7 — tableau de bord réappro consolidé (vues fonction, pas un
    # ViewSet : agrégat en lecture + action de création groupée, pas un CRUD).
    path(
        'tableau-bord-reappro/', tableau_bord_reappro_view,
        name='scm-tableau-bord-reappro'),
    path(
        'tableau-bord-reappro/creer-bcf/', creer_brouillons_bcf_reappro_view,
        name='scm-tableau-bord-reappro-creer-bcf'),
    # NTSCM16 — suggestions d'achat groupées multi-fournisseurs (MOQ/paliers).
    path(
        'suggestions-achat-groupe/', suggestions_achat_groupe_view,
        name='scm-suggestions-achat-groupe'),
    # NTSCM18/19 — simulation « et si… » et allocation en pénurie, par produit
    # (Produit appartient à `apps.stock`, pas `apps.scm` : vue-fonction avec
    # `produit_id` en paramètre d'URL, pas un ViewSet).
    path(
        'produits/<int:produit_id>/simuler/', simuler_rupture_view,
        name='scm-produit-simuler'),
    path(
        'produits/<int:produit_id>/proposer-allocation/',
        proposer_allocation_penurie_view, name='scm-produit-proposer-allocation'),
    # NTSCM20 — suggestions de transfert inter-sites (anticipatif).
    path(
        'suggestions-transfert/', suggestions_transfert_view,
        name='scm-suggestions-transfert'),
    # NTSCM24 — précision de prévision auto-mesurée (MAPE).
    path(
        'precision-previsions/', precision_previsions_view,
        name='scm-precision-previsions'),
    # NTSCM32 — export .xlsx du rapport « Écarts de prévision ».
    path(
        'precision-previsions/export/', export_ecarts_prevision_view,
        name='scm-precision-previsions-export'),
    # NTSCM28 — tableau de bord SCM exécutif (KPI de synthèse).
    path('tableau-bord/', tableau_bord_executif_view, name='scm-tableau-bord'),
    # NTSCM25 — anomalies de demande (pic/creux inattendu).
    path(
        'anomalies-demande/', anomalies_demande_view, name='scm-anomalies-demande'),
    path(
        'anomalies-demande/detecter/', detecter_anomalies_demande_view,
        name='scm-anomalies-demande-detecter'),
    # NTSCM22 — réglages opt-in du cycle S&OP automatique (singleton société).
    path('parametres-sop/', parametres_sop_view, name='scm-parametres-sop'),
    path('', include(router.urls)),
]
