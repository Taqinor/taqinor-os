from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes

from authentication.permissions import IsAnyRole

from .views import (
    EquipementViewSet, TicketViewSet,
    SavSlaSettingsViewSet, MaintenanceChecklistTemplateViewSet,
    WarrantyClaimViewSet, KbArticleViewSet, AlarmeOnduleurViewSet,
    CauseDefaillanceViewSet, RemedeDefaillanceViewSet, ReponseTypeViewSet,
    CompatibilitePieceViewSet, CategorieTicketViewSet,
    sav_parts_forecast, sav_pareto_pannes, sav_fiabilite_insight,
)
from .maintenance import ContratMaintenanceViewSet

router = DefaultRouter()
router.register(r'equipements', EquipementViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'contrats-maintenance', ContratMaintenanceViewSet)
router.register(r'sla-settings', SavSlaSettingsViewSet)
router.register(r'checklist-templates', MaintenanceChecklistTemplateViewSet)
router.register(r'warranty-claims', WarrantyClaimViewSet)
router.register(r'kb-articles', KbArticleViewSet)
router.register(r'alarmes-onduleur', AlarmeOnduleurViewSet)
router.register(r'causes-defaillance', CauseDefaillanceViewSet)
router.register(r'remedes-defaillance', RemedeDefaillanceViewSet)
router.register(r'reponses-type', ReponseTypeViewSet)
router.register(r'compatibilites-piece', CompatibilitePieceViewSet)
router.register(r'categories-ticket', CategorieTicketViewSet)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def parts_forecast_view(request):
    """FG89 — Prévision de pièces SAV (interne, pas de prix achat)."""
    return sav_parts_forecast(request)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def pareto_pannes_view(request):
    """XSAV14 — Pareto des pannes par modèle de produit / fournisseur."""
    return sav_pareto_pannes(request)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def fiabilite_insight_view(request):
    """XSAV15 — MTBF/MTTR/coût cumulé, vue d'ensemble du parc."""
    return sav_fiabilite_insight(request)


urlpatterns = [
    path('', include(router.urls)),
    path('insights/sav-parts-forecast/', parts_forecast_view,
         name='sav-parts-forecast'),
    path('insights/sav-pannes/', pareto_pannes_view,
         name='sav-pareto-pannes'),
    path('insights/sav-fiabilite/', fiabilite_insight_view,
         name='sav-fiabilite'),
]
