from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

from .views import (
    EquipementViewSet, TicketViewSet,
    SavSlaSettingsViewSet, MaintenanceChecklistTemplateViewSet,
    WarrantyClaimViewSet, KbArticleViewSet,
    sav_parts_forecast,
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


@api_view(['GET'])
@permission_classes([IsAnyRole])
def parts_forecast_view(request):
    """FG89 — Prévision de pièces SAV (interne, pas de prix achat)."""
    return sav_parts_forecast(request)


urlpatterns = [
    path('', include(router.urls)),
    path('insights/sav-parts-forecast/', parts_forecast_view,
         name='sav-parts-forecast'),
]
