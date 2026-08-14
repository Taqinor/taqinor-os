"""Routes de planification supply chain (NTSCM), montées sous
``/api/django/scm/…`` via ``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EvenementDemandeViewSet, PrevisionDemandeViewSet

router = DefaultRouter()
router.register(
    r'previsions-demande', PrevisionDemandeViewSet, basename='scm-prevision-demande')
router.register(
    r'evenements-demande', EvenementDemandeViewSet, basename='scm-evenement-demande')

urlpatterns = [
    path('', include(router.urls)),
]
