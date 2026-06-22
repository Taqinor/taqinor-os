from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContratLienViewSet, ContratViewSet, PartieContratViewSet

router = DefaultRouter()
router.register(r'contrats', ContratViewSet)
router.register(r'parties', PartieContratViewSet)
router.register(r'contrat-liens', ContratLienViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
