from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ContratMaintenanceViewSet, EquipementViewSet,
    ReclamationGarantieViewSet, TicketViewSet,
)

router = DefaultRouter()
router.register(r'equipements', EquipementViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'contrats', ContratMaintenanceViewSet)
router.register(r'reclamations-garantie', ReclamationGarantieViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
