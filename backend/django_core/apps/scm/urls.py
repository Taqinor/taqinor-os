"""Routes de planification supply chain (NTSCM), montées sous
``/api/django/scm/…`` via ``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClassificationABCViewSet, EvenementDemandeViewSet, PolitiqueStockViewSet,
    PrevisionDemandeViewSet, creer_brouillons_bcf_reappro_view,
    tableau_bord_reappro_view,
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

urlpatterns = [
    # NTSCM7 — tableau de bord réappro consolidé (vues fonction, pas un
    # ViewSet : agrégat en lecture + action de création groupée, pas un CRUD).
    path(
        'tableau-bord-reappro/', tableau_bord_reappro_view,
        name='scm-tableau-bord-reappro'),
    path(
        'tableau-bord-reappro/creer-bcf/', creer_brouillons_bcf_reappro_view,
        name='scm-tableau-bord-reappro-creer-bcf'),
    path('', include(router.urls)),
]
