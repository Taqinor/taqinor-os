"""Routes du registre des assurances & sinistres d'entreprise (NTASS).

Montées sous ``/api/django/assurances/…`` (et ``/api/v1/assurances/…``) via
``erp_agentique.urls``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssureurViewSet, CourtierViewSet

router = DefaultRouter()
router.register(r'assureurs', AssureurViewSet, basename='assurances-assureur')
router.register(r'courtiers', CourtierViewSet, basename='assurances-courtier')

urlpatterns = [
    path('', include(router.urls)),
]
