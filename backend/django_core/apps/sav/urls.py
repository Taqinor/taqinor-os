from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import EquipementViewSet, TicketViewSet

router = DefaultRouter()
router.register(r'equipements', EquipementViewSet)
router.register(r'tickets', TicketViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
