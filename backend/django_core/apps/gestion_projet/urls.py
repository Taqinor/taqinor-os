from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DependanceTacheViewSet,
    PhaseProjetViewSet,
    ProjetChantierViewSet,
    ProjetLienViewSet,
    ProjetViewSet,
    TacheViewSet,
)

router = DefaultRouter()
router.register(r'projets', ProjetViewSet)
router.register(r'projet-chantiers', ProjetChantierViewSet)
router.register(r'projet-liens', ProjetLienViewSet)
router.register(r'phases', PhaseProjetViewSet)
router.register(r'taches', TacheViewSet)
router.register(r'dependances', DependanceTacheViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
