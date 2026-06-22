from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContratViewSet, PartieContratViewSet

router = DefaultRouter()
router.register(r'contrats', ContratViewSet)
router.register(r'parties', PartieContratViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
