from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AbonnementAddOnLigneViewSet,
    AddOnAbonnementViewSet,
    AlerteContratViewSet,
    AvenantViewSet,
    CautionViewSet,
    ClauseContratViewSet,
    ClauseViewSet,
    CompteurUsageViewSet,
    ContratLienViewSet,
    ContratViewSet,
    CycleFacturationLogViewSet,
    EcheancierContratViewSet,
    EngagementSLAViewSet,
    IndexationPrixViewSet,
    JalonContratViewSet,
    LigneEcheanceViewSet,
    ModeleContratClauseViewSet,
    ModeleContratViewSet,
    MotifResiliationViewSet,
    ObligationViewSet,
    OrdreLocationViewSet,
    PalierUsageViewSet,
    ParametresLocationViewSet,
    PartieContratViewSet,
    PieceConformiteViewSet,
    PlanAbonnementViewSet,
    PlanRecurrentViewSet,
    RegleApprobationViewSet,
    ResiliationViewSet,
    RetenueGarantieViewSet,
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
router.register(r'retenues-garantie', RetenueGarantieViewSet)
router.register(r'cautions', CautionViewSet)
router.register(r'echeanciers', EcheancierContratViewSet)
router.register(r'lignes-echeance', LigneEcheanceViewSet)
router.register(r'indexations', IndexationPrixViewSet)
router.register(r'pieces-conformite', PieceConformiteViewSet)
router.register(r'cycles-facturation', CycleFacturationLogViewSet)
router.register(r'ordres-location', OrdreLocationViewSet)
router.register(r'plans-recurrents', PlanRecurrentViewSet)
router.register(r'motifs-resiliation', MotifResiliationViewSet)
router.register(r'parametres-location', ParametresLocationViewSet)
router.register(r'plans-abonnement', PlanAbonnementViewSet)
router.register(r'addons-abonnement', AddOnAbonnementViewSet)
router.register(r'addon-lignes', AbonnementAddOnLigneViewSet)
router.register(r'paliers-usage', PalierUsageViewSet)
router.register(r'compteurs-usage', CompteurUsageViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
