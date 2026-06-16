from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ContratMaintenanceViewSet, EquipementViewSet, TicketViewSet,
)

router = DefaultRouter()
router.register(r'equipements', EquipementViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'contrats', ContratMaintenanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
