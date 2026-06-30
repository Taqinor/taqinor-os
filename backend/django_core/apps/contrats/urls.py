from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlerteContratViewSet,
    AvenantViewSet,
    ClauseContratViewSet,
    ClauseViewSet,
    ContratLienViewSet,
    ContratViewSet,
    EngagementSLAViewSet,
    JalonContratViewSet,
    ModeleContratClauseViewSet,
    ModeleContratViewSet,
    ObligationViewSet,
    PartieContratViewSet,
    RegleApprobationViewSet,
    ResiliationViewSet,
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
router.register(r'resiliations', ResiliationViewSet)
router.register(r'alertes', AlerteContratViewSet)
router.register(r'jalons', JalonContratViewSet)
router.register(r'obligations', ObligationViewSet)
router.register(r'sla', EngagementSLAViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
