from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import EquipementViewSet, TicketViewSet
from .maintenance import ContratMaintenanceViewSet

router = DefaultRouter()
router.register(r'equipements', EquipementViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'contrats-maintenance', ContratMaintenanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
