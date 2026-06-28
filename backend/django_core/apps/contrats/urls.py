from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContratLienViewSet,
    ContratViewSet,
    ModeleContratViewSet,
    PartieContratViewSet,
)

router = DefaultRouter()
router.register(r'contrats', ContratViewSet)
router.register(r'parties', PartieContratViewSet)
router.register(r'contrat-liens', ContratLienViewSet)
router.register(r'modeles', ModeleContratViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
