"""Routes de planification supply chain (NTSCM), montées sous
``/api/django/scm/…`` via ``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClassificationABCViewSet, EvenementDemandeViewSet, PrevisionDemandeViewSet,
)

router = DefaultRouter()
router.register(
    r'previsions-demande', PrevisionDemandeViewSet, basename='scm-prevision-demande')
router.register(
    r'evenements-demande', EvenementDemandeViewSet, basename='scm-evenement-demande')
router.register(
    r'classification-abc', ClassificationABCViewSet, basename='scm-classification-abc')

urlpatterns = [
    path('', include(router.urls)),
]
