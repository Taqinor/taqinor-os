from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlerteContratViewSet,
    AvenantViewSet,
    ClauseContratViewSet,
    ClauseViewSet,
    ContratLienViewSet,
    ContratViewSet,
    ModeleContratClauseViewSet,
    ModeleContratViewSet,
    PartieContratViewSet,
    RegleApprobationViewSet,
    VersionContratViewSet,
)

router = DefaultRouter()
router.register(r'contrats', ContratViewSet)
router.register(r'parties', PartieContratViewSet)
router.register(r'contrat-liens', ContratLienViewSet)
router.register(r'modeles', ModeleContratViewSet)
router.register(r'clauses', ClauseViewSet)
router.register(r'modele-clauses', ModeleContratClauseViewSet)
router.register(r'clauses-contrat', ClauseContratViewSet)
router.register(r'regles-approbation', RegleApprobationViewSet)
router.register(r'versions', VersionContratViewSet)
router.register(r'avenants', AvenantViewSet)
router.register(r'alertes', AlerteContratViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
