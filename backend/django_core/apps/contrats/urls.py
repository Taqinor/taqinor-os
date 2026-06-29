from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClauseContratViewSet,
    ClauseViewSet,
    ContratLienViewSet,
    ContratViewSet,
    ModeleContratClauseViewSet,
    ModeleContratViewSet,
    PartieContratViewSet,
)

router = DefaultRouter()
router.register(r'contrats', ContratViewSet)
router.register(r'parties', PartieContratViewSet)
router.register(r'contrat-liens', ContratLienViewSet)
router.register(r'modeles', ModeleContratViewSet)
router.register(r'clauses', ClauseViewSet)
router.register(r'modele-clauses', ModeleContratClauseViewSet)
router.register(r'clauses-contrat', ClauseContratViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
